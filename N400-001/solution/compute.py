"""Offline, source-bound 12-person N400 method control.

This is not the paper's artifact-cleaned N=39 analysis. Original SET metadata
supplies every event identity; MNE reads the three required FDT channels and
applies the public FIR. No network, ICA, behavioral exclusion, result-direction
check or unmeasured pooled contrast is used.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
import csv
import hashlib
import json
import os
from pathlib import Path
import platform
import time
import warnings

import mne
import numpy as np
import scipy
from scipy.io import loadmat

TASK_ID = "N400-001"
PIPELINE_ID = "erpcore-n400-target-subset-v2"
MANIFEST_SHA256 = "09483405a6b48aec79d9e40c96409709a7e0c4e462cb0deb646551fe6cfb2616"
METHOD_SHA256 = "8771e08ea44ee3c973a9b57c32f7d0352078f50e89767334635b8e2c8f1a0dc1"
SUBJECTS = tuple(range(1, 13))
READOUT = ("CPz", "P9", "P10")
CHANNELS = (
    "FP1", "F3", "F7", "FC3", "C3", "C5", "P3", "P7", "P9", "PO7", "PO3",
    "O1", "Oz", "Pz", "CPz", "FP2", "Fz", "F4", "F8", "FC4", "FCz", "Cz",
    "C4", "C6", "P4", "P8", "P10", "PO8", "PO4", "O2", "HEOG_left",
    "HEOG_right", "VEOG_lower",
)
OFFSETS = np.arange(-51, 206, dtype=np.int64)
BASELINE = OFFSETS <= 0
MEASUREMENT = (OFFSETS >= 77) & (OFFSETS <= 128)
CONTRAST = "unrelated minus related (target words)"


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def jsonable(value):
    """Private source metadata only; preserve unknown numeric values as null."""
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, np.ndarray):
        return jsonable(value.tolist())
    if isinstance(value, np.generic):
        return jsonable(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def dumps(value):
    return json.dumps(value, indent=2, sort_keys=True, allow_nan=False)


def load_inputs(data_dir, method_contract_path):
    data_dir = Path(data_dir)
    manifest_path = data_dir / "data_manifest.json"
    if data_dir.is_symlink() or manifest_path.is_symlink():
        raise ValueError("Source directory/manifest must not be symlinks")
    if sha256(manifest_path) != MANIFEST_SHA256:
        raise ValueError("Source manifest differs from frozen original inputs")
    manifest = json.loads(manifest_path.read_text())
    method_contract_path = Path(method_contract_path)
    if method_contract_path.is_symlink() or sha256(method_contract_path) != METHOD_SHA256:
        raise ValueError("Public method contract differs from the frozen method")
    contract = json.loads(method_contract_path.read_text())
    if contract["pipeline_id"] != PIPELINE_ID or contract["subjects"] != list(SUBJECTS):
        raise ValueError("Unexpected numerical contract identity")
    paths, hashes, expected = {}, {}, {"data_manifest.json"}
    for entry in manifest["files"]:
        name = entry["path"]
        if Path(name).name != name or name in expected:
            raise ValueError("Duplicate or non-flat original source path")
        expected.add(name)
        path = data_dir / name
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"Missing/non-regular original file: {name}")
        if path.stat().st_size != entry["size_bytes"] or sha256(path) != entry["sha256"]:
            raise ValueError(f"Original file checksum/size mismatch: {name}")
        key = (entry["subject"], entry["role"])
        if key in paths:
            raise ValueError("Duplicate source subject/role")
        paths[key] = path
        hashes[name] = entry["sha256"]
    if set(paths) != {(s, role) for s in SUBJECTS for role in ("set", "fdt")}:
        raise ValueError("Expected exactly twelve original SET/FDT pairs")
    if {p.name for p in data_dir.iterdir()} != expected:
        raise ValueError("Unexpected file in immutable input directory")
    return {"manifest": manifest, "contract": contract, "paths": paths,
            "source_sha256": hashes, "data_dir": data_dir}


def scalar_number(value, name):
    array = np.asarray(value)
    if array.size != 1 or array.dtype.kind not in "iuf":
        raise ValueError(f"Expected scalar numeric {name}")
    number = float(array.item())
    if not np.isfinite(number):
        raise ValueError(f"Nonfinite {name}")
    return number


def scalar_int(value, name):
    number = scalar_number(value, name)
    if number != int(number):
        raise ValueError(f"Nonintegral {name}")
    return int(number)


def canonical_type(value):
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, np.integer, np.floating)) and not isinstance(value, bool):
        number = float(value)
        if np.isfinite(number) and number == int(number):
            return str(int(number))
    raise ValueError(f"Unsupported original event type: {value!r}")


def records(value):
    if isinstance(value, dict):
        return [value]
    if isinstance(value, np.ndarray):
        value = value.tolist()
    if not isinstance(value, list) or not all(isinstance(v, dict) for v in value):
        raise ValueError("Unexpected MATLAB structure array")
    return value


def duration(event):
    if "duration" not in event:
        return "", "absent"
    value = event["duration"]
    if value is None or np.asarray(value).size == 0:
        return "", "empty"
    array = np.asarray(value)
    if array.size != 1 or array.dtype.kind not in "iuf":
        raise ValueError("Unsupported source event duration")
    number = float(array.item())
    return (number, "finite") if np.isfinite(number) else ("", "nonfinite")


def event_role(label):
    if label in ("211", "212"):
        return "target", "related"
    if label in ("221", "222"):
        return "target", "unrelated"
    if label in ("111", "112"):
        return "prime", "related"
    if label in ("121", "122"):
        return "prime", "unrelated"
    if label in ("201", "202"):
        return "response", ""
    if label in ("boundary", "-99"):
        return "boundary", ""
    return "other", ""


def event_ledger(subject, original_events, n_samples):
    """Original row identity, half-sample cuts, and source-only epoch eligibility."""
    source_rows, cuts, seen_targets = [], {0, n_samples}, set()
    for index, event in enumerate(original_events):
        label = canonical_type(event["type"])
        latency = scalar_number(event["latency"], "event latency")
        role, condition = event_role(label)
        dur, dur_status = duration(event)
        row = {"subject": subject, "event_index": index, "event_type": label,
               "latency_samples": latency, "duration_samples": dur,
               "duration_status": dur_status, "event_sample": "",
               "boundary_cut_sample": "", "role": role, "condition": condition,
               "segment_id": "", "retained": 0, "drop_reason": "not_target"}
        if role == "boundary":
            cut = int(np.floor(latency))
            if latency != cut + .5 or not 0 <= cut <= n_samples:
                raise ValueError("Ambiguous/non-half-integer source boundary")
            row["boundary_cut_sample"] = cut
            cuts.add(cut)
        else:
            sample = int(np.rint(latency - 1))
            row["event_sample"] = sample
            if role == "target":
                if sample in seen_targets:
                    raise ValueError("Duplicate rounded target sample; no merge permitted")
                seen_targets.add(sample)
        source_rows.append(row)
    cut_order = sorted(cuts)
    segments = [{"subject": subject, "segment_id": i, "start_sample": left,
                 "end_sample_exclusive": right, "n_samples": right - left,
                 "filter_length": 8449, "pad_samples": min(8449, right - left) - 1}
                for i, (left, right) in enumerate(zip(cut_order[:-1], cut_order[1:]))]
    for row in source_rows:
        if row["role"] == "boundary":
            continue
        sample = row["event_sample"]
        if 0 <= sample < n_samples:
            row["segment_id"] = int(np.searchsorted(cut_order, sample, side="right") - 1)
        if row["role"] != "target":
            continue
        start, end = sample - 51, sample + 206
        if start < 0 or end > n_samples:
            row["drop_reason"] = "out_of_data"
        elif row["segment_id"] == "":
            raise AssertionError("Valid epoch has no source segment")
        else:
            segment = segments[row["segment_id"]]
            if start < segment["start_sample"] or end > segment["end_sample_exclusive"]:
                row["drop_reason"] = "boundary_crossing"
            else:
                row["retained"], row["drop_reason"] = 1, ""
    return source_rows, segments


def load_subject_header(subject, set_path, fdt_path):
    eeg = loadmat(set_path, simplify_cells=True)["EEG"]
    if not isinstance(eeg, dict):
        raise ValueError("Expected original EEG MATLAB structure")
    n_samples = scalar_int(eeg["pnts"], "pnts")
    n_channels = scalar_int(eeg["nbchan"], "nbchan")
    sfreq = scalar_number(eeg["srate"], "srate")
    labels = [str(c["labels"]) for c in records(eeg["chanlocs"])]
    if sfreq != 256 or scalar_int(eeg["trials"], "trials") != 1:
        raise ValueError("Expected continuous 256 Hz original inputs")
    if n_samples <= 0 or n_channels != 33 or tuple(labels) != CHANNELS:
        raise ValueError("Original channel order/layout differs from frozen source")
    if eeg["data"] != fdt_path.name or eeg["datfile"] != fdt_path.name:
        raise ValueError("SET/FDT original basename mismatch")
    if fdt_path.stat().st_size != n_samples * n_channels * 4:
        raise ValueError("FDT length differs from source float32 layout")
    empty_ica = all(np.asarray(eeg[name]).size == 0 for name in (
        "icaweights", "icasphere", "icawinv", "icachansind"))
    if not empty_ica:
        raise ValueError("Unexpected ICA state in original shifted_ds source")
    original_events = records(eeg["event"])
    source_rows, segments = event_ledger(subject, original_events, n_samples)
    history = str(eeg["history"])
    observations = {
        "subject": subject, "set_path": set_path.name, "fdt_path": fdt_path.name,
        "sfreq_hz": sfreq, "n_samples": n_samples, "n_channels": n_channels,
        "channel_labels": labels,
        "readout_channel_indices": {name: labels.index(name) for name in READOUT},
        "header_reference": str(eeg["ref"]), "n_source_events": len(source_rows),
        "event_type_counts": dict(sorted(Counter(r["event_type"] for r in source_rows).items())),
        "n_boundary_events": sum(r["role"] == "boundary" for r in source_rows),
        "n_segments": len(segments), "n_target_candidates": sum(r["role"] == "target" for r in source_rows),
        "n_retained_target_epochs": sum(r["retained"] for r in source_rows),
        "n_dropped_out_of_data": sum(r["drop_reason"] == "out_of_data" for r in source_rows),
        "n_dropped_boundary_crossing": sum(r["drop_reason"] == "boundary_crossing" for r in source_rows),
        "duration_fields_present": any("duration" in e for e in original_events),
        "ica_fields_empty": empty_ica,
        "history_sha256": hashlib.sha256(history.encode()).hexdigest(),
    }
    return {"events": source_rows, "segments": segments, "observed": observations,
            "original_events": jsonable(original_events), "history": history}


def filter_coefficients():
    h = mne.filter.create_filter(None, 256, .1, 30, method="fir", phase="zero",
                                 fir_window="hamming", fir_design="firwin", verbose=False)
    if h.shape != (8449,) or not np.isfinite(h).all():
        raise ValueError("FIR design differs from public coefficients")
    return h


def filter_segments(three_channel_uv, segments):
    data = np.asarray(three_channel_uv, dtype=np.float64)
    if data.ndim != 2 or data.shape[0] != 3 or not np.isfinite(data).all():
        raise ValueError("Required source voltage channels must be finite 3×samples")
    output = np.empty_like(data)
    expected_start = 0
    for segment in segments:
        a, b = segment["start_sample"], segment["end_sample_exclusive"]
        if a != expected_start or b <= a or b > data.shape[1]:
            raise ValueError("Segments must partition complete source timeline")
        output[:, a:b] = mne.filter.filter_data(
            data[:, a:b], 256, .1, 30, filter_length=8449,
            l_trans_bandwidth=.1, h_trans_bandwidth=7.5, method="fir", phase="zero",
            fir_window="hamming", fir_design="firwin", pad="edge", n_jobs=1,
            verbose=False,
        )
        expected_start = b
    if expected_start != data.shape[1] or not np.isfinite(output).all():
        raise ValueError("Incomplete/nonfinite filtered source")
    return output[0] - (output[1] + output[2]) / 2


def measure_subject(subject, filtered_cpz_uv, source_rows):
    trials, kept_events, raw_epochs, conditions = [], [], [], []
    for source in source_rows:
        if source["role"] != "target":
            continue
        sample = source["event_sample"]
        trial = {key: source[key] for key in (
            "subject", "event_index", "event_type", "event_sample", "condition", "segment_id")}
        trial.update(epoch_start_sample=sample - 51, epoch_end_sample_exclusive=sample + 206,
                     status="retained" if source["retained"] else "dropped",
                     drop_reason=source["drop_reason"], baseline_uv="",
                     window_raw_mean_uv="", window_baseline_corrected_uv="")
        if source["retained"]:
            epoch = np.asarray(filtered_cpz_uv[sample + OFFSETS], dtype=np.float64)
            if epoch.shape != (257,) or not np.isfinite(epoch).all():
                raise ValueError("Nonfinite/malformed retained original epoch")
            baseline, raw_mean = float(epoch[BASELINE].mean()), float(epoch[MEASUREMENT].mean())
            trial.update(baseline_uv=baseline, window_raw_mean_uv=raw_mean,
                         window_baseline_corrected_uv=raw_mean - baseline)
            kept_events.append(source["event_index"])
            raw_epochs.append(epoch)
            conditions.append(source["condition"])
        trials.append(trial)
    conditions = np.asarray(conditions)
    if not all(np.any(conditions == name) for name in ("related", "unrelated")):
        raise ValueError(f"Subject {subject} has empty retained target condition")
    raw_epochs = np.stack(raw_epochs)
    epochs = raw_epochs - raw_epochs[:, BASELINE].mean(axis=1, keepdims=True)
    condition_curves = {name: epochs[conditions == name].mean(axis=0)
                        for name in ("related", "unrelated")}
    related, unrelated = condition_curves["related"], condition_curves["unrelated"]
    curves = [{"subject": subject, "sample_offset": int(offset), "time_ms": float(offset * 1000 / 256),
               "related_uv": float(related[i]), "unrelated_uv": float(unrelated[i]),
               "difference_uv": float(unrelated[i] - related[i])}
              for i, offset in enumerate(OFFSETS)]
    subject_row = {"subject": subject}
    for condition in ("related", "unrelated"):
        subset = [t for t in trials if t["condition"] == condition]
        retained = [t for t in subset if t["status"] == "retained"]
        subject_row[f"n_{condition}_candidate"] = len(subset)
        subject_row[f"n_{condition}_retained"] = len(retained)
        subject_row[f"n_{condition}_dropped"] = len(subset) - len(retained)
        subject_row[f"{condition}_uv"] = float(np.mean([t["window_baseline_corrected_uv"] for t in retained]))
    subject_row["n400_uv"] = subject_row["unrelated_uv"] - subject_row["related_uv"]
    return {"trials": trials, "curves": curves, "subject": subject_row,
            "retained_event_indices": np.asarray(kept_events, dtype=np.int64),
            "raw_epochs_uv": raw_epochs, "epochs_uv": epochs}


def summarize(subject_rows, status="ok"):
    values = np.array([r["n400_uv"] for r in subject_rows], dtype=np.float64)
    if not len(values) or not np.isfinite(values).all():
        raise ValueError("No finite subject measurements")
    return {
        "status": status, "pipeline_id": PIPELINE_ID, "channel": "CPz", "contrast": CONTRAST,
        "n_subjects": len(subject_rows), "subject_ids": [r["subject"] for r in subject_rows],
        "window_ms": [300, 500], "epoch_sample_offsets": [-51, 205],
        "baseline_sample_offsets": [-51, 0], "measurement_sample_offsets": [77, 128],
        "n400_difference_amplitude_uv": float(values.mean()),
        "related_mean_amplitude_uv": float(np.mean([r["related_uv"] for r in subject_rows])),
        "unrelated_mean_amplitude_uv": float(np.mean([r["unrelated_uv"] for r in subject_rows])),
        "n_target_events": sum(r["n_related_candidate"] + r["n_unrelated_candidate"] for r in subject_rows),
        "n_retained_target_epochs": sum(r["n_related_retained"] + r["n_unrelated_retained"] for r in subject_rows),
        "n_subjects_negative": int(np.sum(values < 0)), "n_subjects_zero": int(np.sum(values == 0)),
        "n_subjects_positive": int(np.sum(values > 0)),
    }


def make_metadata(inputs, observed, status="ok"):
    return {"status": status, "task_id": TASK_ID, "pipeline_id": PIPELINE_ID,
            "source_manifest_sha256": MANIFEST_SHA256, "method_contract_sha256": METHOD_SHA256,
            "source_sha256": inputs["source_sha256"], "method_contract": inputs["contract"],
            "source_observed": {"subjects": observed},
            "software_versions": {"python": platform.python_version(), "numpy": np.__version__,
                                  "scipy": scipy.__version__, "mne": mne.__version__}}


@contextmanager
def visible_warnings(subject, warning_records):
    """Retain and display warnings even when the source computation fails."""
    caught = []
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            yield
    finally:
        for warning in caught:
            warnings.showwarning(warning.message, warning.category, warning.filename, warning.lineno)
            warning_records.append({"subject": subject, "category": warning.category.__name__,
                                    "message": str(warning.message)})


def analyze(inputs, pilot=False):
    tables = {name: [] for name in inputs["contract"]["outputs"] if name.endswith(".csv")}
    private = {"sample_offsets": OFFSETS, "filter_coefficients": filter_coefficients()}
    observed, warning_records = [], []
    for subject in ((1,) if pilot else SUBJECTS):
        set_path, fdt_path = inputs["paths"][(subject, "set")], inputs["paths"][(subject, "fdt")]
        header = load_subject_header(subject, set_path, fdt_path)
        with visible_warnings(subject, warning_records):
            raw = mne.io.read_raw_eeglab(set_path, preload=False, verbose=False)
            if raw.ch_names != list(CHANNELS) or raw.n_times != header["observed"]["n_samples"] or raw.info["sfreq"] != 256:
                raise ValueError("MNE reader differs from original SET metadata")
            # EEGLAB stored µV -> MNE SI volts -> explicitly reported µV.
            three_uv = raw.get_data(picks=list(READOUT)).astype(np.float64) * 1e6
            raw.close()
            filtered = filter_segments(three_uv, header["segments"])
        measured = measure_subject(subject, filtered, header["events"])
        tables["source_events.csv"].extend(header["events"])
        tables["segments.csv"].extend(header["segments"])
        tables["trial_measurements.csv"].extend(measured["trials"])
        tables["curves.csv"].extend(measured["curves"])
        tables["per_subject.csv"].append(measured["subject"])
        observed.append(header["observed"])
        suffix = f"s{subject:02d}"
        private[f"raw_three_channel_uv_{suffix}"] = three_uv
        private[f"filtered_cpz_uv_{suffix}"] = filtered
        private[f"retained_epochs_uv_{suffix}"] = measured["epochs_uv"]
        private[f"unbaselined_epochs_uv_{suffix}"] = measured["raw_epochs_uv"]
        private[f"retained_event_indices_{suffix}"] = measured["retained_event_indices"]
        private[f"original_events_json_{suffix}"] = np.array(dumps(header["original_events"]))
        private[f"source_history_{suffix}"] = np.array(header["history"])
        print(f"Subject {subject}: {header['observed']['n_retained_target_epochs']} retained target epochs", flush=True)
    status = "resource_pilot" if pilot else "ok"
    results = summarize(tables["per_subject.csv"], status)
    metadata = make_metadata(inputs, observed, status)
    private.update(metadata_json=np.array(dumps(metadata)), results_json=np.array(dumps(results)),
                   tables_json=np.array(dumps(tables)), warnings_json=np.array(dumps(warning_records)),
                   pipeline_id=np.array(PIPELINE_ID))
    return tables, results, metadata, private


def prepare_directory(path):
    path = Path(path)
    if path.is_symlink() or (path.exists() and (not path.is_dir() or any(path.iterdir()))):
        raise FileExistsError(f"Refusing to replace existing output/evidence: {path}")
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path, value):
    with Path(path).open("x") as stream:
        stream.write(dumps(value) + "\n")


def write_outputs(output, private_dir, tables, results, metadata, private):
    for name, rows in tables.items():
        with (output / name).open("x", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=metadata["method_contract"]["outputs"][name])
            writer.writeheader()
            writer.writerows(rows)
    write_json(output / "n400.json", results)
    write_json(output / "run_metadata.json", metadata)
    with (output / "findings.md").open("x") as stream:
        stream.write(
            "# Original-data N400 method control\n\n"
            f"Across {results['n_subjects']} included participants, the equal-subject mean "
            f"CPz unrelated-minus-related target-word amplitude is {results['n400_difference_amplitude_uv']:.9g} µV "
            "in the declared sampled 300–500 ms window. "
            f"{results['n_subjects_negative']} subject contrasts are negative, "
            f"{results['n_subjects_zero']} are exactly zero and {results['n_subjects_positive']} positive.\n\n"
            "This is a fixed 12-person method adaptation using original shifted/downsampled inputs, "
            "not the paper's artifact-cleaned 39-person finding. The public custom FIR, no ICA, "
            "and no behavioral/amplitude rejection change that analysis. No population inference, "
            "prime-pooling dilution, artificial sign constraint or coding-agent difficulty is inferred. "
            "The source files have no boundary records; boundary behavior is a declared robustness fixture, "
            "not an observed challenge. Stored voltage units use the EEGLAB µV convention, "
            "not a populated per-channel unit attribute.\n"
        )
    with (private_dir / "analysis_arrays.npz").open("xb") as stream:
        np.savez_compressed(stream, **private)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=os.environ.get("ERPCORE_N400_DIR", "/app/data/erpcore_n400"))
    parser.add_argument("--method-contract", type=Path, default="/app/method_contract.json")
    parser.add_argument("--output-dir", type=Path, default=os.environ.get("OUTPUT_DIR", "/app/output"))
    parser.add_argument("--private-dir", type=Path, default=os.environ.get("PRIVATE_DIR", "/app/oracle_private"))
    parser.add_argument("--pilot-subject", type=int, choices=[1], help="Resource pilot only; never an accepted full submission")
    args = parser.parse_args()
    out, private = args.output_dir.resolve(), args.private_dir.resolve()
    data = args.data_dir.resolve()
    if out == private or out in private.parents or private in out.parents:
        raise ValueError("Public output and private evidence must be separate directories")
    if any(p == data or data in p.parents or p in data.parents for p in (out, private)):
        raise ValueError("Output/evidence must not overlap original inputs")
    output = prepare_directory(args.output_dir)
    private_dir = prepare_directory(args.private_dir)
    started = time.monotonic()
    try:
        inputs = load_inputs(args.data_dir, args.method_contract)
        artifacts = analyze(inputs, pilot=args.pilot_subject is not None)
        write_outputs(output, private_dir, *artifacts)
    except Exception as exc:
        failed = {"status": "failed_precondition", "task_id": TASK_ID,
                  "pipeline_id": PIPELINE_ID, "reason": str(exc)}
        for name in ("run_metadata.json", "n400.json"):
            if not (output / name).exists():
                write_json(output / name, failed)
        if not (output / "findings.md").exists():
            with (output / "findings.md").open("x") as stream:
                stream.write(f"# Failed precondition\n\n{exc}\n\nNo accepted scientific result was produced.\n")
        write_json(private_dir / "failure.json", failed)
        raise
    print(f"Completed {artifacts[1]['status']} in {time.monotonic() - started:.3f}s", flush=True)


if __name__ == "__main__":
    main()
