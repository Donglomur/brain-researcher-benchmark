"""Score complete Figure 2h held-event predictions; never fit or select a model."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import statistics

TASK = "PAPER-SCOPE-20261114-REM-DYNAMICS"
PCS = tuple(range(1, 23))
REPEATS = tuple(range(25))
ARTICLE_SHA256 = "83792709d1157ba7527a4b67e95c93c98d94932e3396d8a0c44c6f9587cfdc18"
SHA = re.compile(r"[a-f0-9]{64}\Z")
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")
MAX_BYTES = 32 * 1024 * 1024


class Invalid(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise Invalid(message)


def fields(value, keys, where):
    require(type(value) is dict and set(value) == set(keys), where + ": exact fields required")


def identifier(value):
    require(type(value) is str and ID.fullmatch(value), "invalid identifier")
    return value


def digest(value):
    require(type(value) is str and SHA.fullmatch(value), "invalid SHA-256")
    return value


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def time_grid(value):
    """No inferred bin count or endpoint convention; owner supplies source coordinates."""
    require(type(value) is list and 1 <= len(value) <= 64, "explicit bounded source time grid required")
    require(all(type(t) in (int, float) and -150 <= t <= 0 and math.isfinite(t) for t in value),
            "finite source coordinates within preceding 150 seconds required")
    require(all(b - a == 10 for a, b in zip(value, value[1:])),
            "ordered distinct source coordinates at 10-second spacing required")
    return tuple(value)


def owner_index(owner):
    fields(owner, ("schema", "task_id", "provenance", "mice", "events", "time_seconds", "rem_train_count", "splits"), "owner")
    require(owner["schema"] == "rem-fig2h-owner-v1" and owner["task_id"] == TASK, "owner identity")
    provenance = owner["provenance"]
    fields(provenance, ("article_sha256", "cohort_join_sha256", "preprocessing_sha256", "split_source_sha256", "time_grid_source_sha256", "time_grid_source_locator"), "provenance")
    for key, value in provenance.items():
        if key != "time_grid_source_locator":
            digest(value)
    locator = provenance["time_grid_source_locator"]
    require(type(locator) is str and 0 < len(locator.strip()) <= 512, "exact source numerical grid locator required")
    require(provenance["article_sha256"] == ARTICLE_SHA256, "article identity")
    time_grid(owner["time_seconds"])
    mice = owner["mice"]
    require(type(mice) is list and len(mice) == 6, "six source mice required")
    require(len(set(identifier(m) for m in mice)) == 6, "unique mice required")
    require(type(owner["events"]) is list and len(owner["events"]) == 424, "47 REM plus 377 Wake events required")
    events = {}
    for event in owner["events"]:
        fields(event, ("event_id", "mouse_id", "label"), "event")
        eid = identifier(event["event_id"])
        require(eid not in events and type(event["mouse_id"]) is str and event["mouse_id"] in mice, "duplicate event or unknown mouse")
        require(type(event["label"]) is int and event["label"] in (0, 1), "label must be 1 REM or 0 Wake")
        events[eid] = event
    require(Counter(e["label"] for e in events.values()) == {1: 47, 0: 377}, "47 REM and 377 Wake required")
    require({e["mouse_id"] for e in events.values()} == set(mice), "every mouse must contribute")
    n_train = owner["rem_train_count"]
    require(type(n_train) is int and n_train in (32, 33), "explicit original 70% rounding required (32 or 33 REM)")
    splits = owner["splits"]
    require(type(splits) is list and len(splits) == 22 * 25, "22 by 25 split cells required; time bins reuse each split")
    by_key = {}
    all_rem = {eid for eid, e in events.items() if e["label"] == 1}
    for split in splits:
        fields(split, ("pc", "repeat", "train_ids", "test_ids"), "split")
        pc, rep = split["pc"], split["repeat"]
        require(type(pc) is int and pc in PCS and type(rep) is int and rep in REPEATS, "split index")
        require((pc, rep) not in by_key, "duplicate split")
        sets = {}
        for field, n_class in (("train_ids", n_train), ("test_ids", 47 - n_train)):
            ids = split[field]
            require(type(ids) is list and len(ids) == 2 * n_class, "balanced split size")
            require(all(type(eid) is str and eid in events for eid in ids) and len(set(ids)) == len(ids), "unknown or duplicate split event")
            require(Counter(events[eid]["label"] for eid in ids) == {0: n_class, 1: n_class}, "split must have equal REM and Wake counts")
            sets[field] = set(ids)
        require(not sets["train_ids"] & sets["test_ids"], "train/test event overlap")
        selected_rem = {eid for eid in sets["train_ids"] | sets["test_ids"] if events[eid]["label"] == 1}
        require(selected_rem == all_rem, "all REM events must enter train or test in every split")
        by_key[pc, rep] = split
    return events, by_key


def public_plan(owner):
    """Structural plan only. Actual participant delivery and isolation are separate."""
    owner_index(owner)
    return {"task_id": TASK, "time_seconds": owner["time_seconds"], "mice": owner["mice"],
            "provenance": owner["provenance"], "rem_train_count": owner["rem_train_count"],
            "events": [{"event_id": e["event_id"], "mouse_id": e["mouse_id"]} for e in owner["events"]],
            "splits": owner["splits"]}


def prediction_index(predictions, plan_hash, splits, times):
    fields(predictions, ("schema", "task_id", "case_plan_sha256", "cells"), "predictions")
    require(predictions["schema"] == "rem-fig2h-predictions-v1" and predictions["task_id"] == TASK, "prediction identity")
    require(predictions["case_plan_sha256"] == plan_hash, "case-plan mismatch")
    rows = predictions["cells"]
    require(type(rows) is list and len(rows) == 22 * 25 * len(times), "complete owner-bound PC/time/repeat family required")
    index = {}
    for row in rows:
        fields(row, ("pc", "repeat", "time_seconds", "test_ids", "predicted_labels"), "prediction cell")
        pc, rep, t = row["pc"], row["repeat"], row["time_seconds"]
        require(type(pc) is int and pc in PCS and type(rep) is int and rep in REPEATS and type(t) in (int, float) and t in times, "prediction indices")
        key = (pc, rep, t)
        require(key not in index, "duplicate prediction cell")
        ids, labels = row["test_ids"], row["predicted_labels"]
        required = splits[pc, rep]["test_ids"]
        require(type(ids) is list and len(ids) == len(required) and all(type(eid) is str for eid in ids) and set(ids) == set(required), "exact held-event identities required")
        require(type(labels) is list and len(labels) == len(ids) and all(type(y) is int and y in (0, 1) for y in labels), "one binary prediction per held event required")
        index[key] = dict(zip(ids, labels))
    return index


def _counts(ids, events, predictions, baseline=None):
    result = {"n_test": len(ids), "tp": 0, "tn": 0, "fp": 0, "fn": 0}
    if baseline is not None:
        result.update(baseline_correct=0, candidate_only_correct=0, baseline_only_correct=0)
    for eid in ids:
        y, prediction = events[eid]["label"], predictions[eid]
        result[{(1, 1): "tp", (0, 0): "tn", (0, 1): "fp", (1, 0): "fn"}[y, prediction]] += 1
        if baseline is not None:
            result["baseline_correct"] += int(baseline[eid] == y)
            result["candidate_only_correct"] += int(prediction == y and baseline[eid] != y)
            result["baseline_only_correct"] += int(prediction != y and baseline[eid] == y)
    correct = result["tp"] + result["tn"]
    result["accuracy"] = correct / len(ids) if ids else None
    if baseline is not None:
        result["baseline_accuracy"] = result["baseline_correct"] / len(ids) if ids else None
        result["paired_accuracy_delta"] = (correct - result["baseline_correct"]) / len(ids) if ids else None
    return result


def score(owner, candidate, baseline=None):
    events, splits = owner_index(owner)
    times = time_grid(owner["time_seconds"])
    plan_hash = canonical_hash(public_plan(owner))
    candidate_index = prediction_index(candidate, plan_hash, splits, times)
    baseline_index = prediction_index(baseline, plan_hash, splits, times) if baseline is not None else None
    cells, curves = [], []
    for pc in PCS:
        for t in times:
            accuracies, deltas = [], []
            for rep in REPEATS:
                key = (pc, rep, t)
                ids = splits[pc, rep]["test_ids"]
                pred = candidate_index[key]
                base = baseline_index[key] if baseline_index is not None else None
                cell = {"pc": pc, "time_seconds": t, "repeat": rep, **_counts(ids, events, pred, base)}
                cell["mice"] = [{"mouse_id": m, **_counts([eid for eid in ids if events[eid]["mouse_id"] == m], events, pred, base)} for m in owner["mice"]]
                cells.append(cell)
                accuracies.append(cell["accuracy"])
                if base is not None:
                    deltas.append(cell["paired_accuracy_delta"])
            curve = {"pc": pc, "time_seconds": t, "accuracies": accuracies,
                     "mean_accuracy": statistics.mean(accuracies),
                     "resampling_sem": statistics.stdev(accuracies) / math.sqrt(len(accuracies))}
            if baseline_index is not None:
                curve.update(paired_accuracy_deltas=deltas, mean_paired_accuracy_delta=statistics.mean(deltas))
            curves.append(curve)
    usage = Counter(eid for s in splits.values() for eid in s["test_ids"])
    support = [{"event_id": eid, "mouse_id": e["mouse_id"], "held_split_uses": usage[eid]} for eid, e in events.items()]
    return {"schema": "rem-fig2h-score-v1", "task_id": TASK, "case_plan_sha256": plan_hash,
            "scope": "Figure2h accuracy component only; Figure5e is required separately for the registered family",
            "mice": 6, "events": 424, "time_seconds": list(times), "fit_cells": len(cells), "curves": curves, "cells": cells,
            "event_support": support, "comparison_present": baseline_index is not None,
            "author_parity_established": False, "paper_reproduction_established": False, "paper_improvement_established": False,
            "interpretation": "Pooled held-event accuracy on the explicitly supplied source-bound time grid. Completeness is checked against that declared grid, not authenticated original numerical support. SEM describes 25 reused-event resamples, not uncertainty over six mice. Time coordinates do not specify neural sample support. Source grid, splits, preprocessing, original outputs and both protocols must be independently qualified for reproduction or improvement."}


def _unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def _nonfinite(value):
    raise Invalid("nonfinite JSON constant")


def load(path):
    with Path(path).open("rb") as stream:
        body = stream.read(MAX_BYTES + 1)
    require(0 < len(body) <= MAX_BYTES, "JSON file byte limit")
    try:
        value = json.loads(body, object_pairs_hook=_unique, parse_constant=_nonfinite)
    except (ValueError, UnicodeError, RecursionError) as error:
        raise Invalid("invalid bounded JSON") from error
    return value, hashlib.sha256(body).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("owner")
    parser.add_argument("candidate")
    parser.add_argument("--baseline", help="Frozen comparator predictions on the identical event plan")
    args = parser.parse_args()
    try:
        owner, owner_hash = load(args.owner)
        candidate, candidate_hash = load(args.candidate)
        baseline, baseline_hash = load(args.baseline) if args.baseline else (None, None)
        report = score(owner, candidate, baseline)
        report.update(owner_sha256=owner_hash, candidate_sha256=candidate_hash, baseline_sha256=baseline_hash)
        print(json.dumps(report, allow_nan=False, sort_keys=True))
        return 0
    except (Invalid, OSError, RecursionError) as error:
        print(json.dumps({"schema": "rem-fig2h-refusal-v1", "error": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
