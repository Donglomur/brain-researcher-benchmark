"""Parser, algebra and public-contract mechanics on explicit tiny fixtures."""
import json

import numpy as np
import pytest

from test_scale import small_reference, output, write_output, read_rows, write_rows, q
from build_reference import verify_wls_normal_equations


@pytest.mark.parametrize("value", ["", None, True, False, "NaN", "inf", "1.01"])
def test_integer_rejects_invalid(value):
    with pytest.raises(AssertionError): q.integer(value, "test")


@pytest.mark.parametrize("value", [1, 1., "1", "1.0", "1e0"])
def test_integer_notation(value):
    assert q.integer(value, "test") == 1


@pytest.mark.parametrize("mutation", ["drop", "duplicate", "fractional_coord", "outside", "nonfinite", "missing_beta", "fractional_floor", "negative_floor"])
def test_bad_voxel_table(output, small_reference, mutation):
    rows = read_rows(output)
    if mutation == "drop": rows.pop()
    elif mutation == "duplicate": rows.append(dict(rows[0]))
    elif mutation == "fractional_coord": rows[0]["i"] = .1
    elif mutation == "outside": rows[0]["k"] = 1
    elif mutation == "nonfinite": rows[0]["beta_0"] = "nan"
    elif mutation == "missing_beta":
        for row in rows: del row["beta_21"]
    elif mutation == "fractional_floor": rows[0]["n_signal_floored"] = .5
    elif mutation == "negative_floor": rows[0]["n_eigenvalues_floored"] = -1
    write_rows(output, rows)
    with pytest.raises(AssertionError): q.validate_output_directory(output, small_reference)


@pytest.mark.parametrize("key", q.METRICS)
def test_every_derived_voxel_field_is_checked(output, small_reference, key):
    rows = read_rows(output); rows[0][key] = float(rows[0][key]) + 1
    write_rows(output, rows)
    with pytest.raises(AssertionError): q.validate_output_directory(output, small_reference)


def test_csv_order_integer_notation_extras_and_free_prose(output, small_reference):
    rows = read_rows(output)
    for row in rows:
        for key in ("i", "j", "k", *q.INTEGER_METRICS): row[key] = f'{int(row[key])}.0'
        row["comment"] = "ignored"
    write_rows(output, rows[::-1], list(rows[0])[::-1])
    (output/"findings.md").write_text("Numerical measurements are attached.")
    q.validate_output_directory(output, small_reference)


@pytest.mark.parametrize("key", ["md_mean", "fa_mean", "S0_hat_mean", "nrmse_mean", "log_rmse_mean",
                                 "n_wm_voxels", "n_signal_floored_total", "n_eigenvalues_floored_total",
                                 "n_voxels_signal_floored", "n_voxels_eigenvalues_floored"])
def test_all_summary_fields_recomputed(output, small_reference, key):
    path = output/"diffusivity.json"; result = q.load_json(path)
    result[key] += max(10, abs(result[key])*.1)
    path.write_text(json.dumps(result))
    with pytest.raises(AssertionError, match="summary"):
        q.validate_output_directory(output, small_reference)


@pytest.mark.parametrize("key,value", [("status", "failed_precondition"), ("pipeline_id", "old"),
                                       ("n_wm_voxels", 1), ("n_brain_voxels", 1),
                                       ("source_sha256", {}), ("model_config", "dti_all")])
def test_bad_metadata(output, small_reference, key, value):
    path = output/"run_metadata.json"; result = q.load_json(path); result[key] = value
    path.write_text(json.dumps(result))
    with pytest.raises(AssertionError): q.validate_output_directory(output, small_reference)


@pytest.mark.parametrize("file", q.FILES)
def test_missing_file(output, small_reference, file):
    (output/file).unlink()
    with pytest.raises(AssertionError): q.validate_output_directory(output, small_reference)


def test_empty_findings(output, small_reference):
    (output/"findings.md").write_text(" \n")
    with pytest.raises(AssertionError, match="empty findings"):
        q.validate_output_directory(output, small_reference)


def test_raw_tensor_floor_and_intercept_mechanics(small_reference):
    entry = small_reference["configs"]["dki_all"]
    assert entry["n_eigenvalues_floored"][0] == 1
    assert entry["n_signal_floored"][0] == 2
    assert entry["observed_b0"][0] == 0 and entry["normalization_scale"][0] == 1e-4
    np.testing.assert_allclose(entry["S0_hat"], np.arange(100, 160, 10))
    floor = 1e-6 / (-entry["design"].min())
    assert entry["md"][0] == pytest.approx((floor+.0006+.0003)/3*1000)


def test_design_column_multiplicity_and_intercept():
    b = np.array([0., 1200.]); g = np.array([[0,0,0], [1,2,3]], float)
    matrix = q.design_matrix(b, g, "dki_all")
    np.testing.assert_array_equal(matrix[0, :-1], 0)
    np.testing.assert_array_equal(matrix[:, -1], -1)
    assert matrix[1, 1] == -2*1200*2
    assert matrix[1, 6+12] == 1200**2/6*12*1**2*2*3


def test_nonfinite_exponential_is_rejected(small_reference):
    entry = small_reference["configs"]["dti_all"]
    beta = entry["beta"].copy(); beta[:, -1] = -10000
    with pytest.raises(AssertionError, match="S0"):
        q.derive(beta, small_reference["signal"], entry["design"], small_reference["bvals"])


def test_legacy_bank_pipeline_is_rejected(small_reference):
    small_reference["stats"]["pipeline_id"] = "old-correlation-control"
    with pytest.raises(AssertionError): q.validate_reference(small_reference)


def test_builder_weighted_normal_equation_mechanical_identity():
    design = np.array([[-1., -1.], [0., -1.], [1., -1.]])
    beta = np.array([[.1, -1.], [.2, -1.2]])
    signal = np.exp(beta @ design.T)
    assert verify_wls_normal_equations(design, signal, beta) < 1e-12
    with pytest.raises(AssertionError, match="WLS normal equations"):
        verify_wls_normal_equations(design, signal, beta+.1)


def test_tiny_recipe_number_uses_relative_not_absolute_tolerance():
    q.match_metadata({"fit": {"pinv_rcond": 1e-15}}, {"fit": {"pinv_rcond": 1e-15}})
    with pytest.raises(AssertionError, match="recipe"):
        q.match_metadata({"fit": {"pinv_rcond": 0}}, {"fit": {"pinv_rcond": 1e-15}})
