"""Fixed NEURAL-004 reference specifications; no numerical imports."""
import hashlib
import json
import math

LAMBDAS = (0.0001, 0.01, 1.0, 100.0)
BANDWIDTHS = (0.05, 0.1, 0.2, 0.4, 0.8, 1.6)
FAMILIES = ('B', 'G', 'C', 'GC')
SCHEMA = 'neural004_reference_state_v1'

class Refusal(ValueError):
    def __init__(self, code, record=None):
        super().__init__(code)
        self.code = code
        self.record = {} if record is None else record


def require(condition, code):
    if not condition:
        raise Refusal(code)


def candidate_specs():
    result = [{'id': 'B-mean', 'kind': 'mean', 'family': 'B'}]
    result += [{'id': f'B-ridge-{v:g}', 'kind': 'ridge', 'family': 'B', 'lambda': v} for v in LAMBDAS]
    result += [{'id': f'B-kernel-{v:g}', 'kind': 'kernel', 'family': 'B', 'bandwidth': v} for v in BANDWIDTHS]
    for f in ('G', 'C', 'GC'):
        result += [{'id': f'{f}-ridge-{v:g}', 'kind': 'ridge', 'family': f, 'lambda': v} for v in LAMBDAS]
    return tuple(result)


def specification(identifier):
    for row in candidate_specs():
        if row['id'] == identifier:
            return row
    raise Refusal('unknown_candidate')


def safe_metadata(value, depth=0):
    require(depth <= 20, 'metadata_depth')
    if value is None or type(value) in (bool, str):
        if type(value) is str:
            require(len(value) <= 4096, 'metadata_string')
        return
    if type(value) is int:
        require(abs(value) <= 2**53, 'metadata_integer')
        return
    if type(value) is float:
        require(math.isfinite(value), 'metadata_nonfinite')
        return
    if type(value) is list:
        require(len(value) <= 1000000, 'metadata_list')
        for item in value:
            safe_metadata(item, depth + 1)
        return
    require(type(value) is dict and len(value) <= 4096, 'metadata_type')
    for key, item in value.items():
        require(type(key) is str and len(key) <= 256, 'metadata_key')
        safe_metadata(item, depth + 1)


def canonical(value):
    safe_metadata(value)
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def pin(value):
    body = canonical(value)
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def identity(value, code='identity'):
    require(type(value) is str and 0 < len(value) <= 256, code)
    return value


def ids(values, n, unique=True):
    require(type(values) in (list, tuple) and len(values) == n, 'identity_shape')
    out = [identity(v) for v in values]
    require(not unique or len(set(out)) == n, 'duplicate_identity')
    return out


def feature_order(family, channel_order):
    require(family in FAMILIES, 'feature_family')
    channels = ids(channel_order, 32)
    b = ['intercept', 'instruction', 'log_rt', 'instruction*log_rt', 'log_rt^2', 'instruction*log_rt^2']
    b += [f'rt_rbf:{j}' for j in range(32)]
    b += [f'instruction*rt_rbf:{j}' for j in range(32)]
    g = [f'G:{c}:{j}:{stat}' for c in channels for j in range(8) for stat in ('mean', 'population_sd')]
    c = [f'C:{channels[i]}:{channels[j]}' for i in range(32) for j in range(i, 32)]
    if family == 'B':
        return b
    neural = g if family == 'G' else c if family == 'C' else g + c
    return b + neural + ['instruction*' + x for x in neural]
