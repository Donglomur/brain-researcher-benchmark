"""Operator-only complete Siena leave-one-person-out evaluation.

This prospective protocol orchestrates the preserved selected-patient scorer.
Complete declared support does not authenticate EDFs, annotations or fitting.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path


OCCUPANCY_SHA256 = "2cc993e9860c6ace1e6ed82689197f0302d5f4b580539fc9f4915bcae4cc317e"


def _load_occupancy():
    path = Path(__file__).resolve().parent.parent / "occupancy-evaluator-v2" / "siena_occupancy.py"
    if hashlib.sha256(path.read_bytes()).hexdigest() != OCCUPANCY_SHA256:
        raise RuntimeError("preserved occupancy scorer hash mismatch")
    spec = importlib.util.spec_from_file_location("_neural011_lopo_occupancy", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


occupancy = _load_occupancy()
native = occupancy.native


def _recipe(frozen: dict) -> dict:
    """Bind fixed settings across folds; allow documented train-fitted values."""
    native.validate_frozen(frozen)
    parameters = frozen["parameters"]
    if not isinstance(parameters, dict):
        raise ValueError("frozen parameters must be a dictionary")
    fitted = "scales" if frozen["method"] == "line_length_v1" else "rates"
    fixed_keys = ({"window_seconds", "scale_floor", "signal_unit"}
                  if fitted == "scales" else {"bin_seconds", "unobserved_bin_score"})
    if set(parameters) != fixed_keys | {fitted, "threshold_selection"}:
        raise ValueError("complete known reference recipe required for LOPO pooling")
    selection = parameters["threshold_selection"]
    if (not isinstance(selection, dict) or set(selection) != {"rule", "training_summary"}
            or not isinstance(selection["rule"], str) or not selection["rule"]):
        raise ValueError("declared training-only threshold selection rule required")
    values = parameters[fitted]
    if not isinstance(values, list) or not values:
        raise ValueError("nonempty fitted reference values required")
    values = [native.finite_number(x, fitted) for x in values]
    if fitted == "scales":
        if len(values) != len(frozen["channels"]) or any(x <= 0 for x in values):
            raise ValueError("positive per-channel training scales required")
        expected = {"window_seconds": 1.0, "scale_floor": 1e-12, "signal_unit": "microvolts"}
    else:
        if any(x < 0 or x > 1 for x in values):
            raise ValueError("timing rates must be probabilities")
        expected = {"bin_seconds": 60.0, "unobserved_bin_score": 0.0}
    if any(parameters[key] != value for key, value in expected.items()):
        raise ValueError("unknown fixed reference recipe")
    return {"method": frozen["method"], "channels": list(frozen["channels"]),
            "parameters": expected, "threshold_selection_rule": selection["rule"],
            "scoring_parameters": dict(frozen["scoring_parameters"])}


def _summary(results: list[dict]) -> dict:
    patients, recordings = {}, []
    for result in results:
        patients.update(result["patients"])
        recordings.extend(result["recordings"])
    patients = dict(sorted(patients.items()))
    recordings.sort(key=lambda row: row["recording_id"])
    duration = math.fsum(row["duration_seconds"] for row in patients.values())
    observed = math.fsum(row["observed_duration_seconds"] for row in patients.values())
    positive = math.fsum(row["predicted_positive_seconds"] for row in patients.values())
    undefined_f1 = [p for p, row in patients.items() if row["event_f1"] is None]
    return {
        "patient_macro_event_f1": native._mean_defined([row["event_f1"] for row in patients.values()]),
        "patient_macro_sensitivity": native._mean_defined([row["sensitivity"] for row in patients.values()]),
        "patient_macro_false_alarms_per_24h": native._mean_defined([
            row["false_alarms_per_24h"] for row in patients.values()]),
        "pooled_false_alarms_per_24h": sum(row["false_alarms"] for row in patients.values()) * 86400 / duration,
        "patient_macro_predicted_positive_time_fraction": math.fsum(
            row["predicted_positive_time_fraction"] for row in patients.values()) / len(patients),
        "pooled_predicted_positive_time_fraction": positive / observed,
        "duration_seconds": duration,
        "observed_duration_seconds": observed,
        "predicted_positive_seconds": positive,
        "f1_defined_patients": [p for p in patients if p not in undefined_f1],
        "f1_undefined_patients": undefined_f1,
        "sensitivity_undefined_patients": [p for p, row in patients.items() if row["sensitivity"] is None],
        "occupancy_patients": list(patients),
        "occupancy_undefined_patients": [],
        "full_cohort_event_f1_defined": not undefined_f1,
        "patients": patients,
        "recordings": recordings,
    }


def evaluate_folds(folds: list[dict]) -> dict:
    """Score exactly14 held-person folds using complete41-recording support.

    Each fold has manifest, predictions and frozen entries. Both comparator
    entries must occur in every fold or none. All records remain operator-private.
    """
    source = native.inventory()
    roster = sorted({row["patient_id"] for row in source.values()})
    if len(roster) != 14 or len(source) != 41:
        raise RuntimeError("preserved Siena inventory changed")
    if not isinstance(folds, list) or len(folds) != len(roster):
        raise ValueError("exactly14 leave-one-person-out folds required")
    base = {"manifest", "predictions", "frozen"}
    paired_fields = {"comparator_predictions", "comparator_frozen"}
    seen, recipes, comparator_recipes = set(), [], []
    paired = None
    # Validate outer-study metadata and recipes before event scoring. Prediction
    # vectors retain the preserved scorer's per-fold validation on evaluation.
    for fold in folds:
        if not isinstance(fold, dict) or set(fold) not in (base, base | paired_fields):
            raise ValueError("invalid fold fields or incomplete comparator")
        has_comparator = paired_fields <= set(fold)
        if paired is not None and has_comparator != paired:
            raise ValueError("comparators must cover every fold or none")
        paired = has_comparator
        manifest = fold["manifest"]
        native.validate_manifest(manifest, "test", references=True)
        if len(manifest["patients"]) != 1:
            raise ValueError("each fold must hold exactly one patient")
        patient = manifest["patients"][0]
        if patient in seen:
            raise ValueError("duplicate held-out patient")
        seen.add(patient)
        expected_training = set(roster) - {patient}
        for key, descriptors in (("frozen", recipes), ("comparator_frozen", comparator_recipes)):
            if key not in fold:
                continue
            frozen = fold[key]
            descriptors.append(_recipe(frozen))
            if set(frozen["training_patients"]) != expected_training:
                raise ValueError("LOPO training must declare exactly the other13 patients")
            if any(native.validate_channels(row["channels"]) != frozen["channels"]
                   for row in manifest["recordings"]):
                raise ValueError("locked fold channel recipe mismatch")
        if has_comparator:
            first, second = fold["frozen"], fold["comparator_frozen"]
            if (first["training_manifest_sha256"] != second["training_manifest_sha256"]
                    or first["training_patients"] != second["training_patients"]):
                raise ValueError("paired folds require identical training manifest and patients")
    if seen != set(roster):
        raise ValueError("every source patient must be held out exactly once")
    if any(recipe != recipes[0] for recipe in recipes[1:]):
        raise ValueError("candidate fixed recipe must match across folds")
    if paired and any(recipe != comparator_recipes[0] for recipe in comparator_recipes[1:]):
        raise ValueError("comparator fixed recipe must match across folds")
    candidate_results, comparator_results, controls, identities = [], [], [], []
    for fold in sorted(folds, key=lambda value: value["manifest"]["patients"][0]):
        manifest, frozen = fold["manifest"], fold["frozen"]
        result = occupancy.evaluate(manifest, fold["predictions"], frozen)
        candidate_results.append(result)
        controls.append(result["constant_controls"])
        identity = {"held_patient": manifest["patients"][0],
                    "reference_manifest_sha256": result["reference_manifest_sha256"],
                    "training_manifest_sha256": frozen["training_manifest_sha256"],
                    "frozen_artifact_sha256": frozen["artifact_sha256"]}
        if paired:
            other = occupancy.evaluate(manifest, fold["comparator_predictions"], fold["comparator_frozen"])
            comparator_results.append(other)
            identity["comparator_frozen_artifact_sha256"] = fold["comparator_frozen"]["artifact_sha256"]
        identities.append(identity)
    result = _summary(candidate_results)
    result.update({
        "schema_version": 1, "task_id": "NEURAL-011",
        "protocol": "prospective_complete_leave_one_patient_out_v1",
        "status": "engineering_evaluation_only", "scientific_qualification": "unknown",
        "data_scope": "public_development_only", "fold_count": 14,
        "source_patient_count": 14, "source_recording_count": 41,
        "complete_declared_outer_coverage": True,
        "source_authentication_established": False,
        "fitting_provenance_established": False,
        "candidate_recipe": recipes[0], "folds": identities,
        "occupancy_scorer_sha256": OCCUPANCY_SHA256,
        "constant_controls": {name: _summary([row[name] for row in controls])
                              for name in ("always_negative", "always_positive")},
        "limits": [
            "Training patient membership and manifest hashes are declarations, not independently verified fitting provenance.",
            "EDFs, calibration, clock origins and complete annotations still require independent authentication.",
            "Native event-F1 means exclude undefined patient endpoints and list exclusions; full support is reported separately.",
            "Overlapping training folds limit interpretation of the descriptive paired patient bootstrap.",
            "Only existing line-length/timing reference artifacts are admitted; no arbitrary participant condition or CHB transfer.",
        ],
    })
    if paired:
        other = _summary(comparator_results)
        result["comparator"] = other
        result["comparator_recipe"] = comparator_recipes[0]
        result["paired_comparison"] = native.paired_bootstrap(result, other)
        result["full_cohort_paired_event_f1_defined"] = (
            result["full_cohort_event_f1_defined"] and other["full_cohort_event_f1_defined"])
        deltas = {p: result["patients"][p]["predicted_positive_time_fraction"]
                  - other["patients"][p]["predicted_positive_time_fraction"] for p in roster}
        result["paired_predicted_positive_time_fraction"] = {
            "status": "descriptive_public_development", "patients": roster, "excluded": [],
            "candidate_minus_comparator_by_patient": deltas,
            "patient_macro_difference": math.fsum(deltas.values()) / len(roster),
        }
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("study", help="operator-private JSON listing fold input paths")
    parser.add_argument("output", help="operator-private report including reference events")
    args = parser.parse_args(argv)
    study_path = Path(args.study).resolve()
    study = json.loads(study_path.read_text())
    if (not isinstance(study, dict) or set(study) != {"schema_version", "task_id", "folds"}
            or study["schema_version"] != 1 or study["task_id"] != "NEURAL-011"
            or not isinstance(study["folds"], list)):
        raise ValueError("invalid LOPO study document")
    folds = []
    for row in study["folds"]:
        if not isinstance(row, dict):
            raise ValueError("fold paths must be a dictionary")
        loaded = {}
        for key, value in row.items():
            if key not in {"manifest", "predictions", "frozen", "comparator_predictions", "comparator_frozen"}:
                raise ValueError("unknown fold input")
            if not isinstance(value, str) or not value:
                raise ValueError("fold paths must be nonempty strings")
            path = study_path.parent / value
            loaded[key] = native._load_arrays(str(path)) if key.endswith("predictions") else json.loads(path.read_text())
        folds.append(loaded)
    result = evaluate_folds(folds)
    Path(args.output).write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
