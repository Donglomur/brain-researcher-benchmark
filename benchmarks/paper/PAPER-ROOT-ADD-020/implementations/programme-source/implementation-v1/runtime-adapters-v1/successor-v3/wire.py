"""Bounded typed values, immutable files and lossless guardian output transport.

No pickle, object dtype, compressed stream, arbitrary type import or executable
deserializer. Scientific NaN/Inf are allowed only inside explicitly typed arrays.
"""
import base64
import dataclasses
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import uuid
import numpy as np

SCHEMA = "paper020_wire_manifest_v1"

@dataclasses.dataclass(frozen=True)
class IndexManifest:
    unfamiliar: tuple
    familiar: tuple
    matched: tuple
    ancillary: tuple
    subsets: tuple
    role_qualification_sha256: str
    sampling_qualification_sha256: str | None = None
    sampling_procedure: str | None = None

class WireError(ValueError): pass

def need(ok, message):
    if not ok: raise WireError(message)

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()

def sha(raw): return hashlib.sha256(raw).hexdigest()

def parse(raw, maximum):
    need(type(raw) is bytes and len(raw) <= maximum, "JSON extent exceeds admitted bound")
    def pairs(items):
        out = {}
        for k, v in items:
            need(k not in out, "Duplicate JSON key")
            out[k] = v
        return out
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda x: (_ for _ in ()).throw(WireError("Nonfinite JSON")))

@dataclasses.dataclass(frozen=True)
class WireLimits:
    bytes: int
    metadata: int
    nodes: int
    depth: int = 64
    def validate(self):
        need(all(type(x) is int and x > 0 for x in dataclasses.astuple(self)), "Positive wire limits required")
        need(self.depth <= 128, "Wire nesting ceiling exceeded")

def encode(value, limits):
    limits.validate(); blobs = {}; count = 0; total = 0
    def blob(raw):
        nonlocal total
        key = sha(raw)
        if key not in blobs:
            total += len(raw); need(total <= limits.bytes, "Complete wire blob budget exceeded")
            blobs[key] = raw
        return key
    def node(x, depth=0):
        nonlocal count
        count += 1; need(count <= limits.nodes and depth <= limits.depth, "Typed node bound exceeded")
        if x is None or type(x) in (bool, int, str): return ["scalar", x]
        if type(x) is float:
            need(math.isfinite(x), "Nonfinite scalar metadata"); return ["scalar", x]
        if isinstance(x, np.ndarray):
            need(x.dtype.kind in "fiubU" and not x.dtype.hasobject and x.ndim <= 8,
                 "Only explicit real numeric/bool/unicode arrays accepted")
            a = np.ascontiguousarray(x); raw = a.tobytes(order="C")
            return ["array", a.dtype.str, list(a.shape), blob(raw)]
        if type(x) is bytes: return ["bytes", blob(x)]
        if type(x) in (list, tuple): return ["tuple" if type(x) is tuple else "list", [node(v, depth+1) for v in x]]
        if type(x) is dict:
            need(all(type(k) in (str, tuple) for k in x), "Only string/tuple map keys accepted")
            return ["map", [[node(k, depth+1), node(v, depth+1)] for k,v in x.items()]]
        if dataclasses.is_dataclass(x) and type(x).__name__=="IndexManifest" and \
                [f.name for f in dataclasses.fields(x)]==[f.name for f in dataclasses.fields(IndexManifest)]:
            return ["IndexManifest", node({f.name:getattr(x,f.name) for f in dataclasses.fields(x)}, depth+1)]
        raise WireError("Unapproved wire type: " + type(x).__name__)
    root = node(value)
    manifest = canonical({"schema":SCHEMA, "root":root, "blobs":{
        k:{"file":k+".bin", "bytes":len(v), "sha256":k} for k,v in sorted(blobs.items())}})
    need(len(manifest) <= limits.metadata, "Complete wire metadata budget exceeded")
    return manifest, blobs

def decode(manifest, blobs, limits):
    limits.validate(); m = parse(manifest, limits.metadata)
    need(type(m) is dict and set(m)=={"schema","root","blobs"} and m["schema"]==SCHEMA,
         "Exact wire manifest required")
    need(type(blobs) is dict and set(blobs)==set(m["blobs"]), "Complete exact blob set required")
    total = 0
    for k, info in m["blobs"].items():
        need(re.fullmatch("[0-9a-f]{64}", k) is not None and type(info) is dict
             and set(info)=={"file","bytes","sha256"} and info["file"]==k+".bin" and info["sha256"]==k,
             "Exact content-addressed blob declaration required")
        raw = blobs[k]; need(type(raw) is bytes and type(info["bytes"]) is int and len(raw)==info["bytes"]
                            and sha(raw)==k, "Blob size/content mismatch")
        total += len(raw); need(total <= limits.bytes, "Complete blob bound exceeded")
    count = 0; used = set()
    def node(n, depth=0):
        nonlocal count
        count += 1; need(count <= limits.nodes and depth <= limits.depth, "Typed node bound exceeded")
        need(type(n) is list and n and type(n[0]) is str, "Malformed typed node")
        tag=n[0]
        if tag=="scalar":
            need(len(n)==2 and (n[1] is None or type(n[1]) in (bool,int,float,str)), "Plain scalar required")
            if type(n[1]) is float: need(math.isfinite(n[1]), "Nonfinite metadata")
            return n[1]
        if tag in ("tuple","list"):
            need(len(n)==2 and type(n[1]) is list, "Sequence node required")
            values=[node(x,depth+1) for x in n[1]]; return tuple(values) if tag=="tuple" else values
        if tag=="map":
            need(len(n)==2 and type(n[1]) is list, "Map node required"); out={}
            for pair in n[1]:
                need(type(pair) is list and len(pair)==2, "Map pair required")
                k=node(pair[0],depth+1)
                need(type(k) in (str,tuple) and k not in out, "Duplicate/unapproved map key")
                out[k]=node(pair[1],depth+1)
            return out
        if tag=="IndexManifest":
            need(len(n)==2, "Exact index manifest required")
            cls=IndexManifest; fields=node(n[1],depth+1)
            need(type(fields) is dict and set(fields)=={f.name for f in dataclasses.fields(cls)}, "Index fields differ")
            return cls(**fields)
        if tag in ("array","bytes"):
            need(len(n)==(4 if tag=="array" else 2) and n[-1] in blobs, "Blob reference absent")
            raw=blobs[n[-1]]; used.add(n[-1])
            if tag=="bytes": return raw
            dtype=np.dtype(n[1]); shape=n[2]
            need(dtype.kind in "fiubU" and not dtype.hasobject and dtype.itemsize>0
                 and type(shape) is list and len(shape)<=8 and all(type(x) is int and x>=0 for x in shape),
                 "Invalid array dtype/shape")
            expected=math.prod(shape)*dtype.itemsize
            need(expected==len(raw) and expected<=limits.bytes, "Array extent differs")
            value=np.frombuffer(raw,dtype=dtype).reshape(tuple(shape)); value.flags.writeable=False
            return value
        raise WireError("Unapproved node tag")
    out=node(m["root"]); need(used==set(blobs), "Undeclared unused blob exposure")
    return out

def bundle_bytes(manifest, blobs):
    return canonical({"manifest_base64":base64.b64encode(manifest).decode(),
                      "blobs_base64":{k:base64.b64encode(v).decode() for k,v in blobs.items()}})

def decode_bundle(raw, limits):
    cap=2*(limits.bytes+limits.metadata)+4096
    bundle=parse(raw,cap)
    need(type(bundle) is dict and set(bundle)=={"manifest_base64","blobs_base64"}
         and type(bundle["blobs_base64"]) is dict, "Exact guardian bundle required")
    manifest=base64.b64decode(bundle["manifest_base64"],validate=True)
    blobs={k:base64.b64decode(v,validate=True) for k,v in bundle["blobs_base64"].items()}
    return decode(manifest,blobs,limits)

def _read(path, cap):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        before=os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size<=cap, "Unsafe/oversized immutable file")
        raw=bytearray()
        while len(raw)<before.st_size:
            chunk=os.read(fd,min(65536,before.st_size-len(raw)))
            need(bool(chunk),"Short immutable read");raw.extend(chunk)
        after=os.fstat(fd)
        need((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==
             (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns),"Immutable file changed")
        return bytes(raw)
    finally: os.close(fd)

def _write(path, raw):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400)
    try:
        view=memoryview(raw)
        while view:
            n=os.write(fd,view);need(n>0,"Short immutable write");view=view[n:]
        os.fsync(fd)
    finally: os.close(fd)

def write_wire(root, value, limits):
    root=Path(root); need(not root.exists(), "Fresh immutable artifact directory required")
    root.mkdir(mode=0o700)
    manifest,blobs=encode(value,limits)
    for k,raw in blobs.items(): _write(root/(k+".bin"),raw)
    _write(root/"result.json",manifest); os.chmod(root,0o500)
    return sha(manifest)

def read_wire(root, limits):
    root=Path(root); need(not root.is_symlink() and root.is_dir(),"Immutable directory required")
    manifest=_read(root/"result.json",limits.metadata);m=parse(manifest,limits.metadata)
    need(type(m) is dict and type(m.get("blobs")) is dict,"Wire declaration missing")
    keys=set(m["blobs"])
    need(all(re.fullmatch("[0-9a-f]{64}",k) for k in keys),"Unsafe blob filename")
    need(all(type(v) is dict and type(v.get("bytes")) is int and v["bytes"]>=0 for v in m["blobs"].values())
         and sum(v["bytes"] for v in m["blobs"].values())<=limits.bytes,"Complete blob extent exceeds admitted budget")
    need({p.name for p in root.iterdir()}=={"result.json"}|{k+".bin" for k in keys},"Extra/missing artifact members")
    blobs={k:_read(root/(k+".bin"),limits.bytes) for k in keys}
    return decode(manifest,blobs,limits)

class ImmutableStore:
    """Operator-owned store. Only selected files, never its root, enter a worker."""
    def __init__(self,root,limits,authority,capability):
        authority.require_store(capability,str(root))
        self.root=Path(root); self.limits=limits; self.handles={}
        need(self.root.is_absolute() and not self.root.is_symlink() and self.root.is_dir(),"Prequalified private store root required")
        need(stat.S_IMODE(self.root.stat().st_mode)==0o700,"Private store root mode must be 0700")
    def put(self,kind,value,context,binding):
        from .basis import basis
        handle=uuid.uuid4().hex; path=self.root/handle
        seal=write_wire(path,value,self.limits)
        fingerprint=seal if kind=="native_capture_evidence" else basis("dispatcher").artifact_fingerprint(value)
        self.handles[handle]=(context,binding,kind,seal,fingerprint)
        return {"handle":handle,"artifact_digest":fingerprint}
    def get(self,handle,context):
        need(handle in self.handles and self.handles[handle][0]==context,"Cross-context/unknown store handle")
        record=self.handles[handle];path=self.root/handle
        need(sha(_read(path/"result.json",self.limits.metadata))==record[3],"Stored manifest mutated")
        value=read_wire(path,self.limits)
        from .basis import basis
        actual=record[3] if record[2]=="native_capture_evidence" else basis("dispatcher").artifact_fingerprint(value)
        need(actual==record[4],"Stored typed value mutated")
        return value
