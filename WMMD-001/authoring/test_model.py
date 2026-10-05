"""Small equation/mechanics fixtures only; never a substitute scientific bank."""
import csv
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

SPEC = importlib.util.spec_from_file_location("wmmd_independent", Path(__file__).with_name("check_independent.py"))
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)


def acquisition(n=72):
    rng = np.random.default_rng(4181)
    directions = rng.normal(size=(n, 3))
    directions /= np.linalg.norm(directions, axis=1)[:, None]
    directions[0] = 0
    b = np.resize(np.array([400., 800., 1200., 1800., 2400., 3000.]), n)
    b[0] = 0
    return b, directions


def parameters(kurtosis=False, n=3):
    beta = np.zeros((n, 22 if kurtosis else 7))
    beta[:, :6] = [1.2e-3, 5e-5, 6e-4, -2e-5, 3e-5, 3e-4]
    beta[:, -1] = -np.log(np.linspace(50, 130, n))
    if kurtosis:
        beta[:, 6:9] = [2e-7, 1e-7, 5e-8]
        beta[:, 9:21] = np.linspace(-1e-8, 1e-8, 12)
    return beta


@pytest.mark.parametrize("kurtosis", [False, True])
def test_manual_design_matches_pinned_dipy(kurtosis):
    from dipy.core.gradients import gradient_table
    from dipy.reconst import dti, dki
    b, g = acquisition()
    g[1] *= 1.0000001  # Source gradients must not silently be renormalized.
    gtab = gradient_table(b, bvecs=g, b0_threshold=50)
    expected = dki.design_matrix(gtab) if kurtosis else dti.design_matrix(gtab)
    np.testing.assert_allclose(CHECK.manual_design(b, g, kurtosis), expected, atol=1e-8, rtol=1e-14)


@pytest.mark.parametrize("bad", ["shape", "negative_b", "nonfinite_g"])
def test_bad_gradient_inputs_fail(bad):
    b, g = acquisition()
    if bad == "shape":
        g = g.T
    elif bad == "negative_b":
        b[4] = -1
    else:
        g[4, 1] = np.nan
    with pytest.raises(AssertionError):
        CHECK.manual_design(b, g)


@pytest.mark.parametrize("kurtosis", [False, True])
def test_gelsd_recovers_exact_finite_model(kurtosis):
    b, g = acquisition()
    a = CHECK.manual_design(b, g, kurtosis)
    beta = parameters(kurtosis)
    signal = np.exp(beta @ a.T)
    fitted, ranks = CHECK.gelsd_wls(a, signal)
    CHECK.check_coefficients(fitted, beta)
    assert np.all(ranks == a.shape[1])
    metric = CHECK.evaluate_coefficients(fitted, a, signal, signal[:, 0])
    assert np.max(metric["nrmse"]) < 1e-9
    assert np.max(metric["log_rmse"]) < 1e-9
    assert not metric["n_signal_floored"].any()
    assert not metric["n_eigenvalues_floored"].any()


@pytest.mark.parametrize("kurtosis", [False, True])
def test_gelsd_matches_explicit_two_pass_pinv_and_dipy(kurtosis):
    b, g = acquisition()
    a = CHECK.manual_design(b, g, kurtosis)
    beta = parameters(kurtosis)
    signal = np.exp(beta @ a.T)*(1+.015*np.sin(np.arange(len(b)))[None, :])
    fitted, _ = CHECK.gelsd_wls(a, signal)
    y = np.log(np.maximum(signal, CHECK.SIGNAL_FLOOR))
    initial = y @ np.linalg.pinv(a, rcond=1e-15).T
    weights = np.exp(initial @ a.T)
    other = np.array([np.linalg.pinv(a*w[:, None], rcond=1e-15) @ (row*w)
                      for row, w in zip(y, weights)])
    CHECK.check_coefficients(fitted, other)
    CHECK.dipy_helper_sanity(a, signal, fitted, kurtosis)


@pytest.mark.parametrize("kurtosis", [False, True])
@pytest.mark.parametrize("chunk_size", [1, 2, 256])
def test_oracle_chunked_formula_matches_separate_small_fixture(kurtosis, chunk_size):
    # The checker itself never imports the oracle. This unit test separately
    # exercises the implementation under test on a tiny, non-scientific fixture.
    spec = importlib.util.spec_from_file_location(
        "wmmd_oracle_fixture", Path(__file__).resolve().parents[1]/"solution/compute.py")
    oracle = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(oracle)
    b, g = acquisition()
    a = CHECK.manual_design(b, g, kurtosis)
    beta = parameters(kurtosis)
    signal = np.exp(beta @ a.T)*(1+.025*np.cos(np.arange(len(b)))[None, :])
    actual = oracle.fit_raw_wls(a, signal, chunk_size=chunk_size)
    expected, _ = CHECK.gelsd_wls(a, signal)
    CHECK.check_coefficients(actual, expected)
    theirs = oracle.derive_fit(a, signal, actual, signal[:, 0])
    ours = CHECK.evaluate_coefficients(actual, a, signal, signal[:, 0])
    for key in CHECK.METRIC_COLUMNS:
        np.testing.assert_allclose(theirs[key], ours[key], atol=1e-12, rtol=1e-12)


@pytest.mark.parametrize("kurtosis", [False, True])
def test_raw_and_post_floor_predictions_are_distinct(kurtosis):
    b, g = acquisition()
    a = CHECK.manual_design(b, g, kurtosis)
    beta = parameters(kurtosis, n=1)
    beta[0, :6] = [8e-4, 0, 4e-4, 0, 0, -1e-4]
    raw_prediction = np.exp(beta @ a.T)
    metric = CHECK.evaluate_coefficients(beta, a, raw_prediction, raw_prediction[:, 0])
    assert metric["n_eigenvalues_floored"].tolist() == [1]
    assert metric["log_rmse"][0] == pytest.approx(0, abs=1e-14)
    assert metric["nrmse"][0] > 0
    assert np.max(np.abs(metric["predicted"]-raw_prediction)) > .01
    assert np.array_equal(metric["post_beta"][:, 6:], beta[:, 6:])
    assert metric["md"][0] == pytest.approx((.0008+.0004+metric["eigenvalue_floor"])*1000/3)


def test_fitted_s0_is_used_for_dki_prediction():
    from dipy.core.gradients import gradient_table
    from dipy.reconst.dki import dki_prediction, params_to_dki_params
    b, g = acquisition()
    a = CHECK.manual_design(b, g, True)
    beta = parameters(True, n=1)
    beta[0, :6] = [8e-4, 0, 4e-4, 0, 0, -1e-4]
    observed = np.exp(beta @ a.T)
    metric = CHECK.evaluate_coefficients(beta, a, observed, observed[:, 0])
    converted = params_to_dki_params(beta[0], min_diffusivity=metric["eigenvalue_floor"])
    gtab = gradient_table(b, bvecs=g, b0_threshold=50)
    expected = dki_prediction(converted[:-1], gtab, S0=converted[-1])
    np.testing.assert_allclose(metric["predicted"][0], expected, atol=1e-10, rtol=1e-12)
    wrong = dki_prediction(converted[:-1], gtab)
    assert np.max(np.abs(expected-wrong)) > 1


@pytest.mark.parametrize("b0", [0., -3., 1e-4, 2.])
def test_observed_b0_normalization_floor_and_source_clipping(b0):
    b, g = acquisition()
    a = CHECK.manual_design(b, g)
    beta = parameters(False, n=1)
    signal = np.exp(beta @ a.T)
    signal[0, :4] = [0, -2, CHECK.SIGNAL_FLOOR, CHECK.SIGNAL_FLOOR/2]
    metric = CHECK.evaluate_coefficients(beta, a, signal, np.array([b0]))
    assert metric["normalization_scale"][0] == max(b0, CHECK.SIGNAL_FLOOR)
    assert metric["n_signal_floored"][0] == 3
    assert np.isfinite(metric["nrmse"]).all()


def test_isotropic_fa_is_zero():
    b, g = acquisition()
    a = CHECK.manual_design(b, g)
    beta = parameters(False, n=1)
    beta[0, :6] = [.0007, 0, .0007, 0, 0, .0007]
    signal = np.exp(beta @ a.T)
    metric = CHECK.evaluate_coefficients(beta, a, signal, signal[:, 0])
    assert metric["fa"][0] == pytest.approx(0, abs=1e-15)
    assert metric["md"][0] == pytest.approx(.7)


def test_rotated_tensor_has_identical_md_fa_without_eigenvector_gate():
    b, g = acquisition()
    a = CHECK.manual_design(b, g)
    beta = parameters(False, n=2)
    q, _ = np.linalg.qr(np.array([[1., 3., 2.], [4., -2., 1.], [-3., 1., 4.]]))
    tensor = CHECK.tensor_from_beta(beta[:1])[0]
    rotated = q @ tensor @ q.T
    beta[1, :6] = [rotated[0, 0], rotated[0, 1], rotated[1, 1], rotated[0, 2], rotated[1, 2], rotated[2, 2]]
    signal = np.exp(beta @ a.T)
    metric = CHECK.evaluate_coefficients(beta, a, signal, signal[:, 0])
    assert metric["md"][0] == pytest.approx(metric["md"][1], abs=1e-14)
    assert metric["fa"][0] == pytest.approx(metric["fa"][1], abs=1e-14)


@pytest.mark.parametrize("case", ["nan_beta", "inf_source", "overflow"])
def test_invalid_or_overflowing_fit_fails_closed(case):
    b, g = acquisition()
    a = CHECK.manual_design(b, g)
    beta = parameters(False, n=1)
    signal = np.exp(beta @ a.T)
    if case == "nan_beta":
        beta[0, 0] = np.nan
    elif case == "inf_source":
        signal[0, 1] = np.inf
    else:
        beta[0, -1] = -1000
    with pytest.raises((AssertionError, FloatingPointError)):
        CHECK.evaluate_coefficients(beta, a, signal, signal[:, 0])


@pytest.mark.parametrize("n", [1, 17, 256, 257, 10105])
def test_sampling_is_fixed_evenly_spaced_unique_and_c_order(n):
    selected = CHECK.sampled_indices(n)
    assert len(selected) == min(256, n)
    assert selected[0] == 0 and selected[-1] == n-1
    assert np.all(np.diff(selected) > 0)


@pytest.mark.parametrize("wrapper", ["selected", "direct_collection", "configs_collection"])
def test_config_specific_public_metadata_template(wrapper):
    contract = {"pipeline_id": CHECK.PIPELINE, "model_config": "dti_lowb", "fit": {"method": "WLS"}}
    document = contract if wrapper == "selected" else {"dti_lowb": contract}
    if wrapper == "configs_collection":
        document = {"configs": document}
    assert CHECK.select_public_contract(document, "dti_lowb") == contract
    with pytest.raises((AssertionError, KeyError)):
        CHECK.select_public_contract(document, "dki_all")


def test_descriptive_distribution_preserves_zeros_negatives_and_large_values():
    values = np.array([-2., 0., 0., 2., 1e8])
    result = CHECK.distribution(values)
    assert result["n"] == 5 and result["n_negative"] == 1 and result["n_zero"] == 2
    assert result["mean"] == float(values.mean())
    assert result["quantiles"]["max"] == 1e8
    assert result["quantiles"]["median"] == 0
    assert CHECK.distribution([])["mean"] is None
    with pytest.raises(AssertionError):
        CHECK.distribution([1, np.inf])


def test_normalization_diagnostics_keep_both_groups_without_filtering():
    evaluated = {"observed_b0": np.array([0., 100., 50.]),
                 "normalization_scale": np.array([1e-4, 100., 50.]),
                 "nrmse": np.array([1e5, .3, .4]), "log_rmse": np.array([2., .2, .3]),
                 "n_signal_floored": np.array([2, 0, 1]),
                 "n_eigenvalues_floored": np.array([1, 0, 0])}
    result = CHECK.diagnostics(evaluated)
    assert result["n_normalization_scales_floored"] == 1
    assert result["distributions"]["nrmse"]["n"] == 3
    assert result["nrmse_by_normalization_floor"]["floored"]["mean"] == 1e5
    assert result["nrmse_by_normalization_floor"]["not_floored"]["n"] == 2
    assert sum(row["n_voxels"] for row in result["floor_count_histograms"]["n_signal_floored"]) == 3
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("config", ["dki_all", "dti_lowb", "dti_all"])
def test_independent_artifact_preserves_selected_rows_and_raw_coefficients(tmp_path, config):
    ijk = np.array([[0, 0, 0], [0, 0, 1], [0, 1, 0], [1, 0, 0]])
    indices = np.array([0, 3])
    beta = parameters(config == "dki_all", n=2)
    path = CHECK.save_independent_coefficients(tmp_path, config, ijk, indices, beta, {"source": "hash"})
    assert path.name == f"independent_coefficients_{config}.npz"
    with np.load(path, allow_pickle=False) as receipt:
        assert str(receipt["model_config"].item()) == config
        assert str(receipt["pipeline_id"].item()) == CHECK.PIPELINE
        assert int(receipt["n_roi_voxels"].item()) == len(ijk)
        assert json.loads(str(receipt["source_sha256_json"].item())) == {"source": "hash"}
        np.testing.assert_array_equal(receipt["roi_row_indices"], indices)
        np.testing.assert_array_equal(receipt["roi_ijk"], ijk[indices])
        np.testing.assert_array_equal(receipt["beta"], beta)


def csv_fixture(path, mutation=None):
    ijk = np.array([[0, 1, 2], [2, 4, 3]])
    fields = ["i", "j", "k"] + list(CHECK.METRIC_COLUMNS) + [f"beta_{i}" for i in range(7)]
    rows = [{field: "0" for field in fields} for _ in range(2)]
    for row, coord in zip(rows, ijk):
        row.update({key: f"{float(value)}" for key, value in zip(("i", "j", "k"), coord)})
    if mutation == "duplicate":
        rows[1] = rows[0].copy()
    elif mutation == "fractional":
        rows[0]["i"] = ".1"
    elif mutation == "missing":
        rows.pop()
    elif mutation == "padding":
        rows.append(rows[0].copy())
    elif mutation == "foreign":
        rows[0]["k"] = "9"
    elif mutation == "fractional_count":
        rows[0]["n_eigenvalues_floored"] = ".5"
    elif mutation == "nan":
        rows[0]["fa"] = "nan"
    elif mutation == "missing_column":
        fields.remove("fa")
        for row in rows:
            del row["fa"]
    elif mutation == "extra_column":
        fields.append("comment")
        for row in rows:
            row["comment"] = "harmless"
    elif mutation == "row_order":
        rows.reverse()
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return ijk


@pytest.mark.parametrize("case", [None, "row_order", "extra_column"])
def test_complete_keyed_csv_accepts_harmless_format_variants(tmp_path, case):
    path = tmp_path/"rows.csv"
    ijk = csv_fixture(path, case)
    _, beta = CHECK.read_voxels(path, ijk, 7)
    assert beta.shape == (2, 7)


@pytest.mark.parametrize("case", ["duplicate", "fractional", "missing", "padding", "foreign",
                                "fractional_count", "nan", "missing_column"])
def test_incomplete_or_invalid_csv_fails(tmp_path, case):
    path = tmp_path/"rows.csv"
    ijk = csv_fixture(path, case)
    with pytest.raises(AssertionError):
        CHECK.read_voxels(path, ijk, 7)
