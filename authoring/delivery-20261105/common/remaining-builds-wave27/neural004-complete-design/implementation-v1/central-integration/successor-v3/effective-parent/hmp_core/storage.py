"""Safe explicit numerical artifacts. No pickle, executable state, or callbacks.

Checks are cooperative; the qualified enclosing process supplies hard clock/RSS
and filesystem enforcement. Known array/serialization extents are not whole RSS.
"""
import hashlib
import json
import math
import os
import stat
from pathlib import Path
from .schedule import need


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def identity(info):
    """Stable same-open/name custody; reading may legitimately update atime."""
    return tuple(getattr(info, key) for key in (
        'st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_uid', 'st_gid',
        'st_size', 'st_mtime_ns', 'st_ctime_ns'))


def primary_close(fd, error=None):
    try:
        os.close(fd)
    except BaseException as later:
        if error is None:
            error = later
        else:
            error.add_note('independent close failure: ' + type(later).__name__)
    if error is not None:
        raise error


class Session:
    def __init__(self, limits, inherited_context):
        self.context = inherited_context
        for name in ('tick', 'reserve', 'fail'):
            need(callable(getattr(inherited_context, name, None)), 'source-owned ledger interface: ' + name)
        self.limits = dict(limits)
        for name in ('read_bytes', 'write_bytes', 'retained_bytes', 'live_bytes', 'metadata_bytes', 'source_bytes'):
            need(type(limits.get(name)) is int and limits[name] > 0, 'ordinary selected finite cap: ' + name)
        self.cost = {'read_bytes': 0, 'write_bytes': 0, 'retained_bytes': 0,
                     'serialized_bytes': 0, 'known_live_max': 0, 'failed_publications': 0}
        self.response_extent = 0
        self.tick()

    def tick(self):
        self.context.tick()

    def charge(self, kind, count, detail):
        need(type(count) is int and count >= 0, 'ordinary nonnegative charge')
        self.tick()
        self.context.reserve(kind, count, detail)
        self.tick()

    def live(self, count, detail):
        need(type(count) is int and 0 <= count <= self.limits['live_bytes'], 'known allocation extent')
        self.cost['known_live_max'] = max(self.cost['known_live_max'], count)
        self.charge('known_live_bytes', count, detail)

    def response(self, additional, temporary=0):
        """Conservative known representation retention, independent of full RSS."""
        need(type(additional)is int and additional>=0,'ordinary response reservation')
        self.live(self.response_extent+additional+temporary,'cumulative known tool response retention')
        self.response_extent+=additional

    def read(self, path, descriptor, source=False):
        size = descriptor['bytes']
        need(type(size) is int and 0 <= size <= (self.limits['source_bytes'] if source else self.limits['live_bytes']), 'declared bounded body')
        need(self.cost['read_bytes'] + size + 1 <= self.limits['read_bytes'], 'cumulative read cap')
        self.charge('source_read_bytes' if source else 'array_read_bytes', size + 1, str(path))
        self.cost['read_bytes'] += size + 1
        path = Path(path)
        need(not any(p.is_symlink() for p in (path, *path.parents)), 'ordinary source/artifact path')
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        error = None
        try:
            before = os.fstat(fd)
            need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == size, 'ordinary exact body extent')
            self.live(2 * size + 1, 'bounded capture and join')
            parts = []; left = size + 1
            while left:
                self.tick(); chunk = os.read(fd, min(left, 65536))
                if not chunk: break
                parts.append(chunk); left -= len(chunk)
            raw = b''.join(parts)
            need(identity(os.fstat(fd)) == identity(before) and identity(path.stat()) == identity(before), 'unchanged same-open body')
            need(pin(raw) == {k: descriptor[k] for k in ('bytes', 'sha256')}, 'exact body pin')
            self.tick()
        except BaseException as exc:
            error = exc
        primary_close(fd, error)
        self.tick()
        return raw


class Store:
    def __init__(self, session, root):
        self.session = session
        self.root = Path(root)
        need(self.root.is_absolute() and not any(p.is_symlink() for p in (self.root, *self.root.parents)), 'absolute ordinary output namespace')
        need(not os.path.lexists(self.root), 'fresh output namespace')
        session.tick(); self.root.mkdir(); session.tick()
        self.members = []

    def _name(self, name):
        need(type(name) is str and name and '/' not in name and '\\' not in name and name not in ('.', '..'), 'single artifact name')
        return self.root / name

    def write(self, name, raw, serialized=True):
        s = self.session; path = self._name(name); n = len(raw)
        need(s.cost['write_bytes'] + n <= s.limits['write_bytes'] and s.cost['retained_bytes'] + n <= s.limits['retained_bytes'], 'cumulative output and retained caps')
        s.charge('artifact_write_bytes', n, name)
        s.charge('retained_bytes', n, name)
        s.cost['write_bytes'] += n; s.cost['retained_bytes'] += n
        if serialized:
            s.charge('serialized_bytes', n, name); s.cost['serialized_bytes'] += n
        s.tick(); fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
        error = None
        try:
            offset = 0
            while offset < n:
                s.tick(); wrote = os.write(fd, memoryview(raw)[offset:]); need(wrote > 0, 'positive write progress'); offset += wrote
            os.fsync(fd); s.tick()
        except BaseException as exc:
            error = exc; s.cost['failed_publications'] += 1
        primary_close(fd, error)
        dfd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW); error = None
        try: os.fsync(dfd)
        except BaseException as exc: error = exc
        primary_close(dfd, error)
        s.tick()
        descriptor = {'name': name, **pin(raw)}
        self.members.append(descriptor)
        return descriptor

    def json(self, name, document):
        s = self.session; chunks = []; count = 0
        for part in json.JSONEncoder(sort_keys=True, separators=(',', ':'), allow_nan=False).iterencode(document):
            size = len(part.encode('utf-8'))
            need(count + size <= s.limits['metadata_bytes'], 'complete metadata encoding cap')
            s.live(2 * (count + size), 'JSON chunks and final join')
            s.charge('serialized_bytes', size, name); s.cost['serialized_bytes'] += size
            chunks.append(part); count += size
        # Each chunk's encoding and the final joined encoding are distinct work.
        s.charge('serialized_bytes',count,name+' final encoding');s.cost['serialized_bytes']+=count
        raw = ''.join(chunks).encode('utf-8')
        return self.write(name, raw, serialized=False)

    def array(self, name, array, axes, unit, allow_nonfinite=False):
        import numpy as np
        s = self.session
        need(isinstance(array, np.ndarray) and array.dtype.kind in 'fiu b'.replace(' ', ''), 'explicit primitive numerical array')
        need(len(axes) == array.ndim and len(set(axes)) == len(axes), 'named array axes')
        dtype = '<f8' if array.dtype.kind == 'f' else '<i8' if array.dtype.kind in 'iu' else '|u1'
        size = int(array.size) * (1 if dtype == '|u1' else 8)
        s.live(int(array.nbytes) + 2 * size, 'explicit endian conversion and bytes')
        if not allow_nonfinite: need(bool(np.isfinite(array).all()), 'finite array required')
        if array.dtype.kind == 'u': need(bool((array <= np.iinfo(np.int64).max).all()), 'lossless signed integer conversion')
        s.charge('serialized_bytes',size,name);s.cost['serialized_bytes']+=size
        s.tick(); raw = array.astype(dtype, copy=False).tobytes(order='C'); s.tick()
        need(len(raw) == size, 'exact array encoding extent')
        return {**self.write(name, raw,serialized=False), 'dtype': dtype, 'shape': [int(x) for x in array.shape],
                'axes': list(axes), 'unit': unit, 'nonfinite_permitted': bool(allow_nonfinite), 'order': 'C'}


def load_array(session, root, descriptor):
    import numpy as np
    need(descriptor['dtype'] in ('<f8', '<i8', '|u1') and descriptor['order'] == 'C', 'safe explicit array format')
    shape = descriptor['shape']; need(type(shape) is list and all(type(n) is int and n >= 0 for n in shape), 'ordinary shape')
    size = math.prod(shape) * (1 if descriptor['dtype'] == '|u1' else 8)
    need(size == descriptor['bytes'], 'array extent equals shape')
    name = descriptor['name']; need(Path(name).name == name and name not in ('.', '..'), 'single artifact operand')
    raw = session.read(Path(root)/name, descriptor)
    session.live(2 * size, 'safe array restore')
    result = np.frombuffer(raw, dtype=descriptor['dtype']).reshape(shape).copy()
    if not descriptor['nonfinite_permitted']: need(bool(np.isfinite(result).all()), 'restored finite array')
    session.tick(); return result
