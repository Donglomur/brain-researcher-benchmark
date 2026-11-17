"""Exact-byte view projection; no numerical model, target or source recording access."""
import ast
import hashlib
import io
import json
import re
import stat
import struct
import zipfile


MAX_NPZ = 800_000


COMMON = {'case_id', 'condition', 'context', 'nominal_ts_ms', 'clock_seconds'}


TRAIN = COMMON | {'tp_ms', 'fold'}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(body):
    return hashlib.sha256(body).hexdigest()


def header(body, key, n):
    stream = io.BytesIO(body)
    need(stream.read(6) == b'\x93NUMPY', 'NPY magic')
    version = stream.read(2)
    need(version in (b'\x01\x00', b'\x02\x00'), 'NPY1/2 only')
    width = 2 if version == b'\x01\x00' else 4
    value = stream.read(width)
    need(len(value) == width, 'Complete NPY length')
    length = struct.unpack('<H' if width == 2 else '<I', value)[0]
    need(1 <= length <= 4096, 'Bounded header')
    raw = stream.read(length)
    need(len(raw) == length and raw.endswith(b'\n'), 'Complete header')
    expression = ast.parse(raw.decode('latin1').strip(), mode='eval')
    need(isinstance(expression.body, ast.Dict), 'Literal header')
    keys = [ast.literal_eval(k) for k in expression.body.keys]
    need(len(keys) == 3 and set(keys) == {'descr', 'fortran_order', 'shape'}, 'Unique header keys')
    obj = ast.literal_eval(expression)
    shape = (n, 4, 40) if key == 'counts' else (n,)
    need(type(obj['shape']) is tuple and obj['shape'] == shape and
         all(type(x) is int for x in obj['shape']) and obj['fortran_order'] is False,
         'Exact C-order geometry')
    descriptor = obj['descr']
    need(type(descriptor) is str, 'Simple dtype')
    if key == 'case_id':
        need(descriptor in ('<U11', '>U11'), 'U11 identities')
        width = 44
    elif key == 'counts':
        need(descriptor in ('<u4', '>u4'), 'Unchanged uint32 counts')
        width = 4
    elif key in ('condition', 'context', 'fold'):
        need(re.fullmatch(r'[<>|][iu][1248]', descriptor) is not None, 'Integer metadata')
        width = int(descriptor[-1])
    else:
        need(descriptor in ('<f4', '>f4', '<f8', '>f8'), 'Floating point observations')
        width = int(descriptor[-1])
    size = width
    for x in shape:
        size *= x
    need(stream.tell() + size == len(body), 'Exact header and payload length')
    return {'shape': list(shape), 'dtype': descriptor, 'npy_bytes': len(body), 'sha256': sha(body)}


def members(body, expected, n):
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        rows = archive.infolist()
        need(len(rows) == len(expected) and {x.filename for x in rows} == {x + '.npy' for x in expected},
             'Exact unique NPZ members')
        need(sum(x.file_size for x in rows) <= MAX_NPZ, 'Expanded bound')
        result, inventory = {}, {}
        for row in rows:
            need(not row.is_dir() and row.compress_type == zipfile.ZIP_STORED and
                 not row.flag_bits & 1 and stat.S_IFMT(row.external_attr >> 16) in (0, stat.S_IFREG),
                 'Stored ordinary unencrypted NPY')
            payload = archive.read(row)  # CRC verified; bytes never interpreted as values.
            key = row.filename[:-4]
            inventory[key] = header(payload, key, n)
            result[key] = payload
        return result, inventory


def cue_archive(values):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_STORED, allowZip64=False) as archive:
        for key in sorted(values):
            if key == 'counts':
                continue
            info = zipfile.ZipInfo(key + '.npy', date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o444) << 16
            archive.writestr(info, values[key])
    return stream.getvalue()
