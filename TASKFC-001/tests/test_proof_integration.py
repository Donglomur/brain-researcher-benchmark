"""Ten-person manufactured validation; no original sources or output artifacts."""
import copy
import csv
import json

import numpy as np
import pytest

import artifact_reader as a
import proof_of_work as p
import sensitivity_math as m
from verifier_fixture_support import emit, manufactured_reference, write_csv, write_json


@pytest.fixture(scope="module")
def reference():
    return manufactured_reference()


@pytest.fixture
def output(tmp_path, reference):
    return emit(tmp_path/"output", reference)


def npz(path):
    with np.load(path, allow_pickle=False) as archive:
        return {key: archive[key].copy() for key in archive.files}


def rows(path):
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def replay(output, reference):
    own = p.canonical_primitives(npz(output/"model_arrays.npz"), reference)
    result = m.derive_cohort(own, {pid: part["active"] for pid, part in reference["participants"].items()}, p.PARTICIPANTS)
    write_csv(output/"connectivity.csv", list(result["per_subject"].values()))
    write_json(output/"connectivity_summary.json", dict(schema_version="taskfc-results-v2", status="complete", **result["summary"]))


@pytest.mark.parametrize("mode", ["baseline", "coherent_axes", "metadata_records", "scalar_rounding",
                                  "float32_primitives", "source_close_own_replay", "extras", "design_receipt_only"])
def test_legitimate_manufactured_equivalents(output, reference, mode):
    if mode == "coherent_axes":
        data = npz(output/"model_arrays.npz")
        rng = np.random.default_rng(5)
        s, f, c = rng.permutation(10), rng.permutation(len(data["frame_time_s"])), rng.permutation(len(data["design_column_ids"]))
        data["participant_ids"] = data["participant_ids"][s].astype("S")
        data["design_included"] = data["design_included"][s, ::-1][:, :, c]
        for key in ("frame_participant_id", "source_frame_index", "frame_time_s", "roi_signals", "design_values", "residuals"):
            data[key] = data[key][f]
        data["source_frame_index"] = data["source_frame_index"].astype(float)
        data["roi_ids"] = data["roi_ids"][::-1]
        data["model_ids"] = data["model_ids"][::-1]
        data["roi_signals"] = data["roi_signals"][:, ::-1]
        data["residuals"] = data["residuals"][:, ::-1, ::-1]
        data["design_column_ids"] = data["design_column_ids"][c]
        data["design_values"] = data["design_values"][:, c]
        np.savez(output/"model_arrays.npz", **data)
        for name in ("cohort.csv", "events.csv", "connectivity.csv"):
            values = rows(output/name)
            write_csv(output/name, [{key: row[key] for key in reversed(list(row))} for row in values[::-1]])
    elif mode == "metadata_records":
        metadata = json.loads((output/"run_metadata.json").read_text())
        metadata["source_files"].reverse()
        metadata["analysis_observed"].reverse()
        for person in metadata["analysis_observed"]:
            person["models"].reverse()
            for model in person["models"]:
                model["roi_support"].reverse(); model["column_ids"].reverse()
        metadata["source_observed"]["headers"]["sub-01"]["storage_dtype"] = "float32"
        write_json(output/"run_metadata.json", metadata)
    elif mode == "scalar_rounding":
        values = rows(output/"connectivity.csv")
        for row in values:
            for key in ("connectivity", "background_connectivity", "raw_fisher_z", "background_fisher_z", "raw_minus_background_z"):
                if row[key] != "": row[key] = f"{float(row[key]):.6f}"
        write_csv(output/"connectivity.csv", values)
        def rounded(value):
            if type(value) is float: return round(value, 6)
            if isinstance(value, dict): return {k: rounded(v) for k, v in value.items()}
            if isinstance(value, list): return [rounded(v) for v in value]
            return value
        write_json(output/"connectivity_summary.json", rounded(json.loads((output/"connectivity_summary.json").read_text())))
    elif mode in ("float32_primitives", "source_close_own_replay", "design_receipt_only"):
        data = npz(output/"model_arrays.npz")
        if mode == "float32_primitives":
            data["roi_signals"] = data["roi_signals"].astype(np.float32)
            data["residuals"] = data["residuals"].astype(np.float32)
        elif mode == "source_close_own_replay": data["residuals"][0, 0, 0] += 1e-8
        else: data["design_values"][0, 0] += 1e-10
        np.savez(output/"model_arrays.npz", **data)
        if mode != "design_receipt_only": replay(output, reference)
    elif mode == "extras":
        data = npz(output/"model_arrays.npz"); data["optional_array"] = np.zeros((1,)*9)
        np.savez(output/"model_arrays.npz", **data)
        metadata = json.loads((output/"run_metadata.json").read_text())
        metadata["source_observed"]["description"] = "Unscored descriptive addition."
        metadata["analysis_observed"][0]["models"][0]["optional_note"] = 1.
        write_json(output/"run_metadata.json", metadata)
        (output/"findings.md").write_text("No prescribed scientific vocabulary or direction.\n")
    assert p.validate_output_directory(output, reference)["status"] == "accepted"


@pytest.mark.parametrize("mode", ["raw_changed", "design_changed", "residual_changed", "membership_changed",
                                  "digit_subject", "duplicate_frame", "wrong_roi", "wrong_model",
                                  "missing_array", "broadcast_shape", "integer_membership", "nonfinite",
                                  "wrong_clock", "missing_design_column"])
def test_primitive_falsifiers(output, reference, mode):
    data = npz(output/"model_arrays.npz")
    if mode == "raw_changed": data["roi_signals"][0, 0] += .1
    if mode == "design_changed": data["design_values"][0, 0] += .01
    if mode == "residual_changed": data["residuals"][0, 0, 0] += 1.
    if mode == "membership_changed": data["design_included"][0, 0, -1] = ~data["design_included"][0, 0, -1]
    if mode == "digit_subject": data["participant_ids"][0] = "1"
    if mode == "duplicate_frame": data["source_frame_index"][1] = data["source_frame_index"][0]
    if mode == "wrong_roi": data["roi_ids"][0] = "another_ROI"
    if mode == "wrong_model": data["model_ids"][0] = "another_model"
    if mode == "missing_array": del data["roi_signals"]
    if mode == "broadcast_shape": data["residuals"] = data["residuals"][:, :1, :]
    if mode == "integer_membership": data["design_included"] = data["design_included"].astype(int)
    if mode == "nonfinite": data["residuals"][0, 0, 0] = np.nan
    if mode == "wrong_clock": data["frame_time_s"] += .75
    if mode == "missing_design_column": data["design_column_ids"] = data["design_column_ids"][:-1]
    np.savez(output/"model_arrays.npz", **data)
    with pytest.raises(ValueError): p.validate_output_directory(output, reference)


@pytest.mark.parametrize("mode", ["event_clock", "event_token", "duplicate_event", "event_missing", "cohort_alias", "cohort_duplicate", "cohort_support"])
def test_source_ledger_falsifiers(output, reference, mode):
    name = "events.csv" if mode.startswith("event") or mode == "duplicate_event" else "cohort.csv"
    data = rows(output/name)
    if mode == "event_clock": data[0]["onset_s"] = str(float(data[0]["onset_s"])+1.)
    if mode == "event_token": data[0]["onset_token"] = "fabricated"
    if mode == "duplicate_event": data.append(data[0].copy()); data[-1]["source_event_index"] = "0e0"
    if mode == "event_missing": data.pop()
    if mode == "cohort_alias": data[0]["subject"] = "1"
    if mode == "cohort_duplicate": data.append(data[0].copy())
    if mode == "cohort_support": data[0]["left_n_voxels"] = "999"
    write_csv(output/name, data)
    with pytest.raises(ValueError): p.validate_output_directory(output, reference)


@pytest.mark.parametrize("mode", ["source_pin", "method_pin", "schema_pin", "source_missing", "source_changed",
                                  "rank", "rank_bool", "active", "negative_norm", "wrong_source_columns",
                                  "numeric_software", "missing_subject_header", "duplicate_model", "wrong_diagnostic_columns"])
def test_metadata_falsifiers(output, reference, mode):
    data = json.loads((output/"run_metadata.json").read_text())
    if mode == "source_pin": data["source_manifest_sha256"] = "f"*64
    if mode == "method_pin": data["method_sha256"] = "f"*64
    if mode == "schema_pin": data["output_schema_sha256"] = "f"*64
    if mode == "source_missing": data["source_files"].pop()
    if mode == "source_changed": data["source_files"][0]["sha256"] = "f"*64
    model = data["analysis_observed"][0]["models"][0]
    if mode == "rank": model["rank"] += 1
    if mode == "rank_bool": model["rank"] = True
    if mode == "active": model["roi_support"][0]["active"] = not model["roi_support"][0]["active"]
    if mode == "negative_norm": model["roi_support"][0]["activity_threshold"] = -1e-14
    if mode == "wrong_source_columns": data["source_observed"]["confound_column_names"]["sub-01"].reverse()
    if mode == "numeric_software": data["software_versions"]["manufactured"] = 123
    if mode == "missing_subject_header": del data["source_observed"]["headers"]["sub-01"]
    if mode == "duplicate_model": data["analysis_observed"][0]["models"].append(copy.deepcopy(model))
    if mode == "wrong_diagnostic_columns": model["column_ids"][0] = "fake"
    write_json(output/"run_metadata.json", data)
    with pytest.raises(ValueError): p.validate_output_directory(output, reference)


@pytest.mark.parametrize("mode", ["wrong_person_r", "wrong_person_z", "wrong_person_delta", "wrong_person_null",
                                  "wrong_group", "wrong_paired_sign", "wrong_ci", "wrong_p", "numeric_boolean"])
def test_derived_falsifiers(output, reference, mode):
    if mode.startswith("wrong_person"):
        data = rows(output/"connectivity.csv")
        key = {"wrong_person_r": "connectivity", "wrong_person_z": "raw_fisher_z",
               "wrong_person_delta": "raw_minus_background_z", "wrong_person_null": "connectivity"}[mode]
        data[0][key] = "" if mode == "wrong_person_null" else str(float(data[0][key])+.25)
        write_csv(output/"connectivity.csv", data)
    else:
        data = json.loads((output/"connectivity_summary.json").read_text())
        if mode == "wrong_group": data["raw"]["fisher_mean_r"] += .25
        if mode == "wrong_paired_sign": data["paired_z_sensitivity"]["mean_raw_minus_background_z"] += .25
        if mode == "wrong_ci": data["paired_z_sensitivity"]["ci95"].reverse()
        if mode == "wrong_p": data["paired_z_sensitivity"]["p"] = 2.
        if mode == "numeric_boolean": data["n_subjects"] = True
        write_json(output/"connectivity_summary.json", data)
    with pytest.raises(ValueError): p.validate_output_directory(output, reference)


@pytest.mark.parametrize("mode", ["one_inactive", "all_inactive", "zero_variance"])
def test_legitimate_undefined_or_equal_person_outputs(tmp_path, mode):
    reference = manufactured_reference(mode)
    output = emit(tmp_path/"output", reference)
    assert p.validate_output_directory(output, reference)["status"] == "accepted"
    summary = json.loads((output/"connectivity_summary.json").read_text())
    status = summary["paired_z_sensitivity"]["status"]
    assert status == ("zero_variance" if mode == "zero_variance" else "incomplete_support")


def test_inactive_pair_numeric_fabrication_rejected(tmp_path):
    reference = manufactured_reference("one_inactive")
    output = emit(tmp_path/"output", reference)
    data = rows(output/"connectivity.csv")
    assert data[0]["connectivity"] == ""
    data[0]["connectivity"] = "0"
    write_csv(output/"connectivity.csv", data)
    with pytest.raises(ValueError): p.validate_output_directory(output, reference)


def test_available_case_group_fabrication_rejected(tmp_path):
    reference = manufactured_reference("one_inactive")
    output = emit(tmp_path/"output", reference)
    data = json.loads((output/"connectivity_summary.json").read_text())
    assert data["raw"]["mean_z"] is None
    data["raw"].update(status="ok", mean_z=0., fisher_mean_r=0.)
    write_json(output/"connectivity_summary.json", data)
    with pytest.raises(ValueError): p.validate_output_directory(output, reference)


def test_zero_variance_test_statistic_must_remain_null(tmp_path):
    reference = manufactured_reference("zero_variance")
    output = emit(tmp_path/"output", reference)
    data = json.loads((output/"connectivity_summary.json").read_text())
    assert data["paired_z_sensitivity"]["t"] is None
    data["paired_z_sensitivity"].update(t=0., p=1.)
    write_json(output/"connectivity_summary.json", data)
    with pytest.raises(ValueError): p.validate_output_directory(output, reference)


def test_authoritative_late_failure_after_valid_success(output, reference):
    assert p.validate_output_directory(output, reference)["status"] == "accepted"
    (output/"failure_report.json").symlink_to(output/"absent")
    with pytest.raises(ValueError, match="authoritative"): p.validate_output_directory(output, reference)


def test_no_partial_basis_can_use_production_validator(output, reference):
    partial = copy.deepcopy(reference)
    partial["participant_ids"] = ["sub-01"]
    with pytest.raises(ValueError, match="ten-person"): p.validate_output_directory(output, partial)
