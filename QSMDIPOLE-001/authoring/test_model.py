"""Small equation fixtures, never source-data reconstructions or reference banks."""
import ast
import importlib.util
from pathlib import Path

import numpy as np
import pytest
from scipy import fft

TASK = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("qsm_independent", TASK / "authoring/check_independent.py")
independent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(independent)


def oracle_functions():
    tree = ast.parse((TASK / "solution/compute.py").read_text())
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name in {"dipole_kernel", "gradient_operator", "cf_l2"}]
    namespace = {"np": np}
    exec(compile(ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[])),
                 "oracle_numerical_functions_only", "exec"), namespace)
    return namespace


@pytest.mark.parametrize("size", [6, 8, 12])
@pytest.mark.parametrize("voxel", [[1., 1., 1.], [1.0625, 1.0625, 1.0714285714285714], [.8, 1.2, 2.1]])
def test_matlab_frequency_and_sine_kernel_match_modern_recipe(size, voxel):
    oracle = oracle_functions()
    shape = (size,)*3
    d, e = independent.matlab_kernels(shape, voxel)
    original_d = oracle["dipole_kernel"](shape, voxel, 2)[:, :, :size//2+1]
    original_e = oracle["gradient_operator"](shape)[:, :, :size//2+1]
    assert d[0, 0, 0] == original_d[0, 0, 0] == 1/3
    assert np.allclose(d, original_d, atol=1e-12, rtol=0)
    assert np.allclose(e, original_e, atol=1e-14, rtol=1e-14)


@pytest.mark.parametrize("size", [6, 10, 14])
def test_random_source_independent_fft_and_normal_equation(size):
    oracle = oracle_functions()
    shape, voxel = (size,)*3, [1.0625, 1.0625, 1.0714285714285714]
    rng = np.random.default_rng(431)
    field = rng.normal(0, .03, shape)
    mask = rng.random(shape) > .2
    pre, masked, _, _, _ = independent.independent_reconstruction(field, mask, voxel)
    expected_pre = oracle["cf_l2"](field, np.ones(shape, bool), voxel, 2, .09)
    expected_masked = oracle["cf_l2"](field, mask, voxel, 2, .09)
    assert np.allclose(pre, expected_pre, atol=1e-12, rtol=1e-12)
    assert np.allclose(masked, expected_masked, atol=1e-12, rtol=1e-12)
    report = independent.check_normal_equation(expected_pre, field, voxel)
    assert report["relative_spectral_normal_equation_residual"] < 1e-12
    assert report["dc_mean_absolute_error_ppm"] < 1e-15
    assert np.equal(masked[~mask], 0).all()


def test_constant_field_dc_convention_not_zero_mean():
    field, mask = np.full((8, 8, 8), .12), np.ones((8, 8, 8), bool)
    pre, result, _, _, _ = independent.independent_reconstruction(field, mask, [1, 1, 1])
    assert np.allclose(pre, .36, atol=1e-15)
    assert np.allclose(result, .36, atol=1e-15)


def test_field_constant_offset_adds_threefold_masked_offset():
    rng = np.random.default_rng(5)
    field = rng.normal(0, .1, (8, 8, 8))
    mask = rng.random(field.shape) > .3
    _, original, *_ = independent.independent_reconstruction(field, mask, [1, 1, 1])
    _, shifted, *_ = independent.independent_reconstruction(field+.04, mask, [1, 1, 1])
    assert np.allclose(shifted-original, .12*mask, atol=1e-14)


@pytest.mark.parametrize("axis,dipole", [(0, 1/3), (1, 1/3), (2, -2/3)])
def test_single_fourier_mode_gain(axis, dipole):
    n = 12
    coords = np.indices((n,)*3)
    field = np.cos(2*np.pi*coords[axis]/n)
    _, reconstructed, *_ = independent.independent_reconstruction(field, np.ones_like(field, bool), [1, 1, 1])
    penalty = 4*np.sin(np.pi/n)**2
    gain = dipole/(dipole*dipole+.09*penalty)
    assert np.allclose(reconstructed, gain*field, atol=1e-12, rtol=1e-12)


def test_mixed_fourier_mode_uses_physical_voxel_spacing():
    n, voxel = 12, np.array([.8, 1.1, 1.7])
    coords, mode = np.indices((n,)*3), np.array([1, 0, 2])
    field = np.cos(2*np.pi*np.sum(mode[:, None, None, None]*coords, axis=0)/n)
    k = mode/(n*voxel)
    d = 1/3-k[2]**2/(k @ k)
    e = 4*np.sum(np.sin(np.pi*mode/n)**2)
    _, actual, *_ = independent.independent_reconstruction(field, np.ones_like(field, bool), voxel)
    assert np.allclose(actual, d/(d*d+.09*e)*field, atol=1e-12)


def test_final_mask_does_not_preserve_spectral_normal_equation():
    field = np.ones((8, 8, 8))*.1
    mask = np.zeros_like(field, bool)
    mask[:4] = True
    pre, masked, *_ = independent.independent_reconstruction(field, mask, [1, 1, 1])
    good = independent.check_normal_equation(pre, field, [1, 1, 1])
    bad = independent.check_normal_equation(masked, field, [1, 1, 1])
    assert good["relative_spectral_normal_equation_residual"] < 1e-12
    assert bad["relative_spectral_normal_equation_residual"] > .1


def test_half_spectrum_norm_equals_complete_complex_spectrum():
    field = np.random.default_rng(9).normal(size=(10,)*3)
    expected = np.linalg.norm(fft.fftn(field))
    actual = independent.spectral_norm(fft.rfftn(field), field.shape)
    assert actual == pytest.approx(expected, rel=1e-14)


def test_even_cubic_source_shape_is_explicit():
    with pytest.raises(AssertionError):
        independent.matlab_kernels((7, 7, 7), [1, 1, 1])
    with pytest.raises(AssertionError):
        independent.matlab_kernels((8, 6, 8), [1, 1, 1])
