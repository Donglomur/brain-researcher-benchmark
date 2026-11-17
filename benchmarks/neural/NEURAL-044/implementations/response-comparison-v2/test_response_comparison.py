"""Small generated software controls; no source recordings or model trials."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / 'registered-runtime' / 'source'
sys.path.insert(0, str(SOURCE))

from alm.contracts import Refusal, digest
from alm.inference import held_mouse_improvement
from alm.response_comparison_v2 import prepare_response_comparison, score_response_comparison
from alm.operator_response_v2 import ResponseComparisonOperator

LIMITS = dict(wall_seconds=30, cpu_seconds=30, memory_bytes=2**26,
              output_bytes=2**20, model_calls=1, model_tokens=1)
KEY = b'generated-key-not-for-source-data' * 2
SOURCE_DIGEST = 'a' * 64


def construction():
    # Unequal pair counts deliberately distinguish equal-mouse and pooled scores.
    rows = []
    for mouse, n, response in [('a', 1, 0.0), ('b', 3, 2.0), ('c', 5, 8.0)]:
        for i in range(n):
            rows.append(dict(mouse=mouse, session='session', epoch='rest',
                target_id='target', power=150.0, condition='neuron_target',
                follower_roi=['rest', 'plane', i], distance=100.0,
                baseline=0.0, movement=0.0, similarity=0.5,
                response=response, control='lagged',
                classification_basis='independent_pretest'))
    # This mouse has response-selected sites only; it must remain dispositioned.
    rows.append({**rows[0], 'mouse': 'selected', 'classification_basis': 'response_selected'})
    return {'rows': rows, 'disposition_digest': digest([]), 'dispositions': []}


def prepare(value=None, mice=None):
    return prepare_response_comparison(value or construction(),
        mice or ['a', 'b', 'c', 'selected', 'no_pairs'], KEY, LIMITS, SOURCE_DIGEST)


def scoring_inputs(packet, prediction='truth'):
    public, private, submissions = {}, {}, {}
    for case in packet['cases']:
        p, q = case['public'], case['private']
        key = p['case_id']
        public[key], private[key] = p, q
        pred = q['responses'] if prediction == 'truth' else q['references'][prediction]
        submissions[key] = {'case_id': key, 'ids': p['ids'], 'responses': pred.copy()}
    return submissions, public, private, packet['cohort']


class EndpointTests(unittest.TestCase):
    def test_closed_form_reference_and_equal_mouse_primary(self):
        packet = prepare()
        # All features are constant: the weighted ridge intercept is the mean of
        # other-mouse means, irrespective of their numbers of response pairs.
        expected = {'a': 5.0, 'b': 4.0, 'c': 1.0}
        for case in packet['cases']:
            q = case['private']
            for name in ('nuisance', 'tuning'):
                for value in q['references'][name]:
                    self.assertAlmostEqual(value, expected[q['units'][0]])
        score = score_response_comparison(*scoring_inputs(packet))
        self.assertAlmostEqual(score['primary']['value'], (25.0 + 4.0 + 49.0) / 3)
        self.assertNotAlmostEqual(score['primary']['value'], (25 + 3*4 + 5*49) / 9)
        self.assertEqual(score['n_mice'], 3)
        self.assertEqual(score['n_source_mice'], 5)
        self.assertEqual(score['primary']['uncertainty']['n_mice'], 3)
        unsupported = [r for r in score['mouse_values'] if r['status'] == 'not_estimable']
        self.assertEqual({r['mouse'] for r in unsupported}, {'selected', 'no_pairs'})
        self.assertTrue(all(r['improvement'] is None for r in unsupported))

    def test_nuisance_submission_is_zero_and_worse_candidate_is_negative(self):
        packet = prepare()
        self.assertAlmostEqual(score_response_comparison(
            *scoring_inputs(packet, 'nuisance'))['primary']['value'], 0.0)
        args = scoring_inputs(packet)
        for row in args[0].values():
            row['responses'] = [v + 100 for v in row['responses']]
        self.assertLess(score_response_comparison(*args)['primary']['value'], 0)

    def test_reference_matches_preserved_recipe_on_variable_design(self):
        data = construction()
        for i, row in enumerate(data['rows']):
            row.update(distance=25.0+i*19, baseline=(i % 4)*0.1,
                       movement=float(i % 3), similarity=(i-4)/10,
                       power=100.0+(i % 2)*50)
        packet = prepare(data)
        score = score_response_comparison(*scoring_inputs(packet))
        legacy = {r['mouse']: r for r in held_mouse_improvement(data['rows'], 1.0)}
        for row in score['mouse_values']:
            if row['status'] == 'estimable':
                self.assertAlmostEqual(row['nuisance_mse'], legacy[row['mouse']]['nuisance_mse'])
                self.assertAlmostEqual(row['tuning_mse'], legacy[row['mouse']]['tuning_mse'])

    def test_held_labels_do_not_change_own_public_packet_or_references(self):
        before = prepare()
        changed = construction()
        for row in changed['rows']:
            if row['mouse'] == 'a':
                row['response'] += 1000
        after = prepare(changed)
        get = lambda p: next(c for c in p['cases'] if c['private']['units'][0] == 'a')
        a, b = get(before), get(after)
        self.assertEqual(a['public'], b['public'])
        self.assertEqual(a['private']['references'], b['private']['references'])
        self.assertNotEqual(a['private']['responses'], b['private']['responses'])
        self.assertNotIn('source_ids', a['public'])
        self.assertNotIn('references', a['public'])

    def test_too_few_mice_retains_all_dispositions(self):
        data = construction()
        data['rows'] = [r for r in data['rows'] if r['mouse'] != 'c']
        packet = prepare(data)
        self.assertEqual(packet['cases'], [])
        score = score_response_comparison(*scoring_inputs(packet))
        self.assertIsNone(score['primary']['value'])
        self.assertEqual(score['status'], 'not_estimable')
        self.assertEqual(len(score['mouse_values']), 5)

    def test_reject_incomplete_source_roster_and_duplicate_response(self):
        with self.assertRaises(Refusal):
            prepare(mice=['a', 'b', 'c'])
        data = construction()
        data['rows'].append(copy.deepcopy(data['rows'][0]))
        with self.assertRaises(Refusal):
            prepare(data)

    def test_reject_invalid_case_vectors_units_and_bindings(self):
        base = scoring_inputs(prepare())
        key = next(iter(base[0]))
        mutations = [
            lambda a: a[0].pop(key),
            lambda a: a[0].update(extra=copy.deepcopy(a[0][key])),
            lambda a: a[0][key].update(case_id='wrong'),
            lambda a: a[2][key].update(case_id='wrong'),
            lambda a: a[0][key].update(ids=['wrong']),
            lambda a: a[2][key].update(units=['another_mouse']),
            lambda a: a[2][key].update(responses=[float('nan')]),
            lambda a: a[0][key].update(responses=[float('inf')]),
            lambda a: a[0][key].update(responses=[True]),
            lambda a: a[0][key].update(responses=['1.0']),
            lambda a: a[0][key].update(responses=[[1.0]]),
            lambda a: a[0][key].update(responses=[1e308]),
            lambda a: a[2][key]['references'].update(nuisance=[float('nan')]),
            lambda a: a[1][key].update(source_digest='b'*64),
            lambda a: a[3].update(disposition_digest='c'*64),
            lambda a: a[1][key]['query_features'][0].__setitem__(0, 999.0),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutations.index(mutation)):
                args = copy.deepcopy(base)
                mutation(args)
                with self.assertRaises(Refusal):
                    score_response_comparison(*args)


class OperatorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.public = self.root / 'public'
        self.private = self.root / 'private'
        self.public.mkdir()
        self.private.mkdir()
        self.data = construction()
        self.data['outputs'] = {
            'lagged': {'effect': [{'mouse': 'a', 'effect': 0.0}],
                       'improvement': [{'mouse': 'a', 'improvement': 0.0}],
                       'tuning_rotation_null': [], 'distance_sensitivity': {},
                       'site_class_association': [], 'matched': []},
            'lead_null': {}, 'true_sham': {'status': 'unavailable'}}
        self.op = ResponseComparisonOperator()
        manifest = {'recordings': [{'mouse': m} for m in ['a', 'b', 'c', 'selected', 'no_pairs']]}
        with patch('alm.programme.load_population', return_value=([], {'generated': True})), \
             patch('alm.programme.construct_perturbation', return_value=self.data):
            self.op.prepare_perturbation(None, manifest, None, None, None, KEY, LIMITS,
                self.public, self.private, self.private/'truth.json',
                self.private/'comparison.json', SOURCE_DIGEST,
                self.private/'receipt.json', 2**20)

    def submissions(self):
        submissions, commits = {}, {}
        truth = json.loads((self.private/'truth.json').read_text())
        truth.update(task='NEURAL-044', estimand='conditional_tuning_response_association',
                     interpretation='inconclusive')
        for arm in ('frozen_program', 'case_adaptive'):
            submissions[arm], commits[arm] = {}, {}
            values = {c['public']['case_id']: {'case_id': c['public']['case_id'],
                'ids': c['public']['ids'], 'responses': c['private']['references']['nuisance']}
                for c in self.op._packets}
            values['investigation'] = truth
            for key, value in values.items():
                path = self.root / (arm + '-' + key + '.json')
                path.write_text(json.dumps(value))
                submissions[arm][key] = path
                commits[arm][key] = self.root / (arm + '-' + key + '.commit.json')
        return submissions, commits

    def test_real_publish_capture_and_score_order(self):
        submissions, commits = self.submissions()
        private_read = self.op._private
        def checked_read(path, pin):
            self.assertTrue(all(p.is_file() for table in commits.values() for p in table.values()))
            return private_read(path, pin)
        with patch.object(self.op, '_private', side_effect=checked_read):
            result = self.op.evaluate_perturbation(submissions, commits,
                                                   {'absolute': 1e-9, 'relative': 1e-9})
        for score in result['scores'].values():
            self.assertAlmostEqual(score['held_response']['primary']['value'], 0.0)
            self.assertTrue(score['investigation']['numerical_reproduction_pass'])
        self.assertFalse(result['scientific_qualification'])
        with self.assertRaises(Refusal):
            self.op.evaluate_perturbation(submissions, commits, {})

    def test_mutated_private_reference_rejected_after_commit(self):
        submissions, commits = self.submissions()
        path = self.op._publications[0]['private_path']
        value = json.loads(path.read_text())
        value['references']['nuisance'][0] += 1
        path.write_text(json.dumps(value))
        with self.assertRaisesRegex(Refusal, 'exact original published protected target'):
            self.op.evaluate_perturbation(submissions, commits, {'absolute': 0, 'relative': 0})
        self.assertTrue(all(p.is_file() for table in commits.values() for p in table.values()))


if __name__ == '__main__':
    unittest.main(verbosity=2)
