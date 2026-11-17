"""Prospective complete MATLAB-v5 schema census. Never run implicitly on import.
The source is unexecuted. A separate exact native operation must be selected.
No numerical package is imported until runtime and original-file gates pass.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import shutil
import signal
import stat
import struct
import subprocess
import sys
import time
import warnings

DATA = Path("/Users/nicholas/Documents/Codex/benchmark-engineering-evidence/vestibular-vo-authentic-intake-20261114-v1/VO_dataset.mat")
DEST = Path("/Users/nicholas/Documents/Codex/benchmark-engineering-evidence/vestibular-vo-schema-census-20261114-v1")
EXPECTED_BYTES = 180725660
EXPECTED_MD5 = "852fd759272db2e9be69356264b032ca"
EXPECTED_SHA = "3db6c47e61f51230ea4a83b5722f1c019337ab09f7ad836b36ce934a0270ca86"
GIB = 1024**3
MAX_RUNTIME_BYTES = 128*1024**2
MAX_FILE_READ_BYTES = 3*EXPECTED_BYTES+8*1024**2
MAX_CENSUS_BYTES = 16*1024**2
MAX_ARRAY_BYTES = 2*GIB
MAX_TEXT_BYTES = 256*1024
MAX_NODES = 100000
MAX_DEPTH = 64
SCALAR_METADATA_NAMES = frozenset({
    "fs", "Fs", "samplingrate", "samplingfrequency", "samplerate", "dt", "timestep",
    "animal", "animalid", "monkey", "monkeyid", "neuronid", "unitid",
    "cellid", "pairid", "sessionid", "trialid", "repeatid", "conditionid",
    "frequency", "stimulusfrequency", "amplitude", "stimulusamplitude"
})

REFUSAL_CODES = frozenset(["regular single-link file required","file extent pin mismatch","file read budget exceeded","file ended before pinned extent","file grew past pinned extent","file identity changed during read","SHA256 pin mismatch","symlink output parent refused","output namespace already exists","host metadata limit","12GiB memory / 3GiB disk guard failed","unexpected package root","runtime read cap","invalid or duplicate runtime member","runtime member coverage mismatch","MAT reader byte budget","invalid seek mode","out-of-original seek","complete census output budget","complete tree depth/node budget","unsupported MATLAB object/function/opaque class","unsupported sparse storage format","decoded-array accounting budget","invalid array dimensions","complete text metadata budget","unsupported decoded value type","duplicate/reserved top variable","unsupported top-level MATLAB class","top-variable coverage mismatch","original checksum mismatch","original must remain read-only","unsupported MATLAB header","only MAT-v5 family selected; no HDF5 fallback","imported package version mismatch","original stat changed","census_deadline"])

class Refusal(RuntimeError):
    """An authored static refusal code; arbitrary third-party text is never public."""
    def __init__(self, code):
        self.code = code
        super().__init__(code)

def failure_record(error):
    result = {"type":type(error).__name__}
    if type(error) is Refusal:
        result["code"] = (error.code if error.code in REFUSAL_CODES
                          else "unrecognized_refusal")
    return result

def digest_file(path, expected_size=None, byte_cap=None, ledger=None):
    st = path.lstat()
    if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
        raise Refusal("regular single-link file required")
    if expected_size is not None and st.st_size != expected_size:
        raise Refusal("file extent pin mismatch")
    limit = st.st_size if byte_cap is None else byte_cap
    if st.st_size > limit:
        raise Refusal("file read budget exceeded")
    h = hashlib.sha256()
    m = hashlib.md5()
    count = 0
    prefix = bytearray()
    with path.open("rb") as stream:
        while count < st.st_size:
            block = stream.read(min(262144, st.st_size-count))
            if not block:
                raise Refusal("file ended before pinned extent")
            count += len(block)
            if ledger is not None:
                ledger["bytes"] += len(block)
            h.update(block)
            m.update(block)
            if len(prefix) < 1024:
                prefix.extend(block[:1024-len(prefix)])
        extra = stream.read(1)
        if ledger is not None:
            ledger["bytes"] += len(extra)
        if extra:
            raise Refusal("file grew past pinned extent")
    aft = path.lstat()
    if (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns) != (
            aft.st_dev, aft.st_ino, aft.st_size, aft.st_mtime_ns, aft.st_ctime_ns):
        raise Refusal("file identity changed during read")
    return {"bytes": count, "sha256": h.hexdigest(), "md5": m.hexdigest()}, bytes(prefix)

def pin(path, size, sha256, ledger=None):
    observed, _ = digest_file(path, size, size, ledger)
    if observed["sha256"] != sha256:
        raise Refusal("SHA256 pin mismatch")
    return observed

def host_guard():
    for path in (DEST.parent, *DEST.parent.parents):
        if path.is_symlink():
            raise Refusal("symlink output parent refused")
    if DEST.exists() or DEST.is_symlink():
        raise Refusal("output namespace already exists")
    raw = subprocess.run(["/usr/bin/vm_stat"], check=True,
                         capture_output=True, timeout=5).stdout
    if len(raw) > 16384:
        raise Refusal("host metadata limit")
    text = raw.decode("ascii")
    page = int(text.split("page size of ", 1)[1].split(" bytes", 1)[0])
    values = {k: int(v.strip().rstrip(".")) for line in text.splitlines()[1:]
              if ":" in line for k, v in [line.split(":", 1)]}
    available = page*sum(values[k] for k in
        ("Pages free", "Pages inactive", "Pages speculative"))
    disk = shutil.disk_usage(DEST.parent).free
    if available < 12*GIB or disk < 3*GIB:
        raise Refusal("12GiB memory / 3GiB disk guard failed")
    return {"available_memory_estimate": available, "free_disk": disk,
            "ledger": "5GiB other +6GiB process address-space cap +1GiB headroom"}

def verify_inventory(inventory, ledger=None):
    site = Path(inventory["site_root"])
    if site != Path("/opt/homebrew/lib/python3.11/site-packages"):
        raise Refusal("unexpected package root")
    used = 0
    for dist in inventory["distributions"]:
        for item in dist["metadata"]:
            used += item["bytes"]
            if used > MAX_RUNTIME_BYTES:
                raise Refusal("runtime read cap")
            pin(Path(item["path"]), item["bytes"], item["sha256"], ledger)
    names = set()
    for item in inventory["hashed_importable_members"]:
        rel = Path(item["relative_path"])
        if rel.is_absolute() or ".." in rel.parts or str(rel) in names:
            raise Refusal("invalid or duplicate runtime member")
        names.add(str(rel))
        used += item["bytes"]
        if used > MAX_RUNTIME_BYTES:
            raise Refusal("runtime read cap")
        pin(site/rel, item["bytes"], item["sha256"], ledger)
    if len(names) != inventory["member_count"]:
        raise Refusal("runtime member coverage mismatch")
    return used

class BoundedFile:
    """One file object shared across complete variable census and load."""
    def __init__(self, path, budget):
        self.file = path.open("rb")
        self.used = 0
        self.budget = budget
    def read(self, size=-1):
        if size is None or size < 0:
            size = EXPECTED_BYTES-self.file.tell()
        if size > self.budget-self.used:
            raise Refusal("MAT reader byte budget")
        data = self.file.read(size)
        self.used += len(data)
        return data
    def seek(self, offset, whence=0):
        if whence == 0:
            target = offset
        elif whence == 1:
            target = self.file.tell()+offset
        elif whence == 2:
            target = EXPECTED_BYTES+offset
        else:
            raise Refusal("invalid seek mode")
        if not 0 <= target <= EXPECTED_BYTES:
            raise Refusal("out-of-original seek")
        return self.file.seek(target)
    def tell(self):
        return self.file.tell()
    def close(self):
        self.file.close()

class Emitter:
    def __init__(self, output, np, sparse):
        self.output = output
        self.np = np
        self.sparse = sparse
        self.nodes = 0
        self.bytes = 0
        self.array_bytes = 0
        self.text_bytes = 0
        self.seen = {}
        self.scalar_candidates = []
    def emit(self, row):
        encoded = (json.dumps(row, allow_nan=False, ensure_ascii=True,
                              separators=(",", ":"))+"\n").encode()
        if len(encoded) > 65536 or self.bytes+len(encoded) > MAX_CENSUS_BYTES:
            raise Refusal("complete census output budget")
        self.output.write(encoded)
        self.bytes += len(encoded)
    def walk(self, value, path, field_name=None, depth=0):
        if depth > MAX_DEPTH or self.nodes >= MAX_NODES:
            raise Refusal("complete tree depth/node budget")
        self.nodes += 1
        np = self.np
        row = {"path": path, "node": self.nodes}
        # Do not mistake MATLAB functions/opaque/object subclasses for ordinary
        # record arrays. No function reconstruction or execution is supported.
        if type(value).__name__ in ("MatlabObject", "MatlabFunction", "MatlabOpaque"):
            raise Refusal("unsupported MATLAB object/function/opaque class")
        if isinstance(value, np.ndarray) or self.sparse.issparse(value):
            key = id(value)
            if key in self.seen:
                row.update(kind="memory_alias", first_path=self.seen[key][0],
                           biological_identity_inferred=False)
                self.emit(row)
                return
            self.seen[key] = (path, value)  # Retain objects: prevent ID reuse.
        if self.sparse.issparse(value):
            if value.format != "csc":
                raise Refusal("unsupported sparse storage format")
            total = value.data.nbytes+value.indices.nbytes+value.indptr.nbytes
            self.array_bytes += total
            if self.array_bytes > MAX_ARRAY_BYTES:
                raise Refusal("decoded-array accounting budget")
            row.update(kind="sparse_array", shape=list(value.shape),
                       dtype=str(value.dtype), nnz=int(value.nnz),
                       storage_bytes=int(total), values_disclosed=False)
            self.emit(row)
            return
        if isinstance(value, np.ndarray):
            shape = [int(x) for x in value.shape]
            if any(x < 0 for x in shape):
                raise Refusal("invalid array dimensions")
            self.array_bytes += int(value.nbytes)
            if self.array_bytes > MAX_ARRAY_BYTES:
                raise Refusal("decoded-array accounting budget")
            row.update(kind="array", shape=shape, dtype=str(value.dtype),
                       elements=int(value.size), storage_bytes=int(value.nbytes),
                       values_disclosed=False)
            if value.dtype.names:
                fields = list(value.dtype.names)
                row.update(kind="struct_array", fields=fields)
                self.emit(row)
                for k in range(value.size):
                    idx = tuple(int(x) for x in np.unravel_index(k, value.shape, order="F"))
                    for field in fields:
                        self.walk(value[idx][field], path+[{"index":list(idx)}, field],
                                  field, depth+1)
                return
            if value.dtype.kind == "O":
                row["kind"] = "cell_array"
                self.emit(row)
                for k in range(value.size):
                    idx = tuple(int(x) for x in np.unravel_index(k, value.shape, order="F"))
                    self.walk(value[idx], path+[{"index":list(idx)}],
                              field_name, depth+1)
                return
            if value.dtype.kind in ("U", "S"):
                text_values = [str(x) if value.dtype.kind == "U"
                               else bytes(x).decode("utf-8", errors="strict")
                               for x in value.ravel(order="F")]
                text_size = sum(len(x.encode("utf-8")) for x in text_values)
                self.text_bytes += text_size
                if self.text_bytes > MAX_TEXT_BYTES:
                    raise Refusal("complete text metadata budget")
                row.update(kind="text_array", text_values=text_values,
                           values_disclosed=True, custody="private metadata only")
            elif value.size == 1 and field_name is not None:
                if field_name in SCALAR_METADATA_NAMES and value.dtype.kind in "biuf":
                    scalar = value.item()
                    if isinstance(scalar, float) and not math.isfinite(scalar):
                        row["scalar_metadata"] = {"nonfinite":str(scalar)}
                    else:
                        row["scalar_metadata"] = {"dtype":str(value.dtype),
                            "value_decimal":("1" if scalar else "0") if isinstance(scalar,bool) else str(scalar),
                            "encoding":"exact decimal string; boolean0/1"}
                    row["values_disclosed"] = True
                    row["semantic_role"] = "name-matched metadata candidate; unverified"
                    self.scalar_candidates.append(path)
            self.emit(row)
            return
        if isinstance(value, np.void) and value.dtype.names:
            row.update(kind="struct_scalar", fields=list(value.dtype.names))
            self.emit(row)
            for field in value.dtype.names:
                self.walk(value[field], path+[field], field, depth+1)
            return
        # MATLAB-compatible reading is configured not to squeeze numeric arrays.
        # Unexpected Python values are not silently converted or skipped.
        raise Refusal("unsupported decoded value type")

def read_all_variables(stream, sio):
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        top = sio.whosmat(stream,appendmat=False,
                          verify_compressed_data_integrity=True)
        names = [x[0] for x in top]
        if len(names) != len(set(names)) or any(n.startswith("__") for n in names):
            raise Refusal("duplicate/reserved top variable")
        allowed = {"int8","uint8","int16","uint16","int32","uint32",
                   "int64","uint64","single","double","cell","struct",
                   "char","sparse","logical"}
        if any(item[2] not in allowed for item in top):
            raise Refusal("unsupported top-level MATLAB class")
        stream.seek(0)
        loaded = sio.loadmat(stream,appendmat=False,spmatrix=True,
            squeeze_me=False,chars_as_strings=False,struct_as_record=True,
            mat_dtype=False,simplify_cells=False,uint16_codec="utf-8",
            verify_compressed_data_integrity=True,variable_names=None)
    observed = set(loaded)-{"__header__","__version__","__globals__"}
    if observed != set(names):
        raise Refusal("top-variable coverage mismatch")
    return top, names, loaded

def alarm(*_):
    raise Refusal("census_deadline")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--inventory-sha256", required=True)
    parser.add_argument("--runtime-sha256", required=True)
    args = parser.parse_args()
    src = Path(__file__).resolve()
    pin(src, src.stat().st_size, args.source_sha256)
    runtime = Path(sys.executable).resolve()
    pin(runtime, 52640, args.runtime_sha256)
    inv_path = src.parent.parent/"RUNTIME_INVENTORY.json"
    pin(inv_path, 482675, args.inventory_sha256)
    inventory = json.loads(inv_path.read_bytes())
    guard = host_guard()
    # Unsupported hard-limit setup is a preflight failure, not a silent fallback.
    resource.setrlimit(resource.RLIMIT_AS, (6*GIB,6*GIB))
    resource.setrlimit(resource.RLIMIT_CPU, (180,190))
    resource.setrlimit(resource.RLIMIT_FSIZE, (20*1024**2,20*1024**2))
    DEST.mkdir(mode=0o700)
    for name in ("OPENBLAS_NUM_THREADS","OMP_NUM_THREADS","MKL_NUM_THREADS",
                 "VECLIB_MAXIMUM_THREADS","NUMEXPR_NUM_THREADS"):
        os.environ[name] = "1"
    sys.dont_write_bytecode = True
    sys.pycache_prefix = str(DEST/"unused-pycache")
    started = time.monotonic()
    signal.signal(signal.SIGALRM, alarm)
    signal.setitimer(signal.ITIMER_REAL,300)
    accepted = False
    failure = None
    before = DATA.lstat()
    stream = None
    emitter = None
    runtime_ledger = {"bytes":0}
    original_ledger = {"bytes":0}
    runtime_verification_complete = False
    original_hash_complete = False
    file_read_bytes = 0
    top = []
    partial = DEST/"PRIVATE_SCHEMA_CENSUS.partial.jsonl"
    try:
        verify_inventory(inventory,runtime_ledger)
        runtime_verification_complete = True
        original, header = digest_file(DATA, EXPECTED_BYTES, EXPECTED_BYTES,original_ledger)
        original_hash_complete = True
        file_read_bytes = original_ledger["bytes"]
        if original["sha256"] != EXPECTED_SHA or original["md5"] != EXPECTED_MD5:
            raise Refusal("original checksum mismatch")
        if before.st_mode & 0o222:
            raise Refusal("original must remain read-only")
        if len(header) < 128 or header[126:128] not in (b"IM",b"MI"):
            raise Refusal("unsupported MATLAB header")
        order = "<" if header[126:128] == b"IM" else ">"
        if struct.unpack(order+"H",header[124:126])[0] != 0x0100:
            raise Refusal("only MAT-v5 family selected; no HDF5 fallback")
        sys.path.insert(0,inventory["site_root"])
        import numpy as np
        import scipy
        import scipy.io as sio
        import scipy.sparse as sparse
        if np.__version__ != "2.4.6" or scipy.__version__ != "1.17.1":
            raise Refusal("imported package version mismatch")
        stream = BoundedFile(DATA,MAX_FILE_READ_BYTES-file_read_bytes)
        top, names, loaded = read_all_variables(stream,sio)
        with partial.open("xb") as output:
            emitter = Emitter(output,np,sparse)
            emitter.emit({"schema":"complete-private-MAT-v5-census-v1",
                          "original_sha256":EXPECTED_SHA,
                          "index_convention":"zero-based coordinates; Fortran traversal",
                          "top_variables":[{"name":n,"shape":list(sh),"class":cl}
                                           for n,sh,cl in top],
                          "biological_roles_not_inferred":True})
            for name in names:
                emitter.walk(loaded[name],[name],name)
            output.flush()
            os.fsync(output.fileno())
        after = DATA.lstat()
        if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns) != (
                after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns):
            raise Refusal("original stat changed")
        partial.rename(DEST/"PRIVATE_SCHEMA_CENSUS.jsonl")
        (DEST/"PRIVATE_SCHEMA_CENSUS.jsonl").chmod(0o400)
        accepted = True
    except BaseException as error:
        # Do not expose arbitrary loader messages that could contain file values.
        failure = failure_record(error)
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        file_read_bytes = original_ledger["bytes"]
        if stream is not None:
            file_read_bytes += stream.used
            stream.close()
    receipt = {"schema":"MAT-v5-census-receipt-v1","accepted_complete_census":accepted,
        "original_sha256":EXPECTED_SHA,"original_bytes":EXPECTED_BYTES,
        "runtime_bytes_delivered_to_hasher":runtime_ledger["bytes"],
        "runtime_verification_complete":runtime_verification_complete,
        "original_hash_complete":original_hash_complete,
        "byte_counter_semantics":"bytes delivered to code, including failed verified reads; not OS prefetch or page cache",
        "scientific_file_bytes_read":file_read_bytes,
        "nodes":emitter.nodes if emitter else 0,
        "schema_bytes":emitter.bytes if emitter else 0,
        "accounted_array_bytes":emitter.array_bytes if emitter else 0,
        "text_metadata_bytes":emitter.text_bytes if emitter else 0,
        "scalar_name_matches":len(emitter.scalar_candidates) if emitter else 0,
        "failure":failure,"guard":guard,"elapsed_seconds":time.monotonic()-started,
        "non_allowlisted_numeric_values_disclosed":False,
        "allowlisted_scalar_values_may_be_measurements":True,
        "private_output_requires_semantic_review_before_export":True,
        "all_variables_requested":True,"no_fits_or_predictions":True,
        "biological_membership_verified":False,
        "roles_unresolved":["animal","neuron","session","simultaneous pair","condition",
                            "repeat","spike clock","velocity clock","units","alignment"],
        "source_sha256":args.source_sha256,
        "inventory_sha256":args.inventory_sha256,
        "runtime_sha256":args.runtime_sha256}
    (DEST/"CENSUS_RECEIPT.json").write_text(json.dumps(receipt,indent=2)+"\n")
    (DEST/"CENSUS_RECEIPT.json").chmod(0o400)
    print(json.dumps(receipt),flush=True)
    return 0 if accepted else 1

if __name__ == "__main__":
    sys.exit(main())

