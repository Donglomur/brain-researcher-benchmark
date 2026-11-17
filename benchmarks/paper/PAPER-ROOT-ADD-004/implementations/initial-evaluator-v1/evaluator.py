"""Prospective, train-only localizer→retrieval analysis for PAPER-ROOT-ADD-004.

This is an executable normalized-epoch recipe, not a native-paper reproduction
or a numeric benchmark grader. See ../../docs/initial-evaluator-v1.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from pathlib import Path

import numpy as np
from scipy import __version__ as scipy_version
from scipy.stats import rankdata

TASK_ID = "PAPER-ROOT-ADD-004"
RECIPE = "prospective-train-only-epoch-analysis-v1"
FS = 200
TRAIN_TIMES = np.round(np.arange(-.15, 1.50001, .05), 8)
CUE_TIMES = np.round(np.arange(0., 1.50001, .05), 8)
EXHALATION_TIMES = np.round(np.arange(-2., 2.00001, .05), 8)
SOURCE_ROSTER = ["P02", "P05", "P07", "P09", "P11", "P12", "P13", "P14", "P15", "P16",
                 "P19", "P21", "P22", "P25", "P26", "P29", "P30", "P31"]
HOLDS = [
    "Native MATLAB loader, trial labels, excluded participants and full trial inventory need archive audit.",
    "April 2025 archive versus final journal article version reconciliation is unresolved.",
    "Train-only PCA/standardization and fixed ridge LDA are prospective, not native-equivalent.",
    "Complete channel inventory and source preprocessing equivalence remain unverified.",
    "Figure 3c outcome-group/exhalation baseline differs from the paper's cue-baseline description.",
    "Manuscript modulus/0.15–1.5 s confidence differs from legacy decision-value generator.",
    "FieldTrip/MVPA-Light/CircStat numerical equivalence and dependency pins are unverified.",
    "Authentic 18-participant results, independent references and tolerances are unavailable.",
    "Protected assessment, artifact/timing controls and grouped improvement panel are unqualified.",
    "LMU CC BY-NC-SA 4.0 terms and unresolved GitHub licensing remain; no source code is redistributed.",
    "No native runtime envelope, scientific qualification or causal breathing claim is established.",
]


def finite(value, name, ndim=None):
    a = np.asarray(value, dtype=float)
    if (ndim is not None and a.ndim != ndim) or not np.isfinite(a).all():
        raise ValueError(f"{name}: expected finite {ndim}-dimensional numeric array")
    return a


def string(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name}: nonempty string required")
    return value


def time_axis(value, name):
    a = finite(value, name, 1)
    if len(a) < 2 or not np.allclose(np.diff(a), 1 / FS, atol=1e-8, rtol=0):
        raise ValueError(f"{name}: strictly increasing 200 Hz axis required")
    return a


def sample_indices(axis, centers):
    centers = finite(centers, "sample centers", 1)
    indices = np.rint((centers - axis[0]) * FS).astype(int)
    if np.any(indices < 0) or np.any(indices >= len(axis)):
        raise ValueError("requested epoch extends beyond available samples; no padding")
    if not np.allclose(axis[indices], centers, atol=1e-8, rtol=0):
        raise ValueError("event/grid is not sample aligned; interpolation policy is unresolved")
    return indices


def smooth_samples(x, axis, centers):
    """200 ms running mean; even window offsets -20..19, truncated at edges."""
    indices = sample_indices(axis, centers)
    return np.stack([x[..., max(0, i - 20):min(len(axis), i + 20)].mean(-1)
                     for i in indices], axis=-1)


def auc(labels, scores):
    """Mann–Whitney AUC, scene=1, with half credit for ties."""
    y = np.asarray(labels)
    s = finite(scores, "scores", 1)
    if y.shape != s.shape or not np.isin(y, [0, 1]).all():
        raise ValueError("binary labels and scores must have identical shape")
    n1, n0 = int(np.sum(y == 1)), int(np.sum(y == 0))
    if not n1 or not n0:
        return float("nan")
    return float((rankdata(s)[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def spearman(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    if x.ndim != 1 or x.shape != y.shape:
        raise ValueError("Spearman vectors must have equal one-dimensional shapes")
    if len(x) < 3 or not np.isfinite(x).all() or not np.isfinite(y).all():
        return float("nan")
    a, b = rankdata(x), rankdata(y)
    a, b = a - a.mean(), b - b.mean()
    denominator = np.linalg.norm(a) * np.linalg.norm(b)
    return float(a @ b / denominator) if denominator else float("nan")


def fit_lda(x, labels):
    """Training-only z-score, PCA(95%), pooled covariance + fixed 0.1 ridge.

    Equal class priors; no retrieval arrays or labels enter this function.
    Constant channels are retained with scale 1; a zero-rank design is rejected.
    """
    x = finite(x, "training features", 2)
    y = np.asarray(labels)
    if y.shape != (len(x),) or not np.isin(y, [0, 1]).all():
        raise ValueError("binary training labels required")
    if min(np.sum(y == 0), np.sum(y == 1)) < 2:
        raise ValueError("at least two localizer trials per class required")
    mean, scale = x.mean(0), x.std(0, ddof=1)
    scale = np.where(scale > 0, scale, 1.)
    z = (x - mean) / scale
    _, singular, vt = np.linalg.svd(z, full_matrices=False)
    variance = singular ** 2
    if variance.sum() <= np.finfo(float).eps:
        raise ValueError("localizer features have zero rank")
    k = int(np.searchsorted(np.cumsum(variance) / variance.sum(), .95) + 1)
    projection = vt[:k].T
    p = z @ projection
    m0, m1 = p[y == 0].mean(0), p[y == 1].mean(0)
    residual = p - np.where((y == 1)[:, None], m1, m0)
    covariance = residual.T @ residual / (len(x) - 2)
    ridge = .1 * max(float(np.trace(covariance) / k), np.finfo(float).eps)
    weight = np.linalg.solve(covariance + ridge * np.eye(k), m1 - m0)
    # Export in the input channel basis, so decision calculation is independently testable.
    w = projection @ weight / scale
    intercept = -.5 * (m1 + m0) @ weight - mean @ w
    return {"weight": w, "intercept": float(intercept), "components": k,
            "training_mean": mean, "training_scale": scale}


def temporal_decisions(localizer, labels, retrieval):
    """Inputs trial × channel × time; output trial × train-time × test-time."""
    localizer = finite(localizer, "localizer features", 3)
    retrieval = finite(retrieval, "retrieval features", 3)
    if localizer.shape[1] != retrieval.shape[1]:
        raise ValueError("channel identities/order must agree")
    models = [fit_lda(localizer[:, :, j], labels) for j in range(localizer.shape[2])]
    decisions = np.stack([np.einsum("nct,c->nt", retrieval, m["weight"]) + m["intercept"]
                          for m in models], axis=1)
    return decisions, models


def decision_confidence(decisions, train_times=TRAIN_TIMES):
    d = finite(decisions, "decisions", 3)
    t = finite(train_times, "training times", 1)
    if d.shape[1] != len(t):
        raise ValueError("training axis mismatch")
    mask = (t >= .15 - 1e-9) & (t <= 1.5 + 1e-9)
    if not mask.any():
        raise ValueError("confidence requires localizer 0.15–1.5 s")
    return np.abs(d[:, mask, :].mean(axis=1))


def temporal_auc(decisions, labels):
    d = finite(decisions, "decisions", 3)
    return np.array([[auc(labels, d[:, i, j]) for j in range(d.shape[2])]
                     for i in range(d.shape[1])])


def hann_power(eeg, axis, centers, frequencies=tuple(range(8, 21))):
    """Five-cycle symmetric Hann direct Fourier power, no zero padding.

    Output trial × channel × frequency × center. Kernel length is the nearest
    odd sample count (exact ties choose longer); this is not FieldTrip parity.
    """
    eeg = finite(eeg, "EEG", 3)
    if eeg.shape[-1] != len(axis):
        raise ValueError("EEG/time shape mismatch")
    indices = sample_indices(axis, centers)
    result = []
    for f in frequencies:
        if not 0 < f < FS / 2:
            raise ValueError("frequency outside Nyquist interval")
        length = 2 * int(math.floor((5 * FS / f) / 2)) + 1
        half = length // 2
        if np.any(indices - half < 0) or np.any(indices + half >= len(axis)):
            raise ValueError("insufficient epoch padding for five-cycle Hann power")
        offsets = np.arange(-half, half + 1)
        taper = np.hanning(length)
        kernel = taper * np.exp(-2j * np.pi * f * offsets / FS)
        values = np.stack([np.abs(eeg[..., i + offsets] @ kernel) ** 2 / np.sum(taper ** 2)
                           for i in indices], axis=-1)
        result.append(values)
    return np.stack(result, axis=2)


def baseline_alpha_beta(eeg, axis, remembered):
    """Figure-3c source policy: outcome-group pooled -1..0 s exhalation baseline.

    Each channel/frequency baseline pools trials and baseline times, using sample
    SD. This source policy differs from the journal's cue-baseline description;
    the difference remains an explicit reconciliation hold.
    """
    power = hann_power(eeg, axis, EXHALATION_TIMES)
    baseline_mask = (EXHALATION_TIMES >= -1) & (EXHALATION_TIMES <= 0)
    out = np.empty_like(power)
    remembered = np.asarray(remembered, bool)
    for group in (remembered, ~remembered):
        if not group.any():
            continue
        baseline = power[group][..., baseline_mask]
        mean = baseline.mean(axis=(0, 3), keepdims=True)
        sd = baseline.transpose(1, 2, 0, 3).reshape(power.shape[1], power.shape[2], -1).std(-1, ddof=1)[None, ..., None]
        if np.any(sd <= np.finfo(float).eps):
            raise ValueError("constant baseline power makes a z-score undefined")
        out[group] = (power[group] - mean) / sd
    return out.mean(2)


def coupling(confidence, power):
    """Across-trial Spearman at each channel/time; centered five-bin (250 ms) mean."""
    c, p = finite(confidence, "confidence", 2), finite(power, "power", 3)
    if c.shape != (p.shape[0], p.shape[2]):
        raise ValueError("confidence/power axes disagree")
    raw = np.array([[spearman(c[:, t], p[:, ch, t]) for t in range(p.shape[2])]
                    for ch in range(p.shape[1])])
    # Undefined bins remain undefined and contaminate their smoothing windows.
    smoothed = np.stack([raw[:, max(0, t - 2):min(p.shape[2], t + 3)].mean(-1)
                         for t in range(p.shape[2])], axis=1)
    return {"raw": raw, "smoothed_250ms": smoothed}


def resultant(phases):
    p = finite(phases, "phases", 1)
    if not len(p):
        return {"length": float("nan"), "mean_angle_radians": float("nan"), "n": 0}
    z = np.exp(1j * p).mean()
    return {"length": float(abs(z)), "mean_angle_radians": float(np.angle(z)), "n": len(p)}


def memory_summary(trials):
    """Figure-3b pooled hit-conditional accuracy plus four-cell diagnostics."""
    cells = []
    for session in ("object", "scene"):
        for test in ("pre", "post"):
            rows = [r for r in trials if r["session"] == session and r["test"] == test]
            if not rows:
                raise ValueError(f"missing condition cell {session}/{test}")
            hits = [r for r in rows if r["is_old"] and r["recognized"]]
            cells.append({"session": session, "test": test, "trials": len(rows),
                          "hits": len(hits), "remembered": sum(r["remembered"] for r in hits),
                          "accuracy": sum(r["remembered"] for r in hits) / len(hits) if hits else float("nan")})
    if not sum(c["hits"] for c in cells):
        raise ValueError("zero pooled recognition hits; memory endpoint is undefined")
    return {"cells": cells, "mean_four_cell_accuracy_diagnostic": float(np.mean([c["accuracy"] for c in cells])),
            "pooled_hit_accuracy": sum(c["remembered"] for c in cells) / sum(c["hits"] for c in cells)}


def validate_participant(p):
    string(p["participant_id"], "participant_id")
    channels = p["channels"]
    if not isinstance(channels, list) or not channels or len(set(channels)) != len(channels):
        raise ValueError("unique channel names required")
    for ch in channels:
        string(ch, "channel")
    loc_axis = time_axis(p["localizer_times"], "localizer_times")
    ret_axis = time_axis(p["retrieval_times"], "retrieval_times")
    exh_axis = time_axis(p["exhalation_times"], "exhalation_times")
    if loc_axis[0] > -.2 + 1e-8 or loc_axis[-1] < 3 - 1e-8:
        raise ValueError("localizer epochs must cover -0.2 to 3 s")
    if ret_axis[0] > -.2 + 1e-8 or ret_axis[-1] < 3 - 1e-8:
        raise ValueError("cue-referenced retrieval epochs must cover -0.2 to 3 s")
    if exh_axis[0] > -5 + 1e-8 or exh_axis[-1] < 5 - 1e-8:
        raise ValueError("exhalation epochs must cover -5 to 5 s")
    ids = []
    for name, axis in (("localizer", loc_axis), ("retrieval", ret_axis)):
        if not p[name]:
            raise ValueError(f"{name}: no trials")
        for row in p[name]:
            ids.append(string(row["trial_id"], "trial_id"))
            if row["session"] not in ("object", "scene"):
                raise ValueError("session must be object or scene")
            eeg = finite(row["eeg"], "trial EEG", 2)
            if eeg.shape != (len(channels), len(axis)):
                raise ValueError("trial EEG/channel/time shape mismatch")
            if name == "localizer":
                if row["category"] not in ("object", "scene"):
                    raise ValueError("localizer category must be object or scene")
            else:
                if row["test"] not in ("pre", "post"):
                    raise ValueError("retrieval test must be pre or post")
                if any(type(row[k]) is not bool for k in ("is_old", "recognized", "remembered")):
                    raise ValueError("memory fields must be booleans")
                if row["remembered"] and not (row["is_old"] and row["recognized"]):
                    raise ValueError("remembered requires a true recognition hit")
                phase = finite(row["respiration_phase_radians"], "respiration phase", 1)
                if phase.shape != axis.shape:
                    raise ValueError("respiration phase/time shape mismatch")
                events = finite(row["exhalation_trough_seconds"], "trough events", 1)
                if len(events) != len(np.unique(events)) or (len(events) > 1 and np.any(np.diff(events) <= 0)):
                    raise ValueError("trough events must be unique and sorted")
                if len(events):
                    sample_indices(axis, events)
                valid = [v for v in events if 0 < v < 3]
                if row["is_old"] and valid:
                    exheeg = finite(row["exhalation_eeg"], "exhalation EEG", 2)
                    if exheeg.shape != (len(channels), len(exh_axis)):
                        raise ValueError("exhalation EEG/channel/time shape mismatch")
                    marker = row["exhalation_epoch_trough_seconds"]
                    if not isinstance(marker, (int, float)) or not np.isfinite(marker) or abs(marker - valid[-1]) > 1e-8:
                        raise ValueError("exhalation epoch must identify the last strictly interior trough")
    if len(ids) != len(set(ids)):
        raise ValueError("trial IDs must be unique across localizer and retrieval within participant")
    if set(r["session"] for r in p["localizer"]) != {"object", "scene"}:
        raise ValueError("both localizer sessions must be present")
    return loc_axis, ret_axis, exh_axis


def analyze_participant(p):
    loc_axis, ret_axis, exh_axis = validate_participant(p)
    loc = sorted(p["localizer"], key=lambda r: r["trial_id"])
    all_ret = sorted(p["retrieval"], key=lambda r: r["trial_id"])
    behavior = memory_summary(all_ret)
    # Pinned figure_3b/3c admission: learned items, including recognition misses.
    old = [r for r in all_ret if r["is_old"]]
    if not old:
        raise ValueError("no learned retrieval trials")
    xloc = smooth_samples(np.array([r["eeg"] for r in loc]), loc_axis, TRAIN_TIMES)
    yloc = np.array([int(r["category"] == "scene") for r in loc])
    xcue = smooth_samples(np.array([r["eeg"] for r in old]), ret_axis, CUE_TIMES)
    dcue, models = temporal_decisions(xloc, yloc, xcue)
    ccue = decision_confidence(dcue)
    # Ties use the earliest time, are counted, and are not silently jittered.
    peak_indices = np.argmax(ccue, axis=1)
    phase_indices = sample_indices(ret_axis, CUE_TIMES)
    peak_phases = np.array([r["respiration_phase_radians"][phase_indices[k]] for r, k in zip(old, peak_indices)])
    remembered_old = np.array([r["remembered"] for r in old])
    peaks = resultant(peak_phases[remembered_old])
    audit, selected, troughs = [], [], []
    for r in all_ret:
        valid = [e for e in r["exhalation_trough_seconds"] if 0 < e < 3]
        reason = "foil" if not r["is_old"] else "no_trough_strictly_0_to_3s" if not valid else "included"
        audit.append({"trial_id": r["trial_id"], "status": reason,
                      "candidate_trough_count": len(valid),
                      "selected_trough_seconds": valid[-1] if reason == "included" else None})
        if reason == "included":
            selected.append(r)
            troughs.append(valid[-1])
    if not selected:
        raise ValueError("no old trials with troughs strictly inside 0–3 s")
    xexh = smooth_samples(np.array([r["exhalation_eeg"] for r in selected]), exh_axis, EXHALATION_TIMES)
    dexh, _ = temporal_decisions(xloc, yloc, xexh)
    cexh = decision_confidence(dexh)
    yret = np.array([int(r["session"] == "scene") for r in selected])
    remembered = np.array([r["remembered"] for r in selected])
    power = baseline_alpha_beta(np.array([r["exhalation_eeg"] for r in selected]), exh_axis, remembered)
    groups = {}
    for name, mask in (("remembered", remembered), ("not_remembered", ~remembered)):
        groups[name] = {"n_trials": int(mask.sum()), "n_object": int(np.sum(yret[mask] == 0)),
                        "n_scene": int(np.sum(yret[mask] == 1)),
                        "auc": temporal_auc(dexh[mask], yret[mask]),
                        "confidence_power_spearman": coupling(cexh[mask], power[mask])}
    return {"participant_id": p["participant_id"], "channels": p["channels"], "behavior": behavior,
            "localizer_trial_ids": [r["trial_id"] for r in loc],
            "localizer_components_by_training_time": [m["components"] for m in models],
            "retrieval_admission_audit": audit,
            "cue_peak_trials": [{"trial_id": r["trial_id"], "remembered": r["remembered"],
                                "peak_time_seconds": float(CUE_TIMES[k]), "peak_phase_radians": float(ph),
                                "maximum_tie_count": int(np.sum(ccue[i] == ccue[i, k]))}
                               for i, (r, k, ph) in enumerate(zip(old, peak_indices, peak_phases))],
            "remembered_peak_phase_resultant": peaks, "exhalation_groups": groups,
            "remembered_minus_not_auc": groups["remembered"]["auc"] - groups["not_remembered"]["auc"],
            "remembered_minus_not_coupling": groups["remembered"]["confidence_power_spearman"]["smoothed_250ms"] - groups["not_remembered"]["confidence_power_spearman"]["smoothed_250ms"]}


def evaluate(packet):
    """Require a declared complete 18-person cohort; never silently intersect rosters."""
    if packet.get("schema") != "respiration-epochs-v1":
        raise ValueError("schema must be respiration-epochs-v1")
    provenance = packet["provenance"]
    if provenance.get("data_kind") not in ("generated_engineering_control", "authentic_preprocessed_epochs"):
        raise ValueError("declare data_kind: generated_engineering_control or authentic_preprocessed_epochs")
    for key in ("epoch_preprocessing", "respiration_phase_convention", "trial_label_source", "cohort_source"):
        string(provenance[key], key)
    if provenance.get("sample_rate_hz") != FS:
        raise ValueError("sample_rate_hz must be 200")
    expected = packet["expected_participant_ids"]
    actual = [p["participant_id"] for p in packet["participants"]]
    if len(expected) != 18 or set(expected) != set(SOURCE_ROSTER) or len(actual) != len(set(actual)) or set(expected) != set(actual):
        raise ValueError("complete source-pinned 18-person roster required with no duplicates, additions or omissions")
    if any(p["channels"] != packet["participants"][0]["channels"] for p in packet["participants"]):
        raise ValueError("all participants must have identical channel identities and order")
    start = time.perf_counter()
    rows = [analyze_participant(p) for p in sorted(packet["participants"], key=lambda p: p["participant_id"])]
    lengths = [r["remembered_peak_phase_resultant"]["length"] for r in rows]
    memory = [r["behavior"]["pooled_hit_accuracy"] for r in rows]
    return {"task_id": TASK_ID, "recipe": RECIPE, "classification": "prospective_engineering_analysis",
            "scientifically_qualified": False, "binary_reward": None, "holds": HOLDS,
            "input_provenance": provenance, "participant_ids": sorted(expected),
            "grids_seconds": {"localizer_training": TRAIN_TIMES, "cue_peak_search": CUE_TIMES,
                              "exhalation": EXHALATION_TIMES},
            "participants": rows,
            "group": {"n_participants": len(rows), "channels": rows[0]["channels"],
                      "peak_resultant_vs_memory_spearman": spearman(lengths, memory),
                      "auc_difference_equal_participant_mean": np.mean([r["remembered_minus_not_auc"] for r in rows], axis=0),
                      "coupling_difference_equal_participant_mean": np.mean([r["remembered_minus_not_coupling"] for r in rows], axis=0),
                      "inference": "descriptive_only_no_cluster_p_values_or_pass_threshold"},
            "runtime": {"elapsed_seconds": time.perf_counter() - start, "numpy": np.__version__, "scipy": scipy_version}}


def json_safe(value):
    if isinstance(value, np.ndarray):
        return json_safe(value.tolist())
    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, (float, np.floating)) and not math.isfinite(value):
        return None
    if isinstance(value, np.generic):
        return value.item()
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    raw = args.input.read_bytes()
    report = evaluate(json.loads(raw))
    report["input_sha256"] = hashlib.sha256(raw).hexdigest()
    report["undefined_value_encoding"] = "null; no imputation or participant deletion"
    args.output.write_text(json.dumps(json_safe(report), indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
