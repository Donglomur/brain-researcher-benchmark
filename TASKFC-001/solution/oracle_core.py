"""Prospective TASKFC mathematics; no I/O, fetching, execution or fitted targets.

Clock/source facts remain explicit arguments until structural freeze. The public
HRF sampler, cosine construction and canonical SciPy gesvd are shared numerical
ingredients, not claimed independent algorithms. Source decoding and downstream
composition can be independently implemented. CSV scalars are receipts: a single
accepted-residual replay supplies every person and group quantity.
"""
from __future__ import annotations

import math
from collections import OrderedDict

import numpy as np
from scipy import linalg, stats
from nilearn.glm.first_level.hemodynamic_models import compute_regressor
from nilearn.signal import create_cosine_drift

ROI_NAMES = ("L_lateral_occipital", "R_lateral_occipital")
CENTERS = ((-30.0, -90.0, -6.0), (30.0, -90.0, -6.0))
MODEL_NAMES = ("nuisance_only", "glover_task_residual")
MOTION_NAMES = ("X", "Y", "Z", "RotX", "RotY", "RotZ")
TASK_NAMES = ("language", "string")
ACTIVITY_FACTOR = 1e-12
FISHER_CLIP = 0.999
EPS64 = np.finfo(np.float64).eps


def need(condition, message):
    if not condition:
        raise ValueError(message)


def no_bool(value):
    if isinstance(value, (bool, np.bool_)):
        raise ValueError("boolean_numeric_input")
    if isinstance(value, (list, tuple)):
        for item in value:
            no_bool(item)
    elif isinstance(value, np.ndarray):
        need(value.dtype.kind != "b", "boolean_numeric_input")
        if value.dtype.kind == "O":
            for item in value.flat:
                no_bool(item)


def scalar(value):
    no_bool(value)
    need(isinstance(value, (int, float, np.integer, np.floating)), "numeric_scalar")
    result = float(value)
    need(math.isfinite(result), "finite_scalar")
    return result


def array64(value, ndim):
    no_bool(value)
    a = np.asarray(value)
    need(a.ndim == ndim and a.dtype.kind in "iuf", "numeric_array_shape")
    a = np.ascontiguousarray(a, dtype=np.float64)
    need(np.isfinite(a).all(), "finite_array")
    return a


def centered(value):
    """Scaled accurate centering, exact constants first; no denominator epsilon."""
    x = array64(value, 1)
    need(len(x) >= 2, "insufficient_frames")
    if np.all(x == x[0]):
        return {"scaled": np.zeros_like(x), "scaled_l2": 0.0,
                "scale": abs(float(x[0])), "l2": 0.0, "sample_sd": 0.0}
    scale = float(np.max(np.abs(x)))
    u = x / scale
    c = u - math.fsum(map(float, u)) / len(u)
    norm = stable_l2(c)
    original_norm = scale * norm
    need(math.isfinite(original_norm), "nonfinite_centered_norm")
    return {"scaled": c, "scaled_l2": norm, "scale": scale,
            "l2": original_norm, "sample_sd": original_norm / math.sqrt(len(x)-1)}


def stable_l2(value):
    x = array64(value, 1)
    peak = float(np.max(np.abs(x))) if len(x) else 0.0
    if peak == 0:
        return 0.0
    norm = peak*math.sqrt(math.fsum((float(v)/peak)**2 for v in x))
    need(math.isfinite(norm), "finite_l2")
    return norm


def sphere_support(shape, affine, centers=CENTERS, radius=8.0):
    """Pure in-FOV physical voxel-center spheres; no implicit mask or rescue."""
    need(isinstance(shape, (list, tuple)) and len(shape) == 3, "shape3")
    need(all(isinstance(v, (int, np.integer)) and not isinstance(v, (bool, np.bool_))
             and v > 0 for v in shape), "positive_integer_shape")
    a = array64(affine, 2)
    need(a.shape == (4, 4) and np.array_equal(a[3], [0, 0, 0, 1]), "affine_shape")
    need(np.linalg.det(a[:3, :3]) != 0, "singular_affine")
    c = array64(centers, 2)
    need(c.shape == (2, 3), "two_centers")
    radius = scalar(radius)
    need(radius > 0, "positive_radius")
    ijk = np.indices(shape, dtype=np.int64).reshape(3, -1).T
    xyz = ijk @ a[:3, :3].T + a[:3, 3]
    need(np.isfinite(xyz).all(), "nonfinite_world_grid")
    supports = []
    for point in c:
        d = xyz - point
        distance2 = d[:, 0]*d[:, 0] + d[:, 1]*d[:, 1] + d[:, 2]*d[:, 2]
        indices = np.flatnonzero(distance2 <= radius*radius)
        need(len(indices) > 0, "empty_sphere")
        supports.append(indices)
    return tuple(supports)


def voxel_mean(volume, support):
    """Volume is already calibrated; only measured support must be finite."""
    no_bool(volume)
    image = np.asarray(volume)
    need(image.ndim == 3 and image.dtype.kind in "iuf", "numeric_volume")
    ids = np.asarray(support)
    need(ids.ndim == 1 and ids.dtype.kind in "iu" and len(ids) > 0, "support_indices")
    need(np.all(ids >= 0) and np.all(ids < image.size), "support_bounds")
    need(np.all(ids[1:] > ids[:-1]), "support_sorted_unique")
    selected = np.ascontiguousarray(image.ravel(order="C")[ids], dtype=np.float64)
    need(np.isfinite(selected).all(), "nonfinite_selected_voxels")
    mean = float(np.mean(selected, dtype=np.float64))
    need(math.isfinite(mean), "nonfinite_voxel_mean")
    return mean


def build_design(n_frames, tr, frame_origin, events, motion,
                 motion_names=MOTION_NAMES, high_pass=0.01,
                 oversampling=50, min_onset=-24.0):
    """Explicit unregularized Glover and cosine components; source facts generic."""
    need(isinstance(n_frames, (int, np.integer)) and not isinstance(n_frames, (bool, np.bool_))
         and n_frames >= 2, "frame_count")
    tr, origin = scalar(tr), scalar(frame_origin)
    cutoff, min_onset = scalar(high_pass), scalar(min_onset)
    need(tr > 0 and cutoff > 0 and cutoff*tr < 0.5, "clock_or_drift_frequency")
    need(isinstance(oversampling, (int, np.integer)) and not isinstance(oversampling, (bool, np.bool_))
         and oversampling >= 1, "oversampling")
    need(tuple(motion_names) == MOTION_NAMES, "motion_column_order")
    m = array64(motion, 2)
    need(m.shape == (n_frames, 6), "six_motion_rows")
    times = np.arange(n_frames, dtype=np.float64)*tr + origin
    need(np.isfinite(times).all() and np.all(np.diff(times) > 0), "finite_frame_clock")
    need(isinstance(events, (list, tuple)) and len(events) > 0, "event_rows")
    combined = OrderedDict()
    seen_types = set()
    for event in events:
        need(isinstance(event, dict), "event_object")
        need(all(k in event for k in ("trial_type", "onset", "duration")), "event_columns")
        condition = event["trial_type"]
        need(isinstance(condition, str) and condition in TASK_NAMES, "event_condition")
        onset, duration = scalar(event["onset"]), scalar(event["duration"])
        amplitude = scalar(event.get("modulation", 1.0))
        need(duration >= 0 and onset >= times[0]+min_onset, "event_timing_domain")
        need(math.isfinite(onset+duration), "finite_event_offset")
        key = (condition, onset, duration)
        combined.setdefault(key, []).append(amplitude)
        seen_types.add(condition)
    need(seen_types == set(TASK_NAMES), "both_conditions_required")
    effective = []
    for (condition, onset, duration), amplitudes in combined.items():
        amplitude = math.fsum(amplitudes)
        need(math.isfinite(amplitude), "finite_combined_modulation")
        effective.append(dict(trial_type=condition, onset=onset, duration=duration,
                              modulation=amplitude, n_source_rows=len(amplitudes)))
    columns = []
    for condition in TASK_NAMES:
        selected = [row for row in effective if row["trial_type"] == condition]
        exp = np.asarray([[row[key] for row in selected]
                          for key in ("onset", "duration", "modulation")], dtype=np.float64)
        reg, names = compute_regressor(exp, "glover", times, con_id=condition,
                                       oversampling=int(oversampling), min_onset=min_onset)
        need(names == [condition] and reg.shape == (n_frames, 1), "glover_column")
        columns.append(reg[:, 0])
    task = np.ascontiguousarray(np.column_stack(columns), dtype=np.float64)
    drift = create_cosine_drift(cutoff, times)[:, :-1]
    nuisance = np.ascontiguousarray(np.column_stack((np.ones(n_frames), drift, m)))
    full = np.ascontiguousarray(np.column_stack((nuisance, task)))
    need(np.isfinite(full).all(), "finite_design")
    nuisance_names = ("intercept",) + tuple(f"drift_{k+1}" for k in range(drift.shape[1])) + MOTION_NAMES
    return {"frame_indices": np.arange(n_frames, dtype=np.int64), "frame_times": times,
            "nuisance_names": nuisance_names, "task_names": TASK_NAMES,
            "nuisance_design": nuisance, "task_design": task, "full_design": full,
            "full_names": nuisance_names + TASK_NAMES, "effective_events": effective}


def fit_residuals(roi_signals, design):
    y, x = array64(roi_signals, 2), array64(design, 2)
    need(y.shape[1] == 2 and len(y) >= 2, "two_roi_signals")
    need(x.shape[0] == len(y) and x.shape[1] > 0, "design_rows_columns")
    u, singulars, _ = linalg.svd(x, full_matrices=False, check_finite=True,
                                lapack_driver="gesvd")
    need(np.isfinite(u).all() and np.isfinite(singulars).all(), "finite_svd")
    threshold = max(x.shape)*EPS64*float(singulars[0])
    need(math.isfinite(threshold), "finite_rank_threshold")
    keep = singulars > threshold
    basis = u[:, keep]
    residual = y - basis @ (basis.T @ y)
    need(np.isfinite(residual).all(), "finite_residuals")
    return {"residuals": residual, "rank": int(np.count_nonzero(keep)),
            "n_columns": int(x.shape[1]), "residual_df": int(len(y)-np.count_nonzero(keep)),
            "singular_values": singulars, "rank_threshold": threshold}


def model_support(residuals, roi_signals):
    r, y = array64(residuals, 2), array64(roi_signals, 2)
    need(y.shape == r.shape and y.shape[1] == 2 and len(y) >= 2, "support_shape")
    raw_sd = np.asarray([centered(y[:, j])["sample_sd"] for j in range(2)])
    norm = np.asarray([centered(r[:, j])["l2"] for j in range(2)])
    threshold = ACTIVITY_FACTOR*math.sqrt(len(y))*np.maximum(1.0, raw_sd)
    need(np.isfinite(threshold).all(), "finite_activity_threshold")
    return {"raw_sample_sd": raw_sd, "residual_centered_l2": norm,
            "activity_threshold": threshold, "active": norm > threshold}


def analyze_person(roi_signals, designs):
    y = array64(roi_signals, 2)
    fits, diagnostics = [], []
    for key in ("nuisance_design", "full_design"):
        fit = fit_residuals(y, designs[key])
        fits.append(fit)
        diagnostics.append(model_support(fit["residuals"], y))
    return {"residuals": np.stack([fit["residuals"] for fit in fits], axis=1),
            "active": np.stack([d["active"] for d in diagnostics]),
            "fits": fits, "support": diagnostics}


def pearson(left, right):
    a, b = centered(left), centered(right)
    need(len(a["scaled"]) == len(b["scaled"]), "pearson_length")
    need(a["scaled_l2"] > 0 and b["scaled_l2"] > 0, "constant_accepted_active_residual")
    r = math.fsum(float(v)*float(w) for v, w in zip(a["scaled"], b["scaled"])) / (
        a["scaled_l2"]*b["scaled_l2"])
    need(math.isfinite(r) and abs(r) <= 1+1e-12, "pearson_roundoff_domain")
    return min(1.0, max(-1.0, r))


def fisher(r):
    r = scalar(r)
    need(-1 <= r <= 1, "pearson_domain")
    return math.atanh(max(-FISHER_CLIP, min(FISHER_CLIP, r)))


def group_fisher(values, n_expected):
    need(isinstance(n_expected, int) and not isinstance(n_expected, bool)
         and n_expected >= 2, "expected_count")
    finite = [scalar(v) for v in values if v is not None]
    need(len(values) <= n_expected, "group_count")
    result = {"status": "incomplete_support", "n_expected": n_expected,
              "n_defined": len(finite), "mean_z": None, "fisher_mean_r": None}
    if len(finite) == n_expected:
        mean_z = math.fsum(finite)/n_expected
        result.update(status="ok", mean_z=mean_z, fisher_mean_r=math.tanh(mean_z))
    return result


def paired_summary(deltas, n_expected):
    need(isinstance(n_expected, int) and not isinstance(n_expected, bool)
         and n_expected >= 2, "expected_count")
    need(len(deltas) <= n_expected, "paired_count")
    finite = [scalar(v) for v in deltas if v is not None]
    result = {"status": "incomplete_support", "n_expected": n_expected,
              "n_defined": len(finite),
              "mean_raw_minus_background_z": None, "sample_sd": None,
              "standard_error": None, "df": None, "ci95": None, "t": None, "p": None}
    if len(finite) != n_expected:
        return result
    need(n_expected >= 2, "paired_expected_count")
    mean = math.fsum(finite)/n_expected
    if all(v == finite[0] for v in finite):
        sd = 0.0
        mean = finite[0]
    else:
        sd = stable_l2(np.asarray(finite)-mean)/math.sqrt(n_expected-1)
        need(sd > 0, "nonconstant_standard_deviation_underflow")
    se = sd/math.sqrt(n_expected)
    halfwidth = float(stats.t.ppf(0.975, n_expected-1))*se
    result.update(status="ok", mean_raw_minus_background_z=mean, sample_sd=sd,
                  standard_error=se, df=n_expected-1, ci95=[mean-halfwidth, mean+halfwidth])
    if se == 0:
        result["status"] = "zero_variance"
    else:
        t = mean/se
        need(math.isfinite(t), "nonfinite_t_statistic")
        result.update(t=t, p=float(2*stats.t.sf(abs(t), n_expected-1)))
    need(all(math.isfinite(v) for v in (mean, sd, se, halfwidth, *result["ci95"])),
         "finite_paired_summary")
    return result


def derive(residuals_by_person, active_by_person, participant_ids, n_expected=10):
    """Own accepted-residual arithmetic; source binding belongs to the verifier."""
    need(isinstance(n_expected, int) and not isinstance(n_expected, bool)
         and n_expected >= 2, "expected_count")
    ids = list(participant_ids)
    need(all(isinstance(s, str) and s for s in ids) and len(set(ids)) == len(ids), "participant_keys")
    need(len(ids) == len(residuals_by_person) and len(ids) <= n_expected, "participant_count")
    active = np.asarray(active_by_person)
    need(active.dtype.kind == "b" and active.shape == (len(ids), 2, 2), "canonical_active_mask")
    rows, raw_z, background_z, delta_z = [], [], [], []
    for index, (sid, values) in enumerate(zip(ids, residuals_by_person)):
        r = array64(values, 3)
        need(r.shape[0] >= 2 and r.shape[1:] == (2, 2), "residual_model_roi_axes")
        corr, z, statuses = [], [], []
        for arm in range(2):
            ok = bool(np.all(active[index, arm]))
            corr.append(pearson(r[:, arm, 0], r[:, arm, 1]) if ok else None)
            z.append(fisher(corr[-1]) if ok else None)
            statuses.append("ok" if ok else "inactive_both" if not active[index, arm].any()
                            else "inactive_left" if not active[index, arm, 0] else "inactive_right")
        paired = all(value is not None for value in z)
        delta = z[0]-z[1] if paired else None
        rows.append({"subject": sid, "region_a": ROI_NAMES[0], "region_b": ROI_NAMES[1],
                     "raw_status": statuses[0], "background_status": statuses[1],
                     "connectivity": corr[0], "background_connectivity": corr[1],
                     "raw_fisher_z": z[0], "background_fisher_z": z[1],
                     "paired_status": "ok" if paired else "incomplete_support",
                     "raw_minus_background_z": delta})
        raw_z.append(z[0]); background_z.append(z[1]); delta_z.append(delta)
    raw, background = group_fisher(raw_z, n_expected), group_fisher(background_z, n_expected)
    raw_r, background_r = raw["fisher_mean_r"], background["fisher_mean_r"]
    return {"rows": rows, "n_subjects": len(ids), "region_a": ROI_NAMES[0], "region_b": ROI_NAMES[1],
            "raw": raw, "background": background,
            "difference_of_group_fisher_mean_r": raw_r-background_r if raw_r is not None and background_r is not None else None,
            "paired_z_sensitivity": paired_summary(delta_z, n_expected)}
