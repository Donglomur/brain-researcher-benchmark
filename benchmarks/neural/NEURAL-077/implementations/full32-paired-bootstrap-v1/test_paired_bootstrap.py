"""New generated bootstrap controls; no original targets or evaluator import.

The coordinator runs these once inside the selected NumPy runtime. Replicate
arrays stay in memory. The sole CLI fixture writes only small JSON summaries.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import platform
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('erp_paired_bootstrap_controls', HERE / 'paired_bootstrap.py')
bootstrap = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = bootstrap
spec.loader.exec_module(bootstrap)
POLICY = json.loads((HERE / 'BOOTSTRAP_POLICY.v1.json').read_bytes())


def result_fixture(mode='varied'):
    scores = {}
    for arm, condition in enumerate(bootstrap.CONDITIONS):
        rows = []
        for index, person in enumerate(bootstrap.PEOPLE):
            if mode == 'constant':
                tp, tn, loss = (40, 160, .2) if arm == 0 else (20, 80, .7)
            else:
                effective_arm = 0 if mode == 'identical' else arm
                tp = (index * 7 + effective_arm * 3) % 41
                tn = (index * 19 + effective_arm * 11) % 161
                loss = math.sqrt(index + 2) / 10 + effective_arm * (index % 5 + 1) / 50
            rows.append({'participant_id': person, 'trials': 200, 'targets': 40, 'standards': 160,
                         'target_true_positive': tp, 'standard_true_negative': tn,
                         'balanced_accuracy': .5 * (tp / 40 + tn / 160), 'natural_log_loss': loss})
        scores[condition] = {'participants': rows,
                             'participant_macro_balanced_accuracy': sum(r['balanced_accuracy'] for r in rows) / 32,
                             'participant_macro_natural_log_loss': sum(r['natural_log_loss'] for r in rows) / 32}
    a, b = (scores[c]['participants'] for c in bootstrap.CONDITIONS)
    differences = [{'participant_id': x['participant_id'],
                    'direct_minus_program_balanced_accuracy': x['balanced_accuracy'] - y['balanced_accuracy'],
                    'direct_minus_program_natural_log_loss': x['natural_log_loss'] - y['natural_log_loss']}
                   for x, y in zip(a, b, strict=True)]
    return {'schema': 'erp-full32-protected-pair-evaluation-v1', 'status': 'complete_finite_cohort_pair',
            'people': 32, 'queries': 6400, 'scores': scores, 'paired_person_differences': differences,
            'primary_direct_minus_program_macro_BA': sum(r['direct_minus_program_balanced_accuracy'] for r in differences) / 32,
            'both_public_arms_and_owned_closures_validated_before_private': True,
            'contract': {'bytes': 4096, 'sha256': 'a' * 64},
            # Real ARM receipts can exceed the sidecar's small input-file cap.
            'public_arm_receipts': [{'bytes': 1048576, 'sha256': 'b' * 64},
                                    {'bytes': 1048577, 'sha256': 'c' * 64}],
            'new_benchmarks': 0}


def run_generated(result):
    return bootstrap.paired_bootstrap(result, POLICY, expected_python_version='3.11.6', expected_numpy_version='1.26.3')


class PairedParticipantBootstrapControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if platform.python_version() != '3.11.6' or np.__version__ != '1.26.3':
            raise AssertionError('These selected source controls require observed Python3.11.6/NumPy1.26.3; no skip.')

    def test_policy_exact_declared_and_completed_conventions(self):
        self.assertEqual(POLICY, bootstrap.POLICY)
        self.assertEqual((POLICY['participants'], POLICY['draw_size'], POLICY['resamples']), (32, 32, 10000))
        self.assertEqual((POLICY['rng'], POLICY['seed']), ('NumPy.Generator(PCG64)', 20261119))
        self.assertEqual((POLICY['confidence_level'], POLICY['interval_family'], POLICY['quantile_method']), (.95, 'percentile', 'linear'))
        self.assertEqual(POLICY['secondary_unadjusted_intervals'], list(bootstrap.METRICS[1:]))
        self.assertIsNone(POLICY['significance_or_pass_threshold'])
        for key, value in [('seed', 1), ('seed', 20261119.0), ('draw_size', 6400), ('quantile_method', 'nearest')]:
            altered = copy.deepcopy(POLICY); altered[key] = value
            with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, 'policy'):
                bootstrap.paired_bootstrap(result_fixture(), altered, expected_python_version='3.11.6', expected_numpy_version='1.26.3')

    def test_complete_ordered_pairing_and_no_missingness_or_trial_reweighting(self):
        fixture = result_fixture(); bootstrap.validate_result(fixture)
        for change in ('missing', 'duplicate', 'foreign', 'reordered', 'trial_count', 'class_count', 'unvalidated'):
            altered = copy.deepcopy(fixture); rows = altered['scores'][bootstrap.CONDITIONS[1]]['participants']
            if change == 'missing': rows.pop()
            elif change == 'duplicate': rows[1] = rows[0]
            elif change == 'foreign': rows[0]['participant_id'] = 'sub-007'
            elif change == 'reordered': rows[0], rows[1] = rows[1], rows[0]
            elif change == 'trial_count': rows[0]['trials'] = 199
            elif change == 'class_count': rows[0]['targets'] = 39
            else: altered['both_public_arms_and_owned_closures_validated_before_private'] = False
            with self.subTest(change=change), patch.object(np.random, 'Generator') as generator, self.assertRaises(ValueError):
                run_generated(altered)
            generator.assert_not_called()

    def test_confusion_macro_and_paired_difference_consistency(self):
        for change in ('confusion', 'macro', 'orientation', 'paired_count', 'boolean', 'nonfinite'):
            result = result_fixture(); score = result['scores'][bootstrap.CONDITIONS[0]]
            if change == 'confusion': score['participants'][0]['target_true_positive'] += 1
            elif change == 'macro': score['participant_macro_natural_log_loss'] += .1
            elif change == 'orientation': result['paired_person_differences'][0]['direct_minus_program_balanced_accuracy'] *= -1
            elif change == 'paired_count': result['paired_person_differences'].pop()
            elif change == 'boolean': score['participants'][0]['balanced_accuracy'] = False
            else: score['participants'][0]['natural_log_loss'] = float('nan')
            with self.subTest(change=change), self.assertRaises(ValueError):
                bootstrap.validate_result(result)

    def test_identical_arms_have_zero_paired_intervals_despite_person_variation(self):
        output = run_generated(result_fixture('identical'))
        for metric in bootstrap.METRICS[:2]:
            self.assertEqual([output['intervals'][metric][key] for key in ('point_estimate', 'lower', 'upper')], [0.0, 0.0, 0.0])
        for metric in bootstrap.METRICS[2:]:
            self.assertGreater(output['intervals'][metric]['upper'], output['intervals'][metric]['lower'])
        self.assertFalse(output['trial_resampling']); self.assertEqual(output['draws']['shape'], [10000, 32])

    def test_constant_shift_orientation_and_tied_percentiles(self):
        output = run_generated(result_fixture('constant'))
        for field in ('point_estimate', 'lower', 'upper'):
            self.assertEqual(output['intervals'][bootstrap.METRICS[0]][field], .5)
            self.assertAlmostEqual(output['intervals'][bootstrap.METRICS[1]][field], -.5, places=14)
        self.assertEqual(output['people'], 32)
        self.assertNotIn('participants', output); self.assertNotIn('paired_person_differences', output)

    def test_seeded_determinism_and_no_global_rng_mutation(self):
        state_before = np.random.get_state()
        first = run_generated(result_fixture()); second = run_generated(result_fixture())
        self.assertEqual(first, second)
        state_after = np.random.get_state()
        self.assertEqual(state_before[0], state_after[0]); np.testing.assert_array_equal(state_before[1], state_after[1])
        self.assertEqual(state_before[2:], state_after[2:])

    def test_shared_draws_person_weights_and_manual_linear_percentile_oracle(self):
        result = result_fixture(); output = run_generated(result)
        # Independent frequency-weight calculation, not advanced indexing mean.
        rng = np.random.Generator(np.random.PCG64(20261119))
        indices = rng.integers(0, 32, size=(10000, 32), dtype=np.int64, endpoint=False)
        expected_hash = hashlib.sha256(indices.astype('<i8', copy=False).tobytes()).hexdigest()
        self.assertEqual(output['draws']['sha256'], expected_hash)
        counts = np.asarray([np.bincount(row, minlength=32) for row in indices], dtype=np.float64)
        np.testing.assert_array_equal(counts.sum(axis=1), np.full(10000, 32.0))
        vectors = bootstrap.validate_result(result)
        for name in bootstrap.METRICS:
            draws = (counts @ np.asarray(vectors[name], dtype=np.float64)) / 32
            ordered = np.sort(draws)
            expected = []
            for quantile in (.025, .975):
                position = (len(ordered) - 1) * quantile; lower = int(math.floor(position))
                expected.append(float(ordered[lower] + (position - lower) * (ordered[lower + 1] - ordered[lower])))
            observed = output['intervals'][name]
            self.assertAlmostEqual(observed['lower'], expected[0], places=13)
            self.assertAlmostEqual(observed['upper'], expected[1], places=13)
            self.assertEqual(observed['point_estimate'], sum(vectors[name]) / 32)

    def test_explicit_runtime_versions_are_checked_before_rng(self):
        for python_version, numpy_version in [('0.0.0', '1.26.3'), ('3.11.6', '0.0.0'), ('', '1.26.3')]:
            with self.subTest(python=python_version, numpy=numpy_version), patch.object(np.random, 'Generator') as generator, self.assertRaises(ValueError):
                bootstrap.paired_bootstrap(result_fixture(), POLICY, expected_python_version=python_version,
                                           expected_numpy_version=numpy_version)
            generator.assert_not_called()

    def test_additive_reporting_does_not_mutate_input_or_invent_thresholds(self):
        result = result_fixture(); before = copy.deepcopy(result); output = run_generated(result)
        self.assertEqual(result, before); self.assertEqual(set(output['intervals']), set(bootstrap.METRICS))
        self.assertEqual(output['intervals'][bootstrap.METRICS[0]]['role'], 'primary')
        self.assertTrue(all(output['intervals'][metric]['role'] == 'secondary_unadjusted' for metric in bootstrap.METRICS[1:]))
        self.assertFalse(output['multiple_comparisons_adjusted']); self.assertEqual(output['private_targets_read'], 0)
        self.assertEqual(output['new_benchmarks'], 0)
        self.assertIn('not representative-population', output['interpretation'])
        for forbidden in ('p_value', 'significant', 'passed', 'improvement_ready'):
            self.assertNotIn(forbidden, output)

    def test_cli_pinned_summary_and_policy_create_only_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve(); result_path = root / 'result.json'; policy_path = root / 'policy.json'
            result_body = bootstrap.encode(result_fixture()); policy_body = bootstrap.encode(POLICY)
            result_path.write_bytes(result_body); policy_path.write_bytes(policy_body)
            output = root / 'bootstrap.json'
            argv = ['--result', str(result_path), '--result-bytes', str(len(result_body)), '--result-sha256', bootstrap.pin(result_body)['sha256'],
                    '--policy', str(policy_path), '--policy-bytes', str(len(policy_body)), '--policy-sha256', bootstrap.pin(policy_body)['sha256'],
                    '--python-version', '3.11.6', '--numpy-version', '1.26.3', '--output', str(output)]
            wrong = list(argv); wrong[wrong.index('--result-sha256') + 1] = 'f' * 64
            with self.assertRaisesRegex(ValueError, 'commitment'):
                bootstrap.main(wrong)
            self.assertFalse(output.exists())
            with redirect_stdout(io.StringIO()): self.assertEqual(bootstrap.main(argv), 0)
            body = output.read_bytes(); saved = json.loads(body)
            self.assertEqual(saved['input_result'], bootstrap.pin(result_body)); self.assertEqual(saved['input_policy'], bootstrap.pin(policy_body))
            with self.assertRaises(FileExistsError), redirect_stdout(io.StringIO()):
                bootstrap.main(argv)
            self.assertEqual(output.read_bytes(), body)


if __name__ == '__main__':
    unittest.main(verbosity=2)
