"""Generated fixtures only: independent spike-count direction and boundaries."""

import importlib.util
import math
from pathlib import Path
import unittest


_spec = importlib.util.spec_from_file_location("neural099_count_oracle", Path(__file__).with_name("count_oracle.py"))
oracle = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(oracle)


def chunks(spikes, size):
    return [{"source_start": index, "spikes": spikes[index:index + size]}
            for index in range(0, len(spikes), size)]


def stream(cluster_id, spikes, size=65536):
    return {"cluster_id": cluster_id, "declared_spike_count": len(spikes),
            "chunks": chunks(spikes, size)}


class CountingOracleTests(unittest.TestCase):
    def test_every_exact_edge_is_left_closed_right_open(self):
        anchor = 0.375
        history = [anchor + micros / 1_000_000 for micros in range(-100000, 1, 1000)]
        response = [anchor + micros / 1_000_000 for micros in range(0, 100001, 1000)]
        # The shared onset appears twice, representing two deposited events.
        spikes = sorted(history + response)
        counted = oracle.count_cluster([anchor], chunks(spikes, 17), declared_spike_count=len(spikes))
        self.assertEqual(counted["history_counts"], [[1] * 100])
        self.assertEqual(counted["response_counts"], [[2] + [1] * 99])
        self.assertEqual(sum(counted["history_counts"][0]) + sum(counted["response_counts"][0]), 201)

    def test_neighboring_floats_around_boundaries_are_not_recentered(self):
        anchor = 1024.125
        start = anchor - 0.1
        middle = anchor + 0.05
        end = anchor + 0.1
        spikes = sorted([math.nextafter(start, -math.inf), start,
                         math.nextafter(anchor, -math.inf), anchor,
                         math.nextafter(middle, -math.inf), middle,
                         math.nextafter(end, -math.inf), end])
        counted = oracle.count_cluster([anchor], chunks(spikes, 3), declared_spike_count=len(spikes))
        history = counted["history_counts"][0]
        response = counted["response_counts"][0]
        self.assertEqual((history[0], history[-1], sum(history)), (1, 1, 2))
        self.assertEqual((response[0], response[49], response[50], response[99], sum(response)),
                         (1, 1, 1, 1, 4))

    def test_gap_spikes_are_excluded_and_all_actual_anchors_are_used(self):
        anchors = [1.125, 1.825, 3.125]
        spikes = [0.0, 1.125, 1.5, 1.825, 2.5, 3.125, 4.0]
        counted = oracle.count_cluster(anchors, chunks(spikes, 2), declared_spike_count=len(spikes))
        self.assertEqual([sum(row) for row in counted["history_counts"]], [0, 0, 0])
        self.assertEqual([sum(row) for row in counted["response_counts"]], [1, 1, 1])
        self.assertEqual([row[0] for row in counted["response_counts"]], [1, 1, 1])

    def test_equal_time_spikes_crossing_chunks_are_not_deduplicated(self):
        spikes = [-0.1, 0.0, 0.0, 0.0, 0.099, 0.1]
        single = oracle.count_cluster([0.0], chunks(spikes, 6), declared_spike_count=6)
        for size in (1, 2, 3, 4):
            with self.subTest(size=size):
                counted = oracle.count_cluster([0.0], chunks(spikes, size), declared_spike_count=6)
                self.assertEqual(counted, single)
        self.assertEqual(single["history_counts"][0][0], 1)
        self.assertEqual(single["response_counts"][0][0], 3)
        self.assertEqual(single["response_counts"][0][99], 1)

    def test_empty_retained_clusters_remain_in_nominal_denominator(self):
        counted = oracle.count_region([0.0], [7, 91], [stream(91, []), stream(7, [0.0])], region="MGv")
        self.assertEqual(counted["source_cluster_count"], 2)
        self.assertEqual(counted["source_spikes_consumed"], 1)
        self.assertEqual(counted["response_counts"][0][0], 1)
        self.assertEqual(counted["response_nominal_rates"][0][0], 500)
        self.assertEqual(sum(counted["history_counts"][0]), 0)
        self.assertFalse(counted["observation_coverage_verified"])
        empty = oracle.count_cluster([-0.5], [], declared_spike_count=0)
        self.assertEqual(empty["response_counts"], [[0] * 100])

    def test_nominal_exposure_does_not_follow_absolute_float_edge_gaps(self):
        anchor = 1_000_000.125
        window = oracle.make_windows([anchor])[0]
        gaps = [right - left for left, right in zip(window["response_edges_seconds"],
                                                   window["response_edges_seconds"][1:])]
        self.assertTrue(any(gap != 0.001 for gap in gaps))
        result = oracle.count_region([anchor], [8], [stream(8, [anchor])], region="MGm")
        self.assertEqual(result["response_nominal_rates"][0][0], 1000)
        self.assertEqual(oracle.nominal_rates([[1] * 100], 3)[0][0], 1000 / 3)

    def test_negative_clock_references_and_unsorted_source_rows_are_preserved(self):
        anchors = [0.0, -0.5]
        spikes = [-0.6, -0.5, -0.1, 0.0]
        result = oracle.count_cluster(anchors, chunks(spikes, 2), declared_spike_count=4)
        self.assertEqual([row[0] for row in result["history_counts"]], [1, 1])
        self.assertEqual([row[0] for row in result["response_counts"]], [1, 1])

    def test_global_history_response_overlap_refuses_but_touching_is_allowed(self):
        # Own-trial history/response never overlap; this is cross-trial leakage.
        with self.assertRaisesRegex(ValueError, "History row 1 overlaps scored response row 0"):
            oracle.make_windows([0.0, 0.15])
        self.assertEqual(len(oracle.make_windows([0.0, 0.2])), 2)
        # Repeated source rows are retained; this oracle does not silently dedupe
        # or declare a scientific source-identity failure from equal times alone.
        self.assertEqual(len(oracle.make_windows([0.0, 0.0])), 2)

    def test_full_frozen_roster_is_checked_before_spike_consumption(self):
        class Trap:
            def __iter__(self):
                raise AssertionError("Spike iterator was opened before roster validation")
        descriptor = {"cluster_id": 1, "declared_spike_count": 1, "chunks": Trap()}
        for roster, descriptors in (([1, 2], [descriptor]),
                                    ([1], [descriptor, descriptor]),
                                    ([2], [descriptor])):
            with self.subTest(roster=roster), self.assertRaises(ValueError):
                oracle.count_region([0.0], roster, descriptors, region="SG")

    def test_chunk_offsets_extent_order_and_bounds_are_enforced(self):
        bad = [
            ([{"source_start": 1, "spikes": [0.0]}], 1),
            ([{"source_start": 0, "spikes": [0.0]}, {"source_start": 0, "spikes": [0.0]}], 2),
            ([{"source_start": 0, "spikes": [0.0]}, {"source_start": 2, "spikes": [0.0]}], 2),
            ([{"source_start": 0, "spikes": [0.0, -0.1]}], 2),
            ([{"source_start": 0, "spikes": [0.0]}, {"source_start": 1, "spikes": [-0.1]}], 2),
            ([{"source_start": 0, "spikes": []}], 0),
            ([{"source_start": 0, "spikes": [0.0]}], 2),
            ([{"source_start": 0, "spikes": [0.0, 0.0]}], 1),
            ([{"source_start": True, "spikes": [0.0]}], 1),
        ]
        for values, declared in bad:
            with self.subTest(values=values), self.assertRaises(ValueError):
                oracle.count_cluster([0.0], values, declared_spike_count=declared)
        with self.assertRaises(ValueError):
            oracle.count_cluster([0.0], chunks([0.0, 0.0], 2), declared_spike_count=2, max_chunk_size=1)
        with self.assertRaises(ValueError):
            oracle.count_cluster([0.0], [], declared_spike_count=0, max_chunk_size=65537)

    def test_nonfinite_collapsed_clock_and_invalid_count_inputs_refuse(self):
        for anchor in (math.nan, math.inf, -math.inf, True, 1e308):
            with self.subTest(anchor=anchor), self.assertRaises(ValueError):
                oracle.make_windows([anchor])
        for spike in (math.nan, math.inf, -math.inf, True):
            with self.subTest(spike=spike), self.assertRaises(ValueError):
                oracle.count_cluster([0.0], chunks([spike], 1), declared_spike_count=1)
        for count in (-1, True, 1.0):
            with self.subTest(count=count), self.assertRaises(ValueError):
                oracle.nominal_rates([[count] * 100], 1)
        for denominator in (0, -1, True):
            with self.subTest(denominator=denominator), self.assertRaises(ValueError):
                oracle.nominal_rates([[0] * 100], denominator)
        with self.assertRaises(ValueError):
            oracle.count_region([0.0], [1], [stream(1, [])], region=" ")
        with self.assertRaises(ValueError):
            oracle.count_region([0.0], [True], [stream(True, [])], region="MGv")


if __name__ == "__main__":
    unittest.main(verbosity=2)
