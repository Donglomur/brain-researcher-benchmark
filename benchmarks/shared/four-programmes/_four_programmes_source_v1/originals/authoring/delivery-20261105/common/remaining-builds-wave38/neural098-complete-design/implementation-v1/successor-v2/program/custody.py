"""Bounded ordinary-file custody for the selected future programme.

All data operations are reached only after controller admission. This module
contains no fixture, native import, credential lookup or ambient discovery.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import sys
import time


def need(ok, message):
    if not ok:
        raise ValueError(message)


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'),
                       ensure_ascii=True, allow_nan=False) + '\n').encode('ascii')


def parse(raw):
    def pairs(items):
        out = {}
        for k, v in items:
            need(k not in out, 'duplicate JSON key')
            out[k] = v
        return out
    def nonfinite(value):
        raise ValueError('nonfinite JSON: ' + value)
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=nonfinite)


def pin(raw, path=None):
    out = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    if path is not None:
        out['path'] = str(path)
    return out


def descriptor(d, cap=256_000_000):
    need(type(d) is dict and set(d) == {'path', 'bytes', 'sha256'}, 'exact descriptor')
    need(type(d['bytes']) is int and 0 <= d['bytes'] <= cap, 'bounded descriptor bytes')
    h = d['sha256']
    need(type(h) is str and len(h) == 64 and all(c in '0123456789abcdef' for c in h), 'SHA256')
    relative_or_absolute(d['path'])
    return d


def relative_or_absolute(path):
    need(type(path) is str and 0 < len(path) <= 4096 and '\\' not in path and '\0' not in path,
         'canonical ordinary path spelling')
    parts = path.split('/')[1:] if path.startswith('/') else path.split('/')
    need(parts and all(p not in ('', '.', '..') for p in parts), 'ordinary path components')
    return parts


class Budget:
    def __init__(self, *, seconds, read_bytes, write_bytes, origin=None):
        need(type(seconds) in (int, float) and math.isfinite(seconds) and seconds > 0, 'finite duration')
        need(all(type(x) is int and x > 0 for x in (read_bytes, write_bytes)), 'positive byte budgets')
        self.origin = time.monotonic() if origin is None else origin
        need(type(self.origin) in (int, float) and math.isfinite(self.origin)
             and self.origin <= time.monotonic(), 'original clock origin')
        self.deadline = self.origin + seconds
        self.read_cap, self.write_cap = read_bytes, write_bytes
        self.read_reserved = self.write_reserved = self.read_completed = self.write_completed = 0

    def check(self):
        if time.monotonic() >= self.deadline:
            raise TimeoutError('whole-programme deadline')

    def charge_read(self, n):
        self.check()
        need(type(n) is int and n >= 0 and self.read_reserved + n <= self.read_cap, 'aggregate read budget')
        self.read_reserved += n

    def charge_write(self, n):
        self.check()
        need(type(n) is int and n >= 0 and self.write_reserved + n <= self.write_cap, 'aggregate write budget')
        self.write_reserved += n

    def record(self):
        return {'read_reserved': self.read_reserved, 'write_reserved': self.write_reserved,
                'read_completed': self.read_completed, 'write_completed': self.write_completed,
                'origin': self.origin, 'deadline': self.deadline,
                'physical_OS_IO_measured': False}


def parent_fd(path):
    p = str(Path(path).absolute())
    relative_or_absolute(p)
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in p.split('/')[1:-1]:
            nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = nxt
        return fd, p.rsplit('/', 1)[1]
    except BaseException:
        os.close(fd)
        raise


def finish(owned, budget, original, prefix=None):
    """Consume each owned FD once; retain the original failure and uncertainty."""
    errors = []
    for fd in owned:
        if fd is not None:
            try:
                os.close(fd)
            except BaseException as error:
                errors.append(error)
    try:
        budget.check()
    except BaseException as error:
        errors.append(error)
    if errors and original is not None:
        original.cleanup_uncertain = True
        for error in errors:
            original.add_note('Cleanup/clock failure: ' + type(error).__name__)
    elif errors:
        if prefix is not None:
            errors[0].known_output_prefix = prefix
        raise errors[0]


def capture(path, cap, budget, expected=None):
    if expected is not None:
        descriptor(expected, cap)
    parent, name = parent_fd(path)
    fd = None
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 <= before.st_size <= cap,
             'bounded single-linked ordinary file')
        if expected is not None:
            need(before.st_size == expected['bytes'], 'selected extent before read')
        budget.charge_read(before.st_size + 1)
        chunks = []
        remaining = before.st_size + 1
        while remaining:
            budget.check()
            chunk = os.read(fd, min(65536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b''.join(chunks)
        after = os.fstat(fd)
        named = os.stat(name, dir_fd=parent, follow_symlinks=False)
        fields = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_nlink')
        need(len(raw) == before.st_size and all(getattr(before, k) == getattr(after, k) == getattr(named, k)
             for k in fields), 'stable complete captured object and EOF')
        actual = pin(raw, str(Path(path).absolute()))
        if expected is not None:
            need(actual['sha256'] == expected['sha256'], 'selected captured SHA256')
        budget.read_completed += len(raw)
        return raw, actual
    finally:
        finish((fd, parent), budget, sys.exception())


def read_pin(root, d, cap, budget):
    descriptor(d, cap)
    path = Path(d['path'])
    if not path.is_absolute():
        path = Path(root) / path
    return capture(path, cap, budget, d)[0]


def new_directory(parent, name, budget):
    need(len(relative_or_absolute(name)) == 1 and not name.startswith('/'), 'one fresh namespace')
    target = str(Path(parent).absolute() / name)
    fd, leaf = parent_fd(target)
    created = False
    try:
        budget.check()
        os.mkdir(leaf, mode=0o700, dir_fd=fd)
        created = True
        os.fsync(fd)
        budget.check()
        return Path(target)
    except BaseException as error:
        if created:
            error.known_output_prefix = target
        raise
    finally:
        finish((fd,), budget, sys.exception(), target if created else None)


def write_new(path, raw, budget, cap=4_000_000):
    need(type(raw) is bytes and len(raw) <= cap, 'bounded encoded publication')
    budget.charge_write(len(raw))
    parent, name = parent_fd(path)
    fd = None
    created = False
    try:
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=parent)
        created = True
        view = memoryview(raw)
        while view:
            budget.check()
            n = os.write(fd, view)
            need(n > 0, 'progressing complete publication')
            budget.write_completed += n
            view = view[n:]
        os.fsync(fd)
        closing, fd = fd, None
        os.close(closing)
        os.fsync(parent)
        budget.check()
        return pin(raw, str(Path(path).absolute()))
    except BaseException as error:
        if created:
            error.known_output_prefix = str(Path(path).absolute())
        raise
    finally:
        finish((fd, parent), budget, sys.exception(), str(path) if created else None)


def write_json(path, value, budget, cap=4_000_000):
    return write_new(path, encode(value), budget, cap)
