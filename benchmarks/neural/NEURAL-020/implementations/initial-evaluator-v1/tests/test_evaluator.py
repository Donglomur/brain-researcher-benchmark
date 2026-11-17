"""Generated engineering controls; none are authentic Area2 observations."""
import ast
import copy
import hashlib
import io
import importlib.util
import json
import logging
import math
import os
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import evaluator as e


def complete_fixture():
    counts = np.ones((826, 30, 65), dtype=np.float64)
    rows = []
    for i in range(826):
        role = 'train' if i < 2 else 'eval' if i < 4 else 'excluded'
        rows.append({'trial_id': 'source-trial-%04d' % i, 'block_id': 'block-%04d' % i,
                     'native_split': {'train': 'train', 'eval': 'val', 'excluded': 'test'}[role],
                     'role': role, 'ctr_hold_bump': i % 2, 'window_start_seconds': float(i),
                     'window_stop_seconds': i + .6,
                     'exclusion_reason': 'generated fixture exclusion' if role == 'excluded' else None})
    meta = {'schema_version': 1, 'task_id': e.TASK_ID, 'contract_sha256': e.CONTRACT_SHA256,
            'source': {'dandiset': '000127', 'version': '0.220113.0359', 'subject': 'Han',
                       'session_start_time': '2017-12-07T17:06:09.727000-05:00',
                       'asset_id': 'ded26b6c-418d-43f5-8a37-dfd072c2dbd4',
                       'asset_sha256': '639b1a03ab813f96fec76681110a1634942476badc0fd4c93d406c24701f5db2'},
            'bin_width_ms': 20, 'unit_ids': ['source-unit-%03d' % i for i in range(65)],
            'heldout_mask': [False] * 63 + [True] * 2, 'trial_roster': rows,
            'protocol': {'protocol_id': 'generated-control-only',
                         'native_split_roles': {'train': 'train', 'val': 'eval', 'test': 'excluded'},
                         'selection_rationale': 'Generated controls, not an authentic selection policy.',
                         'condition_policy': 'report_active_and_perturbed_within_condition_null',
                         'access_policy': 'Frozen numerical control', 'resource_budget': 'Bounded generated arrays'},
            'conversion_receipt': {'nlb_commit': e.NLB_COMMIT, 'alignment_event': 'move_onset_time',
                                   'window_ms': [-100, 500], 'rate_units': 'spikes_per_bin',
                                   'mask_source': 'NWB units.heldout',
                                   'counts_sha256': hashlib.sha256(counts.tobytes()).hexdigest(),
                                   'operator_evidence': 'Generated fixture; no native qualification'}}
    return meta, counts


class MetricControls(unittest.TestCase):
    def score(self, target, prediction):
        return e.poisson_bits_per_spike(np.asarray(target, float).reshape(1, -1, 1),
                                       np.asarray(prediction, float).reshape(1, -1, 1))

    def test_independently_derived_scalar_values(self):
        cases = [([0, 2, 1, 1], [.5, 1.5, 1, 1], .2924812503605781),
                 ([0, 2], [0, 0], -28.45465781453999),
                 ([0, 2], [0, 2], .9999999992786526),
                 ([0, 2, np.nan, 1], [.5, 1.5, 999, 1], .38997500048077083)]
        for target, prediction, expected in cases:
            with self.subTest(target=target):
                self.assertAlmostEqual(self.score(target, prediction)['co_bps'], expected, places=12)

    def test_exact_zero_and_tiny_positive_are_different(self):
        zero = self.score([0, 2], [1, 0])['co_bps']
        tiny = self.score([0, 2], [1, 1e-12])['co_bps']
        self.assertLess(tiny, zero - 9)

    def test_null_is_evaluation_mean(self):
        self.assertEqual(self.score([0, 2], [1, 1])['co_bps'], 0)
        self.assertLess(self.score([0, 2], [3, 3])['co_bps'], 0)

    def test_zero_total_is_explicit_undefined(self):
        result = self.score([0, 0], [1, 2])
        self.assertEqual(result['status'], 'undefined_zero_target_spikes')
        self.assertIsNone(result['co_bps'])

    def test_reject_malformed_counts_and_rates(self):
        for target, prediction in [([0, -1], [1, 1]), ([0, .5], [1, 1]),
                                   ([0, np.inf], [1, 1]), ([0, 1], [-1, 1]),
                                   ([0, 1], [1, np.inf]), ([0, 1], [1, np.nan]),
                                   ([0, np.nan], [1, np.nan]), ([np.nan, np.nan], [1, 1])]:
            with self.subTest(target=target, prediction=prediction), self.assertRaises(ValueError):
                self.score(target, prediction)
        with self.assertRaises(ValueError):
            e.counts_array(np.array([2**64 - 1], dtype=np.uint64), 'overflow')
        with self.assertRaises(ValueError):
            e.poisson_bits_per_spike(np.ones((1, 1, 1)), np.ones((1, 2, 1)))

    def test_does_not_mutate_zero_rates(self):
        target = np.array([0, 2.]).reshape(1, 2, 1)
        prediction = np.zeros_like(target)
        e.poisson_bits_per_spike(target, prediction)
        self.assertTrue(np.all(prediction == 0))

    @unittest.skipUnless(os.environ.get('NLB_OFFICIAL_SOURCE') and importlib.util.find_spec('scipy'),
                         'optional exact pinned official source parity requires source and SciPy')
    def test_official_byte_pinned_parity(self):
        raw = Path(os.environ['NLB_OFFICIAL_SOURCE']).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
                         '05f49d3cdf7720ae68e0fb76113a9e450e9df3813c6c6837689f23a9be278476')
        tree = ast.parse(raw)
        nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                 and n.name in ('neg_log_likelihood', 'bits_per_spike')]
        self.assertEqual(len(nodes), 2)
        from scipy.special import gammaln
        scope = {'np': np, 'gammaln': gammaln, 'logger': logging.getLogger('official-control')}
        exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])),
                     'pinned-official-metric', 'exec'), scope)
        rng = np.random.default_rng(20261117)
        for _ in range(24):
            target = rng.poisson(.5, size=(4, 7, 3)).astype(float)
            prediction = rng.uniform(1e-3, 2, size=target.shape)
            target[0, 0, 0] = np.nan
            prediction[0, 1, 0] = 0
            prediction[1, 1, 1] = 1e-12
            official = scope['bits_per_spike'](prediction.copy(), target.copy())
            actual = e.poisson_bits_per_spike(target, prediction)['co_bps']
            self.assertAlmostEqual(actual, official, places=11)


class PacketControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.meta, cls.counts = complete_fixture()
        cls.query, cls.training, cls.gold = e.prepare_packet(cls.meta, cls.counts)

    def test_complete_projection_and_privacy(self):
        self.assertEqual(self.query['visible_counts'].shape, (2, 30, 63))
        self.assertEqual(self.gold['target_counts'].shape, (2, 30, 2))
        self.assertEqual(self.training['target_counts'].shape, (2, 30, 2))
        self.assertFalse({'ctr_hold_bump', 'target_counts', 'trial_roster', 'source'} & set(self.query))
        self.assertTrue(all(str(x).startswith('eval-') for x in self.query['trial_ids']))
        self.assertNotEqual(self.query['trial_ids'][0], self.meta['trial_roster'][2]['trial_id'])

    def test_condition_normalization_not_pooled_average(self):
        gold = copy.deepcopy(self.gold)
        gold['target_counts'][:] = 4
        gold['target_counts'][0, :15] = 0
        gold['target_counts'][0, 15:] = 2
        candidate = e.mean_rate_reference(self.training, self.query)
        candidate['expected_counts'][0] = 1
        candidate['expected_counts'][1] = 4
        result = e.score_submission(gold, candidate)
        self.assertEqual(result['primary_endpoints']['active']['co_bps'], 0)
        self.assertEqual(result['primary_endpoints']['perturbed']['co_bps'], 0)
        self.assertAlmostEqual(result['pooled_official_equation_diagnostic']['co_bps'], .2780719051126378, places=12)
        self.assertFalse(result['research_qualified'])
        self.assertTrue(result['retained_gates'])

    def test_submission_identity_order_units_and_private_fields(self):
        candidate = e.mean_rate_reference(self.training, self.query)
        for field, value in [('trial_ids', candidate['trial_ids'][::-1]),
                             ('heldout_unit_ids', candidate['heldout_unit_ids'][::-1]),
                             ('packet_sha256', np.asarray('b' * 64)),
                             ('prediction_units', np.asarray('Hz')),
                             ('ctr_hold_bump', np.asarray([0, 1]))]:
            bad = dict(candidate); bad[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                e.score_submission(self.gold, bad)

    def test_constant_outputs_are_valid_diagnostic_not_disqualified(self):
        result = e.score_submission(self.gold, e.mean_rate_reference(self.training, self.query))
        self.assertTrue(result['constant_prediction_diagnostic'])
        self.assertEqual(result['primary_endpoints']['active']['co_bps'], 0)

    def test_training_mean_does_not_read_query_or_eval_targets(self):
        query = copy.deepcopy(self.query); query['visible_counts'][:] = 100
        candidate = e.mean_rate_reference(self.training, query)
        self.assertTrue(np.all(candidate['expected_counts'] == 1))
        altered = copy.deepcopy(self.training); altered['target_counts'][:] = 2
        self.assertTrue(np.all(e.mean_rate_reference(altered, query)['expected_counts'] == 2))

    def assert_bad_meta(self, mutate):
        bad = copy.deepcopy(self.meta); mutate(bad)
        with self.assertRaises(ValueError):
            e.prepare_packet(bad, self.counts)

    def test_population_and_source_identity_fail_closed(self):
        for mutation in [lambda m: m['trial_roster'].pop(), lambda m: m['unit_ids'].pop(),
                         lambda m: m['source'].update(subject='Other'),
                         lambda m: m['trial_roster'][2].update(ctr_hold_bump=2),
                         lambda m: m['trial_roster'][3].update(ctr_hold_bump=0),
                         lambda m: m['trial_roster'][4].update(exclusion_reason=None),
                         lambda m: m['trial_roster'][2].update(native_split='train'),
                         lambda m: m['conversion_receipt'].update(counts_sha256='0' * 64)]:
            self.assert_bad_meta(mutation)

    def test_fixed_unit_mask_changes_bound_identity(self):
        changed = copy.deepcopy(self.meta)
        changed['heldout_mask'][0], changed['heldout_mask'][-1] = True, False
        query, _, _ = e.prepare_packet(changed, self.counts)
        self.assertNotEqual(str(query['packet_sha256']), str(self.query['packet_sha256']))

    def test_whole_block_and_time_overlap_rejected(self):
        self.assert_bad_meta(lambda m: m['trial_roster'][2].update(block_id='block-0000'))
        self.assert_bad_meta(lambda m: m['trial_roster'][2].update(window_start_seconds=1.5, window_stop_seconds=2.1))

    def test_digest_changes_with_payload(self):
        changed = self.counts.copy(); changed[4, 0, 0] += 1
        with self.assertRaises(ValueError):
            e.prepare_packet(self.meta, changed)
        meta = copy.deepcopy(self.meta)
        meta['conversion_receipt']['counts_sha256'] = hashlib.sha256(changed.tobytes()).hexdigest()
        query, _, _ = e.prepare_packet(meta, changed)
        self.assertNotEqual(str(query['packet_sha256']), str(self.query['packet_sha256']))

    def test_missingness_cannot_remove_unit_condition(self):
        gold = copy.deepcopy(self.gold); gold['target_counts'][0, :, 0] = np.nan
        with self.assertRaises(ValueError):
            e.score_submission(gold, e.mean_rate_reference(self.training, self.query))

    @unittest.skipUnless(importlib.util.find_spec('sklearn') and importlib.util.find_spec('scipy'),
                         'optional smoothing controls require scikit-learn and SciPy')
    def test_smoothing_source_recipe_constant_target_control(self):
        training = copy.deepcopy(self.training); training['target_counts'][:] = 2
        query = copy.deepcopy(self.query); query['visible_counts'][:] = 10
        result, audit = e.smoothing_reference(training, query)
        np.testing.assert_allclose(result['expected_counts'], 2, rtol=1e-12)
        self.assertEqual(audit['kernel_length_bins'], 9)
        self.assertEqual(audit['kernel_std_bins'], 1)
        self.assertTrue(audit['training_only'])
        self.assertFalse(audit['authentic_reference_qualified'])

    @unittest.skipUnless(importlib.util.find_spec('sklearn') and importlib.util.find_spec('scipy'),
                         'optional smoothing controls require scikit-learn and SciPy')
    def test_smoothing_rejects_unsupported_missingness_and_zero_training_unit(self):
        training = copy.deepcopy(self.training); training['visible_counts'][0, 0, 0] = np.nan
        with self.assertRaises(ValueError):
            e.smoothing_reference(training, self.query)
        training = copy.deepcopy(self.training); training['target_counts'][:, :, 0] = 0
        with self.assertRaises(ValueError):
            e.smoothing_reference(training, self.query)

    def test_cli_round_trip_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / 'metadata.json').write_text(json.dumps(self.meta))
            np.savez_compressed(p / 'source.npz', full_counts=self.counts)
            args = ['prepare', '--metadata', str(p / 'metadata.json'), '--source-counts', str(p / 'source.npz'),
                    '--output-directory', str(p / 'packet')]
            e.main(args)
            with self.assertRaises(FileExistsError):
                e.main(args)
            e.main(['mean-reference', '--training', str(p / 'packet/public_training.npz'),
                    '--query', str(p / 'packet/public_query.npz'), '--output', str(p / 'submission.npz')])
            e.main(['score', '--gold', str(p / 'packet/private_gold.npz'), '--submission', str(p / 'submission.npz'),
                    '--output', str(p / 'result.json')])
            result = json.loads((p / 'result.json').read_text())
            self.assertEqual(result['primary_endpoints']['active']['co_bps'], 0)
            receipt = json.loads((p / 'packet/private_receipt.json').read_text())
            self.assertEqual(len(receipt['files_sha256']), 4)


class ArchiveControls(unittest.TestCase):
    def test_reject_object_arrays(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'object.npz'
            np.savez(path, attack=np.asarray([{'x': 1}], object))
            with self.assertRaises(ValueError):
                e.load_npz(path)

    def test_reject_declared_allocation_bomb(self):
        header = io.BytesIO()
        np.lib.format.write_array_header_1_0(header, {'descr': '<f8', 'fortran_order': False, 'shape': (2**40,)})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'huge.npz'
            with zipfile.ZipFile(path, 'w') as z:
                z.writestr('attack.npy', header.getvalue())
            with self.assertRaises(ValueError):
                e.load_npz(path)


if __name__ == '__main__':
    unittest.main()
