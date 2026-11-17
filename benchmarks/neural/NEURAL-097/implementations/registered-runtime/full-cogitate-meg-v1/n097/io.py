"""Strict bounded ordinary-file custody. No candidate imports or data readers."""
import hashlib
import json
import os
from pathlib import Path
import stat

class Refusal(ValueError):
    pass

def need(ok, reason):
    if not ok:
        raise Refusal(reason)

def exact(obj, fields):
    need(type(obj) is dict and set(obj) == set(fields), "Exact object fields required")

def canonical(obj):
    return (json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()

def parse(body):
    def pairs(items):
        out = {}
        for key, value in items:
            need(key not in out, "Duplicate JSON key")
            out[key] = value
        return out
    def constant(value):
        raise Refusal("Nonfinite JSON constant")
    return json.loads(body, object_pairs_hook=pairs, parse_constant=constant)

def relative(name):
    need(type(name) is str and name and "\\" not in name and "\0" not in name, "Relative path string")
    p = Path(name)
    need(not p.is_absolute() and all(x not in ("", ".", "..") for x in p.parts)
         and p.as_posix() == name, "Canonical contained relative path")
    return p

def plain(path, exists=True):
    p = Path(path).absolute()
    for q in (p, *p.parents):
        need(not q.is_symlink(), "No symlink in custody path")
    if exists:
        s = p.stat()
        need(stat.S_ISREG(s.st_mode) and s.st_nlink == 1, "Ordinary single-link file required")
    return p

def identity(body):
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}

def pin_shape(pin):
    need(type(pin) is dict and set(pin) >= {"bytes", "sha256"}, "Typed exact byte pin")
    need(type(pin["bytes"]) is int and pin["bytes"] >= 0, "Nonnegative byte length")
    h = pin["sha256"]
    need(type(h) is str and len(h) == 64 and all(c in "0123456789abcdef" for c in h), "Lowercase SHA256")

def read(path, cap, expected=None):
    need(type(cap) is int and cap >= 0, "Explicit finite byte cap")
    p = plain(path)
    if expected:
        pin_shape(expected)
        need(expected["bytes"] <= cap, "Declared bytes exceed cap")
    fd = os.open(p, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        pre = os.fstat(fd)
        need(stat.S_ISREG(pre.st_mode) and pre.st_nlink == 1 and pre.st_size <= cap, "Bounded single-link file")
        chunks, remaining = [], cap + 1
        while remaining:
            chunk = os.read(fd, min(65536, remaining))
            if not chunk:
                break
            chunks.append(chunk); remaining -= len(chunk)
        body = b"".join(chunks)
        post = os.fstat(fd)
        current = p.stat()
        signature = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_nlink)
        need(signature(pre) == signature(post) == signature(current) and len(body) == pre.st_size
             and len(body) <= cap, "Source changed during bounded read")
        if expected:
            need(identity(body) == {k: expected[k] for k in ("bytes", "sha256")}, "Exact source pin mismatch")
        return body
    finally:
        os.close(fd)

def read_json(path, cap, expected=None):
    return parse(read(path, cap, expected))

def write_new(path, body, cap):
    need(type(body) is bytes and len(body) <= cap, "Bounded byte output")
    p = plain(path, exists=False)
    p.parent.mkdir(parents=True, exist_ok=True)
    plain(p, exists=False)
    with p.open("xb") as stream:
        stream.write(body)
    return identity(body)

def write_json(path, obj, cap=4_000_000):
    return write_new(path, canonical(obj), cap)

def source_bundle(root, manifest, total_cap=100_000_000):
    need(type(manifest) is list and manifest, "Nonempty complete source manifest")
    out, total, names = {}, 0, set()
    for row in manifest:
        exact(row, ["path", "bytes", "sha256"])
        name = relative(row["path"]).as_posix()
        need(name.casefold() not in names, "Unique case-insensitive source path")
        names.add(name.casefold()); total += row["bytes"]
        need(total <= total_cap, "Whole source closure cap")
        out[name] = read(Path(root) / name, row["bytes"], row)
    return out

def bind_source(root, rows):
    bodies = source_bundle(root, rows)
    return {"files": rows, "closure_sha256": identity(canonical(rows))["sha256"],
            "total_bytes": sum(len(b) for b in bodies.values())}


def stream_pin(path, expected, chunk_bytes=1_048_576):
    """Complete bounded-memory hashing for future explicitly selected large files."""
    pin_shape(expected);p=plain(path);before=p.stat()
    need(before.st_size==expected["bytes"],"Exact declared full native file size")
    h=hashlib.sha256();total=0
    with p.open("rb")as stream:
        while True:
            b=stream.read(chunk_bytes)
            if not b:break
            total+=len(b);need(total<=expected["bytes"],"Native file grew during full stream");h.update(b)
        after=os.fstat(stream.fileno())
    now=p.stat()
    signature=lambda x:(x.st_dev,x.st_ino,x.st_size,x.st_mtime_ns,x.st_nlink)
    need(signature(before)==signature(after)==signature(now),"Stable original full file")
    need(total==expected["bytes"]and h.hexdigest()==expected["sha256"],"Complete native identity")
    return {"bytes":total,"sha256":h.hexdigest()}
