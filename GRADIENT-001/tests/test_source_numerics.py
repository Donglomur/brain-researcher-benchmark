"""Manufactured extraction/cleaning only; no source files or oracle imports."""
import hashlib

import numpy as np
import pytest
from scipy import signal

import source_numerics as n


def test_identity_labels_and_no_input_mutation():
    labels = np.arange(8).reshape(2, 2, 2)
    result = n.resample_labels(labels, np.eye(4), (2, 2, 2), np.eye(4))
    assert np.array_equal(result, labels) and not np.shares_memory(result, labels)


def test_nearest_translation_closed_edge_and_no_rescue():
    labels = np.arange(1, 4)[:, None, None]
    affine = np.eye(4); affine[0, 3] = .5
    result = n.resample_labels(labels, np.eye(4), (4, 1, 1), affine)
    assert result[:, 0, 0].tolist() == [2, 3, 0, 0]
    affine[0, 3] = -.5
    assert n.resample_labels(labels, np.eye(4), (4, 1, 1), affine)[:, 0, 0].tolist() == [0, 2, 3, 0]


@pytest.mark.parametrize("mode", ["fractional", "negative", "bool", "nonfinite", "affine", "shape"])
def test_invalid_geometry(mode):
    labels = np.ones((2, 2, 2))
    affine = np.eye(4); shape = (2, 2, 2)
    if mode == "fractional": labels[0, 0, 0] = 1.5
    elif mode == "negative": labels[0, 0, 0] = -1
    elif mode == "bool": labels = labels.astype(bool)
    elif mode == "nonfinite": labels[0, 0, 0] = np.nan
    elif mode == "affine": affine[3, 0] = 1
    else: shape = (2, True, 2)
    with pytest.raises(ValueError): n.resample_labels(labels, affine, shape, np.eye(4))


def test_c_order_support_hash_and_empty_parcels_retained():
    grid = np.array([[[2, 1], [0, 2]], [[1, 2], [0, 0]]])
    support = n.parcel_support(grid, [1, 2, 3])
    assert [x.tolist() for x in support["indices"]] == [[1, 4], [0, 3, 5], []]
    assert support["counts"].tolist() == [2, 3, 0]
    assert support["sha256"][0] == hashlib.sha256(np.array([1, 4], dtype="<i8").tobytes()).hexdigest()
    assert support["sha256"][2] == hashlib.sha256(b"").hexdigest()
    result = n.volume_means(np.arange(8.).reshape(2, 2, 2), support)
    assert result[0] == 2.5 and result[1] == 8 / 3 and np.isnan(result[2])


def test_float64_voxel_mean_before_any_storage_rounding():
    support = n.parcel_support(np.ones((3, 1, 1)), [1])
    values = np.array([1e8, 1, -1e8], dtype=np.float32).reshape(3, 1, 1)
    assert n.volume_means(values, support)[0] == 1 / 3


@pytest.mark.parametrize("mode", ["unknown_label", "nonfinite_volume", "wrong_grid"])
def test_source_mean_preconditions(mode):
    support = n.parcel_support(np.ones((2, 2, 2)), [1, 2])
    volume = np.ones((2, 2, 2))
    with pytest.raises(ValueError):
        if mode == "unknown_label": n.parcel_support(np.full((2, 2, 2), 3), [1, 2])
        elif mode == "nonfinite_volume":
            volume[0, 0, 0] = np.nan
            n.volume_means(volume, support)
        else: n.volume_means(np.ones((3, 2, 2)), support)


def test_exact_constant_detrend_zero_and_linear_trend_removal():
    values = np.column_stack([np.full(168, .1), np.arange(168.) * 2 + 3])
    result = n.detrend(values)
    assert np.array_equal(result[:, 0], np.zeros(168))
    assert np.max(np.abs(result[:, 1])) < 1e-12
    assert np.all(values[:, 0] == .1)


def test_clean_both_arms_shared_projection_then_filter_not_joint_filter():
    rng = np.random.default_rng(91)
    raw = rng.normal(size=(168, 4))
    confounds = rng.normal(size=(168, 3))
    confounds[:, 2] = confounds[:, 1]
    result = n.reconstruct_person(raw, confounds, np.ones(4, bool))
    assert result["nuisance_rank"] == 2
    y = result["cleaned_series"][0]
    expected = signal.sosfiltfilt(signal.butter(5, [.01, .1], fs=.5, btype="bandpass", output="sos"),
                               y, axis=0, padtype="odd", padlen=33)
    np.testing.assert_array_equal(result["cleaned_series"][1], expected)
    np.testing.assert_allclose(n.detrend(confounds).T @ y, 0, atol=1e-11)
    assert result["person_parcel_active"].all()
    for arm in range(2):
        np.testing.assert_allclose(result["fc"][arm], np.corrcoef(result["cleaned_series"][arm].T), atol=1e-14)


def test_nuisance_removed_constant_and_empty_geometry_are_accounted_not_rescued():
    time = np.arange(168.)
    raw = np.column_stack([np.full(168, .1), np.sin(time / 9), np.full(168, np.nan)])
    result = n.reconstruct_person(raw, np.sin(time / 9)[:, None], np.array([True, True, False]))
    assert not result["person_parcel_active"].any()
    assert np.isnan(result["fc"]).all()
    assert np.isnan(result["cleaned_series"][:, :, 2]).all()
    assert np.array_equal(result["cleaned_series"][:, :, 0], np.zeros((2, 168)))


@pytest.mark.parametrize("mode", ["short", "confound_nan", "raw_bool", "mask_integer", "present_nan", "absent_finite"])
def test_cleaning_precondition_rejections(mode):
    raw = np.arange(168.)[:, None]; confounds = np.zeros((168, 1)); mask = np.array([True])
    if mode == "short": raw, confounds = raw[:33], confounds[:33]
    elif mode == "confound_nan": confounds[0, 0] = np.nan
    elif mode == "raw_bool": raw = raw.astype(bool)
    elif mode == "mask_integer": mask = mask.astype(int)
    elif mode == "present_nan": raw[0, 0] = np.nan
    else: mask[:] = False
    with pytest.raises(ValueError): n.reconstruct_person(raw, confounds, mask)


def test_single_active_parcel_diagonal_and_no_inactive_fc_imputation():
    data = np.column_stack([np.arange(5.), np.ones(5)])
    fc = n.canonical_fc(data, np.array([True, False]))
    assert fc[0, 0] == 1 and np.isnan(fc[1]).all() and np.isnan(fc[:, 1]).all()
    assert np.isnan(n.canonical_fc(data, np.zeros(2, bool))).all()


def test_complete_group_keeps_invalid_person_and_half_membership():
    fc = np.repeat(np.eye(3)[None], 3, axis=0)
    fc[:, 0, 1] = [.2, .4, .9]; fc[:, 1, 0] = fc[:, 0, 1]
    active = np.ones((3, 3), bool); active[2, 2] = False
    fc[2, 2, :] = np.nan; fc[2, :, 2] = np.nan
    full, full_mask = n.group_connectivity(fc, active, np.ones(3, bool))
    half, half_mask = n.group_connectivity(fc, active, np.array([True, True, False]))
    assert full_mask.tolist() == [True, True, False]
    assert np.isnan(full[2]).all() and full[0, 1] == np.mean([.2, .4, .9])
    assert half_mask.all() and half[0, 1] == np.mean([.2, .4])


def test_group_rejects_nonfinite_claimed_complete_support():
    fc = np.repeat(np.eye(3)[None], 2, axis=0); fc[1, 0, 1] = np.nan
    with pytest.raises(ValueError, match="nonfinite"):
        n.group_connectivity(fc, np.ones((2, 3), bool), np.ones(2, bool))
