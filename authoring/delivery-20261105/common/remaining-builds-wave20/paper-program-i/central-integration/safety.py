"""Bounded private metadata I/O; source construction performs no runtime action."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import time


def need(value, message):
    if not value:
        raise ValueError(message)


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()


def parse(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'Duplicate metadata key')
            result[key] = value
        return result
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, 'Nonfinite metadata value'))


def descriptor(value):
    need(type(value) is dict and set(value) == {'bytes', 'sha256'} and
         type(value['bytes']) is int and value['bytes'] >= 0 and
         type(value['sha256']) is str and re.fullmatch('[a-f0-9]{64}', value['sha256']),
         'Exact byte/SHA descriptor')
    return value


def typed_equal(left, right):
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return set(left) == set(right) and all(typed_equal(left[k], right[k]) for k in left)
    if type(left) in (list, tuple):
        return len(left) == len(right) and all(typed_equal(a, b) for a, b in zip(left, right))
    return left == right


def ordinary(value):
    path = Path(value)
    need(path.is_absolute() and '..' not in path.parts, 'Literal absolute path')
    need(not any(p.is_symlink() for p in (path, *path.parents)), 'No linked path chain')
    return path


def relative(value):
    need(type(value) is str and re.fullmatch(r'[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*', value)
         and all(part not in ('.', '..') for part in Path(value).parts), 'Ordinary relative path')
    return value


def cleanup(primary, actions):
    errors = []
    for label, action in actions:
        try:
            action()
        except BaseException as error:
            errors.append({'action': label, 'type': type(error).__name__})
    if errors:
        if primary is None:
            primary = RuntimeError('Independent cleanup failed')
            primary.cleanup_errors = errors
            raise primary
        primary.cleanup_errors = [*getattr(primary, 'cleanup_errors', []), *errors]


def fsync_dir(path):
    fd = os.open(ordinary(path), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    primary = None
    try:
        os.fsync(fd)
    except BaseException as error:
        primary = error
        raise
    finally:
        cleanup(primary, [('directory.close', lambda: os.close(fd))])


class IO:
    """Counters charge before I/O and never refund failed/unknown work."""
    def __init__(self, origin, read_cap=268435456, write_cap=8388608, clock=time.monotonic):
        need(type(origin) in (int, float) and math.isfinite(origin), 'Original finite clock')
        self.origin, self.clock, self.deadline = origin, clock, origin + 120
        self.read_cap, self.write_cap = read_cap, write_cap
        self.reads = self.writes = 0
        self.last = origin
        self.budget = None

    def tick(self):
        now = self.clock()
        need(self.last <= now < self.deadline, 'Original caller clock and strict cutoff')
        self.last = now
        return now

    def attach(self, budget):
        need(self.budget is None and budget.origin == self.origin, 'One original-clock budget attachment')
        budget.read(self.reads)
        if self.writes:
            budget.write(self.writes)
        self.budget = budget
        self.deadline = budget.end
        self.tick()

    def read_charge(self, size):
        self.tick()
        need(type(size) is int and size >= 0 and self.reads + size <= self.read_cap,
             'Caller cumulative read ceiling')
        if self.budget is not None:
            self.budget.read(size)
        self.reads += size

    def write_charge(self, size):
        self.tick()
        need(type(size) is int and size >= 0 and self.writes + size <= self.write_cap,
             'Caller cumulative write/retention ceiling')
        if self.budget is not None:
            self.budget.write(size)
        self.writes += size

    def read(self, path, expected=None, cap=1048576, allow_empty=False):
        self.tick()
        path = ordinary(path)
        if expected is not None:
            descriptor(expected)
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        primary = None
        try:
            before = os.fstat(fd)
            need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
                 (0 <= before.st_size if allow_empty else 0 < before.st_size) and before.st_size <= cap,
                 'Bounded ordinary single-link source or metadata')
            if expected is not None:
                need(before.st_size == expected['bytes'], 'Exact input extent before read')
            self.read_charge(before.st_size + 1)
            chunks, remaining = [], before.st_size
            while remaining:
                self.tick()
                chunk = os.read(fd, min(65536, remaining))
                need(bool(chunk), 'Complete input read')
                chunks.append(chunk)
                remaining -= len(chunk)
            need(not os.read(fd, 1), 'Exact input EOF')
            after, named = os.fstat(fd), path.lstat()
            fields = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size,
                                s.st_mtime_ns, s.st_ctime_ns)
            need(fields(before) == fields(after) == fields(named), 'Stable captured file identity')
            raw = b''.join(chunks)
            if expected is not None:
                need(pin(raw) == expected, 'Exact captured raw SHA')
            return raw
        except BaseException as error:
            primary = error
            raise
        finally:
            cleanup(primary, [('input.close', lambda: os.close(fd))])

    def save(self, path, raw, mode=0o400):
        need(type(raw) is bytes, 'Complete ordinary metadata bytes')
        self.write_charge(len(raw))
        path = ordinary(path)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
        primary, owned = None, None
        try:
            stamp = os.fstat(fd)
            owned = (stamp.st_dev, stamp.st_ino)
            view = memoryview(raw)
            while view:
                self.tick()
                count = os.write(fd, view)
                need(count > 0, 'Complete partial-write loop')
                view = view[count:]
            os.fsync(fd)
        except BaseException as error:
            primary = error
            raise
        finally:
            def remove_owned():
                if owned is None:
                    return
                try:
                    current = path.lstat()
                except FileNotFoundError:
                    return
                need((current.st_dev, current.st_ino) == owned, 'Never delete a foreign replacement inode')
                path.unlink()
            actions = [('output.close', lambda: os.close(fd))]
            if primary is not None:
                actions.append(('partial.unlink_owned', remove_owned))
            actions.append(('output.parent_fsync', lambda: fsync_dir(path.parent)))
            cleanup(primary, actions)
        self.tick()
        return pin(raw)

    def mkdir(self, path, mode=0o700):
        self.tick()
        path = ordinary(path)
        path.mkdir(mode=mode, parents=False, exist_ok=False)
        fsync_dir(path.parent)
        return path


class ReceiptStore:
    def __init__(self, root, io, metadata_cap, outer_cap):
        self.root, self.io = ordinary(root), io
        self.metadata_cap, self.outer_cap = metadata_cap, outer_cap
        self.cache = {}

    def _path(self, name):
        return ordinary(self.root / relative(name))

    def read(self, name, expected, cap):
        descriptor(expected)
        key = relative(name)
        if key in self.cache:
            raw = self.cache[key]
            need(pin(raw) == expected and len(raw) <= cap, 'Same immutable cached receipt identity')
            return raw
        raw = self.io.read(self._path(name), expected, cap, allow_empty=True)
        self.cache[key] = raw
        return raw

    def observe(self, name, cap):
        key = relative(name)
        if key not in self.cache:
            self.cache[key] = self.io.read(self._path(name), cap=cap)
        raw = self.cache[key]
        need(len(raw) <= cap, 'Observed raw receipt bound')
        return raw, pin(raw)

    def names(self, name, max_entries):
        self.io.tick()
        path = self.root if name == '' else self._path(name)
        need(path.is_dir() and not path.is_symlink(), 'Ordinary private receipt directory')
        result = []
        with os.scandir(path) as iterator:
            for item in iterator:
                need(len(result) < max_entries and not item.is_symlink(), 'Bounded unlinked receipt entries')
                relative(item.name)
                result.append(item.name)
        return sorted(result)
