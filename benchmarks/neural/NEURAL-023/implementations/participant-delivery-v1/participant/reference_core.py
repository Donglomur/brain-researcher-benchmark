"""Prespecified chronological ridge panel. No assessment targets are accepted."""
import numpy as np
from scipy.linalg import solve_triangular

LAMBDAS = (0.01, 0.1, 1.0, 10.0)
REGIMES = ('source_only', 'calibration_only', 'balanced_pooled')
ARMS = ('zero_velocity', 'source_mean_velocity', 'calibration_mean_velocity',
        'source_only_ridge', 'source_only_ridge_plus_calibration_mean_residual',
        'calibration_only_ridge', 'balanced_pooled_ridge')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def features(counts, endpoints, origin):
    require(counts.dtype == np.dtype('uint32') and counts.ndim == 2 and counts.shape[1] == 96,
            'Exact 96-channel integer event counts')
    require(endpoints.dtype == np.dtype('uint32') and endpoints.ndim == 1,
            'Exact endpoint integer identifiers')
    relative = endpoints.astype(np.int64) - origin
    require(np.all(relative >= 10) and np.all(relative <= len(counts)), 'Complete past-only supports')
    result = np.empty((len(endpoints), 960), dtype=np.float64)
    for begin in range(0, len(endpoints), 2048):
        end = min(len(endpoints), begin + 2048)
        indices = relative[begin:end, None] - 10 + np.arange(10)[None, :]
        # k-10 through k-1: never the bin starting at prediction endpoint k.
        result[begin:end] = np.log1p(counts[indices]).reshape(end - begin, 960)
    require(np.isfinite(result).all(), 'Finite transformed observations')
    return result


def uniform_weights(count):
    require(type(count) is int and count > 0, 'Nonempty training set')
    return np.full(count, 1.0 / count, dtype=np.float64)


def pooled_weights(source_count, calibration_count):
    return np.r_[uniform_weights(source_count) * 0.5,
                 uniform_weights(calibration_count) * 0.5]


def problem(x, y, weights):
    require(x.ndim == 2 and y.shape == (len(x), 2) and weights.shape == (len(x),),
            'Aligned training rows and axes')
    require(all(np.isfinite(v).all() for v in (x, y, weights)) and np.all(weights > 0),
            'Finite positive training weights and data')
    weights = weights / weights.sum()
    x_mean = weights @ x
    # Preserve mathematically zero variance for exactly constant columns rather
    # than amplifying floating weighted-sum roundoff during standardization.
    constant = np.all(x == x[0], axis=0)
    x_mean[constant] = x[0, constant]
    centered = x - x_mean
    variance = np.einsum('ij,i,ij->j', centered, weights, centered, optimize=True)
    require(np.all(variance >= 0) and np.isfinite(variance).all(), 'Nonnegative weighted variance')
    scale = np.sqrt(variance)
    scale[scale == 0] = 1.0
    z = centered / scale
    z_mean = weights @ z
    z -= z_mean
    y_mean = weights @ y
    gram = z.T @ (weights[:, None] * z)
    gram = (gram + gram.T) * 0.5
    cross = z.T @ (weights[:, None] * (y - y_mean))
    require(np.isfinite(gram).all() and np.isfinite(cross).all(), 'Finite ridge normal equations')
    return {'gram': gram, 'cross': cross, 'x_mean': x_mean, 'x_scale': scale,
            'z_mean': z_mean, 'y_mean': y_mean, 'training_count': len(x)}


def solve(prepared, penalty):
    require(penalty in LAMBDAS, 'Only frozen positive penalties')
    normal = prepared['gram'].copy()
    normal.flat[::len(normal) + 1] += penalty
    lower = np.linalg.cholesky(normal)
    rhs = solve_triangular(lower, prepared['cross'], lower=True, check_finite=True)
    coefficient = solve_triangular(lower.T, rhs, lower=False, check_finite=True)
    require(np.isfinite(coefficient).all(), 'Finite fitted coefficients; no numerical rescue')
    return {key: prepared[key] for key in ('x_mean', 'x_scale', 'z_mean', 'y_mean', 'training_count')} | {
        'coefficient': coefficient, 'lambda': penalty}


def predict(model, x):
    output = np.empty((len(x), 2), dtype=np.float64)
    for begin in range(0, len(x), 2048):
        end = min(len(x), begin + 2048)
        z = (x[begin:end] - model['x_mean']) / model['x_scale'] - model['z_mean']
        output[begin:end] = z @ model['coefficient'] + model['y_mean']
    require(np.isfinite(output).all(), 'Finite predictions without clipping')
    return output


def choose_penalty(errors):
    require(errors.shape == (4, 4) and np.isfinite(errors).all(), 'Every fixed fold/penalty must succeed')
    averages = errors.mean(axis=0)
    index = min(range(4), key=lambda j: (float(averages[j]), -LAMBDAS[j]))
    return LAMBDAS[index], averages


def fold_masks(regime, ids, fold):
    """Production masks, validated against the complete frozen endpoint identity."""
    require(regime in REGIMES and type(fold) is int and 1 <= fold <= 4,
            'Only predeclared chronological folds and regimes')
    width, last = (3740, 18700) if regime == 'source_only' else (600, 3000)
    require(ids.dtype == np.dtype('uint32') and ids.ndim == 1 and
            np.array_equal(ids, np.arange(10, last + 1, dtype=np.uint32)),
            'Complete ordered endpoint identities; no duplicates, omissions or substitutions')
    end = width * fold
    train = ids <= end
    valid = (ids >= end + 10) & (ids <= end + width)
    require(int(train.sum()) == end - 9 and int(valid.sum()) == width - 9,
            'Exact predeclared chronological fold counts')
    require(int(ids[train].max()) == int(ids[valid].min()) - 10,
            'Disjoint train/validation neural supports at exact half-open bin edges')
    return train, valid


def select_and_fit(regime, source, calibration, emit):
    require(regime in REGIMES, 'Fixed reference regime')
    sx, sy, sid = source
    cx, cy, cid = calibration
    errors = np.empty((4, 4), dtype=np.float64)
    folds = []
    fits = 0
    for fold in range(1, 5):
        width = 3740 if regime == 'source_only' else 600
        end = width * fold
        x, y, ids = source if regime == 'source_only' else calibration
        train, valid = fold_masks(regime, ids, fold)
        tx, ty = x[train], y[train]
        if regime == 'balanced_pooled':
            tx, ty = np.concatenate((sx, tx)), np.concatenate((sy, ty))
            weights = pooled_weights(len(sx), int(train.sum()))
        else:
            weights = uniform_weights(len(tx))
        prepared = problem(tx, ty, weights)
        for index, penalty in enumerate(LAMBDAS):
            model = solve(prepared, penalty)
            fits += 1
            residual = predict(model, x[valid]) - y[valid]
            error = float(np.mean(residual * residual))
            require(np.isfinite(error), 'Finite fixed-fold error')
            errors[fold - 1, index] = error
            emit({'phase': 'cv_fit_completed', 'regime': regime, 'fold': fold,
                  'lambda': penalty, 'validation_mse': error, 'regime_fits_completed': fits})
        folds.append({'fold': fold, 'within_day_training_endpoint_range': [10, end],
                      'validation_endpoint_range': [end + 10, end + width],
                      'within_day_train_rows': int(train.sum()), 'validation_rows': int(valid.sum()),
                      'source_rows_additionally_available': len(sx) if regime == 'balanced_pooled' else 0})
    penalty, averages = choose_penalty(errors)
    if regime == 'source_only':
        tx, ty, weights = sx, sy, uniform_weights(len(sx))
    elif regime == 'calibration_only':
        tx, ty, weights = cx, cy, uniform_weights(len(cx))
    else:
        tx, ty = np.concatenate((sx, cx)), np.concatenate((sy, cy))
        weights = pooled_weights(len(sx), len(cx))
    model = solve(problem(tx, ty, weights), penalty)
    fits += 1
    emit({'phase': 'final_fit_completed', 'regime': regime, 'lambda': penalty,
          'training_rows': len(tx), 'regime_fits_completed': fits})
    return model, {'regime': regime, 'folds': folds, 'lambda_candidates': list(LAMBDAS),
                   'fold_mse': errors.tolist(), 'mean_fold_mse': averages.tolist(),
                   'selected_lambda': penalty, 'coefficient_fits': fits}


def panel(source, calibration, query_x, emit):
    sx, sy, sid = source
    cx, cy, cid = calibration
    require(sx.shape == (18691, 960) and sy.shape == (18691, 2) and
            cx.shape == (2991, 960) and cy.shape == (2991, 2) and query_x.shape == (22091, 960),
            'Exact complete fixed source/calibration/assessment observations')
    require(np.array_equal(sid, np.arange(10, 18701)) and np.array_equal(cid, np.arange(10, 3001)),
            'Fixed source-order endpoint identities')
    models, selections = {}, []
    for regime in REGIMES:
        models[regime], selected = select_and_fit(regime, source, calibration, emit)
        selections.append(selected)
    output = {'zero_velocity': np.zeros((22091, 2), dtype=np.float64),
              'source_mean_velocity': np.tile(sy.mean(axis=0), (22091, 1)),
              'calibration_mean_velocity': np.tile(cy.mean(axis=0), (22091, 1))}
    output['source_only_ridge'] = predict(models['source_only'], query_x)
    offset = (cy - predict(models['source_only'], cx)).mean(axis=0)
    output['source_only_ridge_plus_calibration_mean_residual'] = output['source_only_ridge'] + offset
    output['calibration_only_ridge'] = predict(models['calibration_only'], query_x)
    output['balanced_pooled_ridge'] = predict(models['balanced_pooled'], query_x)
    require(set(output) == set(ARMS) and all(np.isfinite(v).all() for v in output.values()),
            'All seven frozen finite streams retained')
    require(sum(x['coefficient_fits'] for x in selections) == 51, 'Exactly the frozen 51 coefficient fits')
    return output, {'selections': selections, 'source_offset_m_s': offset.tolist(),
                    'coefficient_fit_count': 51, 'assessment_labels_read': False}, models
