"""Bounded immutable-buffer output decoding; no fitting, source or bank access."""
import ast
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import stat
import struct
import zipfile

import numpy as np

CAPS = {'vt_estimates.csv': 1048576, 'kinetic_evidence.npz': 16777216,
        'sensitivity_summary.json': 1048576, 'run_metadata.json': 8388608,
        'findings.md': 65536}
TOTAL_CAP = 33554432
NPY_ELEMENTS = 2000000


class ContractError(ValueError):
    pass


def require(ok, message):
    if not ok: raise ContractError(message)


def signature(value):
    return (value.st_dev, value.st_ino, value.st_mode, value.st_size,
            value.st_mtime_ns, value.st_ctime_ns)  # deliberately excludes atime


def read_file(path, cap):
    path = Path(path)
    require(not any(p.is_symlink() for p in (path, *path.parents)), 'symlink path')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= cap,
                'bounded regular single-link artifact required')
        with os.fdopen(fd, 'rb', closefd=False) as stream: raw = stream.read(cap+1)
        require(len(raw) == before.st_size and len(raw) <= cap, 'artifact size changed')
        require(signature(before) == signature(os.fstat(fd)) == signature(path.lstat()), 'artifact changed during read')
        return raw
    finally:
        os.close(fd)


def json_bytes(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON key'); result[key] = value
        return result
    def number(token):
        value = float(token); require(math.isfinite(value), 'nonfinite JSON'); return value
    def invalid(token): raise ContractError('nonfinite JSON')
    try:
        result = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                            parse_float=number, parse_constant=invalid)
    except (UnicodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise ContractError('invalid strict JSON') from exc
    pending = [(result, 0)]
    while pending:
        item, depth = pending.pop(); require(depth <= 64, 'JSON depth cap')
        if isinstance(item, dict): pending.extend((v, depth+1) for v in item.values())
        elif isinstance(item, list): pending.extend((v, depth+1) for v in item)
    require(type(result) is dict, 'JSON top-level object')
    return result


def csv_bytes(raw):
    require(b'\0' not in raw, 'CSV NUL')
    csv.field_size_limit(16384)
    try:
        reader = csv.reader(io.StringIO(raw.decode('utf-8'), newline=''), strict=True)
        header = next(reader, [])
        require(1 <= len(header) <= 64 and len(set(header)) == len(header) and
                all(k and k == k.strip() and all(ord(c) >= 32 and ord(c) != 127 for c in k) for k in header), 'CSV header')
        require(all(len(k.encode('utf-8')) <= 16384 for k in header), 'CSV header field cap')
        rows = []
        for row in reader:
            require(len(rows) < 28 and len(row) == len(header), 'CSV shape/row cap')
            require(all(len(v.encode('utf-8')) <= 16384 for v in row), 'CSV field cap')
            rows.append(dict(zip(header, row)))
    except (UnicodeError, csv.Error) as exc:
        raise ContractError('CSV encoding/parser') from exc
    require(len(rows) == 28, 'complete 28 CSV records required')
    return rows


def npy_bytes(raw):
    require(len(raw) >= 10 and raw[:6] == b'\x93NUMPY', 'NPY magic')
    version = tuple(raw[6:8]); require(version in ((1, 0), (2, 0), (3, 0)), 'NPY version')
    size_width = 2 if version == (1, 0) else 4
    require(len(raw) >= 8+size_width, 'NPY prefix')
    header_size = struct.unpack('<H' if size_width == 2 else '<I', raw[8:8+size_width])[0]
    require(0 < header_size <= 65536 and 8+size_width+header_size <= len(raw), 'NPY header cap')
    offset = 8+size_width+header_size
    try:
        header = ast.literal_eval(raw[8+size_width:offset].decode('utf-8' if version == (3, 0) else 'latin1'))
        require(type(header) is dict and set(header) == {'descr', 'fortran_order', 'shape'}, 'NPY header keys')
        dtype = np.dtype(header['descr']); shape = header['shape']
    except (ValueError, TypeError, SyntaxError, RecursionError, UnicodeError) as exc:
        raise ContractError('invalid NPY header') from exc
    require(type(header['fortran_order']) is bool and type(shape) is tuple and len(shape) <= 4, 'NPY dimensions')
    require(dtype.fields is None and dtype.subdtype is None and dtype.kind in 'biufSU', 'unsafe NPY dtype')
    count = 1
    for dimension in shape:
        require(type(dimension) is int and 0 <= dimension <= NPY_ELEMENTS, 'NPY shape domain')
        count *= dimension; require(count <= NPY_ELEMENTS, 'NPY logical element cap')
    require(count*dtype.itemsize <= 16777216 and offset+count*dtype.itemsize == len(raw), 'NPY body length')
    try: result = np.load(io.BytesIO(raw), allow_pickle=False, max_header_size=65536)
    except (ValueError, EOFError, OSError) as exc: raise ContractError('NPY decode') from exc
    if result.dtype.kind in 'iuf': require(np.all(np.isfinite(result)), 'nonfinite NPY')
    return result


def npz_bytes(raw):
    result = {}
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            members = archive.infolist()
            require(1 <= len(members) <= 64, 'NPZ member cap')
            require(sum(m.file_size for m in members) <= 16777216, 'NPZ total uncompressed cap')
            for member in members:
                name = member.filename
                require(name.endswith('.npy') and '/' not in name and '\\' not in name and
                        name[:-4] and all(c.isascii() and (c.isalnum() or c == '_') for c in name[:-4]), 'NPZ member name')
                require(name[:-4] not in result and not member.is_dir() and not (member.flag_bits & 1), 'NPZ duplicate/encrypted member')
                require(member.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED) and
                        0 < member.file_size <= 16777216, 'NPZ compression/member cap')
                with archive.open(member) as stream: body = stream.read(member.file_size+1)
                require(len(body) == member.file_size, 'NPZ member length')
                result[name[:-4]] = npy_bytes(body)
    except (zipfile.BadZipFile, NotImplementedError, RuntimeError, EOFError, OSError) as exc:
        raise ContractError('invalid NPZ archive') from exc
    return result


def inventory(output):
    """Stat bounded extras without opening their content or following links."""
    require(not (output/'failure_report.json').exists() and not (output/'failure_report.json').is_symlink(), 'authoritative failure marker')
    files, directories, total = {}, 0, 0
    for base, dirs, names in os.walk(output, followlinks=False):
        for name in dirs:
            path = Path(base)/name; relative = path.relative_to(output)
            require(not path.is_symlink() and stat.S_ISDIR(path.lstat().st_mode), 'extra directory type')
            directories += 1
            require(directories <= 64 and len(relative.parts) <= 32, 'extra directory cap')
        for name in names:
            path = Path(base)/name; value = path.lstat()
            require(stat.S_ISREG(value.st_mode), 'extra file must be regular; no links/devices')
            files[str(path.relative_to(output))] = signature(value)
            total += value.st_size
            require(len(files) <= 256 and total <= TOTAL_CAP, 'output inventory cap')
    require(set(CAPS) <= set(files), 'missing required output file')
    return files


def read_output(output):
    output = Path(output)
    require(not any(p.is_symlink() for p in (output, *output.parents)) and output.is_dir(), 'output directory')
    before = inventory(output)
    buffers = {name: read_file(output/name, cap) for name, cap in CAPS.items()}
    require(sum(map(len, buffers.values())) <= TOTAL_CAP, 'output total bytes')
    try: findings = buffers['findings.md'].decode('utf-8')
    except UnicodeError as exc: raise ContractError('findings UTF-8') from exc
    require(findings.strip(), 'empty findings')
    result = dict(rows=csv_bytes(buffers['vt_estimates.csv']), arrays=npz_bytes(buffers['kinetic_evidence.npz']),
                  summary=json_bytes(buffers['sensitivity_summary.json']), metadata=json_bytes(buffers['run_metadata.json']),
                  findings=findings)
    require(inventory(output) == before, 'late output inventory change')
    result['file_sha256'] = {name: hashlib.sha256(raw).hexdigest() for name, raw in buffers.items()}
    return result
