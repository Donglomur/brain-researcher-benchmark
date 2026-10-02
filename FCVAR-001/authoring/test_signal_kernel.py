"""Manufactured FCVAR kernel qualification only; no filesystem data or fetches."""
import importlib.util
import math
from pathlib import Path

import numpy as np
import pytest
from scipy import signal

SPEC = importlib.util.spec_from_file_location('fcvar_kernel', Path(__file__).resolve().parents[1]/'environment/signal_kernel.py')
k = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(k)


def series(n=68, p=3):
    rng = np.random.default_rng(917)
    x = np.zeros((n, 48))
    x[:, :p] = rng.normal(size=(n, p))
    active = np.arange(48) < p
    return x, active


def norms(x):
    return np.array([k.stable_center(x[:, i])[2] for i in range(x.shape[1])])


@pytest.mark.parametrize('value', [True, [1., False], np.array([True]), [1., float('nan')], [float('inf')], [1+0j]])
def test_real_array_rejects_invalid(value):
    with pytest.raises(k.PreconditionError):
        k.real_array(value)


@pytest.mark.parametrize('value', [True, -1, 2**32, 0., '0', np.float64(1)])
def test_seed_strict_domain(value):
    with pytest.raises(k.PreconditionError):
        k.generate_phases(64, '0010064', 30, value)


@pytest.mark.parametrize('sid', ['10064', 'sub-0010064', '0010064x', '００１００６４', 10064])
def test_literal_subject_keys(sid):
    with pytest.raises(k.PreconditionError):
        k.generate_phases(64, sid, 20)


@pytest.mark.parametrize('n', [63, 64, 69, 70])
@pytest.mark.parametrize('seed', [0, 2**32-1])
def test_full_rng_trace_overwrites_after_drawing(n, seed):
    got = k.generate_phases(n, '0010064', 30, seed)
    expected = np.random.default_rng(seed + 10064 + 30).uniform(0, 2*np.pi, (50, n//2+1))
    expected[:, 0] = 0
    if n % 2 == 0:
        expected[:, -1] = 0
    assert np.array_equal(got, expected)
    assert np.all(got[:, 0] == 0)
    assert np.all(got[:, -1] == 0) if n % 2 == 0 else np.any(got[:, -1] != 0)


def test_seed_domains_are_person_window_specific():
    a = k.generate_phases(64, '0010064', 20)
    assert not np.array_equal(a, k.generate_phases(64, '0010064', 30))
    assert not np.array_equal(a, k.generate_phases(64, '0010042', 20))
    assert not np.array_equal(a, k.generate_phases(64, '0010064', 20, 1))


@pytest.mark.parametrize('n', [63, 64])
def test_shared_phase_preserves_cross_spectrum(n):
    y, _ = series(n)
    y = y[:, :3]
    p = k.generate_phases(n, '0010064', 20)[0]
    result = k.phase_surrogate(y, p)
    f, g = np.fft.rfft(y, axis=0), np.fft.rfft(result, axis=0)
    expected = f[:, :, None] * f[:, None, :].conj()
    actual = g[:, :, None] * g[:, None, :].conj()
    np.testing.assert_allclose(actual, expected, atol=1e-11, rtol=1e-12)
    np.testing.assert_allclose(result.mean(axis=0), y.mean(axis=0), atol=1e-14)
    assert result.shape == y.shape


@pytest.mark.parametrize('kind', ['shape', 'dc', 'nyquist', 'negative', 'nonfinite'])
def test_wrong_phase_rejected(kind):
    y, _ = series(64)
    p = k.generate_phases(64, '0010064', 20)[0].copy()
    if kind == 'shape': p = p[:, None]
    if kind == 'dc': p[0] = .1
    if kind == 'nyquist': p[-1] = .1
    if kind == 'negative': p[1] = -.1
    if kind == 'nonfinite': p[1] = np.nan
    with pytest.raises(k.PreconditionError):
        k.phase_surrogate(y, p)


def test_empty_active_set_can_have_full_phase_receipts():
    x = np.zeros((64, 48))
    got = k.analyze_subject(x, x, np.zeros(48, dtype=bool), '0010064')
    assert len(got['surrogates']) == 150
    assert all(row['status'] == 'insufficient_rois' for row in got['surrogates'])
    assert all(row['p_denominator'] == 51 and row['n_null_defined'] == 0 for row in got['windows'])
    assert all(p.shape == (50, 33) for p in got['phases'].values())


@pytest.mark.parametrize('value', [0., .1, 1e250, -1e-250])
def test_stable_center_literal_constants(value):
    c, scale, norm = k.stable_center(np.full(100, value))
    assert np.all(c == 0) and scale == norm == 0


@pytest.mark.parametrize('factor', [1e-200, 1e-20, 1., 1e200])
def test_stable_norm_scale_covariance(factor):
    x = np.array([-2., -1., 1., 2.]) * factor
    _, _, value = k.stable_center(x)
    assert value / factor == pytest.approx(math.sqrt(10), rel=1e-14)


def cleaning_inputs(n=96):
    rng = np.random.default_rng(55)
    raw = rng.normal(size=(n, 48))
    confounds = rng.normal(size=(n, 13))
    return raw, confounds, np.ones(48, dtype=bool)


def test_cleaning_complete_finite_and_sample_standardized():
    raw, confounds, geom = cleaning_inputs()
    got = k.clean_roi_signals(raw, confounds, 2., geom)
    assert got['clean'].shape == (96, 48) and got['clean'].flags.c_contiguous
    assert got['active'].all() and 0 <= got['cleaning_rank'] <= 13
    np.testing.assert_allclose(got['clean'].std(axis=0, ddof=1), 1, atol=1e-14)
    np.testing.assert_allclose(got['clean'].mean(axis=0), 0, atol=1e-14)
    np.testing.assert_allclose(got['activity_threshold'], 1e-12*got['raw_sample_sd']*math.sqrt(95), rtol=1e-14)


def test_cleaning_geometry_and_exact_constants_stay_inactive():
    raw, confounds, geom = cleaning_inputs()
    raw[:, 0] = .1
    raw[:, 1] = 0
    geom[1] = False
    raw[:, 2] = np.arange(len(raw))
    got = k.clean_roi_signals(raw, confounds, 2., geom)
    assert not got['active'][:3].any()
    assert np.all(got['clean'][:, :3] == 0)
    assert got['raw_sample_sd'][0] == got['activity_threshold'][0] == 0


@pytest.mark.parametrize('factor', [1e-20, 1e20])
def test_active_standardization_has_no_absolute_sd_floor(factor):
    raw, confounds, geom = cleaning_inputs()
    expected = k.clean_roi_signals(raw, confounds, 2., geom)
    actual = k.clean_roi_signals(raw*factor, confounds, 2., geom)
    assert np.array_equal(actual['active'], expected['active'])
    np.testing.assert_allclose(actual['clean'], expected['clean'], atol=1e-8, rtol=1e-8)


@pytest.mark.parametrize('kind', ['short', 'missing_column', 'missing_row', 'nan', 'bool_tr', 'nyquist', 'geometry', 'empty_nonzero'])
def test_cleaning_preconditions(kind):
    raw, confounds, geom = cleaning_inputs()
    tr = 2.
    if kind == 'short': raw, confounds = raw[:33], confounds[:33]
    if kind == 'missing_column': confounds = confounds[:, :-1]
    if kind == 'missing_row': confounds = confounds[:-1]
    if kind == 'nan': confounds[0, 0] = np.nan
    if kind == 'bool_tr': tr = True
    if kind == 'nyquist': tr = 7.
    if kind == 'geometry': geom = geom.astype(int)
    if kind == 'empty_nonzero': geom[0] = False
    with pytest.raises(k.PreconditionError):
        k.clean_roi_signals(raw, confounds, tr, geom)


def test_cleaning_replays_declared_matrix_operator():
    raw, confounds, geom = cleaning_inputs()
    y, c = k.detrend(raw), k.detrend(confounds)
    sos = signal.butter(5, [.009, .08], btype='bandpass', fs=.5, output='sos')
    y = np.array(signal.sosfiltfilt(sos, y, axis=0, padtype='odd', padlen=33), order='C')
    c = np.array(signal.sosfiltfilt(sos, c, axis=0, padtype='odd', padlen=33), order='C')
    c -= c.mean(axis=0)
    sd = c.std(axis=0); sd[sd < k.EPS] = 1
    c /= sd
    q, r, _ = k.linalg.qr(c, mode='economic', pivoting=True, check_finite=True)
    q = np.ascontiguousarray(q[:, np.abs(np.diag(r)) > 100*k.EPS])
    residual = y - (q@q.T)@y
    residual -= residual.mean(axis=0)
    expected = np.zeros_like(raw)
    for j in range(48):
        centered, scale, norm = k.stable_center(residual[:, j])
        expected[:, j] = centered/(norm/scale)*math.sqrt(len(raw)-1)
    got = k.clean_roi_signals(raw, confounds, 2., geom)
    np.testing.assert_array_equal(got['clean'], expected)


@pytest.mark.parametrize('window', k.WINDOWS)
def test_window_stat_matches_direct_pearson_fisher_sd(window):
    x, _ = series(92)
    x = x[:, :3]
    rows = [np.arctanh(np.clip(np.corrcoef(x[s:s+window].T), -.999, .999))[np.triu_indices(3, 1)]
            for s in range(0, len(x)-window+1, 3)]
    expected = np.std(rows, axis=0, ddof=1).mean()
    got = k.window_statistic(x, x, norms(x), window)
    assert got['status'] == 'ok'
    assert got['mean_edge_sd'] == pytest.approx(expected, abs=1e-13)


@pytest.mark.parametrize('n,expected', [(19, 'insufficient_windows'), (20, 'insufficient_windows'), (22, 'insufficient_windows'), (23, 'ok'), (26, 'ok')])
def test_exact_two_window_minimum(n, expected):
    x, _ = series(n)
    x = x[:, :3]
    assert k.window_statistic(x, x, norms(x), 20)['status'] == expected


def test_fixed_edges_no_windowwise_drop():
    x, _ = series(68)
    x = x[:, :3]
    x[:20, 0] = .1
    got = k.window_statistic(x, x, norms(x), 20)
    assert got == {'status': 'undefined_window_correlation', 'mean_edge_sd': None}
    assert k.window_statistic(x[:, 1:], x[:, 1:], norms(x[:, 1:]), 20)['status'] == 'ok'


def test_nearconstant_canonical_window_is_undefined_not_perturbed_active():
    x, _ = series(68)
    x = x[:, :3]
    x[:20, 0] = .1 + 1e-15*np.arange(20)
    accepted = x.copy()
    accepted[:20, 0] += 1e-8*np.sin(np.arange(20))
    # Other overlapping, canonical-active windows still need fidelity. Their
    # ordinary variation makes this perturbation small; inactive first window
    # can never create a new edge or defined scalar.
    got = k.window_statistic(accepted, x, norms(x), 20)
    assert got['status'] == 'undefined_window_correlation'


def test_active_small_window_needs_relative_not_only_global_fidelity():
    x, _ = series(68)
    x = x[:, :3]
    x[:20, 0] = 1e-8*np.sin(np.arange(20))
    accepted = x.copy()
    accepted[:20, 0] += 1e-9*np.cos(np.arange(20))
    assert np.max(np.abs(accepted-x)) < 1e-7
    with pytest.raises(k.FidelityError, match='local'):
        k.window_statistic(accepted, x, norms(x), 20)


def test_inactive_receipt_jitter_does_not_reactivate():
    x, active = series(48)
    accepted = x.copy(); accepted[:, ~active] = 1e-8
    expected = k.analyze_subject(x, x, active, '0010064')
    actual = k.analyze_subject(accepted, x, active, '0010064')
    assert actual['windows'] == expected['windows']
    assert actual['surrogates'] == expected['surrogates']


def test_global_centered_relative_check():
    x, active = series()
    accepted = x.copy(); accepted[:, 0] *= 1+2e-6
    with pytest.raises(k.FidelityError, match='global'):
        k.validate_series(accepted, x, active)
    accepted[:, 0] = x[:, 0]*(1+1e-8)
    k.validate_series(accepted, x, active)


def test_signed_correlations_and_zero_sd_for_collinear_columns():
    x, _ = series(68)
    x = np.column_stack([x[:, 0], -x[:, 0]])
    got = k.window_statistic(x, x, norms(x), 20)
    assert got == {'status': 'ok', 'mean_edge_sd': 0.}


def test_full_collinear_replay_has_zero_variability_and_defined_rank():
    x, active = series(48, p=2)
    x[:, 1] = -x[:, 0]
    got = k.analyze_subject(x, x, active, '0010064')
    for row in got['windows']:
        assert row['mean_edge_sd'] == row['mean_edge_sd_null'] == 0.
        assert row['ratio_status'] == 'zero_null_mean'
        assert row['observed_over_null_ratio'] is None
        assert row['p_value'] == 1. and row['n_exceedances'] == 50


def slot(value, status='ok'):
    return dict(status=status, mean_edge_sd=value)


@pytest.mark.parametrize('observed,null,exceeds,p,ratio_status', [(0., 0., 50, 1., 'zero_null_mean'), (1., 0., 0, 1/51, 'zero_null_mean'), (1., 1., 50, 1., 'ok'), (2., 1., 0, 1/51, 'ok'), (.5, 1., 50, 1., 'ok')])
def test_rank_ties_and_zero_null_mean(observed, null, exceeds, p, ratio_status):
    got, comparisons = k.summarize_slots(slot(observed), [slot(null)]*50)
    assert got['n_exceedances'] == exceeds
    assert sum(comparisons) == exceeds
    assert got['p_value'] == p and got['p_denominator'] == 51
    assert got['ratio_status'] == ratio_status


@pytest.mark.parametrize('exceeds,significant', [(0, True), (1, True), (2, False), (50, False)])
def test_exact_integer_alpha_boundary(exceeds, significant):
    got, _ = k.summarize_slots(slot(1.), [slot(1.)]*exceeds + [slot(0.)]*(50-exceeds))
    assert got['significant'] is significant


def test_one_undefined_null_preserves_denominator_and_individual_comparisons():
    got, comparisons = k.summarize_slots(slot(1.), [slot(1.)]*49 + [slot(None, 'undefined_window_correlation')])
    assert got['n_null_expected'] == 50 and got['n_null_defined'] == 49
    assert got['p_denominator'] == 51 and got['p_value'] is None and got['n_exceedances'] is None
    assert comparisons == [True]*49+[None]
    assert got['mean_edge_sd_null'] is None


def test_undefined_observed_does_not_erase_defined_null_mean():
    got, comparisons = k.summarize_slots(slot(None, 'insufficient_windows'), [slot(.2)]*50)
    assert got['mean_edge_sd_null'] == pytest.approx(.2)
    assert got['n_null_defined'] == 50 and got['p_value'] is None
    assert comparisons == [None]*50


def test_full_replay_retains_all_keyed_rows():
    x, active = series(48)
    got = k.analyze_subject(x, x, active, '0010064', 2**32-1)
    assert len(got['windows']) == 3 and len(got['surrogates']) == 150
    assert {r['window_tr'] for r in got['windows']} == set(k.WINDOWS)
    for row in got['windows']:
        draws = [r for r in got['surrogates'] if r['window_tr'] == row['window_tr']]
        assert [r['surrogate_id'] for r in draws] == list(range(50))
        assert row['n_edges'] == 3 and row['n_rois'] == 3
        assert row['n_windows'] == len(range(0, 48-row['window_tr']+1, 3))
        assert row['n_exceedances'] == sum(r['exceeds_observed'] for r in draws)


def group_person(sid, observed, null_mean, ratio, p, significant):
    return dict(subject=sid, seed=0, windows=[dict(window_tr=w,
        mean_edge_sd=observed, mean_edge_sd_null=null_mean,
        observed_over_null_ratio=ratio, p_value=p, significant=significant) for w in k.WINDOWS])


def test_group_uses_equal_person_ratio_not_ratio_of_means_and_exact_p():
    a = group_person('0010042', 1., 1., 1., 1/51, True)
    b = group_person('0010064', 8., 4., 2., 3/51, False)
    got = k.summarize_subjects([b, a], ['0010042', '0010064'])
    assert got['n_subjects'] == 2
    for window in got['windows']:
        assert window['mean_subject_observed_over_null_ratio']['value'] == 1.5
        assert window['mean_observed_edge_sd']['value'] == 4.5
        assert window['mean_null_edge_sd']['value'] == 2.5
        assert window['median_subject_p']['value'] == pytest.approx(2/51)
        assert window['fraction_subjects_significant']['value'] == .5


def test_group_metric_specific_undefined_not_nanmean():
    a = group_person('0010042', 0., 0., None, 1., False)
    b = group_person('0010064', 8., 4., 2., 3/51, False)
    got = k.summarize_subjects([a, b], ['0010042', '0010064'])
    for window in got['windows']:
        assert window['mean_subject_observed_over_null_ratio'] == dict(n_expected=2, n_defined=1, status='incomplete_support', value=None)
        assert window['mean_observed_edge_sd']['status'] == 'ok'
        assert window['median_subject_p']['status'] == 'ok'


@pytest.mark.parametrize('kind', ['missing', 'duplicate', 'seed', 'windows'])
def test_group_complete_keyed_membership(kind):
    a = group_person('0010042', 1., 1., 1., 1., False)
    b = group_person('0010064', 1., 1., 1., 1., False)
    rows = [a, b]
    if kind == 'missing': rows = [a]
    if kind == 'duplicate': rows = [a, a]
    if kind == 'seed': b['seed'] = 1
    if kind == 'windows': b['windows'] = b['windows'][:2]
    with pytest.raises(k.PreconditionError):
        k.summarize_subjects(rows, ['0010042', '0010064'])
