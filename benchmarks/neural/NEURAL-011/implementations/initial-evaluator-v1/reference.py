"""Prospective train-only causal line-length and timing-only comparators.

These transparent controls are original benchmark construction choices, not
the Siena authors' detector and not scientifically qualified references.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from siena_evaluator import (SCORING_PARAMETERS, TASK_ID, digest, finite_number,
                             score_manifest, validate_channels, validate_frozen,
                             validate_manifest, _load_arrays)


def _signals(rows: list[dict], signals: dict) -> dict:
    if not isinstance(signals, dict) or set(signals) != {r["recording_id"] for r in rows}:
        raise ValueError("signal array IDs must exactly match complete recordings")
    arrays = {}
    for r in rows:
        x = np.asarray(signals[r["recording_id"]])
        if x.shape != (r["n_samples"], len(r["channels"])) or x.dtype.kind not in "fiu" or not np.isfinite(x).all():
            raise ValueError("finite complete sample-by-EEG-channel array required")
        arrays[r["recording_id"]] = x.astype(np.float64, copy=False)
    return arrays


def _line_length(x: np.ndarray, fs: float, scales: list[float]) -> np.ndarray:
    """Trailing one-second mean absolute difference; no future samples."""
    scales = np.asarray(scales, dtype=float)
    if scales.shape != (x.shape[1],) or not np.isfinite(scales).all() or np.any(scales <= 0):
        raise ValueError("invalid frozen training scales")
    window = max(1, round(fs))
    differences = np.abs(np.diff(x, axis=0, prepend=x[:1]))
    cumulative = np.cumsum(differences, axis=0)
    sums = cumulative.copy()
    if len(x) > window:
        sums[window:] -= cumulative[:-window]
    denominators = np.minimum(np.arange(len(x)) + 1, window)
    scores = np.median(sums / denominators[:, None] / scales[None, :], axis=1)
    if not np.isfinite(scores).all():
        raise ValueError("signal dynamic range overflow")
    return scores


def _timing_scores(row: dict, rates: list[float], bin_seconds: float) -> np.ndarray:
    indices = np.floor(np.arange(row["n_samples"]) / row["sample_rate"] / bin_seconds).astype(int)
    scores = np.zeros(row["n_samples"], dtype=float)
    available = indices < len(rates)
    scores[available] = np.asarray(rates)[indices[available]]
    return scores


def _threshold(manifest: dict, predictions: dict) -> tuple[float, dict]:
    values = np.concatenate(list(predictions.values()))
    # Freeze the candidate rule before observations. Select using training only.
    candidates = np.unique(np.concatenate((np.quantile(values, np.linspace(0, 1, 65)),
                                           [np.nextafter(values.max(), np.inf)])))
    if not np.isfinite(candidates).all():
        raise ValueError("threshold candidate overflow")
    best = None
    for threshold in candidates:
        score = score_manifest(manifest, predictions, float(threshold), role="train")
        f1 = score["patient_macro_event_f1"]
        sensitivity = score["patient_macro_sensitivity"]
        key = (f1 if f1 is not None else -1.0,
               -score["patient_macro_false_alarms_per_24h"],
               sensitivity if sensitivity is not None else -1.0, float(threshold))
        if best is None or key > best[0]:
            best = (key, float(threshold), score)
    return best[1], {"patient_macro_event_f1": best[2]["patient_macro_event_f1"],
                     "patient_macro_false_alarms_per_24h": best[2]["patient_macro_false_alarms_per_24h"],
                     "candidate_count": len(candidates)}


def fit(manifest: dict, signals: dict | None, method: str = "line_length_v1") -> dict:
    rows = validate_manifest(manifest, "train", references=True)
    channels = validate_channels(rows[0]["channels"])
    if any(validate_channels(r["channels"]) != channels for r in rows):
        raise ValueError("fixed common EEG channel order required")
    if method == "line_length_v1":
        arrays = _signals(rows, signals)
        total = np.zeros(len(channels), dtype=float)
        count = 0
        for x in arrays.values():
            total += np.abs(np.diff(x, axis=0)).sum(axis=0)
            count += len(x) - 1
        scales = np.maximum(total / count, 1e-12)
        if not np.isfinite(scales).all():
            raise ValueError("training scale overflow")
        parameters = {"scales": scales.tolist(), "window_seconds": 1.0,
                      "scale_floor": 1e-12, "signal_unit": "microvolts"}
        predictions = {r["recording_id"]: _line_length(arrays[r["recording_id"]], r["sample_rate"], scales) for r in rows}
    elif method == "timing_only_v1":
        if signals is not None:
            raise ValueError("timing-only comparator accepts no neural arrays")
        bin_seconds = 60.0
        bins = max(int(np.floor((r["n_samples"] - 1) / r["sample_rate"] / bin_seconds)) + 1 for r in rows)
        exposure, ictal = np.zeros(bins), np.zeros(bins)
        for r in rows:
            indices = np.floor(np.arange(r["n_samples"]) / r["sample_rate"] / bin_seconds).astype(int)
            mask = np.zeros(r["n_samples"], dtype=bool)
            for start, end in r["reference_events"]:
                mask[round(start * r["sample_rate"]):round(end * r["sample_rate"])] = True
            exposure += np.bincount(indices, minlength=bins) / r["sample_rate"]
            ictal += np.bincount(indices, weights=mask, minlength=bins) / r["sample_rate"]
        rates = np.divide(ictal, exposure, out=np.zeros_like(ictal), where=exposure > 0)
        parameters = {"bin_seconds": bin_seconds, "rates": rates.tolist(), "unobserved_bin_score": 0.0}
        predictions = {r["recording_id"]: _timing_scores(r, rates, bin_seconds) for r in rows}
    else:
        raise ValueError("unknown comparator method")
    threshold, training_summary = _threshold(manifest, predictions)
    parameters["threshold_selection"] = {"rule": "65 pooled-score quantiles plus above-maximum; maximize training patient-macro F1; ties lower FA24 then higher sensitivity then higher threshold",
                                         "training_summary": training_summary}
    artifact = {"schema_version": 1, "task_id": TASK_ID, "method": method,
                "training_patients": sorted(manifest["patients"]),
                "training_manifest_sha256": digest(manifest), "threshold": threshold,
                "channels": channels, "parameters": parameters,
                "scoring_parameters": SCORING_PARAMETERS}
    artifact["artifact_sha256"] = digest(artifact)
    return artifact


def predict(manifest: dict, signals: dict | None, artifact: dict) -> dict:
    validate_frozen(artifact)
    rows = validate_manifest(manifest, "test", references=False)
    if set(manifest["patients"]) & set(artifact["training_patients"]):
        raise ValueError("training/evaluation patient leakage")
    if any(validate_channels(r["channels"]) != artifact["channels"] for r in rows):
        raise ValueError("locked channel order mismatch")
    parameters = artifact["parameters"]
    if artifact["method"] == "line_length_v1":
        if parameters["window_seconds"] != 1 or parameters["signal_unit"] != "microvolts" or parameters["scale_floor"] != 1e-12:
            raise ValueError("unknown line-length recipe")
        arrays = _signals(rows, signals)
        return {r["recording_id"]: _line_length(arrays[r["recording_id"]], r["sample_rate"], parameters["scales"]) for r in rows}
    if signals is not None:
        raise ValueError("timing-only comparator accepts no neural arrays")
    if parameters["bin_seconds"] != 60 or parameters["unobserved_bin_score"] != 0:
        raise ValueError("unknown timing-only recipe")
    rates = np.asarray(parameters["rates"])
    if rates.ndim != 1 or not len(rates) or rates.dtype.kind not in "fiu" or not np.isfinite(rates).all() or np.any((rates < 0) | (rates > 1)):
        raise ValueError("invalid timing probabilities")
    return {r["recording_id"]: _timing_scores(r, rates, 60.0) for r in rows}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["fit", "predict"])
    parser.add_argument("manifest")
    parser.add_argument("output")
    parser.add_argument("--signals", help="NPZ with recording IDs as keys; selected EEG in microvolts")
    parser.add_argument("--method", choices=["line_length_v1", "timing_only_v1"], default="line_length_v1")
    parser.add_argument("--artifact")
    args = parser.parse_args(argv)
    manifest = json.loads(Path(args.manifest).read_text())
    signals = _load_arrays(args.signals) if args.signals else None
    if args.command == "fit":
        if args.artifact:
            parser.error("fit does not accept an existing artifact")
        result = fit(manifest, signals, args.method)
        Path(args.output).write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    else:
        if not args.artifact:
            parser.error("predict requires --artifact")
        artifact = json.loads(Path(args.artifact).read_text())
        result = predict(manifest, signals, artifact)
        np.savez(args.output, **result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
