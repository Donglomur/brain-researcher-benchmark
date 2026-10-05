"""Offline source-bound fixed-sensor total-power method control.

Not an induced-only estimate, a localization analysis, or an exact paper finding.
Importing this module neither reads source data nor computes an answer.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path, PurePosixPath

import mne
import numpy as np

PIPELINE_ID = "somato-total-power-v2"
MANIFEST_SHA256 = "47e96a3c3562c4a5ab2baab6a1ab4d8dc3c246e9bef3382b2cc2f9d5a96069ae"
METHOD_SHA256 = "ee318487bb63ca223bde0ba05ba0b597e44a8b291bd9a6eb5bdf0c824933722c"
FIF_SHA256 = "71bb33cb530fe6bf289c492deac5bc184da7ee0dbbc964203a59175cda32ffc3"
CHANS = ["MEG 1342", "MEG 1343", "MEG 1332", "MEG 1333"]
FREQS = np.arange(15.0, 31.0)
BASELINE, TARGET = (-1.0, -0.25), (0.1, 0.35)
TMIN, TMAX = -1.5, 1.5
VERSIONS = {"numpy": "2.2.6", "scipy": "1.14.1", "mne": "1.12.1", "pooch": "1.8.2"}
EVENT_SETTINGS = dict(output="onset", consecutive="increasing", min_duration=0,
                      shortest_event=2, mask=None, uint_cast=False,
                      mask_type="and", initial_event=False)
EPOCH_SETTINGS = dict(baseline=None, detrend=None, proj=True, reject=None,
                      flat=None, reject_by_annotation=True, decim=1,
                      event_repeated="error", on_missing="raise")
EVENT_FIELDS = ["event_index", "event_sample", "event_code", "retained", "drop_reason",
                "epoch_start_sample", "epoch_end_sample"]
PUBLIC_FILES = ["source_events.csv", "mean_power.csv", "trial_windows.csv",
                "beta_power_timecourse.csv", "erd.json", "run_metadata.json", "findings.md"]


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def json_text(value):
    return json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"


def check_versions():
    actual = {name: importlib.metadata.version(name) for name in VERSIONS}
    if actual != VERSIONS:
        raise ValueError(f"Pinned numerical versions required: {VERSIONS}; found {actual}")
    return actual


def load_inputs(data_dir, method_contract_path=None):
    """Verify every retained original file, with no network or cache fallback."""
    data_dir = Path(data_dir)
    manifest_path = data_dir / "data_manifest.json"
    method_path = Path(method_contract_path or "/app/method_contract.json")
    if data_dir.is_symlink() or manifest_path.is_symlink() or method_path.is_symlink():
        raise ValueError("Symlinked source/contract paths are not accepted")
    if sha256(manifest_path) != MANIFEST_SHA256:
        raise ValueError("Source manifest identity mismatch")
    if sha256(method_path) != METHOD_SHA256:
        raise ValueError("Public method contract identity mismatch")
    manifest = json.loads(manifest_path.read_text())
    contract = json.loads(method_path.read_text())
    if manifest["dataset_id"] != "mne-somato" or manifest["source_version"] != "osf-tp4sg-v8":
        raise ValueError("Unexpected original dataset/version")
    paths, hashes = {}, {}
    for item in manifest["files"]:
        relative = PurePosixPath(item["path"])
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise ValueError("Unsafe source path")
        path = data_dir.joinpath(*relative.parts)
        if any(data_dir.joinpath(*relative.parts[:i]).is_symlink()
               for i in range(1, len(relative.parts) + 1)):
            raise ValueError("Symlinked source member")
        if not path.is_file() or path.stat().st_size != item["size_bytes"]:
            raise ValueError(f"Original file size mismatch: {relative}")
        digest = sha256(path)
        if digest != item["sha256"]:
            raise ValueError(f"Original file digest mismatch: {relative}")
        if item["role"] in paths:
            raise ValueError("Duplicate source role")
        paths[item["role"]] = path
        hashes[item["path"]] = digest
    if hashes[next(item["path"] for item in manifest["files"] if item["role"] == "raw_fif")] != FIF_SHA256:
        raise ValueError("Original FIF identity mismatch")
    return dict(manifest=manifest, paths=paths, contract=contract,
                source_sha256=hashes, source_manifest_sha256=MANIFEST_SHA256,
                source_fif_sha256=FIF_SHA256, method_contract_sha256=METHOD_SHA256)


def source_times(sfreq):
    if not np.isfinite(sfreq) or sfreq <= 2 * FREQS.max():
        raise ValueError("Invalid source sampling frequency")
    offsets = np.arange(int(round(TMIN * sfreq)), int(round(TMAX * sfreq)) + 1,
                        dtype=np.int64)
    return offsets, offsets.astype(np.float64) / sfreq


def prepare_raw(raw, pilot_trials=None):
    """Apply source SSP to all gradiometers before selecting four readouts.

    The ledger always describes full scientific membership. Resource pilots
    process the first <=4 retained epochs without inventing rejection reasons.
    """
    if pilot_trials is not None and (isinstance(pilot_trials, bool)
                                    or pilot_trials not in range(1, 5)):
        raise ValueError("Resource pilot must use between one and four trials")
    sfreq = float(raw.info["sfreq"])
    offsets, times = source_times(sfreq)
    source_bads = list(raw.info["bads"])
    for channel in CHANS:
        if channel not in raw.ch_names:
            raise ValueError(f"Required readout channel absent: {channel}")
        if channel in source_bads:
            raise ValueError(f"Required readout is source-marked bad: {channel}")
        if raw.get_channel_types(picks=[channel]) != ["grad"]:
            raise ValueError(f"Readout is not a gradiometer: {channel}")
    events = mne.find_events(raw, stim_channel="STI 014", **EVENT_SETTINGS, verbose="warning")
    if not len(events) or not np.any(events[:, 2] == 1):
        raise ValueError("No target source events")
    if np.any(np.diff(events[:, 0]) <= 0):
        raise ValueError("Discovered event sample identities are not strictly ordered")
    grad_indices = mne.pick_types(raw.info, meg="grad", eeg=False, stim=False, eog=False, exclude=[])
    grad_raw = raw.copy().pick(grad_indices)
    grad_names = list(grad_raw.ch_names)
    epochs = mne.Epochs(grad_raw, events, event_id={"stim": 1}, tmin=TMIN, tmax=TMAX,
                       preload=True, **EPOCH_SETTINGS, verbose="warning")
    if not len(epochs):
        raise ValueError("No source epochs survived annotation and boundary rejection")
    if not np.array_equal(epochs.times, times):
        raise ValueError("Epoch grid is not the original unrounded sample clock")
    source_retained = np.asarray(epochs.selection, dtype=np.int64)
    retained_set = set(source_retained.tolist())
    ledger = []
    for index, (sample, _previous, code) in enumerate(events):
        retained = index in retained_set
        reason = "" if retained else ("non_target_event" if code != 1
                                       else ";".join(epochs.drop_log[index]))
        if not retained and not reason:
            raise ValueError("Missing source epoch rejection reason")
        ledger.append(dict(event_index=index, event_sample=int(sample), event_code=int(code),
                           retained=int(retained), drop_reason=reason,
                           epoch_start_sample=int(sample + offsets[0]),
                           epoch_end_sample=int(sample + offsets[-1])))
    projector = (np.eye(len(grad_names), dtype=np.float64) if epochs._projector is None
                 else np.asarray(epochs._projector, dtype=np.float64).copy())
    selected = epochs.copy().pick(CHANS)
    if selected.ch_names != CHANS:
        raise ValueError("Readout channel order changed")
    n_process = len(selected) if pilot_trials is None else min(pilot_trials, len(selected))
    selected_data = selected[:n_process].get_data(copy=True).astype(np.float64, copy=False)
    if not np.isfinite(selected_data).all():
        raise ValueError("Nonfinite retained readout signal")
    return dict(source_events=ledger, source_events_json=json_text(ledger),
                retained_event_indices=source_retained[:n_process].copy(),
                source_retained_event_indices=source_retained, times=times,
                sample_offsets=offsets, selected_epochs=selected_data,
                source_grad_names=grad_names, grad_projector=projector,
                sfreq_hz=sfreq, first_samp=int(raw.first_samp),
                n_source_samples=int(raw.n_times), n_discovered_events=len(events),
                source_bads=source_bads, n_source_projectors=len(raw.info["projs"]),
                source_projector_descriptions=[str(p["desc"]) for p in raw.info["projs"]],
                source_projector_active=[bool(p["active"]) for p in raw.info["projs"]],
                source_highpass_hz=float(raw.info["highpass"]),
                source_lowpass_hz=float(raw.info["lowpass"]),
                status="ok" if pilot_trials is None else "resource_pilot")


def prepare_epochs(inputs, pilot_trials=None):
    raw = mne.io.read_raw_fif(inputs["paths"]["raw_fif"], preload=False, verbose="warning")
    try:
        return prepare_raw(raw, pilot_trials)
    finally:
        raw.close()


def window_masks(times):
    times = np.asarray(times, dtype=np.float64)
    if times.ndim != 1 or not np.isfinite(times).all() or np.any(np.diff(times) <= 0):
        raise ValueError("Invalid epoch time grid")
    baseline = (times >= BASELINE[0]) & (times <= BASELINE[1])
    target = (times >= TARGET[0]) & (times <= TARGET[1])
    if not baseline.any() or not target.any():
        raise ValueError("Empty baseline or target window")
    return baseline, target


def aggregate_power(power, times):
    power = np.asarray(power, dtype=np.float64)
    if power.ndim != 4 or power.shape[0] < 1 or power.shape[-1] != len(times):
        raise ValueError("Expected trial/channel/frequency/time power")
    if not np.isfinite(power).all() or np.any(power < 0):
        raise ValueError("Power must be finite and nonnegative")
    baseline_mask, target_mask = window_masks(times)
    mean_power = power.mean(axis=0)
    baseline_power = mean_power[:, :, baseline_mask].mean(axis=-1)
    if not np.isfinite(baseline_power).all() or np.any(baseline_power <= 0):
        raise ValueError("Every channel/frequency baseline must be finite and positive")
    percent_power = 100.0 * (mean_power / baseline_power[:, :, None] - 1.0)
    curve = percent_power.mean(axis=(0, 1))
    if not np.isfinite(percent_power).all():
        raise ValueError("Nonfinite baseline-normalized power")
    return dict(mean_power=mean_power, baseline_power=baseline_power,
                percent_power=percent_power, beta_power_pct=curve,
                beta_erd_percent=float(curve[target_mask].mean()),
                trial_baseline_power=power[..., baseline_mask].mean(axis=-1),
                trial_target_power=power[..., target_mask].mean(axis=-1),
                baseline_mask=baseline_mask, target_mask=target_mask)


def compute_power(prepared):
    data = prepared["selected_epochs"]
    if data.ndim != 3 or data.shape[1] != len(CHANS) or not np.isfinite(data).all():
        raise ValueError("Invalid retained readout epochs")
    power = mne.time_frequency.tfr_array_morlet(
        data, sfreq=prepared["sfreq_hz"], freqs=FREQS, n_cycles=FREQS / 2.0,
        zero_mean=True, use_fft=True, decim=1, output="power", n_jobs=1, verbose="warning")
    return aggregate_power(power, prepared["times"])


def make_metadata(inputs, prepared, software_versions=None):
    keys = ["status", "sfreq_hz", "first_samp", "n_source_samples", "n_discovered_events",
            "source_bads", "n_source_projectors", "source_projector_descriptions",
            "source_projector_active", "source_highpass_hz", "source_lowpass_hz"]
    return {**{key: prepared[key] for key in keys}, "task_id": "SOMATOERD-001",
            **{key: inputs[key] for key in ["source_manifest_sha256", "source_fif_sha256", "method_contract_sha256"]},
            "source_sha256": inputs["source_sha256"], "source_scope": inputs["manifest"]["source_scope"],
            "n_trials": len(prepared["retained_event_indices"]),
            "n_source_retained_trials": len(prepared["source_retained_event_indices"]),
            "n_epoch_times": len(prepared["times"]),
            "software_versions": check_versions() if software_versions is None else software_versions,
            "method_contract": inputs["contract"]}


def make_results(prepared, power):
    return dict(beta_erd_percent=power["beta_erd_percent"], band_hz=[15, 30], channels=CHANS,
                window_ms=[100, 350], baseline_ms=[-1000, -250],
                n_trials=len(prepared["retained_event_indices"]))


def ensure_fresh_outputs(output_dir, private_dir):
    output_dir, private_dir = Path(output_dir), Path(private_dir)
    for folder in {output_dir, private_dir}:
        if folder.is_symlink() or (folder.exists() and not folder.is_dir()):
            raise FileExistsError(f"Not a safe output directory: {folder}")
    for path in [*(output_dir / name for name in PUBLIC_FILES), private_dir / "analysis_arrays.npz"]:
        if path.exists() or path.is_symlink():
            raise FileExistsError(f"Refusing to overwrite existing evidence: {path}")
    output_dir.mkdir(parents=True, exist_ok=True)
    private_dir.mkdir(parents=True, exist_ok=True)


def write_csv(path, fields, rows):
    with Path(path).open("x", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(fields)
        writer.writerows(rows)


def write_outputs(output_dir, private_dir, prepared, power, metadata, results):
    output_dir, private_dir = Path(output_dir), Path(private_dir)
    write_csv(output_dir / "source_events.csv", EVENT_FIELDS,
              ([row[field] for field in EVENT_FIELDS] for row in prepared["source_events"]))
    write_csv(output_dir / "mean_power.csv",
              ["channel", "frequency_hz", "time_index", "time_s", "mean_power_T2_per_m2"],
              ((channel, int(freq), t, float(time), float(power["mean_power"][c, f, t]))
               for c, channel in enumerate(CHANS) for f, freq in enumerate(FREQS)
               for t, time in enumerate(prepared["times"])))
    write_csv(output_dir / "trial_windows.csv",
              ["event_index", "channel", "frequency_hz", "baseline_power_T2_per_m2", "target_power_T2_per_m2"],
              ((int(index), channel, int(freq), float(power["trial_baseline_power"][e, c, f]),
                float(power["trial_target_power"][e, c, f]))
               for e, index in enumerate(prepared["retained_event_indices"])
               for c, channel in enumerate(CHANS) for f, freq in enumerate(FREQS)))
    write_csv(output_dir / "beta_power_timecourse.csv", ["time_index", "time_s", "beta_power_pct"],
              ((i, float(t), float(v)) for i, (t, v) in enumerate(zip(prepared["times"], power["beta_power_pct"]))))
    for name, value in [("run_metadata.json", metadata), ("erd.json", results)]:
        with (output_dir / name).open("x") as handle:
            handle.write(json_text(value))
    with (output_dir / "findings.md").open("x") as handle:
        handle.write(f"# Fixed-sensor total beta power\n\n"
                     f"The signed change is {results['beta_erd_percent']:.12g}% across "
                     f"{results['n_trials']} processed trials ({metadata['status']}). "
                     "This descriptive single-recording total-power estimate includes phase-locked "
                     "and non-phase-locked activity. It is not isolated induced power, population "
                     "inference, laterality, cortical localization, or a precise onset estimate. "
                     "Morlet temporal smoothing and endpoint padding affect interpretation.\n")
    arrays = {key: np.asarray(prepared[key]) for key in ["selected_epochs", "retained_event_indices",
              "source_retained_event_indices", "times", "sample_offsets", "source_grad_names", "grad_projector"]}
    arrays.update({key: np.asarray(value) for key, value in power.items()})
    arrays.update(pipeline_id=np.asarray(PIPELINE_ID), channels=np.asarray(CHANS), frequencies_hz=FREQS,
                  source_events_json=np.asarray(prepared["source_events_json"]),
                  metadata_json=np.asarray(json_text(metadata)), results_json=np.asarray(json_text(results)))
    with (private_dir / "analysis_arrays.npz").open("xb") as handle:
        np.savez_compressed(handle, **arrays)


def failure_outputs(output_dir, error):
    reason = f"{type(error).__name__}: {error}"
    value = dict(status="failed_precondition", task_id="SOMATOERD-001", reason=reason)
    for name in ["run_metadata.json", "erd.json"]:
        path = Path(output_dir) / name
        if not path.exists():
            with path.open("x") as handle:
                handle.write(json_text(value))
    path = Path(output_dir) / "findings.md"
    if not path.exists():
        with path.open("x") as handle:
            handle.write(f"# Failed precondition\n\n{reason}\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("/app/data/somato"))
    parser.add_argument("--output-dir", type=Path, default=Path(os.environ.get("OUTPUT_DIR", "/app/output")))
    parser.add_argument("--private-dir", type=Path)
    parser.add_argument("--method-contract", type=Path, default=Path("/app/method_contract.json"))
    parser.add_argument("--pilot-trials", type=int, choices=range(1, 5))
    args = parser.parse_args(argv)
    private_dir = args.private_dir or args.output_dir
    ensure_fresh_outputs(args.output_dir, private_dir)
    try:
        versions = check_versions()
        inputs = load_inputs(args.data_dir, args.method_contract)
        prepared = prepare_epochs(inputs, args.pilot_trials)
        power = compute_power(prepared)
        metadata = make_metadata(inputs, prepared, versions)
        results = make_results(prepared, power)
        write_outputs(args.output_dir, private_dir, prepared, power, metadata, results)
    except Exception as error:
        failure_outputs(args.output_dir, error)
        raise
    print(f"{metadata['status']}: {results['n_trials']} trials; "
          f"total beta-power change {results['beta_erd_percent']:.12g}%")


if __name__ == "__main__":
    main()
