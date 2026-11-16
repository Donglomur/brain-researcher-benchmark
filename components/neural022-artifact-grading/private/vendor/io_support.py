"""Bounded trusted-worker IO. Never imported by the host or candidate program."""
import ast
import hashlib
import io
import json
import math
import os
from pathlib import Path
import stat
import zipfile


def need(ok, why):
    if not ok:
        raise ValueError(why)


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def capture(path, expected, maximum):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and 0 < before.st_size <= maximum and before.st_size == expected['bytes'],
             'Exact bounded ordinary committed file')
        chunks = []; size = 0
        while True:
            block = os.read(fd, min(1048576, maximum + 1 - size))
            if not block:
                break
            chunks.append(block); size += len(block)
            need(size <= maximum, 'Bounded captured extent')
        raw = b''.join(chunks)
        after = os.fstat(fd)
        need((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
             == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
             and pin(raw) == {k: expected[k] for k in ('bytes', 'sha256')}, 'Stable exact captured bytes')
        return raw
    finally:
        os.close(fd)


def npz(raw, schema):
    """Pin checks happen before this bounded ZIP/NPY decode; no pickle/object arrays."""
    import numpy as np
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        rows = archive.infolist()
        need(len(rows) == len(schema) and len({v.filename for v in rows}) == len(rows)
             and {v.filename for v in rows} == {k + '.npy' for k in schema}, 'Exact archive members')
        need(sum(v.file_size for v in rows) <= 1100000, 'Total uncompressed archive cap')
        for entry in rows:
            need(entry.compress_type == zipfile.ZIP_STORED and not entry.flag_bits & 1
                 and not entry.is_dir() and stat.S_IFMT(entry.external_attr >> 16) in (0, stat.S_IFREG),
                 'Original stored ordinary arrays only')
            with archive.open(entry) as stream:
                prefix = stream.read(8)
                need(prefix[:6] == b'\x93NUMPY' and prefix[6:] in (b'\x01\x00', b'\x02\x00'),
                     'Supported exact NPY format')
                width = 2 if prefix[6:] == b'\x01\x00' else 4
                length_bytes = stream.read(width)
                need(len(length_bytes) == width, 'Complete NPY header size')
                n = int.from_bytes(length_bytes, 'little')
                need(0 < n <= 4096, 'Bounded NPY header')
                header_raw = stream.read(n)
                need(len(header_raw) == n, 'Complete NPY header')
                header = ast.literal_eval(header_raw.decode('latin1').strip())
            dtype, shape = schema[entry.filename[:-4]]
            need(type(header) is dict and set(header) == {'descr', 'shape', 'fortran_order'}
                 and header['descr'] == dtype and header['shape'] == shape
                 and header['fortran_order'] is False, 'Exact fixed dtype/shape/C-order')
            need(entry.file_size == 8 + width + n + math.prod(shape) * np.dtype(dtype).itemsize,
                 'Exact preallocation array extent')
        archive.testzip() is None or need(False, 'Complete archive CRC')
    with np.load(io.BytesIO(raw), allow_pickle=False, max_header_size=4096) as archive:
        return {k: archive[k] for k in schema}


def encoded_npz(value):
    import numpy as np
    stream = io.BytesIO(); np.savez(stream, **value)
    return stream.getvalue()


def output(root, name, raw, maximum):
    need(type(raw) is bytes and 0 < len(raw) <= maximum, 'Bounded output')
    root = Path(root)
    need(root.is_dir() and not root.is_symlink() and '/' not in name, 'Exact private output directory')
    path = root / name
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'wb', closefd=False) as stream:
            stream.write(raw); stream.flush(); os.fsync(fd)
    finally:
        os.close(fd)
    return pin(raw)


def encoded_json(value):
    return (json.dumps(value, allow_nan=False, separators=(',', ':')) + '\n').encode()


def schema(kind, methods):
    ids = ('<U24', (92,)); velocity = ('<f8', (92, 2))
    if kind == 'active':
        return {'ids': ('<U24', (141,)), 'counts': ('<i8', (141, 390)),
                'velocity': ('<f8', (141, 2)), 'source_rows': ('<i8', (141,)),
                'directions': ('<i8', (141,))}
    if kind == 'query':
        return {'ids': ids, 'counts': ('<i8', (92, 390)), 'directions': ('<i8', (92,)),
                'modes': ('<U7', (92,))}
    if kind == 'target':
        return {'ids': ids, 'velocity': velocity}
    if kind == 'references':
        return {'ids': ids, **{m: velocity for m in methods}}
    need(kind == 'private', 'Declared archive role')
    return {'ids': ids, 'velocity': velocity, **{m: velocity for m in methods}}


def source_contract(path, sha, strict, entrypoint):
    p = Path(path)
    need(p.name == 'CONTRACT.json', 'Exact source contract basename')
    # The runtime captures and pins this small metadata file; its exact SHA is CLI-bound.
    size = p.lstat().st_size
    raw = capture(p, {'bytes': size, 'sha256': sha}, 65536)
    obj = strict(raw)
    need(obj['schema'] == 'neural022_finite_program_source_contract_v1'
         and obj['execution_authority'] is False and obj['candidate_id'] == 'NEURAL-022',
         'Non-authorizing exact scientific source contract')
    need(entrypoint in ('project.py', 'grade.py'), 'Exact scientific entrypoint')
    names = {entrypoint, 'candidate.py', 'held_scorer.py', 'io_support.py', 'packet.py', 'controls.py'}
    if entrypoint == 'project.py':
        names.add('TASK.md')
    need(set(obj['entrypoint_sources'][entrypoint]) == names, 'Exact role-specific source mounts')
    for name in sorted(names):
        expected = obj['local_sources'][name]
        need('/' not in name and name != 'CONTRACT.json', 'Literal source basename')
        capture(p.parent / name, expected, 65536)
    return obj, pin(raw)
