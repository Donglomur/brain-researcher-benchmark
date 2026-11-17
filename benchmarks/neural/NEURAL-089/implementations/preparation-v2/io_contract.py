"""Bounded strict I/O for the fixed 2025 39-phoneme task."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat

TASK = "NEURAL-089"
ID = re.compile(r"[0-9a-f]{24}\Z")
MAX_QUERIES = 200000
MAX_JSON = 256000000


def need(ok, message):
    if not ok: raise ValueError(message)


def strict(raw):
    def pairs(items):
        result = {}
        for k, v in items:
            need(k not in result, "duplicate JSON key"); result[k] = v
        return result
    def invalid(value): raise ValueError("nonfinite JSON token")
    try: return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=invalid)
    except (UnicodeError, RecursionError) as error: raise ValueError("malformed JSON") from error


def read(path, cap=MAX_JSON, pin=None):
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= cap,
             "bounded ordinary single-link input")
        parts, size = [], 0
        while True:
            b = os.read(fd, min(65536, cap + 1 - size))
            if not b: break
            size += len(b); need(size <= cap, "input cap"); parts.append(b)
        after = os.fstat(fd)
        need(size == before.st_size and all(getattr(before, k) == getattr(after, k)
             for k in ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")), "input changed")
        body = b"".join(parts)
        if pin is not None: need(hashlib.sha256(body).hexdigest() == pin, "input SHA256 mismatch")
        return body
    finally: os.close(fd)


def encoded(value): return (json.dumps(value, sort_keys=True, allow_nan=False, separators=(",", ":")) + "\n").encode()


def write(path, value):
    body = encoded(value); need(len(body) <= MAX_JSON, "output cap")
    with Path(path).open("xb") as stream: stream.write(body)
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def fields(value, keys): need(type(value) is dict and set(value) == set(keys), "exact fields required")


def header(value, tail):
    fields(value, ["schema_version", "task_id", tail])
    need(type(value["schema_version"]) is int and value["schema_version"] == 1 and value["task_id"] == TASK,
         "exact task/schema")


def panel_ids(value):
    header(value, "query_ids")
    ids = value["query_ids"]
    need(type(ids) is list and 1 <= len(ids) <= MAX_QUERIES and all(type(q) is str and ID.fullmatch(q) for q in ids)
         and len(set(ids)) == len(ids), "complete unique opaque panel")
    return ids
