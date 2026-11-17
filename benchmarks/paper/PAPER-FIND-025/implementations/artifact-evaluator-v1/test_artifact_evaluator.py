"""Invented software controls; no source data or empirical prediction is opened."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'submission-comparison'))
import find025_evaluator as e
from invented_fixture import fixture
c = e.c


def encode(value):
    return json.dumps(value, separators=(',', ':'), allow_nan=False).encode()


def setup(mode='code_reconstruction'):
    plan, submissions, _ = fixture(mode)
    bundle = {'schema': 'find025_operands_v1', 'plan_sha256': c.digest(plan), 'cases': []}
    payloads = {}
    for case in plan['cases']:
        metric = case['identity']['metric_id']
        if metric in e.SUPPORTED:
            operand = {'case_id': case['case_id'], 'identity': deepcopy(case['identity']),
                       'row_ids': ['trial:a', 'trial:b', 'trial:c'],
                       'target_values': [-1, 1, 1] if metric == c.ACCURACY else [0, 1, 2],
                       'times': None, 'delay_onset': None,
                       'representation': 'delay_trialmeans' if metric == c.CORR else 'assigned_rows',
                       'preparation_id': 'INVENTED:prepared:' + case['panel_id']}
            if metric == c.LATENCY:
                operand.update(target_values=None, times=[-0.5, -0.25, 0], delay_onset=0.1,
                               representation='oriented_smoothed_prego_trace')
            bundle['cases'].append(operand)
        for submission in submissions:
            row = next(r for r in submission['records'] if r['case_id'] == case['case_id'])
            values = [-1, -1, 1] if metric == c.ACCURACY else [0, 0.9, 1] if metric == c.LATENCY else [10, 11, 12]
            body = encode({'schema': 'find025_prediction_vector_v1',
                           'row_ids': ['trial:a', 'trial:b', 'trial:c'], 'values': values})
            descriptor = row['artifacts'][0]
            descriptor.update(logical_id='INVENTED:' + case['panel_id'], sha256=sha256(body).hexdigest())
            payloads[e.payload_key(submission['run_id'], descriptor)] = body
    return plan, submissions, payloads, bundle


def score(result, name, run='paper_data/candidate'):
    return next(r for r in result['scores'] if r['run_id'] == run and r['case_id'] == name)


def detail(result, name, run='paper_data/candidate'):
    return next(r for r in result['case_audit'] if r['run_id'] == run and r['case_id'] == name)


def replace_body(data, name, body, run=0):
    plan, submissions, payloads, bundle = data
    row = next(r for r in submissions[run]['records'] if r['case_id'] == name)
    artifact = row['artifacts'][0]
    old = e.payload_key(submissions[run]['run_id'], artifact)
    payloads.pop(old)
    artifact['sha256'] = sha256(body).hexdigest()
    payloads[e.payload_key(submissions[run]['run_id'], artifact)] = body


class ArtifactControls(unittest.TestCase):
    def test_full_assigned_panel_routes_actual_arithmetic(self):
        data = setup()
        result = e.evaluate_submissions(*data)
        self.assertEqual(len(result['case_audit']), 32)
        self.assertEqual(len(result['scores']), 20)
        self.assertEqual(score(result, 'choice_neural_decoding:0')['value'], 2/3)
        self.assertAlmostEqual(score(result, 'movement_choice_prediction:0')['value'], 1, places=14)
        self.assertEqual(score(result, 'fixed_motion_onset:0')['value'], -0.1)
        self.assertEqual(detail(result, 'normalized_null_variance:0')['status'], 'unsupported')
        self.assertEqual(detail(result, 'subspaces_and_projectors:0')['status'], 'artifact_authenticated')
        self.assertFalse(result['comparison']['scientifically_qualified'])
        self.assertIsNone(result['comparison']['paper_pass'])

    def test_common_vector_preserves_negative_ve_and_high_corr(self):
        result = e.evaluate_submissions(*setup('protected_improvement'))
        self.assertEqual(score(result, 'movement_choice_prediction:0')['value'], -149)
        self.assertAlmostEqual(score(result, 'movement_choice_prediction:1')['value'], 1, places=14)
        a, b = [detail(result, 'movement_choice_prediction:' + str(n)) for n in (0, 1)]
        self.assertEqual(a['ordered_rows_sha256'], b['ordered_rows_sha256'])
        self.assertEqual(len(result['case_audit']), 72)

    def test_original_corr_requires_operator_trialmean_reduction(self):
        data = setup()
        next(r for r in data[3]['cases'] if r['case_id'].startswith('movement_'))['representation'] = 'assigned_rows'
        with self.assertRaisesRegex(e.OperandError, 'delay_trialmeans'):
            e.evaluate_submissions(*data)

    def test_common_target_cannot_differ_between_primary_and_secondary(self):
        data = setup('protected_improvement')
        next(r for r in data[3]['cases'] if r['case_id'] == 'movement_choice_prediction:1')['target_values'][0] = 2
        with self.assertRaisesRegex(e.OperandError, 'vectors differ'):
            e.evaluate_submissions(*data)

    def test_primary_and_secondary_require_both_operator_operands(self):
        data = setup('protected_improvement')
        data[3]['cases'] = [r for r in data[3]['cases'] if r['case_id'] != 'movement_choice_prediction:1']
        with self.assertRaisesRegex(e.OperandError, 'required together'):
            e.evaluate_submissions(*data)

    def test_missing_case_is_retained_in_denominator(self):
        data = setup()
        removed = data[1][0]['records'].pop(6)
        data[2].pop(e.payload_key(data[1][0]['run_id'], removed['artifacts'][0]))
        result = e.evaluate_submissions(*data)
        self.assertEqual(detail(result, removed['case_id'])['status'], 'missing')
        self.assertEqual(result['comparison']['denominators']['paper_data/candidate']['decoding_delay']['assigned'], 10)

    def test_failed_and_abstained_records_are_retained(self):
        data = setup()
        for status, row in zip(('failed', 'abstained'), data[1][0]['records'][6:8]):
            row.update(status=status, reason='INVENTED:failure')
        result = e.evaluate_submissions(*data)
        self.assertEqual(detail(result, 'choice_neural_decoding:0')['status'], 'failed')
        self.assertEqual(detail(result, 'choice_kinematic_decoding:0')['status'], 'abstained')

    def test_tampered_payload_cannot_supply_score(self):
        data = setup()
        artifact = data[1][0]['records'][6]['artifacts'][0]
        data[2][e.payload_key(data[1][0]['run_id'], artifact)] += b' '
        result = e.evaluate_submissions(*data)
        self.assertEqual(detail(result, 'choice_neural_decoding:0')['reason'], 'payload_sha256_mismatch')

    def test_strict_payload_failures_do_not_reduce_case_denominator(self):
        base = {'schema': 'find025_prediction_vector_v1', 'row_ids': ['trial:a', 'trial:b', 'trial:c'], 'values': [-1, 1, 1]}
        for mutation in ('target', 'reorder', 'duplicate', 'missing', 'extra', 'bool', 'class', 'infinite'):
            with self.subTest(mutation=mutation):
                data = setup()
                payload = deepcopy(base)
                if mutation == 'target': payload['target_values'] = [-1, 1, 1]
                if mutation == 'reorder': payload['row_ids'].reverse()
                if mutation == 'duplicate': payload['row_ids'][1] = 'trial:a'
                if mutation == 'missing': payload['row_ids'].pop(); payload['values'].pop()
                if mutation == 'extra': payload['row_ids'].append('trial:d'); payload['values'].append(1)
                if mutation == 'bool': payload['values'][0] = True
                if mutation == 'class': payload['values'][0] = 0
                body = encode(payload)
                if mutation == 'infinite': body = body.replace(b'[-1,1,1]', b'[NaN,1,1]')
                replace_body(data, 'choice_neural_decoding:0', body)
                result = e.evaluate_submissions(*data)
                self.assertEqual(score(result, 'choice_neural_decoding:0')['status'], 'failed')
                self.assertEqual(len(result['case_audit']), 32)

    def test_duplicate_json_key_is_rejected(self):
        data = setup()
        body = b'{"schema":"find025_prediction_vector_v1","row_ids":["trial:a","trial:b","trial:c"],"values":[-1,1,1],"values":[1,1,1]}'
        replace_body(data, 'choice_neural_decoding:0', body)
        self.assertEqual(score(e.evaluate_submissions(*data), 'choice_neural_decoding:0')['status'], 'failed')

    def test_constancy_is_undefined_and_not_zero(self):
        data = setup('protected_improvement')
        for row in data[3]['cases']:
            if row['case_id'].startswith('movement_choice_prediction'):
                row['target_values'] = [3, 3, 3]
        result = e.evaluate_submissions(*data)
        for n in (0, 1):
            row = score(result, 'movement_choice_prediction:' + str(n))
            self.assertEqual(row['status'], 'undefined')
            self.assertIsNone(row['value'])

    def test_latency_no_crossing_is_undefined(self):
        data = setup()
        replace_body(data, 'fixed_motion_onset:0', encode({'schema': 'find025_prediction_vector_v1',
                    'row_ids': ['trial:a', 'trial:b', 'trial:c'], 'values': [0, 0, 0]}))
        self.assertEqual(score(e.evaluate_submissions(*data), 'fixed_motion_onset:0')['status'], 'undefined')

    def test_operator_timestamp_and_identity_fail_before_any_scores(self):
        for mutation in ('timestamp', 'identity', 'plan'):
            with self.subTest(mutation=mutation):
                data = setup()
                if mutation == 'timestamp':
                    next(r for r in data[3]['cases'] if r['times'] is not None)['times'] = [0, 0, 1]
                elif mutation == 'identity': data[3]['cases'][0]['identity']['target_id'] = 'different'
                else: data[3]['plan_sha256'] = '0' * 64
                with self.assertRaises(e.OperandError): e.evaluate_submissions(*data)

    def test_unresolved_join_holds_every_numeric_case(self):
        data = setup()
        data[0]['joins']['cohort_animal_session_identity'] = {'status': 'unresolved', 'evidence_id': None}
        for submission in data[1]: submission['plan_sha256'] = c.digest(data[0])
        data[3]['plan_sha256'] = c.digest(data[0])
        result = e.evaluate_submissions(*data)
        self.assertEqual(result['scores'], [])
        self.assertTrue(all(r['status'] == 'held' for r in result['case_audit']))

    def test_protected_execution_gate_is_preserved(self):
        data = setup('protected_improvement')
        data[1][0]['execution_declaration']['split_realization_id'] = 'different'
        result = e.evaluate_submissions(*data)
        self.assertTrue(all(r['status'] == 'held' for r in result['case_audit'] if r['run_id'] == 'paper_data/candidate'))
        self.assertFalse(any(r['run_id'] == 'paper_data/candidate' for r in result['scores']))

    def test_paper_mode_never_promotes_arithmetic_to_reproduction(self):
        result = e.evaluate_submissions(*setup('paper_reproduction'))
        self.assertTrue(result['scores'])
        self.assertTrue(all(r['left_minus_right'] is None for r in result['comparison']['comparisons']))
        self.assertIsNone(result['comparison']['paper_pass'])

    def test_ambiguous_primary_is_held(self):
        data = setup()
        row = data[1][0]['records'][6]
        row['artifacts'].append(deepcopy(row['artifacts'][0]))
        result = e.evaluate_submissions(*data)
        self.assertEqual(detail(result, row['case_id'])['reason'], 'exactly_one_primary_prediction_required')

    def test_missing_payload_is_explicit(self):
        data = setup()
        artifact = data[1][0]['records'][6]['artifacts'][0]
        data[2].pop(e.payload_key(data[1][0]['run_id'], artifact))
        self.assertEqual(detail(e.evaluate_submissions(*data), 'choice_neural_decoding:0')['reason'], 'payload_missing')

    def test_no_target_values_or_row_ids_in_returned_audit(self):
        result = e.evaluate_submissions(*setup())
        serialized = json.dumps(result)
        self.assertNotIn('target_values', serialized)
        self.assertNotIn('trial:a', serialized)
        self.assertNotIn('/Users/', serialized)

    def test_payload_ceiling_rejects_instead_of_truncating(self):
        data = setup()
        replace_body(data, 'choice_neural_decoding:0', b' ' * (e.MAX_PAYLOAD_BYTES + 1))
        result = e.evaluate_submissions(*data)
        self.assertEqual(detail(result, 'choice_neural_decoding:0')['reason'], 'payload_byte_limit_exceeded')

    def test_unassigned_payload_is_not_silently_ignored(self):
        data = setup()
        data[2][('other', 'label_predictions', 'x', '0' * 64)] = b'{}'
        with self.assertRaisesRegex(e.OperandError, 'unassigned'):
            e.evaluate_submissions(*data)

    def test_unknown_or_duplicate_operator_case_is_rejected(self):
        data = setup()
        data[3]['cases'].append(deepcopy(data[3]['cases'][0]))
        with self.assertRaisesRegex(e.OperandError, 'duplicate'):
            e.evaluate_submissions(*data)


if __name__ == '__main__':
    unittest.main(verbosity=2)
