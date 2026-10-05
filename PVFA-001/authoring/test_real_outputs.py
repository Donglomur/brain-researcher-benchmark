"""Actual-source acceptance and coherent-forgery regression tests.

Set REPAIR_ORACLE_OUTPUT to the genuine all-three-model output. These tests do
not fit source data, download it, or create/overwrite any reference bank.
"""
import copy
import hashlib
import itertools
import json
import os
from pathlib import Path
import shutil
import sys

import numpy as np
import pytest

TASK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK/"tests"))
import proof_of_work as q
from test_contract import emit, write_csv


@pytest.fixture(scope="module")
def genuine_output():
    configured = os.environ.get("REPAIR_ORACLE_OUTPUT")
    if not configured: pytest.skip("requires genuine full source-derived output")
    source = Path(configured)
    assert source.is_dir()
    return source


@pytest.fixture(scope="module")
def reference(genuine_output):
    reference = q.load_reference(TASK/"tests/reference.npz")
    q.validate_output_directory(genuine_output, reference)
    return reference


@pytest.fixture
def output(tmp_path, genuine_output):
    for filename in q.FILES: shutil.copyfile(genuine_output/filename, tmp_path/filename)
    return tmp_path


def update_entry(entry, reference, model):
    expected = reference["models"][model]
    derived = q.derive(q.entry_beta(entry), entry["f"], reference["signal"][:,expected["indices"]],
                       expected["design"], reference["bvals"][expected["indices"]], model)
    for key, value in derived.items(): entry[key] = value
    success = np.isin(entry["optimizer_status"], (1,2,3,4)) if model == "fwdti" else np.ones(len(reference["ijk"]),bool)
    entry["eligible"] = ((entry["status"] == "ok") & entry["fit_attempted"] & success &
                         np.isfinite(q.entry_beta(entry)).all(axis=1) & np.isfinite(entry["f"]) &
                         (entry["f"] >= 0) & (entry["f"] < 1) & (derived["S0_hat"] > 0) &
                         np.isfinite(derived["normalized_predictions"]).all(axis=1) & np.isfinite(derived["sse"]) & derived["tensor_nonzero"])
    return entry


def test_original_genuine_output_and_optional_private_artifacts_not_required(output, reference):
    assert not (output/"analysis_arrays.npz").exists()
    q.validate_output_directory(output, reference)


@pytest.mark.parametrize("models,main", [(models,main) for count in (2,3)
    for models in itertools.combinations(q.MODELS,count) for main in models])
def test_every_selected_pair_or_triple_and_main(output, reference, models, main):
    emit(output, reference, models, main)
    q.validate_output_directory(output, reference)


def test_public_template_identity_and_minimal_measured_metadata(output, reference):
    template = q.load_json(TASK/"environment/method_contract.json")
    assert template == reference["stats"]["metadata_contract"]
    measured = q.load_json(output/"run_metadata.json")
    required = ("status","main_model","fitted_models","n_roi_voxels","n_brain_voxels",
                "n_seed_voxels","n_common_valid","status_counts_by_model")
    template.update({key: measured[key] for key in required})
    (output/"run_metadata.json").write_text(json.dumps(template))
    (output/"findings.md").write_text("The tables contain the estimates and support counts. These results are conditional on the public models.")
    q.validate_output_directory(output, reference)


def test_order_extra_columns_and_equivalent_numeric_notation(output, reference):
    for filename in ("fit_parameters.csv","fa_sweep.csv","fa_voxelwise.csv"):
        rows = q.read_csv(output/filename, ("i","j","k"))
        for row in rows:
            for key in ("i","j","k"):
                original = q.integer(row[key], key)
                row[key] = format(float(original), ".17e")
                assert q.integer(row[key], key) == original, "formatting must preserve source coordinates"
            if filename == "fit_parameters.csv":
                for key in q.BOOL_FIELDS: row[key] = str(q.boolean(row[key],key)).upper()
            row["optional_note"] = "ignored"
        write_csv(output/filename, list(rows[0])[::-1], rows[::-1])
    metadata = q.load_json(output/"run_metadata.json")
    metadata["fitted_models"].reverse(); metadata["ungraded_extra"] = {"anything": "allowed"}
    (output/"run_metadata.json").write_text(json.dumps(metadata))
    q.validate_output_directory(output, reference)


def test_optional_private_array_is_not_a_submission_gate(output, reference):
    (output/"analysis_arrays.npz").write_bytes(b"optional non-submission artifact")
    q.validate_output_directory(output, reference)


def test_omitted_zero_status_counts(output, reference):
    result, metadata = q.load_json(output/"results.json"), q.load_json(output/"run_metadata.json")
    for values in result["by_model"].values():
        values["status_counts"] = {key: value for key,value in values["status_counts"].items() if value}
    metadata["status_counts_by_model"] = {model: {key:value for key,value in counts.items() if value}
                                         for model,counts in metadata["status_counts_by_model"].items()}
    (output/"results.json").write_text(json.dumps(result))
    (output/"run_metadata.json").write_text(json.dumps(metadata))
    q.validate_output_directory(output, reference)


def test_solver_success_code_and_evaluation_count_not_point_matched(output, reference):
    entries = copy.deepcopy(reference["models"])
    successful = entries["fwdti"]["status"] == "ok"
    entries["fwdti"]["optimizer_status"][successful] = 3
    entries["fwdti"]["nfev"][successful] += 1
    emit(output, reference, entries=entries)
    q.validate_output_directory(output, reference)


@pytest.mark.parametrize("model", ["dti_b1000", "dti_b2000"])
def test_genuinely_independent_wls_subset_is_accepted(output, reference, model):
    configured = os.environ.get("REPAIR_INDEPENDENT_FITS")
    if not configured: pytest.skip("requires retained genuine SciPy least-squares coefficient artifact")
    with np.load(configured, allow_pickle=False) as artifact:
        assert str(artifact["pipeline_id"].item()) == q.PIPELINE_ID
        assert str(artifact["source_manifest_sha256"].item()) == reference["stats"]["metadata_contract"]["source_manifest_sha256"]
        assert json.loads(str(artifact["source_sha256_json"].item())) == reference["stats"]["source_sha256"]
        rows, xyz, beta = artifact["roi_indices"], artifact["roi_ijk"], artifact["beta_"+model]
    expected_rows = np.unique(np.linspace(0, len(reference["ijk"])-1, min(64,len(reference["ijk"])), dtype=int))
    assert np.array_equal(rows, expected_rows) and np.array_equal(xyz, reference["ijk"][rows])
    assert beta.shape == (len(rows),7) and np.isfinite(beta).all()
    entries = copy.deepcopy(reference["models"])
    for index,key in enumerate((*q.TENSOR_FIELDS,"neg_log_S0")): entries[model][key][rows] = beta[:,index]
    update_entry(entries[model], reference, model)
    emit(output, reference, entries=entries)
    # Only the independently refitted subset is replaced; this is not a claim
    # of an independent whole-ROI nonlinear or conventional-tensor execution.
    q.validate_output_directory(output,reference)


def test_genuinely_independent_analytic_lm_subset_is_accepted(output, reference):
    configured = os.environ.get("REPAIR_INDEPENDENT_FITS")
    if not configured: pytest.skip("requires retained genuine analytic-LM subset and its full report")
    artifact_path = Path(configured)
    report_path = Path(os.environ["REPAIR_INDEPENDENT_REPORT"]) if os.environ.get("REPAIR_INDEPENDENT_REPORT") else artifact_path.with_name(artifact_path.name.removesuffix(".alternate_fits.npz")+".json")
    report = q.load_json(report_path)
    assert report["status"] == "passed" and report["mode"] == "complete_source_check"
    assert report["pipeline_id"] == q.PIPELINE_ID
    assert report["source_sha256"] == reference["stats"]["source_sha256"]
    assert report["source_manifest_sha256"] == reference["stats"]["metadata_contract"]["source_manifest_sha256"]
    assert report["source_roi_count"] == report["evaluated_roi_count"] == len(reference["ijk"])
    assert hashlib.sha256(artifact_path.read_bytes()).hexdigest() == report["alternate_fit_artifact"]["sha256"]
    with np.load(artifact_path, allow_pickle=False) as artifact:
        assert str(artifact["pipeline_id"].item()) == q.PIPELINE_ID
        assert json.loads(str(artifact["source_sha256_json"].item())) == reference["stats"]["source_sha256"]
        assert str(artifact["source_manifest_sha256"].item()) == report["source_manifest_sha256"]
        rows, xyz = artifact["roi_indices"], artifact["roi_ijk"]
        parameters, predictions, statuses = artifact["lm_parameters"], artifact["lm_predictions"], artifact["lm_status"]
    expected_rows = np.unique(np.linspace(0,len(reference["ijk"])-1,min(64,len(reference["ijk"])),dtype=int))
    assert np.array_equal(rows,expected_rows) and np.array_equal(xyz,reference["ijk"][rows])
    assert parameters.shape == (len(rows),8) and np.isfinite(parameters).all()
    diagnostics = {item["roi_index"]: item for item in report["alternative_fit_diagnostics"]}
    assert len(diagnostics) == len(report["alternative_fit_diagnostics"]) and set(diagnostics) == set(rows)
    entries = copy.deepcopy(reference["models"])
    entry = entries["fwdti"]
    for position,row in enumerate(rows):
        diagnostic = diagnostics[int(row)]; actual = diagnostic["alternatives"]["lm"]
        assert diagnostic["ijk"] == reference["ijk"][row].tolist()
        assert diagnostic["oracle_status"] == "ok"
        assert actual["converged"] and actual["numerically_equivalent_fixed_recipe_candidate"]
        assert actual["status"] in (1,2,3,4) and actual["nfev"] > 0
        assert str(actual["status"]) == statuses[position]
        assert np.array_equal(parameters[position],np.asarray(actual["parameters"]))
        assert np.array_equal(predictions[position],np.asarray(actual["prediction"]))
        for column,key in enumerate((*q.TENSOR_FIELDS,"neg_log_S0")): entry[key][row] = parameters[position,column]
        entry["f"][row] = .5*(1+np.sin(parameters[position,7]-np.pi/2))
        entry["optimizer_status"][row] = actual["status"]
        entry["nfev"][row] = actual["nfev"]
    update_entry(entry,reference,"fwdti")
    np.testing.assert_allclose(entry["normalized_predictions"][rows],predictions/entry["normalization_scale"][rows,None],atol=1e-12,rtol=1e-12)
    emit(output,reference,entries=entries)
    metadata = q.load_json(output/"run_metadata.json")
    metadata["equivalent_implementation"] = {"model":"fwdti","independent_subset_size":len(rows),
        "solver":"SciPy leastsq with independent analytic Jacobian", "remaining_rows":"original genuine full execution"}
    (output/"run_metadata.json").write_text(json.dumps(metadata))
    # Every preselected sampled fit is retained. Different TRF optima are not
    # promoted to passes, and no favorable subset or new fitting is used.
    q.validate_output_directory(output,reference)


@pytest.mark.parametrize("model", q.MODELS)
@pytest.mark.parametrize("mutation", ["tensor_scale","tensor_shift","tensor_permutation","fitted_S0"])
def test_coherent_parameter_forgery(output, reference, model, mutation):
    entries = copy.deepcopy(reference["models"]); entry = entries[model]
    finite = np.isfinite(q.entry_beta(entry)).all(axis=1)
    assert finite.any()
    if mutation == "tensor_scale":
        for key in q.TENSOR_FIELDS: entry[key][finite] *= 1.05
    elif mutation == "tensor_shift":
        for key in ("Dxx","Dyy","Dzz"): entry[key][finite] += .00005
    elif mutation == "tensor_permutation":
        indices = np.flatnonzero(finite)
        for key in (*q.TENSOR_FIELDS,"neg_log_S0","f"): entry[key][indices] = entry[key][indices[::-1]]
    elif mutation == "fitted_S0": entry["neg_log_S0"][finite] += .05
    assert any(not np.array_equal(entry[key],reference["models"][model][key],equal_nan=True)
               for key in (*q.TENSOR_FIELDS,"neg_log_S0","f"))
    update_entry(entry,reference,model)
    emit(output,reference,entries=entries)
    with pytest.raises(AssertionError,match="source raw tensor|source fraction|source fitted S0"):
        q.validate_output_directory(output,reference)


def test_coherent_freewater_fraction_forgery(output, reference):
    entries = copy.deepcopy(reference["models"]); entry = entries["fwdti"]
    finite = np.isfinite(entry["f"])
    assert finite.any()
    entry["f"][finite] = .5*entry["f"][finite]+.1
    update_entry(entry,reference,"fwdti")
    emit(output,reference,entries=entries)
    with pytest.raises(AssertionError,match="source fraction"):
        q.validate_output_directory(output,reference)


def test_other_dti_model_cannot_be_relabelled(output, reference):
    entries = copy.deepcopy(reference["models"])
    for key in (*q.TENSOR_FIELDS,"neg_log_S0"): entries["dti_b1000"][key] = entries["dti_b2000"][key].copy()
    update_entry(entries["dti_b1000"],reference,"dti_b1000")
    emit(output,reference,entries=entries)
    with pytest.raises(AssertionError,match="source raw tensor"):
        q.validate_output_directory(output,reference)


@pytest.mark.parametrize("mutation", ["drop","half_roi","duplicate","fractional_coordinate",
 "foreign_coordinate","unknown_group","partial_extra_group","one_model","nonfinite_tensor",
 "missing_tensor","false_status","eligible","common","residual","clipping_count","source_b0",
 "normalization","signal_floor_count","optimizer_failed","negative_nfev","initial_fraction","boundary_flag"])
def test_incomplete_invalid_or_inconsistent_receipt(output,reference,mutation):
    path=output/"fit_parameters.csv"; rows=q.read_csv(path,q.TABLE_COLUMNS); columns=list(rows[0])
    ok_index=next(index for index,row in enumerate(rows) if row["model"]=="fwdti" and row["status"]=="ok")
    row=rows[ok_index]
    if mutation=="drop": rows.pop()
    elif mutation=="half_roi": rows=rows[:len(rows)//2]
    elif mutation=="duplicate": rows.append(dict(row))
    elif mutation=="fractional_coordinate": row["i"]=str(float(row["i"])+.5)
    elif mutation=="foreign_coordinate": row["i"]="9999"
    elif mutation=="unknown_group": row["model"]="unrecognized"
    elif mutation=="partial_extra_group":
        rows=[item for item in rows if item["model"]!="dti_b1000"]+[next(item for item in rows if item["model"]=="dti_b1000")]
    elif mutation=="one_model": rows=[item for item in rows if item["model"]=="fwdti"]
    elif mutation=="nonfinite_tensor": row["Dxx"]="nan"
    elif mutation=="missing_tensor":
        columns.remove("Dxx")
        for item in rows:item.pop("Dxx")
    elif mutation=="false_status": row["status"]="optimizer_failed"
    elif mutation=="eligible": row["eligible"]="false"
    elif mutation=="common": row["common_valid"]=str(not q.boolean(row["common_valid"],"common_valid"))
    elif mutation=="residual": row["nrmse"]=str(float(row["nrmse"])+.01)
    elif mutation=="clipping_count": row["n_eigenvalues_clipped"]=str(int(float(row["n_eigenvalues_clipped"]))+1)
    elif mutation=="source_b0": row["observed_b0"]=str(float(row["observed_b0"])+1)
    elif mutation=="normalization": row["normalization_scale"]=str(float(row["normalization_scale"])+1)
    elif mutation=="signal_floor_count": row["n_signal_floored"]=str(int(row["n_signal_floored"])+1)
    elif mutation=="optimizer_failed": row["optimizer_status"]="5"
    elif mutation=="negative_nfev": row["nfev"]="-1"
    elif mutation=="initial_fraction": row["init_f"]=str(float(row["init_f"])+.1)
    elif mutation=="boundary_flag": row["boundary_f_low"]=str(not q.boolean(row["boundary_f_low"],"boundary"))
    write_csv(path,columns,rows)
    with pytest.raises(AssertionError): q.validate_output_directory(output,reference)


@pytest.mark.parametrize("filename",["fa_voxelwise.csv","fa_sweep.csv"])
@pytest.mark.parametrize("mutation",["drop","duplicate","wrong_fa","fractional_coordinate","unknown_model"])
def test_fa_receipt_cross_file_checks(output,reference,filename,mutation):
    path=output/filename; rows=q.read_csv(path,("i","j","k","fa"))
    if mutation=="unknown_model" and filename=="fa_voxelwise.csv":
        # Main is a checked metadata choice, not an extra CSV column.
        result=q.load_json(output/"results.json"); result["main_model"]="unrecognized"
        (output/"results.json").write_text(json.dumps(result))
    else:
        if mutation=="drop": rows.pop()
        elif mutation=="duplicate": rows.append(dict(rows[0]))
        elif mutation=="wrong_fa":
            row=next(row for row in rows if row["fa"]); row["fa"]=str(float(row["fa"])+.1)
        elif mutation=="fractional_coordinate": rows[0]["i"]="1.5"
        elif mutation=="unknown_model": rows[0]["model"]="unknown"
        write_csv(path,list(rows[0]),rows)
    with pytest.raises(AssertionError): q.validate_output_directory(output,reference)


@pytest.mark.parametrize("mutation",["primary_mean","n_roi","n_common","valid_count","status_count",
 "clipping_total","common_mean","paired_sign_or_offset","missing_pair","extra_pair","model_membership"])
def test_summary_arithmetic_and_selected_support(output,reference,mutation):
    result=q.load_json(output/"results.json"); main=result["main_model"]
    if mutation=="primary_mean": result["fa_proxy_roi"]+=.1
    elif mutation=="n_roi": result["n_roi_voxels"]+=1
    elif mutation=="n_common": result["n_common_valid"]+=1
    elif mutation=="valid_count": result["by_model"][main]["n_valid"]+=1
    elif mutation=="status_count": result["by_model"][main]["status_counts"]["ok"]+=1
    elif mutation=="clipping_total": result["by_model"][main]["n_eigenvalues_clipped_total"]+=1
    elif mutation=="common_mean": result["common_valid"]["by_model"][main]["fa_mean"]+=.1
    elif mutation=="paired_sign_or_offset":
        key=next(iter(result["common_valid"]["paired_fa_differences"]))
        result["common_valid"]["paired_fa_differences"][key]+=.1
    elif mutation=="missing_pair": result["common_valid"]["paired_fa_differences"].pop(next(iter(result["common_valid"]["paired_fa_differences"])))
    elif mutation=="extra_pair": result["common_valid"]["paired_fa_differences"]["fake_minus_fake"]=0
    elif mutation=="model_membership": result["by_model"]["fake"]=copy.deepcopy(result["by_model"][main])
    (output/"results.json").write_text(json.dumps(result))
    with pytest.raises(AssertionError): q.validate_output_directory(output,reference)


@pytest.mark.parametrize("mutation",["source_sha","source_extra","smoothing","model_recipe","main",
 "model_set","roi_count","brain_count","seed_count","status","missing_contract","status_count"])
def test_public_metadata_binding(output,reference,mutation):
    metadata=q.load_json(output/"run_metadata.json")
    if mutation=="source_sha": metadata["source_sha256"][next(iter(metadata["source_sha256"]))]="0"*64
    elif mutation=="source_extra": metadata["source_sha256"]["undeclared"]="0"*64
    elif mutation=="smoothing": metadata["preprocessing"]["smoothing"]["fwhm_voxels"]*=2
    elif mutation=="model_recipe": metadata["models"]["fwdti"]["Diso"]*=2
    elif mutation=="main": metadata["main_model"]="unknown"
    elif mutation=="model_set": metadata["fitted_models"]=["fwdti","fwdti"]
    elif mutation=="roi_count": metadata["n_roi_voxels"]+=1
    elif mutation=="brain_count": metadata["n_brain_voxels"]+=1
    elif mutation=="seed_count": metadata["n_seed_voxels"]+=1
    elif mutation=="status": metadata["status"]="resource_pilot"
    elif mutation=="missing_contract": metadata.pop("models")
    elif mutation=="status_count": metadata["status_counts_by_model"]["fwdti"]["ok"]+=1
    (output/"run_metadata.json").write_text(json.dumps(metadata))
    with pytest.raises(AssertionError): q.validate_output_directory(output,reference)


@pytest.mark.parametrize("filename",q.FILES)
def test_missing_required_output(output,reference,filename):
    (output/filename).unlink()
    with pytest.raises(AssertionError): q.validate_output_directory(output,reference)


def test_empty_findings(output,reference):
    (output/"findings.md").write_text(" \n ")
    with pytest.raises(AssertionError,match="empty findings"): q.validate_output_directory(output,reference)
