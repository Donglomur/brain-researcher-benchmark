"""Pure source-array import and split construction. No MAT loader or file access.

The caller is a trusted data operator. Arrays must come from the separately
qualified exact source asset; declared metadata cannot certify that provenance.
"""
import hashlib
import json
import math

import numpy as np

from source_binding import GROUPS, Refusal, require, validate_binding, opaque
from temporal import planned_mask

BIN_WIDTH = 0.1
BEHAVIOR_STEP = 0.005
QC_HISTORY = 300
QC_HIGH_COUNT = 297  # Valid iff every tested full history is strictly below 99%.
QC_INTERVAL = (-1.75, 1.75)


def array(value, name, ndim, binary=False):
    require(type(value) in (list, tuple, np.ndarray), name + "_array_type")
    raw = np.asarray(value)
    require(raw.dtype.kind in "bifu" and raw.ndim == ndim, name + "_numeric_shape")
    result = np.array(raw, dtype=np.float64, copy=True)
    require(np.isfinite(result).all(), name + "_finite")
    if binary:
        require(np.logical_or(result == 0, result == 1).all(), name + "_binary")
    result.setflags(write=False)
    return result


def scalar(value, name):
    require(type(value) in (int, float) and math.isfinite(value), name + "_scalar")
    return float(value)


def clock(value, step, name):
    t = array(value, name, 1)
    require(t.size >= 2 and np.all(np.diff(t) > 0), name + "_strict_increasing")
    require(step > 0 and np.allclose(np.diff(t), step, rtol=1e-8, atol=1e-10), name + "_sampling_step")
    return t


def integers(value, name, n):
    a = array(value, name, 1)
    require(a.shape == (n,) and np.all(a == np.floor(a)) and np.all(a >= 1)
            and np.all(a < 2**52), name + "_positive_exact_source_indices")
    return a


def behavior_ticks(t):
    """Declared zero-centered 200-Hz clock represented as exact integer ticks."""
    ticks = np.rint(t / BEHAVIOR_STEP)
    require(np.all(np.abs(t - ticks * BEHAVIOR_STEP) <= 1e-9), "behavior_clock_zero_grid")
    require(np.all(np.diff(ticks) == 1), "behavior_clock_contiguous_ticks")
    require(np.all(np.abs(ticks) < 2**52), "behavior_tick_extent")
    return ticks.astype(np.int64)


def contact_onsets(contacts, t, start, duration):
    """Count rising contacts in half-open bins, with right-sample time ownership."""
    b = array(contacts, "contacts", 1, binary=True)
    t = clock(t, BEHAVIOR_STEP, "contact_time")
    require(b.shape == t.shape, "contact_clock_shape")
    require(type(duration) in (int, float) and duration in (1.0, 2.0), "planned_delay")
    start = scalar(start, "target_start")
    ticks = behavior_ticks(t)
    start_tick = round(start / BEHAVIOR_STEP)
    require(abs(start - start_tick * BEHAVIOR_STEP) <= 1e-9, "movement_end_on_behavior_grid")
    duration_ticks = int(duration / BEHAVIOR_STEP)
    require(ticks[0] < start_tick and ticks[-1] >= start_tick + duration_ticks, "complete_contact_support_and_preceding_sample")
    event_ticks = ticks[1:][np.logical_and(b[:-1] == 0, b[1:] == 1)] - start_tick
    nbin = int(round(duration / BIN_WIDTH))
    in_window = event_ticks[np.logical_and(event_ticks >= 0, event_ticks < duration_ticks)]
    bins = in_window // 20  # Exactly 20 behavioral samples per 100-ms bin.
    require(np.logical_and(bins >= 0, bins < nbin).all(), "event_bin_domain")
    return np.bincount(bins, minlength=nbin).astype(np.int64)


def sensor_quality(reward_contacts, t):
    """Source99 threshold plus explicit full-observed-history amendment."""
    b = array(reward_contacts, "reward_aligned_contacts", 2, binary=True)
    t = clock(t, BEHAVIOR_STEP, "quality_time")
    require(b.shape[1] == t.size, "quality_clock_shape")
    ticks = behavior_ticks(t)
    centers = np.flatnonzero(np.logical_and(ticks >= -350, ticks <= 350))
    require(centers.size > 0 and centers[0] >= QC_HISTORY - 1, "quality_full_causal_history")
    require(ticks[0] <= -350 and ticks[-1] >= 350, "quality_full_interval")
    sums = np.pad(np.cumsum(b.astype(np.int64), axis=1), ((0, 0), (1, 0)))
    rolling = sums[:, centers + 1] - sums[:, centers + 1 - QC_HISTORY]
    maxima = np.max(rolling, axis=1)
    return maxima < QC_HIGH_COUNT, maxima


def split_trials(midpoints, ends, dtb, duration):
    """Freeze whole-trial 60/20/20 blocks before QC; refuse window overlap."""
    n = len(midpoints)
    midpoints = integers(midpoints, "split_midpoints", n)
    ends = integers(ends, "split_ends", n)
    require(type(duration) in (int, float) and duration in (1., 2.), "split_planned_duration")
    require(math.isclose(scalar(dtb, "split_dtb"), BEHAVIOR_STEP, rel_tol=0, abs_tol=1e-12), "split_behavior_step")
    require(n >= 5 and np.all(np.diff(midpoints) > 0), "trial_chronology_and_minimum")
    require(np.all(ends >= midpoints), "end_after_midpoint")
    a, b = math.floor(0.6 * n), math.floor(0.8 * n)
    require(0 < a < b < n, "nonempty_original_split")
    names = np.array(["train"] * a + ["development"] * (b - a) + ["query"] * (n - b))
    start_ticks = ends.astype(np.int64) - 1  # Source indices are one based.
    stop_ticks = start_ticks + int(duration * 200)
    # Check every cross-fold interval, not just neighboring indices. Half-open
    # windows that only touch do not share an input sample interval.
    for i in range(n):
        for j in range(i + 1, n):
            if names[i] != names[j]:
                require(not (start_ticks[i] < stop_ticks[j] and start_ticks[j] < stop_ticks[i]), "cross_fold_window_overlap")
    return names, start_ticks * dtb, stop_ticks * dtb


def import_session(curd, identity):
    """Import only named same-record fields into paired public/private views.

    Supplied source arrays use the README's explicit trial/cell/time and
    trial/coordinate/behavior-time conventions. There is no shape guessing.
    """
    require(type(curd) is dict, "session_object")
    fields = {"dtb", "dtimCb", "tmpxx", "tmpxCb", "midpt", "trueend", "truestart", "goodmvdir", "midAlgn", "rewAlgn"}
    require(fields <= set(curd), "required_native_fields")
    dtb, dti = scalar(curd["dtb"], "dtb"), scalar(curd["dtimCb"], "dtimCb")
    require(math.isclose(dtb, BEHAVIOR_STEP, rel_tol=0, abs_tol=1e-12), "documented_200Hz_behavior")
    tb = clock(curd["tmpxx"], dtb, "tmpxx")
    tn = clock(curd["tmpxCb"], dti, "tmpxCb")
    m, r = curd["midAlgn"], curd["rewAlgn"]
    require(type(m) is dict and type(r) is dict, "native_aligned_objects")
    require({"sigFilt_GrC", "sp_CF", "pos", "lick"} <= set(m) and "lick" in r, "native_aligned_fields")
    grc = array(m["sigFilt_GrC"], "grc", 3)
    cf = array(m["sp_CF"], "cf", 3, binary=True)
    handle = array(m["pos"], "handle_trial_coordinate_time", 3)
    contact = array(m["lick"], "midpoint_contacts", 2, binary=True)
    reward_contact = array(r["lick"], "reward_contacts", 2, binary=True)
    n = grc.shape[0]
    require(n > 0 and grc.shape[1] > 0 and cf.shape[1] > 0, "nonempty_neural_channels")
    require(grc.shape[2] == cf.shape[2] == tn.size and cf.shape[0] == n, "neural_axes")
    require(handle.shape == (n, 2, tb.size), "handle_axes")
    require(contact.shape == reward_contact.shape == (n, tb.size), "contact_axes")
    mid = integers(curd["midpt"], "midpt", n)
    end = integers(curd["trueend"], "trueend", n)
    begin = integers(curd["truestart"], "truestart", n)
    require(np.all(begin <= mid), "movement_start_order")
    good_movement = array(curd["goodmvdir"], "goodmvdir", 1, binary=True)
    require(good_movement.shape == (n,), "movement_quality_shape")
    group_name, duration, _ = GROUPS[identity["group"]]
    folds, absolute_starts, absolute_stops = split_trials(mid, end, dtb, duration)
    sensor_good, sensor_max = sensor_quality(reward_contact, tb)
    case_id = opaque("session", identity["session_id"])
    views = {"train": [], "development": [], "query": []}
    expected = []
    dispositions = []
    for i in range(n):
        trial_id = opaque(case_id, str(i + 1))
        fold = str(folds[i])
        reasons = []
        if good_movement[i] != 1:
            reasons.append("source_movement_quality")
        if not sensor_good[i]:
            reasons.append("sensor_contact_occupancy_at_least_99_percent")
        dispositions.append({"trial_id": trial_id, "source_trial_index_one_based": i + 1,
                             "fold": fold, "included": not reasons, "reasons": reasons,
                             "quality_max_high_samples_of_300": int(sensor_max[i]),
                             "source_input_interval_ticks_zero_based": [int(end[i]) - 1, int(end[i]) - 1 + int(duration * 200)],
                             "source_input_interval_s": [float(absolute_starts[i]), float(absolute_stops[i])]})
        if reasons:
            continue
        shift = float((end[i] - mid[i]) * dtb)
        nt, _, nm = planned_mask(tn - shift, duration)
        ht, _, hm = planned_mask(tb - shift, duration, behavior=True)
        require(np.all(np.diff(nt) > 0) and np.all(np.diff(ht) > 0), "normalized_predictor_clock_order")
        require(nt[0] <= 0 and nt[-1] >= duration, "complete_neural_planned_window")
        require(ht[0] < 0 and ht[-1] >= duration, "complete_behavior_planned_window")
        counts = contact_onsets(contact[i], tb, shift, duration)
        # No target, reward timestamp, sensor quality, original path or lick
        # summary is copied into query predictors.
        require(nm.sum() >= 2 and hm.sum() >= 2, "predictor_window_nonempty")
        trial = {"trial_id": trial_id, "session_id": case_id, "trial_order": i + 1,
                 "delay_s": duration, "stage": group_name,
                 "neural_time": nt[nm].tolist(),
                 "grc": grc[i][:, nm].tolist(), "cf": cf[i][:, nm].tolist(),
                 "handle_time": ht[hm].tolist(),
                 "handle": handle[i][:, hm].tolist()}
        if fold in ("train", "development"):
            trial["counts"] = counts.tolist()
        else:
            expected.append({"trial_id": trial_id, "session_id": case_id,
                             "bin_count": counts.size, "counts": counts.tolist()})
        views[fold].append(trial)
    require(all(views[k] for k in views), "nonempty_splits_after_fixed_quality")
    return {"session_id": case_id, "condition": group_name, "delay_s": duration, **views}, {
        "session_id": case_id, "expected": expected, "dispositions": dispositions,
        "source_identity": identity, "authenticity_established": False}


def prepare_collection(binding, sessions):
    """Require the complete source-position map; return isolated data views."""
    identity = validate_binding(binding)
    require(type(sessions) is dict and set(sessions) == set(identity), "complete_session_array_map")
    public_cases, private_cases = [], []
    for position in sorted(identity):
        public, private = import_session(sessions[position], identity[position])
        public_cases.append(public)
        private_cases.append(private)
    public = {"schema": "neural030_cerebellar_public_v1", "cases": public_cases,
              "view_scope": "retrospective_processed_within_session_calibration",
              "query_target_feedback": False}
    expected = [r for c in private_cases for r in c["expected"]]
    mapping = {c["session_id"]: opaque("mouse", c["source_identity"]["mouse_id"]) for c in private_cases}
    binding_bytes = json.dumps(binding, sort_keys=True, separators=(",", ":")).encode()
    private = {"schema": "neural030_cerebellar_private_v1", "cases": private_cases, "expected": expected,
               "mouse_binding": {"verification_status": "operator_attested",
                                 "binding_id": hashlib.sha256(binding_bytes).hexdigest(),
                                 "evidence_sha256": binding["evidence"]["artifact_sha256"],
                                 "session_to_mouse": mapping},
               "scientific_qualification": False,
               "input_authenticity_not_established_by_preparer": True}
    return public, private
