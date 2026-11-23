"""Generated full-panel pairing controls; no authentic data or model execution."""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(add_help=False)
parser.add_argument('--implementations-root', type=Path, default=HERE.parent)
args, remaining = parser.parse_known_args()
sys.argv = [sys.argv[0], *remaining]
spec = importlib.util.spec_from_file_location('n021_paired_compare', HERE / 'compare.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


def generated_packet(delivery):
    conditions = [0] * 52 + [1] * 40
    cases = {'schema': 'neural021_public_cases_v1', 'task_id': 'NEURAL-021', 'time_bins': 30,
             'feature_shape': [30, 6, 65], 'units': 'm/s',
             'conditions': {'0': 'active', '1': 'passive'},
             'queries': [{'trial_id': f'q{i:04d}', 'condition': delivery.CONDITIONS[condition]}
                         for i, condition in enumerate(conditions)]}
    counts = tuple(tuple((b + 2 * u) % 13 for u in range(65)) for b in range(35))
    history = delivery.expand_counts(counts)
    trajectory = [[float(t), float(2 * t)] for t in range(30)]
    training = {'spike_counts': [history] * 272, 'condition': [0, 1] * 136,
                'velocity_m_s': [trajectory] * 272}
    queries = {'spike_counts': [history] * 92, 'condition': conditions}
    packet = delivery.Packet.from_arrays(training, queries, delivery.encode(cases))
    gold = {'schema': 'neural021_private_targets_v1', 'cases_sha256': packet.cases_sha256,
            'query_ids': [row['trial_id'] for row in cases['queries']],
            'velocity_m_s': [[list(pair) for pair in trajectory] for _ in range(92)]}
    return packet, gold


def finished(delivery, packet, mode, offset, calibrations):
    session = delivery.Session(packet, mode)
    for index in calibrations:
        session.calibration(index)
    for index in reversed(range(92)):
        key = f'q{index:04d}'
        session.view(key)
        if mode == 'typed_viewer' and index == 91:
            session.view(key, unit_start=60, unit_stop=65, bin_start=29, bin_stop=35)
        session.answer(key, [[float(t) + offset, float(2 * t) + offset] for t in range(30)])
    submission, receipt = session.finish()
    return {'submission': submission, 'receipt': receipt}


class PairedObservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.grade, cls.sources = c.load_grade(args.implementations_root)
        cls.delivery = cls.sources['delivery']
        cls.packet, cls.gold = generated_packet(cls.delivery)
        cls.arms = {
            'direct_observation': finished(cls.delivery, cls.packet, 'direct_observation', 100., [0, 271]),
            'typed_viewer': finished(cls.delivery, cls.packet, 'typed_viewer', 1., [0]),
        }

    def evaluate(self, arms=None, gold=None, sources=None):
        calls = []
        def targets():
            calls.append(True)
            return self.gold if gold is None else gold
        result = c.compare(self.grade, sources or self.sources, self.packet, arms or self.arms, targets)
        self.assertEqual(calls, [True])
        return result

    def refused_before_targets(self, arms):
        calls = []
        with self.assertRaises((ValueError, TypeError)):
            c.compare(self.grade, self.sources, self.packet, arms, lambda: calls.append(True))
        self.assertEqual(calls, [])

    def test_full_panel_analytic_r2_loss_differences_and_negative_score(self):
        result = self.evaluate()
        denominator = 5. * (30. * 30. - 1.) / 12.
        expected_direct = 1. - 2. * 100. ** 2 / denominator
        expected_viewer = 1. - 2. / denominator
        self.assertLess(result['scores']['direct_observation']['mean_condition_r2'], 0.)
        for mode, value in [('direct_observation', expected_direct), ('typed_viewer', expected_viewer)]:
            self.assertAlmostEqual(result['scores'][mode]['mean_condition_r2'], value, places=12)
        self.assertAlmostEqual(result['viewer_minus_direct']['mean_condition_r2'],
                               expected_viewer - expected_direct, places=12)
        for condition, count in [('active', 52), ('passive', 40)]:
            row = result['viewer_minus_direct']['conditions'][condition]
            self.assertEqual((row['trials'], row['trajectory_rows']), (count, count * 30))
            self.assertEqual(row['squared_euclidean_loss_m2_s2'], 2. - 2. * 100. ** 2)
        self.assertEqual(result['queries_per_arm'], 92)
        self.assertFalse(result['runtime_qualified'])
        self.assertFalse(result['scientific_qualified'])
        self.assertIsNone(result['binary_success_threshold'])

    def test_exposure_differences_remain_visible(self):
        result = self.evaluate()
        a, b = (result['exposures'][mode] for mode in c.MODES)
        self.assertEqual(a['calibration_indices_in_view_order'], [0, 271])
        self.assertEqual(b['calibration_indices_in_view_order'], [0])
        self.assertEqual((a['query_views'], b['query_views']), (92, 93))
        self.assertEqual((a['cropped_query_views'], b['cropped_query_views']), (0, 1))
        self.assertFalse(result['same_calibration_view_sequence'])

    def test_bad_second_arm_refused_before_target(self):
        arms = copy.deepcopy(self.arms)
        submission = json.loads(arms['typed_viewer']['submission'])
        submission['predictions'].pop()
        arms['typed_viewer']['submission'] = self.grade.encode(submission)
        self.refused_before_targets(arms)

    def test_swapped_modes_and_missing_or_extra_arms_refused(self):
        self.refused_before_targets({mode: self.arms[other]
                                     for mode, other in zip(c.MODES, reversed(c.MODES))})
        self.refused_before_targets({'direct_observation': self.arms['direct_observation']})
        self.refused_before_targets(dict(self.arms, unsupported=self.arms['typed_viewer']))

    def test_undefined_constant_targets_keep_null_r2_and_loss_difference(self):
        gold = copy.deepcopy(self.gold)
        gold['velocity_m_s'] = [[[0., 0.] for _ in range(30)] for _ in range(92)]
        result = self.evaluate(gold=gold)
        self.assertIsNone(result['viewer_minus_direct']['mean_condition_r2'])
        for row in result['viewer_minus_direct']['conditions'].values():
            self.assertIsNone(row['r2_variance_weighted'])
            self.assertEqual(row['axis_r2'], [None, None])
            self.assertLess(row['squared_euclidean_loss_m2_s2'], 0.)

    def test_one_target_capture_provides_fresh_same_generation_to_both_scores(self):
        original = self.sources['scorer'].score
        seen = []
        def spy(submission, cases, targets, interface):
            gold = targets()
            seen.append(copy.deepcopy(gold))
            result = original(submission, cases, lambda: gold, interface)
            gold['velocity_m_s'][0][0][0] = 999.
            return result
        sources = dict(self.sources, scorer=types.SimpleNamespace(score=spy))
        result = self.evaluate(sources=sources)
        self.assertEqual(len(seen), 2)
        self.assertEqual(seen[0], seen[1])
        self.assertEqual(seen[0], self.gold)
        self.assertEqual(result['private_target_callbacks'], 1)

    def test_target_callback_cannot_replace_accepted_arm_bytes(self):
        arms = copy.deepcopy(self.arms)
        def targets():
            arms['typed_viewer'].update(self.arms['direct_observation'])
            return self.gold
        result = c.compare(self.grade, self.sources, self.packet, arms, targets)
        expected = 1. - 2. / (5. * (30. * 30. - 1.) / 12.)
        self.assertAlmostEqual(result['scores']['typed_viewer']['mean_condition_r2'], expected, places=12)
        self.assertEqual(result['exposures']['typed_viewer']['calibration_indices_in_view_order'], [0])
        self.assertEqual(result['replays']['typed_viewer']['submission'],
                         self.grade.pin(self.arms['typed_viewer']['submission']))

    def test_invalid_target_produces_no_partial_comparison(self):
        gold = copy.deepcopy(self.gold)
        gold['query_ids'][-1] = 'q9999'
        with self.assertRaisesRegex(ValueError, 'private target/public roster'):
            self.evaluate(gold=gold)

    def test_operator_refuses_target_alias_before_operand_capture(self):
        with tempfile.TemporaryDirectory(prefix='n021-generated-pair-paths-') as name:
            root = Path(name).resolve()
            public = root / 'public'
            public.mkdir()
            target = root / 'target.json'
            descriptors = {mode: {
                'submission': {'path': root / f'{mode}.json', 'pin': {}},
                'receipt': {'path': root / f'{mode}-receipt.json', 'pin': {}}}
                for mode in c.MODES}
            descriptors['typed_viewer']['receipt']['path'] = target
            with patch.object(c, 'load_grade', return_value=(self.grade, self.sources)), \
                    patch.object(self.grade, 'capture', side_effect=AssertionError('must refuse first')):
                with self.assertRaisesRegex(ValueError, 'separate arm artifacts'):
                    c.operator_compare(public, descriptors, target, root / 'output.json')
            self.assertFalse((root / 'output.json').exists())


if __name__ == '__main__':
    unittest.main()
