"""Generated arithmetic regressions only; no original data or native execution."""
from copy import deepcopy
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('_find025_scale_evaluator', HERE / 'find025_evaluator.py')
e = importlib.util.module_from_spec(spec)
exec(compile((HERE / 'find025_evaluator.py').read_bytes(), str(HERE / 'find025_evaluator.py'), 'exec'), e.__dict__)
m, c = e.m, e.c
fixture_path = HERE.parent / 'submission-comparison' / 'invented_fixture.py'
fixture_spec = importlib.util.spec_from_file_location('_find025_scale_invented_fixture', fixture_path)
fixture_module = importlib.util.module_from_spec(fixture_spec)
_missing_contract = object()
_previous_contract = sys.modules.get('find025_contract', _missing_contract)
try:
    # The preserved fixture uses this import name; bind only its authenticated
    # evaluator contract for the duration of this uniquely named path import.
    sys.modules['find025_contract'] = c
    exec(compile(fixture_path.read_bytes(), str(fixture_path), 'exec'), fixture_module.__dict__)
finally:
    if _previous_contract is _missing_contract:
        sys.modules.pop('find025_contract', None)
    else:
        sys.modules['find025_contract'] = _previous_contract
fixture = fixture_module.fixture


def panel(scale):
    plan, submissions, _ = fixture('protected_improvement')
    bundle = {'schema': 'find025_operands_v1', 'plan_sha256': c.digest(plan), 'cases': []}
    payloads = {}
    rows = ['INVENTED:a', 'INVENTED:b', 'INVENTED:c']
    for case in plan['cases']:
        movement = case['obligation'].startswith('movement_')
        if movement:
            bundle['cases'].append({'case_id': case['case_id'], 'identity': deepcopy(case['identity']),
                'row_ids': rows, 'target_values': [0, scale, 2 * scale], 'times': None,
                'delay_onset': None, 'representation': 'assigned_rows',
                'preparation_id': 'INVENTED:' + case['panel_id']})
        for submission in submissions:
            record = next(r for r in submission['records'] if r['case_id'] == case['case_id'])
            body = json.dumps({'schema': 'find025_prediction_vector_v1', 'row_ids': rows,
                'values': [0, 2 * scale, 4 * scale]}, separators=(',', ':'), allow_nan=False).encode()
            descriptor = record['artifacts'][0]
            descriptor.update(logical_id='INVENTED:' + case['panel_id'], sha256=sha256(body).hexdigest())
            payloads[e.payload_key(submission['run_id'], descriptor)] = body
    return plan, submissions, payloads, bundle


class ScaleControls(unittest.TestCase):
    def test_correlation_rescales_small_and_large_valid_vectors(self):
        for scale in (1e-200, 1.0, 1e100):
            with self.subTest(scale=scale):
                self.assertAlmostEqual(m.squared_pearson_correlation(
                    [-scale, 0, scale], [-scale, scale, 0]), .25, places=14)
                self.assertAlmostEqual(m.squared_pearson_correlation(
                    [0, scale, 2 * scale], [0, scale, 2 * scale]), 1., places=14)

    def test_signed_ve_rescales_and_retains_negative_scores(self):
        for scale in (1e-300, 1e-200, 1.0, 1e99):
            with self.subTest(scale=scale):
                self.assertAlmostEqual(m.signed_variance_explained(
                    [0, scale, 2 * scale], [0, 2 * scale, 4 * scale]), -1.5, places=14)
                self.assertEqual(m.signed_variance_explained(
                    [0, scale, 2 * scale], [0, scale, 2 * scale]), 1.)

    def test_constancy_and_malformed_inputs_still_refused(self):
        with self.assertRaises(m.UndefinedMetric):
            m.signed_variance_explained([1e-200] * 3, [0, 1e-200, 2e-200])
        with self.assertRaises(m.UndefinedMetric):
            m.squared_pearson_correlation([0, 1e-200, 2e-200], [1e-200] * 3)
        for observed, predicted in [([0, 1], [1]), ([0, True], [0, 1]), ([0, float('nan')], [0, 1])]:
            with self.subTest(observed=observed):
                with self.assertRaises(ValueError):
                    m.signed_variance_explained(observed, predicted)
        self.assertEqual(m.binary_accuracy([-1, 1], [-1, -1]), .5)
        self.assertEqual(m.first_strict_90pct_latency([-1, 0], [0, 1], 0), 0)

    def test_artifact_batch_preserves_pairing_with_small_operands(self):
        result = e.evaluate_submissions(*panel(1e-200))
        self.assertEqual(result['schema'], 'find025_artifact_evaluation_v1')
        self.assertEqual(len(result['case_audit']), 72)
        self.assertEqual(len(result['scores']), 16)
        for record in result['scores']:
            self.assertEqual(record['status'], 'valid')
            expected = -1.5 if record['identity']['metric_id'] == c.SIGNED else 1.
            self.assertAlmostEqual(record['value'], expected, places=14)
        self.assertFalse(result['comparison']['scientifically_qualified'])
        self.assertIsNone(result['comparison']['paper_pass'])
        self.assertFalse(result['support_contract']['paper_qualification'])

    def test_artifact_batch_keeps_failed_predictions_and_full_denominator(self):
        data = panel(1e-200)
        plan, submissions, payloads, bundle = data
        submission = submissions[0]
        chosen = [r for r in submission['records'] if r['case_id'].startswith('movement_choice_prediction:')]
        old = e.payload_key(submission['run_id'], chosen[0]['artifacts'][0])
        invalid = json.loads(payloads.pop(old))
        invalid['values'][0] = True
        body = json.dumps(invalid, separators=(',', ':')).encode()
        for record in chosen:
            record['artifacts'][0]['sha256'] = sha256(body).hexdigest()
        payloads[e.payload_key(submission['run_id'], chosen[0]['artifacts'][0])] = body
        result = e.evaluate_submissions(*data)
        self.assertEqual(len(result['case_audit']), 72)
        bad = [r for r in result['scores'] if r['run_id'] == submission['run_id'] and
               r['case_id'].startswith('movement_choice_prediction:')]
        self.assertEqual(len(bad), 2)
        self.assertEqual({r['status'] for r in bad}, {'failed'})
        self.assertEqual(result['comparison']['denominators'][submission['run_id']]['decoding_delay']['assigned'], 12)


if __name__ == '__main__':
    unittest.main()
