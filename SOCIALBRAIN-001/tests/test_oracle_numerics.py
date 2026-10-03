"""Manufactured upstream-composed oracle/direct-verifier comparisons only."""
import importlib.util
from pathlib import Path

import numpy as np
import pytest


def module(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


O = module('oracle_numerics')
V = module('source_numerics')
K = module('reporting_kernel')


@pytest.mark.parametrize('seed', [0, 13, 888])
@pytest.mark.parametrize('layout', ['C', 'F'])
def test_clean_two_implementations(seed, layout):
    rng = np.random.default_rng(seed)
    raw = np.array(rng.normal(size=(64, 12)), order=layout)
    raw[:, 0] = .1
    nuis = rng.normal(size=(64, 15))
    nuis[:, 1] = nuis[:, 0]
    nuis[:, 2] = 1.
    a = O.clean_roi(raw, nuis, activity_fn=K.residual_active)
    b = V.clean_roi(raw, nuis, activity_fn=K.residual_active)
    assert a['rank'] == b['rank']
    assert np.array_equal(a['active'], b['active'])
    for key in ('cleaned', 'residual', 'raw_centered_l2', 'residual_centered_l2'):
        np.testing.assert_allclose(a[key], b[key], rtol=1e-12, atol=1e-12)


@pytest.mark.parametrize('shift', [0., .125, 1.])
def test_geometry_and_reduction(shift):
    shape = (17, 18, 19)
    affine = np.eye(4)
    centers = np.array([[8., 8., 8.], [8.5, 9.5, 8.5]])
    a = O.sphere_supports(shape, affine, centers, radius=2.)
    b = V.sphere_supports(shape, affine, centers, radius=2.)
    assert all(np.array_equal(x, y) for x, y in zip(a, b))
    template = np.zeros(shape)
    template[3:-3, 3:-3, 3:-3] = 10.
    target = affine.copy(); target[:3, 3] += shift
    ga = O.global_support(template, affine, shape, target)
    gb = V.global_support(template, affine, shape, target)
    assert np.array_equal(ga['indices'], gb['indices'])
    assert ga['resampling_branch'] == gb['resampling_branch']
    np.testing.assert_allclose(ga['resampled_template'], gb['resampled_template'], rtol=0, atol=0)
    rng = np.random.default_rng(9)
    data = rng.normal(size=(*shape, 16))
    xa = O.extract_raw_and_gs(data, a, ga['indices'])
    xb = V.extract_raw_and_gs(data, b, gb['indices'])
    for x, y in zip(xa, xb):
        np.testing.assert_allclose(x, y, rtol=0, atol=0)
    assert O.support_digest(shape, target, ga['indices']) == V.support_digest(shape, target, gb['indices'])


def test_nonfinite_unused_is_not_imputed_or_consumed():
    data = np.ones((3, 3, 3, 8))
    data[0, 0, 0, :] = np.nan
    support = np.array([13, 14])
    raw, gs = O.extract_raw_and_gs(data, [support], support)
    assert np.isfinite(raw).all() and np.isfinite(gs).all()
    with pytest.raises(ValueError, match='nonfinite_contributing'):
        O.extract_raw_and_gs(data, [np.array([0, 13])], support)
