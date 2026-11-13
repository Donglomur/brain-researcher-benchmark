"""Ordinary controller custody; not a native resource or input authority issuer."""
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
import stat
import sys
import time


class Refusal(RuntimeError):
    pass


@dataclass(frozen=True)
class ErrorOccurrence:
    owner: object
    index: int
    boundary: str
    raw: BaseException
    traceback: object


class Custody:
    def __init__(self, parent=None):
        self.parent = parent
        self.events = []
        self._seen = set()

    def catch(self, boundary, raw):
        # A fresh catch is an occurrence even when raw was raised previously.
        event = ErrorOccurrence(self, len(self.events), boundary, raw, sys.exc_info()[2])
        self.merge(event)
        return event

    def merge(self, event):
        key = (event.owner, event.index)
        if key in self._seen:
            return
        self._seen.add(key)
        self.events.append(event)
        if self.parent is not None:
            self.parent.merge(event)

    @property
    def first(self):
        return self.events[0] if self.events else None

    def raise_first(self):
        if self.first is not None:
            event = self.first
            raise BaseException.with_traceback(event.raw, event.traceback)

    @contextmanager
    def attempt(self, name):
        before = len(self.events)
        try:
            yield self
        except BaseException as error:
            # Nested operations explicitly merge their existing occurrence first.
            if len(self.events) == before:
                self.catch(name, error)
            self.raise_first()

    def close(self, name, close):
        try:
            close()
        except BaseException as error:
            self.catch(name, error)


class Budget:
    """Monotone logical controller accounting; native CPU/RSS/IO remain separate."""
    def __init__(self, *, read_bytes, write_bytes, files, deadline, custody):
        values = (read_bytes, write_bytes, files)
        if any(type(v) is not int or v <= 0 for v in values):
            raise Refusal('explicit positive controller limits required')
        if type(deadline) not in (int, float) or not time.monotonic() < deadline:
            raise Refusal('live original monotonic deadline required')
        self.limits = dict(read=read_bytes, write=write_bytes, files=files)
        self.reserved = dict.fromkeys(self.limits, 0)
        self.known = dict.fromkeys(self.limits, 0)
        self.pending = []
        self.deadline = deadline
        self.custody = custody
        self.closed = False

    def checkpoint(self):
        if self.closed or self.custody.first is not None:
            self.custody.raise_first()
            raise Refusal('closed budget')
        if time.monotonic() >= self.deadline:
            raise Refusal('controller deadline')

    def reserve(self, domain, amount):
        self.checkpoint()
        if domain not in self.limits or type(amount) is not int or amount < 0:
            raise Refusal('invalid logical reservation')
        if self.reserved[domain] + amount > self.limits[domain]:
            raise Refusal('logical budget exceeded')
        self.reserved[domain] += amount
        token = [domain, amount, None]
        self.pending.append(token)
        return token

    def observed(self, token, amount):
        if not any(x is token for x in self.pending) or token[2] is not None:
            raise Refusal('reservation identity/reuse')
        if type(amount) is not int or not 0 <= amount <= token[1]:
            raise Refusal('invalid observed extent')
        token[2] = amount
        self.known[token[0]] += amount
        # Original reservation is never refunded, including an unknown prefix.

    def report(self):
        return {'limits': dict(self.limits), 'reserved': dict(self.reserved),
                'known': dict(self.known), 'unknown_reservations':
                [[d, n] for d, n, used in self.pending if used is None],
                'native_costs': 'not_observed_by_controller'}


def relative_name(name):
    if type(name) is not str or not name or '\\' in name or '\x00' in name:
        raise Refusal('invalid relative name')
    if any(x in ('', '.', '..') for x in name.split('/')):
        raise Refusal('invalid path component')
    return name


def open_parent(root_fd, name, custody):
    parts = relative_name(name).split('/')
    fd = os.dup(root_fd)
    try:
        for part in parts[:-1]:
            nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            old, fd = fd, nxt
            os.close(old)
        return fd, parts[-1]
    except BaseException as error:
        custody.catch('path traversal', error)
        custody.close('path traversal close', lambda: os.close(fd))
        custody.raise_first()


@dataclass(frozen=True)
class Captured:
    relative: str
    bytes: int
    sha256: str
    stat_identity: tuple


def read_exact(root_fd, name, expected_bytes, expected_sha256, budget, custody):
    """Read ordinary/input bytes only when called by an admitted future operator."""
    local = Custody(custody)
    parent = fd = None
    chunks = []
    with local.attempt('capture'):
        try:
            token = budget.reserve('read', expected_bytes)
            parent, leaf = open_parent(root_fd, name, local)
            fd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or before.st_size != expected_bytes:
                raise Refusal('input type/extent')
            digest = hashlib.sha256()
            remaining = expected_bytes
            while remaining:
                budget.checkpoint()
                block = os.read(fd, min(65536, remaining))
                if not block:
                    raise Refusal('short read')
                chunks.append(block)
                digest.update(block)
                remaining -= len(block)
            after = os.fstat(fd)
            identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
            if identity(before) != identity(after) or digest.hexdigest() != expected_sha256:
                raise Refusal('input changed or digest mismatch')
            budget.observed(token, expected_bytes)
            result = Captured(name, expected_bytes, digest.hexdigest(), identity(after))
        except BaseException as error:
            if local.first is None:
                local.catch('capture body', error)
        finally:
            if fd is not None:
                local.close('input close', lambda: os.close(fd))
            if parent is not None:
                local.close('input parent close', lambda: os.close(parent))
        local.raise_first()
    return b''.join(chunks), result


def write_exact(root_fd, name, data, budget, custody):
    local = Custody(custody)
    parent = fd = None
    with local.attempt('write'):
        try:
            token = budget.reserve('write', len(data))
            creation = budget.reserve('files', 1)
            parent, leaf = open_parent(root_fd, name, local)
            fd = os.open(leaf, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o600, dir_fd=parent)
            budget.observed(creation, 1)
            done = 0
            while done < len(data):
                budget.checkpoint()
                n = os.write(fd, memoryview(data)[done:done + 65536])
                if not 0 < n <= min(65536, len(data) - done):
                    raise Refusal('invalid/zero write')
                done += n
            os.fsync(fd)
            if os.fstat(fd).st_size != len(data):
                raise Refusal('written extent mismatch')
            budget.observed(token, done)
        except BaseException as error:
            if local.first is None:
                local.catch('write body', error)
        finally:
            if fd is not None:
                local.close('output close', lambda: os.close(fd))
            if parent is not None:
                local.close('output parent close', lambda: os.close(parent))
        local.raise_first()
    return {'name': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def encode_json(value):
    return (json.dumps(value, sort_keys=True, allow_nan=False, separators=(',', ':')) + '\n').encode()
