"""DEVCONN accepted-clean replay: prospective pure shared math, no source I/O.

Stable centering/fidelity and rank helpers are adapted self-contained from PR198
reporting kernel SHA89db8ca04db493d5f8522246200b7c8b11562856b2fb977f201748b1ebb1f4d6.
DEVCONN differs: one filtered arm, canonical eligible edges in distance tertiles,
mean signed Fisher-z WITHOUT tanh, and all 1000 seed-11 participant resamples.
Canonical source support/FD/age/geometry are inputs, not rounded output receipts.
All geometric sphere supports must be nonempty (caller failed-precondition gate);
false active bits here denote only canonical post-clean numerical inactivity.
Production callers authenticate literal155/Power264; explicit smaller dimensions
are for manufactured qualification. Importing this module performs no analysis.
"""
from __future__ import annotations

import math

import numpy as np
from scipy import linalg, stats
from scipy.spatial.distance import pdist

METRICS = ("short_range", "long_range", "segregation")
ASSOCIATIONS = ("raw", "motion_adjusted")
FISHER_CAP = 0.999
CLEAN_ATOL = CLEAN_RTOL = 1e-7
RELATIVE_FIDELITY = 1e-6
ACTIVITY_RELATIVE = 1e-12
FD_THRESHOLD = 0.2
BOOTSTRAP_DRAWS = 1000
BOOTSTRAP_SEED = 11
EPS = np.finfo(np.float64).eps


def _has_bool(value):
    if isinstance(value, (bool, np.bool_)):
        return True
    if isinstance(value, (list, tuple)):
        return any(_has_bool(item) for item in value)
    return False


def real_array(value, ndim=None):
    """Strict finite real input; do not coerce Boolean/string/object data."""
    if _has_bool(value):
        raise ValueError("boolean_numeric_input")
    arr = np.asarray(value)
    if arr.dtype.kind not in "iuf" or (ndim is not None and arr.ndim != ndim):
        raise ValueError("real_array_type_or_shape")
    arr = np.array(arr, dtype=np.float64, order="C", copy=True)
    if not np.isfinite(arr).all():
        raise ValueError("nonfinite_numeric_input")
    return arr


def _vector(value):
    arr = real_array(value, 1)
    if arr.size == 0:
        raise ValueError("empty_vector")
    return arr


def _integer(value, minimum=0):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
        raise ValueError("integer_type")
    value = int(value)
    if value < minimum:
        raise ValueError("integer_domain")
    return value


def _center_parts(value):
    """Return dimensionless C(x)/scale and positive scale, or exact zeros."""
    x = _vector(value)
    if np.all(x == x[0]):
        return np.zeros_like(x), 1.0
    scale = float(np.max(np.abs(x)))
    scaled = x / scale
    centered = scaled - math.fsum(float(v) for v in scaled) / x.size
    return centered, scale


def _norm_parts(value, scale=1.0):
    """Represent L2*scale as mantissa/exponent without restoring huge scales."""
    maximum = float(np.max(np.abs(value)))
    if maximum == 0.0:
        return 0.0, 0
    normalized = value / maximum
    length = math.sqrt(math.fsum(float(v) * float(v) for v in normalized))
    a, ea = math.frexp(maximum)
    b, eb = math.frexp(float(scale))
    c, ec = math.frexp(length)
    mantissa, adjust = math.frexp(a * b * c)
    return mantissa, ea + eb + ec + adjust


def _ratio(numerator, denominator):
    if denominator[0] == 0.0:
        return math.inf if numerator[0] else 0.0
    if numerator[0] == 0.0:
        return 0.0
    try:
        return math.ldexp(numerator[0] / denominator[0], numerator[1] - denominator[1])
    except OverflowError:
        return math.inf


def _unit_centered(value):
    centered, _ = _center_parts(value)
    maximum = float(np.max(np.abs(centered)))
    if maximum == 0.0:
        return None
    normalized = centered / maximum
    length = math.sqrt(math.fsum(float(v) * float(v) for v in normalized))
    return normalized / length


def centered_relative_error(observed, reference):
    """Relative centered L2, no absolute floor; constants are handled separately."""
    x, sx = _center_parts(observed)
    y, sy = _center_parts(reference)
    if x.shape != y.shape:
        raise ValueError("vector_shape_mismatch")
    if _norm_parts(y)[0] == 0.0:
        return 0.0 if _norm_parts(x)[0] == 0.0 else math.inf
    if _norm_parts(x)[0] == 0.0:
        return 1.0
    # A constant has no centered scale. Its arbitrary sentinel scale must not
    # force a subnormal reference direction through a unit-scale subtraction.
    scale = max(sx if _norm_parts(x)[0] else 0.0, sy)
    difference = x * (sx / scale) - y * (sy / scale)
    return _ratio(_norm_parts(difference, scale), _norm_parts(y, sy))


def residual_active(residual, raw):
    """Public 1e-12 relative activity, useful to independently test the rule."""
    r, sr = _center_parts(residual)
    y, sy = _center_parts(raw)
    if r.shape != y.shape:
        raise ValueError("vector_shape_mismatch")
    original = _norm_parts(y, sy)
    return original[0] > 0.0 and _ratio(_norm_parts(r, sr), original) > ACTIVITY_RELATIVE


def validate_continuous_fidelity(observed, reference):
    """Return canonical continuous support; never require canonical rank ties.

    If source values are exactly constant under declared centering, output jitter
    cannot create child association support. It is not itself rejected here.
    Adult means do not call this cohort-variation guard.
    """
    observed = _vector(observed)
    reference = _vector(reference)
    if observed.shape != reference.shape:
        raise ValueError("vector_shape_mismatch")
    centered, _ = _center_parts(reference)
    if _norm_parts(centered)[0] == 0.0:
        return False
    if centered_relative_error(observed, reference) > RELATIVE_FIDELITY:
        raise ValueError("continuous_centered_fidelity")
    return True


def validate_clean_series(observed, reference, active):
    observed, reference = real_array(observed, 2), real_array(reference, 2)
    active = np.asarray(active)
    if (observed.shape != reference.shape or observed.shape[0] < 2
            or active.dtype.kind != "b" or active.shape != (observed.shape[1],)):
        raise ValueError("clean_shape_or_active_type")
    if np.any(reference[:, ~active] != 0):
        raise ValueError("canonical_inactive_not_zero")
    with np.errstate(over="ignore", invalid="ignore"):
        close = np.abs(observed - reference) <= CLEAN_ATOL + CLEAN_RTOL * np.abs(reference)
    if not np.all(close):
        raise ValueError("clean_pointwise_fidelity")
    for roi in np.flatnonzero(active):
        if _unit_centered(reference[:, roi]) is None:
            raise ValueError("canonical_active_constant")
        if centered_relative_error(observed[:, roi], reference[:, roi]) > RELATIVE_FIDELITY:
            raise ValueError("clean_centered_fidelity")
    return observed, reference, active.copy()


def distance_bins(coordinates, roi_ids):
    """Canonical coordinates only; source row order, strict linear tertiles."""
    coords = real_array(coordinates, 2)
    ids = list(roi_ids)
    if (coords.shape != (len(ids), 3) or len(ids) < 2
            or any(not isinstance(s, str) or not s for s in ids)
            or len(set(ids)) != len(ids)):
        raise ValueError("roi_axis")
    distances = pdist(coords, metric="euclidean")
    if not np.isfinite(distances).all():
        raise ValueError("nonfinite_distance")
    q1, q2 = np.quantile(distances, [1 / 3, 2 / 3], method="linear")
    i, j = np.triu_indices(len(ids), 1)
    return {"roi_ids": ids, "pairs": np.column_stack((i, j)),
            "distances_mm": distances, "q1_mm": float(q1), "q2_mm": float(q2),
            "short_range": distances < q1, "long_range": distances > q2,
            "n_pairs": int(distances.size)}


def correlation_matrix(clean, active):
    """Stable scaled directions, then one float64 U.T @ U (not per-edge dots).

    Each column uses accurate centering and stable L2 normalization. Inactive or
    zero-norm columns have zero placeholders and an explicit false support bit.
    No new near-constant threshold is introduced here.
    """
    clean = real_array(clean, 2)
    active = np.asarray(active)
    if clean.shape[0] < 2 or active.shape != (clean.shape[1],) or active.dtype.kind != "b":
        raise ValueError("matrix_shape_or_active_type")
    directions = np.zeros_like(clean)
    defined = np.zeros(clean.shape[1], dtype=bool)
    for roi in np.flatnonzero(active):
        unit = _unit_centered(clean[:, roi])
        if unit is not None:
            directions[:, roi] = unit
            defined[roi] = True
    directions = np.ascontiguousarray(directions)
    return directions.T @ directions, defined


def checked_correlations(values):
    values = real_array(values, 1)
    if np.any(np.abs(values) > 1.0 + 1e-12):
        return None
    return np.clip(values, -1.0, 1.0)


def participant_metrics(clean, active, bins):
    """Eligible edges fixed by canonical active mask and canonical bin membership."""
    clean = real_array(clean, 2)
    if clean.shape[1] != len(bins["roi_ids"]):
        raise ValueError("roi_shape")
    correlation, defined = correlation_matrix(clean, active)
    i, j = bins["pairs"].T
    eligible = np.asarray(active)[i] & np.asarray(active)[j]
    values, statuses, counts = {}, {}, {}
    for name in METRICS[:2]:
        nominal = bins[name]
        selected = nominal & eligible
        used = int(np.count_nonzero(selected))
        counts[name] = {"n_nominal_edges": int(np.count_nonzero(nominal)),
                        "n_used_edges": used}
        if used == 0:
            values[name], statuses[name] = None, "empty_edge_family"
            continue
        if not np.all(defined[i[selected]] & defined[j[selected]]):
            values[name], statuses[name] = None, "numerical_failure"
            continue
        rs = checked_correlations(correlation[i[selected], j[selected]])
        if rs is None:
            values[name], statuses[name] = None, "numerical_failure"
            continue
        zs = np.arctanh(np.clip(rs, -FISHER_CAP, FISHER_CAP))
        values[name] = math.fsum(float(z) for z in zs) / used
        statuses[name] = "ok"
    if any(values[name] is None for name in METRICS[:2]):
        values["segregation"], statuses["segregation"] = None, "incomplete_edge_families"
    else:
        values["segregation"] = values["short_range"] - values["long_range"]
        statuses["segregation"] = "ok"
    return {"values": values, "statuses": statuses, "edge_counts": counts}


def pearson(x, y):
    x, y = _vector(x), _vector(y)
    if x.shape != y.shape:
        raise ValueError("vector_shape_mismatch")
    a, b = _unit_centered(x), _unit_centered(y)
    if a is None or b is None:
        return None
    r = math.fsum(float(v) * float(w) for v, w in zip(a, b))
    if not math.isfinite(r) or abs(r) > 1.0 + 1e-12:
        return None
    return max(-1.0, min(1.0, r))


def fd_rank_projector(mean_fd):
    motion = _vector(mean_fd)
    ranks = stats.rankdata(motion, method="average")
    design = np.ascontiguousarray(np.column_stack((np.ones(motion.size), ranks)), dtype=np.float64)
    u, singular, _ = linalg.svd(design, full_matrices=False, lapack_driver="gesvd", check_finite=True)
    cutoff = max(design.shape) * EPS * float(singular[0])
    keep = singular > cutoff
    return {"basis": np.ascontiguousarray(u[:, keep]), "rank": int(np.sum(keep)),
            "df": int(motion.size - np.sum(keep) - 1), "cutoff": cutoff}


def _rank_residual(ranks, basis):
    centered, scale = _center_parts(ranks)
    # All rank vectors are bounded by n, so restoration here is representable.
    centered = centered * scale
    return centered - basis @ (basis.T @ centered)


def correlation_inference(r, df):
    """Conventional t approximation; supported exact perfection has no infinity."""
    if isinstance(df, (bool, np.bool_)) or not isinstance(df, (int, np.integer)):
        raise ValueError("df_type")
    df = int(df)
    if df <= 0:
        return {"r": None, "p": None, "status": "insufficient_df"}
    if r is None:
        return {"r": None, "p": None, "status": "numerical_failure"}
    rr = real_array(r, 0)
    r = float(rr)
    if abs(r) > 1.0:
        raise ValueError("correlation_domain")
    if abs(r) == 1.0:
        return {"r": r, "p": 0.0, "status": "perfect_correlation"}
    statistic = r * math.sqrt(df / (1.0 - r * r))
    p = float(2.0 * stats.t.sf(abs(statistic), df))
    if not math.isfinite(p) or not 0.0 <= p <= 1.0:
        return {"r": None, "p": None, "status": "numerical_failure"}
    return {"r": r, "p": p, "status": "ok"}


def rank_inference(age, accepted_values, mean_fd, canonical_values, *, _projector=None):
    """Own ranks after a separate canonical continuous fidelity/support guard."""
    age, y, motion, source = map(_vector, (age, accepted_values, mean_fd, canonical_values))
    if not age.shape == y.shape == motion.shape == source.shape:
        raise ValueError("vector_shape_mismatch")
    n = y.size
    projector = fd_rank_projector(motion) if _projector is None else _projector
    output = {"n_expected": n, "n_defined": n, "df": n - 2,
              "motion_adjusted_nuisance_rank": projector["rank"],
              "motion_adjusted_df": projector["df"]}
    supported = validate_continuous_fidelity(y, source)
    age_rank = stats.rankdata(age, method="average")
    value_rank = stats.rankdata(y, method="average")

    def one(adjusted):
        df = projector["df"] if adjusted else n - 2
        if df <= 0:
            return {"r": None, "p": None, "status": "insufficient_df"}
        if not supported:
            return {"r": None, "p": None, "status": "constant_source_metric"}
        a, b = age_rank, value_rank
        if adjusted:
            a = _rank_residual(a, projector["basis"])
            b = _rank_residual(b, projector["basis"])
            age_active = residual_active(a, age_rank)
            value_active = residual_active(b, value_rank)
        else:
            age_active = _unit_centered(a) is not None
            value_active = _unit_centered(b) is not None
        if not age_active:
            return {"r": None, "p": None, "status": "inactive_age_rank"}
        if not value_active:
            return {"r": None, "p": None, "status": "inactive_connectivity_rank"}
        return correlation_inference(pearson(a, b), df)

    ordinary, adjusted = one(False), one(True)
    output.update(ordinary)
    output.update({"motion_adjusted_rank_r": adjusted["r"],
                   "motion_adjusted_rank_p": adjusted["p"],
                   "motion_adjusted_rank_status": adjusted["status"]})
    return output


def _nullable_vector(values):
    if not isinstance(values, (list, tuple, np.ndarray)) or len(values) == 0:
        raise ValueError("nullable_vector")
    return [None if v is None else float(real_array(v, 0)) for v in values]


def _sample_inference(age, values, motion, source, projector):
    """One complete resample. Null slots are retained, never dropped/redrawn."""
    n = len(age)
    count = sum(v is not None for v in values)
    if count != n:
        return {"r": None, "p": None, "status": "incomplete_subject_support",
                "motion_adjusted_rank_r": None, "motion_adjusted_rank_p": None,
                "motion_adjusted_rank_status": "incomplete_subject_support",
                "n_expected": n, "n_defined": count, "df": n - 2,
                "motion_adjusted_nuisance_rank": projector["rank"],
                "motion_adjusted_df": projector["df"]}
    if any(v is None for v in source):
        raise ValueError("canonical_metric_missing_for_defined_accepted")
    result = rank_inference(age, values, motion, source, _projector=projector)
    result["n_defined"] = n
    return result


def bootstrap_indices(n):
    n = _integer(n, 1)
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    return np.stack([rng.integers(0, n, size=n) for _ in range(BOOTSTRAP_DRAWS)])


def percentile_interval(values, defined):
    x = real_array(values, 1)
    mask = np.asarray(defined)
    if x.size != BOOTSTRAP_DRAWS or mask.shape != x.shape or mask.dtype.kind != "b":
        raise ValueError("bootstrap_shape_or_type")
    n = int(np.count_nonzero(mask))
    if n != BOOTSTRAP_DRAWS:
        return {"ci95": None, "n_expected": BOOTSTRAP_DRAWS, "n_defined": n,
                "status": "incomplete_bootstrap_support"}
    return {"ci95": np.quantile(x, [.025, .975], method="linear").tolist(),
            "n_expected": BOOTSTRAP_DRAWS, "n_defined": n, "status": "ok"}


def child_estimates(age, values, motion, canonical_values):
    """Three aligned metric columns, one shared index matrix; receipts are outputs."""
    age, motion = _vector(age), _vector(motion)
    if age.shape != motion.shape or set(values) != set(METRICS) or set(canonical_values) != set(METRICS):
        raise ValueError("child_axes")
    ys = {m: _nullable_vector(values[m]) for m in METRICS}
    source = {m: _nullable_vector(canonical_values[m]) for m in METRICS}
    if any(len(v) != age.size for v in [*ys.values(), *source.values()]):
        raise ValueError("child_shape")
    projector = fd_rank_projector(motion)
    effects = {m: _sample_inference(age, ys[m], motion, source[m], projector) for m in METRICS}
    indices = bootstrap_indices(age.size)
    rs = np.zeros((BOOTSTRAP_DRAWS, len(METRICS), 2), dtype=np.float64)
    defined = np.zeros_like(rs, dtype=bool)
    statuses = np.full(rs.shape, "incomplete_subject_support", dtype="U40")
    ranks = np.zeros(BOOTSTRAP_DRAWS, dtype=np.int64)
    dfs = np.zeros(BOOTSTRAP_DRAWS, dtype=np.int64)
    for draw, index in enumerate(indices):
        ages, fd = age[index], motion[index]
        projection = fd_rank_projector(fd)
        ranks[draw], dfs[draw] = projection["rank"], projection["df"]
        for k, metric in enumerate(METRICS):
            y = [ys[metric][int(i)] for i in index]
            ref = [source[metric][int(i)] for i in index]
            result = _sample_inference(ages, y, fd, ref, projection)
            for arm, (value_key, status_key) in enumerate(
                    (("r", "status"), ("motion_adjusted_rank_r", "motion_adjusted_rank_status"))):
                value = result[value_key]
                statuses[draw, k, arm] = result[status_key]
                if value is not None:
                    rs[draw, k, arm], defined[draw, k, arm] = value, True
    for k, metric in enumerate(METRICS):
        for arm, name in enumerate(ASSOCIATIONS):
            effects[metric][name + "_bootstrap"] = percentile_interval(rs[:, k, arm], defined[:, k, arm])
    return {"effects": effects, "bootstrap": {
        "seed": BOOTSTRAP_SEED, "n_draws": BOOTSTRAP_DRAWS,
        "metric_ids": list(METRICS), "association_ids": list(ASSOCIATIONS),
        "indices": indices, "r": rs, "defined": defined, "status": statuses,
        "motion_nuisance_rank": ranks, "motion_df": dfs}}


def complete_mean(values):
    """Complete equal-person mean; exact constants first, otherwise scaled fsum."""
    values = _nullable_vector(values) if len(values) else []
    n, defined = len(values), sum(v is not None for v in values)
    value = None
    if n and defined == n:
        if all(v == values[0] for v in values):
            value = values[0]
        else:
            scale = max(abs(v) for v in values)
            value = scale * (math.fsum(v / scale for v in values) / n)
    return {"mean": value, "n_expected": n, "n_defined": defined,
            "status": "ok" if value is not None else "incomplete_subject_support"}


def _sample_variance(values):
    """Stable centered L2 squared/(n-1), with representational failure explicit."""
    centered, scale = _center_parts(values)
    mantissa, exponent = _norm_parts(centered, scale)
    if mantissa == 0:
        return 0.0, "ok"
    try:
        variance = math.ldexp(mantissa * mantissa / (len(values) - 1), 2 * exponent)
    except OverflowError:
        return None, "numerical_overflow"
    if not math.isfinite(variance):
        return None, "numerical_overflow"
    if variance == 0:
        return None, "numerical_underflow"
    return variance, "ok"


def welch_groups(child_values, adult_values, canonical_child_values, canonical_adult_values):
    """Own signed means/difference with source-conditioned variance support.

    Every complete nonconstant canonical group requires centered-relative fidelity.
    Canonical constant groups contribute variance zero despite accepted jitter.
    There is no canonical t/p/difference gate. Source-close signal validation is
    the caller's separate prerequisite; this function never reactivates support.
    """
    left, right = complete_mean(child_values), complete_mean(adult_values)
    variance_active = []
    for values, canonical in ((child_values, canonical_child_values),
                              (adult_values, canonical_adult_values)):
        source = _nullable_vector(canonical) if len(canonical) else []
        if len(values) != len(source):
            raise ValueError("welch_canonical_shape")
        if any(ref is None and value is not None for value, ref in zip(values, source)):
            raise ValueError("canonical_metric_missing_for_defined_accepted")
        variance_active.append(
            validate_continuous_fidelity(values, source)
            if len(values) and all(value is not None for value in values) else None)
    result = {"child": left, "adult": right, "difference": None,
              "t": None, "p": None, "df": None, "status": "incomplete_subject_support"}
    if left["mean"] is None or right["mean"] is None:
        return result
    difference = left["mean"] - right["mean"]
    if not math.isfinite(difference):
        result["status"] = "numerical_overflow"
        return result
    result["difference"] = difference
    if min(left["n_expected"], right["n_expected"]) < 2:
        result["status"] = "insufficient_group_size"
        return result
    v1, status1 = _sample_variance(child_values) if variance_active[0] else (0.0, "ok")
    v2, status2 = _sample_variance(adult_values) if variance_active[1] else (0.0, "ok")
    if status1 != "ok" or status2 != "ok":
        result["status"] = status1 if status1 != "ok" else status2
        return result
    a, b = v1 / len(child_values), v2 / len(adult_values)
    if (v1 > 0 and a == 0) or (v2 > 0 and b == 0):
        result["status"] = "numerical_underflow"
        return result
    scale = max(a, b)
    if scale == 0:
        result["status"] = "zero_standard_error"
        return result
    se2 = a + b
    if not math.isfinite(se2):
        result["status"] = "numerical_overflow"
        return result
    wa, wb = a / scale, b / scale
    df = (wa + wb) ** 2 / (wa * wa / (len(child_values) - 1) + wb * wb / (len(adult_values) - 1))
    t = difference / math.sqrt(se2)
    if not math.isfinite(t):
        result["status"] = "numerical_overflow"
        return result
    p = float(2 * stats.t.sf(abs(t), df))
    if not math.isfinite(p) or not 0 <= p <= 1:
        result["status"] = "numerical_failure"
        return result
    result.update({"t": t, "p": p, "df": df, "status": "ok"})
    return result


def analyze(accepted_clean, reference_clean, active, covariates, subject_ids,
            coordinates, roi_ids, *, expected_children=122, expected_adults=33,
            expected_rois=264):
    """Keyed source-bound dictionaries -> all unrounded receipts, no file I/O.

    Inputs have canonical source ROI/frame order; artifact parsing owns coherent
    axis permutations. Child draws always use sorted literal subject IDs.
    """
    nc, na, nr = (_integer(expected_children, 1), _integer(expected_adults, 1),
                  _integer(expected_rois, 2))
    ids = list(subject_ids)
    if (len(ids) != nc + na or len(set(ids)) != len(ids)
            or any(not isinstance(s, str) or not s for s in ids)):
        raise ValueError("subject_ids")
    for mapping in (accepted_clean, reference_clean, active, covariates):
        if not isinstance(mapping, dict) or set(mapping) != set(ids):
            raise ValueError("subject_membership")
    bins = distance_bins(coordinates, roi_ids)
    if len(bins["roi_ids"]) != nr:
        raise ValueError("roi_count")
    people, canonical, children, adults = {}, {}, [], []
    for sid in sorted(ids):
        cov = covariates[sid]
        if not isinstance(cov, dict) or not {"age", "group", "mean_fd"} <= set(cov):
            raise ValueError("covariates")
        age = float(real_array(cov["age"], 0))
        fd = float(real_array(cov["mean_fd"], 0))
        group = cov["group"]
        if group not in ("child", "adult") or fd < 0:
            raise ValueError("covariate_domain")
        (children if group == "child" else adults).append(sid)
        observed, source, mask = validate_clean_series(accepted_clean[sid], reference_clean[sid], active[sid])
        own, ref = participant_metrics(observed, mask, bins), participant_metrics(source, mask, bins)
        canonical[sid] = ref["values"]
        row = {"subject_id": sid, "age": age, "group": group, "mean_fd": fd,
               "n_active_rois": int(np.count_nonzero(mask)), **own["values"]}
        row.update({m + "_status": own["statuses"][m] for m in METRICS})
        for name in METRICS[:2]:
            row.update({name + "_" + key: value for key, value in own["edge_counts"][name].items()})
        people[sid] = row
    if len(children) != nc or len(adults) != na:
        raise ValueError("group_membership_count")
    age = [people[s]["age"] for s in children]
    fd = [people[s]["mean_fd"] for s in children]
    y = {m: [people[s][m] for s in children] for m in METRICS}
    source_y = {m: [canonical[s][m] for s in children] for m in METRICS}
    child = child_estimates(age, y, fd, source_y)
    group_means = {m: {"child": complete_mean([people[s][m] for s in children]),
                       "adult": complete_mean([people[s][m] for s in adults])} for m in METRICS}
    lowchild = [s for s in children if people[s]["mean_fd"] < FD_THRESHOLD]
    lowadult = [s for s in adults if people[s]["mean_fd"] < FD_THRESHOLD]
    restricted = welch_groups([people[s]["segregation"] for s in lowchild],
                              [people[s]["segregation"] for s in lowadult],
                              [canonical[s]["segregation"] for s in lowchild],
                              [canonical[s]["segregation"] for s in lowadult])
    restricted.update({"fd_thresh": FD_THRESHOLD, "child_ids": lowchild, "adult_ids": lowadult})
    effects = {"population": "children_only", "n_children": nc, "n_adults": na,
               "children_age_spearman": child["effects"], "group_means": group_means,
               "segregation_child_vs_adult": welch_groups(
                   [people[s]["segregation"] for s in children],
                   [people[s]["segregation"] for s in adults],
                   [canonical[s]["segregation"] for s in children],
                   [canonical[s]["segregation"] for s in adults]),
               "motion_control": {"segregation_low_motion_restriction": restricted}}
    child["bootstrap"]["subject_ids"] = children
    return {"participant_rows": [people[s] for s in sorted(ids)], "age_effects": effects,
            "bootstrap": child["bootstrap"], "bin_diagnostics": bins}
