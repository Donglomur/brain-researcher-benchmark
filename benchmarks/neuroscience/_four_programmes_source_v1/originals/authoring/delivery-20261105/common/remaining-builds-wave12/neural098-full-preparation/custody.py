"""Bounded immutable snapshot capture for explicitly selected source files.

Only a future selected driver calls these routines. Source construction and
tests do not open any authentic source asset.
"""
import hashlib
import math
import os
from pathlib import PurePosixPath
import stat
import sys
import time


class Refusal(ValueError):
    pass


def need(ok, why):
    if not ok:
        raise Refusal(why)


def relative(value):
    need(type(value) is str and value and len(value) <= 512 and value.isascii()
         and '\x00' not in value and '\\' not in value, 'bounded relative source name')
    p = PurePosixPath(value)
    need(not p.is_absolute() and all(x not in ('', '.', '..') for x in value.split('/'))
         and str(p) == value, 'canonical relative source name')
    return p.parts


def signature(s):
    return (s.st_dev, s.st_ino, s.st_mode, s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def below(root_fd, name, flags, mode=0o400):
    """No symlink in any descendant component; caller owns root_fd."""
    parts = relative(name)
    current = result = None
    try:
        current = os.dup(root_fd)
        for component in parts[:-1]:
            nxt = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                          dir_fd=current)
            previous, current = current, nxt
            # Consume the previous descriptor before closing. An error never
            # retries a potentially reused descriptor and cannot lose nxt.
            os.close(previous)
        result = os.open(parts[-1], flags | os.O_NOFOLLOW | os.O_NONBLOCK,
                         mode, dir_fd=current)
        previous, current = current, None
        os.close(previous)
        answer, result = result, None
        return answer
    finally:
        original = sys.exception()
        errors = []
        for fd in (result, current):
            if fd is not None:
                try: os.close(fd)
                except BaseException as exc: errors.append(exc)
        if errors:
            if original is not None and not isinstance(original, Exception): raise original
            raise errors[0] from original


class Budget:
    def __init__(self, *, deadline, read_cap, write_cap):
        need(type(deadline) is float and math.isfinite(deadline)
             and deadline > time.monotonic(), 'original deadline')
        for n in (read_cap, write_cap):
            need(type(n) is int and 0 < n <= 2**50, 'selected extent cap')
        self.deadline = deadline
        self.read_cap = read_cap
        self.write_cap = write_cap
        self.read = self.write = 0
        self.space = None

    def check(self):
        need(time.monotonic() < self.deadline, 'original preparation deadline')
        if self.space is not None:
            fd, minimum = self.space
            info = os.fstatvfs(fd)
            need(info.f_bavail * info.f_frsize >= minimum, 'protected physical floor and OTHER reservations')

    def charge(self, kind, n):
        self.check()
        need(type(n) is int and n >= 0, 'bounded I/O request')
        value = getattr(self, kind) + n
        need(value <= getattr(self, kind + '_cap'), 'whole preparation ' + kind + ' cap')
        setattr(self, kind, value)


def capture_file(source_root_fd, stage_root_fd, entry, budget):
    """Create one exclusive staged source; hash and stable-FD check before close.

    No cleanup removes failed evidence. The driver reserves a fresh private stage
    and later authenticates its complete declared closure before native loading.
    """
    need(type(entry) is dict and set(entry) == {'path', 'bytes', 'sha256'}, 'exact asset descriptor')
    relative(entry['path'])
    expected = entry['bytes']; wanted = entry['sha256']
    need(type(expected) is int and 0 < expected <= 2_000_000_000, 'canonical per-file domain')
    need(type(wanted) is str and len(wanted) == 64
         and all(c in '0123456789abcdef' for c in wanted), 'source SHA256')
    source = target = None
    try:
        source = below(source_root_fd, entry['path'], os.O_RDONLY)
        before = os.fstat(source)
        need(stat.S_ISREG(before.st_mode) and before.st_size == expected, 'selected ordinary source extent')
        target = below(stage_root_fd, entry['path'], os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        h = hashlib.sha256(); copied = 0
        while copied < expected:
            count = min(1 << 20, expected - copied)
            budget.charge('read', count)
            raw = os.read(source, count)
            need(raw, 'source truncated')
            budget.charge('write', len(raw))
            offset = 0
            while offset < len(raw):
                budget.check()
                n = os.write(target, raw[offset:])
                need(n > 0, 'source snapshot short write')
                offset += n
            h.update(raw); copied += len(raw)
        budget.charge('read', 1)
        need(os.read(source, 1) == b'', 'source grew')
        need(signature(before) == signature(os.fstat(source)), 'source changed during snapshot')
        need(h.hexdigest() == wanted, 'source snapshot hash')
        os.fsync(target)
        after = os.fstat(target)
        need(stat.S_ISREG(after.st_mode) and after.st_size == expected, 'closed snapshot extent')
        budget.check()
        return {'path': entry['path'], 'bytes': expected, 'sha256': wanted,
                'source_signature': list(signature(before)),
                'stage_signature': list(signature(after))}
    finally:
        original = sys.exception()
        errors = []
        for fd in (target, source):
            if fd is not None:
                try:
                    os.close(fd)
                except BaseException as exc:
                    errors.append(exc)
        if errors:
            if original is not None and not isinstance(original, Exception):
                raise original
            raise errors[0] from original
        if original is None:
            budget.check()


def read_pinned(root_fd, entry, budget, cap, *, expected_signature=None):
    """Small immutable metadata/source capture; body never printed by driver."""
    need(entry['bytes'] <= cap, 'selected capture cap')
    fd = below(root_fd, entry['path'], os.O_RDONLY)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_size == entry['bytes'], 'pinned ordinary capture')
        if expected_signature is not None:
            need(signature(before) == tuple(expected_signature), 'same staged capture')
        budget.charge('read', before.st_size + 1)
        chunks = []; remaining = before.st_size
        while remaining:
            budget.check(); raw = os.read(fd, min(remaining, 1 << 20))
            need(raw, 'capture truncation'); chunks.append(raw); remaining -= len(raw)
        need(os.read(fd, 1) == b'' and signature(before) == signature(os.fstat(fd)), 'stable capture')
        raw = b''.join(chunks)
        need(hashlib.sha256(raw).hexdigest() == entry['sha256'], 'selected capture hash')
        budget.check()
        return raw
    finally:
        original = sys.exception()
        try: os.close(fd)
        except BaseException as cleanup:
            if original is not None and not isinstance(original, Exception): raise original
            raise cleanup from original


def hash_staged(root_fd, entry, expected_signature, budget):
    fd = below(root_fd, entry['path'], os.O_RDONLY)
    try:
        before = os.fstat(fd)
        need(signature(before) == tuple(expected_signature), 'same complete staged source')
        remaining = entry['bytes']; h = hashlib.sha256()
        while remaining:
            n = min(remaining, 1 << 20); budget.charge('read', n)
            raw = os.read(fd, n); need(raw, 'staged source truncated')
            h.update(raw); remaining -= len(raw)
        budget.charge('read', 1)
        need(os.read(fd, 1) == b'' and signature(before) == signature(os.fstat(fd))
             and h.hexdigest() == entry['sha256'], 'whole staged source post-read hash')
        budget.check()
    finally:
        original = sys.exception()
        try: os.close(fd)
        except BaseException as cleanup:
            if original is not None and not isinstance(original, Exception): raise original
            raise cleanup from original


def write_exclusive(root_fd, name, raw, budget, cap):
    need(type(raw) is bytes and 0 < len(raw) <= cap, 'bounded complete output')
    budget.charge('write', len(raw))
    fd = below(root_fd, name, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    try:
        offset = 0
        while offset < len(raw):
            budget.check(); count = os.write(fd, raw[offset:offset + (1 << 20)])
            need(count > 0, 'output short write'); offset += count
        os.fsync(fd)
        need(os.fstat(fd).st_size == len(raw), 'whole output extent')
    finally:
        original = sys.exception()
        try: os.close(fd)
        except BaseException as cleanup:
            if original is not None and not isinstance(original, Exception): raise original
            raise cleanup from original
    os.fsync(root_fd); budget.check()
    return {'path': name, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
