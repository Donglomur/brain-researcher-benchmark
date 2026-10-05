"""Tiny in-memory parser/source/QC fixtures, not a measured SRTM reference bank."""
import copy
import csv
import json
import sys
from pathlib import Path
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "tests"))
from proof_of_work import (SCANS, TARGET, REFERENCE, MODEL, PIPELINE_ID, PARAMETERS, SOURCE_TAC_FIELDS,
    LOWER, UPPER, BOUND_ATOL, number, integer, bound_flags, read_json, match_contract,
    load_estimates, load_tac_fit)
from srtm_contract import (srtm_prediction, validate_frames, validate_estimates, paired_metrics,
                           validate_results, validate_metadata)


def mechanics_fixture():
    n = 5
    starts, ends = np.array([0., 10., 20., 60., 120.]), np.array([10., 20., 60., 120., 240.])
    midpoint = (starts+ends)/120.
    cr = np.array([0., .5, 2., 1., .2])
    params = np.array([[1., .1, 1.], [1.1, .2, 1.2], [.9, .15, 2.], [1., .12, 2.1]])
    target = np.array([.1, .8, 2.5, 1.5, .6])
    prediction = np.concatenate([srtm_prediction(midpoint, cr, p) for p in params])
    ref = {"subject": np.array([key[0] for key in SCANS]), "session": np.array([key[1] for key in SCANS]),
        "frame_scan": np.repeat(np.arange(4), n), "frame_index": np.tile(np.arange(n), 4),
        "frame_start_s": np.tile(starts, 4), "frame_end_s": np.tile(ends, 4), "mid_time_min": np.tile(midpoint, 4),
        "source_tacs": np.tile(np.column_stack((target, target, cr, cr)), (4, 1)),
        "target": np.tile(target, 4), "reference": np.tile(cr, 4), "params": params,
        "prediction": prediction, "residual": prediction-np.tile(target, 4), "reference_scale": np.full(4, 2.)}
    hashes = {"mechanics-only-not-real-tac.tsv": "a"*64}
    observations = [{"subject": s, "session": e, "n_frames": n, "start_s": 0., "end_s": 240., "duration_s": 240.} for s, e in SCANS]
    ref["stats"] = {"source_sha256": hashes, "metadata_contract": {"pipeline_id": PIPELINE_ID, "source_sha256": hashes},
                    "per_scan_observations": observations}
    frames = {field: ref[field].copy() for field in ("frame_start_s", "frame_end_s", "mid_time_min", "target", "reference", "residual")}
    frames["predicted_target"] = prediction.copy()
    for i, field in enumerate(SOURCE_TAC_FIELDS): frames[field] = ref["source_tacs"][:, i].copy()
    frame_rows = {(*SCANS[int(scan)], int(frame)): {field: float(values[i]) for field, values in frames.items()}
                  for i, (scan, frame) in enumerate(zip(ref["frame_scan"], ref["frame_index"]))}
    estimates = {}
    for index, key in enumerate(SCANS):
        residual = ref["residual"][ref["frame_scan"] == index]; sse = float(residual@residual)
        estimates[key] = {"target": TARGET, "reference_region": REFERENCE, "model": MODEL, "status": "ok",
            **dict(zip(PARAMETERS, params[index])), "k2prime": params[index, 1]/params[index, 0],
            "selected_start_index": 0, "optimizer_status": 1, "nfev": 10,
            "at_lower_bound": np.isclose(params[index], LOWER, atol=BOUND_ATOL, rtol=0),
            "at_upper_bound": np.isclose(params[index], UPPER, atol=BOUND_ATOL, rtol=0),
            "reference_scale": 2., "sse": sse, "rmse": np.sqrt(sse/n), "normalized_rmse": np.sqrt(sse/n)/2}
    return ref, frames, frame_rows, estimates


def write_rows(path, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


def estimate_csv_rows(estimates):
    return [{"subject": key[0], "session": key[1], **{name: json.dumps(value.tolist()) if isinstance(value, np.ndarray) else value
             for name, value in row.items()}} for key, row in estimates.items()]


def frame_csv_rows(frame_rows):
    return [{"subject": key[0], "session": key[1], "frame_index": key[2], **row} for key, row in frame_rows.items()]


@pytest.mark.parametrize("value", [True, False, "NaN", "inf", "-inf"])
def test_nonfinite_or_boolean_numeric_values_fail(value):
    with pytest.raises((AssertionError, ValueError)): number(value)


@pytest.mark.parametrize("value", [-1, .5, "1.1"])
def test_frame_and_diagnostic_ids_are_integral(value):
    with pytest.raises(AssertionError): integer(value)


def test_reasonable_integer_and_boolean_notation():
    assert integer("2.0") == integer("2e0") == 2
    np.testing.assert_array_equal(bound_flags('[true,0,"1"]'), [True, False, True])


@pytest.mark.parametrize("value", ['[]', '[true,true]', '[false,false,false,false]', '["maybe",true,false]'])
def test_bound_flag_shape_and_values(value):
    with pytest.raises(AssertionError): bound_flags(value)


@pytest.mark.parametrize("text", ['{"x":1,"x":2}', '{"x":NaN}', '[]'])
def test_strict_json(tmp_path, text):
    path = tmp_path / "data.json"; path.write_text(text)
    with pytest.raises((AssertionError, ValueError)): read_json(path)


def test_mechanics_source_model_and_metrics_are_consistent():
    ref, frames, rows, estimates = mechanics_fixture()
    validate_frames(rows, ref); validate_estimates(estimates, frames, ref)
    validate_results({"status": "ok", "pipeline_id": PIPELINE_ID, **paired_metrics(estimates)}, estimates)


def test_order_extra_columns_and_numeric_frame_notation(tmp_path):
    ref, frames, rows, estimates = mechanics_fixture()
    table = frame_csv_rows(rows)[::-1]
    for row in table: row["frame_index"] = f'{row["frame_index"]}.0'; row["description"] = "extra"
    path = tmp_path / "tac.csv"; write_rows(path, table)
    validate_frames(load_tac_fit(path), ref)
    table = estimate_csv_rows(estimates)[::-1]
    for row in table: row["description"] = "extra"
    path = tmp_path / "bp.csv"; write_rows(path, table)
    validate_estimates(load_estimates(path), frames, ref)


@pytest.mark.parametrize("kind", ["drop", "duplicate", "foreign_session", "nan_parameter", "wrong_flag_shape"])
def test_exact_estimate_parser(tmp_path, kind):
    _, _, _, estimates = mechanics_fixture(); rows = estimate_csv_rows(estimates)
    if kind == "drop": rows.pop()
    elif kind == "duplicate": rows.append(rows[0].copy())
    elif kind == "foreign_session": rows[0]["session"] = "ses-invented"
    elif kind == "nan_parameter": rows[0]["BP_ND"] = "NaN"
    else: rows[0]["at_lower_bound"] = "[]"
    path = tmp_path / "bp.csv"; write_rows(path, rows)
    with pytest.raises((AssertionError, ValueError)): load_estimates(path)


@pytest.mark.parametrize("kind", ["drop", "foreign_frame", "time_units", "target", "reference", "hemisphere"])
def test_frame_source_identity_cannot_be_relabelled(kind):
    ref, _, rows, _ = mechanics_fixture(); key = next(iter(rows))
    if kind == "drop": del rows[key]
    elif kind == "foreign_frame": rows[(*key[:2], 999)] = rows.pop(key)
    elif kind == "time_units": rows[key]["mid_time_min"] *= 60
    elif kind == "target": rows[key]["target"] += 1
    elif kind == "reference": rows[key]["reference"] += 1
    else: rows[key]["left_putamen"] += 1
    with pytest.raises(AssertionError): validate_frames(rows, ref)


@pytest.mark.parametrize("field,value", [("model", "Logan"), ("reference_region", "whole_cerebellum"),
    ("optimizer_status", 0), ("nfev", 0), ("selected_start_index", 3), ("R1", 0),
    ("BP_ND", 8), ("k2prime", 3), ("reference_scale", 1), ("sse", -1), ("rmse", 99), ("normalized_rmse", 99)])
def test_parameter_model_qc_and_residual_metrics(field, value):
    ref, frames, _, estimates = mechanics_fixture(); estimates[SCANS[0]][field] = value
    with pytest.raises(AssertionError): validate_estimates(estimates, frames, ref)


def test_optimizer_iterations_are_semantic_not_exact_reference_gate():
    ref, frames, _, estimates = mechanics_fixture()
    for row in estimates.values(): row.update(selected_start_index=2, optimizer_status=3, nfev=19)
    validate_estimates(estimates, frames, ref)


def test_bound_flags_are_recomputed_not_arbitrary_qc_labels():
    ref, frames, _, estimates = mechanics_fixture(); estimates[SCANS[0]]["at_lower_bound"][0] = True
    with pytest.raises(AssertionError, match="lower-bound flags"): validate_estimates(estimates, frames, ref)


def test_wrong_signed_residual_is_not_accepted_as_small_error():
    ref, frames, _, estimates = mechanics_fixture(); frames["residual"] *= -1
    with pytest.raises(AssertionError, match="signed residual"): validate_estimates(estimates, frames, ref)


def test_public_metadata_needs_no_private_candidate_receipt():
    ref, _, _, _ = mechanics_fixture()
    metadata = {**ref["stats"]["metadata_contract"], "status": "ok",
                "per_scan_observations": ref["stats"]["per_scan_observations"][::-1], "extra": "description"}
    validate_metadata(metadata, ref)
    metadata["per_scan_observations"][0]["n_frames"] += 1
    with pytest.raises(AssertionError, match="frame count"): validate_metadata(metadata, ref)


def test_source_numeric_tolerance_does_not_admit_negative_zero_frame_tac():
    ref, _, rows, _ = mechanics_fixture()
    rows[(*SCANS[0], 0)]["left_cerebellum_cortex"] = -5e-11
    with pytest.raises(AssertionError, match="negative required regional TAC"):
        validate_frames(rows, ref)


def test_source_numeric_tolerance_does_not_admit_negative_time_origin():
    ref, _, rows, _ = mechanics_fixture()
    rows[(*SCANS[0], 0)]["frame_start_s"] = -5e-11
    with pytest.raises(AssertionError, match="negative frame start"):
        validate_frames(rows, ref)
