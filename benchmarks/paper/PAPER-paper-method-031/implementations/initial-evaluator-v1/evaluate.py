"""FAST construction evaluator: full movie coverage, fixed ROIs, no real clean target.

NumPy is the only runtime dependency. See ../.. /docs/initial-evaluator-v1.md.
This is a prospective measurement recipe, never a scientific qualification gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np

TASK_ID = "PAPER-paper-method-031"
SOURCE_COMMIT = "6f92663f7a36589507cac57c8d24cfd8adbce7b1"
CONTRACT_SHA256 = "1b43d761bbefff82386fa2a5ae7f03a6a83dc3a62c38abbbfd63b520cdd67b90"
TIMING_BOUNDARY = "input_available_through_output_available_including_io_transfers_preprocess_inference_postprocess"
HOLDS = [
    "No authentic FAST or comparator execution/reference has been established.",
    "Figure-specific source normalization, sampling, SNR definitions and numerical tolerances remain unfrozen.",
    "No real fluorescence image has been assigned a universal clean target.",
    "Authentic archive ingestion, full population/collection inclusion and synchronization require independent audit.",
    "Full five-collection paper, segmentation, SSIM and volumetric endpoints are not implemented here.",
    "Protected reference panel, model exposure, source/weight rights and grouped improvement qualification remain open.",
    "Zenodo README leaves reused real files 1/3/4 under original-source terms; deposit-level CC BY does not clear them.",
    "Timing receipts and fit/exposure declarations are caller supplied; native attempt-level leakage and resource audit remain required.",
]


class ContractError(ValueError):
    """Input cannot be compared under the frozen prospective recipe."""


def require(condition, message):
    if not condition:
        raise ContractError(message)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def finite_number(value, name, *, positive=False):
    require(isinstance(value, (int, float)) and not isinstance(value, bool), f"{name}: expected number")
    require(math.isfinite(value) and (not positive or value > 0), f"{name}: invalid finite value")
    return float(value)


def integer(value, name, minimum=0):
    require(isinstance(value, int) and not isinstance(value, bool) and value >= minimum, f"{name}: invalid integer")
    return value


def nonempty(value, name):
    require(isinstance(value, str) and bool(value.strip()), f"{name}: nonempty string required")
    return value


def load_array(descriptor, base, name):
    require(isinstance(descriptor, dict), f"{name}: array descriptor required")
    path = (base / nonempty(descriptor.get("path"), name + ".path")).resolve()
    require(path.suffix == ".npy", f"{name}: use explicit time-first .npy export")
    digest = nonempty(descriptor.get("sha256"), name + ".sha256")
    require(sha256(path) == digest, f"{name}: SHA256 mismatch")
    data = np.load(path, mmap_mode="r", allow_pickle=False)
    require(data.dtype.kind in "uif", f"{name}: numeric non-complex array required")
    require(data.size > 0, f"{name}: empty array")
    for start in range(0, len(data), 64):
        require(np.isfinite(data[start:start + 64]).all(), f"{name}: nonfinite values")
    return data


def correlation(x, y):
    """Unshifted Pearson r; constant inputs remain explicitly undefined."""
    a = np.asarray(x, dtype=np.float64) - np.mean(x, dtype=np.float64)
    b = np.asarray(y, dtype=np.float64) - np.mean(y, dtype=np.float64)
    norm = np.linalg.norm(a) * np.linalg.norm(b)
    require(np.isfinite(norm), "correlation overflow")
    return None if norm == 0 else float(np.clip(np.dot(a, b) / norm, -1, 1))


def strict_mean(values):
    return None if not values or any(v is None for v in values) else float(np.mean(values))


def extract_traces(movie, masks):
    require(movie.ndim == 3 and movie.shape[0] >= 3, "movie must be (time,y,x), at least 3 frames")
    require(masks.ndim == 3 and masks.shape[1:] == movie.shape[1:], "ROI masks must be (roi,y,x) matching movie")
    require(np.isin(masks, [0, 1]).all(), "ROI masks must be fixed binary masks")
    weights = np.asarray(masks, dtype=np.float64).reshape(masks.shape[0], -1)
    counts = weights.sum(axis=1)
    require((counts > 0).all(), "empty ROI is forbidden")
    require(len(np.unique(weights, axis=0)) == len(weights), "duplicate ROI masks are forbidden")
    weights /= counts[:, None]
    traces = np.empty((len(movie), len(masks)), dtype=np.float64)
    for start in range(0, len(movie), 64):
        block = np.asarray(movie[start:start + 64], dtype=np.float64).reshape(-1, weights.shape[1])
        traces[start:start + len(block)] = block @ weights.T
    return traces


def delta_f_over_f(traces, baseline_frames):
    baseline = traces[baseline_frames].mean(axis=0)
    require((baseline > 0).all(), "baseline fluorescence must be positive; no silent epsilon or rescaling")
    dff = (traces - baseline) / baseline
    require(np.isfinite(dff).all(), "dff overflow; baseline is not numerically usable")
    return dff, baseline


def trace_measurements(traces, record, comparator=None):
    indices = record["baseline_frames"]
    dff, baseline = delta_f_over_f(traces, indices)
    out = {"baseline_fluorescence": baseline.tolist(), "dff": dff.tolist(),
           "zero_lag_pearson_by_roi": None if comparator is None else
           [correlation(dff[:, i], comparator[:, i]) for i in range(dff.shape[1])],
           "event_measurements": []}
    std = np.std(dff[indices], axis=0, ddof=1)
    for start, stop in record["event_windows"]:
        segment = record["event_polarity"] * dff[start:stop]
        peaks = segment.max(axis=0)
        sample = start + segment.argmax(axis=0)
        event = {"window_frames": [start, stop], "peak_dff_oriented": peaks.tolist(),
                 "peak_frame": sample.tolist(),
                 "event_to_baseline_std_proxy": [None if s == 0 else float(p / s) for p, s in zip(peaks, std)]}
        if comparator is not None:
            reference_polarity = record["event_polarity"] if record["kind"] == "synthetic" else record.get("reference_event_polarity", record["event_polarity"])
            ref_segment = reference_polarity * comparator[start:stop]
            ref_sample = start + ref_segment.argmax(axis=0)
            event["peak_time_error_ms"] = ((sample - ref_sample) * 1000 / record["frame_rate_hz"]).tolist()
            if record["kind"] == "synthetic":
                event["peak_dff_error"] = (peaks - ref_segment.max(axis=0)).tolist()
        out["event_measurements"].append(event)
    return out


def image_error(prediction, clean, data_range):
    """Synthetic-only pooled full-movie MSE/PSNR with externally fixed range."""
    require(prediction.shape == clean.shape, "clean/prediction shape mismatch")
    squared_error = 0.0
    for start in range(0, len(clean), 64):
        diff = np.asarray(prediction[start:start + 64], dtype=np.float64) - np.asarray(clean[start:start + 64], dtype=np.float64)
        squared_error += float(np.sum(diff * diff))
    mse = squared_error / clean.size
    require(math.isfinite(mse), "image error overflow")
    return {"mse": mse, "psnr_db": None if mse == 0 else float(20 * math.log10(data_range) - 10 * math.log10(mse)),
            "psnr_status": "positive_infinity_exact_match" if mse == 0 else "finite",
            "data_range": data_range}


def validate_record(record):
    for name in ("id", "group_id", "collection_id", "source_asset", "source_checksum", "export_provenance", "roi_provenance"):
        nonempty(record.get(name), name)
    integer(record.get("original_frame_count"), "original_frame_count", 3)
    require(record.get("frame_ids") == list(range(record["original_frame_count"])), "record must declare all original frames in order")
    require(record.get("split") in ("train", "validation", "test"), "invalid split")
    require(record.get("kind") in ("real_voltage", "real_calcium", "synthetic"), "invalid record kind")
    finite_number(record.get("frame_rate_hz"), "frame_rate_hz", positive=True)
    finite_number(record.get("exposure_ms"), "exposure_ms", positive=True)
    require(record["exposure_ms"] <= 1000 / record["frame_rate_hz"] + 1e-9, "exposure exceeds frame interval")
    require(record.get("event_polarity") in (-1, 1) and not isinstance(record["event_polarity"], bool), "event_polarity must be +1 or -1")
    require(isinstance(record.get("baseline_frames"), list) and len(record["baseline_frames"]) >= 2, "at least two frozen baseline frames required")
    require(len(set(record["baseline_frames"])) == len(record["baseline_frames"]), "duplicate baseline frames")
    for i in record["baseline_frames"]:
        integer(i, "baseline frame")
    require(isinstance(record.get("event_windows"), list), "event_windows must be explicit, possibly empty")
    for window in record["event_windows"]:
        require(isinstance(window, list) and len(window) == 2, "event window must be [start,stop)")
        a, b = window
        integer(a, "event start")
        integer(b, "event stop", 1)
        require(a < b, "empty event window")
        require(not any(a <= i < b for i in record["baseline_frames"]), "event and baseline frames overlap")
    if record["kind"] != "synthetic":
        require("clean" not in record and "data_range" not in record, "real data must not carry a clean-image target")
    else:
        require("clean" in record, "synthetic known-truth record needs clean array")
        finite_number(record.get("data_range"), "data_range", positive=True)
        require("electrophysiology" not in record, "synthetic truth and real ephys cannot be mixed")
    if "electrophysiology" not in record:
        require("reference_event_polarity" not in record and "synchronization_provenance" not in record, "ephys-only fields require an electrophysiology comparator")
    if "electrophysiology" in record:
        require(record["kind"] == "real_voltage", "ephys endpoint requires real voltage")
        nonempty(record.get("synchronization_provenance"), "synchronization_provenance")
        require(record.get("reference_event_polarity") in (-1, 1) and not isinstance(record["reference_event_polarity"], bool), "ephys reference_event_polarity must be declared")


def timing_metrics(receipt, frames, future_context_frames=0):
    require(receipt.get("boundary") == TIMING_BOUNDARY, "forward-only timing is not an end-to-end receipt")
    hardware = nonempty(receipt.get("hardware"), "hardware")
    budget = nonempty(receipt.get("resource_budget_id"), "resource_budget_id")
    nonempty(receipt.get("measurement_provenance"), "measurement_provenance")
    require(receipt.get("clock") == "monotonic_seconds", "timing requires one monotonic clock")
    start = finite_number(receipt.get("start_s"), "start_s")
    end = finite_number(receipt.get("end_s"), "end_s")
    require(end > start, "invalid processing interval")
    ready = np.asarray(receipt.get("input_available_s"), dtype=float)
    done = np.asarray(receipt.get("output_available_s"), dtype=float)
    require(ready.shape == done.shape == (frames,), "timing must cover each original frame exactly")
    require(np.isfinite(ready).all() and np.isfinite(done).all(), "nonfinite timestamp")
    require((np.diff(ready) >= 0).all(), "input timestamps must be chronological")
    require((ready >= start).all() and (done <= end).all() and (done >= ready).all(), "timestamps outside timing boundary or before input")
    future = np.minimum(np.arange(frames) + future_context_frames, frames - 1)
    require((done >= ready[future]).all(), "output predates declared future context availability")
    latency = done - ready
    return {"frames": frames, "end_to_end_seconds": end - start, "throughput_fps": frames / (end - start),
            "frame_latency_ms_median": float(np.median(latency) * 1000),
            "frame_latency_ms_p95": float(np.quantile(latency, .95) * 1000),
            "frame_latency_ms_max": float(np.max(latency) * 1000),
            "hardware": hardware, "resource_budget_id": budget, "boundary": TIMING_BOUNDARY,
            "receipt_status": "declared_unverified"}


def evaluate(panel, submissions, panel_base=Path("."), submission_base=Path(".")):
    require(panel.get("task_id") == TASK_ID and panel.get("recipe") == "prospective-v1", "task/recipe mismatch")
    nonempty(panel.get("freeze_provenance"), "freeze_provenance")
    records = panel.get("records")
    require(isinstance(records, list) and records, "nonempty complete record roster required")
    ids, groups = set(), {}
    for record in records:
        validate_record(record)
        require(record["id"] not in ids, "duplicate record id")
        ids.add(record["id"])
        group = record["group_id"]
        require(group not in groups or groups[group] == record["split"], "recording/animal group crosses splits")
        groups[group] = record["split"]
    test = [r for r in records if r["split"] == "test"]
    require(test, "no test recordings")
    expected = {r["id"] for r in test}
    require(submissions.get("task_id") == TASK_ID, "submission task mismatch")
    methods = submissions.get("methods")
    require(isinstance(methods, list) and len(methods) >= 2, "official FAST and at least one matched candidate required")
    method_ids = [nonempty(m.get("id"), "method id") for m in methods]
    require(len(set(method_ids)) == len(method_ids) and "raw" not in method_ids, "duplicate/reserved method id")
    fast = [m for m in methods if m.get("role") == "official_fast"]
    require(len(fast) == 1 and fast[0].get("code_commit") == SOURCE_COMMIT, "exactly one pinned official FAST comparator required")
    require(any(m.get("role") == "candidate" for m in methods), "candidate method required")
    by_method = {}
    for method in methods:
        require(method.get("role") in ("official_fast", "candidate", "matched_baseline"), "invalid method role")
        nonempty(method.get("implementation_provenance"), "implementation_provenance")
        nonempty(method.get("fit_provenance"), "fit_provenance")
        fit_groups = method.get("fit_group_ids")
        require(isinstance(fit_groups, list) and all(isinstance(g, str) for g in fit_groups), "fit groups must be declared")
        require(len(set(fit_groups)) == len(fit_groups) and all(groups.get(g) == "train" for g in fit_groups), "fit groups must belong only to frozen training panel")
        require(method.get("raw_test_adaptation") is False and method.get("protected_reference_exposure") is False, "prospective held-out route forbids test adaptation/reference exposure")
        integer(method.get("temporal_window_frames"), "temporal_window_frames", 1)
        integer(method.get("stride_frames"), "stride_frames", 1)
        integer(method.get("future_context_frames"), "future_context_frames")
        require(isinstance(method.get("predictions"), list), "prediction roster required")
        pred = {p["record_id"]: p for p in method["predictions"]}
        require(len(pred) == len(method["predictions"]) and set(pred) == expected, "predictions must cover all test recordings exactly once")
        by_method[method["id"]] = pred
    results = []
    for record in test:
        raw = load_array(record["raw"], panel_base, "raw")
        masks = load_array(record["rois"], panel_base, "rois")
        require(len(raw) == record["original_frame_count"], "raw export omits original frames")
        raw_traces = extract_traces(raw, masks)
        require(max(record["baseline_frames"]) < len(raw), "baseline frame out of range")
        require(all(b <= len(raw) for a, b in record["event_windows"]), "event window out of range")
        comparator, clean = None, None
        reference_kind = "none_no_clean_target"
        if record["kind"] == "synthetic":
            clean = load_array(record["clean"], panel_base, "clean")
            require(clean.shape == raw.shape, "clean/raw shape mismatch")
            comparator, _ = delta_f_over_f(extract_traces(clean, masks), record["baseline_frames"])
            reference_kind = "synthetic_clean_trace"
        elif "electrophysiology" in record:
            comparator = load_array(record["electrophysiology"], panel_base, "electrophysiology")
            require(comparator.shape == raw_traces.shape, "aligned ephys must have one column per fixed ROI and every frame")
            reference_kind = "synchronized_ephys_temporal_agreement_only"
        measured = {"raw": {"traces": trace_measurements(raw_traces, record, comparator), "timing": None}}
        if clean is not None:
            measured["raw"]["synthetic_image_error"] = image_error(raw, clean, record["data_range"])
        matched_timing = None
        for method in methods:
            prediction = by_method[method["id"]][record["id"]]
            movie = load_array(prediction["output"], submission_base, "prediction")
            require(movie.shape == raw.shape, "prediction must preserve every original frame/pixel, without mirrored tail")
            timer = timing_metrics(prediction["timing"], len(raw), method["future_context_frames"])
            require(prediction.get("frame_ids") == record["frame_ids"], "prediction frame identities/order differ")
            signature = (timer["hardware"], timer["resource_budget_id"])
            require(matched_timing is None or signature == matched_timing, "hardware/resource budget differs across matched methods")
            matched_timing = signature
            out = {"traces": trace_measurements(extract_traces(movie, masks), record, comparator), "timing": timer}
            if clean is not None:
                out["synthetic_image_error"] = image_error(movie, clean, record["data_range"])
            measured[method["id"]] = out
        results.append({"record_id": record["id"], "group_id": record["group_id"], "collection_id": record["collection_id"],
                        "kind": record["kind"], "frames": len(raw), "roi_count": len(masks),
                        "reference_kind": reference_kind, "methods": measured})
    # Equal ROI -> equal recording -> equal group means, keeping undefined entries undefined.
    # Biological groups, never frames/pixels, are the independent aggregation units.
    summary = {}
    for method_id in ["raw"] + method_ids:
        grouped = {}
        for result in results:
            values = result["methods"][method_id]["traces"]["zero_lag_pearson_by_roi"]
            grouped.setdefault((result["kind"], result["reference_kind"], result["group_id"]), []).append(None if values is None else strict_mean(values))
        strata = {}
        for (kind, reference, group), values in grouped.items():
            key = kind + "/" + reference
            strata.setdefault(key, {})[group] = strict_mean(values)
        summary[method_id] = {key: {"group_means": values, "equal_group_mean_pearson": strict_mean(list(values.values())),
                                    "group_count": len(values)} for key, values in strata.items()}
    return {"task_id": TASK_ID, "recipe": "prospective-v1", "status": "engineering_measurements_only",
            "source_commit": SOURCE_COMMIT, "canonical_contract_sha256": CONTRACT_SHA256,
            "qualification": {"scientific": False, "full_contract_complete": False, "binary_reward": None},
            "definitions": {"dff": "(F-mean(F[frozen_baseline_frames]))/mean(F[frozen_baseline_frames]); prospective baseline policy",
                            "pearson": "zero lag on all original frames; no fitted lag, sign, gain, smoothing or held-out calibration",
                            "snr_proxy": "oriented event-window max dff / baseline dff sample std; prospective diagnostic, not clean-target SNR",
                            "aggregation": "equal ROI within recording, equal recording within group, equal group within kind/reference stratum; undefined is not dropped"},
            "records": results, "grouped_temporal_agreement": summary, "preserved_holds": HOLDS}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", type=Path, required=True)
    parser.add_argument("--panel-sha256", required=True)
    parser.add_argument("--submissions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        panel_bytes = args.panel.read_bytes()
        require(hashlib.sha256(panel_bytes).hexdigest() == args.panel_sha256, "frozen panel SHA256 mismatch")
        submission_bytes = args.submissions.read_bytes()
        panel = json.loads(panel_bytes.decode("utf-8"))
        submissions = json.loads(submission_bytes.decode("utf-8"))
        report = evaluate(panel, submissions, args.panel.parent, args.submissions.parent)
        report["input_pins"] = {"panel_sha256": args.panel_sha256,
                                "submissions_sha256": hashlib.sha256(submission_bytes).hexdigest()}
        args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    except (ContractError, KeyError, TypeError, OSError, ValueError) as error:
        print(f"evaluation rejected: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
