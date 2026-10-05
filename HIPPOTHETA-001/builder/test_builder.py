"""Synthetic source-reader/provenance fixtures, not measurements on DANDI data."""
import copy
import importlib.util
import json
from pathlib import Path
import sys

import h5py
import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("hippotheta_independent_builder", HERE / "build_reference.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


@pytest.fixture
def miniature_source(tmp_path):
    contract = json.loads((HERE.parent / "environment" / "method_contract.json").read_text())
    contract = copy.deepcopy(contract)
    contract["lfp"].update(n_samples=100, n_channels=2)
    contract["behavior"].update(shape=[3, 2], first_timestamp_s=0.0, last_timestamp_s=0.07)
    paths = {}
    for role in ("raw", "behavior"):
        path = tmp_path / (role + ".nwb")
        paths[role] = path
        with h5py.File(path, "w") as archive:
            archive.create_dataset("general/session_id", data=contract["source"]["session"] + ("_raw" if role == "raw" else ""))
            archive.create_dataset("session_start_time", data=contract["clocks"][role + "_calendar"])
            archive.create_dataset("timestamps_reference_time", data=contract["clocks"][role + "_calendar"])
            table = archive.create_group("general/extracellular_ephys/electrodes")
            table.create_dataset("id", data=[0, 1])
            table.create_dataset("channel_name", data=np.array(["1", "2"], dtype="S1"))
            table.create_dataset("location", data=np.array(["unknown", "unknown"], dtype="S7"))
            if role == "raw":
                group = archive.create_group(contract["lfp"]["path"])
                dataset = group.create_dataset("data", data=np.arange(200, dtype=np.int16).reshape(100, 2), chunks=(10, 1))
                dataset.attrs.update(conversion=1.9499999999999999e-7, offset=0.0, unit="volts")
                time = group.create_dataset("starting_time", data=0.0)
                time.attrs["rate"] = 1250.0
                region = group.create_dataset("electrodes", data=[0, 1])
                region.attrs["table"] = table.ref
            else:
                group = archive.create_group(contract["behavior"]["path"])
                dataset = group.create_dataset("data", data=[[1, 2], [np.nan, 3], [4, 5]])
                dataset.attrs.update(conversion=1.0, offset=0.0, unit="cm")
                group.create_dataset("reference_frame", data="Arbitrary, camera")
                times = group.create_dataset("timestamps", data=[0.0, 0.035, 0.07])
                times.attrs["unit"] = "seconds"
    records = []
    for record in contract["source"]["files"]:
        path = paths[record["role"]]
        record.update(path=path.name, size_bytes=path.stat().st_size, sha256=builder.sha256_file(path))
        records.append(dict(record))
    (tmp_path / "source_manifest.json").write_text(json.dumps({"files": records}))
    method = tmp_path / "method_contract.json"
    method.write_text(json.dumps(contract))
    return tmp_path, method, paths


def test_full_hashes_then_independent_header_and_column_reader(miniature_source):
    root, method, _ = miniature_source
    inputs = builder.source_files(root, method)
    source = builder.read_source(inputs)
    assert len(source["volts"]) == 100
    assert np.allclose(source["volts"], np.arange(0, 200, 2) * 1.95e-7, rtol=1e-14, atol=0)
    assert np.isnan(source["positions"][1, 0]) and source["positions"][1, 1] == 3
    assert source["observed"]["raw_session_id"].endswith("_raw")


def test_changed_original_bytes_rejected(miniature_source):
    root, method, paths = miniature_source
    with h5py.File(paths["raw"], "r+") as archive:
        archive["processing/ecephys/LFP/ElectricalSeriesLFP/data"][0, 0] = 99
    with pytest.raises(AssertionError, match="hash"):
        builder.source_files(root, method)


@pytest.mark.parametrize("mutation", ["unit", "conversion", "start", "channel_name", "location", "calendar", "timestamp_order", "position_units"])
def test_header_schema_mismatches_fail_before_measurement(miniature_source, mutation):
    root, method, paths = miniature_source
    inputs = builder.source_files(root, method)
    with h5py.File(paths["raw"], "r+") as raw, h5py.File(paths["behavior"], "r+") as behavior:
        lfp = raw["processing/ecephys/LFP/ElectricalSeriesLFP"]
        if mutation == "unit":
            lfp["data"].attrs["unit"] = "uV"
        elif mutation == "conversion":
            lfp["data"].attrs["conversion"] = 1.0
        elif mutation == "start":
            lfp["starting_time"][()] = 1.0
        elif mutation in {"channel_name", "location"}:
            raw["general/extracellular_ephys/electrodes/" + mutation][0] = b"2" if mutation == "channel_name" else b"CA1"
        elif mutation == "calendar":
            raw["session_start_time"][()] = "2022-01-17T00:00:00-05:00"
        elif mutation == "timestamp_order":
            behavior["processing/behavior/SubjectPosition/SpatialSeries/timestamps"][1] = -1
        else:
            behavior["processing/behavior/SubjectPosition/SpatialSeries/data"].attrs["unit"] = "pixels"
    # Direct header-reader mechanics only; production verifies full bytes first.
    with pytest.raises(AssertionError):
        builder.read_source(inputs)


def test_no_oracle_numeric_import():
    text = (HERE / "build_reference.py").read_text()
    assert "solution.compute" not in text and "import compute" not in text
    assert "np.fft.rfft" in (HERE.parent / "tests" / "state_contract.py").read_text()
