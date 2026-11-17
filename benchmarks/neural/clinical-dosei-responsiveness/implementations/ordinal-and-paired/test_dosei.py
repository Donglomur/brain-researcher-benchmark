"""Invented complete-scope controls. No authentic identity/data fixture."""
import copy
from fractions import Fraction
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('dosei_score', HERE / 'dosei_score.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


def fixture():
    people = ['INVENTED_A', 'INVENTED_B']
    recs = [{'recording_id': f'R{i:03d}', 'person_id': people[int(i == 170)]} for i in range(171)]
    policy = {'schema': 'dosei_complete_policy_v1', 'task': m.TASK, 'categories': [1, 2, 3, 4, 5],
              'label_source': 'original_EVENT_MOAAS_assessment',
              'provenance': {k: '0' * 64 for k in m.PROVENANCE}, 'people': people,
              'folds': [{'fold_id': f'F{i}', 'training_people': [people[1-i]], 'heldout_people': [people[i]]}
                        for i in range(2)], 'recordings': recs, 'assessments': [], 'transitions': []}
    predictions = {'schema': 'dosei_predictions_v1', 'task': m.TASK, 'assessments': []}
    targets = {'schema': 'dosei_targets_v1', 'task': m.TASK, 'assessments': []}
    for i in range(7328):
        aid = f'A{i:04d}'; person = int(i == 7327)
        policy['assessments'].append({'assessment_id': aid, 'recording_id': f'R{170 if person else i % 170:03d}',
             'source_event_id': f'E{i:04d}', 'label_status': 'valid', 'window_status': 'complete',
             'timing_status': 'verified', 'artifact_status': 'included'})
        predictions['assessments'].append({'assessment_id': aid, 'outer_fold': f'F{person}',
             'status': 'ok', 'probabilities': ['1', '0', '0', '0', '0']})
        targets['assessments'].append({'assessment_id': aid, 'category': 1})
    for i in range(1129):
        policy['transitions'].append({'transition_id': f'T{i:04d}', 'recording_id': f'R{i % 171:03d}',
                                     'source_event_id': f'SOC{i:04d}'})
    return policy, predictions, targets


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def score(p, x, y):
    raw = [encode(v) for v in (p, x, y)]
    return m.score_artifacts(*raw, **{f'expected_{k}_sha256': hashlib.sha256(v).hexdigest()
                                     for k, v in zip(m.INPUT_CAPS, raw)})


def value(row):
    return Fraction(int(row['numerator']), int(row['denominator']))


class DoSEIControls(unittest.TestCase):
    def setUp(self):
        self.p, self.x, self.y = fixture()

    def test_exact_unequal_person_support_and_repeated_recordings(self):
        self.x['assessments'][0]['probabilities'] = ['0', '0', '0', '0', '1']
        self.x['assessments'][-1]['probabilities'] = ['0', '0', '0', '0', '1']
        out = score(self.p, self.x, self.y)
        self.assertEqual(value(out['primary_normalized_rps']), Fraction(3664, 7327))
        self.assertNotEqual(value(out['primary_normalized_rps']), Fraction(2, 7328))
        self.assertEqual(value(out['people'][0]['normalized_rps']), Fraction(1, 7327))
        self.assertEqual(out['counts'], {**m.COUNTS, 'people': 2, 'evaluable_assessments': 7328})
        self.assertEqual(len(out['recordings']), 171)

    def test_uniform_middle_rps_and_extreme_categories(self):
        uniform = m.probability_vector(['0.2'] * 5)
        self.assertEqual(m.normalized_rps(uniform, 3), Fraction(1, 10))
        for category in range(1, 6):
            point = tuple(Fraction(int(i == category)) for i in range(1, 6))
            self.assertEqual(m.normalized_rps(point, category), 0)
        self.assertEqual(m.normalized_rps((1, 0, 0, 0, 0), 5), 1)
        self.assertEqual(m.normalized_rps((0, 0, 0, 0, 1), 1), 1)

    def test_missing_frozen_labels_preserve_all_slots(self):
        self.p['assessments'][1]['label_status'] = 'missing'
        self.y['assessments'][1]['category'] = None
        self.x['assessments'][1].update(status='not_evaluable', probabilities=None)
        out = score(self.p, self.x, self.y)
        self.assertEqual(out['counts']['assessments'], 7328)
        self.assertEqual(out['counts']['evaluable_assessments'], 7327)
        self.assertEqual(len(out['assessments']), 7328)
        self.assertIsNone(out['assessments'][1]['normalized_rps'])

    def test_all_status_dimensions_and_zero_support_person(self):
        self.p['assessments'][-1].update(window_status='incomplete', timing_status='unresolved', artifact_status='excluded')
        self.x['assessments'][-1].update(status='not_evaluable', probabilities=None)
        out = score(self.p, self.x, self.y)
        self.assertIsNone(out['primary_normalized_rps'])
        self.assertEqual(out['people_without_evaluable_assessments'], ['INVENTED_B'])
        self.assertEqual(len(out['people']), 2)
        self.assertEqual(out['assessments'][-1]['status'], 'valid|incomplete|unresolved|excluded')
        json.dumps(out, allow_nan=False)

    def test_missing_evaluable_prediction_refuses_before_target_parse(self):
        self.x['assessments'][-1].update(status='not_evaluable', probabilities=None)
        p, x = encode(self.p), encode(self.x)
        with self.assertRaisesRegex(ValueError, 'evaluable prediction'):
            m.score_artifacts(p, x, b'not-json', expected_policy_sha256=hashlib.sha256(p).hexdigest(),
                expected_predictions_sha256=hashlib.sha256(x).hexdigest(), expected_targets_sha256='0' * 64)

    def test_omission_duplicate_and_transition_predictions_rejected(self):
        for mutation in ('omit', 'duplicate', 'transition'):
            x = copy.deepcopy(self.x)
            if mutation == 'omit': x['assessments'].pop()
            if mutation == 'duplicate': x['assessments'][-1] = x['assessments'][0]
            if mutation == 'transition': x['assessments'][-1]['assessment_id'] = 'T0000'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                score(self.p, x, self.y)

    def test_full_transitions_accounted_but_never_scored(self):
        out = score(self.p, self.x, self.y)
        self.assertEqual(sum(x['transitions'] for x in out['people']), 1129)
        self.assertEqual(sum(x['transitions'] for x in out['recordings']), 1129)
        self.assertFalse(out['transitions_are_targets'])
        self.p['transitions'].pop()
        with self.assertRaisesRegex(ValueError, '1129'):
            score(self.p, self.x, self.y)

    def test_recording_person_and_fold_leakage_refused(self):
        mutations = [lambda p: p['recordings'][0].update(person_id='UNKNOWN'),
                     lambda p: p['recordings'].pop(),
                     lambda p: p['folds'][0]['training_people'].append('INVENTED_A'),
                     lambda p: p['folds'][1].update(heldout_people=['INVENTED_A'])]
        for mutation in mutations:
            p = copy.deepcopy(self.p); mutation(p)
            with self.assertRaises(ValueError): score(p, self.x, self.y)
        self.x['assessments'][-1]['outer_fold'] = 'F0'
        with self.assertRaisesRegex(ValueError, 'outer fold'): score(self.p, self.x, self.y)

    def test_original_event_census_not_forwarded_labels(self):
        self.p['label_source'] = 'forward_filled_pEEG'
        with self.assertRaisesRegex(ValueError, 'forwarded'): score(self.p, self.x, self.y)
        self.p['label_source'] = 'original_EVENT_MOAAS_assessment'
        self.p['assessments'][170]['source_event_id'] = 'E0000'
        with self.assertRaisesRegex(ValueError, 'forward filling'): score(self.p, self.x, self.y)

    def test_scale_null_and_binary_target_errors(self):
        for label in (0, 6, True, 1.0, '1'):
            y = copy.deepcopy(self.y); y['assessments'][0]['category'] = label
            with self.subTest(label=label), self.assertRaises(ValueError): score(self.p, self.x, y)
        self.p['assessments'][0]['label_status'] = 'ambiguous'
        self.x['assessments'][0].update(status='not_evaluable', probabilities=None)
        with self.assertRaisesRegex(ValueError, 'stay null'): score(self.p, self.x, self.y)

    def test_decimal_precision_strictness_and_small_loss(self):
        p = m.probability_vector(['0.999999999999999999', '0.000000000000000001', '0', '0', '0'])
        self.assertEqual(m.normalized_rps(p, 1), Fraction(1, 4 * 10**36))
        invalid = [[0.2] * 5, ['0.2'] * 4, ['0.1'] * 5, ['NaN', '0', '0', '0', '0'],
                   ['-0.1', '1.1', '0', '0', '0'], ['0.9999999999999999999', '0', '0', '0', '0']]
        for p in invalid:
            with self.assertRaises(ValueError): m.probability_vector(p)

    def test_required_external_hashes_and_strict_json(self):
        raw = encode(self.p)
        with self.assertRaisesRegex(ValueError, 'hash mismatch'): m.decode(raw, 'f' * 64, 'policy')
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}'):
            with self.assertRaises(ValueError): m.decode(raw, hashlib.sha256(raw).hexdigest(), 'policy')
        with self.assertRaises(TypeError): m.score_artifacts(b'{}', b'{}', b'{}')

    def test_cli_fresh_output_and_pre_target_admission(self):
        with tempfile.TemporaryDirectory(prefix='dosei-invented-') as temp:
            base = Path(temp); argv = []
            for name, data in zip(m.INPUT_CAPS, (self.p, self.x, self.y)):
                raw = encode(data); (base / name).write_bytes(raw)
                argv += ['--' + name, str(base / name), '--expected-' + name + '-sha256', hashlib.sha256(raw).hexdigest()]
            output = base / 'score.json'; argv += ['--output', str(output)]
            m.main(argv)
            self.assertEqual(json.loads(output.read_bytes())['primary_normalized_rps']['numerator'], '0')
            with self.assertRaises(FileExistsError): m.main(argv)
            # Bad prediction is rejected without ever opening the target path.
            self.x['assessments'].pop(); raw = encode(self.x); (base / 'predictions').write_bytes(raw)
            index = argv.index('--expected-predictions-sha256') + 1; argv[index] = hashlib.sha256(raw).hexdigest()
            observed = []; original = m.read_regular
            def read(path, cap):
                observed.append(str(path)); return original(path, cap)
            with patch.object(m, 'read_regular', side_effect=read), self.assertRaises(ValueError): m.main(argv)
            self.assertNotIn(str(base / 'targets'), observed)

    def test_regular_admission_rejects_final_symlink_fifo_and_cap(self):
        with tempfile.TemporaryDirectory(prefix='dosei-invented-') as temp:
            base = Path(temp); p = base / 'a'; p.write_bytes(b'123')
            with self.assertRaises(ValueError): m.read_regular(p, 2)
            (base / 'link').symlink_to(p)
            with self.assertRaises(OSError): m.read_regular(base / 'link', 3)
            os.mkfifo(base / 'fifo')
            with self.assertRaises(ValueError): m.read_regular(base / 'fifo', 3)


if __name__ == '__main__':
    unittest.main()
