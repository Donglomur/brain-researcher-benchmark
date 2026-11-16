"""Generated controls for the complete55-person scientific scoring endpoint."""
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('stroop', Path(__file__).with_name('stroop.py'))
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


def opaque(name):
    return hashlib.sha256(('generated-only:' + name).encode()).hexdigest()


def fixture(extra_neutral=0):
    people = [opaque('person' + str(i)) for i in range(55)]
    seed = '12' * 32
    folds = s.fold_assignment(people, seed)
    m = {'schema': 'stroop55-private-labels-v1', 'task': s.TASK, 'partition_seed': seed,
         'cohort': [{'participant': p, 'sessions': [1, 2, 3]} for p in people], 'cases': []}
    y = {'schema': 'stroop55-predictions-v1', 'task': s.TASK, 'predictions': []}
    for i, person in enumerate(people):
        targets = [0, 1, 2] + ([0] * extra_neutral if i == 0 else [])
        for block, target in enumerate(targets):
            case_id = opaque('case:' + str(i) + ':' + str(block))
            m['cases'].append({'case_id': case_id, 'participant': person, 'session': 3,
                               'block': block, 'fold': folds[person], 'target': target})
            y['predictions'].append({'case_id': case_id, 'probabilities': [int(k == target) for k in range(3)],
                                      'label': s.CLASSES[target]})
    return m, y


class Controls(unittest.TestCase):
    def test_perfect_complete_cohort(self):
        m, y = fixture(); r = s.evaluate(m, y)
        self.assertEqual((r['participants'], r['source_session_metadata_count'], r['cases']), (55, 165, 165))
        self.assertEqual(r['primary']['value'], 1)
        self.assertEqual(r['secondary']['participant_mean_brier_sum3'], 0)
        self.assertEqual(r['secondary']['participant_mean_log_loss'], 0)
        self.assertEqual(len(r['per_participant']), 55)
        self.assertEqual([f['participants'] for f in r['per_fold']], [11] * 5)

    def test_uniform_tie_and_analytic_chance(self):
        m, y = fixture()
        for row in y['predictions']:
            row.update(probabilities=[1 / 3] * 3, label='neutral')
        r = s.evaluate(m, y)
        self.assertAlmostEqual(r['primary']['value'], 1 / 3)
        self.assertAlmostEqual(r['secondary']['participant_mean_brier_sum3'], 2 / 3)
        self.assertAlmostEqual(r['secondary']['participant_mean_log_loss'], math.log(3))

    def test_wrong_confident_predictions_and_log_clipping(self):
        m, y = fixture()
        for case, row in zip(m['cases'], y['predictions']):
            wrong = (case['target'] + 1) % 3
            row.update(probabilities=[int(k == wrong) for k in range(3)], label=s.CLASSES[wrong])
        r = s.evaluate(m, y)
        self.assertEqual(r['primary']['value'], 0)
        self.assertEqual(r['secondary']['participant_mean_brier_sum3'], 2)
        self.assertAlmostEqual(r['secondary']['participant_mean_log_loss'], -math.log(1e-15))

    def test_unequal_block_counts_person_macro_and_no30_block_truncation(self):
        m, y = fixture(extra_neutral=60)
        for row in y['predictions'][3:63]:
            row.update(probabilities=[0, 1, 0], label='congruent')
        r = s.evaluate(m, y)
        expected = (54 + (1 / 61 + 1 + 1) / 3) / 55
        self.assertEqual(r['cases'], 225)
        self.assertAlmostEqual(r['primary']['value'], expected)
        self.assertNotAlmostEqual(r['primary']['value'], 165 / 225)
        self.assertAlmostEqual(r['secondary']['participant_mean_brier_sum3'], (120 / 63) / 55)

    def test_folds_are_stable_and_training_is_jointly_held_out(self):
        m, _ = fixture(); people = [x['participant'] for x in m['cohort']]
        a = s.fold_assignment(people, m['partition_seed'])
        self.assertEqual(a, s.fold_assignment(list(reversed(people)), m['partition_seed']))
        self.assertEqual(sorted(list(a.values()).count(f) for f in range(5)), [11] * 5)
        for fold in range(5):
            roles = s.training_roles(a, fold)
            self.assertTrue(s.check_training_roles(a, fold, roles))
            self.assertEqual(len(roles), 88)
            self.assertTrue(all(a[p] != fold and session in (1, 2) for p, session in roles))
            bad = list(roles); bad[0] = (roles[0][0], 3)
            with self.assertRaises(s.Invalid): s.check_training_roles(a, fold, bad)
            bad = list(roles); bad[0] = (next(p for p in a if a[p] == fold), 1)
            with self.assertRaises(s.Invalid): s.check_training_roles(a, fold, bad)

    def test_no_missing_classes_people_sessions_or_fold_reassignment(self):
        for kind in ('person', 'class', 'session', 'fold', 'duplicate_block'):
            m, y = fixture()
            if kind == 'person': m['cohort'].pop()
            if kind == 'class': m['cases'].pop(1); y['predictions'].pop(1)
            if kind == 'session': m['cohort'][0]['sessions'] = [1, 3]
            if kind == 'fold': m['cases'][0]['fold'] = (m['cases'][0]['fold'] + 1) % 5
            if kind == 'duplicate_block': m['cases'][1]['block'] = m['cases'][0]['block']
            with self.subTest(kind=kind), self.assertRaises(s.Invalid): s.evaluate(m, y)

    def test_case_coverage_cannot_be_changed_by_candidate(self):
        for kind in ('missing', 'duplicate', 'extra', 'unknown'):
            m, y = fixture()
            if kind == 'missing': y['predictions'].pop()
            if kind == 'duplicate': y['predictions'][1] = copy.deepcopy(y['predictions'][0])
            if kind == 'extra': y['predictions'].append(copy.deepcopy(y['predictions'][0]))
            if kind == 'unknown': y['predictions'][0]['case_id'] = 'fe' * 32
            with self.subTest(kind=kind), self.assertRaises(s.Invalid): s.evaluate(m, y)

    def test_probability_and_label_failures(self):
        variants = [[float('nan'), 0, 1], [float('inf'), 0, 0], [True, 0, 0], [-.1, .1, 1],
                    [.2, .2, .2], [1, 0], [1.1, 0, -.1]]
        for values in variants:
            m, y = fixture(); y['predictions'][0]['probabilities'] = values
            with self.subTest(values=values), self.assertRaises(s.Invalid): s.evaluate(m, y)
        m, y = fixture(); y['predictions'][0]['label'] = 'incongruent'
        with self.assertRaises(s.Invalid): s.evaluate(m, y)
        m, y = fixture(); y['predictions'][0].update(probabilities=[.5, .5, 0], label='congruent')
        with self.assertRaises(s.Invalid): s.evaluate(m, y)

    def test_case_order_does_not_change_scientific_score(self):
        m, y = fixture(); r = s.evaluate(m, y)
        y['predictions'].reverse(); m['cases'].reverse(); m['cohort'].reverse()
        self.assertEqual(r, s.evaluate(m, y))

    def test_manifest_freeze_and_duplicate_json_keys(self):
        m, _ = fixture()
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as d:
            p = Path(d) / 'manifest.json'; body = json.dumps(m).encode(); p.write_bytes(body)
            expected = hashlib.sha256(body).hexdigest()
            self.assertEqual(s.load_json(p, expected), m)
            with self.assertRaises(s.Invalid): s.load_json(p, '00' * 32)
            p.write_bytes(b'{"a":1,"a":2}')
            with self.assertRaises(s.Invalid): s.load_json(p)
            p.write_bytes(b'{"a":NaN}')
            with self.assertRaises(s.Invalid): s.load_json(p)


if __name__ == '__main__':
    unittest.main(verbosity=2)
