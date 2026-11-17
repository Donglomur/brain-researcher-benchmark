"""Public, generic-path inference over the original non-executable frozen state.

No fitting occurs here. The verbatim numerical dependency contains the public
cohort constants, but receives no current administrative identity or private path.
Imports are inert; numerical imports occur only when a caller requests inference.
"""
import ast
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import types

CLASSES = [1, 2, 3, 4, 11, 12, 13, 14, 21, 22, 23, 24]
HANDLES = ('BP_LDA', 'TM_LDA', 'RBF_KRR', 'HISTORICAL_BP_LDA')
NUMERIC_BYTES = 38757
NUMERIC_SHA256 = '64d74293bde8b6f595ecee37de8592d5c703e969a240cedf3d4a7b10570f3bb5'
DEFAULT_LIMITS = {'max_array_bytes': 256*2**20, 'max_workspace_bytes': 1024*2**20,
                  'max_output_bytes': 256*2**20}
MODEL_KEYS = ('schema', 'handle', 'family', 'configuration', 'class_ids',
              'feature_definition', 'scaler', 'parameters', 'calibration',
              'training_row_tokens_or_null', 'strongest_family',
              'uniform_probabilities', 'laplace_probabilities')


def _need(ok, message):
    if not ok: raise ValueError(message)


def _exact(value, keys):
    _need(type(value) is dict and set(value) == set(keys), 'exact public schema')


def _int(value, low=0, high=2**63-1):
    _need(type(value) is int and low <= value <= high, 'bounded nonboolean integer')
    return value


def _number(value):
    _need(type(value) in (int, float) and math.isfinite(value), 'finite public number')
    return float(value)


def _hex(value, size):
    _need(type(value) is str and len(value) == size and all(c in '0123456789abcdef' for c in value), 'exact opaque hex value')
    return value


def _parse(raw):
    def pairs(rows):
        result = {}
        for key, value in rows:
            _need(key not in result, 'duplicate public JSON key'); result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: _need(False, 'finite public JSON'))


def _limits(limits):
    limits = dict(DEFAULT_LIMITS) if limits is None else limits
    _exact(limits, DEFAULT_LIMITS)
    for value in limits.values(): _int(value, 1)
    return limits


def _metadata_bound(meta):
    tokens = meta['training_row_tokens_or_null']
    return 16384 + (256*len(tokens) if tokens is not None else 0)


def configurations():
    """The finite written recipe roster; no numerical import or fitting."""
    rows = []
    for family in HANDLES[:2]:
        for i, shrinkage in enumerate((0.01, 0.1, 0.5, 'AUTO')):
            rows.append(dict(id=family+'_'+str(i), family=family, shrinkage=shrinkage, alpha=None, gamma=None))
    for i, (alpha, gamma) in enumerate((a, g) for a in (0.01, 0.1, 1.0, 10.0)
                                     for g in (1.0/1280.0, 1.0/320.0, 4.0/320.0)):
        rows.append(dict(id='RBF_KRR_'+str(i), family='RBF_KRR', shrinkage=None, alpha=alpha, gamma=gamma))
    rows.append(dict(id='HISTORICAL_BP_LDA', family='HISTORICAL_BP_LDA', shrinkage='AUTO', alpha=None, gamma=None))
    return rows


def parameter_shapes(handle, n):
    _need(handle in HANDLES, 'fixed public model handle')
    d = 1024 if handle == 'TM_LDA' else 320
    return ({'training_z': [n, d], 'dual': [n, 12], 'row_kernel_mean': [n],
             'grand_kernel_mean': [], 'class_mean': [12]} if handle == 'RBF_KRR'
            else {'coefficients': [d, 12], 'intercepts': [12]})


def _same(a, b):
    if type(a) is not type(b): return False
    if type(a) is dict: return a.keys() == b.keys() and all(_same(a[k], b[k]) for k in a)
    if type(a) is list: return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    return a == b


def validate_model(meta, handle):
    """Validate only sanitized JSON metadata; never open any array body."""
    _exact(meta, MODEL_KEYS)
    _need(handle in HANDLES and meta['schema'] == 'neural081_candidate_model_v2'
          and meta['handle'] == meta['family'] == handle, 'exact public model identity')
    _need(_same(meta['class_ids'], CLASSES), 'canonical class axis')
    _need(any(_same(meta['configuration'], row) for row in configurations() if row['family'] == handle), 'actual fixed recipe')
    _need(meta['feature_definition'] == ('TM' if handle == 'TM_LDA' else 'BP'), 'fixed full feature definition')
    tokens = meta['training_row_tokens_or_null']
    if handle == 'RBF_KRR':
        _need(type(tokens) is list, 'complete fixed model row tokens')
        n = _int(len(tokens), 108, 90000)
        for token in tokens: _hex(token, 32)
        _need(tokens == sorted(tokens) and len(set(tokens)) == n, 'unique fixed role-order tokens')
    else:
        _need(tokens is None, 'LDA has no row-indexed state')
        # LDA prediction does not depend on n_train. The public schema omits it;
        # 12 is solely the pure predictor ABI minimum, not a fitted support count.
        n = 12
    d = 1024 if handle == 'TM_LDA' else 320
    shapes = {'scaler_mean': [d], 'scaler_scale': [d], **parameter_shapes(handle, n)}
    _exact(meta['scaler'], ('scaler_mean', 'scaler_scale'))
    _exact(meta['parameters'], parameter_shapes(handle, n))
    total = 0
    for name, desc in {**meta['scaler'], **meta['parameters']}.items():
        _exact(desc, ('relative_path', 'dtype', 'shape', 'bytes', 'sha256'))
        _need(desc['relative_path'] == name+'.npy' and desc['dtype'] == 'float64'
              and _same(desc['shape'], shapes[name]), 'fixed non-executable state descriptor')
        size = 8
        for extent in shapes[name]: size *= _int(extent, 1)
        _int(desc['bytes'], size+10, size+65548); _hex(desc['sha256'], 64); total += size
    _exact(meta['calibration'], ('temperature',))
    t = _number(meta['calibration']['temperature'])
    _need(t in (1., .25, 4., .0625, 16., .015625, 64.) and (handle != 'HISTORICAL_BP_LDA' or t == 1.), 'selected positive calibration')
    _need(meta['strongest_family'] in HANDLES[:3], 'training-selected strongest family')
    for key in ('uniform_probabilities', 'laplace_probabilities'):
        values = meta[key]; _need(type(values) is list and len(values) == 12, 'complete legitimate prior')
        _need(all(0 < _number(v) <= 1 for v in values) and abs(math.fsum(values)-1.) <= 1e-12, 'normalized positive training prior')
    _need(all(v == 1./12. for v in meta['uniform_probabilities']), 'exact uniform prior')
    return n, d, total


def _capture(path, maximum, descriptor=None):
    """One stable ordinary complete generic-path body, bounded before reading."""
    p = Path(path)
    _need(str(p) == path and path.startswith(('/models/', '/tools/'))
          and not any(x in ('', '.', '..') for x in path.split('/')[1:])
          and not any(q.is_symlink() for q in (p, *p.parents)), 'ordinary generic input path')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        _need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= maximum, 'bounded complete ordinary input')
        if descriptor is not None: _need(before.st_size == descriptor['bytes'], 'exact sealed input extent')
        with os.fdopen(fd, 'rb', closefd=False) as stream: raw = stream.read(before.st_size+1)
        after = os.fstat(fd); named = p.lstat()
        fields = ('st_dev', 'st_ino', 'st_size', 'st_mode', 'st_nlink', 'st_mtime_ns', 'st_ctime_ns')
        _need(len(raw) == before.st_size and all(getattr(before, k) == getattr(after, k) == getattr(named, k) for k in fields), 'stable complete input')
        if descriptor is not None: _need(hashlib.sha256(raw).hexdigest() == descriptor['sha256'], 'exact sealed input hash')
        return raw
    finally: os.close(fd)


def _npy_payload(raw, shape):
    """Admit the exact bounded header and body before any ndarray allocation."""
    _need(type(raw) is bytes and len(raw) >= 10 and raw[:6] == b'\x93NUMPY', 'one NPY body')
    version = tuple(raw[6:8]); _need(version in ((1, 0), (2, 0)), 'fixed ordinary NPY version')
    width = 2 if version == (1, 0) else 4
    start = 8+width; length = int.from_bytes(raw[8:start], 'little')
    _need(0 < length <= 65536 and start+length <= len(raw), 'bounded complete NPY header')
    header = raw[start:start+length]
    _need(header.endswith(b'\n'), 'complete NPY header terminator')
    tree = ast.parse(header.decode('ascii'), mode='eval')
    _need(isinstance(tree.body, ast.Dict) and len(tree.body.keys) == 3, 'exact nonduplicate NPY header')
    keys = [ast.literal_eval(k) for k in tree.body.keys]
    _need(len(set(keys)) == 3, 'unique NPY header fields')
    value = ast.literal_eval(tree); _exact(value, ('descr', 'fortran_order', 'shape'))
    _need(value['descr'] == '<f8' and value['fortran_order'] is False and type(value['shape']) is tuple
          and len(value['shape']) == len(shape) and all(type(x) is int and x == y for x, y in zip(value['shape'], shape)), 'exact primitive binary64 C-order shape before allocation')
    expected = 8
    for extent in shape: expected *= _int(extent, 1)
    offset = start+length
    _need(offset+expected == len(raw), 'one complete NPY payload without trailing bytes')
    return offset, expected


def _numeric():
    raw = _capture('/tools/numeric.py', NUMERIC_BYTES,
                   {'bytes': NUMERIC_BYTES, 'sha256': NUMERIC_SHA256})
    module = types.ModuleType('neural081_public_numeric')
    module.__file__ = '/tools/numeric.py'
    exec(compile(raw, '/tools/numeric.py', 'exec'), module.__dict__)
    return module


def load_model(handle, *, limits=None, n_train=None):
    """Load validated readonly numeric arrays and sanitized metadata.

    Returns {metadata, model}; model is the pure inference ABI dictionary, with
    empty diagnostics. Pass context['training']['shape'][0] as n_train to carry
    the actual public support count. If omitted for LDA only, the unused pure
    predictor ABI count is 12, explicitly not a fitted-support claim.
    """
    limits = _limits(limits); _need(handle in HANDLES, 'fixed model handle')
    raw_meta = _capture('/models/'+handle+'/model.json', min(8*2**20, limits['max_workspace_bytes']//8))
    meta = _parse(raw_meta); n, d, total = validate_model(meta, handle)
    if n_train is not None:
        _int(n_train, 108, 90000)
        _need(handle != 'RBF_KRR' or n_train == n, 'same full kernel training support')
        n = n_train
    states = {**meta['scaler'], **meta['parameters']}
    _need(total+_metadata_bound(meta) <= limits['max_output_bytes'] and 4*total+8*len(raw_meta)+262144 <= limits['max_workspace_bytes'], 'complete model decode allocation bound')
    for desc in states.values():
        size = math.prod(desc['shape'])*8
        _need(size <= limits['max_array_bytes'], 'preventive individual model allocation bound')
    import numpy as np
    model = dict(schema='neural081_numeric_model_v1', family=handle,
                 configuration=meta['configuration'], class_ids=list(CLASSES), n_train=n,
                 n_features=d, temperature=float(meta['calibration']['temperature']),
                 parameters={}, diagnostics={})
    for name, desc in states.items():
        raw = _capture('/models/'+handle+'/'+desc['relative_path'], desc['bytes'], desc)
        offset, expected = _npy_payload(raw, desc['shape'])
        a = np.frombuffer(raw, dtype='<f8', count=expected//8, offset=offset).reshape(tuple(desc['shape'])).copy(order='C')
        _need(bool(np.isfinite(a).all()), 'finite full model state')
        if name == 'scaler_scale': _need(bool((a > 0).all()), 'strictly positive scale')
        if desc['shape'] == []: a = float(a)
        else: a.setflags(write=False)
        if name.startswith('scaler_'): model[name] = a
        else: model['parameters'][name] = a
    return {'metadata': meta, 'model': model}


def features(windows, family='BP_LDA', *, limits=None):
    """Full BP/TM features for a batch of [n,64,512] permitted windows."""
    return _numeric().features(windows, family, limits=_limits(limits))


def _window_bytes(windows, limits):
    """Admit the primitive input header before allocating any model state.

    This does not scan/copy the input. Full finite-value validation remains in
    the numerical feature function, under that stage's allocation allowance.
    """
    import numpy as np
    _need(type(windows) is np.ndarray and windows.ndim == 3
          and windows.dtype in (np.dtype('float32'), np.dtype('float64'))
          and not windows.dtype.hasobject and windows.dtype.fields is None
          and windows.dtype.subdtype is None, 'exact primitive window header')
    _need(windows.shape[1:] == (64, 512) and type(windows.shape[0]) is int
          and windows.shape[0] > 0, 'complete nonempty window extent')
    size = windows.shape[0]*64*512*windows.dtype.itemsize
    _need(size == int(windows.nbytes) and size <= limits['max_array_bytes']
          and size < limits['max_workspace_bytes'], 'retained input allocation bound before model load')
    return size


def predict_scores(handle, windows, *, limits=None, n_train=None):
    """Raw twelve-class scores for a batch; no refitting or state mutation."""
    limits = _limits(limits); _need(handle in HANDLES, 'fixed model handle')
    window_bytes = _window_bytes(windows, limits)
    # The input is live throughout model decoding. The caller's limits already
    # exclude any enclosing predict_proba metadata; subtract the windows once.
    load_limits = dict(limits, max_workspace_bytes=limits['max_workspace_bytes']-window_bytes)
    loaded = load_model(handle, limits=load_limits, n_train=n_train); numeric = _numeric()
    retained = sum(v.nbytes for v in loaded['model'].values() if hasattr(v, 'nbytes'))
    retained += sum(v.nbytes for v in loaded['model']['parameters'].values() if hasattr(v, 'nbytes'))
    metadata = _metadata_bound(loaded['metadata'])
    workspace = limits['max_workspace_bytes']-retained-metadata
    _need(workspace > 0, 'features plus retained model allocation bound')
    # features accounts for its own live input, so do not subtract it twice.
    feature_limits = dict(limits, max_workspace_bytes=workspace)
    x = numeric.features(windows, handle, limits=feature_limits)
    # The caller's original windows remain live while the score kernel runs.
    score_workspace = limits['max_workspace_bytes']-window_bytes-metadata
    _need(score_workspace > 0, 'scores plus retained input/metadata allocation bound')
    return numeric.predict_scores(loaded['model'], x, limits=dict(limits, max_workspace_bytes=score_workspace))


def predict_proba(handle, windows, *, limits=None, n_train=None):
    """Selected-temperature probabilities in the canonical twelve-class order."""
    limits = _limits(limits); _need(handle in HANDLES, 'fixed model handle')
    window_bytes = _window_bytes(windows, limits)
    # Metadata is small, bounded, and contains no private diagnostics.
    metadata_workspace = limits['max_workspace_bytes']-window_bytes
    meta = _parse(_capture('/models/'+handle+'/model.json', min(8*2**20, metadata_workspace//8)))
    validate_model(meta, handle)
    score_workspace = limits['max_workspace_bytes']-_metadata_bound(meta)
    _need(score_workspace > 0, 'nested prediction plus public metadata allocation bound')
    scores = predict_scores(handle, windows, limits=dict(limits, max_workspace_bytes=score_workspace), n_train=n_train)
    workspace = limits['max_workspace_bytes']-window_bytes-_metadata_bound(meta)
    _need(workspace > 0, 'probabilities plus retained input/metadata allocation bound')
    return _numeric().probabilities(scores, meta['calibration']['temperature'], limits=dict(limits, max_workspace_bytes=workspace))
