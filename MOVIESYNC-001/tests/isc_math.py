"""MOVIESYNC source-bound ISC algebra; no loader, oracle imports, or answer bank.

Canonical support is computed before participant serialization. Accepted final
series determine every defined correlation; canonical ISC values are not gates.
Flexible dimensions are for manufactured fixtures; production checks live in
the keyed verifier. All formulas/tolerances are prospective public choices.
"""
from __future__ import annotations

import math
import numpy as np

SUPPORT_FACTOR = 1e-12
Fidelity_REL = 1e-6
SERIES_ATOL = SERIES_RTOL = 1e-7
RAW_ATOL, RAW_RTOL = 1e-5, 1e-6
SCALAR_ATOL = 1e-6


def require(condition, message):
    if not condition:
        raise ValueError(message)


def real_array(value, name, ndim=None):
    value = np.asarray(value)
    require(value.dtype.fields is None and value.dtype.kind in "iuf", f"{name}: real nonboolean array")
    if ndim is not None:
        require(value.ndim == ndim, f"{name}: wrong dimensions")
    result = np.asarray(value, dtype=np.float64)
    require(np.isfinite(result).all(), f"{name}: nonfinite")
    return result


def centered(values):
    x = real_array(values, "series", 1)
    require(x.size >= 2, "series needs at least two frames")
    if np.all(x == x[0]):
        return np.zeros_like(x)
    mean = math.fsum(float(v) for v in x) / len(x)
    d = x - mean
    require(np.isfinite(d).all(), "nonfinite centered series")
    return d


def stable_l2(values):
    x = real_array(values, "L2 input", 1)
    if not x.size:
        return 0.0
    scale = float(np.max(np.abs(x)))
    if scale == 0:
        return 0.0
    norm = scale * math.sqrt(math.fsum(float(v/scale)**2 for v in x))
    require(math.isfinite(norm), "nonfinite L2")
    return norm


def templates(values):
    x = real_array(values, "ISC inputs", 3)
    n, t, k = x.shape
    require(n >= 2 and t >= 2 and k >= 1, "ISC input shape")
    # Explicit self-exclusion: subtracting own value from a rounded total is
    # not our template reduction and can lose a small remaining contribution.
    result = np.empty_like(x)
    for i in range(n):
        for frame in range(t):
            for region in range(k):
                result[i, frame, region] = math.fsum(
                    float(x[j, frame, region]) for j in range(n) if j != i) / (n-1)
    require(np.isfinite(result).all(), "nonfinite LOO template")
    return result


def support(values):
    x = real_array(values, "canonical ISC inputs", 3)
    mt = templates(x)
    n, t, k = x.shape
    norms = np.empty((n, k), dtype=np.float64)
    template_norms = np.empty_like(norms)
    for i in range(n):
        for r in range(k):
            norms[i, r] = stable_l2(centered(x[i, :, r]))
            template_norms[i, r] = stable_l2(centered(mt[i, :, r]))
    threshold = SUPPORT_FACTOR * math.sqrt(t)
    return {"person_active": norms > threshold,
            "template_active": template_norms > threshold,
            "person_centered_l2": norms,
            "template_centered_l2": template_norms,
            "threshold": threshold}


def source_fidelity(actual, canonical):
    x = real_array(actual, "submitted ISC inputs", 3)
    ref = real_array(canonical, "canonical ISC inputs", 3)
    require(x.shape == ref.shape, "ISC source shape mismatch")
    require(np.all(np.abs(x-ref) <= SERIES_ATOL + SERIES_RTOL*np.abs(ref)),
            "source ISC input pointwise mismatch")
    basis = support(ref)
    own_templates, ref_templates = templates(x), templates(ref)
    for name, a, b, active in (("person", x, ref, basis["person_active"]),
                               ("template", own_templates, ref_templates, basis["template_active"])):
        for i, r in np.argwhere(active):
            da, db = centered(a[i, :, r]), centered(b[i, :, r])
            error, ref_norm = stable_l2(da-db), stable_l2(db)
            require(error <= Fidelity_REL*ref_norm,
                    f"source active {name} centered fidelity mismatch: {i}/{r}")
    return basis


def pearson(a, b):
    da, db = centered(a), centered(b)
    require(da.shape == db.shape, "Pearson shape mismatch")
    na, nb = stable_l2(da), stable_l2(db)
    require(na > 0 and nb > 0, "active Pearson input became constant")
    value = math.fsum(float(x/na)*float(y/nb) for x, y in zip(da, db))
    require(math.isfinite(value) and -1-1e-12 <= value <= 1+1e-12,
            "invalid Pearson arithmetic")
    return min(1.0, max(-1.0, value))


def complete_mean(values):
    values = list(values)
    if not values or any(v is None for v in values):
        return None
    return math.fsum(float(v) for v in values)/len(values)


def replay(values, canonical_support):
    """All arithmetic-r estimates, preserving complete denominators and nulls.

Pair/LOO support is source-authoritative, not reclassified using rounded values.
No per-output comparison to canonical correlations occurs here.
"""
    x = real_array(values, "accepted ISC inputs", 3)
    n, _, k = x.shape
    pa, ta = canonical_support["person_active"], canonical_support["template_active"]
    require(isinstance(pa, np.ndarray) and pa.dtype.kind == "b" and pa.shape == (n, k), "person support mask")
    require(isinstance(ta, np.ndarray) and ta.dtype.kind == "b" and ta.shape == (n, k), "template support mask")
    mt = templates(x)
    pair_values = {}
    for i in range(n):
        for j in range(i+1, n):
            for r in range(k):
                pair_values[i, j, r] = pearson(x[i, :, r], x[j, :, r]) if pa[i, r] and pa[j, r] else None
    per_person, per_region = [], []
    for i in range(n):
        row = []
        for r in range(k):
            partners = [pair_values[min(i,j), max(i,j), r] for j in range(n) if j != i]
            loo = pearson(x[i, :, r], mt[i, :, r]) if pa[i, r] and ta[i, r] else None
            row.append({"pairwise": complete_mean(partners), "loo": loo,
                        "n_pairs_expected": n-1, "n_pairs_defined": sum(v is not None for v in partners)})
        per_person.append(row)
    for r in range(k):
        pairs = [pair_values[i, j, r] for i in range(n) for j in range(i+1, n)]
        loos = [per_person[i][r]["loo"] for i in range(n)]
        per_region.append({"pairwise": complete_mean(pairs), "loo": complete_mean(loos),
                           "n_pairs_expected": n*(n-1)//2, "n_pairs_defined": sum(v is not None for v in pairs),
                           "n_loo_expected": n, "n_loo_defined": sum(v is not None for v in loos)})
    person_summary = [{est: complete_mean(row[r][est] for r in range(k)) for est in ("pairwise", "loo")}
                      for row in per_person]
    headline = {est: complete_mean(row[est] for row in person_summary) for est in ("pairwise", "loo")}
    return {"pairs": pair_values, "per_person_region": per_person,
            "per_region": per_region, "per_person": person_summary,
            "headline": headline}
