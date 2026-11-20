"""Target-free, source-precision scalar gains over a frozen VALID prediction.

The generic HDF5 seam supports small generated fixtures. The production wrapper
always supplies the complete original VALID geometry. This module has no target
operand, evaluator import, method fitting, or process-qualification authority.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import types

DATASET = 'mc_maze_20'
GAIN_GRID = ((1, 1), (8, 9), (9, 8), (4, 5), (5, 4), (2, 3), (3, 2), (1, 2), (2, 1))
RATE_KEYS = tuple(f'{split}_rates_{units}{suffix}' for split in ('train', 'eval')
                  for suffix in ('', '_forward') for units in ('heldin', 'heldout'))
SHAPES = {name: [1721 if name.startswith('train_') else 574,
                 10 if name.endswith('_forward') else 35,
                 137 if 'heldin' in name else 45] for name in RATE_KEYS}
FILE_CAP = 512 * 1024 * 1024
META_CAP = 1024 * 1024
BLOCK_BYTES = 4 * 1024 * 1024


def need(condition, message):
    if not condition:
        raise ValueError(message)


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def validate_pin(value, cap=FILE_CAP):
    need(type(value) is dict and set(value) == {'bytes', 'sha256'}
         and type(value['bytes']) is int and 0 < value['bytes'] <= cap
         and type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}', value['sha256']),
         'exact bounded byte identity')
    return value


def ordinary(value):
    need(isinstance(value, (str, Path)), 'path text')
    text = str(value)
    p = Path(text)
    need(p.is_absolute() and str(p) == text and '..' not in p.parts
         and not any(c in text for c in ('\0', '\n', '\r')), 'canonical absolute path')
    need(not any(q.is_symlink() for q in (p, *p.parents)), 'no named-path symlink')
    return p


def signature(value):
    return tuple(getattr(value, name) for name in
                 ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns'))


def read_pin(value, cap=FILE_CAP):
    p = ordinary(value)
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and 0 < before.st_size <= cap, 'bounded ordinary single-link file')
        digest = hashlib.sha256()
        count = 0
        while True:
            block = stream.read(min(1024 * 1024, cap - count + 1))
            if not block:
                break
            count += len(block)
            need(count <= cap, 'bounded file read')
            digest.update(block)
        after = os.fstat(stream.fileno())
    need(count == before.st_size and signature(before) == signature(after) == signature(p.lstat()),
         'complete stable named file')
    return {'bytes': count, 'sha256': digest.hexdigest()}


def descriptor(value):
    need(type(value) is dict and set(value) == {'path', 'bytes', 'sha256'}, 'named byte descriptor')
    ordinary(value['path'])
    validate_pin({key: value[key] for key in ('bytes', 'sha256')})
    return value


def _source_bytes(value):
    p = ordinary(value)
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and 0 < before.st_size <= META_CAP, 'bounded ordinary kernel source or metadata')
        raw = stream.read(META_CAP + 1)
        after = os.fstat(stream.fileno())
    need(len(raw) == before.st_size and signature(before) == signature(after) == signature(p.lstat()),
         'stable complete kernel source or metadata')
    return raw


def _decoded(raw):
    def unique(rows):
        result = {}
        for key, value in rows:
            need(key not in result, 'no duplicate kernel manifest fields')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda _: need(False, 'finite kernel manifest JSON'))


def _authenticated_core():
    root = ordinary(Path(__file__).absolute()).parent
    source_path = root / 'SOURCE.json'
    raw = _source_bytes(source_path)
    manifest = _decoded(raw)
    names = {'gain_core.py', 'gain_selector.py', 'gain_transform.py', 'METHOD.json'}
    need(type(manifest) is dict and set(manifest) == {'schema', 'files'}
         and manifest['schema'] == 'smc_gain_kernel_source_v1'
         and type(manifest['files']) is dict and set(manifest['files']) == names,
         'exact four-leaf gain kernel source manifest')
    sources = {}
    for name in sorted(names):
        expected = validate_pin(manifest['files'][name], META_CAP)
        sources[name] = _source_bytes(root / name)
        need(pin(sources[name]) == expected, 'authenticated gain kernel leaf: ' + name)
    need(pin(sources['gain_transform.py']) == source_identity(), 'current transform matches selected kernel source')
    module = types.ModuleType('_smc_authenticated_gain_transform_core')
    module.__file__ = str(root / 'gain_core.py')
    exec(compile(sources['gain_core.py'], module.__file__, 'exec'), module.__dict__)
    return module, {'path': str(source_path), **pin(raw)}


def source_identity():
    return read_pin(Path(__file__).absolute(), META_CAP)


def validate_gain(gain):
    need(type(gain) is list and len(gain) == 2 and all(type(x) is int and x > 0 for x in gain)
         and tuple(gain) in GAIN_GRID, 'one exact declared positive reduced rational gain')
    return tuple(gain)


def _arithmetic(dtype, gain):
    import numpy as np
    numerator, denominator = validate_gain(gain)
    source_dtype = np.dtype(dtype)
    need(source_dtype.kind == 'f' and source_dtype.itemsize in (4, 8)
         and source_dtype.fields is None and source_dtype.subdtype is None
         and not source_dtype.metadata, 'only ordinary float32/float64 rate dtype')
    arithmetic_dtype = np.dtype('float32' if source_dtype.itemsize == 4 else 'float64')
    with np.errstate(over='raise', invalid='raise', divide='raise', under='ignore'):
        scalar = np.divide(np.asarray(numerator, dtype=arithmetic_dtype),
                           np.asarray(denominator, dtype=arithmetic_dtype), dtype=arithmetic_dtype)
    need(bool(np.isfinite(scalar)) and bool(scalar > 0), 'finite strictly positive executed gain')
    return source_dtype, arithmetic_dtype, scalar


def executed_gain(dtype, gain):
    """Shared selector/transform description of the actually rounded scalar."""
    source_dtype, arithmetic_dtype, scalar = _arithmetic(dtype, gain)
    return {'gain': list(gain), 'dtype': source_dtype.str,
            'arithmetic_dtype': arithmetic_dtype.name, 'value_hex': float(scalar).hex()}


def scale_block(array, gain):
    """Scale in source precision; retain zero rates, dtype, shape and index order."""
    import numpy as np
    need(isinstance(array, np.ndarray), 'rate block is an ndarray')
    source_dtype, arithmetic_dtype, scalar = _arithmetic(array.dtype, gain)
    need(bool(np.isfinite(array).all()) and bool((array >= 0).all()),
         'finite nonnegative source rates')
    if gain == [1, 1]:
        return array.copy(order='K')
    try:
        with np.errstate(over='raise', invalid='raise', divide='raise', under='ignore'):
            result = np.multiply(array, scalar, dtype=arithmetic_dtype)
    except FloatingPointError as error:
        raise ValueError('gain multiplication overflow or invalid result') from error
    result = np.asarray(result, dtype=source_dtype)
    need(result.dtype == array.dtype and result.shape == array.shape
         and bool(np.isfinite(result).all()) and bool((result >= 0).all()),
         'same-dtype finite nonnegative transformed rates')
    need(not bool(((array > 0) & (result == 0)).any()), 'no positive-to-zero gain underflow')
    return result


def _validate_shapes(expected_shapes):
    need(type(expected_shapes) is dict and set(expected_shapes) == set(RATE_KEYS),
         'exact eight canonical prediction rate fields')
    for shape in expected_shapes.values():
        need(type(shape) is list and len(shape) == 3
             and all(type(x) is int and x > 0 for x in shape), 'three positive array dimensions')
    need(sum(math.prod(shape) * 8 for shape in expected_shapes.values()) <= FILE_CAP,
         'bounded complete rate-array extent')


def _attrs(obj):
    """Fingerprint supported non-rate attributes without changing them."""
    import h5py
    import numpy as np
    names = list(obj.attrs.keys())
    need(len(names) <= 128 and all(type(x) is str and len(x) <= 256 for x in names),
         'bounded attribute names')
    rows = []
    total = 0
    for name in names:
        attribute_id = obj.attrs.get_id(name)
        dtype = attribute_id.dtype
        shape = list(attribute_id.shape)
        need(math.prod(shape) * max(dtype.itemsize, 1) <= META_CAP, 'bounded attribute extent')
        vlen = h5py.check_dtype(vlen=dtype)
        need(h5py.check_dtype(ref=dtype) is None and dtype.fields is None and dtype.subdtype is None,
             'no indirect or compound attribute')
        value = np.asarray(obj.attrs[name])
        if vlen in (str, bytes):
            chunks = []
            for item in value.reshape(-1):
                need(isinstance(item, (str, bytes)), 'string attribute values')
                data = item.encode('utf-8') if isinstance(item, str) else bytes(item)
                chunks.append(len(data).to_bytes(8, 'big') + data)
            raw = b''.join(chunks)
            encoding = 'utf8' if vlen is str else 'bytes'
        else:
            need(vlen is None and dtype.kind in 'biufcS' and value.dtype.kind != 'O',
                 'supported finite-size attribute dtype')
            raw = np.asarray(value, dtype=dtype).tobytes(order='C')
            encoding = None
        total += len(raw)
        need(total <= META_CAP, 'whole attribute metadata cap')
        rows.append({'name': name, 'dtype': dtype.str, 'shape': shape, 'vlen': encoding,
                     'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
    return rows


def _inspect(handle, expected_shapes, gain):
    import h5py
    import numpy as np
    _validate_shapes(expected_shapes)
    need(list(handle) == [DATASET]
         and isinstance(handle.get(DATASET, getlink=True), h5py.HardLink), 'one direct prediction group')
    group = handle[DATASET]
    need(isinstance(group, h5py.Group) and set(group) == set(RATE_KEYS), 'canonical prediction group')
    seen = set()
    metadata = {'root_attrs': _attrs(handle), 'group_attrs': _attrs(group),
                'rate_order': list(group), 'datasets': {}}
    for name in RATE_KEYS:
        need(isinstance(group.get(name, getlink=True), h5py.HardLink), 'direct rate dataset')
        item = group[name]
        need(isinstance(item, h5py.Dataset) and not item.is_virtual and not item.external,
             'ordinary internal rate dataset')
        address = h5py.h5o.get_info(item.id).addr
        need(address not in seen, 'no shared rate object alias')
        seen.add(address)
        need(list(item.shape) == expected_shapes[name], 'exact selected rate geometry')
        _arithmetic(item.dtype, gain)
        need(item.scaleoffset is None and item.compression in (None, 'gzip', 'lzf'),
             'supported lossless rate storage')
        row_bytes = math.prod(item.shape[1:]) * item.dtype.itemsize
        need(row_bytes <= BLOCK_BYTES, 'bounded single trial block')
        step = max(1, BLOCK_BYTES // row_bytes)
        for first in range(0, item.shape[0], step):
            block = item[first:first + step]
            need(bool(np.isfinite(block).all()) and bool((block >= 0).all()),
                 'finite nonnegative prediction rates')
        fill = np.asarray(item.fillvalue, dtype=item.dtype).tobytes().hex()
        metadata['datasets'][name] = {
            'shape': list(item.shape), 'dtype': item.dtype.str, 'attrs': _attrs(item),
            'chunks': item.chunks, 'compression': item.compression,
            'compression_opts': item.compression_opts, 'shuffle': item.shuffle,
            'fletcher32': item.fletcher32, 'scaleoffset': item.scaleoffset,
            'fillvalue_bytes': fill, 'maxshape': item.maxshape,
            'executed_gain': executed_gain(item.dtype, gain)}
    return metadata


def _stable_copy(source, destination, expected):
    source, destination = ordinary(source), ordinary(destination)
    validate_pin(expected)
    need(source != destination and destination.parent.is_dir() and not os.path.lexists(destination),
         'fresh distinct output under an existing directory')
    infd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(infd, 'rb') as incoming:
        before = os.fstat(incoming.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and 0 < before.st_size <= FILE_CAP and before.st_size == expected['bytes'],
             'bounded frozen baseline input')
        outfd = os.open(destination, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(outfd, 'wb') as outgoing:
            digest = hashlib.sha256()
            count = 0
            while True:
                block = incoming.read(min(1024 * 1024, FILE_CAP - count + 1))
                if not block:
                    break
                count += len(block)
                need(count <= FILE_CAP, 'copy byte cap')
                outgoing.write(block)
                digest.update(block)
            outgoing.flush()
            os.fsync(outgoing.fileno())
        after = os.fstat(incoming.fileno())
    observed = {'bytes': count, 'sha256': digest.hexdigest()}
    need(count == before.st_size and signature(before) == signature(after) == signature(source.lstat()),
         'stable full baseline snapshot')
    need(observed == expected and read_pin(destination) == expected, 'authenticated exact baseline byte copy')
    return destination


def transform_h5(source, destination, expected_baseline_pin, gain, *, expected_shapes):
    """Shape-generic generated-fixture seam; production fixes SHAPES below.

    An unsuccessful call can leave only its fresh partial output. No input file
    is mutated, and a receipt is returned only after complete output validation.
    """
    import h5py
    validate_gain(gain)
    _validate_shapes(expected_shapes)
    destination = _stable_copy(source, destination, expected_baseline_pin)
    fd = os.open(destination, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        initial = os.fstat(stream.fileno())
        need(stat.S_ISREG(initial.st_mode) and initial.st_nlink == 1
             and signature(initial) == signature(destination.lstat()), 'owned ordinary copied output')
        # Reject every redirected dataset/link/attribute before opening HDF5 r+.
        with h5py.File(stream, 'r') as handle:
            metadata = _inspect(handle, expected_shapes, gain)
        inspected = os.fstat(stream.fileno())
        need(signature(initial) == signature(inspected) == signature(destination.lstat()),
             'stable read-only complete HDF5 admission')
        if gain == [1, 1]:
            os.fchmod(stream.fileno(), 0o400)
    if gain != [1, 1]:
        fd = os.open(destination, os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'r+b') as stream:
            need(signature(os.fstat(stream.fileno())) == signature(inspected) == signature(destination.lstat()),
                 'same inspected HDF5 bytes before write admission')
            with h5py.File(stream, 'r+') as handle:
                for name in RATE_KEYS:
                    item = handle[DATASET][name]
                    row_bytes = math.prod(item.shape[1:]) * item.dtype.itemsize
                    step = max(1, BLOCK_BYTES // row_bytes)
                    for first in range(0, item.shape[0], step):
                        result = scale_block(item[first:first + step], gain)
                        item[first:first + step] = result
                        reread = item[first:first + step]
                        need(reread.dtype == result.dtype and reread.tobytes(order='C') == result.tobytes(order='C'),
                             'stored transformed values retain exact dtype and element order')
                handle.flush()
                need(encoded(_inspect(handle, expected_shapes, gain)) == encoded(metadata),
                     'rate geometry, dtype, units, attributes, order and creation properties unchanged')
            stream.flush()
            os.fsync(stream.fileno())
            final = os.fstat(stream.fileno())
            need((initial.st_dev, initial.st_ino) == (final.st_dev, final.st_ino)
                 and final.st_nlink == 1 and 0 < final.st_size <= FILE_CAP
                 and signature(final) == signature(destination.lstat()), 'same bounded ordinary output inode')
            os.fchmod(stream.fileno(), 0o400)
    result = read_pin(destination)
    if gain == [1, 1]:
        need(result == expected_baseline_pin, 'identity preserves every serialized HDF5 byte')
    return {'schema': 'smc_gain_transform_result_v1', 'gain': list(gain),
            'baseline': dict(expected_baseline_pin), 'output': {'path': str(destination), **result},
            'identity_byte_copy': gain == [1, 1], 'rate_fields': list(RATE_KEYS),
            'shapes': expected_shapes, 'executed_gains':
            {name: metadata['datasets'][name]['executed_gain'] for name in RATE_KEYS},
            'metadata_sha256': hashlib.sha256(encoded(metadata)).hexdigest(),
            'target_accessed': False, 'inference_execution_qualified': False,
            'scientific_improvement': False}


def production_transform(selection_descriptor, method_descriptor, selector_result_descriptor, output_path):
    """Admit an actually bounded selection before copying any prediction bytes.

    Only gain_core admits the frozen method, baseline lineage, exact grid winner
    and bounded selector result. No raw-gain override or target operand exists.
    """
    core, source = _authenticated_core()
    admitted = core.admit_selected_gain(selection_descriptor, method_descriptor, selector_result_descriptor)
    need(type(admitted) is dict
         and set(admitted) == {'gain', 'baseline_descriptor', 'method', 'selection', 'lineage', 'source'},
         'exact authenticated selected-gain admission')
    need(encoded(admitted['source']) == encoded(source), 'admitted selected source is current gain kernel')
    need(encoded(core.SHAPES) == encoded(SHAPES), 'unchanged complete original VALID geometry')
    gain = admitted['gain']
    validate_gain(gain)
    baseline = descriptor(admitted['baseline_descriptor'])
    result = transform_h5(baseline['path'], output_path,
                          {key: baseline[key] for key in ('bytes', 'sha256')},
                          gain, expected_shapes=SHAPES)
    return {'schema': 'smc_gain_production_transform_v1', 'source': source,
            'method': admitted['method'], 'selection': admitted['selection'],
            'selector_result': selector_result_descriptor, 'lineage': admitted['lineage'],
            'baseline': baseline, 'output': result['output'], 'transform': result,
            'target_accessed': False, 'scientific_improvement': False}
