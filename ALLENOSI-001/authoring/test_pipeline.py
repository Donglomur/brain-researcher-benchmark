"""Tiny NWB-like HDF5 fixtures; never a scientific bank or real-source run."""
import csv
import importlib.util
import json
from pathlib import Path

import h5py
import numpy as np
import pytest

SPEC = importlib.util.spec_from_file_location("allenosi_pipeline_mechanics", Path(__file__).parents[1] / "solution/compute.py")
c = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(c)


@pytest.fixture
def fixture_inputs(tmp_path):
    path = tmp_path / "mechanical.nwb"
    with h5py.File(path, "w") as h:
        e = h.create_group(c.ELECTRODE_PATH)
        e["id"] = [200, 100, 300]
        e["location"] = np.asarray(["OTHER", "VISp", "VISp"], dtype=h5py.string_dtype())
        u = h.create_group("units")
        u["id"] = [900, 700, 600]
        u["peak_channel_id"] = [100, 200, 300]
        u["spike_times"] = [9.75, 10.0, 10.0, 10.5, 11.0, 18.0, 18.5, 0.0]
        u["spike_times_index"] = [7, 8, 8]
        u["isi_violations"] = [0.1, 0.1, np.nan]
        u["amplitude_cutoff"] = [0.01, 0.01, 0.01]
        # Entire presence_ratio column deliberately absent.
        p = h.create_group(c.STIMULUS_PATH)
        start = 10 + np.arange(16) * 4
        p["id"] = 1000 + np.arange(16) * 7
        p["start_time"] = start.astype(float)
        p["stop_time"] = start.astype(float) + np.tile([1.0, 2.0], 8)
        p["orientation"] = np.repeat(np.arange(0, 360, 45, dtype=float), 2)
        p["temporal_frequency"] = np.tile([1.0, 2.0], 8)
        p["contrast"] = np.full(16, 0.8)
        h["session_id"] = "721123822"
        h["general/subject/subject_id"] = "707296975"
    return {"path": path, "source_sha256": {"mechanical.nwb": "mechanical-fixture-not-a-bank"}}


def test_import_performs_no_io(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("import attempted I/O")
    monkeypatch.setattr(Path, "mkdir", forbidden)
    monkeypatch.setattr(h5py, "File", forbidden)
    spec = importlib.util.spec_from_file_location("allenosi_import_probe", Path(c.__file__))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)


def test_electrode_id_join_not_row_index_and_all_visp_preserved(fixture_inputs):
    source = c.read_source(fixture_inputs)
    np.testing.assert_array_equal(source["unit_id"], [900, 600])
    np.testing.assert_array_equal(source["peak_channel_id"], [100, 300])
    assert len(source["spikes"][0]) == 7
    assert len(source["spikes"][1]) == 0
    assert source["spike_duplicates_by_unit"].tolist() == [1, 0, 0]
    assert np.all(np.isnan(source["qc"]["presence_ratio"]))


def test_probe_cannot_compute_responses_or_osi(fixture_inputs, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("structure probe called scientific analysis")
    for name in ("count_spikes", "condition_means", "two_point_osi", "analyze"):
        monkeypatch.setattr(c, name, forbidden)
    report = c.inspect_source(fixture_inputs)
    assert report["status"] == "source_structure_only"
    assert report["response_counting_performed"] is False
    assert report["n_visp_units_total"] == 2
    assert report["support"]["n_gratings_presentations"] == 16
    assert report["visp_qc_nonfinite_by_field"]["presence_ratio"] == 2
    assert "osi" not in report


def test_inspect_cli_writes_only_requested_probe_report(fixture_inputs, tmp_path, monkeypatch):
    monkeypatch.setattr(c, "load_inputs", lambda path: fixture_inputs)
    output, report = tmp_path / "forbidden-output", tmp_path / "probe.json"
    c.main(["--inspect-source", "--output", str(output), "--report", str(report)])
    assert json.loads(report.read_text())["response_counting_performed"] is False
    assert not output.exists()


@pytest.mark.parametrize("change", ["duplicate_unit", "duplicate_electrode", "unresolved_peak", "unordered_spikes", "nonfinite_spikes", "bad_ragged"])
def test_source_identity_or_spike_errors_fail_closed(fixture_inputs, change):
    with h5py.File(fixture_inputs["path"], "r+") as h:
        if change == "duplicate_unit":
            h["units/id"][1] = 900
        elif change == "duplicate_electrode":
            h[c.ELECTRODE_PATH + "/id"][1] = 200
        elif change == "unresolved_peak":
            h["units/peak_channel_id"][1] = 999
        elif change == "unordered_spikes":
            h["units/spike_times"][3] = 1
        elif change == "nonfinite_spikes":
            h["units/spike_times"][3] = np.nan
        else:
            h["units/spike_times_index"][2] = 7
    with pytest.raises(ValueError):
        c.read_source(fixture_inputs)


def test_primary_only_does_not_touch_optional_baseline(fixture_inputs, monkeypatch):
    source = c.read_source(fixture_inputs)
    def forbidden(*args, **kwargs):
        raise AssertionError("primary-only analysis called QC")
    monkeypatch.setattr(c, "qc_sensitivity", forbidden)
    arrays, result = c.analyze(source, include_qc=False)
    assert arrays["spike_count"].shape == (2, 16)
    assert result["n_visp_units_total"] == result["n_visp_units_analyzed"] == 2
    assert result["n_osi_undefined"] == 1
    assert "baseline_spike_count" not in arrays
    assert "qc_responsive_selective_fraction" not in result


@pytest.mark.parametrize("baseline_only", [False, True])
def test_invalid_intervals_fail_without_silent_exclusions(fixture_inputs, baseline_only):
    with h5py.File(fixture_inputs["path"], "r+") as h:
        invalid = h.create_group("intervals/invalid_times")
        invalid["start_time"] = [9.6 if baseline_only else 10.1]
        invalid["stop_time"] = [9.9 if baseline_only else 10.2]
    source = c.read_source(fixture_inputs)
    with pytest.raises(ValueError, match="invalid interval overlaps"):
        c.analyze(source, include_qc=True)
    if baseline_only:
        # A genuinely optional QC limitation cannot remove primary-only units.
        _, result = c.analyze(source, include_qc=False)
        assert result["n_visp_units_total"] == 2


def test_contrast_mismatch_is_not_a_hidden_trial_filter(fixture_inputs):
    with h5py.File(fixture_inputs["path"], "r+") as h:
        h[c.STIMULUS_PATH + "/contrast"][0] = 0.5
    with pytest.raises(ValueError, match="contrast"):
        c.analyze(c.read_source(fixture_inputs), include_qc=False)


def test_normal_source_load_failure_writes_failure_outputs(tmp_path, monkeypatch):
    def fail(_):
        raise ValueError("source checksum mismatch fixture")
    monkeypatch.setattr(c, "load_inputs", fail)
    output = tmp_path / "failed"
    with pytest.raises(ValueError, match="checksum"):
        c.main(["--output", str(output)])
    assert json.loads((output / "results.json").read_text())["status"] == "failed_precondition"
    assert json.loads((output / "run_metadata.json").read_text())["reason"]
    assert (output / "findings.md").read_text().strip()


@pytest.mark.parametrize("include_qc", [False, True])
def test_coherent_outputs_and_null_empty_qc(fixture_inputs, tmp_path, include_qc):
    source = c.read_source(fixture_inputs)
    arrays, result = c.analyze(source, include_qc)
    output = tmp_path / "outputs"
    metadata = c.write_outputs(output, fixture_inputs, source, arrays, result, include_qc)
    assert metadata["include_qc"] is include_qc
    assert len(list(csv.DictReader((output / "trial_responses.csv").open()))) == 32
    assert len(list(csv.DictReader((output / "units.csv").open()))) == 2
    with np.load(output / "analysis_arrays.npz", allow_pickle=False) as receipt:
        assert receipt["spike_count"].shape == (2, 16)
        assert "elapsed_seconds" not in receipt.files
        assert json.loads(receipt["metadata_json"].item()) == metadata
    if include_qc:
        assert result["n_qc_responsive_units"] == result["n_qc_responsive_orientation_selective"] == 0
        assert result["qc_responsive_selective_fraction"] is None
        rows = list(csv.DictReader((output / "qc_sensitivity.csv").open()))
        assert rows[0]["presence_ratio"] == ""
    else:
        assert not (output / "qc_sensitivity.csv").exists()
        assert not (output / "baseline_counts.csv").exists()
