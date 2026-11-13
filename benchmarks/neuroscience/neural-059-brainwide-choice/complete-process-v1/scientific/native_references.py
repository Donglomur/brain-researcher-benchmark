"""Finite N059 references. Source-only until an independently admitted native profile.

Native imports occur only after the selected concrete process capability profile and
complete package identity pass. This additive admission does not certify science.
InertRuntime runs owned NumPy arithmetic with fixed no-learning leaves; it is never a
native reference qualification. All records are JSON-friendly; native estimators stay
in their owning runtime and their serialized state is checked on each prediction.
"""
import hashlib
import importlib
import importlib.metadata
import inspect
import json
import math
from pathlib import Path
import pickle
import platform

from . import logistic
from .validation import ValidationPanel
from ..native_profile import validate_capability as _validate_capability

QUALIFICATION = 'source_only_unqualified'
CONDITIONS = ('SH', 'SHN', 'SBH', 'SBHN')
S_NAMES = ['S:-1', 'S:-0.25', 'S:-0.125', 'S:-0.0625', 'S:0', 'S:0.0625', 'S:0.125', 'S:0.25', 'S:1']
H_NAMES = ['H:unavailable', 'H:right:0', 'H:right:1', 'H:left:0', 'H:left:1', 'H:no_response:0', 'H:no_response:1']
B_NAMES = ['B:0.2', 'B:0.5', 'B:0.8']
# Original empty registry retained as ancestry, not a production-admission mechanism.
# The selected process route validates real owner/worker capability facts below.
_ADMITTED_NATIVE_PROFILES = ()
HGB_FIXED = {
    'loss': 'log_loss', 'learning_rate': .05, 'max_depth': None,
    'min_samples_leaf': 5, 'max_bins': 255, 'max_features': 1.0,
    'categorical_features': None, 'monotonic_cst': None, 'interaction_cst': None,
    'warm_start': False, 'early_stopping': False, 'scoring': 'loss',
    'validation_fraction': None, 'n_iter_no_change': 10, 'tol': 1e-7,
    'verbose': 0, 'class_weight': None,
}
TOLERANCES = {
    'objective': (5e-11, 2e-12), 'gradient': (5e-10, 2e-12),
    'logit': (5e-10, 2e-12), 'probability': (5e-12, 2e-12),
    'scaler_mean': (5e-12, 5e-12), 'scaler_scale': (0., 5e-12),
    'scaled_value': (5e-11, 5e-12),
}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                      allow_nan=False).encode('utf-8')


def _digest(value):
    return hashlib.sha256(_json(value)).hexdigest()


def reference_grid(family):
    need(family in ('L', 'H'), 'Reference family must be L or H')
    if family == 'L':
        return [{'lambda': value} for value in logistic.LAMBDAS]
    return [{'max_leaf_nodes': leaves, 'max_iter': iterations, 'l2_regularization': ridge}
            for leaves in (7, 15, 31) for iterations in (100, 300) for ridge in (1., 10.)]


def hgb_seed(session_id):
    need(type(session_id) is str and bool(session_id), 'Exact session identity')
    body = json.dumps(['N059-complete-choice-v1', session_id, 'HGB-fit'],
                      separators=(',', ':'), ensure_ascii=True).encode('utf-8')
    return int.from_bytes(hashlib.sha256(body).digest()[:4], 'big')


def _shape(shape):
    need(type(shape) is dict and set(shape) == {'session_id', 'unit_ids', 'case_ids', 'feature_names'},
         'Exact independently prepared session shape schema')
    need(type(shape['session_id']) is str and bool(shape['session_id']), 'Session identity')
    units = shape['unit_ids']
    need(type(units) is list and all(type(x) is str and bool(x) for x in units)
         and len({_json(x) for x in units}) == len(units), 'Exact ordered unique full unit census')
    ids = shape['case_ids']
    need(type(ids) is dict and set(ids) == {'train', 'val', 'test'}, 'Three original case rosters')
    for split in ids:
        need(type(ids[split]) is list and all(type(x) is str and x for x in ids[split]),
             'Opaque exact ordered case IDs')
    flattened = sum((ids[x] for x in ('train', 'val', 'test')), [])
    need(len(flattened) == len(set(flattened)), 'Case IDs are unique across original splits')
    names = shape['feature_names']
    need(type(names) is dict and set(names) == set(CONDITIONS), 'Four full feature schemas')
    for condition in CONDITIONS:
        declared_names = S_NAMES + H_NAMES + (B_NAMES if condition in ('SBH', 'SBHN') else []) + (['N:' + unit for unit in units] if condition.endswith('N') else [])
        need(names[condition] == declared_names, 'Exact original context indicators and full ordered unit names')
        expected = (16 if condition in ('SH', 'SHN') else 19) + (len(units) if condition.endswith('N') else 0)
        logistic._schema(names[condition], expected)
    need(names['SHN'][:16] == names['SH'] and names['SBHN'][:19] == names['SBH']
         and names['SHN'][16:] == names['SBHN'][19:], 'Matched context and full neural schema order')
    return json.loads(_json(shape))


def shape_from_prepared(prepared):
    """Private operator-only bridge; never pass this unit/case census to C actors."""
    from .preparation import project_case
    cases = prepared['cases']
    if cases:
        names = {condition: project_case(cases[0], condition)['feature_names'] for condition in CONDITIONS}
    else:
        # Preserve an empty eligible roster without inventing a case or dropping its
        # full admitted source unit census. Fits below report every slot unavailable.
        names = {condition: S_NAMES + H_NAMES + (B_NAMES if condition in ('SBH', 'SBHN') else [])
                 + (['N:' + unit for unit in prepared['unit_ids']] if condition.endswith('N') else [])
                 for condition in CONDITIONS}
    return _shape({'session_id': prepared['session_id'], 'unit_ids': list(prepared['unit_ids']),
                   'case_ids': {split: [case['case_id'] for case in cases if case['split'] == split]
                                for split in ('train', 'val', 'test')}, 'feature_names': names})


class _Runtime:
    def __init__(self, shape, identity):
        self._shape = _shape(shape)
        self.shape_identity = _digest(self._shape)
        self.identity = identity
        self.models = {}
        self.calls = {'optimizer_leaf': 0, 'hgb_constructor': 0, 'hgb_fit_leaf': 0,
                      'hgb_predict_leaf': 0}
        self.np = None
        self.inference_records = []
        self.validation_selections = {}

    def limits(self, condition):
        ids = self._shape['case_ids']
        return {'session_id': self._shape['session_id'],
                'max_rows': max(1, len(ids['train']) + len(ids['val']), len(ids['test'])),
                'n_features': len(self._shape['feature_names'][condition])}


class InertRuntime(_Runtime):
    """Explicit fixed controls only: no optimizer search and no learned HGB state."""
    def __init__(self, shape, *, optimizer_fault=None, hgb_fault=None):
        need(optimizer_fault in (None, 'raise_before', 'raise_after', 'bad_count', 'shift_intercept', 'one_candidate'),
             'Enumerated inert optimizer fault')
        need(hgb_fault in (None, 'raise_fit', 'one_class_axis', 'duplicate_axis', 'reverse_axis',
                          'bad_probability', 'bad_rowsum', 'wrong_width', 'changing_axis', 'one_candidate'),
             'Enumerated inert HGB fault')
        super().__init__(shape, {'mode': 'explicit_inert_fixed_leaves', 'qualification': QUALIFICATION,
                                'optimizer_fault': optimizer_fault, 'hgb_fault': hgb_fault})
        self.optimizer_fault = optimizer_fault
        self.hgb_fault = hgb_fault

    def load(self):
        if self.np is None:
            self.np = importlib.import_module('numpy')
        return self.np

    def optimizer(self, objective, initial, *, callback, **settings):
        self.calls['optimizer_leaf'] += 1
        if self.optimizer_fault == 'raise_before' or (self.optimizer_fault == 'one_candidate' and self.calls['optimizer_leaf'] == 2):
            raise RuntimeError('inert optimizer raised before objective')
        theta = initial.copy()
        if self.optimizer_fault == 'shift_intercept':
            theta[0] += .25
        value, gradient = objective(theta)
        if self.optimizer_fault == 'raise_after':
            raise RuntimeError('inert optimizer raised after objective')
        return theta, value, {'warnflag': 0, 'task': 'INERT unchanged fixed point; no optimization',
                             'nit': 0, 'funcalls': 2 if self.optimizer_fault == 'bad_count' else 1,
                             'grad': gradient.copy()}

    def hgb(self, parameters):
        self.calls['hgb_constructor'] += 1
        return _InertHGB(self, parameters)


class _InertHGB:
    def __init__(self, runtime, parameters):
        self.runtime = runtime
        self.parameters = dict(parameters)
        self.classes_ = None

    def fit(self, X, y):
        self.runtime.calls['hgb_fit_leaf'] += 1
        if self.runtime.hgb_fault == 'raise_fit' or (self.runtime.hgb_fault == 'one_candidate' and self.parameters['max_leaf_nodes'] == 15 and self.parameters['max_iter'] == 100 and self.parameters['l2_regularization'] == 1.):
            raise RuntimeError('inert HGB fit leaf failure')
        axis = {'one_class_axis': [1], 'duplicate_axis': [0, 0], 'reverse_axis': [1, 0]}.get(
            self.runtime.hgb_fault, [0, 1])
        self.classes_ = self.runtime.np.asarray(axis, dtype=self.runtime.np.int64)
        self.n_features_in_ = X.shape[1]
        return self

    def predict_proba(self, X):
        self.runtime.calls['hgb_predict_leaf'] += 1
        np = self.runtime.np
        result = np.full((len(X), 2), .5, dtype=np.float64)
        if self.runtime.hgb_fault == 'reverse_axis':
            result[:, 0] = .75
            result[:, 1] = .25
        if self.runtime.hgb_fault == 'bad_probability':
            result[0, 0] = math.nan
        if self.runtime.hgb_fault == 'bad_rowsum':
            result[0, 0] = .4
        if self.runtime.hgb_fault == 'wrong_width':
            result = result[:, :1]
        if self.runtime.hgb_fault == 'changing_axis':
            self.classes_ = np.asarray([1, 0], dtype=np.int64)
        return result

    def state(self):
        return {'kind': 'inert_fixed_no_learning', 'parameters': self.parameters,
                'classes': self.classes_.tolist(), 'n_features': self.n_features_in_}


def inert_runtime(shape, *, optimizer_fault=None, hgb_fault=None):
    return InertRuntime(shape, optimizer_fault=optimizer_fault, hgb_fault=hgb_fault)


class NativeRuntime(_Runtime):
    def __init__(self, shape, profile, authorization):
        capability = _validate_capability(profile, authorization)
        super().__init__(shape, {'mode': 'selected_process_native_capability_checked',
                                'qualification': QUALIFICATION, 'profile_sha256': _digest(profile),
                                'selection_identity': authorization['selection_identity'],
                                'capability': capability})
        self.profile = json.loads(_json(profile))
        self._optimizer = None
        self._hgb = None

    def load(self):
        if self.np is not None:
            return self.np
        p = self.profile
        need(platform.python_version() == p['python_version'], 'Exact admitted Python version')
        need(set(p['packages']) == {'numpy', 'scipy', 'scikit-learn'}, 'Complete native package profile')
        need(p['packages']['numpy']['version'] == '2.2.6'
             and p['packages']['scipy']['version'] == '1.15.3', 'Inherited NumPy/SciPy version contract')
        # Authenticate every ordinary source/native package body before imports. Profile
        # roots and manifests are future selected operands, never discovered from data.
        for distribution, package in p['packages'].items():
            need(importlib.metadata.version(distribution) == package['version'], 'Exact package version')
            root = Path(package['root'])
            need(root.is_absolute() and root.is_dir() and not root.is_symlink(), 'Exact ordinary package root')
            manifest = package['files']
            need(type(manifest) is dict and manifest, 'Complete independently admitted package file manifest')
            actual = {str(path.relative_to(root)) for path in root.rglob('*')
                      if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc'}
            need(actual == set(manifest), 'Exact package source/native file census')
            for relative, pin in manifest.items():
                path = root / relative
                need(path.resolve().is_relative_to(root.resolve()) and not path.is_symlink(),
                     'Ordinary native package member stays inside admitted root')
                body = path.read_bytes()
                need(len(body) == pin['bytes'] and hashlib.sha256(body).hexdigest() == pin['sha256'],
                     'Exact admitted source/native package identity')
        np = importlib.import_module('numpy')
        scipy_optimize = importlib.import_module('scipy.optimize')
        ensemble = importlib.import_module('sklearn.ensemble')
        hgb = ensemble.HistGradientBoostingClassifier
        need(hgb.__module__ == 'sklearn.ensemble._hist_gradient_boosting.gradient_boosting',
             'Concrete selected sklearn HistGradientBoostingClassifier API')
        need(str(inspect.signature(hgb)) == p['hgb_signature']
             and str(inspect.signature(scipy_optimize.fmin_l_bfgs_b)) == p['optimizer_signature'],
             'Exact independently admitted constructor/optimizer API signatures')
        for distribution, module in [('numpy', np), ('scipy', importlib.import_module('scipy')),
                                     ('scikit-learn', importlib.import_module('sklearn'))]:
            need(Path(module.__file__).resolve().parent == Path(p['packages'][distribution]['root']).resolve(),
                 'Imported package matches authenticated source root')
        need(set(HGB_FIXED) | set(reference_grid('H')[0]) | {'random_state'}
             <= set(inspect.signature(hgb).parameters), 'Every fixed HGB field supported explicitly')
        self.np, self._optimizer, self._hgb = np, scipy_optimize.fmin_l_bfgs_b, hgb
        return np

    def optimizer(self, *args, **kwargs):
        self.load()
        return self._optimizer(*args, **kwargs)

    def hgb(self, parameters):
        self.load()
        # Concrete native path; never executed by source-only controls.
        return self._hgb(**parameters)


def admit_runtime(profile, *, shape, authorization):
    """Concrete selected process admission; scientific qualification remains unchanged."""
    need(type(profile) is dict, 'Exact native profile document required')
    return NativeRuntime(shape, profile, authorization)


def _views(views, runtime, condition, *, split=None, labels=False):
    need(type(runtime) in (InertRuntime, NativeRuntime), 'Constructed explicit reference runtime')
    shape = runtime._shape
    need(runtime.shape_identity == _digest(shape), 'Frozen runtime dimension contract')
    need(condition in CONDITIONS and type(views) is list and views, 'Nonempty exact condition view list')
    names = shape['feature_names'][condition]
    ids, rows, ys = [], [], []
    required = {'case_id', 'condition', 'feature_names', 'features'} | ({'y'} if labels else set())
    for view in views:
        need(type(view) is dict and set(view) == required, 'Exact view schema; held labels never accepted')
        need(view['condition'] == condition and view['feature_names'] == names, 'Exact full feature name/order')
        need(type(view['case_id']) is str and view['case_id'], 'Opaque view identity')
        row = view['features']
        need(type(row) is list and len(row) == len(names)
             and all(type(x) in (int, float) and math.isfinite(x) for x in row), 'Finite complete feature row')
        ids.append(view['case_id']); rows.append(row)
        if labels:
            need(type(view['y']) is int and view['y'] in (0, 1), 'Exact binary calibration label')
            ys.append(view['y'])
    need(len(ids) == len(set(ids)), 'No duplicate support IDs')
    if split is not None:
        expected = shape['case_ids']['train'] + shape['case_ids']['val'] if split == 'refit' else shape['case_ids'][split]
        need(ids == expected, 'Exact ordered fitting/validation support; no held test label can fit')
    else:
        need(set(ids) <= set(sum(shape['case_ids'].values(), [])), 'Prediction support belongs to frozen session')
    np = runtime.load()
    X = np.asarray(rows, dtype=np.float64)
    logistic._matrix(np, X, runtime.limits(condition))
    y = np.asarray(ys, dtype=np.int64) if labels else None
    return X, y, ids, names


def _close(actual, expected, kind):
    atol, rtol = TOLERANCES[kind]
    need(math.isfinite(actual) and math.isfinite(expected)
         and abs(actual - expected) <= atol + rtol * abs(expected), 'Independent scalar '+kind+' agreement')


def _sigmoid(z):
    return 1./(1.+math.exp(-z)) if z >= 0 else math.exp(z)/(1.+math.exp(z))


def scalar_equations(rows, labels, intercept, coefficients, regularization):
    """Independent inherited scalar contract: no NumPy/primary arithmetic calls."""
    n, p = len(rows), len(coefficients)
    need(n > 0 and len(labels) == n and all(len(row) == p for row in rows), 'Exact scalar equation shape')
    need(all(type(y) is int and y in (0, 1) for y in labels), 'Scalar binary support')
    need(all(math.isfinite(float(v)) for row in rows for v in row)
         and all(math.isfinite(float(v)) for v in [intercept, *coefficients]), 'Finite scalar operands')
    logits, probabilities, residuals, losses = [], [], [], []
    for row, y in zip(rows, labels):
        z = math.fsum((intercept, math.fsum(float(x)*b for x, b in zip(row, coefficients))))
        need(math.isfinite(z), 'Finite scalar logit')
        m = (1-2*y)*z
        logits.append(z); probabilities.append(_sigmoid(z))
        residuals.append(_sigmoid(z) if y == 0 else -_sigmoid(-z))
        losses.append(max(m, 0.) + math.log1p(math.exp(-abs(m))))
    penalty = .5*regularization*math.fsum(b*b for b in coefficients)
    gradient = [math.fsum(residuals)/n] + [
        math.fsum(float(row[j])*r for row, r in zip(rows, residuals))/n + regularization*coefficients[j]
        for j in range(p)]
    result = {'objective': math.fsum(losses)/n+penalty, 'gradient': gradient,
              'logits': logits, 'probabilities': probabilities,
              'gradient_max_abs': max(abs(v) for v in gradient)}
    need(all(math.isfinite(v) for v in [result['objective'], *gradient]), 'Finite independent full equation')
    return result


def _audit_scaler(raw, transformed, scaler):
    rows = raw.tolist(); scaled = transformed.tolist(); n = len(rows)
    for j, inactive in enumerate(scaler['inactive']):
        values = [row[j] for row in rows]
        constant = all(v == values[0] for v in values)
        need(constant == inactive, 'Independent exact-constant detection')
        mean, scale = scaler['mean'][j], scaler['scale'][j]
        _close(mean, values[0] if constant else math.fsum(values)/n, 'scaler_mean')
        if constant:
            need(mean == values[0] and scale == 0. and all(row[j] == 0. for row in scaled),
                 'Independent exact-zero inactive scaling')
        else:
            expected = math.sqrt(math.fsum((v-mean)**2 for v in values)/n)
            need(expected > 0. and scale > 0., 'Independent positive population RMS')
            _close(scale, expected, 'scaler_scale')
            for value, row in zip(values, scaled):
                _close(row[j], (value-mean)/scale, 'scaled_value')
    return {'status': 'independent_scalar_scaler_agrees', 'rows': n, 'columns': len(scaler['mean'])}


def _audit_transform(raw, transformed, scaler):
    for raw_row, row in zip(raw.tolist(), transformed.tolist()):
        for j, (value, actual) in enumerate(zip(raw_row, row)):
            if scaler['inactive'][j]:
                need(actual == 0., 'Independent inactive query column stays zero')
            else:
                _close(actual, (value-scaler['mean'][j])/scaler['scale'][j], 'scaled_value')


def _axis(np, estimator):
    axis = estimator.classes_
    need(type(axis) is np.ndarray and axis.ndim == 1 and axis.shape == (2,)
         and axis.dtype.kind in ('i', 'u') and set(axis.tolist()) == {0, 1},
         'HGB requires exact binary native classes_ with both labels')
    values = [int(v) for v in axis]
    return {'classes': values, 'label1_column': values.index(1)}


def _state_identity(estimator, runtime):
    """Bounded streaming identity of exact retained estimator state; no repr hash."""
    limit = 1024*1024 if type(runtime) is InertRuntime else runtime.profile['state_limit_bytes']
    need(type(limit) is int and limit > 0, 'Prospectively selected exact native-state byte ceiling')
    class Writer:
        def __init__(self):
            self.size = 0
            self.hash = hashlib.sha256()
        def write(self, data):
            need(self.size + len(data) <= limit, 'Exact native-state capture exceeds selected ceiling')
            self.size += len(data)
            self.hash.update(data)
            return len(data)
    writer = Writer()
    if type(estimator) is _InertHGB:
        writer.write(_json(estimator.state()))
    else:
        pickle.Pickler(writer, protocol=5).dump(estimator)
    return {'sha256': writer.hash.hexdigest(), 'bytes': writer.size}


def _hgb_predict(runtime, estimator, X, axis, record):
    np = runtime.np
    need(_axis(np, estimator) == axis, 'Frozen classes_ order and explicit label1 mapping')
    record['native_predict_attempted'] = 1
    values = estimator.predict_proba(X)
    record['native_predict_completed'] = 1
    record['native_probability_return'] = _observed_array(values, maximum_cells=2*len(X))
    record['classes_after_prediction'] = _observed_array(estimator.classes_, maximum_cells=2)
    need(_axis(np, estimator) == axis, 'Native prediction cannot mutate probability class axis')
    need(type(values) is np.ndarray and values.dtype == np.dtype('float64')
         and values.shape == (len(X), 2) and bool(np.all(np.isfinite(values)))
         and bool(np.all((values >= 0.) & (values <= 1.)))
         and bool(np.all(np.abs(values.sum(axis=1)-1.) <= 1e-12)),
         'Finite binary probability rows in native class-axis order')
    return values[:, axis['label1_column']].tolist()


def _loss(labels, probabilities):
    need(len(labels) == len(probabilities) and len(labels) > 0, 'Complete validation probability support')
    losses = []
    for y, p in zip(labels, probabilities):
        need(type(p) is float and math.isfinite(p) and 0 <= p <= 1, 'Valid raw validation probability')
        q = min(max(p, 1e-12), 1-1e-12)
        losses.append(-math.log(q) if y else -math.log1p(-q))
    return math.fsum(losses)/len(losses)


def _fit_one(family, config, views, runtime, session_id, condition, split, fit_id, record):
    record.update({'status': 'attempted', 'fit_id': fit_id, 'config': dict(config),
                   'qualification': QUALIFICATION, 'error': None})
    try:
        X, y, ids, names = _views(views, runtime, condition, split=split, labels=True)
        need(session_id == runtime._shape['session_id'], 'Exact runtime session identity')
        need(0 < int(y.sum()) < len(y), 'Both fitting classes 0/1 required; no fallback')
        np, limits = runtime.np, runtime.limits(condition)
        record.update({'case_ids': ids, 'feature_names': names, 'n_fit': len(ids),
                       'n_features': X.shape[1], 'class_counts': {'0': int((y == 0).sum()), '1': int(y.sum())},
                       'fit_values_sha256': _digest(views), 'runtime_identity': runtime.identity})
        model = {'family': family, 'condition': condition, 'session_id': session_id,
                 'shape_identity': runtime.shape_identity, 'runtime_identity': runtime.identity,
                 'feature_names': names, 'config': dict(config), 'qualification': QUALIFICATION,
                 'status': 'available', 'fit_id': fit_id, 'fit_case_ids': ids, 'fit_phase': split}
        if family == 'L':
            scaler = logistic.fit_scaler(np, X, names, limits=limits)
            transformed = logistic.apply_scaler(np, X, scaler, limits=limits)
            record['scaler'] = scaler
            record['scaler_audit'] = _audit_scaler(X, transformed, scaler)
            fit_record = {}; record['fit_record'] = fit_record
            fitted = logistic.fit_logistic(np, runtime.optimizer, transformed, y, config['lambda'],
                                           names, scaler['inactive'], fit_id=fit_id, limits=limits,
                                           record=fit_record)
            independent = scalar_equations(transformed.tolist(), y.tolist(), fitted['intercept'],
                                           fitted['coefficients'], config['lambda'])
            _close(fitted['objective'], independent['objective'], 'objective')
            for key, kind in [('gradient', 'gradient'), ('training_logits', 'logit'),
                              ('training_probabilities', 'probability')]:
                source_key = {'training_logits': 'logits', 'training_probabilities': 'probabilities'}.get(key, key)
                need(len(fitted[key]) == len(independent[source_key]), 'Full independent arithmetic roster')
                for actual, expected in zip(fitted[key], independent[source_key]):
                    _close(actual, expected, kind)
            need(independent['gradient_max_abs'] <= logistic.GRADIENT_LIMIT,
                 'Independent full gradient including intercept exceeds 1e-7')
            record['independent_fit_audit'] = independent
            model.update({'scaler': scaler, 'fitted': fitted})
        else:
            params = {**HGB_FIXED, **config, 'random_state': hgb_seed(session_id)}
            work = {'constructor_attempted': 1, 'constructor_completed': 0,
                    'fit_attempted': 0, 'fit_completed': 0}
            record.update({'parameters': params, 'native_work': work})
            estimator = runtime.hgb(params)
            work['constructor_completed'] += 1; work['fit_attempted'] += 1
            returned = estimator.fit(X.copy(), y.copy())
            work['fit_completed'] += 1
            need(returned is estimator, 'Concrete native fit returns its fresh estimator')
            record['native_classes_returned'] = _observed_array(getattr(estimator, 'classes_', None), maximum_cells=2)
            axis = _axis(np, estimator)
            need(int(estimator.n_features_in_) == X.shape[1], 'HGB retains every original feature')
            state = _state_identity(estimator, runtime)
            state_hash = state['sha256']
            key = fit_id + ':' + state_hash
            runtime.models[key] = estimator
            bin_state = {'status': 'inert_no_bins'} if type(estimator) is _InertHGB else {
                'thresholds': [x.tolist() for x in estimator._bin_mapper.bin_thresholds_],
                'n_bins_non_missing': estimator._bin_mapper.n_bins_non_missing_.tolist()}
            record.update({'axis': axis, 'state_sha256': state_hash, 'state_bytes': state['bytes'], 'bin_state': bin_state})
            model.update({'axis': axis, 'native_key': key, 'state_sha256': state_hash,
                          'parameters': params, 'bin_state': bin_state})
        record['status'] = 'available'
        model['parameter_identity'] = _digest(model)
        return model
    except Exception as error:
        record.update({'status': 'unavailable', 'error': type(error).__name__+': '+str(error)})
        return None


def _predict(model, views, runtime, observation):
    need(type(model) is dict and model.get('status') == 'available', 'Available committed reference model')
    saved_identity = model.get('parameter_identity')
    body = {k: v for k, v in model.items() if k != 'parameter_identity'}
    need(saved_identity == _digest(body), 'Frozen exact reference parameters')
    need(model['runtime_identity'] == runtime.identity and model['shape_identity'] == runtime.shape_identity,
         'Exact runtime/profile and session shape binding')
    condition = model['condition']
    X, unused, ids, names = _views(views, runtime, condition, labels=False)
    need(model['feature_names'] == names, 'Full fixed prediction schema')
    if model['family'] == 'L':
        transformed = logistic.apply_scaler(runtime.np, X, model['scaler'], limits=runtime.limits(condition))
        _audit_transform(X, transformed, model['scaler'])
        probabilities = logistic.predict(runtime.np, transformed, model['fitted'], limits=runtime.limits(condition)).tolist()
        for row, p in zip(transformed.tolist(), probabilities):
            z = math.fsum((model['fitted']['intercept'], math.fsum(x*b for x, b in zip(row, model['fitted']['coefficients']))))
            _close(p, _sigmoid(z), 'probability')
        return probabilities
    need(model['family'] == 'H' and model['native_key'] in runtime.models, 'Owned immutable native state required')
    estimator = runtime.models[model['native_key']]
    need(_state_identity(estimator, runtime)['sha256'] == model['state_sha256'], 'Unchanged committed native state')
    probabilities = _hgb_predict(runtime, estimator, X, model['axis'], observation)
    need(_state_identity(estimator, runtime)['sha256'] == model['state_sha256'], 'Inference cannot mutate native parameters')
    return probabilities


def _observed_array(value, *, maximum_cells):
    """Retain original malformed native output without nonfinite JSON erasure."""
    if value is None:
        return {'type': 'NoneType'}
    if not hasattr(value, 'shape') or not hasattr(value, 'tolist'):
        return {'type': type(value).__name__}
    if value.size > maximum_cells:
        return {'shape': list(value.shape), 'dtype': str(value.dtype),
                'values_unavailable': 'oversized native return refused before list materialization'}
    def safe(item):
        if type(item) is list:
            return [safe(x) for x in item]
        if type(item) is float and not math.isfinite(item):
            return {'nonfinite': 'NaN' if math.isnan(item) else ('+Infinity' if item > 0 else '-Infinity')}
        if type(item) in (int, float, str, bool) or item is None:
            return item
        return {'type': type(item).__name__}
    return {'shape': list(value.shape), 'dtype': str(value.dtype), 'values': safe(value.tolist())}


def _predict_recorded(model, views, runtime, record, *, final_only=False):
    record.update({'status': 'attempted', 'case_ids': [v.get('case_id') for v in views],
                   'inference_attempted': 1, 'inference_completed': 0,
                   'native_predict_attempted': 0, 'native_predict_completed': 0,
                   'qualification': QUALIFICATION})
    try:
        if final_only:
            need(type(model) is dict and model.get('fit_phase') == 'refit',
                 'Ordinary held prediction refuses train-grid models; use the actual validation panel')
        result = _predict(model, views, runtime, record)
        record.update({'status': 'available', 'inference_completed': 1, 'probabilities': result})
        return result
    except Exception as error:
        record.update({'status': 'unavailable', 'error': type(error).__name__+': '+str(error)})
        raise


def predict(model, views, runtime):
    observation = {}
    runtime.inference_records.append(observation)
    return _predict_recorded(model, views, runtime, observation, final_only=True)


def _checked_stage(stage, runtime):
    """Authenticate exact stage/source/configuration/state joins without fitting."""
    need(type(runtime) in (InertRuntime, NativeRuntime), 'Explicit reference runtime')
    need(type(stage) is dict and set(stage) == {'snapshot', 'models', 'stage_identity'},
         'Exact train-only stage schema')
    snapshot = stage['snapshot']
    need(type(snapshot) is dict and set(snapshot) == {
        'family', 'session_id', 'condition', 'runtime_identity', 'shape_identity',
        'train_values_sha256', 'candidates'}, 'Exact immutable stage snapshot')
    need(stage['stage_identity'] == _digest(snapshot), 'Unchanged train-only stage snapshot')
    need(snapshot['session_id'] == runtime._shape['session_id']
         and snapshot['condition'] in CONDITIONS
         and snapshot['runtime_identity'] == runtime.identity
         and snapshot['shape_identity'] == runtime.shape_identity == _digest(runtime._shape),
         'Exact stage session/schema/runtime binding')
    grid = reference_grid(snapshot['family'])
    candidates, models = snapshot['candidates'], stage['models']
    need(type(candidates) is list and type(models) is list
         and len(candidates) == len(models) == len(grid), 'Complete fixed staged candidate roster')
    for index, (config, candidate, model) in enumerate(zip(grid, candidates, models)):
        need(type(candidate) is dict and set(candidate) == {
            'index', 'config', 'status', 'parameter_identity'}, 'Exact staged candidate schema')
        need(type(candidate['index']) is int and candidate['index'] == index
             and candidate['config'] == config
             and candidate['status'] in ('available', 'unavailable'), 'Ordered fixed candidate/config/status')
        if candidate['status'] == 'unavailable':
            need(model is None and candidate['parameter_identity'] is None,
                 'Failed candidate retains explicit absent model')
            continue
        need(type(snapshot['train_values_sha256']) is str and len(snapshot['train_values_sha256']) == 64,
             'Successful stage binds original train-only operands')
        need(type(model) is dict and model.get('status') == 'available'
             and model.get('fit_phase') == 'train'
             and model['family'] == snapshot['family'] and model['condition'] == snapshot['condition']
             and model['session_id'] == snapshot['session_id']
             and model['runtime_identity'] == snapshot['runtime_identity']
             and model['shape_identity'] == snapshot['shape_identity']
             and model['config'] == config and model['fit_case_ids'] == runtime._shape['case_ids']['train'],
             'Exact staged train-model source/config/support join')
        identity = _digest({k: v for k, v in model.items() if k != 'parameter_identity'})
        need(identity == model['parameter_identity'] == candidate['parameter_identity'],
             'Unchanged actual staged parameters')
        if snapshot['family'] == 'H':
            need(model['native_key'] in runtime.models, 'Original staged native state remains owned')
            estimator = runtime.models[model['native_key']]
            need(_state_identity(estimator, runtime)['sha256'] == model['state_sha256'],
                 'Unchanged actual staged native state')
    return snapshot


def stage_grid(family, train_views, runtime, *, session_id, condition, record):
    """Fit all candidates using train only; no validation view or label operand."""
    need(type(record) is dict and not record, 'Fresh mutable train-only staging record')
    grid = reference_grid(family)
    record.update({'family': family, 'session_id': session_id, 'condition': condition,
                   'qualification': QUALIFICATION, 'status': 'attempted', 'grid_records': [],
                   'runtime_identity': runtime.identity, 'shape_identity': runtime.shape_identity,
                   'train_values_sha256': None})
    try:
        record['train_values_sha256'] = _digest(train_views)
    except (ValueError, TypeError) as error:
        record['train_identity_error'] = type(error).__name__+': '+str(error)
    models, candidates = [], []
    for index, config in enumerate(grid):
        entry = {'index': index, 'config': dict(config)}
        record['grid_records'].append(entry)
        fit_id = f'{session_id}:{condition}:{family}:grid:{index}'
        model = _fit_one(family, config, train_views, runtime, session_id, condition,
                         'train', fit_id, entry)
        models.append(model)
        candidates.append({'index': index, 'config': dict(config),
                           'status': 'available' if model is not None else 'unavailable',
                           'parameter_identity': None if model is None else model['parameter_identity']})
    snapshot = json.loads(_json({
        'family': family, 'session_id': session_id, 'condition': condition,
        'runtime_identity': runtime.identity, 'shape_identity': runtime.shape_identity,
        'train_values_sha256': record['train_values_sha256'], 'candidates': candidates}))
    stage = {'snapshot': snapshot, 'models': models, 'stage_identity': _digest(snapshot)}
    _checked_stage(stage, runtime)
    record.update({'status': 'staged' if all(m is not None for m in models) else 'staged_with_unavailable',
                   'snapshot': json.loads(_json(snapshot)), 'stage_identity': stage['stage_identity']})
    return stage


def predict_validation_case(stage, one_y_free_view, runtime, *, panel_gate, record):
    """One current observation across every candidate, before any validation label."""
    need(type(record) is dict and not record, 'Fresh caller-owned validation cell record')
    record.update({'status': 'attempted', 'qualification': QUALIFICATION,
                   'candidate_records': [], 'observations': [],
                   'candidate_predictions_attempted': 0, 'candidate_predictions_completed': 0,
                   'submitted': False})
    try:
        need(type(panel_gate) is ValidationPanel, 'Actual owner chronological ValidationPanel required')
        snapshot = _checked_stage(stage, runtime)
        record.update({'stage_identity': stage['stage_identity'], 'family': snapshot['family'],
                       'condition': snapshot['condition']})
        current = panel_gate.current_view(stage)
        need(type(one_y_free_view) is dict and 'y' not in one_y_free_view
             and _json(one_y_free_view) == _json(current), 'Exactly the gate current y-free validation view')
        record['case_id'] = current['case_id']
        record['view'] = json.loads(_json(current))
        observations = record['observations']
        for candidate, model in zip(snapshot['candidates'], stage['models']):
            entry = {'index': candidate['index'], 'config': dict(candidate['config']),
                     'parameter_identity': candidate['parameter_identity'], 'status': 'unavailable'}
            record['candidate_records'].append(entry)
            if model is None:
                observations.append({**entry, 'p': None})
                entry['reason'] = 'train_candidate_unavailable'
                continue
            observation = {}
            entry['inference_record'] = observation
            # Keep the original inference record reachable before any raised call.
            runtime.inference_records.append(observation)
            record['candidate_predictions_attempted'] += 1
            probabilities = _predict_recorded(model, [current], runtime, observation)
            need(len(probabilities) == 1, 'Exactly one captured current-case probability')
            record['candidate_predictions_completed'] += 1
            entry['status'] = 'available'
            observations.append({'index': candidate['index'], 'config': dict(candidate['config']),
                                 'parameter_identity': candidate['parameter_identity'],
                                 'status': 'available', 'p': probabilities[0]})
        panel_gate.submit(stage, observations)
        record.update({'status': 'captured', 'submitted': True})
        return observations
    except Exception as error:
        record.update({'status': 'unavailable', 'error': type(error).__name__+': '+str(error)})
        if type(panel_gate) is ValidationPanel and panel_gate.failed is None:
            panel_gate.failed = {'type': type(error).__name__, 'error': str(error),
                                 'position': panel_gate.position,
                                 'stage_identity': record.get('stage_identity')}
        raise


def _validation_capture(stage, labels, transcript, released, runtime):
    """Independent complete ordered label/view/candidate/state/receipt joins."""
    snapshot = _checked_stage(stage, runtime)
    need(type(released) is dict and set(released) == {
        'labels', 'labelled_views', 'transcript', 'validation_identity', 'stage_identity'},
         'Exact sealed validation release')
    need(released['stage_identity'] == stage['stage_identity']
         and _json(labels) == _json(released['labels'])
         and _json(transcript) == _json(released['transcript']),
         'Supplied labels and transcript are the exact actual gate release')
    ids = runtime._shape['case_ids']['val']
    labelled = released['labelled_views']
    need(type(labels) is list and type(transcript) is list and type(labelled) is list
         and len(labels) == len(transcript) == len(labelled) == len(ids),
         'Complete original validation support after seal')
    names = runtime._shape['feature_names'][snapshot['condition']]
    y, probabilities = [], [[] for unused in snapshot['candidates']]
    for case_id, label, capture, labelled_view in zip(ids, labels, transcript, labelled):
        need(type(label) is dict and set(label) == {'case_id', 'y'}
             and label['case_id'] == case_id and type(label['y']) is int and label['y'] in (0, 1),
             'Exact original ordered validation labels')
        need(type(capture) is dict and set(capture) == {
            'case_id', 'view', 'candidates', 'whole_panel_ack'} and capture['case_id'] == case_id,
             'Exact ordered full-panel validation capture')
        view = capture['view']
        need(type(view) is dict and set(view) == {'case_id', 'condition', 'feature_names', 'features'}
             and view['case_id'] == case_id and view['condition'] == snapshot['condition']
             and view['feature_names'] == names, 'Captured permitted schema and source case')
        values = view['features']
        need(type(values) is list and len(values) == len(names)
             and all(type(v) in (int, float) and math.isfinite(v) for v in values),
             'Full finite captured validation features')
        need(_json(labelled_view) == _json({**view, 'y': label['y']}),
             'Released labels attach only to their captured y-free views')
        ack = capture['whole_panel_ack']
        need(type(ack) is dict and set(ack) == {'bytes', 'sha256'}
             and type(ack['bytes']) is int and ack['bytes'] > 0
             and type(ack['sha256']) is str and len(ack['sha256']) == 64,
             'Actual exact durable whole-panel receipt retained')
        observed = capture['candidates']
        need(type(observed) is list and len(observed) == len(snapshot['candidates']),
             'Every fixed candidate in every committed validation case')
        for expected, actual, ps in zip(snapshot['candidates'], observed, probabilities):
            need(type(actual) is dict and set(actual) == {
                'index', 'config', 'parameter_identity', 'status', 'p'}, 'Exact candidate observation')
            need(actual['index'] == expected['index'] and actual['config'] == expected['config']
                 and actual['parameter_identity'] == expected['parameter_identity']
                 and actual['status'] == expected['status'],
                 'Every captured probability joins its frozen candidate/config/state')
            if expected['status'] == 'available':
                need(type(actual['p']) is float and math.isfinite(actual['p']) and 0 <= actual['p'] <= 1,
                     'Valid raw captured label1 probability')
                ps.append(actual['p'])
            else:
                need(actual['p'] is None, 'Unavailable candidate has no replacement probability')
        y.append(label['y'])
    return y, probabilities, ids


def select_grid(stage, released_validation_labels, validation_transcript, runtime, *, panel_gate, record):
    """Select only after the actual complete matched validation journal is sealed."""
    need(type(record) is dict and not record, 'Fresh mutable sealed validation-selection record')
    record.update({'qualification': QUALIFICATION, 'status': 'attempted', 'selected': None,
                   'grid_records': [], 'selection_route': 'sealed_chronological_validation_v2'})
    try:
        need(type(panel_gate) is ValidationPanel, 'Actual owner chronological ValidationPanel required')
        snapshot = _checked_stage(stage, runtime)
        record.update({key: snapshot[key] for key in (
            'family', 'session_id', 'condition', 'runtime_identity', 'shape_identity', 'train_values_sha256')})
        record['stage_identity'] = stage['stage_identity']
        for candidate in snapshot['candidates']:
            record['grid_records'].append({**candidate, 'fit_status': candidate['status'],
                                           'validation_case_ids': None, 'validation_probabilities': None,
                                           'validation_logloss': None})
        released = panel_gate.released(stage)
        labels, probabilities, ids = _validation_capture(
            stage, released_validation_labels, validation_transcript, released, runtime)
        record.update({'validation_identity': json.loads(_json(released['validation_identity'])),
                       'validation_transcript_sha256': _digest(released['transcript']),
                       'val_values_sha256': _digest(released['labelled_views'])})
        for entry, ps in zip(record['grid_records'], probabilities):
            entry['validation_case_ids'] = list(ids)
            if entry['fit_status'] != 'available':
                entry['error'] = 'train_candidate_unavailable'
                continue
            entry['validation_probabilities'] = list(ps)
            if not ids:
                entry.update({'status': 'unavailable', 'error': 'empty_validation_support'})
                continue
            entry['validation_logloss'] = _loss(labels, ps)
        available = all(entry['status'] == 'available' and entry['validation_logloss'] is not None
                        for entry in record['grid_records'])
        record['status'] = 'available' if available else 'unavailable'
        if available:
            family = snapshot['family']
            tie = (lambda e: -e['config']['lambda']) if family == 'L' else (
                lambda e: (e['config']['max_leaf_nodes'], e['config']['max_iter'], -e['config']['l2_regularization']))
            chosen = min(record['grid_records'], key=lambda e: (e['validation_logloss'], tie(e)))
            record['selected'] = dict(chosen['config'])
            record['selected_index'] = chosen['index']
        else:
            record['unavailable_reason'] = 'complete_grid_required_no_favorable_survivor'
    except Exception as error:
        record.update({'status': 'unavailable', 'error': type(error).__name__+': '+str(error)})
    record['selection_identity'] = _digest(record)
    if record['status'] == 'available':
        runtime.validation_selections[record['selection_identity']] = {
            'stage_identity': record['stage_identity'],
            'validation_identity': json.loads(_json(record['validation_identity']))}
    return record


def fit_grid(family, train_views, val_views, runtime, *, session_id, condition, record):
    """Unsafe whole-validation convenience route is closed in the additive successor."""
    need(type(record) is dict and not record, 'Fresh refused legacy-grid record')
    message = ('Whole-batch labelled validation is refused; use stage_grid, the actual ValidationPanel, '
               'predict_validation_case, seal/released, then select_grid')
    record.update({'status': 'unavailable', 'qualification': QUALIFICATION,
                   'family': family, 'session_id': session_id, 'condition': condition,
                   'error': message, 'grid_records': [], 'selected': None,
                   'fit_calls_attempted': 0})
    raise ValueError(message)

def refit_selected(selection, train_views, val_views, runtime, *, session_id, condition, record):
    need(type(record) is dict and not record, 'Fresh mutable final-refit record')
    record.update({'status': 'unavailable', 'qualification': QUALIFICATION, 'error': None})
    try:
        need(selection['status'] == 'available' and selection['selected'] is not None,
             'Complete available validation grid required for fresh final refit')
        need(selection.get('selection_route') == 'sealed_chronological_validation_v2'
             and type(selection.get('stage_identity')) is str
             and type(selection.get('validation_identity')) is dict,
             'Final refit requires the sealed chronological validation selection')
        need(selection['selection_identity'] == _digest({k: v for k, v in selection.items() if k != 'selection_identity'}),
             'Frozen complete selection record')
        need(runtime.validation_selections.get(selection['selection_identity']) == {
            'stage_identity': selection['stage_identity'],
            'validation_identity': selection['validation_identity']},
             'Refit selection must originate from this runtime actual sealed validation gate')
        need(selection['session_id'] == session_id and selection['condition'] == condition
             and selection['shape_identity'] == runtime.shape_identity
             and selection['runtime_identity'] == runtime.identity, 'Exact final-refit selection binding')
        need(selection['train_values_sha256'] == _digest(train_views)
             and selection['val_values_sha256'] == _digest(val_views), 'No calibration changes after selection')
        model = _fit_one(selection['family'], selection['selected'], train_views+val_views, runtime,
                         session_id, condition, 'refit', f'{session_id}:{condition}:{selection["family"]}:refit', record)
        if model is None:
            return record
        model.update({'selection_identity': selection['selection_identity'],
                      'validation_identity': json.loads(_json(selection['validation_identity'])),
                      'stage_identity': selection['stage_identity']})
        model['parameter_identity'] = _digest({k: v for k, v in model.items() if k != 'parameter_identity'})
        record['selection_identity'] = selection['selection_identity']
        record['validation_identity'] = model['validation_identity']
        record['model'] = model
        return model
    except Exception as error:
        record.update({'status': 'unavailable', 'error': type(error).__name__+': '+str(error)})
        return record


def prior(labels):
    """Laplace fitting-set estimate, independently checked; no held labels supplied."""
    need(type(labels) in (list, tuple) and labels, 'Nonempty explicit fitting labels')
    result = logistic.prior_estimate(labels, limits={'session_id': 'explicit-fitting-prior',
                                                    'max_rows': len(labels), 'n_features': 1})
    need(result['probability_left'] == (math.fsum(labels)+1)/(len(labels)+2), 'Independent fitting prior')
    return {**result, 'qualification': QUALIFICATION}


def model_commitment(model):
    """Finite concrete learned-state commitment for the durable panel controller."""
    need(type(model) is dict and model.get('status') == 'available', 'Available reference model to commit')
    identity = model.get('parameter_identity')
    need(identity == _digest({k: v for k, v in model.items() if k != 'parameter_identity'}),
         'Complete actual parameter/scaler/native-state identity')
    return {'config_identity': _digest({'family': model['family'], 'condition': model['condition'],
                                      'config': model['config']}),
            'parameter_identity': identity, 'runtime_identity': model['runtime_identity'],
            'status': model['status'], 'qualification': QUALIFICATION}


def source_identity():
    """Semantic method binding; complete actual source pins are owner freeze operands."""
    return {'contract': 'N059-complete-choice-reference-v2-chronological-validation',
            'donor_sha256': logistic.DONOR_SHA256,
            'composition': ['program/logistic.py', 'program/references.py', 'program/validation.py'],
            'L': {'grid': reference_grid('L'), 'optimizer': logistic.OPTIMIZER_SETTINGS,
                  'gradient_limit': logistic.GRADIENT_LIMIT},
            'H': {'grid': reference_grid('H'), 'fixed': HGB_FIXED,
                  'api': 'sklearn.ensemble.HistGradientBoostingClassifier'},
            'qualification': QUALIFICATION}
