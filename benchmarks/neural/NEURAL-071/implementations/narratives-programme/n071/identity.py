"""Strict ordinary JSON, immutable content identities and safe relative names."""
import hashlib
import json
import math
from pathlib import PurePosixPath
from .errors import need

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")

def identity(value):
    return hashlib.sha256(canonical(value)).hexdigest()

def pin(body):
    need(type(body) is bytes, "byte-body")
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}

def pairs(items):
    out = {}
    for key, value in items:
        need(key not in out, "duplicate-json-key")
        out[key] = value
    return out

def parse(body):
    return json.loads(body.decode("utf-8"), object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite-json")))

def exact(value, fields, code="exact-fields"):
    need(type(value) is dict and set(value) == set(fields), code)

def digest(value):
    need(type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value),
         "sha256")
    return value

def descriptor(value):
    exact(value, ("path", "bytes", "sha256", "mode"))
    relative(value["path"])
    need(type(value["bytes"]) is int and value["bytes"] >= 0, "byte-extent")
    digest(value["sha256"])
    need(value["mode"] in (0o400, 0o444, 0o500, 0o600, 0o644, 0o700, 0o755), "regular-mode")
    return value

def relative(value):
    need(type(value) is str and value and "\\" not in value and "\0" not in value, "relative-path")
    p = PurePosixPath(value)
    need(not p.is_absolute() and all(s not in ("", ".", "..") for s in value.split("/")),
         "relative-components")
    return value

def finite(value):
    return type(value) in (int, float) and math.isfinite(value)
