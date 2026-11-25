"""Generated complete-grid median controls; no authentic data or references."""
from fractions import Fraction
import math
import unittest

import neutral_contract as n
from test_centroid_control import fixture


def complete_report(spikes, template):
    neural, _unused_bodies, reference = fixture()
    for cell in reference['cells']:
        cell['coordinate_um'] = [0.0, 0.0]
    rows = []
    for case in neural['cases']:
        for request in case['requests']:
            value = template if request['kind'] == 'template' else spikes[request['array_index']]
            rows.append({'request_id': request['request_id'], 'case_id': case['case_id'],
                         'status': 'ok', 'coordinate_um': [value, 0.0]})
    submission = {'schema': 'localization-predictions-v1', 'program_sha256': '3' * 64,
                  'coordinate_unit': 'um', 'axis_names': ['x', 'y'], 'rows': rows}
    return n.score(neural, reference, submission, frozen_program_sha256='3' * 64)


class MedianPrecisionTests(unittest.TestCase):
    def test_complete_grid_preserves_representable_subnormal_median(self):
        tiny = math.ulp(0.0)
        report = complete_report((tiny, 2 * tiny), tiny)
        self.assertEqual(report['status'], 'COMPLETE_SUPPORT_SCORE')
        self.assertEqual(report['requested'], 2640)
        self.assertEqual(report['valid'], 2640)
        self.assertEqual(report['primary_spike_macro_accuracy'], 1.0)
        self.assertEqual(report['template_macro_accuracy'], 1.0)
        for cell in report['per_cell_condition']:
            self.assertEqual(cell['median_error_um_complete_support_only'],
                             2 * tiny if cell['kind'] == 'spike' else tiny)
        for row in report['per_condition']:
            self.assertEqual(row['animal_macro_mean_cell_median_error_um'],
                             2 * tiny if row['kind'] == 'spike' else tiny)

    def test_midpoints_round_once_for_subnormal_differences(self):
        tiny = math.ulp(0.0)
        for low, high in ((tiny, 2*tiny), (tiny, 4*tiny), (0.0, tiny),
                          (2*tiny, 5*tiny), (0.0, 0.0), (12.0, 18.0),
                          (1e308, 1.6e308), (1.6e308, 1.6e308)):
            with self.subTest(low=low, high=high):
                expected = float((Fraction(low) + Fraction(high)) / 2)
                self.assertEqual(n.nonnegative_median([low, high]), expected)

    def test_complete_grid_normal_midpoint_rounds_once(self):
        low = 3 * 2.0**-54
        expected = float((Fraction(low) + Fraction(1.0)) / 2)
        report = complete_report((low, 1.0), 0.0)
        self.assertEqual(report['status'], 'COMPLETE_SUPPORT_SCORE')
        self.assertEqual(report['primary_spike_macro_accuracy'], 1.0)
        self.assertEqual(report['template_macro_accuracy'], 1.0)
        for cell in report['per_cell_condition']:
            self.assertEqual(cell['median_error_um_complete_support_only'],
                             expected if cell['kind'] == 'spike' else 0.0)

    def test_complete_grid_retains_strict_threshold_and_large_distances(self):
        report = complete_report((49.0, 50.0), 1.6e308)
        self.assertEqual(report['status'], 'COMPLETE_SUPPORT_SCORE')
        self.assertEqual(report['primary_spike_macro_accuracy'], 0.5)
        self.assertEqual(report['template_macro_accuracy'], 0.0)
        for cell in report['per_cell_condition']:
            self.assertEqual(cell['median_error_um_complete_support_only'],
                             49.5 if cell['kind'] == 'spike' else 1.6e308)


if __name__ == '__main__':
    unittest.main()
