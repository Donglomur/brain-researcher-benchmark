"""Invented complete nominal populations; no authentic participant or target."""
import copy
import hashlib
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import scorer as s

PROTOCOL = 'a' * 64
REPRESENTATION = 'b' * 64


def fixture():
    people, rows = [], []
    for exp, count in enumerate(s.COUNTS, 1):
        for pi in range(count):
            pid = f'invented_e{exp}_p{pi}'
            trials = [{'query_id': pid + '_excluded', 'chronology': 0, 'eligible': False,
                       'rating': None, 'exclusion_reason': 'invented source exclusion'}]
            for i in range(1, 5):
                qid = f'{pid}_t{i}'
                trials.append({'query_id': qid, 'chronology': i, 'eligible': True,
                               'rating': 9.5 if i <= 2 else 0.0, 'exclusion_reason': None})
                if i > 2:
                    rows.append({'query_id': qid, 'median': 0.0})
            people.append({'experiment': exp, 'person_id': pid, 'trials': trials})
    pred = {'schema': 'lep-predictions-v1', 'task_id': s.TASK_ID,
            'protocol_sha256': PROTOCOL, 'representation_sha256': REPRESENTATION,
            'predictions': rows}
    targets = {'schema': 'lep-targets-v1', 'task_id': s.TASK_ID,
               'protocol_sha256': PROTOCOL, 'representation_sha256': REPRESENTATION,
               'inventory_receipt_sha256': 'c' * 64, 'producer_receipt_sha256': 'd' * 64,
               'people': people}
    ref = {'schema': 'lep-comparator-v1', 'reference_id': 'invented_context_reference',
           'information': 'energy_context_only', 'selection_receipt_sha256': 'e' * 64,
           'prediction': copy.deepcopy(pred)}
    for row in ref['prediction']['predictions']:
        row['median'] = 2.0
    return pred, targets, ref


def raw(doc):
    return json.dumps(doc, separators=(',', ':')).encode()


class MetricControls(unittest.TestCase):
    def setUp(self):
        self.p, self.t, self.r = fixture()

    def grade(self, payload=None):
        return s.grade(raw(self.p) if payload is None else payload, lambda: (self.t, self.r),
                       protocol_sha256=PROTOCOL, representation_sha256=REPRESENTATION)

    def test_complete_support_and_calibration(self):
        out = self.grade()
        self.assertEqual(out['candidate_mae'], 0)
        self.assertEqual(out['reference_mae'], 2)
        self.assertEqual(out['paired_mae_reduction'], 2)
        self.assertEqual(out['population'], {'experiments': 9, 'nominal_people': 678,
                         'source_trial_count': 3390, 'excluded_trial_count': 678,
                         'calibration_trial_count': 1356, 'scored_trial_denominator': 1356})
        self.assertTrue(out['output_contract_passed'])
        self.assertEqual(out['people'][0]['calibration_ids'],
                         ['invented_e1_p0_t1', 'invented_e1_p0_t2'])

    def test_experiment_macro_not_person_weighted(self):
        for row in self.p['predictions']:
            row['median'] = int(row['query_id'].split('_')[1][1:]) - 1
        out = self.grade()
        self.assertEqual(out['candidate_mae'], 4)
        self.assertAlmostEqual(out['candidate_person_macro_mae'],
                               sum(i * n for i, n in enumerate(s.COUNTS)) / 678)
        self.assertNotEqual(out['candidate_mae'], out['candidate_person_macro_mae'])
        self.assertEqual(out['paired_mae_reduction'], -2)

    def test_person_macro_not_trial_weighted(self):
        person = self.t['people'][0]
        for i in range(5, 9):
            qid = f'invented_extra_{i}'
            person['trials'].append({'query_id': qid, 'chronology': i, 'eligible': True,
                                      'rating': 0, 'exclusion_reason': None})
            self.p['predictions'].append({'query_id': qid, 'median': 10})
            self.r['prediction']['predictions'].append({'query_id': qid, 'median': 2})
        for row in self.p['predictions'][:2]: row['median'] = 10
        out = self.grade()
        self.assertAlmostEqual(out['candidate_mae'], 10 / 26 / 9)
        self.assertEqual(out['people'][0]['scored_denominator'], 6)
        self.assertEqual(out['population']['scored_trial_denominator'], 1360)

    def test_decimal_and_zero_intensity_preserved(self):
        self.t['people'][0]['trials'][3]['rating'] = 2.25
        self.p['predictions'][0]['median'] = 2.75
        out = self.grade()
        self.assertEqual(out['people'][0]['candidate_mae'], 0.25)
        self.assertAlmostEqual(out['candidate_mae'], 0.25 / 26 / 9)

    def test_missing_duplicate_malformed_penalties_do_not_shrink_denominator(self):
        self.p['predictions'].pop(0)
        self.p['predictions'].append(copy.deepcopy(self.p['predictions'][0]))
        self.p['predictions'][1]['median'] = 11
        self.p['predictions'][2]['median'] = True
        out = self.grade()
        self.assertEqual(out['penalty_counts'], {'missing': 1, 'duplicate': 1, 'malformed': 2})
        self.assertEqual(out['people'][0]['candidate_mae'], 10)
        self.assertEqual(out['people'][1]['candidate_mae'], 10)
        self.assertAlmostEqual(out['candidate_mae'], 20 / 26 / 9)
        self.assertEqual(out['population']['scored_trial_denominator'], 1356)
        self.assertFalse(out['output_contract_passed'])

    def test_nonfinite_and_wrong_type_per_record(self):
        for bad in (None, 'NaN', -1, math.inf, 1e308):
            # 1e400 is valid JSON syntax with a nonfinite parsed float.
            payload = raw(self.p).replace(b'"median":0.0', b'"median":1e400', 1) if bad == math.inf else None
            if payload is None: self.p['predictions'][0]['median'] = bad
            out = self.grade(payload)
            self.assertEqual(out['penalty_counts']['malformed'], 1)
            self.assertEqual(out['people'][0]['candidate_mae'], 5)
            self.p['predictions'][0]['median'] = 0.0

    def test_invalid_whole_envelope_penalty_and_fixed_policy(self):
        for payload in (b'not JSON', b'{"a":1,"a":2}', b'{"value":NaN}'):
            out = self.grade(payload)
            self.assertEqual(out['candidate_mae'], 10)
            self.assertEqual(out['penalty_counts']['missing'], 1356)
            self.assertFalse(out['admission']['envelope_valid'])
        self.p['representation_sha256'] = 'f' * 64
        self.assertEqual(self.grade()['candidate_mae'], 10)

    def test_unknown_and_unassignable_extras_cannot_enter_metric(self):
        self.p['predictions'].extend([{'query_id': 'not_a_query', 'median': 10},
                                      {'query_id': '/private/answer', 'median': 0}, 7])
        out = self.grade()
        self.assertEqual(out['candidate_mae'], 0)
        self.assertFalse(out['output_contract_passed'])
        self.assertEqual(out['unknown_prediction_ids'], ['not_a_query'])
        self.assertEqual(out['admission']['unassignable_records'], 2)
        self.assertEqual(out['population']['scored_trial_denominator'], 1356)

    def test_rank_ties_constants_and_no_valid_only_rank(self):
        rho, why = s.rank_correlation([0, 0, 2, 3], [1, 1, 4, 5])
        self.assertAlmostEqual(rho, 1); self.assertIsNone(why)
        self.assertEqual(s.rank_correlation([1, 1], [1, 2])[1], 'constant_prediction_or_target')
        self.assertEqual(s.rank_correlation([1], [1])[1], 'fewer_than_two_scored_trials')
        self.p['predictions'].pop(0)
        out = self.grade()
        self.assertEqual(out['people'][0]['rank_undefined_reason'],
                         'invalid_predictions_full_trial_support_required')

    def test_quantile_order_and_conditional_coverage_denominators(self):
        self.p['predictions'][0].update(q10=0, q90=1)
        out = self.grade()
        interval = out['people'][0]['interval_diagnostic']
        self.assertEqual(interval['conditional_coverage'], 1)
        self.assertEqual(interval['conditional_mean_width'], 1)
        self.assertEqual((interval['supplied_valid_count'], interval['required_denominator']), (1, 2))
        self.assertFalse(interval['complete_interval_support'])
        self.p['predictions'][0]['q10'] = 0.5
        out = self.grade()
        self.assertEqual(out['people'][0]['candidate_mae'], 5)
        self.assertEqual(out['people'][0]['interval_diagnostic']['supplied_valid_count'], 0)

    def test_defective_targets_refuse_not_candidate_penalty(self):
        self.t['people'][0]['trials'][3]['rating'] = None
        with self.assertRaises(s.ContractError): self.grade()
        self.t['people'][0]['trials'][3]['rating'] = 0
        self.t['people'][0]['trials'] = self.t['people'][0]['trials'][:3]
        with self.assertRaises(s.ContractError): self.grade()
        self.p, self.t, self.r = fixture()
        self.t['people'].pop()
        with self.assertRaises(s.ContractError): self.grade()
        self.p, self.t, self.r = fixture()
        self.t['people'][0]['experiment'] = True
        with self.assertRaises(s.ContractError): self.grade()

    def test_chronology_and_cohort_counts_and_identity(self):
        self.t['people'][0]['trials'][1]['chronology'] = 0
        with self.assertRaises(s.ContractError): self.grade()
        self.p, self.t, self.r = fixture()
        self.t['people'][0]['experiment'] = 2
        with self.assertRaises(s.ContractError): self.grade()
        self.p, self.t, self.r = fixture()
        self.t['people'][0]['trials'][3]['query_id'] = self.t['people'][0]['trials'][4]['query_id']
        with self.assertRaises(s.ContractError): self.grade()

    def test_reference_cannot_inflate_gain_through_invalid_support(self):
        self.r['prediction']['predictions'][0]['median'] = 11
        with self.assertRaises(s.ContractError): self.grade()
        self.r['prediction']['predictions'].pop(0)
        with self.assertRaises(s.ContractError): self.grade()
        self.p, self.t, self.r = fixture()
        self.r['information'] = 'EEG'
        with self.assertRaises(s.ContractError): self.grade()


class InterfaceControls(unittest.TestCase):
    def test_missing_policy_identity_never_loads_trusted(self):
        calls = []
        for a, b in ((None, REPRESENTATION), (PROTOCOL, None), ('bad', REPRESENTATION)):
            with self.assertRaises(s.ContractError):
                s.grade(b'{}', lambda: calls.append(True), protocol_sha256=a, representation_sha256=b)
        self.assertEqual(calls, [])

    def test_full_public_classification_precedes_trusted_callback(self):
        p, t, r = fixture(); order = []; original = s.parse_submission
        def parse(*args):
            answer = original(*args); order.append('classified'); return answer
        def load():
            self.assertEqual(order, ['classified']); order.append('trusted'); return t, r
        with patch.object(s, 'parse_submission', parse):
            out = s.grade(b'broken JSON', load, protocol_sha256=PROTOCOL,
                          representation_sha256=REPRESENTATION)
        self.assertEqual(out['candidate_mae'], 10)
        self.assertEqual(order[:2], ['classified', 'trusted'])

    def test_cli_identity_before_input_open_and_complete_dispatch(self):
        with patch.object(s, 'read_bytes', side_effect=AssertionError('unexpected open')):
            with self.assertRaises(s.ContractError):
                s.main(['--submission','P','--protocol-sha256',PROTOCOL,
                        '--representation-sha256',REPRESENTATION,'--targets','T',
                        '--targets-sha256','a'*64,'--comparator','R','--comparator-sha256','bad',
                        '--output','OUT'])
        p, t, r = fixture(); docs = {'P':raw(p),'T':raw(t),'R':raw(r)}; calls=[]
        def read(path, expected=None): calls.append((path,expected)); return docs[path]
        with tempfile.TemporaryDirectory() as d:
            output=Path(d)/'result.json'
            argv=['--submission','P','--protocol-sha256',PROTOCOL,
                  '--representation-sha256',REPRESENTATION,'--targets','T',
                  '--targets-sha256',hashlib.sha256(docs['T']).hexdigest(),
                  '--comparator','R','--comparator-sha256',hashlib.sha256(docs['R']).hexdigest(),
                  '--output',str(output)]
            with patch.object(s,'read_bytes',read): s.main(argv)
            out=json.loads(output.read_bytes());self.assertEqual(out['candidate_mae'],0)
            self.assertEqual([x[0] for x in calls],['P','T','R'])
            self.assertEqual(out['document_sha256']['targets'],hashlib.sha256(docs['T']).hexdigest())


if __name__ == '__main__':
    unittest.main()
