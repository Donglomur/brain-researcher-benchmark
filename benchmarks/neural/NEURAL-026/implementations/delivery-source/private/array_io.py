"""Task-local bounded capture and primitive NPZ decoding of the same bytes.

NPY extent checks follow the unchanged donor common.npz_load implementation.
No candidate path is opened by NumPy, and FIFOs/devices cannot block capture.
"""
import hashlib
import io
import json
import math
import os
from pathlib import Path
import stat
import zipfile
import numpy as np
from common import need


def capture(path, cap):
    path = Path(path)
    need(all(not x.is_symlink() for x in (path, *path.parents)), 'No linked file or ancestor')
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | getattr(os, 'O_NOFOLLOW', 0))
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and 0 < before.st_size <= cap, 'Bounded ordinary file only')
        parts, n = [], 0
        while True:
            block = os.read(fd, min(1024**2, cap + 1 - n))
            if not block: break
            parts.append(block); n += len(block)
            need(n <= cap, 'Bounded capture')
        after = os.fstat(fd)
        need((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
             == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
             and n == before.st_size, 'Stable complete file capture')
        return b''.join(parts)
    finally:
        os.close(fd)


def identity(raw):
    return dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def metadata(path, cap=1024**2):
    def pairs(items):
        out = {}
        for k, v in items:
            need(k not in out, 'No duplicate metadata keys')
            out[k] = v
        return out
    return json.loads(capture(path, cap), object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, 'Finite JSON numbers'))


def arrays(raw, keys, cap):
    need(0 < len(raw) <= cap, 'Bounded NPZ bytes')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        members = z.infolist()
        need(len(members) == len(keys) and {m.filename for m in members} == {k+'.npy' for k in keys},
             'Exact unique NPZ members')
        need(sum(m.file_size for m in members) <= cap, 'Expanded NPZ bound')
        for m in members:
            need(not m.is_dir() and not m.flag_bits & 1 and
                 m.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
                 and not stat.S_ISLNK(m.external_attr >> 16), 'Ordinary primitive NPY member')
            with z.open(m) as f:
                version = np.lib.format.read_magic(f)
                if version == (1, 0): shape, _, dtype = np.lib.format.read_array_header_1_0(f, max_header_size=4096)
                elif version == (2, 0): shape, _, dtype = np.lib.format.read_array_header_2_0(f, max_header_size=4096)
                else: raise ValueError('NPY version1/2 only')
                need(dtype.kind in 'iuf' and dtype.fields is None and len(shape) <= 3
                     and all(type(n) is int and 0 < n <= 10000000 for n in shape), 'Primitive bounded dimensions')
                size = math.prod(shape) * dtype.itemsize
                need(size <= cap and f.tell() + size == m.file_size, 'Exact header/payload extent')
    with np.load(io.BytesIO(raw), allow_pickle=False, max_header_size=4096) as z:
        return {k: z[k] for k in keys}


def fresh_output(path):
    path = Path(path)
    need(not path.exists() and not path.is_symlink()
         and all(not p.is_symlink() for p in path.parents), 'Fresh unlinked output before input/private work')
