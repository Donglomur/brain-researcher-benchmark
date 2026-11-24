"""Invented full-panel controls; no authentic inputs or scientific scores."""
import itertools
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np

from cohort import MODES, Refusal
from grading import array_digest, grade_admitted_arrays
from io_support import object_digest
from test_core import PROFILE, panels


class PriorComparisonControls(unittest.TestCase):
    def varied_panel(self):
        records, descriptors, methods, selected, _, targets = panels()
        executions = set()
        for key, record in records.items():
            labels = targets[key]
            # The six invented queries give person accuracies 1, 2/3, 1/3, 0.
            predictions = labels.copy()
            wrong = key[2] * 2
            predictions[:wrong] = predictions[:wrong] % PROFILE.classes + 1
            p = np.eye(PROFILE.classes, dtype=np.float32)[predictions - 1]
            record['probabilities'] = p
            record['execution_receipt']['probabilities_digest'] = array_digest(p)
            executions.add(object_digest(record['execution_receipt']))
        return records, descriptors, methods, selected, frozenset(executions), targets

    def test_both_priors_use_every_person_for_every_mode_and_replication(self):
        records, descriptors, methods, selected, executions, targets = self.varied_panel()
        result = grade_admitted_arrays(records, descriptors, methods, selected,
                                       executions, lambda _: targets, PROFILE)
        contrasts = { (c['mode'], c['replication'], c['contrast']): c
                      for c in result['contrasts'] if c['contrast'] in
                      ('neural_minus_uniform', 'neural_minus_training_prior') }
        expected_keys = set(itertools.product(MODES, range(3),
                            ('neural_minus_uniform', 'neural_minus_training_prior')))
        self.assertEqual(set(contrasts), expected_keys)
        expected = np.array([1, 2 / 3, 1 / 3, 0]) - 1 / 3
        # Independent enumerated bootstrap calculation of all four-person draws.
        draws = np.array(list(itertools.product(expected, repeat=4))).mean(axis=1)
        low, high = np.quantile(draws, [.025, .975], method='linear')
        for contrast in contrasts.values():
            np.testing.assert_allclose(contrast['person_differences'], expected,
                                       rtol=0, atol=1e-15)
            self.assertAlmostEqual(contrast['mean'], 1 / 6)
            self.assertEqual(contrast['comparator_top1_per_person'], [1 / 3] * 4)
            self.assertEqual(contrast['metric'], 'class_balanced_top1')
            self.assertAlmostEqual(contrast['interval']['low'], low)
            self.assertAlmostEqual(contrast['interval']['high'], high)
            self.assertEqual(contrast['interval']['resamples'], 256)
        self.assertEqual(result['biological_people'], 4)
        self.assertEqual(len(result['cases']), 160)
        self.assertFalse(result['scientific_qualification_conferred'])
        self.assertTrue(result['engineering_profile'])

    def test_missing_matrix_refuses_before_target_access(self):
        records, descriptors, methods, selected, executions, _ = self.varied_panel()
        del records[next(iter(records))]
        accessed = []
        with self.assertRaises(Refusal):
            grade_admitted_arrays(records, descriptors, methods, selected, executions,
                                   lambda _: accessed.append(True), PROFILE)
        self.assertEqual(accessed, [])

    def test_incomplete_class_support_cannot_get_closed_form_prior_contrasts(self):
        records, descriptors, methods, selected, executions, targets = self.varied_panel()
        first = next(iter(targets))
        targets[first] = targets[first].copy()
        targets[first][0] = 2  # Same length, but no longer exactly two per class.
        with self.assertRaises(Refusal):
            grade_admitted_arrays(records, descriptors, methods, selected, executions,
                                   lambda _: targets, PROFILE)


if __name__ == '__main__':
    unittest.main()
