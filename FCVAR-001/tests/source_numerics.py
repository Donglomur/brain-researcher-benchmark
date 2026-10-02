"""FCVAR independent source extraction/cleaning; no original I/O or kernel import.

Shared NumPy/SciPy interpolation, SOS and QR operations are disclosed. The
oracle's public statistic kernel is used only downstream by proof_of_work.
"""
from __future__ import annotations

import hashlib
import math

import numpy as np
from scipy import linalg, ndimage, signal

from artifact_reader import require

EPS = np.finfo(np.float64).eps
CONFOUNDS = ("motion-pitch", "motion-roll", "motion-yaw", "motion-x", "motion-y", "motion-z",
             "compcor1", "compcor2", "compcor3", "compcor4", "compcor5", "wm", "csf")


def real_array(value, ndim, name="array"):
    def no_bool(item):
        require(not isinstance(item, (bool, np.bool_)), name + ": Boolean number")
        if isinstance(item, (list, tuple)):
            for child in item: no_bool(child)
    no_bool(value)
    array = np.asarray(value)
    require(array.dtype.kind in "iuf" and array.dtype.fields is None and array.ndim == ndim,
            name + ": non-Boolean real shape/type")
    require(np.isfinite(array).all(), name + ": finite required")
    return np.asarray(array, dtype=np.float64)


def centered_components(values):
    """Scaled center, original scale and physical norm, without tiny divisor."""
    values = real_array(values, 1)
    require(values.size > 0, "empty vector")
    if np.all(values == values[0]):
        return np.zeros_like(values), 0., 0.
    scale = float(np.max(np.abs(values)))
    scaled = values / scale
    out = scaled - math.fsum(map(float, scaled)) / len(values)
    norm = scale * l2(out)
    require(math.isfinite(norm), "centering norm overflow")
    return out, scale, norm


def centered(values):
    c, scale, _ = centered_components(values)
    return c * scale


def l2(values):
    values = real_array(values, 1)
    if not len(values): return 0.
    scale = float(np.max(np.abs(values)))
    if scale == 0.: return 0.
    result = scale * math.sqrt(math.fsum(float(x) * float(x) for x in values / scale))
    require(math.isfinite(result), "norm overflow")
    return result


def resample_labels(atlas, source_affine, target_shape, target_affine):
    labels = real_array(atlas, 3, "atlas")
    require(np.all(labels == np.floor(labels)) and np.all(labels >= 0) and np.all(labels <= 48), "atlas label domain")
    source = real_array(source_affine, 2, "atlas affine")
    target = real_array(target_affine, 2, "BOLD affine")
    require(source.shape == target.shape == (4, 4), "affine shape")
    require(len(target_shape) == 3 and all(type(v) is int and v > 0 for v in target_shape), "spatial shape")
    require(np.linalg.det(source[:3, :3]) != 0 and np.linalg.det(target[:3, :3]) != 0, "singular affine")
    if labels.shape == tuple(target_shape) and np.array_equal(source, target):
        return labels.astype(np.int64)
    transform = np.eye(4) if np.array_equal(source, target) else linalg.inv(source) @ target
    result = ndimage.affine_transform(labels, transform[:3, :3], offset=transform[:3, 3],
                                     output_shape=target_shape, order=0,
                                     mode="constant", cval=0., prefilter=False)
    return result.astype(np.int64)


def support_records(label_grid, roi_ids, selected_affine):
    flat = np.asarray(label_grid).reshape(-1, order="C")
    indices = [np.flatnonzero(flat == roi).astype(np.int64) for roi in roi_ids]
    affine = real_array(selected_affine, 2, "support affine")
    require(affine.shape == (4, 4), "support affine shape")
    prefix = (b"FCVAR_support_v3\n" + np.asarray(label_grid.shape, dtype="<i8").tobytes()
              + affine.astype("<f8").tobytes(order="C"))
    digests = [hashlib.sha256(prefix + ids.astype("<i8").tobytes()).hexdigest() for ids in indices]
    return {"indices": indices, "n_voxels": np.asarray([len(ids) for ids in indices], dtype=np.int64),
            "geometry_present": np.asarray([len(ids) > 0 for ids in indices], dtype=bool),
            "support_sha256": np.asarray(digests)}


def parcel_means(data, supports):
    """Independent ascending-C-index float64 means; empty support is flagged0."""
    values = np.asarray(data)
    require(values.ndim == 4 and values.dtype.kind in "iuf" and values.dtype.fields is None, "calibrated BOLD real shape/type")
    values = np.asarray(values, dtype=np.float64)
    flat = values.reshape(-1, values.shape[-1], order="C")
    result = np.zeros((values.shape[-1], len(supports["indices"])), dtype=np.float64)
    for j, indices in enumerate(supports["indices"]):
        require(indices.ndim == 1 and (not len(indices) or (indices.min() >= 0 and indices.max() < len(flat))), "support index bounds")
        if len(indices):
            for t in range(values.shape[-1]):
                contributing = np.ascontiguousarray(flat[indices, t], dtype=np.float64)
                require(np.isfinite(contributing).all(), "nonfinite contributing source voxel")
                result[t, j] = np.mean(contributing)
    return real_array(result, 2, "raw ROI means")


def detrend(values):
    values = real_array(values, 2).copy(order="C")
    require(values.shape[0] >= 2, "detrend frame count")
    values -= values.mean(axis=0)
    axis = np.arange(values.shape[0], dtype=np.float64)
    axis -= axis.mean()
    axis /= np.sqrt(np.sum(axis ** 2))
    values -= np.dot(axis, values) * axis[:, None]
    return values


def clean_roi_signals(raw, confounds, tr_sec, geometry_present):
    raw = np.ascontiguousarray(real_array(raw, 2, "raw"))
    nuisance = np.ascontiguousarray(real_array(confounds, 2, "confounds"))
    geometry = np.asarray(geometry_present)
    require(geometry.dtype.kind == "b" and geometry.shape == (raw.shape[1],), "geometry Boolean shape")
    require(raw.shape[0] > 33 and raw.shape[1] == 48 and nuisance.shape == (raw.shape[0], 13), "cleaning frames/48 ROIs/13 nuisance columns")
    require(np.all(raw[:, ~geometry] == 0.), "source geometry-empty raw sentinel")
    require(not isinstance(tr_sec, (bool, np.bool_)) and np.isscalar(tr_sec) and math.isfinite(float(tr_sec)) and .1 < float(tr_sec) < 10, "positive finite TR")
    require(.08 < .5 / float(tr_sec), "band below source Nyquist")
    sos = signal.butter(5, [.009, .08], btype="bandpass", fs=1./float(tr_sec), output="sos")
    y = np.ascontiguousarray(signal.sosfiltfilt(sos, detrend(raw), axis=0, padtype="odd", padlen=33))
    nuisance = np.ascontiguousarray(signal.sosfiltfilt(sos, detrend(nuisance), axis=0, padtype="odd", padlen=33))
    nuisance -= nuisance.mean(axis=0)
    sd = nuisance.std(axis=0, ddof=0)
    sd[sd < EPS] = 1.
    nuisance /= sd
    q, r, _ = linalg.qr(nuisance, mode="economic", pivoting=True)
    keep = np.abs(np.diag(r)) > 100*EPS
    q = np.ascontiguousarray(q[:, keep])
    residual = np.ascontiguousarray(y - (q @ q.T) @ y)
    residual -= residual.mean(axis=0)
    raw_norm = np.asarray([centered_components(raw[:, j])[2] for j in range(raw.shape[1])])
    pieces = [centered_components(residual[:, j]) for j in range(raw.shape[1])]
    norms = np.asarray([piece[2] for piece in pieces])
    threshold = 1e-12 * raw_norm
    active = geometry & (raw_norm > 0.) & (norms > threshold)
    clean = np.zeros(raw.shape, dtype=np.float64)
    for j in np.flatnonzero(active):
        scaled_center, scale, _ = pieces[j]
        clean[:, j] = scaled_center / (norms[j] / scale) * math.sqrt(raw.shape[0]-1)
    require(np.isfinite(clean).all(), "finite cleaned series")
    return {"clean": clean, "active": active,
            "raw_sample_sd": raw_norm / math.sqrt(raw.shape[0]-1),
            "prestandardization_centered_l2": norms, "activity_threshold": threshold,
            "full_clean_centered_l2": np.asarray([centered_components(clean[:, j])[2] for j in range(raw.shape[1])]),
            "cleaning_rank": int(keep.sum())}
