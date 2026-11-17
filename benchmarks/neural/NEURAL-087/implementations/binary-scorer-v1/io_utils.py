"""Bounded plain JSON and ordinary-file helpers; no data read on import."""
import hashlib
import json
import os
import stat
from pathlib import Path
from contract import need


def capture(path, cap, expected=None):
    path = Path(path)
    need(not any(p.is_symlink() for p in (path, *path.parents)), 'Unlinked path and ancestors')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= cap, 'Bounded ordinary single-link file')
        with os.fdopen(fd, 'rb', closefd=False) as f:
            raw = f.read(cap + 1)
        after = os.fstat(fd)
        need(len(raw) == before.st_size and all(getattr(before, k) == getattr(after, k) for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')), 'Stable complete input')
    finally:
        os.close(fd)
    pin = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    if expected is not None:
        need(pin == {k: expected[k] for k in pin}, 'Exact committed input descriptor')
    return raw


def decode(raw):
    def pairs(items):
        result = {}
        for k, v in items:
            need(k not in result, 'Duplicate JSON object key')
            result[k] = v
        return result
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON literal')))


def write_json(path, value, cap, mode=0o444):
    raw = (json.dumps(value, allow_nan=False, sort_keys=True, separators=(',', ':')) + '\n').encode()
    need(len(raw) <= cap, 'Complete output fits declared cap')
    with Path(path).open('xb') as f:
        f.write(raw); f.flush(); os.fsync(f.fileno())
    os.chmod(path, mode)
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
