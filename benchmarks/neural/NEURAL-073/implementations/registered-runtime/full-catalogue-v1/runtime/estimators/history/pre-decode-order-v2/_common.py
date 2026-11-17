"""Explicit numerical budgets and safe immutable estimator state primitives.

No import-time NumPy import, source discovery, I/O or fitting. Logical byte/work
counters are conservative source-level accounting, not native scratch/RSS claims.
"""
from dataclasses import dataclass, field
import base64
import hashlib
import json
import math
import re
import time


class EstimatorError(ValueError):
    def __init__(self, code, details=None):
        super().__init__(code)
        self.code = code
        self.details = {} if details is None else details


@dataclass
class NumericBudget:
    max_bytes: int
    max_work: int
    deadline: float
    allocated_bytes: int = 0
    work_units: int = 0
    counters: dict = field(default_factory=dict)

    def __post_init__(self):
        if (type(self.max_bytes) is not int or self.max_bytes <= 0 or
                type(self.max_work) is not int or self.max_work <= 0 or
                not math.isfinite(self.deadline)):
            raise EstimatorError('invalid_budget')

    def tick(self, kind, count=1):
        if type(count) is not int or count < 0:
            raise EstimatorError('invalid_work_count')
        if time.monotonic() > self.deadline:
            raise EstimatorError('deadline_exceeded', self.snapshot())
        if self.work_units + count > self.max_work:
            raise EstimatorError('work_budget_exceeded', self.snapshot())
        self.work_units += count
        self.counters[kind] = self.counters.get(kind, 0) + count

    def charge(self, count, role):
        if type(count) is not int or count < 0:
            raise EstimatorError('invalid_byte_count')
        self.tick('allocation_events')
        if self.allocated_bytes + count > self.max_bytes:
            raise EstimatorError('byte_budget_exceeded', self.snapshot())
        self.allocated_bytes += count
        self.counters['bytes:' + role] = self.counters.get('bytes:' + role, 0) + count

    def snapshot(self):
        return {'allocated_bytes': self.allocated_bytes, 'work_units': self.work_units,
                'counters': dict(sorted(self.counters.items())),
                'meaning': 'Conservative cumulative logical allocations/work; not physical RSS, native workspace, time or full-environment qualification.'}


def numpy():
    import numpy as np
    if np.__version__ != '2.4.6':
        raise EstimatorError('numpy_version_unbound', {'observed': np.__version__})
    return np


def finite_number(value, name, positive=False):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise EstimatorError('invalid_' + name)
    value = float(value)
    if positive and value <= 0:
        raise EstimatorError('invalid_' + name)
    return value


def matrix(value, budget, name='X', columns=None):
    np = numpy()
    if type(value) is not np.ndarray or value.dtype != np.dtype('float64') or value.ndim != 2:
        raise EstimatorError('invalid_' + name + '_array')
    if not value.flags.c_contiguous or value.shape[0] <= 0 or value.shape[1] <= 0:
        raise EstimatorError('invalid_' + name + '_extent')
    if columns is not None and value.shape[1] != columns:
        raise EstimatorError('wrong_' + name + '_width')
    budget.tick('validated_scalar_values', value.size)
    # Scalar traversal avoids unaccounted full-array boolean temporaries.
    if any(not math.isfinite(float(x)) for x in value.flat):
        raise EstimatorError('nonfinite_' + name)
    return value


def training(X, y, weights, budget, classes):
    np = numpy()
    matrix(X, budget)
    n = X.shape[0]
    if type(classes) is not int or not 2 <= classes <= 25:
        raise EstimatorError('invalid_class_count')
    if type(y) not in (tuple, list) or len(y) != n or any(type(x) is not int for x in y):
        raise EstimatorError('invalid_training_labels')
    if set(y) != set(range(classes)):
        raise EstimatorError('incomplete_training_class_support')
    if (type(weights) is not np.ndarray or weights.dtype != np.dtype('float64') or
            weights.ndim != 1 or weights.shape[0] != n or not weights.flags.c_contiguous):
        raise EstimatorError('invalid_weights_array')
    if any(not math.isfinite(float(w)) or w <= 0 for w in weights):
        raise EstimatorError('nonpositive_or_nonfinite_weight')
    total = math.fsum(float(w) for w in weights)
    if abs(total - 1.0) > 1e-12:
        raise EstimatorError('weights_do_not_sum_to_one', {'total': total})
    budget.tick('validated_training_rows', n)
    return n, X.shape[1]


def empty(shape, budget, role):
    np = numpy()
    count = math.prod(shape)
    budget.charge(count * 8, role)
    return np.empty(shape, dtype=np.float64, order='C')


def context(value):
    keys = {'opaque_reference_context_token', 'condition', 'view',
            'configuration_index', 'fit_role'}
    if type(value) is not dict or set(value) != keys:
        raise EstimatorError('invalid_context_fields')
    for key in ('opaque_reference_context_token', 'fit_role'):
        if type(value[key]) is not str or re.fullmatch('[0-9a-f]{32,64}', value[key]) is None:
            raise EstimatorError('context_token_not_opaque_format')
    if value['condition'] not in ('original', 'spatial_scrambled', 'C_only'):
        raise EstimatorError('invalid_condition')
    if value['view'] not in ('N', 'C', 'NC') or (value['condition'] == 'C_only' and value['view'] != 'C'):
        raise EstimatorError('invalid_view')
    if type(value['configuration_index']) is not int or value['configuration_index'] < 0:
        raise EstimatorError('invalid_configuration_index')
    return tuple(value[k] for k in ('opaque_reference_context_token', 'condition', 'view', 'configuration_index', 'fit_role'))


def context_dict(value):
    return dict(zip(('opaque_reference_context_token', 'condition', 'view', 'configuration_index', 'fit_role'), value))


@dataclass(frozen=True)
class FrozenArray:
    shape: tuple
    body: bytes

    @classmethod
    def freeze(cls, values, budget, role):
        np = numpy()
        if type(values) is not np.ndarray or values.dtype != np.dtype('float64'):
            raise EstimatorError('invalid_state_array')
        if any(not math.isfinite(float(x)) for x in values.flat):
            raise EstimatorError('nonfinite_state_array')
        budget.charge(values.size * 8, 'frozen:' + role)
        return cls(tuple(int(x) for x in values.shape), values.astype('<f8', copy=False).tobytes(order='C'))

    def array(self):
        np = numpy()
        # Bytes backing is immutable; setflags(write=True) cannot mutate it.
        return np.frombuffer(self.body, dtype='<f8').reshape(self.shape)

    def to_dict(self, budget):
        budget.charge(8 * ((len(self.body) + 2) // 3), 'encoded_state_bytes_and_text')
        return {'shape': list(self.shape), 'dtype': '<f8',
                'sha256': hashlib.sha256(self.body).hexdigest(),
                'base64': base64.b64encode(self.body).decode('ascii')}

    @classmethod
    def from_dict(cls, value, budget, rank, max_elements):
        if type(value) is not dict or set(value) != {'shape', 'dtype', 'sha256', 'base64'}:
            raise EstimatorError('invalid_array_state_fields')
        shape = value['shape']
        if (type(shape) is not list or len(shape) != rank or
                any(type(x) is not int or x <= 0 for x in shape)):
            raise EstimatorError('invalid_array_state_shape')
        elements = math.prod(shape)
        if elements > max_elements or value['dtype'] != '<f8':
            raise EstimatorError('array_state_extent_limit')
        size = elements * 8
        text = value['base64']
        if type(text) is not str or len(text) != 4 * ((size + 2) // 3):
            raise EstimatorError('array_state_encoded_extent')
        budget.charge(size, 'decoded_state')
        try:
            body = base64.b64decode(text, validate=True)
        except (ValueError, TypeError) as exc:
            raise EstimatorError('invalid_array_state_encoding') from exc
        if len(body) != size or type(value['sha256']) is not str or hashlib.sha256(body).hexdigest() != value['sha256']:
            raise EstimatorError('array_state_digest_or_extent')
        result = cls(tuple(shape), body)
        if any(not math.isfinite(float(x)) for x in result.array().flat):
            raise EstimatorError('nonfinite_array_state')
        return result


def strict_keys(value, keys, name):
    if type(value) is not dict or set(value) != set(keys):
        raise EstimatorError('invalid_' + name + '_fields')


def production_features(X, fit_context, family, full_grid_dimension=None):
    """Necessary numeric width guard; authentic geometry binding belongs to owner."""
    ctx=context(fit_context); view=ctx[2]; d=int(X.shape[1])
    if view=='C':
        if d!=105 or full_grid_dimension is not None:
            raise EstimatorError('production_C_feature_width')
    elif family=='linear_ovr_svm':
        if type(full_grid_dimension) is not int or full_grid_dimension<256:
            raise EstimatorError('full_grid_dimension_required')
        expected=full_grid_dimension+(105 if view=='NC' else 0)
        if d!=expected:
            raise EstimatorError('production_linear_feature_width')
    elif family in ('rbf_ovr_svm','extra_trees'):
        if full_grid_dimension is not None:
            raise EstimatorError('full_grid_dimension_not_applicable_to_PCA_width')
        if d not in ((64,256) if view=='N' else (169,361)):
            raise EstimatorError('production_PCA_feature_width')
    else:
        raise EstimatorError('unsupported_production_family')
    return ctx
