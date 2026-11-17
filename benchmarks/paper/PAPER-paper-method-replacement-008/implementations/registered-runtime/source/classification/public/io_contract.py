"""Bounded same-open regular-file capture and exclusive JSON transport."""
import json
import math
import os
from pathlib import Path
import stat
from protocol import canonical


def ordinary(path):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("Linked path refused")
    return path


def fresh(path):
    path = ordinary(path)
    if path.exists() or path.is_symlink() or not path.parent.is_dir():
        raise ValueError("Fresh output with existing ordinary parent required")
    return path


def capture(path, cap=64_000_000, *, allow_empty=False):
    path = ordinary(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        a = os.fstat(fd)
        if not stat.S_ISREG(a.st_mode) or a.st_nlink != 1 or not (0 if allow_empty else 1) <= a.st_size <= cap:
            raise ValueError("Bounded ordinary single-link file required")
        with os.fdopen(fd, "rb", closefd=False) as f:
            body = f.read(cap + 1)
        b, c = os.fstat(fd), os.lstat(path)
        fields = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        if len(body) != a.st_size or fields(a) != fields(b) or fields(a) != fields(c):
            raise ValueError("Input identity changed during capture")
        return body
    finally:
        os.close(fd)


def parse(body):
    text = body.decode("utf-8")
    depth, quoted, escape = 0, False, False
    for c in text:
        if quoted:
            if escape: escape = False
            elif c == "\\": escape = True
            elif c == '"': quoted = False
        elif c == '"': quoted = True
        elif c in "[{":
            depth += 1
            if depth > 48: raise ValueError("JSON nesting bound")
        elif c in "]}": depth -= 1
    def pairs(rows):
        out = {}
        for k, v in rows:
            if k in out: raise ValueError("Duplicate JSON field")
            out[k] = v
        return out
    def integer(s):
        if len(s) > 18: raise ValueError("JSON integer bound")
        return int(s)
    def number(s):
        x = float(s)
        if not math.isfinite(x): raise ValueError("Nonfinite JSON number")
        return x
    def reject(s): raise ValueError("Nonfinite JSON constant")
    return json.loads(text, object_pairs_hook=pairs, parse_int=integer, parse_float=number, parse_constant=reject)


def load(path, cap=64_000_000):
    return parse(capture(path, cap))


def put(path, value):
    path = fresh(path)
    body = canonical(value) + b"\n"
    if len(body) > 64_000_000: raise ValueError("JSON output cap")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(body); f.flush(); os.fsync(f.fileno())
