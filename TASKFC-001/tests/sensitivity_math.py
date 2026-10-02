"""External, source-free TASKFC numerical proposal; no I/O or source imports.

Canonical rank/projector uses SciPy gesvd (shared explicitly with the oracle).
NumPy SVD is only a qualification diagnostic, not a universal equivalent rank
rule. Glover/cosine primitives are shared pinned Nilearn implementations.
Clock/event source facts and serialization tolerances remain caller-supplied.
"""
from __future__ import annotations

import math
from numbers import Integral, Real
import warnings

import numpy as np
from scipy import linalg, special, stats
from nilearn.glm.first_level.design_matrix import create_cosine_drift
from nilearn.glm.first_level.hemodynamic_models import compute_regressor

EPS = np.finfo(np.float64).eps
MODELS = ("nuisance_only", "glover_task_residual")
ROIS = ("L_lateral_occipital", "R_lateral_occipital")
MOTION = ("X", "Y", "Z", "RotX", "RotY", "RotZ")
CONDITIONS = ("language", "string")
FISHER_CLIP = .999
ACTIVITY_FACTOR = 1e-12
CORRELATION_ROUNDOFF = 1e-12


def require(ok, message):
    if not ok:
        raise ValueError(message)


def scalar(value):
    require(isinstance(value, Real) and not isinstance(value, (bool, np.bool_)),
            "real numeric scalar required")
    result = float(value)
    require(math.isfinite(result), "finite scalar required")
    return result


def integer(value):
    require(isinstance(value, Integral) and not isinstance(value, (bool, np.bool_)),
            "typed integer required")
    require(0 <= value <= 2**63-1, "integer range")
    return int(value)


def array(value, ndim=None):
    # Inspect Python leaves before NumPy coercion can hide mixed [1, True].
    if not isinstance(value, np.ndarray):
        probe = np.asarray(value, dtype=object)
        for leaf in probe.flat:
            scalar(leaf)
    value = np.asarray(value)
    require(value.dtype.fields is None and value.dtype.kind in "iuf", "real array dtype")
    require(ndim is None or value.ndim == ndim, "array dimensionality")
    result = np.asarray(value, dtype=np.float64)
    require(np.isfinite(result).all(), "finite array required")
    return result


def mask(value, shape):
    result = np.asarray(value)
    require(result.dtype.kind == "b" and result.shape == shape, "Boolean mask shape")
    return result


def labels(value):
    result = np.asarray(value)
    require(result.ndim == 1 and result.dtype.kind in "US", "literal text axis")
    if result.dtype.kind == "S":
        result = np.char.decode(result, "utf-8")
    require(np.all(result != ""), "empty label")
    return result


def centered_scaled(values, *, scale=None):
    """Exact constants ->0; otherwise scale then accurate mean subtraction.

    Scaling protects norms/dot products; it is not an added signal floor.
    A shared explicit scale is used for centered source-fidelity differences.
    """
    values = array(values, 1)
    require(len(values) >= 2, "at least two frames")
    if np.all(values == values[0]):
        return np.zeros_like(values), 0. if scale is None else scalar(scale)
    scale = float(np.max(np.abs(values))) if scale is None else scalar(scale)
    require(scale > 0., "positive nonconstant scale")
    scaled = values / scale
    centered = scaled - math.fsum(map(float, scaled))/len(scaled)
    require(np.isfinite(centered).all(), "finite centered series")
    return centered, scale


def stable_l2(values):
    values = array(values, 1)
    peak = float(np.max(np.abs(values))) if len(values) else 0.
    if peak == 0.:
        return 0.
    result = peak * math.sqrt(math.fsum(float(v/peak)**2 for v in values))
    require(math.isfinite(result), "finite L2 required")
    return result


def centered_l2(values):
    shifted, scale = centered_scaled(values)
    result = scale * stable_l2(shifted)
    require(math.isfinite(result), "finite physical centered L2")
    return result


def build_design(frame_times, onsets, durations, conditions, modulation, motion,
                 *, high_pass, oversampling, min_onset):
    """Two nested, unregularized designs; no hidden full_rank or frame trimming.

    Exact frame clock and original event interpretation are authenticated
    upstream. Both literal conditions must occur. Duplicate event triples sum
    their amplitudes accurately in first-occurrence order, while the caller
    retains every original source row in the event ledger.
    """
    times = array(frame_times, 1)
    require(len(times) >= 2 and np.all(np.diff(times) > 0), "increasing frame clock")
    onset, duration, amplitude = array(onsets, 1), array(durations, 1), array(modulation, 1)
    condition = labels(conditions)
    require(onset.shape == duration.shape == amplitude.shape == condition.shape,
            "complete event axes")
    require(np.all(duration >= 0), "nonnegative duration")
    require(set(condition.tolist()) == set(CONDITIONS), "both and only modeled conditions")
    nuisance = array(motion, 2)
    require(nuisance.shape == (len(times), 6), "six motion columns and all frames")
    high_pass, min_onset = scalar(high_pass), scalar(min_onset)
    oversampling = integer(oversampling)
    require(high_pass > 0 and oversampling > 0, "positive design parameters")
    require(np.all(onset >= times[0]+min_onset), "event precedes declared HRF sampling window")
    grouped = {}
    for name, start, length, weight in zip(condition, onset, duration, amplitude):
        grouped.setdefault((str(name), float(start), float(length)), []).append(float(weight))
    event_rows = [(name, start, length, math.fsum(weights))
                  for (name, start, length), weights in grouped.items()]
    require(all(math.isfinite(row[3]) for row in event_rows), "finite combined event amplitude")
    columns, present = [], []
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        drift = create_cosine_drift(high_pass, times)
        for name in CONDITIONS:
            selected = [row for row in event_rows if row[0] == name]
            present.append(bool(selected))
            values, names = compute_regressor(
                tuple(np.asarray([row[k] for row in selected]) for k in (1, 2, 3)),
                "glover", times, con_id=name, oversampling=oversampling,
                min_onset=min_onset)
            require(values.shape == (len(times), 1) and names == [name], "Glover column")
            columns.append(values[:, 0])
    nuisance_design = np.column_stack([np.ones(len(times)), drift[:, :-1], nuisance])
    task_design = np.column_stack(columns)
    full_design = np.column_stack([nuisance_design, task_design])
    array(full_design, 2)
    nuisance_names = ["intercept", *[f"drift_{k+1}" for k in range(drift.shape[1]-1)], *MOTION]
    return dict(nuisance_design=nuisance_design, task_design=task_design,
                full_design=full_design, nuisance_columns=nuisance_names,
                full_columns=[*nuisance_names, *CONDITIONS], frame_times=times.copy(),
                condition_present=np.asarray(present, dtype=bool),
                warnings=[dict(category=type(w.message).__name__, message=str(w.message))
                          for w in caught])


def fit_residuals(response, design):
    """Canonical gesvd rank and retained-left-space orthogonal residual."""
    y, x = (np.ascontiguousarray(array(value, 2), dtype=np.float64)
            for value in (response, design))
    require(y.shape == (len(x), 2) and min(x.shape) > 0 and len(x) >= 2, "fit axes")
    u, singular, _ = linalg.svd(x, full_matrices=False, check_finite=True,
                                lapack_driver="gesvd")
    cutoff = float(max(x.shape) * EPS * singular[0])
    keep = singular > cutoff
    retained = u[:, keep]
    residual = y - retained @ (retained.T @ y)
    array(residual, 2)
    return dict(residuals=residual, design_rank=int(keep.sum()),
                residual_df=len(x)-int(keep.sum()), singular_values=singular,
                rank_cutoff=cutoff)


def source_support(raw, residuals):
    raw, residuals = array(raw, 2), array(residuals, 3)
    require(raw.shape == (len(raw), 2) and len(raw) >= 2,
            "complete raw two-ROI series")
    require(residuals.shape == (len(raw), 2, 2), "frame/model/ROI residual axes")
    raw_sd = np.asarray([centered_l2(raw[:, j])/math.sqrt(len(raw)-1) for j in range(2)])
    norms = np.asarray([[centered_l2(residuals[:, m, j]) for j in range(2)] for m in range(2)])
    threshold = ACTIVITY_FACTOR*math.sqrt(len(raw))*np.maximum(1., raw_sd)
    require(np.isfinite(threshold).all(), "finite activity threshold")
    return dict(raw_sample_sd=raw_sd, residual_centered_l2=norms,
                activity_threshold=threshold, active=norms > threshold[None, :])


def residual_fidelity(submitted, canonical, active, *, atol, rtol, centered_rtol=1e-6):
    own, source = array(submitted, 3), array(canonical, 3)
    require(own.shape == source.shape and len(source) >= 2 and source.shape[1:] == (2, 2),
            "exact residual axes")
    active = mask(active, (2, 2))
    atol, rtol, centered_rtol = scalar(atol), scalar(rtol), scalar(centered_rtol)
    require(min(atol, rtol, centered_rtol) >= 0., "nonnegative tolerances")
    require(np.all(np.abs(own-source) <= atol+rtol*np.abs(source)), "pointwise source fidelity")
    for m in range(2):
        for j in range(2):
            if not active[m, j]:
                continue
            scale = max(float(np.max(np.abs(own[:, m, j]))),
                        float(np.max(np.abs(source[:, m, j]))))
            require(scale > 0., "active canonical support")
            observed, _ = centered_scaled(own[:, m, j], scale=scale)
            expected, _ = centered_scaled(source[:, m, j], scale=scale)
            norm = stable_l2(expected)
            require(norm > 0., "active canonical column nonconstant")
            require(stable_l2(observed-expected) <= centered_rtol*norm,
                    "relative centered source fidelity")
    return own


def pearson(left, right):
    left, right = array(left, 1), array(right, 1)
    require(left.shape == right.shape, "paired frame shape")
    x, _ = centered_scaled(left)
    y, _ = centered_scaled(right)
    denominator = stable_l2(x)*stable_l2(y)
    require(denominator > 0. and math.isfinite(denominator), "active Pearson support")
    value = math.fsum(float(a)*float(b) for a, b in zip(x, y))/denominator
    require(math.isfinite(value) and abs(value) <= 1.+CORRELATION_ROUNDOFF,
            "Pearson arithmetic excursion")
    return min(1., max(-1., value))


def fisher(value):
    value = scalar(value)
    require(-1. <= value <= 1., "correlation domain")
    return math.atanh(min(FISHER_CLIP, max(-FISHER_CLIP, value)))


def derive_subject(residuals, active):
    residuals, active = array(residuals, 3), mask(active, (2, 2))
    require(residuals.shape[1:] == (2, 2) and len(residuals) >= 2, "residual axes")
    values, zs, statuses = [], [], []
    for m in range(2):
        status = ("ok" if active[m].all() else "inactive_both" if not active[m].any()
                  else "inactive_left" if not active[m, 0] else "inactive_right")
        value = pearson(residuals[:, m, 0], residuals[:, m, 1]) if status == "ok" else None
        values.append(value)
        zs.append(fisher(value) if value is not None else None)
        statuses.append(status)
    delta = zs[0]-zs[1] if all(v is not None for v in zs) else None
    return dict(region_a=ROIS[0], region_b=ROIS[1], raw_status=statuses[0],
                background_status=statuses[1], connectivity=values[0],
                background_connectivity=values[1], raw_fisher_z=zs[0],
                background_fisher_z=zs[1], paired_status="ok" if delta is not None else "incomplete_support",
                raw_minus_background_z=delta)


def paired_summary(differences, expected_n):
    n = integer(expected_n)
    require(n >= 2 and len(differences) == n, "complete declared independent people")
    values = [None if v is None else scalar(v) for v in differences]
    present = [v for v in values if v is not None]
    result = dict(status="incomplete_support", n_expected=n, n_defined=len(present),
                  mean_raw_minus_background_z=None, sample_sd=None, standard_error=None,
                  df=None, t=None, p=None, ci95=None)
    if len(present) != n:
        return result
    mean = math.fsum(present)/n
    if min(present) == max(present):
        return dict(result, status="zero_variance", mean_raw_minus_background_z=present[0],
                    sample_sd=0., standard_error=0., df=n-1, ci95=[present[0], present[0]])
    deviations = np.asarray(present)-mean
    sd = stable_l2(deviations)/math.sqrt(n-1)
    se = sd/math.sqrt(n)
    require(se > 0., "nonconstant standard error underflow")
    t = mean/se
    require(math.isfinite(t), "finite nonzero-SE statistic")
    df = n-1
    tail = 0. if abs(t) > math.sqrt(np.finfo(float).max-df) else df/(df+t*t)
    p = float(special.betainc(df/2., .5, tail))
    half = float(stats.t.ppf(.975, df))*se
    require(all(math.isfinite(v) for v in (mean, sd, se, p, half, mean-half, mean+half)),
            "finite paired summary")
    return dict(result, status="ok", mean_raw_minus_background_z=mean, sample_sd=sd,
                standard_error=se, df=df, t=t, p=p, ci95=[mean-half, mean+half])


def summarize_subjects(subject_rows, participant_ids):
    """Rows MUST be derive_subject outputs from one accepted-residual replay.

    Serialized participant r/z receipts are never inputs to this function.
    """
    ids = labels(participant_ids).tolist()
    require(len(ids) >= 2 and len(set(ids)) == len(ids), "unique complete literal cohort")
    require(isinstance(subject_rows, dict) and set(subject_rows) == set(ids), "exact participant membership")
    groups = []
    for key in ("raw_fisher_z", "background_fisher_z"):
        values = [subject_rows[pid][key] for pid in ids]
        defined = [scalar(v) for v in values if v is not None]
        mean = math.fsum(defined)/len(ids) if len(defined) == len(ids) else None
        groups.append(dict(status="ok" if mean is not None else "incomplete_support",
                           n_expected=len(ids), n_defined=len(defined), mean_z=mean,
                           fisher_mean_r=math.tanh(mean) if mean is not None else None))
    a, b = [item["fisher_mean_r"] for item in groups]
    paired = paired_summary([subject_rows[pid]["raw_minus_background_z"] for pid in ids], len(ids))
    return dict(n_subjects=len(ids), region_a=ROIS[0], region_b=ROIS[1],
                raw=groups[0], background=groups[1],
                difference_of_group_fisher_mean_r=a-b if a is not None and b is not None else None,
                paired_z_sensitivity=paired)


def derive_cohort(residuals_by_id, active_by_id, participant_ids):
    ids = labels(participant_ids).tolist()
    require(len(ids) >= 2 and len(set(ids)) == len(ids), "unique cohort IDs")
    require(set(residuals_by_id) == set(active_by_id) == set(ids), "closed participant mappings")
    rows = {pid: dict(subject=pid, **derive_subject(residuals_by_id[pid], active_by_id[pid])) for pid in ids}
    return dict(per_subject=rows, summary=summarize_subjects(rows, ids))
