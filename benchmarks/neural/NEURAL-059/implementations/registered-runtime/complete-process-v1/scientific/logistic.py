"""Dimension-contract successor of inherited Stage B float64 source; source only.

NumPy and the held SciPy1.15.3 fmin_l_bfgs_b are injected by a later worker.
Feature construction, cohort/schema admission, sequential history disclosure,
parameter commitments, independent audit, scoring, and resource admission remain
caller responsibilities. These routines do not select lambdas or query cases. All local shape consumers
use one explicit per-session contract; no pilot cap is raised globally.
"""

import math


DONOR_SHA256 = '19d4b8140236f131496c3cbafcdc0eb91fb37067c51207752db790c6ed0414db'
QUALIFICATION = 'source_only_unqualified'


def _limits(limits):
    need(type(limits) is dict and set(limits) == {'session_id', 'max_rows', 'n_features'},
         'Explicit session dimension contract required')
    need(type(limits['session_id']) is str and bool(limits['session_id'])
         and type(limits['max_rows']) is int and limits['max_rows'] > 0
         and type(limits['n_features']) is int and limits['n_features'] > 0,
         'Positive admitted session dimensions')
    return limits

LAMBDAS = (.001, .1, 10.)
GRADIENT_LIMIT = 1e-7
OPTIMIZER_SETTINGS = {
    'm': 20, 'factr': 0.0, 'pgtol': 5e-8,
    'maxiter': 1000, 'maxfun': 20000, 'maxls': 50,
    'bounds': None, 'approx_grad': 0,
}
COUNTER_KEYS = (
    'fit_calls_attempted', 'optimizer_calls_attempted', 'optimizer_calls_completed',
    'optimizer_objective_requests', 'objective_evaluations_attempted',
    'objective_evaluations_completed', 'iteration_callbacks',
    'final_evaluations_attempted', 'final_evaluations_completed', 'accepted_fits',
)


def need(condition, message):
    if not condition:
        raise ValueError(message)


def _tick(tick):
    if tick is not None:
        tick()


def _matrix(np, features, limits):
    _limits(limits)
    need(type(features) is np.ndarray and features.dtype == np.dtype('float64'),
         'Exact float64 feature ndarray required')
    need(features.ndim == 2 and 1 <= features.shape[0] <= limits['max_rows']
         and features.shape[1] == limits['n_features'], 'Bounded nonempty feature matrix')
    need(bool(np.all(np.isfinite(features))), 'Nonfinite model feature')
    return features.shape


def _schema(names, columns):
    need(type(names) in (list, tuple) and len(names) == columns
         and all(type(name) is str and 1 <= len(name) <= 160 for name in names)
         and len(set(names)) == columns, 'Complete unique original feature schema')
    return list(names)


def _mask(inactive, columns):
    need(type(inactive) in (list, tuple) and len(inactive) == columns
         and all(type(value) is bool for value in inactive), 'Full boolean inactive schema')
    return list(inactive)


def _labels(np, labels, rows, both_classes=False):
    need(type(labels) is np.ndarray and labels.dtype == np.dtype('int64')
         and labels.shape == (rows,), 'Complete int64 label vector')
    need(bool(np.all((labels == 0) | (labels == 1))), 'Labels must be right0/left1')
    left = int(labels.sum(dtype=np.int64))
    if both_classes:
        need(0 < left < rows, 'Both classes required for fixed logistic initialization')
    return rows-left, left


def _lambda(value):
    need(type(value) in (int, float) and value in LAMBDAS, 'Fixed prospective lambda grid')
    return float(value)


def _parameters(np, theta, columns):
    need(type(theta) is np.ndarray and theta.dtype == np.dtype('float64')
         and theta.shape == (columns+1,), 'Full float64 intercept-and-slopes vector')
    need(bool(np.all(np.isfinite(theta))), 'Nonfinite model parameter')


def fit_scaler(np, features, feature_names, *, limits, tick=None):
    """Fit population centering/RMS on these rows only; retain every column.

    Exact fitting constants are identified by equality to their first entry before
    mean reduction. This avoids inventing variance when a rounded sum shifts the
    mean of repeated nonbinary log1p values. A nonconstant column whose computed
    deviation underflows to zero fails instead of being silently made inactive.
    """
    _tick(tick)
    rows, columns = _matrix(np, features, limits)
    names = _schema(feature_names, columns)
    inactive = np.all(features == features[0], axis=0)
    with np.errstate(over='raise', invalid='raise', divide='raise', under='ignore'):
        means = features[0].copy()
        if not bool(np.all(inactive)):
            means[~inactive] = features[:, ~inactive].mean(axis=0, dtype=np.float64)
        centered = features-means
        variance = np.mean(centered*centered, axis=0, dtype=np.float64)
        need(bool(np.all(np.isfinite(means))) and bool(np.all(np.isfinite(variance)))
             and bool(np.all(variance >= 0)), 'Invalid fitting moments')
        variance[inactive] = 0.
        need(bool(np.all(variance[~inactive] > 0)),
             'Nonconstant fitting variance underflowed to zero')
        scales = np.sqrt(variance)
    need(bool(np.all(np.isfinite(scales))) and bool(np.all(scales[~inactive] > 0)),
         'Unbounded or nonfinite fitting scale')
    result = {'feature_names': names, 'n_fit': rows, 'mean': means.tolist(),
              'scale': scales.tolist(), 'inactive': inactive.tolist()}
    _tick(tick)
    return result


def _scaler(np, scaler, columns, limits):
    _limits(limits)
    need(type(scaler) is dict and set(scaler) == {
        'feature_names', 'n_fit', 'mean', 'scale', 'inactive'}, 'Exact fitted scaler schema')
    _schema(scaler['feature_names'], columns)
    need(type(scaler['n_fit']) is int and 1 <= scaler['n_fit'] <= limits['max_rows'],
         'Bounded fitting-row provenance')
    inactive = _mask(scaler['inactive'], columns)
    for key in ('mean', 'scale'):
        need(type(scaler[key]) is list and len(scaler[key]) == columns
             and all(type(value) is float and math.isfinite(value) for value in scaler[key]),
             'Finite full fitted '+key)
    need(all((scale == 0. if off else scale > 0.)
             for scale, off in zip(scaler['scale'], inactive)),
         'Inactive scales are zero; active scales are strictly positive')
    return (np.asarray(scaler['mean'], dtype=np.float64),
            np.asarray(scaler['scale'], dtype=np.float64),
            np.asarray(inactive, dtype=np.bool_))


def apply_scaler(np, features, scaler, *, limits, tick=None):
    """Use fixed training moments, with exact zero in every inactive query column."""
    _tick(tick)
    unused_rows, columns = _matrix(np, features, limits)
    means, scales, inactive = _scaler(np, scaler, columns, limits)
    transformed = np.zeros_like(features, dtype=np.float64)
    active = ~inactive
    with np.errstate(over='raise', invalid='raise', divide='raise', under='ignore'):
        transformed[:, active] = (features[:, active]-means[active])/scales[active]
    need(bool(np.all(np.isfinite(transformed))), 'Unbounded transformed feature')
    transformed.setflags(write=False)
    _tick(tick)
    return transformed


def stable_sigmoid(np, logits, *, limits):
    _limits(limits)
    """Finite raw probabilities; saturation to0 or1 is permitted, never clipped."""
    need(type(logits) is np.ndarray and logits.dtype == np.dtype('float64')
         and logits.ndim == 1 and 1 <= logits.size <= limits['max_rows']
         and bool(np.all(np.isfinite(logits))), 'Finite bounded float64 logits')
    probabilities = np.empty_like(logits)
    positive = logits >= 0.
    with np.errstate(over='raise', invalid='raise', divide='raise', under='ignore'):
        probabilities[positive] = 1./(1.+np.exp(-logits[positive]))
        tail = np.exp(logits[~positive])
        probabilities[~positive] = tail/(1.+tail)
    need(bool(np.all(np.isfinite(probabilities)))
         and bool(np.all((probabilities >= 0.) & (probabilities <= 1.))),
         'Invalid raw model probability')
    return probabilities


def _evaluate(np, features, labels, theta, regularization, limits):
    """Internal equation after fixed X/y admission; still validate each theta."""
    _parameters(np, theta, features.shape[1])
    with np.errstate(over='raise', invalid='raise', divide='raise', under='ignore'):
        logits = theta[0]+features@theta[1:]
        need(bool(np.all(np.isfinite(logits))), 'Nonfinite fitting logits')
        sign = 1.-2.*labels
        margin = sign*logits
        losses = np.logaddexp(0., margin)
        # Unlike sigmoid(z)-y, this retains small correct-class residuals.
        residual = sign*stable_sigmoid(np, margin, limits=limits)
        mean_loss = float(np.mean(losses, dtype=np.float64))
        penalty = .5*regularization*float(np.dot(theta[1:], theta[1:]))
        objective = mean_loss+penalty
        gradient = np.empty(theta.size, dtype=np.float64)
        gradient[0] = np.mean(residual, dtype=np.float64)
        gradient[1:] = features.T@residual/features.shape[0]+regularization*theta[1:]
    need(math.isfinite(objective) and math.isfinite(mean_loss) and math.isfinite(penalty)
         and bool(np.all(np.isfinite(gradient))), 'Nonfinite declared objective or full gradient')
    return {'objective': objective, 'mean_log_loss': mean_loss, 'ridge_penalty': penalty,
            'gradient': gradient, 'logits': logits,
            'probabilities': stable_sigmoid(np, logits, limits=limits)}


def objective_gradient(np, features, labels, theta, regularization, *, limits, tick=None):
    """Public declared equation, allowing any valid binary class support."""
    _tick(tick)
    rows, unused_columns = _matrix(np, features, limits)
    _labels(np, labels, rows)
    result = _evaluate(np, features, labels, theta, _lambda(regularization), limits)
    _tick(tick)
    return result


def _safe_parameters(np, parameters, limits):
    if not (type(parameters) is np.ndarray and parameters.ndim == 1
            and parameters.size <= limits['n_features']+1 and parameters.dtype == np.dtype('float64')):
        return {'unavailable': 'parameter shape or dtype outside declared envelope'}
    return [float(value) if math.isfinite(float(value)) else {
        'nonfinite': 'NaN' if math.isnan(float(value)) else ('+Infinity' if value > 0 else '-Infinity')}
        for value in parameters]


def _safe_scalar(np, value):
    if type(value) is str:
        return value[:1000]
    if type(value) is int:
        return value
    if isinstance(value, (float, np.floating)):
        value = float(value)
        if math.isfinite(value):
            return value
        return {'nonfinite': 'NaN' if math.isnan(value) else ('+Infinity' if value > 0 else '-Infinity')}
    return {'unavailable_type': type(value).__name__}


def fit_logistic(np, optimizer, features, labels, regularization, feature_names,
                 inactive, *, fit_id, limits, tick=None, counters=None, record=None):
    """One fixed-start fit; never retry, change lambdas, or accept a success flag alone.

    Fresh caller dictionaries retain partial attempts/parameters on every failure.
    Up to20000 optimizer objective evaluations and one separately counted final
    declared-equation evaluation are permitted. Accepted output is JSON-friendly.
    The full original schema is optimized, including exact-zero inactive columns;
    all inactive slopes must remain exactly zero on return.
    """
    if counters is None:
        counters = {}
    if record is None:
        record = {}
    need(type(counters) is dict and not counters and type(record) is dict and not record,
         'Provide fresh empty fit counters and record')
    counters.update({key: 0 for key in COUNTER_KEYS})
    counters['fit_calls_attempted'] = 1
    record.update({'fit_id': fit_id if type(fit_id) is str else None,
                   'status': 'attempted', 'counters': counters, 'error': None})
    phase = 'preflight'
    try:
        need(type(fit_id) is str and 1 <= len(fit_id) <= 160, 'Bounded explicit fit identity')
        need(callable(optimizer) and (tick is None or callable(tick)), 'Callable fixed optimizer/tick')
        _tick(tick)
        rows, columns = _matrix(np, features, limits)
        names = _schema(feature_names, columns)
        inactive = _mask(inactive, columns)
        right, left = _labels(np, labels, rows, both_classes=True)
        regularization = _lambda(regularization)
        mask = np.asarray(inactive, dtype=np.bool_)
        need(bool(np.all(features[:, mask] == 0.)), 'Inactive fitting columns must be exactly zero')
        # Own one bounded immutable fitting copy; no later query can alter it.
        fitting = features.copy(); fitting.setflags(write=False)
        targets = labels.copy(); targets.setflags(write=False)
        initial = np.zeros(columns+1, dtype=np.float64)
        initial[0] = math.log(left/right)
        record.update({
            'n_fit': rows, 'n_features': columns, 'feature_names': names,
            'inactive': inactive, 'lambda': regularization,
            'class_counts': {'right': right, 'left': left},
            'initial_intercept': float(initial[0]),
            'initial_coefficients': initial[1:].tolist(),
            'optimizer_settings': dict(OPTIMIZER_SETTINGS),
        })

        def objective(theta):
            counters['optimizer_objective_requests'] += 1
            record['last_objective_parameters'] = _safe_parameters(np, theta, limits)
            need(counters['objective_evaluations_attempted'] < OPTIMIZER_SETTINGS['maxfun'],
                 'Hard objective-evaluation limit reached')
            _tick(tick)
            counters['objective_evaluations_attempted'] += 1
            result = _evaluate(np, fitting, targets, theta, regularization, limits)
            counters['objective_evaluations_completed'] += 1
            record['last_completed_evaluation'] = {
                'evaluation_index': counters['objective_evaluations_completed'],
                'parameters': record['last_objective_parameters'],
                'objective': result['objective'], 'mean_log_loss': result['mean_log_loss'],
                'ridge_penalty': result['ridge_penalty'],
                'gradient_max_abs': float(np.max(np.abs(result['gradient']))),
                'gradient': result['gradient'].tolist(),
            }
            _tick(tick)
            return result['objective'], result['gradient']

        def iteration(theta):
            counters['iteration_callbacks'] += 1
            need(counters['iteration_callbacks'] <= OPTIMIZER_SETTINGS['maxiter'],
                 'Hard optimization-iteration limit reached')
            record['last_iteration_parameters'] = _safe_parameters(np, theta, limits)
            _parameters(np, theta, columns)
            _tick(tick)

        phase = 'optimization'
        counters['optimizer_calls_attempted'] += 1
        returned = optimizer(
            objective, initial.copy(), fprime=None, args=(), callback=iteration,
            **OPTIMIZER_SETTINGS)
        counters['optimizer_calls_completed'] += 1
        need(type(returned) in (list, tuple) and len(returned) == 3,
             'Pinned optimizer must return exactly parameters, objective, info')
        solution, reported_objective, info = returned
        record['returned_parameters'] = _safe_parameters(np, solution, limits)
        metadata = info if type(info) is dict else {}
        record['optimizer_return'] = {
            key: _safe_scalar(np, metadata.get(key)) for key in ('warnflag', 'task', 'nit', 'funcalls')}
        record['optimizer_return'].update({
            'reported_objective': _safe_scalar(np, reported_objective),
            'reported_gradient': _safe_parameters(np, metadata.get('grad'), limits),
        })
        _parameters(np, solution, columns)
        need(type(info) is dict and all(key in info for key in ('warnflag', 'task', 'nit', 'funcalls', 'grad')),
             'Complete pinned optimizer termination record')
        need(type(info['warnflag']) is int and info['warnflag'] in (0, 1, 2)
             and type(info['task']) is str and len(info['task']) <= 1000,
             'Bounded optimizer termination reason')
        need(type(info['nit']) is int and type(info['funcalls']) is int
             and info['nit'] == counters['iteration_callbacks'] <= OPTIMIZER_SETTINGS['maxiter']
             and info['funcalls'] == counters['objective_evaluations_completed']
             == counters['objective_evaluations_attempted']
             == counters['optimizer_objective_requests'] <= OPTIMIZER_SETTINGS['maxfun'],
             'Reported and actual optimizer work must reconcile')
        _parameters(np, info['grad'], columns)
        reported_objective = float(reported_objective)
        need(math.isfinite(reported_objective), 'Nonfinite optimizer objective')
        record['optimizer_return'] = {
            'warnflag': info['warnflag'], 'task': info['task'], 'nit': info['nit'],
            'funcalls': info['funcalls'], 'reported_objective': reported_objective,
            'reported_gradient': info['grad'].tolist(),
        }
        phase = 'final_evaluation'
        _tick(tick)
        counters['final_evaluations_attempted'] += 1
        final = _evaluate(np, fitting, targets, solution, regularization, limits)
        counters['final_evaluations_completed'] += 1
        gradient_norm = float(np.max(np.abs(final['gradient'])))
        record.update({
            'intercept': float(solution[0]), 'coefficients': solution[1:].tolist(),
            'objective': final['objective'], 'mean_log_loss': final['mean_log_loss'],
            'ridge_penalty': final['ridge_penalty'], 'gradient': final['gradient'].tolist(),
            'gradient_max_abs': gradient_norm,
            'training_logits': final['logits'].tolist(),
            'training_probabilities': final['probabilities'].tolist(),
        })
        phase = 'acceptance'
        need(bool(np.all(solution[1:][mask] == 0.)), 'Inactive coefficient changed from exact zero')
        need(gradient_norm <= GRADIENT_LIMIT,
             'Full declared gradient including intercept exceeds convergence threshold')
        _tick(tick)
        counters['accepted_fits'] = 1
        record['status'] = 'accepted'
        return record
    except BaseException as error:
        record['status'] = 'failed'
        record['failed_phase'] = phase
        record['error'] = type(error).__name__+': '+str(error)[:1800]
        raise


def predict(np, features, model, *, limits, tick=None):
    """Raw left probabilities from a committed model and already-scaled rows."""
    _tick(tick)
    unused_rows, columns = _matrix(np, features, limits)
    need(type(model) is dict and model.get('status') == 'accepted', 'Accepted fixed model required')
    _schema(model['feature_names'], columns)
    inactive = _mask(model['inactive'], columns)
    need(type(model['intercept']) is float and math.isfinite(model['intercept'])
         and type(model['coefficients']) is list and len(model['coefficients']) == columns
         and all(type(value) is float and math.isfinite(value) for value in model['coefficients']),
         'Finite full original coefficient schema')
    need(all(not off or coefficient == 0.
             for off, coefficient in zip(inactive, model['coefficients'])),
         'Inactive model slopes must be exactly zero')
    mask = np.asarray(inactive, dtype=np.bool_)
    need(bool(np.all(features[:, mask] == 0.)), 'Inactive query columns must be exactly zero')
    with np.errstate(over='raise', invalid='raise', divide='raise', under='ignore'):
        logits = model['intercept']+features@np.asarray(model['coefficients'], dtype=np.float64)
    probabilities = stable_sigmoid(np, logits, limits=limits)
    probabilities.setflags(write=False)
    _tick(tick)
    return probabilities


def prior_estimate(labels, *, limits):
    _limits(limits)
    """Closed-form Laplace-smoothed fitting prevalence; no optimizer or query data."""
    need(type(labels) in (list, tuple) and 1 <= len(labels) <= limits['max_rows']
         and all(type(value) is int and value in (0, 1) for value in labels),
         'Complete binary fitting labels required for prior')
    left = sum(labels)
    return {'n_fit': len(labels), 'n_left': left, 'n_right': len(labels)-left,
            'probability_left': (left+1)/(len(labels)+2)}
