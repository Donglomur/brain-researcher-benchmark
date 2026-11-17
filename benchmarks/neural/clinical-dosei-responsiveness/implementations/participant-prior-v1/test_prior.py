"""Generated complete-count software controls; no authentic labels or EEG."""
import copy
from fractions import Fraction
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
PRIMARY = HERE.parent / 'ordinal-and-paired' / 'dosei_score.py'
spec = importlib.util.spec_from_file_location('dosei_prior', HERE / 'dosei_prior.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
s = m.primary_module(PRIMARY)


def pin(raw):
    return hashlib.sha256(raw).hexdigest()


def fixture():
    people = ['INVENTED_P0', 'INVENTED_P1', 'INVENTED_P2']
    policy = {'schema': 'dosei_complete_policy_v1', 'task': m.TASK, 'categories': [1, 2, 3, 4, 5],
              'label_source': 'original_EVENT_MOAAS_assessment',
              'provenance': {k: '0' * 64 for k in s.PROVENANCE}, 'people': people,
              'folds': [{'fold_id': f'F{i}', 'training_people': [p for p in people if p != people[i]],
                         'heldout_people': [people[i]]} for i in range(3)],
              'recordings': [{'recording_id': f'R{i}', 'person_id': people[i % 3]} for i in range(171)],
              'assessments': [], 'transitions': []}
    # One, three and two eligible assessments. All other original slots stay null.
    persons = [0, 1, 1, 1, 2, 2]
    categories = [1, 5, 5, 5, 3, 3]
    targets = {'schema': 'dosei_targets_v1', 'task': m.TASK, 'assessments': []}
    for i in range(7328):
        policy['assessments'].append({'assessment_id': f'A{i}', 'recording_id': f'R{persons[i] if i < 6 else i % 171}',
             'source_event_id': f'E{i}', 'label_status': 'valid' if i < 6 else 'missing',
             'window_status': 'complete', 'timing_status': 'verified', 'artifact_status': 'included'})
        targets['assessments'].append({'assessment_id': f'A{i}', 'category': categories[i] if i < 6 else None})
    policy['transitions'] = [{'transition_id': f'T{i}', 'recording_id': f'R{i % 171}', 'source_event_id': f'S{i}'}
                             for i in range(1129)]
    return policy, targets


def training(policy, targets, fid):
    # Test-only evaluator export. Production must use an isolated fold exporter.
    admitted = s.admit_policy(policy)
    expected = m.fold_scope(s, policy, admitted, fid)[2]
    return {'schema': 'dosei_prior_training_v1', 'task': m.TASK, 'policy_sha256': pin(m.encode(policy)),
            'outer_fold': fid, 'assessments': [r.copy() for r in targets['assessments'] if r['assessment_id'] in expected]}


def fit(policy, labels):
    p, t = m.encode(policy), m.encode(labels)
    return m.fit_artifacts(p, t, primary_source=PRIMARY, expected_policy_sha256=pin(p), expected_training_sha256=pin(t))


def merge(policy, bundles):
    p = m.encode(policy)
    raws = [m.encode(b) for b in bundles]
    return m.merge_artifacts(p, raws, primary_source=PRIMARY, expected_policy_sha256=pin(p), expected_bundle_sha256=[pin(b) for b in raws])


class PriorControls(unittest.TestCase):
    def setUp(self):
        self.policy, self.targets = fixture()

    def test_equal_person_prior_is_not_assessment_pooled(self):
        out = fit(self.policy, training(self.policy, self.targets, 'F2'))
        self.assertEqual(out['probabilities'], ['0.5', '0', '0', '0', '0.5'])
        self.assertNotEqual(out['probabilities'], ['0.25', '0', '0', '0', '0.75'])
        self.assertEqual([r['eligible_assessments'] for r in out['training_people']], [1, 3])

    def test_complete_merge_runs_unchanged_primary_and_manual_macro_score(self):
        bundles = [fit(self.policy, training(self.policy, self.targets, f'F{i}')) for i in range(3)]
        predictions = merge(self.policy, list(reversed(bundles)))
        self.assertEqual(len(predictions['assessments']), 7328)
        self.assertEqual(sum(r['status'] == 'not_evaluable' for r in predictions['assessments']), 7322)
        admitted = s.admit_policy(self.policy)
        report = s.score_admitted(self.targets, admitted, s.admit_predictions(predictions, admitted))
        exact = report['primary_normalized_rps']
        self.assertEqual(Fraction(int(exact['numerator']), int(exact['denominator'])), Fraction(1, 2))
        self.assertEqual(report['counts']['recordings'], 171)
        self.assertEqual(report['counts']['transitions'], 1129)

    def test_simplex_rounding_repeating_fractions_and_ties(self):
        exact = (Fraction(1, 3), Fraction(1, 3), Fraction(1, 3), Fraction(0), Fraction(0))
        result = m.simplex_decimal(exact)
        self.assertEqual(result, ['0.333333333333333334', '0.333333333333333333', '0.333333333333333333', '0', '0'])
        decoded = s.probability_vector(result)
        self.assertTrue(all(abs(a - b) < Fraction(1, 10**18) for a, b in zip(exact, decoded)))
        self.assertEqual(m.simplex_decimal((Fraction(1),) + (Fraction(0),) * 4), ['1', '0', '0', '0', '0'])

    def test_train_rows_cannot_include_heldout_or_nonevaluable_labels(self):
        for aid in ('A4', 'A6'):
            labels = training(self.policy, self.targets, 'F2')
            labels['assessments'].append({'assessment_id': aid, 'category': 1})
            with self.subTest(aid=aid), self.assertRaisesRegex(ValueError, 'outer-training'):
                fit(self.policy, labels)

    def test_missing_duplicate_invalid_scale_and_policy_mismatch_refused(self):
        mutations = [lambda x: x['assessments'].pop(),
                     lambda x: x['assessments'].append(x['assessments'][0]),
                     lambda x: x['assessments'][0].update(category=True),
                     lambda x: x['assessments'][0].update(category=0),
                     lambda x: x.update(policy_sha256='f' * 64)]
        for mutation in mutations:
            labels = training(self.policy, self.targets, 'F2')
            mutation(labels)
            with self.assertRaises(ValueError):
                fit(self.policy, labels)

    def test_training_person_without_support_refuses_not_dropped(self):
        self.policy['assessments'][0]['window_status'] = 'incomplete'
        with self.assertRaisesRegex(ValueError, 'every training person'):
            fit(self.policy, training(self.policy, self.targets, 'F2'))

    def test_training_label_change_only_changes_folds_that_train_on_person(self):
        original = [fit(self.policy, training(self.policy, self.targets, f'F{i}')) for i in range(3)]
        self.targets['assessments'][0]['category'] = 2
        changed = [fit(self.policy, training(self.policy, self.targets, f'F{i}')) for i in range(3)]
        self.assertEqual(original[0], changed[0])
        self.assertNotEqual(original[1]['probabilities'], changed[1]['probabilities'])
        self.assertNotEqual(original[2]['probabilities'], changed[2]['probabilities'])

    def test_merge_rejects_omitted_duplicate_tampered_folds_and_counts(self):
        bundles = [fit(self.policy, training(self.policy, self.targets, f'F{i}')) for i in range(3)]
        mutations = [lambda x: x.pop(), lambda x: x.__setitem__(1, x[0]),
                     lambda x: x[0]['assessments'].pop(),
                     lambda x: x[0].update(probabilities=['0.2'] * 5),
                     lambda x: x[0]['training_people'][0].update(eligible_assessments=999)]
        for mutation in mutations:
            altered = copy.deepcopy(bundles)
            mutation(altered)
            with self.assertRaises(ValueError):
                merge(self.policy, altered)

    def test_hash_and_source_pin_refusals(self):
        labels = m.encode(training(self.policy, self.targets, 'F2'))
        with self.assertRaisesRegex(ValueError, 'training hash mismatch'):
            m.fit_artifacts(m.encode(self.policy), labels, primary_source=PRIMARY,
                            expected_policy_sha256=pin(m.encode(self.policy)), expected_training_sha256='f' * 64)
        with tempfile.TemporaryDirectory() as tmp:
            wrong = Path(tmp) / 'wrong.py'
            raw = PRIMARY.read_bytes()
            wrong.write_bytes(b'#' + raw[1:])
            with self.assertRaisesRegex(ValueError, 'source identity'):
                m.primary_module(wrong)

    def test_cli_fit_and_merge_fresh_outputs_without_target_argument(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            p = m.encode(self.policy)
            (base / 'policy').write_bytes(p)
            common = ['--primary-source', str(PRIMARY), '--policy', str(base / 'policy'), '--expected-policy-sha256', pin(p)]
            merge_args = []
            for i in range(3):
                t = m.encode(training(self.policy, self.targets, f'F{i}'))
                (base / f'train{i}').write_bytes(t)
                output = base / f'fold{i}'
                argv = ['fit', *common, '--training', str(base / f'train{i}'), '--expected-training-sha256', pin(t), '--output', str(output)]
                m.main(argv)
                with self.assertRaises(FileExistsError):
                    m.main(argv)
                merge_args += ['--fold-bundle', str(output), '--expected-bundle-sha256', pin(output.read_bytes())]
            m.main(['merge', *common, *merge_args, '--output', str(base / 'predictions')])
            predictions = json.loads((base / 'predictions').read_bytes())
            s.admit_predictions(predictions, s.admit_policy(self.policy))
            self.assertEqual(len(predictions['assessments']), 7328)


if __name__ == '__main__':
    unittest.main()
