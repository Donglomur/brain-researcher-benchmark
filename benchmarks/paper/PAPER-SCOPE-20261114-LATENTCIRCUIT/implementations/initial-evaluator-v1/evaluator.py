#!/usr/bin/env python3
"""Owner-side prospective fixed-neuron scoring for the two-monkey PFC task.

This implements neither the missing native empirical adapter nor its behavior guard.
All normalization and condition-mean estimates use inner training trials only.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from collections import defaultdict
from pathlib import Path

TASK = "PAPER-SCOPE-20261114-LATENTCIRCUIT"
SCHEMA = "latentcircuit.owner.v1"
POLICY = "original-neuron-condition-balanced-train-variance-v1"
MONKEYS = ("A", "F")
ROLES = ("train", "validation", "assessment")
HOLD_REASONS = [
    "Authentic archive census, unit-denominator reconciliation and rights admission unverified.",
    "Native 150-by-10ms to 15-sample neural clock and preprocessing support join unresolved.",
    "Native empirical three-term loss, fitted intercept and continuous behavior guard unresolved.",
    "Full 200-start-per-monkey reference, equal-budget comparators and failed-start census absent.",
    "Protected execution/context isolation and actual end-to-end agent comparisons unqualified.",
    "Session hierarchy and trial independence unverified; no population inference or confidence interval.",
]


class ContractError(ValueError):
    """An input cannot be scored under the frozen prospective policy."""


def require(condition, message):
    if not condition:
        raise ContractError(message)


def exact_keys(value, keys, where):
    require(isinstance(value, dict), f"{where}: expected object")
    require(set(value) == set(keys), f"{where}: expected exactly {sorted(keys)}")


def identifier(value, where):
    require(isinstance(value, str) and value and value.strip() == value,
            f"{where}: nonempty canonical string required")
    return value


def sha(value, where):
    require(isinstance(value, str) and len(value) == 64
            and all(c in "0123456789abcdef" for c in value), f"{where}: lowercase SHA256 required")
    return value


def number(value, where):
    try:
        require(type(value) in (int, float) and math.isfinite(value), f"{where}: finite number required")
        return float(value)
    except OverflowError as exc:
        raise ContractError(f"{where}: finite number required") from exc


def vector(value, where):
    require(isinstance(value, list) and len(value) == 15, f"{where}: exactly 15 samples required")
    return [number(x, where) for x in value]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def mean(values):
    values = list(values)
    require(bool(values), "empty average")
    try:
        result = math.fsum(values) / len(values)
    except (OverflowError, ValueError) as exc:
        raise ContractError("non-finite arithmetic") from exc
    require(math.isfinite(result), "non-finite arithmetic")
    return result


def squared(value):
    try:
        result = value * value
    except OverflowError as exc:
        raise ContractError("non-finite squared error") from exc
    require(math.isfinite(result), "non-finite squared error")
    return result


def unit_key(row):
    return row["monkey"], row["unit_id"]


def trial_key(row):
    return row["monkey"], row["unit_id"], row["recording_id"], row["trial_id"]


def identity(row):
    return {k: row[k] for k in ("monkey", "unit_id", "recording_id", "trial_id", "condition_id")}


def _parse_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, f"duplicate JSON key: {key}")
            result[key] = value
        return result
    def bad_constant(value):
        raise ContractError(f"invalid JSON constant: {value}")
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=bad_constant)


def _load_json(path):
    return _parse_json(Path(path).read_bytes())


def audit(owner):
    """Validate the *declared* complete census, split and time/coordinate interface.

    Authentic source census and rights are not established by this local audit.
    Correct-trial counts determine eligibility; no candidate exclusion switch exists.
    """
    exact_keys(owner, ("schema", "task_id", "policy", "data_provenance", "time_axis",
                       "frozen_program_sha256", "units", "conditions", "trials"), "owner")
    require(owner["schema"] == SCHEMA and owner["task_id"] == TASK, "wrong task/schema")
    require(owner["policy"] == POLICY, "unknown normalization/aggregation policy")
    sha(owner["frozen_program_sha256"], "frozen program")
    prov = owner["data_provenance"]
    exact_keys(prov, ("dataset_id", "owner_census_sha256", "origin", "preprocessing_description"),
               "data provenance")
    identifier(prov["dataset_id"], "dataset_id")
    sha(prov["owner_census_sha256"], "owner census")
    identifier(prov["preprocessing_description"], "preprocessing description")
    require(prov["origin"] in ("generated_engineering_controls", "authentic_unadmitted"),
            "this package cannot confer authentic data admission")
    axis = owner["time_axis"]
    exact_keys(axis, ("sample_centers_ms", "reference_event", "alignment_policy", "native_join"),
               "time axis")
    centers = vector(axis["sample_centers_ms"], "sample centers")
    require(all(b > a for a, b in zip(centers, centers[1:])), "sample centers must increase")
    identifier(axis["reference_event"], "reference event")
    identifier(axis["alignment_policy"], "prospective alignment policy")
    require(axis["native_join"] == "unresolved", "native clock cannot be certified by this package")
    require(isinstance(owner["conditions"], list) and len(owner["conditions"]) == 72,
            "exactly all 72 conditions required")
    conditions = {}
    combinations = set()
    for condition in owner["conditions"]:
        exact_keys(condition, ("condition_id", "context", "motion_level", "color_level"), "condition")
        cid = identifier(condition["condition_id"], "condition ID")
        require(cid not in conditions, "duplicate condition ID")
        require(condition["context"] in ("motion", "color"), "unknown context")
        combo = (condition["context"], number(condition["motion_level"], "motion level"),
                 number(condition["color_level"], "color level"))
        require(combo not in combinations, "duplicate stimulus condition")
        combinations.add(combo)
        conditions[cid] = condition
    motion = {x[1] for x in combinations}
    color = {x[2] for x in combinations}
    require(len(motion) == len(color) == 6
            and combinations == set(itertools.product(("motion", "color"), motion, color)),
            "conditions must be the complete 2 by 6 by 6 stimulus grid")
    require(isinstance(owner["units"], list) and owner["units"], "complete original unit list required")
    units = {}
    for unit in owner["units"]:
        exact_keys(unit, ("monkey", "unit_id", "original_exclusion_reason"), "unit")
        require(unit["monkey"] in MONKEYS, "unknown monkey")
        identifier(unit["unit_id"], "unit ID")
        require(unit_key(unit) not in units, "duplicate original unit")
        if unit["original_exclusion_reason"] is not None:
            identifier(unit["original_exclusion_reason"], "original exclusion reason")
        units[unit_key(unit)] = unit
    require({k[0] for k in units} == set(MONKEYS), "both original monkey populations required")
    require(isinstance(owner["trials"], list) and owner["trials"], "complete trial ledger required")
    seen = set()
    physical = {}
    counts = defaultdict(lambda: defaultdict(int))
    trial_counts = defaultdict(int)
    for row in owner["trials"]:
        exact_keys(row, ("monkey", "unit_id", "recording_id", "trial_id", "condition_id",
                         "correct", "split", "values"), "trial")
        for field in ("monkey", "unit_id", "recording_id", "trial_id", "condition_id"):
            identifier(row[field], field)
        require(unit_key(row) in units, "trial has undeclared original unit")
        require(row["condition_id"] in conditions, "undeclared stimulus condition")
        require(type(row["correct"]) is bool, "correct must be boolean")
        require(row["split"] in ROLES, "split must be train, validation or assessment")
        key = trial_key(row)
        require(key not in seen, "duplicate original trial identity")
        seen.add(key)
        physical_key = row["monkey"], row["recording_id"], row["trial_id"]
        physical_metadata = row["split"], row["condition_id"], row["correct"]
        require(physical_key not in physical or physical[physical_key] == physical_metadata,
                "shared physical trial crosses splits or has inconsistent condition/outcome")
        physical[physical_key] = physical_metadata
        trial_counts[unit_key(row)] += 1
        if row["correct"]:
            counts[unit_key(row)][row["condition_id"]] += 1
        if row["values"] is not None:
            vector(row["values"], "trial values")
    require(set(trial_counts) == set(units), "unit omitted from complete trial ledger")
    # This digest binds declared identities only, not private neural values or an authenticated archive.
    census = {"units": sorted([list(k) for k in units]),
              "trials": sorted([list(k) for k in seen]),
              "conditions": sorted(conditions)}
    require(digest(census) == prov["owner_census_sha256"], "declared census SHA256 mismatch")
    eligible = set()
    ledger = []
    for key in sorted(units):
        low = {cid: counts[key][cid] for cid in sorted(conditions) if counts[key][cid] < 4}
        if not low:
            eligible.add(key)
        ledger.append({"monkey": key[0], "unit_id": key[1], "eligible": not low,
                       "correct_trial_counts": dict(sorted(counts[key].items())),
                       "under_four_conditions": low, "total_trials": trial_counts[key],
                       "original_exclusion_reason": units[key]["original_exclusion_reason"]})
    require({key[0] for key in eligible} == set(MONKEYS), "both monkeys need eligible original units")
    cells = defaultdict(list)
    for row in owner["trials"]:
        if unit_key(row) in eligible and row["correct"]:
            require(row["values"] is not None, "eligible correct trial has missing neural values")
            cells[(unit_key(row), row["condition_id"], row["split"])].append(row)
    for key in sorted(eligible):
        for cid in conditions:
            for split, minimum in (("train", 2), ("validation", 1), ("assessment", 1)):
                require(len(cells[(key, cid, split)]) >= minimum,
                        f"incomplete nested partition for {key}/{cid}/{split}: minimum {minimum}")
    return {"eligible": eligible, "conditions": conditions, "cells": cells, "ledger": ledger,
            "declared_census_sha256": digest(census), "owner_sha256": digest(owner)}


def fit_training(owner, checked=None):
    """Derive condition-balanced population variance and 15-point means from train only."""
    checked = audit(owner) if checked is None else checked
    fitted = {}
    for key in sorted(checked["eligible"]):
        condition_means = {}
        for cid in sorted(checked["conditions"]):
            rows = checked["cells"][(key, cid, "train")]
            condition_means[cid] = [mean(row["values"][t] for row in rows) for t in range(15)]
        center = mean(mean(curve) for curve in condition_means.values())
        variance = mean(mean(mean(squared(x - center) for x in row["values"])
                             for row in checked["cells"][(key, cid, "train")])
                        for cid in sorted(checked["conditions"]))
        require(variance > 0, f"zero training variance for original unit {key}; unit cannot be dropped")
        fitted[key] = {"center": center, "variance": variance, "condition_means": condition_means}
    return fitted


def assessment_rows(owner, checked):
    return sorted((row for row in owner["trials"] if row["split"] == "assessment"
                   and unit_key(row) in checked["eligible"]), key=trial_key)


def prepare(owner):
    """Construct separate public development/assessment metadata packets for the owner.

    This is a serialization boundary, not enforcement of process/context isolation.
    """
    checked = audit(owner)
    fit_training(owner, checked)  # refuse degenerate scales before candidate packet generation
    common = {"task_id": TASK, "policy": POLICY, "conditions": owner["conditions"],
              "time_axis": owner["time_axis"], "frozen_program_sha256": owner["frozen_program_sha256"],
              "units": [{"monkey": k[0], "unit_id": k[1]} for k in sorted(checked["eligible"])]}
    development = {**common, "schema": "latentcircuit.development.v1", "trials": [
        dict(row) for row in sorted(owner["trials"], key=trial_key)
        if row["split"] in ("train", "validation") and row["correct"]
        and unit_key(row) in checked["eligible"]]}
    assessment = {**common, "schema": "latentcircuit.assessment-inputs.v1",
                  "trials": [identity(row) for row in assessment_rows(owner, checked)]}
    # Public packet binding excludes all assessment values, outcomes, census and excluded rows.
    packet_digest = digest({"development": development, "assessment": assessment})
    development["packet_sha256"] = assessment["packet_sha256"] = packet_digest
    return development, assessment


def baseline_submission(owner):
    """Complete train-condition-mean predictions, used as the owner-side reference control."""
    checked = audit(owner)
    fit = fit_training(owner, checked)
    _, assessment = prepare(owner)
    return {"schema": "latentcircuit.predictions.v1", "task_id": TASK,
            "coordinate_system": "original_neuron", "packet_sha256": assessment["packet_sha256"],
            "frozen_program_sha256": owner["frozen_program_sha256"],
            "predictions": [{**identity(row), "values": fit[unit_key(row)]["condition_means"][row["condition_id"]]}
                            for row in assessment_rows(owner, checked)]}


def score(owner, submission, candidate_program_bytes):
    """Score frozen candidate predictions and paired training-mean control on owner targets."""
    checked = audit(owner)
    fitted = fit_training(owner, checked)
    require(isinstance(candidate_program_bytes, bytes), "supply frozen candidate program bytes")
    require(hashlib.sha256(candidate_program_bytes).hexdigest() == owner["frozen_program_sha256"],
            "candidate program artifact differs from frozen byte hash")
    exact_keys(submission, ("schema", "task_id", "coordinate_system", "packet_sha256",
                            "frozen_program_sha256", "predictions"), "submission")
    require(submission["schema"] == "latentcircuit.predictions.v1"
            and submission["task_id"] == TASK, "wrong prediction task/schema")
    require(submission["coordinate_system"] == "original_neuron", "candidate projection is forbidden")
    _, packet = prepare(owner)
    require(submission["packet_sha256"] == packet["packet_sha256"], "prediction packet binding mismatch")
    require(submission["frozen_program_sha256"] == owner["frozen_program_sha256"], "wrong program identity")
    require(isinstance(submission["predictions"], list), "prediction list required")
    predictions = {}
    for row in submission["predictions"]:
        exact_keys(row, ("monkey", "unit_id", "recording_id", "trial_id", "condition_id", "values"),
                   "prediction")
        for field in ("monkey", "unit_id", "recording_id", "trial_id", "condition_id"):
            identifier(row[field], "prediction " + field)
        key = trial_key(row)
        require(key not in predictions, "duplicate prediction identity")
        vector(row["values"], "prediction values")
        predictions[key] = row
    targets = assessment_rows(owner, checked)
    require(set(predictions) == {trial_key(row) for row in targets},
            "predictions must cover exactly all original assessment neuron/trial coordinates")
    cell_errors = defaultdict(list)
    cell_baselines = defaultdict(list)
    for target in targets:
        pred = predictions[trial_key(target)]
        require(pred["condition_id"] == target["condition_id"], "prediction condition mismatch")
        # Do not directly filter outer input rows by correctness. Only the
        # registered correct-trial endpoint is scored; error-trial analysis is held.
        if not target["correct"]:
            continue
        key = unit_key(target)
        cid = target["condition_id"]
        scale = fitted[key]["variance"]
        cell_errors[(key, cid)].append(mean(squared(p - y) / scale
                                            for p, y in zip(pred["values"], target["values"])))
        control = fitted[key]["condition_means"][cid]
        cell_baselines[(key, cid)].append(mean(squared(p - y) / scale
                                               for p, y in zip(control, target["values"])))
    per_unit = []
    for key in sorted(checked["eligible"]):
        loss = mean(mean(cell_errors[(key, cid)]) for cid in checked["conditions"])
        control = mean(mean(cell_baselines[(key, cid)]) for cid in checked["conditions"])
        per_unit.append({"monkey": key[0], "unit_id": key[1], "neural_nse": loss,
                         "condition_mean_nse": control, "candidate_minus_condition_mean": loss - control,
                         "training_center": fitted[key]["center"],
                         "training_variance": fitted[key]["variance"]})
    per_monkey = {}
    for monkey in MONKEYS:
        rows = [row for row in per_unit if row["monkey"] == monkey]
        per_monkey[monkey] = {"eligible_units": len(rows),
                              "assessment_prediction_rows": sum(row["monkey"] == monkey for row in targets),
                              "assessment_trial_rows": sum(row["monkey"] == monkey and row["correct"]
                                                           for row in targets),
                              "neural_nse": mean(row["neural_nse"] for row in rows),
                              "condition_mean_nse": mean(row["condition_mean_nse"] for row in rows),
                              "candidate_minus_condition_mean": mean(row["candidate_minus_condition_mean"]
                                                                      for row in rows)}
    return {"schema": "latentcircuit.score.v1", "task_id": TASK, "policy": POLICY,
            "owner_sha256": checked["owner_sha256"], "packet_sha256": packet["packet_sha256"],
            "candidate_program_sha256": owner["frozen_program_sha256"], "lower_is_better": True,
            "equal_monkey_neural_nse": mean(row["neural_nse"] for row in per_monkey.values()),
            "equal_monkey_condition_mean_nse": mean(row["condition_mean_nse"] for row in per_monkey.values()),
            "equal_monkey_candidate_minus_condition_mean": mean(row["candidate_minus_condition_mean"]
                                                                  for row in per_monkey.values()),
            "per_monkey": per_monkey, "per_original_unit": per_unit,
            "declared_eligibility_ledger": checked["ledger"], "biological_animals": 2,
            "native_behavior_guard": "unresolved_not_scored", "improvement_decision": "withheld",
            "scientific_qualification": "unknown", "authentic_census_verified": False,
            "holds": HOLD_REASONS}


def write_json(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("audit", "prepare", "baseline", "score"))
    parser.add_argument("--owner", required=True, help="owner-only complete target/ledger JSON")
    parser.add_argument("--expected-owner-sha256", required=True,
                        help="owner-predeclared SHA256 of exact input file bytes")
    parser.add_argument("--output", required=True, help="owner-only output JSON; development packet for prepare")
    parser.add_argument("--assessment-output", help="separate metadata-only packet for prepare")
    parser.add_argument("--predictions", help="candidate predictions JSON for score")
    parser.add_argument("--candidate-program", help="frozen candidate artifact for score; bytes checked only")
    args = parser.parse_args()
    try:
        owner_bytes = Path(args.owner).read_bytes()
        actual = hashlib.sha256(owner_bytes).hexdigest()
        require(actual == sha(args.expected_owner_sha256, "expected owner file hash"),
                "owner file bytes differ from predeclared SHA256")
        # Refuse accidental overwrite of any input or the two packet outputs.
        inputs = {Path(p).resolve() for p in (args.owner, args.predictions, args.candidate_program) if p}
        outputs = [Path(p).resolve() for p in (args.output, args.assessment_output) if p]
        require(not inputs.intersection(outputs) and len(set(outputs)) == len(outputs),
                "input/output paths must be distinct")
        owner = _parse_json(owner_bytes)
        if args.command == "prepare":
            require(args.assessment_output is not None, "prepare requires --assessment-output")
            development, assessment = prepare(owner)
            write_json(args.output, development)
            write_json(args.assessment_output, assessment)
        elif args.command == "audit":
            checked = audit(owner)
            fit_training(owner, checked)
            write_json(args.output, {"task_id": TASK, "owner_sha256": checked["owner_sha256"],
                                    "declared_eligibility_ledger": checked["ledger"],
                                    "authentic_census_verified": False, "holds": HOLD_REASONS})
        elif args.command == "baseline":
            write_json(args.output, baseline_submission(owner))
        else:
            require(args.predictions and args.candidate_program,
                    "score requires --predictions and --candidate-program")
            result = score(owner, _load_json(args.predictions), Path(args.candidate_program).read_bytes())
            result["owner_file_sha256"] = actual
            write_json(args.output, result)
    except (ContractError, OSError, json.JSONDecodeError, UnicodeError) as exc:
        parser.exit(2, f"error: {exc}\n")


if __name__ == "__main__":
    main()
