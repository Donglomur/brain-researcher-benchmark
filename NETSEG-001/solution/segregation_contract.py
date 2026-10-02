"""Import-safe float64 reference numerics; no source IO or verifier imports.

SciPy pivoted QR and NumPy reductions are shared numerical libraries, not an
independent implementation of those libraries. This module does not fetch data.
"""
import math

import numpy as np
from scipy import linalg

EPS64 = np.finfo(np.float64).eps
FISHER_CLIP = 0.999999
RESIDUAL_SD_FACTOR = 1e-12


class PreconditionError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise PreconditionError(message)


def finite_array(value, ndim, name):
    array = np.asarray(value, dtype=np.float64)
    require(array.ndim == ndim and array.size > 0, name + ': invalid dimensions or empty')
    require(np.isfinite(array).all(), name + ': nonfinite values')
    return array


def center_columns(value):
    """Exact constants stay zero rather than acquiring decimal mean roundoff."""
    array = finite_array(value, 2, 'columns')
    centered = array - array.mean(axis=0)
    centered[:, np.all(array == array[0], axis=0)] = 0.0
    return centered


def linear_detrend(value):
    array = finite_array(value, 2, 'detrend input')
    require(array.shape[0] >= 2, 'detrending requires at least two frames')
    centered = center_columns(array)
    trend = np.arange(array.shape[0], dtype=np.float64)
    trend -= trend.mean()
    trend /= np.sqrt(np.dot(trend, trend))
    result = centered - trend[:, None] * (trend @ centered)[None, :]
    require(np.isfinite(result).all(), 'nonfinite detrended values')
    return result


def clean_parcels(raw_parcel, confounds):
    """Demean/detrend, standardized confound QR span, sample-SD residuals."""
    raw = finite_array(raw_parcel, 2, 'raw parcel means')
    nuisance = finite_array(confounds, 2, 'confounds')
    require(raw.shape[0] == nuisance.shape[0] and raw.shape[0] >= 3, 'frame mismatch or too few frames')
    raw_sd = np.sqrt(np.sum(center_columns(raw) ** 2, axis=0) / (raw.shape[0] - 1))
    detrended = linear_detrend(raw)
    nuisance_detrended = linear_detrend(nuisance)
    nuisance_centered = center_columns(nuisance_detrended)
    nuisance_sd = nuisance_centered.std(axis=0, ddof=0)
    divisor = np.where(nuisance_sd < EPS64, 1.0, nuisance_sd)
    nuisance_standardized = nuisance_centered / divisor
    q, r, pivots = linalg.qr(nuisance_standardized, mode='economic', pivoting=True, check_finite=True)
    diagonal = np.abs(np.diag(r))
    retained = diagonal > 100.0 * EPS64
    basis = q[:, retained]
    residual = detrended - basis @ (basis.T @ detrended)
    residual_centered = center_columns(residual)
    residual_sd = residual_centered.std(axis=0, ddof=1)
    lower_bound = RESIDUAL_SD_FACTOR * np.maximum(1.0, raw_sd)
    require(np.isfinite(raw_sd).all() and np.isfinite(residual_sd).all(), 'nonfinite signal SD')
    invalid = np.flatnonzero(residual_sd <= lower_bound)
    require(not len(invalid), 'residual SD precondition failed for parcel columns ' + repr(invalid.tolist()))
    cleaned = residual_centered / residual_sd
    require(np.isfinite(cleaned).all(), 'nonfinite standardized residuals')
    return {'cleaned': cleaned, 'raw_sd': raw_sd, 'residual_sd': residual_sd,
            'residual_sd_lower_bound': lower_bound, 'nuisance_rank': int(retained.sum()),
            'nuisance_qr_diagonal': diagonal, 'nuisance_qr_pivots': pivots,
            'nuisance_retained': retained, 'nuisance_sd': nuisance_sd,
            'detrended_parcel': detrended, 'detrended_confounds': nuisance_detrended,
            'standardized_confounds': nuisance_standardized, 'residual_centered': residual_centered}


def affine_matrix(value, name):
    matrix = finite_array(value, 2, name)
    require(matrix.shape == (4, 4) and np.array_equal(matrix[3], [0, 0, 0, 1]), name + ': invalid affine')
    require(np.linalg.matrix_rank(matrix[:3, :3]) == 3, name + ': singular affine')
    return matrix


def integer_ids(value, name):
    raw = np.asarray(value)
    require(raw.ndim == 1 and raw.size > 0 and raw.dtype.kind in 'iu', name + ': integer axis required')
    require(len(set(raw.tolist())) == raw.size, name + ': duplicate identities')
    return raw.astype(np.int64)


def nearest_labels(atlas, atlas_affine, target_shape, target_affine):
    """Identity-world order-0 constant sampling: valid [0,n-1], floor(x+.5)."""
    labels = finite_array(atlas, 3, 'atlas labels')
    require(np.equal(labels, np.floor(labels)).all() and np.all(labels >= 0), 'atlas labels must be nonnegative integers')
    shape = tuple(target_shape)
    require(len(shape) == 3 and all(type(n) in {int, np.int64, np.int32} and n > 0 for n in shape),
            'invalid target grid shape')
    source = affine_matrix(atlas_affine, 'atlas affine')
    destination = affine_matrix(target_affine, 'BOLD affine')
    transform = np.linalg.solve(source, destination)
    ijk = np.indices(shape, dtype=np.float64).reshape(3, -1)
    coordinates = transform[:3, :3] @ ijk + transform[:3, 3, None]
    require(np.isfinite(coordinates).all(), 'nonfinite transformed coordinates')
    valid = np.all((coordinates >= 0.0) & (coordinates <= np.asarray(labels.shape)[:, None] - 1), axis=0)
    output = np.zeros(ijk.shape[1], dtype=np.int64)
    selected = np.floor(coordinates[:, valid] + 0.5).astype(np.int64)
    output[valid] = labels[tuple(selected)].astype(np.int64)
    return output.reshape(shape)


def parcel_means(scaled_bold, label_grid, roi_ids):
    """All finite, scaled source voxels count; no signal-dependent mask."""
    data = finite_array(scaled_bold, 4, 'scaled BOLD')
    labels = np.asarray(label_grid)
    ids = integer_ids(roi_ids, 'parcel IDs')
    require(labels.shape == data.shape[:3] and labels.dtype.kind in 'iu', 'label grid mismatch')
    require(np.all(ids > 0), 'background cannot be a parcel')
    require(set(np.unique(labels)) <= {0, *ids.tolist()}, 'unknown grid label')
    counts = np.asarray([np.count_nonzero(labels == roi) for roi in ids], dtype=np.int64)
    require(np.all(counts > 0), 'absent transferred parcel')
    means = np.column_stack([data[labels == roi, :].mean(axis=0, dtype=np.float64) for roi in ids])
    require(np.isfinite(means).all(), 'nonfinite parcel reduction')
    return means, counts


def edge_connectivity(cleaned, roi_ids):
    series = finite_array(cleaned, 2, 'cleaned series')
    ids = integer_ids(roi_ids, 'parcel IDs')
    require(series.shape[1] == len(ids) and len(ids) >= 2 and series.shape[0] >= 2, 'connectivity axis mismatch')
    centered = center_columns(series)
    norms = np.sqrt(np.sum(centered ** 2, axis=0))
    require(np.isfinite(norms).all() and np.all(norms > 0), 'constant or nonfinite correlation input')
    matrix = (centered.T @ centered) / np.outer(norms, norms)
    require(np.isfinite(matrix).all() and np.all(np.abs(matrix) <= 1.0 + 1e-12), 'invalid Pearson correlation')
    matrix = np.clip(matrix, -1.0, 1.0)
    i, j = np.triu_indices(len(ids), k=1)
    r = matrix[i, j]
    z = np.arctanh(np.clip(r, -FISHER_CLIP, FISHER_CLIP))
    return {'edge_roi_i': ids[i], 'edge_roi_j': ids[j], 'pearson_r': r,
            'fisher_z': z, 'positive_z': np.maximum(z, 0.0)}


def segregation_edges(fisher_z, roi_ids, networks, edge_roi_i, edge_roi_j):
    ids = integer_ids(roi_ids, 'parcel IDs')
    labels = np.asarray(networks, dtype=str)
    require(labels.shape == ids.shape and np.all(labels != ''), 'network axis mismatch')
    z = finite_array(fisher_z, 1, 'Fisher-z edges')
    i, j = np.asarray(edge_roi_i), np.asarray(edge_roi_j)
    require(i.dtype.kind in 'iu' and j.dtype.kind in 'iu' and i.shape == j.shape == z.shape, 'edge axis mismatch')
    expected = {frozenset((int(a), int(b))) for k, a in enumerate(ids) for b in ids[k + 1:]}
    actual = [frozenset((int(a), int(b))) for a, b in zip(i, j)]
    require(len(actual) == len(expected) and set(actual) == expected, 'missing, duplicate or unexpected pair')
    group = dict(zip(ids.tolist(), labels.tolist()))
    within = np.asarray([group[int(a)] == group[int(b)] for a, b in zip(i, j)], dtype=bool)
    require(within.any() and (~within).any(), 'both within and between support required')
    positive = np.maximum(z, 0.0)
    n_within, n_between = int(within.sum()), int((~within).sum())
    within_sum = float(positive[within].sum(dtype=np.float64))
    between_sum = float(positive[~within].sum(dtype=np.float64))
    w, b = within_sum / n_within, between_sum / n_between
    require(all(math.isfinite(x) for x in (within_sum, between_sum, w, b)), 'nonfinite complete-pair reduction')
    value = None if w == 0 else (w - b) / w
    require(value is None or math.isfinite(value), 'nonfinite segregation')
    return {'n_within_pairs': n_within, 'n_between_pairs': n_between, 'within_sum': within_sum,
            'between_sum': between_sum, 'mean_within': w, 'mean_between': b, 'numerator': w - b,
            'segregation': value, 'status': 'zero_within_mean' if value is None else 'ok'}


def complete_summary(values):
    """Never silently switch the estimand to an available-case subset."""
    values = list(values)
    require(values, 'empty summary cohort')
    require(all(x is None or (type(x) in {int, float} and math.isfinite(x)) for x in values), 'invalid summary value')
    n_defined = sum(x is not None for x in values)
    if n_defined != len(values):
        return {'n': len(values), 'n_defined': n_defined, 'n_undefined': len(values) - n_defined,
                'mean': None, 'sample_variance': None,
                'status': 'undefined_member'}
    array = np.asarray(values, dtype=np.float64)
    constant = bool(np.all(array == array[0]))
    mean = float(array[0]) if constant else float(array.mean())
    variance = None if len(array) < 2 else (0.0 if constant else float(array.var(ddof=1)))
    return {'n': len(values), 'n_defined': n_defined, 'n_undefined': 0,
            'mean': mean, 'sample_variance': variance, 'status': 'ok'}


def cohort_summary(values, groups):
    values, groups = list(values), list(groups)
    require(len(values) == len(groups) and set(groups) == {'child', 'adult'}, 'invalid age-group membership')
    summaries = {name: complete_summary([x for x, g in zip(values, groups) if g == name])
                 for name in ('child', 'adult')}
    all_people = complete_summary(values)
    child, adult = summaries['child'], summaries['adult']
    contrast = {'status': 'undefined_member', 'estimate': None, 'se': None, 'ci95': None}
    if child['status'] == adult['status'] == 'ok' and child['sample_variance'] is not None and adult['sample_variance'] is not None:
        difference = adult['mean'] - child['mean']
        se = math.sqrt(adult['sample_variance'] / adult['n'] + child['sample_variance'] / child['n'])
        contrast = {'status': 'ok', 'estimate': difference, 'se': se,
                    'ci95': [difference - 1.96 * se, difference + 1.96 * se]}
    return {'cohort': all_people, 'groups': summaries, 'adult_minus_child': contrast}
