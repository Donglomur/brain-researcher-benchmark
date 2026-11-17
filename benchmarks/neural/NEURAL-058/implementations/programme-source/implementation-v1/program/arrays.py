"""Primitive NPY/JSON artifacts, bounded before decoding; no numerical import at load."""
import ast
import io
import math
import struct
from pathlib import Path
from core import need, integer, capture, publish, encoded, parse, relative, descriptor


def header(raw, expanded_limit):
    need(type(raw) is bytes and raw[:6] == b'\x93NUMPY', 'primitive NPY magic')
    need(raw[6:8] in (b'\x01\x00', b'\x02\x00'), 'NPY versions1/2 only')
    width = 2 if raw[6] == 1 else 4
    need(len(raw) >= 8 + width, 'complete NPY prefix')
    length = int.from_bytes(raw[8:8+width], 'little')
    need(0 < length <= 16384 and len(raw) >= 8+width+length, 'bounded complete primitive header')
    try:
        h = ast.literal_eval(raw[8+width:8+width+length].decode('latin1'))
    except (ValueError, SyntaxError, UnicodeError, RecursionError) as error:
        raise ValueError('invalid NPY header') from error
    need(type(h) is dict and set(h) == {'descr','fortran_order','shape'}, 'exact primitive header fields')
    d = h['descr']; shape = h['shape']
    need(d in ('<f8','<f4','<i8','<i4','<u8','<u4','|u1','|i1','|b1'), 'non-object little-endian numeric dtype')
    need(h['fortran_order'] is False and type(shape) is tuple and len(shape) <= 8, 'C order bounded rank')
    need(all(type(n) is int and n >= 0 for n in shape), 'ordinary array extents')
    size = math.prod(shape) * int(d[2:])
    need(size <= integer(expanded_limit) and 8+width+length+size == len(raw), 'exact expanded extent/no trailing payload')
    return {'dtype': d, 'shape': list(shape), 'expanded_bytes': size}


def read_array(root, item, budget, raw_limit, expanded_limit):
    need(type(item) is dict and set(item) == {'path','pin','array'}, 'array descriptor')
    raw, custody = capture(Path(root)/relative(item['path']), item['pin'], raw_limit, budget, readonly=True)
    info = header(raw, expanded_limit)
    need(info == item['array'], 'admitted primitive shape/dtype')
    budget.tick()
    import numpy as np
    value = np.load(io.BytesIO(raw), allow_pickle=False)
    need(value.dtype.kind in 'fiub' and not value.dtype.hasobject and value.nbytes == info['expanded_bytes'], 'primitive decoder parity')
    budget.tick()
    return value, custody


def write_array(root, name, value, budget, expanded_limit):
    import numpy as np
    need(type(value) is np.ndarray and not value.dtype.hasobject and value.dtype.kind in 'fiub', 'ordinary numeric ndarray')
    need(value.nbytes <= integer(expanded_limit), 'expanded array reservation')
    if value.dtype.kind == 'f': need(bool(np.isfinite(value).all()), 'finite numeric artifact')
    target = value.dtype.newbyteorder('<')
    value = np.ascontiguousarray(value, dtype=target)
    # Bound the actual encoder buffer before constructing it. Encoding work and
    # file publication are separate debits, both charged to the selected ledger.
    budget.reserve_write(value.nbytes + 16384)
    stream = io.BytesIO(); np.save(stream, value, allow_pickle=False)
    raw = stream.getvalue(); info = header(raw, expanded_limit)
    out = publish(Path(root)/relative(name), raw, budget, readonly=True)
    budget.tick()
    return {'path': name, 'pin': out, 'array': info}


def read_json(root, item, budget, limit):
    need(type(item) is dict and set(item) == {'path','pin'}, 'JSON descriptor')
    raw, _ = capture(Path(root)/relative(item['path']), item['pin'], limit, budget, readonly=True)
    return parse(raw)


def write_json(root, name, value, budget, cap):
    # The enclosing runtime selects a bounded metadata object; publication and
    # encoding are both reserved. Physical allocation/RSS still needs enforcement.
    budget.reserve_write(integer(cap))
    body = encoded(value); need(len(body) <= cap, 'metadata encoding cap')
    return {'path': name, 'pin': publish(Path(root)/relative(name), body, budget, readonly=True)}
