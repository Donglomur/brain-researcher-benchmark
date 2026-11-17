"""Generated software controls only; no authentic labels, models or data."""
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('sleep_probability_diagnostics', HERE / 'diagnostics.py')
diagnostics = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diagnostics)


class ProbabilityDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.targets = {}
        for person, count in diagnostics.CASES:
            self.targets[person] = {'epoch_id': self.ids(person, count),
                                    'stage': np.zeros(count, dtype=np.int8),
                                    'score_mask': np.ones(count, dtype=bool)}
        self.calls = 0
        self.candidate = self.write('candidate')
        self.references = {name: self.write(name) for name in diagnostics.COMPARATORS}

    @staticmethod
    def ids(person, count):
        return np.asarray([f'{person}/{i:05d}' for i in range(count)])

    def write(self, name, by_person=None, change=None):
        values = {'class_order': np.asarray(['W', 'N1', 'N2', 'N3', 'R'])}
        for person, count in diagnostics.CASES:
            p = np.full((count, 5), .2, dtype=np.float64)
            if by_person is not None:
                p[:] = by_person[person]
            values[person + '__epoch_id'] = self.ids(person, count)
            values[person + '__probabilities'] = p
        if change:
            change(values)
        path = self.root / (name + '.npz')
        np.savez(path, **values)
        body = path.read_bytes()
        return path, {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}

    def loader(self):
        self.calls += 1
        return self.targets

    def evaluate(self, candidate=None):
        path, lock = self.candidate if candidate is None else candidate
        return diagnostics.evaluate(path, lock, self.loader, self.references)

    def test_uniform_known_values_and_exact_primary_parity(self):
        result = self.evaluate()
        self.assertEqual(self.calls, 1)
        score = result['diagnostics']['candidate']
        self.assertAlmostEqual(score['person_mean_log_loss'], math.log(5))
        self.assertAlmostEqual(score['person_mean_multiclass_brier'], .8)
        self.assertAlmostEqual(score['person_mean_top_label_ece_10'], .8)
        self.assertEqual(result['full_epochs'], 5450)
        adapter = diagnostics.load_adapter()
        old_spec = adapter.Specification(tuple(adapter.Case(*c) for c in diagnostics.CASES), diagnostics.COMPARATORS)
        old = adapter.evaluate(*self.candidate, old_spec, self.loader, self.references)
        self.assertEqual(result['primary']['candidate'], old['candidate'])
        self.assertEqual(result['primary']['comparators'], old['comparators'])
        self.assertEqual(result['primary']['signed_comparator_differences'], old['signed_comparator_differences'])
        self.assertEqual(result['input_freezes'], old['input_freezes'])
        json.dumps(result, allow_nan=False)

    def test_perfect_probability_is_zero_without_changing_fixed_five_f1(self):
        candidate = self.write('perfect', {person: [1., 0., 0., 0., 0.] for person, _ in diagnostics.CASES})
        result = self.evaluate(candidate)
        row = result['diagnostics']['candidate']
        self.assertEqual(row['person_mean_log_loss'], 0.)
        self.assertEqual(row['person_mean_multiclass_brier'], 0.)
        self.assertEqual(row['person_mean_top_label_ece_10'], 0.)
        self.assertEqual(result['primary']['candidate']['person_mean_macro_f1'], .2)
        self.assertEqual(result['primary']['candidate'], result['primary']['comparators']['YASA'])

    def test_equal_person_not_epoch_weighting_and_private_mask(self):
        for index, (person, _) in enumerate(diagnostics.CASES):
            stage = self.targets[person]['stage']
            stage[:] = -1
            stage[:1 if index == 0 else 3] = 0
            self.targets[person]['score_mask'][:] = stage >= 0
        candidate = self.write('unequal', {'development-001': [.8, .05, .05, .05, .05],
                                           'development-002': [.2] * 5})
        result = self.evaluate(candidate)['diagnostics']['candidate']
        self.assertEqual([r['scored_epochs'] for r in result['per_person']], [1, 3])
        self.assertAlmostEqual(result['person_mean_multiclass_brier'], (.05 + .8) / 2)
        self.assertAlmostEqual(result['person_mean_log_loss'], (-math.log(.8) + math.log(5)) / 2)
        self.assertAlmostEqual(result['person_mean_top_label_ece_10'], (.2 + .8) / 2)
        self.assertNotAlmostEqual(result['person_mean_multiclass_brier'], (.05 + 3 * .8) / 4)

    def test_zero_true_probability_is_infinite_without_clipping(self):
        candidate = self.write('wrong', {person: [0., 1., 0., 0., 0.] for person, _ in diagnostics.CASES})
        result = self.evaluate(candidate)
        row = result['diagnostics']['candidate']
        self.assertTrue(row['log_loss_is_infinite'])
        self.assertIsNone(row['person_mean_log_loss'])
        self.assertEqual(row['person_mean_multiclass_brier'], 2.)
        self.assertEqual(row['person_mean_top_label_ece_10'], 1.)
        self.assertEqual(sum(r['zero_true_probability_epochs'] for r in row['per_person']), 5450)
        delta = result['diagnostics']['signed_comparator_differences']['RF']
        self.assertEqual(delta['person_mean_log_loss_delta'], {'value': None, 'status': 'positive_infinity'})
        self.references = {name: candidate for name in diagnostics.COMPARATORS}
        result = self.evaluate(candidate)
        self.assertEqual(result['diagnostics']['signed_comparator_differences']['RF']['person_mean_log_loss_delta'],
                         {'value': None, 'status': 'undefined_both_infinite'})
        result = self.evaluate()
        self.assertEqual(result['diagnostics']['signed_comparator_differences']['RF']['person_mean_log_loss_delta'],
                         {'value': None, 'status': 'negative_infinity'})
        json.dumps(result, allow_nan=False)

    def test_calibration_exact_edges_ties_and_empty_bins(self):
        rows = np.asarray([[.3, .3, .2, .1, .1], [.1, .3, .2, .3, .1], [1., 0., 0., 0., 0.]])
        value = diagnostics._diagnostics(rows, np.asarray([0, 3, 0]))
        bins = value['calibration_bins']
        self.assertEqual(bins[2]['count'], 0)
        self.assertIsNone(bins[2]['accuracy'])
        self.assertIsNone(bins[2]['mean_confidence'])
        self.assertEqual((bins[3]['count'], bins[3]['correct']), (2, 1))
        self.assertEqual((bins[9]['count'], bins[9]['correct']), (1, 1))
        self.assertAlmostEqual(value['top_label_ece_10'], abs(1 - .6) / 3)
        self.assertEqual(sum(b['count'] for b in bins), 3)

    def test_probabilities_are_not_silently_normalized(self):
        rows = np.asarray([[.5000002, .5, 0., 0., 0.]])
        value = diagnostics._diagnostics(rows, np.asarray([0]))
        self.assertEqual(value['mean_log_loss'], -math.log(.5000002))
        self.assertEqual(value['mean_multiclass_brier'], (.5000002 - 1) ** 2 + .5 ** 2)

    def test_missing_epoch_rejected_before_loader(self):
        def remove(values):
            values['development-002__epoch_id'] = values['development-002__epoch_id'][:-1]
            values['development-002__probabilities'] = values['development-002__probabilities'][:-1]
        with self.assertRaises(ValueError):
            self.evaluate(self.write('missing', change=remove))
        self.assertEqual(self.calls, 0)

    def test_invalid_probability_even_on_masked_epoch_precedes_loader(self):
        self.targets['development-001']['stage'][0] = -1
        self.targets['development-001']['score_mask'][0] = False
        def change(values):
            values['development-001__probabilities'][0, 0] = np.nan
        with self.assertRaises(ValueError):
            self.evaluate(self.write('bad', change=change))
        self.assertEqual(self.calls, 0)

    def test_later_reference_failure_precedes_loader(self):
        def change(values):
            values['development-002__epoch_id'][-1] = 'development-002/00000'
        self.references['RF'] = self.write('bad_reference', change=change)
        with self.assertRaises(ValueError):
            self.evaluate()
        self.assertEqual(self.calls, 0)

    def test_missing_comparator_precedes_loader(self):
        del self.references['RF']
        with self.assertRaises(ValueError):
            self.evaluate()
        self.assertEqual(self.calls, 0)

    def test_invalid_private_mask_and_empty_person_not_averaged_away(self):
        self.targets['development-001']['score_mask'][0] = False
        with self.assertRaises(ValueError):
            self.evaluate()
        self.assertEqual(self.calls, 1)
        self.targets['development-001']['stage'][:] = -1
        self.targets['development-001']['score_mask'][:] = False
        with self.assertRaises(ValueError):
            self.evaluate()
        self.assertEqual(self.calls, 2)

    def test_changed_predecessor_is_rejected_before_any_target_access(self):
        body = bytearray(diagnostics.ADAPTER.read_bytes())
        body[-1] ^= 1
        path = self.root / 'altered.py'
        path.write_bytes(body)
        with mock.patch.object(diagnostics, 'ADAPTER', path), self.assertRaisesRegex(ValueError, 'digest'):
            self.evaluate()
        self.assertEqual(self.calls, 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
