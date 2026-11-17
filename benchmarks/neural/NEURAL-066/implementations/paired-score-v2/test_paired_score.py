"""Generated software controls only; no authentic data, fitting, or model calls."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import core
import protected_score as primary
import independent_score as independent

LEGACY = HERE.parent / 'neural-066' / 'typing-s3-public-v1' / 'source'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class Workspace:
    """In-memory sealed-capture stand-in, with no filesystem targets."""
    def __init__(self, bodies):
        self.bodies = bodies
        self.budget = self
        self.reads = 0

    def from_capture(self, capture, name):
        assert name == 'PREDICTIONS.json'
        return {'source_path': capture}

    def read(self, path, descriptor):
        self.reads += 1
        return self.bodies[path]

    def tick(self):
        return None


def fixture():
    expected, gold, languages, predictions, bodies = {}, {}, {}, {}, {}
    counts = {'starts': [1] * 29, 'transition': [[1] * 29 for _ in range(29)]}
    for case in core.cases():
        slot = case['slot']
        # Unequal sentence counts across folds and unequal key counts: the
        # registered estimand must not become equal-fold or key-micro CER.
        truths = [[0, 1, 2, 3]] if case['fold'] == 0 else [[4, 5], [6, 7]]
        gold[slot] = {f'generated/{slot}/{i}': truth for i, truth in enumerate(truths)}
        languages[slot] = counts
        rows = [{'id': f'opaque-{slot}-{i}', 'source_key': source}
                for i, source in enumerate(gold[slot])]
        cells = [('candidate', mode, arm) for mode in core.MODES for arm in core.CONDITIONS]
        cells += [(role, 'reference', arm) for role, arms in (
            ('r0', core.CONDITIONS), ('r2', core.R2_ARMS), ('r1', ('LANGUAGE_ONLY',)))
            for arm in arms]
        for role, mode, arm in cells:
            context = core.identity([role, slot, mode, arm])
            expected[context] = {**case, 'role': role, 'mode': mode, 'condition': arm,
                                 'private_queries': copy.deepcopy(rows)}
            view = {'generation': 'generated-only', 'case': f'case-{slot}',
                    'condition': arm, 'queries': [
                        {'id': row['id'], 'n_keys': len(gold[slot][row['source_key']])}
                        for row in rows]}
            sentences = []
            for row in rows:
                decoded = list(gold[slot][row['source_key']])
                if (role == 'candidate' and arm == 'NEURAL' and
                        case['fold'] == 0 and case['person_slot'] % 2 == 0):
                    decoded[0] = 28
                p = [[float(k == value) for k in range(29)] for value in decoded]
                sentences.append({'id': row['id'], 'p': p})
            bodies[context] = {'format': 'typing_predictions_v1', 'task': 'NEURAL-066',
                               'generation': view['generation'], 'case': view['case'],
                               'arm': arm, 'sentences': sentences}
            predictions[context] = {'capture': context, 'public': {'view': view}}
    return expected, gold, languages, predictions, bodies


class PairedScoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.expected, cls.gold, cls.languages, cls.predictions, cls.bodies = fixture()
        cls.contrasts = json.loads((LEGACY / 'design' / 'CONTRAST_ROSTER.json').read_text())['records']

    def items(self):
        for context, entry in self.predictions.items():
            yield context, primary.admit_predictions(self.bodies[context], entry['public']['view'])

    def reject_both(self, expected, gold=None):
        gold = self.gold if gold is None else gold
        # These are the actual scoring entrypoints, not isolated validator tests.
        with self.assertRaises(ValueError):
            primary.grade_stream(iter(()), expected, gold, self.languages, self.contrasts)
        ws = Workspace(self.bodies)
        with self.assertRaises(ValueError):
            independent.verify_stream(self.predictions, expected, gold, {}, ws,
                                      self.languages, self.contrasts)
        self.assertEqual(ws.reads, 0, 'Reject support before reading prediction captures')

    def test_complete_registered_aggregation_and_independent_pass(self):
        result = primary.grade_stream(self.items(), self.expected, self.gold,
                                      self.languages, self.contrasts)
        check = independent.verify_stream(self.predictions, self.expected, self.gold,
                                           result, Workspace(self.bodies), self.languages,
                                           self.contrasts)
        self.assertEqual((len(result['metrics']), len(result['contrasts'])), (90, 164))
        self.assertEqual(check['sentence_audit_rows'], 5265)
        for modality, people in [('MEG', 19), ('EEG', 20)]:
            for mode in core.MODES:
                key = '|'.join(['candidate', mode, 'NEURAL', 'raw', modality])
                metric = result['metrics'][key]
                person_values = [(1 / 12 if p % 2 == 0 else 0) for p in range(people)]
                mean = sum(person_values) / people
                se = math.sqrt(sum((x - mean) ** 2 for x in person_values) / (people - 1) / people)
                self.assertAlmostEqual(metric['person_macro_sentence_CER'], mean, places=14)
                self.assertAlmostEqual(metric['descriptive_person_SE'], se, places=14)
                self.assertAlmostEqual(metric['by_person']['0'], 1 / 12, places=14)
                self.assertNotAlmostEqual(metric['by_person']['0'], 1 / 8, places=14)
        self.assertLess(result['contrasts']['C001']['mean'], 0, 'Unfavorable neural contrast retained')
        self.assertIsNone(result['primary_scalar'])
        self.assertFalse(result['modalities_pooled'])
        self.assertFalse(result['scientific_qualified'])

    def test_predecessors_accept_swapped_private_sources(self):
        old_primary = module('neural066_old_primary', LEGACY / 'protected_score.py')
        old_independent = module('neural066_old_independent', LEGACY / 'independent_score.py')
        expected = copy.deepcopy(self.expected)
        context = core.identity(['candidate', 'EEG-00-1', core.MODES[0], 'TIMING'])
        rows = expected[context]['private_queries']
        rows[0]['source_key'], rows[1]['source_key'] = rows[1]['source_key'], rows[0]['source_key']
        result = old_primary.grade_stream(self.items(), expected, self.gold,
                                          self.languages, self.contrasts)
        self.assertTrue(old_independent.verify_stream(
            self.predictions, expected, self.gold, result, Workspace(self.bodies),
            self.languages, self.contrasts)['matched'])
        key = '|'.join(['candidate', core.MODES[0], 'TIMING', 'raw', 'EEG'])
        self.assertAlmostEqual(result['metrics'][key]['by_person']['0'], 2 / 3)
        # Public views/bodies are unchanged; both predecessor passes agree on
        # the wrong source assignment. Both successor entrypoints must refuse.
        self.reject_both(expected)

    def test_omitted_sentence(self):
        expected = copy.deepcopy(self.expected)
        context = core.identity(['r0', 'EEG-00-1', 'reference', 'EOG'])
        expected[context]['private_queries'].pop()
        self.reject_both(expected)

    def test_duplicate_source_and_duplicate_id(self):
        context = core.identity(['r2', 'MEG-00-1', 'reference', 'NEURAL'])
        for field in ('id', 'source_key'):
            with self.subTest(field=field):
                expected = copy.deepcopy(self.expected)
                rows = expected[context]['private_queries']
                rows[1][field] = rows[0][field]
                self.reject_both(expected)

    def test_same_sources_different_opaque_assignment(self):
        expected = copy.deepcopy(self.expected)
        context = core.identity(['candidate', 'EEG-00-1', core.MODES[1], 'EOG'])
        rows = expected[context]['private_queries']
        rows[0]['id'], rows[1]['id'] = rows[1]['id'], rows[0]['id']
        self.reject_both(expected)

    def test_empty_case_and_extra_or_missing_vault_source(self):
        for change in ('empty', 'extra', 'missing'):
            with self.subTest(change=change):
                gold = copy.deepcopy(self.gold)
                if change == 'empty':
                    gold['MEG-00-0'] = {}
                elif change == 'extra':
                    gold['MEG-00-0']['generated-extra'] = [0]
                else:
                    gold['MEG-00-0'].pop(next(iter(gold['MEG-00-0'])))
                self.reject_both(self.expected, gold)

    def test_cross_fold_sentence_reuse(self):
        gold = copy.deepcopy(self.gold)
        source = next(iter(gold['MEG-00-0']))
        gold['MEG-00-1'][source] = [0, 1, 2, 3]
        self.reject_both(self.expected, gold)

    def test_context_identity_and_typed_person(self):
        context = core.identity(['candidate', 'MEG-00-0', core.MODES[0], 'NEURAL'])
        for field, value in [('person_slot', 1), ('person_slot', False),
                             ('fold', 1), ('slot', 'EEG-00-0'), ('role', 'r0')]:
            with self.subTest(field=field, value=value):
                expected = copy.deepcopy(self.expected)
                expected[context][field] = value
                self.reject_both(expected)

    def test_malformed_prediction_remains_rejected(self):
        context = next(iter(self.predictions))
        view = self.predictions[context]['public']['view']
        for value in (math.nan, math.inf, -0.1, True):
            body = copy.deepcopy(self.bodies[context])
            body['sentences'][0]['p'][0][0] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                primary.admit_predictions(body, view)


if __name__ == '__main__':
    unittest.main(verbosity=2)
