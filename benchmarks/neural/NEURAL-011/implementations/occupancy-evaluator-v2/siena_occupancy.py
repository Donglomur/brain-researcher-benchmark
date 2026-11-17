"""Operator-only Siena event evaluation with complete-recording alarm occupancy.

The preserved v1 evaluator remains the source of event semantics and validation.
Occupancy is a prospective companion, not a replacement endpoint or clinical
qualification. No participant access mode is established by this module.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path

import numpy as np


PREDECESSOR_PINS = {
    "siena_evaluator.py": "de9f34b9d9399ae34210e55d39047c6ab1f4371d345c68ba15846c839d05aa16",
    "source_inventory.json": "4d4ae5ae132d851bea2a2388965dbc0b528e533b4f9cbea97e5822ab660203ea",
}
COMPANION_PARAMETERS = {
    "name": "predicted_positive_time_fraction_v1",
    "positive_rule": "score >= finite-float-normalized frozen threshold, matching native scorer",
    "sample_support": "[i/sample_rate, (i+1)/sample_rate)",
    "preprocessing": "none; before event merging, splitting, tolerance or 10 Hz rounding",
    "recording_denominator": "n_samples/sample_rate seconds",
    "patient_aggregation": "sum positive seconds / sum observed seconds across all patient recordings",
    "macro_aggregation": "equal mean over every selected patient, including undefined event-F1 patients",
    "pooled_aggregation": "sum positive seconds / sum observed seconds across all selected recordings",
}


def _load_predecessor():
    folder = Path(__file__).resolve().parent.parent / "initial-evaluator-v1"
    for filename, expected in PREDECESSOR_PINS.items():
        if hashlib.sha256((folder / filename).read_bytes()).hexdigest() != expected:
            raise RuntimeError(f"preserved predecessor hash mismatch: {filename}")
    spec = importlib.util.spec_from_file_location("_neural011_occupancy_predecessor", folder / "siena_evaluator.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


native = _load_predecessor()


def _occupancy(manifest: dict, predictions: dict, threshold: float) -> dict:
    """Calculate burdens only after native validation has accepted all vectors."""
    # Match native scores_to_events normalization even for integers beyond the
    # exact float range; otherwise event and occupancy decisions can disagree.
    threshold = native.finite_number(threshold, "threshold")
    recordings, grouped = {}, {}
    for row in manifest["recordings"]:
        rid = row["recording_id"]
        positive_samples = int(np.count_nonzero(np.asarray(predictions[rid]) >= threshold))
        duration = row["n_samples"] / row["sample_rate"]
        positive_seconds = positive_samples / row["sample_rate"]
        recordings[rid] = {
            "observed_duration_seconds": duration,
            "predicted_positive_samples": positive_samples,
            "predicted_positive_seconds": positive_seconds,
            "predicted_positive_time_fraction": positive_samples / row["n_samples"],
        }
        grouped.setdefault(row["patient_id"], []).append(recordings[rid])
    patients = {}
    for patient, rows in sorted(grouped.items()):
        duration = math.fsum(r["observed_duration_seconds"] for r in rows)
        positive_seconds = math.fsum(r["predicted_positive_seconds"] for r in rows)
        patients[patient] = {
            "observed_duration_seconds": duration,
            "predicted_positive_seconds": positive_seconds,
            "predicted_positive_time_fraction": positive_seconds / duration,
        }
    duration = math.fsum(r["observed_duration_seconds"] for r in patients.values())
    positive_seconds = math.fsum(r["predicted_positive_seconds"] for r in patients.values())
    return {
        "recordings": recordings,
        "patients": patients,
        "occupancy_patients": sorted(patients),
        "occupancy_undefined_patients": [],
        "observed_duration_seconds": duration,
        "predicted_positive_seconds": positive_seconds,
        "patient_macro_predicted_positive_time_fraction": math.fsum(
            r["predicted_positive_time_fraction"] for r in patients.values()) / len(patients),
        "pooled_predicted_positive_time_fraction": positive_seconds / duration,
    }


def _attach_occupancy(result: dict, occupancy: dict) -> dict:
    for row in result["recordings"]:
        row.update(occupancy["recordings"][row["recording_id"]])
    for patient, row in result["patients"].items():
        row.update(occupancy["patients"][patient])
    result.update({key: value for key, value in occupancy.items() if key not in {"recordings", "patients"}})
    return result


def score_manifest(manifest: dict, predictions: dict, threshold: float, role: str = "test") -> dict:
    """Retain v1 event metrics and add exact, unsmoothed score-grid occupancy."""
    result = native.score_manifest(manifest, predictions, threshold, role)
    return _attach_occupancy(result, _occupancy(manifest, predictions, threshold))


def constant_controls(manifest: dict) -> dict:
    """Score predeclared always-negative/positive decisions on identical support.

    Broadcast arrays avoid allocating a separate full score vector for controls.
    The native scorer still allocates its ordinary 10 Hz scoring masks.
    """
    native.validate_manifest(manifest, "test", references=True)
    controls = {}
    for name, value in (("always_negative", 0.0), ("always_positive", 1.0)):
        predictions = {r["recording_id"]: np.broadcast_to(np.array(value), (r["n_samples"],))
                       for r in manifest["recordings"]}
        controls[name] = score_manifest(manifest, predictions, 0.5)
        controls[name]["control_policy"] = "fixed decisions on complete support; no fitting or selection"
    return controls


def evaluate(manifest: dict, predictions: dict, frozen: dict,
             comparator: tuple[dict, dict] | None = None) -> dict:
    """Validate the existing frozen references and emit mandatory burden controls."""
    result = native.evaluate(manifest, predictions, frozen, comparator)
    occupancy = _occupancy(manifest, predictions, frozen["threshold"])
    _attach_occupancy(result, occupancy)
    result["companion"] = {
        "implementation": "occupancy-evaluator-v2",
        "parameters": dict(COMPANION_PARAMETERS),
        "predecessor_sha256": dict(PREDECESSOR_PINS),
        "scope": "companion software; authentic signal qualification not established by implementation",
    }
    result["constant_controls"] = constant_controls(manifest)
    if comparator is not None:
        comparator_predictions, comparator_frozen = comparator
        other = _occupancy(manifest, comparator_predictions, comparator_frozen["threshold"])
        result["paired_predicted_positive_time_fraction"] = {
            "status": "descriptive_public_development",
            "patients": occupancy["occupancy_patients"],
            "excluded": [],
            "candidate_minus_comparator_by_patient": {
                p: occupancy["patients"][p]["predicted_positive_time_fraction"]
                - other["patients"][p]["predicted_positive_time_fraction"]
                for p in occupancy["occupancy_patients"]
            },
            "patient_macro_difference": occupancy["patient_macro_predicted_positive_time_fraction"]
            - other["patient_macro_predicted_positive_time_fraction"],
            "candidate_patient_macro": occupancy["patient_macro_predicted_positive_time_fraction"],
            "comparator_patient_macro": other["patient_macro_predicted_positive_time_fraction"],
            "comparator_occupancy": other,
        }
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest")
    parser.add_argument("predictions")
    parser.add_argument("frozen")
    parser.add_argument("output")
    parser.add_argument("--comparator-predictions")
    parser.add_argument("--comparator-frozen")
    args = parser.parse_args(argv)
    if bool(args.comparator_predictions) != bool(args.comparator_frozen):
        parser.error("both comparator inputs required")
    comparator = None
    if args.comparator_predictions:
        comparator = (native._load_arrays(args.comparator_predictions),
                      json.loads(Path(args.comparator_frozen).read_text()))
    result = evaluate(json.loads(Path(args.manifest).read_text()),
                      native._load_arrays(args.predictions),
                      json.loads(Path(args.frozen).read_text()), comparator)
    Path(args.output).write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
