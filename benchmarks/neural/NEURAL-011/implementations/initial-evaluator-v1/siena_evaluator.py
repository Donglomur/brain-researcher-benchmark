"""Complete-recording Siena evaluation; construction source, not scientific admission.

Event semantics independently reimplemented from timescoring commit
426f8d2b77974641dc9db71884e0812b249ba93b. NumPy is the only dependency.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any

import numpy as np

TASK_ID = "NEURAL-011"
CONTRACT_SHA256 = "044340155db14895d22a711e2a892261d0377603714125502e911dd7181fd0ea"
SCORING_PARAMETERS = {"tolerance_start": 30.0, "tolerance_end": 60.0,
                      "min_overlap": 0.0, "max_event_duration": 300.0,
                      "min_gap": 90.0, "scoring_hz": 10}
EEG_CHANNELS = frozenset("FP1 FP2 F3 F4 F7 F8 F9 F10 FZ FC1 FC2 FC5 FC6 C3 C4 CZ CP1 CP2 CP5 CP6 P3 P4 PZ T3 T4 T5 T6 O1 O2".split())


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def finite_number(value: Any, name: str, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, np.number)):
        raise ValueError(f"{name} must be a finite number")
    value = float(value)
    if not math.isfinite(value) or (positive and value <= 0):
        raise ValueError(f"invalid {name}")
    return value


def validate_channels(channels: list[str]) -> list[str]:
    if not isinstance(channels, list) or not channels or any(not isinstance(c, str) for c in channels):
        raise ValueError("nonempty channel names required")
    canonical = [c.strip().upper() for c in channels]
    if len(set(canonical)) != len(canonical) or any(c not in EEG_CHANNELS for c in canonical):
        raise ValueError("only unique unambiguous EEG electrodes are permitted; auxiliary/marker channels forbidden")
    return canonical


def validate_events(events: list, duration: float) -> list[tuple[float, float]]:
    if not isinstance(events, list):
        raise ValueError("events must be a list")
    result = []
    for pair in events:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise ValueError("event requires [start, end]")
        start, end = (finite_number(x, "event endpoint") for x in pair)
        if not 0 <= start < end <= duration:
            raise ValueError("event outside complete recording or empty")
        if result and start < result[-1][1]:
            raise ValueError("events must be sorted and nonoverlapping")
        result.append((start, end))
    return result


def _merge_split(events: list[tuple[float, float]]) -> list[tuple[float, float]]:
    merged = []
    for start, end in events:
        if merged and start - merged[-1][1] < SCORING_PARAMETERS["min_gap"]:
            merged[-1] = (merged[-1][0], end)
        else:
            merged.append((start, end))
    result = []
    for start, end in merged:
        while end - start > SCORING_PARAMETERS["max_event_duration"]:
            result.append((start, start + 300.0))
            start += 300.0
        result.append((start, end))
    return result


def _metrics(tp: int, fp: int, ref_count: int, duration: float) -> dict:
    return {"true_positives": tp, "false_alarms": fp, "reference_events": ref_count,
            "sensitivity": tp / ref_count if ref_count else None,
            "precision": tp / (tp + fp) if tp + fp else None,
            "event_f1": 2 * tp / (tp + fp + ref_count) if ref_count + fp else None,
            "false_alarms_per_24h": fp * 86400 / duration,
            "duration_seconds": duration}


def event_score(reference: list, prediction: list, duration: float) -> dict:
    """Pinned 10 Hz event metrics, including non-one-to-one matching.

    Original endpoints remain floats. Only mask boundaries use Python round.
    The time denominator matches the pinned scorer's rounded 10 Hz duration.
    """
    duration = finite_number(duration, "duration", True)
    n = round(duration * 10)
    if n < 1:
        raise ValueError("duration must contain at least one scoring sample")
    refs = _merge_split(validate_events(reference, duration))
    hyps = _merge_split(validate_events(prediction, duration))
    hyp_mask = np.zeros(n, dtype=bool)
    for start, end in hyps:
        hyp_mask[round(start * 10):round(end * 10)] = True
    detected_mask = np.zeros(n, dtype=bool)
    tp = 0
    for start, end in refs:
        start, end = max(0.0, start - 30.0), min(n / 10, end + 60.0)
        overlap = np.count_nonzero(hyp_mask[round(start * 10):round(end * 10)]) / 10
        if overlap / (end - start) > 1e-6:
            tp += 1
            detected_mask[round(start * 10):round(end * 10)] = True
    fp = sum(not np.any(detected_mask[round(start * 10):round(end * 10)]) for start, end in hyps)
    out = _metrics(tp, int(fp), len(refs), n / 10)
    out["processed_reference_events"] = refs
    out["processed_prediction_events"] = hyps
    return out


def scores_to_events(scores: Any, sample_rate: float, threshold: float) -> list[tuple[float, float]]:
    scores = np.asarray(scores)
    sample_rate = finite_number(sample_rate, "sample_rate", True)
    threshold = finite_number(threshold, "threshold")
    if scores.ndim != 1 or not scores.size or scores.dtype.kind not in "fiu" or not np.isfinite(scores).all():
        raise ValueError("scores must be a nonempty finite numeric vector")
    mask = scores >= threshold
    boundaries = np.diff(np.concatenate(([0], mask.astype(np.int8), [0])))
    starts, ends = np.flatnonzero(boundaries == 1), np.flatnonzero(boundaries == -1)
    return [(float(a / sample_rate), float(b / sample_rate)) for a, b in zip(starts, ends)]


def inventory() -> dict[str, dict]:
    data = json.loads(Path(__file__).with_name("source_inventory.json").read_text())
    return {r["recording_id"]: r for r in data["records"]}


def validate_manifest(manifest: dict, role: str, references: bool) -> list[dict]:
    """Require every publisher-listed recording for each selected PN patient.

    This checks declarations and source hashes, not the actual EDF payload.
    The operator must independently authenticate full payload/header equality.
    """
    if not isinstance(manifest, dict) or set(manifest) != {"schema_version", "task_id", "role", "patients", "recordings"}:
        raise ValueError("manifest has missing or unknown fields")
    if manifest["schema_version"] != 1 or manifest["task_id"] != TASK_ID or manifest["role"] != role:
        raise ValueError("manifest identity or partition mismatch")
    patients = manifest["patients"]
    source = inventory()
    source_patients = {r["patient_id"] for r in source.values()}
    if not isinstance(patients, list) or not patients or any(not isinstance(p, str) for p in patients):
        raise ValueError("patients must be a nonempty list")
    if len(patients) != len(set(patients)) or not set(patients) <= source_patients:
        raise ValueError("unknown or duplicate patient")
    rows = manifest["recordings"]
    if not isinstance(rows, list) or not rows:
        raise ValueError("complete recordings required")
    expected = {key for key, r in source.items() if r["patient_id"] in patients}
    seen = set()
    required = {"recording_id", "patient_id", "sample_rate", "n_samples", "source_sha256", "channels"}
    if references:
        required.add("reference_events")
    for row in rows:
        if not isinstance(row, dict) or set(row) != required:
            raise ValueError("recording has missing/unknown fields or exposed reference labels")
        rid = row["recording_id"]
        if not isinstance(rid, str) or rid not in expected or rid in seen:
            raise ValueError("unknown, duplicate, or wrong-patient recording")
        seen.add(rid)
        if row["patient_id"] != source[rid]["patient_id"] or row["source_sha256"] != source[rid]["source_sha256"]:
            raise ValueError("publisher recording identity/hash mismatch")
        fs = finite_number(row["sample_rate"], "sample_rate", True)
        count = row["n_samples"]
        if isinstance(count, bool) or not isinstance(count, int) or count < 2:
            raise ValueError("n_samples must be an integer >= 2")
        if round(count / fs * 10) < 1:
            raise ValueError("recording too short for scoring")
        validate_channels(row["channels"])
        if references:
            validate_events(row["reference_events"], count / fs)
    if seen != expected:
        raise ValueError("missing complete recording(s) for selected patient")
    return rows


def _mean_defined(values: list) -> float | None:
    values = [x for x in values if x is not None]
    return float(np.mean(values)) if values else None


def _patient_summary(recording_scores: list[dict]) -> dict:
    grouped = {}
    for row in recording_scores:
        grouped.setdefault(row["patient_id"], []).append(row)
    out = {}
    for patient, rows in sorted(grouped.items()):
        out[patient] = _metrics(sum(r["true_positives"] for r in rows),
                                sum(r["false_alarms"] for r in rows),
                                sum(r["reference_events"] for r in rows),
                                sum(r["duration_seconds"] for r in rows))
    return out


def score_manifest(manifest: dict, predictions: dict, threshold: float, role: str = "test") -> dict:
    rows = validate_manifest(manifest, role, references=True)
    threshold = finite_number(threshold, "threshold")
    if not isinstance(predictions, dict) or set(predictions) != {r["recording_id"] for r in rows}:
        raise ValueError("predictions must contain every and only selected recording ID")
    results = []
    for row in rows:
        scores = np.asarray(predictions[row["recording_id"]])
        if scores.ndim != 1 or len(scores) != row["n_samples"]:
            raise ValueError("per-sample scores must cover the complete recording")
        events = scores_to_events(scores, row["sample_rate"], threshold)
        result = event_score(row["reference_events"], events, row["n_samples"] / row["sample_rate"])
        result.update({"recording_id": row["recording_id"], "patient_id": row["patient_id"],
                       "raw_prediction_events": events, "constant_scores": bool(np.all(scores == scores[0]))})
        results.append(result)
    patients = _patient_summary(results)
    return {"patient_macro_event_f1": _mean_defined([r["event_f1"] for r in patients.values()]),
            "patient_macro_sensitivity": _mean_defined([r["sensitivity"] for r in patients.values()]),
            "patient_macro_false_alarms_per_24h": _mean_defined([r["false_alarms_per_24h"] for r in patients.values()]),
            "pooled_false_alarms_per_24h": sum(r["false_alarms"] for r in patients.values()) * 86400 / sum(r["duration_seconds"] for r in patients.values()),
            "f1_defined_patients": [p for p, r in patients.items() if r["event_f1"] is not None],
            "f1_undefined_patients": [p for p, r in patients.items() if r["event_f1"] is None],
            "sensitivity_undefined_patients": [p for p, r in patients.items() if r["sensitivity"] is None],
            "patients": patients, "recordings": results}


def paired_bootstrap(first: dict, second: dict, *, draws: int = 2000, seed: int = 0) -> dict:
    """Prospective paired PN-patient bootstrap of event-F1 differences."""
    if set(first["patients"]) != set(second["patients"]):
        raise ValueError("paired comparisons require identical patients")
    if not isinstance(draws, int) or isinstance(draws, bool) or draws < 1:
        raise ValueError("positive bootstrap draws required")
    patients = [p for p in sorted(first["patients"]) if first["patients"][p]["event_f1"] is not None and second["patients"][p]["event_f1"] is not None]
    excluded = sorted(set(first["patients"]) - set(patients))
    if len(patients) < 2:
        return {"status": "insufficient_independent_patients", "patients": patients, "excluded": excluded}
    delta = np.array([first["patients"][p]["event_f1"] - second["patients"][p]["event_f1"] for p in patients])
    rng = np.random.default_rng(seed)
    means = [float(np.mean(delta[rng.integers(0, len(delta), len(delta))])) for _ in range(draws)]
    return {"status": "descriptive_public_development", "estimator": "paired patient-macro F1 difference",
            "difference": float(np.mean(delta)), "percentile_95_interval": np.quantile(means, [0.025, 0.975]).tolist(),
            "patients": patients, "excluded": excluded, "draws": draws, "seed": seed}


def validate_frozen(frozen: dict) -> None:
    required = {"schema_version", "task_id", "method", "training_patients", "training_manifest_sha256",
                "threshold", "channels", "parameters", "scoring_parameters", "artifact_sha256"}
    if not isinstance(frozen, dict) or set(frozen) != required:
        raise ValueError("invalid frozen artifact fields")
    if frozen["schema_version"] != 1 or frozen["task_id"] != TASK_ID or frozen["method"] not in {"line_length_v1", "timing_only_v1"}:
        raise ValueError("unknown frozen method")
    if frozen["scoring_parameters"] != SCORING_PARAMETERS:
        raise ValueError("scoring policy mismatch")
    finite_number(frozen["threshold"], "threshold")
    validate_channels(frozen["channels"])
    patients = frozen["training_patients"]
    if not isinstance(patients, list) or not patients or any(not isinstance(p, str) for p in patients) or len(set(patients)) != len(patients) or not set(patients) <= {r["patient_id"] for r in inventory().values()}:
        raise ValueError("invalid training patient identities")
    if not re.fullmatch(r"[0-9a-f]{64}", frozen["training_manifest_sha256"]):
        raise ValueError("invalid training manifest hash")
    if digest({k: v for k, v in frozen.items() if k != "artifact_sha256"}) != frozen["artifact_sha256"]:
        raise ValueError("frozen artifact hash mismatch")


def evaluate(manifest: dict, predictions: dict, frozen: dict,
             comparator: tuple[dict, dict] | None = None) -> dict:
    validate_frozen(frozen)
    validate_manifest(manifest, "test", True)
    if set(manifest["patients"]) & set(frozen["training_patients"]):
        raise ValueError("training/evaluation patient leakage")
    if any(validate_channels(r["channels"]) != frozen["channels"] for r in manifest["recordings"]):
        raise ValueError("locked channel recipe mismatch")
    result = score_manifest(manifest, predictions, frozen["threshold"])
    result.update({"schema_version": 1, "task_id": TASK_ID, "scientific_qualification": "unknown",
                   "status": "engineering_evaluation_only", "data_scope": "public_development_only",
                   "contract_sha256": CONTRACT_SHA256, "reference_manifest_sha256": digest(manifest),
                   "frozen_artifact_sha256": frozen["artifact_sha256"], "scoring_parameters": SCORING_PARAMETERS,
                   "constant_recordings": [r["recording_id"] for r in result["recordings"] if r["constant_scores"]]})
    if comparator is not None:
        comparator_predictions, comparator_frozen = comparator
        validate_frozen(comparator_frozen)
        if (comparator_frozen["training_manifest_sha256"] != frozen["training_manifest_sha256"]
                or comparator_frozen["training_patients"] != frozen["training_patients"]):
            raise ValueError("paired comparators require the identical training manifest and patient set")
        comparison = evaluate(manifest, comparator_predictions, comparator_frozen)
        result["paired_comparison"] = paired_bootstrap(result, comparison)
        result["comparator_artifact_sha256"] = comparator_frozen["artifact_sha256"]
    return result


def _clock(text: str) -> int:
    matches = list(re.finditer(r"(?<!\d)(\d{1,2})[.:](\d{2})[.:](\d{2})(?!\d)", text))
    if not matches:
        raise ValueError("unrecognized Siena clock")
    # The pinned parser's greedy prefix selects the final clock. This matters
    # for PN10-2's alternative offset and PN10-3's clinical/electrical onset.
    match = matches[-1]
    h, m, s = map(int, match.groups())
    if h > 23 or m > 59 or s > 59:
        raise ValueError("invalid Siena clock")
    return h * 3600 + m * 60 + s


def parse_siena_annotations(text: str, recording_id: str, duration: float) -> dict:
    """Parse standard and documented exceptional Siena annotation blocks.

    An absent file mention fails closed; an unmentioned file is not assumed
    seizure-free. Durations must come from independently verified EDF headers.
    """
    duration = finite_number(duration, "duration", True)
    if recording_id not in inventory():
        raise ValueError("unknown Siena recording")
    filename = recording_id.split("/")[1]
    aliases = {"PN01-1.edf": "PN01.edf", "PN06-1.edf": "PNO6-1.edf",
               "PN06-2.edf": "PNO6-2.edf", "PN06-4.edf": "PNO6-4.edf", "PN11-1.edf": "PN11-.edf"}
    expected = aliases.get(filename, filename)
    active = False
    registration = None
    pending = None
    found = False
    events, corrections = [], []
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("File name:"):
            if pending is not None:
                raise ValueError("unmatched event start before new file block")
            active = line.split(":", 1)[1].strip() == expected
            if active:
                found = True
            continue
        if not active:
            continue
        if "Registration start time:" in line:
            if filename == "PN10-7.8.9.edf" and "1 6.49.25" in line:
                line = line.replace("1 6.49.25", "16.49.25")
                corrections.append("PN10-7.8.9 registration clock spacing corrected")
            registration = _clock(line)
        elif re.search(r"(?:Seizure start time|Start time):", line):
            if registration is None or pending is not None:
                raise ValueError("missing registration clock or unmatched event start")
            pending = (_clock(line) - registration) % 86400
            if len(re.findall(r"\d{1,2}[.:]\d{2}[.:]\d{2}", line)) > 1:
                corrections.append("multiple onset clocks: final clock selected per pinned parser")
        elif re.search(r"(?:Seizure end time|End time):", line):
            if registration is None or pending is None:
                raise ValueError("unmatched event end")
            if filename == "PN00-3.edf":
                line = "Seizure end time: 18.29.29"
                corrections.append("PN00-3 end clock corrected to18.29.29 per pinned parser")
            end = (_clock(line) - registration) % 86400
            if len(re.findall(r"\d{1,2}[.:]\d{2}[.:]\d{2}", line)) > 1:
                corrections.append("multiple offset clocks: final clock selected per pinned parser")
            events.append((pending, end))
            pending = None
    if not found or pending is not None or not events:
        raise ValueError("missing or incomplete file annotation; no silent background inference")
    events = validate_events(events, duration)
    if expected != filename:
        corrections.append(f"annotation filename alias {expected}")
    return {"recording_id": recording_id, "events": events, "corrections": corrections,
            "annotation_text_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "duration_seconds": duration}


def _load_arrays(path: str) -> dict:
    with np.load(path, allow_pickle=False) as archive:
        return {key: archive[key] for key in archive.files}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    annotation = sub.add_parser("annotations")
    annotation.add_argument("text")
    annotation.add_argument("recording_id")
    annotation.add_argument("duration", type=float)
    annotation.add_argument("output")
    scorer = sub.add_parser("evaluate")
    scorer.add_argument("manifest")
    scorer.add_argument("predictions")
    scorer.add_argument("frozen")
    scorer.add_argument("output")
    scorer.add_argument("--comparator-predictions")
    scorer.add_argument("--comparator-frozen")
    args = parser.parse_args(argv)
    if args.command == "annotations":
        result = parse_siena_annotations(Path(args.text).read_text(), args.recording_id, args.duration)
    else:
        if bool(args.comparator_predictions) != bool(args.comparator_frozen):
            parser.error("both comparator inputs required")
        comparison = None
        if args.comparator_predictions:
            comparison = (_load_arrays(args.comparator_predictions), json.loads(Path(args.comparator_frozen).read_text()))
        result = evaluate(json.loads(Path(args.manifest).read_text()), _load_arrays(args.predictions),
                          json.loads(Path(args.frozen).read_text()), comparison)
    Path(args.output).write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
