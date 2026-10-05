"""Small algebra/parser fixtures only; never a scientific reference bank."""
import copy
import csv
import itertools
import json
from pathlib import Path
import sys

import numpy as np
import pytest

TASK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK/"tests"))
import proof_of_work as q


def mechanical_reference():
    directions = np.array([[1,0,0],[0,1,0],[0,0,1],[1,1,0],[1,0,1],[0,1,1],[1,1,1]], float)
    directions /= np.linalg.norm(directions, axis=1)[:, None]
    bvals = np.array([0]+[1000]*7+[2000]*7+[3500], float)
    bvecs = np.vstack(([0,0,0], directions, directions, [1,0,0]))
    base = np.array([[.0013,.00003,.0007,.00001,.00002,.0005,-np.log(100)],
                     [.0011,.00002,.0008,.00004,.00003,.0006,-np.log(110)],
                     [.0014,.00001,.0006,.00002,.00001,.0004,-np.log(120)]])
    signal = np.exp(base @ q.design_matrix(bvals, bvecs).T)
    reference = {"ijk": np.array([[1,2,3],[2,3,4],[3,4,5]]), "signal": signal,
                 "bvals": bvals, "bvecs": bvecs, "models": {},
                 "stats": {"pipeline_id": q.PIPELINE_ID, "source_sha256": {"unit-fixture": "0"*64},
                           "n_brain_voxels": 12, "n_seed_voxels": 1,
                           "metadata_contract": {"pipeline_id": q.PIPELINE_ID, "source_sha256": {"unit-fixture": "0"*64},
                               "smoothing": {"fwhm_voxels": .625}, "minimum_signal": 1e-6}}}
    for index, model in enumerate(q.MODELS):
        beta = base.copy(); beta[:, :6] *= 1+.05*index
        indices = q.model_indices(bvals, model)
        design = q.design_matrix(bvals[indices], bvecs[indices])
        f = np.array([.1,.2,.3]) if model == "fwdti" else np.zeros(3)
        derived = q.derive(beta, f, signal[:, indices], design, bvals[indices], model)
        entry = {"indices": indices, "design": design, "status": np.array(["ok"]*3, dtype="U32"),
                 **{key: beta[:, j].copy() for j, key in enumerate((*q.TENSOR_FIELDS, "neg_log_S0"))},
                 "f": f, "init_f": np.array([.15,.15,.15]) if model == "fwdti" else np.full(3, np.nan),
                 "init_md": np.full(3, .001) if model == "fwdti" else np.full(3, np.nan),
                 "fit_attempted": np.ones(3, bool), "eligible": np.ones(3, bool), "common_valid": np.ones(3, bool),
                 "optimizer_status": np.ones(3) if model == "fwdti" else np.full(3, np.nan),
                 "nfev": np.full(3, 12 if model == "fwdti" else 0, int), **derived}
        reference["models"][model] = entry
    reference["stats"]["results"] = q.summarize("fwdti", reference["models"])
    return q.validate_reference(reference)


def public_value(value):
    if isinstance(value, (bool, np.bool_)): return bool(value)
    if isinstance(value, (int, np.integer)): return int(value)
    if isinstance(value, (float, np.floating)): return float(value) if np.isfinite(value) else ""
    return str(value)


def write_csv(path, columns, rows):
    with Path(path).open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader(); writer.writerows(rows)


def emit(output, reference, models=None, main=None, entries=None):
    """Format an in-memory fixture or genuine copied values; never write a bank."""
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    models = list(models or q.MODELS); main = main or models[0]
    entries = copy.deepcopy(entries or {model: reference["models"][model] for model in models})
    common = np.logical_and.reduce([entry["eligible"] for entry in entries.values()])
    for entry in entries.values(): entry["common_valid"] = common.copy()
    rows, sweep, primary = [], [], []
    for model, entry in entries.items():
        for index, xyz in enumerate(reference["ijk"]):
            base = dict(zip(("i", "j", "k"), map(int, xyz)))
            row = dict(base, model=model, **{key: public_value(entry[key][index]) for key in ("status", *q.BOOL_FIELDS, *q.INT_FIELDS, *q.FLOAT_FIELDS)})
            rows.append(row)
            fa = public_value(entry["fa"][index])
            sweep.append(dict(base, model=model, fa=fa))
            if model == main: primary.append(dict(base, fa=fa))
    write_csv(output/"fit_parameters.csv", q.TABLE_COLUMNS, rows)
    write_csv(output/"fa_sweep.csv", ["i","j","k","model","fa"], sweep)
    write_csv(output/"fa_voxelwise.csv", ["i","j","k","fa"], primary)
    result = q.summarize(main, entries)
    metadata = copy.deepcopy(reference["stats"]["metadata_contract"])
    metadata.update(status="ok", main_model=main, fitted_models=models,
                    n_roi_voxels=len(reference["ijk"]), n_common_valid=int(common.sum()),
                    n_brain_voxels=reference["stats"]["n_brain_voxels"], n_seed_voxels=reference["stats"]["n_seed_voxels"],
                    status_counts_by_model={model: values["status_counts"] for model, values in result["by_model"].items()})
    (output/"results.json").write_text(json.dumps(result, allow_nan=False))
    (output/"run_metadata.json").write_text(json.dumps(metadata, allow_nan=False))
    (output/"findings.md").write_text("These are conditional computational estimates, not independent microstructure truth.\n")
    return entries


@pytest.fixture
def reference(): return mechanical_reference()


@pytest.mark.parametrize("models", list(itertools.combinations(q.MODELS, 2))+[q.MODELS])
def test_any_two_or_three_models_and_each_primary(tmp_path, reference, models):
    for main in models:
        emit(tmp_path, reference, models, main)
        selected, _ = q.validate_output_directory(tmp_path, reference)
        assert selected == main


@pytest.mark.parametrize("value", [True, "nan", "inf", "", "abc", None])
def test_numeric_parser_rejects_invalid(value):
    with pytest.raises(AssertionError): q.finite(value, "fixture")


@pytest.mark.parametrize("value", ["1.1", "nan", True, "inf"])
def test_integer_parser_does_not_round(value):
    with pytest.raises(AssertionError): q.integer(value, "fixture")


@pytest.mark.parametrize("value", ["1.0", "1e0", 1, 1.0])
def test_integer_accepts_equivalent_notation(value): assert q.integer(value, "fixture") == 1


@pytest.mark.parametrize("mutation", ["tiny_recipe", "wrong_source", "missing_source", "extra_source"])
def test_static_contract_exact_semantics_not_absolute_epsilon(reference, mutation):
    expected = reference["stats"]["metadata_contract"]
    actual = copy.deepcopy(expected)
    if mutation == "tiny_recipe": actual["minimum_signal"] = 2e-6
    elif mutation == "wrong_source": actual["source_sha256"]["unit-fixture"] = "1"*64
    elif mutation == "missing_source": actual["source_sha256"] = {}
    else: actual["source_sha256"]["other"] = "1"*64
    with pytest.raises(AssertionError): q.match_metadata(actual, expected)


def test_geometry_rounding_and_extra_metadata_accepted():
    q.match_metadata({"affine": [[2.0000001]], "extra": True}, {"affine": [[2.]]})


def test_prediction_is_raw_tensor_not_clipped_tensor():
    beta = np.array([[-.0001,0,.0005,0,0,.001,-np.log(100)]])
    bvals = np.array([0,1000,1000,1000.])
    design = q.design_matrix(bvals, np.array([[0,0,0],[1,0,0],[0,1,0],[0,0,1]]))
    derived = q.derive(beta, np.array([0.]), np.full((1,4),100.), design, bvals, "dti_b1000")
    assert derived["n_eigenvalues_clipped"][0] == 1
    assert derived["normalized_predictions"][0,1] > 1
    assert derived["md"][0] > 0 and 0 < derived["fa"][0] < 1


def test_freewater_tensor_clips_at_zero_without_status_filter():
    beta = np.array([[-.0001,0,-.0002,0,0,-.0003,-np.log(100)]])
    bvals = np.array([0,1000.])
    design = q.design_matrix(bvals, np.array([[0,0,0],[1,0,0]]))
    derived = q.derive(beta, np.array([.2]), np.full((1,2),100.), design, bvals, "fwdti")
    assert derived["fa"][0] == derived["md"][0] == 0
    assert derived["n_eigenvalues_clipped"][0] == 3
    assert not derived["tensor_nonzero"][0]


def test_fraction_boundary_flags_diagnostic_only():
    beta = np.array([[.001,0,.0007,0,0,.0005,-np.log(100)]]*3)
    bvals = np.array([0,1000.]); design = q.design_matrix(bvals, np.array([[0,0,0],[1,0,0]]))
    result = q.derive(beta, np.array([0,1e-6,1-1e-6]), np.full((3,2),100.), design, bvals,"fwdti")
    assert result["boundary_f_low"].tolist() == [True,True,False]
    assert result["boundary_f_high"].tolist() == [False,False,True]


def test_selected_common_support_and_empty_means(reference):
    entries = copy.deepcopy(reference["models"])
    entries["fwdti"]["eligible"][:] = False
    summary = q.summarize("dti_b1000", entries)
    assert summary["n_common_valid"] == 0
    assert summary["by_model"]["fwdti"]["fa_mean"] is None
    assert summary["fa_proxy_roi"] is not None
    assert all(value is None for value in summary["common_valid"]["paired_fa_differences"].values())
    two = q.summarize("dti_b1000", {key: entries[key] for key in ("dti_b2000","dti_b1000")})
    assert two["n_common_valid"] == 3


def test_optimizer_status_and_nfev_are_semantic_not_exact(tmp_path, reference):
    entries = copy.deepcopy(reference["models"])
    entries["fwdti"]["optimizer_status"][:] = 3
    entries["fwdti"]["nfev"][:] = 100
    emit(tmp_path, reference, entries=entries)
    q.validate_output_directory(tmp_path, reference)


def test_zero_status_counts_can_be_omitted(tmp_path, reference):
    emit(tmp_path, reference)
    result = q.load_json(tmp_path/"results.json")
    metadata = q.load_json(tmp_path/"run_metadata.json")
    for summary in result["by_model"].values(): summary["status_counts"] = {key: value for key, value in summary["status_counts"].items() if value}
    metadata["status_counts_by_model"] = {model: {key: value for key, value in counts.items() if value} for model, counts in metadata["status_counts_by_model"].items()}
    (tmp_path/"results.json").write_text(json.dumps(result))
    (tmp_path/"run_metadata.json").write_text(json.dumps(metadata))
    q.validate_output_directory(tmp_path, reference)


def test_legacy_bank_fails_closed(tmp_path):
    # A tiny obsolete-metadata fixture must fail before reading any arrays.
    # Keep this regression active even after genuine bank regeneration.
    path = tmp_path/"obsolete_reference.npz"
    np.savez(path, ref_stats=np.asarray(json.dumps({"pipeline_id": "physical-mm-pvfa-v1"})))
    with pytest.raises(AssertionError, match="obsolete"): q.load_reference(path)


@pytest.mark.parametrize("mutation", ["drop", "duplicate", "fractional", "foreign", "unknown", "one_model", "missing_field", "nan", "status", "eligibility", "common", "floorcount", "fraction", "negative_nfev"])
def test_strict_receipt_mechanics(tmp_path, reference, mutation):
    emit(tmp_path, reference)
    path = tmp_path/"fit_parameters.csv"
    rows = q.read_csv(path, q.TABLE_COLUMNS)
    columns = list(q.TABLE_COLUMNS)
    if mutation == "drop": rows.pop()
    elif mutation == "duplicate": rows.append(dict(rows[0]))
    elif mutation == "fractional": rows[0]["i"] = "1.5"
    elif mutation == "foreign": rows[0]["i"] = "999"
    elif mutation == "unknown": rows[0]["model"] = "unknown"
    elif mutation == "one_model": rows = [row for row in rows if row["model"] == "fwdti"]
    elif mutation == "missing_field":
        columns.remove("Dxx")
        for row in rows: row.pop("Dxx")
    elif mutation == "nan": rows[0]["Dxx"] = "nan"
    elif mutation == "status": rows[0]["status"] = "invented"
    elif mutation == "eligibility": rows[0]["eligible"] = "false"
    elif mutation == "common": rows[0]["common_valid"] = "false"
    elif mutation == "floorcount": rows[0]["n_signal_floored"] = "1.5"
    elif mutation == "fraction": rows[3]["f"] = ".1"
    elif mutation == "negative_nfev": rows[0]["nfev"] = "-1"
    write_csv(path, columns, rows)
    with pytest.raises(AssertionError): q.validate_output_directory(tmp_path, reference)


def test_no_variance_or_direction_gate(tmp_path, reference):
    # Constant synthetic fixture checks absence of arbitrary gates, not science.
    for model, entry in reference["models"].items():
        for key in (*q.TENSOR_FIELDS, "neg_log_S0", "f"): entry[key][:] = entry[key][0]
        entry.update(q.derive(q.entry_beta(entry), entry["f"], reference["signal"][:,entry["indices"]],entry["design"],reference["bvals"][entry["indices"]],model))
    reference["stats"]["results"] = q.summarize("fwdti", reference["models"])
    q.validate_reference(reference)
    emit(tmp_path, reference)
    q.validate_output_directory(tmp_path, reference)


def with_failed_and_skipped(reference):
    reference = copy.deepcopy(reference)
    entry = reference["models"]["fwdti"]
    entry["status"][0] = "optimizer_failed"
    entry["optimizer_status"][0] = 5
    entry["eligible"][0] = False
    entry["status"][1] = "high_initial_fraction"
    entry["fit_attempted"][1] = False
    entry["optimizer_status"][1] = np.nan
    entry["nfev"][1] = 0
    entry["init_f"][1] = .995
    for key in (*q.TENSOR_FIELDS, "neg_log_S0", "f"): entry[key][1] = np.nan
    entry.update(q.derive(q.entry_beta(entry), entry["f"], reference["signal"][:,entry["indices"]], entry["design"], reference["bvals"][entry["indices"]], "fwdti"))
    entry["eligible"][1] = False
    common = np.logical_and.reduce([values["eligible"] for values in reference["models"].values()])
    for values in reference["models"].values(): values["common_valid"] = common.copy()
    reference["stats"]["results"] = q.summarize("fwdti", reference["models"])
    return q.validate_reference(reference)


def test_finite_failed_and_unattempted_candidates_remain_in_tables(tmp_path, reference):
    reference = with_failed_and_skipped(reference)
    emit(tmp_path, reference)
    _, entries = q.validate_output_directory(tmp_path, reference)
    assert np.isfinite(entries["fwdti"]["fa"][0]) and not entries["fwdti"]["eligible"][0]
    assert np.isnan(entries["fwdti"]["fa"][1]) and not entries["fwdti"]["fit_attempted"][1]
    result = q.load_json(tmp_path/"results.json")
    assert result["n_common_valid"] == result["by_model"]["fwdti"]["n_valid"] == 1
    # Omitting the failed free-water recipe changes the valid common support.
    emit(tmp_path, reference, ("dti_b2000","dti_b1000"), "dti_b1000")
    q.validate_output_directory(tmp_path, reference)
    assert q.load_json(tmp_path/"results.json")["n_common_valid"] == 3


@pytest.mark.parametrize("mutation", ["drop_failed", "replace_failed_with_zero", "failed_eligible", "skipped_attempted", "skipped_zero_candidate"])
def test_failures_cannot_be_dropped_or_promoted(tmp_path, reference, mutation):
    reference = with_failed_and_skipped(reference)
    emit(tmp_path, reference)
    rows = q.read_csv(tmp_path/"fit_parameters.csv", q.TABLE_COLUMNS)
    if mutation == "drop_failed": rows.pop(0)
    elif mutation == "replace_failed_with_zero": rows[0]["fa"] = "0"
    elif mutation == "failed_eligible": rows[0]["eligible"] = "true"
    elif mutation == "skipped_attempted": rows[1]["fit_attempted"] = "true"
    elif mutation == "skipped_zero_candidate":
        for key in (*q.TENSOR_FIELDS, "neg_log_S0", "f"): rows[1][key] = "0"
    write_csv(tmp_path/"fit_parameters.csv", q.TABLE_COLUMNS, rows)
    with pytest.raises(AssertionError): q.validate_output_directory(tmp_path, reference)


def test_gradient_norm_is_not_silently_renormalized():
    bvals = np.array([0.,1000.]); g = np.array([[0.,0.,0.],[1.001,0.,0.]])
    beta = np.array([[.001,0.,.0007,0.,0.,.0005,-np.log(100)]])
    design = q.design_matrix(bvals,g)
    derived = q.derive(beta,np.array([1.]),np.full((1,2),100.),design,bvals,"fwdti")
    assert derived["normalized_predictions"][0,1] == pytest.approx(np.exp(-3*1.001**2))
    assert not np.isclose(derived["normalized_predictions"][0,1], np.exp(-3), atol=1e-7)
