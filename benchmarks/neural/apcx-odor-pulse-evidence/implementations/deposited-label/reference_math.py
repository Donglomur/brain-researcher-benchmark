"""Pure session-local APCx reference mathematics; execution is caller-selected.

NumPy is supplied by the accepted runtime, never imported here. This module
does no filesystem/network access, model selection, clipping, or owner scoring.
Only deposited integer labels are fitted; physical delivery is not inferred.
The caller's immutable source manifest supplies this file's cryptographic pin.
"""

import math

IMPLEMENTATION = "apcx-public-session-ridge-v1"
ALPHAS = (0.0001, 0.001, 0.01, 0.1, 1.0, 10.0, 100.0)
CAPS = {"calibration": 220, "development": 73, "queries": 74, "units": 19}
BINS = 90
INTEGER_LIMIT = 2**31
RELATIVE_RESIDUAL_LIMIT = 1e-8
GROUPS = ("calibration", "development", "queries")


def _identity(value, field):
    if (type(value) is not str or len(value) != 64
            or any(c not in "0123456789abcdef" for c in value)):
        raise ValueError(field + " must be 64 lowercase hexadecimal characters")
    return value


def _integer(value, field):
    if type(value) is not int or not 0 <= value < INTEGER_LIMIT:
        raise ValueError(field + " must be an integer in [0, 2**31)")
    return value


def _validate(session, check):
    check()
    if type(session) is not dict or set(session) != {
            "session_id", "channel_ids", *GROUPS}:
        raise ValueError("session schema mismatch")
    _identity(session["session_id"], "session_id")
    channels = session["channel_ids"]
    if type(channels) is not list or not 1 <= len(channels) <= CAPS["units"]:
        raise ValueError("channel count outside fixed bounds")
    for channel in channels:
        _identity(channel, "channel_id")
    if len(set(channels)) != len(channels):
        raise ValueError("duplicate channel_id")
    seen = set()
    for group in GROUPS:
        rows = session[group]
        if type(rows) is not list or not 1 <= len(rows) <= CAPS[group]:
            raise ValueError(group + " count outside fixed bounds")
        for row in rows:
            check()
            fields = {"case_id", "spikes"}
            if group != "queries":
                fields |= {"count", "high"}
            if type(row) is not dict or set(row) != fields:
                raise ValueError(group + " row schema mismatch")
            case_id = _identity(row["case_id"], "case_id")
            if case_id in seen:
                raise ValueError("case_id repeated within or between partitions")
            seen.add(case_id)
            if group != "queries":
                count = _integer(row["count"], "count")
                if (type(row["high"]) is not int or row["high"] not in (0, 1)
                        or row["high"] != int(count >= 9)):
                    raise ValueError("high must be the exact integer count>=9 label")
            spikes = row["spikes"]
            if type(spikes) is not list or len(spikes) != len(channels):
                raise ValueError("spike unit shape mismatch")
            for unit in spikes:
                if type(unit) is not list or len(unit) != BINS:
                    raise ValueError("spike time shape must contain exactly 90 bins")
                for value in unit:
                    _integer(value, "spike count")
    check()


def _finite(array, np, name):
    if not bool(np.isfinite(array).all()):
        raise ValueError(name + " contains nonfinite values")


def _trace(ids, values, np):
    if values.shape != (len(ids),):
        raise ValueError("prediction shape mismatch")
    _finite(values, np, "predictions")
    return [{"case_id": case_id, "prediction": float(value)}
            for case_id, value in zip(ids, values)]


def _normalization(matrices, np, check):
    """Population moments and mask come exclusively from calibration."""
    check()
    train = matrices["calibration"]
    means = np.mean(train, axis=0, dtype=np.float64)
    centered = train - means
    # Exact equality, not a data-dependent near-constant threshold.
    active = np.any(train != train[0:1], axis=0)
    variance = np.mean(centered * centered, axis=0, dtype=np.float64)
    scales = np.sqrt(variance)
    _finite(means, np, "calibration means")
    _finite(scales, np, "calibration standard deviations")
    if bool(np.any(scales[active] <= 0)):
        raise ValueError("nonconstant calibration feature has nonpositive scale")
    if bool(np.any(scales[~active] != 0)):
        raise ValueError("constant calibration feature has nonzero scale")
    p = int(np.count_nonzero(active))
    transformed = {}
    for group in GROUPS:
        check()
        if p:
            transformed[group] = (
                (matrices[group][:, active] - means[active])
                / scales[active] / math.sqrt(p))
        else:
            transformed[group] = np.zeros((len(matrices[group]), 0), dtype=np.float64)
        _finite(transformed[group], np, "transformed " + group)
        check()
    audit = {
        "fitted_partition": "calibration",
        "ddof": 0,
        "means": means.tolist(),
        "population_standard_deviations": scales.tolist(),
        "active_mask": [bool(value) for value in active],
        "active_feature_count": p,
        "feature_divisor": math.sqrt(p) if p else None,
        "constant_feature_policy": "coefficient_zero_no_cohort_exclusion",
        "target_scaling": "center_only",
    }
    return transformed, audit


def _ridge(matrices, feature_order, ids, target, target_mean, np, check):
    transformed, normalization = _normalization(matrices, np, check)
    check()
    train = transformed["calibration"]
    n = len(target)
    centered_target = target - target_mean
    kernel = train @ train.T
    _finite(kernel, np, "calibration kernel")
    trace_per_trial = float(np.trace(kernel) / n)
    cross = {}
    for group in GROUPS:
        check()
        cross[group] = transformed[group] @ train.T
        _finite(cross[group], np, group + " cross kernel")
        check()
    models = []
    for alpha in ALPHAS:
        check()  # Original owner deadline may interrupt every fit.
        penalty = n * alpha
        system = kernel + penalty * np.eye(n, dtype=np.float64)
        if normalization["active_feature_count"]:
            dual = np.asarray(np.linalg.solve(system, centered_target), dtype=np.float64)
            solver = "numpy.linalg.solve"
        else:
            # Exact all-constant solution, not an error fallback.
            dual = centered_target / penalty
            solver = "analytic_zero_feature_kernel"
        check()
        if dual.shape != (n,):
            raise ValueError("dual coefficient shape mismatch")
        _finite(dual, np, "dual coefficients")
        residual = system @ dual - centered_target
        _finite(residual, np, "normal equation residual")
        numerator = float(np.linalg.norm(residual))
        denominator = max(1.0, float(np.linalg.norm(centered_target)))
        relative = numerator / denominator
        if not math.isfinite(relative) or relative > RELATIVE_RESIDUAL_LIMIT:
            raise ValueError("ridge normal equation relative residual exceeds limit")
        predictions = {}
        for group in GROUPS:
            check()  # Every partition's inference has its own deadline checks.
            raw = target_mean + cross[group] @ dual
            predictions[group] = _trace(ids[group], raw, np)
            check()
        models.append({
            "alpha": alpha,
            "n_times_alpha": penalty,
            "dual_coefficients": dual.tolist(),
            "solver": solver,
            "normal_equation_certificate": {
                "residual_l2": numerator,
                "denominator_max_1_centered_target_l2": denominator,
                "relative_residual": relative,
                "limit": RELATIVE_RESIDUAL_LIMIT,
                "passed": True,
            },
            "predictions": predictions,
        })
    check()
    return {
        "feature_order": feature_order,
        "normalization": normalization,
        "calibration_count": n,
        "calibration_target_mean": target_mean,
        "calibration_centered_targets": centered_target.tolist(),
        "kernel_trace_per_calibration_trial": trace_per_trial,
        "objective": "mean_squared_calibration_error + alpha * squared_l2_beta",
        "intercept": "unpenalized_calibration_target_mean_with_centered_features",
        "models": models,
    }


def reference_session(session, np, check):
    """Return every reference trace; any error aborts this complete session.

    Declared channel and case order is preserved. All returned values are finite
    JSON primitives/lists/dicts. The seven-alpha traces are NOT a chosen model.
    The caller selects one alpha per representation/condition using development
    loss alone, with fixed scorer clipping, and never refits on development.
    """
    _validate(session, check)
    ids = {group: [row["case_id"] for row in session[group]] for group in GROUPS}
    arrays = {}
    for group in GROUPS:
        check()
        arrays[group] = np.asarray(
            [row["spikes"] for row in session[group]], dtype=np.float64)
        expected = (len(ids[group]), len(session["channel_ids"]), BINS)
        if arrays[group].shape != expected:
            raise ValueError("validated spike array shape changed")
        _finite(arrays[group], np, group + " spikes")
        check()
    target = np.asarray([row["count"] for row in session["calibration"]],
                        dtype=np.float64)
    check()
    target_mean = float(np.mean(target, dtype=np.float64))
    if not math.isfinite(target_mean):
        raise ValueError("calibration target mean is nonfinite")
    mean_traces = {}
    for group in GROUPS:
        check()
        mean_traces[group] = _trace(
            ids[group], np.full(len(ids[group]), target_mean, dtype=np.float64), np)
        check()
    count_matrices = {group: np.sum(arrays[group], axis=2, dtype=np.float64)
                      for group in GROUPS}
    temporal_matrices = {
        group: arrays[group].reshape(len(ids[group]), -1) for group in GROUPS}
    channels = list(session["channel_ids"])
    count_order = [{"channel_id": channel, "bins": "all_90_[0.5,5)_50ms"}
                   for channel in channels]
    temporal_order = [{"channel_id": channel, "bin_index": index}
                      for channel in channels for index in range(BINS)]
    count_ridge = _ridge(count_matrices, count_order, ids, target, target_mean, np, check)
    temporal_ridge = _ridge(
        temporal_matrices, temporal_order, ids, target, target_mean, np, check)
    check()
    return {
        "schema": "apcx-session-reference-traces-v1",
        "implementation": IMPLEMENTATION,
        "source_identity_authority": "caller's_frozen_complete_source_manifest",
        "session_id": session["session_id"],
        "channel_ids": channels,
        "partition_case_order": ids,
        "alpha_grid": list(ALPHAS),
        "prediction_policy": "raw_finite_no_clipping_no_rounding",
        "label_endpoint": "literal_deposited_Total_pulse",
        "observed_window": {"start_seconds": 0.5, "end_seconds_exclusive": 5.0,
                            "bin_seconds": 0.05, "bins": BINS,
                            "first_500ms": "unavailable_not_imputed"},
        "development_use": "returned_predictions_only_no_fitting_or_selection",
        "calibration_mean": {"calibration_count": len(target),
                             "calibration_target_mean": target_mean,
                             "predictions": mean_traces},
        "count_ridge": count_ridge,
        "temporal_ridge": temporal_ridge,
    }

