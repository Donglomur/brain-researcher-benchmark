"""Original seven-bin time endpoint; no model fitting or source-target loading.

The operator owns the independent source roster and trial-LOO provenance. This
module computes the original endpoint from predictions, not from reported scores.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

ANIMALS = ("CD217", "CD218", "CD219", "CD220", "CD221", "CD242",
           "CD243", "CD244", "CD245", "CD246", "CD247")
DAYS = ("standard_minus2", "standard_minus1", "reversal1", "reversal2")
CUES = ("short", "long")
CONTROLS = ("real", "shuffled")
CONDITIONS = (11, 12, 21, 22, 511, 512, 521, 522)
SOURCE_SHA256 = "2ddee31087cd4ee4d6b133e02e05432a27d5fa5ee5beb81915fae65416b69f61"
MAX_JSON_BYTES = 8 * 1024 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def fields(value, names, context):
    require(type(value) is dict and set(value) == set(names),
            f"{context}: exact fields {sorted(names)} required")


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode()).hexdigest()


def validate_roster(roster):
    """Validate complete source metadata; does not authenticate its acquisition."""
    fields(roster, ("schema", "input_sha256", "sessions"), "roster")
    require(roster["schema"] == "h_original_time_roster_v1", "Wrong roster schema")
    require(roster["input_sha256"] == SOURCE_SHA256,
            "Original processed input required; alternate preprocessing is a separate endpoint")
    require(type(roster["sessions"]) is list and len(roster["sessions"]) == 44,
            "Exactly 44 original imaging sessions required")
    result = {}
    for session in roster["sessions"]:
        fields(session, ("animal", "day", "condition_codes", "recorded_delay_seconds"), "session")
        animal, day = session["animal"], session["day"]
        require(type(animal) is str and animal in ANIMALS and
                type(day) is str and day in DAYS, "Unknown original animal/day")
        key = animal, day
        require(key not in result, "Duplicate original session")
        codes = session["condition_codes"]
        require(type(codes) is list and len(codes) == 140 and
                all(type(code) is int and code in CONDITIONS for code in codes),
                "Exactly 140 source-ordered trial condition codes required")
        require(not day.startswith("standard") or all(code < 100 for code in codes),
                "Reversal condition on standard day")
        delays = session["recorded_delay_seconds"]
        require(type(delays) is list and len(delays) == 140 and
                all(type(delay) in (int, float) and math.isfinite(delay) for delay in delays),
                "Exactly 140 finite recorded source delays in seconds required")
        # TimeDecoding.m:65-66 uses beh(:,1)<100 AND beh(:,3)==2.5/5.
        # Source preprocessing copies session delay1/delay2 values; trial codes
        # alone do not establish their values. Preserve exact equality, not a
        # tolerance or an inferred short/long delay from the odor code.
        result[key] = {
            "short": tuple(i for i, (code, delay) in enumerate(zip(codes, delays)) if code < 100 and delay == 2.5),
            "long": tuple(i for i, (code, delay) in enumerate(zip(codes, delays)) if code < 100 and delay == 5),
        }
    require(set(result) == {(animal, day) for animal in ANIMALS for day in DAYS},
            "Complete original animal/day cohort required")
    return result


def panel_keys():
    return [(animal, day, cue, control) for animal in ANIMALS for day in DAYS
            for cue in CUES for control in CONTROLS]


def score_panel(trial_indices, records):
    """Pool every trial's seven bins before Pearson correlation.

    Confusion rows are predicted bins; columns are true bins. Each column has
    one prediction per trial, so its normalization denominator is trial count.
    A missing/failed trial leaves the complete panel unscored, never narrowed.
    """
    require(type(trial_indices) in (list, tuple) and
            all(type(i) is int and 0 <= i < 140 for i in trial_indices) and
            len(set(trial_indices)) == len(trial_indices), "Unique source trial indices required")
    require(type(records) is list, "Trial records must be a list")
    expected, received = set(trial_indices), {}
    for record in records:
        require(type(record) is dict, "Trial record must be an object")
        status = record.get("status")
        require(status in ("finite", "failed", "unstarted"), "Unknown trial disposition")
        fields(record, ("trial_index", "status", "predicted_bins") if status == "finite"
               else ("trial_index", "status", "reason"), "trial")
        trial = record["trial_index"]
        require(type(trial) is int and trial in expected, "Prediction outside standard cue support")
        require(trial not in received, "Duplicate held-out trial")
        if status == "finite":
            bins = record["predicted_bins"]
            require(type(bins) is list and len(bins) == 7 and
                    all(type(value) is int and 1 <= value <= 7 for value in bins),
                    "Exactly seven predicted class indices 1..7 required")
        else:
            require(type(record["reason"]) is str and bool(record["reason"].strip()),
                    "Failure/unstarted reason required")
        received[trial] = record
    failures = []
    for trial in trial_indices:
        record = received.get(trial)
        if record is None:
            failures.append({"trial_index": trial, "status": "unstarted", "reason": "Missing trial prediction"})
        elif record["status"] != "finite":
            failures.append(dict(record))
    result = {"trial_count": len(trial_indices), "observation_count": 7 * len(trial_indices),
              "received_trial_count": len(received), "failures": failures,
              "pearson_r": None, "confusion_predicted_by_actual": None}
    if failures:
        return {**result, "status": "incomplete", "reason": "Complete trial support required"}
    if not trial_indices:
        return {**result, "status": "source_undefined", "reason": "No standard trials for cue"}
    counts = [[0] * 7 for _ in range(7)]
    sx = sy = sxx = syy = sxy = 0
    for trial in trial_indices:
        for actual, predicted in enumerate(received[trial]["predicted_bins"], start=1):
            counts[predicted - 1][actual - 1] += 1
            sx += actual
            sy += predicted
            sxx += actual * actual
            syy += predicted * predicted
            sxy += actual * predicted
    n = 7 * len(trial_indices)
    vx, vy = n * sxx - sx * sx, n * syy - sy * sy
    result["confusion_predicted_by_actual"] = [[v / len(trial_indices) for v in row] for row in counts]
    if vx == 0 or vy == 0:
        return {**result, "status": "source_undefined", "reason": "Zero variance in time-bin predictions"}
    result["pearson_r"] = (n * sxy - sx * sy) / math.sqrt(vx * vy)
    return {**result, "status": "finite", "reason": None}


def score_run(roster, document):
    sessions = validate_roster(roster)
    fields(document, ("schema", "roster_sha256", "panels"), "prediction document")
    require(document["schema"] == "h_original_time_predictions_v1", "Wrong prediction schema")
    require(document["roster_sha256"] == canonical_hash(roster), "Independent roster identity mismatch")
    require(type(document["panels"]) is list, "Panels must be a list")
    expected = set(panel_keys())
    received = {}
    for panel in document["panels"]:
        fields(panel, ("animal", "day", "cue", "control", "trials"), "panel")
        require(all(type(panel[k]) is str for k in ("animal", "day", "cue", "control")),
                "Panel identities must be strings")
        key = tuple(panel[k] for k in ("animal", "day", "cue", "control"))
        require(key in expected and key not in received, "Unknown or duplicate panel")
        received[key] = panel["trials"]
    output = []
    for key in panel_keys():
        animal, day, cue, control = key
        score = score_panel(sessions[(animal, day)][cue], received.get(key, []))
        output.append({"animal": animal, "day": day, "cue": cue, "control": control, **score})
    return {"schema": "h_original_time_scores_v1", "roster_sha256": canonical_hash(roster),
            "panels": output, "expected_panel_count": 176,
            "finite_panel_count": sum(row["status"] == "finite" for row in output),
            "complete_prediction_support": all(row["status"] != "incomplete" for row in output)}


def compare(roster, author, candidate):
    """Keep original panels separate; no inferred headline metric or win rule."""
    left, right = score_run(roster, author), score_run(roster, candidate)
    pairs = {}
    for a, b in zip(left["panels"], right["panels"]):
        key = tuple(a[k] for k in ("animal", "day", "cue", "control"))
        pairs[key] = b["pearson_r"] - a["pearson_r"] if (
            a["status"] == b["status"] == "finite") else None
    summaries = []
    for day in DAYS:
        for cue in CUES:
            for control in CONTROLS:
                values = [pairs[(animal, day, cue, control)] for animal in ANIMALS]
                mean = math.fsum(values) / 11 if all(x is not None for x in values) else None
                sem = math.sqrt(math.fsum((x - mean) ** 2 for x in values) / 10 / 11) if mean is not None else None
                summaries.append({"day": day, "cue": cue, "control": control,
                                  "animals": list(ANIMALS), "paired_animal_deltas": values,
                                  "equal_animal_mean_delta": mean, "descriptive_sem": sem,
                                  "expected_animals": 11, "finite_pairs": sum(x is not None for x in values)})
    return {"schema": "h_original_time_comparison_v1", "author": left, "candidate": right,
            "separate_panel_deltas": summaries,
            "qualification": "Numerical endpoint component only; source joins, trial-LOO execution, native baseline and companion analyses require independent qualification",
            "superiority_test": None, "paper_win": None,
            "aggregation": "No averaging across cues/days; paired mice within each original day/cue/control panel"}


def read_json(path):
    def pairs(items):
        output = {}
        for key, value in items:
            require(key not in output, "Duplicate JSON key")
            output[key] = value
        return output

    def constant(value):
        raise ValueError(f"Nonfinite JSON constant: {value}")

    with Path(path).open("rb") as handle:
        raw = handle.read(MAX_JSON_BYTES + 1)
    require(len(raw) <= MAX_JSON_BYTES, "JSON input exceeds 8 MiB")
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("roster", "author", "candidate", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    result = compare(read_json(args.roster), read_json(args.author), read_json(args.candidate))
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write("\n")


if __name__ == "__main__":
    main()
