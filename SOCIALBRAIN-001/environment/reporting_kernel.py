"""Prospective SOCIALBRAIN accepted-clean replay; pure numerical code, no I/O.

The original source reader owns geometry, cleaning and canonical activity. This
disclosed shared kernel never reconstructs a nuisance design from output receipts
and never uses displayed CSV values as downstream inputs. Production callers must
bind the fixed literal source cohort; smaller explicit counts support manufactured
qualification only. No source access or analysis occurs during module import.
"""
from __future__ import annotations

import math
from itertools import combinations

import numpy as np
from scipy import linalg, stats


ROI_IDS = ("DMPFC", "MMPFC", "VMPFC", "PCC", "RTPJ", "LTPJ",
           "rSII", "lSII", "rINS", "lINS", "dACC", "MFG")
PIPELINE_IDS = ("without_GSR", "with_GSR")
METRICS = ("within_tom", "within_pain", "across_network", "across_network_gsr")
FISHER_CAP = 0.999999
CLEAN_ATOL = 1e-7
CLEAN_RTOL = 1e-7
RELATIVE_FIDELITY = 1e-6
ACTIVITY_RELATIVE = 1e-12
EPS = np.finfo(np.float64).eps
FAMILIES = {
    "within_tom": (0, tuple(combinations(range(6), 2))),
    "within_pain": (0, tuple(combinations(range(6, 12), 2))),
    "across_network": (0, tuple((i, j) for i in range(6) for j in range(6, 12))),
    "across_network_gsr": (1, tuple((i, j) for i in range(6) for j in range(6, 12))),
}


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
    observed = real_array(observed, 3)
    reference = real_array(reference, 3)
    active = np.asarray(active)
    if (observed.shape != reference.shape or observed.shape[0] < 2
            or observed.shape[1:] != (2, 12) or active.dtype.kind != "b"
            or active.shape != (2, 12)):
        raise ValueError("clean_shape_or_active_type")
    if np.any(reference[:, ~active] != 0.0):
        raise ValueError("canonical_inactive_not_zero")
    with np.errstate(over="ignore", invalid="ignore"):
        close = np.abs(observed - reference) <= CLEAN_ATOL + CLEAN_RTOL * np.abs(reference)
    if not np.all(close):
        raise ValueError("clean_pointwise_fidelity")
    for arm, roi in zip(*np.nonzero(active)):
        source = reference[:, arm, roi]
        if _unit_centered(source) is None:
            raise ValueError("canonical_active_constant")
        if centered_relative_error(observed[:, arm, roi], source) > RELATIVE_FIDELITY:
            raise ValueError("clean_centered_fidelity")
    return observed, reference, active.copy()


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


def participant_metrics(clean, active):
    """Compute only the fixed four families; caller already source-bound clean."""
    clean = real_array(clean, 3)
    active = np.asarray(active)
    if (clean.shape[0] < 2 or clean.shape[1:] != (2, 12)
            or active.shape != (2, 12) or active.dtype.kind != "b"):
        raise ValueError("clean_shape_or_active_type")
    values, statuses = {}, {}
    for metric, (arm, pairs) in FAMILIES.items():
        if not all(active[arm, i] and active[arm, j] for i, j in pairs):
            values[metric], statuses[metric] = None, "inactive_roi"
            continue
        correlations = [pearson(clean[:, arm, i], clean[:, arm, j]) for i, j in pairs]
        if any(value is None for value in correlations):
            values[metric], statuses[metric] = None, "numerical_failure"
            continue
        zs = [math.atanh(max(-FISHER_CAP, min(FISHER_CAP, r))) for r in correlations]
        values[metric] = math.tanh(math.fsum(zs) / len(zs))
        statuses[metric] = "ok"
    return {"values": values, "statuses": statuses}


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


def rank_inference(age, accepted_values, mean_fd, canonical_values):
    """Own ranks after a separate canonical continuous fidelity/support guard."""
    age, y, motion, source = map(_vector, (age, accepted_values, mean_fd, canonical_values))
    if not age.shape == y.shape == motion.shape == source.shape:
        raise ValueError("vector_shape_mismatch")
    n = y.size
    projector = fd_rank_projector(motion)
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


def _null_child(n, n_defined, projector):
    return {"r": None, "p": None, "status": "incomplete_subject_support",
            "n_expected": n, "n_defined": n_defined, "df": n - 2,
            "motion_adjusted_rank_r": None, "motion_adjusted_rank_p": None,
            "motion_adjusted_rank_status": "incomplete_subject_support",
            "motion_adjusted_nuisance_rank": projector["rank"],
            "motion_adjusted_df": projector["df"]}


def analyze(accepted_clean, reference_clean, active, covariates, subject_ids,
            *, expected_children=122, expected_adults=33):
    """Return unrounded CSV rows and JSON values, not serialized artifact files.

    All dictionaries are keyed by the same literal IDs. Arrays are canonical
    [T, without/with_GSR, the twelve fixed ROI IDs]; parser joins/permutations are
    the caller's responsibility. No source or rounded CSV values are read here.
    """
    nc = _integer(expected_children, 1)
    na = _integer(expected_adults, 1)
    ids = list(subject_ids)
    if (len(ids) != nc + na or any(not isinstance(s, str) or not s for s in ids)
            or len(set(ids)) != len(ids)):
        raise ValueError("subject_ids")
    for mapping in (accepted_clean, reference_clean, active, covariates):
        if not isinstance(mapping, dict) or set(mapping) != set(ids):
            raise ValueError("subject_membership")
    people, canonical, children, adults = {}, {}, [], []
    for sid in ids:
        cov = covariates[sid]
        if not isinstance(cov, dict) or not {"age", "group", "mean_fd"} <= set(cov):
            raise ValueError("covariates")
        age = float(real_array(cov["age"], 0))
        motion = float(real_array(cov["mean_fd"], 0))
        group = cov["group"]
        if group not in ("child", "adult"):
            raise ValueError("group_token")
        (children if group == "child" else adults).append(sid)
        observed, source, mask = validate_clean_series(accepted_clean[sid], reference_clean[sid], active[sid])
        accepted = participant_metrics(observed, mask)
        canonical[sid] = participant_metrics(source, mask)
        row = {"subject_id": sid, "age": age, "group": group, "mean_fd": motion}
        row.update(accepted["values"])
        row.update({name + "_status": accepted["statuses"][name] for name in METRICS})
        people[sid] = row
    if len(children) != nc or len(adults) != na:
        raise ValueError("group_membership_count")
    # Canonical ordering prevents representation permutations changing fsum/QR.
    children, adults = sorted(children), sorted(adults)
    ages = [people[s]["age"] for s in children]
    motion = [people[s]["mean_fd"] for s in children]
    projector = fd_rank_projector(motion)
    effects = {"n_children": nc, "n_adults": na, "adult_means": {}, "adult_support": {}}
    for metric in METRICS:
        y = [people[s][metric] for s in children]
        n_defined = sum(value is not None for value in y)
        if n_defined != nc:
            effects[metric] = _null_child(nc, n_defined, projector)
        else:
            source_values = [canonical[s]["values"][metric] for s in children]
            if any(value is None for value in source_values):
                raise ValueError("canonical_metric_not_defined_for_active_reference")
            effects[metric] = rank_inference(ages, y, motion, source_values)
        values = [people[s][metric] for s in adults]
        n_defined = sum(value is not None for value in values)
        effects["adult_means"][metric] = math.fsum(values) / na if n_defined == na else None
        effects["adult_support"][metric] = {"n_expected": na, "n_defined": n_defined,
                                               "status": "ok" if n_defined == na else "incomplete_subject_support"}
    return {"participant_rows": [people[s] for s in ids], "age_effects": effects,
            "analysis_observed": {"child_motion_nuisance_rank": projector["rank"]}}
