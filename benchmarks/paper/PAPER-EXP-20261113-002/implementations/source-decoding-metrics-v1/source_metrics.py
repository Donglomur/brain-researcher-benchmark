"""Reduce Horrocks publication-route decoder outputs; no fitting or reward.

Input arrays correspond to native perm.meanPerf (within-time) and perm.perf
(cross-time). They must be prepared by a separately authenticated operator.
This module cannot establish their cohort, split or model provenance.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path

SCHEMA = "horrocks-source-decoding-accuracies-v1"
CHANCE = 1 / 6
STATES = ("stat", "run")
SESSIONS = (
    "M22027_20220517", "M22029_20220607", "M22031_20220524",
    "M22032_20220621", "M22033_20220706",
)
WITHIN_CENTERS_MS = tuple(range(-150, 1751, 10))
CROSS_CENTERS_MS = tuple(range(-150, 1751, 100))
STIMULUS_INDICES = tuple(range(2, 12))  # MATLAB 3:12; 0--100 through 900--1000 ms.
EARLY_TRAIN_INDEX = 3  # MATLAB 4; 100--200 ms.
INPUT_CAP = 4 * 1024 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result

    def nonfinite(_):
        raise ValueError("nonfinite JSON value")

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=nonfinite)


def validate_array(value, shape, name):
    """Require complete original support; do not drop cells or accept NaNs."""
    if shape:
        require(type(value) is list and len(value) == shape[0],
                f"{name}: expected shape {shape}")
        for child in value:
            validate_array(child, shape[1:], name)
    else:
        require(type(value) in (int, float) and math.isfinite(value)
                and 0 <= value <= 1, f"{name}: accuracy must be finite in [0,1]")


def mean(values):
    return math.fsum(values) / len(values)


def mean_axis_zero(arrays):
    """Equal weight for permutations/mice, without flattening other axes."""
    if type(arrays[0]) is list:
        return [mean_axis_zero([array[i] for array in arrays])
                for i in range(len(arrays[0]))]
    return mean(arrays)


def sem_axis_zero(arrays):
    if type(arrays[0]) is list:
        return [sem_axis_zero([array[i] for array in arrays])
                for i in range(len(arrays[0]))]
    center = mean(arrays)
    return math.sqrt(math.fsum((value - center) ** 2 for value in arrays)
                     / (len(arrays) - 1) / len(arrays))


def score_within_time_folds(folds):
    """do_cvDA.m semantics for one window: mean of three fold accuracies.

    Each fold is six prediction lists in true-class order 1..6. A source fold
    uses the same held trial positions per class. Fold sizes may differ by one;
    pooling trials across folds would change the source meanPerf.
    """
    require(type(folds) is list and len(folds) == 3, "three within-time folds required")
    accuracies = []
    sizes = []
    for fold in folds:
        require(type(fold) is list and len(fold) == 6, "six ordered true classes")
        require(all(type(row) is list for row in fold), "class prediction lists")
        n_test = len(fold[0])
        require(n_test > 0 and all(len(row) == n_test for row in fold),
                "balanced nonempty class support in each fold")
        require(all(type(pred) is int and 1 <= pred <= 6
                    for row in fold for pred in row), "class predictions must be 1..6")
        correct = sum(pred == label for label, row in enumerate(fold, 1) for pred in row)
        accuracies.append(correct / (6 * n_test))
        sizes.append(n_test)
    require(max(sizes) - min(sizes) <= 1, "source k-fold test sizes differ by at most one")
    return {"fold_accuracy": accuracies, "fold_trials_per_class": sizes,
            "mean_accuracy": mean(accuracies)}


def relative_performance(matrix):
    """Source AUC-type equation-21 reduction, after averaging permutations.

    Preserve the denominator and unclipped raw accuracy separately. Clip
    accuracy minus chance below zero before summing, but do not cap the ratio.
    A zero denominator has no defined relative score; no epsilon or omission.
    """
    validate_array(matrix, (20, 20), "cross-time mean")
    diagonal = [matrix[i][i] for i in range(20)]
    denominator = math.fsum(max(diagonal[i] - CHANCE, 0.0) for i in STIMULUS_INDICES)
    numerators = [math.fsum(max(row[i] - CHANCE, 0.0) for i in STIMULUS_INDICES)
                  for row in matrix]
    ratios = [value / denominator if denominator > 0 else None for value in numerators]
    return {"diagonal_accuracy": diagonal,
            "stimulus_diagonal_above_chance_sum": denominator,
            "stimulus_cross_time_above_chance_sum": numerators,
            "relative_performance": ratios,
            "early_relative_performance": ratios[EARLY_TRAIN_INDEX],
            "undefined_reason": None if denominator > 0 else "zero_above_chance_diagonal_sum"}


def summarize(document):
    """Retain the complete two-endpoint, five-mouse support and state dispatch."""
    require(type(document) is dict and set(document) == {"schema", "sessions"},
            "exact input fields: schema, sessions")
    require(document["schema"] == SCHEMA, "input schema")
    sessions = document["sessions"]
    require(type(sessions) is dict and set(sessions) == set(SESSIONS),
            "all five original sessions required")
    per_mouse = {}
    for session_id in SESSIONS:
        session = sessions[session_id]
        require(type(session) is dict and set(session) == set(STATES),
                "separate stat and run states required")
        per_mouse[session_id] = {}
        for state in STATES:
            data = session[state]
            require(type(data) is dict and set(data) == {"within_time", "cross_time"},
                    "both within-time and cross-time endpoints required")
            validate_array(data["within_time"], (5, 191), "within-time permutations")
            validate_array(data["cross_time"], (5, 20, 20), "cross-time permutations")
            within = mean_axis_zero(data["within_time"])
            cross = mean_axis_zero(data["cross_time"])
            per_mouse[session_id][state] = {
                "within_time_mean_accuracy": within,
                "cross_time_mean_accuracy": cross,
                **relative_performance(cross),
            }

    group = {}
    for state in STATES:
        rows = [per_mouse[session_id][state] for session_id in SESSIONS]
        group[state] = {}
        for metric in ("within_time_mean_accuracy", "cross_time_mean_accuracy", "diagonal_accuracy"):
            values = [row[metric] for row in rows]
            group[state][metric] = {"mean": mean_axis_zero(values), "sem": sem_axis_zero(values)}
        valid = all(row["undefined_reason"] is None for row in rows)
        values = [row["relative_performance"] for row in rows]
        group[state]["relative_performance"] = {
            "mean": mean_axis_zero(values) if valid else None,
            "sem": sem_axis_zero(values) if valid else None,
            "undefined_sessions": [session_id for session_id in SESSIONS
                                   if per_mouse[session_id][state]["undefined_reason"] is not None],
        }
    paired = {}
    for session_id in SESSIONS:
        row = per_mouse[session_id]
        left = row["stat"]["early_relative_performance"]
        right = row["run"]["early_relative_performance"]
        paired[session_id] = None if left is None or right is None else right - left

    return {"schema": "horrocks-source-decoding-summary-v1", "chance_accuracy": CHANCE,
            "accuracy_units": "fraction_correct", "time_units": "milliseconds_from_stimulus_onset",
            "within_time_centers_ms": WITHIN_CENTERS_MS,
            "cross_time_centers_ms": CROSS_CENTERS_MS,
            "cross_time_axes": ["train_time", "test_time"],
            "relative_test_window_ms": [0, 1000], "early_train_window_ms": [100, 200],
            "biological_units": 5, "permutations_per_mouse_state_endpoint": 5,
            "per_mouse": per_mouse, "group": group,
            "early_paired_run_minus_stat": paired,
            "qualification": "software_metric_reduction_only"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--input-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    with args.input.open("rb") as stream:
        raw = stream.read(INPUT_CAP + 1)
    require(0 < len(raw) <= INPUT_CAP, "input exceeds 4 MiB limit or is empty")
    require(hashlib.sha256(raw).hexdigest() == args.input_sha256, "input digest mismatch")
    result = summarize(strict_json(raw))
    result["input_sha256"] = args.input_sha256
    output = (json.dumps(result, allow_nan=False, separators=(",", ":")) + "\n").encode()
    with args.output.open("xb") as stream:
        stream.write(output)
    print(json.dumps({"bytes": len(output), "sha256": hashlib.sha256(output).hexdigest(),
                      "qualification": result["qualification"]}))


if __name__ == "__main__":
    main()
