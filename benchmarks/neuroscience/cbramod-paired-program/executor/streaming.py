"""Bounded-memory ordinary-file capture and NPY envelope checks (no samples)."""
import ast
import hashlib
import math
import os
from pathlib import Path
import stat
import struct
import time
import safe_io as safe

ATTRS = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')


def copy(source, destination, descriptor, end, cap):
    from engine import pin, plain_path
    source, destination = plain_path(str(source)), plain_path(str(destination))
    pin({k: descriptor[k] for k in ('bytes', 'sha256')}, cap)
    fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    out = None
    try:
        first = os.fstat(fd)
        safe.need(stat.S_ISREG(first.st_mode) and first.st_nlink == 1 and
                  first.st_size == descriptor['bytes'], 'Pinned single-link ordinary source')
        out = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        sha = hashlib.sha256(); count = 0
        with os.fdopen(fd, 'rb', closefd=False) as f, os.fdopen(out, 'wb', closefd=False) as g:
            while True:
                safe.need(time.monotonic() < end, 'Complete streaming deadline')
                block = f.read(min(65536, descriptor['bytes'] + 1 - count))
                if not block:
                    break
                count += len(block); safe.need(count <= descriptor['bytes'], 'Streaming extent')
                sha.update(block); g.write(block)
            g.flush(); os.fsync(out)
        last, linked = os.fstat(fd), source.lstat()
        safe.need(all(getattr(first, k) == getattr(last, k) == getattr(linked, k) for k in ATTRS),
                  'Stable streaming source identity')
        safe.need(count == descriptor['bytes'] and sha.hexdigest() == descriptor['sha256'],
                  'Complete streaming content pin')
        os.chmod(destination, 0o444)
        return {'bytes': count, 'sha256': sha.hexdigest()}
    finally:
        os.close(fd)
        if out is not None:
            os.close(out)


def npy_envelope(path, shape, dtype):
    """Validate the entire declared file extent without loading its data."""
    from engine import plain_path
    path = plain_path(str(path))
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        a = os.fstat(fd)
        safe.need(stat.S_ISREG(a.st_mode) and a.st_nlink == 1, 'Ordinary NPY')
        with os.fdopen(fd, 'rb', closefd=False) as f:
            prefix = f.read(8)
            safe.need(prefix[:6] == b'\x93NUMPY' and prefix[6:] in (b'\x01\x00', b'\x02\x00'), 'NPY1/2 envelope')
            n = 2 if prefix[6] == 1 else 4
            raw = f.read(n); safe.need(len(raw) == n, 'Complete NPY length')
            size = int.from_bytes(raw, 'little'); safe.need(0 < size <= 65536, 'Bounded NPY header')
            header = f.read(size); safe.need(len(header) == size, 'Complete NPY header')
            value = ast.literal_eval(header.decode('latin1'))
            safe.need(type(value) is dict and set(value) == {'descr', 'fortran_order', 'shape'}
                      and value['descr'] == dtype and value['fortran_order'] is False and
                      type(value['shape']) is tuple and all(type(x) is int for x in value['shape'])
                      and list(value['shape']) == shape, 'Exact C-order NPY type and complete shape')
            safe.need(dtype in ('<f4', '<f8', '<i4', '<i8') and all(type(x) is int and x > 0 for x in shape),
                      'Numeric nonempty axes')
            safe.need(a.st_size == 8 + n + size + math.prod(shape) * int(dtype[-1]), 'No trailing or truncated NPY payload')
        z, linked = os.fstat(fd), path.lstat()
        safe.need(all(getattr(a,k) == getattr(z,k) == getattr(linked,k) for k in ATTRS), 'Stable NPY envelope')
    finally:
        os.close(fd)
