"""Bounded JSON/NPZ readers for the spinal current-condition operator evaluator."""
import ast
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import re
import struct
import zipfile

import numpy as np

SHA = re.compile(r'[0-9a-f]{64}\Z')
MAX_ARCHIVE_BYTES = 32 * 1024 * 1024
MAX_HEADER_BYTES = 4096


def digest(data):
    return hashlib.sha256(data).hexdigest()


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key] = value
    return result


def read_json(path, *, expected_sha=None, limit=1024 * 1024):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise ValueError('bounded regular JSON file required')
    with path.open('rb') as stream:
        payload = stream.read(limit + 1)
    if len(payload) > limit:
        raise ValueError('JSON byte limit exceeded')
    if expected_sha is not None and (not SHA.fullmatch(expected_sha) or digest(payload) != expected_sha):
        raise ValueError('JSON identity mismatch')
    def invalid(value):
        raise ValueError('nonfinite JSON number')
    def finite_float(value):
        number = float(value)
        return number if math.isfinite(number) else invalid(value)
    result = json.loads(payload, object_pairs_hook=_unique, parse_constant=invalid, parse_float=finite_float)
    if not isinstance(result, dict):
        raise ValueError('JSON object required')
    return result, digest(payload)


def read_pinned(root, pin, *, limit=MAX_ARCHIVE_BYTES):
    if not isinstance(pin, dict) or set(pin) != {'path', 'bytes', 'sha256'}:
        raise ValueError('exact path/bytes/sha256 artifact pin required')
    if not isinstance(pin['path'], str) or not isinstance(pin['sha256'], str) or not SHA.fullmatch(pin['sha256']):
        raise ValueError('invalid artifact identity')
    if type(pin['bytes']) is not int or not 0 < pin['bytes'] <= limit:
        raise ValueError('artifact byte budget exceeded')
    relative = PurePosixPath(pin['path'])
    if relative.is_absolute() or '..' in relative.parts or '\\' in pin['path'] or str(relative) != pin['path']:
        raise ValueError('canonical relative artifact path required')
    path = Path(root)
    if path.is_symlink() or not path.is_dir():
        raise ValueError('real artifact directory required')
    for part in relative.parts:
        path = path / part
        if path.is_symlink():
            raise ValueError('artifact symlink refused')
    if not path.is_file() or path.stat().st_size != pin['bytes']:
        raise ValueError('artifact size mismatch')
    with path.open('rb') as stream:
        payload = stream.read(pin['bytes'] + 1)
    if len(payload) != pin['bytes'] or digest(payload) != pin['sha256']:
        raise ValueError('artifact identity mismatch')
    return payload


def read_npz_bytes(payload, expected):
    """Decode the same pinned bytes, after exact uncompressed NPY admission.

    expected maps array name to (dtype-policy, bin-count). Policy is numeric,
    float64, int64 or bool. ZIP_STORED is an intentional submission format.
    """
    if not payload or len(payload) > MAX_ARCHIVE_BYTES or not 1 <= len(expected) <= 5:
        raise ValueError('bounded NPZ with one to five expected arrays required')
    # Bound directory allocation BEFORE ZipFile creates one object per entry.
    # Default np.savez uses this ordinary EOCD even when local headers use ZIP64.
    # Archive comments, multidisk and ZIP64 end directories are outside contract.
    if len(payload) < 22:
        raise ValueError('bounded ordinary ZIP directory required')
    if len(payload) >= 42 and payload[-42:-38] == b'PK\x06\x07':
        raise ValueError('ZIP64 end locator is outside bounded format')
    signature, disk, cd_disk, local_count, count, cd_bytes, cd_offset, comment = struct.unpack('<4s4H2LH', payload[-22:])
    if (signature != b'PK\x05\x06' or disk != 0 or cd_disk != 0 or comment != 0
            or local_count != count or count != len(expected) or not 1 <= count <= 5
            or not 1 <= cd_bytes <= 8192 or cd_offset + cd_bytes != len(payload) - 22):
        raise ValueError('ZIP directory count/extent exceeds bounded format')
    decoded = {}
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        entries = archive.infolist()
        names = {name + '.npy' for name in expected}
        if len(entries) != len(names) or {e.filename for e in entries} != names:
            raise ValueError('NPZ members must exactly match required methods/arrays')
        for entry in entries:
            if (entry.is_dir() or entry.flag_bits & 1 or entry.compress_type != zipfile.ZIP_STORED
                    or entry.file_size != entry.compress_size or entry.file_size > MAX_ARCHIVE_BYTES):
                raise ValueError('only bounded unencrypted ZIP_STORED arrays are supported')
            name = entry.filename[:-4]
            policy, n = expected[name]
            if type(n) is not int or not 0 < n <= 1_000_000:
                raise ValueError('bounded declared bin count required')
            with archive.open(entry) as stream:
                magic = stream.read(8)
                if magic[:6] != b'\x93NUMPY' or magic[6:] not in (b'\x01\x00', b'\x02\x00'):
                    raise ValueError('NPY version1 or2 required')
                width = 2 if magic[6] == 1 else 4
                raw_length = stream.read(width)
                if len(raw_length) != width:
                    raise ValueError('truncated NPY length')
                header_length = int.from_bytes(raw_length, 'little')
                if not 1 <= header_length <= MAX_HEADER_BYTES:
                    raise ValueError('NPY header budget exceeded')
                raw_header = stream.read(header_length)
                if len(raw_header) != header_length:
                    raise ValueError('truncated NPY header')
                try:
                    syntax = ast.parse(raw_header.decode('latin1'), mode='eval').body
                    if (not isinstance(syntax, ast.Dict) or len(syntax.keys) != 3
                            or any(not isinstance(k, ast.Constant) or not isinstance(k.value, str) for k in syntax.keys)
                            or len({k.value for k in syntax.keys}) != 3):
                        raise ValueError('duplicate or invalid NPY header key')
                    header = ast.literal_eval(syntax)
                except (SyntaxError, TypeError, RecursionError) as exc:
                    raise ValueError('invalid bounded NPY header') from exc
                if (not isinstance(header, dict) or set(header) != {'descr', 'fortran_order', 'shape'}
                        or not isinstance(header['descr'], str) or header['fortran_order'] is not False
                        or not isinstance(header['shape'], tuple) or len(header['shape']) != 1
                        or type(header['shape'][0]) is not int or header['shape'] != (n,)):
                    raise ValueError('one-dimensional C-order numeric NPY required')
                dtype = np.dtype(header['descr'])
                permitted = (dtype.kind in 'fiu' and dtype.itemsize in (1, 2, 4, 8)) if policy == 'numeric' else {
                    'float64': dtype.kind == 'f' and dtype.itemsize == 8,
                    'int64': dtype.kind == 'i' and dtype.itemsize == 8,
                    'bool': dtype.kind == 'b' and dtype.itemsize == 1,
                }.get(policy, False)
                if not permitted or dtype.hasobject or dtype.fields or dtype.subdtype:
                    raise ValueError('array dtype violates its source or prediction role')
                body_bytes = n * dtype.itemsize
                if entry.file_size != 8 + width + header_length + body_bytes:
                    raise ValueError('NPY exact byte extent mismatch')
                body = stream.read(body_bytes + 1)
                if len(body) != body_bytes:
                    raise ValueError('truncated or overlong NPY payload')
                # Array bytes are immutable and were hashed with this same archive.
                decoded[name] = np.frombuffer(body, dtype=dtype)
    return decoded
