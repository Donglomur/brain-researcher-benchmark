#!/usr/bin/env python3
"""Prospective, session-local NEURAL-025 decoding on admitted normalized trials.

This module does not load MAT files or establish authentic input identity,
native clock parity, original-author result parity, or scientific qualification.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import itertools
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np


TASK_ID = "NEURAL-025"
AUTHOR_COMMIT = "815b610b3beddfed5a3abf611d3a465ab9e4ce5c"
MICE = ("cfa17", "cfa19", "cfa20", "cfa22", "cfa24")
JOINT_NAMES = ("SHDRf", "SHDRa", "SHDRr", "ELBOf", "WRSTf", "WRSTd", "WRSTr",
               "MCP1f", "MCP2f", "MCP3f", "MCP4f", "MCP1a", "MCP2a", "MCP3a",
               "MCP4a", "MCP1o", "MCP4o", "P1P2", "P2P3", "P3P4", "PIP1f",
               "PIP2f", "PIP3f", "PIP4f")
METRIC_POLICY = "train_sd_trial_session_mouse_macro_v1"
FEATURE_FIELDS = {"smoothed_deconvolved_events": "data", "radical": "radical_rates"}
TARGET_UNITS = {"jointAngles": "degrees", "jointVelocities": "degrees_per_second"}
# Pinned main/fig5/fig5_analysis.m lines19–20. cfa24 has reversed date order.
SESSIONS = {
    "cfa17_20200825_172828": ("cfa17", "M1"),
    "cfa17_20200827_165724": ("cfa17", "S1"),
    "cfa19_20200820_143508": ("cfa19", "M1"),
    "cfa19_20200826_191222": ("cfa19", "S1"),
    "cfa20_20201114_194635": ("cfa20", "M1"),
    "cfa20_20201118_200612": ("cfa20", "S1"),
    "cfa22_20220605_182006": ("cfa22", "M1"),
    "cfa22_20220611_174801": ("cfa22", "S1"),
    "cfa24_20220727_160603": ("cfa24", "M1"),
    "cfa24_20220724_155906": ("cfa24", "S1"),
}


class Refusal(ValueError):
    """The supplied source, split, numeric domain or policy is inadmissible."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise Refusal(message)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def identifiers(value: Any, name: str, count: int | None = None) -> list[str]:
    require(isinstance(value, (list, tuple)), name + " must be an ordered array")
    require(bool(value), name + " must not be empty")
    require(all(isinstance(x, str) and 0 < len(x) <= 200 and
                x.strip() == x and not any(ord(c) < 32 for c in x) for x in value),
            name + " has invalid identifiers")
    require(len(set(value)) == len(value), name + " has duplicate identifiers")
    require(count is None or len(value) == count, name + " has the wrong length")
    return list(value)


def integer(value: Any, name: str, minimum: int = 1) -> int:
    require(type(value) is int and value >= minimum, name + " must be an integer")
    return value


def matrix(value: Any, name: str) -> np.ndarray:
    try:
        # Mixed JSON lists otherwise coerce bools and oversized integers to
        # float before dtype admission can inspect their original values.
        if isinstance(value, (list, tuple)):
            for row in value:
                require(isinstance(row, (list, tuple, np.ndarray)), name + " rows must be arrays")
                for item in row:
                    require(isinstance(item, (int, float, np.integer, np.floating)) and
                            not isinstance(item, (bool, np.bool_)),
                            name + " must contain real numeric scalars, not booleans")
                    if isinstance(item, (int, np.integer)):
                        require(abs(int(item)) <= 2**53,
                                name + " integers exceed exact float64 admission")
        raw = np.asarray(value)
        require(raw.ndim == 2 and min(raw.shape) > 0, name + " must be a nonempty matrix")
        require(raw.dtype.kind in "iuf", name + " must contain real numbers, not booleans")
        if raw.dtype.kind in "iu":
            require(bool(np.all(raw <= 2**53)) and
                    (raw.dtype.kind == "u" or bool(np.all(raw >= -(2**53)))),
                    name + " integers exceed exact float64 admission")
        require(bool(np.all(np.isfinite(raw))), name + " has nonfinite numbers")
        with np.errstate(over="ignore", invalid="ignore"):
            out = np.asarray(raw, dtype=np.float64)
        require(bool(np.all(np.isfinite(out))), name + " cannot be represented in float64")
        return out
    except Refusal:
        raise
    except (TypeError, ValueError, OverflowError) as exc:
        raise Refusal(name + " is not a real matrix") from exc


def finite_result(value: np.ndarray, name: str) -> np.ndarray:
    require(bool(np.all(np.isfinite(value))), name + " exceeds supported numeric precision")
    return value


def _column_mean(values: np.ndarray) -> np.ndarray:
    scale = np.max(np.abs(values), axis=0)
    divisor = np.where(scale > 0, scale, 1.0)
    return finite_result(np.mean(values / divisor, axis=0) * scale, "Scaled mean")


def _column_rms(values: np.ndarray) -> np.ndarray:
    scale = np.max(np.abs(values), axis=0)
    divisor = np.where(scale > 0, scale, 1.0)
    result = finite_result(np.sqrt(np.mean((values / divisor) ** 2, axis=0)) * scale,
                           "Scaled root mean square")
    require(not bool(np.any((scale > 0) & (result == 0))),
            "Nonzero RMS falls below representable float64 precision")
    return result


@dataclass(frozen=True)
class FittedModel:
    roi_ids: tuple[str, ...]
    selected_roi_ids: tuple[str, ...]
    selected_indices: tuple[int, ...]
    mean_x: np.ndarray
    mean_y: np.ndarray
    components: np.ndarray
    coef: np.ndarray
    training_target_sd: np.ndarray
    ridge_alpha: float
    training_rows: int


def _frozen(value: np.ndarray) -> np.ndarray:
    result = np.array(value, dtype=np.float64, copy=True)
    result.setflags(write=False)
    return result


def fit_train_only(X: Any, Y: Any, *, roi_ids: list[str], cell_budget: int,
                   pca_components: int, ridge_alpha: float) -> FittedModel:
    """Fit from training rows only; caller must admit complete trial splits first.

    Selection ranks training feature variance. PCA centers but does not scale.
    Ridge minimizes sum squared residuals + alpha * squared coefficient norm;
    target intercept is unpenalized. No evaluation arrays are accepted here.
    """
    x, y = matrix(X, "training features"), matrix(Y, "training targets")
    ids = identifiers(roi_ids, "ROI IDs", x.shape[1])
    require(x.shape[0] == y.shape[0] and x.shape[0] >= 2,
            "Training feature/target rows differ or contain fewer than two rows")
    budget = integer(cell_budget, "cell_budget")
    rank = integer(pca_components, "pca_components")
    require(budget <= x.shape[1], "Unavailable cell budget")
    require(rank <= min(budget, x.shape[0] - 1), "PCA rank exceeds training support")
    require(type(ridge_alpha) in (int, float) and math.isfinite(ridge_alpha)
            and 0 <= ridge_alpha <= np.finfo(np.float64).max,
            "Ridge penalty must be finite and nonnegative")
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            mean_all = _column_mean(x)
            centered_all = finite_result(x - mean_all, "Centered features")
            # SD has the same ranking as variance and avoids squaring small or
            # large amplitudes before normalization.
            variances = _column_rms(centered_all)
            selected = tuple(sorted(range(len(ids)), key=lambda i: (-variances[i], ids[i]))[:budget])
            centered = centered_all[:, selected]
            _, _, vt = np.linalg.svd(centered, full_matrices=False)
            components = vt[:rank].T.copy()
            # Canonicalize each axis sign; this does not choose an eigenbasis
            # in tied subspaces or claim cross-platform bitwise equivalence.
            for column in range(rank):
                anchor = int(np.argmax(np.abs(components[:, column])))
                if components[anchor, column] < 0:
                    components[:, column] *= -1
            z = finite_result(centered @ components, "PCA scores")
            mean_y = _column_mean(y)
            yc = finite_result(y - mean_y, "Centered targets")
            if ridge_alpha == 0:
                coef = np.linalg.lstsq(z, yc, rcond=None)[0]
            else:
                # The augmented least-squares equation also handles deficient
                # training rank without solving normal equations.
                augmented_z = np.vstack((z, math.sqrt(ridge_alpha) * np.eye(rank)))
                augmented_y = np.vstack((yc, np.zeros((rank, y.shape[1]))))
                coef = np.linalg.lstsq(augmented_z, augmented_y, rcond=None)[0]
            finite_result(coef, "Ridge coefficients")
            sd = _column_rms(yc)
    except (FloatingPointError, np.linalg.LinAlgError) as exc:
        raise Refusal("Training calculation exceeds supported finite numeric domain") from exc
    return FittedModel(tuple(ids), tuple(ids[i] for i in selected), selected,
                       _frozen(mean_all[list(selected)]), _frozen(mean_y),
                       _frozen(components), _frozen(coef), _frozen(sd),
                       float(ridge_alpha), x.shape[0])


def predict(model: FittedModel, X: Any, *, roi_ids: list[str]) -> np.ndarray:
    x = matrix(X, "prediction features")
    ids = identifiers(roi_ids, "prediction ROI IDs", x.shape[1])
    require(set(ids) == set(model.roi_ids), "Prediction ROI identity differs from fitted session")
    order = [ids.index(x) for x in model.selected_roi_ids]
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            return finite_result((x[:, order] - model.mean_x) @ model.components @
                                 model.coef + model.mean_y, "Prediction")
    except FloatingPointError as exc:
        raise Refusal("Prediction exceeds supported finite numeric domain") from exc


def model_record(model: FittedModel) -> dict[str, Any]:
    fields = {
        "roi_ids": list(model.roi_ids), "selected_roi_ids": list(model.selected_roi_ids),
        "mean_x": model.mean_x.tolist(), "mean_y": model.mean_y.tolist(),
        "components": model.components.tolist(), "coef": model.coef.tolist(),
        "training_target_sd": model.training_target_sd.tolist(),
        "ridge_alpha": model.ridge_alpha, "training_rows": model.training_rows,
        "selection": "training_variance_descending_roi_id_ties",
        "pca": "training_centered_unscaled_fixed_rank",
        "ridge_objective": "sum_squared_error_plus_alpha_squared_coef_norm",
    }
    return {**fields, "fit_state_sha256": digest(fields)}


def _sha(value: Any, name: str) -> str:
    require(isinstance(value, str) and len(value) == 64 and
            all(c in "0123456789abcdef" for c in value), name + " must be lowercase SHA256")
    return value


def _records(value: Any, name: str, key: str) -> dict[str, dict[str, Any]]:
    require(isinstance(value, list) and bool(value), name + " must be a nonempty array")
    require(all(isinstance(x, dict) and isinstance(x.get(key), str) for x in value),
            name + " contains malformed records")
    identifiers([x[key] for x in value], name + " IDs")
    return {x[key]: x for x in value}


def _mean_rows(y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            mean = _column_mean(y)
            sd = _column_rms(y - mean)
        return finite_result(mean, "Target mean"), finite_result(sd, "Target SD")
    except FloatingPointError as exc:
        raise Refusal("Target normalization exceeds supported numeric domain") from exc


def admit(dataset: dict[str, Any], protocol: dict[str, Any], *,
          expected_protocol_sha256: str) -> dict[str, Any]:
    """Admit every declared normalized trial, with exact identities and support.

    The caller's expected digest is an external trust input, not proof that the
    protocol was frozen before observing outcomes. Native provenance hashes are
    compared to the declared binding, not independently authenticated here.
    """
    require(isinstance(dataset, dict) and isinstance(protocol, dict),
            "Dataset and protocol must be objects")
    _sha(expected_protocol_sha256, "Expected protocol identity")
    try:
        require(digest(protocol) == expected_protocol_sha256, "Protocol digest mismatch")
        require(protocol["schema"] == "calcium_protocol_v1" and
                dataset["schema"] == "calcium_normalized_v1", "Unsupported schema")
        for document in (dataset, protocol):
            require(document["task_id"] == TASK_ID and document["author_commit"] == AUTHOR_COMMIT,
                    "Task or author source identity mismatch")
            require(document["joint_names"] == list(JOINT_NAMES), "Wrong joint identity/order")
            require(document["target_field"] in ("jointAngles", "jointVelocities"),
                    "Angles and velocities must be separate 24-channel conditions")
            require(document["target_units"] == TARGET_UNITS[document["target_field"]],
                    "Kinematic units differ from source-backed target field")
            require(document["feature_variant"] in FEATURE_FIELDS,
                    "This component supports smoothed deconvolved events or RADICaL as separate tracks")
            require(document["event_conditioning"] == "retrospective_public_liftTimeDLC",
                    "This version is retrospective publicly event-conditioned readout")
            require(document["upstream_exposure_policy"] == "processed_inputs_no_fold_safe_claim",
                    "Decoder fitting does not verify upstream calcium fit exposure")
        require(dataset["target_field"] == protocol["target_field"] and
                dataset["feature_variant"] == protocol["feature_variant"],
                "Dataset target or input variant differs from protocol")
        require(protocol["metric_policy"] == METRIC_POLICY, "Unsupported explicit metric policy")
        require(protocol["condition"] in ("within_mouse", "calibrated_new_mouse_local_baseline"),
                "Unsupported condition; no cross-session ROI correspondence is assumed")
        require(protocol["recipe_selection"] == "fixed_before_evaluation_no_data_tuning",
                "Only an explicitly fixed recipe is implemented")
        window = protocol["window_ms"]
        require(isinstance(window, list) and len(window) == 2 and
                all(type(x) is int for x in window) and window[0] < window[1],
                "Window requires increasing integer milliseconds")
        step = integer(protocol["grid_step_ms"], "grid_step_ms")
        require((window[1] - window[0]) % step == 0, "Window endpoints must lie on the exact grid")
        limits = protocol["limits"]
        max_rows = integer(limits["max_total_timepoints"], "max_total_timepoints")
        max_rois = integer(limits["max_rois_per_session"], "max_rois_per_session")
        max_trials = integer(limits["max_trials_per_session"], "max_trials_per_session")
        grid_length = (window[1] - window[0]) // step + 1
        require(2 <= grid_length <= max_rows, "Window exceeds declared row budget")
        grid = [window[0] + i * step for i in range(grid_length)]
        budget = integer(protocol["cell_budget"], "cell_budget")
        rank = integer(protocol["pca_components"], "pca_components")
        alpha = protocol["ridge_alpha"]
        require(type(alpha) in (int, float) and math.isfinite(alpha) and alpha >= 0,
                "Invalid fixed ridge penalty")
        require(rank <= budget, "PCA rank exceeds fixed cell budget")
        bindings = _records(protocol["sessions"], "Protocol sessions", "session_id")
        supplied = _records(dataset["sessions"], "Dataset sessions", "session_id")
        require(set(bindings) == set(supplied) == set(SESSIONS),
                "Complete five-mouse, ten-session imaging cohort is required")
        admitted: dict[str, Any] = {}
        actual_payload_rows = []
        total_rows = 0
        for session_id, (mouse, region) in SESSIONS.items():
            binding, data = bindings[session_id], supplied[session_id]
            for row in (binding, data):
                require(row["mouse_id"] == mouse and row["region"] == region,
                        "Mouse/region/session identity mismatch")
            for field in ("source_asset_sha256", "clock_evidence_sha256",
                          "feature_provenance_sha256", "normalization_recipe_sha256",
                          "upstream_exposure_sha256", "trial_selection_policy_sha256"):
                require(_sha(binding[field], field) == _sha(data[field], field),
                        "Native provenance binding mismatch: " + field)
            require(isinstance(binding["native_neural_field"], str) and
                    binding["native_neural_field"] == FEATURE_FIELDS[protocol["feature_variant"]] and
                    binding["native_neural_field"] == data["native_neural_field"],
                    "Source-backed neural field/variant mismatch")
            support = binding["upstream_temporal_support_ms"]
            require(isinstance(support, list) and len(support) == 2 and
                    all(type(x) is int for x in support) and support[0] <= window[0] and
                    support[1] >= window[1] and support == data["upstream_temporal_support_ms"],
                    "Upstream temporal support must be explicitly bound and contain output grid")
            if protocol["feature_variant"] == "radical":
                require(support[0] <= -200 and support[1] >= 900,
                        "RADICaL source support includes lift-locked padding outside decoder window")
            roi_ids = identifiers(binding["roi_ids"], "Bound ROI IDs")
            require(data["roi_ids"] == roi_ids, "ROI columns differ from explicit session binding")
            require(budget <= len(roi_ids) <= max_rois, "Cell budget or ROI resource bound violated")
            all_ids = identifiers(binding["all_trial_ids"], "Complete trial census")
            train_ids = identifiers(binding["training_trial_ids"], "Training/calibration trial IDs")
            test_ids = identifiers(binding["evaluation_trial_ids"], "Evaluation trial IDs")
            require(not set(train_ids) & set(test_ids), "A complete trial appears in both splits")
            require(set(train_ids) | set(test_ids) == set(all_ids),
                    "Training and evaluation trials must partition the complete selected census")
            require(len(all_ids) <= max_trials, "Trial resource bound violated")
            require(binding["trial_census_sha256"] == digest(all_ids), "Trial census digest mismatch")
            trials = _records(data["trials"], "Normalized trials", "trial_id")
            require(set(trials) == set(all_ids), "Missing or unexpected normalized trial")
            total_rows += len(all_ids) * grid_length
            require(total_rows <= max_rows, "Complete cohort exceeds declared timepoint budget")
            require(rank <= min(budget, len(train_ids) * grid_length - 1),
                    "PCA rank exceeds available training rows")
            numeric = {}
            for trial_id in all_ids:
                trial = trials[trial_id]
                require(trial["neural_trial_id"] == trial["target_trial_id"] == trial_id,
                        "Neural and kinematic trial identity mismatch")
                require(trial["neural_time_ms"] == trial["target_time_ms"] == grid and
                        all(type(x) is int for x in trial["neural_time_ms"]) and
                        all(type(x) is int for x in trial["target_time_ms"]),
                        "Neural and target grids must exactly match full declared millisecond support")
                x = matrix(trial["neural"], "Neural trial")
                y = matrix(trial["targets"], "Kinematic trial")
                require(x.shape == (grid_length, len(roi_ids)) and
                        y.shape == (grid_length, len(JOINT_NAMES)), "Trial matrix shape mismatch")
                numeric[trial_id] = {"x": x, "y": y}
                actual_payload_rows.append({
                    "session_id": session_id, "trial_id": trial_id,
                    "neural_shape": list(x.shape), "target_shape": list(y.shape),
                    "neural_float64_le_sha256": hashlib.sha256(memoryview(
                        np.ascontiguousarray(x, dtype="<f8")).cast("B")).hexdigest(),
                    "target_float64_le_sha256": hashlib.sha256(memoryview(
                        np.ascontiguousarray(y, dtype="<f8")).cast("B")).hexdigest(),
                })
            admitted[session_id] = {"mouse": mouse, "region": region,
                                    "roi_ids": roi_ids, "training_ids": train_ids,
                                    "evaluation_ids": test_ids, "trials": numeric}
        cases = protocol["new_mouse_cases"]
        if protocol["condition"] == "within_mouse":
            require(cases == [], "Within-mouse condition cannot carry new-mouse claims")
        else:
            case_map = _records(cases, "New-mouse cases", "heldout_mouse")
            require(set(case_map) == set(MICE), "All five held-out mouse cases are required")
            for mouse, case in case_map.items():
                development = identifiers(case["development_mice"], "Development mice", 4)
                require(set(development) == set(MICE) - {mouse}, "Outer mouse leakage")
                require(case["transfer"] == "none_session_local_calibration_only",
                        "This baseline does not establish neuron correspondence or transfer")
                require(case["calibration_label_access"] == "declared_training_trials_only",
                        "Undefined calibration-label access")
                expected_calibration = {s: admitted[s]["training_ids"] for s in SESSIONS
                                        if SESSIONS[s][0] == mouse}
                require(case["calibration_trials"] == expected_calibration,
                        "Each new mouse must have exact session-local calibration trials")
        return {"sessions": admitted, "protocol": protocol,
                "protocol_sha256": expected_protocol_sha256, "total_timepoints": total_rows,
                "normalized_input_sha256": digest({"protocol_sha256": expected_protocol_sha256,
                                                    "actual_numeric_payload": actual_payload_rows})}
    except Refusal:
        raise
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise Refusal("Malformed normalized dataset or explicit protocol: " + str(exc)) from exc


def _finite_list(values: np.ndarray) -> list[float]:
    return finite_result(np.asarray(values), "Metric result").astype(float).tolist()


def _score(admitted: dict[str, Any], predictions: dict[str, Any]) -> dict[str, Any]:
    sessions = admitted["sessions"]
    require(isinstance(predictions, dict) and set(predictions) == set(SESSIONS),
            "Predictions must cover all ten sessions exactly")
    session_results = {}
    mouse_accumulator = {mouse: [] for mouse in MICE}
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            for session_id, session in sessions.items():
                supplied = predictions[session_id]
                require(isinstance(supplied, dict) and set(supplied) == set(session["evaluation_ids"]),
                        "Predictions must cover every evaluation trial exactly")
                training_y = np.concatenate([session["trials"][t]["y"]
                                             for t in session["training_ids"]], axis=0)
                _, scale = _mean_rows(training_y)
                trial_rmse, observed = [], []
                for trial_id in session["evaluation_ids"]:
                    y = session["trials"][trial_id]["y"]
                    p = matrix(supplied[trial_id], "Candidate predictions")
                    require(p.shape == y.shape, "Prediction matrix shape mismatch")
                    trial_rmse.append(_column_rms(finite_result(p - y, "Trial residual")))
                    observed.append(y)
                rmse = _column_rms(np.stack(trial_rmse))
                nrmse = [float(rmse[j] / scale[j]) if scale[j] > 0 else None
                         for j in range(len(JOINT_NAMES))]
                require(all(x is None or math.isfinite(x) for x in nrmse), "NRMSE is nonfinite")
                session_results[session_id] = {
                    "mouse_id": session["mouse"], "region": session["region"],
                    "evaluation_trials": len(observed), "training_target_sd": _finite_list(scale),
                    "rmse_per_joint": _finite_list(rmse), "nrmse_per_joint": nrmse,
                    "undefined_normalization_joints": [JOINT_NAMES[j] for j, x in enumerate(nrmse)
                                                        if x is None],
                }
                # Whole trials have identical windows; use explicit per-trial
                # moments so no future variable-length extension can pool them.
                session_mean = _column_mean(np.stack([_column_mean(y) for y in observed]))
                session_target_rms = _column_rms(np.stack([_column_rms(y - session_mean)
                                                          for y in observed]))
                session_r2 = [float(1 - (rmse[j] / session_target_rms[j]) ** 2)
                              if session_target_rms[j] > 0 else None for j in range(len(JOINT_NAMES))]
                require(all(x is None or math.isfinite(x) for x in session_r2), "R-squared is nonfinite")
                session_results[session_id]["r_squared_per_joint"] = session_r2
                session_results[session_id]["undefined_r_squared_joints"] = [
                    JOINT_NAMES[j] for j, x in enumerate(session_r2) if x is None]
                mouse_accumulator[session["mouse"]].append({"nrmse": nrmse, "r2": session_r2})
            mice_results = {}
            for mouse in MICE:
                records = mouse_accumulator[mouse]
                require(len(records) == 2, "Each mouse requires both M1/S1 sessions")
                per_joint = [None if any(r["nrmse"][j] is None for r in records)
                             else math.fsum(r["nrmse"][j] for r in records) / 2
                             for j in range(len(JOINT_NAMES))]
                # Session-local target means prevent between-session offsets
                # from masquerading as decoded movement variance.
                r2 = [None if any(r["r2"][j] is None for r in records)
                      else math.fsum(r["r2"][j] / 2 for r in records)
                      for j in range(len(JOINT_NAMES))]
                require(all(x is None or math.isfinite(x) for x in r2), "R-squared is nonfinite")
                mice_results[mouse] = {"nrmse_per_joint": per_joint,
                                       "nrmse": None if any(x is None for x in per_joint)
                                       else math.fsum(per_joint) / len(JOINT_NAMES),
                                       "r_squared_per_joint": r2,
                                       "undefined_r_squared_joints": [JOINT_NAMES[j] for j, x in enumerate(r2)
                                                                      if x is None]}
            values = [mice_results[m]["nrmse"] for m in MICE]
            primary = None if any(x is None for x in values) else math.fsum(values) / len(MICE)
            secondary = [None if any(mice_results[m]["r_squared_per_joint"][j] is None for m in MICE)
                         else math.fsum(mice_results[m]["r_squared_per_joint"][j] for m in MICE) / len(MICE)
                         for j in range(len(JOINT_NAMES))]
    except (FloatingPointError, OverflowError) as exc:
        raise Refusal("Scoring exceeds supported finite numeric domain") from exc
    return {"status": "scored_normalized_source_only", "task_id": TASK_ID,
            "condition": admitted["protocol"]["condition"],
            "target_field": admitted["protocol"]["target_field"],
            "target_units": admitted["protocol"]["target_units"],
            "feature_variant": admitted["protocol"]["feature_variant"],
            "event_conditioning": "retrospective_public_liftTimeDLC",
            "upstream_exposure_policy": "processed_inputs_no_fold_safe_claim",
            "metric_policy": METRIC_POLICY, "protocol_sha256": admitted["protocol_sha256"],
            "normalized_input_sha256": admitted["normalized_input_sha256"],
            "joint_names": list(JOINT_NAMES), "mouse_macro_nrmse": primary,
            "primary_status": "defined" if primary is not None else "undefined_training_target_scale",
            "mouse_macro_r_squared_per_joint": secondary,
            "mice": mice_results, "sessions": session_results,
            "support": {"mice": 5, "sessions": 10,
                        "evaluation_trials": sum(len(s["evaluation_ids"]) for s in sessions.values()),
                        "complete_declared_normalized_census": True},
            "verification": {"authentic_input_identity": False, "native_clock_alignment": False,
                             "original_route_parity": False, "reference_competence": False,
                             "protected_candidate_execution": False, "scientific_qualification": False,
                             "cross_animal_transfer_demonstrated": False,
                             "causal_online_decoding": False, "upstream_preprocessing_fold_safe": False,
                             "protocol_frozen_before_outcomes": False}}


def score_predictions(dataset: dict[str, Any], protocol: dict[str, Any],
                      predictions: dict[str, Any], *, expected_protocol_sha256: str) -> dict[str, Any]:
    """Operator-side complete-domain scorer; not a protected evaluation process."""
    return _score(admit(dataset, protocol, expected_protocol_sha256=expected_protocol_sha256), predictions)


def run_pipeline(dataset: dict[str, Any], protocol: dict[str, Any], *,
                 expected_protocol_sha256: str) -> dict[str, Any]:
    """Fit ten independent session-local models and score all five mice.

    All selected training/calibration trials are consumed; no evaluation target
    or neural sample participates in selection, centering, PCA or fitting.
    """
    admitted = admit(dataset, protocol, expected_protocol_sha256=expected_protocol_sha256)
    predictions, models = {}, {}
    for session_id, session in admitted["sessions"].items():
        train_x = np.concatenate([session["trials"][t]["x"] for t in session["training_ids"]])
        train_y = np.concatenate([session["trials"][t]["y"] for t in session["training_ids"]])
        model = fit_train_only(train_x, train_y, roi_ids=session["roi_ids"],
                               cell_budget=protocol["cell_budget"],
                               pca_components=protocol["pca_components"],
                               ridge_alpha=protocol["ridge_alpha"])
        predictions[session_id] = {
            t: predict(model, session["trials"][t]["x"], roi_ids=session["roi_ids"]).tolist()
            for t in session["evaluation_ids"]}
        models[session_id] = model_record(model)
    return {"metrics": _score(admitted, predictions), "models": models,
            "predictions": predictions, "execution_scope": "normalized_session_local_reference",
            "original_route_status": "source_characterized_not_executed"}


def paired_mouse_uncertainty(candidate: dict[str, Any], reference: dict[str, Any]) -> dict[str, Any]:
    """Exact ordered five-mouse bootstrap, descriptive and paired by mouse.

    No significance threshold, coverage guarantee, or extra independent units
    are inferred from the 5**5 resampling combinations.
    """
    try:
        for name in ("task_id", "condition", "target_field", "target_units", "feature_variant",
                     "event_conditioning", "upstream_exposure_policy", "metric_policy",
                     "protocol_sha256", "normalized_input_sha256", "joint_names"):
            require(candidate[name] == reference[name], "Paired comparison differs in " + name)
        for result in (candidate, reference):
            require(result["status"] == "scored_normalized_source_only" and
                    result["task_id"] == TASK_ID and result["metric_policy"] == METRIC_POLICY and
                    result["joint_names"] == list(JOINT_NAMES), "Invalid paired metric domain")
            _sha(result["protocol_sha256"], "Paired protocol identity")
            _sha(result["normalized_input_sha256"], "Paired normalized input identity")
            require(set(result["mice"]) == set(MICE) and result["support"]["mice"] == 5 and
                    result["support"]["sessions"] == 10 and
                    result["support"]["complete_declared_normalized_census"] is True,
                    "Paired uncertainty requires complete matching biological support")
            for mouse in MICE:
                value = result["mice"][mouse]["nrmse"]
                require(value is None or (type(value) in (int, float) and math.isfinite(value)
                                         and value >= 0), "Invalid paired mouse metric")
    except Refusal:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise Refusal("Malformed paired metric records: " + str(exc)) from exc
    differences = {m: None if candidate["mice"][m]["nrmse"] is None or
                   reference["mice"][m]["nrmse"] is None else
                   reference["mice"][m]["nrmse"] - candidate["mice"][m]["nrmse"]
                   for m in MICE}
    result = {"direction": "reference_minus_candidate_nrmse_positive_favors_candidate",
              "mouse_differences": differences, "independent_biological_units": 5,
              "method": "all_3125_ordered_five_mouse_bootstrap_linear_percentiles",
              "descriptive_exploratory_only": True, "coverage_validated": False}
    if any(v is None for v in differences.values()):
        return {**result, "status": "undefined_full_mouse_support", "mean_difference": None,
                "percentile_interval_95": None, "bootstrap_resamples": 0}
    values = [differences[m] for m in MICE]
    require(all(math.isfinite(v) for v in values), "Paired difference exceeds numeric domain")
    resampled = [float(_column_mean(np.asarray([values[i] for i in draw])[:, None])[0])
                 for draw in itertools.product(range(5), repeat=5)]
    return {**result, "status": "defined_descriptive",
            "mean_difference": float(_column_mean(np.asarray(values)[:, None])[0]),
            "percentile_interval_95": np.quantile(resampled, [0.025, 0.975], method="linear").tolist(),
            "bootstrap_resamples": 3125}


def run_reference_controls(dataset: dict[str, Any], protocol: dict[str, Any],
                           context: dict[str, Any], *, expected_protocol_sha256: str,
                           expected_context_sha256: str) -> dict[str, Any]:
    """Run complete phase/direction controls and a training-only shift diagnostic.

    Context is public experimental reach target and original trial number. Its
    digest is an operator binding, not independent native-context verification.
    """
    admitted = admit(dataset, protocol, expected_protocol_sha256=expected_protocol_sha256)
    try:
        require(digest(context) == _sha(expected_context_sha256, "Expected context identity"),
                "Context digest mismatch")
        require(context["schema"] == "calcium_reach_context_v1" and context["task_id"] == TASK_ID,
                "Wrong context schema/task")
        require(context["event_conditioning"] == "retrospective_public_liftTimeDLC",
                "Controls require the same public event phase")
        context_sessions = _records(context["sessions"], "Context sessions", "session_id")
        require(set(context_sessions) == set(SESSIONS), "Context must cover all ten sessions")
        labels = {}
        for session_id, session in admitted["sessions"].items():
            row = context_sessions[session_id]
            binding = next(x for x in protocol["sessions"] if x["session_id"] == session_id)
            require(row["source_asset_sha256"] == binding["source_asset_sha256"], "Context source differs")
            _sha(row["native_target_mapping_sha256"], "Target mapping evidence")
            records = _records(row["trials"], "Context trials", "trial_id")
            require(set(records) == set(session["trials"]), "Context must cover complete trial census")
            numbers = []
            for trial_id, record in records.items():
                number = integer(record["original_trial_number"], "Original trial number", minimum=0)
                require(record["reach_target"] in ("left", "right"), "Unknown reach target")
                numbers.append(number)
            require(len(set(numbers)) == len(numbers), "Original trial numbers must be unique per session")
            labels[session_id] = records
    except Refusal:
        raise
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise Refusal("Malformed complete control context: " + str(exc)) from exc
    baseline = run_pipeline(dataset, protocol, expected_protocol_sha256=expected_protocol_sha256)
    names = ("phase_only", "target_only", "phase_by_target", "within_target_trial_shift")
    predictions = {name: {} for name in names}
    unsupported: dict[str, list[str]] = {name: [] for name in names}
    shift_models = {}
    for session_id, session in admitted["sessions"].items():
        train = session["training_ids"]
        trials = session["trials"]
        context_rows = labels[session_id]
        phase = _column_mean(np.stack([trials[t]["y"] for t in train]))
        predictions["phase_only"][session_id] = {t: phase for t in session["evaluation_ids"]}
        groups = {label: sorted([t for t in train if context_rows[t]["reach_target"] == label],
                                key=lambda t: context_rows[t]["original_trial_number"])
                  for label in ("left", "right")}
        wanted = {context_rows[t]["reach_target"] for t in session["evaluation_ids"]}
        missing = [label for label in wanted if not groups[label]]
        if missing:
            for name in ("target_only", "phase_by_target"):
                unsupported[name].append(session_id + ": no training support for " + ",".join(sorted(missing)))
        else:
            target_means = {label: _column_mean(np.concatenate([trials[t]["y"] for t in groups[label]]))
                            for label in wanted}
            phase_means = {label: _column_mean(np.stack([trials[t]["y"] for t in groups[label]]))
                           for label in wanted}
            predictions["target_only"][session_id] = {
                t: np.broadcast_to(target_means[context_rows[t]["reach_target"]], trials[t]["y"].shape)
                for t in session["evaluation_ids"]}
            predictions["phase_by_target"][session_id] = {
                t: phase_means[context_rows[t]["reach_target"]] for t in session["evaluation_ids"]}
        if any(len(group) < 2 for group in groups.values()):
            unsupported["within_target_trial_shift"].append(
                session_id + ": fewer than two training trials in a reach-target category")
        else:
            rotated = {t: group[(i + 1) % len(group)]
                       for group in groups.values() for i, t in enumerate(group)}
            model = fit_train_only(np.concatenate([trials[t]["x"] for t in train]),
                                   np.concatenate([trials[rotated[t]]["y"] for t in train]),
                                   roi_ids=session["roi_ids"], cell_budget=protocol["cell_budget"],
                                   pca_components=protocol["pca_components"], ridge_alpha=protocol["ridge_alpha"])
            predictions["within_target_trial_shift"][session_id] = {
                t: predict(model, trials[t]["x"], roi_ids=session["roi_ids"])
                for t in session["evaluation_ids"]}
            shift_models[session_id] = {"rotation": rotated, "model": model_record(model)}
    controls, comparisons = {}, {}
    for name in names:
        if unsupported[name]:
            controls[name] = {"status": "unsupported_complete_population", "reasons": unsupported[name],
                              "metrics": None, "partial_population_scoring": False}
            comparisons[name] = None
        else:
            metrics = _score(admitted, predictions[name])
            controls[name] = {"status": "scored_normalized_source_only", "metrics": metrics}
            comparisons[name] = paired_mouse_uncertainty(baseline["metrics"], metrics)
    return {"baseline": baseline, "controls": controls, "paired_comparisons": comparisons,
            "within_target_trial_shift_models": shift_models if not unsupported["within_target_trial_shift"] else {},
            "context_sha256": expected_context_sha256,
            "shift_policy": "cyclic_plus_one_whole_training_trial_within_session_and_reach_target_sorted_original_number",
            "phase_policy": "training_only_mean_trajectory_on_identical_public_event_grid",
            "native_context_verified": False, "scientific_qualification": False}


def freeze_within_mouse_splits(context: dict[str, Any], *, expected_context_sha256: str,
                               seed: int) -> dict[str, Any]:
    """Freeze one 90/10 split per session and reach target from metadata alone.

    This prospective recipe is not the author's repeated CV. A split includes
    ceil(n/10) evaluation trials per direction; at least two training trials per
    direction remain so the within-direction rotation diagnostic is supported.
    """
    _sha(expected_context_sha256, "Context identity")
    integer(seed, "seed", minimum=0)
    require(digest(context) == expected_context_sha256, "Context digest mismatch")
    try:
        require(context["schema"] == "calcium_reach_context_v1" and context["task_id"] == TASK_ID and
                context["event_conditioning"] == "retrospective_public_liftTimeDLC", "Wrong context")
        sessions = _records(context["sessions"], "Context sessions", "session_id")
        require(set(sessions) == set(SESSIONS), "All ten sessions are required for split freezing")
        splits = {}
        for session_id, row in sessions.items():
            trials = _records(row["trials"], "Context trials", "trial_id")
            for record in trials.values():
                integer(record["original_trial_number"], "Original trial number", minimum=0)
                require(record["reach_target"] in ("left", "right"), "Unknown reach target")
            require(len({x["original_trial_number"] for x in trials.values()}) == len(trials),
                    "Duplicate original trial number")
            evaluation = []
            for target in ("left", "right"):
                group = [t for t in trials if trials[t]["reach_target"] == target]
                count = (len(group) + 9) // 10
                require(count >= 1 and len(group) - count >= 2,
                        "Each direction needs at least three eligible whole trials")
                ranked = sorted(group, key=lambda t: (digest({
                    "domain": "NEURAL025-prospective-stratified-v1", "seed": seed,
                    "session_id": session_id, "trial_id": t}), t))
                evaluation.extend(ranked[:count])
            ordered = sorted(trials, key=lambda t: trials[t]["original_trial_number"])
            splits[session_id] = {"all_trial_ids": ordered, "trial_census_sha256": digest(ordered),
                                  "training_trial_ids": [t for t in ordered if t not in evaluation],
                                  "evaluation_trial_ids": [t for t in ordered if t in evaluation]}
        return {"status": "metadata_split_frozen", "recipe": "single_90_10_stratified_hash_split_v1",
                "seed": seed, "context_sha256": expected_context_sha256, "sessions": splits,
                "authentic_eligibility_verified": False, "frozen_before_outcomes_verified": False,
                "scientific_qualification": False}
    except Refusal:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise Refusal("Malformed split metadata: " + str(exc)) from exc


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate JSON key: " + key)
        result[key] = value
    return result


def _read_bounded(stream: Any, limit: int) -> bytes:
    # A logical large limit must not become a large allocation before seeing
    # any input bytes. Capture in fixed chunks and probe at most one excess byte.
    chunks, total = [], 0
    while total <= limit:
        chunk = stream.read(min(65536, limit + 1 - total))
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
    require(total <= limit, "Request exceeds input-byte budget")
    return b"".join(chunks)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("fit-score", "score", "compare-controls"))
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--expected-input-sha256", required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--expected-context-sha256")
    parser.add_argument("--max-input-bytes", required=True, type=int)
    parser.add_argument("--max-output-bytes", required=True, type=int)
    args = parser.parse_args(argv)
    try:
        require(0 < args.max_input_bytes < sys.maxsize and 0 < args.max_output_bytes < sys.maxsize,
                "Byte budgets must be positive and below the platform index limit")
        _sha(args.expected_input_sha256, "Expected request identity")
        with args.input.open("rb") as stream:
            body = _read_bounded(stream, args.max_input_bytes)
        require(hashlib.sha256(body).hexdigest() == args.expected_input_sha256, "Request digest mismatch")
        request = json.loads(body, object_pairs_hook=_unique_object,
                             parse_constant=lambda _: (_ for _ in ()).throw(Refusal("Nonfinite JSON")))
        if args.mode == "fit-score":
            result = run_pipeline(request["dataset"], request["protocol"],
                                  expected_protocol_sha256=args.expected_protocol_sha256)
        elif args.mode == "score":
            result = score_predictions(request["dataset"], request["protocol"], request["predictions"],
                                       expected_protocol_sha256=args.expected_protocol_sha256)
        else:
            result = run_reference_controls(request["dataset"], request["protocol"], request["context"],
                                            expected_protocol_sha256=args.expected_protocol_sha256,
                                            expected_context_sha256=args.expected_context_sha256)
        rendered = canonical_bytes(result) + b"\n"
        require(len(rendered) <= args.max_output_bytes, "Result exceeds output-byte budget")
        sys.stdout.buffer.write(rendered)
        return 0
    except (Refusal, OSError, ValueError, TypeError, KeyError, RecursionError, OverflowError) as exc:
        # Diagnostics contain only the refusal reason, never request contents.
        print(json.dumps({"status": "refused", "reason": str(exc)[:1000],
                          "scientific_qualification": False}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
