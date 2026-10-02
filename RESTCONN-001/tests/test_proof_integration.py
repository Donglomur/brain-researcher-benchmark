"""End-to-end manufactured files with independent expected primitives only."""
import copy
import csv
import json

import numpy as np
import pytest

import circular_contract as c
import proof_of_work as p
import source_reference as source
from fixture_support import emit, json_write, manufactured_basis, synthetic_sources


def read_npz(path):
    with np.load(path, allow_pickle=False) as archive: return {k: archive[k] for k in archive.files}


def test_genuine_synthetic_source_reconstruction_to_complete_output(tmp_path, monkeypatch):
    root, method, schema = synthetic_sources(tmp_path, monkeypatch)
    basis = source.reconstruct(root, method, schema)
    output = tmp_path / "output"; emit(output, basis)
    assert p.validate_output_directory(output, basis) == dict(status="accepted", inference_status="ok", n_frames=64, n_raw_maps=39, source_bound=True)


@pytest.mark.parametrize("choice", ["ordinary", "negative", "zero", "constant_x", "constant_y", "both_inactive"])
def test_complete_signed_zero_and_inactive_outcomes_valid(tmp_path, choice):
    x = np.array([-1., 0, 1, 0]); y = np.array([0., 1, 0, -1.]); active = [True, True]
    if choice == "ordinary": y = x
    if choice == "negative": y = -x
    if choice in ("constant_x", "both_inactive"): x = np.zeros(4); active[0] = False
    if choice in ("constant_y", "both_inactive"): y = np.zeros(4); active[1] = False
    basis = manufactured_basis(np.column_stack([x, y]), active)
    output = tmp_path / "output"; emit(output, basis)
    assert p.validate_output_directory(output, basis)["status"] == "accepted"


def test_coherent_serialization_permutations_and_harmless_metadata(tmp_path):
    basis = manufactured_basis(); output = tmp_path / "output"; emit(output, basis)
    path = output / "raw_map_coefficients.npz"; arrays = read_npz(path)
    arrays["participant_id"] = arrays["participant_id"].astype("S")
    arrays["frame_indices"] = arrays["frame_indices"][::-1].astype(float)
    arrays["map_ids"] = arrays["map_ids"][::-1].astype(float)
    arrays["map_labels"] = arrays["map_labels"][::-1].astype("S")
    arrays["raw_coefficients"] = arrays["raw_coefficients"][::-1, ::-1].astype(np.float32)
    arrays["optional_array"] = np.zeros((1,) * 7); np.savez(path, **arrays)
    lines = (output / "timeseries.csv").read_text().splitlines()
    (output / "timeseries.csv").write_text("\n".join([lines[0], *lines[:0:-1]]) + "\n")
    result = json.loads((output / "connectivity.json").read_text())
    for key in ("shifts", "null_r", "exceeds"): result["inference"][key].reverse()
    result["r"] = round(result["r"], 6)
    result["inference"]["null_r"] = [round(v, 6) for v in result["inference"]["null_r"]]
    json_write(output / "connectivity.json", result)
    metadata = json.loads((output / "run_metadata.json").read_text())
    metadata["source_files"].reverse(); metadata["source_observed"]["map_labels"].reverse()
    metadata["analysis_observed"]["target_support"].reverse()
    metadata["source_observed"]["bold_header"]["storage_dtype"] = "float32"
    metadata["source_observed"]["description"] = "Free explanatory text."
    metadata["software_versions"]["numpy"] = "alternative actual version"
    metadata["warnings"] = ["Retained warning, not an outcome gate."]
    json_write(output / "run_metadata.json", metadata)
    assert p.validate_output_directory(output, basis)["status"] == "accepted"


def test_own_accepted_near_tie_count_is_authority_not_hidden_bank(tmp_path):
    basis = manufactured_basis(); clean = basis["cleaned_series"].copy(); clean[0, 1] += 1e-8
    expected = c.circular_evidence(basis["cleaned_series"], basis["active"])
    actual = c.circular_evidence(clean, basis["active"])
    assert actual["inference"]["n_exceedances"] != expected["inference"]["n_exceedances"]
    output = tmp_path / "output"; emit(output, basis, cleaned=clean)
    assert p.validate_output_directory(output, basis)["status"] == "accepted"
    json_write(output / "connectivity.json", expected)
    with pytest.raises(ValueError): p.validate_output_directory(output, basis)


@pytest.mark.parametrize("mutation", ["raw", "subject", "dropped_map", "label", "duplicate_frame", "finite_series_wrong", "reversed_clock"])
def test_primitive_source_binding_is_live_before_metadata(tmp_path, mutation):
    basis = manufactured_basis(); output = tmp_path / "output"; emit(output, basis)
    path = output / "raw_map_coefficients.npz"; arrays = read_npz(path)
    if mutation == "raw": arrays["raw_coefficients"][0, 38] += .1
    if mutation == "subject": arrays["participant_id"] = np.array("10064")
    if mutation == "dropped_map": arrays["raw_coefficients"] = arrays["raw_coefficients"][:, :-1]
    if mutation == "label": arrays["map_labels"] = arrays["map_labels"][::-1]
    if mutation == "duplicate_frame": arrays["frame_indices"][0] = arrays["frame_indices"][1]
    if mutation in ("finite_series_wrong", "reversed_clock"):
        clean = basis["cleaned_series"].copy()
        if mutation == "finite_series_wrong": clean[0, 0] += .1
        else: clean = clean[::-1]
        with (output / "timeseries.csv").open("w", newline="") as handle:
            writer = csv.writer(handle); writer.writerow(["frame_index", *c.TARGETS]); writer.writerows([i, *row] for i, row in enumerate(clean))
        json_write(output / "connectivity.json", c.circular_evidence(clean, basis["active"]))
    np.savez(path, **arrays)
    with pytest.raises(ValueError): p.validate_output_directory(output, basis)


@pytest.mark.parametrize("mutation", ["observed_r", "null_value", "null_reverse", "count", "numerator", "denominator", "p", "significant", "missing_shift", "duplicate_shift", "bool_count", "string_p", "inactive_status"])
def test_all_circular_evidence_recomputed_not_trusted(tmp_path, mutation):
    basis = manufactured_basis(); output = tmp_path / "output"; emit(output, basis)
    report = json.loads((output / "connectivity.json").read_text()); inf = report["inference"]
    if mutation == "observed_r": report["r"] += .01
    if mutation == "null_value": inf["null_r"][0] += .01
    if mutation == "null_reverse":
        inf["null_r"].reverse(); assert inf["null_r"] != c.circular_evidence(basis["cleaned_series"], basis["active"])["inference"]["null_r"]
    if mutation == "count": inf["n_exceedances"] -= 1
    if mutation == "numerator": inf["numerator"] -= 1
    if mutation == "denominator": inf["denominator"] += 1
    if mutation == "p": report["p_value"] = inf["p_value"] = .2
    if mutation == "significant": report["significant"] = inf["significant"] = not report["significant"]
    if mutation == "missing_shift":
        for key in ("shifts", "null_r", "exceeds"): inf[key].pop()
    if mutation == "duplicate_shift": inf["shifts"][0] = inf["shifts"][1]
    if mutation == "bool_count": inf["n_exceedances"] = True
    if mutation == "string_p": report["p_value"] = str(report["p_value"])
    if mutation == "inactive_status": report["status"] = "inactive_target"
    json_write(output / "connectivity.json", report)
    with pytest.raises(ValueError): p.validate_output_directory(output, basis)


@pytest.mark.parametrize("mutation", ["pin", "sourcefile", "missing_source", "extra_source", "frame", "confound", "dtype", "affine", "clock", "active", "rank", "norm", "negative_norm", "nonfinite_extra", "bool_integer", "software_missing", "warnings_wrong"])
def test_source_metadata_cannot_be_fabricated(tmp_path, mutation):
    basis = manufactured_basis(); output = tmp_path / "output"; emit(output, basis)
    report = json.loads((output / "run_metadata.json").read_text()); obs = report["source_observed"]; analysis = report["analysis_observed"]
    if mutation == "pin": report["method_sha256"] = "0" * 64
    if mutation == "sourcefile": report["source_files"][0]["sha256"] = "0" * 64
    if mutation == "missing_source": report["source_files"] = []
    if mutation == "extra_source": report["source_files"].append({**report["source_files"][0], "path": "extra"})
    if mutation == "frame": obs["frame_count"] += 1
    if mutation == "confound": obs["selected_confound_columns"].reverse()
    if mutation == "dtype": obs["bold_header"]["storage_dtype"] = "float64"
    if mutation == "affine": obs["bold_header"]["selected_affine"][0][3] = .1
    if mutation == "clock": obs["operational_TR_s"] = 1.
    if mutation == "active": analysis["target_support"][0]["active"] = False
    if mutation == "rank": analysis["map_rank"] -= 1
    if mutation == "norm": analysis["target_support"][0]["residual_centered_l2"] *= 2
    if mutation == "negative_norm": analysis["target_support"][0]["activity_threshold"] = -1e-12
    if mutation == "bool_integer": obs["map_labels"][0]["map_id"] = False
    if mutation == "software_missing": del report["software_versions"]["scipy"]
    if mutation == "warnings_wrong": report["warnings"] = {}
    if mutation == "nonfinite_extra":
        (output / "run_metadata.json").write_text(json.dumps(report)[:-1] + ',"extra":{"x":1e999}}')
    else: json_write(output / "run_metadata.json", report)
    with pytest.raises(ValueError): p.validate_output_directory(output, basis)


def test_inactive_jitter_cannot_manufacture_inference(tmp_path):
    basis = manufactured_basis(np.column_stack([np.zeros(5), [1, 0, -1, 0, 0]]), [False, True])
    clean = basis["cleaned_series"].copy(); clean[:, 0] = np.arange(5)*1e-9
    output = tmp_path / "output"; emit(output, basis, cleaned=clean)
    assert p.validate_output_directory(output, basis)["inference_status"] == "inactive_target"
    json_write(output / "connectivity.json", c.circular_evidence(clean, [True, True]))
    with pytest.raises(ValueError): p.validate_output_directory(output, basis)


def test_complete_outcomes_do_not_override_late_failure(tmp_path):
    basis = manufactured_basis(); output = tmp_path / "output"; emit(output, basis)
    (output / "failure_report.json").symlink_to(output / "missing_failure_payload")
    with pytest.raises(ValueError, match="authoritative"): p.validate_output_directory(output, basis)
