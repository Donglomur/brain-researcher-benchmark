"""Array-only SOCIALBRAIN source operators, independently composed from 0.12.1.

No filesystem, template discovery, Nilearn/oracle imports, source authentication,
or cohort statistics. Caller supplies authenticated scaled arrays/affines and
the authenticated public residual_active callback. Shared NumPy/SciPy/sklearn
primitives and that conditioning rule are disclosed, not independent libraries.
"""
import hashlib
import math

import numpy as np
from scipy import linalg, ndimage
from sklearn.neighbors import NearestNeighbors
from sklearn.utils import gen_even_slices

EPS = np.finfo(np.float64).eps


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def real(value, ndim, *, finite=True, copy=True):
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


def sphere_supports(shape, affine, centers, radius=9.0):
    """Full-grid sklearn radius graph plus both published seed-voxel additions."""
    shape, affine = grid(shape, affine)
    centers = real(centers, 2)
    require(centers.shape[0] > 0 and centers.shape[1] == 3, 'sphere_centers')
    require(not isinstance(radius, (bool, np.bool_)) and np.isfinite(radius) and radius >= 0, 'sphere_radius')
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


def normalize_template(template):
    """Preserve loader's float32 cast/global-max division; never find a template."""
    values = np.asarray(template)
    require(values.ndim == 3 and values.dtype.kind in 'iuf', 'template_shape_or_type')
    values = values.astype(np.float32, copy=True)
    require(np.isfinite(values).all() and values.size > 0, 'template_nonfinite')
    maximum = values.max()
    require(maximum > 0, 'template_positive_maximum')
    values /= maximum
    require(np.isfinite(values).all(), 'template_normalization_nonfinite')
    return values, float(maximum)


def resample_template(normalized, source_affine, target_shape, target_affine):
    """Explicit reached resample_to_img branches: F-float32, cubic, no clipping.

    The allclose-affine/equal-shape no-op and integer-translation crop/padding
    branch are retained literally, including the upstream cropped-subset rule.
    """
    values = np.asarray(normalized)
    require(values.ndim == 3 and values.dtype == np.dtype('float32') and np.isfinite(values).all(),
            'normalized_template_float32')
    source_shape, source_affine = grid(values.shape, source_affine)
    target_shape, target_affine = grid(target_shape, target_affine)
    if source_shape == target_shape and np.allclose(target_affine, source_affine):
        return values.copy(), 'allclose_equal_shape_noop'
    a, b, c = np.asarray(source_shape) - 1
    corners = np.array([[0., 0, 0, 1], [a, 0, 0, 1], [0, b, 0, 1], [0, 0, c, 1],
                        [a, b, 0, 1], [a, 0, c, 1], [0, b, c, 1], [a, b, c, 1]]).T
    target_corners = np.dot(np.linalg.inv(target_affine).dot(source_affine), corners)[:3]
    require(np.all(target_corners.max(axis=-1) >= 0), 'template_outside_negative_fov')
    transform = np.eye(4) if np.all(target_affine == source_affine) else \
        np.dot(linalg.inv(source_affine), target_affine)
    matrix, offset = transform[:3, :3], transform[:3, 3]
    output = np.zeros(target_shape, dtype=np.float32, order='F')
    if np.all(matrix == np.eye(3)) and all(x == np.round(x) for x in offset):
        scale = max(-values.min(), values.max())
        occupied = np.array(np.where((values < -1e-8 * scale) | (values > 1e-8 * scale)))
        if occupied.shape[1]:
            start, stop = occupied.min(axis=1), occupied.max(axis=1) + 1
        else:
            start, stop = np.zeros(3, dtype=int), np.asarray(source_shape)
        cropped = values[tuple(slice(int(a), int(b)) for a, b in zip(start, stop))]
        ranges = [(int(a - shift), int(b - shift)) for a, b, shift in zip(start, stop, offset)]
        slices = tuple(slice(max(0, a), min(n, b)) for n, (a, b) in zip(target_shape, ranges))
        subset = tuple(slice(0, section.stop - section.start) for section in slices)
        output[slices] = cropped[subset]
        branch = 'integer_translation_crop_padding'
    else:
        diagonal = np.all(np.diag(np.diag(matrix)) == matrix)
        if diagonal:
            matrix = np.diag(matrix)
        ndimage.affine_transform(values, matrix, offset=offset, output_shape=target_shape,
                                 output=output, cval=0., order=3)
        branch = 'cubic_diagonal' if diagonal else 'cubic_full_matrix'
    require(np.isfinite(output).all(), 'resampled_template_nonfinite')
    return output, branch


def global_support(template, template_affine, target_shape, target_affine):
    normalized, maximum = normalize_template(template)
    sampled, branch = resample_template(normalized, template_affine, target_shape, target_affine)
    mask = ndimage.binary_erosion((sampled >= .5).astype(np.int8), iterations=2)
    if mask.any():
        labels, n_labels = ndimage.label(mask)
        if n_labels > 1:
            counts = np.bincount(labels.ravel().astype(int))
            counts[0] = 0
            mask = labels == counts.argmax()
        else:
            mask = mask.astype(bool)
    mask = ndimage.binary_dilation(mask, iterations=4)
    mask = ndimage.binary_erosion(mask, iterations=2)
    indices = np.flatnonzero(mask.ravel(order='C')).astype(np.int64)
    require(indices.size > 0, 'empty_global_support')
    return dict(indices=indices, mask=mask, resampled_template=sampled,
                normalization_maximum=maximum, resampling_branch=branch)


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
    indices = np.asarray(indices)
    require(indices.ndim == 1 and indices.dtype.kind in 'iu' and indices.size > 0,
            'support_type_or_empty')
    require(np.all(indices < count) and np.all(indices >= 0) and
            np.all(indices[1:] > indices[:-1]), 'support_order_or_range')
    return indices.astype(np.int64)


def extract_raw_and_gs(scaled_bold, roi_supports, gs_support):
    """Contributing voxels only: explicit contiguous float64 rows, no imputation."""
    data = real(scaled_bold, 4, finite=False, copy=False)
    require(data.shape[3] >= 2 and len(roi_supports) > 0, 'source_frames_or_rois')
    flat = data.reshape(-1, data.shape[3])
    rois = [checked_support(x, flat.shape[0]) for x in roi_supports]
    gs = checked_support(gs_support, flat.shape[0])
    union = np.unique(np.concatenate([*rois, gs]))
    require(np.isfinite(flat[union]).all(), 'nonfinite_contributing_values')
    raw = np.empty((data.shape[3], len(rois)), dtype=np.float64)
    for column, support in enumerate(rois):
        voxel_rows = np.ascontiguousarray(flat[support].T, dtype=np.float64)
        raw[:, column] = [np.mean(row, dtype=np.float64) for row in voxel_rows]
    voxel_rows = np.ascontiguousarray(flat[gs].T, dtype=np.float64)
    voxel_rows = detrend(voxel_rows)
    global_signal = np.asarray([np.mean(row, dtype=np.float64) for row in voxel_rows])
    require(np.isfinite(raw).all() and np.isfinite(global_signal).all(), 'source_reduction_nonfinite')
    return raw, global_signal


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
    """Fixed cleaning composition; callback is only shared residual_active(r,y)."""
    raw = real(raw_roi, 2)
    confounds = real(nuisance, 2)
    require(raw.shape[0] == confounds.shape[0] and raw.shape[1] > 0, 'clean_shape')
    require(callable(activity_fn), 'activity_callback_required')
    signal = detrend(raw)
    confounds = detrend(confounds)
    confounds = confounds - confounds.mean(axis=0)
    confound_sd = confounds.std(axis=0)
    confound_sd[confound_sd < EPS] = 1.
    confounds /= confound_sd
    require(np.isfinite(confounds).all(), 'standardized_confound_nonfinite')
    q, triangular, pivots = linalg.qr(confounds, mode='economic', pivoting=True)
    keep = np.abs(np.diag(triangular)) > EPS * 100.
    q = q[:, keep]
    residual = signal - q.dot(q.T).dot(signal)
    centered = residual - residual.mean(axis=0)
    sample_sd = centered.std(axis=0, ddof=1)
    denominator = sample_sd.copy()
    denominator[denominator < EPS] = 1.
    cleaned = centered / denominator
    require(np.isfinite(residual).all() and np.isfinite(cleaned).all(), 'clean_nonfinite')
    flags = [activity_fn(residual[:, i], raw[:, i]) for i in range(raw.shape[1])]
    require(all(type(value) is bool for value in flags), 'activity_callback_bool')
    active = np.asarray(flags, dtype=bool)
    cleaned[:, ~active] = 0.
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
    return hashlib.sha256(b'SOCIALBRAIN_support_v2\n' + np.asarray(shape, dtype='<i8').tobytes() +
        np.asarray(affine, dtype='<f8', order='C').tobytes(order='C') +
        np.asarray(indices, dtype='<i8').tobytes()).hexdigest()
