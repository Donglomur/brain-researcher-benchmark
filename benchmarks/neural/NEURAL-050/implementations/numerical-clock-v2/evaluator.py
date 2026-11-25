#!/usr/bin/env python3
"""NEURAL-050 numerical clock repair; prospective development evaluator only."""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime
from fractions import Fraction
import hashlib
import io
import json
import math
from pathlib import Path
import sys

import numpy as np

IMPLEMENTATION = "NEURAL-050-numerical-clock-v2"

PROTOCOL = {
    "id": "NEURAL-050-prospective-v1",
    "window_seconds": 2.0,
    "gamma_band_hz_half_open": [80.0, 100.0],
    "pose_min_confidence": 0.4,
    "ridge_alpha": 1.0,
    "time_match_bin_seconds": 3600.0,
    "max_pair_separation_seconds": 300.0,
    "guard_seconds": 2.0,
    "bootstrap_replicates": 2000,
    "random_seed": 50,
}
GATES = [
    "Full selected AJILE12 payload, clock/alignment and hash qualification",
    "Preregistered motor anatomy, contralateral wrist and pose-scale validity",
    "Source-qualified gap, line/muscle/noise, bad-channel and pose QC",
    "Prospective estimator, population/exclusion and resource protocol approval",
    "Protected packet/access controls; all current data are public development",
    "Authentic signal-derived reference/comparator execution and independent replication",
    "Scientific admission, native parity, rights/access and submission readiness",
]


def require(ok, message):
    if not ok:
        raise ValueError(message)


def number(value, name):
    require(isinstance(value, (int, float)) and not isinstance(value, bool), name + " must be numeric")
    require(math.isfinite(value), name + " must be finite")
    return float(value)


def identifier(value, name):
    require(isinstance(value, str) and bool(value.strip()), name + " must be a nonempty string")
    return value


def canonical_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path):
    def pairs(items):
        out = {}
        for key, value in items:
            require(key not in out, "duplicate JSON key: " + key)
            out[key] = value
        return out
    return json.loads(Path(path).read_text(), object_pairs_hook=pairs,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError("nonfinite JSON: " + x)))


def regular_clock(times, name):
    times = np.asarray(times, dtype=float)
    require(times.ndim == 1 and len(times) >= 3 and np.isfinite(times).all(), name + " invalid clock")
    dt = np.diff(times)
    require((dt > 0).all(), name + " clock must increase strictly")
    # Use the full observed span, so cancellation in a single pair of offset
    # timestamps does not determine every FFT frequency. This neither resets
    # stream origins nor rounds the measured rate to the advertised 500 Hz.
    step = (times[-1] - times[0]) / (len(times) - 1)
    require(np.allclose(dt, step, rtol=1e-6, atol=1e-8), name + " clock must be regular; gaps require explicit QC masks")
    return times, float(1.0 / step)


def rate_roundoff_bound(times):
    """Conservative relative error bound for floating-point endpoint subtraction.

    This covers binary64 representation/arithmetic only, not clock calibration,
    source synchronization error, or irregular sampling admitted by QC tolerance.
    """
    span = float(times[-1] - times[0])
    ulp = float(np.spacing(np.max(np.abs(times))))
    return 4 * ulp / span + 8 * np.finfo(float).eps


def gamma_bin_slice(n_samples, fs, relative_rate_roundoff):
    """Select [80,100) in integer FFT-bin coordinates with roundoff-only snaps."""
    require(type(n_samples) is int and n_samples >= 3, "invalid FFT sample count")
    fs = number(fs, "sample rate")
    uncertainty = number(relative_rate_roundoff, "relative rate roundoff")
    lower, upper = PROTOCOL["gamma_band_hz_half_open"]
    require(fs > 2 * upper and uncertainty >= 0, "invalid gamma frequency grid")
    coordinates = np.array([lower, upper]) * n_samples / fs
    # Integer comparisons encode the half-open endpoint without a floating-point
    # rfftfreq comparison. Snap only within a propagated binary64 error bound.
    tolerance = np.abs(coordinates) * (uncertainty + 8 * np.finfo(float).eps)
    require((tolerance < 0.25).all(), "clock precision cannot resolve gamma band edges")
    nearest = np.rint(coordinates)
    snapped = np.abs(coordinates - nearest) <= tolerance
    stable = np.where(snapped, nearest, coordinates)
    first, stop = (int(math.ceil(value)) for value in stable)
    require(0 < first < stop <= n_samples // 2, "gamma band has no interior FFT support")
    return slice(first, stop), {
        "sample_count": n_samples,
        "inferred_sample_rate_hz": fs,
        "rate_estimator": "full_clock_endpoint_span",
        "relative_rate_roundoff_bound": uncertainty,
        "band_hz_half_open": [lower, upper],
        "fft_bin_start": first,
        "fft_bin_stop_exclusive": stop,
        "edge_bin_coordinates_before_roundoff_correction": coordinates.tolist(),
        "edge_bin_roundoff_tolerances": tolerance.tolist(),
        "edge_roundoff_snapped": snapped.tolist(),
    }


def interval_indices(times, left, right, inclusive_right=False):
    """Exact bounded index selection on a previously validated sorted clock."""
    start = np.searchsorted(times, left - 1e-8, side="left")
    end = np.searchsorted(times, right + 1e-8 if inclusive_right else right - 1e-8,
                          side="right" if inclusive_right else "left")
    return np.arange(start, end)


def prepare(manifest, directory=Path(".")):
    """Build disjoint features from local, hash-bound raw-array exports, never fetch data."""
    require(manifest.get("schema") == "neural050-raw-v1", "wrong raw schema")
    require(manifest.get("data_scope") == "public_development_only", "development scope required")
    require(manifest.get("protocol") == PROTOCOL, "exact prospective protocol required")
    require(manifest.get("input_kind") in ("generated_engineering_control", "ajile12_export"), "explicit input kind required")
    require(manifest.get("source_dataset") == {"dandiset": "000055", "version": "0.220127.0436"}, "exact source dataset/version required")
    recordings = manifest.get("recordings")
    require(isinstance(recordings, list) and recordings, "recordings required")
    rows, source_pins, excluded = [], [], []
    seen = set()
    for rec in recordings:
        patient = identifier(rec.get("patient"), "patient")
        day = identifier(rec.get("day"), "day")
        session = identifier(rec.get("session"), "session")
        require((patient, session) not in seen, "duplicate patient/session")
        seen.add((patient, session))
        for key in ("anatomy_evidence", "wrist_selection_evidence", "clock_evidence", "artifact_mask_evidence", "pose_units", "source_asset_path", "source_asset_id"):
            identifier(rec.get(key), key)
        require(rec["pose_units"] == "pixels", "v1 requires source pixel coordinates; do not silently mix units")
        dt = datetime.fromisoformat(rec["session_start_utc"].replace("Z", "+00:00"))
        require(dt.tzinfo is not None and dt.utcoffset().total_seconds() == 0, "session_start_utc requires UTC timezone")
        epoch = dt.timestamp()
        utc_offset = number(rec["local_utc_offset_seconds"], "local UTC offset")
        require(abs(utc_offset) <= 14 * 3600, "invalid UTC offset")
        local_day = datetime.fromtimestamp(epoch + utc_offset, tz=dt.tzinfo).date().isoformat()
        require(day == local_day, "day must match local date at recording origin")
        path = (Path(directory) / rec["path"]).resolve()
        expected = rec.get("sha256")
        require(isinstance(expected, str) and len(expected) == 64, "raw payload SHA256 mismatch")
        # Bind the decoded arrays to exactly the bytes authenticated here. A
        # later replacement of the pathname must not change these features.
        payload = path.read_bytes()
        require(hashlib.sha256(payload).hexdigest() == expected, "raw payload SHA256 mismatch")
        with np.load(io.BytesIO(payload), allow_pickle=False) as data:
            required = {"ecog", "ecog_time_s", "ecog_valid", "pose_xy", "pose_time_s", "pose_confidence", "pose_valid"}
            require(set(data.files) == required, "raw array fields differ from contract")
            arrays = {k: data[k] for k in required}
        del payload
        et, fs = regular_clock(arrays["ecog_time_s"], "ecog")
        rate_roundoff = rate_roundoff_bound(et)
        pt, pose_fs = regular_clock(arrays["pose_time_s"], "pose")
        require(fs > 2 * PROTOCOL["gamma_band_hz_half_open"][1], "gamma band exceeds Nyquist")
        ecog = np.asarray(arrays["ecog"], float)
        pose = np.asarray(arrays["pose_xy"], float)
        confidence = np.asarray(arrays["pose_confidence"], float)
        ev, pv = arrays["ecog_valid"], arrays["pose_valid"]
        require(ecog.ndim == 2 and len(ecog) == len(et), "ecog shape mismatch")
        require(pose.shape == (len(pt), 2) and confidence.shape == (len(pt),), "pose shape mismatch")
        require(ev.dtype == np.bool_ and ev.shape == (len(et),), "ecog_valid must be a boolean sample mask")
        require(pv.dtype == np.bool_ and pv.shape == (len(pt),), "pose_valid must be a boolean frame mask")
        require(np.isfinite(confidence).all() and ((confidence >= 0) & (confidence <= 1)).all(), "pose confidence outside [0,1]")
        channels = rec.get("motor_channels")
        require(isinstance(channels, list) and channels and len(set(channels)) == len(channels), "unique motor channels required")
        require(all(type(c) is int and 0 <= c < ecog.shape[1] for c in channels), "invalid motor channel")
        epochs = rec.get("behavior_epochs")
        require(isinstance(epochs, list) and epochs, "behavior epochs required")
        intervals = []
        for item in epochs:
            start = number(item["start_s"], "epoch start")
            stop = number(item["stop_s"], "epoch stop")
            require(start < stop, "invalid behavior epoch")
            intervals.append((start, stop, identifier(item["state"], "state")))
        intervals.sort()
        width = PROTOCOL["window_seconds"]
        start = math.ceil(max(et[0], pt[0]) / width) * width
        last = min(et[-1] + 1 / fs, pt[-1])
        count = 0
        spectral_grid = None
        for left in np.arange(start, last - width + 1e-8, width):
            right = left + width
            ei = interval_indices(et, left, right)
            pi = interval_indices(pt, left, right, inclusive_right=True)
            covering = [state for a, b, state in intervals if a <= left and b >= right]
            reasons = []
            if len(ei) != round(width * fs) or len(pi) < 2 or pt[pi[-1]] - pt[pi[0]] < width - 1 / pose_fs - 1e-8:
                reasons.append("incomplete_clock_support")
            crossing = any(a < right and b > left and not (a <= left and b >= right) for a, b, _ in intervals)
            if not covering or crossing:
                reasons.append("behavior_boundary_or_missing")
            if not ev[ei].all() or not pv[pi].all() or not (confidence[pi] >= PROTOCOL["pose_min_confidence"]).all():
                reasons.append("artifact_or_pose_QC")
            if not np.isfinite(ecog[ei][:, channels]).all() or not np.isfinite(pose[pi]).all():
                reasons.append("nonfinite_signal")
            if reasons:
                excluded.append({"patient": patient, "session": session, "start_s": float(left), "reasons": reasons})
                continue
            x = ecog[ei][:, channels]
            x = x - x.mean(axis=0)
            taper = np.hanning(len(x))
            spectrum = np.fft.rfft(x * taper[:, None], axis=0)
            band, spectral_grid = gamma_bin_slice(len(x), fs, rate_roundoff)
            # One-sided periodogram integrated over band; no cross-window filtering.
            power = (2 * np.abs(spectrum[band]) ** 2 / (fs * np.sum(taper ** 2))).sum(axis=0) * fs / len(x)
            require(np.isfinite(power).all() and (power > 0).all(), "zero/invalid gamma power; cannot log")
            gamma = float(np.log(power).mean())
            speed = float(np.linalg.norm(np.diff(pose[pi], axis=0), axis=1).sum() / (pt[pi[-1]] - pt[pi[0]]))
            midpoint = epoch + (left + right) / 2
            # Reject cross-midnight exports: assign actual local days at intake instead.
            require(datetime.fromtimestamp(epoch + right + utc_offset - 1e-6, tz=dt.tzinfo).date().isoformat() == day, "recording crosses local day; split export at midnight")
            rows.append({"id": f"{patient}/{session}/{count}", "patient": patient, "day": day, "session": session,
                         "start_utc_s": float(epoch + left), "stop_utc_s": float(epoch + right),
                         "local_seconds": float((midpoint + utc_offset) % 86400), "state": json.dumps(sorted(set(covering)), separators=(",", ":")),
                         "gamma": gamma, "movement": speed})
            count += 1
        require(count > 0, "recording has no admissible feature windows")
        source_pins.append({"patient": patient, "day": day, "session": session, "sha256": expected,
                            "ecog_hz": fs, "pose_hz": pose_fs, "n_windows": count,
                            "gamma_frequency_grid": spectral_grid,
                            "motor_channels": channels, "extraction_manifest_record": dict(rec), **{k: rec[k] for k in ("anatomy_evidence", "wrist_selection_evidence", "clock_evidence", "artifact_mask_evidence", "pose_units")}})
    result = {"schema": "neural050-features-v1", "data_scope": "public_development_only", "protocol": PROTOCOL,
              "feature_preparation_implementation": IMPLEMENTATION,
              "source_pins": source_pins, "rows": rows, "excluded_windows": excluded,
              "raw_manifest_sha256": canonical_digest(manifest), "source_dataset": manifest["source_dataset"], "input_kind": manifest["input_kind"]}
    validate_features(result)
    return result


def validate_features(packet):
    require(packet.get("schema") == "neural050-features-v1", "wrong feature schema")
    require(packet.get("data_scope") == "public_development_only", "development scope required")
    require(packet.get("protocol") == PROTOCOL, "prospective protocol mismatch")
    require(packet.get("input_kind") in ("generated_engineering_control", "ajile12_export"), "explicit feature input kind required")
    require(packet.get("source_dataset") == {"dandiset": "000055", "version": "0.220127.0436"}, "exact feature source dataset/version required")
    manifest_hash = packet.get("raw_manifest_sha256")
    require(isinstance(manifest_hash, str) and len(manifest_hash) == 64 and all(c in "0123456789abcdef" for c in manifest_hash), "raw manifest SHA256 required")
    require(isinstance(packet.get("source_pins"), list) and packet["source_pins"], "raw provenance required")
    rows = packet.get("rows")
    require(isinstance(rows, list) and rows, "feature rows required")
    pins = {}
    for pin in packet["source_pins"]:
        key = (identifier(pin.get("patient"), "pin patient"), identifier(pin.get("session"), "pin session"))
        require(key not in pins, "duplicate source pin")
        identifier(pin.get("day"), "pin day")
        sha = pin.get("sha256")
        require(isinstance(sha, str) and len(sha) == 64 and all(c in "0123456789abcdef" for c in sha), "invalid source SHA256")
        pins[key] = pin
    seen, by_patient = set(), defaultdict(list)
    for row in rows:
        for key in ("id", "patient", "day", "session", "state"):
            identifier(row.get(key), key)
        require((row["patient"], row["session"]) in pins and pins[(row["patient"], row["session"])]["day"] == row["day"], "row has no matching source pin")
        require(row["id"] not in seen, "duplicate row ID")
        seen.add(row["id"])
        for key in ("start_utc_s", "stop_utc_s", "local_seconds", "gamma", "movement"):
            number(row.get(key), key)
        require(row["stop_utc_s"] - row["start_utc_s"] == PROTOCOL["window_seconds"], "feature support must equal fixed window")
        require(0 <= row["local_seconds"] < 86400 and row["movement"] >= 0, "invalid time/movement")
        by_patient[row["patient"]].append(row)
    for values in by_patient.values():
        ordered = sorted(values, key=lambda r: r["start_utc_s"])
        require(all(a["stop_utc_s"] <= b["start_utc_s"] for a, b in zip(ordered, ordered[1:])), "patient feature supports overlap, including across sessions/days")
    return sorted(rows, key=lambda r: r["id"])


def balanced_weights(rows):
    groups = defaultdict(list)
    for i, row in enumerate(rows):
        groups[(row["patient"], row["day"])].append(i)
    days = defaultdict(int)
    for patient, _ in groups:
        days[patient] += 1
    weights = np.zeros(len(rows))
    for (patient, _), ids in groups.items():
        weights[ids] = 1 / (len(days) * days[patient] * len(ids))
    return weights


def fit_predict(train, test, augmented):
    states = sorted({r["state"] for r in train})
    require(all(r["state"] in states for r in test), "held-out behavior state absent from training")
    def design(rows):
        out = []
        for r in rows:
            phase = 2 * np.pi * r["local_seconds"] / 86400
            values = [float(r["state"] == s) for s in states[1:]] + [math.sin(phase), math.cos(phase)]
            if augmented:
                values.append(r["gamma"])
            out.append(values)
        return np.asarray(out, float)
    x, z = design(train), design(test)
    w = balanced_weights(train)
    mean = (w[:, None] * x).sum(axis=0)
    scale = np.sqrt((w[:, None] * (x - mean) ** 2).sum(axis=0))
    scale[scale < 1e-12] = 1
    x = np.column_stack([np.ones(len(x)), (x - mean) / scale])
    z = np.column_stack([np.ones(len(z)), (z - mean) / scale])
    penalty = np.eye(x.shape[1]) * PROTOCOL["ridge_alpha"]
    penalty[0, 0] = 0
    # Weighted objective is mean squared error + alpha * ||beta||^2.
    beta = np.linalg.solve(x.T @ (w[:, None] * x) + penalty, x.T @ (w * np.array([r["movement"] for r in train])))
    prediction = z @ beta
    require(np.isfinite(prediction).all(), "nonfinite fitted predictions")
    return prediction, {"states": states, "training_mean": mean.tolist(), "training_scale": scale.tolist(), "coefficients": beta.tolist()}


def folds(rows, mode):
    require(mode in ("population_transfer", "within_patient_days"), "invalid split mode")
    patients = sorted({r["patient"] for r in rows})
    if mode == "population_transfer":
        require(len(patients) >= 3, "population transfer needs at least three patients")
        cases = [(p, None) for p in patients]
    else:
        cases = []
        for p in patients:
            days = sorted({r["day"] for r in rows if r["patient"] == p})
            require(len(days) >= 2, "within-patient mode needs at least two days for every patient")
            cases.extend((p, d) for d in days)
    for patient, day in cases:
        test = [r for r in rows if r["patient"] == patient and (day is None or r["day"] == day)]
        train = [r for r in rows if (r["patient"] != patient if day is None else r["patient"] == patient and r["day"] != day)]
        require(len(train) >= 4 and len(test) >= 4, "insufficient training/test windows")
        if day is not None:
            ordered = sorted(test, key=lambda r: r["start_utc_s"])
            starts = np.array([r["start_utc_s"] for r in ordered])
            for a in train:
                position = int(np.searchsorted(starts, a["start_utc_s"]))
                for i in (position - 1, position):
                    if 0 <= i < len(ordered):
                        b = ordered[i]
                        require(a["stop_utc_s"] + PROTOCOL["guard_seconds"] <= b["start_utc_s"] or b["stop_utc_s"] + PROTOCOL["guard_seconds"] <= a["start_utc_s"], "split violates continuous support guard")
        yield f"{patient}/{day or 'all-days'}", train, test


def _variance_fallback(y, baseline, augmented):
    """Recover reportable ratios when the variance intermediate is out of range."""
    observed = [Fraction(float(value)) for value in y]
    count = len(observed)
    mean = sum(observed) / count
    variance = sum((value - mean) ** 2 for value in observed) / count
    require(variance > 0, "nonconstant target is not distinct in binary64")
    errors = [sum((target - Fraction(float(prediction))) ** 2
                  for target, prediction in zip(observed, values, strict=True)) / count
              for values in (baseline, augmented)]
    delta = errors[0] - errors[1]
    result = []
    for name, value in zip(("baseline MSE", "gamma MSE", "delta MSE", "delta R2"),
                           (*errors, delta, delta / variance), strict=True):
        try:
            rounded = float(value)
        except OverflowError as error:
            raise ValueError(name + " is not representable") from error
        require(math.isfinite(rounded), name + " is not representable")
        result.append(rounded)
    return result


def score_predictions(rows, baseline, augmented):
    ids = {r["id"] for r in rows}
    require(set(baseline) == ids and set(augmented) == ids, "prediction IDs must equal complete target IDs")
    groups = defaultdict(list)
    for row in rows:
        for values in (baseline, augmented):
            number(values[row["id"]], "prediction")
        groups[(row["patient"], row["day"])].append(row)
    results = []
    for (patient, day), values in sorted(groups.items()):
        y = np.array([r["movement"] for r in values])
        b = np.array([baseline[r["id"]] for r in values])
        a = np.array([augmented[r["id"]] for r in values])
        constant_target = bool(np.all(y == y[0]))
        denominator = float(np.mean((y - y.mean()) ** 2))
        # Constancy is an exact property of the observed target, not an absolute
        # threshold in pixel units. Keep the established arithmetic for ordinary
        # variances; an under/overflowed intermediate need not invalidate a finite
        # normalized score. The rare fallback uses the exact binary64 operands.
        mb, ma = float(np.mean((y - b) ** 2)), float(np.mean((y - a) ** 2))
        if not constant_target and (not math.isfinite(denominator) or denominator <= 0):
            mb, ma, delta, delta_r2 = _variance_fallback(y, b, a)
        else:
            delta = mb - ma
            delta_r2 = delta / denominator if not constant_target else None
        results.append({"patient": patient, "day": day, "n_windows": len(y), "baseline_mse": mb, "gamma_mse": ma,
                        "delta_mse": delta, "delta_r2": delta_r2,
                        "constant_target": constant_target, "constant_gamma_prediction": bool(np.ptp(a) <= 1e-12)})
    return results


def matched_contrasts(test, threshold):
    groups = defaultdict(list)
    for row in test:
        key = (row["patient"], row["day"], row["state"], int(row["local_seconds"] // PROTOCOL["time_match_bin_seconds"]))
        groups[key].append(row)
    pairs, unmatched = [], 0
    for key, rows in sorted(groups.items()):
        high = sorted([r for r in rows if r["movement"] > threshold], key=lambda r: (r["start_utc_s"], r["id"]))
        low = {r["id"]: r for r in rows if r["movement"] <= threshold}
        for h in high:
            eligible = [l for l in low.values() if abs(h["start_utc_s"] - l["start_utc_s"]) <= PROTOCOL["max_pair_separation_seconds"]]
            if not eligible:
                unmatched += 1
                continue
            l = min(eligible, key=lambda r: (abs(h["start_utc_s"] - r["start_utc_s"]), r["id"]))
            del low[l["id"]]
            pairs.append({"patient": key[0], "day": key[1], "state": key[2], "hour_bin": key[3], "high_id": h["id"], "low_id": l["id"],
                          "gamma_difference": h["gamma"] - l["gamma"], "movement_difference": h["movement"] - l["movement"]})
        unmatched += len(low)
    return pairs, unmatched


def patient_summary(day_values, field):
    groups = defaultdict(list)
    for row in day_values:
        if row[field] is not None:
            groups[row["patient"]].append(row[field])
    values = {p: float(np.mean(v)) for p, v in sorted(groups.items())}
    x = np.array(list(values.values()))
    out = {"n_days_total": len(day_values), "n_days_defined": sum(r[field] is not None for r in day_values), "patient_values": values, "n_patients": len(x), "mean": float(x.mean()) if len(x) else None,
           "percentile_95_interval": None, "inference": "descriptive development cluster bootstrap; scientific admission unresolved"}
    if len(x) >= 2:
        rng = np.random.default_rng(PROTOCOL["random_seed"])
        draws = x[rng.integers(0, len(x), (PROTOCOL["bootstrap_replicates"], len(x)))].mean(axis=1)
        out["percentile_95_interval"] = np.quantile(draws, [0.025, 0.975]).tolist()
    return out


def shifted_gamma(rows):
    groups = defaultdict(list)
    copied = [dict(r) for r in rows]
    for r in copied:
        groups[(r["patient"], r["day"])].append(r)
    for values in groups.values():
        values.sort(key=lambda r: (r["start_utc_s"], r["id"]))
        shift = max(1, len(values) // 2)
        gamma = np.roll([r["gamma"] for r in values], shift)
        for r, value in zip(values, gamma):
            r["gamma"] = float(value)
    return copied


def evaluate(packet, mode="population_transfer"):
    rows = validate_features(packet)
    baseline, augmented, null, audit, pairs = {}, {}, {}, [], []
    unmatched = 0
    for name, train, test in folds(rows, mode):
        b, bfit = fit_predict(train, test, False)
        a, afit = fit_predict(train, test, True)
        n, _ = fit_predict(shifted_gamma(train), shifted_gamma(test), True)
        for r, pb, pa, pn in zip(test, b, a, n):
            baseline[r["id"]], augmented[r["id"]], null[r["id"]] = float(pb), float(pa), float(pn)
        # Unweighted median is a prospective event definition, derived only from this fold's train targets.
        threshold = float(np.median([r["movement"] for r in train]))
        matched, missing = matched_contrasts(test, threshold)
        pairs.extend(matched)
        unmatched += missing
        audit.append({"fold": name, "train_ids": [r["id"] for r in train], "test_ids": [r["id"] for r in test],
                      "train_movement_median": threshold, "baseline_fit": bfit, "gamma_fit": afit})
    days = score_predictions(rows, baseline, augmented)
    null_days = score_predictions(rows, baseline, null)
    grouped_pairs = defaultdict(list)
    for pair in pairs:
        grouped_pairs[(pair["patient"], pair["day"])].append(pair["gamma_difference"])
    pair_days = [{"patient": p, "day": d, "gamma_difference": float(np.mean(v)), "n_pairs": len(v)} for (p, d), v in sorted(grouped_pairs.items())]
    matched_counts = {(p, d): len(v) for (p, d), v in grouped_pairs.items()}
    coverage = [{"patient": d["patient"], "day": d["day"], "n_windows": d["n_windows"], "n_pairs": matched_counts.get((d["patient"], d["day"]), 0)} for d in days]
    return {"schema": "neural050-report-v1", "feature_packet_sha256": canonical_digest(packet),
            "evaluation_implementation": IMPLEMENTATION,
            "feature_preparation_implementation": packet.get("feature_preparation_implementation", "unrecorded"),
            "raw_manifest_sha256": packet["raw_manifest_sha256"], "input_kind": packet["input_kind"], "source_dataset": packet["source_dataset"], "protocol": PROTOCOL, "split_mode": mode,
            "scientific_qualification": "unknown", "data_scope": "public_development_only", "preserved_gates": GATES,
            "estimand": "Same-window source-pixel wrist speed: state/time baseline MSE minus gamma-augmented MSE; equal day within patient, equal patient",
            "day_metrics": days, "incremental_delta_r2": patient_summary(days, "delta_r2"),
            "incremental_delta_mse_pixels2_per_s2": patient_summary(days, "delta_mse"),
            "matched_gamma_log_power_difference": patient_summary(pair_days, "gamma_difference"),
            "matched_day_metrics": pair_days, "matched_coverage": {"n_evaluated_patients": len({r["patient"] for r in rows}), "n_matched_patients": len({p["patient"] for p in pairs}), "n_evaluated_days": len(days), "n_matched_days": len(pair_days), "days": coverage}, "pairs": pairs, "n_unmatched_windows": unmatched,
            "day_half_circular_shift_diagnostic": {"delta_r2": patient_summary(null_days, "delta_r2"), "day_metrics": null_days,
                "interpretation": "Fixed within-day half-sequence shift preserves ordered structure except wrap; diagnostic only, not exchangeable randomization or p-value; gaps and state changes can invalidate a null interpretation"},
            "predictions": {"baseline": baseline, "gamma": augmented, "day_shift_gamma": null}, "fold_audit": audit,
            "source_pins": packet["source_pins"], "excluded_windows": packet.get("excluded_windows", [])}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "evaluate"])
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--mode", choices=["population_transfer", "within_patient_days"], default="population_transfer")
    args = parser.parse_args(argv)
    try:
        require(args.input.resolve() != args.output.resolve(), "input/output paths must differ")
        packet = read_json(args.input)
        result = prepare(packet, args.input.parent) if args.command == "prepare" else evaluate(packet, args.mode)
        content = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
        args.output.write_text(content)
    except (ValueError, KeyError, TypeError, OSError, np.linalg.LinAlgError) as error:
        print(f"NEURAL-050: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
