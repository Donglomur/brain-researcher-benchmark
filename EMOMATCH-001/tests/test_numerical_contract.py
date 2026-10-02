"""Manufactured numerical contracts only: no originals, old bank or oracle."""
from decimal import Decimal
import copy

import numpy as np
import pandas as pd
import pytest
from scipy import linalg, stats
from nilearn.glm.first_level.design_matrix import make_first_level_design_matrix

import numerical_contract as n


@pytest.mark.parametrize("value", [0., .1, -3., 1e100])
@pytest.mark.parametrize("frames", [1, 3, 135])
def test_exact_constant_not_tiny_invented_signal(value, frames):
    result = n.normalization(np.full((frames, 2), value))
    assert result["exact_constant"].all()
    np.testing.assert_array_equal(result["mean"], [value, value])
    np.testing.assert_array_equal(result["sd"], [0., 0.])
    np.testing.assert_array_equal(result["normalized"], np.zeros((frames, 2)))
    np.testing.assert_array_equal(result["denominator"], [1e-8, 1e-8])


@pytest.mark.parametrize("scale", [1e-12, 1., 1e9])
def test_population_sd_plus_source_unit_floor(scale):
    values = np.array([[-2.], [0.], [2.]]) * scale
    result = n.normalization(values)
    np.testing.assert_allclose(result["sd"], np.sqrt(8/3)*scale, rtol=1e-14)
    np.testing.assert_allclose(result["normalized"], values/(np.sqrt(8/3)*scale+1e-8), rtol=1e-14)


def test_nearconstant_is_not_exactconstant():
    values = (1+1e-12*np.array([-1., 1., -1., 1.]))[:, None]
    result = n.normalization(values)
    assert not result["exact_constant"][0]
    assert np.max(np.abs(result["normalized"])) > 1e-5


@pytest.mark.parametrize("bad", [True, np.bool_(False), "1", 1+0j, np.nan, np.inf, -np.inf])
def test_strict_types_before_mixed_casting(bad):
    with pytest.raises((ValueError, TypeError)):
        n.array([[1., 2.], [3., bad]], 2)
    with pytest.raises((ValueError, TypeError)):
        n.complete_summary([1.]*19+[bad])
    with pytest.raises((ValueError, TypeError)):
        n.paired_summary([1.]*19+[bad], [2.]*20)
    with pytest.raises((ValueError, TypeError)):
        n.paired_summary([None]*20, [2.]*19+[bad])


def test_real_decimal_allowed_but_object_arrays_not():
    assert n.scalar(Decimal("1.25")) == 1.25
    with pytest.raises(ValueError):
        n.array(np.array([1., 2.], dtype=object))


def test_arithmetic_overflow_fails_not_missing():
    with pytest.raises((OverflowError, FloatingPointError, ValueError)):
        n.normalization([[1e308], [-1e308]])


def test_missing_confounds_mean_and_allmissing_zero():
    raw = np.array([[1., 99., 2.], [3., 99., 4.], [0., 99., 6.]])
    mask = np.array([[False, True, False], [False, True, False], [True, True, False]])
    result = n.impute_confounds(raw, mask)
    np.testing.assert_array_equal(result["effective"], [[1., 0., 2.], [3., 0., 4.], [2., 0., 6.]])
    np.testing.assert_array_equal(result["all_missing"], [False, True, False])
    np.testing.assert_array_equal(raw[:, 1], [99., 99., 99.])


@pytest.mark.parametrize("bad_mask", [[0, 1], [False], ["false", "true"]])
def test_mask_types_and_shape(bad_mask):
    with pytest.raises(ValueError):
        n.duration_models([1., 0.], bad_mask)


def test_rt_median_missing_and_equal_arms():
    result = n.duration_models([.5, 0., 1.5, 2.5, 3.5], [False, True, False, False, False])
    assert result["median"] == 2.
    np.testing.assert_array_equal(result["modelA"], np.full(5, 2.))
    np.testing.assert_array_equal(result["modelB"], [.5, 2, 1.5, 2.5, 3.5])
    equal = n.duration_models([1., 1.], [False, False])
    np.testing.assert_array_equal(equal["modelA"], equal["modelB"])


@pytest.mark.parametrize("rt,missing", [([0.], [False]), ([-1.], [False]), ([0.], [True]),
                                      ([True, 1.], [False, False]), ([np.nan], [True]),
                                      ([np.inf], [False])])
def test_invalid_or_allmissing_rt(rt, missing):
    with pytest.raises(ValueError): n.duration_models(rt, missing)


def design_inputs():
    onsets = np.arange(48)*5.+10
    conditions = np.where((np.arange(48)//6) % 2, "emotion", "control")
    return onsets, conditions


def test_explicit_unregularized_design_and_column_names():
    onsets, conditions = design_inputs()
    result = n.design(onsets, np.ones(48), conditions, 135, np.zeros((135, 13)))
    assert result["matrix"].shape == (135, 20)
    assert result["column_keys"][:2] == ["control", "emotion"]
    assert result["column_keys"][-14:-1] == list(n.CONFOUNDS)
    assert result["column_keys"][-1] == "constant"
    assert result["condition_present"].all()
    np.testing.assert_array_equal(result["frame_times"], 2*np.arange(135))
    np.testing.assert_array_equal(result["contrast"][:2], [-1., 1.])
    assert not result["warnings"]


def test_design_matches_builder_only_where_fullrank_not_triggered():
    onsets, conditions = design_inputs()
    duration = .8 + .1*np.sin(np.arange(48))
    result = n.design(onsets, duration, conditions, 135, np.zeros((135, 13)))
    ordinary = make_first_level_design_matrix(
        2*np.arange(135), pd.DataFrame({"onset": onsets, "duration": duration, "trial_type": conditions}),
        hrf_model="spm", drift_model="cosine", high_pass=.008, oversampling=50, min_onset=-24)
    columns = [result["column_keys"].index(name) for name in ordinary.columns]
    np.testing.assert_allclose(result["matrix"][:, columns], ordinary.to_numpy(), atol=1e-14, rtol=1e-13)


def test_no_regularization_of_zero_nuisance_columns():
    onsets, conditions = design_inputs()
    result = n.design(onsets, np.ones(48), conditions, 135, np.zeros((135, 13)))
    positions = [result["column_keys"].index(name) for name in n.CONFOUNDS]
    np.testing.assert_array_equal(result["matrix"][:, positions], np.zeros((135, 13)))
    fit = n.fit_svd(result["matrix"], np.ones((135, 2)), result["contrast"])
    assert fit["design_rank"] < result["matrix"].shape[1]
    assert fit["contrast_estimable"] and fit["status"] == "ok"


def test_no_new_source_onset_rule_warnings_retained():
    result = n.design([-30., 10.], [1., 1.], ["control", "emotion"], 135, np.zeros((135, 13)))
    assert result["warnings"]
    assert all(set(w) == {"category", "message"} for w in result["warnings"])


@pytest.mark.parametrize("bad", [True, 135., "135", 1])
def test_frame_count_exact_type(bad):
    with pytest.raises(ValueError):
        n.design([1., 10.], [1., 1.], ["control", "emotion"], bad, np.zeros((135, 13)))


def test_missing_condition_retained_finite_placeholders():
    result = n.design([10.], [1.], ["control"], 135, np.zeros((135, 13)))
    fit = n.fit_svd(result["matrix"], np.ones((135, 3)), result["contrast"],
                    condition_present=result["condition_present"])
    assert fit["status"] == "missing_condition"
    assert not fit["contrast_defined"].any()
    np.testing.assert_array_equal(fit["contrast_estimate"], np.zeros(3))
    assert np.isfinite(fit["beta"]).all()


@pytest.mark.parametrize("factor,rank", [(.25, 1), (.99, 1), (1., 1), (1.01, 2), (4., 2)])
def test_rank_boundary_strict(factor, rank):
    x = np.diag([1., 3*n.EPS*factor, 0.])
    fit = n.fit_svd(x, np.eye(3), [0., 1., 0.])
    assert fit["design_rank"] == rank
    assert fit["contrast_estimable"] == (rank == 2)
    assert fit["contrast_defined"].all() == (rank == 2)


def test_estimable_rankdeficient_public_minimum_norm():
    time = np.linspace(-1, 1, 40)
    x = np.column_stack([time, np.ones(40), np.ones(40)])
    fit = n.fit_svd(x, (3*time+4)[:, None], [1., 0., 0.])
    assert fit["status"] == "ok" and fit["design_rank"] == 2
    np.testing.assert_allclose(fit["beta"][:, 0], [3., 2., 2.], atol=1e-13)
    assert fit["residual_df"] == 38
    shifted = fit["beta"] + np.array([[0.], [1.], [-1.]])
    np.testing.assert_allclose(x@shifted, x@fit["beta"], atol=1e-13)
    with pytest.raises(ValueError, match="public tolerance"):
        n.check_close(shifted, fit["beta"], label="minimum-norm beta")


def test_nonestimable_and_rankzero():
    x = np.column_stack([np.arange(10), np.ones(10), np.ones(10)])
    fit = n.fit_svd(x, np.ones((10, 2)), [0., 1., -1.])
    assert fit["status"] == "contrast_nonestimable"
    assert not fit["contrast_defined"].any()
    zero = n.fit_svd(np.zeros((10, 3)), np.ones((10, 2)), [1., 0., 0.])
    assert zero["design_rank"] == 0 and zero["residual_df"] == 10
    np.testing.assert_array_equal(zero["beta"], np.zeros((3, 2)))


@pytest.mark.parametrize("driver", ["gelsd", "gelsy", "gelss"])
def test_equivalent_lapack_solvers(driver):
    rng = np.random.default_rng(186)
    x, y = rng.normal(size=(135, 20)), rng.normal(size=(135, 111))
    c = np.r_[[-1., 1.], np.zeros(18)]
    fit = n.fit_svd(x, y, c)
    alternative = linalg.lstsq(x, y, cond=max(x.shape)*n.EPS, lapack_driver=driver)[0]
    n.check_close(alternative, fit["beta"])
    n.check_close(c@alternative, fit["contrast_estimate"])


def test_exactzero_response_zero_all111_contrasts():
    x = np.column_stack([np.arange(20), np.ones(20)])
    fit = n.fit_svd(x, np.zeros((20, 111)), [1., 0.])
    assert fit["contrast_defined"].all()
    np.testing.assert_array_equal(fit["beta"], np.zeros((2, 111)))
    np.testing.assert_array_equal(fit["contrast_estimate"], np.zeros(111))


@pytest.mark.parametrize("value", [-2., 0., .1, 7.])
def test_complete_exact_constant_group(value):
    result = n.complete_summary([value]*20)
    assert result["status"] == "zero_variance"
    assert result["mean"] == value and result["sample_sd"] == 0.
    assert result["ci95"] == [value, value]
    assert result["df"] == 19 and result["t"] is None and result["p"] is None


@pytest.mark.parametrize("values,expected,status", [([], 0, "insufficient_n"),
                                                  ([1.], 1, "insufficient_n"),
                                                  ([None]*20, 20, "incomplete_support"),
                                                  ([1.]*19+[None], 20, "incomplete_support")])
def test_undefined_group_accounting(values, expected, status):
    result = n.complete_summary(values, expected)
    assert result["status"] == status
    assert result["ci95"] is None and result["t"] is None
    if status == "incomplete_support": assert result["mean"] is None


def test_group_signed_paired_t19_ci_and_no_direction_gate():
    a = np.arange(20, dtype=float)
    b = a + np.linspace(-3., 1., 20)
    result = n.paired_summary(a, b)
    expected = stats.ttest_rel(b, a)
    assert result["mean"] < 0
    assert result["t"] == pytest.approx(expected.statistic, abs=1e-13)
    assert result["p"] == pytest.approx(expected.pvalue, abs=1e-14)
    differences = b-a
    half = stats.t.ppf(.975, 19) * differences.std(ddof=1)/np.sqrt(20)
    np.testing.assert_allclose(result["ci95"], [differences.mean()-half, differences.mean()+half], atol=1e-13)


def test_equal_person_not_unequal_trial_weights():
    person_values = [-2.]*10 + [1.]*10
    result = n.complete_summary(person_values)
    assert result["mean"] == -.5
    assert result["mean"] != np.average(person_values, weights=[1]*10+[100]*10)


def test_tiny_nonconstant_group_not_floor_or_zero_variance():
    values = np.linspace(-1., 1., 20)*1e-300
    result = n.complete_summary(values)
    assert result["status"] == "ok" and result["sample_sd"] > 0


def test_accepted_aggregate_authority_can_change_nearzero_group():
    canonical = np.ones(20)
    accepted = canonical + np.linspace(-1, 1, 20)*1e-7
    n.check_close(accepted, canonical)
    assert n.complete_summary(canonical)["status"] == "zero_variance"
    recomputed = n.complete_summary(accepted)
    assert recomputed["status"] == "ok"
    n.validate_summary(recomputed, n.complete_summary(accepted))


def test_cancellation_independent_rounding_uses_propagated_budget():
    reference_beta = np.array([1e8, 1e8])
    submitted_beta = reference_beta + np.array([900., -900.])
    submitted_contrast = 9e-8
    result = n.validate_linear_receipt(submitted_beta, reference_beta, [-1., 1.], submitted_contrast)
    assert abs(result["recomputed"]-submitted_contrast) > 1000
    assert result["allowed_difference"] > abs(result["recomputed"]-submitted_contrast)
    # Both separately source-bound fields are legal. A tight direct comparison
    # would silently revoke the declared beta precision near cancellation.
    with pytest.raises(ValueError):
        n.check_close(submitted_contrast, result["recomputed"])


def test_opposite_endpoint_rounding_and_outside_bound():
    ref = np.array([1., 3.]); w = [.5, .5]
    actual = ref + .9*n.bound(ref, n.FIT_TOL)
    actual_mean = 2. - .9*float(n.bound(2., n.FIT_TOL))
    n.validate_linear_receipt(actual, ref, w, actual_mean)
    with pytest.raises(ValueError, match="linear result"):
        n.validate_linear_receipt(actual, ref, w, 2.+1.1*float(n.bound(2., n.FIT_TOL)))


def test_same_fusiform_offset_not_hidden_by_unchanged_paired_difference():
    a, b = np.linspace(-1, 2, 20), np.linspace(0, 3, 20)
    np.testing.assert_allclose((b+1)-(a+1), b-a)
    with pytest.raises(ValueError, match="public tolerance"):
        n.check_close(a+1, a, label="fusiform modelA")
    with pytest.raises(ValueError, match="linear result"):
        n.validate_linear_receipt([.25, .75], [.25, .75], [.5, .5], 1.5)


def test_public_submitted_magnitude_roundoff_formula():
    budget = n.linear_coherence_bound([1., 2.], [-1., 1.], 1., [1., 2.])
    expected = float(n.bound(1., n.FIT_TOL)) + sum(n.bound([1., 2.], n.FIT_TOL))
    assert budget == expected + 8*n.EPS*2*3


@pytest.mark.parametrize("dimension", [2, 7, 20, 111])
def test_roundoff_dimension_includes_zero_weight_columns(dimension):
    reference = np.full(dimension, 1e8)
    submitted = reference + np.linspace(-100., 100., dimension)
    weights = np.zeros(dimension); weights[0], weights[-1] = -1., 1.
    zero = n.Tolerance(0., 0.)
    result = n.linear_coherence_bound(reference, weights, 0., submitted, zero, zero)
    expected = 8*n.EPS*dimension*sum(abs(weights*submitted))
    assert result == expected


def test_roundoff_uses_submitted_not_reference_magnitude():
    zero = n.Tolerance(0., 0.)
    small = n.linear_coherence_bound([1., 1.], [1., -1.], 0., [1., 1.], zero, zero)
    large = n.linear_coherence_bound([1., 1.], [1., -1.], 0., [100., 100.], zero, zero)
    assert large == 100*small
    # The public wrapper first source-binds each component: magnitude cannot
    # be inflated to evade the separately required source envelopes.
    with pytest.raises(ValueError, match="linear components"):
        n.validate_linear_receipt([100., 100.], [1., 1.], [1., -1.], 0.)


@pytest.mark.parametrize("key,value", [("n_expected", True), ("df", "19"), ("mean", "1.5"),
                                      ("mean", np.nan), ("status", "zero_variance"),
                                      ("sample_sd", -1e-10), ("p", -1e-10)])
def test_group_receipt_types_status_domains(key, value):
    expected = n.complete_summary(np.linspace(-1, 2, 20))
    actual = dict(expected); actual[key] = value
    with pytest.raises(ValueError): n.validate_summary(actual, expected)


def test_group_nulls_cannot_be_zero_and_extras_are_harmless():
    expected = n.complete_summary([0.]*20)
    good = dict(expected, description="no hidden phrase required")
    n.validate_summary(good, expected)
    wrong = dict(expected, t=0.)
    with pytest.raises(ValueError, match="null required"):
        n.validate_summary(wrong, expected)


def test_shape_mismatch_not_broadcast_and_public_tolerances():
    with pytest.raises(ValueError, match="shape"):
        n.check_close([1.], 1.)
    assert n.SOURCE_TOL == n.Tolerance(1e-8, 1e-6)
    assert n.FIT_TOL == n.GROUP_TOL == n.Tolerance(1e-7, 1e-5)
    assert n.DIAGNOSTIC_TOL == n.Tolerance(1e-14, 1e-6)


def test_canonical_basis_required_not_perturbed_design_replay():
    x = np.diag([1., 1e-10]); y = np.array([[1.], [1e-10]])
    canonical = n.fit_svd(x, y, [0., 1.])["contrast_estimate"]
    perturbed_y = y.copy(); perturbed_y[1] += 1e-8
    n.check_close(perturbed_y, y, n.SOURCE_TOL)
    altered = n.fit_svd(x, perturbed_y, [0., 1.])["contrast_estimate"]
    assert abs(altered[0]-canonical[0]) > 99
    with pytest.raises(ValueError): n.check_close(altered, canonical)
