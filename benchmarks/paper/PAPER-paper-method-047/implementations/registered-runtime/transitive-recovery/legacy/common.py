"""Bounded trusted metadata custody for the prospective GCaMP8 registration."""
import hashlib
import json
import os
from pathlib import Path
import stat
import time
import types

HERE = Path(__file__).absolute().parent
ROOT = HERE.parents[4]
TASK = 'PAPER-paper-method-047'
READ_CAP = 1100000000
WRITE_CAP = 20000000
TOTAL = 33020000000
META = 20000000


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def parse(raw):
    def pairs(rows):
        result = {}
        for key, value in rows:
            need(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, 'nonfinite JSON'))


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def only(value):
    return {k: value[k] for k in ('bytes', 'sha256')}


def descriptor(value, cap):
    need(type(value) is dict and set(value) == {'bytes', 'sha256'}, 'exact descriptor')
    need(type(value['bytes']) is int and 0 < value['bytes'] <= cap, 'descriptor extent')
    h = value['sha256']
    need(type(h) is str and len(h) == 64 and all(x in '0123456789abcdef' for x in h), 'descriptor hash')
    return value


def literal(value):
    need(type(value) is str and value and not any(c in value for c in '\0\r\n,'), 'literal path')
    p = Path(value)
    need(p.is_absolute() and '..' not in p.parts and str(p) == value, 'canonical absolute path')
    need(not any(x.is_symlink() for x in (p, *p.parents)), 'unlinked path')
    return p


def selected(value, cap=65536):
    need(type(value) is dict and set(value) == {'path', 'bytes', 'sha256'}, 'selected descriptor')
    return literal(value['path']), descriptor(only(value), cap)


def relative(value):
    p = Path(value)
    need(type(value) is str and value and not p.is_absolute() and '..' not in p.parts and
         '\\' not in value and p.as_posix() == value, 'repository-relative source')
    return literal(str(ROOT / p))


class Capture:
    def __init__(self, end):
        self.end = end
        self.reads = 0
        self.writes = 0

    def tick(self):
        need(time.monotonic() < self.end, 'original outer clock')

    def read(self, path, cap, expected=None):
        self.tick()
        path = literal(str(path))
        if expected is not None:
            descriptor(expected, cap)
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            before = os.fstat(fd)
            need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= cap,
                 'bounded regular metadata/source')
            need(expected is None or before.st_size == expected['bytes'], 'pinned extent before read')
            self.reads += before.st_size + 1
            need(self.reads <= READ_CAP, 'whole observer read ceiling')
            with os.fdopen(fd, 'rb', closefd=False) as f:
                raw = f.read(before.st_size + 1)
            fields = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
            key = lambda s: tuple(getattr(s, k) for k in fields)
            need(len(raw) == before.st_size and key(before) == key(os.fstat(fd)) == key(path.lstat()),
                 'stable captured identity')
            need(expected is None or pin(raw) == expected, 'exact captured content')
            self.tick()
            return raw
        finally:
            os.close(fd)

    def document(self, row, cap=65536):
        path, expected = selected(row, cap)
        return parse(self.read(path, cap, expected)), (path, expected)

    def write(self, path, value):
        self.tick()
        raw = encoded(value)
        self.writes += len(raw)
        need(self.writes <= WRITE_CAP and len(raw) <= 2000000, 'observer metadata write ceiling')
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
            os.fchmod(f.fileno(), 0o444)
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        self.tick()
        return pin(raw)


def module(raw, path, name):
    result = types.ModuleType(name)
    result.__file__ = str(path)
    exec(compile(raw, str(path), 'exec'), result.__dict__)
    return result
