"""Bounded primitive NPY/JSON custody. Actual immutable backing is external."""
import ast
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import struct
from contextlib import contextmanager
from .budget import ReferenceFailure, require, encode
from .contracts import numpy

PRIMITIVES = {'|b1': (1, 'bool'), '<f4': (4, 'float32'), '<f8': (8, 'float64'),
              '<i8': (8, 'int64'), '|u1': (1, 'uint8')}
PUBLIC_DTYPES = {v[1]: k for k, v in PRIMITIVES.items()}


def pin_check(pin):
    require(type(pin) is dict and set(pin) == {'bytes', 'sha256'} and
            type(pin['bytes']) is int and pin['bytes'] >= 0 and
            type(pin['sha256']) is str and re.fullmatch('[0-9a-f]{64}', pin['sha256']), 'body pin')


def canonical_path(value, *, exists=True):
    require(type(value) is str and value.startswith('/') and '\x00' not in value, 'absolute primitive path')
    p = Path(value)
    require(str(p) == value and all(x not in ('.', '..') for x in p.parts), 'canonical path')
    for q in reversed((p, *p.parents)):
        if q == p and not exists:
            continue
        st = q.lstat()
        require(not stat.S_ISLNK(st.st_mode), 'symlink component')
        if q != p:
            require(stat.S_ISDIR(st.st_mode), 'directory component')
    return p


def descriptor(desc, roots):
    require(type(desc) is dict and set(desc) in ({'path', 'pin'}, {'path', 'pin', 'shape', 'dtype'}), 'descriptor schema')
    pin_check(desc['pin'])
    p = canonical_path(desc['path'])
    require(any(p != root and root in p.parents for root in roots), 'outside admitted input roots')
    return p


def stamp(st):
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns, st.st_mode, st.st_nlink)


def joined(file, path, initial):
    a, b = os.fstat(file.fileno()), path.lstat()
    require(stat.S_ISREG(a.st_mode) and a.st_nlink == 1 and stamp(a) == initial and stamp(b) == initial,
            'same-open/current-name/extent identity changed')


def hash_open(file, size, budget):
    budget.charge('read_bytes', size+1, 'full source body plus sentinel')
    file.seek(0)
    digest, seen = hashlib.sha256(), 0
    while seen < size:
        budget.tick('bounded body hash chunk')
        chunk = file.read(min(65536, size-seen))
        require(bool(chunk), 'short body')
        digest.update(chunk)
        seen += len(chunk)
    require(file.read(1) == b'', 'unexpected trailing body')
    budget.tick('body hash read completed')
    return digest.hexdigest()


@contextmanager
def captured(desc, roots, budget):
    path = descriptor(desc, roots)
    budget.charge('files', 1, 'input open')
    fd, file, failure, later = None, None, None, []
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
        st = os.fstat(fd)
        require(stat.S_ISREG(st.st_mode) and st.st_nlink == 1 and st.st_size == desc['pin']['bytes'], 'exact ordinary input extent')
        initial = stamp(st)
        file = os.fdopen(fd, 'rb', buffering=0)
        fd = None
        joined(file, path, initial)
        require(hash_open(file, st.st_size, budget) == desc['pin']['sha256'], 'input body hash')
        file.seek(0)
        yield file
        joined(file, path, initial)
        require(hash_open(file, st.st_size, budget) == desc['pin']['sha256'], 'post-operation input body hash')
        joined(file, path, initial)
        budget.tick('captured input completed')
    except BaseException as exc:
        failure = exc
    finally:
        for handle in (file,):
            if handle is not None:
                try:
                    handle.close()
                except BaseException as exc:
                    later.append(type(exc).__name__+': '+str(exc)[:500])
        if fd is not None:
            try:
                os.close(fd)
            except BaseException as exc:
                later.append(type(exc).__name__+': '+str(exc)[:500])
        try:
            budget.tick('input post-close clock')
        except BaseException as exc:
            if failure is None:
                failure = exc
            else:
                later.append(type(exc).__name__+': '+str(exc)[:500])
    if failure is not None or later:
        record = {'cost': budget.snapshot(), 'primary': repr(failure)[:1000], 'later': later,
                  'path': str(path), 'no_retry': True}
        raise ReferenceFailure('input operation failed', record) from failure


def parse_json(body):
    def pairs(rows):
        d = {}
        for key, val in rows:
            require(key not in d, 'duplicate JSON key')
            d[key] = val
        return d
    return json.loads(body, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ReferenceFailure('nonfinite JSON')))


def read_json(desc, roots, budget):
    size = desc['pin']['bytes']
    budget.charge('serialized_bytes', size*4+4096, 'JSON parse/metadata reservation')
    budget.workspace(size*16+65536, 'bounded JSON parse workspace')
    with captured(desc, roots, budget) as file:
        budget.charge('read_bytes', size+1, 'JSON actual read plus sentinel')
        body = file.read(size+1)
        require(len(body) == size, 'JSON exact body')
        obj = parse_json(body)
        budget.tick('JSON parsed')
    return obj


def header(file, extent, expected_shape, expected_dtype, budget):
    """Read only a bounded header; shape/primitive/extent admission precedes load."""
    budget.charge('read_bytes', min(extent, 65548), 'NPY bounded header reservation')
    start = file.read(8)
    require(len(start) == 8 and start[:6] == b'\x93NUMPY' and start[6:] in (b'\x01\x00', b'\x02\x00'), 'NPY version')
    width = 2 if start[6] == 1 else 4
    size_bytes = file.read(width)
    require(len(size_bytes) == width, 'NPY length field')
    length = int.from_bytes(size_bytes, 'little')
    require(0 < length <= 65536 and 8+width+length <= extent, 'bounded NPY header extent')
    body = file.read(length)
    require(len(body) == length and body.endswith(b'\n'), 'NPY header bytes')
    tree = ast.parse(body.decode('latin1').strip(), mode='eval')
    require(isinstance(tree.body, ast.Dict) and len(tree.body.keys) == 3, 'exact NPY dictionary')
    keys = [ast.literal_eval(k) for k in tree.body.keys]
    require(len(set(keys)) == 3 and set(keys) == {'descr', 'fortran_order', 'shape'}, 'NPY fields')
    h = ast.literal_eval(tree)
    require(h['fortran_order'] is False and h['descr'] in PRIMITIVES, 'primitive native little-endian C-order NPY')
    shape = h['shape']
    require(type(shape) is tuple and 1 <= len(shape) <= 4 and
            all(type(x) is int and 0 <= x < 2**40 for x in shape), 'NPY shape')
    require(list(shape) == expected_shape and PRIMITIVES[h['descr']][1] == expected_dtype, 'NPY declared shape/dtype')
    nbytes = math.prod(shape)*PRIMITIVES[h['descr']][0]
    require(8+width+length+nbytes == extent, 'NPY exact payload extent')
    budget.arrays(nbytes*3+65536, 'NPY load/copy native source reservation', live=nbytes*4+65536)
    budget.tick('NPY header admitted before allocation')
    return shape


def read_array(desc, roots, budget):
    require(set(desc) == {'path', 'pin', 'shape', 'dtype'} and type(desc['shape']) is list
            and desc['dtype'] in PUBLIC_DTYPES, 'primitive array descriptor')
    with captured(desc, roots, budget) as file:
        header(file, desc['pin']['bytes'], desc['shape'], desc['dtype'], budget)
        file.seek(0)
        budget.charge('read_bytes', desc['pin']['bytes']+1, 'NPY decoder read reservation')
        np = numpy()
        value = np.load(file, allow_pickle=False)
        require(type(value) is np.ndarray and value.shape == tuple(desc['shape']) and
                value.dtype == np.dtype(desc['dtype']) and value.flags.c_contiguous, 'decoded primitive NPY')
        require(bool(np.isfinite(value).all()), 'finite state/input matrix')
        budget.tick('NPY decoded')
    return value


def directory_sync(path, budget):
    fd, failure = None, None
    try:
        budget.charge('files', 1, 'directory fsync open')
        fd = os.open(path, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
        os.fsync(fd)
        budget.tick('directory fsync completed')
    except BaseException as exc:
        failure = exc
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except BaseException as exc:
                if failure is None:
                    failure = exc
                else:
                    raise ReferenceFailure('directory close after primary failure',
                        {'primary': repr(failure)[:1000], 'later': repr(exc)[:1000], 'cost': budget.snapshot()}) from failure
    if failure is not None:
        raise failure
    budget.tick('directory post-close clock')


def make_directory(path, budget):
    budget.charge('files', 1, 'fresh directory entry')
    path.mkdir(mode=0o700)
    directory_sync(path.parent, budget)


def publish(path, chunks, length, budget):
    budget.charge('write_bytes', length, 'exclusive primitive publication')
    budget.charge('files', 1, 'output file entry')
    fd, file, failure, later = None, None, None, []
    digest, size = hashlib.sha256(), 0
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        file = os.fdopen(fd, 'wb', buffering=0)
        fd = None
        for chunk in chunks:
            budget.tick('output chunk')
            require(size+len(chunk) <= length, 'publication bound')
            view = memoryview(chunk)
            while view:
                count = file.write(view)
                require(type(count) is int and count > 0, 'output short write')
                digest.update(view[:count])
                size += count
                view = view[count:]
        require(size == length, 'publication exact extent')
        file.flush()
        budget.tick('output flush completed')
        os.fchmod(file.fileno(), 0o444)
        os.fsync(file.fileno())
        initial = stamp(os.fstat(file.fileno()))
        joined(file, path, initial)
        budget.tick('output fsync completed')
    except BaseException as exc:
        failure = exc
    finally:
        if file is not None:
            try:
                file.close()
            except BaseException as exc:
                later.append(repr(exc)[:500])
        if fd is not None:
            try:
                os.close(fd)
            except BaseException as exc:
                later.append(repr(exc)[:500])
    if failure is None and not later:
        try:
            require(stamp(path.lstat()) == initial, 'post-close output identity')
            directory_sync(path.parent, budget)
            budget.tick('output publication post-close')
        except BaseException as exc:
            failure = exc
    if failure is not None or later:
        raise ReferenceFailure('publication incomplete', {'primary': repr(failure)[:1000], 'later': later,
            'path': str(path), 'intended_bytes': length, 'observed_written_bytes': size,
            'cost': budget.snapshot(), 'durability_uncertain': True, 'no_retry': True}) from failure
    return {'path': str(path), 'pin': {'bytes': size, 'sha256': digest.hexdigest()}}


def write_json(path, obj, budget):
    body = encode(obj, budget, 'output JSON')
    return publish(path, (body,), len(body), budget)


def write_array(path, value, budget):
    np = numpy()
    require(type(value) is np.ndarray and value.flags.c_contiguous and value.dtype.name in PUBLIC_DTYPES
            and 1 <= value.ndim <= 4, 'safe primitive output')
    budget.arrays(value.size, 'output array finite-check mask', live=value.nbytes+value.size+65536)
    require(bool(np.isfinite(value).all()), 'finite primitive output')
    descr = PUBLIC_DTYPES[value.dtype.name]
    text = repr({'descr': descr, 'fortran_order': False, 'shape': tuple(value.shape)}).encode('ascii')
    padding = (64-(10+len(text)+1)%64)%64
    body = text+b' '*padding+b'\n'
    require(len(body) < 65536, 'output NPY header bound')
    budget.charge('serialized_bytes', len(body)+10, 'NPY header encoding')
    prefix = b'\x93NUMPY\x01\x00'+struct.pack('<H', len(body))+body
    # CPython refuses a cast for some zero-extent multidimensional buffer shapes.
    view = memoryview(value).cast('B') if value.nbytes else memoryview(b'')
    def chunks():
        yield prefix
        for offset in range(0, value.nbytes, 65536):
            yield view[offset:offset+65536]
    desc = publish(path, chunks(), len(prefix)+value.nbytes, budget)
    desc.update({'shape': list(value.shape), 'dtype': value.dtype.name})
    return desc


def packing_plan(obj, budget):
    from .budget import json_bound
    np = numpy()
    def bound(value, depth=0):
        require(depth < 64, 'packing depth')
        if type(value) is np.ndarray:
            return 2048
        if type(value) is dict:
            require(all(type(k) is str for k in value), 'packing keys')
            return 2+sum(json_bound(k)+bound(v,depth+1)+2 for k,v in value.items())
        if type(value) in (tuple,list):
            return 2+sum(bound(v,depth+1)+1 for v in value)
        return json_bound(value)
    size = bound(obj)
    budget.charge('serialized_bytes', size, 'safe state descriptor-tree prospective construction')
    budget.workspace(size*4, 'safe state descriptor-tree live bound')


def pack(obj, root, budget, counter=None):
    np = numpy()
    if counter is None:
        counter = [0]
    if type(obj) is np.ndarray:
        index = counter[0]
        counter[0] += 1
        return {'__primitive_array__': write_array(root/'arrays'/('%08d.npy' % index), obj, budget)}
    if type(obj) is dict:
        require('__primitive_array__' not in obj, 'reserved state marker')
        return {k: pack(v, root, budget, counter) for k, v in obj.items()}
    if type(obj) in (list, tuple):
        return [pack(v, root, budget, counter) for v in obj]
    require(obj is None or type(obj) in (str, bool, int, float), 'primitive safe state only')
    return obj


def unpack(obj, roots, budget, depth=0):
    require(depth < 64, 'state depth')
    if type(obj) is dict:
        if '__primitive_array__' in obj:
            require(set(obj) == {'__primitive_array__'}, 'array marker schema')
            return read_array(obj['__primitive_array__'], roots, budget)
        return {k: unpack(v, roots, budget, depth+1) for k, v in obj.items()}
    if type(obj) is list:
        return [unpack(v, roots, budget, depth+1) for v in obj]
    require(obj is None or type(obj) in (str, bool, int, float), 'safe state scalar')
    return obj
