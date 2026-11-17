"""ABR transfer construction scorer; no native-data admission or model execution.

Original implementation of the registered animal-macro threshold endpoint.
Public CLI accepts generated controls and audits unverified prepared references.
It cannot certify source semantics, turn a historical predictor into a label,
or admit authentic benchmark scores while the task's native gates are open.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from pathlib import Path

TASK_ID = "NEURAL-SCOPE-20261114-ABR-TRANSFER"
CONTRACT_SHA256 = "3ac11adf902d863075f6c38ee76365321a1fe44f23fde898e7f13c6b6a3c0f86"
TARGET_RELEASE = "zenodo:15619100"
BACKGROUNDS = ("C57BL/6NTacCdh23+", "C57BL/6N")
TONES_HZ = (3000, 6000, 12000, 18000, 24000, 30000, 36000, 42000)
HOLDS = [
    "Native complete target/support census and globally unique animal identities are unauthenticated.",
    "Native threshold, sentinel/censoring, repeated ear/session and annotation mappings remain unresolved.",
    "Physical voltage units, acoustic zero, sample endpoints, interpolation and full-stack fidelity remain unresolved.",
    "Candidate-safe adapter, protected paths, grouped source splits and condition state isolation remain unverified.",
    "Code/weight rights, target-excluded training provenance and competent full-support baselines remain unresolved.",
    "Matched four-stack calibration, byte-identical documentation and native context budgets remain unverified.",
    "No authentic reference reproduction, scientific qualification or native evaluation has been performed.",
]


class ContractError(ValueError):
    """Malformed reference or analysis request, rather than a low-scoring submission."""


def finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ContractError(f"{name} must be a finite number")
    try:
        value = float(value)
    except OverflowError as error:
        raise ContractError(f"{name} exceeds the evaluator numeric range") from error
    if not math.isfinite(value):
        raise ContractError(f"{name} must be a finite number")
    return value


def identifier(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{name} must be a nonempty string")
    return value


def exact_keys(value, required, optional=()):
    if not isinstance(value, dict):
        raise ContractError("expected an object")
    missing = set(required) - value.keys()
    unknown = value.keys() - set(required) - set(optional)
    if missing or unknown:
        raise ContractError(f"missing keys {sorted(missing)}; unknown keys {sorted(unknown)}")


def stimulus_key(stimulus):
    if not isinstance(stimulus, dict):
        raise ContractError("stimulus must be an object")
    if stimulus.get("kind") == "click":
        exact_keys(stimulus, ("kind",))
        return "click"
    exact_keys(stimulus, ("kind", "frequency_hz"))
    frequency = finite(stimulus["frequency_hz"], "frequency_hz")
    if stimulus["kind"] != "tone" or frequency not in TONES_HZ:
        raise ContractError("target tone must be a registered frequency; source frequency 100 is click, not a tone")
    return f"tone:{int(frequency)}Hz"


def annotation_bounds(annotation):
    if not isinstance(annotation, dict):
        raise ContractError("annotation must be an object")
    kind = annotation.get("kind")
    if kind == "exact":
        exact_keys(annotation, ("kind", "value_db"))
        value = finite(annotation["value_db"], "exact annotation")
        return value, value
    if kind == "left_censored":
        exact_keys(annotation, ("kind", "upper_db", "semantics_evidence"))
        identifier(annotation["semantics_evidence"], "censoring semantics evidence")
        return -math.inf, finite(annotation["upper_db"], "upper_db")
    if kind == "right_censored":
        exact_keys(annotation, ("kind", "lower_db", "semantics_evidence"))
        identifier(annotation["semantics_evidence"], "censoring semantics evidence")
        return finite(annotation["lower_db"], "lower_db"), math.inf
    raise ContractError("annotation kind must be exact, left_censored or right_censored; no sentinel inference")


def validate_reference(reference):
    exact_keys(reference, ("task_id", "contract_sha256", "target_release", "evidence_kind", "animal_roster", "cases"))
    if (reference["task_id"], reference["contract_sha256"], reference["target_release"]) != (TASK_ID, CONTRACT_SHA256, TARGET_RELEASE):
        raise ContractError("reference task, immutable contract or target release pin differs")
    mode = reference["evidence_kind"]
    if mode not in ("generated_engineering_control", "unverified_prepared_reference"):
        raise ContractError("no authentic-score admission mode exists in this initial evaluator")
    if not isinstance(reference["animal_roster"], list) or not reference["animal_roster"]:
        raise ContractError("animal_roster must be a nonempty complete roster")
    animals = {}
    for row in reference["animal_roster"]:
        exact_keys(row, ("animal_id", "genetic_background"))
        animal = identifier(row["animal_id"], "animal_id")
        if animal in animals:
            raise ContractError(f"duplicate animal {animal}")
        if row["genetic_background"] not in BACKGROUNDS:
            raise ContractError("unknown target genetic background")
        animals[animal] = row["genetic_background"]
    if mode == "unverified_prepared_reference":
        if len(animals) != 104 or [list(animals.values()).count(x) for x in BACKGROUNDS] != [54, 50]:
            raise ContractError("prepared authentic cohort requires all 104 animals and the 54/50 background roster")
    if not isinstance(reference["cases"], list) or not reference["cases"]:
        raise ContractError("cases must be the nonempty frozen native census, never an inferred Cartesian product")
    cases, represented = {}, set()
    for row in reference["cases"]:
        exact_keys(row, ("case_id", "animal_id", "stimulus", "annotation"))
        case = identifier(row["case_id"], "case_id")
        if case in cases:
            raise ContractError(f"duplicate case {case}")
        identifier(row["animal_id"], "case animal_id")
        if row["animal_id"] not in animals:
            raise ContractError(f"case {case} has an unrostered animal")
        stimulus_key(row["stimulus"])
        annotation_bounds(row["annotation"])
        cases[case] = row
        represented.add(row["animal_id"])
    if represented != set(animals):
        raise ContractError("rostered animals cannot disappear from the complete case denominator")
    return animals, cases


def validate_predictions(predictions, cases):
    """Return complete ledger, without overwriting duplicate or dropping bad rows."""
    if not isinstance(predictions, list):
        raise ContractError("predictions must be a list")
    groups, failures = {}, []
    for index, row in enumerate(predictions):
        if not isinstance(row, dict) or not isinstance(row.get("case_id"), str):
            failures.append({"row": index, "reason": "invalid_case_id"})
            continue
        case = row["case_id"]
        groups.setdefault(case, []).append((index, row))
        if case not in cases:
            failures.append({"row": index, "case_id": case, "reason": "unknown_case"})
    valid, ledger = {}, []
    for case in sorted(cases):
        entries = groups.get(case, [])
        status, reason = "valid", None
        if not entries:
            status, reason = "missing", "no_required_prediction"
        elif len(entries) != 1:
            status, reason = "invalid", "duplicate_case_id"
        else:
            _, row = entries[0]
            try:
                exact_keys(row, ("case_id", "threshold_db", "censoring", "abstain", "uncertainty"))
                finite(row["threshold_db"], "threshold_db")
                if row["censoring"] not in ("none", "left", "right"):
                    raise ContractError("censoring must be none/left/right")
                if not isinstance(row["abstain"], bool):
                    raise ContractError("abstain must be boolean")
                exact_keys(row["uncertainty"], ("lower_db", "upper_db", "coverage"))
                low = finite(row["uncertainty"]["lower_db"], "uncertainty lower_db")
                high = finite(row["uncertainty"]["upper_db"], "uncertainty upper_db")
                coverage = finite(row["uncertainty"]["coverage"], "uncertainty coverage")
                if low > high or not 0 < coverage < 1:
                    raise ContractError("uncertainty requires ordered endpoints and 0 < coverage < 1")
                valid[case] = row
            except (ContractError, TypeError) as error:
                status, reason = "invalid", str(error)
        ledger.append({"case_id": case, "animal_id": cases[case]["animal_id"], "status": status, "reason": reason})
    for case, entries in groups.items():
        if case not in cases and len(entries) > 1:
            failures.append({"case_id": case, "reason": "duplicate_unknown_case_id"})
    complete = len(valid) == len(cases) and not failures
    return complete, valid, ledger, failures


def _mean(values):
    if not values:
        return None
    values = [finite(value, "derived contribution") for value in values]
    scale = max(abs(value) for value in values)
    return 0.0 if scale == 0 else scale * (math.fsum(value / scale for value in values) / len(values))


def _finite_derived(value):
    if isinstance(value, float) and not math.isfinite(value):
        raise ContractError("derived arithmetic exceeds the evaluator numeric range")
    if isinstance(value, dict):
        for item in value.values():
            _finite_derived(item)
    elif isinstance(value, list):
        for item in value:
            _finite_derived(item)


def _macro(rows, key):
    by_animal = {}
    for row in rows:
        if row[key] is not None:
            by_animal.setdefault(row["animal_id"], []).append(row[key])
    contributions = {animal: _mean(values) for animal, values in sorted(by_animal.items())}
    return {"value": _mean(list(contributions.values())), "eligible_animals": len(contributions),
            "eligible_cases": sum(len(values) for values in by_animal.values()), "animal_contributions": contributions}


def _metrics(cases, predictions, animals):
    rows = []
    for case, truth in sorted(cases.items()):
        prediction = predictions[case]
        value = float(prediction["threshold_db"])
        lower, upper = annotation_bounds(truth["annotation"])
        exact = truth["annotation"]["kind"] == "exact"
        distance = max(lower - value, 0.0, value - upper)
        interval = prediction["uncertainty"]
        rows.append({"case_id": case, "animal_id": truth["animal_id"],
                     "genetic_background": animals[truth["animal_id"]], "stimulus": stimulus_key(truth["stimulus"]),
                     "annotation_kind": truth["annotation"]["kind"], "absolute_error_db": distance,
                     "signed_error_db": value - lower if exact else None,
                     "within_5_db": float(distance <= 5) if exact else None,
                     "within_10_db": float(distance <= 10) if exact else None,
                     "interval_coverage": float(interval["lower_db"] <= lower <= interval["upper_db"]) if exact else None,
                     "interval_width_db": interval["upper_db"] - interval["lower_db"],
                     "nominal_coverage": interval["coverage"], "abstain": float(prediction["abstain"]),
                     "declared_censoring": prediction["censoring"]})
    metric_keys = ("absolute_error_db", "signed_error_db", "within_5_db", "within_10_db", "interval_coverage", "interval_width_db", "abstain")
    metrics = {key: _macro(rows, key) for key in metric_keys}
    strata = {}
    for field in ("genetic_background", "stimulus", "annotation_kind"):
        strata[field] = {value: {key: _macro([r for r in rows if r[field] == value], key) for key in metric_keys}
                         for value in sorted({r[field] for r in rows})}
    # Varying claimed interval coverages must not be pooled into a calibration claim.
    calibration = {str(value): _macro([r for r in rows if r["nominal_coverage"] == value], "interval_coverage")
                   for value in sorted({r["nominal_coverage"] for r in rows})}
    result = {"metrics": metrics, "strata": strata, "exact_interval_coverage_by_nominal": calibration, "case_contributions": rows}
    _finite_derived(result)
    return result


def _quantile(sorted_values, q):
    position = (len(sorted_values) - 1) * q
    lo, hi = math.floor(position), math.ceil(position)
    fraction = position - lo
    return (1 - fraction) * sorted_values[lo] + fraction * sorted_values[hi]


def _bootstrap_config(replicates, seed, confidence):
    if not isinstance(replicates, int) or isinstance(replicates, bool) or not 1 <= replicates <= 100000:
        raise ContractError("bootstrap replicates must be an integer in [1,100000]")
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise ContractError("bootstrap seed must be integer")
    if not 0 < finite(confidence, "bootstrap confidence") < 1:
        raise ContractError("confidence must be in (0,1)")


def animal_bootstrap(contributions, replicates=2000, seed=0, confidence=0.95):
    """Percentile bootstrap of whole animal contributions, with multiplicity."""
    _bootstrap_config(replicates, seed, confidence)
    if not contributions:
        raise ContractError("bootstrap requires animal contributions")
    values = [finite(value, "animal contribution") for _, value in sorted(contributions.items())]
    rng = random.Random(seed)
    estimates = sorted(_mean([values[rng.randrange(len(values))] for _ in values]) for _ in range(replicates))
    tail = (1 - confidence) / 2
    return {"estimate": _mean(values), "lower": _quantile(estimates, tail), "upper": _quantile(estimates, 1 - tail),
            "confidence": confidence, "replicates": replicates, "seed": seed, "animal_count": len(values),
            "method": "whole-animal percentile bootstrap; replacement multiplicity retained; linear quantiles",
            "scope": "conditional descriptive uncertainty for fixed fits and one fixed target laboratory; not independent-laboratory population inference"}


def evaluate(reference, predictions, baseline=None, bootstrap_replicates=2000, seed=0):
    _bootstrap_config(bootstrap_replicates, seed, 0.95)
    animals, cases = validate_reference(reference)
    complete, valid, ledger, failures = validate_predictions(predictions, cases)
    report = {"task_id": TASK_ID, "contract_sha256": CONTRACT_SHA256, "evidence_kind": reference["evidence_kind"],
              "reference_sha256": hashlib.sha256(json.dumps(reference, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest(),
              "scientifically_qualified": False, "submission_ready": False, "benchmark_runnable": False,
              "preserved_holds": list(HOLDS), "expected_animals": len(animals), "expected_cases": len(cases),
              "valid_required_predictions": len(valid), "prediction_coverage": len(valid) / len(cases),
              "abstained_valid_predictions": sum(row["abstain"] for row in valid.values()),
              "abstention_fraction_all_cases": sum(row["abstain"] for row in valid.values()) / len(cases),
              "submission_complete": complete, "ledger": ledger, "submission_failures": failures,
              "primary_mae_db": None, "analysis": None, "paired_comparison": None}
    if not complete:
        report["status"] = "incomplete_submission_no_aggregate_score"
    elif reference["evidence_kind"] != "generated_engineering_control":
        report["status"] = "native_semantics_and_population_gate_no_aggregate_score"
    else:
        report["status"] = "generated_engineering_control_only"
        try:
            analysis = _metrics(cases, valid, animals)
            metric = analysis["metrics"]["absolute_error_db"]
            bootstrap = animal_bootstrap(metric["animal_contributions"], bootstrap_replicates, seed)
        except (ArithmeticError, ContractError) as error:
            report["status"] = "numeric_range_exceeded_no_aggregate_score"
            report["analysis_failure"] = str(error)
        else:
            report["analysis"] = analysis
            report["primary_mae_db"] = metric["value"]
            report["primary_bootstrap"] = bootstrap
    if baseline is not None:
        b_complete, b_valid, b_ledger, b_failures = validate_predictions(baseline, cases)
        paired = {"baseline_complete": b_complete, "baseline_ledger": b_ledger, "baseline_failures": b_failures,
                  "baseline_primary_mae_db": None, "candidate_minus_baseline_mae_db": None, "bootstrap": None}
        if report["analysis"] is not None and b_complete:
            try:
                baseline_analysis = _metrics(cases, b_valid, animals)
                metric = baseline_analysis["metrics"]["absolute_error_db"]
                differences = {animal: report["analysis"]["metrics"]["absolute_error_db"]["animal_contributions"][animal] - loss
                               for animal, loss in metric["animal_contributions"].items()}
                difference = _mean(list(differences.values()))
                bootstrap = animal_bootstrap(differences, bootstrap_replicates, seed)
            except (ArithmeticError, ContractError) as error:
                paired["analysis_failure"] = str(error)
            else:
                paired.update({"baseline_primary_mae_db": metric["value"],
                               "candidate_minus_baseline_mae_db": difference,
                               "animal_differences": differences,
                               "bootstrap": bootstrap,
                               "negative_difference_favors": "candidate"})
        report["paired_comparison"] = paired
    return report


def audit_threshold_rules(levels_db, probabilities):
    """Independent behavioral reconstruction; NEVER derives annotation labels.

    Historical v0.1.1: descending levels, strict p>0.5, two-negative stop,
    highest-level initialization. Paper-rule reconstruction: lowest lower member
    of an adjacent positive pair on the ascending list of recorded levels.
    No pair returns None (unresolved prediction), not an inferred censored label.
    """
    if not isinstance(levels_db, list) or not isinstance(probabilities, list) or not levels_db or len(levels_db) != len(probabilities):
        raise ContractError("equal nonzero level/probability lengths required")
    levels = [finite(value, "level_db") for value in levels_db]
    probs = [finite(value, "response probability") for value in probabilities]
    if len(set(levels)) != len(levels) or any(not 0 <= p <= 1 for p in probs):
        raise ContractError("levels must be unique and probabilities within [0,1]")
    ascending = sorted(zip(levels, probs))
    descending = list(reversed(ascending))
    historical, negatives = descending[0][0], 0
    for level, probability in descending:
        if probability > 0.5:
            historical, negatives = level, 0
        else:
            negatives += 1
            if negatives == 2:
                break
    paper = next((a[0] for a, b in zip(ascending, ascending[1:]) if a[1] > 0.5 and b[1] > 0.5), None)
    return {"historical_v0_1_1_db": historical, "declared_paper_rule_db": paper,
            "paper_rule_status": "adjacent_positive_pair" if paper is not None else "no_pair_unresolved",
            "rules_disagree": paper != historical,
            "not_annotation_or_censoring_inference": True,
            "paper_rule_boundary_policy": "prospective reconstruction; insufficient/all-negative/no-pair unresolved, not a finite threshold"}


def _load(path):
    def no_duplicate_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ContractError(f"duplicate JSON key {key}")
            result[key] = value
        return result
    def no_constant(value):
        raise ContractError(f"nonfinite JSON constant {value}")
    return json.loads(Path(path).read_text(), object_pairs_hook=no_duplicate_keys, parse_constant=no_constant)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--baseline")
    parser.add_argument("--bootstrap-replicates", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    try:
        result = evaluate(_load(args.reference), _load(args.predictions), _load(args.baseline) if args.baseline else None,
                          args.bootstrap_replicates, args.seed)
    except (ContractError, OSError, json.JSONDecodeError) as error:
        parser.exit(2, f"reference/input rejected: {error}\n")
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0 if result["submission_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
