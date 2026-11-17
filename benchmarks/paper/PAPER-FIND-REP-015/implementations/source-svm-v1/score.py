#!/usr/bin/env python3
"""Complete source-SVM point metrics; no fitting, split creation, or win decision."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

REGION_UNITS = {"DCN": 1006, "VTA": 22}
METRICS = ("accuracy", "sensitivity", "precision", "f1")


def _keys(value, expected, context):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ValueError(f"{context}: exact keys required")


def _binary(value):
    if type(value) is not int or value not in (0, 1):
        raise ValueError("Reward labels and decisions must be integer 0 or 1")
    return value


def _index_units(packet, region, field):
    _keys(packet, ("schema", "region", "units"), field)
    expected_schema = "cerebellar-source-test-v1" if field == "reward" else "cerebellar-decisions-v1"
    if packet["schema"] != expected_schema or packet["region"] != region:
        raise ValueError("Wrong schema or source region")
    if not isinstance(packet["units"], list):
        raise ValueError("units must be a list")
    units = {}
    for unit in packet["units"]:
        _keys(unit, ("unit_id", "trials"), "unit")
        uid = unit["unit_id"]
        if type(uid) is not int or uid in units:
            raise ValueError("Unit IDs must be distinct source integers")
        if not isinstance(unit["trials"], list) or not unit["trials"]:
            raise ValueError("Every unit must have nonempty test trials")
        trials = {}
        for trial in unit["trials"]:
            _keys(trial, ("trial_id", field), "trial")
            tid = trial["trial_id"]
            if not isinstance(tid, str) or not tid or tid in trials:
                raise ValueError("Trial IDs must be distinct nonempty strings within a unit")
            trials[tid] = _binary(trial[field])
        units[uid] = trials
    if set(units) != set(range(1, REGION_UNITS[region] + 1)):
        raise ValueError("Complete original region unit inventory required")
    return units


def _metrics(labels, decisions):
    counts = {"tp": 0, "tn": 0, "fp": 0, "fn": 0}
    for tid, label in labels.items():
        prediction = decisions[tid]
        key = "tp" if label == prediction == 1 else "tn" if label == prediction == 0 else "fp" if prediction else "fn"
        counts[key] += 1
    tp, tn, fp, fn = (counts[key] for key in ("tp", "tn", "fp", "fn"))
    def ratio(numerator, denominator):
        # The released HappyML revision and its zero-division behavior are unknown.
        return numerator / denominator if denominator else None
    values = {"accuracy": (tp + tn) / len(labels),
              "sensitivity": ratio(tp, tp + fn),
              "precision": ratio(tp, tp + fp),
              "f1": ratio(2 * tp, 2 * tp + fp + fn)}
    return {"trials": len(labels), "confusion": counts, **values}


def _mean(values):
    return None if any(value is None for value in values) else math.fsum(values) / len(values)


def score_pair(reference, candidate, author):
    """Compare two frozen decision sets on one complete, operator-owned test roster.

    Region is scored separately; no across-region or animal inference is made.
    Reference contains test outcomes and must never be provided by the candidate.
    This API checks identity/census, not scientific provenance or access custody.
    """
    if not isinstance(reference, dict) or reference.get("region") not in REGION_UNITS:
        raise ValueError("Source region must be DCN or VTA")
    region = reference["region"]
    targets = _index_units(reference, region, "reward")
    predictions = _index_units(candidate, region, "decision")
    comparator = _index_units(author, region, "decision")
    # Validate every identity before computing any partial metrics.
    for uid, trials in targets.items():
        if set(predictions[uid]) != set(trials) or set(comparator[uid]) != set(trials):
            raise ValueError(f"Unit {uid}: candidate, author, and reference test IDs must match")
    rows = []
    for uid in sorted(targets):
        candidate_metrics = _metrics(targets[uid], predictions[uid])
        author_metrics = _metrics(targets[uid], comparator[uid])
        delta = {metric: None if candidate_metrics[metric] is None or author_metrics[metric] is None
                 else candidate_metrics[metric] - author_metrics[metric] for metric in METRICS}
        rows.append({"unit_id": uid, "candidate": candidate_metrics, "author": author_metrics,
                     "improvement_delta": delta,
                     "reproduction_absolute_metric_error": {key: None if value is None else abs(value)
                                                            for key, value in delta.items()}})
    return {"schema": "cerebellar-source-paired-metrics-v1", "region": region,
            "unit_count": len(rows), "test_trial_count": sum(len(v) for v in targets.values()),
            "aggregation": "equal_unit_arithmetic_mean",
            "source_aggregation_binding": "A02_Read_decoding_outcome.m" if region == "DCN" else
                                          "companion_equal_unit_summary_not_verified_figure_binding",
            "candidate": {m: _mean([r["candidate"][m] for r in rows]) for m in METRICS},
            "author": {m: _mean([r["author"][m] for r in rows]) for m in METRICS},
            "improvement_delta": {m: _mean([r["improvement_delta"][m] for r in rows]) for m in METRICS},
            "reproduction_mean_absolute_metric_error": {
                m: _mean([r["reproduction_absolute_metric_error"][m] for r in rows]) for m in METRICS},
            "units": rows}


def _load(path):
    def unique_pairs(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("Duplicate JSON key")
            value[key] = item
        return value
    def nonfinite(value):
        raise ValueError(f"Nonfinite JSON number: {value}")
    return json.loads(Path(path).read_text(), object_pairs_hook=unique_pairs, parse_constant=nonfinite)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", required=True, help="Operator-private exact source test roster and labels")
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--author", required=True, help="Separately frozen author decisions on identical test IDs")
    parser.add_argument("--output", required=True, help="Fresh operator-private detailed report")
    args = parser.parse_args()
    result = score_pair(_load(args.reference), _load(args.candidate), _load(args.author))
    # Never overwrite an earlier report, and do not emit target-derived detail to stdout.
    with open(args.output, "x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write("\n")


if __name__ == "__main__":
    main()
