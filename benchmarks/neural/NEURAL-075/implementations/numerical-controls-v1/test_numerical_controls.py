"""Generated full60 controls for the retained numerical grading seam.

No authentic data, target, candidate program, producer run, or authority is used.
The invented ClosedPair deliberately enters grade_verified_pair, not production
capture. Source authentication and the unchanged numerical scorer are real.
"""
from contextlib import contextmanager
from dataclasses import replace
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

import numpy as np

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent / 'paired-grading'
GRADER = PACKAGE / 'paired_grading'
SOURCE = PACKAGE / 'source_repository'
SOURCE_PIN = {'bytes': 1589, 'sha256': '2f7efbaa03fd83449038d83700efd7e187a4ce440073735ea90f7b3efd8c1dd9'}


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def forbidden(*args, **kwargs):
    raise AssertionError('Generated controls cannot launch a process or use a network')


@contextmanager
def loaded():
    # The existing public inventory supplies the entrypoint pin; the immutable
    # source manifest then authenticates every loaded grading module.
    inventory = json.loads((PACKAGE / 'PUBLIC_INVENTORY.json').read_bytes())
    row = next(r for r in inventory['files'] if r['path'] == 'paired_grading/operator.py')
    raw = (GRADER / 'operator.py').read_bytes()
    if (len(raw), hashlib.sha256(raw).hexdigest()) != (row['bytes'], row['sha256']):
        raise ValueError('Existing operator inventory pin')
    spec = importlib.util.spec_from_file_location('neural075_numerical_control_operator', GRADER / 'operator.py')
    operator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(operator)
    budget = operator._InspectBudget(2**20, 2**20, 30)
    root, _, bodies = operator._capture(SOURCE_PIN, budget)
    with operator._modules(root, bodies, budget) as grader:
        closure = sys.modules['closed_pair']
        pinned = sys.modules['pinned_scorer']
        scorer = pinned.load_scorer(str(SOURCE), closure.FileReader(budget))
        yield grader, closure, scorer


def make_fixture(grader, closure):
    """Full original geometry, generated IDs/scores/labels, ten protected bodies."""
    categories = ['n%08d' % i for i in range(50)]
    supports, private = {}, {}
    for person in grader.PEOPLE:
        for phase in grader.PHASES:
            n = grader.ROWS[phase]
            labels = np.arange(n, dtype=np.int64) % 50
            stream = io.BytesIO()
            np.savez(stream, labels=labels, source_rows=np.arange(n, dtype=np.int64))
            raw = stream.getvalue()
            name = person + '_' + phase + '.npz'
            private[name] = raw
            supports[person, phase] = {
                'person': person, 'phase': phase,
                'trial_ids': ['q' + hashlib.sha256((person + phase + str(i)).encode()).hexdigest()[:24] for i in range(n)],
                'gold': {'path': name, **closure.pin(raw)},
            }
    design = encoded({'protocol': 'neural075-v1', 'people': list(grader.PEOPLE),
                      'roi': 'ROI_VC', 'feature': 'cnn7', 'n_units': 1000,
                      'categories': categories, 'cases': list(supports.values())})
    cases = []
    for access in ('A', 'B'):
        for case in grader.CASES:
            person, arm, phase = case.split('/')
            n = grader.ROWS[phase]
            context = encoded({'case_id': case, 'person': person, 'arm': arm, 'phase': phase,
                               'access_condition': access, 'n_units': 1000,
                               'design_sha256': closure.pin(design)['sha256'],
                               'categories': categories, 'trial_ids': supports[person, phase]['trial_ids']})
            labels = np.arange(n) % 50
            scores = np.zeros((n, 50), dtype=np.int8)
            if arm != 'no_neural':
                correct = 0
                if arm == 'neural':
                    fraction_a = (int(person[-1]) - 1) / 5
                    fraction = fraction_a if access == 'A' else 1 - fraction_a
                    if phase == 'perception':
                        fraction = 1 if access == 'A' else 0
                    correct = round(n * fraction)
                winners = (labels + 1) % 50
                winners[:correct] = labels[:correct]
                scores[np.arange(n), winners] = 1
            prediction = encoded({'protocol': 'neural075-v1', 'case_id': case,
                                  'context_sha256': closure.pin(context)['sha256'],
                                  'categories': categories,
                                  'trial_ids': supports[person, phase]['trial_ids'],
                                  'scores': scores.tolist()})
            cases.append(closure.CapturedCase(access, case, prediction, context))
    # Only the function bodies used for child_ok are read. This invented
    # lifecycle observation is explicitly not a producer-attestation claim.
    invoke = SOURCE / 'authoring/delivery-20261105/neural075/full-cohort-program-v1/invoke.py'
    root = '/invented-neural075-full60'
    snapshot = closure.ClosedSnapshot(root, b'{}', b'{}',
        ((root + '/runs/A/00/source/invoke.py', invoke.read_bytes()),), ())
    complete = closure.pin(b'invented-complete')
    pair = closure.ClosedPair(tuple(cases), snapshot,
        encoded({'design': closure.pin(design), 'complete': complete,
                 'fixture_scope': 'invented numerical seam; no production capture'}))
    child = {'natural_exit': True, 'process_reaped': True, 'streams_closed': True,
             'timed_out': False, 'exit_code': 0, 'error_type': None,
             'process_group_absent': True, 'timer_disable_error': None, 'timer_restore_error': None}
    observation = {'child': child, 'returned': {'status': 'complete_unscored', 'completion': complete, 'outputs': 60}}
    return pair, observation, design, private


class NumericalControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.patches = [patch.object(subprocess, 'Popen', forbidden),
                       patch.object(socket, 'socket', forbidden),
                       patch.object(socket, 'create_connection', forbidden)]
        for item in cls.patches:
            item.start()
        cls.loader = loaded()
        cls.grader, cls.closure, cls.scorer = cls.loader.__enter__()
        cls.pair, cls.observation, cls.design, cls.private = make_fixture(cls.grader, cls.closure)

    @classmethod
    def tearDownClass(cls):
        cls.loader.__exit__(None, None, None)
        for item in reversed(cls.patches):
            item.stop()

    def run_pair(self, pair=None, private=None):
        events = []
        admissions = []
        callback_admissions = []
        supplied = self.private if private is None else private
        def design_read():
            events.append('design')
            callback_admissions.append(len(admissions))
            return self.design
        def private_read(descriptor):
            events.append(descriptor['path'])
            callback_admissions.append(len(admissions))
            return supplied[descriptor['path']]
        original_admit = self.scorer.admit
        def counted_admit(output, context):
            array = original_admit(output, context)
            admissions.append((context['access_condition'], context['case_id'], array.size))
            return array
        budget = self.grader.Budget(512 * 2**20, 512 * 2**20, time.monotonic() + 120)
        self.last_events = events
        self.last_admissions = admissions
        self.callback_admissions = callback_admissions
        with patch.object(self.scorer, 'admit', counted_admit):
            return self.grader.grade_verified_pair(self.pair if pair is None else pair,
                self.observation, design_read, private_read, self.scorer, budget)

    def test_full60_fractional_ties_signed_effects_and_ten_target_reads(self):
        result = self.run_pair()
        self.assertEqual(result['complete_cases_admitted_before_private_read'], 60)
        self.assertEqual(result['score_entries_admitted'], 3375000)
        self.assertEqual(sum(row[2] for row in self.last_admissions), 3375000)
        self.assertEqual([(r[0], r[1]) for r in self.last_admissions],
                         [(a, c) for a in ('A', 'B') for c in self.grader.CASES])
        self.assertEqual(self.callback_admissions, [60] * 11)
        self.assertEqual(result['private_underlying_reads'], 10)
        self.assertEqual(self.last_events[0], 'design')
        self.assertEqual(len(self.last_events), 11)
        self.assertEqual(len(set(self.last_events[1:])), 10)
        compare = result['comparison']
        self.assertAlmostEqual(compare['original_results']['A']['primary'], .4)
        self.assertAlmostEqual(compare['original_results']['B']['primary'], .6)
        primary = compare['primary']['contrast']
        self.assertAlmostEqual(primary['equal_person_mean'], .2)
        np.testing.assert_allclose([r['B_minus_A'] for r in primary['per_person']], [1, .6, .2, -.2, -.6], atol=1e-14)
        self.assertAlmostEqual(compare['access_contrasts']['perception']['neural']['equal_person_mean'], -1)
        for access in ('A', 'B'):
            flat = compare['original_results'][access]['per_case']['Subject1/no_neural/imagery']['trial']
            for name, expected in [('top1_tie_fraction', .02), ('mean_midrank', 25.5),
                                   ('pairwise_half_ties', .5), ('author_strict_greater_rank_fraction_diagnostic', 1)]:
                self.assertAlmostEqual(flat[name], expected)
        for key in ('scientific_qualification_added', 'runtime_qualified'):
            self.assertIs(result[key], False)
        self.assertIsNone(compare['p_value'])

    def test_last_of60_invalid_scores_refuses_before_design_or_private_read(self):
        row = self.pair.cases[-1]
        output = json.loads(row.prediction)
        output['scores'][-1][-1] = 1000001
        bad = replace(row, prediction=encoded(output))
        pair = replace(self.pair, cases=self.pair.cases[:-1] + (bad,))
        with self.assertRaisesRegex(ValueError, 'Complete finite bounded score matrix'):
            self.run_pair(pair)
        self.assertEqual(self.last_events, [])
        self.assertEqual(len(self.last_admissions), 59)

    def test_last_case_wrong_design_trial_join_refuses_before_targets(self):
        row = self.pair.cases[-1]
        context, output = json.loads(row.context), json.loads(row.prediction)
        context['trial_ids'] = context['trial_ids'][::-1]
        context_raw = encoded(context)
        output['trial_ids'] = context['trial_ids']
        output['context_sha256'] = self.closure.pin(context_raw)['sha256']
        bad = replace(row, prediction=encoded(output), context=context_raw)
        pair = replace(self.pair, cases=self.pair.cases[:-1] + (bad,))
        with self.assertRaisesRegex(ValueError, 'Exact paired design support before gold'):
            self.run_pair(pair)
        self.assertEqual(self.last_events, ['design'])
        self.assertEqual(self.callback_admissions, [60])

    def test_private_bytes_tamper_refuses_without_partial_result(self):
        private = dict(self.private)
        private['Subject1_imagery.npz'] = b'not-the-bound-protected-body'
        with self.assertRaisesRegex(ValueError, 'Protected bytes match selected exact descriptor'):
            self.run_pair(private=private)
        self.assertEqual(self.last_events, ['design', 'Subject1_imagery.npz'])

    def test_category_score_mean_is_not_trial_accuracy_mean(self):
        labels = np.repeat(np.arange(50), 10)
        scores = np.zeros((500, 50))
        # In every category: one correct score10, nine wrong score1.
        # Trial Top1=.1, but category score means favor truth1 over foil.9.
        scores[np.arange(500), (labels + 1) % 50] = 1
        scores[::10, :] = 0
        scores[np.arange(0, 500, 10), np.arange(50)] = 10
        result = self.scorer.summarize(scores, labels, 10)
        self.assertAlmostEqual(result['trial']['top1_tie_fraction'], .1)
        self.assertAlmostEqual(result['private_category_mean_scores']['top1_tie_fraction'], 1)

    def test_tie_and_wrong_top_ranks_have_independent_oracle(self):
        result = self.scorer.metrics(np.array([[3., 3., 0., -1.], [0., 2., 1., -1.]]), np.array([0, 0]))
        # Ranks are1.5 and3; top credits .5 and0; correct wins versus
        # distractors are2.5/3 and1/3, with half credit for exact ties.
        self.assertAlmostEqual(result['top1_tie_fraction'], .25)
        self.assertAlmostEqual(result['mean_midrank'], 2.25)
        self.assertAlmostEqual(result['pairwise_half_ties'], 7/12)
        self.assertAlmostEqual(result['author_strict_greater_rank_fraction_diagnostic'], 2/3)


if __name__ == '__main__':
    unittest.main(verbosity=2)
