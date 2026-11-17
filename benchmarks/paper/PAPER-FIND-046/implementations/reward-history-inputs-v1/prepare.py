#!/usr/bin/env python3
"""Prepare the pinned Figure 3k robustfit inputs; never fit or score a model."""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import math
from pathlib import Path

RATS = ("G008", "G016", "G021", "G022", "G024", "G036", "G037", "G051", "G127")
STAGES = ("Proestrus", "Diestrus")
SOURCE_REVISION = "b7b68ca8c107d8ce4a061e16da214307f175c3e5"
NBACK = 7


class ContractError(ValueError):
    """The export cannot preserve the source's row associations."""


def require(condition, message):
    if not condition:
        raise ContractError(message)


def finite_number(value, where, nullable=False):
    if value is None and nullable:
        return None
    require(isinstance(value, (int, float)) and not isinstance(value, bool),
            f"{where}: finite number required")
    try:
        value = float(value)
    except OverflowError as exc:
        raise ContractError(f"{where}: finite number required") from exc
    require(math.isfinite(value), f"{where}: nonfinite values must use null")
    return value


def integer(value, where, minimum):
    require(isinstance(value, int) and not isinstance(value, bool) and value >= minimum,
            f"{where}: integer >= {minimum} required")
    return value


def date(value, where):
    require(isinstance(value, str) and len(value) == 8, f"{where}: YYYYMMDD required")
    try:
        parsed = datetime.strptime(value, "%Y%m%d")
    except ValueError as exc:
        raise ContractError(f"{where}: YYYYMMDD required") from exc
    require(parsed.strftime("%Y%m%d") == value, f"{where}: canonical YYYYMMDD required")
    return value


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def source_window(width):
    """MATLAB i1:i2 directly indexes pstruct; do NOT strip its first column."""
    require(width >= 4, "CPIn needs at least three clock samples plus its leading column")
    times = [-5.0 + 15.0 * i / (width - 2) for i in range(width - 1)]
    nearest = lambda target: min(range(len(times)), key=lambda i: abs(times[i] - target))
    start, end = nearest(0.0), nearest(0.5)
    require(start < end, "clock does not resolve the source 0 to 0.5 second window")
    dt = sum(times[i + 1] - times[i] for i in range(len(times) - 1)) / (len(times) - 1)
    return start, end, dt, {
        "clock": "linspace(-5,10,CPIn_width-1)",
        "clock_samples": len(times),
        "dt_seconds": dt,
        "clock_indices_zero_based": [start, end],
        "pstruct_columns_one_based_inclusive": [start + 1, end + 1],
        "nominal_clock_window_seconds": [times[start], times[end]],
        "operation": "sum(pstruct(:,i1:i2),2) * mean(diff(T)); no baseline subtraction",
        "leading_column_removed": False,
    }


def prepare_rat(rat, data):
    require(isinstance(data, dict), f"{rat}: object required")
    matrix, behavior = data.get("cpin"), data.get("behavior")
    require(isinstance(matrix, list) and matrix and isinstance(matrix[0], list),
            f"{rat}: nonempty CPIn matrix required")
    require(isinstance(behavior, list) and len(behavior) == len(matrix),
            f"{rat}: CPIn/behavior row mismatch")
    width = len(matrix[0])
    start, end, dt, window = source_window(width)
    records, seen, maxima = [], set(), {}
    for i, (signal, row) in enumerate(zip(matrix, behavior)):
        where = f"{rat}/row/{i}"
        require(isinstance(signal, list) and len(signal) == width, f"{where}: ragged CPIn")
        signal = [finite_number(v, where, nullable=True) for v in signal]
        require(isinstance(row, dict), f"{where}: behavior object required")
        day = date(row.get("unique_day"), where)
        trial = integer(row.get("trial_number"), where, 1)
        identity = (day, trial)
        require(identity not in seen, f"{where}: duplicate day/trial identity")
        seen.add(identity)
        reward = finite_number(row.get("reward"), where)
        require(reward > 0, f"{where}: positive finite Reward required for real log2; no row is silently dropped")
        stages = row.get("stages")
        require(isinstance(stages, list) and all(isinstance(s, str) for s in stages),
                f"{where}: stage-label string array required")
        block = integer(row.get("block"), where, 1)
        require(block <= 3, f"{where}: Block must be 1, 2 or 3")
        trial_type = integer(row.get("trial_type"), where, 0)
        selected = signal[start:end + 1]
        auc = None if None in selected else sum(selected) * dt
        require(auc is None or math.isfinite(auc), f"{where}: AUC overflow")
        records.append({"source_row_zero_based": i, "identity": list(identity),
                        "reward_log2": math.log2(reward), "auc": auc,
                        "stages": list(stages), "block": block, "trial_type": trial_type})
        maxima[day] = max(trial, maxima.get(day, 0))
    # Source concatenates sorted unique dates and dense trial-number vectors,
    # then applies a mask in ORIGINAL bdata order. Establish equality explicitly.
    require([tuple(r["identity"]) for r in records] == sorted(seen),
            f"{rat}: original behavior order differs from sorted day/trial order; source positional stage mask is not identity-safe")
    offsets, total = {}, 0
    sessions = []
    for day in sorted(maxima):
        offsets[day] = total
        sessions.append({"unique_day": day, "padded_trial_count": maxima[day],
                         "concatenated_offset_zero_based": total,
                         "observed_trial_count": sum(r["identity"][0] == day for r in records)})
        total += maxima[day]
    require(total >= NBACK,
            f"{rat}: source lag construction requires at least {NBACK} padded trial positions")
    # Sparse representation equals the source dense NaN padding without allocating
    # max(TrialNumber) rows; missing trial numbers remain missing lag observations.
    by_position = {offsets[r["identity"][0]] + r["identity"][1] - 1: r for r in records}
    rows = []
    for position, record in by_position.items():
        history = [by_position.get(position - lag) for lag in range(NBACK + 1)]
        values = [None if previous is None else previous["reward_log2"] for previous in history]
        ids = [None if previous is None else previous["identity"] for previous in history]
        cross = [lag for lag, previous in enumerate(history) if previous is not None and
                 previous["identity"][0] != record["identity"][0]]
        rows.append({**record, "concatenated_position_zero_based": position,
                     "predictors_log2_reward_current_through_lag7": values,
                     "predictor_trial_identities": ids, "cross_session_lag_numbers": cross,
                     "missing_predictor_lag_numbers": [lag for lag, value in enumerate(values) if value is None],
                     "complete_numeric_row": record["auc"] is not None and None not in values})
    stages = {}
    for stage in STAGES:
        selected = [r for r in rows if stage in r["stages"]]
        stages[stage] = {
            "trial_identities": [r["identity"] for r in selected],
            "X_without_intercept": [r["predictors_log2_reward_current_through_lag7"] for r in selected],
            "AUC": [r["auc"] for r in selected],
            "complete_numeric_rows": [r["complete_numeric_row"] for r in selected],
            "n_selected_rows": len(selected),
            "n_complete_numeric_rows": sum(r["complete_numeric_row"] for r in selected),
            "selected_despite_comment_mixed_nonviolation_filter": [r["identity"] for r in selected
                if r["block"] != 1 or r["trial_type"] == 2],
            "selection": "stage membership only; Block and TrialType predicates are commented out in source",
        }
    return {"rat": rat, "window": window, "sessions": sessions,
            "n_source_rows": len(rows), "n_padded_source_positions": total,
            "row_ledger": rows, "stages": stages}


def prepare(payload):
    require(isinstance(payload, dict) and type(payload.get("schema_version")) is int and payload["schema_version"] == 1,
            "schema_version must be 1")
    require(payload.get("input_kind") in ("generated_engineering_control", "authorized_native_export"),
            "explicit input_kind required")
    require(payload.get("ratlist") == list(RATS), "full pinned nine-rat ordered roster required")
    population = payload.get("figure3_cpin")
    require(isinstance(population, dict) and set(population) == set(RATS),
            "figure3_cpin keys must exactly equal the full source roster")
    return {"schema_version": 1, "task_id": "PAPER-FIND-046",
            "implementation": "reward-history-inputs-v1", "source_revision": SOURCE_REVISION,
            "input_kind": payload["input_kind"], "status": "regression_input_construction_only",
            "research_qualified": False, "improvement_eligible": False,
            "source_figure": "3k", "nback": NBACK, "stage_order": list(STAGES),
            "coefficient_order_for_native_robustfit": ["intercept", "current_reward_log2"] +
                [f"lag_{i}_reward_log2" for i in range(1, NBACK + 1)],
            "rats": [prepare_rat(rat, population[rat]) for rat in RATS],
            "fit_policy": "No coefficients or p-values. Preserve selected rows and nulls for independent MATLAB robustfit calibration; complete_numeric_rows is diagnostic only.",
            "limits": [
                "Native archive/export identity and MATLAB parity are unverified.",
                "Executable source semantics differ from mixed-block prose; this component preserves executable semantics.",
                "Other Figure 3 RPE, supplied BestFits and Figure 2 controls remain separate and required for full calibration.",
                "No native preparation, fit, paper reproduction, ordered improvement endpoint or scientific performance is established.",
            ]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        payload = json.loads(args.input.read_text(), object_pairs_hook=unique_object,
                             parse_constant=lambda value: (_ for _ in ()).throw(ContractError(f"invalid JSON constant: {value}")))
        result = prepare(payload)
        args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    except (ContractError, OSError, json.JSONDecodeError) as exc:
        parser.exit(2, f"input rejected: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
