"""Primitive bounded NPY and JSON state transport; no pickle, eager numerical import or fit."""
import ast
import math
import struct
from pathlib import Path
from core import need, integer, finite, descriptor, canonical, capture, publish, encoded, parse, pin

DTYPES = {'<f8': 8, '<f4': 4, '<i8': 8, '<i4': 4, '|b1': 1, '|u1': 1}


class Limits:
    def __init__(self, budget, selected):
        self.budget = budget; self.limits = dict(selected); self.used = {k: 0 for k in selected}
        for key in ('allocation_bytes', 'elements', 'serialized_bytes', 'files', 'work'):
            integer(self.limits[key], 1)
    def reserve(self, key, count):
        integer(count); need(self.used[key] + count <= self.limits[key], 'prospective numeric '+key)
        self.used[key] += count; self.budget.tick()
    def record(self): return {'limits': self.limits, 'reserved': self.used, 'arbitrary_method_internal_allocations_not_measured': True}


def shape_extent(shape, dtype):
    need(type(shape) in (list, tuple) and len(shape) <= 8 and dtype in DTYPES, 'primitive bounded array schema')
    elements = 1
    for n in shape: elements *= integer(n)
    return elements, elements * DTYPES[dtype]


def header(raw, expected_shape, expected_dtype):
    need(raw[:6] == b'\x93NUMPY' and raw[6:8] in (b'\x01\x00', b'\x02\x00'), 'primitive NPY version')
    width = 2 if raw[6] == 1 else 4; start = 8 + width
    need(len(raw) >= start, 'complete NPY header prefix')
    size = int.from_bytes(raw[8:start], 'little'); need(0 < size <= 16384 and len(raw) >= start+size, 'bounded NPY header')
    expression = ast.parse(raw[start:start+size].decode('latin1').strip(), mode='eval')
    need(isinstance(expression.body, ast.Dict) and len(expression.body.keys) == 3
         and all(isinstance(k, ast.Constant) and type(k.value) is str for k in expression.body.keys), 'literal primitive header keys')
    keys = [k.value for k in expression.body.keys]
    need(set(keys) == {'descr', 'fortran_order', 'shape'} and len(set(keys)) == 3, 'exact nonduplicate NPY fields')
    value = ast.literal_eval(expression)
    need(value['descr'] == expected_dtype and value['fortran_order'] is False
         and type(value['shape']) is tuple and list(value['shape']) == list(expected_shape), 'exact declared C-order shape/dtype')
    elements, count = shape_extent(value['shape'], value['descr'])
    need(len(raw) == start+size+count, 'exact primitive payload extent before numerical allocation')
    return start+size, elements, count


def load(desc, roots, limits):
    need(type(desc) is dict and set(desc) == {'path', 'pin', 'shape', 'dtype'}, 'exact primitive array descriptor')
    path = canonical(desc['path']); roots = [canonical(r) for r in roots]
    need(any(r in path.parents for r in roots), 'array inside admitted input root')
    expected = descriptor(desc['pin']); elements, count = shape_extent(desc['shape'], desc['dtype'])
    need(count + 10 <= expected['bytes'] <= count + 16396, 'declared payload/header bound before read')
    limits.reserve('allocation_bytes', 2 * expected['bytes'] + count)
    limits.reserve('elements', elements); limits.reserve('files', 1)
    raw, _ = capture(path, expected, count+16396, limits.budget, readonly=True)
    offset, _, _ = header(raw, desc['shape'], desc['dtype'])
    import numpy as np
    array = np.frombuffer(raw, dtype=desc['dtype'], count=elements, offset=offset).reshape(desc['shape']).copy(order='C')
    need(array.dtype.kind not in 'fc' or bool(np.isfinite(array).all()), 'all numeric values finite before downstream use')
    limits.budget.tick(); return array


def save(array, path, limits):
    import numpy as np
    need(type(array) is np.ndarray and array.dtype.str in DTYPES and array.flags.c_contiguous, 'safe exact primitive C ndarray')
    need(array.dtype.kind not in 'fc' or bool(np.isfinite(array).all()), 'finite raw output before projection/serialization')
    _, size = shape_extent(array.shape, array.dtype.str)
    text = repr({'descr': array.dtype.str, 'fortran_order': False, 'shape': tuple(array.shape)})
    padding = (64 - ((10 + len(text) + 1) % 64)) % 64
    h = (text + ' ' * padding + '\n').encode('latin1'); need(len(h) < 65536, 'primitive writer header')
    limits.reserve('allocation_bytes', 2 * size + len(h) + 10)
    limits.reserve('serialized_bytes', size+len(h)+10); limits.reserve('files', 1)
    body = b'\x93NUMPY\x01\x00' + struct.pack('<H', len(h)) + h + array.tobytes(order='C')
    desc = publish(path, body, limits.budget, readonly=True)
    return {'path': str(path), 'pin': desc, 'shape': list(array.shape), 'dtype': array.dtype.str}


def pack(value, root, limits, array_cap, metadata_cap):
    """Bounded acyclic safe tree; no arbitrary object reduction or executable state."""
    import numpy as np
    arrays = []; seen = set(); nodes = 0; text_cost = 0
    def walk(x, depth):
        nonlocal nodes, text_cost
        nodes += 1; need(depth <= 32 and nodes <= metadata_cap//2, 'safe state tree bounds')
        if type(x) is np.ndarray:
            need(len(arrays) < array_cap, 'complete declared state array count')
            name = 'arrays/' + str(len(arrays)).zfill(8) + '.npy'
            d = save(x, Path(root)/name, limits); arrays.append(d)
            return {'__primitive_array__': {**d, 'path': name}}
        if type(x) in (list, tuple, dict):
            need(id(x) not in seen, 'no cyclic or aliased state containers'); seen.add(id(x))
            if type(x) is dict:
                need(all(type(k) is str for k in x), 'string state keys')
                out = {k: walk(v, depth+1) for k, v in x.items()}
                text_cost += sum(6*len(k.encode())+4 for k in x)
            else: out = [walk(v, depth+1) for v in x]
            return out
        need(x is None or type(x) in (str, int, float, bool), 'safe primitive state only')
        if type(x) is float: finite(x)
        if type(x) is str: text_cost += 6*len(x.encode())+2
        elif type(x) is int: text_cost += len(str(x))+2
        else: text_cost += 32
        need(text_cost + nodes*4 <= metadata_cap, 'prospective state JSON size bound')
        return x
    tree = walk(value, 0)
    limits.reserve('serialized_bytes', metadata_cap); limits.reserve('allocation_bytes', 2*metadata_cap)
    raw = encoded(tree); need(len(raw) <= metadata_cap, 'safe state exact metadata cap')
    return tree, arrays


def unpack(value, root, limits):
    if type(value) is dict and set(value) == {'__primitive_array__'}:
        d = dict(value['__primitive_array__']); from core import relative
        d['path'] = str(canonical(root)/relative(d['path'])); return load(d, [root], limits)
    if type(value) is dict: return {k: unpack(v, root, limits) for k, v in value.items()}
    if type(value) is list: return [unpack(v, root, limits) for v in value]
    need(value is None or type(value) in (str, int, float, bool), 'safe decoded primitive'); return value
