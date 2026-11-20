"""Bounded typed arrays and template-bound pytrees; no dynamic class loading."""
import base64
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import fixed_coordinate_policy as fixed_policy
import struct

MAX_LEAVES = 1024
MAX_RAW_BYTES = 262144
MAX_STRUCTURE_BYTES = 65536
DTYPES = {'<f8', '<f4', '<i8', '<i4', '<u8', '<u4', '|b1', '|i1', '|u1', '<i2', '<u2'}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON field')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda value: require(False, 'nonfinite JSON constant'))


def array_descriptor(value, np, *, role='finite', path=()):
    try:
        array = np.asarray(value)
    except Exception:
        raise fixed_policy.BoundaryViolation(role, path, [], 'unconverted', 'leaf_conversion') from None
    shape, dtype = list(array.shape), array.dtype.str
    for accepted, category in ((dtype in DTYPES, 'leaf_dtype'), (array.ndim <= 4, 'leaf_rank'),
                               (array.nbytes <= MAX_RAW_BYTES, 'leaf_extent')):
        if not accepted:
            raise fixed_policy.BoundaryViolation(role, path, shape, dtype, category)
    try:
        array = array.copy(order='C')
        raw = array.tobytes(order='C')
    except Exception:
        raise fixed_policy.BoundaryViolation(role, path, shape, dtype, 'leaf_byte_conversion') from None
    fixed_policy.validate_leaf_bytes(role, path, shape, dtype, raw)
    return array, {'shape': shape, 'dtype': dtype, 'sha256': hashlib.sha256(raw).hexdigest()}


def encode_array(value, np, *, role='finite', path=()):
    array, descriptor = array_descriptor(value, np, role=role, path=path)
    raw = array.tobytes(order='C')
    require(len(raw) <= MAX_RAW_BYTES, 'bounded context leaf')
    return {**descriptor, 'nbytes': len(raw), 'data_base64': base64.b64encode(raw).decode('ascii')}


def _decode_leaf_record(packet, *, role, path):
    require(type(packet) is dict and set(packet) == {'shape', 'dtype', 'sha256', 'nbytes', 'data_base64'},
            'exact context leaf schema')
    shape, dtype, size = packet['shape'], packet['dtype'], packet['nbytes']
    require(type(shape) is list and len(shape) <= 4 and all(type(x) is int and 0 <= x <= MAX_RAW_BYTES for x in shape),
            'plain context shape')
    require(type(dtype) is str and dtype in DTYPES and type(size) is int and 0 <= size <= MAX_RAW_BYTES,
            'bounded context dtype/extent')
    require(math.prod(shape) * struct.calcsize('<' + fixed_policy.DTYPE_FORMATS[dtype]) == size,
            'shape matches byte extent')
    text = packet['data_base64']
    require(type(text) is str and len(text) <= 4 * ((MAX_RAW_BYTES + 2) // 3), 'bounded base64 leaf')
    raw = base64.b64decode(text, validate=True)
    require(len(raw) == size and base64.b64encode(raw).decode('ascii') == text and
            hashlib.sha256(raw).hexdigest() == packet['sha256'], 'canonical complete authenticated leaf')
    fixed_policy.validate_leaf_bytes(role, path, shape, dtype, raw)
    return {'path': list(path), 'shape': shape, 'dtype': dtype, 'raw': raw}


def decode_array(packet, np, *, role='finite', path=()):
    record = _decode_leaf_record(packet, role=role, path=path)
    return np.frombuffer(record['raw'], dtype=np.dtype(record['dtype'])).copy().reshape(tuple(record['shape']))


def parameter_records(value, np):
    records = []
    for path, leaf in fixed_policy.parameter_tree_items(value):
        array, descriptor = array_descriptor(leaf, np, role='parameters', path=path)
        records.append({'path': list(path), 'shape': descriptor['shape'], 'dtype': descriptor['dtype'],
                        'raw': array.tobytes(order='C')})
    fixed_policy.validate_parameter_records(records)
    return records


def encode_parameter_records(records, structure):
    """Production parameter serializer; also callable with engineering byte fixtures."""
    fixed_policy.validate_parameter_records(records)
    require(type(structure) is str and len(structure.encode()) <= MAX_STRUCTURE_BYTES, 'bounded parameter structure')
    encoded = [{'shape': row['shape'], 'dtype': row['dtype'], 'nbytes': len(row['raw']),
                'sha256': hashlib.sha256(row['raw']).hexdigest(),
                'data_base64': base64.b64encode(row['raw']).decode('ascii')} for row in records]
    require(sum(row['nbytes'] for row in encoded) <= MAX_RAW_BYTES, 'aggregate parameter raw-byte bound')
    return {'structure': structure, 'leaves': encoded}


def decode_parameter_records(packet, expected_structure):
    """No serialized classes, paths, selectors or policies can extend the fixed role."""
    require(type(packet) is dict and set(packet) == {'structure', 'leaves'}, 'exact parameter tree schema')
    require(type(expected_structure) is str and type(packet['structure']) is str and
            len(expected_structure.encode()) <= MAX_STRUCTURE_BYTES and packet['structure'] == expected_structure,
            'same trusted parameter template tree')
    require(type(packet['leaves']) is list and len(packet['leaves']) == 15, 'exact parameter leaf count')
    records = [_decode_leaf_record(row, role='parameters', path=path)
               for row, path in zip(packet['leaves'], fixed_policy.PARAMETER_PATHS)]
    fixed_policy.validate_parameter_records(records)
    require(sum(len(row['raw']) for row in records) <= MAX_RAW_BYTES, 'aggregate decoded parameter bound')
    return records


def _tree_paths(value, tree_util):
    pairs, definition = tree_util.tree_flatten_with_path(value)
    paths = []
    for keys, leaf in pairs:
        path = []
        for key in keys:
            if hasattr(key, 'idx'):
                item = key.idx
            elif hasattr(key, 'key'):
                item = key.key
            elif hasattr(key, 'name'):
                item = key.name
            else:
                item = 'opaque_key'
            path.append(item if type(item) in (int, str) else 'opaque_key')
        paths.append((tuple(path), leaf))
    return paths, definition


def encode_tree(value, np, tree_util, *, role='finite'):
    leaves, treedef = tree_util.tree_flatten(value)
    require(0 < len(leaves) <= MAX_LEAVES, 'bounded nonempty context tree')
    structure = str(treedef)
    require(len(structure.encode()) <= MAX_STRUCTURE_BYTES, 'bounded context structure')
    if role == 'parameters':
        return encode_parameter_records(parameter_records(value, np), structure)
    paths, same_definition = _tree_paths(value, tree_util)
    require(same_definition == treedef and len(paths) == len(leaves), 'same context paths')
    encoded = [encode_array(x, np, role=role, path=path) for path, x in paths]
    require(sum(x['nbytes'] for x in encoded) <= MAX_RAW_BYTES, 'aggregate context raw-byte bound')
    return {'structure': structure, 'leaves': encoded}


def decode_tree_like(packet, template, np, jnp, tree_util, *, role='finite'):
    """The trusted caller supplies the real template; serialized types never execute."""
    require(type(packet) is dict and set(packet) == {'structure', 'leaves'}, 'exact context tree schema')
    template_leaves, treedef = tree_util.tree_flatten(template)
    require(type(packet['structure']) is str and len(packet['structure'].encode()) <= MAX_STRUCTURE_BYTES and
            packet['structure'] == str(treedef), 'same trusted template tree')
    leaves = packet['leaves']
    require(type(leaves) is list and 0 < len(leaves) == len(template_leaves) <= MAX_LEAVES,
            'exact context leaf count')
    if role == 'parameters':
        fixed_policy.parameter_tree_items(template)
        records = decode_parameter_records(packet, str(treedef))
    else:
        paths, same_definition = _tree_paths(template, tree_util)
        require(same_definition == treedef, 'same decoded context paths')
        records = [_decode_leaf_record(row, role=role, path=path)
                   for row, (path, _) in zip(leaves, paths)]
    decoded = []
    extent = 0
    for row, expected in zip(records, template_leaves):
        array = np.frombuffer(row['raw'], dtype=np.dtype(row['dtype'])).copy().reshape(tuple(row['shape']))
        expected = np.asarray(expected)
        require(array.shape == expected.shape and array.dtype == expected.dtype,
                'context leaf matches trusted template')
        extent += array.nbytes
        require(extent <= MAX_RAW_BYTES, 'aggregate decoded context bound')
        decoded.append(jnp.asarray(array))
    return tree_util.tree_unflatten(treedef, decoded)


def tree_witness(value, np, tree_util):
    """Validate explicit roles, preserving the exact old tree_digest preimage."""
    require(type(value) is tuple and len(value) == 3, 'parameter/model/optimizer context triple')
    parameters, model_states, optimizer_states = value
    fixed_policy.validate_parameter_records(parameter_records(parameters, np))
    selected = [('parameters', path, leaf) for path, leaf in fixed_policy.parameter_tree_items(parameters)]
    for role, part in (('model_state', model_states), ('optimizer_state', optimizer_states)):
        pairs, _ = _tree_paths(part, tree_util)
        selected.extend((role, path, leaf) for path, leaf in pairs)
    leaves, treedef = tree_util.tree_flatten(value)
    require(0 < len(leaves) == len(selected) <= MAX_LEAVES, 'bounded initial-state witness')
    require(all(left is right for left, (_, _, right) in zip(leaves, selected)), 'same ordered context leaf objects')
    structure = str(treedef)
    require(len(structure.encode()) <= MAX_STRUCTURE_BYTES, 'bounded initial-state structure')
    return {'structure': structure,
            'leaves': [array_descriptor(leaf, np, role=role, path=path)[1] for role, path, leaf in selected]}


def witness_digest(witness):
    require(type(witness) is dict and set(witness) == {'structure', 'leaves'}, 'exact witness schema')
    require(type(witness['structure']) is str and len(witness['structure'].encode()) <= MAX_STRUCTURE_BYTES,
            'bounded witness structure')
    require(type(witness['leaves']) is list and 0 < len(witness['leaves']) <= MAX_LEAVES,
            'bounded witness leaves')
    for row in witness['leaves']:
        require(type(row) is dict and set(row) == {'shape', 'dtype', 'sha256'}, 'exact witness leaf schema')
        require(type(row['shape']) is list and len(row['shape']) <= 4 and
                all(type(x) is int and x >= 0 for x in row['shape']) and row['dtype'] in DTYPES,
                'plain witness signature')
        digest = row['sha256']
        require(type(digest) is str and len(digest) == 64 and all(c in '0123456789abcdef' for c in digest),
                'witness digest syntax')
    return hashlib.sha256(canonical(witness)).hexdigest()


def bind_context_to_witness(witness, parameters, optimizer_states):
    """Old tree is (opt, model_states, optimizer_states): prefix/suffix are exact."""
    witness_digest(witness)
    def descriptors(packet):
        require(type(packet) is dict and set(packet) == {'structure', 'leaves'} and
                type(packet['leaves']) is list, 'context packet schema')
        return [{k: row[k] for k in ('shape', 'dtype', 'sha256')} for row in packet['leaves']]
    left, right = descriptors(parameters), descriptors(optimizer_states)
    require(len(left) == 15 and 0 < len(right) <= MAX_LEAVES, 'exact parameter prefix and optimizer suffix')
    leaves = witness['leaves']
    require(len(leaves) > len(left) + len(right) and leaves[:len(left)] == left and leaves[-len(right):] == right,
            'context values bound to complete initial-state commitment')
    return True


def bounded_json(value, cap):
    encoded = bytearray()
    for chunk in json.JSONEncoder(sort_keys=True, separators=(',', ':'), allow_nan=False).iterencode(value):
        raw = chunk.encode()
        require(len(encoded) + len(raw) + 1 <= cap, 'bounded packet serialization')
        encoded.extend(raw)
    encoded.extend(b'\n')
    return bytes(encoded)


def publish(root, name, value, caps):
    require(name in caps and '/' not in name, 'fixed output publication')
    raw = bounded_json(value, caps[name])
    root = Path(root)
    require(root.is_dir() and not root.is_symlink(), 'ordinary output root')
    final, temporary = root/name, root/('.'+name+'.part')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'wb') as stream:
            require(stream.write(raw) == len(raw), 'complete packet write')
            stream.flush()
            os.fchmod(stream.fileno(), 0o444)
            os.fsync(stream.fileno())
        os.link(temporary, final, follow_symlinks=False)
        temporary.unlink()
        directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if temporary.exists():
            temporary.unlink()
    return {'filename': name, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
            'complete': True, 'container_fsynced': True, 'host_export_confirmed': False}
