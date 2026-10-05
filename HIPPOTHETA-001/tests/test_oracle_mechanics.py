"""Small synthetic-only oracle mechanics; never open the original recordings."""
import copy
import csv
import importlib.util
import json
from pathlib import Path

import h5py
import numpy as np
import pytest

TASK = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("hippotheta_oracle", TASK / "solution/compute.py")
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)


@pytest.fixture
def contract():
    return json.loads((TASK / "environment/method_contract.json").read_text())


@pytest.fixture
def movement():
    times = np.arange(0, 20.125, 0.125)
    prepared = oracle.prepare_behavior(np.column_stack((10 * times, 0 * times)), times, n_samples=30000)
    return prepared


def test_public_pins(contract):
    assert oracle.sha256(TASK / "environment/method_contract.json") == oracle.METHOD_SHA256
    assert oracle.sha256(TASK / "environment/source_manifest.json") == oracle.MANIFEST_SHA256
    assert contract["contract_id"] == oracle.PIPELINE_ID


def test_constant_velocity_full_support(movement):
    assert len(movement["blocks"]) == 1
    speed = movement["speed"]
    np.testing.assert_allclose(speed[np.isfinite(speed)], 10, atol=1e-11)
    assert not np.isfinite(speed[:9]).any()
    assert np.isfinite(movement["smoothed_position"][8]).all()
    assert not np.isfinite(speed[8])
    assert len(movement["bouts"]) == 1
    assert movement["bouts"][0]["start_row"] == 9
    assert not movement["selected_interval_to_next"][-1]


def test_irregular_gaussian_uses_actual_times():
    times = np.cumsum(np.tile([0.031, 0.034, 0.033, 0.035], 40))
    position = np.column_stack((times**2, np.sin(times)))
    result = oracle.prepare_behavior(position, times)
    i = 80
    take = np.abs(times - times[i]) <= 1
    weights = np.exp(-0.5 * ((times[take] - times[i]) / 0.25)**2)
    expected = (weights[:, None] * position[take]).sum(axis=0) / weights.sum()
    np.testing.assert_allclose(result["smoothed_position"][i], expected, rtol=1e-14)


def test_nonuniform_central_derivative_quadratic():
    times = np.array([0.7, 1.0, 1.9])
    values = np.column_stack((times**2, 3 * times**2 + 2 * times))
    np.testing.assert_allclose(oracle.central_derivative(times, values), [2, 8], atol=1e-14)


def test_float_boundary_uses_difference_not_rounded_search_bound():
    times = np.linspace(0, 3, 31)
    times[1], times[11] = 0.10000000000000003, 1.1
    assert times[1] < times[11] - 1
    assert times[11] - times[1] == 1
    position = np.zeros((len(times), 2))
    position[1, 0] = 100
    result = oracle.prepare_behavior(position, times)
    use = np.abs(times - times[11]) <= 1
    weights = np.exp(-0.5 * ((times[use] - times[11]) / .25)**2)
    expected = np.sum(weights * position[use, 0]) / np.sum(weights)
    assert expected > 0
    assert result["smoothed_position"][11, 0] == pytest.approx(expected, rel=1e-14)


@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf])
def test_missing_coordinate_breaks_block_preserves_other_axis(bad):
    times = np.arange(0, 8.25, 0.25)
    position = np.column_stack((times, 2 * times))
    position[16, 0] = bad
    result = oracle.prepare_behavior(position, times)
    assert len(result["blocks"]) == 2
    assert result["block_id"][16] == -1
    row = oracle.behavior_rows(result)[16]
    assert row["x_cm"] is None and row["y_cm"] == 8
    assert row["block_id"] is None and row["position_valid"] == 0
    assert not result["selected_interval_to_next"][15:17].any()


def test_gap_rule_exact_boundary_and_above():
    times = np.array([0, 1, 2, 3.5, 4.5, 5.5, 7.01, 8.01, 9.01])
    result = oracle.prepare_behavior(np.zeros((len(times), 2)), times)
    assert result["dt0_s"] == 1
    assert result["blocks"][0]["end_row_exclusive"] == 6
    assert len(result["blocks"]) == 2


@pytest.mark.parametrize("times", [[0, 0, 1], [0, -1, 1], [0, np.nan, 1], [0, np.inf, 1]])
def test_bad_timestamps_rejected(times):
    with pytest.raises(ValueError, match="timestamps"):
        oracle.prepare_behavior(np.zeros((3, 2)), np.array(times))


def test_threshold_strict_and_no_block_bridging():
    speed = np.array([6, 5, 6, 6, np.nan, 7, 7])
    blocks = np.array([0, 0, 0, 1, -1, 2, 2])
    np.testing.assert_array_equal(oracle.select_intervals(speed, blocks), [False]*5 + [True, False])


def test_bounds_ceil_floor_short_and_no_clipping():
    t = np.array([0.0001, 0.4001, 0.8001])
    bouts = oracle.make_bouts(t, np.zeros(3, dtype=int), np.array([True, True, False]), 1250, 0, 2000)
    assert (bouts[0]["start_sample"], bouts[0]["end_sample"]) == (1, 1000)
    assert bouts[0]["status"] == "short" and bouts[0]["n_windows"] == 0
    with pytest.raises(ValueError, match="outside"):
        oracle.make_bouts(t, np.zeros(3, dtype=int), np.array([True, True, False]), 1250, 1, 2000)


def test_no_joining_short_bouts():
    prepared = {"bouts": [{"bout_id": 0, "start_sample": 0, "end_sample": 3000},
                          {"bout_id": 1, "start_sample": 6000, "end_sample": 9000}]}
    assert not any(r["condition"] == "locomotion" for r in oracle.planned_windows(prepared, 10000))
    with pytest.raises(ValueError, match="no complete"):
        oracle.analyze_windows(np.zeros(10000), prepared, 1)


def test_periodogram_matches_explicit_fft_and_raw_moments():
    x = 3 + np.cos(2 * np.pi * 8 * np.arange(5000) / 1250)
    frequencies, actual = oracle.window_spectrum(x)
    w = 0.5 - 0.5 * np.cos(2 * np.pi * np.arange(5000) / 5000)
    expected = abs(np.fft.rfft((x - x.mean()) * w))**2 / (1250 * np.sum(w*w))
    expected[1:-1] *= 2
    np.testing.assert_allclose(actual, expected, atol=1e-28, rtol=1e-12)
    prepared = {"bouts": [{"bout_id": 0, "start_sample": 0, "end_sample": 5000}]}
    result = oracle.analyze_windows(x, prepared, 1)
    assert result["windows"][0]["mean_volts"] == pytest.approx(3)
    assert result["windows"][0]["mean_square_volts"] == pytest.approx(9.5)
    assert result["conditions"]["locomotion"]["theta_peak_grid_hz"] == 8
    assert oracle.theta_integral(frequencies, actual) == pytest.approx(0.5)


def test_individual_window_weighting_not_equal_bouts():
    n = 25000
    x = np.cos(2*np.pi*8*np.arange(n)/1250)
    x[15000:] *= 3
    prepared = {"bouts": [{"bout_id": 0, "start_sample": 0, "end_sample": 5000},
                          {"bout_id": 1, "start_sample": 15000, "end_sample": 25000}]}
    analysis = oracle.analyze_windows(x, prepared, 1)
    assert analysis["conditions"]["locomotion"]["n_windows"] == 4
    assert analysis["conditions"]["locomotion"]["theta_power_v2"] == pytest.approx((0.5 + 3*4.5)/4)


def test_peak_ties_edges_and_interpolation():
    f = np.arange(2501)/4
    p = np.ones(2501)
    result = oracle.peak_summary(f, p)
    assert result["theta_peak_grid_hz"] == 6 and result["peak_tie_count"] == 17
    assert result["peak_at_band_edge"] is True
    p[:] = 0
    p[31:34] = [2, 4, 3]
    result = oracle.peak_summary(f, p)
    assert result["theta_peak_frequency_hz"] == pytest.approx(8 + 1/24)
    p[:] = 0
    p[24], p[40] = 2, 4
    assert oracle.theta_integral(f, p) == 0.75


@pytest.mark.parametrize("bad", [np.nan, np.inf])
def test_nonfinite_lfp_is_not_silently_removed(bad, movement):
    x = np.zeros(30000)
    x[0] = bad
    with pytest.raises(ValueError, match="nonfinite"):
        oracle.analyze_windows(x, movement, 1)


def test_pilot_first_four_each_condition(movement, contract):
    x = np.sin(2*np.pi*8*np.arange(30000)/1250)
    result = oracle.analyze_windows(x, movement, 1, pilot_windows=4)
    assert len(result["windows"]) == 8
    for condition in ("locomotion", "whole_session"):
        assert [r["window_index"] for r in result["windows"] if r["condition"] == condition] == [0,1,2,3]
    summary = oracle.make_results(contract, movement, result, "resource_pilot")
    assert summary["status"] == "resource_pilot" and summary["locomotion_used_support_s"] == 10


def test_output_schema_private_separation_and_preservation(tmp_path, movement, contract):
    source = {"counts": np.zeros(30000, dtype=np.int16), "position": movement["position"],
              "timestamps": movement["timestamps"], "observed": {}}
    inputs = {"contract": contract, "source_sha256": {}, "source_manifest_sha256": oracle.MANIFEST_SHA256,
              "method_contract_sha256": oracle.METHOD_SHA256}
    analysis = oracle.analyze_windows(source["counts"], movement, 1.95e-7, pilot_windows=4)
    output, private = tmp_path / "public", tmp_path / "private"
    oracle.write_outputs(inputs, source, movement, analysis, output, private, "resource_pilot")
    assert {p.name for p in output.iterdir()} == set(oracle.PUBLIC_FILES)
    with (output / "behavior.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    assert rows[0]["speed_cm_s"] == "" and rows[0]["smoothed_x_cm"] == ""
    result = json.loads((output / "results.json").read_text())
    assert set(result) == set(contract["outputs"]["results.json"])
    assert result["channel"] == contract["channel"]
    with np.load(private / "analysis_arrays.npz", allow_pickle=False) as arrays:
        assert arrays["raw_lfp_counts"].dtype == np.int16
        assert str(arrays["pipeline_id"]) == oracle.PIPELINE_ID
    with pytest.raises(ValueError, match="overwrite"):
        oracle.write_outputs(inputs, source, movement, analysis, output, private)
    with pytest.raises(ValueError, match="outside"):
        oracle.ensure_fresh_outputs(tmp_path / "new", tmp_path / "new/private")


def test_failure_outputs_are_parseable_and_nonoverwriting(tmp_path):
    oracle.failure_outputs(tmp_path, "fixture failure")
    oracle.failure_outputs(tmp_path, "later failure")
    assert json.loads((tmp_path / "results.json").read_text())["reason"] == "fixture failure"


def test_wrong_method_rejected_before_source_read(tmp_path):
    fake = tmp_path / "method.json"
    fake.write_text("{}")
    with pytest.raises(ValueError, match="method contract checksum"):
        oracle.load_inputs(tmp_path, fake)


def make_source_fixture(tmp_path, contract):
    c = copy.deepcopy(contract)
    c["lfp"].update(n_samples=20, n_channels=2)
    c["behavior"].update(shape=[3, 2], first_timestamp_s=0.0, last_timestamp_s=0.2)
    paths = {role: tmp_path / f"{role}.nwb" for role in ("raw", "behavior")}
    for role, path in paths.items():
        with h5py.File(path, "w") as file:
            file["session_start_time"] = c["clocks"][f"{role}_calendar"]
            file["timestamps_reference_time"] = c["clocks"][f"{role}_calendar"]
            file["general/session_id"] = c["source"]["session"] + ("_raw" if role == "raw" else "")
            if role == "raw":
                table = file.create_group(oracle.TABLE)
                table["id"], table["channel_name"], table["location"] = [0, 1], [b"1", b"2"], [b"unknown", b"unknown"]
                es = file.create_group(c["lfp"]["path"])
                es["data"] = np.arange(40, dtype=np.int16).reshape(20, 2)
                es["data"].attrs.update(unit="volts", conversion=1.9499999999999999e-7, offset=0.0)
                es["starting_time"] = 0.0
                es["starting_time"].attrs.update(unit="seconds", rate=1250.0)
                es["electrodes"] = [0, 1]
                es["electrodes"].attrs["table"] = table.ref
            else:
                sp = file.create_group(c["behavior"]["path"])
                sp["data"] = np.zeros((3, 2))
                sp["data"].attrs.update(unit="cm", conversion=1.0, offset=0.0)
                sp["timestamps"] = [0, .1, .2]
                sp["timestamps"].attrs["unit"] = "seconds"
                sp["reference_frame"] = "Arbitrary, camera"
    return {"contract": c, "paths": paths}


def test_source_reader_original_mapping_scale_and_dates(tmp_path, contract):
    inputs = make_source_fixture(tmp_path, contract)
    source = oracle.read_source(inputs)
    np.testing.assert_array_equal(source["counts"], np.arange(0, 40, 2))
    assert source["observed"]["raw_calendar"] != source["observed"]["behavior_calendar"]
    assert source["observed"]["lfp_conversion"] == 1.9499999999999999e-7
    assert set(source["observed"]) == set(contract["source_observed_fields"])


@pytest.mark.parametrize("mutation", ["units", "mapping", "calendar", "channel_scaling", "timestamp"])
def test_source_reader_fails_closed(tmp_path, contract, mutation):
    inputs = make_source_fixture(tmp_path, contract)
    with h5py.File(inputs["paths"]["raw"], "r+") as file:
        es = file[contract["lfp"]["path"]]
        if mutation == "units":
            es["data"].attrs["unit"] = "microvolts"
        elif mutation == "mapping":
            es["electrodes"][0] = 1
        elif mutation == "calendar":
            file["session_start_time"][()] = contract["clocks"]["behavior_calendar"]
        elif mutation == "channel_scaling":
            es["channel_conversion"] = [1, 1]
        elif mutation == "timestamp":
            es["timestamps"] = np.arange(20)/1250
    with pytest.raises(ValueError):
        oracle.read_source(inputs)
