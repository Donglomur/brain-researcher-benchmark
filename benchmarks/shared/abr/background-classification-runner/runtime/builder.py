"""Ordinary-file I/O only; private acquisition is maintained separately."""
import hashlib
import json
import os
from pathlib import Path
import stat
import packet

STABLE = ("st_dev", "st_ino", "st_mode", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns")


need = packet.need


def pairs(items):
    result = {}
    for key, value in items:
        need(key not in result, "duplicate JSON object key"); result[key] = value
    return result


def decode(raw):
    def bad(value):
        raise packet.PacketError("nonfinite JSON constant: " + value)
    return json.loads(raw.decode("utf8"), object_pairs_hook=pairs, parse_constant=bad)


def identity(path, directory=False):
    p = Path(path)
    need(p.is_absolute() and ".." not in p.parts and
         not any(x.is_symlink() for x in (p, *p.parents)), "ordinary absolute path and ancestors")
    s = p.lstat()
    need(stat.S_ISDIR(s.st_mode) if directory else stat.S_ISREG(s.st_mode) and s.st_nlink == 1,
         "ordinary directory or single-link file")
    return tuple(getattr(s, k) for k in STABLE)


def read_fixed(pin, guard, cap=4 * 1024**2):
    before = identity(pin["path"]); need(before[4] == pin["bytes"] <= cap, "bounded complete input extent")
    guard.charge("read", pin["bytes"] + 1)
    fd = os.open(pin["path"], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        need(tuple(getattr(os.fstat(fd), k) for k in STABLE) == before, "opened metadata identity")
        with os.fdopen(fd, "rb", closefd=False) as f:
            raw = f.read(pin["bytes"] + 1)
        need(len(raw) == pin["bytes"] and hashlib.sha256(raw).hexdigest() == pin["sha256"],
             "complete metadata pin")
        need(identity(pin["path"]) == before and
             tuple(getattr(os.fstat(fd), k) for k in STABLE) == before, "metadata stable through read")
    finally:
        os.close(fd)
    return raw, before

