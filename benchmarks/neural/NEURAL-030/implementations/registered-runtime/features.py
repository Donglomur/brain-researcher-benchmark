"""Independent transparent features for paired no-neural/neural references."""
import numpy as np

from source_binding import require
from temporal import planned_mask

TRIAL_KEYS = {"trial_id", "session_id", "trial_order", "delay_s", "stage",
              "neural_time", "grc", "cf", "handle_time", "handle"}


def features(trials, arm="joint"):
    require(arm in ("context_handle", "grc", "cf", "joint"), "reference_arm")
    require(type(trials) is list and trials, "reference_trials")
    rows, ids = [], []
    width = None
    names = None
    session = None
    seen = set()
    for trial in trials:
        require(type(trial) is dict and set(trial) in (TRIAL_KEYS, TRIAL_KEYS | {"counts"}), "public_trial_fields")
        tid = trial["trial_id"]
        require(type(tid) is str and tid and tid not in seen, "unique_public_trial")
        seen.add(tid)
        if session is None:
            session = trial["session_id"]
        require(trial["session_id"] == session, "within_session_reference")
        d = trial["delay_s"]
        require(type(d) in (int, float) and d in (1.0, 2.0), "feature_delay")
        require(type(trial["trial_order"]) is int and trial["trial_order"] > 0, "feature_order")
        nt, nb, nm = planned_mask(trial["neural_time"], d)
        ht, hb, hm = planned_mask(trial["handle_time"], d, behavior=True)
        grc = np.asarray(trial["grc"], dtype=float)
        cf = np.asarray(trial["cf"], dtype=float)
        handle = np.asarray(trial["handle"], dtype=float)
        require(nt.ndim == ht.ndim == 1 and nt.size >= 2 and ht.size >= 2, "feature_clocks")
        require(np.all(np.diff(nt) > 0) and np.all(np.diff(ht) > 0), "feature_clock_order")
        require(grc.ndim == cf.ndim == 2 and grc.shape[1] == cf.shape[1] == nt.size, "feature_neural_axes")
        require(grc.shape[0] > 0 and cf.shape[0] > 0, "feature_neural_channels")
        require(np.logical_or(cf == 0, cf == 1).all(), "feature_CF_binary_events")
        require(handle.shape == (2, ht.size), "feature_handle_axes")
        require(all(np.isfinite(a).all() for a in (nt, ht, grc, cf, handle)), "feature_values_finite")
        require(nm.all() and hm.all(), "public_predictors_within_planned_interval")
        local_names = ["bin_midpoint_s", "bin_fraction", "trial_order", "planned_delay_s",
                       "handle_x_mean", "handle_y_mean", "handle_x_velocity", "handle_y_velocity"]
        if arm in ("grc", "joint"):
            local_names += ["grc_mean_" + str(k) for k in range(grc.shape[0])]
        if arm in ("cf", "joint"):
            local_names += ["cf_binary_mean_" + str(k) for k in range(cf.shape[0])]
        if names is None:
            names = local_names
        require(local_names == names, "fixed_feature_schema_per_session")
        for k in range(int(round(d / 0.1))):
            left, right = k * 0.1, (k + 1) * 0.1
            nh = hb == k
            nn = nb == k
            require(nh.sum() >= 2 and nn.sum() >= 1, "native_bin_support_no_extrapolation")
            h = handle[:, nh]
            v = (h[:, -1] - h[:, 0]) / (ht[nh][-1] - ht[nh][0])
            row = [(left + right) / 2, (left + right) / (2 * d), trial["trial_order"], d,
                   float(h[0].mean()), float(h[1].mean()), float(v[0]), float(v[1])]
            if arm in ("grc", "joint"):
                row += grc[:, nn].mean(axis=1).tolist()
            if arm in ("cf", "joint"):
                row += cf[:, nn].mean(axis=1).tolist()
            if width is None:
                width = len(row)
            require(len(row) == width, "feature_width")
            rows.append(row)
            ids.append(tid)
    return np.asarray(rows, dtype=float), ids, names


def training_counts(trials):
    values = []
    for trial in trials:
        require("counts" in trial, "training_targets_required")
        y = np.asarray(trial["counts"])
        n = int(round(trial["delay_s"] / 0.1))
        require(y.ndim == 1 and y.size == n and y.dtype.kind in "ifu", "training_target_shape_type")
        require(np.isfinite(y).all() and np.all(y >= 0) and np.all(y == np.floor(y)), "training_target_counts")
        values += y.tolist()
    return np.asarray(values, dtype=float)
