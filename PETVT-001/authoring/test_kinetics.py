"""Manufactured arithmetic only; never original source or historical bank."""
import importlib.util
import math
from pathlib import Path

import numpy as np
import pytest
from scipy import integrate, linalg

PATH = Path(__file__).resolve().parents[1]/'solution'/'kinetics.py'
SPEC = importlib.util.spec_from_file_location('prospective_kinetics', PATH)
k = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(k)


def test_finite_solver_coefficients_survive_diagnostic_residual_overflow(monkeypatch):
    # Force the representability branch, not a claim about a particular
    # LAPACK solution for this extreme manufactured design.
    monkeypatch.setattr(k.linalg,'lstsq',lambda *a,**kw:(np.array([1e308,1e308]),None,2,np.array([1.,1.])))
    result=k.solve_ols([[1e308,1e308],[1.,0.],[0.,1.]],[1.,2.,3.])
    assert result['status']=='ok' and result['coefficients'].tolist()==[1.,1.]
    assert result['residual_rss'] is None and result['rss_status']=='numerical_overflow'


def test_input_two_assumptions_half_life_and_nonzero_reference():
    half = 6586.2; t = np.array([100., 100.+half]); p = np.array([3., 3.]); f = np.array([.5, 1.])
    a = k.parent_knots(t, p, f, k.ASSUMPTIONS[0], image_reference_s=100.)
    b = k.parent_knots(t, p, f, k.ASSUMPTIONS[1], image_reference_s=100.)
    assert a['inserted_zero_anchor'] and b['inserted_zero_anchor']
    np.testing.assert_allclose(a['values'], [0, 1.5, 3], rtol=1e-14)
    np.testing.assert_allclose(b['values'], [0, 1.5, 6], rtol=1e-14)
    np.testing.assert_array_equal(t, [100., 100.+half])
    np.testing.assert_array_equal(p, [3., 3.]); np.testing.assert_array_equal(f, [.5, 1.])


def test_zero_time_observation_not_replaced_and_parent_zero_valid():
    result = k.parent_knots([0, 60], [2, 3], [1, 0], 'sample_time_reference')
    assert result['inserted_zero_anchor'] is False
    np.testing.assert_array_equal(result['values'], [2, 0])


def test_parent_transform_before_interpolation_not_interpolated_product():
    a = k.parent_knots([0, 60], [2, 6], [1, .5], 'already_image_reference')
    assert k.input_integral(a['times_min'], a['values'], [.5])[0] == pytest.approx(1.125)
    # Product of separately interpolated P and f has a different integral.
    separate = integrate.quad(lambda t: (2+4*t)*(1-.5*t), 0, .5)[0]
    assert abs(separate-1.125) > .05


@pytest.mark.parametrize('times,plasma,parent', [([0, 0], [1, 1], [1, 1]),
    ([1, 0], [1, 1], [1, 1]), ([-1, 60], [1, 1], [1, 1]),
    ([0, 60], [-1, 1], [1, 1]), ([0, 60], [1, 1], [1, 1.1]),
    ([0, 60], [1, 1], [1, -.1]), ([0, 60], [1, float('nan')], [1, 1])])
def test_paired_domains(times, plasma, parent):
    with pytest.raises(k.ContractError): k.parent_knots(times, plasma, parent, k.ASSUMPTIONS[0])


def test_tissue_rectangles_include_earliest_half_frame_and_unequal_widths():
    mid, area = k.tissue_integral([0, 60, 180], [60, 180, 240], [2, 4, 3])
    np.testing.assert_array_equal(mid, [.5, 2, 3.5])
    np.testing.assert_array_equal(area, [1, 6, 11.5])


@pytest.mark.parametrize('start,end', [([0, 61], [60, 120]), ([0, 59], [60, 120]),
                                     ([1, 60], [60, 120]), ([0, 60], [60, 60])])
def test_frame_gap_overlap_origin_and_zero_width(start, end):
    with pytest.raises(k.ContractError): k.tissue_integral(start, end, [1, 1])


def test_piecewise_integral_exact_and_independent_quadrature():
    t = np.array([0., 1., 3.]); v = np.array([0., 2., 4.]); q = np.array([0., .5, 1., 2., 3.])
    expected = np.array([0, .25, 1, 3.5, 7.])
    np.testing.assert_allclose(k.input_integral(t, v, q), expected, atol=1e-14)
    independent = [integrate.quad(lambda s: np.interp(s, t, v), 0, target,
                                  points=[x for x in t if 0 < x < target], epsabs=1e-12)[0] for target in q]
    np.testing.assert_allclose(k.input_integral(t, v, q), independent, atol=1e-12)


@pytest.mark.parametrize('target', [[-1e-9], [3.000000001]])
def test_no_left_or_held_tail_extrapolation(target):
    with pytest.raises(k.Unavailable, match='input_time_support_unavailable'):
        k.input_integral([0, 1, 3], [0, 2, 4], target)


def test_cortical_mean_equal_region_signed_and_immutable():
    original = np.array([[1., 3., 8.], [-3., 0., 3.]])
    copy = original.copy(); actual = k.cortical_mean(original)
    np.testing.assert_allclose(actual, [4., 0.]); np.testing.assert_array_equal(copy, original)


def test_logan_analytic_coefficients_and_qr_independent():
    x = np.array([1., 2., 4., 8.]); y = 1.7*x+2.3
    result = k.fit_model([30, 40, 50, 60], np.ones(4), y, x, 'logan')
    q, r = np.linalg.qr(np.column_stack((x, np.ones(4))))
    independent = linalg.solve_triangular(r, q.T@y)
    assert result['status'] == 'ok' and result['rank'] == 2
    np.testing.assert_allclose(result['coefficients'], independent, atol=1e-12, rtol=1e-12)
    assert result['vt'] == pytest.approx(1.7, abs=1e-12)


def test_ma1_analytic_coefficients_and_signed_negative_not_rejected():
    ip = np.array([1., 2., 4., 8.]); it = np.array([2., 1., 3., 4.]); ct = .3*ip+.2*it
    result = k.fit_model([30, 40, 50, 60], ct, it, ip, 'ma1')
    np.testing.assert_allclose(result['coefficients'], [.3, .2], atol=1e-12)
    assert result['status'] == 'ok' and result['vt'] == pytest.approx(-1.5)
    assert result['nonpositive_vt'] is True


@pytest.mark.parametrize('scale', [1e-150, 1., 1e150])
def test_common_amplitude_scale_invariance(scale):
    ip = np.array([1., 2., 4., 8.]); it = np.array([2., 1., 3., 4.]); ct = .3*ip+.2*it
    result = k.fit_model([30, 40, 50, 60], scale*ct, scale*it, scale*ip, 'ma1')
    assert result['status'] == 'ok'
    np.testing.assert_allclose(result['coefficients'], [.3, .2], atol=1e-12, rtol=1e-12)


def test_plasma_only_scale_inverse_vt():
    ip = np.array([1., 2., 4., 8.]); it = np.array([2., 1., 3., 4.]); ct = .3*ip+.2*it
    first = k.fit_model([30, 40, 50, 60], ct, it, ip, 'ma1')
    second = k.fit_model([30, 40, 50, 60], ct, it, 2*ip, 'ma1')
    assert second['vt'] == pytest.approx(first['vt']/2)


def test_unsupported_records_retain_late_count():
    assert k.fit_model([10, 30, 40, 50], [1]*4, [1]*4, None, 'logan')['n_fit_rows'] == 3
    assert k.fit_model([10, 20, 30], [1]*3, [1]*3, [1]*3, 'ma1')['status'] == 'insufficient_fit_rows'
    assert k.fit_model([30, 40, 50], [1, 0, 1], [1]*3, [1]*3, 'logan')['status'] == 'nonpositive_tissue_for_logan'


def test_rank_one_and_zero_column_explicit():
    x = np.column_stack((np.arange(1., 6.), 2*np.arange(1., 6.)))
    result = k.solve_ols(x, np.arange(5.))
    assert result['status'] == 'rank_deficient' and result['rank'] == 1 and result['coefficients'] is None
    assert k.solve_ols(np.column_stack((np.zeros(5), np.ones(5))), np.arange(5.))['status'] == 'zero_design_column'


def test_resolved_near_rank_design_no_extra_condition_number_gate():
    x = np.column_stack((np.ones(6), 1+np.arange(6)*1e-8))
    result = k.solve_ols(x, x@np.array([2., 3.]))
    assert result['status'] == 'ok' and result['rank'] == 2
    np.testing.assert_allclose(result['coefficients'], [2, 3], atol=1e-6)


@pytest.mark.parametrize('coeff,supported', [([1., 0.], False), ([0., 0.], False),
    ([1., 64*k.EPS], False), ([1., 128*k.EPS], True), ([1e-300, -1e-300], True),
    ([np.nextafter(0., 1.), -np.nextafter(0., 1.)], True)])
def test_denominator_resolution_scale_safe(coeff, supported):
    assert k.ma1_supported(coeff) is supported


def test_canonical_unresolved_cannot_reactivate_but_amplitude_receipt_finite():
    source = [1., 0.]; own = k.accepted_coefficients('ma1', [1., 1e-9], source, source_supported=False)
    result = k.derive_vt('ma1', own, source_supported=False)
    assert result['status'] == 'ma1_denominator_unresolved' and result['vt'] is None


def test_tiny_ma1_full_vector_and_denominator_guards():
    source = np.array([1e-300, -1e-300])
    own = k.accepted_coefficients('ma1', source*[1+1e-7, 1], source)
    assert k.derive_vt('ma1', own)['vt'] == pytest.approx(1+1e-7)
    for bad in ([1e-9, -1e-300], [1e-300, 0], [1e-300, 1e-300]):
        with pytest.raises(k.ContractError): k.accepted_coefficients('ma1', bad, source)


def test_denominator_guard_not_subsumed_by_vector_error():
    source = [1., 1e-10]
    with pytest.raises(k.ContractError, match='denominator relative'):
        k.accepted_coefficients('ma1', [1., 1e-10*(1+1e-5)], source)


def test_subnormal_identical_coefficients_accepted_without_underflowing_bound():
    tiny = np.nextafter(0., 1.); source = [tiny, -tiny]
    actual = k.accepted_coefficients('ma1', source, source)
    assert k.derive_vt('ma1', actual)['vt'] == 1.


def test_quotient_zero_and_nonzero_underflow_or_overflow():
    assert k.derive_vt('ma1', [0., 1.])['vt'] == 0
    assert k.derive_vt('ma1', [1e-300, 1e300])['status'] == 'numerical_failure'
    assert k.derive_vt('ma1', [1e300, 1e-300])['status'] == 'numerical_failure'


def test_complete_group_constant_and_missing_all_seven_retained():
    constant = k.complete_summary([2.]*7)
    assert constant == dict(n_expected=7, n_defined=7, status='ok', mean=2., sample_sd=0., minimum=2., maximum=2.)
    incomplete = k.complete_summary([2.]*6+[None])
    assert incomplete['n_defined'] == 6 and incomplete['mean'] is None and incomplete['status'] == 'incomplete'
    with pytest.raises(k.ContractError): k.complete_summary([2.]*6)


def test_complete_group_signed_changes_not_absolute():
    result = k.complete_summary([-3., -2., -1., 0., 1., 2., 3.])
    assert result['mean'] == 0 and result['sample_sd'] == pytest.approx(math.sqrt(28/6))


def test_nonconstant_group_sd_underflow_is_not_a_constant():
    tiny = float(np.nextafter(0., 1.))
    result = k.complete_summary([tiny, 0., 0., 0., 0., 0., 0.])
    assert result['status'] == 'numerical_failure' and result['sample_sd'] is None
    assert k.complete_summary([tiny]*7)['sample_sd'] == 0


def test_group_large_level_small_represented_spread_not_lost():
    base = float(2**50); values = [base+i*.25 for i in range(7)]
    result = k.complete_summary(values)
    assert result['mean'] == base+.75
    assert result['sample_sd'] == pytest.approx(math.sqrt(7/24))


def test_known_one_tissue_model_converges_under_frame_and_knot_refinement():
    # Independent analytic one-tissue model: Cp=exp(-a*t),
    # CT=K1/(k2-a)*(exp(-a*t)-exp(-k2*t)); exact VT=K1/k2=2.
    # This is a manufactured discretization diagnostic, not an original-data gate.
    def estimate(step):
        a, k2, k1 = .025, .15, .3
        edges = np.arange(0., 60.+step*.5, step)
        def integral_exp(rate):
            return (np.exp(-rate*edges[:-1])-np.exp(-rate*edges[1:]))/rate
        ct = k1/(k2-a)*(integral_exp(a)-integral_exp(k2))/step
        times, it = k.tissue_integral(edges[:-1]*60, edges[1:]*60, ct)
        ip = k.input_integral(edges, np.exp(-a*edges), times)
        return k.fit_model(times, ct, it, ip, 'logan')['vt']
    coarse, fine = estimate(.4), estimate(.2)
    assert abs(fine-2.) < abs(coarse-2.)
    assert abs(fine-2.) < 1e-3


@pytest.mark.parametrize('bad', [[True, False], ['1', '2'], [1+0j, 2+0j], [1., np.inf]])
def test_finite_real_input_domains(bad):
    with pytest.raises(k.ContractError): k.real_array(bad, 1, 'fixture')
