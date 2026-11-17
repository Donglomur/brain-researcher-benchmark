#!/usr/bin/env python3
"""Descriptive, roster-first reporting of paired paper benchmark attempts.

Consumes trusted operator records, never candidates or neural data. This does
not authenticate records, establish scientific validity, or compute p-values.
"""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import sys

ARMS = ("paper_and_data", "paper_data_official_code")
REPRODUCTION = {"success", "failure", "abstained", "infrastructure_error", "pending"}
IMPROVEMENT = {"scored", "unavailable", "abstained", "infrastructure_error", "pending"}
CONTEXT = ("contract_id", "common_inputs_id", "baseline_id", "budget_profile_id")
MAX_INPUT_BYTES = 8 * 1024 * 1024


def require(ok, message):
    if not ok:
        raise ValueError(message)


def object_keys(obj, required, optional=()):
    require(isinstance(obj, dict), "Expected an object")
    require(set(required) <= set(obj) <= set(required) | set(optional),
            "Missing or unknown fields: " + ", ".join(sorted(set(obj) ^ set(required))))


def name(value):
    require(isinstance(value, str) and 0 < len(value) <= 200
            and all(32 <= ord(c) < 127 for c in value), "Expected a printable identifier")
    return value


def number(value):
    require(type(value) in (int, float), "Expected a finite number, not a boolean")
    original = value
    try:
        value = float(value)
    except (OverflowError, ValueError) as error:
        raise ValueError("Number exceeds finite arithmetic") from error
    require(math.isfinite(value), "Expected a finite number")
    require(type(original) is not int or original == value,
            "Integer is not exactly representable in the selected float arithmetic")
    return value


def mean(values):
    require(bool(values), "Cannot average an empty set")
    # Dividing first avoids overflow from a finite mean of large values.
    return number(math.fsum(value / len(values) for value in values))


def parse_json(body):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "Duplicate JSON key: " + key)
            result[key] = value
        return result
    def constant(value):
        raise ValueError("Invalid JSON constant: " + value)
    return json.loads(body, object_pairs_hook=pairs, parse_constant=constant)


def load_json(path):
    with Path(path).open("rb") as stream:
        body = stream.read(MAX_INPUT_BYTES + 1)
    require(len(body) <= MAX_INPUT_BYTES, "Input exceeds 8 MiB")
    return parse_json(body)


def validate_plan(plan):
    object_keys(plan, {"schema_version", "study_id", "arms", "tasks"})
    require(type(plan["schema_version"]) is int and plan["schema_version"] == 1,
            "Unsupported plan schema")
    name(plan["study_id"])
    require(plan["arms"] == list(ARMS), "Expected the two ordered paper access arms")
    require(isinstance(plan["tasks"], list) and 1 <= len(plan["tasks"]) <= 1000,
            "Expected 1 to 1000 assigned tasks")
    tasks = {}
    for task in plan["tasks"]:
        object_keys(task, {"task_id", "family_id", "metric", "direction", "replicates", *CONTEXT})
        for field in ("task_id", "family_id", "metric", *CONTEXT):
            name(task[field])
        require(task["task_id"] not in tasks, "Duplicate task assignment")
        require(task["direction"] in ("minimize", "maximize"), "Unknown metric direction")
        reps = task["replicates"]
        require(isinstance(reps, list) and 1 <= len(reps) <= 1000,
                "Expected 1 to 1000 assigned replicates per task")
        for rep in reps:
            name(rep)
        require(len(set(reps)) == len(reps), "Duplicate replicate assignment")
        tasks[task["task_id"]] = task
    require(sum(len(t["replicates"]) for t in tasks.values()) <= 10000,
            "Too many assigned pairs")
    return tasks


def validate_records(document, plan, tasks):
    object_keys(document, {"schema_version", "study_id", "attempts"})
    require(type(document["schema_version"]) is int and document["schema_version"] == 1,
            "Unsupported record schema")
    require(document["study_id"] == plan["study_id"], "Study identity mismatch")
    require(isinstance(document["attempts"], list) and len(document["attempts"]) <= 20000,
            "Expected at most 20000 attempt records")
    indexed = {}
    for record in document["attempts"]:
        object_keys(record, {"task_id", "replicate", "arm", "reproduction", "improvement",
                             "operator_evidence_id", *CONTEXT})
        for field in ("task_id", "replicate", "arm", "operator_evidence_id", *CONTEXT):
            name(record[field])
        require(record["task_id"] in tasks, "Unassigned task")
        task = tasks[record["task_id"]]
        require(record["replicate"] in task["replicates"], "Unassigned replicate")
        require(record["arm"] in ARMS, "Unassigned arm")
        require(all(record[k] == task[k] for k in CONTEXT), "Assessment or budget identity mismatch")
        key = (record["task_id"], record["replicate"], record["arm"])
        require(key not in indexed, "Duplicate attempt: retries cannot replace assigned attempts")
        require(record["reproduction"] in REPRODUCTION, "Unknown reproduction status")
        improvement = record["improvement"]
        require(isinstance(improvement, dict), "Improvement must be an object")
        status = improvement.get("status")
        require(isinstance(status, str) and status in IMPROVEMENT, "Unknown improvement status")
        if status == "scored":
            object_keys(improvement, {"status", "candidate", "baseline"})
            candidate, baseline = number(improvement["candidate"]), number(improvement["baseline"])
            number(candidate - baseline)
        else:
            object_keys(improvement, {"status"})
        indexed[key] = record
    return indexed


def success_bounds(status):
    if status == "success":
        return (1.0, 1.0)
    if status in ("failure", "abstained"):
        return (0.0, 0.0)
    return (0.0, 1.0)


def summarize(plan, document):
    tasks = validate_plan(plan)
    records = validate_records(document, plan, tasks)
    result = []
    for task in tasks.values():
        counts = {arm: Counter() for arm in ARMS}
        improve_counts = {arm: Counter() for arm in ARMS}
        arm_bounds = {arm: [] for arm in ARMS}
        pair_bounds, scored_pairs, observed_pairs = [], [], []
        for replicate in task["replicates"]:
            observations, bounds = {}, {}
            for arm in ARMS:
                record = records.get((task["task_id"], replicate, arm))
                status = record["reproduction"] if record else "pending"
                improvement = record["improvement"] if record else {"status": "pending"}
                counts[arm][status] += 1
                improve_counts[arm][improvement["status"]] += 1
                bounds[arm] = success_bounds(status)
                arm_bounds[arm].append(bounds[arm])
                observations[arm] = {"record_present": record is not None, "reproduction": status,
                                     "improvement": improvement}
                if record:
                    observations[arm]["operator_evidence_id"] = record["operator_evidence_id"]
            a, b = (bounds[arm] for arm in ARMS)
            pair_bounds.append((b[0] - a[1], b[1] - a[0]))
            ia, ib = (observations[arm]["improvement"] for arm in ARMS)
            if ia["status"] == ib["status"] == "scored":
                require(ia["baseline"] == ib["baseline"],
                        "Paired attempts must use the same common-baseline value")
                sign = 1 if task["direction"] == "maximize" else -1
                gain_a = number(sign * (number(ia["candidate"]) - number(ia["baseline"])))
                gain_b = number(sign * (number(ib["candidate"]) - number(ib["baseline"])))
                effect = number(sign * (number(ib["candidate"]) - number(ia["candidate"])))
                scored_pairs.append({"replicate": replicate, "paper_and_data_gain": gain_a,
                                     "paper_data_official_code_gain": gain_b,
                                     "code_minus_no_code_gain": effect})
            observed_pairs.append({"replicate": replicate, "arms": observations})
        lower = mean([p[0] for p in pair_bounds])
        upper = mean([p[1] for p in pair_bounds])
        result.append({
            "task_id": task["task_id"], "family_id": task["family_id"], "metric": task["metric"],
            "direction": task["direction"], "assigned_pairs": len(task["replicates"]),
            "reproduction_status_counts": {arm: {s: counts[arm][s] for s in sorted(REPRODUCTION)} for arm in ARMS},
            "improvement_status_counts": {arm: {s: improve_counts[arm][s] for s in sorted(IMPROVEMENT)} for arm in ARMS},
            "arm_success_rate_bounds": {arm: [mean([x[i] for x in arm_bounds[arm]]) for i in (0, 1)] for arm in ARMS},
            "code_minus_no_code_success_bounds": [lower, upper],
            "code_minus_no_code_success_point": lower if lower == upper else None,
            "improvement_pairs_scored": len(scored_pairs),
            "conditional_mean_code_minus_no_code_gain": mean([p["code_minus_no_code_gain"] for p in scored_pairs]) if scored_pairs else None,
            "improvement_pairs": scored_pairs, "assigned_pair_records": observed_pairs,
        })
    families = {}
    for task in result:
        families.setdefault(task["family_id"], []).append(task)
    family_rows = [{"family_id": family, "task_count": len(rows),
                    "code_minus_no_code_success_bounds": [mean([r["code_minus_no_code_success_bounds"][i] for r in rows]) for i in (0, 1)]}
                   for family, rows in sorted(families.items())]
    task_bounds = [mean([r["code_minus_no_code_success_bounds"][i] for r in result]) for i in (0, 1)]
    family_bounds = [mean([r["code_minus_no_code_success_bounds"][i] for r in family_rows]) for i in (0, 1)]
    return {"schema_version": 1, "study_id": plan["study_id"],
            "scope": "descriptive_operator_record_summary_not_scientific_validation",
            "assigned_tasks": len(tasks), "declared_families": len(families),
            "assigned_pairs": sum(len(t["replicates"]) for t in tasks.values()),
            "records_present": len(records),
            "equal_task_success_effect_bounds": task_bounds,
            "equal_declared_family_success_effect_bounds": family_bounds,
            "bounds_meaning": "Logical missing-outcome bounds, not confidence intervals; infrastructure errors remain unknown.",
            "improvement_meaning": "Within-task complete-pair descriptions only; no cross-task raw-metric average and no selection-free gain claim.",
            "limitations": ["Operator labels and identities are assertions, not authenticated evidence.",
                            "Budget-profile equality does not measure actual resources or verify information access.",
                            "Family labels do not establish biological independence.",
                            "Reproduction success and scored improvement need separate task-specific adjudication.",
                            "No causal code benefit, statistical significance, scientific admission or SOTA claim is inferred."],
            "families": family_rows, "tasks": result}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--records", required=True)
    args = parser.parse_args(argv)
    try:
        output = summarize(load_json(args.plan), load_json(args.records))
        print(json.dumps(output, indent=2, sort_keys=True, allow_nan=False))
    except (ValueError, OSError, TypeError, KeyError, OverflowError) as error:
        print("Invalid paired study input: " + str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
