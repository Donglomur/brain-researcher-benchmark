"""Array-only DEVCONN oracle using pinned Nilearn 0.12.1, no source discovery.

Independent composition from the direct private module; no import of that module
or cohort reporting. NumPy/SciPy/sklearn and authenticated activity semantics are
shared, disclosed dependencies. Only manufactured/supplied arrays are consumed.
"""
import hashlib
import math

import nibabel as nib
import numpy as np
from nilearn import signal
from nilearn.maskers.nifti_spheres_masker import apply_mask_and_get_affinity
from scipy import linalg

CONF_COLS = ("trans_x", "trans_y", "trans_z", "rot_x", "rot_y", "rot_z",
             "a_comp_cor_00", "a_comp_cor_01", "a_comp_cor_02", "a_comp_cor_03",
             "a_comp_cor_04", "a_comp_cor_05", "csf", "white_matter")


def _contains_boolean(value):
    if isinstance(value, (bool, np.bool_)):
        return True
    return isinstance(value, (list, tuple)) and any(_contains_boolean(x) for x in value)


def _array(value, dimensions, *, finite=True):
    if _contains_boolean(value):
        raise ValueError('boolean_numeric_input')
    data = np.asarray(value)
    if data.ndim != dimensions or data.dtype.kind not in 'iuf':
        raise ValueError('invalid_numeric_shape_or_type')
    data = np.array(data, dtype=np.float64, order='C', copy=True)
    if finite and not np.isfinite(data).all():
        raise ValueError('nonfinite_contributing_values')
    return data


def _grid(shape, affine):
    if len(shape) != 3 or any(isinstance(v, (bool, np.bool_)) or
                             not isinstance(v, (int, np.integer)) or v <= 0 for v in shape):
        raise ValueError('invalid_grid_shape')
    affine = _array(affine, 2)
    if affine.shape != (4, 4) or not np.array_equal(affine[3], [0., 0., 0., 1.]) \
            or not np.isfinite(np.linalg.inv(affine)).all():
        raise ValueError('invalid_grid_affine')
    return tuple(int(v) for v in shape), affine


def _support(indices, count):
    if _contains_boolean(indices):
        raise ValueError('invalid_support')
    row = np.asarray(indices)
    if row.ndim != 1 or row.dtype.kind not in 'iu' or row.size == 0 \
            or np.any(row < 0) or np.any(row >= count) or np.any(row[1:] <= row[:-1]):
        raise ValueError('invalid_support')
    return row.astype(np.int64)


def sphere_supports(shape, affine, centers, radius=5.0):
    """Pinned library geometry only; original signal never enters this call."""
    shape, affine = _grid(shape, affine)
    centers = _array(centers, 2)
    if centers.shape[0] == 0 or centers.shape[1] != 3:
        raise ValueError('invalid_sphere_centers')
    if isinstance(radius, (bool, np.bool_)) or not isinstance(radius, (int, float, np.integer, np.floating)) \
            or not np.isfinite(radius) or radius < 0:
        raise ValueError('invalid_sphere_radius')
    geometric_image = nib.Nifti1Image(np.zeros((*shape, 1), dtype=np.float64), affine)
    _, affinity = apply_mask_and_get_affinity(centers, geometric_image, float(radius), True, mask_img=None)
    supports = [np.flatnonzero(affinity.getrow(i).toarray().ravel()).astype(np.int64)
                for i in range(len(centers))]
    if any(row.size == 0 for row in supports):
        raise ValueError('empty_sphere_support')
    return supports


def extract_raw(scaled_bold, roi_supports):
    """Independent per-frame slicing; source scaling precedes this array API."""
    data = _array(scaled_bold, 4, finite=False)
    if data.shape[3] < 2 or len(roi_supports) == 0:
        raise ValueError('invalid_source_shape')
    flat = data.reshape(-1, data.shape[3], order='C')
    supports = [_support(row, len(flat)) for row in roi_supports]
    selected = np.unique(np.concatenate(supports))
    if not np.isfinite(flat[selected]).all():
        raise ValueError('nonfinite_contributing_values')
    raw = np.column_stack([
        [np.mean(np.ascontiguousarray(flat[support, frame]), dtype=np.float64)
         for frame in range(data.shape[3])] for support in supports])
    if not np.isfinite(raw).all():
        raise ValueError('source_reduction_nonfinite')
    return np.ascontiguousarray(raw)


def _centered_norm(values):
    if np.all(values == values[0]):
        return 0.0
    scale = float(np.max(np.abs(values)))
    centered = values / scale
    centered -= math.fsum(map(float, centered)) / len(centered)
    peak = float(np.max(np.abs(centered)))
    if peak == 0:
        return 0.0
    unit = centered / peak
    length = math.sqrt(math.fsum(float(v) * float(v) for v in unit))
    a, ea = math.frexp(scale)
    b, eb = math.frexp(peak)
    c, ec = math.frexp(length)
    try:
        result = math.ldexp(a * b * c, ea + eb + ec)
    except OverflowError as exc:
        raise ValueError('diagnostic_norm_unrepresentable') from exc
    if not math.isfinite(result):
        raise ValueError('diagnostic_norm_unrepresentable')
    return result


def clean_roi(raw_roi, nuisance, *, activity_fn):
    """Library residual, public activity gate, library sample standardization."""
    raw, confounds = _array(raw_roi, 2), _array(nuisance, 2)
    if len(raw) < 2 or raw.shape[1] == 0 or confounds.shape != (len(raw), 14):
        raise ValueError('clean_shape_or_confound_count')
    if not callable(activity_fn):
        raise ValueError('activity_callback_required')
    residual = signal.clean(raw, confounds=confounds, detrend=True, standardize=False,
        standardize_confounds=True, filter='butterworth', low_pass=.08, high_pass=.009,
        t_r=2.0, ensure_finite=False, butterworth__order=5,
        butterworth__padtype='odd', butterworth__padlen=None)
    if not np.isfinite(residual).all():
        raise ValueError('clean_nonfinite')
    flags = [activity_fn(residual[:, i], raw[:, i]) for i in range(raw.shape[1])]
    if not all(type(flag) is bool for flag in flags):
        raise ValueError('activity_callback_bool')
    active = np.asarray(flags, dtype=bool)
    cleaned = signal.standardize_signal(residual, detrend=False, standardize='zscore_sample')
    if not np.isfinite(cleaned).all():
        raise ValueError('clean_nonfinite')
    cleaned[:, ~active] = 0.0
    # Independent library-based rank receipt; never an input to signal.clean.
    c = signal.standardize_signal(confounds, detrend=True, standardize=False)
    c = signal.butterworth(c, sampling_rate=.5, low_pass=.08, high_pass=.009,
                          order=5, padtype='odd', padlen=None, copy=False)
    c = signal.standardize_signal(c, detrend=False, standardize=True)
    _, triangular, pivots = linalg.qr(c, mode='economic', pivoting=True)
    rank = int(np.count_nonzero(np.abs(np.diag(triangular)) > 100 * np.finfo(np.float64).eps))
    centered = residual - residual.mean(axis=0)
    sample_sd = centered.std(axis=0, ddof=1)
    denominator = sample_sd.copy()
    denominator[denominator < np.finfo(np.float64).eps] = 1.0
    raw_norm = np.asarray([_centered_norm(raw[:, i]) for i in range(raw.shape[1])])
    residual_norm = np.asarray([_centered_norm(residual[:, i]) for i in range(raw.shape[1])])
    return dict(cleaned=cleaned, residual=residual, active=active, rank=rank,
        pivots=np.asarray(pivots, dtype=np.int64), sample_sd=sample_sd,
        standardization_denominator=denominator, raw_centered_l2=raw_norm,
        residual_centered_l2=residual_norm, activity_threshold=1e-12 * raw_norm)


def support_digest(shape, affine, indices):
    shape, affine = _grid(shape, affine)
    indices = _support(indices, math.prod(shape))
    affine = np.array(affine, dtype='<f8', order='C', copy=True)
    affine[affine == 0] = 0
    return hashlib.sha256(b'DEVCONN_support_v2\n' +
        np.asarray(shape, dtype='<i8').tobytes() + affine.tobytes(order='C') +
        np.asarray(indices, dtype='<i8').tobytes()).hexdigest()
