#!/usr/bin/env python3
"""Calculate the registered vestibular estimand on an assessor's normalized inputs.

This module authenticates no biological identities, performs no fitting, and runs
no participant code. An externally trusted reference supplies the complete roster.
"""

import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import sys

TASK = "NEURAL-DISC-20261114-VESTIBULAR-VO"
CONDITIONS = ("naturalistic", "sinusoidal0.5Hz", "sinusoidal1Hz", "sinusoidal2Hz",
              "sinusoidal3Hz", "sinusoidal4Hz", "sinusoidal5Hz", "sinusoidal8Hz", "sinusoidal17Hz")
STRATA = ("simultaneous_pair", "single_neuron")


class Invalid(ValueError):
    def __init__(self, kind, message):
        super().__init__(message)
        self.kind = kind


def need(condition, message, kind="invalid_reference"):
    if not condition:
        raise Invalid(kind, message)


def fields(value, required, optional=(), *, kind="invalid_reference"):
    need(isinstance(value, dict), "Expected an object", kind)
    need(set(required) <= set(value) <= set(required) | set(optional),
         "Missing or unexpected object fields", kind)


def identifier(value, *, kind="invalid_reference"):
    need(isinstance(value, str) and 0 < len(value) <= 256
         and value.strip() == value and not any(ord(c) < 32 for c in value),
         "Expected a bounded nonempty identity", kind)
    return value


def digest(value):
    need(isinstance(value, str) and len(value) == 64
         and all(c in "0123456789abcdef" for c in value), "Expected a SHA-256 identity")


def finite(value, *, kind="invalid_reference"):
    need(type(value) in (int, float), "Expected a finite numeric value", kind)
    try:
        result = float(value)
    except (ValueError, OverflowError):
        raise Invalid(kind, "Numeric value is outside finite arithmetic") from None
    need(math.isfinite(result), "Expected a finite numeric value", kind)
    need(type(value) is not int or int(result) == value,
         "Integer metric value is not exactly representable in float arithmetic", kind)
    return result


def unique_rows(rows, count=None):
    need(isinstance(rows, list), "Expected an explicit roster")
    result = {}
    for row in rows:
        need(isinstance(row, dict), "Roster members must be objects")
        key = identifier(row.get("id"))
        need(key not in result, "Duplicate roster identity")
        result[key] = row
    need(count is None or len(result) == count, "Incomplete registered census")
    return result


def reasons(value, expected):
    need(isinstance(value, dict) and set(value) == set(expected),
         "Unavailable identities and their reasons must be explicit and exact")
    for reason in value.values():
        identifier(reason)


def validate_reference(ref):
    fields(ref, ("schema", "task_id", "evaluation_id", "evidence_id", "access_condition",
                 "binding", "animals", "neurons", "pairs", "groups", "excluded_pairs",
                 "excluded_neurons", "conditions", "additional_conditions", "coverage", "cases"))
    need(ref["schema"] == "vestibular-reference-v1" and ref["task_id"] == TASK,
         "Wrong reference schema or task")
    for key in ("evaluation_id", "access_condition"):
        identifier(ref[key])
    digest(ref["evidence_id"])
    binding = ref["binding"]
    fields(binding, ("kind", "source_version", "source_sha256", "roster_sha256",
                     "protocol_sha256", "target_unit", "tick_unit", "mask_basis", "prior"))
    need(binding["kind"] in ("generated_control", "assessor_supplied"), "Unknown reference kind")
    for key in ("source_version", "target_unit", "tick_unit"):
        identifier(binding[key])
    for key in ("source_sha256", "roster_sha256", "protocol_sha256"):
        digest(binding[key])
    need(binding["mask_basis"] == "input_acquisition_metadata", "Target-selected masks are forbidden")
    prior = binding["prior"]
    fields(prior, ("id", "selection_split", "selection_protocol_sha256"))
    identifier(prior["id"])
    need(prior["selection_split"] == "training_only", "Prior choice must precede held outcomes")
    digest(prior["selection_protocol_sha256"])

    animals = ref["animals"]
    need(isinstance(animals, list) and len(animals) == 3 and len(set(animals)) == 3,
         "Exactly three explicit animal identities are required")
    for animal in animals:
        identifier(animal)
    neurons = unique_rows(ref["neurons"], 49)
    for row in neurons.values():
        fields(row, ("id", "animal_id"))
        need(row["animal_id"] in animals, "Neuron belongs to an unknown animal")
    need({r["animal_id"] for r in neurons.values()} == set(animals), "All animals need census members")
    pairs = unique_rows(ref["pairs"], 35)
    for row in pairs.values():
        fields(row, ("id", "animal_id", "neuron_ids"))
        ns = row["neuron_ids"]
        need(isinstance(ns, list) and len(ns) == 2 and len(set(ns)) == 2,
             "A genuine pair requires two distinct neuron identities")
        need(row["animal_id"] in animals and all(n in neurons and neurons[n]["animal_id"] == row["animal_id"] for n in ns),
             "A pair cannot mix animals or unknown neurons")
    need({r["animal_id"] for r in pairs.values()} == set(animals), "All animals need pair census members")
    groups = unique_rows(ref["groups"])
    physical = set()
    used_pairs, used_neurons = set(), set()
    for row in groups.values():
        fields(row, ("id", "animal_id", "session_id", "recording_id", "stratum", "neuron_ids", "pair_id"))
        for key in ("session_id", "recording_id"):
            identifier(row[key])
        ns = row["neuron_ids"]
        need(isinstance(ns, list) and len(set(ns)) == len(ns), "Group neuron identities must be unique")
        need(row["animal_id"] in animals and all(n in neurons and neurons[n]["animal_id"] == row["animal_id"] for n in ns),
             "A recording group cannot mix animals or unknown neurons")
        if row["stratum"] == "simultaneous_pair":
            need(row["pair_id"] in pairs and len(ns) == 2
                 and set(ns) == set(pairs[row["pair_id"]]["neuron_ids"])
                 and row["animal_id"] == pairs[row["pair_id"]]["animal_id"],
                 "Primary groups must use a declared genuine pair, never a pseudopopulation")
            used_pairs.add(row["pair_id"])
        else:
            need(row["stratum"] == "single_neuron" and len(ns) == 1 and row["pair_id"] is None,
                 "Single-neuron groups must occupy their separate stratum")
        identity = (row["animal_id"], row["session_id"], row["recording_id"], tuple(sorted(ns)))
        need(identity not in physical, "Duplicate physical recording group aliases")
        physical.add(identity)
        used_neurons.update(ns)
    reasons(ref["excluded_pairs"], set(pairs) - used_pairs)
    reasons(ref["excluded_neurons"], set(neurons) - used_neurons)
    conditions = ref["conditions"]
    need(isinstance(conditions, list) and len(set(conditions)) == len(conditions)
         and set(CONDITIONS) <= set(conditions), "All nine declared motion conditions must be accounted for")
    for condition in conditions:
        identifier(condition)
    reasons(ref["additional_conditions"], set(conditions) - set(CONDITIONS))

    coverage, expected = {}, {}
    need(isinstance(ref["coverage"], list), "Expected complete coverage rows")
    for cell in ref["coverage"]:
        fields(cell, ("animal_id", "condition", "stratum", "status", "group_repeats", "unavailable_groups"), ("reason",))
        key = (cell["animal_id"], cell["condition"], cell["stratum"])
        need(key[0] in animals and key[1] in conditions and key[2] in STRATA and key not in coverage,
             "Unknown or duplicate coverage cell")
        eligible = {g for g, row in groups.items() if (row["animal_id"], row["stratum"]) == (key[0], key[2])}
        need(isinstance(cell["group_repeats"], list), "Expected frozen group-repeat membership")
        selected = set()
        for member in cell["group_repeats"]:
            fields(member, ("group_id", "repeat_ids"))
            group = member["group_id"]
            need(group in eligible and group not in selected, "Unknown or repeated group in coverage")
            selected.add(group)
            repeats = member["repeat_ids"]
            need(isinstance(repeats, list) and repeats and len(set(repeats)) == len(repeats),
                 "Complete held repeat identities must be unique and nonempty")
            for repeat in repeats:
                identifier(repeat)
                expected[(group, key[1], repeat)] = key
        reasons(cell["unavailable_groups"], eligible - selected)
        if selected:
            need(cell["status"] == "available" and "reason" not in cell, "Available cell status mismatch")
        else:
            need(cell["status"] == "unavailable", "Unavailable cell must not receive a score")
            identifier(cell.get("reason"))
        coverage[key] = cell
    required_cells = {(a, c, s) for a in animals for c in conditions for s in STRATA}
    need(set(coverage) == required_cells, "Every animal-condition-stratum cell needs an availability decision")
    need(any(key[2] == "simultaneous_pair" for key in expected.values()), "No primary pair cases are available")

    cases = unique_rows(ref["cases"])
    seen = set()
    for case in cases.values():
        fields(case, ("id", "group_id", "condition", "repeat_id", "sample_ticks", "valid_mask", "target", "prior"))
        key = (case["group_id"], case["condition"], case["repeat_id"])
        need(key in expected and key not in seen, "Case is missing from or duplicated in frozen repeat support")
        seen.add(key)
        ticks, mask = case["sample_ticks"], case["valid_mask"]
        need(isinstance(ticks, list) and ticks and all(type(t) is int for t in ticks)
             and all(a < b for a, b in zip(ticks, ticks[1:])), "Sample clocks must be exact strictly increasing integer ticks")
        need(isinstance(mask, list) and len(mask) == len(ticks)
             and all(type(v) is bool for v in mask) and any(mask), "A scored repeat needs a fixed nonempty valid core")
        need(isinstance(case["target"], list) and isinstance(case["prior"], list)
             and len(case["target"]) == len(case["prior"]) == len(ticks), "Complete repeat arrays must align")
        for use, target, value in zip(mask, case["target"], case["prior"]):
            if use or target is not None:
                finite(target)
            finite(value)
        try:
            repeat_metrics([float(v) for v, use in zip(case["target"], mask) if use],
                           [float(v) for v, use in zip(case["prior"], mask) if use])
        except (ArithmeticError, ValueError):
            raise Invalid("invalid_reference", "Reference or prior arithmetic is outside finite support") from None
    need(seen == set(expected), "The reference lacks required complete held repeats")
    return {"cases": cases, "groups": groups, "coverage": coverage, "neurons": neurons, "pairs": pairs}


def validate_submission(submission, ref, plan):
    kind = "invalid_submission"
    fields(submission, ("schema", "task_id", "evaluation_id", "evidence_id", "access_condition", "mode", "cases"), kind=kind)
    need(submission["schema"] == "vestibular-predictions-v1", "Wrong prediction schema", kind)
    for key in ("task_id", "evaluation_id", "evidence_id", "access_condition"):
        need(submission[key] == ref[key], "Submission does not match the selected evidence and protocol", kind)
    identifier(submission["mode"], kind=kind)
    need(isinstance(submission["cases"], list), "Expected complete prediction cases", kind)
    rows = {}
    for row in submission["cases"]:
        fields(row, ("id", "sample_ticks", "prediction"), kind=kind)
        key = identifier(row["id"], kind=kind)
        need(key in plan["cases"] and key not in rows, "Unknown or duplicate prediction case", kind)
        case = plan["cases"][key]
        need(isinstance(row["sample_ticks"], list) and all(type(t) is int for t in row["sample_ticks"])
             and row["sample_ticks"] == case["sample_ticks"], "Prediction clocks do not match complete native support", kind)
        need(isinstance(row["prediction"], list) and len(row["prediction"]) == len(case["sample_ticks"]),
             "Missing or extra prediction samples", kind)
        rows[key] = [finite(v, kind=kind) for v in row["prediction"]]
    need(set(rows) == set(plan["cases"]), "Missing required prediction cases", kind)
    return rows


def mean(values):
    try:
        result = math.fsum(values) / len(values)
    except OverflowError:
        # Finite means can exist even when the unscaled sum exceeds float range.
        result = math.fsum(v / len(values) for v in values)
    need(result != 0 or not ((all(v >= 0 for v in values) and any(v > 0 for v in values))
                            or (all(v <= 0 for v in values) and any(v < 0 for v in values))),
         "Mean arithmetic underflow", "invalid_submission")
    return result


def repeat_metrics(target, prediction):
    errors = [p - y for y, p in zip(target, prediction)]
    mse = mean([e * e for e in errors])
    ymean, pmean = mean(target), mean(prediction)
    ys, ps = [y - ymean for y in target], [p - pmean for p in prediction]
    yvar, pvar = mean([y * y for y in ys]), mean([p * p for p in ps])
    need(mse != 0 or all(e == 0 for e in errors), "Error arithmetic underflow", "invalid_submission")
    need(yvar != 0 or all(y == target[0] for y in target), "Target variance arithmetic underflow", "invalid_submission")
    need(pvar != 0 or all(p == prediction[0] for p in prediction), "Prediction variance arithmetic underflow", "invalid_submission")
    covariance = mean([y * p for y, p in zip(ys, ps)])
    slope = covariance / yvar if yvar else None
    correlation = covariance / math.sqrt(yvar) / math.sqrt(pvar) if yvar and pvar else None
    if correlation is not None:
        correlation = max(-1.0, min(1.0, correlation))
    result = {"mse": mse, "r2": 1.0 - mse / yvar if yvar else None,
              "pearson_r": correlation, "mean_error": mean(errors), "scale_slope": slope,
              "scale_intercept": pmean - slope * ymean if slope is not None else None,
              "sign_agreement": mean([float((p > 0) - (p < 0) == (y > 0) - (y < 0)) for y, p in zip(target, prediction)]),
              "r2_undefined_reason": None if yvar else "constant_target",
              "pearson_undefined_reason": None if yvar and pvar else "constant_target_or_prediction"}
    need(all(v is None or isinstance(v, str) or math.isfinite(v) for v in result.values()),
         "Metric arithmetic is nonfinite", "invalid_submission")
    return result


def _score(ref, plan, submission):
    predictions = validate_submission(submission, ref, plan)
    grouped = defaultdict(list)
    repeats = []
    try:
        for key, case in sorted(plan["cases"].items()):
            mask = case["valid_mask"]
            target = [float(v) for v, use in zip(case["target"], mask) if use]
            pred = [v for v, use in zip(predictions[key], mask) if use]
            prior = [float(v) for v, use in zip(case["prior"], mask) if use]
            candidate_metrics, prior_metrics = repeat_metrics(target, pred), repeat_metrics(target, prior)
            group = plan["groups"][case["group_id"]]
            cell_key = (group["animal_id"], case["condition"], group["stratum"])
            row = {"case_id": key, "group_id": case["group_id"], "repeat_id": case["repeat_id"],
                   "animal_id": group["animal_id"], "condition": case["condition"], "stratum": group["stratum"],
                   "native_samples": len(mask), "valid_samples": len(target),
                   "candidate": candidate_metrics, "prior": prior_metrics}
            repeats.append(row)
            grouped[cell_key].append(row)
        vectors = {stratum: [] for stratum in STRATA}
        for key, cell in sorted(plan["coverage"].items()):
            entry = {"animal_id": key[0], "condition": key[1], "status": cell["status"],
                     "unavailable_groups": cell["unavailable_groups"]}
            if cell["status"] == "unavailable":
                entry.update(reason=cell["reason"], candidate_mse=None, prior_mse=None, prior_improvement=None)
            else:
                rows = grouped[key]
                by_group = defaultdict(list)
                for row in rows:
                    by_group[row["group_id"]].append(row)
                summaries = [{"group_id": g, "repeat_count": len(rs),
                              "candidate_mse": mean([r["candidate"]["mse"] for r in rs]),
                              "prior_mse": mean([r["prior"]["mse"] for r in rs])}
                             for g, rs in sorted(by_group.items())]
                candidate = mean([g["candidate_mse"] for g in summaries])
                prior = mean([g["prior_mse"] for g in summaries])
                samples = sum(r["valid_samples"] for r in rows)
                max_mse = max(r["candidate"]["mse"] for r in rows)
                sample_mse = max_mse * math.fsum((r["candidate"]["mse"] / max_mse) * (r["valid_samples"] / samples)
                                               for r in rows) if max_mse else 0.0
                need(sample_mse != 0 or max_mse == 0, "Weighted mean arithmetic underflow", "invalid_submission")
                entry.update(candidate_mse=candidate, prior_mse=prior, prior_improvement=prior - candidate,
                             group_count=len(summaries), repeat_count=len(rows), valid_samples=samples,
                             groups=summaries, secondary_sample_weighted_mse=sample_mse,
                             secondary_sample_weights=[{"case_id": r["case_id"], "valid_samples": r["valid_samples"]} for r in rows])
            vectors[key[2]].append(entry)
    except (ArithmeticError, ValueError) as error:
        if isinstance(error, Invalid):
            raise
        raise Invalid("invalid_submission", "Metric arithmetic is outside finite support") from None
    return {"status": "valid_submission", "task_id": TASK, "evaluation_id": ref["evaluation_id"],
            "evidence_id": ref["evidence_id"], "access_condition": ref["access_condition"],
            "mode_claim": submission["mode"], "reference_kind": ref["binding"]["kind"],
            "target_unit": ref["binding"]["target_unit"], "prior_id": ref["binding"]["prior"]["id"],
            "primary_animal_condition_vector": vectors["simultaneous_pair"],
            "single_neuron_diagnostics": vectors["single_neuron"], "repeat_diagnostics": repeats,
            "coverage": {"animal_count": 3, "neuron_census": 49, "pair_census": 35,
                         "recording_group_count": len(plan["groups"]), "required_cases": len(plan["cases"]),
                         "predicted_native_samples": sum(len(c["sample_ticks"]) for c in plan["cases"].values()),
                         "excluded_pairs": ref["excluded_pairs"], "excluded_neurons": ref["excluded_neurons"],
                         "group_membership": list(plan["groups"].values()),
                         "shared_neuron_groups": {n: sorted(g for g, row in plan["groups"].items() if n in row["neuron_ids"])
                                                  for n in plan["neurons"]}},
            "interpretation": {"cross_animal_primary_aggregate": None, "maximum_independent_animal_units": 3,
                               "animals_with_pair_scores": sorted({r["animal_id"] for r in vectors["simultaneous_pair"] if r["status"] == "available"}),
                               "native_data_binding_verified": False, "prior_training_provenance_verified": False,
                               "mode_execution_verified": False, "scientific_qualification": False,
                               "pass_threshold": None}}


def evaluate(reference, submission):
    """All-or-failure calculation; reference is trusted assessor input, not participant input."""
    try:
        plan = validate_reference(reference)
        return _score(reference, plan, submission)
    except (Invalid, KeyError, TypeError, RecursionError) as error:
        return {"status": error.kind if isinstance(error, Invalid) else "invalid_reference_or_submission",
                "reason": str(error) if isinstance(error, Invalid) else "Malformed input structure",
                "primary_animal_condition_vector": None, "scientific_qualification": False}


def compare(reference, fixed_program, case_investigation):
    """Matched comparison only; no execution or evidence-parity claims are inferred."""
    first, second = evaluate(reference, fixed_program), evaluate(reference, case_investigation)
    if first["status"] != "valid_submission" or second["status"] != "valid_submission":
        return {"status": "invalid_comparison", "fixed_status": first["status"], "investigation_status": second["status"],
                "primary_comparison": None, "scientific_qualification": False}
    if first["mode_claim"] != "fixed_program" or second["mode_claim"] != "case_investigation":
        return {"status": "invalid_comparison", "reason": "Expected fixed_program and case_investigation artifacts",
                "primary_comparison": None, "scientific_qualification": False}
    rows = []
    for a, b in zip(first["primary_animal_condition_vector"], second["primary_animal_condition_vector"]):
        rows.append({"animal_id": a["animal_id"], "condition": a["condition"], "status": a["status"],
                     "fixed_mse": a["candidate_mse"], "investigation_mse": b["candidate_mse"],
                     "investigation_improvement": None if a["status"] == "unavailable" else a["candidate_mse"] - b["candidate_mse"]})
    return {"status": "valid_comparison", "task_id": TASK, "evaluation_id": reference["evaluation_id"],
            "evidence_id": reference["evidence_id"], "primary_comparison": rows,
            "fixed_program": first, "case_investigation": second,
            "mode_execution_verified": False, "scientific_qualification": False}


def read_json(path, limit, expected_sha=None):
    need(type(limit) is int and limit > 0, "Explicit positive input byte limit required", "invalid_input")
    path = Path(path)
    need(path.is_file() and not path.is_symlink(), "Expected an ordinary JSON input", "invalid_input")
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    need(len(raw) <= limit, "Input exceeds selected byte limit", "invalid_input")
    if expected_sha is not None:
        digest(expected_sha)
        need(hashlib.sha256(raw).hexdigest() == expected_sha, "Assessor reference hash mismatch", "invalid_reference")
    def unique(items):
        result = {}
        for key, value in items:
            need(key not in result, "Duplicate JSON key", "invalid_input")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda value: (_ for _ in ()).throw(Invalid("invalid_input", "Nonfinite JSON constant")))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--reference-sha256", required=True)
    parser.add_argument("--submission", required=True, help="Frozen-program artifact for --investigation comparisons")
    parser.add_argument("--investigation", help="Optional matched case-investigation prediction artifact")
    parser.add_argument("--max-reference-bytes", required=True, type=int)
    parser.add_argument("--max-submission-bytes", required=True, type=int)
    args = parser.parse_args(argv)
    try:
        submission = read_json(args.submission, args.max_submission_bytes)
        investigation = read_json(args.investigation, args.max_submission_bytes) if args.investigation else None
        reference = read_json(args.reference, args.max_reference_bytes, args.reference_sha256)
        result = compare(reference, submission, investigation) if args.investigation else evaluate(reference, submission)
    except (Invalid, OSError, ValueError, RecursionError) as error:
        result = {"status": error.kind if isinstance(error, Invalid) else "invalid_input",
                  "reason": str(error) if isinstance(error, Invalid) else "Could not read bounded JSON inputs",
                  "primary_animal_condition_vector": None, "scientific_qualification": False}
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0 if result["status"] in ("valid_submission", "valid_comparison") else 2


if __name__ == "__main__":
    raise SystemExit(main())
