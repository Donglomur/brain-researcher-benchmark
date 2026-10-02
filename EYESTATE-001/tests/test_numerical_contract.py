"""Small manufactured matrices only; no original cohort or outcome computation."""
import numpy as np
import pytest
from sklearn.covariance import LedoitWolf
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import StandardScaler
import metric_contract as m


@pytest.mark.parametrize('mode', ['ordinary', 'constant_columns', 'correlated', 'scale_shift', 'almost_constant'])
def test_manual_lw_matches_pinned_recipe(mode):
    rng = np.random.default_rng(2); x = rng.normal(size=(78, 200))
    if mode == 'constant_columns': x[:, :118] = 0
    elif mode == 'correlated': x += rng.normal(size=(78, 1)) * 3
    elif mode == 'scale_shift': x = x * np.linspace(.01, 100, 200) + 10000
    elif mode == 'almost_constant': x[:, :10] = 4 + 1e-14 * x[:, :10]
    centered = x - x.mean(axis=0); sd = centered.std(axis=0)
    standardized = centered / np.where(sd < np.finfo(float).eps, 1, sd)
    model = LedoitWolf(store_precision=False, assume_centered=False, block_size=1000).fit(standardized)
    v = model.covariance_; expected = (v / np.sqrt(np.diag(v)[:, None] * np.diag(v)[None, :]))[np.tril_indices(200, -1)]
    actual = m.connectivity(x)
    np.testing.assert_allclose(actual['correlation'], expected, atol=1e-12, rtol=1e-10)
    assert abs(actual['shrinkage'] - model.shrinkage_) < 1e-12


@pytest.mark.parametrize('bad', [np.zeros((60, 200)), np.full((60, 200), np.nan), np.ones(3)])
def test_undefined_source_fails_not_zero_features(bad):
    with pytest.raises(AssertionError): m.connectivity(bad)


@pytest.mark.parametrize('first', [0, 1])
def test_manual_stratification_original_class_order(first):
    labels = np.concatenate([np.repeat(first, 23), np.repeat(1 - first, 31)])
    sites = np.tile(['z', 'a', 'm'], 18)
    got = [f for f in m.make_folds(labels, sites) if f['scheme'] == 'random10']
    for fold, (train, test) in zip(got, StratifiedKFold(10, shuffle=True, random_state=0).split(np.zeros(len(labels)), labels)):
        np.testing.assert_array_equal(fold['train'], train); np.testing.assert_array_equal(fold['test'], test)
    assert [f['held_out_site'] for f in m.make_folds(labels, sites)[:3]] == ['a', 'm', 'z']


@pytest.mark.parametrize('mode', ['ordinary', 'constant_decimal', 'numerically_constant'])
def test_corrected_population_scaler(mode):
    x = np.random.default_rng(4).normal(size=(37, 8))
    if mode == 'constant_decimal': x[:, :2] = .1
    if mode == 'numerically_constant': x[:, :2] = 1e8 + x[:, :2] * 1e-9
    actual = m.scale_training(x); expected = StandardScaler().fit(x)
    np.testing.assert_allclose(actual['mean'], expected.mean_, atol=1e-14, rtol=1e-15)
    np.testing.assert_allclose(actual['variance'], expected.var_, atol=1e-14, rtol=1e-14)
    np.testing.assert_allclose(actual['scale'], expected.scale_, atol=1e-14, rtol=1e-14)


def test_gap_identity_penalizes_intercept():
    rng = np.random.default_rng(9); z = rng.normal(size=(16, 7)); y = np.tile([0, 1], 8)
    w = rng.normal(size=7); b = .7; t = 2 * y - 1; theta = np.r_[w, b]
    a = np.column_stack([z, np.ones(len(z))]); h = np.maximum(0, 1 - t * (a @ theta)); alpha = 2 * h
    dual = alpha.sum() - .5 * np.linalg.norm(a.T @ (t * alpha)) ** 2 - .25 * (alpha @ alpha)
    actual = m.fit_certificate(z, y, w, b)
    assert actual['certificate_gap'] == pytest.approx(actual['primal_objective'] - dual, rel=1e-13)
    assert actual['primal_objective'] == pytest.approx(.5 * (w @ w + b * b) + h @ h)


def test_analytic_intercept_optimum_and_wrong_unpenalized_intercept():
    y = np.r_[np.ones(12, int), np.zeros(8, int)]; z = np.zeros((20, 3)); w = np.zeros(3)
    optimum = 2 * (2 * y - 1).sum() / (1 + 2 * len(y))
    cert = m.fit_certificate(z, y, w, optimum)
    assert cert['certificate_gap'] < 1e-28
    wrong = m.fit_certificate(z, y, w, (2 * y - 1).mean())
    assert wrong['certificate_gap'] > wrong['certificate_limit']


@pytest.mark.parametrize('truth,pred,expected', [([1, 1], [0, 1], .5), ([0, 0], [0, 0], 1),
                                               ([0, 1], [1, 0], 0), ([], [], None)])
def test_supported_class_metric_not_forced_chance(truth, pred, expected):
    result = m.confusion(truth, pred)
    assert result['balanced_accuracy'] == expected
    if 0 not in truth: assert result['closed_recall'] is None
    if 1 not in truth: assert result['open_recall'] is None


def test_pooled_balanced_accuracy_differs_from_equal_site_mean_without_fixed_direction():
    labels = np.r_[np.ones(20, int), np.zeros(10, int)]; sites = np.array(['large'] * 20 + ['small'] * 10)
    # Metrics fixture only: deliberately define train/test indices directly so
    # the one-class training case does not masquerade as a valid fit protocol.
    folds = []
    for scheme in ('loso', 'random10'):
        for k, site in enumerate(('large', 'small')):
            te = np.flatnonzero(sites == site); tr = np.flatnonzero(sites != site)
            folds.append(dict(scheme=scheme, fold_id=k, held_out_site=site if scheme == 'loso' else None, train=tr, test=te))
    prediction = np.r_[np.ones(10, int), np.zeros(20, int)]
    _, results = m.summarize(labels, sites, folds, {'loso': prediction, 'random10': prediction}, 'toy', 30, 0)
    assert results['cv_balanced_accuracy'] == .75
    assert results['legacy_equal_site_mean_recall'] == .75
    # Mixed-site support with unequal class weighting can separate the estimands.
    sites[0] = 'small'; folds = []
    for scheme in ('loso', 'random10'):
        for k, site in enumerate(('large', 'small')):
            te = np.flatnonzero(sites == site); tr = np.flatnonzero(sites != site)
            folds.append(dict(scheme=scheme, fold_id=k, held_out_site=site if scheme == 'loso' else None, train=tr, test=te))
    _, changed = m.summarize(labels, sites, folds, {'loso': prediction, 'random10': prediction}, 'toy', 30, 0)
    assert changed['cv_balanced_accuracy'] == .75
    assert changed['legacy_equal_site_mean_recall'] != .75
