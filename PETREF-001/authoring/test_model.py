"""Independent verifier-model mechanics; no real-TAC fits or scientific bank."""
import sys
from pathlib import Path
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "tests"))
from proof_of_work import SCANS, PIPELINE_ID
from srtm_contract import srtm_prediction, paired_metrics, validate_results


@pytest.mark.parametrize("params", [[1.1, .1, 2.], [.5, .0001, 15.], [2., 5., -.5]])
def test_piecewise_linear_recurrence_matches_independent_quadrature(params):
    integrate = pytest.importorskip("scipy.integrate")
    t = np.array([.01, .09, .31, 1.2, 2.3, 7., 19.])
    cr = np.array([0., .2, 1.8, 2., .9, .3, .02])
    knots, values = np.r_[0., t], np.r_[0., cr]
    r1, k2, bp = params; theta = k2/(1+bp)
    expected = []
    for index, time in enumerate(t):
        # Independent adaptive quadrature of each linear segment, not the
        # verifier's analytic recurrence or an oracle function.
        convolution = sum(integrate.quad(lambda u: np.interp(u, knots, values)*np.exp(-theta*(time-u)),
            knots[j], knots[j+1], epsabs=1e-12, epsrel=1e-12)[0] for j in range(index+1))
        expected.append(r1*cr[index]+(k2-r1*theta)*convolution)
    np.testing.assert_allclose(srtm_prediction(t, cr, params), expected, atol=1e-10, rtol=1e-10)


def test_zero_reference_and_initial_zero_frames_are_valid():
    t = np.array([.1, .2, .5, 1.])
    np.testing.assert_array_equal(srtm_prediction(t, np.zeros(4), [1., .1, 1.]), np.zeros(4))
    output = srtm_prediction(t, np.array([0., 0., 1., 2.]), [1., .1, 1.])
    np.testing.assert_array_equal(output[:2], [0., 0.])


def test_origin_is_linear_zero_anchor_not_zero_until_first_midpoint():
    r1, k2, bp, t, cr = 1.1, .2, 2., .5, 3.
    theta = k2/(1+bp)
    integral = cr/t*(t/theta+(np.expm1(-theta*t))/(theta*theta))
    expected = r1*cr+(k2-r1*theta)*integral
    assert srtm_prediction([t], [cr], [r1, k2, bp])[0] == pytest.approx(expected, rel=1e-12)
    assert abs(expected-r1*cr) > .01


def test_common_activity_scaling_preserves_model_parameters():
    t = np.array([.1, .2, 1., 3., 10.]); cr = np.array([0., 1., 4., 2., .4])
    parameters = [1.2, .2, 1.7]
    np.testing.assert_allclose(srtm_prediction(t, cr*1000, parameters),
                               1000*srtm_prediction(t, cr, parameters), atol=1e-10, rtol=1e-12)


@pytest.mark.parametrize("time", [[0., 1.], [1., 1.], [2., 1.], [1., np.nan]])
def test_invalid_model_time_support_is_rejected(time):
    with pytest.raises(AssertionError): srtm_prediction(time, [1., 2.], [1., .1, 1.])


@pytest.mark.parametrize("params", [[0., .1, 1.], [1., -1., 1.], [1., .1, -1.], [1., .1, 16.]])
def test_model_computational_bounds(params):
    with pytest.raises(AssertionError): srtm_prediction([.1, 1.], [1., 2.], params)


def bp_fixture(values):
    return {key: {"BP_ND": value} for key, value in zip(SCANS, values)}


def test_test_retest_is_mean_of_two_paired_percentages_not_pooled_ratio():
    estimates = bp_fixture([1., 2., 3., 3.])
    result = paired_metrics(estimates)
    assert result["per_subject"][0]["test_retest_pct"] == pytest.approx(100/1.5)
    assert result["test_retest_pct"] == pytest.approx((100/1.5)/2)
    assert result["putamen_BP_ND_mean"] == 2.25
    assert result["test_retest_pct"] != pytest.approx(100*.5/2.25)


def test_identical_binding_and_zero_retest_are_not_intrinsically_invalid():
    estimates = bp_fixture([.1, .1, .1, .1])
    result = {"status": "ok", "pipeline_id": PIPELINE_ID, **paired_metrics(estimates)}
    assert result["test_retest_pct"] == 0 and result["putamen_BP_ND_mean"] == .1
    validate_results(result, estimates)


@pytest.mark.parametrize("pair", [[0., 0.], [-.2, .2], [-.4, -.1]])
def test_nonpositive_pair_mean_is_undefined_and_not_silently_dropped(pair):
    estimates = bp_fixture([*pair, 1., 2.])
    result = {"status": "ok", "pipeline_id": PIPELINE_ID, **paired_metrics(estimates)}
    assert result["n_defined_pairs"] == 1 and result["test_retest_pct"] is None
    assert result["per_subject"][0]["test_retest_pct"] is None
    assert result["per_subject"][0]["status"] == "undefined_nonpositive_mean"
    validate_results(result, estimates)
    result["test_retest_pct"] = result["per_subject"][1]["test_retest_pct"]
    with pytest.raises(AssertionError, match="both defined pairs"): validate_results(result, estimates)
