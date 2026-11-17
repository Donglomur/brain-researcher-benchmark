"""Generated boundary comparisons; no authentic events or native packages."""
from copy import deepcopy
import math
import unittest

from count_oracle import count_cluster as reference
from stream_counts import compare_cluster, count_cluster, make_grid


def chunks(values, size=3):
    return [{'source_start': start, 'spikes': values[start:start+size]}
            for start in range(0, len(values), size)]


class StreamCountTests(unittest.TestCase):
    def compare(self, anchors, values):
        pieces = chunks(values)
        first = count_cluster(anchors, pieces, declared_spike_count=len(values))
        second = reference(anchors, pieces, declared_spike_count=len(values))
        self.assertEqual(compare_cluster(first, second, asset_id='generated', cluster_id=4), len(anchors)*200)
        return first

    def test_absolute_boundary_avoids_relative_time_cancellation(self):
        result = self.compare([1.], [1.001])
        self.assertEqual(result['response_counts'][0][0], 0)
        self.assertEqual(result['response_counts'][0][1], 1)
        # The tempting floor(relative_time/.001) implementation yields bin0.
        self.assertEqual(math.floor((1.001-1.)/.001), 0)

    def test_half_open_windows_and_gap_events(self):
        result = self.compare([1., 1.5], [.899, .9, .999, 1., 1.099999, 1.1, 1.25, 1.4, 1.5, 1.6])
        self.assertEqual(result['history_counts'][0][0], 1)
        self.assertEqual(result['history_counts'][0][99], 1)
        self.assertEqual(result['response_counts'][0][0], 1)
        self.assertEqual(result['response_counts'][0][99], 1)
        self.assertEqual(result['event_partition'], {'selected_windows': 6, 'gaps': 2,
            'before_first_window': 1, 'at_or_after_final_edge': 1})

    def test_equal_timestamps_cross_chunk_boundary_are_all_events(self):
        result = self.compare([1.], [1.001]*7)
        self.assertEqual(result['response_counts'][0][1], 7)

    def test_neighbors_of_every_edge_and_varied_chunk_partitions(self):
        edges = [0.375 + offset/1000000 for offset in range(-100000,100001,1000)]
        values = sorted(value for edge in edges for value in
                        (math.nextafter(edge,-math.inf),edge,math.nextafter(edge,math.inf)))
        expected = reference([0.375], chunks(values,11), declared_spike_count=len(values))
        for size in (1,2,17,65536):
            actual = count_cluster([0.375],chunks(values,size),declared_spike_count=len(values))
            self.assertEqual(compare_cluster(actual,expected,asset_id='generated',cluster_id=1),200)

    def test_touching_half_open_extents_share_no_event(self):
        result = self.compare([0.,0.2],[0.1])
        self.assertEqual(sum(result['response_counts'][0]),0)
        self.assertEqual(result['history_counts'][1][0],1)

    def test_negative_reference_and_irregular_gaps_preserved(self):
        result = self.compare([-1., .123, 1.41445], [-1.1, -1., .023, .123, 1.41445])
        self.assertEqual(sum(map(sum, result['history_counts'])) + sum(map(sum, result['response_counts'])), 5)

    def test_empty_cluster_is_a_complete_zero_count_stream(self):
        result = self.compare([0., .51985], [])
        self.assertEqual(result['source_spikes_consumed'], 0)
        self.assertTrue(all(count == 0 for window in ('history_counts', 'response_counts')
                            for row in result[window] for count in row))

    def test_chunk_extent_order_and_numeric_errors_refuse(self):
        cases = [([{'source_start': 1, 'spikes': [1.]}], 1),
                 ([{'source_start': 0, 'spikes': [1.]}, {'source_start': 0, 'spikes': [1.]}], 2),
                 ([{'source_start': 0, 'spikes': [1., .9]}], 2),
                 ([{'source_start': 0, 'spikes': [float('nan')]}], 1),
                 ([{'source_start': 0, 'spikes': [True]}], 1),
                 ([{'source_start': 0, 'spikes': [1.]}], 2),
                 ([{'source_start': 0, 'spikes': []}], 0)]
        for stream, declared in cases:
            with self.subTest(stream=stream), self.assertRaises(ValueError):
                count_cluster([1.], stream, declared_spike_count=declared)

    def test_overlap_and_unrepresentable_clock_refuse(self):
        for anchors in ([1., 1.15], [1., 1.], [1., .5], [1e20], [True]):
            with self.subTest(anchors=anchors), self.assertRaises(ValueError):
                make_grid(anchors)

    def test_independent_comparison_catches_offsetting_cluster_errors(self):
        first = self.compare([1.], [1.])
        corrupted = deepcopy(first)
        corrupted['response_counts'][0][0] -= 1
        corrupted['response_counts'][0][1] += 1
        with self.assertRaisesRegex(ValueError, 'cluster=4'):
            compare_cluster(corrupted, first, asset_id='generated', cluster_id=4)


if __name__ == '__main__':
    unittest.main()
