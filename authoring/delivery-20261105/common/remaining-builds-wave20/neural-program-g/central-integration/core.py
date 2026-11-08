"""Bounded ordinary metadata custody. No numerical, provider or model operation."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import time


def need(ok, message):
    if not ok:
        raise ValueError(message)


def number(x):
    return type(x) in (int, float) and math.isfinite(x)


def integer(x, minimum=0):
    need(type(x) is int and x >= minimum, 'Typed bounded integer')
    return x


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def descriptor(d, empty=False):
    need(type(d) is dict and set(d) == {'bytes', 'sha256'}, 'Exact byte descriptor')
    integer(d['bytes'], 0 if empty else 1)
    need(type(d['sha256']) is str and re.fullmatch('[0-9a-f]{64}', d['sha256']), 'SHA256 descriptor')
    return d


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def decode(raw, depth=64, nodes=2000000):
    need(type(raw) is bytes, 'Captured encoded JSON')
    # Enforce encoded structural depth before the JSON decoder allocates a tree.
    nesting = count = 0
    quoted = escaped = False
    for c in raw:
        if quoted:
            if escaped:
                escaped = False
            elif c == 92:
                escaped = True
            elif c == 34:
                quoted = False
            continue
        if c == 34:
            quoted = True
        elif c in (91, 123):
            nesting += 1
            need(nesting <= depth, 'Encoded JSON depth ceiling')
        elif c in (93, 125):
            nesting -= 1
            need(nesting >= 0, 'Encoded JSON nesting')
        if c in (44, 58, 91, 123):
            count += 1
            need(count <= nodes, 'Encoded JSON node ceiling')
    need(not quoted and nesting == 0, 'Complete encoded JSON structure')
    def pairs(rows):
        result = {}
        for key, value in rows:
            need(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result
    value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                       parse_constant=lambda _: need(False, 'Nonfinite JSON'))
    pending = [value]
    visited = 0
    while pending:
        item = pending.pop(); visited += 1
        need(visited <= nodes, 'Decoded JSON node ceiling')
        if type(item) is dict:
            pending.extend(item.values())
        elif type(item) is list:
            pending.extend(item)
        elif type(item) is float:
            need(math.isfinite(item), 'Finite JSON number')
    return value


def path(value):
    p = Path(value)
    need(p.is_absolute() and '..' not in p.parts and p.as_posix() == str(value), 'Canonical absolute path')
    need(len(str(p).encode()) <= 4096 and not any(c in str(p) for c in ('\0', '\n', '\r', ',')), 'Bounded unambiguous ordinary path')
    need(not any(x.is_symlink() for x in (p, *p.parents)), 'No linked path component')
    return p


def relative(value):
    need(type(value) is str and value and not value.startswith('/') and '\\' not in value
         and all(x not in ('', '.', '..') for x in value.split('/')), 'Confined relative path')
    return value


class Meter:
    def __init__(self, read_bytes, write_bytes, end, member_cap=16*1024*1024,
                 depth=64, nodes=2000000):
        self.read_cap, self.write_cap = integer(read_bytes, 1), integer(write_bytes, 1)
        need(number(end), 'Absolute closeout deadline')
        self.end, self.member_cap, self.depth, self.nodes = end, integer(member_cap, 1), depth, nodes
        self.read_bytes = self.write_bytes = 0
        self.index = {}
        self.owned_roots = []
        self.path_reads = {}

    def check(self):
        need(time.monotonic() < self.end, 'Original selected closeout deadline')

    def tick(self):
        self.check()
        return time.monotonic()

    def reserve_read(self, size):
        self.check(); integer(size)
        need(self.read_bytes + size <= self.read_cap, 'Complete logical read reservation')

    def read(self, size):
        self.reserve_read(size); self.read_bytes += size

    def write(self, size):
        self.check(); integer(size)
        need(self.write_bytes + size <= self.write_cap, 'Cumulative central write ceiling')
        self.write_bytes += size


def capture(value, expected=None, meter=None, cap=None):
    p = path(value)
    if expected is not None:
        descriptor(expected, True)
    limit = cap if cap is not None else (meter.member_cap if meter else 16*1024*1024)
    integer(limit, 1)
    if meter:
        meter.check()
        if any(p == root or p.is_relative_to(root) for root in meter.owned_roots):
            count = meter.path_reads.get(str(p), 0) + 1
            need(count <= 3, 'At most three complete captures of each parent-published output')
            meter.path_reads[str(p)] = count
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= limit,
             'Bounded ordinary single-link metadata')
        if expected is not None:
            need(before.st_size == expected['bytes'], 'Expected metadata extent')
        if meter:
            meter.reserve_read(before.st_size + 1)
        chunks = []; size = 0
        while size <= before.st_size:
            if meter:
                meter.check()
            chunk = os.read(fd, min(65536, before.st_size + 1-size))
            if meter:
                meter.read(len(chunk))
            if not chunk:
                break
            chunks.append(chunk); size += len(chunk)
        after, current = os.fstat(fd), p.lstat()
        fields = ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_nlink')
        need(size == before.st_size and all(getattr(before,k)==getattr(after,k)==getattr(current,k) for k in fields),
             'Captured exact stable metadata inode')
        raw = b''.join(chunks); actual = pin(raw)
        need(expected is None or actual == expected, 'Exact metadata content')
        if meter:
            old = meter.index.setdefault(str(p), actual)
            need(old == actual, 'No operand replacement during readback')
        return raw
    finally:
        os.close(fd)


def read_json(value, meter, expected=None):
    return decode(capture(value, expected, meter), meter.depth, meter.nodes)


def sync_directory(value):
    fd = os.open(path(value), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def publish(value, raw, meter):
    p = path(value); need(type(raw) is bytes, 'Exact output bytes')
    meter.write(len(raw))
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        offset = 0
        while offset < len(raw):
            meter.check(); written = os.write(fd, raw[offset:])
            need(written > 0, 'Complete output write'); offset += written
        os.fsync(fd)
    finally:
        os.close(fd)
    sync_directory(p.parent)
    return pin(raw)


def directory(value, fresh=False):
    p = path(value)
    if fresh:
        need(not p.exists(), 'Fresh operation path')
        p.mkdir(mode=0o700); sync_directory(p.parent)
    info = p.stat()
    need(stat.S_ISDIR(info.st_mode), 'Ordinary operation directory')
    return p


def inventory(root, meter, count_cap):
    """Stat-only complete tree; numerical bodies are never opened."""
    root = directory(root); result = {}; pending = [root]
    while pending:
        current = pending.pop(); meter.check()
        before = current.stat()
        with os.scandir(current) as entries:
            for item in entries:
                meter.check(); need(len(result) < count_cap, 'Complete tree member bound')
                info = item.stat(follow_symlinks=False)
                relative_name = str(Path(item.path).relative_to(root))
                need(len(relative_name.encode())<=4096 and len(str(item.path).encode())<=4096,
                     'Finite full and relative output path representations')
                need(not stat.S_ISLNK(info.st_mode), 'No linked output member')
                if stat.S_ISDIR(info.st_mode):
                    kind = 'directory'; pending.append(Path(item.path))
                else:
                    need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, 'Ordinary single-link output')
                    kind = 'file'
                result[relative_name] = {'kind':kind,'bytes':info.st_size,'dev':info.st_dev,
                    'ino':info.st_ino,'mtime_ns':info.st_mtime_ns,'ctime_ns':info.st_ctime_ns}
        after = current.stat()
        need((before.st_dev,before.st_ino,before.st_mtime_ns,before.st_ctime_ns)==
             (after.st_dev,after.st_ino,after.st_mtime_ns,after.st_ctime_ns), 'Stable directory census')
    return result
