"""Generated software controls only; no original arrays or historical targets."""
import math
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import numpy as np

import delivery_io as io
import preparation_core as prep
import scorer_core as core
import score as cli
from array_io import put_array


def panel():
    contexts = []
    for i, (cells, frames) in enumerate(core.SHAPES, 1):
        for order in prep.ORDERS:
            contexts.append({'context_id': f'acquisition_{i}_{order}',
                'acquisition': f'acquisition_{i}', 'query_order': order,
                'cell_keys': [f'cell_{j:04d}' for j in range(cells)], 'frames': frames})
    public = {'schema': 'neural037-panel-v1', 'generation': 'a' * 64, 'contexts': contexts}
    public['packet_id'] = core.fingerprint(public)
    targets = {'packet_id': public['packet_id'], 'contexts': {}}
    submission = {'schema': 'neural037-predictions-v1', 'packet_id': public['packet_id'], 'outcomes': []}
    for c in contexts:
        shape = (len(c['cell_keys']), c['frames'])
        targets['contexts'][c['context_id']] = {'means': np.zeros(shape, dtype=np.float64),
            'counts': np.full(shape, 50, dtype=np.uint16), 'training_scale': 2.}
        submission['outcomes'].append({'context_id': c['context_id'], 'status': 'complete',
            'responses': [{'cell_key': key, 'values': [0.] * c['frames']} for key in c['cell_keys']]})
    return public, targets, submission


class EndpointTests(unittest.TestCase):
    def test_trial_mean_keeps_missing_rows_and_frames(self):
        traces = np.full((3, 50, 4), np.nan, dtype='<f8')
        traces[0, 0, :] = [1., 2., 3., 4.]
        traces[0, 1, :] = [5., 6., 7., 8.]
        traces[1, :, 0] = 9.
        means, counts = prep.summarize(traces, np)
        np.testing.assert_array_equal(means, [[3., 4., 5., 6.], [9., 0., 0., 0.], [0., 0., 0., 0.]])
        np.testing.assert_array_equal(counts, [[2, 2, 2, 2], [50, 0, 0, 0], [0, 0, 0, 0]])
        with self.assertRaises(ValueError):
            prep.summarize(np.full((3, 50, 4), np.nan), np)
        traces[0, 0, 0] = np.inf
        with self.assertRaises(ValueError):
            prep.summarize(traces, np)

    def test_training_scale_is_within_cell_and_training_only(self):
        # Variances 1 and 4, equally weighted; offsets and missing row irrelevant.
        means = np.array([[0., 2.], [98., 102.], [0., 0.]])
        counts = np.array([[1, 50], [1, 1], [0, 0]], dtype=np.uint16)
        self.assertAlmostEqual(prep.training_scale(means, counts, np), math.sqrt(2.5))
        with self.assertRaises(ValueError):
            prep.training_scale(np.ones((3, 2)), counts, np)

    def test_all_twelve_holdouts_keep_exact_other_eleven(self):
        pool = [{'acquisition': f'acquisition_{i}', 'order': o} for i in range(1, 7) for o in prep.ORDERS]
        for query in pool:
            train = prep.select_training(pool, query['acquisition'], query['order'])
            self.assertEqual(len(train), 11)
            self.assertNotIn(query, train)
            self.assertEqual(sum(r['acquisition'] == query['acquisition'] for r in train), 1)
        bad = pool[:-1] + [pool[0]]
        with self.assertRaises(ValueError):
            prep.select_training(bad, 'acquisition_1', 'ABC')

    def test_complete_geometry_not_a_small_surrogate_panel(self):
        public, _, _ = panel()
        self.assertEqual(sum(len(c['cell_keys']) for c in public['contexts']), 2264)
        public['contexts'][0]['frames'] = 239
        public['contexts'][1]['frames'] = 239
        public['packet_id'] = core.fingerprint({k: v for k, v in public.items() if k != 'packet_id'})
        with self.assertRaises(ValueError):
            core.public_contract(public)

    def test_exact_and_equal_acquisition_order_aggregation(self):
        public, targets, submission = panel()
        self.assertEqual(core.score(public, submission, lambda: targets, np)['metric'], 0.)
        for j, outcome in enumerate(submission['outcomes'], 1):
            for row in outcome['responses']:
                row['values'] = [2. * j] * len(row['values'])
        result = core.score(public, submission, lambda: targets, np)
        self.assertAlmostEqual(result['metric'], 6.5)
        np.testing.assert_allclose([r['normalized_rmse'] for r in result['acquisitions']], [1.5, 3.5, 5.5, 7.5, 9.5, 11.5])
        np.testing.assert_allclose([r['raw_rmse'] for r in result['acquisitions']], [3., 7., 11., 15., 19., 23.])

    def test_cell_equal_weight_not_trial_or_observed_frame_weight(self):
        public, targets, submission = panel()
        name = public['contexts'][0]['context_id']
        target = targets['contexts'][name]
        target['counts'][:] = 0
        target['counts'][0, 0] = 1
        target['counts'][1, :] = 50
        submission['outcomes'][0]['responses'][0]['values'] = [4.] * 240
        # The two observed cells have normalized MSEs 4 and 0.
        result = core.score(public, submission, lambda: targets, np)
        self.assertAlmostEqual(result['metric'], math.sqrt(2.) / 12)
        row = result['contexts'][0]
        self.assertEqual(row['observed_cells'], 2)
        self.assertEqual(row['unobserved_cells'], 249)
        self.assertEqual(row['per_cell_normalized_mse'][:3], [4., 0., None])

    def test_reordering_is_identity_joined(self):
        public, targets, submission = panel()
        submission['outcomes'].reverse()
        for outcome in submission['outcomes']:
            outcome['responses'].reverse()
        self.assertEqual(core.score(public, submission, lambda: targets, np)['metric'], 0.)

    def test_bad_submission_never_reads_target(self):
        public, _, submission = panel()
        for value in (True, float('nan'), float('inf')):
            submission['outcomes'][0]['responses'][0]['values'][0] = value
            with self.assertRaises(ValueError):
                core.score(public, submission, lambda: self.fail('target accessed'), np)
        submission['outcomes'][0]['responses'][0]['values'][0] = 0.
        submission['outcomes'][0]['responses'][1]['cell_key'] = 'cell_0000'
        with self.assertRaises(ValueError):
            core.score(public, submission, lambda: self.fail('target accessed'), np)
        submission['outcomes'].pop()
        with self.assertRaises(ValueError):
            core.score(public, submission, lambda: self.fail('target accessed'), np)

    def test_abstention_is_no_score_with_no_target_access(self):
        public, _, submission = panel()
        submission['outcomes'][0] = {'context_id': 'acquisition_1_ABC', 'status': 'abstain', 'reason': 'fixture'}
        result = core.score(public, submission, lambda: self.fail('target accessed'), np)
        self.assertEqual(result['status'], 'abstained')
        self.assertIsNone(result['metric'])

    def test_empty_source_and_wrong_private_generation_refused(self):
        public, targets, submission = panel()
        targets['packet_id'] = 'b' * 64
        with self.assertRaises(ValueError):
            core.score(public, submission, lambda: targets, np)
        targets['packet_id'] = public['packet_id']
        targets['contexts']['acquisition_1_ABC']['counts'][:] = 0
        with self.assertRaises(ValueError):
            core.score(public, submission, lambda: targets, np)

    def test_finite_mse_is_not_rejected_by_intermediate_sum_overflow(self):
        public, targets, submission = panel()
        value = math.sqrt(5e307)
        for target in targets['contexts'].values():
            target['training_scale'] = 1.
        for outcome in submission['outcomes']:
            for row in outcome['responses']:
                row['values'] = [value] * len(row['values'])
        result = core.score(public, submission, lambda: targets, np)
        self.assertEqual(result['status'], 'scored')
        self.assertTrue(math.isclose(result['metric'], value, rel_tol=1e-14))
        submission['outcomes'][0]['responses'][0]['values'][0] = 1e308
        result = core.score(public, submission, lambda: targets, np)
        self.assertEqual(result['status'], 'numeric_error')
        self.assertIsNone(result['metric'])

    def test_subnormal_squared_errors_remain_positive_at_every_level(self):
        public, targets, submission = panel()
        value = math.sqrt(100 * math.ulp(0.0))
        for target in targets['contexts'].values():
            target['training_scale'] = 1.
        for outcome in submission['outcomes']:
            for row in outcome['responses']:
                row['values'] = [value] * len(row['values'])
        result = core.score(public, submission, lambda: targets, np)
        self.assertEqual(result['status'], 'scored')
        self.assertTrue(math.isclose(result['metric'], value, rel_tol=1e-14, abs_tol=0.))
        for context in result['contexts']:
            self.assertTrue(math.isclose(context['normalized_rmse'], value, rel_tol=1e-14, abs_tol=0.))
            self.assertTrue(all(x > 0 for x in context['per_cell_normalized_mse']))
        for acquisition in result['acquisitions']:
            self.assertTrue(math.isclose(acquisition['normalized_rmse'], value, rel_tol=1e-14, abs_tol=0.))

    def test_single_large_residual_with_finite_cell_mse_is_scored(self):
        public, targets, submission = panel()
        for target in targets['contexts'].values():
            target['training_scale'] = 1.
        submission['outcomes'][0]['responses'][0]['values'][0] = 1e155
        result = core.score(public, submission, lambda: targets, np)
        self.assertEqual(result['status'], 'scored')
        expected = 1e155 / math.sqrt(240 * 251)
        self.assertTrue(math.isclose(result['contexts'][0]['normalized_rmse'], expected, rel_tol=1e-14))
        self.assertTrue(math.isclose(result['metric'], expected / 12, rel_tol=1e-14))
        self.assertTrue(math.isfinite(result['contexts'][0]['per_cell_normalized_mse'][0]))

    def test_unrepresentable_nonzero_diagnostic_never_becomes_zero_score(self):
        public, targets, submission = panel()
        submission['outcomes'][0]['responses'][0]['values'][0] = 1e-200
        result = core.score(public, submission, lambda: targets, np)
        self.assertEqual(result['status'], 'numeric_error')
        self.assertIsNone(result['metric'])

    def test_stable_reducers_preserve_tiny_uniform_values_and_large_means(self):
        smallest = math.ulp(0.0)
        self.assertEqual(core.stable_rms([smallest] * 240), smallest)
        self.assertEqual(core.stable_mean_nonnegative([smallest] * 12), smallest)
        self.assertEqual(core.stable_mean_nonnegative([1e308] * 12), 1e308)
        self.assertEqual(core.stable_rms([1e308] * 240), 1e308)

    def test_cli_admits_before_opening_private_path(self):
        public, _, _ = panel()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            io.put(root / 'panel.json', public)
            argv = ['score.py', '--public', str(root / 'panel.json'), '--submission', str(root / 'missing.json'),
                '--private', str(root / 'forbidden.json'), '--private-bytes', '1', '--private-sha256', '0' * 64,
                '--output', str(root / 'result.json')]
            with mock.patch('sys.argv', argv), mock.patch.object(cli, 'load_targets', side_effect=AssertionError('target read')):
                self.assertEqual(cli.main(), 2)
            self.assertEqual(io.json_file(root / 'result.json')['private_target_callbacks'], 0)

    def test_cli_full_array_transport_and_hash_binding(self):
        public, targets, submission = panel()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            metadata = {'schema': 'neural037-targets-v1', **targets, 'contexts': {}}
            for name, target in targets['contexts'].items():
                entry = {'training_scale': target['training_scale']}
                for kind in ('means', 'counts'):
                    path = f'{name}_{kind}.npy'
                    entry[kind] = {'path': path, **put_array(root / path, target[kind], np)}
                metadata['contexts'][name] = entry
            pin = io.put(root / 'targets.json', metadata)
            io.put(root / 'panel.json', public)
            io.put(root / 'submission.json', submission, 64000000)
            argv = ['score.py', '--public', str(root / 'panel.json'), '--submission', str(root / 'submission.json'),
                '--private', str(root / 'targets.json'), '--private-bytes', str(pin['bytes']),
                '--private-sha256', pin['sha256'], '--output', str(root / 'result.json')]
            with mock.patch('sys.argv', argv):
                self.assertEqual(cli.main(), 0)
            self.assertEqual(io.json_file(root / 'result.json')['metric'], 0.)
            wrong = {**pin, 'sha256': '0' * 64}
            with self.assertRaises(ValueError):
                cli.load_targets(root / 'targets.json', wrong, public)

    def test_duplicate_json_and_escape_paths_refused(self):
        with self.assertRaises(ValueError):
            io.decode(b'{"a":1,"a":2}')
        for path in ('../targets.npy', '/targets.npy', 'arrays/../targets.npy'):
            with self.assertRaises(ValueError):
                io.resolve(Path('.'), path)


if __name__ == '__main__':
    unittest.main(verbosity=2)
