"""Equation/optimizer mechanics only; fixtures are not a scientific reference bank."""
import importlib.util
from pathlib import Path

import numpy as np
import pytest
from scipy.integrate import quad

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


oracle = module("petref_oracle_test", ROOT / "solution/compute.py")
independent = module("petref_independent_test", ROOT / "authoring/check_independent.py")


@pytest.mark.parametrize("theta,h", [(0., .001), (6.25e-6, .001), (6.25e-6, 5.),
                                    (.2, .4), (10., 10.), (.001, 1.)])
@pytest.mark.parametrize("left,slope", [(0., 3.), (2., -0.1), (1., 0.)])
def test_stable_segment_against_quadrature(theta, h, left, slope):
    z = .23
    expected = np.exp(-theta*h)*z + quad(
        lambda u: (left+slope*u)*np.exp(-theta*(h-u)), 0, h,
        epsabs=1e-12, epsrel=1e-12)[0]
    actual = oracle.linear_segment(z, left, slope, h, theta)
    assert np.isclose(actual, expected, atol=1e-11, rtol=1e-11)


@pytest.mark.parametrize("params", [
    [.01, .0001, 15.], [3., 5., -.5], [1., .1, 1.],
    [2.9, .0001, -.5], [.01, 5., 15.], [1.2, .2, .2]])
def test_irregular_midpoint_predictor_agrees_with_ode_and_matrix(params):
    mid = np.array([.001, .004, .2, .7, 2., 5., 15., 30., 60., 89.])
    ref = np.array([0., 0., .1, .8, 1.0, .7, .4, .2, .05, .01])
    expected = independent.ode_prediction(mid, ref, params)
    matrix = independent.matrix_prediction(mid, ref, params)
    actual = oracle.srtm_predict(mid, ref, params)
    assert np.allclose(actual, expected, atol=1e-9, rtol=1e-9)
    assert np.allclose(actual, matrix, atol=1e-11, rtol=1e-11)


def test_direct_reference_limit_and_initial_zeros():
    mid = np.array([.1, .3, 1., 4., 15.])
    ref = np.array([0., 0., 1., .4, .1])
    pred = oracle.srtm_predict(mid, ref, [1.2, .2, .2])
    assert np.allclose(pred, 1.2*ref, atol=1e-14)
    assert np.array_equal(pred[:2], [0., 0.])


def test_origin_segment_is_linear_not_delayed_step():
    actual = oracle.srtm_predict(np.array([1.]), np.array([2.]), [1., .2, 1.])
    expected = independent.ode_prediction(np.array([1.]), np.array([2.]), [1., .2, 1.])
    assert np.allclose(actual, expected, atol=1e-11)
    assert actual[0] > 2.0  # convolution accumulates over the first segment.


def test_matrix_complex_step_jacobian_matches_central_difference():
    mid = np.array([.1, .4, 1., 3., 10., 40.])
    ref = np.array([0., .1, 1., .7, .3, .1])
    params = np.array([1.2, .2, 2.])
    jac = independent.matrix_jacobian(mid, ref, params)
    numeric = []
    for k in range(3):
        shift = np.zeros(3)
        shift[k] = 1e-6
        numeric.append((independent.matrix_prediction(mid, ref, params+shift)
                        - independent.matrix_prediction(mid, ref, params-shift))/2e-6)
    assert np.allclose(jac, np.column_stack(numeric), atol=1e-8, rtol=1e-7)


def test_bounded_fixture_fit_preserves_all_candidate_diagnostics():
    mid = np.linspace(.2, 50., 25)
    ref = (1-np.exp(-mid*2))*np.exp(-mid/15)
    planted = np.array([1.1, .15, 1.8])
    target = independent.matrix_prediction(mid, ref, planted)
    fit = oracle.fit_scan({"mid": mid, "reference": ref, "target": target,
                           "scale": float(ref.max())})
    assert len(fit["candidates"]) == 3
    assert np.allclose(fit["params"], planted, atol=1e-6)
    assert fit["normalized_rmse"] < 1e-8
    assert all("jacobian_singular_values" in item for item in fit["candidates"])
    accepted = [x for x in fit["candidates"] if x["success"]]
    best = min(accepted, key=lambda x: (x["normalized_sse"], x["start_index"]))
    assert fit["selected_start_index"] == best["start_index"]


def test_pair_summary_preserves_undefined_pairs():
    p = np.array([[1., .1, -.5], [1., .1, .1], [1., .1, 1.], [1., .1, 2.]])
    result = oracle.summarize(p)
    assert result["n_defined_pairs"] == 1 and result["test_retest_pct"] is None
    assert result["per_subject"][0]["status"] == "undefined_nonpositive_mean"
    assert result["per_subject"][0]["test_retest_pct"] is None
    assert result["per_subject"][1]["test_retest_pct"] == pytest.approx(100/1.5)


def test_zero_repeat_difference_is_valid():
    result = oracle.summarize(np.array([[1., .1, 2.]]*4))
    assert result["test_retest_pct"] == 0. and result["n_defined_pairs"] == 2


def test_bounds_are_diagnostics_not_interior_only_gate():
    lo, hi = oracle.boundary_flags(np.array([.01, 5., 2.]))
    assert lo.tolist() == [True, False, False]
    assert hi.tolist() == [False, True, False]


def test_tac_parser_retains_initial_zeros_and_frame_durations(tmp_path):
    path = tmp_path / "fixture.tsv"
    path.write_text("frame_start\tframe_end\t" + "\t".join(oracle.COLUMNS) + "\n"
                    "0\t10\t0\t0\t0\t0\n10\t30\t2\t4\t1\t3\n")
    start, end, values = oracle.read_tac(path)
    assert np.array_equal(start, [0., 10.]) and np.array_equal(end, [10., 30.])
    assert np.array_equal(values[0], [0., 0., 0., 0.])
