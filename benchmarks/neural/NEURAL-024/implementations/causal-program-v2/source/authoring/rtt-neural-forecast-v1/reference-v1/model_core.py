"""Fixed NEURAL-024 reference mathematics; execute only in the trusted worker."""
import math
import numpy as np
from scipy.optimize import fmin_l_bfgs_b
from scipy.special import gammaln

FAMILIES = ('self_history', 'self_population_history')
LAMBDAS = (.01, .1, 1.)
OPTIMIZER = {'name': 'scipy.optimize.fmin_l_bfgs_b', 'm': 10,
             'factr': 0., 'pgtol': 1e-7, 'maxiter': 300,
             'maxfun': 800, 'maxls': 30, 'independent_gradient_limit': 1e-6}


def need(condition, message):
    if not condition:
        raise ValueError(message)


def raw_features(counts, indices, family):
    """At k, every feature uses k-1..k-10; no current population count."""
    need(isinstance(counts, np.ndarray) and counts.ndim == 2 and
         counts.dtype in (np.dtype('uint32'), np.dtype('int64')) and
         bool(np.all(counts >= 0)), 'Nonnegative integer count matrix')
    need(isinstance(indices, np.ndarray) and indices.dtype == np.dtype('int64')
         and indices.ndim == 1 and len(indices) > 0 and
         int(indices.min()) >= 10 and int(indices.max()) < len(counts),
         'History and future target both inside the recording')
    need(family in FAMILIES and counts.shape[1] >= 2, 'Fixed family and population')
    columns = 10 if family == FAMILIES[0] else 20
    result = np.empty((len(indices), counts.shape[1], columns), dtype=np.float64)
    for lag in range(1, 11):
        previous = counts[indices - lag].astype(np.float64)
        result[:, :, lag - 1] = np.log1p(previous)
        if columns == 20:
            others = (np.sum(previous, axis=1, keepdims=True) - previous) / (counts.shape[1] - 1)
            need(bool(np.all(others >= 0)), 'Leave-self-out population mean')
            result[:, :, lag + 9] = np.log1p(others)
    need(bool(np.isfinite(result).all()), 'Finite history features')
    return result


def fit_scaler(raw):
    need(raw.ndim == 3 and len(raw) > 0 and bool(np.isfinite(raw).all()), 'Finite fitting features')
    constant = np.all(raw == raw[0:1], axis=0)
    mean = np.mean(raw, axis=0)
    centered = raw - mean
    scale = np.sqrt(np.mean(centered * centered, axis=0))
    need(bool(np.isfinite(mean).all()) and bool(np.isfinite(scale).all()), 'Finite fitting scaler')
    need(bool(np.all(scale[~constant] > 0)), 'Positive scale for nonconstant fitting columns')
    mean[constant] = raw[0][constant]
    scale[constant] = 1.
    return {'mean': mean.tolist(), 'scale': scale.tolist(), 'constant': constant.tolist()}


def transform(raw, scaler):
    mean = np.asarray(scaler['mean'], dtype=np.float64)
    scale = np.asarray(scaler['scale'], dtype=np.float64)
    constant = np.asarray(scaler['constant'], dtype=bool)
    need(raw.ndim == 3 and raw.shape[1:] == mean.shape == scale.shape == constant.shape,
         'Exact declared scaler dimensions')
    need(bool(np.isfinite(raw).all()) and bool(np.isfinite(mean).all()) and
         bool(np.isfinite(scale).all()) and bool(np.all(scale > 0)), 'Finite positive scaling')
    value = (raw - mean) / scale
    value[:, constant] = 0.
    need(bool(np.isfinite(value).all()), 'Finite transformed values')
    return value


def _labels(y):
    need(isinstance(y, np.ndarray) and y.ndim == 2 and y.dtype == np.dtype('int64')
         and len(y) > 0 and bool(np.all(y >= 0)), 'Nonnegative int64 response counts')


def _exp(z):
    # No clipping or silent flooring. Unsupported overflow/underflow fails closed.
    with np.errstate(over='raise', under='ignore', invalid='raise'):
        result = np.exp(z)
    need(bool(np.isfinite(result).all()) and bool(np.all(result > 0)),
         'Every expected count must be finite and strictly positive')
    return result


def objective_gradient(theta, X, y, lam):
    _labels(y)
    need(X.ndim == 3 and X.shape[:2] == y.shape and lam in LAMBDAS,
         'Fixed ridge value and fitting support')
    C, P = X.shape[1:]
    need(theta.shape == (C * (P + 1),) and bool(np.isfinite(theta).all()), 'Finite parameters')
    parameters = theta.reshape(C, P + 1)
    alpha, beta = parameters[:, 0], parameters[:, 1:]
    z = alpha[None, :] + np.einsum('ncp,cp->nc', X, beta, optimize=False)
    mu = _exp(z)
    intercept_rate = _exp(alpha)
    n = len(y)
    # SUM of channel-wise mean objectives, NOT an extra 1/C average.
    objective = (np.sum(mu - y * z) + .5 * np.sum(intercept_rate - alpha)) / n
    objective += .5 * lam * np.sum(beta * beta)
    residual = (mu - y) / n
    gradient = np.empty_like(parameters)
    gradient[:, 0] = np.sum(residual, axis=0) + .5 * (intercept_rate - 1.) / n
    gradient[:, 1:] = np.einsum('ncp,nc->cp', X, residual, optimize=False) + lam * beta
    need(math.isfinite(float(objective)) and bool(np.isfinite(gradient).all()), 'Finite objective and full gradient')
    return float(objective), gradient.reshape(-1)


def constant_rates(y):
    _labels(y)
    return (np.sum(y, axis=0, dtype=np.float64) + .5) / (len(y) + .5)


def fit(raw, y, lam, tick=None, progress=None):
    _labels(y)
    scaler = fit_scaler(raw)
    X = transform(raw, scaler)
    C, P = X.shape[1:]
    initial = np.zeros((C, P + 1), dtype=np.float64)
    initial[:, 0] = np.log(constant_rates(y))
    evaluations = 0
    if progress is None:
        progress = {}
    progress.update(objective_callback_calls=0, objective_attempts=0, objective_completions=0, solver_returned=False,
                    final_gradient_attempted=False, final_gradient_completed=False)
    def evaluate(theta):
        nonlocal evaluations
        progress['objective_callback_calls'] += 1
        if tick is not None:
            tick()
        evaluations += 1
        need(evaluations <= 830, 'Finite maxfun plus one maxls objective-call ceiling')
        progress['objective_attempts'] += 1
        answer = objective_gradient(theta, X, y, lam)
        progress['objective_completions'] += 1
        return answer
    theta, _, information = fmin_l_bfgs_b(
        evaluate, initial.reshape(-1), m=10, factr=0., pgtol=1e-7,
        maxiter=300, maxfun=800, maxls=30)
    progress['solver_returned'] = True
    if tick is not None:
        tick()
    progress['final_gradient_attempted'] = True
    objective, gradient = objective_gradient(theta, X, y, lam)
    progress['final_gradient_completed'] = True
    parameters = theta.reshape(C, P + 1)
    maximum = float(np.max(np.abs(gradient)))
    need(maximum <= 1e-6, 'Final full per-channel gradient criterion')
    constant = np.asarray(scaler['constant'], dtype=bool)
    need(bool(np.all(parameters[:, 1:][constant] == 0.)), 'Fitting-constant columns retain exactly zero slopes')
    task = information['task']
    if isinstance(task, bytes):
        task = task.decode('utf-8', errors='replace')
    need(len(str(task)) <= 1000, 'Bounded optimizer diagnostic')
    return {'alpha': parameters[:, 0].tolist(), 'beta': parameters[:, 1:].tolist(),
            'scaler': scaler, 'lambda': float(lam), 'n_fit': len(y), 'channels': C,
            'features_per_channel': P, 'parameter_coordinates': C * (P + 1),
            'objective': objective, 'gradient_max_abs': maximum,
            'optimizer': dict(OPTIMIZER), 'optimizer_info': {
                'warnflag': int(information['warnflag']), 'task': str(task),
                'iterations': int(information['nit']), 'function_calls': int(information['funcalls']),
                'observed_objective_calls': evaluations},
            'acceptance': 'full_gradient_criterion_subject_to_independent_audit',
            'intensity_prior': {'family': 'Gamma', 'shape': 1.5, 'rate': .5,
                                'density_parameter': 'exp(alpha)', 'jacobian_added': False}}


def predict(raw, model):
    X = transform(raw, model['scaler'])
    beta = np.asarray(model['beta'], dtype=np.float64)
    alpha = np.asarray(model['alpha'], dtype=np.float64)
    need(beta.shape == X.shape[1:] and alpha.shape == (X.shape[1],), 'Exact model dimensions')
    return _exp(alpha[None, :] + np.einsum('ncp,cp->nc', X, beta, optimize=False))


def calibration_gain(y, means):
    _labels(y)
    need(means.shape == y.shape and bool(np.isfinite(means).all()) and bool(np.all(means > 0)),
         'Exact positive calibration predictions')
    gain = (np.sum(y, axis=0, dtype=np.float64) + .5) / (np.sum(means, axis=0) + .5)
    need(bool(np.isfinite(gain).all()) and bool(np.all(gain > 0)), 'Positive finite calibration-only gain')
    return gain


def score(y, means):
    _labels(y)
    need(means.shape == y.shape and bool(np.isfinite(means).all()) and bool(np.all(means > 0)),
         'Complete positive finite expected counts')
    log_likelihood = y * np.log(means) - means - gammaln(y + 1.)
    need(bool(np.isfinite(log_likelihood).all()), 'Finite complete Poisson log likelihood')
    per_channel = []
    for channel in range(y.shape[1]):
        ll = float(np.sum(log_likelihood[:, channel], dtype=np.float64))
        per_channel.append({'channel_index': channel,
                            'spikes': int(np.sum(y[:, channel], dtype=np.int64)),
                            'log_likelihood': ll, 'mean_nll': -ll / len(y)})
    total = math.fsum(x['log_likelihood'] for x in per_channel)
    return {'rows': len(y), 'channels': y.shape[1], 'cells': int(y.size),
            'spikes': sum(x['spikes'] for x in per_channel), 'log_likelihood': total,
            'mean_nll': -total / y.size, 'per_channel': per_channel}
