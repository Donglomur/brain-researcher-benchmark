"""Strict metadata and ordinary-file custody for the full Sleep Cassette programme.

Importing this module performs no I/O, data loading, provider or scientific work.
"""
from __future__ import annotations
import ast
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import struct
import time

CLASSES = ('W', 'N1', 'N2', 'N3', 'R')
VIEWS = {'C': (), 'EC': (0, 1), 'OC': (2,), 'EOC': (0, 1, 2)}
CHANNELS = ('EEG Fpz-Cz', 'EEG Pz-Oz', 'EOG horizontal')
MODES = ('frozen_program', 'case_adaptive_equal_inputs_tools_compute')
PROFILES = ('generic_current_person', 'training_only_reuse')


def need(value, message):
    if not value:
        raise ValueError(message)


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode('utf-8')


def decode(body, cap=8 * 1024 * 1024):
    need(type(body) is bytes and 0 < len(body) <= cap, 'Bounded nonempty JSON bytes')
    def pairs(rows):
        result = {}
        for key, value in rows:
            need(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result
    def real(token):
        value = float(token)
        need(math.isfinite(value), 'Finite JSON float')
        need(value != 0 or not any(c in '123456789' for c in token.lower().split('e')[0]), 'No nonzero underflow')
        return value
    def no_constant(_):
        raise ValueError('Nonfinite JSON constant')
    value = json.loads(body.decode('utf-8'), object_pairs_hook=pairs, parse_float=real, parse_constant=no_constant)
    def check(node, depth):
        need(depth <= 48, 'Bounded JSON depth')
        if isinstance(node, dict):
            for k, v in node.items():
                need(type(k) is str and '\0' not in k, 'Ordinary JSON keys')
                check(v, depth + 1)
        elif isinstance(node, list):
            for v in node:
                check(v, depth + 1)
        elif isinstance(node, int) and not isinstance(node, bool):
            need(abs(node) <= 2**63 - 1, 'Bounded JSON integer')
        elif isinstance(node, str):
            need('\0' not in node, 'No NUL in text')
    check(value, 0)
    return value


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def descriptor(value):
    need(type(value) is dict and set(value) == {'bytes', 'sha256'}, 'Exact byte descriptor')
    need(type(value['bytes']) is int and value['bytes'] >= 0, 'Nonnegative extent')
    need(type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}', value['sha256']), 'Lowercase SHA256')
    return value


def ordinary(path):
    path = Path(path)
    need(path.is_absolute(), 'Absolute local path')
    need(not any(p.is_symlink() for p in (path, *path.parents)), 'No symlink component')
    st = path.stat()
    need(stat.S_ISREG(st.st_mode) and st.st_nlink == 1, 'Ordinary singly linked file')
    return path, st


def relative(name):
    need(type(name) is str and name and '\0' not in name and '\\' not in name, 'Ordinary relative name')
    q = PurePosixPath(name)
    need(not q.is_absolute() and str(q) == name and all(x not in ('.', '..') for x in q.parts), 'Canonical relative path')
    return name


class Meter:
    """Precharged logical I/O and original-clock accounting, not measured physical I/O."""
    def __init__(self, read_bytes, write_bytes, origin, deadline):
        need(all(type(x) is int and x >= 0 for x in (read_bytes, write_bytes)), 'Explicit I/O limits')
        need(all(type(x) in (int, float) and math.isfinite(x) for x in (origin, deadline)) and 0 <= origin < deadline, 'Original clock')
        self.read_limit, self.write_limit = read_bytes, write_bytes
        self.read_bytes = self.write_bytes = 0
        self.origin, self.deadline = origin, deadline
    def tick(self):
        now = time.monotonic()
        need(self.origin <= now < self.deadline, 'Original deadline expired')
        return now
    def read(self, n):
        self.tick(); need(type(n) is int and n >= 0 and self.read_bytes + n <= self.read_limit, 'Read allocation')
        self.read_bytes += n
    def write(self, n):
        self.tick(); need(type(n) is int and n >= 0 and self.write_bytes + n <= self.write_limit, 'Write allocation')
        self.write_bytes += n
    def report(self):
        return {'logical_read_bytes': self.read_bytes, 'logical_write_bytes': self.write_bytes,
                'origin': self.origin, 'deadline': self.deadline, 'observed_at': time.monotonic(),
                'physical_io_and_peak_rss': None}


def capture(path, expected=None, cap=8 * 1024 * 1024, meter=None):
    path, st = ordinary(path)
    need(0 <= st.st_size <= cap, 'Bounded captured file')
    if expected is not None:
        descriptor(expected); need(st.st_size == expected['bytes'], 'Exact declared extent')
    if meter:
        meter.read(st.st_size + 1)
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
    fd = os.open(path, flags)
    try:
        before = os.fstat(fd)
        need((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
             (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns), 'Same admitted inode')
        chunks, remaining = [], st.st_size + 1
        while remaining:
            b = os.read(fd, min(65536, remaining))
            if not b:
                break
            chunks.append(b); remaining -= len(b)
        body = b''.join(chunks)
        after = os.fstat(fd)
        need((after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_nlink) ==
             (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, 1), 'Stable captured file')
    finally:
        os.close(fd)
    need(len(body) == st.st_size, 'No growth or truncation')
    if expected is not None:
        need(pin(body) == expected, 'Exact captured bytes')
    return body


def stream_pin(path, expected, meter=None, chunk_bytes=65536):
    """Authenticate a large ordinary artifact without materializing it in host RAM."""
    descriptor(expected); path, st = ordinary(path)
    need(st.st_size == expected['bytes'], 'Complete large artifact extent')
    value, count = hashlib.sha256(), 0
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    try:
        before = os.fstat(fd)
        need((before.st_dev, before.st_ino) == (st.st_dev, st.st_ino), 'Same stream inode')
        while True:
            n = min(chunk_bytes, expected['bytes'] - count + 1)
            if meter:
                meter.read(n)
            b = os.read(fd, n)
            if not b:
                break
            count += len(b); need(count <= expected['bytes'], 'No trailing bytes')
            value.update(b)
        after = os.fstat(fd)
        need((before.st_size, before.st_mtime_ns, before.st_nlink) ==
             (after.st_size, after.st_mtime_ns, after.st_nlink) and after.st_nlink == 1, 'Stable large artifact')
    finally:
        os.close(fd)
    result = {'bytes': count, 'sha256': value.hexdigest()}
    need(result == expected, 'Large artifact identity')
    return result


def publish(path, body, meter=None, readonly=True):
    path = Path(path)
    need(path.is_absolute() and not path.exists() and not path.is_symlink(), 'Fresh publication path')
    need(path.parent.is_dir() and not any(p.is_symlink() for p in path.parents), 'Ordinary publication parents')
    need(type(body) is bytes, 'Exact bytes publication')
    if meter:
        meter.write(len(body))
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    try:
        offset = 0
        while offset < len(body):
            n = os.write(fd, body[offset:]); need(n > 0, 'Complete publication write'); offset += n
        os.fsync(fd)
        if readonly:
            os.fchmod(fd, 0o444)
    finally:
        os.close(fd)
    dfd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)
    return pin(body)


def npy_header(path, expected_bytes=None, meter=None):
    """Header/geometry only; never calls NumPy or reads a numerical payload."""
    path, st = ordinary(path)
    with path.open('rb') as f:
        if meter: meter.read(8)
        prefix = f.read(8)
        need(prefix[:6] == b'\x93NUMPY' and prefix[6:] in (b'\x01\x00', b'\x02\x00'), 'Supported NPY version')
        width = 2 if prefix[6] == 1 else 4
        if meter: meter.read(width)
        raw = f.read(width); need(len(raw) == width, 'Complete header extent')
        n = int.from_bytes(raw, 'little'); need(0 < n <= 4096, 'Bounded NPY header')
        if meter: meter.read(n)
        body = f.read(n); need(len(body) == n and body.endswith(b'\n'), 'Complete NPY header')
    return npy_layout(prefix + raw + body, st.st_size, expected_bytes)


def npy_layout(raw, file_bytes, expected_bytes=None):
    """Parse the exact consumed header, never an offset from another reopen."""
    need(type(raw) is bytes and len(raw) >= 10 and raw[:6] == b'\x93NUMPY' and raw[6:8] in (b'\x01\x00', b'\x02\x00'), 'Supported consumed NPY prefix')
    width=2 if raw[6]==1 else 4
    n=int.from_bytes(raw[8:8+width],'little')
    need(0<n<=4096 and len(raw)==8+width+n and raw.endswith(b'\n'), 'Exact bounded consumed header extent')
    value=ast.literal_eval(raw[8+width:].decode('latin1'))
    need(type(value) is dict and set(value)=={'descr','fortran_order','shape'}, 'Exact consumed NPY dictionary')
    need(value['descr'] in ('<f8','|i1','|b1') and value['fortran_order'] is False, 'Plain consumed numeric layout')
    shape=value['shape'];need(type(shape) is tuple and 1<=len(shape)<=2 and all(type(x) is int and x>0 for x in shape),'Positive one/two-dimensional geometry')
    itemsize=8 if value['descr']=='<f8' else 1
    size=len(raw)+math.prod(shape)*itemsize
    need(file_bytes==size and (expected_bytes is None or size==expected_bytes), 'Exact complete consumed geometry/extent')
    return {'dtype':value['descr'],'shape':list(shape),'header_bytes':len(raw),'bytes':size}


class DecodingStream:
    """Hash the exact original bytes consumed by a sequential decoder.

    finish drains preserved unparsed tail bytes and checks publisher identity;
    no successful derived index can cite a hash from an earlier separate read.
    """
    def __init__(self, path, expected, meter):
        self.path, self.before = ordinary(path); self.expected = descriptor(expected); self.meter = meter
        need(self.before.st_size == expected['bytes'], 'Exact decoding extent')
        self.fd = os.open(self.path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
        try:
            st = os.fstat(self.fd); need((st.st_dev, st.st_ino) == (self.before.st_dev, self.before.st_ino), 'Exact decoder inode')
        except BaseException:
            os.close(self.fd); raise
        self.hash = hashlib.sha256(); self.count = 0; self.done = False
    def read(self, n):
        need(type(n) is int and n >= 0 and not self.done, 'Bounded sequential decoder read')
        self.meter.read(n); body = os.read(self.fd, n); self.count += len(body)
        need(self.count <= self.expected['bytes'], 'No decoding growth'); self.hash.update(body); return body
    def finish(self):
        while self.read(min(65536, self.expected['bytes'] - self.count + 1)): pass
        st = os.fstat(self.fd)
        need((st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_nlink) ==
             (self.before.st_dev, self.before.st_ino, self.before.st_size, self.before.st_mtime_ns, 1), 'Stable exact consumed source')
        need({'bytes': self.count, 'sha256': self.hash.hexdigest()} == self.expected, 'Publisher hash of exact decoding stream')
        self.done = True
    def close(self): os.close(self.fd)
    def __enter__(self): return self
    def __exit__(self, kind, value, traceback):
        try:
            if kind is None: self.finish()
        finally: self.close()
