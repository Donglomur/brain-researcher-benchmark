"""Small manufactured arrays only, independent source arithmetic qualification."""
import math

import numpy as np
import pytest
from scipy import linalg, signal

import source_numerics as s


@pytest.mark.parametrize("mode", ["full", "duplicate", "zero", "cutoff"])
def test_svd_minimum_norm_matches_distinct_gelsd_route(mode):
    rng = np.random.default_rng(3)
    maps = rng.normal(size=(4, 4, 4, 6))
    if mode == "duplicate": maps[..., 5] = maps[..., 2]
    if mode == "zero": maps[:] = 0
    if mode == "cutoff":
        maps[:] = 0
        maps.reshape(-1, 6)[:6] = np.diag([1., .1, .01, 4*s.EPS, s.EPS/4, 0])
    bold = rng.normal(size=(4, 4, 4, 8))
    basis = s.map_basis(maps)
    got = s.extract_coefficients(bold, basis)
    expected, _, rank, _ = linalg.lstsq(maps.reshape(-1, 6), bold.reshape(-1, 8), cond=s.EPS, lapack_driver="gelsd")
    assert got.shape == (8, 6) and np.isfinite(got).all()
    assert basis["rank"] == rank
    assert np.allclose(got, expected.T, atol=1e-8, rtol=1e-10)
    if mode == "duplicate": assert np.allclose(got[:, 2], got[:, 5], atol=1e-12)
    if mode == "zero": assert np.array_equal(got, np.zeros_like(got))


def test_exact_identity_geometry_no_interpolation():
    values = np.arange(3*4*5*2, dtype=float).reshape(3, 4, 5, 2) - 20
    affine = np.diag([2., 3., 4., 1.])
    got = s.resample_maps(values, affine, values.shape[:3], affine)
    assert np.array_equal(got, values) and not np.shares_memory(got, values)


def test_linear_translation_closed_boundary_negative_maps_retained():
    values = np.arange(4., dtype=float).reshape(4, 1, 1, 1) - 2.
    target = np.eye(4); target[0, 3] = .5
    got = s.resample_maps(values, np.eye(4), (4, 1, 1), target)
    assert np.array_equal(got[:, 0, 0, 0], [-1.5, -.5, .5, 0.])


def test_sheared_full_matrix_dispatch_shape():
    maps = np.ones((4, 4, 4, 2)); target = np.eye(4); target[0, 1] = .1
    got = s.resample_maps(maps, np.eye(4), (4, 4, 4), target)
    assert got.shape == maps.shape and np.all((got >= 0) & (got <= 1))


def test_detrend_has_no_mean_or_linear_component():
    t = np.arange(64.); values = np.column_stack([np.ones(64), 17 + .25*t, np.sin(t)])
    got = s.detrend(values)
    assert np.max(np.abs(got.mean(axis=0))) < 1e-14
    assert np.max(np.abs((t-t.mean()) @ got)) < 1e-11
    assert np.array_equal(values[:, 0], np.ones(64))


def test_cleaning_matches_explicit_declared_projection_and_support():
    rng = np.random.default_rng(514); raw = rng.normal(size=(80, 4)); conf = rng.normal(size=(80, 13))
    actual, diag = s.clean_coefficients(raw, conf)
    sos = signal.butter(5, [.01, .1], btype="bandpass", fs=.5, output="sos")
    y = signal.sosfiltfilt(sos, s.detrend(raw), axis=0, padtype="odd", padlen=33)
    z = signal.sosfiltfilt(sos, s.detrend(conf), axis=0, padtype="odd", padlen=33)
    z -= z.mean(axis=0); z /= z.std(axis=0)
    q, r, _ = linalg.qr(z, mode="economic", pivoting=True); q = q[:, np.abs(np.diag(r)) > 100*s.EPS]
    residual = y - (q @ q.T) @ y; residual -= residual.mean(axis=0)
    expected = residual / residual.std(axis=0, ddof=1)
    assert np.array_equal(actual, expected)
    assert np.array_equal(diag["residual_before_zscore"], residual)
    assert diag["projection_association"] == "(Q @ Q.T) @ Y"
    assert diag["confound_rank"] == 13 and diag["active"].all()
    assert np.allclose(actual.std(axis=0, ddof=1), 1., atol=1e-14)


@pytest.mark.parametrize("mode", ["constant", "zero", "nuisance_span", "tiny", "active_small"])
def test_canonical_activity_prevents_residual_noise_manufacture(mode):
    t = np.arange(80.); conf = np.column_stack([np.sin(.27*t), np.cos(.13*t)])
    values = {"constant": np.full(80, .1), "zero": np.zeros(80), "nuisance_span": conf[:, 0],
              "tiny": 1e-15*np.sin(.33*t), "active_small": 1e-8*np.sin(.33*t)}[mode]
    clean, diagnostic = s.clean_coefficients(values[:, None], conf)
    assert bool(diagnostic["active"][0]) is (mode == "active_small")
    if mode != "active_small": assert np.array_equal(clean, np.zeros_like(clean))
    if mode == "constant": assert diagnostic["raw_sample_sd"][0] == 0


def test_rank_deficient_and_constant_nuisance_columns_retained_but_not_rank():
    t = np.arange(80.); conf = np.column_stack([np.sin(.13*t), np.sin(.13*t), np.ones(80)])
    clean, diag = s.clean_coefficients(np.cos(.21*t)[:, None], conf)
    assert diag["confound_rank"] == 1 and diag["active"][0] and np.isfinite(clean).all()


@pytest.mark.parametrize("bad", [np.ones((33, 2)), np.full((64, 2), np.nan), np.ones((64, 2), dtype=bool), [[1, True]]])
def test_bad_raw_arrays_fail(bad):
    with pytest.raises(ValueError): s.clean_coefficients(bad, np.ones((64, 13)))


@pytest.mark.parametrize("bad", [True, 1., 0., np.nan])
def test_operational_clock_not_guessed(bad):
    with pytest.raises(ValueError): s.clean_coefficients(np.ones((64, 2)), np.ones((64, 13)), tr=bad)


def test_source_values_must_be_finite_before_projection():
    maps = np.ones((2, 2, 2, 3)); basis = s.map_basis(maps)
    bold = np.zeros((2, 2, 2, 40)); bold[0, 0, 0, 1] = np.inf
    with pytest.raises(ValueError): s.extract_coefficients(bold, basis)


@pytest.mark.parametrize("scale", [1e-100, 1., 1e100])
def test_scaled_centered_norm_and_exact_constant_guard(scale):
    x = scale * np.array([-2., -1., 1., 2.])
    assert s.centered_l2(x) == pytest.approx(scale * math.sqrt(10), rel=1e-14)
    assert s.centered_l2(np.full(50, .1*scale)) == 0.
