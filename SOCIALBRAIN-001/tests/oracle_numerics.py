"""Oracle-side array operators using pinned Nilearn, never the private extractor.

Only supplied arrays are consumed. No downloader, installed template discovery,
participant statistics or source path is accessed by these functions or import.
NumPy/SciPy and the public activity callback are disclosed shared primitives.
"""
import hashlib
import math

import nibabel as nib
import numpy as np
from nilearn import image, masking, signal
from nilearn.maskers.nifti_spheres_masker import apply_mask_and_get_affinity
from scipy import linalg


def sphere_supports(shape, affine, centers, radius=9.0):
    # A zero singleton image supplies geometry only. Original NaNs cannot trigger
    # upstream's implicit zero replacement: contributing values are checked below.
    geometric_image = nib.Nifti1Image(np.zeros((*shape, 1), dtype=np.float64), affine)
    _, affinity = apply_mask_and_get_affinity(centers, geometric_image, radius, True)
    return [np.flatnonzero(affinity.getrow(i).toarray().ravel()).astype(np.int64)
            for i in range(len(centers))]


def global_support(template, template_affine, target_shape, target_affine):
    values = np.asarray(template, dtype=np.float32).copy()
    if values.ndim != 3 or not np.isfinite(values).all() or values.size == 0:
        raise ValueError('invalid_template')
    maximum = values.max()
    if maximum <= 0:
        raise ValueError('invalid_template_maximum')
    values /= maximum
    source = nib.Nifti1Image(values, template_affine)
    target = nib.Nifti1Image(np.zeros(target_shape, dtype=np.float32), target_affine)
    resampled = image.resample_to_img(source, target, interpolation='continuous',
        copy=True, order='F', clip=False, fill_value=0, force_resample=False, copy_header=True)
    sampled = np.asarray(resampled.dataobj)
    mask, _ = masking._post_process_mask((sampled >= .5).astype(np.int8),
        target_affine, opening=2, connected=True)
    indices = np.flatnonzero(mask.ravel(order='C')).astype(np.int64)
    if indices.size == 0:
        raise ValueError('empty_global_support')
    # Branch label is documentary, not used to compute the support.
    if tuple(values.shape) == tuple(target_shape) and np.allclose(target_affine, template_affine):
        branch = 'allclose_equal_shape_noop'
    else:
        transform = np.eye(4) if np.all(target_affine == template_affine) else \
            linalg.inv(template_affine) @ target_affine
        a, b = transform[:3, :3], transform[:3, 3]
        if np.array_equal(a, np.eye(3)) and np.all(b == np.round(b)):
            branch = 'integer_translation_crop_padding'
        else:
            branch = 'cubic_diagonal' if np.array_equal(a, np.diag(np.diag(a))) else 'cubic_full_matrix'
    return dict(indices=indices, mask=mask, resampled_template=sampled,
                normalization_maximum=float(maximum), resampling_branch=branch)


def extract_raw_and_gs(scaled_bold, roi_supports, gs_support):
    data = np.asarray(scaled_bold, dtype=np.float64)
    if data.ndim != 4 or data.shape[3] < 2:
        raise ValueError('invalid_bold_shape')
    flat = data.reshape(-1, data.shape[3], order='C')
    selected = np.unique(np.concatenate([*roi_supports, gs_support]))
    if not np.isfinite(flat[selected]).all():
        raise ValueError('nonfinite_contributing_values')
    raw = np.column_stack([
        [np.mean(np.ascontiguousarray(flat[support, t]), dtype=np.float64)
         for t in range(data.shape[3])] for support in roi_supports])
    voxels = np.ascontiguousarray(flat[gs_support].T, dtype=np.float64)
    detrended = signal.standardize_signal(voxels, detrend=True, standardize=False)
    gs = np.array([np.mean(np.ascontiguousarray(row), dtype=np.float64) for row in detrended])
    if not np.isfinite(raw).all() or not np.isfinite(gs).all():
        raise ValueError('source_reduction_nonfinite')
    return np.ascontiguousarray(raw), gs


def _centered_norm(x):
    x = np.asarray(x, dtype=np.float64)
    if np.all(x == x[0]):
        return 0.0
    scale = float(np.max(np.abs(x)))
    z = x / scale
    z = z - math.fsum(map(float, z)) / len(z)
    peak = float(np.max(np.abs(z)))
    if not peak:
        return 0.0
    z /= peak
    length = math.sqrt(math.fsum(float(v) * float(v) for v in z))
    a, ea = math.frexp(scale)
    b, eb = math.frexp(peak)
    c, ec = math.frexp(length)
    result = math.ldexp(a * b * c, ea + eb + ec)
    if not math.isfinite(result):
        raise ValueError('diagnostic_norm_unrepresentable')
    return result


def clean_roi(raw_roi, nuisance, *, activity_fn):
    raw = np.array(raw_roi, dtype=np.float64, order='C', copy=True)
    confounds = np.array(nuisance, dtype=np.float64, order='C', copy=True)
    if raw.ndim != 2 or confounds.ndim != 2 or len(raw) != len(confounds) or len(raw) < 2 \
            or not np.isfinite(raw).all() or not np.isfinite(confounds).all():
        raise ValueError('invalid_clean_inputs')
    residual = signal.clean(raw, confounds=confounds, detrend=True, standardize=False,
        standardize_confounds=True, low_pass=None, high_pass=None, t_r=None,
        ensure_finite=False)
    clean = signal.standardize_signal(residual, detrend=False, standardize='zscore_sample')
    active = np.asarray([activity_fn(residual[:, i], raw[:, i]) for i in range(raw.shape[1])], dtype=bool)
    clean[:, ~active] = 0.0
    # Independent diagnostic reconstruction: never used as an input to clean().
    c = signal.standardize_signal(confounds, detrend=True, standardize=False)
    c = signal.standardize_signal(c, detrend=False, standardize=True)
    _, r, pivots = linalg.qr(c, mode='economic', pivoting=True)
    rank = int(np.count_nonzero(np.abs(np.diag(r)) > 100 * np.finfo(np.float64).eps))
    centered = residual - residual.mean(axis=0)
    sample_sd = centered.std(axis=0, ddof=1)
    denominator = sample_sd.copy()
    denominator[denominator < np.finfo(np.float64).eps] = 1.0
    raw_norm = np.asarray([_centered_norm(raw[:, i]) for i in range(raw.shape[1])])
    residual_norm = np.asarray([_centered_norm(residual[:, i]) for i in range(raw.shape[1])])
    return dict(cleaned=clean, residual=residual, active=active, rank=rank,
        pivots=np.asarray(pivots, dtype=np.int64), sample_sd=sample_sd,
        standardization_denominator=denominator, raw_centered_l2=raw_norm,
        residual_centered_l2=residual_norm, activity_threshold=1e-12 * raw_norm)


def support_digest(shape, affine, indices):
    affine = np.array(affine, dtype='<f8', order='C', copy=True)
    affine[affine == 0] = 0
    return hashlib.sha256(b'SOCIALBRAIN_support_v2\n' +
        np.asarray(shape, dtype='<i8').tobytes() + affine.tobytes(order='C') +
        np.asarray(indices, dtype='<i8').tobytes()).hexdigest()
