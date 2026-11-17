"""Pala voltage/spike bridge and prospective paired DSR assessment.

This is construction source, not a scientific qualification or exact Fig. 3 run.
All times are seconds at the public interface; source DSR bins are milliseconds.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import warnings

import numpy as np
from scipy.interpolate import CubicSpline
from scipy.io import loadmat

from third_party.neuron_stat import neuron_stats, NeuronStatsError

TASK_ID = "PAPER-paper-method-009"
RECIPE = "prospective-held-trial-natural-cubic-v1"
SOURCE_SHA256 = "24d9bff22d4eab46891101faed1e082e6483f326469f395850848b9139cf2a2a"
DATA_MD5 = "dc333d3d03b79460f2ec1d36122206c8"
HOLDS = [
    "Authentic data.mat schema/content and eight-neuron/five-mouse cohort not qualified.",
    "25 ms caption versus 50 ms methods remains unresolved; both are reported.",
    "Printed voltage-bin coordinate, spline family/smoothing, and support policy unresolved.",
    "Exact Fig.3 twenty-segment DSR estimator axis/selection is unresolved.",
    "Prospective train/assessment split and DSR millisecond rounding/shift are not historical reconstruction.",
    "No authentic reference execution, protected assessment, numeric grading tolerance, or difficulty qualification.",
    "Public paper/results exposure and data CC BY 4.0/code MIT rights remain applicable.",
]


class ContractError(ValueError):
    """An input would change the declared estimand or lose data silently."""


@dataclass(frozen=True)
class Trial:
    trial_id: str
    mouse_id: str
    cell_id: str
    cell_type: str
    trial_type: str
    sampling_hz: int
    voltage_mv: np.ndarray


def digest(path: Path, algorithm="sha256"):
    h = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def finite_vector(value, name, minimum=1):
    result = np.asarray(value, dtype=float)
    if result.ndim != 1 or result.size < minimum or not np.isfinite(result).all():
        raise ContractError(f"{name} must be a finite 1D vector of length >= {minimum}")
    return result


def decode_pala(data):
    """Decode the scalar struct fields identified in PalaPetersen_Analysis.m.

    No source exclusions, concatenation, trimming, or voltage unit inference.
    MATLAB trial cells must remain a one-dimensional object array/list.
    """
    fields = ["Trial_MembranePotential", "Trial_MembranePotential_SamplingRate",
              "Trial_Type", "Cell_Type", "Mouse_Name", "Cell_Counter"]
    if not isinstance(data, dict) or any(k not in data for k in fields):
        raise ContractError("data must be the scalar Pala struct with all six required fields")
    columns = {k: np.asarray(data[k]) for k in fields}
    voltage = columns[fields[0]]
    if voltage.ndim != 1 or voltage.dtype != object:
        raise ContractError("Trial_MembranePotential must be a 1D MATLAB cell vector; ambiguous numeric matrix refused")
    n = len(voltage)
    if n == 0 or any(v.ndim != 1 or len(v) != n for v in columns.values()):
        raise ContractError("all Pala fields must have the same nonempty trial axis")
    trials = []
    for i in range(n):
        fs = float(columns[fields[1]][i])
        counter = float(columns[fields[5]][i])
        if not np.isfinite(fs) or fs != 20000 or not np.isfinite(counter) or counter != int(counter):
            raise ContractError("expected 20 kHz and an integer Cell_Counter")
        mouse = str(columns[fields[4]][i])
        if not mouse:
            raise ContractError("empty mouse identity")
        trace = np.asarray(voltage[i])
        if trace.ndim > 2 or (trace.ndim == 2 and min(trace.shape) != 1):
            raise ContractError("each voltage cell must be a row or column vector")
        trials.append(Trial(f"pala-row-{i + 1:06d}", mouse, f"{mouse}_{int(counter)}",
                            str(columns[fields[3]][i]), str(columns[fields[2]][i]),
                            int(fs), finite_vector(trace.reshape(-1), "voltage", 2)))
    return trials


def load_pala(path, verify_source=True):
    path = Path(path)
    if verify_source and digest(path, "md5") != DATA_MD5:
        raise ContractError("data.mat differs from the source-recorded MD5")
    try:
        content = loadmat(path, simplify_cells=True)
    except (NotImplementedError, ValueError) as exc:
        raise ContractError("MAT loading failed; v7.3/HDF5 and unverified schema remain held") from exc
    if "data" not in content:
        raise ContractError("missing MATLAB data struct")
    return decode_pala(content["data"])


def spike_indices(voltage):
    v = finite_vector(voltage, "voltage", 2)
    if v[0] >= -30:
        raise ContractError("trace begins above spike threshold; onset is unobserved")
    return np.flatnonzero((v[:-1] < -30) & (v[1:] >= -30)) + 1


def remove_spikes(voltage, sampling_hz=20000):
    """Interpolate merged AP windows, retaining both unmodified endpoint samples."""
    if sampling_hz != 20000:
        raise ContractError("Fig.3 bridge requires 20 kHz")
    v = finite_vector(voltage, "voltage", 2)
    spikes = spike_indices(v)
    intervals = []
    for s in spikes:
        left, right = int(s - 60), int(s + 100)
        if left < 0 or right >= len(v):
            raise ContractError("AP blanking window reaches a trial edge; no extrapolation permitted")
        if intervals and left <= intervals[-1][1]:
            intervals[-1][1] = max(right, intervals[-1][1])
        else:
            intervals.append([left, right])
    clean = v.copy()
    for left, right in intervals:
        clean[left:right + 1] = np.linspace(v[left], v[right], right - left + 1)
    return clean, spikes


def cv2(intervals):
    x = finite_vector(intervals, "intervals", 2)
    if (x <= 0).any():
        raise ContractError("ISIs must be strictly positive")
    return float(np.var(x, ddof=0) / np.mean(x) ** 2)


def operational_isis(rate_hz, spike_times_s, sample_period_s):
    """Exact integral of the declared left-constant sampled rate; no normalization."""
    rate = finite_vector(rate_hz, "rate", 1)
    times = finite_vector(spike_times_s, "spike times", 3)
    if not np.isfinite(sample_period_s) or sample_period_s <= 0 or (rate < 0).any():
        raise ContractError("rate must be nonnegative and sample period positive")
    if (np.diff(times) <= 0).any() or times[0] < 0 or times[-1] > len(rate) * sample_period_s:
        raise ContractError("spikes must be strictly ordered and inside rate support")
    position = times / sample_period_s
    # Floating arithmetic at exact boundaries must not move a spike by a sample.
    nearest = np.rint(position)
    position = np.where(np.abs(position - nearest) < 1e-8, nearest, position)
    index = np.floor(position).astype(int)
    integral = np.concatenate(([0.0], np.cumsum(rate) * sample_period_s))
    tau = integral[index] + (position - index) * sample_period_s * rate[np.minimum(index, len(rate) - 1)]
    result = np.diff(tau)
    if (result <= 0).any():
        raise ContractError("zero operational ISI: fitted rate has no positive mass between spikes")
    return result


def binned_voltage_rate(clean, spikes, bin_ms):
    if bin_ms not in (25, 50):
        raise ContractError("both source voltage sensitivities are fixed at 25/50 ms")
    width = bin_ms * 20
    if len(clean) % width:
        raise ContractError("partial voltage bin; no silent truncation")
    counts = np.bincount(np.asarray(spikes, dtype=int) // width, minlength=len(clean) // width)
    return np.asarray(clean).reshape(-1, width).mean(axis=1), counts / (bin_ms / 1000)


def fit_voltage_curve(prepared, bin_ms):
    """Prospective natural cubic through occupied conventional 1 mV bin centers."""
    pairs = [binned_voltage_rate(v, s, bin_ms) for v, s in prepared]
    voltage, rate = (np.concatenate([p[i] for p in pairs]) for i in (0, 1))
    edges = np.arange(-68.0, -39.0)
    bins = np.searchsorted(edges, voltage, side="right") - 1
    bins[voltage == -40] = 27
    counts = np.array([np.sum(bins == k) for k in range(28)])
    occupied = counts > 0
    if occupied.sum() < 4:
        raise ContractError("at least four occupied voltage bins required for cubic fit")
    x = (edges[:-1] + .5)[occupied]
    y = np.array([rate[bins == k].mean() for k in np.flatnonzero(occupied)])
    curve = CubicSpline(x, y, bc_type="natural", extrapolate=False)
    metadata = {"bin_ms": bin_ms, "centers_mv": x.tolist(), "mean_rate_hz": y.tolist(),
                "counts": counts[occupied].tolist(), "out_of_voltage_range_bins": int(np.sum((voltage < -68) | (voltage > -40))),
                "spline_policy": "natural_cubic_interpolant_no_smoothing", "voltage_support_mv": [float(x[0]), float(x[-1])]}
    return curve, metadata


def predict_rate(curve, metadata, clean):
    lo, hi = metadata["voltage_support_mv"]
    raw = curve(np.clip(clean, lo, hi))
    return np.maximum(0, raw), {"support_clamped_samples": int(np.sum((clean < lo) | (clean > hi))),
                               "negative_rate_floored_samples": int(np.sum(raw < 0))}


def dsr(spikes_by_trial, duration_s, bin_ms=None):
    """Pinned native DSR, with strict complete binary 1 ms input and explicit failures."""
    if digest(Path(__file__).parent / "third_party" / "neuron_stat.py") != SOURCE_SHA256:
        raise ContractError("pinned native estimator was changed")
    if len(spikes_by_trial) < 2 or duration_s <= 0 or int(duration_s * 1000) != duration_s * 1000:
        raise ContractError("DSR requires >=2 aligned trials and integral milliseconds")
    matrix = np.zeros((len(spikes_by_trial), int(duration_s * 1000)), dtype=np.uint8)
    for i, times in enumerate(spikes_by_trial):
        t = np.asarray(times, dtype=float)
        if t.ndim != 1 or not np.isfinite(t).all() or (t < 0).any() or (t >= duration_s).any() or (np.diff(t) <= 0).any():
            raise ContractError("invalid within-trial spike times")
        cells = np.floor(t * 1000 + 1e-9).astype(int)
        if len(np.unique(cells)) != len(cells):
            raise ContractError("multiple spikes occupy one millisecond; native binary input would lose spikes")
        matrix[i, cells] = 1
    mean_hz = float(matrix.sum() / (len(matrix) * duration_s))
    if mean_hz <= 0:
        raise ContractError("no spikes for rate-derived DSR bin")
    # Methods T=2/E[lambda]; upward quantization is a disclosed prospective policy.
    width = int(np.ceil(2000 / mean_hz)) if bin_ms is None else bin_ms
    if not isinstance(width, int) or width < 1 or 2 * width > matrix.shape[1]:
        raise ContractError("rate-derived DSR bin does not fit the analysis window")
    info = {"mean_rate_hz": mean_hz, "bin_ms": width, "unrounded_bin_ms": 2000 / mean_hz,
            "shift_ms": 50, "alpha": 2, "n_trials": len(matrix), "duration_s": duration_s}
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            phi = float(neuron_stats(matrix, waiting_time_cut=matrix.shape[1], binsize=width,
                                     shift=50, alpha=2, max_iterations=10, outlier_threshold=3))
    except NeuronStatsError as exc:
        return {**info, "phi": None, "status": "native_estimator_failure", "reason": str(exc)}
    return {**info, "phi": phi if np.isfinite(phi) else None,
            "status": "ok" if np.isfinite(phi) else "native_nonfinite"}


def audit_population(trials):
    if not trials or any(not isinstance(t.trial_id, str) or not t.trial_id for t in trials) or len({t.trial_id for t in trials}) != len(trials):
        raise ContractError("trial identities must be nonempty and unique")
    cells = {}
    for t in trials:
        finite_vector(t.voltage_mv, "voltage", 2)
        if not t.cell_id or not t.mouse_id or t.sampling_hz != 20000:
            raise ContractError("missing biological identity or non-20kHz trial")
        group = cells.setdefault(t.cell_id, [])
        if group and (group[0].mouse_id != t.mouse_id or group[0].cell_type != t.cell_type):
            raise ContractError("cell identity conflicts across trials")
        group.append(t)
    ledger = []
    eligible = {}
    for cell, records in sorted(cells.items()):
        candidates = [t for t in records if t.cell_type == "PV" and t.trial_type == "Spont"]
        # Do not import original Pala experiment-specific trial deletions into DSR.
        reasons = []
        if not candidates:
            reasons.append("not_PV_spontaneous")
        if any(len(t.voltage_mv) != 400000 for t in candidates):
            raise ContractError("non-20-second PV Spont trial: selection/truncation policy unresolved; cohort not reduced")
        rate = (sum(len(spike_indices(t.voltage_mv)) for t in candidates) /
                sum(len(t.voltage_mv) / 20000 for t in candidates)) if candidates else None
        if len(candidates) < 10:
            reasons.append("fewer_than_10_trials")
        if rate is not None and rate < 20:
            reasons.append("mean_rate_below_20_Hz")
        ledger.append({"cell_id": cell, "mouse_id": records[0].mouse_id,
                       "all_trial_ids": [t.trial_id for t in records],
                       "candidate_trial_ids": [t.trial_id for t in candidates],
                       "mean_rate_hz": rate, "eligible": not reasons, "reasons": reasons})
        if not reasons:
            eligible[cell] = candidates
    return eligible, ledger


def summarize(values):
    x = np.asarray(values, dtype=float)
    if x.size == 0 or not np.isfinite(x).all():
        return {"n": int(x.size), "mean": None, "sem": None, "status": "incomplete"}
    return {"n": len(x), "mean": float(x.mean()),
            "sem": float(x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 1 else None,
            "status": "ok"}


def paired_metrics(prepared, curve, metadata):
    raw, operational, segments, diagnostics = [], [], [], []
    for trial, (clean, spikes) in prepared:
        rate, info = predict_rate(curve, metadata, clean)
        diagnostics.append({"trial_id": trial.trial_id, **info})
        times = spikes / 20000
        if len(times) < 3:
            raise ContractError("too few assessment spikes")
        raw.extend(np.diff(times))
        operational.extend(operational_isis(rate, times, 1 / 20000))
        for half in (0, 1):
            a, b = half * 200000, (half + 1) * 200000
            selected = spikes[(spikes >= a) & (spikes < b)] - a
            if len(selected) < 3:
                raise ContractError("too few spikes in a required 10-second segment")
            raw_phi = cv2(np.diff(selected / 20000))
            op = operational_isis(rate[a:b], selected / 20000, 1 / 20000)
            voltage_phi = cv2(op)
            segments.append({"trial_id": trial.trial_id, "half": half,
                             "raw_cv2": raw_phi, "voltage_phi": voltage_phi,
                             "voltage_fraction": voltage_phi / raw_phi if raw_phi > 0 else None,
                             "mean_operational_isi": float(op.mean())})
    raw_phi, voltage_phi = cv2(raw), cv2(operational)
    return {"raw_cv2": raw_phi, "voltage_phi": voltage_phi,
            "voltage_fraction": voltage_phi / raw_phi if raw_phi > 0 else None,
            "mean_operational_isi": float(np.mean(operational)), "isi_count": len(raw),
            "segments": segments, "diagnostics": diagnostics,
            "voltage_segment_phi_summary": summarize([s["voltage_phi"] for s in segments]),
            "raw_segment_cv2_summary": summarize([s["raw_cv2"] for s in segments]),
            "voltage_segment_fraction_summary": summarize([s["voltage_fraction"] for s in segments])}


def evaluate(trials, plan):
    if plan.get("recipe") != RECIPE:
        raise ContractError("explicit acknowledgement of the prospective recipe required")
    eligible, ledger = audit_population(trials)
    if not eligible:
        raise ContractError("no qualifying cells; an empty cohort cannot be evaluated")
    splits = plan.get("cells", {})
    if set(splits) != set(eligible):
        raise ContractError("plan must include every eligible cell, without extra cells")
    results = []
    for cell, records in sorted(eligible.items()):
        split = splits[cell]
        train, test = split.get("calibration_trial_ids", []), split.get("assessment_trial_ids", [])
        ids = {t.trial_id for t in records}
        if (len(train) < 2 or len(test) < 2 or len(set(train)) != len(train) or len(set(test)) != len(test)
                or set(train) & set(test) or set(train) | set(test) != ids):
            raise ContractError("split must cover all qualifying trials exactly once with >=2 per partition")
        by_id = {t.trial_id: t for t in records}
        prepared = {t.trial_id: remove_spikes(t.voltage_mv) for t in records}
        native = dsr([prepared[i][1] / 20000 for i in test], 20)
        window_dsr = []
        for half in (0, 1):
            times = []
            for i in test:
                s = prepared[i][1] / 20000
                times.append(s[(s >= 10 * half) & (s < 10 * (half + 1))] - 10 * half)
            window_dsr.append({"half": half, **dsr(times, 10)})
        sensitivity = []
        for bin_ms in (25, 50):
            curve, metadata = fit_voltage_curve([prepared[i] for i in train], bin_ms)
            metrics = paired_metrics([(by_id[i], prepared[i]) for i in test], curve, metadata)
            metrics["dsr_fraction"] = native["phi"] / metrics["raw_cv2"] if native["phi"] is not None and metrics["raw_cv2"] > 0 else None
            metrics["dsr_minus_voltage_phi"] = native["phi"] - metrics["voltage_phi"] if native["phi"] is not None else None
            sensitivity.append({"voltage_fit": metadata, **metrics})
        results.append({"cell_id": cell, "mouse_id": records[0].mouse_id,
                        "calibration_trial_ids": train, "assessment_trial_ids": test,
                        "dsr": native, "aligned_window_dsr": window_dsr,
                        "poisson_phi_reference": 1.0, "voltage_sensitivities": sensitivity})
    # Nest neuron summaries within mice; never treat segments as independent animals.
    mouse_summaries = []
    for mouse in sorted({r["mouse_id"] for r in results}):
        subset = [r for r in results if r["mouse_id"] == mouse]
        mouse_summaries.append({"mouse_id": mouse, "cell_ids": [r["cell_id"] for r in subset],
                                "voltage_phi_25ms": summarize([r["voltage_sensitivities"][0]["voltage_phi"] for r in subset]),
                                "voltage_phi_50ms": summarize([r["voltage_sensitivities"][1]["voltage_phi"] for r in subset])})
    return {"task_id": TASK_ID, "recipe": RECIPE, "classification": "prospective_engineering_bridge",
            "scientific_qualified": False, "exact_figure_reproduction": False,
            "population_ledger": ledger, "eligible_neurons": len(eligible),
            "eligible_mice": len({v[0].mouse_id for v in eligible.values()}),
            "count_matches_paper_8_neurons_5_mice": len(eligible) == 8 and len({v[0].mouse_id for v in eligible.values()}) == 5,
            "count_match_is_identity_validation": False, "cells": results, "mouse_summaries": mouse_summaries,
            "holds": HOLDS}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mat", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text())
    report = evaluate(load_pala(args.mat), plan)
    report["input_receipt"] = {"mat_sha256": digest(args.mat), "mat_md5": DATA_MD5,
                               "plan_sha256": digest(args.plan), "dsrp_sha256": SOURCE_SHA256}
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
