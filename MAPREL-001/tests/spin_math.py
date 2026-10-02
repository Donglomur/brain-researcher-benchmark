"""Prospective MAPREL verifier arithmetic; no source or import-time execution.

Canonical geometry uses the disclosed pinned neuromaps generator. This is a
shared scientific dependency, not an independent assignment-algorithm claim.
Signed-map replay and source fidelity are implemented here independently.
"""
from __future__ import annotations

import math
import warnings

import numpy as np

import artifact_reader as a

METHODS = ("original", "vasa", "hungarian")
MAP_ATOL = MAP_RTOL = CENTERED_RTOL = 1e-6
GEOMETRY_ATOL = GEOMETRY_RTOL = 1e-7
SCALAR_ATOL = 1e-6
CORRELATION_ROUNDOFF = 1e-12  # arithmetic excursion only; never a tie epsilon


def array(value, ndim=None):
    if not isinstance(value, np.ndarray):
        probe = np.asarray(value, dtype=object)
        a.require(all(isinstance(x, (int, float, np.integer, np.floating))
                      and not isinstance(x, (bool, np.bool_)) for x in probe.flat),
                  "real non-Boolean array elements")
    result = np.asarray(value)
    a.require(result.dtype.fields is None and result.dtype.kind in "iuf", "real array dtype")
    a.require(ndim is None or result.ndim == ndim, "real array dimensions")
    result = result.astype(np.float64)
    a.require(np.isfinite(result).all(), "finite real array")
    return result


def integers(value, ndim=None):
    if not isinstance(value, np.ndarray):
        probe = np.asarray(value, dtype=object)
        a.require(all(not isinstance(x, (bool, np.bool_)) for x in probe.flat), "Boolean integer array")
    result = a.integer_array(np.asarray(value))
    a.require(ndim is None or result.ndim == ndim, "integer array dimensions")
    return result


def declaration(method, seed, count, *, production=True):
    a.require(type(method) is str and method in METHODS, "declared spin method")
    seed = a.integer(seed, json_number=True)
    count = a.integer(count, json_number=True)
    a.require(0 <= seed <= 2**32-1, "MT19937 seed range")
    a.require((100 if production else 1) <= count <= 4096, "spin count range")
    return method, seed, count


def center_scaled(value, *, scale=None):
    value = array(value, 1)
    a.require(len(value) >= 2, "at least two parcels")
    if np.all(value == value[0]):
        return np.zeros_like(value)
    scale = float(np.max(np.abs(value))) if scale is None else float(scale)
    a.require(math.isfinite(scale) and scale > 0, "positive finite centering scale")
    scaled = value / scale
    return scaled - math.fsum(float(x) for x in scaled) / len(scaled)


def norm(value):
    value = array(value, 1)
    peak = float(np.max(np.abs(value))) if len(value) else 0.
    if peak == 0: return 0.
    result = peak * math.sqrt(math.fsum(float(x/peak)**2 for x in value))
    a.require(math.isfinite(result), "finite L2 norm")
    return result


def active(value):
    return norm(center_scaled(value)) > 0


def pearson(left, right):
    left, right = center_scaled(left), center_scaled(right)
    a.require(left.shape == right.shape, "Pearson shape")
    denominator = norm(left) * norm(right)
    a.require(denominator > 0 and math.isfinite(denominator), "active Pearson denominator")
    result = math.fsum(float(x)*float(y) for x, y in zip(left, right)) / denominator
    a.require(math.isfinite(result) and abs(result) <= 1+CORRELATION_ROUNDOFF, "Pearson arithmetic")
    return max(-1., min(1., result))


def centered_fidelity(own, canonical):
    """No absolute floor; a shared prescale retains relative centered error."""
    own, canonical = array(own, 1), array(canonical, 1)
    a.require(own.shape == canonical.shape, "centered fidelity shape")
    if not active(canonical): return
    scale = max(float(np.max(np.abs(own))), float(np.max(np.abs(canonical))))
    reference = center_scaled(canonical, scale=scale)
    candidate = center_scaled(own, scale=scale)
    reference_norm = norm(reference)
    a.require(reference_norm > 0, "canonical active variation lost in common scale")
    a.require(norm(candidate-reference) <= CENTERED_RTOL*reference_norm, "centered source fidelity")


def mapping_rows(parcel_ids, mapped_ids):
    ids, mapped = integers(parcel_ids, 1), integers(mapped_ids, 2)
    a.require(len(ids) >= 2 and len(set(ids.tolist())) == len(ids), "unique parcel IDs")
    a.require(mapped.shape[0] == len(ids) and mapped.shape[1] >= 1, "complete mapping shape")
    by_id = {int(key): row for row, key in enumerate(ids)}
    a.require(set(mapped.ravel().tolist()) <= set(by_id), "mapped parcel IDs in source axis")
    return np.asarray([by_id[int(key)] for key in mapped.ravel()], dtype=np.int64).reshape(mapped.shape)


def map_fidelity(own, canonical, parcel_ids, mapped_ids):
    own, canonical = array(own, 2), array(canonical, 2)
    a.require(own.shape == canonical.shape and own.shape[1] == 2, "two signed source maps")
    a.require(np.all(np.abs(own-canonical) <= MAP_ATOL+MAP_RTOL*np.abs(canonical)),
              "signed pointwise source fidelity")
    rows = mapping_rows(parcel_ids, mapped_ids)
    a.require(rows.shape[0] == len(own), "source/map parcel shape")
    for column in range(2): centered_fidelity(own[:, column], canonical[:, column])
    # Required for many-to-one original maps; harmless/redundant for permutations.
    for rotation in range(rows.shape[1]):
        idx = rows[:, rotation]
        centered_fidelity(own[idx, 0], canonical[idx, 0])
    return own


def support_status(left, right):
    return "ok" if left and right else ("inactive_both" if not left and not right
                                       else "inactive_gradient" if not left else "inactive_thickness")


def summarize(observed_status, observed_r, null_records):
    """Pure exact rank rule on unrounded replay values, not receipt values."""
    n = len(null_records)
    a.require(n > 0, "complete null slots")
    defined = sum(row["status"] == "ok" for row in null_records)
    result = dict(observed_status=observed_status, pearson_r=observed_r,
                  null_distribution=null_records, n_null_expected=n, n_null_defined=defined,
                  n_exceedances=None, p_spin_numerator=None, p_spin_denominator=n+1, p_spin=None,
                  significant_after_spatial_null=None, inference_status="incomplete_support")
    if observed_status == "ok" and defined == n:
        count = sum(abs(row["r"]) >= abs(observed_r) for row in null_records)
        result.update(n_exceedances=count, p_spin_numerator=count+1, p_spin=(count+1)/(n+1),
                      significant_after_spatial_null=20*(count+1) < n+1,
                      inference_status="ok")
    return result


def replay(own, canonical, parcel_ids, mapped_ids):
    own = map_fidelity(own, canonical, parcel_ids, mapped_ids)
    canonical = array(canonical, 2)
    rows = mapping_rows(parcel_ids, mapped_ids)
    left, right = active(canonical[:, 0]), active(canonical[:, 1])
    status = support_status(left, right)
    observed = pearson(own[:, 0], own[:, 1]) if status == "ok" else None
    nulls = []
    for rotation in range(rows.shape[1]):
        idx = rows[:, rotation]
        status_null = support_status(active(canonical[idx, 0]), right)
        value = pearson(own[idx, 0], own[:, 1]) if status_null == "ok" else None
        nulls.append(dict(rotation_id=rotation, status=status_null, r=value))
    return summarize(status, observed, nulls)


def construct(centroids, hemisphere, parcel_ids, method, seed, count):
    """Use the published, version-pinned package for its exact discrete trace.

    No geometry receipt is supplied by the participant to this function. The
    oracle may independently implement the documented rotation/assignment loop;
    assignment ties and NumPy/SciPy numerical conventions remain shared.
    """
    method, seed, count = declaration(method, seed, count)
    xyz, hemi, ids = array(centroids, 2), integers(hemisphere, 1), integers(parcel_ids, 1)
    a.require(xyz.shape == (len(ids), 3) and hemi.shape == ids.shape, "canonical geometry shape")
    a.require(np.array_equal(ids, np.sort(ids)) and len(set(ids.tolist())) == len(ids), "canonical sorted IDs")
    a.require(set(hemi.tolist()) == {0, 1}, "two hemispheres")
    from neuromaps.nulls.spins import gen_spinsamples
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        positions = gen_spinsamples(xyz, hemi, n_rotate=count, check_duplicates=True,
                                    method=method, seed=seed, verbose=False, return_cost=False)
    positions = integers(positions, 2)
    a.require(positions.shape == (len(ids), count) and np.all((positions >= 0) & (positions < len(ids))),
              "package mapping shape/range")
    a.require(np.array_equal(hemi[positions], np.broadcast_to(hemi[:, None], positions.shape)),
              "package hemisphere locality")
    if method != "original":
        a.require(all(len(set(column.tolist())) == len(ids) for column in positions.T), "package bijections")
    return ids[positions], [str(item.message) for item in caught]
