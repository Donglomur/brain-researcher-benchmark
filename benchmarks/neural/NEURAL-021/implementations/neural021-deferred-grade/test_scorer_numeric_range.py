"""Full92 generated trajectory controls; no authentic targets or native execution."""
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import unittest


HERE = Path(__file__).resolve().parent


def load(path):
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(path.stem, loader=None))
    module.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), 'exec'), module.__dict__)
    return module


scorer = load(HERE / 'science/private/scorer.py')
interface = load(HERE / 'science/public/interface.py')


def fixture(scale=2.0, prediction=1.0, constant_condition=None):
    cases = dict(schema='neural021_public_cases_v1', task_id='NEURAL-021', time_bins=30,
                 queries=[dict(trial_id='q%04d' % i, condition='active' if i < 52 else 'passive')
                          for i in range(92)])
    cases_bytes = json.dumps(cases, allow_nan=False).encode()
    digest = hashlib.sha256(cases_bytes).hexdigest()
    targets = []
    predictions = []
    for row in cases['queries']:
        values = [[0.0 if row['condition'] == constant_condition else
                   (scale if t % 2 else -scale)] * 2 for t in range(30)]
        targets.append(values)
        predictions.append(dict(trial_id=row['trial_id'],
                                velocity_m_s=[[prediction, prediction] for _ in range(30)]))
    gold = dict(schema='neural021_private_targets_v1', cases_sha256=digest,
                query_ids=[row['trial_id'] for row in cases['queries']], velocity_m_s=targets)
    submission = dict(schema='neural021_trajectory_predictions_v1', task_id='NEURAL-021',
                      cases_sha256=digest, predictions=predictions)
    return json.dumps(submission, allow_nan=False).encode(), cases_bytes, gold


def evaluate(*args, **kwargs):
    submission, cases, gold = fixture(*args, **kwargs)
    return scorer.score(submission, cases, lambda: gold, interface)


class NumericRange(unittest.TestCase):
    def test_representable_mean_survives_overflowing_condition_sum(self):
        report = evaluate(scale=1e-154)
        values = [report['conditions'][name]['r2_variance_weighted'] for name in ('active', 'passive')]
        self.assertTrue(all(math.isfinite(value) and value < -9e307 for value in values))
        with self.assertRaises(OverflowError):
            math.fsum(values)
        self.assertTrue(math.isfinite(report['mean_condition_r2']))
        self.assertEqual(report['mean_condition_r2'], math.fsum(value / 2 for value in values))
        self.assertEqual([report['conditions'][name]['trials'] for name in ('active', 'passive')], [52, 40])
        for condition in report['conditions'].values():
            self.assertEqual(condition['r2_status'], 'defined')
            self.assertTrue(all(math.isfinite(value) for value in condition['axis_r2']))
            self.assertTrue(math.isfinite(condition['squared_euclidean_loss_m2_s2']))

    def test_ordinary_finite_mean_keeps_previous_arithmetic(self):
        for scale, prediction in ((2.0, 1.0), (1.0, 0.0), (3.0, 7.0)):
            with self.subTest(scale=scale, prediction=prediction):
                report = evaluate(scale=scale, prediction=prediction)
                values = [report['conditions'][name]['r2_variance_weighted'] for name in ('active', 'passive')]
                self.assertEqual(report['mean_condition_r2'], math.fsum(values) / 2)
        self.assertLess(evaluate()['mean_condition_r2'], 0)

    def test_constant_condition_retains_null_mean_and_loss(self):
        report = evaluate(constant_condition='active')
        self.assertIsNone(report['mean_condition_r2'])
        self.assertEqual(report['conditions']['active']['r2_status'], 'undefined_constant_target')
        self.assertEqual(report['conditions']['active']['squared_euclidean_loss_m2_s2'], 2.0)
        self.assertIsNotNone(report['conditions']['passive']['r2_variance_weighted'])

    def test_unrepresentable_condition_scores_still_remain_null(self):
        report = evaluate(scale=1e-160)
        self.assertIsNone(report['mean_condition_r2'])
        for condition in report['conditions'].values():
            self.assertEqual(condition['r2_status'], 'undefined_numeric_range')
            self.assertIsNone(condition['r2_variance_weighted'])
            self.assertTrue(math.isfinite(condition['squared_euclidean_loss_m2_s2']))

    def test_missing_output_is_rejected_before_target_callback(self):
        submission, cases, _ = fixture(scale=1e-154)
        value = json.loads(submission)
        value['predictions'].pop()
        def forbidden_loader():
            raise AssertionError('private loader must not be called')
        with self.assertRaises(ValueError):
            scorer.score(json.dumps(value).encode(), cases, forbidden_loader, interface)


if __name__ == '__main__':
    unittest.main()
