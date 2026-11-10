"""Strict bounded metadata and primitive-array I/O for future authorized use."""
import failures
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
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))

def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}

def cleanup_note(primary, action, error):
    failures.cleanup(primary, action, error)

def capture(path, cap, expected=None, *, reserve=None, observation=None):
    """Admit one readonly extent, reserve it, then read only that extent.

    No EOF/growth probe is performed. A short read stops the capture without
    retrying or refunding its original reservation. The owner retains known
    returned prefixes separately from a failed syscall's unknown prefix.
    """
    path = Path(path)
    state = observation if observation is not None else {}
    need(type(state) is dict and not state, 'Fresh source-owned capture observation')
    state.update(schema='neural066_read_extent_observation_v1', status='not_started', admitted_extent=None, reserved_upper=0, requested_upper=0, acknowledged_bytes=0, unknown_pending_upper=0, named_stable=False, descriptor_closed=False)
    fd = None
    primary = None
    parts = []
    try:
        need(type(cap) is int and cap > 0, 'Prospective explicit byte cap')
        if expected is not None:
            need(type(expected) is dict and set(expected) == {'bytes', 'sha256'} and type(expected['bytes']) is int and 0 <= expected['bytes'] <= cap and type(expected['sha256']) is str and len(expected['sha256']) == 64 and all(c in '0123456789abcdef' for c in expected['sha256']), 'Exact bounded expected extent and digest before body effects')
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and 0 <= before.st_size <= cap, 'Bounded regular file')
        if expected is not None:
            need(before.st_size == expected['bytes'], 'Exact admitted extent before body effects')
        extent = before.st_size
        state['admitted_extent'] = extent
        if reserve is not None:
            reserve(extent)
        state.update(reserved_upper=extent, status='reserved')
        remaining = extent
        while remaining:
            wanted = min(65536, remaining)
            # All possible bytes of this request are in the original extent
            # reservation; each prefix is requested at most once.
            need(state['requested_upper'] + wanted <= extent, 'No read beyond the original admitted reservation')
            state['requested_upper'] += wanted
            state['unknown_pending_upper'] = wanted
            block = os.read(fd, wanted)
            need(type(block) is bytes and len(block) <= wanted, 'Ordinary bounded byte return')
            state['unknown_pending_upper'] = 0
            state['acknowledged_bytes'] += len(block)
            parts.append(block)
            need(len(block) == wanted, 'Short capture retained without retry or reservation refund')
            remaining -= wanted
        raw = b''.join(parts)
        after = os.fstat(fd)
        fields = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
        signature = lambda s: tuple(getattr(s, k) for k in fields)
        need(stat.S_ISREG(after.st_mode) and signature(before) == signature(after) == signature(path.lstat()) and len(raw) == extent, 'Stable complete named captured file')
        state['named_stable'] = True
        if expected is not None:
            need(pin(raw) == expected, 'Exact operator-bound bytes/SHA')
    except BaseException as error:
        failures.hold(error, 'caught')
        primary = error
        state['status'] = 'failed'
        state['acknowledged_prefix_pin'] = pin(b''.join(parts))
        failures.remember(error, 'capture_observation', state)
        failures.remember(error, 'capture_known_prefix', b''.join(parts))
        raise
    finally:
        if fd is not None:
            closing, fd = fd, None
            try:
                os.close(closing)
                state['descriptor_closed'] = True
            except BaseException as error:
                failures.hold(error, 'caught')
                state['status'] = 'failed_close'
                state['acknowledged_prefix_pin'] = pin(b''.join(parts))
                if primary is None:
                    failures.remember(error, 'capture_observation', state)
                    failures.remember(error, 'capture_known_prefix', b''.join(parts))
                    raise
                cleanup_note(primary, 'capture.close', error)
    state.update(status='complete', acknowledged_prefix_pin=pin(raw))
    return raw

def child(root, relative):
    need(type(relative) is str and relative and (not Path(relative).is_absolute()), 'Relative path')
    parts = Path(relative).parts
    need(all((x not in ('', '.', '..') for x in parts)), 'No traversal')
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
        failures.hold(error, 'caught')
        primary = error
        raise
    finally:
        try:
            os.close(directory)
        except BaseException as error:
            failures.hold(error, 'caught')
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
    need(not path.exists() and (not path.is_symlink()), 'Fresh metadata output')
    temporary = path.parent / ('.' + path.name + '.' + uuid.uuid4().hex + '.partial')
    fd = None
    owned = None
    published = False

    def remove_owned(target):
        try:
            state = os.stat(target, follow_symlinks=False)
        except FileNotFoundError:
            return
        need(owned == (state.st_dev, state.st_ino) and stat.S_ISREG(state.st_mode), 'Cleanup refused a replaced/unowned output inode')
        os.unlink(target)
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 384)
        state = os.fstat(fd)
        need(stat.S_ISREG(state.st_mode), 'Owned regular output')
        owned = (state.st_dev, state.st_ino)
        view = memoryview(raw)
        offset = 0
        while offset < len(view):
            written = os.write(fd, view[offset:])
            need(type(written) is int and 0 < written <= len(view) - offset, 'Complete checked write progress')
            offset += written
        os.fsync(fd)
        closing, fd = (fd, None)
        os.close(closing)
        os.link(temporary, path, follow_symlinks=False)
        published = True
        remove_owned(temporary)
        sync_parent(path)
        return pin(raw)
    except BaseException as primary:
        failures.hold(primary, 'caught')
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
                failures.hold(error, 'caught')
                cleanup_note(primary, label, error)
        raise

def new_json(path, value):
    return durable_new(path, encoded(value))

def npy_header(raw):
    need(len(raw) >= 10 and raw[:8] == b'\x93NUMPY\x01\x00', 'Primitive NPY1 only')
    n = struct.unpack('<H', raw[8:10])[0]
    need(n <= 65535 and 10 + n <= len(raw), 'Bounded NPY header')
    h = ast.literal_eval(raw[10:10 + n].decode('latin1'))
    need(type(h) is dict and set(h) == {'descr', 'fortran_order', 'shape'}, 'Exact NPY metadata')
    need(type(h['fortran_order']) is bool and h['descr'] in ('<f4', '<f8', '<i8', '|i1', '|u1'), 'Primitive little-endian array; explicit C/F order, no pickle/object')
    shape = h['shape']
    need(type(shape) is tuple and all((type(x) is int and x >= 0 for x in shape)), 'Integer shape')
    count = 1
    for x in shape:
        count *= x
    width = {'<f4': 4, '<f8': 8, '<i8': 8, '|i1': 1, '|u1': 1}[h['descr']]
    need(10 + n + count * width == len(raw), 'Exact full NPY extent, no trailing data')
    return {**h, 'offset': 10 + n}

def array(root, desc, cap, *, reserve=None, observation=None):
    need(set(desc) == {'path', 'bytes', 'sha256', 'shape', 'dtype'}, 'Exact array descriptor')
    raw = capture(child(root, desc['path']), cap, {k: desc[k] for k in ('bytes', 'sha256')}, reserve=reserve, observation=observation)
    h = npy_header(raw)
    need(list(h['shape']) == desc['shape'] and h['descr'] == desc['dtype'] and (h['fortran_order'] is False), 'Bound C-order array axes')
    import numpy as np
    return np.frombuffer(raw, dtype=h['descr'], offset=h['offset']).reshape(h['shape'], order='F' if h['fortran_order'] else 'C')

def write_array(path, value, cap):
    """Future numeric handoff; no scientific native imports at module import."""
    import io
    import numpy as np
    x = np.asarray(value)
    need(x.dtype.str in ('<f4', '<f8', '<i8', '|i1', '|u1') and x.flags.c_contiguous, 'Primitive C numeric handoff')
    need(type(cap) is int and cap > 0 and (x.nbytes <= cap), 'Reserve bounded primitive payload before serialization')
    stream = io.BytesIO()
    np.lib.format.write_array(stream, x, version=(1, 0), allow_pickle=False)
    raw = stream.getvalue()
    need(type(cap) is int and cap > 0 and (len(raw) <= cap), 'Explicit output byte allocation')
    path = Path(path)
    durable_new(path, raw)
    return {'path': path.name, **pin(raw), 'shape': list(x.shape), 'dtype': x.dtype.str}
