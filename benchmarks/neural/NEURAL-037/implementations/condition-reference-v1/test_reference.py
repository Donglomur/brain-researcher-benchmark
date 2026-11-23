"""Generated reference controls; no original arrays, targets, fits or scores."""
import copy
import os
from pathlib import Path
import types
import unittest
from unittest import mock

import numpy as np

HERE = Path(__file__).resolve().parent
REFERENCE = types.ModuleType('_neural037_reference_test')
REFERENCE.__file__ = str(HERE / 'reference.py')
exec(compile((HERE / 'reference.py').read_bytes(), REFERENCE.__file__, 'exec'), REFERENCE.__dict__)
REPOSITORY = Path(os.environ.get('NEURAL037_TEST_REPOSITORY', HERE.parents[4]))
REFERENCE.HERE = REPOSITORY / 'benchmarks/neural/NEURAL-037/implementations/condition-reference-v1'


class ReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = REFERENCE.source_bundle()

    def example(self, index=0):
        query = copy.deepcopy(self.bundle.panel['contexts'][index])
        shape = (len(query['cell_keys']), query['frames'])
        means = np.zeros(shape, dtype=np.float64)
        counts = np.zeros(shape, dtype=np.uint16)
        means[0, :3] = [2., 4., 99.]
        counts[0, :3] = [1, 50, 0]
        means[0, 2] = 0.  # unavailable source means have zero placeholders
        key = query['acquisition'] + ('_CBA' if query['query_order'] == 'ABC' else '_ABC')
        return {'query': query}, {key: (means, counts)}

    def test_equal_observed_frames_not_trial_counts_or_zero_placeholders(self):
        metadata, arrays = self.example()
        result, support = REFERENCE.predict(metadata, arrays, self.bundle)
        self.assertEqual(result['responses'][0]['values'], [3.] * 240)
        self.assertEqual(support[:2], [2, 0])
        self.assertEqual(result['responses'][1]['values'], [0.] * 240)

    def test_only_same_acquisition_opposite_order_is_used(self):
        metadata, arrays = self.example()
        expected, _ = REFERENCE.predict(metadata, arrays, self.bundle)
        # Poisoned irrelevant entries must not be read or pooled with ROI indices.
        arrays['acquisition_1_ABC'] = object()
        arrays['acquisition_2_CBA'] = object()
        actual, _ = REFERENCE.predict(metadata, arrays, self.bundle)
        self.assertEqual(actual, expected)

    def test_complete_shapes_in_both_orders_all_six_acquisitions(self):
        total = 0
        for index, query in enumerate(self.bundle.panel['contexts']):
            metadata, arrays = self.example(index)
            outcome, support = REFERENCE.predict(metadata, arrays, self.bundle)
            self.assertEqual(outcome['context_id'], query['context_id'])
            self.assertEqual(len(outcome['responses']), len(query['cell_keys']))
            self.assertEqual(len(support), len(query['cell_keys']))
            total += sum(len(row['values']) for row in outcome['responses'])
        self.assertEqual(total, 509360)

    def test_extreme_finite_signed_means_do_not_overflow(self):
        self.assertEqual(REFERENCE.signed_mean([1e308] * 240), 1e308)
        self.assertEqual(REFERENCE.signed_mean([-1e308] * 240), -1e308)
        self.assertEqual(REFERENCE.signed_mean([1e308, -1e308]), 0.)
        self.assertEqual(REFERENCE.signed_mean([2., 4.]), 3.)
        self.assertEqual(REFERENCE.signed_mean([1e308, -1e308, 1e-308]), 1e-308 / 3)

    def test_invalid_support_and_geometry_refused(self):
        metadata, arrays = self.example()
        key = next(iter(arrays))
        means, counts = arrays[key]
        for changed_means, changed_counts in (
                (means.astype(np.float32), counts), (means, counts.astype(np.int64)),
                (means[:, :-1], counts[:, :-1]), (means, np.zeros_like(counts))):
            with self.assertRaises(ValueError):
                REFERENCE.predict(metadata, {key: (changed_means, changed_counts)}, self.bundle)
        counts[0, 0] = 51
        with self.assertRaises(ValueError):
            REFERENCE.predict(metadata, arrays, self.bundle)
        counts[0, 0] = 1
        means[1, 0] = 17.
        with self.assertRaises(ValueError):
            REFERENCE.predict(metadata, arrays, self.bundle)
        with self.assertRaises(ValueError):
            REFERENCE.predict(metadata, {}, self.bundle)

    def captures(self):
        results = {}
        records = []
        for index, query in enumerate(self.bundle.panel['contexts']):
            metadata, arrays = self.example(index)
            outcome, support = REFERENCE.predict(metadata, arrays, self.bundle)
            descriptor = next(row for row in self.bundle.lock['files']
                              if row['fold'] == index and row['target'] == 'view/input.json')
            value = {'schema': 'neural037-training-mean-reference-v1', 'rule': REFERENCE.RULE,
                     'packet_id': self.bundle.panel['packet_id'], 'context_id': query['context_id'],
                     'source_binding': self.bundle.source_binding,
                     'input_pin': {k: descriptor[k] for k in ('bytes', 'sha256')},
                     'training_observed_frames_per_roi': support, 'outcome': outcome,
                     'scientific_qualified': False}
            path = '/' + query['context_id'] + '.json'
            body = self.bundle.io.canonical(value)
            results[path] = body
            records.append({'context_id': query['context_id'], 'path': path, **self.bundle.io.pin(body)})
        return records, results

    def collect_generated(self, records, results):
        def read(path, cap, expected):
            body = results[str(path)]
            self.assertLessEqual(len(body), cap)
            self.assertEqual(self.bundle.io.pin(body), expected)
            return body
        with mock.patch.object(self.bundle.io, 'read', side_effect=read):
            return REFERENCE.collect(records, self.bundle)

    def test_complete_capture_collection_joins_ids(self):
        records, results = self.captures()
        result = self.collect_generated(list(reversed(records)), results)
        self.assertEqual([x['context_id'] for x in result['outcomes']], self.bundle.lock['contexts'])
        predictions, abstained = self.bundle.core.admit(self.bundle.panel, result, np)
        self.assertEqual(len(predictions), 12)
        self.assertEqual(abstained, [])

    def test_mismatched_reference_and_partial_capture_refused(self):
        records, results = self.captures()
        with self.assertRaises(ValueError):
            self.collect_generated(records[:-1], results)
        bad_records = records[:-1] + [records[0]]
        with self.assertRaises(ValueError):
            self.collect_generated(bad_records, results)
        path = records[0]['path']
        for field, replacement in [('rule', 'another-reference'), ('packet_id', 'wrong'),
                                   ('scientific_qualified', True)]:
            value = self.bundle.io.decode(results[path])
            value[field] = replacement
            body = self.bundle.io.canonical(value)
            altered = [dict(row) for row in records]
            altered[0].update(self.bundle.io.pin(body))
            with self.assertRaises(ValueError):
                self.collect_generated(altered, {**results, path: body})

    def test_producer_reuses_single_view_admission_without_targets(self):
        metadata, arrays = self.example()
        input_pin = {'bytes': 7, 'sha256': '1' * 64}
        loader = mock.Mock(return_value=(metadata, input_pin, arrays))
        with mock.patch.object(self.bundle, 'local', return_value=types.SimpleNamespace(load_view=loader)):
            result = REFERENCE.produce(Path('/generated/view'), 'acquisition_1_ABC', self.bundle)
        loader.assert_called_once_with(Path('/generated/view'), 'acquisition_1_ABC', self.bundle)
        self.assertEqual(result['input_pin'], input_pin)
        self.assertIs(result['scientific_qualified'], False)
        self.assertNotIn('actions', result)
        self.assertEqual(result['rule'], REFERENCE.RULE)


if __name__ == '__main__':
    unittest.main(verbosity=2)
