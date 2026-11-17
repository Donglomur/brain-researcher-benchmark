"""Primitive, bounded transport; fitted participant objects never enter this codec."""
import base64
import json
import math
import re
import struct
import sys
from dataclasses import dataclass


def need(condition, message):
    if not condition:
        raise ValueError(message)


@dataclass(frozen=True)
class Array:
    dtype: str
    shape: tuple
    data: bytes


def array_check(value, cap):
    need(type(value) is Array and type(value.dtype) is str, 'primitive array')
    match = re.fullmatch(r'([<>=|])([biufc])(1|2|4|8|16)', value.dtype)
    need(match is not None, 'closed primitive dtype; no objects/records/strings')
    byteorder, kind, width = match.groups(); width = int(width)
    need(width in {'b': (1,), 'i': (1, 2, 4, 8), 'u': (1, 2, 4, 8),
                  'f': (2, 4, 8), 'c': (8, 16)}[kind], 'valid primitive width')
    need(byteorder != '|' or width == 1, 'explicit multi-byte order')
    need(type(value.shape) is tuple and len(value.shape) <= 16 and
         all(type(n) is int and 0 <= n <= cap for n in value.shape), 'bounded array axes')
    count = math.prod(value.shape)
    need(count * width <= cap and type(value.data) is bytes and
         len(value.data) == count * width, 'complete exact primitive array extent')
    return value


def encode(value, cap):
    need(type(cap) is int and 0 < cap <= 2**31, 'prospective frame byte ceiling')
    nodes = 0
    def visit(v, depth):
        nonlocal nodes
        nodes += 1
        need(depth <= 64 and nodes <= min(cap, 1000000), 'bounded primitive tree')
        t = type(v)
        if v is None or t in (bool, str, int):
            return ['atom', v]
        if t is float:
            # Exact bits preserve masked missing values and negative zero.
            return ['float64', struct.pack('>d', v).hex()]
        if t is bytes:
            need(len(v) <= cap, 'bounded bytes')
            return ['bytes', base64.b64encode(v).decode('ascii')]
        if t is Array:
            a = array_check(v, cap)
            return ['array', a.dtype, list(a.shape), base64.b64encode(a.data).decode('ascii')]
        np = sys.modules.get('numpy')
        if np is not None and t is np.ndarray:
            need(not v.dtype.hasobject and not v.dtype.fields and not v.dtype.subdtype,
                 'no object or structured ndarray')
            need(v.nbytes <= cap, 'array cap before contiguous copy')
            return visit(Array(v.dtype.str, tuple(v.shape), v.tobytes(order='C')), depth + 1)
        if t in (tuple, list):
            return ['tuple' if t is tuple else 'list', [visit(x, depth + 1) for x in v]]
        if t is dict:
            need(all(type(k) in (str, int, tuple) for k in v), 'literal dictionary keys')
            return ['dict', [[visit(k, depth + 1), visit(x, depth + 1)] for k, x in v.items()]]
        raise ValueError('Unsupported transported type; fitted state must stay in its child')
    raw = json.dumps(visit(value, 0), separators=(',', ':'), ensure_ascii=True,
                     allow_nan=False).encode('ascii')
    need(len(raw) <= cap, 'complete encoded frame exceeds selected cap')
    return raw


def decode(raw, cap, *, materialize=True):
    need(type(raw) is bytes and 0 < len(raw) <= cap, 'bounded complete wire body')
    def bad(_):
        raise ValueError('Nonfinite JSON token')
    tree = json.loads(raw, parse_constant=bad)
    nodes = 0
    def visit(v, depth):
        nonlocal nodes
        nodes += 1
        need(depth <= 64 and nodes <= min(cap, 1000000), 'bounded primitive tree')
        need(type(v) is list and len(v) >= 2 and type(v[0]) is str, 'tagged primitive node')
        tag = v[0]
        if tag == 'atom':
            need(len(v) == 2 and (v[1] is None or type(v[1]) in (bool, str, int)), 'literal atom')
            return v[1]
        if tag == 'float64':
            need(len(v) == 2 and type(v[1]) is str and re.fullmatch('[0-9a-f]{16}', v[1]), 'float bits')
            return struct.unpack('>d', bytes.fromhex(v[1]))[0]
        if tag in ('bytes', 'array'):
            need(len(v) == (2 if tag == 'bytes' else 4) and type(v[-1]) is str,
                 'exact primitive byte fields')
            need(len(v[-1]) <= 4 * ((cap + 2) // 3), 'base64 cap before allocation')
            data = base64.b64decode(v[-1], validate=True)
            if tag == 'bytes':
                need(len(data) <= cap, 'byte extent'); return data
            need(type(v[2]) is list, 'array shape list')
            a = array_check(Array(v[1], tuple(v[2]), data), cap)
            if not materialize:
                return a
            import numpy as np
            # No file or pickle loader; construction from checked literal bytes only.
            return np.frombuffer(a.data, dtype=np.dtype(a.dtype)).reshape(a.shape).copy()
        need(tag in ('tuple', 'list', 'dict') and len(v) == 2 and type(v[1]) is list,
             'closed primitive container')
        if tag != 'dict':
            items = [visit(x, depth + 1) for x in v[1]]
            return tuple(items) if tag == 'tuple' else items
        out = {}
        for pair in v[1]:
            need(type(pair) is list and len(pair) == 2, 'dictionary pair')
            key, value = (visit(x, depth + 1) for x in pair)
            need(type(key) in (str, int, tuple) and key not in out, 'unique literal key')
            out[key] = value
        return out
    return visit(tree, 0)


def frame(value, cap):
    raw = encode(value, cap)
    return struct.pack('>Q', len(raw)) + raw


def read_frame(stream, cap):
    def exact(n):
        chunks = bytearray()
        while len(chunks) < n:
            part = stream.read(n - len(chunks))
            need(part, 'premature protocol EOF')
            chunks.extend(part)
        return bytes(chunks)
    size = struct.unpack('>Q', exact(8))[0]
    need(0 < size <= cap, 'frame extent before allocation')
    return decode(exact(size), cap)
