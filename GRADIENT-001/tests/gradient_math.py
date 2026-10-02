"""Prospective PR190 verifier math, independent of BrainSpace/oracle code.

No I/O, source discovery, import-time fitting, or historical reference. Canonical
source operators/eigenvalues are authorities; submitted eigenvectors and certified
GPA rotations determine downstream coordinates. Public constants are prospective
and must be frozen by the parent before any original numerical execution.
"""
from __future__ import annotations

import math
import numpy as np
from scipy import linalg

EIGEN_ATOL = 1e-8
RESIDUAL_L2 = 1e-8
GRAM_ATOL = 1e-7
TRIVIAL_ATOL = 1e-8
GAP_ATOL = 4e-8
COORD_ATOL = COORD_RTOL = 1e-6
GPA_OPTIMALITY = 1e-7
GPA_MAX_ITER = 10
GPA_STOP_TOL = 1e-5


def require(condition, message):
    if not condition:
        raise ValueError(message)


def real(value, name, ndim=None):
    arr = np.asarray(value)
    require(arr.dtype.fields is None and arr.dtype.kind in "iuf", name + ": real non-Boolean values required")
    require(ndim is None or arr.ndim == ndim, name + ": dimensions")
    arr = np.asarray(arr, dtype=np.float64)
    require(np.isfinite(arr).all(), name + ": nonfinite")
    return arr


def count(value, name, lower, upper):
    require(not isinstance(value, (bool, np.bool_)) and isinstance(value, (int, float, np.integer, np.floating)), name + ": integer required")
    require(lower <= value <= upper and np.isfinite(value) and value == int(value), name + ": integer bounds")
    return int(value)


def ids(values, n):
    arr = real(values, "parcel IDs", 1)
    require(arr.shape == (n,) and np.equal(arr, np.floor(arr)).all(), "parcel IDs: integral axis")
    require(np.all(np.abs(arr) < 2**53), "parcel IDs: exact small integer range")
    arr = arr.astype(np.int64)
    require(len(set(arr.tolist())) == n, "parcel IDs: duplicates")
    return arr


def norm(values):
    arr = real(values, "norm input").ravel()
    scale = float(np.max(np.abs(arr))) if arr.size else 0.
    value = 0. if scale == 0 else scale * math.sqrt(math.fsum(float(v / scale)**2 for v in arr))
    require(math.isfinite(value), "nonfinite L2 norm")
    return value


def centered(values):
    values = real(values, "time vector", 1)
    require(len(values) >= 2, "at least two frames required")
    if np.all(values == values[0]):
        return np.zeros_like(values)
    return real(values - math.fsum(float(v) for v in values) / len(values), "centered time vector")


def activity(raw_means, cleaned, geometry_valid):
    """One person's source support; both arms use the same original raw SD.

NaN is permitted only in absent-geometry columns and preserved in diagnostics.
No invented epsilon Pearson or nearzero imputation: invalid parcels remain in
their original positions for downstream complete-family null propagation.
"""
    raw = np.asarray(raw_means)
    clean = np.asarray(cleaned)
    valid = np.asarray(geometry_valid)
    require(raw.dtype.kind in "iuf" and clean.dtype.kind in "iuf", "activity real arrays required")
    require(raw.ndim == 2 and raw.shape[0] >= 2 and clean.ndim == 3, "activity dimensions")
    t, parcels = raw.shape
    require(clean.shape[1:] == raw.shape and valid.shape == (parcels,) and valid.dtype.kind == "b", "activity axes/mask")
    require(np.isfinite(raw[:, valid]).all() and np.isfinite(clean[:, :, valid]).all(), "nonfinite present-geometry signal")
    require(np.isnan(raw[:, ~valid]).all() and np.isnan(clean[:, :, ~valid]).all(), "absent geometry requires NaN signal")
    raw_sd = np.full(parcels, np.nan)
    clean_norm = np.full((clean.shape[0], parcels), np.nan)
    threshold = np.full(parcels, np.nan)
    active = np.zeros((clean.shape[0], parcels), dtype=bool)
    for parcel in np.flatnonzero(valid):
        raw_sd[parcel] = norm(centered(raw[:, parcel])) / math.sqrt(t - 1)
        threshold[parcel] = 1e-12 * math.sqrt(t) * max(1., raw_sd[parcel])
        for arm in range(clean.shape[0]):
            clean_norm[arm, parcel] = norm(centered(clean[arm, :, parcel]))
            active[arm, parcel] = clean_norm[arm, parcel] > threshold[parcel]
    return dict(raw_sample_sd=raw_sd, clean_centered_l2=clean_norm,
                activity_threshold=threshold, person_parcel_active=active)


def close(actual, expected, name, atol=COORD_ATOL, rtol=COORD_RTOL):
    actual, expected = real(actual, name), real(expected, name + " expected")
    require(actual.shape == expected.shape, name + ": shape")
    require(np.all(np.abs(actual - expected) <= atol + rtol * np.abs(expected)), name + ": numeric mismatch")


def sparsify_fc(fc, parcel_ids, retained=40):
    """Keep signed row maxima; diagonal is eligible, not force-injected.

The explicit integer count corrects BrainSpace's floating 1-.9 truncation.
Lower original parcel ID breaks exact ties, independent of array order.
"""
    fc = real(fc, "canonical FC", 2)
    n = fc.shape[0]
    require(fc.shape == (n, n), "FC must be square")
    parcel_ids = ids(parcel_ids, n)
    retained = count(retained, "retained entries", 1, n)
    selected = np.zeros((n, n), dtype=bool)
    for i, row in enumerate(fc):
        order = np.lexsort((parcel_ids, -row))
        selected[i, order[:retained]] = True
    return np.where(selected, fc, 0.), selected


def normalized_angle(profiles):
    profiles = real(profiles, "sparse FC profiles", 2)
    lengths = np.asarray([norm(row) for row in profiles])
    require(np.all(lengths > 0), "undefined zero-norm affinity profile")
    unit = profiles / lengths[:, None]
    cosine = np.clip(unit @ unit.T, -1., 1.)
    affinity = 1. - np.arccos(cosine) / np.pi
    upper = np.triu(affinity, 1)
    return upper + upper.T + np.eye(len(affinity))


def operator_basis(affinity, parcel_ids, n_components=10):
    """Canonical symmetric diffusion operator and source-only support facts."""
    affinity = real(affinity, "affinity", 2)
    n = affinity.shape[0]
    require(affinity.shape == (n, n) and n >= 3, "affinity shape")
    parcel_ids = ids(parcel_ids, n)
    n_components = count(n_components, "components", 1, n - 2)
    require(np.all(affinity >= 0), "negative affinity")
    require(np.max(np.abs(affinity - affinity.T)) <= 1e-12, "asymmetric affinity")
    affinity = np.triu(affinity, 1) + np.triu(affinity, 1).T + np.diag(np.diag(affinity))
    q = np.sum(affinity, axis=1, dtype=np.float64)
    require(np.all(q > 0), "undefined zero affinity degree")
    anisotropic = affinity / (np.sqrt(q)[:, None] * np.sqrt(q)[None, :])
    degree = np.sum(anisotropic, axis=1, dtype=np.float64)
    require(np.isfinite(degree).all() and np.all(degree > 0), "undefined anisotropic degree")
    operator = anisotropic / (np.sqrt(degree)[:, None] * np.sqrt(degree)[None, :])
    operator = np.triu(operator, 1) + np.triu(operator, 1).T + np.diag(np.diag(operator))
    u0 = np.sqrt(degree) / math.sqrt(float(np.sum(degree)))
    # All 400 eigenvalues make leading-order/truncation checks source-defined.
    values, vectors = linalg.eigh(operator, check_finite=True, driver="evr")
    values, vectors = values[::-1].copy(), vectors[:, ::-1].copy()
    require(abs(values[0] - 1.) <= EIGEN_ATOL, "stationary eigenvalue")
    require(norm(operator @ u0 - u0) <= RESIDUAL_L2, "stationary eigenvector residual")
    lambdas = values[1:n_components + 1]
    principal_gap = float(values[1] - values[2])
    boundary_gap = float(values[n_components] - values[n_components + 1])
    finite_multiscale = bool(1. - values[1] > GAP_ATOL)
    return dict(operator=operator, u0=u0, eigenvalues=lambdas,
                spectral_eigenvalues=values[1:n_components + 2],
                all_eigenvalues=values, proposal_vectors=vectors[:, 1:n_components + 1],
                parcel_ids=parcel_ids, degree=degree,
                principal_gap=principal_gap, retained_boundary_gap=boundary_gap,
                principal_identifiable=bool(principal_gap > GAP_ATOL and finite_multiscale),
                retained_boundary_identifiable=bool(boundary_gap > GAP_ATOL),
                multiscale_defined=finite_multiscale,
                gpa_eligible=bool(finite_multiscale and boundary_gap > GAP_ATOL))


def canonical_basis(fc, parcel_ids, retained=40, n_components=10):
    profiles, mask = sparsify_fc(fc, parcel_ids, retained)
    basis = operator_basis(normalized_angle(profiles), parcel_ids, n_components)
    basis["top_entry_mask"] = mask
    return basis


def coordinates(vectors, basis):
    vectors = real(vectors, "eigenvectors", 2)
    require(vectors.shape == (len(basis["u0"]), len(basis["eigenvalues"])), "eigenvector shape")
    if not basis["multiscale_defined"]:
        return None
    lambdas = basis["eigenvalues"]
    gradient = (vectors / basis["u0"][:, None]) * (lambdas / (1. - lambdas))[None, :]
    require(np.isfinite(gradient).all(), "nonfinite diffusion coordinates")
    return gradient


def orient(vectors, basis):
    """Orient accepted eigenvectors using full-precision diffusion coordinates."""
    vectors = real(vectors, "eigenvectors", 2).copy()
    gradient = coordinates(vectors, basis)
    if gradient is None:
        return vectors, None
    parcel_ids = basis["parcel_ids"]
    for c in range(gradient.shape[1]):
        magnitude = np.abs(gradient[:, c])
        tied = np.flatnonzero(magnitude == magnitude.max())
        anchor = tied[np.argmin(parcel_ids[tied])]
        if gradient[anchor, c] < 0:
            vectors[:, c] *= -1.
            gradient[:, c] *= -1.
    return vectors, gradient


def validate_spectrum(vectors, saved_eigenvalues, saved_gradient, basis):
    """Accept valid repeated-block rotations; never match a stored eigenbasis."""
    vectors = real(vectors, "eigenvectors", 2)
    n, k = len(basis["u0"]), len(basis["eigenvalues"])
    require(vectors.shape == (n, k), "eigenvector shape")
    close(saved_eigenvalues, basis["spectral_eigenvalues"], "canonical eigenvalue receipt", EIGEN_ATOL, 0.)
    require(np.max(np.abs(vectors.T @ vectors - np.eye(k))) <= GRAM_ATOL, "eigenvector orthonormality")
    require(np.max(np.abs(basis["u0"] @ vectors)) <= TRIVIAL_ATOL, "trivial-eigenvector orthogonality")
    residual = basis["operator"] @ vectors - vectors * basis["eigenvalues"][None, :]
    require(all(norm(residual[:, c]) <= RESIDUAL_L2 for c in range(k)), "eigenpair residual/leading order")
    canonical = coordinates(vectors, basis)
    if canonical is None:
        require(saved_gradient is None, "undefined multiscale coordinates require null")
        return None
    oriented, _ = orient(vectors, basis)
    require(np.array_equal(oriented, vectors), "raw diffusion-coordinate sign")
    close(saved_gradient, canonical, "raw gradient receipt")
    return canonical


def validate_gpa_history(gradients, initial_reference, rotations, reference_history,
                         distances, n_iterations, saved_aligned=None):
    """Validate every orthogonal minimizer and the complete GPA recurrence.

No centering/scaling. Rounded reference/distance receipts never determine the
next minimization or stopping. This accepts null-space minimizer freedom without
accepting an unrelated final stationary alignment or relying on one SVD basis.
"""
    gradients = real(gradients, "raw subject gradients", 3)
    n, parcels, k = gradients.shape
    require(n >= 2 and parcels >= k and k >= 1, "GPA input shape")
    initial = real(initial_reference, "initial group reference", 2)
    require(initial.shape == (parcels, k), "initial reference shape")
    iterations = count(n_iterations, "GPA iterations", 1, GPA_MAX_ITER)
    rotations = real(rotations, "GPA rotations", 4)
    require(rotations.shape == (iterations, n, k, k), "GPA rotation shape")
    history = real(reference_history, "GPA reference history", 3)
    require(history.shape == (iterations + 1, parcels, k), "GPA reference shape")
    distances = real(distances, "GPA distances", 1)
    require(distances.shape == (iterations,) and np.all(distances >= 0), "GPA distance shape/domain")
    close(history[0], initial, "GPA initial reference receipt")
    prior = initial
    previous_distance = None
    replayed_history, replayed_distances = [initial], []
    gaps = np.empty((iterations, n))
    for step in range(iterations):
        aligned = []
        for person in range(n):
            rotation = rotations[step, person]
            require(np.max(np.abs(rotation.T @ rotation - np.eye(k))) <= GRAM_ATOL, "GPA rotation orthogonality")
            cross = gradients[person].T @ prior
            nuclear = math.fsum(float(v) for v in linalg.svdvals(cross))
            trace = math.fsum(float(x) * float(y) for x, y in zip(rotation.ravel(), cross.ravel()))
            gaps[step, person] = nuclear - trace
            require(nuclear - trace <= GPA_OPTIMALITY * max(1., nuclear), "GPA objective optimality")
            aligned.append(gradients[person] @ rotation)
        aligned = np.stack(aligned)
        current = np.mean(aligned, axis=0, dtype=np.float64)
        distance = float(np.sum((prior - current)**2, dtype=np.float64))
        require(math.isfinite(distance), "nonfinite GPA distance")
        close(history[step + 1], current, "GPA reference recurrence receipt")
        close(distances[step], distance, "GPA distance receipt")
        stopped = previous_distance is not None and abs(distance - previous_distance) < GPA_STOP_TOL
        if step + 1 < iterations:
            require(not stopped, "GPA continued after public stop")
        else:
            require(stopped or iterations == GPA_MAX_ITER, "GPA premature stop")
        replayed_history.append(current)
        replayed_distances.append(distance)
        prior, previous_distance = current, distance
    if saved_aligned is not None:
        close(saved_aligned, aligned, "aligned gradient receipt")
    return dict(aligned=aligned, reference_history=np.stack(replayed_history),
                distances=np.asarray(replayed_distances), optimality_gaps=gaps,
                n_iterations=iterations)
