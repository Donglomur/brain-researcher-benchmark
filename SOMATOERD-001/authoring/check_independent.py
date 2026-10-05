"""Independent source-clock and Morlet reconstruction; never imports the oracle.

The FIF reader is shared MNE. Trigger discovery, epoch slicing, wavelet equations,
SciPy convolution, and all reductions below are separate implementations. This is
an engineering numerical cross-check, not independent biological evidence.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
from pathlib import Path

import mne
import numpy as np
from scipy.signal import fftconvolve

CHANNELS = ["MEG 1342", "MEG 1343", "MEG 1332", "MEG 1333"]
FREQUENCIES = np.arange(15, 31, dtype=np.float64)
MANIFEST_SHA = "47e96a3c3562c4a5ab2baab6a1ab4d8dc3c246e9bef3382b2cc2f9d5a96069ae"
METHOD_SHA = "ee318487bb63ca223bde0ba05ba0b597e44a8b291bd9a6eb5bdf0c824933722c"
FIF_SHA = "71bb33cb530fe6bf289c492deac5bc184da7ee0dbbc964203a59175cda32ffc3"
EVENT_FIELDS = ["event_index", "event_sample", "event_code", "retained", "drop_reason",
                "epoch_start_sample", "epoch_end_sample"]


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def json_text(value):
    return json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n"


def binary_events(stimulus, first_samp):
    """Independent onset finder for the verified archive's binary STI 014 stream."""
    stimulus = np.asarray(stimulus)
    if stimulus.ndim != 1 or not np.isfinite(stimulus).all():
        raise ValueError("Invalid source stimulus channel")
    if not np.isin(stimulus, [0, 1]).all():
        raise ValueError("Pinned original source no longer has a binary stimulus stream")
    # initial_event=False: a high initial value does not create an onset.
    onsets = np.flatnonzero((stimulus[1:] == 1) & (stimulus[:-1] == 0)) + 1
    if len(onsets) == 0 or np.any(np.diff(onsets) < 2):
        raise ValueError("No valid independently detected onsets")
    return np.column_stack([onsets + int(first_samp), np.zeros(len(onsets), int),
                            np.ones(len(onsets), int)]).astype(np.int64)


def slice_epochs(readouts, events, sfreq, first_samp):
    """Sample-clock slicing without MNE Epochs or annotation/filter machinery."""
    readouts = np.asarray(readouts, dtype=np.float64)
    offsets = np.arange(round(-1.5 * sfreq), round(1.5 * sfreq) + 1, dtype=np.int64)
    ledger, retained, epochs = [], [], []
    for index, (sample, _old, code) in enumerate(events):
        begin, end = int(sample + offsets[0]), int(sample + offsets[-1])
        local_begin, local_end = begin - first_samp, end - first_samp
        reason = ("non_target_event" if code != 1 else "NO_DATA" if local_begin < 0
                  else "TOO_SHORT" if local_end >= readouts.shape[1] else "")
        ledger.append(dict(event_index=index, event_sample=int(sample), event_code=int(code),
                           retained=int(not reason), drop_reason=reason,
                           epoch_start_sample=begin, epoch_end_sample=end))
        if not reason:
            retained.append(index)
            epochs.append(readouts[:, local_begin:local_end + 1])
    if not epochs:
        raise ValueError("No retained source epochs")
    epochs = np.stack(epochs)
    if not np.isfinite(epochs).all():
        raise ValueError("Nonfinite retained source samples")
    return dict(selected_epochs=epochs, source_events=ledger,
                retained_event_indices=np.asarray(retained, dtype=np.int64),
                sample_offsets=offsets, times=offsets / float(sfreq))


def read_source(data_dir, method_path):
    """Authenticate all original bytes, then use only the FIF reader from MNE."""
    data_dir, method_path = Path(data_dir), Path(method_path)
    if sha256(data_dir / "data_manifest.json") != MANIFEST_SHA:
        raise ValueError("Source manifest digest mismatch")
    if sha256(method_path) != METHOD_SHA:
        raise ValueError("Public method digest mismatch")
    manifest = json.loads((data_dir / "data_manifest.json").read_text())
    method = json.loads(method_path.read_text())
    paths, hashes = {}, {}
    for entry in manifest["files"]:
        path = data_dir / entry["path"]
        if not path.is_file() or path.is_symlink() or path.stat().st_size != entry["size_bytes"]:
            raise ValueError("Missing or changed original member")
        digest = sha256(path)
        if digest != entry["sha256"]:
            raise ValueError("Original member digest mismatch")
        paths[entry["role"]], hashes[entry["path"]] = path, digest
    if sha256(paths["raw_fif"]) != FIF_SHA:
        raise ValueError("Pinned original FIF mismatch")
    raw = mne.io.read_raw_fif(paths["raw_fif"], preload=False, verbose="warning")
    try:
        if raw.info["bads"] or raw.info["projs"] or len(raw.annotations):
            raise ValueError("Independent manual route requires verified no-bad/no-SSP/no-annotation source")
        if any(raw.get_channel_types(picks=[c]) != ["grad"] for c in CHANNELS):
            raise ValueError("Readout sensor type changed")
        sfreq = float(raw.info["sfreq"])
        events = binary_events(raw.get_data(picks=["STI 014"])[0], raw.first_samp)
        with paths["events"].open(newline="") as handle:
            sidecar = list(csv.DictReader(handle, delimiter="\t"))
        if len(sidecar) != len(events):
            raise ValueError("Original event sidecar membership mismatch")
        for row, event in zip(sidecar, events):
            if int(row["sample"]) != int(event[0] - raw.first_samp) or int(row["value"]) != event[2]:
                raise ValueError("Sidecar event sample/value mismatch")
            if abs(float(row["onset"]) - (event[0] - raw.first_samp) / sfreq) > 1e-9:
                raise ValueError("Sidecar onset/sample-clock mismatch")
        prepared = slice_epochs(raw.get_data(picks=CHANNELS), events, sfreq, raw.first_samp)
        prepared.update(sfreq_hz=sfreq, first_samp=int(raw.first_samp),
                        n_source_samples=int(raw.n_times), n_discovered_events=len(events),
                        source_grad_names=np.asarray([name for name, kind in zip(raw.ch_names, raw.get_channel_types())
                                                      if kind == "grad"]))
        metadata = dict(status="ok", task_id="SOMATOERD-001", source_manifest_sha256=MANIFEST_SHA,
                        source_fif_sha256=FIF_SHA, method_contract_sha256=METHOD_SHA,
                        source_sha256=hashes, source_scope=manifest["source_scope"],
                        sfreq_hz=sfreq, first_samp=int(raw.first_samp), n_source_samples=int(raw.n_times),
                        n_discovered_events=len(events), n_trials=len(prepared["selected_epochs"]),
                        n_source_retained_trials=len(prepared["selected_epochs"]),
                        n_epoch_times=len(prepared["times"]), source_bads=[], n_source_projectors=0,
                        source_projector_descriptions=[], source_projector_active=[],
                        source_highpass_hz=float(raw.info["highpass"]), source_lowpass_hz=float(raw.info["lowpass"]),
                        software_versions={name: importlib.metadata.version(name)
                                           for name in ["numpy", "scipy", "mne", "pooch"]}, method_contract=method)
    finally:
        raw.close()
    return prepared, metadata


def explicit_morlet(sfreq, frequency, cycles=None):
    """Analytic admissible Morlet on integer sample offsets, discrete norm sqrt(2)."""
    cycles = frequency / 2 if cycles is None else cycles
    if min(sfreq, frequency, cycles) <= 0 or not np.isfinite([sfreq, frequency, cycles]).all():
        raise ValueError("Wavelet parameters must be finite and positive")
    sigma = cycles / (2 * np.pi * frequency)
    n = int(np.ceil(5 * sigma * sfreq))
    t = np.arange(1 - n, n, dtype=np.float64) / sfreq
    envelope = np.exp(-0.5 * (t / sigma) ** 2)
    admissibility = np.exp(-0.5 * cycles ** 2)
    wavelet = envelope * (np.cos(2 * np.pi * frequency * t) - admissibility
                          + 1j * np.sin(2 * np.pi * frequency * t))
    return wavelet * np.sqrt(2 / np.sum(wavelet.real ** 2 + wavelet.imag ** 2))


def normalize(mean_power, times):
    times = np.asarray(times)
    baseline_mask = (times >= -1) & (times <= -0.25)
    target_mask = (times >= 0.1) & (times <= 0.35)
    if not baseline_mask.any() or not target_mask.any():
        raise ValueError("Empty analysis window")
    if not np.isfinite(mean_power).all() or np.any(mean_power < 0):
        raise ValueError("Invalid power")
    baseline = np.mean(mean_power[..., baseline_mask], axis=-1)
    if np.any(baseline <= 0) or not np.isfinite(baseline).all():
        raise ValueError("Undefined baseline normalization")
    pct = (mean_power - baseline[..., None]) / baseline[..., None] * 100
    curve = np.sum(pct, axis=(0, 1)) / (mean_power.shape[0] * mean_power.shape[1])
    return dict(baseline_power=baseline, percent_power=pct, beta_power_pct=curve,
                beta_erd_percent=float(np.mean(curve[target_mask])),
                baseline_mask=baseline_mask, target_mask=target_mask)


def independent_power(epochs, sfreq, times, frequencies=FREQUENCIES):
    epochs = np.asarray(epochs, dtype=np.float64)
    if epochs.ndim != 3 or not np.isfinite(epochs).all():
        raise ValueError("Invalid source epochs")
    n_trials, n_channels, n_times = epochs.shape
    mean = np.empty((n_channels, len(frequencies), n_times))
    baseline_mask = (times >= -1) & (times <= -.25)
    target_mask = (times >= .1) & (times <= .35)
    trial_baseline = np.empty((n_trials, n_channels, len(frequencies)))
    trial_target = np.empty_like(trial_baseline)
    direct_records = []
    for f, frequency in enumerate(frequencies):
        wavelet = explicit_morlet(sfreq, float(frequency))
        if len(wavelet) > n_times:
            raise ValueError("Wavelet exceeds epoch length")
        convolution = fftconvolve(epochs, wavelet[None, None, :], mode="same", axes=-1)
        power = convolution.real ** 2 + convolution.imag ** 2
        mean[:, f] = np.sum(power, axis=0) / n_trials
        trial_baseline[:, :, f] = np.mean(power[..., baseline_mask], axis=-1)
        trial_target[:, :, f] = np.mean(power[..., target_mask], axis=-1)
        if f in {0, len(frequencies) // 2, len(frequencies) - 1}:
            for e in sorted({0, n_trials // 2, n_trials - 1}):
                for c in sorted({0, n_channels - 1}):
                    direct = np.convolve(epochs[e, c], wavelet, mode="same")
                    error = float(np.max(np.abs(direct - convolution[e, c])))
                    scale = float(np.max(np.abs(direct)))
                    if error > 5e-13 * scale + np.finfo(float).tiny:
                        raise AssertionError("FFT and direct convolution disagree")
                    direct_records.append(dict(trial=e, channel=c, frequency_hz=float(frequency),
                                               maximum_absolute_error=error, maximum_amplitude=scale))
    values = dict(mean_power=mean, trial_baseline_power=trial_baseline,
                  trial_target_power=trial_target, **normalize(mean, times))
    return values, direct_records


def write_csv(path, fields, rows):
    with Path(path).open("x", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(fields)
        writer.writerows(rows)


def write_positive(folder, prepared, power, metadata):
    """Own serializer for a complete genuine independently computed submission."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=False)
    write_csv(folder / "source_events.csv", EVENT_FIELDS,
              ([row[k] for k in EVENT_FIELDS] for row in prepared["source_events"]))
    write_csv(folder / "mean_power.csv", ["channel", "frequency_hz", "time_index", "time_s", "mean_power_T2_per_m2"],
              ((channel, int(freq), t, float(time), float(power["mean_power"][c, f, t]))
               for c, channel in enumerate(CHANNELS) for f, freq in enumerate(FREQUENCIES)
               for t, time in enumerate(prepared["times"])))
    write_csv(folder / "trial_windows.csv", ["event_index", "channel", "frequency_hz", "baseline_power_T2_per_m2", "target_power_T2_per_m2"],
              ((int(event), channel, int(freq), float(power["trial_baseline_power"][e, c, f]),
                float(power["trial_target_power"][e, c, f]))
               for e, event in enumerate(prepared["retained_event_indices"])
               for c, channel in enumerate(CHANNELS) for f, freq in enumerate(FREQUENCIES)))
    write_csv(folder / "beta_power_timecourse.csv", ["time_index", "time_s", "beta_power_pct"],
              ((t, float(time), float(power["beta_power_pct"][t])) for t, time in enumerate(prepared["times"])))
    result = dict(beta_erd_percent=power["beta_erd_percent"], band_hz=[15, 30], channels=CHANNELS,
                  window_ms=[100, 350], baseline_ms=[-1000, -250], n_trials=len(prepared["selected_epochs"]))
    for name, value in [("run_metadata.json", metadata), ("erd.json", result)]:
        with (folder / name).open("x") as handle:
            handle.write(json_text(value))
    with (folder / "findings.md").open("x") as handle:
        handle.write(f"The independently computed signed total beta-power change is {result['beta_erd_percent']:.12g}% "
                     f"for {result['n_trials']} trials. This fixed-sensor, single-recording method description "
                     "does not isolate induced power or support population, localization, laterality or onset inference.\n")
    return result


def rows_by_key(path, keys):
    with Path(path).open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    output = {}
    for row in rows:
        key = tuple(row[k] if k == "channel" else float(row[k]) for k in keys)
        if key in output:
            raise AssertionError(f"Duplicate public key in {path}")
        output[key] = row
    return output


def power_comparison(actual, expected, baseline, name):
    actual, expected = np.asarray(actual), np.asarray(expected)
    tolerance = 1e-8 * np.asarray(baseline) + 1e-6 * np.abs(expected)
    if actual.shape != expected.shape or not np.isfinite(actual).all():
        raise AssertionError(f"Invalid {name} shape/nonfinite values")
    delta = np.abs(actual - expected)
    if np.any(delta > tolerance):
        raise AssertionError(f"Independent {name} mismatch")
    return dict(max_absolute_difference=float(np.max(delta)),
                max_tolerance_fraction=float(np.max(delta / np.maximum(tolerance, np.finfo(float).tiny))))


def compare_outputs(output, private, prepared, power, metadata):
    output = Path(output)
    expected_events = {float(r["event_index"]): r for r in prepared["source_events"]}
    events = rows_by_key(output / "source_events.csv", ["event_index"])
    if set(events) != {(k,) for k in expected_events}:
        raise AssertionError("Independent event-ledger membership mismatch")
    for (index,), actual in events.items():
        for field, expected in expected_events[index].items():
            value = actual[field] if field == "drop_reason" else float(actual[field])
            if value != expected:
                raise AssertionError(f"Independent source event {field} mismatch")
    times = prepared["times"]
    dense = rows_by_key(output / "mean_power.csv", ["channel", "frequency_hz", "time_index"])
    expected_keys = {(c, float(f), float(t)) for c in CHANNELS for f in FREQUENCIES for t in range(len(times))}
    if set(dense) != expected_keys:
        raise AssertionError("Mean-power full-grid membership mismatch")
    observed = np.empty_like(power["mean_power"])
    for c, channel in enumerate(CHANNELS):
        for f, frequency in enumerate(FREQUENCIES):
            for t, time in enumerate(times):
                row = dense[(channel, float(frequency), float(t))]
                observed_time = float(row["time_s"])
                if not np.isfinite(observed_time) or abs(observed_time - time) > 1e-9:
                    raise AssertionError("Power time clock mismatch")
                observed[c, f, t] = float(row["mean_power_T2_per_m2"])
    report = {"mean_power": power_comparison(observed, power["mean_power"], power["baseline_power"][..., None], "mean power")}
    windows = rows_by_key(output / "trial_windows.csv", ["event_index", "channel", "frequency_hz"])
    expected_keys = {(float(e), c, float(f)) for e in prepared["retained_event_indices"] for c in CHANNELS for f in FREQUENCIES}
    if set(windows) != expected_keys:
        raise AssertionError("Trial-window full-grid membership mismatch")
    for name, field in [("trial_baseline_power", "baseline_power_T2_per_m2"), ("trial_target_power", "target_power_T2_per_m2")]:
        values = np.asarray([[[float(windows[(float(e), c, float(f))][field]) for f in FREQUENCIES]
                              for c in CHANNELS] for e in prepared["retained_event_indices"]])
        report[name] = power_comparison(values, power[name], power["baseline_power"][None], name)
    curve = rows_by_key(output / "beta_power_timecourse.csv", ["time_index"])
    if set(curve) != {(float(t),) for t in range(len(times))}:
        raise AssertionError("Curve membership mismatch")
    observed_curve = np.asarray([float(curve[(float(t),)]["beta_power_pct"]) for t in range(len(times))])
    observed_times = np.asarray([float(curve[(float(t),)]["time_s"]) for t in range(len(times))])
    if not np.allclose(observed_times, times, atol=1e-9, rtol=0) or not np.isfinite(observed_curve).all():
        raise AssertionError("Curve time clock/nonfinite mismatch")
    curve_delta = float(np.max(np.abs(observed_curve - power["beta_power_pct"])))
    if curve_delta > 1e-6:
        raise AssertionError("Independent full-curve mismatch")
    report["curve_max_absolute_difference_pct"] = curve_delta
    result = json.loads((output / "erd.json").read_text())
    if (not np.isfinite(result["beta_erd_percent"])
            or abs(result["beta_erd_percent"] - power["beta_erd_percent"]) > 1e-6):
        raise AssertionError("Independent endpoint mismatch")
    for field, expected in dict(band_hz=[15, 30], channels=CHANNELS, window_ms=[100, 350],
                                baseline_ms=[-1000, -250], n_trials=len(prepared["selected_epochs"])).items():
        if result[field] != expected:
            raise AssertionError(f"Result {field} mismatch")
    actual_metadata = json.loads((output / "run_metadata.json").read_text())
    for field in ["status", "task_id", "source_manifest_sha256", "source_fif_sha256", "method_contract_sha256",
                  "sfreq_hz", "first_samp", "n_source_samples", "n_discovered_events", "n_trials", "n_epoch_times",
                  "source_bads", "n_source_projectors", "method_contract"]:
        if actual_metadata[field] != metadata[field]:
            raise AssertionError(f"Source-bound metadata {field} mismatch")
    if private is not None:
        with np.load(private, allow_pickle=False) as receipt:
            for key in ["sample_offsets", "retained_event_indices", "source_grad_names"]:
                if not np.array_equal(receipt[key], prepared[key]):
                    raise AssertionError(f"Private source {key} mismatch")
            if not np.array_equal(receipt["selected_epochs"], prepared["selected_epochs"]):
                raise AssertionError("Manual source epoch reconstruction differs")
            if json.loads(str(receipt["source_events_json"])) != prepared["source_events"]:
                raise AssertionError("Private event ledger mismatch")
            n_grads = len(prepared["source_grad_names"])
            if not np.array_equal(receipt["grad_projector"], np.eye(n_grads)):
                raise AssertionError("No-SSP source projector should be identity")
        report["private_source_epochs_exact"] = True
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("/app/data/somato"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--private", type=Path, help="Original oracle analysis_arrays.npz (default output/analysis_arrays.npz)")
    parser.add_argument("--method-contract", type=Path, default=Path("/app/method_contract.json"))
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--independent-output", type=Path)
    args = parser.parse_args(argv)
    if args.report.exists():
        raise FileExistsError("Refusing to overwrite existing independent report")
    prepared, metadata = read_source(args.data, args.method_contract)
    values, direct_checks = independent_power(prepared["selected_epochs"], prepared["sfreq_hz"], prepared["times"])
    private = args.private or args.output / "analysis_arrays.npz"
    report = compare_outputs(args.output, private, prepared, values, metadata)
    positive_path = args.independent_output or args.report.parent / "independent-output"
    result = write_positive(positive_path, prepared, values, metadata)
    report.update(status="ok", independent_output=str(positive_path), endpoint=result,
                  n_trials=len(prepared["selected_epochs"]), n_times=len(prepared["times"]),
                  direct_convolution_checks=direct_checks,
                  independence="Shared MNE FIF reader and pinned source; independent binary trigger discovery, manual sample slicing, analytic Morlet, SciPy fftconvolve and reductions. No oracle/verifier imports. All original retained trials/readout sensors/frequencies checked.",
                  limitations="Numerical method agreement is not biological replication or model-difficulty evidence. Upstream SSS and the FIF reader are not independently reimplemented.")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as handle:
        handle.write(json_text(report))
    print(json_text({"status": "ok", "n_trials": report["n_trials"], "independent_output": str(positive_path)}))


if __name__ == "__main__":
    main()
