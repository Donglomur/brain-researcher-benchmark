"""DEVCONN array-only direct operators; no source I/O or Nilearn imports.

Sphere/detrend/reduction mechanics adapt qualified PR198 source_numerics
393116d935d5d84530641db07343ae0320a3b609122b3c5c78e53b2138787059.
This task has 5-mm spheres, 14 nuisances, Butterworth filtering and NO GS/template.
NumPy/SciPy/sklearn and the authenticated activity callback are disclosed shared
primitives. The caller authenticates/scales source data and orders nuisance columns.
"""
import hashlib
import math

import numpy as np
from scipy import linalg, signal
from sklearn.neighbors import NearestNeighbors
from sklearn.utils import gen_even_slices

EPS = np.finfo(np.float64).eps
TR_SECONDS = 2.0
HIGH_PASS_HZ = 0.009
LOW_PASS_HZ = 0.08
CONF_COLS = ("trans_x", "trans_y", "trans_z", "rot_x", "rot_y", "rot_z",
             "a_comp_cor_00", "a_comp_cor_01", "a_comp_cor_02", "a_comp_cor_03",
             "a_comp_cor_04", "a_comp_cor_05", "csf", "white_matter")


def _has_bool(value):
    if isinstance(value, (bool, np.bool_)):
        return True
    return isinstance(value, (tuple, list)) and any(_has_bool(item) for item in value)


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def real(value, ndim, *, finite=True, copy=True):
    require(not _has_bool(value), 'boolean_numeric_input')
    value = np.asarray(value)
    require(value.ndim == ndim and value.dtype.kind in 'iuf', 'real_array_shape_or_type')
    value = np.array(value, dtype=np.float64, order='C', copy=True) if copy else \
        np.asarray(value, dtype=np.float64, order='C')
    require(not finite or np.isfinite(value).all(), 'nonfinite_contributing_values')
    return value


def grid(shape, affine):
    require(len(shape) == 3 and all(isinstance(x, (int, np.integer)) and
            not isinstance(x, (bool, np.bool_)) and x > 0 for x in shape), 'grid_shape')
    affine = real(affine, 2)
    require(affine.shape == (4, 4) and np.array_equal(affine[3], [0., 0., 0., 1.]), 'affine_shape')
    require(np.isfinite(np.linalg.inv(affine)).all(), 'singular_or_nonfinite_affine')
    return tuple(int(x) for x in shape), affine


def sphere_supports(shape, affine, centers, radius=5.0):
    """Full-grid sklearn radius graph plus both published seed-voxel additions."""
    shape, affine = grid(shape, affine)
    centers = real(centers, 2)
    require(centers.shape[0] > 0 and centers.shape[1] == 3, 'sphere_centers')
    require(not isinstance(radius, (bool, np.bool_)) and isinstance(radius, (int, float, np.integer, np.floating))
            and np.isfinite(radius) and radius >= 0, 'sphere_radius')
    coordinates = np.indices(shape).reshape(3, -1)
    # Same affine multiplication/coordinate ordering as coord_transform.
    homogeneous = np.c_[coordinates.T, np.ones_like(coordinates[0])].T
    world = np.dot(affine, homogeneous)[:3].T
    require(np.isfinite(world).all(), 'world_coordinate_overflow')
    graph = NearestNeighbors(radius=float(radius)).fit(world).radius_neighbors_graph(centers).tolil()
    inverse = np.linalg.inv(affine)
    integer_limit = np.iinfo(np.int64).max
    require(np.max(np.abs(world)) < integer_limit and np.max(np.abs(centers)) < integer_limit,
            'integer_world_coordinate_range')
    integer_world = world.astype(int)
    for row, seed in enumerate(centers):
        nearest = np.round(np.dot(inverse, np.r_[seed, 1.][:, np.newaxis])[:3, 0])
        if np.all(nearest >= 0) and np.all(nearest < shape):
            graph[row, np.ravel_multi_index(tuple(nearest.astype(int)), shape)] = True
        # astype(int) truncates toward zero; use the first matching C-grid voxel.
        match = np.flatnonzero(np.all(integer_world == seed.astype(int), axis=1))
        if match.size:
            graph[row, int(match[0])] = True
    supports = [np.asarray(sorted(row), dtype=np.int64) for row in graph.rows]
    require(all(row.size > 0 for row in supports), 'empty_sphere_support')
    return supports


def detrend(values):
    """Literal C-float64 0.12.1 column detrend and one/ten batching convention."""
    output = real(values, 2)
    require(output.shape[0] >= 2, 'at_least_two_frames')
    output -= np.mean(output, axis=0)
    trend = np.arange(output.shape[0], dtype=output.dtype)
    trend -= trend.mean()
    length = np.sqrt((trend ** 2).sum())
    if not length < EPS:
        trend /= length
    trend = trend[:, np.newaxis]
    batches = 1 if output.shape[1] < 500 else 10
    for section in gen_even_slices(output.shape[1], batches):
        output[:, section] -= np.dot(trend[:, 0], output[:, section]) * trend
    require(np.isfinite(output).all(), 'detrend_nonfinite')
    return output


def checked_support(indices, count):
    require(not _has_bool(indices), 'support_type_or_empty')
    indices = np.asarray(indices)
    require(indices.ndim == 1 and indices.dtype.kind in 'iu' and indices.size > 0,
            'support_type_or_empty')
    require(np.all(indices < count) and np.all(indices >= 0) and
            np.all(indices[1:] > indices[:-1]), 'support_order_or_range')
    return indices.astype(np.int64)


def extract_raw(scaled_bold, roi_supports):
    """Means of ascending-C support voxels, framewise contiguous float64 rows.

    Input values are already header-scaled float64 from an authenticated decoder.
    Nonfinite values outside every sphere are ignored, never imputed or required.
    Every supplied support must be nonempty even if its later signal is inactive.
    """
    data = real(scaled_bold, 4, finite=False, copy=False)
    require(data.shape[3] >= 2 and len(roi_supports) > 0, 'source_frames_or_rois')
    flat = data.reshape(-1, data.shape[3], order='C')
    rois = [checked_support(x, flat.shape[0]) for x in roi_supports]
    union = np.unique(np.concatenate(rois))
    require(np.isfinite(flat[union]).all(), 'nonfinite_contributing_values')
    raw = np.empty((data.shape[3], len(rois)), dtype=np.float64)
    for column, support in enumerate(rois):
        voxel_rows = np.ascontiguousarray(flat[support].T, dtype=np.float64)
        raw[:, column] = [np.mean(row, dtype=np.float64) for row in voxel_rows]
    require(np.isfinite(raw).all(), 'source_reduction_nonfinite')
    return raw


def bandpass(values):
    """Literal 0.12.1 copy=False column loop, order5 SOS, odd/default padding."""
    result = real(values, 2)
    require(result.shape[0] >= 2 and result.shape[1] > 0, 'filter_shape')
    sos = signal.butter(5, [HIGH_PASS_HZ, LOW_PASS_HZ], btype='band',
                        output='sos', fs=1.0 / TR_SECONDS)
    for column in result.T:
        column[:] = signal.sosfiltfilt(sos, column, padtype='odd', padlen=None)
    require(np.isfinite(result).all(), 'filter_nonfinite')
    return result


def centered_norm(value):
    """Diagnostic stable norm; the callback, never this restored value, gates activity."""
    value = real(value, 1)
    if np.all(value == value[0]):
        return 0.0
    scale = float(np.max(np.abs(value)))
    center = value / scale
    center -= math.fsum(float(x) for x in center) / center.size
    maximum = float(np.max(np.abs(center)))
    if maximum == 0:
        return 0.0
    unit = center / maximum
    length = math.sqrt(math.fsum(float(x) * float(x) for x in unit))
    a, ea = math.frexp(scale)
    b, eb = math.frexp(maximum)
    c, ec = math.frexp(length)
    try:
        result = math.ldexp(a * b * c, ea + eb + ec)
    except OverflowError as exc:
        raise ValueError('diagnostic_norm_unrepresentable') from exc
    require(math.isfinite(result), 'diagnostic_norm_unrepresentable')
    return result


def clean_roi(raw_roi, nuisance, *, activity_fn):
    """Demean/detrend both -> bandpass both -> pop-standard nuisance -> QR.

    Fourteen columns in CONF_COLS order are mandatory; FD is NOT regressed.
    The public projection association is (Q @ Q.T) @ Y. Activity uses raw and
    prestandardization residual directions before sample-zscore's eps floor.
    """
    raw, confounds = real(raw_roi, 2), real(nuisance, 2)
    require(raw.shape[0] == confounds.shape[0] and raw.shape[1] > 0
            and confounds.shape[1] == len(CONF_COLS), 'clean_shape_or_confound_count')
    require(callable(activity_fn), 'activity_callback_required')
    filtered = bandpass(detrend(raw))
    confounds = bandpass(detrend(confounds))
    confounds = confounds - confounds.mean(axis=0)
    confound_sd = confounds.std(axis=0)
    confound_sd[confound_sd < EPS] = 1.0
    confounds /= confound_sd
    require(np.isfinite(confounds).all(), 'standardized_confound_nonfinite')
    q, triangular, pivots = linalg.qr(confounds, mode='economic', pivoting=True)
    keep = np.abs(np.diag(triangular)) > EPS * 100.0
    q = q[:, keep]
    residual = filtered - q.dot(q.T).dot(filtered)
    require(np.isfinite(residual).all(), 'clean_nonfinite')
    flags = [activity_fn(residual[:, i], raw[:, i]) for i in range(raw.shape[1])]
    require(all(type(value) is bool for value in flags), 'activity_callback_bool')
    active = np.asarray(flags, dtype=bool)
    centered = residual - residual.mean(axis=0)
    sample_sd = centered.std(axis=0, ddof=1)
    denominator = sample_sd.copy()
    denominator[denominator < EPS] = 1.0
    cleaned = centered / denominator
    require(np.isfinite(cleaned).all(), 'clean_nonfinite')
    cleaned[:, ~active] = 0.0
    raw_norm = np.asarray([centered_norm(raw[:, i]) for i in range(raw.shape[1])])
    residual_norm = np.asarray([centered_norm(residual[:, i]) for i in range(raw.shape[1])])
    return dict(cleaned=cleaned, residual=residual, active=active, rank=int(keep.sum()),
                pivots=np.asarray(pivots, dtype=np.int64), sample_sd=sample_sd,
                standardization_denominator=denominator, raw_centered_l2=raw_norm,
                residual_centered_l2=residual_norm, activity_threshold=1e-12 * raw_norm)


def support_digest(shape, affine, indices):
    shape, affine = grid(shape, affine)
    indices = checked_support(indices, math.prod(shape))
    affine[affine == 0.] = 0.  # Normalize negative zero without changing input.
    return hashlib.sha256(b'DEVCONN_support_v2\n' + np.asarray(shape, dtype='<i8').tobytes() +
        np.asarray(affine, dtype='<f8', order='C').tobytes(order='C') +
        np.asarray(indices, dtype='<i8').tobytes()).hexdigest()
