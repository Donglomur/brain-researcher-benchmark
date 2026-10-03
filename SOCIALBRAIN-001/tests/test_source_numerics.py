"""Manufactured arrays only; upstream comparisons never load packaged templates."""
import hashlib
import inspect
import math
import warnings
from importlib.metadata import version

import nibabel as nib
import numpy as np
import pytest
from scipy import linalg
from nilearn import masking, signal
from nilearn.datasets import struct
from nilearn.image import resample_to_img
from nilearn.maskers.nifti_spheres_masker import apply_mask_and_get_affinity

import reporting_kernel as reporting
import source_numerics as m


def image(array, affine):
    return nib.Nifti1Image(array, affine)


def transforms(case):
    affine = np.eye(4)
    if case == 'scaled': affine[:3, :3] = np.diag([2., 3., 1.5])
    elif case == 'reflected': affine[:3, :3] = np.diag([-2., 1., 3.])
    elif case == 'oblique': affine[:3, :3] = [[1., .25, .125], [.125, 1.5, 0.], [0., .2, 2.]]
    elif case == 'fractional': affine[:3, :3] *= .25
    affine[:3, 3] = [-.4, .3, -1.2]
    return affine


def test_qualification_versions_and_no_source_loader_import():
    for name, expected in {'numpy': '2.1.3', 'scipy': '1.14.1', 'scikit-learn': '1.5.2',
                           'nibabel': '5.3.2', 'nilearn': '0.12.1'}.items():
        assert version(name) == expected
    text = inspect.getsource(m)
    assert 'from nilearn' not in text and 'import nilearn' not in text
    assert 'import reporting_kernel' not in text and 'source_reference' not in text


@pytest.mark.parametrize('case', ['identity', 'scaled', 'reflected', 'oblique', 'fractional'])
@pytest.mark.parametrize('radius', [0., .6, 2.])
def test_sphere_support_exact_upstream(case, radius):
    shape, affine = (9, 8, 7), transforms(case)
    voxel_centers = np.array([[2., 3., 2.], [2.5, 3.5, 2.5], [4.04, 2.49, 1.5]])
    centers = (affine @ np.c_[voxel_centers, np.ones(3)].T)[:3].T
    supports = m.sphere_supports(shape, affine, centers, radius)
    _, expected = apply_mask_and_get_affinity(centers, image(np.zeros((*shape, 2)), affine),
                                             radius, True, mask_img=None)
    for actual, indices in zip(supports, expected.rows):
        np.testing.assert_array_equal(actual, np.asarray(sorted(indices)))


def test_both_seed_additions_not_pure_radius():
    shape, affine = (5, 3, 3), np.diag([.25, 1., 1., 1.])
    support = m.sphere_supports(shape, affine, [[.51, 1., 1.]], radius=.001)[0]
    assert set(support) == {np.ravel_multi_index((0, 1, 1), shape),
                            np.ravel_multi_index((2, 1, 1), shape)}


def test_radius_boundary_and_half_voxel_round_to_even():
    shape = (5, 5, 5)
    support = m.sphere_supports(shape, np.eye(4), [[2., 2., 2.]], 1.)[0]
    assert len(support) == 7
    half = m.sphere_supports(shape, np.eye(4), [[.5, 2., 2.]], 0.)[0]
    np.testing.assert_array_equal(half, [np.ravel_multi_index((0, 2, 2), shape)])


def test_empty_sphere_fails_not_moved_or_dropped():
    with pytest.raises(ValueError, match='empty_sphere_support'):
        m.sphere_supports((5, 5, 5), np.eye(4), [[100., 100., 100.]], .1)


def template_values():
    values = np.zeros((16, 15, 14), dtype=np.float64)
    values[2:14, 2:13, 2:12] = np.linspace(.1, 2., 12 * 11 * 10).reshape(12, 11, 10)
    return values


def test_float32_template_loader_equivalence_without_packaged_asset(monkeypatch):
    values, affine = template_values(), np.diag([1., 1., 1., 1.])
    synthetic = image(values, affine)
    monkeypatch.setattr(struct, 'MNI152_FILE_PATH', synthetic)
    struct.load_mni152_template.cache_clear()
    try:
        expected = np.asarray(struct.load_mni152_template(resolution=1).dataobj)
    finally:
        struct.load_mni152_template.cache_clear()
    actual, maximum = m.normalize_template(values)
    assert actual.dtype == np.float32 and maximum == float(values.astype(np.float32).max())
    np.testing.assert_array_equal(actual, expected)
    assert values.dtype == np.float64 and values.max() == 2.


@pytest.mark.parametrize('case', ['same', 'near_affine', 'larger_equal_affine', 'integer_positive',
                                 'integer_negative', 'diagonal', 'oblique', 'reflection'])
def test_resample_branches_match_upstream(case):
    values, _ = m.normalize_template(template_values())
    source = np.eye(4)
    target = source.copy()
    shape = values.shape
    if case == 'near_affine': target[0, 3] = 1e-9
    elif case == 'larger_equal_affine': shape = (18, 17, 16)
    elif case == 'integer_positive': target[:3, 3] = [3., 1., 0.]
    elif case == 'integer_negative': target[:3, 3] = [-2., 0., -1.]
    elif case == 'diagonal': target[:3, :3] = np.diag([1.15, .9, 1.1])
    elif case == 'oblique': target[:3, :3] = [[1., .1, .03], [0., 1.1, .1], [0., 0., .9]]
    elif case == 'reflection': target[0, 0] = -1.; target[0, 3] = 15.
    actual, branch = m.resample_template(values, source, shape, target)
    expected = np.asarray(resample_to_img(image(values, source), image(np.zeros(shape), target),
        interpolation='continuous', copy=True, order='F', clip=False, fill_value=0,
        force_resample=False, copy_header=True).dataobj)
    np.testing.assert_array_equal(actual, expected)
    if case in ('same', 'near_affine'): assert branch == 'allclose_equal_shape_noop'
    elif case in ('larger_equal_affine', 'integer_positive', 'integer_negative'):
        assert branch == 'integer_translation_crop_padding'
    elif case == 'oblique': assert branch == 'cubic_full_matrix'
    else: assert branch == 'cubic_diagonal'
    assert not np.shares_memory(actual, values)


def test_cubic_values_are_not_clipped():
    values = np.zeros((16, 15, 14), dtype=np.float32)
    values[3:13, 3:12, 3:11] = 1.
    target = np.eye(4)
    target[:3, 3] = .4
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', UserWarning)
        actual, _ = m.resample_template(values, np.eye(4), values.shape, target)
        expected = np.asarray(resample_to_img(image(values, np.eye(4)), image(values, target),
            force_resample=False, copy_header=True, clip=False).dataobj)
    np.testing.assert_array_equal(actual, expected)
    assert actual.min() < 0 and actual.max() > 1


@pytest.mark.parametrize('case', ['one_component', 'two_components', 'same_size_tie', 'resampled'])
def test_global_mask_morphology_exact_upstream(monkeypatch, case):
    values = np.zeros((31, 31, 31), dtype=np.float64)
    values[3:15, 3:15, 3:15] = 5.
    if case == 'two_components': values[21:29, 21:29, 21:29] = 5.
    if case == 'same_size_tie': values[17:29, 17:29, 17:29] = 5.
    affine = np.eye(4)
    target = affine.copy()
    if case == 'resampled': target[:3, :3] = np.diag([1.1, 1.05, 1.1])
    normalized, _ = m.normalize_template(values)
    monkeypatch.setattr(masking, 'load_mni152_template',
                        lambda resolution: image(normalized, affine))
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', UserWarning)
        expected = np.asarray(masking.compute_brain_mask(image(np.zeros(values.shape), target),
            threshold=.5, connected=True, opening=2).dataobj).astype(bool)
        actual = m.global_support(values, affine, values.shape, target)
    np.testing.assert_array_equal(actual['mask'], expected)
    np.testing.assert_array_equal(actual['indices'], np.flatnonzero(expected))
    assert actual['normalization_maximum'] == 5.


def test_empty_global_mask_fails_precondition():
    with pytest.raises(ValueError, match='empty_global_support'):
        m.global_support(np.ones((3, 3, 3)), np.eye(4), (3, 3, 3), np.eye(4))


@pytest.mark.parametrize('features', [1, 12, 499, 500, 503])
@pytest.mark.parametrize('layout', ['C', 'F', 'strided'])
def test_detrend_exact_reference_batched(features, layout):
    rng = np.random.default_rng(410)
    values = rng.normal(size=(37, features)) + np.arange(37)[:, None] * .25
    if layout == 'F': values = np.asfortranarray(values)
    elif layout == 'strided': values = np.repeat(values, 2, axis=0)[::2]
    before = values.copy()
    expected = signal._detrend(np.array(values, dtype=np.float64, order='C', copy=True))
    np.testing.assert_array_equal(m.detrend(values), expected)
    np.testing.assert_array_equal(values, before)


@pytest.mark.parametrize('layout', ['C', 'F', 'bigendian', 'float32'])
@pytest.mark.parametrize('gs_size', [90, 520])
def test_raw_roi_gs_means_finite_support_layout(layout, gs_size):
    rng = np.random.default_rng(822)
    values = rng.normal(size=(10, 9, 8, 32)) + np.arange(32)[None, None, None, :]
    if layout == 'F': values = np.asfortranarray(values)
    elif layout == 'bigendian': values = values.astype('>f8')
    elif layout == 'float32': values = values.astype('f4')
    supports = [np.arange(3, 41), np.arange(35, 80), np.arange(200, 215)]
    gs = np.arange(gs_size)
    raw, global_signal = m.extract_raw_and_gs(values, supports, gs)
    flat = np.asarray(values, dtype=np.float64).reshape(-1, 32)
    expected = np.column_stack([[np.mean(np.ascontiguousarray(flat[indices, frame]), dtype=np.float64)
                                for frame in range(32)] for indices in supports])
    voxel_rows = np.ascontiguousarray(flat[gs].T)
    voxel_clean = signal._detrend(voxel_rows)
    expected_gs = np.asarray([np.mean(row, dtype=np.float64) for row in voxel_clean])
    np.testing.assert_array_equal(raw, expected)
    np.testing.assert_array_equal(global_signal, expected_gs)


@pytest.mark.parametrize('bad', [np.nan, np.inf, -np.inf])
def test_nonfinite_unused_allowed_contributing_refused(bad):
    values = np.ones((4, 4, 4, 8))
    values[-1, -1, -1] = bad
    raw, gs = m.extract_raw_and_gs(values, [np.arange(8)], np.arange(16))
    assert np.isfinite(raw).all() and np.isfinite(gs).all()
    values[0, 0, 0, 3] = bad
    with pytest.raises(ValueError, match='nonfinite_contributing_values'):
        m.extract_raw_and_gs(values, [np.arange(8)], np.arange(16))


@pytest.mark.parametrize('case', ['ordinary', 'constant', 'duplicate', 'near_collinear', 'more_than_frames'])
@pytest.mark.parametrize('layout', ['C', 'F', 'float32'])
def test_cleaning_operator_upstream_and_rank(case, layout):
    rng = np.random.default_rng(509)
    y = rng.normal(size=(48, 4)) + .1 * np.arange(48)[:, None]
    x = rng.normal(size=(48, 15))
    if case == 'constant': x[:] = 2. / 3.; y[:, 0] = 2. / 3.
    elif case == 'duplicate': x[:, 3] = x[:, 2]; x[:, 8] = x[:, 2]
    elif case == 'near_collinear': x[:, 4] = x[:, 3] + 1e-13 * x[:, 5]
    elif case == 'more_than_frames': x = rng.normal(size=(48, 60))
    if layout == 'F': y, x = np.asfortranarray(y), np.asfortranarray(x)
    elif layout == 'float32': y, x = y.astype('f4'), x.astype('f4')
    y64, x64 = np.array(y, dtype='f8', order='C'), np.array(x, dtype='f8', order='C')
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', DeprecationWarning)
        warnings.simplefilter('ignore', RuntimeWarning)
        expected = signal.clean(y64, confounds=x64, detrend=True, standardize='zscore_sample',
                                standardize_confounds=True, low_pass=None, high_pass=None)
        z = signal.standardize_signal(signal._detrend(x64), standardize=True, detrend=False)
    q, triangular, pivots = linalg.qr(z, mode='economic', pivoting=True)
    keep = np.abs(np.diag(triangular)) > 100 * np.finfo(float).eps
    q = q[:, keep]
    expected_residual = signal._detrend(y64) - q.dot(q.T).dot(signal._detrend(y64))
    actual = m.clean_roi(y, x, activity_fn=lambda residual, raw: True)
    np.testing.assert_array_equal(actual['cleaned'], expected)
    np.testing.assert_array_equal(actual['residual'], expected_residual)
    np.testing.assert_array_equal(actual['pivots'], pivots)
    assert actual['rank'] == int(keep.sum())


def test_declared_guard_blocks_constant_and_fully_explained_roundoff():
    rng = np.random.default_rng(728)
    x = rng.normal(size=(64, 3))
    y = np.column_stack([np.full(64, 2. / 3.), x[:, 0] * 1000., rng.normal(size=64)])
    actual = m.clean_roi(y, x, activity_fn=reporting.residual_active)
    np.testing.assert_array_equal(actual['active'], [False, False, True])
    assert np.all(actual['cleaned'][:, :2] == 0)
    assert actual['raw_centered_l2'][0] == 0
    assert actual['rank'] == 3


@pytest.mark.parametrize('scale', [1e-18, math.ldexp(1., -600)])
def test_legacy_sample_sd_floor_retains_small_amplitude_on_active_columns(scale):
    t = np.arange(64, dtype=float)
    y = (scale * np.sin(t * .7))[:, None]
    actual = m.clean_roi(y, np.zeros((64, 1)), activity_fn=reporting.residual_active)
    assert actual['active'].tolist() == [True]
    assert actual['standardization_denominator'].tolist() == [1.]
    assert 0 < actual['raw_centered_l2'][0] < 100 * scale
    assert np.max(np.abs(actual['cleaned'])) < 2 * scale
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', DeprecationWarning)
        expected = signal.clean(y, confounds=np.zeros((64, 1)), detrend=True,
                                standardize='zscore_sample', standardize_confounds=True)
    np.testing.assert_array_equal(actual['cleaned'], expected)


def test_gsr_is_appended_then_detrended_again():
    rng = np.random.default_rng(826)
    raw, confounds, gs = rng.normal(size=(64, 12)), rng.normal(size=(64, 15)), rng.normal(size=64)
    without = m.clean_roi(raw, confounds, activity_fn=reporting.residual_active)
    with_gsr = m.clean_roi(raw, np.column_stack([confounds, gs]), activity_fn=reporting.residual_active)
    assert without['rank'] == 15 and with_gsr['rank'] == 16
    assert with_gsr['cleaned'].shape == (64, 12) and with_gsr['active'].all()
    assert not np.array_equal(without['residual'], with_gsr['residual'])


def test_activity_callback_gets_prestandardization_source_not_receipts():
    raw = np.arange(30, dtype=float).reshape(10, 3) + np.sin(np.arange(10))[:, None]
    seen = []
    def callback(residual, original):
        seen.append((residual.copy(), original.copy()))
        return False
    result = m.clean_roi(raw, np.zeros((10, 1)), activity_fn=callback)
    assert len(seen) == 3 and np.all(result['cleaned'] == 0)
    for index, (residual, original) in enumerate(seen):
        np.testing.assert_array_equal(original, raw[:, index])
        np.testing.assert_array_equal(residual, result['residual'][:, index])
    with pytest.raises(ValueError, match='activity_callback_bool'):
        m.clean_roi(raw, np.zeros((10, 1)), activity_fn=lambda *_: 1)


def test_support_digest_grid_and_signed_zero():
    shape, affine, indices = (5, 6, 7), np.eye(4), np.array([1, 5, 19])
    expected = hashlib.sha256(b'SOCIALBRAIN_support_v2\n' + np.asarray(shape, dtype='<i8').tobytes() +
        affine.astype('<f8').tobytes() + indices.astype('<i8').tobytes()).hexdigest()
    assert m.support_digest(shape, affine, indices) == expected
    affine[0, 1] = -0.
    assert m.support_digest(shape, affine, indices) == expected
    affine[0, 3] = 1.
    assert m.support_digest(shape, affine, indices) != expected


@pytest.mark.parametrize('indices', [[], [1., 2.], [True], [-1], [3, 2], [1, 1], [64]])
def test_support_indices_fail_closed(indices):
    with pytest.raises(ValueError): m.checked_support(indices, 64)


@pytest.mark.parametrize('operation', [
    lambda: m.detrend(np.ones((1, 2))),
    lambda: m.detrend(np.full((8, 2), np.nan)),
    lambda: m.detrend(np.ones((8, 2), dtype=bool)),
    lambda: m.normalize_template(np.zeros((5, 5, 5))),
    lambda: m.normalize_template(np.full((5, 5, 5), np.inf)),
    lambda: m.grid((True, 3, 4), np.eye(4)),
    lambda: m.grid((3, 4, 5), np.zeros((4, 4))),
    lambda: m.clean_roi(np.ones((8, 2)), np.ones((7, 3)), activity_fn=reporting.residual_active),
    lambda: m.resample_template(np.ones((5, 5, 5)), np.eye(4), (5, 5, 5), np.eye(4)),
])
def test_invalid_inputs_are_not_imputed_or_repaired(operation):
    with pytest.raises((ValueError, np.linalg.LinAlgError)):
        operation()
