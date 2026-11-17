"""Strict bounded metadata and primitive-array I/O for future authorized use."""
import ast
import hashlib
import json
import os
import stat
import struct
import uuid
from pathlib import Path
from core import encoded, need


def strict(raw):
    def pairs(items):
        d = {}
        for k, v in items:
            need(k not in d, 'Duplicate JSON key')
            d[k] = v
        return d
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def cleanup_note(primary, action, error):
    detail = {'action': action, 'type': type(error).__name__, 'message': str(error)[:2000]}
    primary.cleanup_errors = [*getattr(primary, 'cleanup_errors', []), detail]
    if hasattr(primary, 'add_note'):
        primary.add_note('Cleanup uncertainty: ' + str(detail))


def capture(path, cap, expected=None):
    path = Path(path)
    need(type(cap) is int and cap > 0, 'Prospective explicit byte cap')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    primary = None
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_size <= cap, 'Bounded regular file')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(cap + 1)
        after = os.fstat(fd)
        need(stat.S_ISREG(after.st_mode) and
             (before.st_dev, before.st_ino, before.st_mode, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
             (after.st_dev, after.st_ino, after.st_mode, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
             and len(raw) == before.st_size,
             'Stable complete captured file')
    except BaseException as error:
        primary = error
        raise
    finally:
        try:
            os.close(fd)
        except BaseException as error:
            if primary is None:
                raise
            cleanup_note(primary, 'capture.close', error)
    if expected is not None:
        need(pin(raw) == expected, 'Exact operator-bound bytes/SHA')
    return raw


def child(root, relative):
    need(type(relative) is str and relative and not Path(relative).is_absolute(), 'Relative path')
    parts = Path(relative).parts
    need(all(x not in ('', '.', '..') for x in parts), 'No traversal')
    root = Path(root).resolve()
    current = root
    for part in parts:
        current = current / part
        need(not current.is_symlink(), 'No symlink in captured path')
    need(current.resolve().is_relative_to(root), 'Inside exact root')
    return current


def sync_parent(path):
    """Durably order owned publication/removal; retain primary fsync failure."""
    directory = os.open(Path(path).parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    primary = None
    try:
        os.fsync(directory)
    except BaseException as error:
        primary = error
        raise
    finally:
        try:
            os.close(directory)
        except BaseException as error:
            if primary is None:
                raise
            cleanup_note(primary, 'directory.close', error)


def durable_new(path, raw):
    """Exclusive full-body publication after checked writes/fsync/close.

    Only our own inode is removed on failure. No success receipt is returned
    after short/zero writes, failed close, publication or directory fsync.
    Arrays use this same primitive before completion metadata is published.
    """
    path = Path(path)
    need(type(raw) is bytes, 'Immutable complete output body')
    need(not path.exists() and not path.is_symlink(), 'Fresh metadata output')
    temporary = path.parent / ('.' + path.name + '.' + uuid.uuid4().hex + '.partial')
    fd = None
    owned = None
    published = False
    def remove_owned(target):
        try:
            state = os.stat(target, follow_symlinks=False)
        except FileNotFoundError:
            return
        need(owned == (state.st_dev, state.st_ino) and stat.S_ISREG(state.st_mode),
             'Cleanup refused a replaced/unowned output inode')
        os.unlink(target)
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        state = os.fstat(fd)
        need(stat.S_ISREG(state.st_mode), 'Owned regular output')
        owned = (state.st_dev, state.st_ino)
        view = memoryview(raw)
        offset = 0
        while offset < len(view):
            written = os.write(fd, view[offset:])
            need(type(written) is int and 0 < written <= len(view)-offset, 'Complete checked write progress')
            offset += written
        os.fsync(fd)
        closing, fd = fd, None
        os.close(closing)
        os.link(temporary, path, follow_symlinks=False)
        published = True
        remove_owned(temporary)
        sync_parent(path)
        return pin(raw)
    except BaseException as primary:
        actions = []
        if fd is not None:
            actions.append(('output.close', lambda: os.close(fd)))
        if owned is not None and published:
            actions.append(('published.remove_owned', lambda: remove_owned(path)))
        if owned is not None:
            actions.append(('temporary.remove_owned', lambda: remove_owned(temporary)))
        for label, action in actions:
            try:
                action()
            except BaseException as error:
                cleanup_note(primary, label, error)
        raise


def new_json(path, value):
    return durable_new(path, encoded(value))


def npy_header(raw):
    need(len(raw) >= 10 and raw[:8] == b'\x93NUMPY\x01\x00', 'Primitive NPY1 only')
    n = struct.unpack('<H', raw[8:10])[0]
    need(n <= 65535 and 10 + n <= len(raw), 'Bounded NPY header')
    h = ast.literal_eval(raw[10:10+n].decode('latin1'))
    need(type(h) is dict and set(h) == {'descr', 'fortran_order', 'shape'}, 'Exact NPY metadata')
    need(h['fortran_order'] is False and h['descr'] in ('<f4', '<f8', '<i8', '|i1'),
         'Primitive little-endian C array; no pickle/object')
    shape = h['shape']
    need(type(shape) is tuple and all(type(x) is int and x >= 0 for x in shape), 'Integer shape')
    count = 1
    for x in shape:
        count *= x
    width = {'<f4': 4, '<f8': 8, '<i8': 8, '|i1': 1}[h['descr']]
    need(10+n+count*width == len(raw), 'Exact full NPY extent, no trailing data')
    return {**h, 'offset': 10+n}


def array(root, desc, cap):
    need(set(desc) == {'path', 'bytes', 'sha256', 'shape', 'dtype'}, 'Exact array descriptor')
    raw = capture(child(root, desc['path']), cap, {k: desc[k] for k in ('bytes', 'sha256')})
    h = npy_header(raw)
    need(list(h['shape']) == desc['shape'] and h['descr'] == desc['dtype'], 'Bound array axes')
    import numpy as np
    return np.frombuffer(raw, dtype=h['descr'], offset=h['offset']).reshape(h['shape'])


def write_array(path, value, cap):
    """Future numeric handoff; no scientific native imports at module import."""
    import io
    import numpy as np
    x = np.asarray(value)
    need(x.dtype.str in ('<f4', '<f8', '<i8', '|i1') and x.flags.c_contiguous,
         'Primitive C numeric handoff')
    need(type(cap) is int and cap > 0 and x.nbytes <= cap,
         'Reserve bounded primitive payload before serialization')
    stream = io.BytesIO()
    np.lib.format.write_array(stream, x, version=(1, 0), allow_pickle=False)
    raw = stream.getvalue()
    need(type(cap) is int and cap > 0 and len(raw) <= cap, 'Explicit output byte allocation')
    path = Path(path)
    durable_new(path, raw)
    return {'path': path.name, **pin(raw), 'shape': list(x.shape), 'dtype': x.dtype.str}
