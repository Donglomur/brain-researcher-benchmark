"""Small synthetic mechanics only, never evidence about the original recording."""
import copy
import csv
import json
import math
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
import proof_of_work as pw
import state_contract as sc


def write_table(path, table, rows, extra=False):
    fields = list(pw.FIELDS[table]) + (["comment"] if extra else [])
    with Path(path).open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: "" if row.get(key) is None else row.get(key) for key in fields})


def write_output(path, ref):
    path.mkdir(parents=True, exist_ok=True)
    for table in ("behavior", "blocks", "bouts", "windows"):
        write_table(path / (table + ".csv"), table, ref[table])
    write_table(path / "spectrum.csv", "spectrum", pw.spectrum_rows(ref["frequencies"], ref["spectra"]))
    (path / "results.json").write_text(json.dumps(ref["results"], allow_nan=False))
    (path / "run_metadata.json").write_text(json.dumps(ref["metadata"], allow_nan=False))
    (path / "findings.md").write_text("Synthetic arithmetic fixture; no claim about the original source.\n")


@pytest.fixture
def tiny_reference():
    timestamps = np.arange(101, dtype=float) / 10
    positions = np.column_stack([8 * timestamps, np.zeros(len(timestamps))])
    n_samples = 12500
    behavior, blocks, bouts, _ = sc.behavior_tables(timestamps, positions, n_samples)
    support = sc.window_support(bouts, n_samples)
    time = np.arange(n_samples) / sc.FS
    volts = pw.Q * (100 * np.sin(2 * np.pi * 8 * time) + 17 * np.sin(2 * np.pi * 3 * time))
    windows, frequencies, spectra = sc.measure_windows(volts, support)
    ref = dict(behavior=behavior, blocks=blocks, bouts=bouts, windows=windows,
               frequencies=frequencies, spectra=spectra)
    ref["results"] = sc.summarize(**ref)
    ref["metadata"] = {"status": "ok", "task_id": "HIPPOTHETA-001", "pipeline_id": sc.PIPELINE_ID,
                       "source_manifest_sha256": "a" * 64, "method_contract_sha256": "b" * 64,
                       "source_sha256": {"fixture-only": "c" * 64},
                       "source_observed": {"n_lfp_samples": n_samples, "lfp_conversion": 1.9499999999999999e-7,
                                           "lfp_offset": 0.0, "lfp_column": 0, "lfp_rate_hz": 1250.0,
                                           "position_first_timestamp_s": 0.0},
                       "software_versions": {"synthetic_mechanics": "1"},
                       "method_contract": {"contract_id": sc.PIPELINE_ID, "synthetic_fixture_only": True}}
    return ref


@pytest.fixture
def tiny_output(tmp_path, tiny_reference):
    path = tmp_path / "output"
    write_output(path, tiny_reference)
    return path, tiny_reference


def test_complete_tiny_fixture(tiny_output):
    path, reference = tiny_output
    pw.validate_output_directory(path, reference)


@pytest.mark.parametrize("value,expected", [("1e3", 1000), ("0002", 2), ("-1.0", -1), (" 2 ", 2)])
def test_integer_notation(value, expected):
    assert pw.parse_int(value) == expected


@pytest.mark.parametrize("value", [True, "true", "1.1", "NaN", "Infinity", "", None])
def test_invalid_integer(value):
    with pytest.raises(AssertionError):
        pw.parse_int(value)


@pytest.mark.parametrize("value", [True, None, "NaN", "-Inf", "Infinity", "abc", {}])
def test_invalid_finite_numbers(value):
    with pytest.raises(AssertionError):
        pw.parse_number(value)


@pytest.mark.parametrize("value,expected", [(0, False), ("1e0", True), ("false", False), (True, True)])
def test_boolean_encodings(value, expected):
    assert pw.parse_bool(value) is expected


@pytest.mark.parametrize("text", ['{"x":NaN}', '{"x":Infinity}', '{"x":1,"x":2}'])
def test_nonfinite_duplicate_json(tmp_path, text):
    path = tmp_path / "bad.json"
    path.write_text(text)
    with pytest.raises(AssertionError):
        pw.read_json(path)


def test_complete_reorder_extra_columns_and_versions(tiny_output):
    output, reference = tiny_output
    for table in ("behavior", "blocks", "bouts", "windows"):
        write_table(output / (table + ".csv"), table, list(reversed(reference[table])), extra=True)
    metadata = copy.deepcopy(reference["metadata"])
    metadata["software_versions"] = {"independentImplementation": "0.1"}
    metadata["helpful_note"] = "Optional extra metadata is permitted."
    metadata["source_observed"]["lfp_conversion"] = 1.95e-7
    (output / "run_metadata.json").write_text(json.dumps(metadata))
    pw.validate_output_directory(output, reference)


@pytest.mark.parametrize("field", ["source_sha256", "method_contract", "source_observed"])
def test_closed_scientific_metadata(tiny_output, field):
    output, reference = tiny_output
    metadata = copy.deepcopy(reference["metadata"])
    metadata[field]["undeclared_source_or_recipe"] = 1
    (output / "run_metadata.json").write_text(json.dumps(metadata))
    with pytest.raises(AssertionError):
        pw.validate_output_directory(output, reference)


@pytest.mark.parametrize("filename", pw.FILES)
def test_missing_required_files(tiny_output, filename):
    output, reference = tiny_output
    (output / filename).unlink()
    with pytest.raises(AssertionError):
        pw.validate_output_directory(output, reference)


@pytest.mark.parametrize("field", ["x_cm", "timestamp_s", "speed_cm_s", "block_id", "position_valid"])
def test_wrong_behavior_receipt(tiny_output, field):
    output, reference = tiny_output
    rows = copy.deepcopy(reference["behavior"])
    k = next(i for i, row in enumerate(rows) if row[field] is not None)
    rows[k][field] = not rows[k][field] if isinstance(rows[k][field], bool) else rows[k][field] + 1
    write_table(output / "behavior.csv", "behavior", rows)
    with pytest.raises(AssertionError):
        pw.validate_output_directory(output, reference)


@pytest.mark.parametrize("table", list(pw.FIELDS))
def test_duplicate_table_keys(tiny_output, table):
    output, reference = tiny_output
    rows = (pw.spectrum_rows(reference["frequencies"], reference["spectra"])
            if table == "spectrum" else copy.deepcopy(reference[table]))
    write_table(output / (table + ".csv"), table, rows + [rows[0]])
    with pytest.raises(AssertionError, match="duplicate"):
        pw.validate_output_directory(output, reference)


@pytest.mark.parametrize("table", list(pw.FIELDS))
def test_dropped_source_rows(tiny_output, table):
    output, reference = tiny_output
    rows = (pw.spectrum_rows(reference["frequencies"], reference["spectra"])
            if table == "spectrum" else copy.deepcopy(reference[table]))
    write_table(output / (table + ".csv"), table, rows[1:])
    with pytest.raises(AssertionError, match="keys"):
        pw.validate_output_directory(output, reference)


@pytest.mark.parametrize("scale", [2.0, 0.5, 1.0 / (pw.Q ** 2)])
def test_scaled_spectrum_cannot_pass_correlation_shortcut(tiny_output, scale):
    output, reference = tiny_output
    rows = pw.spectrum_rows(reference["frequencies"], reference["spectra"] * scale)
    write_table(output / "spectrum.csv", "spectrum", rows)
    with pytest.raises(AssertionError):
        pw.validate_output_directory(output, reference)


def test_zero_source_power_is_valid_not_physiology_gate(tiny_output):
    output, ref = tiny_output
    ref["spectra"][:] = 0
    for row in ref["windows"]:
        row.update(mean_volts=0.0, mean_square_volts=0.0, theta_power_v2=0.0)
    ref["results"] = sc.summarize(ref["behavior"], ref["blocks"], ref["bouts"], ref["windows"], ref["frequencies"], ref["spectra"])
    write_output(output, ref)
    pw.validate_output_directory(output, ref)
    assert ref["results"]["conditions"]["locomotion"]["peak_tie_count"] == 17
    assert ref["results"]["peak_difference_hz"] == 0


def test_rounding_induced_peak_tie_keeps_source_category(tiny_output):
    output, ref = tiny_output
    ref["spectra"][:] = pw.Q ** 2
    # Original peak is6Hz. Rounding an extremely close6.25Hz value to the
    # same value must not create a new categorical tie in the graded result.
    ref["spectra"][:, 24] = 100 * pw.Q ** 2
    ref["spectra"][:, 25] = (100 - 1e-8) * pw.Q ** 2
    band = (ref["frequencies"] >= 6) & (ref["frequencies"] <= 10)
    theta = float(np.trapezoid(ref["spectra"][0, band], ref["frequencies"][band]))
    for row in ref["windows"]:
        row["theta_power_v2"] = theta
    ref["results"] = sc.summarize(ref["behavior"], ref["blocks"], ref["bouts"], ref["windows"], ref["frequencies"], ref["spectra"])
    write_output(output, ref)
    rounded = ref["spectra"].copy()
    rounded[:, 25] = rounded[:, 24]
    write_table(output / "spectrum.csv", "spectrum", pw.spectrum_rows(ref["frequencies"], rounded))
    pw.validate_output_directory(output, ref)


def test_no_gap_smoothing_or_partial_coordinate_erasure():
    t = np.arange(101) / 10
    xy = np.column_stack([8 * t, np.zeros(len(t))])
    xy[50, 1] = np.nan
    rows, blocks, bouts, _ = sc.behavior_tables(t, xy, 12500)
    assert len(blocks) == 2 and rows[50]["x_cm"] == 40 and rows[50]["y_cm"] is None
    assert rows[50]["block_id"] is None
    assert all(not r["smoothed_valid"] for r in rows[41:60])
    assert all(not (b["start_row"] < 50 < b["end_row"]) for b in bouts)


def test_timestamp_gap_splits_finite_blocks():
    t = np.arange(101) / 10
    t[50:] += 5
    xy = np.column_stack([8 * t, np.zeros(len(t))])
    rows, blocks, _, _ = sc.behavior_tables(t, xy, 20000)
    assert len(blocks) == 2 and rows[49]["block_id"] != rows[50]["block_id"]
    assert not rows[49]["selected_interval_to_next"]


@pytest.mark.parametrize("invalid", ["duplicate", "decrease", "nan", "inf"])
def test_invalid_time_fails_closed(invalid):
    t = np.arange(20) / 10
    t[10] = {"duplicate": t[9], "decrease": -1, "nan": np.nan, "inf": np.inf}[invalid]
    with pytest.raises(AssertionError):
        sc.behavior_tables(t, np.zeros((20, 2)), 20000)


def test_actual_nonuniform_derivative_of_linear_trajectory():
    t = np.cumsum(np.tile([0.04, 0.045], 150))
    xy = np.column_stack([9 * t, -4 * t])
    rows, _, _, _ = sc.behavior_tables(t, xy, 20000)
    speeds = [r["speed_cm_s"] for r in rows if r["speed_valid"]]
    assert speeds and np.allclose(speeds, math.hypot(9, 4), atol=3e-3)


@pytest.mark.parametrize("origin", [0.0, 6596.563233333333, 1e9])
def test_smoother_uses_actual_inclusive_time_distance(origin):
    t = origin + np.arange(161) / 30
    xy = np.column_stack([np.sin(np.arange(len(t))), np.cos(np.arange(len(t)))])
    rows, _, _, _ = sc.behavior_tables(t, xy, 10000, start=origin)
    for i, row in enumerate(rows):
        if row["smoothed_valid"]:
            use = np.abs(t - t[i]) <= 1
            weights = np.exp(-0.5 * ((t[use] - t[i]) / .25) ** 2)
            expected = np.sum(weights[:, None] * xy[use], axis=0) / np.sum(weights)
            assert np.array_equal([row["smoothed_x_cm"], row["smoothed_y_cm"]], expected)


def test_difference_allows_sum_of_two_peak_rounding_errors():
    pw.check_summary({"peak_difference_hz": .2 + 1.5e-6}, {"peak_difference_hz": .2})
    with pytest.raises(AssertionError):
        pw.check_summary({"peak_difference_hz": .2 + 3e-6}, {"peak_difference_hz": .2})


def test_short_bouts_do_not_join():
    bouts = [{"bout_id": 0, "start_sample": 0, "end_sample": 4000},
             {"bout_id": 1, "start_sample": 5000, "end_sample": 9000}]
    assert not any(r["condition"] == "locomotion" for r in sc.window_support(bouts, 15000))


def test_window_bounds_use_conservative_full_sample_support():
    t = np.arange(201) * 0.05001
    rows, _, bouts, _ = sc.behavior_tables(t, np.column_stack([10*t, t*0]), 15000)
    assert bouts
    for row in bouts:
        assert row["start_sample"] / sc.FS >= row["start_time_s"]
        assert row["end_sample"] / sc.FS <= row["stop_time_s"]


def test_periodogram_matches_independent_scipy_fixture():
    from scipy import signal
    x = np.random.default_rng(47).normal(size=sc.WINDOW)
    freq, power = sc.periodogram(x)
    ff, pp = signal.welch(x, fs=sc.FS, nperseg=sc.WINDOW, noverlap=0,
                          window="hann", detrend="constant", scaling="density", average="mean")
    assert np.array_equal(freq, ff)
    assert np.allclose(power, pp, atol=1e-17, rtol=1e-11)


def test_reference_old_pipeline_rejected_without_relabel(tmp_path):
    path = tmp_path / "obsolete.npz"
    np.savez(path, ref_stats=np.array(json.dumps({"estimator_contract": "contiguous-bout-welch-v1"})))
    with pytest.raises(AssertionError, match="obsolete"):
        pw.load_reference(path)


def test_empty_findings_rejected(tiny_output):
    output, reference = tiny_output
    (output / "findings.md").write_text(" \n")
    with pytest.raises(AssertionError, match="findings"):
        pw.validate_output_directory(output, reference)
