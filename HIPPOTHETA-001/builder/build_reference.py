"""Rebuild ONLY from hash-verified original NWBs, never from an old answer bank.

Independent raw HDF5 reader + time-domain behavior mechanics + explicit NumPy
periodograms. The public oracle is not imported. Parent-authorized real runs only.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import tempfile

import h5py
import numpy as np

TESTS = Path(__file__).resolve().parents[1] / "tests"
sys.path.insert(0, str(TESTS))
import proof_of_work as pw
from state_contract import PIPELINE_ID, behavior_tables, measure_windows, summarize, window_support


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_files(data_dir, contract_path):
    root = Path(data_dir).resolve()
    contract_path = Path(contract_path)
    contract = pw.read_json(contract_path)
    assert contract["contract_id"] == PIPELINE_ID
    manifest_path = root / "source_manifest.json"
    manifest = pw.read_json(manifest_path)
    assert isinstance(manifest.get("files"), list) and len(manifest["files"]) == 2
    records = {record["role"]: record for record in manifest["files"]}
    assert set(records) == {"raw", "behavior"}, "source manifest roles"
    paths, hashes = {}, {}
    for pinned in contract["source"]["files"]:
        record = records[pinned["role"]]
        for field in ("path", "size_bytes", "sha256"):
            assert record[field] == pinned[field], "source manifest pin mismatch: " + field
        relative = Path(record["path"])
        assert not relative.is_absolute() and ".." not in relative.parts
        path = (root / relative).resolve()
        assert root in path.parents and path.is_file(), "source path outside bundle"
        assert path.stat().st_size == record["size_bytes"], "source size mismatch"
        digest = sha256_file(path)
        assert digest == record["sha256"], "source full-byte hash mismatch"
        paths[pinned["role"]] = path
        hashes[record["path"]] = digest
    return {"contract": contract, "paths": paths, "hashes": hashes,
            "source_manifest_sha256": sha256_file(manifest_path),
            "method_contract_sha256": sha256_file(contract_path)}


def text_value(value):
    if isinstance(value, bytes):
        return value.decode("utf-8")
    if isinstance(value, np.ndarray) and value.shape == ():
        return text_value(value.item())
    return str(value)


def read_source(inputs):
    """Only the fixed original column is read; no all-channel signal search."""
    contract = inputs["contract"]
    lp, bp = contract["lfp"], contract["behavior"]
    with h5py.File(inputs["paths"]["raw"], "r") as raw, h5py.File(inputs["paths"]["behavior"], "r") as behavior:
        electrical = raw[lp["path"]]
        data = electrical["data"]
        assert data.shape == (lp["n_samples"], lp["n_channels"])
        assert str(data.dtype) == lp["dtype"] == "int16"
        assert "channel_conversion" not in electrical, "undeclared per-channel conversion"
        start = float(electrical["starting_time"][()])
        rate = float(electrical["starting_time"].attrs["rate"])
        conversion = float(data.attrs["conversion"])
        offset = float(data.attrs["offset"])
        pw.close(conversion, lp["conversion"], atol=0, rtol=1e-10)
        assert start == lp["start_seconds"] and rate == lp["rate_hz"] and offset == lp["offset"]
        assert text_value(data.attrs["unit"]) == lp["unit"] == "volts"
        region = electrical["electrodes"]
        target = raw[region.attrs["table"]]
        assert target.name == "/general/extracellular_ephys/electrodes"
        column = contract["channel"]["lfp_column"]
        row = int(region[column])
        electrode_id = int(target["id"][row])
        name = text_value(target["channel_name"][row])
        location = text_value(target["location"][row])
        assert row == contract["channel"]["electrode_table_row"]
        assert electrode_id == contract["channel"]["electrode_id"]
        assert name == contract["channel"]["channel_name"] and location == contract["channel"]["location"]
        other_table = behavior["/general/extracellular_ephys/electrodes"]
        assert int(other_table["id"][row]) == electrode_id
        assert text_value(other_table["channel_name"][row]) == name
        assert text_value(other_table["location"][row]) == location
        spatial = behavior[bp["path"]]
        positions = spatial["data"]
        assert list(positions.shape) == bp["shape"]
        unit = text_value(positions.attrs["unit"])
        pc, po = float(positions.attrs["conversion"]), float(positions.attrs["offset"])
        frame = text_value(spatial["reference_frame"][()])
        assert unit == bp["unit"] == "cm" and pc == bp["conversion"] and po == bp["offset"]
        assert frame == bp["reference_frame"]
        timestamps = np.asarray(spatial["timestamps"][:], dtype=np.float64)
        assert timestamps.shape == (bp["shape"][0],)
        assert text_value(spatial["timestamps"].attrs["unit"]) == "seconds"
        assert np.isfinite(timestamps).all() and np.all(np.diff(timestamps) > 0)
        pw.close(timestamps[0], bp["first_timestamp_s"], atol=1e-9, rtol=1e-10)
        pw.close(timestamps[-1], bp["last_timestamp_s"], atol=1e-9, rtol=1e-10)
        observed = {
            "raw_session_id": text_value(raw["/general/session_id"][()]),
            "behavior_session_id": text_value(behavior["/general/session_id"][()]),
            "raw_calendar": text_value(raw["/session_start_time"][()]),
            "behavior_calendar": text_value(behavior["/session_start_time"][()]),
            "raw_timestamps_reference_time": text_value(raw["/timestamps_reference_time"][()]),
            "behavior_timestamps_reference_time": text_value(behavior["/timestamps_reference_time"][()]),
            "n_lfp_samples": data.shape[0], "n_lfp_channels": data.shape[1], "lfp_dtype": str(data.dtype),
            "lfp_start_seconds": start, "lfp_rate_hz": rate, "lfp_unit": text_value(data.attrs["unit"]),
            "lfp_conversion": conversion, "lfp_offset": offset, "lfp_column": column,
            "electrode_table_row": row, "electrode_id": electrode_id, "channel_name": name, "location": location,
            "position_n_rows": positions.shape[0], "position_unit": unit, "position_conversion": pc,
            "position_offset": po, "position_reference_frame": frame,
            "position_first_timestamp_s": float(timestamps[0]), "position_last_timestamp_s": float(timestamps[-1]),
        }
        assert set(observed) == set(contract["source_observed_fields"])
        assert observed["behavior_session_id"] == contract["source"]["session"]
        assert observed["raw_session_id"] == contract["source"]["session"] + "_raw"
        for prefix in ("raw", "behavior"):
            assert observed[prefix + "_calendar"] == contract["clocks"][prefix + "_calendar"]
            assert observed[prefix + "_timestamps_reference_time"] == contract["clocks"][prefix + "_calendar"]
        xy = np.asarray(positions[:], dtype=np.float64) * pc + po
        signal = np.empty(data.shape[0], dtype=np.float64)
        step = data.chunks[0] if data.chunks else 250_000
        for a in range(0, len(signal), step):
            b = min(len(signal), a + step)
            signal[a:b] = np.asarray(data[a:b, column], dtype=np.float64) * conversion + offset
        assert np.isfinite(signal).all(), "nonfinite original LFP"
    return {"positions": xy, "timestamps": timestamps, "volts": signal, "observed": observed}


def build_arrays(inputs, source):
    observed = source["observed"]
    behavior, blocks, bouts, dt0 = behavior_tables(source["timestamps"], source["positions"],
                                                 observed["n_lfp_samples"], fs=observed["lfp_rate_hz"],
                                                 start=observed["lfp_start_seconds"])
    support = window_support(bouts, observed["n_lfp_samples"])
    windows, frequencies, spectra = measure_windows(source["volts"], support, observed["lfp_rate_hz"])
    results = summarize(behavior, blocks, bouts, windows, frequencies, spectra,
                        fs=observed["lfp_rate_hz"], dt0=dt0)
    metadata = {"status": "ok", "task_id": "HIPPOTHETA-001", "pipeline_id": PIPELINE_ID,
                "source_manifest_sha256": inputs["source_manifest_sha256"],
                "method_contract_sha256": inputs["method_contract_sha256"],
                "source_sha256": inputs["hashes"], "source_observed": observed,
                "software_versions": {"python": platform.python_version(), "numpy": np.__version__, "h5py": h5py.__version__},
                "method_contract": inputs["contract"]}
    stats = {"pipeline_id": PIPELINE_ID, "source_sha256": inputs["hashes"], "metadata": metadata,
             "results": results, "builder": "independent raw HDF5/time-kernel/NumPy-rFFT; no oracle numeric import"}
    arrays = {"ref_" + key + "_json": np.array(json.dumps(value, allow_nan=False, separators=(",", ":")))
              for key, value in {"behavior": behavior, "blocks": blocks, "bouts": bouts, "windows": windows}.items()}
    arrays.update(ref_frequencies=frequencies, ref_spectra=spectra,
                  ref_stats=np.array(json.dumps(stats, allow_nan=False, separators=(",", ":"))))
    return arrays


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default="/app/source")
    parser.add_argument("--method-contract", default="/app/method_contract.json")
    parser.add_argument("--oracle-output", required=True)
    parser.add_argument("--independent-output")
    parser.add_argument("--reference", default=str(TESTS / "reference.npz"))
    args = parser.parse_args()
    inputs = source_files(args.data_dir, args.method_contract)
    source = read_source(inputs)
    arrays = build_arrays(inputs, source)
    destination = Path(args.reference)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent, prefix=".pending-reference-", suffix=".npz", delete=False) as handle:
        temporary = Path(handle.name)
    try:
        np.savez_compressed(temporary, **arrays)
        reference = pw.load_reference(temporary, method_contract_path=args.method_contract)
        pw.validate_output_directory(args.oracle_output, reference)
        if args.independent_output:
            pw.validate_output_directory(args.independent_output, reference)
        os.replace(temporary, destination)
    except BaseException:
        # Keep any prior bank intact; this scratch artifact contains no unique evidence.
        temporary.unlink(missing_ok=True)
        raise
    print(json.dumps({"status": "ok", "reference": str(destination), "sha256": sha256_file(destination),
                      "source_sha256": inputs["hashes"], "results": reference["results"]}, allow_nan=False))


if __name__ == "__main__":
    main()
