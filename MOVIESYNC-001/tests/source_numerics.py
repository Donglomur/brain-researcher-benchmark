"""Independent numerical extraction/cleaning, without source IO or Nilearn imports.

Shared SciPy interpolation, filter, and QR libraries are explicitly disclosed.
All-map coefficients use explicit SciPy gesvd/pseudoinverse multiplication,
not the oracle's least-squares entrypoint. No source data are opened here.
"""
from __future__ import annotations

import warnings
import numpy as np
from scipy import linalg, ndimage, signal

from isc_math import real_array, require

EPS = np.finfo(np.float64).eps


def resample_maps(atlas, atlas_affine, target_shape, target_affine):
    atlas = real_array(atlas, "atlas", 4)
    source_affine = real_array(atlas_affine, "atlas affine", 2)
    destination_affine = real_array(target_affine, "target affine", 2)
    require(source_affine.shape == destination_affine.shape == (4, 4), "affine shape")
    require(np.array_equal(source_affine[3], [0,0,0,1]) and
            np.array_equal(destination_affine[3], [0,0,0,1]), "affine last row")
    require(len(target_shape) == 3 and all(type(n) is int and n > 0 for n in target_shape), "target shape")
    # Public Nilearn-0.13.1 coordinate arithmetic, shared deliberately: tiny
    # alternative inverse/solve errors at the closed-domain edge may change
    # constant-outside support. Extraction SVD remains independently composed.
    transform = np.eye(4) if np.array_equal(source_affine,destination_affine) else linalg.inv(source_affine) @ destination_affine
    matrix = transform[:3,:3]
    if np.all(np.diag(np.diag(matrix)) == matrix): matrix = np.diag(matrix)
    low, high = min(0., float(np.min(atlas))), max(0., float(np.max(atlas)))
    out = np.empty((*target_shape, atlas.shape[-1]), dtype=np.float64)
    for m in range(atlas.shape[-1]):
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore",message=".*has changed in SciPy 0.18.*")
            out[..., m] = ndimage.affine_transform(
                atlas[..., m], matrix, offset=transform[:3, 3],
                output_shape=target_shape, order=1, mode="constant", cval=0., prefilter=False)
    np.clip(out, low, high, out=out)
    require(np.isfinite(out).all(), "nonfinite resampled maps")
    return out


def map_basis(resampled_maps):
    maps = real_array(resampled_maps, "resampled maps", 4)
    design = np.asarray(maps.reshape(-1, maps.shape[-1], order="C"), order="C")
    u, singular, vt = linalg.svd(design, full_matrices=False, lapack_driver="gesvd", check_finite=True)
    cutoff = EPS*float(singular[0]) if singular.size else 0.
    keep = singular > cutoff
    # Rank zero stays a well-defined zero minimum-norm solution. Source
    # structural preconditions, if any, are separate and never drop columns.
    pinv = (vt[keep].T/singular[keep]) @ u[:, keep].T if np.any(keep) else np.zeros((design.shape[1], design.shape[0]))
    return {"pseudoinverse": pinv, "singular_values": singular,
            "rank": int(np.count_nonzero(keep)), "cutoff": cutoff,
            "shape": maps.shape[:3], "n_maps": maps.shape[-1]}


def extract_coefficients(bold, basis):
    data = real_array(bold, "scaled BOLD", 4)
    require(data.shape[:3] == basis["shape"], "BOLD/map grid mismatch")
    values = data.reshape(-1, data.shape[-1], order="C")
    coefficients = (basis["pseudoinverse"] @ values).T
    require(np.isfinite(coefficients).all(), "nonfinite extracted coefficients")
    return coefficients


def clean_coefficients(coefficients, confounds):
    """Float64 Nilearn-0.13.1 recipe, explicit local operations.

    No detrend, censoring, extra intercept, or second SD+epsilon normalization.
    Filter both matrices before centered/population-standardized confound QR;
    clean all original map columns, then the caller selects visual map IDs.
    """
    y = real_array(coefficients, "raw coefficients", 2).copy()
    c = real_array(confounds, "confounds", 2).copy()
    require(y.shape[0] == c.shape[0] and y.shape[0] > 33, "filter input frame support")
    sos = signal.butter(5, [.01, .1], btype="bandpass", fs=.5, output="sos")
    y = signal.sosfiltfilt(sos, y, axis=0, padtype="odd", padlen=33)
    c = signal.sosfiltfilt(sos, c, axis=0, padtype="odd", padlen=33)
    c -= c.mean(axis=0)
    confound_sd = c.std(axis=0, ddof=0)
    confound_sd[confound_sd < EPS] = 1.
    c /= confound_sd
    q, r, _ = linalg.qr(c, mode="economic", pivoting=True)
    retained = np.abs(np.diag(r)) > 100*EPS
    q = q[:, retained]
    # Preserve the explicit projection order in the public recipe.
    y -= q @ (q.T @ y)
    y -= y.mean(axis=0)
    sd = y.std(axis=0, ddof=1)
    divisor = sd.copy()
    divisor[divisor < EPS] = 1.
    y /= divisor
    require(np.isfinite(y).all(), "nonfinite cleaned coefficients")
    return y, {"confound_rank": int(np.count_nonzero(retained)),
               "residual_sample_sd": sd, "sos": sos}
