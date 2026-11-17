"""Trusted-host immutable captures and explicit logical interface accounting.

This is not an OS sandbox, heap meter, authority issuer or process observer.
Call only from a separately trusted, serialized operator process.
"""
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import time


def need(ok, why):
    if not ok:
        raise ValueError(why)


def pin(raw):
    need(type(raw) is bytes, 'immutable captured bytes')
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def descriptor(row, cap):
    need(type(row) is dict and set(row) == {'bytes', 'sha256'} and
         type(row['bytes']) is int and 0 < row['bytes'] <= cap and
         type(row['sha256']) is str and re.fullmatch('[0-9a-f]{64}', row['sha256']),
         'exact bounded descriptor')
    return row


def parse(raw):
    def pairs(items):
        out = {}
        for key, value in items:
            need(key not in out, 'duplicate JSON key')
            out[key] = value
        return out
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, 'nonfinite JSON token'))


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'),
                       allow_nan=False) + '\n').encode('utf-8')


def path(value):
    p = Path(value)
    need(p.is_absolute() and '..' not in p.parts and
         not any(x in str(p) for x in ('\x00', '\n', '\r', ',')) and
         not any(x.is_symlink() for x in (p, *p.parents)), 'ordinary absolute path')
    return p


@dataclass
class Budget:
    max_read_bytes: int
    max_write_bytes: int
    deadline: float
    read_bytes: int = 0
    write_bytes: int = 0

    def __post_init__(self):
        need(type(self.max_read_bytes) is int and self.max_read_bytes > 0 and
             type(self.max_write_bytes) is int and self.max_write_bytes > 0 and
             type(self.deadline) in (int, float) and math.isfinite(self.deadline) and
             self.deadline > time.monotonic() and self.read_bytes == self.write_bytes == 0,
             'explicit positive grading resource operands and fresh counters')

    def tick(self):
        need(time.monotonic() < self.deadline, 'grading deadline')

    def read(self, n, label='interface read'):
        self.tick()
        need(type(n) is int and n >= 0 and self.read_bytes + n <= self.max_read_bytes,
             'read capacity: ' + label)
        self.read_bytes += n

    def write(self, n, label='interface write'):
        self.tick()
        need(type(n) is int and n >= 0 and self.write_bytes + n <= self.max_write_bytes,
             'write capacity: ' + label)
        self.write_bytes += n

    def decoded(self, raw, label):
        # Charge serialized parser input and a same-byte decoded-interface
        # reservation. Python object overhead is a separate live-memory limit.
        self.read(len(raw), label + ' parse input')
        self.write(len(raw), label + ' decoded interface')
        return parse(raw)

    def record(self):
        return {'read_bytes': self.read_bytes, 'write_bytes': self.write_bytes,
                'read_limit': self.max_read_bytes, 'write_limit': self.max_write_bytes,
                'physical_io_or_heap_measured': False, 'failed_costs_retained': True}


class Captures:
    """Read each named body once; reuse immutable bytes, recheck physical identity."""
    FIELDS = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_uid',
              'st_gid', 'st_mtime_ns', 'st_ctime_ns')

    def __init__(self, budget):
        self.budget = budget
        self.cache = {}
        self.identities = {}

    @classmethod
    def stamp(cls, s):
        return tuple(getattr(s, k) for k in cls.FIELDS)

    def read(self, name, cap, expected=None, allow_empty=False):
        self.budget.tick()
        p = path(name)
        if expected is not None:
            descriptor(expected, cap)
        if p in self.cache:
            raw = self.cache[p]
            need(self.stamp(p.lstat()) == self.identities[p], 'unchanged captured pathname')
            self.budget.read(len(raw), 'cached interface bytes')
        else:
            fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            try:
                before = os.fstat(fd)
                need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
                     (0 if allow_empty else 1) <= before.st_size <= cap,
                     'bounded single-link ordinary file')
                need(expected is None or before.st_size == expected['bytes'], 'extent before body')
                self.budget.read(before.st_size + 1, 'file capture')
                self.budget.write(before.st_size, 'immutable capture buffer')
                with os.fdopen(fd, 'rb', closefd=False) as stream:
                    raw = stream.read(before.st_size + 1)
                need(len(raw) == before.st_size and self.stamp(before) == self.stamp(os.fstat(fd))
                     == self.stamp(p.lstat()), 'stable complete descriptor and named body')
                self.identities[p] = self.stamp(before)
                self.cache[p] = raw
            finally:
                os.close(fd)
        need((allow_empty or len(raw) > 0) and len(raw) <= cap and
             (expected is None or pin(raw) == expected), 'captured content identity')
        self.budget.tick()
        return raw

    def seal(self):
        for p, identity in self.identities.items():
            self.budget.tick()
            need(self.stamp(path(p).lstat()) == identity, 'same final captured names')

