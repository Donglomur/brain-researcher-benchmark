#!/usr/bin/env python3
"""Recompute MINT CA1 decoder fold information from explicitly supplied support.

Independent arithmetic component, not an original-paper scorer or native rerun.
No data acquisition, model fitting, binning, partitioning or RNG occurs here.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import statistics

TASK_ID = "PAPER-paper-method-012"
RUNS = {(kernel, condition, repeat)
        for kernel in ("linear", "RBF")
        for condition, repeats in (("real", (0,)), ("conditionally_shuffled", (1, 2)))
        for repeat in repeats}
KEYS = ("session_id", "kernel", "condition", "conditional_shuffle", "fold_id")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def _ids(values, name):
    if (not isinstance(values, list) or not values or
            any(not isinstance(v, str) or not v.strip() for v in values)):
        raise ValueError(f"{name} requires nonempty string IDs")
    if len(set(values)) != len(values):
        raise ValueError(f"{name} contains duplicate IDs")
    return values


def _labels(values, label_order, name):
    if (not isinstance(values, list) or not values or
            any(type(v) is not int or v not in label_order for v in values)):
        raise ValueError(f"{name} must contain only the declared integer class labels")


def _permutation(order, n):
    if (not isinstance(order, list) or len(order) != n or
            any(type(i) is not int for i in order) or sorted(order) != list(range(n))):
        raise ValueError("Each null order must be a complete zero-based fold permutation")


def confusion_counts(targets, predictions, label_order):
    """Rows are true targets; columns are predicted labels, including empty classes."""
    _labels(targets, label_order, "targets")
    _labels(predictions, label_order, "predictions")
    if len(targets) != len(predictions):
        raise ValueError("Targets and predictions must align")
    counts = Counter(zip(targets, predictions))
    return [[counts[t, p] for p in label_order] for t in label_order]


def information(counts):
    """Empirical discrete MI in bits; occupied cells only, no pseudocounts."""
    rows = [sum(row) for row in counts]
    columns = [sum(column) for column in zip(*counts)]
    n = sum(rows)
    return math.fsum(c / n * math.log2(c * n / (rows[i] * columns[j]))
                     for i, row in enumerate(counts) for j, c in enumerate(row) if c)


def score_fold(targets, predictions, label_order, null_orders):
    """Replay all 30 paired permutation maps; retain negative corrected MI."""
    observed = confusion_counts(targets, predictions, label_order)
    if not isinstance(null_orders, list) or len(null_orders) != 30:
        raise ValueError("CA1 shuffSub requires exactly 30 MI null permutations")
    null_counts = []
    for orders in null_orders:
        if not isinstance(orders, dict) or set(orders) != {"prediction", "target"}:
            raise ValueError("Each null needs separate prediction and target orders")
        _permutation(orders["prediction"], len(targets))
        _permutation(orders["target"], len(targets))
        null_counts.append(confusion_counts(
            [targets[i] for i in orders["target"]],
            [predictions[i] for i in orders["prediction"]], label_order))
    plugin = information(observed)
    null_bits = [information(counts) for counts in null_counts]
    return {"confusion_counts": observed, "plugin_bits": plugin,
            "null_confusion_counts": null_counts, "null_plugin_bits": null_bits,
            "shuffsub_bits": plugin - statistics.fmean(null_bits)}


def _header(packet):
    if not isinstance(packet, dict) or packet.get("schema_version") != 1 or packet.get("task_id") != TASK_ID:
        raise ValueError("Wrong schema or task identity")


def validate_support(support):
    """Validate declared support, without authenticating its historical provenance."""
    _header(support)
    if support.get("data_kind") not in {"generated_engineering_control", "operator_prepared_unqualified"}:
        raise ValueError("Support must explicitly remain generated or unqualified")
    fold_count = support.get("outer_fold_count")
    if type(fold_count) is not int or fold_count not in (2, 5):
        raise ValueError("Declare two pinned-driver folds or five paper folds; their conflict remains unresolved")
    order = support.get("label_order")
    if (not isinstance(order, list) or len(order) != 12 or
            any(type(v) is not int for v in order) or len(set(order)) != 12):
        raise ValueError("Explicit order of twelve distinct integer spatial classes is required")
    sessions = support.get("sessions")
    if not isinstance(sessions, list) or len(sessions) != 11 or any(not isinstance(s, dict) for s in sessions):
        raise ValueError("All eleven declared sessions are required")
    _ids([s.get("session_id") for s in sessions], "sessions")
    animals = [s.get("animal_id") for s in sessions]
    for animal in animals:
        _ids([animal], "animal")
    if len(set(animals)) != 7:
        raise ValueError("The complete seven-animal declaration is required")
    expected = {}
    for session in sessions:
        sid = session["session_id"]
        samples = _ids(session.get("sample_ids"), "session samples")
        targets = session.get("targets")
        _labels(targets, order, "targets")
        if len(targets) != len(samples):
            raise ValueError("Session targets and sample IDs must align")
        by_id = dict(zip(samples, targets))
        runs = session.get("runs")
        if not isinstance(runs, list) or len(runs) != len(RUNS):
            raise ValueError("Both kernels and real/two conditional-shuffle runs are mandatory")
        seen_runs = set()
        for run in runs:
            if not isinstance(run, dict):
                raise ValueError("Each run must be an object")
            run_key = (run.get("kernel"), run.get("condition"), run.get("conditional_shuffle"))
            if type(run_key[2]) is not int or run_key not in RUNS or run_key in seen_runs:
                raise ValueError("Unknown or duplicate decoder run")
            seen_runs.add(run_key)
            folds = run.get("folds")
            if not isinstance(folds, list) or len(folds) != fold_count or any(not isinstance(f, dict) for f in folds):
                raise ValueError("Each run requires its complete declared outer folds")
            _ids([f.get("fold_id") for f in folds], "folds")
            used = []
            for fold in folds:
                ids = _ids(fold.get("sample_ids"), "fold samples")
                if not set(ids).issubset(by_id):
                    raise ValueError("Fold contains a sample outside its session")
                used.extend(ids)
                nulls = fold.get("null_orders")
                # Validate replay maps before any submitted prediction is scored.
                if not isinstance(nulls, list) or len(nulls) != 30:
                    raise ValueError("Each fold requires thirty MI null maps")
                for null in nulls:
                    if not isinstance(null, dict) or set(null) != {"prediction", "target"}:
                        raise ValueError("Each MI null needs both input permutations")
                    for permutation in null.values():
                        _permutation(permutation, len(ids))
                key = (sid, *run_key, fold["fold_id"])
                expected[key] = (session["animal_id"], ids, [by_id[i] for i in ids], nulls)
            if len(used) != len(samples) or set(used) != set(samples):
                raise ValueError("Outer folds must cover every session sample exactly once per decoder run")
    return expected


def evaluate(support, submission):
    expected = validate_support(support)
    _header(submission)
    if submission.get("support_sha256") != digest(support):
        raise ValueError("Submission is not bound to this exact operator support")
    folds = submission.get("folds")
    if not isinstance(folds, list) or len(folds) != len(expected):
        raise ValueError("Submission must cover the complete expected fold panel")
    supplied = {}
    for fold in folds:
        if not isinstance(fold, dict):
            raise ValueError("Each submitted fold must be an object")
        key = tuple(fold.get(name) for name in KEYS)
        if type(key[3]) is not int or key not in expected or key in supplied:
            raise ValueError("Unexpected or duplicate submitted fold")
        predictions = fold.get("predictions")
        if not isinstance(predictions, list) or any(not isinstance(p, dict) for p in predictions):
            raise ValueError("Predictions require sample-ID/label records")
        ids = _ids([p.get("sample_id") for p in predictions], "prediction samples")
        if set(ids) != set(expected[key][1]):
            raise ValueError("Prediction coverage differs from the protected fold")
        labels = [p.get("label") for p in predictions]
        _labels(labels, support["label_order"], "predictions")
        supplied[key] = dict(zip(ids, labels))
    rows = []
    for key, (animal, ids, targets, nulls) in expected.items():
        predictions = [supplied[key][i] for i in ids]
        rows.append({**dict(zip(KEYS, key)), "animal_id": animal, "sample_ids": ids,
                     **score_fold(targets, predictions, support["label_order"], nulls)})
    return {"schema_version": 1, "task_id": TASK_ID,
            "status": "unqualified_decoder_information_component",
            "scientific_qualification": "unknown", "native_equivalence": "unverified",
            "input_data_kind": support["data_kind"], "support_sha256": digest(support),
            "submission_sha256": digest(submission), "label_order": support["label_order"],
            "confusion_axes": ["target", "prediction"],
            "outer_fold_count": support["outer_fold_count"], "folds": rows,
            "aggregate": None,
            "remaining_gaps": ["Authentic source support, preprocessing and native permutation binding",
                               "Historical five-versus-two fold discrepancy and shuffled-field assignment",
                               "Original reduction/SEM rules, reference vectors and comparison criteria"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("support", type=Path)
    parser.add_argument("submission", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = evaluate(json.loads(args.support.read_text()), json.loads(args.submission.read_text()))
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
