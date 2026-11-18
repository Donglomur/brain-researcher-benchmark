"""Operator-side audit of one declared Figure 6 empirical decoding curve.

This module does not recover or authenticate the empirical cohort, original
splits, author classifier, greedy selection, or paper accuracy. See README.md.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from collections.abc import Iterable

TASK_ID = "PAPER-paper-signal-add-001"
SCHEMA = "pac-figure6-curve-support/v1"
REPEATS = 500
HEX = re.compile(r"[0-9a-f]{64}\Z")
TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")


class AuditError(ValueError):
    """An operand differs from the declared, operator-frozen support."""


def _require(ok, message):
    if not ok:
        raise AuditError(message)


def _keys(value, expected, where):
    _require(type(value) is dict and set(value) == set(expected),
             f"{where}: unexpected or missing fields")


def _token(value, where):
    _require(type(value) is str and TOKEN.fullmatch(value) is not None,
             f"{where}: bounded nonempty identifier required")
    return value


def _digest(value, where):
    _require(type(value) is str and HEX.fullmatch(value) is not None,
             f"{where}: lowercase SHA-256 required")
    return value


def canonical_sha256(document):
    """Identity of JSON content, not scientific authentication or secrecy."""
    try:
        encoded = json.dumps(document, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=True, allow_nan=False).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise AuditError("document is not finite JSON") from exc
    return hashlib.sha256(encoded).hexdigest()


def _rows(rows, categories, where):
    _require(type(rows) is list and 1 <= len(rows) <= 10000,
             f"{where}: nonempty bounded observation list required")
    parsed = {}
    for row in rows:
        _keys(row, ("trial", "category"), where)
        trial = _token(row["trial"], where + ".trial")
        category = row["category"]
        _require(type(category) is str and category in categories,
                 f"{where}: category must be one of the five declared labels")
        _require(trial not in parsed, f"{where}: duplicate trial")
        parsed[trial] = category
    return parsed


def _validate_support(manifest, expected_manifest_sha256):
    _digest(expected_manifest_sha256, "expected_manifest_sha256")
    _require(canonical_sha256(manifest) == expected_manifest_sha256,
             "manifest differs from operator-frozen identity")
    _keys(manifest, ("schema", "task_id", "patient", "session", "region",
                     "noise_condition", "ablation", "removal_draw",
                     "categories", "unit_ids", "ensemble_by_step",
                     "source_bindings", "repetitions"), "manifest")
    _require(manifest["schema"] == SCHEMA and manifest["task_id"] == TASK_ID,
             "wrong task or support schema")
    _token(manifest["patient"], "patient")
    _token(manifest["session"], "session")
    _require(manifest["region"] == "hippocampus", "wrong selected brain region")
    _require(manifest["noise_condition"] in ("intact", "category_shuffled"),
             "wrong noise condition")
    _require(manifest["ablation"] in ("all_units", "pac_removed", "nonpac_removed"),
             "unknown ablation")
    draw = manifest["removal_draw"]
    _require(type(draw) is int, "removal draw must be an integer, not bool")
    if manifest["ablation"] == "nonpac_removed":
        _require(1 <= draw <= 500, "non-PAC removal selection must be in 1..500")
    else:
        _require(draw == 0, "non-random ablation must have removal_draw=0")
    categories = manifest["categories"]
    _require(type(categories) is list and len(categories) == 5,
             "exactly five category identifiers required")
    for category in categories:
        _token(category, "category")
    _require(len(set(categories)) == 5, "category identifiers must be unique")
    units = manifest["unit_ids"]
    _require(type(units) is list and 1 <= len(units) <= 4096,
             "bounded nonempty unit roster required")
    for unit in units:
        _token(unit, "unit")
    _require(len(set(units)) == len(units), "duplicate source unit")
    ensembles = manifest["ensemble_by_step"]
    _require(type(ensembles) is list and len(ensembles) == len(units),
             "one ensemble for every size through all declared units required")
    previous = set()
    for step, ensemble in enumerate(ensembles, start=1):
        _require(type(ensemble) is list and len(ensemble) == step,
                 "ensemble size must equal its one-based step")
        for unit in ensemble:
            _token(unit, "ensemble unit")
        current = set(ensemble)
        _require(len(current) == step and current <= set(units),
                 "ensemble has duplicate or undeclared units")
        _require(previous < current, "greedy trace must retain prior units")
        previous = current
    bindings = manifest["source_bindings"]
    _keys(bindings, ("observations_sha256", "correct_load1_selection_sha256",
                     "trial_partition_policy_sha256", "ensemble_producer_sha256",
                     "condition_transform_sha256"), "source_bindings")
    for key, value in bindings.items():
        _digest(value, key)
    repetitions = manifest["repetitions"]
    _require(type(repetitions) is list and len(repetitions) == REPEATS,
             "exactly 500 decoding repetitions required")
    tests = {}
    source_labels = {}
    partition_counts = []
    for rep in repetitions:
        _keys(rep, ("repeat", "training", "testing"), "repetition")
        index = rep["repeat"]
        _require(type(index) is int and 1 <= index <= REPEATS and index not in tests,
                 "repeat IDs must be exactly 1..500 without duplicates")
        training = _rows(rep["training"], categories, "training")
        testing = _rows(rep["testing"], categories, "testing")
        _require(not training.keys() & testing.keys(), "train/test trial overlap")
        for trial, category in (*training.items(), *testing.items()):
            _require(trial not in source_labels or source_labels[trial] == category,
                     "source trial category changed across repetitions")
            source_labels[trial] = category
        pooled = Counter(training.values()) + Counter(testing.values())
        _require(set(pooled) == set(categories) and len(set(pooled.values())) == 1,
                 "source-selected five categories must have equal pooled support")
        tests[index] = testing
        partition_counts.append({"repeat": index, "training": len(training),
                                 "testing": len(testing)})
    _require(set(tests) == set(range(1, REPEATS + 1)), "incomplete repeat roster")
    # Partition rounding and train-only preprocessing are deliberately not guessed.
    return tests, partition_counts


def audit_curve(manifest, predictions: Iterable[dict], *, expected_manifest_sha256):
    """Recompute one complete frozen curve from trial-level predictions.

    Prediction order may vary. Each record is {repeat, step, trial, category}.
    All operator-specified held trials at all 500 repeats and ensemble sizes
    must occur exactly once. No fitting or selection takes place here.
    """
    tests, partition_counts = _validate_support(manifest, expected_manifest_sha256)
    n_steps = len(manifest["unit_ids"])
    correct = {(rep, step): 0 for rep in range(1, REPEATS + 1)
               for step in range(1, n_steps + 1)}
    seen = set()
    for record in predictions:
        _keys(record, ("repeat", "step", "trial", "category"), "prediction")
        rep, step, trial, predicted = (record[x] for x in ("repeat", "step", "trial", "category"))
        _require(type(rep) is int and rep in tests, "prediction has undeclared repeat")
        _require(type(step) is int and 1 <= step <= n_steps,
                 "prediction has undeclared ensemble step")
        _token(trial, "prediction trial")
        _require(trial in tests[rep], "prediction trial is not held out in this repeat")
        _require(type(predicted) is str and predicted in manifest["categories"],
                 "predicted category must be a declared label")
        key = (rep, step, trial)
        _require(key not in seen, "duplicate prediction coordinate")
        seen.add(key)
        correct[(rep, step)] += int(predicted == tests[rep][trial])
    expected = n_steps * sum(len(rows) for rows in tests.values())
    _require(len(seen) == expected, "incomplete held-trial/repeat/ensemble coverage")
    per_step = []
    for step in range(1, n_steps + 1):
        repetitions = [{"repeat": rep, "correct": correct[(rep, step)],
                        "total": len(tests[rep]),
                        "accuracy": correct[(rep, step)] / len(tests[rep])}
                       for rep in range(1, REPEATS + 1)]
        mean = math.fsum(row["accuracy"] for row in repetitions) / REPEATS
        per_step.append({"step": step, "unit_ids": list(manifest["ensemble_by_step"][step - 1]),
                         "repetitions": repetitions, "mean_repeat_accuracy": mean})
    maximum = max(row["mean_repeat_accuracy"] for row in per_step)
    return {
        "schema": "pac-figure6-curve-audit/v1", "task_id": TASK_ID,
        "manifest_sha256": expected_manifest_sha256,
        "session": manifest["session"], "patient": manifest["patient"],
        "noise_condition": manifest["noise_condition"],
        "ablation": manifest["ablation"], "removal_draw": manifest["removal_draw"],
        "prediction_records": expected, "partition_counts": sorted(partition_counts, key=lambda x: x["repeat"]),
        "curve": per_step,
        "maximum_mean_repeat_accuracy": maximum,
        "maximizing_steps_without_tie_resolution": [row["step"] for row in per_step
                                                   if row["mean_repeat_accuracy"] == maximum],
        "scientific_qualification": "unresolved",
        "source_authentication_established": False, "paper_win": None,
    }


def compare_on_frozen_curve(manifest, author_predictions, candidate_predictions,
                            *, expected_manifest_sha256):
    """Return complete paired numeric differences; never an improvement verdict."""
    author = audit_curve(manifest, author_predictions, expected_manifest_sha256=expected_manifest_sha256)
    candidate = audit_curve(manifest, candidate_predictions, expected_manifest_sha256=expected_manifest_sha256)
    deltas = []
    for a, c in zip(author["curve"], candidate["curve"], strict=True):
        deltas.append({"step": a["step"],
                       "candidate_minus_author_mean_repeat_accuracy": c["mean_repeat_accuracy"] - a["mean_repeat_accuracy"],
                       "paired_repeat_differences": [cr["accuracy"] - ar["accuracy"]
                           for ar, cr in zip(a["repetitions"], c["repetitions"], strict=True)]})
    return {"schema": "pac-figure6-paired-curve-audit/v1", "task_id": TASK_ID,
            "manifest_sha256": expected_manifest_sha256,
            "author": author, "candidate": candidate, "differences_by_step": deltas,
            "paper_win": None, "current_sota": "not_assessed",
            "reason": "One operator-declared frozen curve is not the complete Figure 6 panel or a qualified comparator."}
