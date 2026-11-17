"""Bounded captured-file IO only; no source data read at import."""
import hashlib
import json
import os
import stat
from pathlib import Path


def capture(path, limit, expected=None):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as f:
        a = os.fstat(f.fileno())
        if not stat.S_ISREG(a.st_mode) or not 0 < a.st_size <= limit:
            raise ValueError('bounded regular file required')
        raw = f.read(limit + 1)
        b = os.fstat(f.fileno())
        sig = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        if sig(a) != sig(b) or len(raw) != a.st_size:
            raise ValueError('unstable file')
    digest = hashlib.sha256(raw).hexdigest()
    if expected is not None and digest != expected:
        raise ValueError('captured bytes do not match pin')
    return raw, digest


def unique(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise ValueError('duplicate key')
        out[k] = v
    return out


def decode(raw):
    return json.loads(raw.decode('utf-8'), object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))


def fresh(path):
    p = Path(path)
    if p.exists() or p.is_symlink() or p.parent.is_symlink() or not p.parent.is_dir():
        raise ValueError('fresh output in ordinary existing parent required')


def write_json(path, value, limit=20_000_000):
    fresh(path)
    b = json.dumps(value, allow_nan=False, separators=(',', ':')).encode('utf-8') + b'\n'
    if len(b) > limit:
        raise ValueError('output byte cap')
    with open(path, 'xb') as f:
        f.write(b)
