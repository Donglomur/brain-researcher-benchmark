"""Independent pure source reconstruction primitives; no I/O or oracle imports.

The public extraction/cleaning coordinate arithmetic deliberately shares NumPy,
SciPy interpolation/filter/QR with the declared recipe. Spectral certificates
are separate. These functions accept manufactured arrays and never fetch data.
"""
from __future__ import annotations

import hashlib
import numpy as np
from scipy import linalg, ndimage, signal

from gradient_math import activity, ids, real, require

EPS = np.finfo(np.float64).eps


def resample_labels(atlas, atlas_affine, target_shape, target_affine):
    labels = real(atlas, "atlas labels", 3)
    require(np.equal(labels, np.floor(labels)).all() and np.all(labels >= 0), "atlas integer labels")
    require(np.all(labels < 2**31), "atlas label range")
    source_affine = real(atlas_affine, "atlas affine", 2)
    destination_affine = real(target_affine, "BOLD affine", 2)
    require(source_affine.shape == destination_affine.shape == (4, 4), "affine shape")
    require(np.array_equal(source_affine[3], [0, 0, 0, 1]) and
            np.array_equal(destination_affine[3], [0, 0, 0, 1]), "affine last row")
    require(len(target_shape) == 3 and all(type(n) is int and n > 0 for n in target_shape), "target shape")
    labels = labels.astype(np.int32)
    if labels.shape == tuple(target_shape) and np.array_equal(source_affine, destination_affine):
        return labels.copy()
    transform = linalg.inv(source_affine) @ destination_affine
    result = ndimage.affine_transform(labels, transform[:3, :3], offset=transform[:3, 3],
                                     output_shape=target_shape, order=0, mode="constant",
                                     cval=0, prefilter=False)
    require(set(np.unique(result)).issubset(set(np.unique(labels)) | {0}), "invented atlas labels")
    return result


def parcel_support(label_grid, parcel_ids):
    grid = real(label_grid, "label grid", 3)
    require(np.equal(grid, np.floor(grid)).all(), "label grid integers")
    parcel_ids = ids(parcel_ids, len(parcel_ids))
    require(np.all(parcel_ids > 0), "positive parcel IDs required")
    require(set(np.unique(grid)).issubset(set(parcel_ids.tolist()) | {0}), "unexpected source label")
    flat = grid.ravel(order="C")
    supports = [np.flatnonzero(flat == parcel) for parcel in parcel_ids]
    return dict(indices=supports, geometry_valid=np.asarray([len(x) > 0 for x in supports]),
                counts=np.asarray([len(x) for x in supports], dtype=np.int64),
                sha256=[hashlib.sha256(x.astype("<i8").tobytes()).hexdigest() for x in supports],
                shape=grid.shape, parcel_ids=parcel_ids)


def volume_means(volume, supports):
    data = real(volume, "calibrated BOLD volume", 3)
    require(data.shape == supports["shape"], "BOLD geometry mismatch")
    flat = data.ravel(order="C")
    means = np.full(len(supports["indices"]), np.nan)
    for column, indices in enumerate(supports["indices"]):
        if len(indices):
            values = np.ascontiguousarray(flat[indices], dtype=np.float64)
            means[column] = np.mean(values, dtype=np.float64)
    require(np.isfinite(means[supports["geometry_valid"]]).all(), "nonfinite parcel means")
    return means


def detrend(values):
    result = real(values, "detrend input", 2).copy()
    require(result.shape[0] >= 2, "detrend frame support")
    constant = np.all(result == result[0], axis=0)
    result -= np.mean(result, axis=0, dtype=np.float64)
    time = np.arange(len(result), dtype=np.float64)
    time -= np.mean(time, dtype=np.float64)
    time /= np.sqrt(np.sum(time**2, dtype=np.float64))
    result -= time[:, None] * (time @ result)[None, :]
    result[:, constant] = 0.
    return real(result, "detrended values", 2)


def reconstruct_person(raw_means, confounds, geometry_valid):
    """Return both arms and canonical activity/FC, preserving every parcel."""
    raw = np.asarray(raw_means)
    valid = np.asarray(geometry_valid)
    require(raw.ndim == 2 and raw.dtype.kind in "iuf", "raw mean dimensions/type")
    require(valid.dtype.kind == "b" and valid.shape == (raw.shape[1],), "geometry mask")
    require(np.isnan(raw[:, ~valid]).all(), "absent geometry requires NaN")
    y = real(raw[:, valid], "present raw means", 2)
    c = real(confounds, "selected confounds", 2)
    require(y.shape[0] == c.shape[0] and y.shape[0] > 33, "filter frame support")
    y, c = detrend(y), detrend(c)
    c -= np.mean(c, axis=0, dtype=np.float64)
    sd = np.std(c, axis=0, ddof=0, dtype=np.float64)
    divisor = np.where(sd < EPS, 1., sd)
    c /= divisor
    q, r, _ = linalg.qr(c, mode="economic", pivoting=True, check_finite=True)
    retained = np.abs(np.diag(r)) > 100 * EPS
    q = q[:, retained]
    no_bandpass = y - q @ (q.T @ y)
    sos = signal.butter(5, [.01, .1], btype="bandpass", fs=.5, output="sos")
    bandpass = signal.sosfiltfilt(sos, no_bandpass, axis=0, padtype="odd", padlen=33)
    cleaned = np.full((2, *raw.shape), np.nan)
    cleaned[0][:, valid] = no_bandpass
    cleaned[1][:, valid] = bandpass
    support = activity(raw, cleaned, valid)
    fc = np.stack([canonical_fc(cleaned[arm], support["person_parcel_active"][arm]) for arm in range(2)])
    return dict(cleaned_series=cleaned, fc=fc, nuisance_rank=int(np.count_nonzero(retained)), **support)


def canonical_fc(cleaned, active):
    values = np.asarray(cleaned)
    mask = np.asarray(active)
    require(values.ndim == 2 and values.dtype.kind in "iuf", "FC signal dimensions/type")
    require(mask.shape == (values.shape[1],) and mask.dtype.kind == "b", "FC active mask")
    selected = real(values[:, mask], "active FC signals", 2)
    require(selected.shape[0] >= 2, "FC frame support")
    fc = np.full((values.shape[1], values.shape[1]), np.nan)
    count = int(np.count_nonzero(mask))
    if count:
        correlation = np.atleast_2d(np.corrcoef(selected.T))
        require(correlation.shape == (count, count) and np.isfinite(correlation).all(), "undefined active Pearson")
        upper = np.triu(correlation, 1)
        fc[np.ix_(mask, mask)] = upper + upper.T + np.eye(count)
    return fc


def group_connectivity(person_fc, person_active, membership):
    """Input participant axis MUST already be in the frozen source order."""
    fc, active, members = np.asarray(person_fc), np.asarray(person_active), np.asarray(membership)
    require(fc.dtype.kind in "iuf" and fc.ndim == 3 and fc.shape[1] == fc.shape[2], "person FC shape/type")
    require(active.dtype.kind == members.dtype.kind == "b", "group Boolean masks")
    require(active.shape == fc.shape[:2] and members.shape == (fc.shape[0],) and members.any(), "group axes/support")
    valid = active[members].all(axis=0)
    result = np.full(fc.shape[1:], np.nan)
    if valid.any():
        complete = fc[members][:, valid][:, :, valid]
        require(np.isfinite(complete).all(), "nonfinite complete group FC")
        mean = np.mean(complete, axis=0, dtype=np.float64)
        upper = np.triu(mean, 1)
        result[np.ix_(valid, valid)] = upper + upper.T + np.eye(int(valid.sum()))
    return result, valid
