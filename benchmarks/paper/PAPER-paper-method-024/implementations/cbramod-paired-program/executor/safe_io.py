"""Bounded ordinary-file I/O for the trusted offline delivery adapter."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat


def need(ok, message):
    if not ok:
        raise ValueError(message)


def strict(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, 'nonfinite JSON'))


def read(path, cap, pin=None):
    path = Path(path).absolute()
    need('..' not in path.parts and all(not p.is_symlink() for p in (path, *path.parents)),
         'ordinary path without symlink ancestors')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and 0 < before.st_size <= cap, 'bounded single-link regular file')
        if pin is not None:
            need(type(pin) is dict and set(pin) == {'path', 'bytes', 'sha256'}
                 and type(pin['bytes']) is int and pin['bytes'] == before.st_size
                 and type(pin['sha256']) is str
                 and re.fullmatch('[0-9a-f]{64}', pin['sha256']), 'exact descriptor')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(cap + 1)
        after, linked = os.fstat(fd), path.lstat()
        need(len(raw) == before.st_size and all(getattr(before, k) == getattr(after, k)
             == getattr(linked, k) for k in ('st_dev', 'st_ino', 'st_mode', 'st_nlink',
                                            'st_size', 'st_mtime_ns', 'st_ctime_ns')),
             'stable complete captured bytes')
    finally:
        os.close(fd)
    if pin is not None:
        need(hashlib.sha256(raw).hexdigest() == pin['sha256'], 'content SHA256')
    return raw


def captured(root, pin, cap):
    need(type(pin) is dict and set(pin) == {'path', 'bytes', 'sha256'}, 'descriptor shape')
    name = pin['path']
    need(type(name) is str and name and not name.startswith('/')
         and all(p not in ('', '.', '..') for p in name.split('/')), 'relative file identity')
    return read(Path(root) / name, cap, pin)


def write_new(path, value, cap):
    raw = (json.dumps(value, sort_keys=True, allow_nan=False, indent=2) + '\n').encode()
    need(0 < len(raw) <= cap, 'complete bounded JSON output')
    path = Path(path).absolute()
    need(all(not p.is_symlink() for p in (path, *path.parents)), 'unlinked output path')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'wb', closefd=False) as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(fd)
    finally:
        os.close(fd)
    os.chmod(path, 0o444)
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
