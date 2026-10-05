"""Offline fixed-electrode locomotion-conditioning method control.

All estimators and source limitations are public. Importing this module performs
no source reads, numerical analysis, directory creation, or network requests.
"""
import argparse
import csv
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path, PurePosixPath
import platform
import sys

import h5py
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from spectral_contract import FS, WINDOW, HOP, window_spectrum, theta_integral, peak_summary

PIPELINE_ID = "fixed-channel-gap-safe-welch-v2"
METHOD_SHA256 = "33985c49ac69c03be8e0f483a0fe78d328982a7a46351b9bdba9b25b1ce7218b"
MANIFEST_SHA256 = "175cdbcbeaa8259bd8f825521919bdd71698a65e03341d9f391c19c783075ec8"
TABLE = "/general/extracellular_ephys/electrodes"
PUBLIC_FILES = ("behavior.csv", "blocks.csv", "bouts.csv", "windows.csv", "spectrum.csv",
                "results.json", "run_metadata.json", "findings.md")


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def text(value):
    if isinstance(value, np.ndarray) and value.shape == ():
        value = value.item()
    if isinstance(value, bytes):
        return value.decode("utf-8")
    require(isinstance(value, str), "expected scalar source text")
    return value


def load_inputs(source_dir, method_contract):
    source_dir, method_contract = Path(source_dir), Path(method_contract)
    manifest_path = source_dir / "source_manifest.json"
    require(not source_dir.is_symlink() and not manifest_path.is_symlink()
            and not method_contract.is_symlink(), "symlinked input is not allowed")
    require(sha256(method_contract) == METHOD_SHA256, "public method contract checksum mismatch")
    require(sha256(manifest_path) == MANIFEST_SHA256, "source manifest checksum mismatch")
    contract, manifest = json.loads(method_contract.read_text()), json.loads(manifest_path.read_text())
    require(manifest["version"] == contract["source"]["version"]
            and manifest["dandiset_id"] == "000552", "wrong source release")
    files = manifest["files"]
    require(len(files) == 2 and {r["role"] for r in files} == {"raw", "behavior"},
            "exactly the two original source assets are required")
    paths, source_hashes = {}, {}
    for expected in contract["source"]["files"]:
        entry = next(row for row in files if row["role"] == expected["role"])
        require(all(entry[k] == v for k, v in expected.items()), "source identity mismatch")
        relative = PurePosixPath(entry["path"])
        require(not relative.is_absolute() and ".." not in relative.parts, "unsafe source path")
        path = source_dir
        for part in relative.parts:
            path = path / part
            require(not path.is_symlink(), "symlinked source component")
        require(path.is_file() and path.stat().st_size == entry["size_bytes"], "source size mismatch")
        require(sha256(path) == entry["sha256"], "source checksum mismatch")
        paths[entry["role"]] = path
        source_hashes[entry["path"]] = entry["sha256"]
    return {"contract": contract, "manifest": manifest, "paths": paths,
            "source_sha256": source_hashes, "method_contract_sha256": METHOD_SHA256,
            "source_manifest_sha256": MANIFEST_SHA256}


def read_source(inputs):
    """Check original metadata/mapping and read only the fixed LFP column."""
    c, observed = inputs["contract"], {}
    with h5py.File(inputs["paths"]["raw"], "r") as raw:
        es, table = raw[c["lfp"]["path"]], raw[TABLE]
        data, starting = es["data"], es["starting_time"]
        require(data.shape == (c["lfp"]["n_samples"], c["lfp"]["n_channels"]), "LFP shape mismatch")
        require(str(data.dtype) == c["lfp"]["dtype"], "LFP dtype mismatch")
        require("timestamps" not in es and "channel_conversion" not in es, "unexpected LFP timing/scaling")
        require(text(starting.attrs["unit"]) == "seconds", "LFP time unit mismatch")
        require(float(starting[()]) == c["lfp"]["start_seconds"]
                and float(starting.attrs["rate"]) == c["lfp"]["rate_hz"], "LFP clock mismatch")
        require(text(data.attrs["unit"]) == c["lfp"]["unit"], "LFP voltage unit mismatch")
        conversion, offset = float(data.attrs["conversion"]), float(data.attrs["offset"])
        require(np.isclose(conversion, c["lfp"]["conversion"], atol=0, rtol=1e-15)
                and offset == 0, "LFP calibration mismatch")
        region = es["electrodes"]
        require(raw[region.attrs["table"]].name == TABLE, "wrong electrode table reference")
        row = int(region[c["channel"]["lfp_column"]])
        require(row == c["channel"]["electrode_table_row"], "wrong electrode row")
        electrode_id = int(table["id"][row])
        channel_name, location = text(table["channel_name"][row]), text(table["location"][row])
        require(electrode_id == c["channel"]["electrode_id"] and channel_name == c["channel"]["channel_name"]
                and location == c["channel"]["location"], "source channel identity mismatch")
        calendar, reference = text(raw["session_start_time"][()]), text(raw["timestamps_reference_time"][()])
        session = text(raw["general/session_id"][()])
        require(calendar == c["clocks"]["raw_calendar"] and reference == calendar
                and session == c["source"]["session"] + "_raw", "raw session/calendar mismatch")
        observed.update(raw_session_id=session, raw_calendar=calendar, raw_timestamps_reference_time=reference,
                        n_lfp_samples=data.shape[0], n_lfp_channels=data.shape[1], lfp_dtype=str(data.dtype),
                        lfp_start_seconds=float(starting[()]), lfp_rate_hz=float(starting.attrs["rate"]),
                        lfp_unit=text(data.attrs["unit"]), lfp_conversion=conversion, lfp_offset=offset,
                        lfp_column=0, electrode_table_row=row, electrode_id=electrode_id,
                        channel_name=channel_name, location=location)
        counts = np.asarray(data[:, 0])
    with h5py.File(inputs["paths"]["behavior"], "r") as behavior:
        series = behavior[c["behavior"]["path"]]
        data, stamps = series["data"], series["timestamps"]
        require(data.shape == tuple(c["behavior"]["shape"]) and stamps.shape == (data.shape[0],),
                "position shape mismatch")
        require(text(data.attrs["unit"]) == c["behavior"]["unit"]
                and text(stamps.attrs["unit"]) == "seconds", "behavior units mismatch")
        require(float(data.attrs["conversion"]) == 1 and float(data.attrs["offset"]) == 0,
                "position calibration mismatch")
        reference_frame = text(series["reference_frame"][()])
        require(reference_frame == c["behavior"]["reference_frame"], "position reference frame mismatch")
        calendar, reference = text(behavior["session_start_time"][()]), text(behavior["timestamps_reference_time"][()])
        session = text(behavior["general/session_id"][()])
        require(calendar == c["clocks"]["behavior_calendar"] and reference == calendar
                and session == c["source"]["session"], "behavior session/calendar mismatch")
        position, timestamps = np.asarray(data[:], dtype=np.float64), np.asarray(stamps[:], dtype=np.float64)
        require(np.isfinite(timestamps).all() and np.all(np.diff(timestamps) > 0), "invalid original timestamps")
        require(timestamps[0] == c["behavior"]["first_timestamp_s"]
                and timestamps[-1] == c["behavior"]["last_timestamp_s"], "behavior time support mismatch")
        observed.update(behavior_session_id=session, behavior_calendar=calendar,
                        behavior_timestamps_reference_time=reference, position_n_rows=len(timestamps),
                        position_unit=text(data.attrs["unit"]), position_conversion=float(data.attrs["conversion"]),
                        position_offset=float(data.attrs["offset"]), position_reference_frame=reference_frame,
                        position_first_timestamp_s=float(timestamps[0]), position_last_timestamp_s=float(timestamps[-1]))
    require(set(observed) == set(c["source_observed_fields"]), "source metadata receipt incomplete")
    return {"counts": counts, "position": position, "timestamps": timestamps, "observed": observed}


def central_derivative(times, values):
    h0, h1 = times[1] - times[0], times[2] - times[1]
    require(h0 > 0 and h1 > 0, "derivative timestamps must increase")
    return (-h1 / (h0 * (h0 + h1)) * values[0]
            + (h1 - h0) / (h0 * h1) * values[1]
            + h0 / (h1 * (h0 + h1)) * values[2])


def select_intervals(speed, block_id):
    selected = np.zeros(len(speed), dtype=bool)
    selected[:-1] = (np.isfinite(speed[:-1]) & np.isfinite(speed[1:])
                    & (speed[:-1] > 5) & (speed[1:] > 5)
                    & (block_id[:-1] >= 0) & (block_id[:-1] == block_id[1:]))
    return selected


def make_bouts(times, block_id, selected, fs, lfp_start, n_samples):
    bouts, i = [], 0
    while i < len(times) - 1:
        if not selected[i]:
            i += 1
            continue
        first = i
        while i < len(times) - 1 and selected[i] and block_id[i] == block_id[first]:
            i += 1
        a, b = math.ceil((times[first] - lfp_start) * fs), math.floor((times[i] - lfp_start) * fs)
        require(0 <= a <= b <= n_samples, "behavior bout outside original LFP support")
        n_windows = max(0, 1 + (b - a - WINDOW) // HOP)
        bouts.append(dict(bout_id=len(bouts), block_id=int(block_id[first]), start_row=first, end_row=i,
                          start_time_s=float(times[first]), stop_time_s=float(times[i]), start_sample=a,
                          end_sample=b, n_samples=b - a, n_windows=n_windows,
                          status="retained" if n_windows else "short"))
    return bouts


def prepare_behavior(position, timestamps, fs=FS, lfp_start=0, n_samples=31878000):
    position, times = np.asarray(position, dtype=np.float64), np.asarray(timestamps, dtype=np.float64)
    require(position.shape == (len(times), 2) and len(times) >= 2, "invalid behavior arrays")
    require(np.isfinite(times).all() and np.all(np.diff(times) > 0), "invalid original timestamps")
    dt0 = float(np.median(np.diff(times)))
    valid = np.isfinite(position).all(axis=1)
    block_id = np.full(len(times), -1, dtype=np.int64)
    smoothed, speed = np.full_like(position, np.nan), np.full(len(times), np.nan)
    blocks, i = [], 0
    while i < len(times):
        if not valid[i]:
            i += 1
            continue
        first = i
        while i + 1 < len(times) and valid[i + 1] and times[i + 1] - times[i] <= 1.5 * dt0:
            i += 1
        stop = i + 1
        block_id[first:stop] = len(blocks)
        local_times = times[first:stop]
        for row in range(first, stop):
            if times[row] - times[first] < 1 or times[stop - 1] - times[row] < 1:
                continue
            # Search bounds only identify candidates: floating t+1/t-1 can
            # differ from the actual abs(t_j-t_i)<=1 predicate at one boundary.
            left = max(first, first + np.searchsorted(local_times, times[row] - 1, side="left") - 1)
            right = min(stop, first + np.searchsorted(local_times, times[row] + 1, side="right") + 1)
            indices = np.arange(left, right)
            indices = indices[np.abs(times[indices] - times[row]) <= 1]
            weights = np.exp(-0.5 * ((times[indices] - times[row]) / 0.25) ** 2)
            smoothed[row] = (weights / np.sum(weights)) @ position[indices]
            require(np.isfinite(smoothed[row]).all(), "nonfinite smoothed position")
        for row in range(first + 1, stop - 1):
            if np.isfinite(smoothed[row - 1:row + 2]).all():
                velocity = central_derivative(times[row - 1:row + 2], smoothed[row - 1:row + 2])
                speed[row] = np.hypot(*velocity)
                require(np.isfinite(speed[row]), "nonfinite speed")
        blocks.append(dict(block_id=len(blocks), start_row=first, end_row_exclusive=stop, n_rows=stop - first,
                           start_time_s=float(times[first]), last_time_s=float(times[stop - 1]),
                           n_smoothed=int(np.isfinite(smoothed[first:stop]).all(axis=1).sum()),
                           n_speed_valid=int(np.isfinite(speed[first:stop]).sum())))
        i = stop
    selected = select_intervals(speed, block_id)
    bouts = make_bouts(times, block_id, selected, fs, lfp_start, n_samples)
    return {"position": position, "timestamps": times, "position_valid": valid, "block_id": block_id,
            "smoothed_position": smoothed, "speed": speed, "selected_interval_to_next": selected,
            "blocks": blocks, "bouts": bouts, "dt0_s": dt0, "gap_threshold_s": 1.5 * dt0}


def planned_windows(prepared, n_samples):
    rows = []
    for condition in ("locomotion", "whole_session"):
        spans = prepared["bouts"] if condition == "locomotion" else [
            {"bout_id": -1, "start_sample": 0, "end_sample": n_samples}]
        index = 0
        for span in spans:
            for start in range(span["start_sample"], span["end_sample"] - WINDOW + 1, HOP):
                rows.append(dict(condition=condition, bout_id=span["bout_id"], window_index=index,
                                 start_sample=start, end_sample=start + WINDOW))
                index += 1
    return rows


def analyze_windows(counts, prepared, conversion, offset=0, pilot_windows=None):
    counts = np.asarray(counts)
    require(counts.ndim == 1 and np.isfinite(counts).all(), "nonfinite or invalid fixed-channel LFP")
    require(pilot_windows is None or 1 <= pilot_windows <= 4, "pilot limit must be1..4")
    windows, sums = [], {k: np.zeros(WINDOW // 2 + 1) for k in ("locomotion", "whole_session")}
    numbers = {k: 0 for k in sums}
    for row in planned_windows(prepared, len(counts)):
        condition = row["condition"]
        if pilot_windows is not None and numbers[condition] >= pilot_windows:
            continue
        x = counts[row["start_sample"]:row["end_sample"]].astype(np.float64) * conversion + offset
        frequencies, power = window_spectrum(x)
        row.update(mean_volts=float(np.mean(x)), mean_square_volts=float(np.mean(x * x)),
                   theta_power_v2=theta_integral(frequencies, power))
        require(all(np.isfinite(row[k]) for k in ("mean_volts", "mean_square_volts", "theta_power_v2")),
                "nonfinite window receipt")
        windows.append(row)
        sums[condition] += power
        numbers[condition] += 1
    require(all(numbers.values()), "no complete locomotion or whole-session window")
    spectra = {k: sums[k] / numbers[k] for k in sums}
    conditions = {k: {"n_windows": numbers[k], **peak_summary(frequencies, spectra[k])} for k in sums}
    return {"windows": windows, "frequencies": frequencies, "spectra": spectra, "conditions": conditions}


def make_results(contract, prepared, analysis, status="ok"):
    counts = {}
    for row in analysis["windows"]:
        if row["condition"] == "locomotion":
            counts[row["bout_id"]] = counts.get(row["bout_id"], 0) + 1
    bouts = prepared["bouts"]
    return {"status": status, "pipeline_id": PIPELINE_ID, "channel": contract["channel"],
            "n_behavior_rows": len(prepared["timestamps"]),
            "n_valid_position_rows": int(prepared["position_valid"].sum()),
            "n_behavior_blocks": len(prepared["blocks"]), "n_locomotion_bouts": len(bouts),
            "n_retained_bouts": sum(b["n_windows"] > 0 for b in bouts),
            "n_short_bouts": sum(b["n_windows"] == 0 for b in bouts),
            "dt0_s": prepared["dt0_s"], "gap_threshold_s": prepared["gap_threshold_s"],
            "locomotion_interval_duration_s": sum(b["stop_time_s"] - b["start_time_s"] for b in bouts),
            "locomotion_sample_support_s": sum(b["n_samples"] for b in bouts) / FS,
            "locomotion_used_support_s": sum(WINDOW + HOP * (n - 1) for n in counts.values()) / FS,
            "peak_difference_hz": (analysis["conditions"]["locomotion"]["theta_peak_frequency_hz"]
                                   - analysis["conditions"]["whole_session"]["theta_peak_frequency_hz"]),
            "conditions": analysis["conditions"]}


def make_metadata(inputs, source, status="ok"):
    return {"status": status, "task_id": "HIPPOTHETA-001", "pipeline_id": PIPELINE_ID,
            "source_manifest_sha256": inputs["source_manifest_sha256"],
            "method_contract_sha256": inputs["method_contract_sha256"],
            "source_sha256": inputs["source_sha256"], "source_observed": source["observed"],
            "software_versions": {"python": platform.python_version(), **{
                package: importlib.metadata.version(package) for package in ("numpy", "scipy", "h5py")}},
            "method_contract": inputs["contract"]}


def nullable(value):
    return float(value) if np.isfinite(value) else None


def behavior_rows(prepared):
    rows = []
    for i, timestamp in enumerate(prepared["timestamps"]):
        x, y = prepared["position"][i]
        sx, sy = prepared["smoothed_position"][i]
        speed, block = prepared["speed"][i], int(prepared["block_id"][i])
        rows.append(dict(row_id=i, timestamp_s=float(timestamp), x_cm=nullable(x), y_cm=nullable(y),
                         position_valid=int(prepared["position_valid"][i]), block_id=block if block >= 0 else None,
                         smoothed_x_cm=nullable(sx), smoothed_y_cm=nullable(sy),
                         smoothed_valid=int(np.isfinite([sx, sy]).all()), speed_cm_s=nullable(speed),
                         speed_valid=int(np.isfinite(speed)),
                         selected_interval_to_next=int(prepared["selected_interval_to_next"][i])))
    return rows


def ensure_fresh_outputs(output_dir, private_dir):
    output, private = Path(output_dir), Path(private_dir)
    require(not output.is_symlink() and not private.is_symlink(), "symlinked output directory")
    require(private.resolve() != output.resolve() and output.resolve() not in private.resolve().parents,
            "private evidence must remain outside the public output directory")
    for path in [*(output / name for name in PUBLIC_FILES), private / "analysis_arrays.npz"]:
        require(not path.exists() and not path.is_symlink(), f"refusing to overwrite existing evidence: {path}")


def write_outputs(inputs, source, prepared, analysis, output_dir, private_dir, status="ok"):
    ensure_fresh_outputs(output_dir, private_dir)
    output, private = Path(output_dir), Path(private_dir)
    output.mkdir(parents=True, exist_ok=True)
    private.mkdir(parents=True, exist_ok=True)
    results, metadata = make_results(inputs["contract"], prepared, analysis, status), make_metadata(inputs, source, status)
    tables = {"behavior": behavior_rows(prepared), "blocks": prepared["blocks"], "bouts": prepared["bouts"],
              "windows": analysis["windows"], "spectrum": [
                  {"condition": name, "frequency_hz": float(f), "power_v2_per_hz": float(p)}
                  for name, power in analysis["spectra"].items() for f, p in zip(analysis["frequencies"], power)]}
    for name, rows in tables.items():
        with (output / f"{name}.csv").open("x", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=inputs["contract"]["outputs"][f"{name}.csv"])
            writer.writeheader()
            writer.writerows(rows)
    for name, obj in (("results.json", results), ("run_metadata.json", metadata)):
        with (output / name).open("x") as stream:
            json.dump(obj, stream, indent=2, allow_nan=False)
            stream.write("\n")
    conditions = results["conditions"]
    with (output / "findings.md").open("x") as stream:
        stream.write(f"# Fixed-electrode descriptive method control ({status})\n\n")
        for name, values in conditions.items():
            stream.write(f"{name}: {values['n_windows']} complete windows; interpolated6–10 Hz band maximum "
                         f"{values['theta_peak_frequency_hz']:.9g} Hz; band-edge={values['peak_at_band_edge']}, "
                         f"tied grid maxima={values['peak_tie_count']}.\n\n")
        stream.write(f"Locomotion minus whole-session peak: {results['peak_difference_hz']:.9g} Hz.\n\n"
                     f"Only {results['n_retained_bouts']} of {results['n_locomotion_bouts']} selected bouts "
                     f"contribute complete windows; {results['n_short_bouts']} are shorter than four seconds. "
                     f"Unique used locomotion support is {results['locomotion_used_support_s']:.9g} s, "
                     f"versus {results['locomotion_interval_duration_s']:.9g} s selected by the speed rule. "
                     "This sustained-window subset does not represent every above-threshold moment.\n\n"
                     "This is a custom single-session method control, not the paper's birthdate/connectivity finding. "
                     "Electrode anatomy is unknown. Original relative clocks are inherited, not independently TTL-verified; "
                     "conflicting source calendar dates are retained without a calendar shift. A band maximum does not prove "
                     "a physiological oscillation or artifact-free signal. Whole session is not REM or immobility. "
                     "Overlapping windows and nested condition samples are not independent biological replicates; "
                     "no causal, anatomical, inferential or model-hardness claim is made.\n")
    arrays = {"pipeline_id": np.array(PIPELINE_ID), "raw_lfp_counts": source["counts"],
              "original_position": source["position"], "original_timestamps": source["timestamps"],
              "frequencies": analysis["frequencies"],
              **{key: prepared[key] for key in ("smoothed_position", "speed", "position_valid", "block_id", "selected_interval_to_next")},
              **{f"psd_{name}": power for name, power in analysis["spectra"].items()},
              **{f"{name}_json": np.array(json.dumps(rows, allow_nan=False)) for name, rows in tables.items()},
              "results_json": np.array(json.dumps(results, allow_nan=False)),
              "metadata_json": np.array(json.dumps(metadata, allow_nan=False))}
    with (private / "analysis_arrays.npz").open("xb") as stream:
        np.savez_compressed(stream, **arrays)
    return results


def failure_outputs(output_dir, reason):
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    result = {"status": "failed_precondition", "pipeline_id": PIPELINE_ID, "task_id": "HIPPOTHETA-001", "reason": str(reason)}
    for name in ("results.json", "run_metadata.json"):
        if not (output / name).exists():
            with (output / name).open("x") as stream:
                json.dump(result, stream, allow_nan=False)
    if not (output / "findings.md").exists():
        with (output / "findings.md").open("x") as stream:
            stream.write(f"Failed precondition: {reason}\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", "--data-dir", type=Path, default=Path("/app/source"))
    parser.add_argument("--method-contract", type=Path, default=Path("/app/method_contract.json"))
    parser.add_argument("--output-dir", type=Path, default=Path(os.environ.get("OUTPUT_DIR", "/app/output")))
    parser.add_argument("--private-dir", type=Path, default=Path(os.environ.get("PRIVATE_DIR", "/app/oracle_private")))
    parser.add_argument("--pilot-windows", "--max-windows-per-condition", type=int, choices=range(1, 5))
    args = parser.parse_args()
    ensure_fresh_outputs(args.output_dir, args.private_dir)
    try:
        inputs = load_inputs(args.source_dir, args.method_contract)
        source = read_source(inputs)
        prepared = prepare_behavior(source["position"], source["timestamps"], n_samples=len(source["counts"]))
        analysis = analyze_windows(source["counts"], prepared, source["observed"]["lfp_conversion"],
                                   source["observed"]["lfp_offset"], args.pilot_windows)
        result = write_outputs(inputs, source, prepared, analysis, args.output_dir, args.private_dir,
                               "resource_pilot" if args.pilot_windows is not None else "ok")
        print(json.dumps(result, allow_nan=False))
    except Exception as exc:
        failure_outputs(args.output_dir, exc)
        raise


if __name__ == "__main__":
    main()
