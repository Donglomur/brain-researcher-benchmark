"""One source-qualified extended-real raw parameter; all other values stay finite.

This public module has no saved-result references or expected initial-context digest.
The pure byte predicates below are used by the real codec and trusted comparator.
"""
import hashlib
import json
import math
import struct

BOUNDARY_PATH = (2, 0, 'Na_gNa')
BOUNDARY_RAW = bytes.fromhex('000000000000f0ff')
CHANNELS = ('Na_gNa', 'K_gK', 'Leak_gLeak', 'KA_gKA', 'Ca_gCa', 'KCa_gKCa')
PARAMETER_PATHS = tuple((group, index, key) for group, names in enumerate(
    (('w_bc_to_rgc', 'axial_resistivity', 'radius'), CHANNELS, CHANNELS))
    for index, key in enumerate(names))
PARAMETER_SHAPES = ((287,), (154,), (154,)) + ((),) * 12
MAX_RAW_BYTES = 262144
DTYPE_FORMATS = {'<f8': 'd', '<f4': 'f', '<i8': 'q', '<i4': 'i', '<u8': 'Q',
                 '<u4': 'I', '|b1': '?', '|i1': 'b', '|u1': 'B', '<i2': 'h', '<u2': 'H'}
ROLES = ('parameters', 'model_state', 'optimizer_state', 'finite', 'computed')
POLICY = {'schema': 'jaxley-fixed-somatic-sodium-boundary-latent-policy-v2',
 'selector': {'role': 'parameters',
              'path': [2, 0, 'Na_gNa'],
              'shape': [],
              'dtype': '<f8',
              'required_raw_hex': '000000000000f0ff',
              'value_class': 'negative_infinity'},
 'parameter_layout': [{'path': [0, 0, 'w_bc_to_rgc'], 'shape': [287], 'dtype': '<f8'},
                      {'path': [0, 1, 'axial_resistivity'], 'shape': [154], 'dtype': '<f8'},
                      {'path': [0, 2, 'radius'], 'shape': [154], 'dtype': '<f8'},
                      {'path': [1, 0, 'Na_gNa'], 'shape': [], 'dtype': '<f8'},
                      {'path': [1, 1, 'K_gK'], 'shape': [], 'dtype': '<f8'},
                      {'path': [1, 2, 'Leak_gLeak'], 'shape': [], 'dtype': '<f8'},
                      {'path': [1, 3, 'KA_gKA'], 'shape': [], 'dtype': '<f8'},
                      {'path': [1, 4, 'Ca_gCa'], 'shape': [], 'dtype': '<f8'},
                      {'path': [1, 5, 'KCa_gKCa'], 'shape': [], 'dtype': '<f8'},
                      {'path': [2, 0, 'Na_gNa'], 'shape': [], 'dtype': '<f8'},
                      {'path': [2, 1, 'K_gK'], 'shape': [], 'dtype': '<f8'},
                      {'path': [2, 2, 'Leak_gLeak'], 'shape': [], 'dtype': '<f8'},
                      {'path': [2, 3, 'KA_gKA'], 'shape': [], 'dtype': '<f8'},
                      {'path': [2, 4, 'Ca_gCa'], 'shape': [], 'dtype': '<f8'},
                      {'path': [2, 5, 'KCa_gKCa'], 'shape': [], 'dtype': '<f8'}],
 'other_values': 'All other raw parameters, model state, optimizer state and computed quantities '
                 'must be finite.',
 'resulting_parameter_equality': {'boundary': 'exact required raw bytes in both operands',
                                  'finite_rtol': 3e-08,
                                  'finite_scale_atol': 3e-12,
                                  'finite_metric': 'unchanged frozen float_leaf_metrics'},
 'commitment': 'Original treedef, ordered shape/dtype/raw-byte hashes and canonical digest '
               'preimage are unchanged.',
 'physical_transform': 'Unchanged qualified forward gives 0.05+(0.5-0.05)/(1+exp(20.0)); trusted '
                       'comparator requires finite values.',
 'numerical_math': 'Initializer, inverse/forward transform, model, normalization and optimizer '
                   'arithmetic are unchanged.',
 'scope': 'Versioned raw-parameter representation and equality only; no full256 execution or '
          'old-policy PASS.',
 'source_pins': {'model_operation.py': 'c74030ec288d451eb29c4b1febd5664896c508471df3dcefcaebe992c9934460',
                 'author_transforms.py': '959b842e4df8756eea738004b7abcf68cd193acc3ab3c876d7284565ef9f04c0',
                 'Jaxley-0.4.0-py3-none-any.whl': '4b4a1634b89b6db9f895bf1cdfe877faf1d2817aef23fea1558563e710aece99',
                 'jaxley/optimize/transforms.py': '68b61479ef4bb487e0797266a824c08c2fdcea3e8a91916bdfbe4ce2ee52c714',
                 'jaxley/solver_gate.py': '5d6c930824cb05b892adc2924b95f5b4428aeafa586f10c415eb9401b11c33de'}}
POLICY_BYTES = (json.dumps(POLICY, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()
POLICY_SHA256 = hashlib.sha256(POLICY_BYTES).hexdigest()


def _safe_path(path):
    if type(path) not in (tuple, list):
        return ['invalid_path']
    return [x if type(x) is int and -1000000 <= x <= 1000000 else
            x[:64] if type(x) is str else 'unsupported_key' for x in path[:8]]


class BoundaryViolation(ValueError):
    def __init__(self, role, path, shape, dtype, category):
        self.diagnostic = {'schema': 'jaxley-bounded-context-offender-v2',
                           'role': role[:24] if type(role) is str else 'invalid_role',
                           'path': _safe_path(path),
                           'shape': [x if type(x) is int and 0 <= x <= MAX_RAW_BYTES else -1
                                     for x in shape[:4]] if type(shape) is list else [],
                           'dtype': dtype[:16] if type(dtype) is str else 'invalid_dtype',
                           'category': category}
        super().__init__('context policy refusal: ' + json.dumps(self.diagnostic, sort_keys=True, separators=(',', ':')))


def _require(ok, role, path, shape, dtype, category):
    if not ok:
        raise BoundaryViolation(role, path, shape, dtype, category)


def validate_leaf_bytes(role, path, shape, dtype, raw):
    """No caller-controlled allowlist; the one parameter coordinate is mandatory."""
    fail = lambda ok, reason: _require(ok, role, path, shape, dtype, reason)
    fail(type(role) is str and role in ROLES, 'role')
    fail(type(path) in (tuple, list) and len(path) <= 32 and
         all(type(x) in (int, str) for x in path), 'path')
    fail(type(shape) is list and len(shape) <= 4 and
         all(type(x) is int and 0 <= x <= MAX_RAW_BYTES for x in shape), 'shape')
    fail(type(dtype) is str and dtype in DTYPE_FORMATS, 'dtype')
    fail(type(raw) is bytes and len(raw) <= MAX_RAW_BYTES, 'raw_extent')
    fail(math.prod(shape) * struct.calcsize('<' + DTYPE_FORMATS[dtype]) == len(raw), 'shape_extent')
    if role == 'parameters' and tuple(path) == BOUNDARY_PATH:
        fail(shape == [] and dtype == '<f8', 'fixed_coordinate_type')
        if raw != BOUNDARY_RAW:
            value = struct.unpack('<d', raw)[0]
            kind = ('nan' if math.isnan(value) else 'positive_infinity' if value == math.inf
                    else 'finite_replacement' if math.isfinite(value) else 'noncanonical_negative_infinity')
            fail(False, 'fixed_coordinate_' + kind)
        return {'criterion': 'fixed_boundary_raw_identity', 'finite': False}
    if dtype in ('<f4', '<f8'):
        for (value,) in struct.iter_unpack('<' + DTYPE_FORMATS[dtype], raw):
            if not math.isfinite(value):
                kind = 'nan' if math.isnan(value) else 'positive_infinity' if value > 0 else 'negative_infinity'
                fail(False, kind)
    return {'criterion': 'finite_values', 'finite': True}


def parameter_tree_items(tree):
    """Source structure is a tuple of three lists of single-key dictionaries."""
    _require(type(tree) is tuple and len(tree) == 3, 'parameters', [], [], '<f8', 'parameter_outer_structure')
    for group, count in enumerate((3, 6, 6)):
        _require(type(tree[group]) is list and len(tree[group]) == count,
                 'parameters', [group], [], '<f8', 'parameter_group_structure')
    result = []
    for path in PARAMETER_PATHS:
        group, index, name = path
        item = tree[group][index]
        _require(type(item) is dict and set(item) == {name}, 'parameters', path, [], '<f8', 'parameter_key')
        result.append((path, item[name]))
    return result


def validate_parameter_records(records):
    _require(type(records) is list and len(records) == 15, 'parameters', [], [], '<f8', 'parameter_record_count')
    for record, path, shape in zip(records, PARAMETER_PATHS, PARAMETER_SHAPES):
        _require(type(record) is dict and set(record) == {'path', 'shape', 'dtype', 'raw'},
                 'parameters', path, list(shape), '<f8', 'parameter_record_schema')
        _require(type(record['path']) is list and record['path'] == list(path) and
                 all(type(x) is type(y) for x, y in zip(record['path'], path)),
                 'parameters', path, list(shape), '<f8', 'parameter_record_path')
        _require(record['shape'] == list(shape) and record['dtype'] == '<f8',
                 'parameters', path, record['shape'], record['dtype'], 'parameter_record_type')
        validate_leaf_bytes('parameters', path, record['shape'], record['dtype'], record['raw'])
    return True


def compare_parameter_records(reference, streamed, float_leaf_metrics, rtol=3e-8, scale_atol=3e-12):
    """The caller supplies the authenticated frozen metric, not a replacement."""
    _require(type(rtol) is float and type(scale_atol) is float and rtol == 3e-8 and scale_atol == 3e-12,
             'parameters', [], [], '<f8', 'frozen_parameter_tolerances')
    validate_parameter_records(reference)
    validate_parameter_records(streamed)
    reports = []
    for index, (left, right, path) in enumerate(zip(reference, streamed, PARAMETER_PATHS)):
        a, b = left['raw'], right['raw']
        if path == BOUNDARY_PATH:
            metrics = {'passed': a == b == BOUNDARY_RAW, 'criterion': 'fixed_boundary_raw_identity',
                       'extended_real_coordinate': True, 'element_count': 1}
        else:
            av = [x[0] for x in struct.iter_unpack('<d', a)]
            bv = [x[0] for x in struct.iter_unpack('<d', b)]
            metrics = float_leaf_metrics(av, bv, rtol, scale_atol)
        descriptor = lambda row: {'shape': row['shape'], 'dtype': row['dtype'],
                                  'sha256': hashlib.sha256(row['raw']).hexdigest()}
        reports.append({'leaf': index, 'path': list(path), 'reference': descriptor(left),
                        'streamed': descriptor(right), 'byte_equal': a == b, **metrics})
    return {'passed': all(row['passed'] for row in reports), 'leaves': reports,
            'fixed_coordinate_policy_sha256': POLICY_SHA256}
