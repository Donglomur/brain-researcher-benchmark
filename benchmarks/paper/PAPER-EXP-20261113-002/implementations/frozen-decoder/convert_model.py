"""Convert one pinned NPY coefficient triple to the frozen six-class format.

This helper transports coefficients only. It does not fit or score models.
The binary64 decoder and JSON conversion come from the reviewed transport.
"""
import argparse
import ast
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import stat
import struct

NPY_CAP = 65536
PREDICTOR_SHA256 = 'bd70faf03ec8caaf281abb3081c6a7d3fc403f7a937ce75ddcde62c57d9a2adb'

def require(value, reason):
    if not value:
        raise ValueError(reason)

def exact(path, pin, cap):
    path = Path(path)
    require(path.is_absolute() and not any(p.is_symlink() for p in (path, *path.parents)), 'ordinary absolute path')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
                before.st_size == pin['bytes'] <= cap, 'bounded exact regular file')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            body = stream.read(before.st_size + 1)
        after = os.fstat(fd)
        fields = ('st_dev', 'st_ino', 'st_size', 'st_mode', 'st_nlink', 'st_mtime_ns', 'st_ctime_ns')
        require(all(getattr(before, k) == getattr(after, k) for k in fields), 'stable opened file')
        require(len(body) == pin['bytes'] and hashlib.sha256(body).hexdigest() == pin['sha256'], 'complete byte identity')
        return body
    finally:
        os.close(fd)

def npy(body, role):
    require(type(body) is bytes and len(body) <= NPY_CAP and body[:6] == b'\x93NUMPY', 'bounded NPY only')
    require(body[6:8] in (b'\x01\x00', b'\x02\x00'), 'NPY format version 1 or 2')
    start = 10 if body[6] == 1 else 12
    require(len(body) >= start, 'complete NPY prefix')
    length = int.from_bytes(body[8:start], 'little')
    require(0 < length <= 4096 and start + length <= len(body), 'complete bounded NPY header')
    header = body[start:start+length]
    require(header.endswith(b'\n'), 'NPY header newline')
    node = ast.parse(header.decode('latin1').strip(), mode='eval').body
    require(isinstance(node, ast.Dict) and len(node.keys) == 3, 'three literal NPY header keys')
    keys = [ast.literal_eval(k) for k in node.keys]
    require(set(keys) == {'descr', 'fortran_order', 'shape'} and len(set(keys)) == 3, 'exact distinct header keys')
    info = ast.literal_eval(node)
    shape = info['shape']; order = info['fortran_order']; dtype = info['descr']
    require(type(shape) is tuple and all(type(v) is int and 0 <= v <= 984 for v in shape), 'bounded integer shape')
    require(type(order) is bool, 'explicit memory order')
    if role == 'mask':
        require(len(shape) == 1 and 1 <= shape[0] <= 984 and dtype == '|b1', 'bool source-axis mask')
        width = 1
    elif role == 'beta':
        require(len(shape) == 2 and shape[1] == 6 and dtype in ('<f8', '>f8'), 'binary64 beta rows and six columns')
        width = 8
    elif role == 'intercept':
        require(shape == (6,) and dtype in ('<f8', '>f8'), 'binary64 six-vector intercept')
        width = 8
    else:
        raise ValueError('unknown model array role')
    count = math.prod(shape); raw = body[start+length:]
    require(len(raw) == count * width, 'exact NPY extent without trailing data')
    if width == 1:
        require(all(v in (0, 1) for v in raw), 'canonical mask bytes')
        return shape, [bool(v) for v in raw]
    flat = list(struct.unpack(('<' if dtype[0] == '<' else '>') + str(count) + 'd', raw))
    require(all(math.isfinite(v) for v in flat), 'finite coefficient array')
    if role == 'beta':
        rows, cols = shape
        return shape, [[flat[j*rows+i] if order else flat[i*cols+j] for j in range(cols)] for i in range(rows)]
    return shape, flat

def convert(mask_body, beta_body, intercept_body, component):
    shape, mask = npy(mask_body, 'mask')
    beta_shape, beta = npy(beta_body, 'beta')
    _, intercept = npy(intercept_body, 'intercept')
    selected = [i for i, keep in enumerate(mask) if keep]
    require(beta_shape[0] == len(selected), 'mask/beta unit join')
    result = {'schema': component.SCHEMA, 'arithmetic': component.ARITHMETIC,
              'feature_count': shape[0], 'selected_indices': selected, 'beta': beta, 'intercept': intercept}
    component.validate_model(result)
    raw = (json.dumps(result, allow_nan=False, separators=(',', ':')) + '\n').encode()
    require(len(raw) <= component.MODEL_CAP, 'participant model cap')
    roundtrip = component.strict_json(raw)
    component.validate_model(roundtrip)
    # bit equality includes negative zero; JSON transport must preserve each coefficient.
    for left, right in zip([v for row in beta for v in row] + intercept,
                           [v for row in roundtrip['beta'] for v in row] + roundtrip['intercept']):
        require(struct.pack('>d', left) == struct.pack('>d', right), 'binary64 JSON round-trip')
    return raw

def write_new(path, body):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'wb', closefd=False) as stream:
            require(stream.write(body) == len(body), 'complete output write')
            stream.flush(); os.fsync(fd)
        os.fchmod(fd, 0o400)
    finally:
        os.close(fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for role in ('mask', 'beta', 'intercept'):
        parser.add_argument('--' + role, required=True)
        parser.add_argument('--' + role + '-sha256', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    component_path = Path(__file__).absolute().with_name('predict_one.py')
    source = exact(component_path, {'bytes': 4125, 'sha256': PREDICTOR_SHA256}, 65536)
    component = importlib.util.module_from_spec(
        importlib.util.spec_from_loader('frozen_predictor', loader=None))
    exec(compile(source, str(component_path), 'exec'), component.__dict__)
    bodies = []
    for role in ('mask', 'beta', 'intercept'):
        path = Path(getattr(args, role)).absolute()
        pin = {'bytes': path.lstat().st_size, 'sha256': getattr(args, role + '_sha256')}
        bodies.append(exact(path, pin, NPY_CAP))
    raw = convert(*bodies, component)
    output = Path(args.out).absolute()
    require('..' not in output.parts and
            not any(p.is_symlink() for p in (output, *output.parents)),
            'ordinary output path')
    require(output.parent.is_dir() and not output.exists(), 'new output in existing directory')
    write_new(output, raw)
    print(json.dumps({'schema': component.SCHEMA, 'bytes': len(raw),
                      'sha256': hashlib.sha256(raw).hexdigest(), 'fit_calls': 0}))


if __name__ == '__main__':
    main()
