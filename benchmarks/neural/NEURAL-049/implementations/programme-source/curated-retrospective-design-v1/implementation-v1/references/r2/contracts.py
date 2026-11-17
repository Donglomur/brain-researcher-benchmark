"""Independent strict primitive admission; no original-data readers."""
from .budget import require

T = 5000
VIEWS = ('C', 'N', 'NC', 'NC_D')
ENDPOINTS = ('angle', 'magnitude', 'speed')


def environment_check(env, *, numerical=False, tensor=False):
    import re
    fields = {'qualified', 'receipt', 'numpy_version', 'torch_version', 'device',
              'shared_monotonic_domain', 'deterministic_algorithms', 'native_workspace_bytes'}
    require(type(env) is dict and set(env) == fields and env['qualified'] is True
            and env['shared_monotonic_domain'] is True and env['deterministic_algorithms'] is True,
            'independently qualified environment transport required')
    require(type(env['receipt']) is str and re.fullmatch('[0-9a-f]{64}', env['receipt']) is not None,
            'environment receipt identity')
    require(type(env['native_workspace_bytes']) is int and env['native_workspace_bytes'] >= 0
            and env['device'] in ('cpu', 'cuda')
            and type(env['numpy_version']) is str and type(env['torch_version']) is str,
            'environment primitive schema')
    if numerical:
        require(numpy().__version__ == env['numpy_version'], 'NumPy version mismatch')
    if tensor:
        import torch
        require(torch.__version__ == env['torch_version'], 'Torch version mismatch')


def numpy():
    import numpy as np
    return np


def ordinary_ids(ids, name):
    require(type(ids) is list and all(type(x) is str and 0 < len(x) <= 256 for x in ids)
            and len(ids) == len(set(ids)), name + ' ordered unique ids')


def array(a, dtype, shape, budget, name):
    np = numpy()
    require(type(a) is np.ndarray and a.dtype == np.dtype(dtype) and a.shape == tuple(shape)
            and a.flags.c_contiguous, name + ' exact primitive array')
    budget.ops(max(1, a.size), name + ' validation')
    budget.arrays(max(1, a.size), name + ' finite-check temporary', live=a.nbytes * 3 + max(1, a.size))
    require(bool(np.isfinite(a).all()), name + ' finite')


def scope_check(scope):
    require(type(scope) is dict, 'scope object')
    for k in ('person', 'endpoint', 'view', 'base_generation', 'training_days', 'training_ids', 'input_identity', 'source_identity', 'environment', 'axis'):
        require(k in scope, 'missing scope ' + k)
    require(scope['person'] in tuple('%02d' % k for k in range(1, 13)), 'person')
    require(scope['endpoint'] in ENDPOINTS and scope['view'] in VIEWS, 'endpoint/view')
    require(type(scope['base_generation']) is str and bool(scope['base_generation']), 'base generation')
    days = scope['training_days']
    require(type(days) is list and bool(days) and all(type(d) is int and d > 0 for d in days)
            and days == sorted(set(days)), 'ordered training days')
    ordinary_ids(scope['training_ids'], 'training')
    require(scope.get('task') == 'NEURAL-049' and scope.get('implementation') == 'R2', 'task/implementation')
    require(type(scope['input_identity']) is dict and bool(scope['input_identity']) and
            type(scope['source_identity']) is dict and bool(scope['source_identity']), 'input/source identities')
    environment_check(scope['environment'])
    ordinary_ids(scope['axis'], 'scope channel')


def batch_check(batch, view, budget):
    require(type(batch) is dict and batch.get('schema') == 'neural049_numeric_batch_v1', 'batch schema')
    ordinary_ids(batch.get('ids'), 'event')
    ordinary_ids(batch.get('axis'), 'channel')
    n, c = len(batch['ids']), len(batch['axis'])
    require(c > 0 and view in VIEWS, 'full nonempty axis/view')
    shape = (n, c, T)
    budget.workspace(n * c * T * 32 + n * (6 + 165*c) * 64 + 4096, 'complete batch admission')
    array(batch.get('mask'), 'bool', shape, budget, 'mask')
    array(batch.get('offsets'), 'float64', (n,), budget, 'offsets')
    np = numpy()
    require(bool(((batch['offsets'] >= 0) & (batch['offsets'] < .002)).all()), 'fractional offsets')
    if view == 'C':
        require(batch.get('x') is None, 'C must receive no waveform body')
    else:
        array(batch.get('x'), 'float64', shape, budget, 'x')
        budget.arrays(n*c*T*10, 'masked neutrality check', live=n*c*T*32+4096)
        require(bool((batch['x'][~batch['mask']] == 0).all()), 'masked values must be neutral zero')
    if view == 'N':
        require(batch.get('context') is None, 'N must receive no timing body')
    else:
        array(batch.get('context'), 'float64', (n, 6), budget, 'context')
    return n, c


def labels_check(labels, n, endpoint, budget):
    array(labels, 'float64', (n,), budget, 'training labels')
    if endpoint == 'angle':
        require(bool(((labels >= -90) & (labels <= 90)).all()), 'angle label domain')
    else:
        require(bool((labels >= 0).all()), 'nonnegative label domain')


def project(raw, endpoint, budget):
    np = numpy()
    require(endpoint in ENDPOINTS and bool(np.isfinite(raw).all()), 'finite raw values before projection')
    budget.arrays(raw.nbytes, 'physical-domain projection', live=raw.nbytes * 4 + 4096)
    result = np.clip(raw, -90, 90) if endpoint == 'angle' else np.maximum(raw, 0)
    budget.tick('projection completed')
    return result
