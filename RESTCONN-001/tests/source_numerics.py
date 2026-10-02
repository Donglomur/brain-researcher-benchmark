"""Prospective RESTCONN independent source arithmetic, no source I/O.

Interpolation/SOS/QR libraries are shared; all-map coefficients use explicit
gesvd pseudoinversion, not the oracle's gelsd call. Cleaning deliberately uses
(Q @ Q.T) @ Y, matching the declared Nilearn 0.13.1 association, unlike PR188.
"""
from __future__ import annotations

import math
import warnings

import numpy as np
from scipy import linalg, ndimage, signal

from circular_contract import real_array as _real_array, require, stable_l2, center_scaled

EPS = np.finfo(np.float64).eps
ACTIVITY_FACTOR = 1e-12


def real_array(value, name, ndim):
    try:
        return _real_array(value, ndim)
    except ValueError as exc:
        raise ValueError(name + ": " + str(exc)) from exc


def resample_maps(atlas, atlas_affine, target_shape, target_affine):
    atlas = real_array(atlas, "atlas", 4)
    source = real_array(atlas_affine, "atlas affine", 2)
    target = real_array(target_affine, "target affine", 2)
    require(source.shape == target.shape == (4, 4), "affine shape")
    require(len(target_shape) == 3 and all(type(n) is int and n > 0 for n in target_shape), "target shape")
    require(np.linalg.det(source[:3, :3]) != 0 and np.linalg.det(target[:3, :3]) != 0, "singular affine")
    if atlas.shape[:3] == tuple(target_shape) and np.array_equal(source, target):
        result = atlas.copy()
    else:
        transform = np.eye(4) if np.array_equal(source, target) else linalg.inv(source) @ target
        matrix = transform[:3, :3]
        if np.array_equal(matrix, np.diag(np.diag(matrix))):
            matrix = np.diag(matrix)
        result = np.empty((*target_shape, atlas.shape[-1]), dtype=np.float64)
        # SciPy reports the documented diagonal-vector change as a warning.
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="The behavior of affine_transform with a 1-D array")
            for column in range(atlas.shape[-1]):
                result[..., column] = ndimage.affine_transform(
                    atlas[..., column], matrix, offset=transform[:3, 3], output_shape=target_shape,
                    order=1, mode="constant", cval=0., prefilter=False)
    np.clip(result, min(0., float(atlas.min())), max(0., float(atlas.max())), out=result)
    return real_array(result, "resampled atlas", 4)


def map_basis(maps):
    maps = real_array(maps, "maps", 4)
    require(all(n > 0 for n in maps.shape), "empty maps")
    design = np.ascontiguousarray(maps.reshape(-1, maps.shape[-1]), dtype=np.float64)
    u, singular, vt = linalg.svd(design, full_matrices=False, lapack_driver="gesvd")
    cutoff = EPS * float(singular[0])
    keep = singular > cutoff
    pinv = (vt[keep].T / singular[keep]) @ u[:, keep].T if keep.any() else np.zeros(design.T.shape)
    return {"pinv": pinv, "rank": int(keep.sum()), "singular_values": singular,
            "cutoff": cutoff, "spatial_shape": maps.shape[:3], "n_maps": maps.shape[-1]}


def extract_coefficients(bold, basis):
    data = real_array(bold, "BOLD", 4)
    require(data.shape[:3] == tuple(basis["spatial_shape"]), "BOLD/map grid mismatch")
    require(data.shape[-1] > 0, "empty BOLD frames")
    coefficients = (basis["pinv"] @ np.ascontiguousarray(data.reshape(-1, data.shape[-1]))).T
    return real_array(coefficients, "full simultaneous coefficients", 2)


def detrend(values):
    out = real_array(values, "detrend values", 2).copy()
    require(out.shape[0] >= 2, "insufficient frames")
    out -= out.mean(axis=0)
    linear = np.arange(out.shape[0], dtype=np.float64)
    linear -= linear.mean()
    linear /= np.sqrt(np.sum(linear ** 2))
    out -= np.dot(linear, out) * linear[:, None]
    return out


def centered_l2(values):
    values = _real_array(values, 1)
    scale = float(np.max(np.abs(values)))
    result = stable_l2(center_scaled(values)) * scale
    require(math.isfinite(result), "centered norm overflow")
    return result


def clean_coefficients(raw, confounds, *, tr=2.):
    raw = real_array(raw, "raw coefficients", 2)
    confounds = real_array(confounds, "confounds", 2)
    require(raw.shape[0] == confounds.shape[0] and raw.shape[0] > 33, "cleaning frame count/padding")
    require(raw.shape[1] > 0 and confounds.shape[1] > 0, "empty cleaning columns")
    require(not isinstance(tr, (bool, np.bool_)) and float(tr) == 2., "fixed operational TR")
    sos = signal.butter(5, [.01, .1], btype="bandpass", fs=1. / tr, output="sos")
    y = signal.sosfiltfilt(sos, detrend(raw), axis=0, padtype="odd", padlen=33)
    nuisance = signal.sosfiltfilt(sos, detrend(confounds), axis=0, padtype="odd", padlen=33)
    nuisance -= nuisance.mean(axis=0)
    sd = nuisance.std(axis=0, ddof=0)
    sd[sd < EPS] = 1.
    nuisance /= sd
    q, r, _ = linalg.qr(nuisance, mode="economic", pivoting=True)
    keep = np.abs(np.diag(r)) > 100 * EPS
    q = q[:, keep]
    residual = y - (q @ q.T) @ y
    residual -= residual.mean(axis=0)
    residual = real_array(residual, "residual", 2)
    raw_sd = np.asarray([centered_l2(raw[:, j]) / math.sqrt(raw.shape[0] - 1) for j in range(raw.shape[1])])
    norms = np.asarray([centered_l2(residual[:, j]) for j in range(raw.shape[1])])
    threshold = ACTIVITY_FACTOR * math.sqrt(raw.shape[0]) * np.maximum(1., raw_sd)
    active = norms > threshold
    denominator = residual.std(axis=0, ddof=1)
    denominator[denominator < EPS] = 1.
    clean = residual / denominator
    clean[:, ~active] = 0.
    return real_array(clean, "cleaned coefficients", 2), {
        "confound_rank": int(keep.sum()), "raw_sample_sd": raw_sd,
        "residual_centered_l2": norms, "activity_threshold": threshold, "active": active,
        "residual_before_zscore": residual, "sos": sos,
        "projection_association": "(Q @ Q.T) @ Y"}
