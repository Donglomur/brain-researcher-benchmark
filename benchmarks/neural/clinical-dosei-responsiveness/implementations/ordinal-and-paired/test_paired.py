"""Invented complete DoSEI controls; no authentic policy or signal."""
import copy
from fractions import Fraction
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
PRIMARY = HERE / 'dosei_score.py'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


m = load('paired', HERE / 'dosei_paired.py')
base = load('invented_fixture', PRIMARY.with_name('test_dosei.py'))


def encoded(x): return json.dumps(x, sort_keys=True, separators=(',', ':')).encode()
def sha(x): return hashlib.sha256(encoded(x)).hexdigest()
def number(x): return None if x is None else Fraction(int(x['numerator']), int(x['denominator']))


def fixture():
    policy, original, targets = base.fixture()
    maps = {'schema': 'dosei_frozen_pairing_manifest_v1', 'task': base.m.TASK,
            'policy_sha256': sha(policy), 'arms': ['ARM'],
            'freeze_receipts': {k: '0' * 64 for k in ('target_free_rules', 'original_packet_set', 'admissibility', 'before_outcomes')},
            'case_metadata': [{'assessment_id': row['assessment_id'], 'session_id': 'SESSION_' + row['recording_id'],
                              'nuisance_stratum': 'INVENTED_STRATUM', 'original_packet_sha256': '1' * 64}
                             for row in policy['assessments']], 'transforms': []}
    predictions = {'schema': 'dosei_paired_predictions_v1', 'task': base.m.TASK, 'arms': [
        {'arm_id': 'ARM', 'original_packet_set_sha256': '0' * 64, 'original': original, 'transforms': []}]}
    schedule = [({0: 5, 1: 1, 7327: 5}, '2'), ({0: 1, 1: 2}, '3')]
    for index, (support, fingerprint) in enumerate(schedule):
        transform = {'transform_id': 'T' + str(index), 'kind': 'temporal_shuffle',
                     'coordinate_map_sha256': fingerprint * 64, 'nonidentity_receipt_sha256': '4' * 64, 'rows': []}
        output = {'transform_id': transform['transform_id'], 'coordinate_map_sha256': fingerprint * 64, 'assessments': []}
        for i, row in enumerate(policy['assessments']):
            packet = fingerprint * 64 if i in support else None
            transform['rows'].append({'assessment_id': row['assessment_id'],
                'disposition': 'supported' if i in support else 'unsupported',
                'reason': 'supported' if i in support else 'no_admissible_map', 'transformed_packet_sha256': packet})
            output['assessments'].append({'assessment_id': row['assessment_id'], 'outer_fold': 'F1' if i == 7327 else 'F0',
                'status': 'ok' if i in support else 'not_paired', 'packet_sha256': packet,
                'probabilities': [str(int(k == support[i])) for k in range(1, 6)] if i in support else None})
        maps['transforms'].append(transform); predictions['arms'][0]['transforms'].append(output)
    return policy, maps, predictions, targets


def admit(p, maps, predictions):
    primary = m.primary_module(PRIMARY); policy = primary.admit_policy(p)
    map_parts = m.admit_maps(primary, maps, policy, sha(p))
    outputs = m.admit_predictions(primary, predictions, policy, map_parts, maps)
    return primary, policy, map_parts, outputs


class PairedControls(unittest.TestCase):
    def setUp(self): self.p, self.maps, self.x, self.y = fixture()

    def test_unequal_people_then_equal_transforms_not_pooled(self):
        primary, policy, map_parts, outputs = admit(self.p, self.maps, self.x)
        out = m.grade(primary, self.y, policy, map_parts, outputs)
        self.assertEqual(number(out['transforms'][0]['arms'][0]['supported_person_macro_difference']), Fraction(3, 4))
        self.assertEqual(number(out['transforms'][1]['arms'][0]['supported_person_macro_difference']), Fraction(1, 8))
        self.assertEqual(number(out['equal_valid_transform_means'][0]['transformed_minus_original']), Fraction(7, 16))
        self.assertNotEqual(Fraction(7, 16), Fraction(9, 20))
        self.assertEqual(out['complete_original_scores']['ARM']['counts'], {**base.m.COUNTS, 'people': 2, 'evaluable_assessments': 7328})
        for t in out['transforms']:
            self.assertEqual(len(t['all_original_cases']), 7328)
            self.assertEqual(sum(g['original_cases'] for g in t['coverage_by_person_recording_session_stratum']), 7328)
        self.assertEqual(out['transforms'][1]['people_without_support'], ['INVENTED_B'])

    def test_entire_unavailable_transform_retained_not_zero_weight(self):
        for row in self.maps['transforms'][1]['rows']:
            row.update(disposition='invalid', reason='unestablished_masks', transformed_packet_sha256=None)
        for row in self.x['arms'][0]['transforms'][1]['assessments']:
            row.update(status='not_paired', packet_sha256=None, probabilities=None)
        primary, policy, parts, outputs = admit(self.p, self.maps, self.x)
        out = m.grade(primary, self.y, policy, parts, outputs)
        self.assertEqual(out['available_transform_count'], 1)
        self.assertEqual(number(out['equal_valid_transform_means'][0]['transformed_minus_original']), Fraction(3, 4))
        self.assertEqual(out['transforms'][1]['status'], 'unavailable_no_paired_support')
        self.assertEqual(len(out['transforms'][1]['all_original_cases']), 7328)

    def test_original_failure_cannot_be_hidden_by_no_null_support(self):
        self.x['arms'][0]['original']['assessments'][5].update(status='not_evaluable', probabilities=None)
        with self.assertRaisesRegex(ValueError, 'evaluable prediction'): admit(self.p, self.maps, self.x)

    def test_failed_supported_prediction_cannot_select_favorable_subset(self):
        self.x['arms'][0]['transforms'][0]['assessments'][7327].update(status='not_paired', probabilities=None)
        with self.assertRaisesRegex(ValueError, 'failed supported'): admit(self.p, self.maps, self.x)

    def test_full_case_transform_and_transition_scope(self):
        self.maps['transforms'][0]['rows'].pop()
        with self.assertRaisesRegex(ValueError, 'every original slot'): admit(self.p, self.maps, self.x)
        self.maps['transforms'][0]['rows'].append({'assessment_id': 'T0000'})
        with self.assertRaisesRegex(ValueError, 'every original slot'): admit(self.p, self.maps, self.x)
        self.p['transitions'].pop()
        with self.assertRaisesRegex(ValueError, '1129'): admit(self.p, self.maps, self.x)

    def test_two_arm_packet_and_support_parity(self):
        self.maps['arms'].append('SECOND')
        second = copy.deepcopy(self.x['arms'][0]); second['arm_id'] = 'SECOND'
        self.x['arms'].append(second)
        primary, policy, parts, outputs = admit(self.p, self.maps, self.x)
        self.assertEqual(set(outputs['ARM'][1]['T0']), set(outputs['SECOND'][1]['T0']))
        second['transforms'][0]['assessments'][0]['packet_sha256'] = '9' * 64
        with self.assertRaisesRegex(ValueError, 'identical transformed packet'): admit(self.p, self.maps, self.x)

    def test_ineligible_original_kept_with_valid_mapping_but_not_scored(self):
        self.p['assessments'][0]['label_status'] = 'missing'; self.y['assessments'][0]['category'] = None
        self.x['arms'][0]['original']['assessments'][0].update(status='not_evaluable', probabilities=None)
        for t in self.x['arms'][0]['transforms']: t['assessments'][0].update(status='not_paired', probabilities=None)
        self.maps['policy_sha256'] = sha(self.p)
        primary, policy, parts, outputs = admit(self.p, self.maps, self.x)
        self.assertNotIn('A0000', outputs['ARM'][1]['T0'])
        self.assertEqual(len(parts[2]['T0'][1]), 7328)

    def test_target_free_schema_duplicate_mapping_and_pins(self):
        self.maps['case_metadata'][0]['category'] = 1
        with self.assertRaisesRegex(ValueError, 'exact fields'): admit(self.p, self.maps, self.x)
        del self.maps['case_metadata'][0]['category']
        self.maps['transforms'][1]['coordinate_map_sha256'] = self.maps['transforms'][0]['coordinate_map_sha256']
        with self.assertRaisesRegex(ValueError, 'duplicate declared'): admit(self.p, self.maps, self.x)
        with self.assertRaisesRegex(ValueError, 'exact accepted primary|exact ordinary'):
            m.primary_module(HERE / 'test_paired.py')

    def test_byte_api_rejects_before_target_parse(self):
        self.x['arms'][0]['transforms'][0]['assessments'][0].update(status='not_paired', probabilities=None)
        raw = [encoded(v) for v in (self.p, self.maps, self.x)]
        pins = {f'expected_{k}_sha256': hashlib.sha256(v).hexdigest() for k, v in zip(('policy', 'maps', 'predictions'), raw)}
        with self.assertRaisesRegex(ValueError, 'failed supported'):
            m.score_artifacts(*raw, b'invalid targets', primary_source=PRIMARY, expected_targets_sha256='0' * 64, **pins)


if __name__ == '__main__': unittest.main()
