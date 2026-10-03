"""Manufactured arrays only; no source paths, atlas assets or endpoint analysis."""
import hashlib
import inspect
import math
import warnings
from importlib.metadata import version

import nibabel as nib
import numpy as np
import pytest
from nilearn import signal
from nilearn.maskers.nifti_spheres_masker import apply_mask_and_get_affinity
from scipy import linalg

import reporting_kernel as reporting
import source_numerics as m


def transform(case):
    affine = np.eye(4)
    if case == 'scaled': affine[:3, :3] = np.diag([2., 3., 1.5])
    elif case == 'reflected': affine[:3, :3] = np.diag([-2., 1., 3.])
    elif case == 'oblique': affine[:3, :3] = [[1., .25, .125], [.125, 1.5, 0.], [0., .2, 2.]]
    elif case == 'fractional': affine[:3, :3] *= .25
    affine[:3, 3] = [-.4, .3, -1.2]
    return affine


def test_qualified_versions_and_no_private_library_or_reporting_import():
    for name, expected in {'numpy': '2.1.3', 'scipy': '1.14.1', 'scikit-learn': '1.5.2',
                           'nibabel': '5.3.2', 'nilearn': '0.12.1'}.items():
        assert version(name) == expected
    source = inspect.getsource(m)
    assert 'from nilearn' not in source and 'import nilearn' not in source
    assert 'import reporting_kernel' not in source and 'oracle_numerics' not in source
    assert len(m.CONF_COLS) == 14 and 'framewise_displacement' not in m.CONF_COLS
    assert m.CONF_COLS[-2:] == ('csf', 'white_matter')
    assert not hasattr(m, 'global_support') and not hasattr(m, 'normalize_template')


@pytest.mark.parametrize('case', ['identity', 'scaled', 'reflected', 'oblique', 'fractional'])
@pytest.mark.parametrize('radius', [0., .6, 5.])
def test_sphere_support_exact_upstream(case, radius):
    shape, affine = (9, 8, 7), transform(case)
    points = np.array([[2., 3., 2.], [2.5, 3.5, 2.5], [4.04, 2.49, 1.5]])
    centers = (affine @ np.c_[points, np.ones(3)].T)[:3].T
    actual = m.sphere_supports(shape, affine, centers, radius)
    _, expected = apply_mask_and_get_affinity(centers,
        nib.Nifti1Image(np.zeros((*shape, 2)), affine), radius, True, mask_img=None)
    for support, indices in zip(actual, expected.rows):
        np.testing.assert_array_equal(support, np.asarray(sorted(indices)))


def test_default_radius_is_five_and_overlap_is_allowed():
    shape = (15, 15, 15); centers = [[7., 7., 7.], [7., 7., 7.]]
    rows = m.sphere_supports(shape, np.eye(4), centers)
    expected = m.sphere_supports(shape, np.eye(4), centers, 5.)
    assert len(rows[0]) > 1
    np.testing.assert_array_equal(rows[0], rows[1])
    np.testing.assert_array_equal(rows[0], expected[0])


def test_both_seed_additions_and_boundary_rounding():
    shape, affine = (5, 3, 3), np.diag([.25, 1., 1., 1.])
    support = m.sphere_supports(shape, affine, [[.51, 1., 1.]], .001)[0]
    assert set(support) == {np.ravel_multi_index((0, 1, 1), shape),
                            np.ravel_multi_index((2, 1, 1), shape)}
    assert len(m.sphere_supports((5, 5, 5), np.eye(4), [[2., 2., 2.]], 1.)[0]) == 7
    half = m.sphere_supports((5, 5, 5), np.eye(4), [[.5, 2., 2.]], 0.)[0]
    np.testing.assert_array_equal(half, [np.ravel_multi_index((0, 2, 2), (5, 5, 5))])


def test_any_empty_sphere_fails_not_dropped():
    with pytest.raises(ValueError, match='empty_sphere_support'):
        m.sphere_supports((5, 5, 5), np.eye(4), [[2., 2., 2.], [100., 100., 100.]], .1)


@pytest.mark.parametrize('layout', ['C', 'F', 'bigendian', 'float32'])
def test_raw_means_float64_scaled_contributing_values(layout):
    data = np.random.default_rng(822).normal(size=(7, 6, 5, 40)) * 1.25 - 3.5
    if layout == 'F': data = np.asfortranarray(data)
    elif layout == 'bigendian': data = data.astype('>f8')
    elif layout == 'float32': data = data.astype('f4')
    original = data.copy()
    supports = [np.arange(3, 41), np.arange(35, 80), np.arange(120, 135)]
    actual = m.extract_raw(data, supports)
    flat = np.asarray(data, dtype=np.float64).reshape(-1, 40)
    expected = np.column_stack([[np.mean(np.ascontiguousarray(flat[indices, frame]), dtype=np.float64)
                                for frame in range(40)] for indices in supports])
    np.testing.assert_array_equal(actual, expected)
    np.testing.assert_array_equal(data, original)
    assert actual.dtype == np.float64 and actual.flags.c_contiguous


@pytest.mark.parametrize('bad', [np.nan, np.inf, -np.inf])
def test_nonfinite_union_rule_precedes_activity(bad):
    data = np.ones((4, 4, 4, 40)); data[-1, -1, -1] = bad
    assert np.isfinite(m.extract_raw(data, [np.arange(8)])).all()
    data[0, 0, 0, 3] = bad
    with pytest.raises(ValueError, match='nonfinite_contributing_values'):
        m.extract_raw(data, [np.arange(8)])


def test_finite_input_mean_overflow_is_explicit_failure():
    with np.errstate(over='ignore'):
        with pytest.raises(ValueError, match='source_reduction_nonfinite'):
            m.extract_raw(np.full((2, 2, 2, 40), 1e308), [np.arange(8)])


@pytest.mark.parametrize('features', [1, 14, 264, 503])
@pytest.mark.parametrize('layout', ['C', 'F', 'strided'])
def test_detrend_exact_library_and_no_input_mutation(features, layout):
    data = np.random.default_rng(410).normal(size=(64, features)) + np.arange(64)[:, None] * .2
    if layout == 'F': data = np.asfortranarray(data)
    elif layout == 'strided': data = np.repeat(data, 2, axis=0)[::2]
    original = data.copy()
    expected = signal._detrend(np.array(data, dtype=np.float64, order='C', copy=True))
    np.testing.assert_array_equal(m.detrend(data), expected)
    np.testing.assert_array_equal(data, original)


@pytest.mark.parametrize('frames', [34, 48, 168])
def test_bandpass_columnwise_default_padding_matches_pinned_library(frames):
    data = np.random.default_rng(603).normal(size=(frames, 4))
    expected = signal.butterworth(np.array(data, order='C', copy=True), sampling_rate=.5,
                                  low_pass=.08, high_pass=.009, order=5,
                                  padtype='odd', padlen=None, copy=False)
    np.testing.assert_array_equal(m.bandpass(data), expected)


@pytest.mark.parametrize('frames', [2, 16, 33])
def test_actual_filter_padding_precondition_not_old_thirty_frame_shortcut(frames):
    with pytest.raises(ValueError): m.bandpass(np.ones((frames, 3)))


@pytest.mark.parametrize('case', ['ordinary', 'constant', 'duplicate', 'replicated', 'near_collinear'])
@pytest.mark.parametrize('layout', ['C', 'F', 'float32'])
def test_complete_filter_projection_standardization_matches_library(case, layout):
    rng = np.random.default_rng(509)
    raw = rng.normal(size=(64, 4)) + .1 * np.arange(64)[:, None]
    nuisance = rng.normal(size=(64, 14))
    if case == 'constant': nuisance[:] = 2. / 3.; raw[:, 0] = 2. / 3.
    elif case == 'duplicate': nuisance[:, 3] = nuisance[:, 2]; nuisance[:, 8] = nuisance[:, 2]
    elif case == 'replicated': nuisance[:] = nuisance[:, :1]
    elif case == 'near_collinear': nuisance[:, 4] = nuisance[:, 3] + 1e-13 * nuisance[:, 5]
    if layout == 'F': raw, nuisance = np.asfortranarray(raw), np.asfortranarray(nuisance)
    elif layout == 'float32': raw, nuisance = raw.astype('f4'), nuisance.astype('f4')
    raw64, nuisance64 = np.array(raw, dtype='f8', order='C'), np.array(nuisance, dtype='f8', order='C')
    original_y, original_x = raw.copy(), nuisance.copy()
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', DeprecationWarning)
        expected = signal.clean(raw64, confounds=nuisance64, detrend=True,
            standardize='zscore_sample', standardize_confounds=True,
            low_pass=.08, high_pass=.009, t_r=2., ensure_finite=False)
        expected_residual = signal.clean(raw64, confounds=nuisance64, detrend=True,
            standardize=False, standardize_confounds=True,
            low_pass=.08, high_pass=.009, t_r=2., ensure_finite=False)
        c = signal.standardize_signal(nuisance64, standardize=False, detrend=True)
        c = signal.butterworth(c, sampling_rate=.5, low_pass=.08, high_pass=.009,
                              order=5, padtype='odd', padlen=None, copy=False)
        c = signal.standardize_signal(c, standardize=True, detrend=False)
    _, triangular, pivots = linalg.qr(c, mode='economic', pivoting=True)
    actual = m.clean_roi(raw, nuisance, activity_fn=lambda residual, source: True)
    np.testing.assert_array_equal(actual['cleaned'], expected)
    np.testing.assert_array_equal(actual['residual'], expected_residual)
    np.testing.assert_array_equal(actual['pivots'], pivots)
    assert actual['rank'] == int(np.count_nonzero(np.abs(np.diag(triangular)) > 100 * np.finfo(float).eps))
    np.testing.assert_array_equal(raw, original_y); np.testing.assert_array_equal(nuisance, original_x)


def test_guard_rejects_constant_and_projection_roundoff_not_real_direction():
    rng = np.random.default_rng(728); nuisance = rng.normal(size=(64, 14))
    raw = np.column_stack([np.full(64, 2. / 3.), nuisance[:, 0] * 1000., rng.normal(size=64)])
    actual = m.clean_roi(raw, nuisance, activity_fn=reporting.residual_active)
    np.testing.assert_array_equal(actual['active'], [False, False, True])
    assert np.all(actual['cleaned'][:, :2] == 0)
    assert actual['raw_centered_l2'][0] == 0


@pytest.mark.parametrize('scale', [1e-18, math.ldexp(1., -600)])
def test_legacy_sample_sd_floor_is_retained_after_activity(scale):
    time = np.arange(64, dtype=float)
    raw = (scale * np.sin(time * .4))[:, None]
    nuisance = np.zeros((64, 14))
    actual = m.clean_roi(raw, nuisance, activity_fn=reporting.residual_active)
    assert actual['active'].tolist() == [True]
    assert actual['standardization_denominator'].tolist() == [1.]
    assert 0 < actual['raw_centered_l2'][0] < 100 * scale
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', DeprecationWarning)
        expected = signal.clean(raw, confounds=nuisance, detrend=True,
            standardize='zscore_sample', standardize_confounds=True,
            low_pass=.08, high_pass=.009, t_r=2., ensure_finite=False)
    np.testing.assert_array_equal(actual['cleaned'], expected)


def test_callback_receives_original_and_prestandardization_residual_and_is_typed():
    raw = np.random.default_rng(88).normal(size=(64, 3)); seen = []
    def callback(residual, original):
        seen.append((residual.copy(), original.copy()))
        return False
    result = m.clean_roi(raw, np.zeros((64, 14)), activity_fn=callback)
    assert len(seen) == 3 and np.all(result['cleaned'] == 0)
    for i, (residual, original) in enumerate(seen):
        np.testing.assert_array_equal(original, raw[:, i])
        np.testing.assert_array_equal(residual, result['residual'][:, i])
    with pytest.raises(ValueError, match='activity_callback_bool'):
        m.clean_roi(raw, np.zeros((64, 14)), activity_fn=lambda *_: 1)


def test_grid_inclusive_support_digest_and_signed_zero():
    shape, affine, indices = (5, 6, 7), np.eye(4), np.array([1, 5, 19])
    expected = hashlib.sha256(b'DEVCONN_support_v2\n' + np.asarray(shape, dtype='<i8').tobytes() +
        affine.astype('<f8').tobytes() + indices.astype('<i8').tobytes()).hexdigest()
    assert m.support_digest(shape, affine, indices) == expected
    affine[0, 1] = -0.
    assert m.support_digest(shape, affine, indices) == expected
    affine[0, 3] = 1.
    assert m.support_digest(shape, affine, indices) != expected


@pytest.mark.parametrize('indices', [[], [1., 2.], [True], [0, True], [-1], [3, 2], [1, 1], [64]])
def test_support_indices_fail_closed(indices):
    with pytest.raises(ValueError): m.checked_support(indices, 64)


@pytest.mark.parametrize('operation', [
    lambda: m.detrend(np.ones((1, 2))),
    lambda: m.detrend(np.full((64, 2), np.nan)),
    lambda: m.detrend([[1, True], [2, 3]]),
    lambda: m.grid((True, 3, 4), np.eye(4)),
    lambda: m.grid((3, 4, 5), np.zeros((4, 4))),
    lambda: m.sphere_supports((3, 4, 5), np.eye(4), [[1, True, 2]]),
    lambda: m.sphere_supports((3, 4, 5), np.eye(4), [[1, 2, 2]], True),
    lambda: m.clean_roi(np.ones((64, 2)), np.ones((63, 14)), activity_fn=reporting.residual_active),
    lambda: m.clean_roi(np.ones((64, 2)), np.ones((64, 15)), activity_fn=reporting.residual_active),
    lambda: m.clean_roi(np.ones((64, 2)), np.ones((64, 13)), activity_fn=reporting.residual_active),
])
def test_invalid_inputs_are_not_imputed_or_repaired(operation):
    with pytest.raises((ValueError, np.linalg.LinAlgError)): operation()
