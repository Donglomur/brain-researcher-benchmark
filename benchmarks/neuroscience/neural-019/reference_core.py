"""NEURAL-019 fixed retrospective movement readouts; pure numerical functions.

No I/O, global RNG state, query-target argument, or outcome-adaptive recipe.
Real wrappers must bind the exact 1340/126 source rows and frozen type/fold IDs.
Generated fixtures may use fewer trials, retaining 140 bins and 137 input units.
Smoothing is symmetric within each trial: this is not a causal decoder.
"""
from __future__ import annotations
import math
import numpy as np
from scipy.ndimage import gaussian_filter1d

ARMS = ('raw137', 'pca10', 'random10')
LAMBDAS = (0.01, 0.1, 1.0, 10.0)
MAX_TRIALS = 2295
BINS = 140
UNITS = 137
COMPONENTS = 10
CHUNK_TRIALS = 32
RANDOM_SEED = 19019
TIE_TOLERANCE = 1e-12
REPRESENTATION_KEYS = {'arm', 'unit_mean', 'unit_scale', 'basis',
                       'projected_mean', 'projected_scale', 'fit_trials'}
MODEL_KEYS = REPRESENTATION_KEYS | {'phase_mean', 'coefficients', 'intercept', 'lambda_value'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def _counts(value):
    require(isinstance(value, np.ndarray) and value.ndim == 3
            and 1 <= len(value) <= MAX_TRIALS and value.shape[1:] == (BINS, UNITS)
            and value.dtype == np.dtype('uint16'), 'Counts must be bounded n×140×137 uint16')
    return value


def _velocity(value, n, name='velocity'):
    require(isinstance(value, np.ndarray) and value.shape == (n, BINS, 2)
            and value.dtype in (np.dtype('float32'), np.dtype('float64'))
            and np.isfinite(value).all(), name + ': finite floating n×140×2 required')
    return value.astype(np.float64, copy=False)


def _groups(value, n):
    require(isinstance(value, np.ndarray) and value.shape == (n,)
            and ((value.dtype.kind in 'iu' and value.dtype.itemsize <= 8)
                 or (value.dtype.kind == 'U' and 0 < value.dtype.itemsize <= 256
                     and np.all(value != ''))), 'One integer or bounded Unicode trial_type per trial')
    return value


def smooth_counts(counts):
    """Float conversion precedes filtering; at most32 complete trials per filter call."""
    counts = _counts(counts)
    output = np.empty(counts.shape, dtype=np.float64)
    for start in range(0, len(counts), CHUNK_TRIALS):
        stop = min(start + CHUNK_TRIALS, len(counts))
        gaussian_filter1d(counts[start:stop].astype(np.float64), sigma=10.0, axis=1,
                          order=0, output=output[start:stop], mode='reflect', truncate=4.0)
    require(np.isfinite(output).all(), 'Nonfinite smoothed counts')
    return output


def _fit_representation_smoothed(smoothed, arm):
    require(arm in ARMS, 'Unknown representation arm')
    rows = smoothed.reshape(-1, UNITS)
    mean = rows.mean(axis=0)
    scale = rows.std(axis=0, ddof=0)
    scale = np.where(scale == 0, 1.0, scale)
    z = (rows - mean) / scale
    require(np.isfinite(z).all(), 'Nonfinite fit-only standardization')
    if arm == 'raw137':
        basis = np.eye(UNITS)
    elif arm == 'pca10':
        covariance = z.T @ z / len(z)
        require(np.isfinite(covariance).all(), 'Nonfinite fit-only covariance')
        values, vectors = np.linalg.eigh(covariance)
        order = np.argsort(-values, kind='stable')[:COMPONENTS]
        require(np.isfinite(values).all() and np.all(values[order] > 0),
                'PCA requires ten strictly positive fit covariance eigenvalues')
        basis = vectors[:, order].copy()
        pivots = np.argmax(np.abs(basis), axis=0)
        signs = np.where(basis[pivots, np.arange(COMPONENTS)] < 0, -1.0, 1.0)
        basis *= signs
    else:
        rng = np.random.Generator(np.random.PCG64(RANDOM_SEED))
        basis, triangular = np.linalg.qr(rng.standard_normal((UNITS, COMPONENTS)), mode='reduced')
        diagonal = np.diag(triangular)
        require(np.all(diagonal != 0), 'Degenerate fixed random projection')
        basis *= np.where(diagonal < 0, -1.0, 1.0)
    if arm == 'raw137':
        projected_mean = np.zeros(UNITS)
        projected_scale = np.ones(UNITS)
    else:
        projected = z @ basis
        projected_mean = projected.mean(axis=0)
        projected_scale = projected.std(axis=0, ddof=0)
        projected_scale = np.where(projected_scale == 0, 1.0, projected_scale)
    model = {'arm': np.asarray(arm), 'unit_mean': mean, 'unit_scale': scale,
             'basis': basis, 'projected_mean': projected_mean, 'projected_scale': projected_scale,
             'fit_trials': np.asarray(len(smoothed), dtype=np.int64)}
    _validate_representation(model)
    return model


def _validate_representation(model):
    require(isinstance(model, dict) and set(model) in (REPRESENTATION_KEYS, MODEL_KEYS),
            'Unexpected representation/model fields')
    arm = np.asarray(model['arm'])
    require(arm.shape == () and arm.dtype.kind == 'U' and str(arm) in ARMS, 'Invalid stored arm')
    d = UNITS if str(arm) == 'raw137' else COMPONENTS
    shapes = {'unit_mean': (UNITS,), 'unit_scale': (UNITS,), 'basis': (UNITS, d),
              'projected_mean': (d,), 'projected_scale': (d,)}
    for key, shape in shapes.items():
        value = np.asarray(model[key])
        require(value.shape == shape and value.dtype == np.dtype('float64')
                and np.isfinite(value).all(), 'Invalid fitted representation: ' + key)
    require(np.all(model['unit_scale'] > 0) and np.all(model['projected_scale'] > 0),
            'Stored scales must be positive')
    fit_trials = np.asarray(model['fit_trials'])
    require(fit_trials.shape == () and fit_trials.dtype.kind in 'iu'
            and 1 <= int(fit_trials) <= MAX_TRIALS, 'Invalid fit trial count')
    return d


def fit_representation(fit_counts, arm):
    return _fit_representation_smoothed(smooth_counts(fit_counts), arm)


def _transform_smoothed(model, smoothed):
    d = _validate_representation(model)
    output = np.empty((len(smoothed), BINS, d), dtype=np.float64)
    for start in range(0, len(smoothed), CHUNK_TRIALS):
        stop = min(start + CHUNK_TRIALS, len(smoothed))
        z = (smoothed[start:stop] - model['unit_mean']) / model['unit_scale']
        if str(model['arm']) != 'raw137':
            z = (z @ model['basis'] - model['projected_mean']) / model['projected_scale']
        output[start:stop] = z
    require(np.isfinite(output).all(), 'Nonfinite transformed features')
    return output


def transform_representation(model, query_counts):
    return _transform_smoothed(model, smooth_counts(query_counts))


def _ridge_statistics(features, velocity):
    phase = velocity.mean(axis=0)
    x = features.reshape(-1, features.shape[2])
    residual = (velocity - phase).reshape(-1, 2)
    x_mean = x.mean(axis=0)
    y_mean = residual.mean(axis=0)
    centered_x = x - x_mean
    centered_y = residual - y_mean
    gram = centered_x.T @ centered_x / len(x)
    right = centered_x.T @ centered_y / len(x)
    require(all(np.isfinite(a).all() for a in (phase, x_mean, y_mean, gram, right)),
            'Nonfinite ridge sufficient statistics')
    return {'phase': phase, 'x_mean': x_mean, 'y_mean': y_mean, 'gram': gram, 'right': right}


def _solve_ridge(statistics, lambda_value):
    require(type(lambda_value) in (int, float) and lambda_value in LAMBDAS,
            'Only the four predeclared lambdas are allowed')
    gram = statistics['gram'].copy()
    gram.flat[::len(gram) + 1] += float(lambda_value)
    coefficients = np.linalg.solve(gram, statistics['right'])
    intercept = statistics['y_mean'] - statistics['x_mean'] @ coefficients
    require(np.isfinite(coefficients).all() and np.isfinite(intercept).all(),
            'Nonfinite ridge solution; no clipping or fallback')
    return coefficients, intercept


def _predict_features(features, phase, coefficients, intercept):
    with np.errstate(over='ignore', invalid='ignore'):
        prediction = features @ coefficients + intercept + phase
    require(np.isfinite(prediction).all(), 'Nonfinite velocity predictions; no clipping or fallback')
    return prediction


def fit_predict(fit_counts, fit_velocity, query_counts, arm, lambda_value):
    """Fit once; return predictions, phase control, numeric/Unicode model and diagnostics."""
    fit_counts = _counts(fit_counts)
    fit_velocity = _velocity(fit_velocity, len(fit_counts), 'fit velocity')
    query_counts = _counts(query_counts)
    smoothed = smooth_counts(fit_counts)
    model = _fit_representation_smoothed(smoothed, arm)
    features = _transform_smoothed(model, smoothed)
    statistics = _ridge_statistics(features, fit_velocity)
    coefficients, intercept = _solve_ridge(statistics, lambda_value)
    model.update({'phase_mean': statistics['phase'], 'coefficients': coefficients,
                  'intercept': intercept, 'lambda_value': np.asarray(float(lambda_value))})
    del smoothed, features
    prediction = predict(model, query_counts)
    return {'prediction': prediction,
            'phase_only': np.broadcast_to(model['phase_mean'], prediction.shape).copy(),
            'model': model,
            'diagnostics': {'fit_trials': len(fit_counts), 'query_trials': len(query_counts),
                            'arm': arm, 'lambda_value': float(lambda_value),
                            'feature_dimensions': UNITS if arm == 'raw137' else COMPONENTS,
                            'query_targets_received': False, 'ridge_systems_solved': 1}}


def predict(model, query_counts):
    require(isinstance(model, dict) and set(model) == MODEL_KEYS, 'Unexpected fitted model fields')
    d = _validate_representation(model)
    phase = np.asarray(model['phase_mean'])
    beta = np.asarray(model['coefficients'])
    intercept = np.asarray(model['intercept'])
    require(phase.shape == (BINS, 2) and beta.shape == (d, 2) and intercept.shape == (2,)
            and all(a.dtype == np.dtype('float64') and np.isfinite(a).all()
                    for a in (phase, beta, intercept)), 'Invalid fitted readout geometry/values')
    value = np.asarray(model['lambda_value'])
    require(value.shape == () and value.dtype == np.dtype('float64')
            and float(value) in LAMBDAS, 'Invalid stored lambda')
    return _predict_features(transform_representation(model, query_counts), phase, beta, intercept)


def _axis_metrics(truth, prediction):
    y = truth.reshape(-1, 2)
    p = prediction.reshape(-1, 2)
    constant_axis = np.all(y == y[0], axis=0)
    with np.errstate(over='ignore', invalid='ignore'):
        sse = np.square(y - p).sum(axis=0)
        sst = np.square(y - y.mean(axis=0)).sum(axis=0)
        mae = np.abs(y - p).mean(axis=0)
    require(all(np.isfinite(a).all() for a in (sse, sst, mae)), 'Nonfinite metric arithmetic')
    # Exact equality defines a constant target; mean roundoff must not create SST.
    # Check arithmetic above first so this does not hide overflow/nonfinite input.
    sst[constant_axis] = 0.0
    axes = [float(1 - sse[j] / sst[j]) if sst[j] > 0 else None for j in range(2)]
    require(all(v is None or math.isfinite(v) for v in axes), 'Nonfinite R²')
    return {'axis_r2': axes, 'uniform_axis_r2': None if None in axes else math.fsum(axes) / 2,
            'axis_mae': mae.tolist(), 'axis_mse': (sse / len(y)).tolist(),
            'axis_sse': sse.tolist(), 'axis_sst': sst.tolist()}


def metrics(truth, prediction, trial_types):
    """Equal type weight; both axes required. Undefined groups remain in the receipt."""
    require(isinstance(truth, np.ndarray) and truth.ndim == 3
            and 1 <= len(truth) <= MAX_TRIALS, 'Bounded truth tensor required')
    y = _velocity(truth, len(truth), 'metric truth')
    p = _velocity(prediction, len(truth), 'metric prediction')
    groups = _groups(trial_types, len(truth))
    per_type = []
    for group in np.unique(groups):
        selected = groups == group
        per_type.append({'trial_type': group.item(), 'trials': int(selected.sum()),
                         **_axis_metrics(y[selected], p[selected])})
    values = [row['uniform_axis_r2'] for row in per_type]
    defined = all(value is not None for value in values)
    return {'defined': defined,
            'macro_r2': math.fsum(values) / len(values) if defined else None,
            'per_type': per_type, 'pooled': _axis_metrics(y, p),
            'undefined_policy': 'Any constant group/axis makes macro undefined; no groups omitted'}


def validate_folds(trial_types, fold_ids):
    require(isinstance(trial_types, np.ndarray) and 4 <= len(trial_types) <= MAX_TRIALS,
            'At least four bounded trials are required')
    groups = _groups(trial_types, len(trial_types))
    require(isinstance(fold_ids, np.ndarray) and fold_ids.shape == groups.shape
            and fold_ids.dtype.kind in 'iu' and set(fold_ids.tolist()) == {0, 1, 2, 3},
            'All four supplied integer fold IDs0..3 are required')
    for group in np.unique(groups):
        require(len(np.unique(fold_ids[groups == group])) == 1,
                'A whole trial_type must belong to exactly one fold')
    return tuple(np.flatnonzero(fold_ids == fold) for fold in range(4))


def select_lambda(scores):
    require(isinstance(scores, dict) and set(scores) == set(LAMBDAS)
            and all(type(value) in (int, float) and math.isfinite(value) for value in scores.values()),
            'Every declared lambda must have a finite, defined score')
    maximum = max(scores.values())
    return max(value for value in LAMBDAS if maximum - scores[value] <= TIE_TOLERANCE)


def _defined_score(receipt):
    require(receipt['defined'] and receipt['macro_r2'] is not None
            and math.isfinite(receipt['macro_r2']), 'Undefined fold/candidate macro R² stops selection')
    return receipt['macro_r2']


def cross_validate(counts, velocity, trial_types, fold_ids):
    """Four supplied whole-type folds,48 solves; no full fit or assessment target access.

    Smoothing all trials once is label-free and strictly per-trial. Every fitted
    statistic, PCA basis and phase template is recomputed from fit rows only.
    Lambda selection uses all OOF group scores equally, not equal fold weighting.
    """
    counts = _counts(counts)
    velocity = _velocity(velocity, len(counts), 'training velocity')
    groups = _groups(trial_types, len(counts))
    folds = validate_folds(groups, fold_ids)
    smoothed = smooth_counts(counts)
    oof = {arm: {lam: np.empty(velocity.shape, dtype=np.float64) for lam in LAMBDAS} for arm in ARMS}
    phase_oof = np.empty(velocity.shape, dtype=np.float64)
    fold_receipts = []
    for fold_number, held in enumerate(folds):
        fit = np.flatnonzero(fold_ids != fold_number)
        fit_smoothed = smoothed[fit]
        held_smoothed = smoothed[held]
        fit_velocity = velocity[fit]
        phase = fit_velocity.mean(axis=0)
        phase_oof[held] = phase
        phase_score = _defined_score(metrics(velocity[held], phase_oof[held], groups[held]))
        scores = {}
        for arm in ARMS:
            model = _fit_representation_smoothed(fit_smoothed, arm)
            features = _transform_smoothed(model, fit_smoothed)
            query = _transform_smoothed(model, held_smoothed)
            statistics = _ridge_statistics(features, fit_velocity)
            arm_scores = {}
            for lam in LAMBDAS:
                beta, intercept = _solve_ridge(statistics, lam)
                prediction = _predict_features(query, statistics['phase'], beta, intercept)
                oof[arm][lam][held] = prediction
                arm_scores[str(lam)] = _defined_score(metrics(velocity[held], prediction, groups[held]))
            scores[arm] = arm_scores
            del features, query, statistics, model
        fold_receipts.append({'fold': fold_number, 'fit_trials': len(fit), 'held_trials': len(held),
                              'fit_trial_types': np.unique(groups[fit]).tolist(),
                              'held_trial_types': np.unique(groups[held]).tolist(),
                              'phase_only_macro_r2': phase_score, 'scores': scores})
        del fit_smoothed, held_smoothed, fit_velocity
    all_scores = {}
    selected = {}
    for arm in ARMS:
        values = {lam: _defined_score(metrics(velocity, oof[arm][lam], groups)) for lam in LAMBDAS}
        selected[arm] = select_lambda(values)
        all_scores[arm] = {str(lam): values[lam] for lam in LAMBDAS}
    return {'selected_lambda': selected, 'oof_scores': all_scores,
            'phase_only_oof': metrics(velocity, phase_oof, groups),
            'fold_held_positions': [held.tolist() for held in folds], 'folds': fold_receipts,
            'ridge_systems_solved': 48, 'training_trials': len(counts),
            'training_trial_types': len(np.unique(groups)), 'assessment_targets_received': False,
            'selection': 'Equal trial-type macro uniform-two-axis OOF R²; max-relative1e-12 tie takes larger lambda'}
