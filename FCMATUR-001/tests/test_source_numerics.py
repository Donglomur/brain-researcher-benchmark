"""Manufactured independent signed-Fisher primitives; no original inputs."""
import importlib.util
import math
from pathlib import Path

import numpy as np
import pytest

SPEC = importlib.util.spec_from_file_location('fcmatur_independent_numerics_fixture', Path(__file__).with_name('source_numerics.py'))
n = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(n)


def test_signed_fisher_all_edges_without_diagonal():
    x = np.arange(5, dtype=float)
    got = n.connectivity(np.column_stack((x, x, -x, np.full(5, .1))))
    assert got['active_columns'] == [True, True, True, False]
    assert got['n_active_columns'] == 3 and got['n_edges'] == 3
    assert got['connectivity'] == pytest.approx(-math.atanh(.999)/3, abs=1e-14)
    assert got['connectivity'] < 0


@pytest.mark.parametrize('mode', ['constant', 'single_active'])
def test_undefined_not_fabricated_zero(mode):
    x = np.full((6, 4), .1)
    if mode == 'single_active': x[:, 2] = np.arange(6)
    got = n.connectivity(x)
    assert got['connectivity'] is None and got['status'] == 'insufficient_active_columns'
    assert got['n_edges'] == 0


@pytest.mark.parametrize('scale', [1., 1e-300, 1e300])
def test_no_unit_threshold_or_square_underflow(scale):
    t = np.linspace(-1, 1, 7)*scale
    got = n.connectivity(np.column_stack((t, -t)))
    assert got['active_columns'] == [True, True]
    assert got['connectivity'] == pytest.approx(-math.atanh(.999), abs=1e-14)


def test_represented_large_offset_small_variation_preserved():
    x = 1e12+np.arange(8)*np.spacing(1e12)
    got = n.connectivity(np.column_stack((x, x)))
    assert got['n_active_columns'] == 2
    assert got['connectivity'] == pytest.approx(math.atanh(.999), abs=1e-14)


def test_opposite_extreme_signs_centering_no_overflow():
    x = np.array([-1e308, 1e308, -1e308, 1e308])
    got = n.connectivity(np.column_stack((x, -x)))
    assert got['connectivity'] == pytest.approx(-math.atanh(.999), abs=1e-14)


def test_smallest_subnormal_not_dropped():
    x = np.array([0., 5e-324, 0., 5e-324])
    assert n.connectivity(np.column_stack((x, x)))['n_active_columns'] == 2


@pytest.mark.parametrize('value', [np.nan, np.inf, -np.inf])
def test_nonfinite_in_constant_or_active_column_fails(value):
    x = np.column_stack((np.arange(5), np.full(5, value)))
    with pytest.raises(ValueError, match='nonfinite'): n.connectivity(x)


@pytest.mark.parametrize('value', [np.ones(3), np.ones((1, 3)), np.zeros((0, 3)), np.ones((3, 0)),
    np.ones((3, 2), dtype=bool), np.ones((3, 2), dtype=complex), np.ones((3, 2), dtype=object),
    [[1., True], [2., 3.]], [['1', '2'], ['3', '4']]])
def test_typed_dimensions(value):
    with pytest.raises(ValueError): n.connectivity(value)


def test_mean_fisher_not_fisher_of_mean_r_and_row_column_equivalences():
    x = np.random.default_rng(195).normal(size=(17, 4))
    r = np.corrcoef(x.T)[np.triu_indices(4, 1)]
    expected = math.fsum(np.arctanh(np.clip(r, -.999, .999)))/6
    actual = n.connectivity(x)
    assert actual['connectivity'] == pytest.approx(expected, abs=1e-14)
    assert abs(expected-math.atanh(float(np.mean(r)))) > 1e-6
    for altered in (x[::-1], x[:, ::-1], np.asfortranarray(x), x*3+7):
        assert n.connectivity(altered)['connectivity'] == pytest.approx(expected, abs=1e-14)


def test_no_downstream_or_old_estimator_imports():
    import ast
    tree = ast.parse(Path(n.__file__).read_text())
    names = [a.name for node in ast.walk(tree) if isinstance(node, ast.Import) for a in node.names]
    names += [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert set(names) <= {'math', 'numpy'}
