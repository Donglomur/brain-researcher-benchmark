"""Manufactured-only geometry/cleaning tests; no original source accesses."""
import hashlib
import math

import numpy as np
import pytest

import source_numerics as n


def manufactured(t=64):
    rng = np.random.default_rng(513)
    return rng.normal(size=(t, 48)), rng.normal(size=(t, 13)), np.ones(48, dtype=bool)


@pytest.mark.parametrize("bad", [True, [[1., True]], [np.nan], [np.inf], [1j], [object()]])
def test_typed_real_rejects_boolean_and_nonfinite(bad):
    with pytest.raises(ValueError): n.real_array(bad, 1)


@pytest.mark.parametrize("scale", [1., 1e-200, 1e200])
def test_stable_center_constant_and_scaled_norm(scale):
    x = np.array([-2., 1., 3., -1.]) * scale
    c, magnitude, norm = n.centered_components(x)
    assert math.isfinite(norm) and norm > 0
    assert norm / scale == pytest.approx(np.linalg.norm(np.array([-2., 1., 3., -1.]) - .25))
    assert n.centered_components(np.full(12, .1*scale))[2] == 0.
    assert np.all(np.isfinite(c)) and magnitude > 0


def test_full_matrix_nearest_translation_and_closed_domain(monkeypatch):
    atlas = np.arange(1, 5).reshape(4, 1, 1)
    target = np.eye(4); target[0, 3] = .5
    seen = []
    original = n.ndimage.affine_transform
    def wrapped(values, matrix, **kwargs):
        seen.append(np.asarray(matrix).shape)
        return original(values, matrix, **kwargs)
    monkeypatch.setattr(n.ndimage, "affine_transform", wrapped)
    result = n.resample_labels(atlas, np.eye(4), (4, 1, 1), target)
    assert seen == [(3, 3)]
    assert result[:, 0, 0].tolist() == [2, 3, 4, 0]


def test_exact_grid_copy_and_empty_support_preserved():
    grid = np.array([1, 2, 1, 0]).reshape(2, 2, 1)
    assert np.array_equal(n.resample_labels(grid, np.eye(4), grid.shape, np.eye(4)), grid)
    supports = n.support_records(grid, [1, 2, 3], np.eye(4))
    assert supports["n_voxels"].tolist() == [2, 1, 0]
    assert supports["geometry_present"].tolist() == [True, True, False]
    data = np.arange(8.).reshape(2, 2, 1, 2)
    result = n.parcel_means(data, supports)
    assert np.array_equal(result[:, 0], data.reshape(-1, 2)[[0, 2]].mean(axis=0))
    assert np.array_equal(result[:, 2], [0, 0])


def test_support_digest_binds_grid_affine_and_order():
    grid = np.ones((2, 1, 1), dtype=int)
    a = n.support_records(grid, [1], np.eye(4))["support_sha256"][0]
    expected = hashlib.sha256(b"FCVAR_support_v3\n" + np.asarray(grid.shape, dtype="<i8").tobytes()
                              + np.eye(4, dtype="<f8").tobytes() + np.array([0, 1], dtype="<i8").tobytes()).hexdigest()
    assert a == expected
    shifted = np.eye(4); shifted[0, 3] = 1.
    assert a != n.support_records(grid, [1], shifted)["support_sha256"][0]
    assert a != n.support_records(grid.reshape(1, 2, 1), [1], np.eye(4))["support_sha256"][0]


def test_nonfinite_outside_roi_ignored_but_all_contributing_voxels_required():
    grid = np.array([1, 0, 2]).reshape(3, 1, 1)
    support = n.support_records(grid, [1, 2], np.eye(4))
    data = np.array([1., np.nan, 2.]).reshape(3, 1, 1, 1)
    assert np.array_equal(n.parcel_means(data, support), [[1., 2.]])
    data[2] = np.nan
    with pytest.raises(ValueError, match="contributing"):
        n.parcel_means(data, support)


@pytest.mark.parametrize("bad", [True, 0, .1, 10., np.nan, 7.])
def test_invalid_source_tr(bad):
    raw, confounds, geometry = manufactured()
    with pytest.raises(ValueError): n.clean_roi_signals(raw, confounds, bad, geometry)


def test_constants_and_geometry_empty_never_become_active():
    raw, confounds, geometry = manufactured()
    raw[:, 0] = .1
    raw[:, 1] = 0.; geometry[1] = False
    got = n.clean_roi_signals(raw, confounds, 2., geometry)
    assert not got["active"][:2].any()
    assert np.all(got["clean"][:, :2] == 0.)
    assert got["raw_sample_sd"][0] == 0.
    assert 0 <= got["cleaning_rank"] <= 13


def test_geometry_empty_nonzero_source_is_not_imputation():
    raw, confounds, geometry = manufactured(); geometry[0] = False
    with pytest.raises(ValueError, match="sentinel"):
        n.clean_roi_signals(raw, confounds, 2., geometry)


@pytest.mark.parametrize("mode", ["random", "rank_deficient", "constant", "tiny_units", "fortran_inputs"])
def test_independent_cleaner_matches_declared_shared_recipe(mode):
    # This is an explicit public-recipe cross-check, not proof of universal
    # Nilearn.clean equivalence. Both paths share low-level SOS/QR dependencies.
    import signal_kernel as kernel
    raw, confounds, geometry = manufactured()
    if mode == "rank_deficient": confounds[:, 1:] = confounds[:, :1]
    if mode == "constant": raw[:, 0] = .1; confounds[:, 3] = 0.
    if mode == "tiny_units": raw *= 1e-100
    if mode == "fortran_inputs": raw, confounds = np.asfortranarray(raw), np.asfortranarray(confounds)
    got = n.clean_roi_signals(raw, confounds, 2., geometry)
    expected = kernel.clean_roi_signals(raw, confounds, 2., geometry)
    assert np.array_equal(got["active"], expected["active"])
    assert got["cleaning_rank"] == expected["cleaning_rank"]
    for key in ("clean", "raw_sample_sd", "prestandardization_centered_l2", "activity_threshold", "full_clean_centered_l2"):
        assert np.allclose(got[key], expected[key], rtol=1e-12, atol=0.)
