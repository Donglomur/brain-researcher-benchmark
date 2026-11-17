"""CellMincer paired-EP aligned-trace evaluator; no native data or fitting runner.

Published equations 21--23 are implemented separately from explicitly prospective
panel, peak-discretization and spectral policies. EP references stay grader-side.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from scipy.signal import find_peaks, stft

TASK_ID = "PAPER-paper-method-030"
ROOT = Path(__file__).resolve().parent
SAMPLE_RATE = 500.0
N_FRAMES = 5000
DELTA_T_SECONDS = 0.002
DELTA_PROMINENCE_MV = 0.2
# Explicit prospective evaluation grid; article does not provide the exact grid.
PROMINENCE_MV = (0.5, 1.0, 2.0, 3.0, 5.0, 10.0, 20.0)


class ContractError(ValueError):
    """Invalid or incomplete evaluator input; no partial scores are emitted."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def _array(values: Any, name: str, *, length: int | None = None) -> np.ndarray:
    a = np.asarray(values)
    _require(a.ndim == 1 and a.size > 0, f"{name}: expected nonempty vector")
    _require(a.dtype.kind in "iuf" and a.dtype.kind != "b", f"{name}: numeric vector required")
    a = a.astype(float)
    _require(bool(np.all(np.isfinite(a))), f"{name}: nonfinite values")
    if length is not None:
        _require(len(a) == length, f"{name}: expected exactly {length} frames")
    return a


def _events(times: Any, name: str) -> np.ndarray:
    a = np.asarray(times, dtype=float)
    _require(a.ndim == 1 and bool(np.all(np.isfinite(a))), f"{name}: invalid event times")
    _require(bool(np.all(np.diff(a) > 0)), f"{name}: event times must be strictly increasing")
    return a


def _has_neighbor(query: np.ndarray, reference: np.ndarray, tolerance: float) -> np.ndarray:
    if len(reference) == 0:
        return np.zeros(len(query), dtype=bool)
    pos = np.searchsorted(reference, query)
    left = reference[np.maximum(pos - 1, 0)]
    right = reference[np.minimum(pos, len(reference) - 1)]
    # Tiny representational errors at the published strict boundary must not
    # turn one frame at 500 Hz into a hit. The margin is below 1 picosecond.
    distance = np.minimum(np.abs(query - left), np.abs(query - right))
    return (distance < tolerance) & ~np.isclose(distance, tolerance, rtol=0, atol=min(1e-12, tolerance * 1e-6))


def fuzzy_events(reference_seconds: Any, predicted_seconds: Any,
                 tolerance_seconds: float = DELTA_T_SECONDS) -> dict[str, Any]:
    """Paper Eq.21/22: existential matching, intentionally not one-to-one.

    Empty denominators return null. F1 is zero if exactly one set is empty,
    and null if both are empty; those cases are undefined by the article.
    """
    _require(math.isfinite(tolerance_seconds) and tolerance_seconds > 0, "positive finite tolerance required")
    ref = _events(reference_seconds, "reference")
    pred = _events(predicted_seconds, "predicted")
    matched_pred = int(_has_neighbor(pred, ref, tolerance_seconds).sum())
    matched_ref = int(_has_neighbor(ref, pred, tolerance_seconds).sum())
    precision = matched_pred / len(pred) if len(pred) else None
    recall = matched_ref / len(ref) if len(ref) else None
    if not len(ref) and not len(pred):
        f1 = None
    elif not len(ref) or not len(pred) or precision + recall == 0:
        f1 = 0.0
    else:
        f1 = 2 * precision * recall / (precision + recall)
    return dict(reference_count=len(ref), predicted_count=len(pred), matched_reference_count=matched_ref,
                matched_predicted_count=matched_pred, false_event_count=len(pred) - matched_pred,
                missed_event_count=len(ref) - matched_ref, precision=precision, recall=recall, f1=f1)


def peaks(trace: Any, sample_rate: float = SAMPLE_RATE) -> tuple[np.ndarray, np.ndarray]:
    """SciPy local maxima, global prominence, flat peak midpoint; no distance filter."""
    x = _array(trace, "trace")
    _require(math.isfinite(sample_rate) and sample_rate > 0, "invalid sampling rate")
    idx, props = find_peaks(x, prominence=(None, None))
    return idx / sample_rate, props["prominences"]


def prominence_f1_star(reference_peaks: tuple[Any, Any], predicted_peaks: tuple[Any, Any],
                       prominence_mv: float) -> dict[str, Any]:
    """Exact finite-set maximization of paper Eq.23 for a fixed EP prominence.

    Sets use prominence >= threshold. Candidate sets change only immediately
    above an observed prominence; endpoints and all such breakpoints are tried.
    Maximizing threshold is grader-only and never returned to the candidate.
    """
    _require(math.isfinite(prominence_mv) and prominence_mv >= DELTA_PROMINENCE_MV,
             "EP prominence must be finite and >=0.2 mV")
    rt, rp = reference_peaks; pt, pp = predicted_peaks
    rt = _events(rt, "reference peaks"); pt = _events(pt, "predicted peaks")
    rp = np.asarray(rp, dtype=float); pp = np.asarray(pp, dtype=float)
    _require(rp.shape == rt.shape and pp.shape == pt.shape, "peak prominence shape mismatch")
    _require(bool(np.all(np.isfinite(rp))) and bool(np.all(np.isfinite(pp))) and
             bool(np.all(rp >= 0)) and bool(np.all(pp >= 0)), "invalid prominence")
    low, high = prominence_mv - DELTA_PROMINENCE_MV, prominence_mv + DELTA_PROMINENCE_MV
    thresholds = {low, high}
    thresholds.update(float(np.nextafter(v, np.inf)) for v in pp if low <= v < high)
    ref = rt[rp >= prominence_mv]
    choices = [fuzzy_events(ref, pt[pp >= threshold]) for threshold in sorted(thresholds)]
    valid = [x for x in choices if x["f1"] is not None]
    best = max(valid, key=lambda x: x["f1"]) if valid else choices[0]
    return {"ep_prominence_mv": prominence_mv, "f1_star": best["f1"],
            "best_counts": best, "threshold_states_evaluated": len(thresholds)}


def pearson(x: Any, y: Any) -> float | None:
    x = _array(x, "x"); y = _array(y, "y", length=len(x))
    # Scale before centering to avoid overflow for finite extreme inputs.
    xscale, yscale = float(np.max(np.abs(x))), float(np.max(np.abs(y)))
    if xscale == 0 or yscale == 0:
        return None
    x = x / xscale; y = y / yscale
    x = x - x.mean(); y = y - y.mean()
    scale = float(np.linalg.norm(x) * np.linalg.norm(y))
    return None if scale == 0 else float(np.clip(np.dot(x, y) / scale, -1.0, 1.0))


def lagged_correlations(ep: Any, vi: Any, max_lag_frames: int = 5) -> dict[str, Any]:
    """Positive lag means VI occurs later than EP; overlap-wise centering."""
    ep = _array(ep, "ep"); vi = _array(vi, "vi", length=len(ep))
    _require(type(max_lag_frames) is int and 0 <= max_lag_frames < len(ep) - 1, "invalid maximum lag")
    values = []
    for lag in range(-max_lag_frames, max_lag_frames + 1):
        a, b = (ep[-lag:], vi[:lag]) if lag < 0 else ((ep[:-lag], vi[lag:]) if lag else (ep, vi))
        values.append(pearson(a, b))
    return {"lags_seconds": [i / SAMPLE_RATE for i in range(-max_lag_frames, max_lag_frames + 1)],
            "pearson_r": values, "zero_lag_r": values[max_lag_frames]}


def boxcar_control(trace: Any) -> np.ndarray:
    """Fixed three-frame mean with edge extension, prospective weak control."""
    x = _array(trace, "raw")
    return np.convolve(np.pad(x, 1, mode="edge"), np.ones(3) / 3, mode="valid")


def residual_spectrum(ep: Any, raw: Any, vi: Any, ep_power_ceiling_mv2: float,
                      power_floor_mv2: float = 1e-12) -> dict[str, Any]:
    """64/48 STFT paper design with explicit prospective Hann/no-padding policy.

    Mask uses EP only. Mean log power is calculated before raw-minus-method;
    log of mean power is intentionally not substituted. No empty-mask score.
    """
    ep = _array(ep, "ep"); raw = _array(raw, "raw", length=len(ep)); vi = _array(vi, "vi", length=len(ep))
    _require(len(ep) >= 64, "STFT needs at least 64 samples")
    _require(math.isfinite(ep_power_ceiling_mv2) and ep_power_ceiling_mv2 > 0, "EP spectral ceiling must be positive")
    _require(math.isfinite(power_floor_mv2) and power_floor_mv2 > 0, "power floor must be positive")
    def transform(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        f, _, z = stft(x, fs=SAMPLE_RATE, window="hann", nperseg=64, noverlap=48,
                       detrend=False, return_onesided=True, boundary=None, padded=False, scaling="spectrum")
        return f, np.abs(z) ** 2
    f, ep_power = transform(ep)
    mask = ep_power.sum(axis=0) <= ep_power_ceiling_mv2
    n = int(mask.sum())
    if n == 0:
        return {"eligible_windows": 0, "total_windows": len(mask), "status": "undefined_no_eligible_windows"}
    _, raw_power = transform(raw - ep); _, vi_power = transform(vi - ep)
    raw_db = (10 * np.log10(np.maximum(raw_power[:, mask], power_floor_mv2))).mean(axis=1)
    vi_db = (10 * np.log10(np.maximum(vi_power[:, mask], power_floor_mv2))).mean(axis=1)
    gain = raw_db - vi_db
    return {"eligible_windows": n, "total_windows": len(mask), "status": "computed_prospective_policy",
            "frequency_hz": f.tolist(), "noise_reduction_db": gain.tolist(),
            "mean_above_100hz_db": float(gain[f > 100].mean())}


def trace_metrics(ep: Any, raw: Any, vi: Any, policy: dict[str, Any]) -> dict[str, Any]:
    ep = _array(ep, "ep", length=N_FRAMES); raw = _array(raw, "raw", length=N_FRAMES)
    vi = _array(vi, "vi", length=N_FRAMES)
    ref_peaks, vi_peaks = peaks(ep), peaks(vi)
    peak_scores = [prominence_f1_star(ref_peaks, vi_peaks, p) for p in PROMINENCE_MV]
    # Fixed-threshold counts expose false events separately from oracle F1*.
    fixed_profile = []
    for p in PROMINENCE_MV:
        fixed = fuzzy_events(ref_peaks[0][ref_peaks[1] >= p], vi_peaks[0][vi_peaks[1] >= p])
        fixed["prominence_mv"] = p
        fixed["false_events_per_second"] = fixed["false_event_count"] / (N_FRAMES / SAMPLE_RATE)
        fixed_profile.append(fixed)
    with np.errstate(over="raise", invalid="raise"):
        try:
            rmse = float(np.sqrt(np.mean((ep - vi) ** 2)))
        except FloatingPointError as exc:
            raise ContractError("trace arithmetic outside finite numeric range") from exc
    return {"reference_nonconstant": bool(np.ptp(ep) > 0), "lagged_correlation": lagged_correlations(ep, vi), "prominence_scores": peak_scores,
            "spike_threshold_20mv": fixed_profile[-1], "fixed_prominence_profiles": fixed_profile,
            "residual_spectrum": residual_spectrum(ep, raw, vi, policy["ep_power_ceiling_mv2"]),
            "rmse_mv": rmse}


def load_catalogue() -> dict[str, Any]:
    return json.loads((ROOT / "population.json").read_text())


def validate_panel(panel: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    """Evaluator-owned full 22-recording assignment; cells never cross splits."""
    catalogue = load_catalogue()
    expected = {r["recording_id"]: r for r in catalogue["recordings"]}
    _require(panel.get("task_id") == TASK_ID, "wrong task")
    _require(panel.get("population_sha256") == hashlib.sha256((ROOT / "population.json").read_bytes()).hexdigest(), "population pin mismatch")
    records = panel.get("recordings", [])
    _require(isinstance(records, list) and len(records) == len(expected), "complete 22-recording assignment required")
    _require({r.get("recording_id") for r in records} == set(expected), "recording coverage mismatch")
    cells: dict[str, set[str]] = {}
    for r in records:
        source = expected[r["recording_id"]]
        _require(r.get("cell_id") == source["cell_id"], "cell identity differs from frozen metadata")
        _require(r.get("split") in {"train", "validation", "test"}, "invalid split")
        cells.setdefault(r["cell_id"], set()).add(r["split"])
    _require(all(len(v) == 1 for v in cells.values()), "cell leakage across splits")
    _require({r["split"] for r in records} == {"train", "validation", "test"}, "all three splits required")
    methods = panel.get("methods", [])
    _require(isinstance(methods, list) and len(methods) == len(set(methods)) and
             all(isinstance(m, str) and m for m in methods), "unique named methods required")
    _require("cellmincer" in methods and bool({"pmd", "n2s"} & set(methods)), "CellMincer and matched PMD or N2S outputs required")
    _require(not {"raw", "boxcar3"} & set(methods), "reserved control method names")
    _require(panel.get("alignment_policy") == "externally_frozen_no_test_ep_fit", "held-out scoring requires frozen alignment")
    _require(isinstance(panel.get("spectral_policy"), dict) and
             set(panel["spectral_policy"]) == {"ep_power_ceiling_mv2"}, "unsupported spectral policy fields")
    power = panel["spectral_policy"].get("ep_power_ceiling_mv2")
    _require(isinstance(power, (int, float)) and not isinstance(power, bool) and math.isfinite(power) and power > 0,
             "explicit prospectively frozen EP power ceiling required")
    return records, methods


def _mean_available(values: list[float | None]) -> dict[str, Any]:
    valid = [v for v in values if v is not None]
    return {"mean": sum(valid) / len(valid) if valid else None, "defined_count": len(valid), "total_count": len(values)}


def _mean_complete(values: list[float | None]) -> dict[str, Any]:
    """Undefined predictions cannot improve averages by removing hard records."""
    result = _mean_available(values)
    if result["defined_count"] != result["total_count"]:
        result["mean"] = None
    return result


def evaluate(panel: dict[str, Any], private_reference: dict[str, Any], submission: dict[str, Any]) -> dict[str, Any]:
    """Grade complete test population. Inputs are already aligned mV at 500 Hz.

    This function does not create or attest the native alignment or exposure
    boundary. Operator attestations are provenance, never scientific evidence.
    """
    records, methods = validate_panel(panel)
    test = [r for r in records if r["split"] == "test"]
    ids = {r["recording_id"] for r in test}
    _require(private_reference.get("reference_access") == "grader_only", "private EP boundary must be explicit")
    _require(private_reference.get("units") == "mV" and private_reference.get("sampling_rate_hz") == SAMPLE_RATE,
             "reference must be aligned mV at 500 Hz")
    _require(submission.get("units") == "mV" and submission.get("sampling_rate_hz") == SAMPLE_RATE,
             "submission must be aligned mV at 500 Hz")
    train_cells = {r["cell_id"] for r in records if r["split"] == "train"}
    for m in methods:
        access = submission.get("method_access", {}).get(m, {})
        _require(access.get("electrical_targets_accessed") is False, f"{m}: electrical-target access forbidden")
        fit_cells = access.get("fit_cell_ids")
        _require(isinstance(fit_cells, list) and set(fit_cells) <= train_cells,
                 f"{m}: train-only fit cells required")
    refs = private_reference.get("recordings", {})
    preds = submission.get("recordings", {})
    _require(set(refs) == ids and set(preds) == ids, "exact test recording coverage required")
    results = []
    for r in sorted(test, key=lambda r: r["recording_id"]):
        rid = r["recording_id"]; ref = refs[rid]; pred = preds[rid]
        _require(set(pred) == set(methods), f"{rid}: identical method coverage required")
        _require(ref.get("alignment_source") == "frozen_external_calibration", f"{rid}: unresolved alignment")
        _require(isinstance(ref.get("alignment_sha256"), str) and len(ref["alignment_sha256"]) == 64 and
                 all(c in "0123456789abcdef" for c in ref["alignment_sha256"]), "alignment evidence pin required")
        ep = _array(ref["ep_mv"], "EP", length=N_FRAMES)
        raw = _array(ref["raw_mv"], "raw", length=N_FRAMES)
        traces = {"raw": raw, "boxcar3": boxcar_control(raw), **pred}
        results.append({"recording_id": rid, "cell_id": r["cell_id"], "methods": {
            m: trace_metrics(ep, raw, x, panel["spectral_policy"]) for m, x in traces.items()}})
    cells = sorted({r["cell_id"] for r in test})
    # Recordings averaged within cell, then cells given equal weight; repeated
    # recordings do not become independent biological replicates.
    aggregate = {}
    for m in ["raw", "boxcar3", *methods]:
        cell_rows = []
        for cell in cells:
            rows = [r["methods"][m] for r in results if r["cell_id"] == cell]
            cell_rows.append({"cell_id": cell,
                "zero_lag_r": _mean_complete([x["lagged_correlation"]["zero_lag_r"] for x in rows if x["reference_nonconstant"]]),
                "f1_star_by_prominence": [dict(
                    **_mean_available([x["prominence_scores"][i]["f1_star"] for x in rows
                        if x["prominence_scores"][i]["best_counts"]["reference_count"] > 0]),
                    excluded_no_ep_peaks=sum(x["prominence_scores"][i]["best_counts"]["reference_count"] == 0 for x in rows))
                    for i in range(len(PROMINENCE_MV))],
                "false_events_per_second_20mv": _mean_available([x["spike_threshold_20mv"]["false_events_per_second"] for x in rows]),
                "false_events_per_second_by_prominence": [_mean_available([x["fixed_prominence_profiles"][i]["false_events_per_second"] for x in rows]) for i in range(len(PROMINENCE_MV))]})
        aggregate[m] = {"cells": cell_rows,
            "cell_macro_zero_lag_r": _mean_complete([x["zero_lag_r"]["mean"] for x in cell_rows if x["zero_lag_r"]["total_count"] > 0]),
            "cell_macro_f1_star": [_mean_available([x["f1_star_by_prominence"][i]["mean"] for x in cell_rows]) for i in range(len(PROMINENCE_MV))],
            "cell_macro_false_events_per_second_20mv": _mean_available([x["false_events_per_second_20mv"]["mean"] for x in cell_rows]),
            "cell_macro_false_events_per_second_by_prominence": [_mean_available([x["false_events_per_second_by_prominence"][i]["mean"] for x in cell_rows]) for i in range(len(PROMINENCE_MV))]}
    result = {"task_id": TASK_ID, "scope": "prepared_aligned_trace_evaluation_only",
            "scientific_qualification": "unknown", "native_reference_verified": False,
            "policy": {"published_metric": "equations_21_23_existential_strict_2ms_prominence_oracle_0.2mV",
                       "prospective_prominence_grid_mv": list(PROMINENCE_MV),
                       "empty_peak_sets": "both_empty_null_one_empty_zero",
                       "spectral": {"window": "periodic_hann", "length": 64, "overlap": 48,
                                    "boundary": None, "padded": False, "power_floor_mv2": 1e-12,
                                    **panel["spectral_policy"]},
                       "aggregation": "recording_mean_then_equal_cell_mean; F1 uses common EP-positive support; false events use all records"},
            "population_recordings": len(records), "test_recordings": len(test), "test_cells": len(cells),
            "per_recording": results, "aggregate": aggregate,
            "holds": ["Native TIFF/ABF channel, ROI, timing and calibration evidence unverified",
                      "Historical 26-training/22-evaluation population correspondence not empirically verified",
                      "Prospective held-out protocol differs from historical all-recording self-supervision",
                      "Dataset redistribution rights, authentic denoiser execution and isolated access unqualified"]}
    try:
        json.dumps(result, allow_nan=False)
    except ValueError as exc:
        raise ContractError("nonfinite metric arithmetic") from exc
    return result


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--panel", required=True, type=Path)
    p.add_argument("--private-reference", required=True, type=Path)
    p.add_argument("--submission", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    try:
        result = evaluate(json.loads(args.panel.read_text()), json.loads(args.private_reference.read_text()),
                          json.loads(args.submission.read_text()))
        args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    except (ContractError, KeyError, TypeError, json.JSONDecodeError) as exc:
        p.exit(2, f"invalid evaluation input: {exc}\n")


if __name__ == "__main__":
    main()
