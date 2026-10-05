"""Tiny analytic fixtures only: no original-image processing or model fitting."""
import importlib.util
import csv
import json
from pathlib import Path

import numpy as np
import pytest
from scipy.optimize._numdiff import approx_derivative

SPEC = importlib.util.spec_from_file_location("pvfa_independent", Path(__file__).with_name("check_independent.py"))
ind = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ind)


def gradients():
    rng = np.random.RandomState(13)
    directions = rng.normal(size=(40, 3))
    directions /= np.linalg.norm(directions, axis=1)[:, None]
    bvals = np.r_[0, np.full(20, 1000), np.full(20, 2000)]
    bvecs = np.vstack((np.zeros(3), directions))
    return ind.design_matrix(bvals, bvecs)


def test_design_expansion_and_intercept_sign():
    design = ind.design_matrix(np.array([0, 1000]), np.array([[0, 0, 0], [1/np.sqrt(2), 1/np.sqrt(2), 0]]))
    np.testing.assert_allclose(design, [[0, 0, 0, 0, 0, 0, -1], [-500, -1000, -500, 0, 0, 0, -1]])


def test_tensor_pack_and_fa_rotation_invariant():
    tensor = np.diag([0.0016, 0.0005, 0.0003])
    q, _ = np.linalg.qr(np.random.RandomState(0).normal(size=(3, 3)))
    rotated = q@tensor@q.T
    packed = ind.pack_tensor(rotated)
    np.testing.assert_allclose(ind.unpack_tensor(packed), rotated)
    first, second = ind.tensor_summary(ind.pack_tensor(tensor), 0), ind.tensor_summary(packed, 0)
    np.testing.assert_allclose(first["fa"], second["fa"])
    np.testing.assert_allclose(second["reported_tensor"], rotated, atol=1e-16)


def test_negative_eigenvalue_and_zero_tensor_are_explicit():
    result = ind.tensor_summary(np.array([0.001, 0, 0.0004, 0, 0, -0.0001]), 0)
    assert result["clipped"]
    assert result["raw_eigenvalues"][-1] < 0
    assert result["eigenvalues"][-1] == 0
    assert ind.tensor_summary(np.zeros(6), 0)["fa"] == 0


@pytest.mark.parametrize("noise", [0, 0.002])
def test_two_independent_wls_solvers_agree(noise):
    design = gradients()
    coefficients = np.array([.0014, .00005, .0005, -.00003, .00001, .0003, -np.log(800)])
    signal = np.exp(design@coefficients)*(1+noise*np.random.RandomState(2).normal(size=len(design)))
    first = ind.dti_wls(signal, design)[0]
    second = ind.dti_lstsq(signal, design)
    np.testing.assert_allclose(first, second, atol=1e-10, rtol=1e-8)
    if noise == 0:
        np.testing.assert_allclose(first, coefficients, atol=1e-10, rtol=1e-8)


@pytest.mark.parametrize("fraction", [0, .23, 1])
def test_analytic_free_water_jacobian(fraction):
    design = gradients()
    parameters = np.array([.0012, .00005, .0004, -.00002, .00001, .0003, -np.log(900), np.arccos(1-2*fraction)])
    numeric = approx_derivative(lambda p: ind.fw_prediction(p, design), parameters, method="3-point", abs_step=1e-8)
    analytic = ind.fw_jacobian(parameters, design)
    np.testing.assert_allclose(analytic, numeric, rtol=2e-6, atol=2e-5)
    assert ind.fw_prediction(parameters, design)[0] == pytest.approx(900)


def test_intercept_changes_both_signal_components():
    design = gradients()
    parameters = np.array([.0012, 0, .0005, 0, 0, .0003, -np.log(900), 1.2])
    altered = parameters.copy(); altered[6] -= np.log(2)
    np.testing.assert_allclose(ind.fw_prediction(altered, design), 2*ind.fw_prediction(parameters, design))


def test_initializer_records_low_signal_and_high_md():
    design = gradients()
    assert ind.fw_initializer(np.zeros(len(design)), design, 0)["status"] == "low_signal"
    high_md = np.exp(design@np.array([.0029, 0, .0029, 0, 0, .0029, -np.log(1000)]))
    result = ind.fw_initializer(high_md, design, 1000)
    assert result["status"] == "wls_sentinel"
    assert result["fraction"] == 1
    assert result["parameters"] is None


def test_alternative_nonlinear_solvers_on_identifiable_tiny_fixture():
    design = gradients()
    parameters = np.array([.0012, .00001, .0005, -.00002, .00001, .0003, -np.log(900), np.arccos(.5)])
    signal = ind.fw_prediction(parameters, design)
    result = ind.fit_alternatives(signal, design, 900)
    assert result["initializer"]["status"] == "ready"
    for method in ("lm", "trf"):
        assert result[method]["converged"], result[method]
        assert result[method]["normalized_sse"] < 1e-12
        np.testing.assert_allclose(result[method]["prediction"], signal, atol=1e-4)


def test_voxel_sigma_has_no_spatial_unit_conversion():
    assert ind.SIGMA_VOXELS == pytest.approx(.26541306259000597)


def test_physical_fraction_jacobian_is_not_periodic_derivative():
    design = gradients()
    beta = np.array([.0012, .00001, .0005, -.00002, .00001, .0003, -np.log(900)])
    parameters = np.r_[beta, .25]
    numeric = approx_derivative(lambda p: ind.physical_prediction(p[:7], p[7], design), parameters,
                                method="3-point", abs_step=1e-8)
    np.testing.assert_allclose(ind.physical_jacobian(beta, .25, design), numeric, rtol=2e-6, atol=2e-5)


def test_failed_diagnostics_are_preserved_as_json_null():
    data = ind.json_safe({"status": "failed", "coefficients": np.array([1., np.nan, np.inf]),
                         "attempted": np.bool_(True)})
    assert data == {"status": "failed", "coefficients": [1., None, None], "attempted": True}


def test_checks_do_not_hide_nan_finite_mismatch():
    checks = ind.Checks()
    assert not checks.close("nonfinite_mismatch", [np.nan], [1.])
    assert checks.issues == ["nonfinite_mismatch"]
    assert checks.close("both_undefined", [np.nan], [np.nan])


def test_reconstruction_keeps_raw_vs_floored_prediction_distinct():
    design = gradients()
    beta = np.array([.0012, 0, .0005, 0, 0, -.0001, -np.log(900)])
    signal = ind.physical_prediction(beta, .2, design)
    result = ind.reconstruct_fitted_fields(beta, .2, signal, design, "fwdti")
    assert result["n_eigenvalues_clipped"] == 1
    assert result["sse"] == 0
    assert np.max(abs(result["reported_prediction"]-result["prediction"])) > 1
    assert result["jacobian_parameter_count"] == 8


def test_dti_conditioning_has_only_seven_fitted_parameters():
    design = gradients()
    beta = np.array([.0012, 0, .0005, 0, 0, .0003, -np.log(900)])
    signal = np.exp(design@beta)
    result = ind.reconstruct_fitted_fields(beta, 0, signal, design, "dti_b2000")
    assert result["jacobian_parameter_count"] == 7
    assert result["jacobian_rank"] == 7
    assert result["sse"] == 0


def test_unattempted_fit_is_not_fabricated_from_initializer():
    assert ind.reconstruct_fitted_fields(np.full(7, np.nan), np.nan, np.ones(41), gradients(), "fwdti") is None


def fixture_record(model, signal, design, beta, fraction, status="ok"):
    result = ind.reconstruct_fitted_fields(beta, fraction, signal, design, model)
    singular = np.pad(result["scaled_jacobian_singular_values"], (0, 8-result["jacobian_parameter_count"]), constant_values=np.nan)
    result.update(beta=beta, f=fraction, status=status, fit_attempted=True,
                  eligible=status == "ok" and result["nonzero_tensor"] and fraction < 1,
                  optimizer_status=1 if model == "fwdti" else np.nan, nfev=10 if model == "fwdti" else 0,
                  init_f=np.nan, init_md=np.nan, initial_beta=np.full(7, np.nan),
                  initial_raw_beta=np.full(7, np.nan), n_signal_floored=0, observed_b0=float(signal[0]),
                  scaled_jacobian_singular_values=singular)
    result["optimizer_q"] = np.r_[beta, np.arccos(1-2*fraction)] if model == "fwdti" else np.full(8, np.nan)
    return result


def test_all_row_arithmetic_and_failed_candidate_support_are_independent():
    design = gradients()
    beta = np.array([.0012, 0, .0005, 0, 0, .0003, -np.log(900)])
    signal = ind.physical_prediction(beta, .2, design)
    rows = [fixture_record("fwdti", signal, design, beta, .2),
            fixture_record("fwdti", signal, design, beta, .2, status="optimizer_failed")]
    # A finite failed candidate remains in the receipt but never in means.
    rows[1]["optimizer_status"] = 5
    bvals = np.r_[0, np.full(20, 1000), np.full(20, 2000)]
    rng = np.random.RandomState(13); g = rng.normal(size=(40, 3)); g /= np.linalg.norm(g, axis=1)[:, None]
    source = {"signal": np.tile(signal, (2, 1)), "bvals": bvals, "bvecs": np.vstack((np.zeros(3), g))}
    arrays = {"selected_roi_indices": np.arange(2), "roi_ijk": np.array([[1, 2, 3], [1, 2, 4]]),
              "signal_indices_fwdti": np.arange(41), "design_fwdti": design}
    checks = ind.Checks()
    updated, qc = ind.validate_model_arithmetic(source, arrays, "fwdti", rows, checks)
    assert checks.issues == []
    assert qc["n_eligible"] == 1
    assert len(qc["ineligible_rows"]) == 1
    assert np.isfinite(updated[1]["fa"])
    rows[1]["eligible"] = True
    checks = ind.Checks()
    ind.validate_model_arithmetic(source, arrays, "fwdti", rows, checks)
    assert "fwdti.eligible" in checks.issues


def test_summary_uses_selected_intersection_and_null_empty_means():
    def row(fa, valid, status="ok"):
        return {"eligible": valid, "fa": fa, "md": .001, "f": .2, "S0_hat": 900., "nrmse": .01,
                "status": status, "n_eigenvalues_clipped": 0}
    records = {"dti_b1000": [row(.5, True), row(.4, True)],
               "dti_b2000": [row(.6, True), row(.7, False, "optimizer_failed")],
               "fwdti": [row(.8, False, "optimizer_failed"), row(.9, True)]}
    summary, common = ind.compute_summaries(records, "dti_b1000")
    assert summary["fa_proxy_roi"] == pytest.approx(.45)
    assert summary["n_common_valid"] == 0
    assert summary["common_valid"]["by_model"]["fwdti"]["fa_mean"] is None
    assert not common.any()
    pair, common = ind.compute_summaries({key: records[key] for key in ("dti_b1000", "dti_b2000")}, "dti_b1000")
    assert pair["n_common_valid"] == 1
    assert pair["common_valid"]["paired_fa_differences"]["dti_b2000_minus_dti_b1000"] == pytest.approx(.1)


@pytest.mark.parametrize("coordinates", [["1.5", "2", "3"], ["nan", "2", "3"]])
def test_source_coordinate_identity_rejects_rounding(tmp_path, coordinates):
    path = tmp_path/"rows.csv"
    with path.open("w", newline="") as stream:
        writer = csv.writer(stream); writer.writerow(["i", "j", "k", "fa"]); writer.writerow([*coordinates, .5])
    with pytest.raises(ValueError): ind.read_csv_rows(path, ("i", "j", "k"))


def test_duplicate_rows_cannot_be_silently_overwritten(tmp_path):
    path = tmp_path/"rows.csv"
    path.write_text("i,j,k,fa\n1,2,3,.5\n1,2,3,.7\n")
    with pytest.raises(ValueError, match="Duplicate"): ind.read_csv_rows(path, ("i", "j", "k"))


def test_private_record_adapter_preserves_missing_optimizer_status():
    arrays = {"roi_ijk": np.array([[1, 2, 3]]), "beta_dti_b1000": np.ones((1, 7)),
              "optimizer_status_dti_b1000": np.array([np.nan]), "status_dti_b1000": np.array(["ok"]),
              "eligible_dti_b1000": np.array([True]), "design_dti_b1000": np.ones((4, 7)),
              "signal_indices_dti_b1000": np.arange(4), "warnings_json_dti_b1000": np.asarray("[[]]")}
    rows = ind.records_from_arrays(arrays, "dti_b1000")
    assert rows[0]["status"] == "ok"
    assert rows[0]["eligible"] is True
    assert np.isnan(rows[0]["optimizer_status"])
    assert "design" not in rows[0]


def test_summary_accepts_zero_status_entries_but_not_wrong_nonzero_counts():
    checks = ind.Checks()
    ind.check_summary({"ok": 2, "optimizer_failed": 0}, {"ok": 2}, checks, "results.status_counts")
    assert checks.issues == []
    ind.check_summary({"ok": 2, "optimizer_failed": 1}, {"ok": 2}, checks, "results.status_counts")
    assert checks.issues


def test_public_receipt_integration_accepts_reordering_and_rejects_fake_summary(tmp_path):
    design = gradients()
    beta = np.array([.0012, 0, .0005, 0, 0, .0003, -np.log(900)])
    signal = ind.physical_prediction(beta, .2, design)
    records = {model: [fixture_record(model, signal, design, beta, .2 if model == "fwdti" else 0.)]
               for model in ("fwdti", "dti_b2000")}
    ijk = np.array([[1, 2, 3]])
    summary, common = ind.compute_summaries(records, "fwdti")
    summary["status"] = "resource_pilot"
    (tmp_path/"results.json").write_text(json.dumps(summary))
    (tmp_path/"findings.md").write_text("Synthetic mechanics fixture; not a source result.")
    beta_fields = ("Dxx", "Dxy", "Dyy", "Dxz", "Dyz", "Dzz", "neg_log_S0")
    scalar_fields = ("S0_hat", "f", "fa", "md", "sse", "nrmse", "n_eigenvalues_clipped",
                     "optimizer_status", "nfev", "init_f", "init_md", "n_signal_floored",
                     "observed_b0", "normalization_scale")
    bool_fields = ("fit_attempted", "eligible", "boundary_f_low", "boundary_f_high")

    def write_rows(name, fields, rows):
        with (tmp_path/name).open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(reversed(fields)))
            writer.writeheader()
            for row in reversed(rows):
                writer.writerow({key: "" if isinstance(value, (float, np.floating)) and not np.isfinite(value) else value
                                 for key, value in row.items()})

    rows = []
    for model, model_rows in records.items():
        row = model_rows[0]
        output = {"model": model, "i": 1, "j": 2, "k": 3, "status": row["status"], "common_valid": bool(common[0])}
        output.update(dict(zip(beta_fields, row["beta"])))
        output.update({field: row[field] for field in scalar_fields+bool_fields})
        rows.append(output)
    write_rows("fit_parameters.csv", tuple(rows[0]), rows)
    write_rows("fa_sweep.csv", ("i", "j", "k", "model", "fa"),
               [{"i": 1, "j": 2, "k": 3, "model": model, "fa": value[0]["fa"]} for model, value in records.items()])
    write_rows("fa_voxelwise.csv", ("i", "j", "k", "fa"), [{"i": 1, "j": 2, "k": 3, "fa": records["fwdti"][0]["fa"]}])
    metadata = {"main_model": "fwdti", "status": "resource_pilot", "n_roi_voxels": 1, "n_common_valid": 1}
    checks = ind.Checks()
    ind.validate_public(tmp_path, records, ijk, metadata, checks)
    assert checks.issues == []
    summary["fa_proxy_roi"] += .1
    (tmp_path/"results.json").write_text(json.dumps(summary))
    checks = ind.Checks()
    ind.validate_public(tmp_path, records, ijk, metadata, checks)
    assert "results.fa_proxy_roi" in checks.issues
