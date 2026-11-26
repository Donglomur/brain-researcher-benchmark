"""Generated complete-source normalization controls; no authentic observations.

Run under the preparation contract's NumPy 2.2.6. CLI observations are retained
in CLI_EVENTS for a selected outer runner; this module supplies no qualification.
"""
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np

HERE = Path(__file__).resolve().parent
SOURCE = HERE / 'runtime/source'
PROGRAMME = HERE.parent / 'neural029-programme'
CLI_EVENTS = []
GENERATED_OBSERVATIONS = {}
spec = importlib.util.spec_from_file_location('neural029_prepare_controls', SOURCE / 'prepare.py')
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


def original_scale(train):
    return float(np.mean((train - train.mean(axis=(0, 2), keepdims=True)) ** 2))


def raw_fixture(root, sources, targets):
    """Invent a complete six-session census with all three required pairs."""
    census = []
    for session in range(1, 7):
        delay = 1 if session in (1, 4) else 2
        has = session != 6
        census.append({'session_index1': session, 'is_grc': True, 'delay_s': delay,
                       'has_chronic_green': has, 'disposition': 'not_two_second_target' if delay == 1
                       else 'required_registered_target' if has else 'no_chronicGreen_registration'})
    pairs = []
    for ordinal, (source, target, mouse) in enumerate([(1, 2, 'A'), (1, 3, 'A'), (4, 5, 'B')], 1):
        train, query = sources[ordinal - 1], targets[ordinal - 1]
        cells = train.shape[1]
        row = {'pair_index1': ordinal, 'source_session_index1': source, 'target_session_index1': target,
               'mouse_id': mouse, 'reward_type': 'DAT',
               'source_cells_index1': list(range(1, cells + 1)),
               'target_cells_index1': list(range(1, cells + 1)),
               'source_shape': list(train.shape), 'target_shape': list(query.shape),
               'source_time_seconds': [i / 20 for i in range(61)],
               'target_time_seconds': [i / 20 for i in range(61)],
               'registration_rows_source_target': [[i, i] for i in range(1, cells + 1)] + [[0, cells + 1]]}
        for side, values in (('source', train), ('target', query)):
            name = f'pair{ordinal:04d}_{side}.f64'
            body = np.asarray(values, dtype='<f8').tobytes()
            (root / name).write_bytes(body)
            row[side + '_file'] = {'path': name, 'bytes': len(body),
                                  'sha256': hashlib.sha256(body).hexdigest()}
        pairs.append(row)
    index = {'schema': 'neural029-raw-projection-v2', 'source_record': '21645651',
             'complete_selected_cohort': True, 'source_part_count': 2, 'source_session_count': 6,
             'selected_target_session_indices1': [2, 3, 5], 'cohort_dispositions': census, 'pairs': pairs,
             'scientific_fits': 0, 'scientific_scores': 0}
    raw = (json.dumps(index, sort_keys=True, allow_nan=False) + '\n').encode()
    (root / 'INDEX.json').write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


class SourceNormalizationControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if np.__version__ != '2.2.6':
            raise RuntimeError('NumPy2.2.6 required for preparation regression')

    def cli(self, script, arguments, expected=0):
        argv = [sys.executable, '-I', '-B', str(script), *map(str, arguments)]
        result = subprocess.run(argv, capture_output=True, text=True, timeout=20,
                                cwd=HERE, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
        CLI_EVENTS.append({'argv': argv, 'returncode': result.returncode,
                           'stdout': result.stdout, 'stderr': result.stderr})
        self.assertEqual(result.returncode, expected, result.stderr)
        return result

    def test_old_constant_roundoff_is_observed_and_corrected(self):
        train = np.full((5, 2, 61), .1)
        old, corrected = original_scale(train), prepare.training_scale_squared(train, np)
        previous = np.full((5, 1, 61), .1)
        previous_old = original_scale(previous)
        previous_corrected = prepare.training_scale_squared(previous, np)
        GENERATED_OBSERVATIONS['constant_counterexample'] = {
            'shape': list(train.shape), 'value': .1, 'numpy': np.__version__,
            'original_scale': old, 'maintained_scale': corrected,
            'previous_single_cell_fixture': {'shape': list(previous.shape),
                'original_scale': previous_old, 'maintained_scale': previous_corrected}}
        self.assertGreater(old, 0.)
        self.assertEqual(corrected, 0.)
        # The selected diagnostic observed zero/zero here. Retain the actual
        # old value without assuming its summation roundoff on every platform.
        self.assertEqual(previous_corrected, 0.)

    def test_distinct_constant_cells_keep_zero_within_cell_variance(self):
        train = np.broadcast_to(np.array([.1, -.3])[None, :, None], (5, 2, 61)).copy()
        self.assertEqual(prepare.training_scale_squared(train, np), 0.)
        self.assertTrue(np.all(train[:, 0] == .1))
        self.assertTrue(np.all(train[:, 1] == -.3))

    def test_between_trial_differences_are_not_constant(self):
        train = np.broadcast_to(np.arange(5.)[:, None, None], (5, 2, 61)).copy()
        self.assertEqual(prepare.training_scale_squared(train, np), original_scale(train))
        self.assertEqual(prepare.training_scale_squared(train, np), 2.)

    def test_within_trial_variation_preserves_original_arithmetic(self):
        train = np.arange(5 * 2 * 61, dtype=np.float64).reshape(5, 2, 61) / 7
        self.assertEqual(prepare.training_scale_squared(train, np), original_scale(train))

    def test_mixed_cells_retain_constant_cell_weight(self):
        varied = np.broadcast_to(np.arange(5.)[:, None, None], (5, 1, 61)).copy()
        train = np.concatenate((np.full_like(varied, .1), varied), axis=1)
        expected = original_scale(varied) / 2
        self.assertEqual(prepare.training_scale_squared(train, np), expected)
        self.assertEqual(train.shape, (5, 2, 61))
        np.testing.assert_array_equal(train[:, :1], np.full_like(varied, .1))

    def test_small_nonconstant_variance_is_not_thresholded(self):
        train = np.broadcast_to(np.arange(5.)[:, None, None] * 1e-150, (5, 1, 61)).copy()
        expected = original_scale(train)
        self.assertGreater(expected, 0.)
        self.assertEqual(prepare.training_scale_squared(train, np), expected)

    def test_final_source_trial_remains_in_variance(self):
        train = np.full((5, 1, 61), .1)
        train[-1, 0, -1] = .2
        self.assertGreater(prepare.training_scale_squared(train, np), 0.)
        self.assertEqual(prepare.training_scale_squared(train, np), original_scale(train))

    def prepare_and_grade(self, sources, targets):
        with tempfile.TemporaryDirectory(prefix='neural029-source-normalization-') as directory:
            root = Path(directory)
            raw = root / 'raw'
            raw.mkdir()
            digest = raw_fixture(raw, sources, targets)
            packet = root / 'packet'
            self.cli(SOURCE / 'prepare.py',
                     ['--source-root', raw, '--index-sha256', digest, '--output', packet])
            public = json.loads((packet / 'public/MANIFEST.json').read_text())
            metadata = json.loads((packet / 'private/TARGETS.json').read_text())
            receipt = json.loads((packet / 'PREPARATION_RECEIPT.json').read_text())
            self.assertEqual(len(public['pairs']), 3)
            self.assertEqual(len(metadata['pairs']), 3)
            self.assertEqual(metadata['schema'], 'neural029-targets-v2')
            self.assertEqual(public['schema'], 'neural029-public-v1')
            self.assertTrue(receipt['complete_cohort'])
            self.assertFalse(receipt['scientific_execution_qualified'])
            self.assertFalse(receipt['submission_ready'])
            grid = np.arange(61, dtype=np.float64) / 20
            warp_grid = np.where(grid < 2, grid / 2, grid - 1)
            predictions, expected = [], []
            for number, (p, t, train, query) in enumerate(zip(public['pairs'], metadata['pairs'],
                                                             sources, targets, strict=True)):
                self.assertEqual(p['calibration_trials'], 4 * len(train) // 5)
                self.assertEqual(p['validation_trials'], len(train) - 4 * len(train) // 5)
                self.assertEqual(len(p['cell_ids']), train.shape[1])
                self.assertEqual(len(p['query_ids']), len(query))
                with np.load(packet / p['file']['path'], allow_pickle=False) as data:
                    prepared_train = np.concatenate((data['calibration'], data['validation']))
                np.testing.assert_array_equal(prepared_train, train)
                self.assertTrue(prepared_train.flags.c_contiguous)
                baseline = train.mean(axis=0)
                warp = np.stack([np.interp(warp_grid, grid, cell) for cell in baseline])
                with np.load(packet / t['file']['path'], allow_pickle=False) as data:
                    np.testing.assert_array_equal(data['target'], query)
                    np.testing.assert_array_equal(data['baseline'], baseline)
                    np.testing.assert_array_equal(data['fixed_warp_baseline'], warp)
                prediction = query + (1., 3., 9.)[number]
                predictions.append({'pair_id': p['pair_id'], 'values': prediction.tolist()})
                expected.append({'scale': t['training_scale_squared'],
                                 'source_shape': list(prepared_train.shape),
                                 'source_c_contiguous': bool(prepared_train.flags.c_contiguous),
                                 'source_original_scale': original_scale(prepared_train),
                                 'candidate_mse': float(np.mean((prediction - query) ** 2)),
                                 'baseline_mse': float(np.mean((baseline[None] - query) ** 2)),
                                 'warp_mse': float(np.mean((warp[None] - query) ** 2))})
            submission = root / 'submission.json'
            submission.write_text(json.dumps({'schema': 'neural029-predictions-v1',
                                               'predictions': predictions}, allow_nan=False) + '\n')
            output = root / 'grade.json'
            self.cli(PROGRAMME / 'grade.py',
                     ['--root', packet, '--binding', packet / 'private/BINDING.json',
                      '--submission', submission, '--output', output])
            result = json.loads(output.read_text())
            self.assertEqual(result['schema'], 'neural029-grade-v2')
            self.assertEqual(len(result['pairs']), 3)
            self.assertEqual([m['pairs'] for m in result['mice']], [2, 1])
            self.assertTrue(result['all_pairs_retained'])
            self.assertFalse(result['scientific_execution_qualified'])
            self.assertFalse(result['submission_ready'])
            self.assertFalse(result['causal_or_new_animal_claim'])
            self.assertEqual(len(result['leave_one_mouse']), 2)
            for row, train, query in zip(result['pairs'], sources, targets, strict=True):
                self.assertEqual(row['registered_cells'], train.shape[1])
                self.assertEqual(row['query_trials'], len(query))
                self.assertEqual(row['time_bins'], 61)
            return metadata, result, expected

    def test_prepare_constant_source_to_grade_withholds_complete_primary(self):
        sources = [np.full((5, 2, 61), .1) for _ in range(3)]
        targets = [np.arange(2 * 2 * 61, dtype=np.float64).reshape(2, 2, 61) / 20 for _ in range(3)]
        metadata, result, expected = self.prepare_and_grade(sources, targets)
        GENERATED_OBSERVATIONS['constant_packet_grade'] = {'metadata': metadata, 'grade': result,
            'prepared_source': [{'shape': row['source_shape'], 'c_contiguous': row['source_c_contiguous'],
                                 'original_scale': row['source_original_scale'],
                                 'maintained_scale': row['scale']} for row in expected]}
        self.assertTrue(all(row['source_shape'] == [5, 2, 61] for row in expected))
        self.assertTrue(all(row['source_original_scale'] > 0. for row in expected))
        self.assertTrue(all(t['training_scale_squared'] == 0. for t in metadata['pairs']))
        for key in ('primary_nrmse', 'baseline_nrmse', 'fixed_warp_nrmse',
                    'candidate_minus_baseline', 'candidate_minus_fixed_warp', 'fixed_warp_minus_baseline'):
            self.assertIsNone(result[key])
        for pair in result['pairs']:
            self.assertTrue(pair['undefined_normalization'])
            self.assertFalse(pair['undefined_target_variance'])
            self.assertGreater(pair['rmse'], 0.)
            for key in ('nrmse', 'baseline_nrmse', 'fixed_warp_nrmse',
                        'candidate_minus_baseline', 'candidate_minus_fixed_warp', 'fixed_warp_minus_baseline'):
                self.assertIsNone(pair[key])
        self.assertTrue(all(mouse['nrmse'] is None for mouse in result['mice']))

    def test_prepare_nonconstant_source_to_grade_preserves_comparators_and_weights(self):
        train = np.arange(5 * 2 * 61, dtype=np.float64).reshape(5, 2, 61) / 20
        sources = [train.copy(), train.copy(), train * 2]
        targets = [np.arange(n * 2 * 61, dtype=np.float64).reshape(n, 2, 61) / 10 for n in (2, 2, 3)]
        metadata, result, expected = self.prepare_and_grade(sources, targets)
        GENERATED_OBSERVATIONS['nonconstant_packet_grade'] = {
            'metadata': metadata, 'grade': result, 'expected': expected}
        for t, values in zip(metadata['pairs'], sources, strict=True):
            self.assertEqual(t['training_scale_squared'], original_scale(values))
        columns = {'nrmse': 'candidate_mse', 'baseline_nrmse': 'baseline_mse', 'fixed_warp_nrmse': 'warp_mse'}
        for column, mse in columns.items():
            values = [math.sqrt(row[mse] / row['scale']) for row in expected]
            for pair, value in zip(result['pairs'], values, strict=True):
                self.assertEqual(pair[column], value)
                self.assertFalse(pair['undefined_normalization'])
            primary = 'primary_nrmse' if column == 'nrmse' else column
            self.assertEqual(result[primary], math.fsum([math.fsum(values[:2]) / 2, values[2]]) / 2)
        for row in result['pairs']:
            self.assertEqual(row['candidate_minus_baseline'], row['nrmse'] - row['baseline_nrmse'])
            self.assertEqual(row['candidate_minus_fixed_warp'], row['nrmse'] - row['fixed_warp_nrmse'])
            self.assertEqual(row['fixed_warp_minus_baseline'], row['fixed_warp_nrmse'] - row['baseline_nrmse'])

    def test_nonfinite_source_is_refused_before_normalization(self):
        with tempfile.TemporaryDirectory(prefix='neural029-source-nonfinite-') as directory:
            root = Path(directory)
            raw = root / 'raw'
            raw.mkdir()
            sources = [np.full((5, 1, 61), float('inf')) for _ in range(3)]
            targets = [np.ones((2, 1, 61)) for _ in range(3)]
            digest = raw_fixture(raw, sources, targets)
            packet = root / 'packet'
            result = self.cli(SOURCE / 'prepare.py',
                              ['--source-root', raw, '--index-sha256', digest, '--output', packet], expected=1)
            self.assertIn('nonfinite required values are a preparation blocker', result.stderr)
            self.assertFalse((packet / 'private/TARGETS.json').exists())

    def test_current_operator_authenticates_complete_source_inventory(self):
        result = self.cli(HERE / 'central_operator.py', ['inspect'])
        report = json.loads(result.stdout)
        self.assertEqual(report['inherited_source_roles'], 24)
        self.assertTrue(all(value is False for value in report['qualification'].values()))

    def test_inert_source_controls_retain_all_previous_nonvariance_checks(self):
        result = self.cli(SOURCE / 'inert_checks.py', [])
        report = json.loads(result.stdout)
        previous = json.loads((SOURCE / 'INERT_CHECKS.json').read_text())
        old = set(previous['checks']) - {'pooled_training_scale_expression_preserved'}
        self.assertTrue(old <= set(report['checks']))
        self.assertEqual(report['count'], 29)
        self.assertEqual(report['numpy_imports'], 0)
        self.assertFalse(report['scientific_execution_qualified'])


if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=True)
