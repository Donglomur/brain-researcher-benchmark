"""Manufactured-only pinned-library oracle versus independent direct composition."""
import inspect
import warnings

import numpy as np
import pytest

import oracle_numerics as oracle
import source_numerics as direct
import reporting_kernel as reporting


def test_oracle_has_no_private_numerics_or_template_discovery_dependency():
    source = inspect.getsource(oracle)
    assert 'import source_numerics' not in source and 'from source_numerics' not in source
    assert 'datasets' not in source and 'global_support' not in source
    assert oracle.CONF_COLS == direct.CONF_COLS


@pytest.mark.parametrize('seed', [0, 13, 888])
@pytest.mark.parametrize('layout', ['C', 'F', 'float32'])
def test_two_clean_routes_fixed_fourteen_no_fd(seed, layout):
    rng = np.random.default_rng(seed)
    raw = rng.normal(size=(64, 7)); raw[:, 0] = .1
    nuisance = rng.normal(size=(64, 14)); nuisance[:, 1] = nuisance[:, 0]; nuisance[:, 2] = 1.
    if layout == 'F': raw, nuisance = np.asfortranarray(raw), np.asfortranarray(nuisance)
    elif layout == 'float32': raw, nuisance = raw.astype('f4'), nuisance.astype('f4')
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', DeprecationWarning)
        a = oracle.clean_roi(raw, nuisance, activity_fn=reporting.residual_active)
    b = direct.clean_roi(raw, nuisance, activity_fn=reporting.residual_active)
    assert a['rank'] == b['rank']
    np.testing.assert_array_equal(a['active'], b['active'])
    np.testing.assert_array_equal(a['pivots'], b['pivots'])
    for key in ('cleaned', 'residual', 'sample_sd', 'standardization_denominator',
                'raw_centered_l2', 'residual_centered_l2', 'activity_threshold'):
        np.testing.assert_allclose(a[key], b[key], rtol=1e-12, atol=1e-12)


@pytest.mark.parametrize('offset', [0., .125, 1.])
def test_spheres_reduction_and_digest(offset):
    shape, affine = (17, 18, 19), np.eye(4); affine[:3, 3] = offset
    centers = np.array([[8., 8., 8.], [8.5, 9.5, 8.5]])
    a = oracle.sphere_supports(shape, affine, centers)
    b = direct.sphere_supports(shape, affine, centers)
    assert all(np.array_equal(x, y) for x, y in zip(a, b))
    values = np.random.default_rng(9).normal(size=(*shape, 40))
    np.testing.assert_array_equal(oracle.extract_raw(values, a), direct.extract_raw(values, b))
    assert oracle.support_digest(shape, affine, a[0]) == direct.support_digest(shape, affine, b[0])


@pytest.mark.parametrize('bad', [np.nan, np.inf, -np.inf])
def test_oracle_does_not_zero_fill_original_bad_contributors(bad):
    data = np.ones((3, 3, 3, 40)); data[0, 0, 0] = bad
    assert np.isfinite(oracle.extract_raw(data, [np.array([13, 14])])).all()
    with pytest.raises(ValueError, match='nonfinite_contributing'):
        oracle.extract_raw(data, [np.array([0, 13])])


def test_oracle_empty_geometry_and_bad_activity_are_failed_preconditions():
    with pytest.raises(ValueError):
        oracle.sphere_supports((5, 5, 5), np.eye(4), [[100., 100., 100.]])
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', DeprecationWarning)
        with pytest.raises(ValueError, match='activity_callback_bool'):
            oracle.clean_roi(np.ones((64, 2)), np.zeros((64, 14)), activity_fn=lambda *_: 1)


@pytest.mark.parametrize('bad', [np.ones((64, 15)), np.ones((64, 13)), np.ones((63, 14)), np.ones((64, 14), bool)])
def test_oracle_requires_exact_finite_fourteen_confounds(bad):
    with pytest.raises(ValueError):
        oracle.clean_roi(np.ones((64, 2)), bad, activity_fn=reporting.residual_active)


def test_oracle_rejects_boolean_and_unordered_supports():
    for support in ([0, True], [2, 1], [], [0., 1.]):
        with pytest.raises(ValueError): oracle.extract_raw(np.ones((3, 3, 3, 40)), [support])
