"""Genuine original-source positives and coherent output mutations.

These tests are skipped only when a parent-run artifact was not supplied. They
never fit or read the original signal, nor mutate the retained genuine outputs.
"""
import copy
import csv
import json
import os
from pathlib import Path
import shutil
import sys

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tests"))
import proof_of_work as pw
import state_contract as sc
from test_contract import write_table


@pytest.fixture(scope="module")
def reference():
    if not os.environ.get("REPAIR_ORACLE_OUTPUT"):
        pytest.skip("requires parent-run original-source oracle output")
    return pw.load_reference(HERE.parent / "tests" / "reference.npz")


@pytest.fixture
def submitted(tmp_path, reference):
    source = Path(os.environ["REPAIR_ORACLE_OUTPUT"])
    assert source.is_dir(), "configured genuine output is absent"
    output = tmp_path / "submitted"
    output.mkdir()
    for filename in pw.FILES:
        shutil.copy2(source / filename, output / filename)
    return output, reference


def rows(output, table):
    parsed = pw.read_table(output / (table + ".csv"), table)
    return [parsed[key] for key in sorted(parsed)]


def save_result(output, data):
    (output / "results.json").write_text(json.dumps(data, allow_nan=False))


def reject(output, reference):
    with pytest.raises(AssertionError):
        pw.validate_output_directory(output, reference)


def test_genuine_original_oracle_accepts(submitted):
    pw.validate_output_directory(*submitted)


def test_genuine_independent_complete_implementation(reference):
    path = os.environ.get("REPAIR_INDEPENDENT_OUTPUT")
    if not path:
        pytest.skip("requires parent-run complete independent source output")
    pw.validate_output_directory(path, reference)


def test_public_contract_is_exactly_bank_contract(reference):
    path = HERE.parent / "environment" / "method_contract.json"
    pw.static_match(pw.read_json(path), reference["metadata"]["method_contract"], exact_keys=True)


def test_reordered_tables_extra_columns_and_finite_notation(submitted):
    output, reference = submitted
    for table in pw.FIELDS:
        data = rows(output, table)
        for row in data:
            for key, value in list(row.items()):
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    token = format(value, ".17e")
                    assert float(token) == value, "fixture must preserve source numbers"
                    row[key] = token
        write_table(output / (table + ".csv"), table, list(reversed(data)), extra=True)
    pw.validate_output_directory(output, reference)


def test_honest_alternate_versions_and_minimal_public_metadata(submitted):
    output, reference = submitted
    metadata = copy.deepcopy(reference["metadata"])
    metadata["software_versions"] = {"independent_periodogram": "1.0"}
    metadata["source_observed"]["lfp_conversion"] = 1.95e-7
    (output / "run_metadata.json").write_text(json.dumps(metadata))
    (output / "findings.md").write_text("Measurements are reported with the source-clock and electrode-location limitations.\n")
    pw.validate_output_directory(output, reference)


def test_meaningful_decimal_rounding(submitted):
    output, reference = submitted
    for table in ("behavior", "windows", "spectrum"):
        data = rows(output, table)
        for row in data:
            for field, value in list(row.items()):
                if isinstance(value, float) and field != "frequency_hz":
                    row[field] = format(value, ".12g")
        write_table(output / (table + ".csv"), table, data)
    pw.validate_output_directory(output, reference)


@pytest.mark.parametrize("table", list(pw.FIELDS))
@pytest.mark.parametrize("mutation", ["drop", "duplicate"])
def test_complete_source_table_membership(submitted, table, mutation):
    output, reference = submitted
    data = rows(output, table)
    assert data
    data = data[1:] if mutation == "drop" else data + [data[0]]
    write_table(output / (table + ".csv"), table, data)
    reject(output, reference)


@pytest.mark.parametrize("scale", [2.0, 0.5, 1.0 / (pw.Q ** 2)])
def test_coherent_rank_preserving_power_scaling(submitted, scale):
    output, reference = submitted
    data = rows(output, "spectrum")
    for row in data:
        row["power_v2_per_hz"] *= scale
    write_table(output / "spectrum.csv", "spectrum", data)
    window = rows(output, "windows")
    for row in window:
        row["theta_power_v2"] *= scale
        row["mean_square_volts"] *= scale
        row["mean_volts"] *= np.sqrt(scale)
    write_table(output / "windows.csv", "windows", window)
    result = pw.read_json(output / "results.json")
    for condition in sc.CONDITIONS:
        result["conditions"][condition]["theta_power_v2"] *= scale
    save_result(output, result)
    reject(output, reference)


@pytest.mark.parametrize("field", ["n_behavior_rows", "n_behavior_blocks", "n_retained_bouts", "locomotion_used_support_s", "peak_difference_hz"])
def test_fabricated_headline_counts_or_contrast(submitted, field):
    output, reference = submitted
    result = pw.read_json(output / "results.json")
    result[field] += 1
    save_result(output, result)
    reject(output, reference)


def test_fabricated_whole_peak_and_coherent_difference(submitted):
    output, reference = submitted
    result = pw.read_json(output / "results.json")
    old = result["conditions"]["whole_session"]["theta_peak_frequency_hz"]
    result["conditions"]["whole_session"]["theta_peak_frequency_hz"] = 7.0 if abs(old-7) > .1 else 8.0
    result["peak_difference_hz"] = (result["conditions"]["locomotion"]["theta_peak_frequency_hz"]
                                    - result["conditions"]["whole_session"]["theta_peak_frequency_hz"])
    save_result(output, result)
    reject(output, reference)


@pytest.mark.parametrize("mutation", ["missing", "source", "calendar", "column", "extra_recipe", "empty_versions"])
def test_metadata_and_mapping_not_optional(submitted, mutation):
    output, reference = submitted
    path = output / "run_metadata.json"
    if mutation == "missing":
        path.unlink()
    else:
        metadata = pw.read_json(path)
        if mutation == "source":
            first = next(iter(metadata["source_sha256"]))
            metadata["source_sha256"][first] = "0" * 64
        elif mutation == "calendar":
            metadata["source_observed"]["raw_calendar"] = metadata["source_observed"]["behavior_calendar"]
        elif mutation == "column":
            metadata["source_observed"]["lfp_column"] = 1
        elif mutation == "extra_recipe":
            metadata["method_contract"]["artifact_clipping"] = True
        else:
            metadata["software_versions"] = {}
        path.write_text(json.dumps(metadata))
    reject(output, reference)


def test_window_shift_crosses_declared_bout_support(submitted):
    output, reference = submitted
    data = rows(output, "windows")
    row = next(row for row in data if row["condition"] == "locomotion")
    row["start_sample"] += sc.HOP
    row["end_sample"] += sc.HOP
    write_table(output / "windows.csv", "windows", data)
    reject(output, reference)


def test_wrong_per_bout_window_weights(submitted):
    output, reference = submitted
    data = rows(output, "windows")
    # A coherent weighted-receipt forgery: each bout's window contribution is
    # rescaled by1/n_windows. It cannot masquerade as an equal-window result.
    counts = {row["bout_id"]: row["n_windows"] for row in reference["bouts"] if row["n_windows"]}
    assert any(value > 1 for value in counts.values()), "actual artifact lacks this specific unequal-weight control"
    altered = False
    for row in data:
        if row["condition"] == "locomotion" and counts[row["bout_id"]] > 1:
            row["theta_power_v2"] /= counts[row["bout_id"]]
            altered = True
    assert altered
    write_table(output / "windows.csv", "windows", data)
    reject(output, reference)


def test_behavior_source_row_swap_cannot_hide_under_same_distribution(submitted):
    output, reference = submitted
    data = rows(output, "behavior")
    indices = [i for i, row in enumerate(data) if row["x_cm"] is not None]
    first = indices[0]
    second = next(i for i in indices[1:] if abs(data[i]["x_cm"] - data[first]["x_cm"]) > .01)
    data[first]["x_cm"], data[second]["x_cm"] = data[second]["x_cm"], data[first]["x_cm"]
    write_table(output / "behavior.csv", "behavior", data)
    reject(output, reference)


@pytest.mark.parametrize("value", ["NaN", "Infinity", "not-a-number", ""])
def test_bad_spectral_rows_not_silently_dropped(submitted, value):
    output, reference = submitted
    data = rows(output, "spectrum")
    data[0]["power_v2_per_hz"] = value
    write_table(output / "spectrum.csv", "spectrum", data)
    reject(output, reference)


def test_sparse_frequency_interpolation_not_accepted(submitted):
    output, reference = submitted
    data = rows(output, "spectrum")
    write_table(output / "spectrum.csv", "spectrum", data[::4])
    reject(output, reference)


def test_missing_findings(submitted):
    output, reference = submitted
    (output / "findings.md").write_text("\n")
    reject(output, reference)
