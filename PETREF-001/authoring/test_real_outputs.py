"""Genuine-source output acceptance and coherent forgeries, without any model fitting."""
import csv
import json
import os
import shutil
import sys
from pathlib import Path
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "tests"))
from proof_of_work import (SCANS, PARAMETERS, SOURCE_TAC_FIELDS, LOWER, UPPER, BOUND_ATOL, PARAM_ATOL, PARAM_RTOL,
                           PIPELINE_ID, load_reference, read_json)
from srtm_contract import srtm_prediction, validate_output_directory

FILES = ("bp_estimates.csv", "tac_fit.csv", "pet_results.json", "run_metadata.json", "findings.md")


@pytest.fixture(scope="module")
def genuine():
    value = os.environ.get("REPAIR_ORACLE_OUTPUT")
    if not value: pytest.skip("requires genuine source-run REPAIR_ORACLE_OUTPUT; no invented bank")
    output, reference = Path(value), load_reference()
    assert [int(np.sum(reference["frame_scan"] == i)) for i in range(4)] == [32, 36, 36, 36]
    validate_output_directory(output, reference)
    return output, reference


@pytest.fixture
def output_copy(genuine, tmp_path):
    source, reference = genuine
    for name in FILES: shutil.copyfile(source / name, tmp_path / name)
    return tmp_path, reference


def read_rows(path):
    with path.open(newline="") as stream: return list(csv.DictReader(stream))


def write_rows(path, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+"\n")


def key(row): return row["subject"], row["session"]


def refresh_results(output, estimates):
    """Independent elementary paired arithmetic, not copied from reference stats."""
    mapping = {key(row): float(row["BP_ND"]) for row in estimates}
    pairs = []
    for subject in ("sub-01", "sub-02"):
        b, r = mapping[(subject, "ses-baseline")], mapping[(subject, "ses-rescan")]
        mean, difference = (b+r)/2, abs(b-r)
        pairs.append(dict(subject=subject, baseline_BP_ND=b, rescan_BP_ND=r, absolute_difference=difference,
            pair_mean=mean, test_retest_pct=100*difference/mean if mean > 0 else None,
            status="ok" if mean > 0 else "undefined_nonpositive_mean"))
    defined = sum(row["test_retest_pct"] is not None for row in pairs)
    result = dict(status="ok", pipeline_id=PIPELINE_ID, n_scans=4, n_subjects=2,
        putamen_BP_ND_mean=float(np.mean(list(mapping.values()))), per_subject=pairs, n_defined_pairs=defined,
        test_retest_pct=float(np.mean([row["test_retest_pct"] for row in pairs])) if defined == 2 else None)
    write_json(output / "pet_results.json", result)


def reconstruct_all(output, estimates=None, frames=None):
    """Make a forged submission internally consistent; does not optimize parameters."""
    if estimates is None: estimates = read_rows(output / "bp_estimates.csv")
    if frames is None: frames = read_rows(output / "tac_fit.csv")
    mapping = {key(row): row for row in estimates}
    for scan in SCANS:
        row = mapping[scan]
        group = sorted((r for r in frames if key(r) == scan), key=lambda r: int(r["frame_index"]))
        t = np.asarray([float(r["mid_time_min"]) for r in group])
        cr = np.asarray([float(r["reference"]) for r in group])
        target = np.asarray([float(r["target"]) for r in group])
        params = np.array([float(row[field]) for field in PARAMETERS]); scale = float(cr.max())
        prediction = srtm_prediction(t, cr, params); residual = prediction-target
        for item, predicted, error in zip(group, prediction, residual):
            item["predicted_target"], item["residual"] = float(predicted), float(error)
        row.update(k2prime=float(params[1]/params[0]), reference_scale=scale,
            at_lower_bound=json.dumps(np.isclose(params, LOWER, atol=BOUND_ATOL, rtol=0).tolist()),
            at_upper_bound=json.dumps(np.isclose(params, UPPER, atol=BOUND_ATOL, rtol=0).tolist()),
            sse=float(residual@residual), rmse=float(np.sqrt(np.mean(residual**2))),
            normalized_rmse=float(np.sqrt(np.mean(residual**2))/scale))
    write_rows(output / "bp_estimates.csv", estimates); write_rows(output / "tac_fit.csv", frames)
    refresh_results(output, estimates)


def test_genuine_source_outputs_pass(genuine): validate_output_directory(*genuine)


def test_public_template_matches_reference_contract(genuine):
    _, reference = genuine
    assert read_json(Path(__file__).parents[1] / "environment/method_contract.json") == reference["stats"]["metadata_contract"]


def test_minimal_public_template_metadata_needs_no_private_diagnostics(output_copy):
    output, reference = output_copy
    metadata = read_json(Path(__file__).parents[1] / "environment/method_contract.json")
    metadata.update(status="ok", per_scan_observations=reference["stats"]["per_scan_observations"])
    write_json(output / "run_metadata.json", metadata)
    (output / "analysis_arrays.npz").write_text("optional authoring receipt is not graded")
    validate_output_directory(output, reference)


def test_row_column_order_extra_columns_and_free_prose_are_allowed(output_copy):
    output, reference = output_copy
    for name in ("bp_estimates.csv", "tac_fit.csv"):
        rows = read_rows(output / name)[::-1]
        for row in rows:
            row["description"] = "extra"
            for field in ("frame_index", "nfev", "optimizer_status", "selected_start_index"):
                if field in row: row[field] = f"{int(row[field])}.0"
        write_rows(output / name, [dict(reversed(list(row.items()))) for row in rows])
    result = read_json(output / "pet_results.json"); result["per_subject"].reverse(); write_json(output / "pet_results.json", result)
    metadata = read_json(output / "run_metadata.json"); metadata["per_scan_observations"].reverse(); write_json(output / "run_metadata.json", metadata)
    (output / "findings.md").write_text("这是公开数值配方下的两人重复扫描描述，不能证明人群层面的重测信度。\n")
    validate_output_directory(output, reference)


def test_independent_reconstruction_and_metrics_pass(output_copy):
    output, reference = output_copy; reconstruct_all(output)
    validate_output_directory(output, reference)


def test_genuine_independent_dogbox_estimates_are_accepted(output_copy):
    value = os.environ.get("REPAIR_INDEPENDENT_REPORT")
    if not value:
        pytest.skip("requires an executed independent dogbox report; this test performs no fitting")
    output, reference = output_copy
    report = read_json(Path(value))
    assert report["status"] == "passed" and report["source_sha256"] == reference["stats"]["source_sha256"]
    assert len(report["scans"]) == 4 and {key(row) for row in report["scans"]} == set(SCANS)
    alternative = {key(row): row["alternate_dogbox"] for row in report["scans"]}
    estimates = read_rows(output / "bp_estimates.csv")
    for row in estimates:
        candidate = alternative[key(row)]
        assert candidate["success"] is True and len(candidate["params"]) == 3
        row.update(zip(PARAMETERS, candidate["params"]))
        # The independently executed check used the first prespecified start.
        row.update(selected_start_index=0, optimizer_status=candidate["status"], nfev=candidate["nfev"])
    reconstruct_all(output, estimates=estimates)
    metadata = read_json(output / "run_metadata.json")
    metadata["implementation_diagnostic"] = {"optimizer": "dogbox", "forward_model": "independent_matrix_exponential",
        "output_reconstruction": "independent_verifier_analytic_convolution", "refit_performed_by_this_test": False}
    write_json(output / "run_metadata.json", metadata)
    validate_output_directory(output, reference)


def test_successful_optimizer_diagnostic_variation_is_not_a_hidden_gate(output_copy):
    output, reference = output_copy; rows = read_rows(output / "bp_estimates.csv")
    for row in rows:
        row["optimizer_status"] = 1 if int(row["optimizer_status"]) != 1 else 3
        row["nfev"] = 2 if int(row["nfev"]) != 2 else 3
        row["selected_start_index"] = (int(row["selected_start_index"])+1) % 3
    write_rows(output / "bp_estimates.csv", rows)
    validate_output_directory(output, reference)


@pytest.mark.parametrize("kind", ["duplicate_scan", "drop_scan", "foreign_session", "duplicate_frame", "drop_frame", "fractional_frame"])
def test_exact_scan_and_frame_membership(output_copy, kind):
    output, reference = output_copy
    name = "tac_fit.csv" if "frame" in kind else "bp_estimates.csv"; rows = read_rows(output / name)
    if kind.startswith("duplicate"): rows.append(rows[0].copy())
    elif kind.startswith("drop"): rows.pop()
    elif kind == "foreign_session": rows[0]["session"] = "ses-other"
    else: rows[0]["frame_index"] = float(rows[0]["frame_index"])+.25
    write_rows(output / name, rows)
    with pytest.raises((AssertionError, ValueError)): validate_output_directory(output, reference)


@pytest.mark.parametrize("kind", ["R1", "k2", "BP_ND", "mean_preserving_scan_swap", "constant_parameters"])
def test_coherent_parameter_prediction_and_summary_forgery_fails(output_copy, kind):
    output, reference = output_copy; estimates = read_rows(output / "bp_estimates.csv")
    if kind in PARAMETERS:
        column = PARAMETERS.index(kind); value = float(estimates[0][kind]); width = UPPER[column]-LOWER[column]
        estimates[0][kind] = value+.01*width if value+.01*width < UPPER[column] else value-.01*width
    elif kind == "mean_preserving_scan_swap":
        first = estimates[0]
        first_params = np.array([float(first[field]) for field in PARAMETERS])
        second = next((row for row in estimates[1:] if not np.allclose(
            [float(row[field]) for field in PARAMETERS], first_params, atol=PARAM_ATOL, rtol=PARAM_RTOL)), None)
        if second is None: pytest.skip("actual source parameters coincide; no distinguishable scan-swap control")
        for field in PARAMETERS: first[field], second[field] = second[field], first[field]
    else:
        first_params = np.array([float(estimates[0][field]) for field in PARAMETERS])
        if all(np.allclose([float(row[field]) for field in PARAMETERS], first_params,
                           atol=PARAM_ATOL, rtol=PARAM_RTOL) for row in estimates[1:]):
            pytest.skip("actual source parameters are constant; constancy is not itself an error")
        for row in estimates[1:]:
            for field in PARAMETERS: row[field] = estimates[0][field]
    original_mean = read_json(output / "pet_results.json")["putamen_BP_ND_mean"]
    reconstruct_all(output, estimates=estimates)
    if kind == "mean_preserving_scan_swap":
        assert read_json(output / "pet_results.json")["putamen_BP_ND_mean"] == pytest.approx(original_mean, abs=1e-12)
    with pytest.raises(AssertionError, match="parameters differ from declared source fit"):
        validate_output_directory(output, reference)


@pytest.mark.parametrize("kind", ["seconds_as_minutes", "scale_tacs", "wrong_reference", "wrong_target", "source_hemisphere_swap"])
def test_coherent_wrong_source_or_time_contract_fails(output_copy, kind):
    output, reference = output_copy; frames = read_rows(output / "tac_fit.csv")
    for row in frames:
        if kind == "seconds_as_minutes": row["mid_time_min"] = float(row["mid_time_min"])*60
        elif kind == "scale_tacs":
            for field in (*SOURCE_TAC_FIELDS, "target", "reference"): row[field] = float(row[field])*1000
        elif kind == "wrong_reference":
            for field in ("left_cerebellum_cortex", "right_cerebellum_cortex", "reference"):
                row[field] = float(row[field])*1.1
        elif kind == "wrong_target":
            for field in ("left_putamen", "right_putamen", "target"): row[field] = float(row[field])*.9
        else:
            row["left_putamen"], row["right_putamen"] = row["right_putamen"], row["left_putamen"]
    reconstruct_all(output, frames=frames)
    with pytest.raises(AssertionError, match="source .* differs"):
        validate_output_directory(output, reference)


@pytest.mark.parametrize("kind", ["prediction", "residual_sign", "sse", "rmse", "normalized_rmse", "reference_scale", "k2prime"])
def test_prediction_residual_and_reported_qc_are_not_decorative(output_copy, kind):
    output, reference = output_copy
    if kind in ("prediction", "residual_sign"):
        rows = read_rows(output / "tac_fit.csv")
        if kind == "prediction":
            for row in rows:
                row["predicted_target"] = float(row["predicted_target"])*1.02
                row["residual"] = float(row["predicted_target"])-float(row["target"])
        else:
            for row in rows: row["residual"] = -float(row["residual"])
        write_rows(output / "tac_fit.csv", rows)
    else:
        rows = read_rows(output / "bp_estimates.csv")
        rows[0][kind] = float(rows[0][kind])*1.2+1e-3
        write_rows(output / "bp_estimates.csv", rows)
    with pytest.raises(AssertionError): validate_output_directory(output, reference)


@pytest.mark.parametrize("kind", ["optimizer_failure", "impossible_nfev", "invalid_start", "false_bound_flag", "wrong_model"])
def test_explicit_model_and_optimizer_qc_contract(output_copy, kind):
    output, reference = output_copy; rows = read_rows(output / "bp_estimates.csv")
    if kind == "optimizer_failure": rows[0]["optimizer_status"] = 0
    elif kind == "impossible_nfev": rows[0]["nfev"] = 0
    elif kind == "invalid_start": rows[0]["selected_start_index"] = 3
    elif kind == "wrong_model": rows[0]["model"] = "MRTM"
    else:
        flags = json.loads(rows[0]["at_lower_bound"]); flags[0] = not flags[0]
        rows[0]["at_lower_bound"] = json.dumps(flags)
    write_rows(output / "bp_estimates.csv", rows)
    with pytest.raises(AssertionError): validate_output_directory(output, reference)


@pytest.mark.parametrize("kind", ["wrong_mean", "wrong_pairing", "wrong_group_percentage", "drop_pair", "wrong_defined_count"])
def test_paired_summary_arithmetic_and_identity(output_copy, kind):
    output, reference = output_copy; result = read_json(output / "pet_results.json")
    if kind == "wrong_mean": result["putamen_BP_ND_mean"] += .01
    elif kind == "wrong_pairing":
        a, b = result["per_subject"]
        a["rescan_BP_ND"], b["rescan_BP_ND"] = b["rescan_BP_ND"], a["rescan_BP_ND"]
        for pair in (a, b):
            baseline, rescan = pair["baseline_BP_ND"], pair["rescan_BP_ND"]
            pair["absolute_difference"] = abs(baseline-rescan); pair["pair_mean"] = (baseline+rescan)/2
            pair["test_retest_pct"] = 100*pair["absolute_difference"]/pair["pair_mean"] if pair["pair_mean"] > 0 else None
            pair["status"] = "ok" if pair["pair_mean"] > 0 else "undefined_nonpositive_mean"
        result["n_defined_pairs"] = sum(pair["test_retest_pct"] is not None for pair in (a, b))
        result["test_retest_pct"] = (a["test_retest_pct"]+b["test_retest_pct"])/2 if result["n_defined_pairs"] == 2 else None
    elif kind == "wrong_group_percentage": result["test_retest_pct"] += .1
    elif kind == "drop_pair": result["per_subject"].pop()
    else: result["n_defined_pairs"] = 1
    write_json(output / "pet_results.json", result)
    with pytest.raises(AssertionError): validate_output_directory(output, reference)


@pytest.mark.parametrize("kind", ["hash", "frames", "duration", "duplicate_observation"])
def test_source_metadata_is_not_only_a_label(output_copy, kind):
    output, reference = output_copy; metadata = read_json(output / "run_metadata.json")
    if kind == "hash": metadata["source_sha256"][next(iter(metadata["source_sha256"]))] = "0"*64
    elif kind == "frames": metadata["per_scan_observations"][0]["n_frames"] += 1
    elif kind == "duration": metadata["per_scan_observations"][0]["duration_s"] += 1
    else: metadata["per_scan_observations"][1] = metadata["per_scan_observations"][0].copy()
    write_json(output / "run_metadata.json", metadata)
    with pytest.raises(AssertionError): validate_output_directory(output, reference)


@pytest.mark.parametrize("kind", ["missing", "empty"])
def test_findings_required_without_keyword_gate(output_copy, kind):
    output, reference = output_copy
    if kind == "missing": (output / "findings.md").unlink()
    else: (output / "findings.md").write_text(" \n\t")
    with pytest.raises((AssertionError, FileNotFoundError)): validate_output_directory(output, reference)
