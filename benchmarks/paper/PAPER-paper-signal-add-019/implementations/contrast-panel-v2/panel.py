"""Original decision-times contrast panel on fixed exported targets.

Standard-library scoring only: no HMP, fitting, target generation, or admission.
Reference and candidate predictions use the same complete global contrast folds.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import importlib.util
import json
import math
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "decision_times_initial", Path(__file__).resolve().parents[1] / "initial-evaluator-v1" / "evaluator.py")
legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(legacy)
require, number, identifier, mean = legacy.require, legacy.number, legacy.identifier, legacy.mean
TARGETS = tuple(legacy.TARGETS)
CONDITIONS = ("accuracy", "speed")
AUTHOR_MODELS = ("fechner", "pieron", "linear")


def target_digest(targets):
    """Bind both populations, all targets, identities, exclusions and units."""
    return hashlib.sha256(json.dumps(targets, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def _behavior(payload, roster):
    require(isinstance(payload, dict), "separate behavioral population required")
    require(payload.get("time_unit") == "ms" and payload.get("contrast_unit") == "percent",
            "behavior units must be ms and percent")
    inv = {}
    for row in payload.get("trial_inventory", []):
        key = (identifier(row.get("participant"), "participant"), identifier(row.get("epoch"), "epoch"))
        require(key[0] in roster and key not in inv, "unknown/duplicate behavioral inventory trial")
        require(row.get("disposition") in {"retained", "excluded"}, "behavioral disposition required")
        if row["disposition"] == "excluded":
            identifier(row.get("reason"), "exclusion reason")
        inv[key] = row["disposition"]
    require({p for p, _ in inv} == roster, "behavioral inventory must cover complete cohort")
    rows = {}
    for row in payload.get("trials", []):
        key = (identifier(row.get("participant"), "participant"), identifier(row.get("epoch"), "epoch"))
        require(key not in rows and inv.get(key) == "retained", "unknown/duplicate behavioral trial")
        require(row.get("condition") in CONDITIONS, "unknown behavioral condition")
        require(row.get("side") in {"left", "right"} and row.get("response") in {"left", "right"},
                "behavioral row must retain a left/right response")
        contrast = number(row.get("contrast_percent"), "behavioral contrast")
        rt = number(row.get("rt_ms"), "behavioral RT")
        require(2.5 < contrast <= 100 and rt > 0, "behavioral contrast/RT outside source domain")
        rows[key] = dict(participant=key[0], epoch=key[1], condition=row["condition"],
                         contrast_percent=contrast, side=row["side"], response=row["response"],
                         correct=row["side"] == row["response"], values={"rt": rt})
    require(set(rows) == {k for k, state in inv.items() if state == "retained"},
            "missing retained behavioral trial")
    return rows


def prepare(targets):
    require(targets.get("schema") == "decision-times-panel-targets-v2", "wrong target schema")
    hmp = targets.get("hmp", {})
    require(hmp.get("sample_rate_hz") == 512, "original panel requires 512 Hz targets")
    neural = legacy.read_trials(hmp)
    roster = set(hmp["expected_participants"])
    behavior = _behavior(targets.get("behavior"), roster)
    # H rows may be a subset of B; substituting H for B is never automatic.
    for row in neural:
        key = row["participant"], row["epoch"]
        require(key in behavior, "HMP trial absent from behavioral population")
        other = behavior[key]
        require(all(row[k] == other[k] for k in ("condition", "contrast_percent", "side", "response"))
                and row["values"]["rt"] == other["values"]["rt"], "HMP/behavior metadata mismatch")
    groups = defaultdict(list)
    for target in TARGETS:
        source = behavior.values() if target == "rt" else neural
        for row in source:
            groups[target, row["condition"]].append(row)
    panel = {}
    for target in TARGETS:
        for condition in CONDITIONS:
            rows = groups[target, condition]
            require({r["participant"] for r in rows} == roster,
                    "every target/condition must retain the complete cohort")
            contrasts = sorted({r["contrast_percent"] for r in rows})
            require(len(contrasts) >= 2, "contrast-left-out panel needs multiple contrasts")
            # Author matching rounds the common prediction grid to one decimal.
            # Integer-trigger source contrasts satisfy this. Refuse ambiguous
            # grids rather than silently alter the source's matching behavior.
            require(all(b - a > .1000000001 for a, b in zip(contrasts, contrasts[1:])),
                    "ambiguous one-decimal source contrast matching requires native review")
            by_person = defaultdict(list)
            by_contrast = defaultdict(list)
            for row in rows:
                by_person[row["participant"]].append(row)
                by_contrast[row["contrast_percent"]].append(row)
            support = {p: sorted({r["contrast_percent"] for r in by_person[p]}) for p in sorted(roster)}
            require(all(len(v) >= 2 for v in support.values()), "a participant has an empty held-out fit")
            panel[target, condition] = dict(rows=rows, contrasts=contrasts,
                participants=sorted(roster), support=support, by_contrast=by_contrast)
    return panel


def _predictions(method, panel, mode, accuracy_required=False):
    records = method.get(mode)
    require(isinstance(records, list), f"{mode} predictions required")
    expected = {(t, c, p, x) for (t, c), item in panel.items()
                for p in item["participants"] for x in item["contrasts"]}
    indexed = {}
    accuracy_present = []
    for row in records:
        key = row.get("target"), row.get("condition"), row.get("participant"), row.get("contrast_percent")
        number(row.get("contrast_percent"), "prediction contrast")
        require(key in expected and key not in indexed, f"unknown/duplicate {mode} prediction")
        target, condition, participant, contrast = key
        fit = row.get("fit_contrasts_percent")
        require(isinstance(fit, list) and fit, "nonempty fit contrast declaration required")
        fit = [number(x, "fit contrast") for x in fit]
        require(len(set(fit)) == len(fit), "duplicate fit contrast")
        available = set(panel[target, condition]["support"][participant])
        required = available - {contrast} if mode == "held_out" else available
        require(set(fit) == required, "contrast leakage or incomplete fit declaration")
        value = number(row.get("latency_ms"), "predicted latency")
        # Do not clip unconstrained linear predictions or constrain candidate law.
        accuracy = row.get("probability_correct")
        accuracy_present.append(accuracy is not None)
        if accuracy is not None:
            accuracy = number(accuracy, "predicted accuracy")
            require(0 <= accuracy <= 1, "predicted accuracy outside [0,1]")
        indexed[key] = value, accuracy
    require(set(indexed) == expected, f"{mode} must cover every participant on the global contrast grid")
    require(not any(accuracy_present) or all(accuracy_present), "partial accuracy panel")
    if accuracy_required:
        require(all(accuracy_present), "Fechner full-data accuracy companion required")
    return indexed


def score_method(method, panel, digest, reference=False):
    name = identifier(method.get("method_id"), "method ID")
    require(method.get("targets_sha256") == digest, "fixed target identity mismatch")
    require(method.get("latency_selection") == "all_responded", "original panel uses all responded trials")
    require(method.get("time_unit") == "ms" and method.get("contrast_unit") == "percent",
            "prediction units must be ms and percent")
    held = _predictions(method, panel, "held_out")
    full = _predictions(method, panel, "full_data", reference and name == "fechner")
    results = []
    for (target, condition), item in panel.items():
        folds, observed_curve, predicted_curve, observed_accuracy, predicted_accuracy = [], [], [], [], []
        for contrast in item["contrasts"]:
            observed = item["by_contrast"][contrast]
            by_person = defaultdict(list)
            for row in observed:
                by_person[row["participant"]].append(row)
            pooled = mean(row["values"][target] for row in observed)
            equal = mean(mean(row["values"][target] for row in rows) for rows in by_person.values())
            predicted = mean(held[target, condition, p, contrast][0] for p in item["participants"])
            observed_curve.append(equal)
            predicted_curve.append(mean(full[target, condition, p, contrast][0] for p in item["participants"]))
            observed_accuracy.append(mean(mean(r["correct"] for r in rows) for rows in by_person.values()))
            acc = [full[target, condition, p, contrast][1] for p in item["participants"]]
            if all(v is not None for v in acc):
                predicted_accuracy.append(mean(acc))
            error = pooled - predicted
            require(math.isfinite(error * error), "squared prediction error overflow")
            folds.append(dict(contrast_percent=contrast, observed_trials=len(observed),
                observed_participants=len(by_person), predicted_participants=len(item["participants"]),
                observed_pooled_ms=pooled, observed_participant_equal_ms=equal,
                predicted_participant_equal_ms=predicted, squared_error_ms2=error * error))
        results.append(dict(target=target, condition=condition,
            source_rmse_ms=math.sqrt(mean(f["squared_error_ms2"] for f in folds)),
            full_data_latency_r2=legacy.r_squared(observed_curve, predicted_curve),
            full_data_accuracy_r2=legacy.r_squared(observed_accuracy, predicted_accuracy) if predicted_accuracy else None,
            folds=folds))
    return dict(method_id=name, cells=results,
                fit_provenance="declarations_checked_execution_not_attested")


def evaluate(targets, submission):
    panel = prepare(targets)
    digest = target_digest(targets)
    require(submission.get("schema") == "decision-times-panel-predictions-v2", "wrong prediction schema")
    access = submission.get("access_condition")
    require(access in {"paper_data", "paper_data_author_code"}, "explicit paired access condition required")
    references = submission.get("references")
    require(isinstance(references, list) and len(references) == 3, "all three author references required")
    require({r.get("method_id") for r in references} == set(AUTHOR_MODELS), "wrong author reference panel")
    refs = [score_method(r, panel, digest, True) for r in references]
    require("candidate" in submission or "reproduction" in submission, "reproduction or improvement output required")
    candidate = score_method(submission["candidate"], panel, digest) if "candidate" in submission else None
    reproduction = None
    if "reproduction" in submission:
        methods = submission["reproduction"]
        require(isinstance(methods, list) and len(methods) == 3
                and {m.get("method_id") for m in methods} == set(AUTHOR_MODELS),
                "reproduction requires all three source models")
        reproduced = {m["method_id"]: score_method(m, panel, digest, True) for m in methods}
        differences = []
        for reference in refs:
            for ref, rep in zip(reference["cells"], reproduced[reference["method_id"]]["cells"]):
                row = dict(model=reference["method_id"], target=ref["target"], condition=ref["condition"])
                for metric in ("source_rmse_ms", "full_data_latency_r2", "full_data_accuracy_r2"):
                    row["reproduced_minus_reference_" + metric] = None if ref[metric] is None or rep[metric] is None else rep[metric] - ref[metric]
                differences.append(row)
        reproduction = dict(methods=list(reproduced.values()), differences=differences,
                            numerical_tolerance="not_admitted", reproduction_pass=None)
    deltas = []
    if candidate is not None:
        for reference in refs:
            for ref, cand in zip(reference["cells"], candidate["cells"]):
                deltas.append(dict(reference=reference["method_id"], target=ref["target"],
                    condition=ref["condition"], candidate_minus_reference_rmse_ms=cand["source_rmse_ms"] - ref["source_rmse_ms"]))
    return dict(task_id=legacy.TASK, implementation="contrast-panel-v2", targets_sha256=digest,
        purpose=targets["hmp"]["purpose"], source_revision=legacy.REVISION,
        access_condition=access,
        qualification="software_component_only", scientific_runs=0, binary_reward=None,
        primary_metric="original_contrast_left_out_rmse_ms_panel",
        targets=list(TARGETS), conditions=list(CONDITIONS),
        hmp_trial_count=len(targets["hmp"]["trials"]), behavioral_trial_count=len(targets["behavior"]["trials"]),
        references=refs, reproduction=reproduction, candidate=candidate, paired_differences=deltas,
        limits=["Target authenticity, 512 Hz HMP parity and original producing-run population lineage remain unqualified.",
                "Reference IDs do not authenticate source fitting; predictions and declared folds require independent execution receipts.",
                "RT uses its separately inventoried behavioral population; shared HMP rows are matched, not assumed complete for RT.",
                "No full-panel superiority, effect margin, multiplicity or uncertainty rule has been admitted.",
                "No aggregate score, paper win, current-SOTA claim or binary reward is assigned."])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("targets", type=Path)
    parser.add_argument("predictions", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    targets_raw, predictions_raw = args.targets.read_bytes(), args.predictions.read_bytes()
    result = evaluate(json.loads(targets_raw), json.loads(predictions_raw))
    result["input_file_sha256"] = dict(targets=hashlib.sha256(targets_raw).hexdigest(),
                                     predictions=hashlib.sha256(predictions_raw).hexdigest())
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
