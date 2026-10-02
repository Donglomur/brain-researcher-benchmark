"""Source-free quantitative tests of the private reconstruction only."""
import math

import numpy as np
import pytest

import source_numerics as m


@pytest.mark.parametrize('value', [0., .1, 1e100, 5e-324, -1e200])
def test_exact_constants_zero_before_reduction(value):
    centered, sd = m.centered_sd(np.full(7, value))
    assert sd == 0 and np.array_equal(centered, np.zeros(7))


@pytest.mark.parametrize('amplitude,kept', [(2e-8, False), (2.1e-8, True), (1.9e-8, False)])
def test_strict_population_sd_threshold(amplitude, kept):
    _, sd = m.centered_sd([0., amplitude])
    assert (sd > m.SD_THRESHOLD) is kept
    assert sd == pytest.approx(amplitude/2, abs=0, rel=1e-15)


def test_finite_extreme_scale_and_subnormal_support():
    _, huge_sd = m.centered_sd([1e308, -1e308])
    _, tiny_sd = m.centered_sd([-5e-324, 5e-324])
    assert math.isfinite(huge_sd) and huge_sd == 1e308
    assert tiny_sd == 5e-324 and tiny_sd < m.SD_THRESHOLD
    assert np.isfinite(m.unit_column([1e308, -1e308])).all()


@pytest.mark.parametrize('values', [[1e308, 1e308, -1e308, -1e308], [1.7e308, -1.7e308, -1.7e308]])
def test_unrepresentable_intermediate_fails_explicitly(values):
    with pytest.raises(ValueError, match='overflow|nonfinite'): m.centered_sd(values)


@pytest.mark.parametrize('bad', [[True, 1.], [0., np.bool_(False)], [float('nan'), 1.], [float('inf'), 1.],
                               ['0', '1'], [1+0j, 2+0j], np.array([1, 2], dtype=object), [[1., 2.]]])
def test_typed_finite_columns(bad):
    with pytest.raises(ValueError): m.centered_sd(bad)


def test_signed_clipped_perfect_edges_and_minimum_two_rois():
    x = np.arange(6, dtype=np.float64)
    raw = np.stack([np.column_stack([x, -x, 2*x, np.full(6, .1)])]*2)
    got = m.reconstruct(raw)
    assert got['common_roi_mask'].tolist() == [True, True, True, False]
    assert got['edge_roi_i'].tolist() == [1, 1, 2] and got['edge_roi_j'].tolist() == [2, 3, 3]
    cap = math.atanh(.999999)
    assert np.allclose(got['fisher_z'], [-cap, cap, -cap], atol=1e-12, rtol=0)
    two = m.reconstruct(raw[:, :, [0, 1]])
    assert two['n_common_rois'] == 2 and two['n_edges'] == 1


@pytest.mark.parametrize('remaining', [0, 1])
def test_insufficient_common_support_failclosed(remaining):
    raw = np.ones((2, 6, 3))
    if remaining: raw[:, :, 0] = np.arange(6)
    with pytest.raises(ValueError, match='insufficient_common_rois'): m.reconstruct(raw)


def test_transductive_intersection_and_odd_middle():
    t = np.arange(5, dtype=np.float64)
    person = np.column_stack([t, -t, t*t, [0, 0, 10, 0, 0]])
    raw = np.stack([person, person.copy()]); raw[1, :2, 2] = 0.
    got = m.reconstruct(raw)
    assert got['L'] == 2 and got['unused_middle_frame_indices'] == [2]
    assert got['segment_frame_ranges'] == [[0, 2], [3, 5], [0, 5]]
    assert got['common_roi_mask'].tolist() == [True, True, False, False]
    assert got['segment_support'][0, 2, 3] and not got['segment_support'][0, 0, 3]
    assert got['segment_support'][0, 0, 2] and not got['segment_support'][1, 0, 2]


def test_quantitative_full_fisher_matches_direct_scalar_dots():
    t = np.arange(8, dtype=np.float64)
    raw = np.stack([np.column_stack([t, (t-3)**2, [2, -1, 3, 0, 2, -2, 1, 4]])]*2)
    result = m.reconstruct(raw)
    for segment, (a, b) in enumerate(result['segment_frame_ranges']):
        for edge, (i, j) in enumerate(zip(result['edge_roi_i'], result['edge_roi_j'])):
            x, y = raw[0, a:b, i-1], raw[0, a:b, j-1]
            dx, dy = x-math.fsum(x)/len(x), y-math.fsum(y)/len(y)
            r = math.fsum(float(u)*float(v) for u, v in zip(dx, dy)) / math.sqrt(math.fsum(dx*dx)*math.fsum(dy*dy))
            z = math.atanh(max(-.999999, min(.999999, r)))
            assert result['fisher_z'][0, segment, edge] == pytest.approx(z, abs=2e-12, rel=0)


def test_positive_scaling_and_constant_offsets_preserve_supported_fisher():
    x = np.arange(8, dtype=float)
    raw = np.stack([np.column_stack([x, x*x+1, [0, 1, 3, 2, 6, 1, -1, 2]])]*2)
    original = m.reconstruct(raw)
    transformed = m.reconstruct(raw*np.array([2., 3., 4.])+np.array([100., -20., 1.]))
    assert np.array_equal(original['common_roi_mask'], transformed['common_roi_mask'])
    assert np.allclose(original['fisher_z'], transformed['fisher_z'], atol=2e-12, rtol=0)


@pytest.mark.parametrize('raw', [np.ones((2, 3, 3)), np.ones((0, 4, 3)), np.ones((2, 4, 0)), np.ones((4, 3))])
def test_invalid_cohort_shape(raw):
    with pytest.raises(ValueError): m.reconstruct(raw)


def test_nonfinite_any_original_column_rejects_before_support():
    raw = np.ones((2, 6, 3)); raw[0, 0, 2] = np.nan
    with pytest.raises(ValueError, match='nonfinite source'): m.reconstruct(raw)
