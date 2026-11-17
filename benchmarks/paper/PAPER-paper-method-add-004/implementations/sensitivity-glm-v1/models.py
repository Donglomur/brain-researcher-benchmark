"""Balanced Figure 7C Gaussian random-unit-intercept REML calculations.

The source's method-by-covariate interactions give each method the same three
unit-level predictors. Complete paired support makes the fixed effects exactly
multivariate least squares. This specialization is not a general mixed model.
NumPy is loaded only when a numerical function is called.
"""
import math
import random
import hashlib
import json
import sys


METHODS = ('acf_full', 'isttc_full', 'pearsonr_trial_avg', 'sttc_trial_concat')


def _arrays(responses, covariates, mice, methods):
    import numpy as np
    if tuple(methods) not in (METHODS, METHODS[2:]):
        raise ValueError('only the two complete Figure 7C method panels are supported')
    y0, x0 = np.asarray(responses), np.asarray(covariates)
    if y0.dtype.kind not in 'iuf' or x0.dtype.kind not in 'iuf':
        raise ValueError('finite real numerical arrays required; booleans are not numbers')
    y, x = y0.astype(float), x0.astype(float)
    if y.ndim != 2 or y.shape[1] != len(methods) or x.shape != (len(y), 2) or len(y) <= 3:
        raise ValueError('complete paired methods and two covariates with more than three units required')
    if not np.isfinite(y).all() or not np.isfinite(x).all():
        raise ValueError('nonfinite response or covariate')
    if (len(mice) != len(y) or any(type(m) is not str or not m or len(m) > 128 for m in mice)):
        raise ValueError('one nonempty biological mouse identity per unit required')
    # R scale() uses sample SD over the expanded long model table. Every unit
    # occurs K times, so this is neither ddof=0 nor the unique-unit sample SD.
    n, k = y.shape
    magnitude = np.max(np.abs(x), axis=0)
    if (magnitude == 0).any():
        raise ValueError('covariates require nonzero sample SD')
    normalized = x / magnitude
    normalized_center = normalized.mean(axis=0)
    deviations = normalized - normalized_center
    normalized_scales = np.sqrt((deviations * deviations).sum(axis=0) * k / (n * k - 1))
    center = normalized_center * magnitude
    scales = normalized_scales * magnitude
    if not np.isfinite(center).all() or not np.isfinite(scales).all() or (scales <= 0).any():
        raise ValueError('covariates require finite, nonzero long-table sample SD')
    z = np.column_stack((np.ones(n), deviations / normalized_scales))
    if not np.isfinite(z).all():
        raise ValueError('nonfinite scaled design')
    return np, y, z, center, scales


def _treatment_matrix(np, methods):
    """Transform method-major [intercept, FR, Lv] coefficients into R coding."""
    k = len(methods)
    names = ['(Intercept)'] + ['method' + m for m in methods[1:]] + ['fr_s', 'alpha_s']
    names += ['method' + m + ':fr_s' for m in methods[1:]]
    names += ['method' + m + ':alpha_s' for m in methods[1:]]
    transform = np.zeros((3 * k, 3 * k))
    transform[0, 0] = 1
    row = 1
    for method in range(1, k):
        transform[row, 3 * method] = 1
        transform[row, 0] = -1
        row += 1
    for predictor in (1, 2):
        transform[row, predictor] = 1
        row += 1
    for predictor in (1, 2):
        for method in range(1, k):
            transform[row, 3 * method + predictor] = 1
            transform[row, predictor] = -1
            row += 1
    return names, transform


def balanced_reml(responses, covariates, mouse_ids, methods):
    """Fit the balanced source model and a separate mouse-cluster diagnostic.

    Responses are already log10(tau_ms) or log10(pseudo-REE percent). No log
    clipping, imputation, row selection or source p-values happen in this core.
    The caller owns complete-cohort admission and common paired eligibility.
    """
    np, y, z, center, scales = _arrays(responses, covariates, mouse_ids, methods)
    n, k = y.shape
    beta, _, rank, singular = np.linalg.lstsq(z, y, rcond=None)
    if rank != 3 or not np.isfinite(beta).all():
        raise ValueError('rank-deficient or unrepresentable fixed-effect design')
    residual = y - z @ beta
    common = residual.sum(axis=1) / math.sqrt(k)
    within = residual - residual.mean(axis=1, keepdims=True)
    common_variance = float(common @ common / (n - 3))
    within_variance = float((within * within).sum() / ((n - 3) * (k - 1)))
    if not math.isfinite(common_variance) or not math.isfinite(within_variance):
        raise ValueError('residual variance is not representable')
    if ((common_variance == 0 and np.any(common != 0)) or
            (within_variance == 0 and np.any(within != 0))):
        raise ValueError('positive residual variance underflows the numerical representation')
    # REML residual contrasts have N-3 degrees of freedom per method. The
    # compound-symmetry covariance has one common and K-1 within eigenvalues.
    boundary = common_variance < within_variance
    if boundary:
        residual_variance = (common_variance + (k - 1) * within_variance) / k
        unit_variance = 0.0
    else:
        residual_variance = within_variance
        unit_variance = (common_variance - within_variance) / k
    names, transform = _treatment_matrix(np, methods)
    coefficients = transform @ beta.T.reshape(-1)
    if not np.isfinite(coefficients).all():
        raise ValueError('unrepresentable treatment-coded coefficients')
    # QR-based inverse avoids squaring the design's condition number in an
    # explicit inverse of Z'Z. Rank has already been checked by least squares.
    _, r = np.linalg.qr(z, mode='reduced')
    inv_r = np.linalg.solve(r, np.eye(3))
    inverse_crossproduct = inv_r @ inv_r.T
    mice = tuple(dict.fromkeys(mouse_ids))
    grouped = {mouse: np.zeros(3 * k) for mouse in mice}
    for i, mouse in enumerate(mouse_ids):
        leverage = inverse_crossproduct @ z[i]
        grouped[mouse] += (residual[i, :, None] * leverage[None, :]).reshape(-1)
    cluster = {'kind': 'prospective_mouse_cluster_CR1', 'mouse_count': len(mice),
               'unit_count': n, 'long_row_count': n * k, 'fixed_parameters': 3 * k,
               'source_lmerTest_inference': False, 'coverage_qualified': False}
    if len(mice) < 2:
        cluster.update(status='unavailable', reason='fewer_than_two_biological_mice',
                       covariance=None, standard_errors=None, covariance_rank=None)
    else:
        score = np.asarray(list(grouped.values())) @ transform.T
        correction = len(mice) / (len(mice) - 1) * (n * k - 1) / (n * k - 3 * k)
        covariance = (score.T @ score) * correction
        if not np.isfinite(covariance).all():
            raise ValueError('unrepresentable mouse-cluster covariance')
        underflow = np.any(score != 0, axis=0) & (np.diag(covariance) == 0)
        if underflow.any():
            cluster.update(status='unavailable', reason='positive_covariance_underflow',
                           affected_coefficients=[names[i] for i in np.flatnonzero(underflow)],
                           covariance=None, standard_errors=None, covariance_rank=None)
        else:
            cluster.update(status='available', correction=correction,
                           correction_definition='G/(G-1)*(N_long-1)/(N_long-P_fixed)',
                           covariance=covariance.tolist(),
                           standard_errors=np.sqrt(np.maximum(0, np.diag(covariance))).tolist(),
                           covariance_rank=int(np.linalg.matrix_rank(covariance)))
    return {'schema': 'isttc_balanced_fig7c_reml_v1', 'methods': list(methods),
            'unit_count': n, 'random_effect_group': 'unit_id',
            'coefficient_names': names, 'coefficients': coefficients.tolist(),
            'method_coefficients': beta.T.tolist(),
            'covariate_center': center.tolist(), 'covariate_long_table_sample_sd': scales.tolist(),
            'residual_variance': residual_variance, 'unit_intercept_variance': unit_variance,
            'variance_boundary': boundary or unit_variance == 0,
            'degenerate_zero_residual_variance': residual_variance == 0,
            'finite_nonsingular_gaussian_fit': residual_variance > 0,
            'fixed_design_rank': int(rank), 'fixed_design_condition_number': float(singular[0] / singular[-1]),
            'mouse_cluster_diagnostic': cluster,
            'source_p_values': None, 'source_profile_confidence_intervals': None,
            'runtime': {'python': sys.version, 'numpy': np.__version__},
            'native_lme4_parity_qualified': False, 'scientifically_qualified': False}


def mouse_bootstrap(responses, covariates, mouse_ids, methods, *, seed, repetitions):
    """Prospective percentile intervals for fixed effects, resampling mice.

    Covariate scaling remains fixed to the admitted original model table, so
    every draw estimates coefficients on the same axes. Failed draws remain in
    the denominator and suppress every interval; they are never redrawn.
    """
    if type(seed) is not int or not 0 <= seed < 2**64:
        raise ValueError('bootstrap seed must be uint64')
    if type(repetitions) is not int or not 2 <= repetitions <= 10000:
        raise ValueError('bootstrap repetitions must be an integer from 2 through 10000')
    np, y, z, center, scales = _arrays(responses, covariates, mouse_ids, methods)
    # Refuse a deficient primary table even if a random resample might differ.
    if np.linalg.matrix_rank(z) != 3:
        raise ValueError('rank-deficient primary fixed-effect design')
    mice = tuple(dict.fromkeys(mouse_ids))
    names, transform = _treatment_matrix(np, methods)
    if len(mice) < 2:
        return {'status': 'unavailable', 'reason': 'fewer_than_two_biological_mice',
                'repetitions': repetitions, 'seed': seed, 'intervals': None}
    blocks = []
    for mouse in mice:
        selection = np.asarray([m == mouse for m in mouse_ids])
        # QR represents all rows of a mouse without forming normal equations.
        q, r = np.linalg.qr(z[selection], mode='reduced')
        blocks.append((r, q.T @ y[selection]))
    rng, samples, failures, draws = random.Random(seed), [], [], []
    for iteration in range(repetitions):
        chosen = [rng.randrange(len(mice)) for _ in mice]
        draws.append(chosen)
        zz = np.concatenate([blocks[i][0] for i in chosen], axis=0)
        yy = np.concatenate([blocks[i][1] for i in chosen], axis=0)
        beta, _, rank, _ = np.linalg.lstsq(zz, yy, rcond=None)
        values = transform @ beta.T.reshape(-1)
        if rank != 3 or not np.isfinite(values).all():
            failures.append({'replicate': iteration, 'reason': 'rank_deficient_or_unrepresentable'})
            samples.append(None)
        else:
            samples.append(values.tolist())
    intervals = None
    if not failures:
        quantiles = np.quantile(np.asarray(samples), [0.025, 0.975], axis=0, method='linear')
        intervals = {name: quantiles[:, j].tolist() for j, name in enumerate(names)}
    return {'status': 'complete' if not failures else 'incomplete_support',
            'kind': 'prospective_mouse_cluster_percentile_fixed_effects',
            'seed': seed, 'repetitions': repetitions, 'mouse_ids': list(mice),
            'sampled_mouse_indices': draws, 'coefficient_names': names,
            'sampled_indices_sha256': hashlib.sha256(json.dumps(draws, separators=(',', ':')).encode()).hexdigest(),
            'rng': 'Python random.Random(seed).randrange(G)',
            'mouse_order': 'first occurrence in retained source-model units',
            'runtime': {'python': sys.version, 'numpy': np.__version__},
            'fixed_covariate_center': center.tolist(),
            'fixed_covariate_long_table_sample_sd': scales.tolist(),
            'failed_replicates': failures, 'coefficient_samples': samples,
            'intervals': intervals, 'quantiles': [0.025, 0.975], 'quantile_method': 'linear',
            'coverage_qualified': False, 'source_lmerTest_inference': False}
