"""Bounded central source/metadata I/O; no operational effects at import."""
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import time


def need(ok, why):
    if not ok:
        raise ValueError(why)


def integer(v, minimum=0):
    need(type(v) is int and v >= minimum, 'ordinary bounded integer')
    return v


def finite(v):
    need(type(v) in (int, float) and math.isfinite(v), 'ordinary finite time')
    return float(v)


def pin(raw):
    need(type(raw) is bytes, 'captured bytes')
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def encode(value):
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, allow_nan=False,
                       separators=(',', ':'))+'\n').encode()


def parse(raw):
    def pairs(rows):
        out = {}
        for k, v in rows:
            need(k not in out, 'duplicate metadata key'); out[k] = v
        return out
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, 'nonfinite metadata'))


def only_pin(row):
    need(type(row) is dict, 'source descriptor')
    n, h = integer(row['bytes']), row['sha256']
    need(type(h) is str and len(h) == 64 and all(x in '0123456789abcdef' for x in h), 'SHA256 descriptor')
    return {'bytes': n, 'sha256': h}


def path(value):
    need(type(value) is str or isinstance(value, Path), 'literal path')
    raw = str(value); p = Path(raw)
    need(p.is_absolute() and not raw.startswith('//') and raw == str(p)
         and '..' not in p.parts and '\x00' not in raw, 'canonical absolute path')
    for parent in p.parents:
        need(stat.S_ISDIR(parent.lstat().st_mode), 'ordinary nonsymlink path parents')
    return p


def stamp(info):
    return tuple(getattr(info, k) for k in ('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns'))


def capture(value, cap, expected, reserve, tick, readonly=False):
    p = path(value); integer(cap, 1); tick()
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        start = os.fstat(fd)
        need(stat.S_ISREG(start.st_mode) and start.st_nlink == 1 and 0 <= start.st_size <= cap,
             'bounded ordinary single-link metadata')
        if readonly:
            need(start.st_mode & 0o222 == 0, 'sealed readonly metadata')
        if expected is not None:
            need(start.st_size == only_pin(expected)['bytes'], 'metadata extent')
        reserve(start.st_size+1); left = start.st_size; chunks = []
        while left:
            tick(); body = os.read(fd, min(left, 65536)); need(body, 'short metadata read')
            chunks.append(body); left -= len(body)
        need(not os.read(fd, 1), 'metadata grew')
        raw = b''.join(chunks); end = os.fstat(fd)
        need(stamp(start) == stamp(end) == stamp(p.lstat()), 'stable captured metadata')
        if expected is not None:
            need(pin(raw) == only_pin(expected), 'metadata exact bytes/hash')
        tick(); return raw
    finally:
        os.close(fd)


def sync_dir(p):
    fd = os.open(p, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try: os.fsync(fd)
    finally: os.close(fd)


def save(value, raw, cap, reserve, tick):
    p = path(value); need(type(raw) is bytes and len(raw) <= integer(cap, 1), 'bounded publication')
    tick(); reserve(len(raw)); fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        view = memoryview(raw)
        while view:
            tick(); n = os.write(fd, view); need(n > 0, 'short publication'); view = view[n:]
        os.fchmod(fd, 0o444); os.fsync(fd)
    finally: os.close(fd)
    sync_dir(p.parent); tick(); return pin(raw)
