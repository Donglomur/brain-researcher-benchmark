"""Independent generated controls; these arrays are not neural recordings."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

import numpy as np


SPEC = importlib.util.spec_from_file_location("neural096_full_set_go_core", Path(__file__).with_name("core.py"))
core = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(core)


class PhaseEdgesTests(unittest.TestCase):
    def test_exact_affine_quarters(self):
        actual = core.phase_edges(0.0, 1.0, bins=4)
        np.testing.assert_array_equal(actual, np.array([0, .25, .5, .75, 1], dtype=np.float64))
        self.assertEqual(actual.dtype, np.dtype("float64"))

    def test_preserves_both_native_event_endpoints(self):
        actual = core.phase_edges(123.123456789, 124.987654321, bins=20)
        self.assertEqual(actual.shape, (21,))
        self.assertEqual(actual[0], 123.123456789)
        self.assertEqual(actual[-1], 124.987654321)
        self.assertTrue(np.all(actual[1:] > actual[:-1]))

    def test_large_same_sign_clock_does_not_overflow_weighted_sum(self):
        high = np.finfo(np.float64).max
        actual = core.phase_edges(high / 2, high, bins=2)
        self.assertEqual(actual[0], high / 2)
        self.assertEqual(actual[1], float.fromhex("0x1.7ffffffffffffp+1023"))
        self.assertEqual(actual[-1], high)
        self.assertTrue(np.isfinite(actual).all())

    def test_representable_subnormal_steps_are_preserved(self):
        smallest = np.nextafter(0.0, 1.0)
        actual = core.phase_edges(0.0, 4 * smallest, bins=4)
        np.testing.assert_array_equal(actual, smallest * np.arange(5))

    def test_unrepresentable_subdivisions_are_refused(self):
        with self.assertRaises(ValueError):
            core.phase_edges(1.0, np.nextafter(1.0, 2.0), bins=2)

    def test_subnormal_duplicate_midpoint_is_refused(self):
        with self.assertRaises(ValueError):
            core.phase_edges(0.0, np.nextafter(0.0, 1.0), bins=2)

    def test_reversed_or_zero_duration_is_refused(self):
        for first, last in [(1.0, 1.0), (2.0, 1.0)]:
            with self.subTest(first=first, last=last), self.assertRaises(ValueError):
                core.phase_edges(first, last)

    def test_nonfinite_clock_is_refused(self):
        for first, last in [(np.nan, 1.0), (0.0, np.nan), (0.0, np.inf), (-np.inf, 1.0)]:
            with self.subTest(first=first, last=last), self.assertRaises(ValueError):
                core.phase_edges(first, last)

    def test_invalid_bin_counts_are_refused(self):
        for bins in [0, -1, 1.5, True]:
            with self.subTest(bins=bins), self.assertRaises((ValueError, TypeError)):
                core.phase_edges(0.0, 1.0, bins=bins)

    def test_single_round_affine_edge_preserves_spike_membership(self):
        expected_middle = float.fromhex("0x1.5555555555555p-3")
        edges = core.phase_edges(.1, .3, bins=3)
        self.assertEqual(edges[1], expected_middle)
        np.testing.assert_array_equal(core.count_phase_spikes(np.array([expected_middle]), edges), [0, 1, 0])

    def test_negative_clock_origin_is_permitted(self):
        np.testing.assert_array_equal(core.phase_edges(-1.0, 1.0, bins=4), [-1.0, -.5, 0.0, .5, 1.0])

    def test_unrepresentable_exposure_is_refused(self):
        maximum = np.finfo(np.float64).max
        with self.assertRaises(ValueError):
            core.phase_edges(-maximum, maximum, bins=1)

    @unittest.skipIf(np.dtype(np.longdouble).itemsize <= 8, "This platform has no floating dtype wider than binary64")
    def test_wider_floating_clock_is_refused_before_narrowing(self):
        with self.assertRaises(ValueError):
            core.phase_edges(np.longdouble(0), np.longdouble(1), bins=20)


class ObservationCoverageTests(unittest.TestCase):
    def test_overlapping_and_touching_intervals_merge(self):
        actual = core.observed_union([(3.0, 4.0), (0.0, 1.0), (1.0, 2.0), (1.5, 3.0)])
        self.assertEqual(actual, [(0.0, 4.0)])

    def test_positive_gap_is_not_rounded_away(self):
        beyond = float(np.nextafter(1.0, 2.0))
        actual = core.observed_union([(0.0, 1.0), (beyond, 2.0)])
        self.assertEqual(actual, [(0.0, 1.0), (beyond, 2.0)])

    def test_nested_and_duplicate_intervals_do_not_duplicate_support(self):
        actual = core.observed_union([(0.0, 4.0), (1.0, 3.0), (0.0, 4.0)])
        self.assertEqual(actual, [(0.0, 4.0)])

    def test_invalid_observation_intervals_are_refused(self):
        for intervals in [[(0.0, 0.0)], [(2.0, 1.0)], [(0.0, np.nan)], [(0.0, np.inf)]]:
            with self.subTest(intervals=intervals), self.assertRaises(ValueError):
                core.observed_union(intervals)

    def test_exact_complete_window_is_supported(self):
        self.assertEqual(core.containing_segment(2.0, 3.0, [(0.0, 1.0), (2.0, 3.0)]), 1)

    def test_cross_gap_window_is_refused(self):
        with self.assertRaises(ValueError):
            core.containing_segment(0.5, 2.5, [(0.0, 1.0), (2.0, 3.0)])

    def test_partial_window_is_refused(self):
        for first, last in [(-1.0, .5), (.5, 2.0), (2.0, 3.0)]:
            with self.subTest(first=first, last=last), self.assertRaises(ValueError):
                core.containing_segment(first, last, [(0.0, 1.0)])


class SpikeCountingTests(unittest.TestCase):
    def test_exact_endpoints_and_duplicate_spikes(self):
        spikes = np.array([0, 1, 1, 1.5, 2, 2, 2.75, 3, 4], dtype=np.float64)
        actual = core.count_phase_spikes(spikes, np.array([1, 2, 3], dtype=np.float64))
        np.testing.assert_array_equal(actual, [3, 3])
        self.assertEqual(actual.dtype, np.dtype("uint32"))

    def test_right_edge_go_is_excluded(self):
        actual = core.count_phase_spikes(np.array([1.0]), np.array([0.0, .5, 1.0]))
        np.testing.assert_array_equal(actual, [0, 0])

    def test_adjacent_float_boundary_membership(self):
        edge = 0.5
        spikes = np.array([np.nextafter(edge, 0.0), edge, np.nextafter(edge, 1.0)])
        np.testing.assert_array_equal(core.count_phase_spikes(spikes, np.array([0.0, .5, 1.0])), [1, 2])

    def test_no_spikes_has_complete_zero_coverage(self):
        actual = core.count_phase_spikes(np.array([], dtype=np.float64), np.linspace(0, 1, 21))
        np.testing.assert_array_equal(actual, np.zeros(20, dtype=np.uint32))

    def test_conserves_window_count_with_nonuniform_bins(self):
        spikes = np.array([-1, 0, .1, .2, .21, .7, .8, .9, 1, 2], dtype=np.float64)
        edges = np.array([0, .2, .8, 1], dtype=np.float64)
        actual = core.count_phase_spikes(spikes, edges)
        np.testing.assert_array_equal(actual, [2, 3, 2])
        self.assertEqual(int(actual.sum()), 7)

    def test_unsorted_spikes_are_refused(self):
        with self.assertRaises(ValueError):
            core.count_phase_spikes(np.array([0.8, 0.2]), np.array([0.0, 1.0]))

    def test_nonfinite_spikes_are_refused_even_outside_epoch(self):
        for bad in [np.nan, -np.inf, np.inf]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                core.count_phase_spikes(np.array([bad]), np.array([0.0, 1.0]))

    def test_invalid_edges_are_refused(self):
        for edges in [[], [0], [0, 0], [1, 0], [0, np.nan], [0, np.inf]]:
            with self.subTest(edges=edges), self.assertRaises(ValueError):
                core.count_phase_spikes(np.array([], dtype=np.float64), np.array(edges, dtype=np.float64))


class CompleteSupportTests(unittest.TestCase):
    def test_every_zero_cell_is_retained_with_fixed_axis_order(self):
        rows = [
            dict(observation_segment=0, is_eye=False, theta=0, is_short=False),
            dict(observation_segment=0, is_eye=False, theta=0, is_short=False),
            dict(observation_segment=1, is_eye=True, theta=180, is_short=True),
        ]
        actual = core.matched_support(rows, segments=2)
        self.assertEqual(actual["axes"], ["observation_segment", "is_eye", "theta", "is_short"])
        expected = np.zeros((2, 2, 2, 2), dtype=np.int64)
        expected[0, 0, 0, 0] = 2
        expected[1, 1, 1, 1] = 1
        np.testing.assert_array_equal(actual["counts"], expected)
        self.assertEqual(len(actual["zero_cells"]), 14)
        self.assertFalse(actual["all_cells_present"])

    def test_complete_support_counts_every_condition(self):
        rows = [dict(observation_segment=s, is_eye=eye, theta=theta, is_short=short)
                for s in range(2) for eye in (False, True) for theta in (0, 180)
                for short in (False, True)]
        actual = core.matched_support(rows, segments=2)
        np.testing.assert_array_equal(actual["counts"], np.ones((2, 2, 2, 2), dtype=np.int64))
        self.assertEqual(actual["zero_cells"], [])
        self.assertTrue(actual["all_cells_present"])

    def test_missing_entire_segment_stays_in_support_census(self):
        row = dict(observation_segment=0, is_eye=False, theta=0, is_short=False)
        actual = core.matched_support([row], segments=3)
        self.assertEqual(np.asarray(actual["counts"]).shape, (3, 2, 2, 2))
        self.assertEqual(len(actual["zero_cells"]), 23)

    def test_unknown_segment_is_refused(self):
        for segment in [-1, 2, 0.5, True]:
            row = dict(observation_segment=segment, is_eye=False, theta=0, is_short=False)
            with self.subTest(segment=segment), self.assertRaises(ValueError):
                core.matched_support([row], segments=2)

    def test_invalid_cue_identity_is_refused(self):
        for change in [dict(is_eye=0), dict(is_short=1), dict(theta=90), dict(theta=np.nan)]:
            row = dict(observation_segment=0, is_eye=False, theta=0, is_short=False)
            row.update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                core.matched_support([row], segments=2)

    def test_nonscalar_or_nonreal_direction_is_refused(self):
        for theta in [False, np.bool_(False), 0j, np.array(0.0), np.array([0.0])]:
            row = dict(observation_segment=0, is_eye=False, theta=theta, is_short=False)
            with self.subTest(theta=theta), self.assertRaises(ValueError):
                core.matched_support([row], segments=2)


if __name__ == "__main__":
    unittest.main()
