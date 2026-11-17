"""Generated aggregation controls; no authentic observations or hidden targets."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import sys
import types
import unittest

HERE = Path(__file__).resolve().parent
RUNTIME = HERE.parent / 'registered-runtime' / 'complete_study'
sys.path.insert(0, str(RUNTIME))
from n055 import registry, reporting
from n055.common import Refusal

spec = importlib.util.spec_from_file_location('participant_effects', HERE / 'endpoint.py')
endpoint = importlib.util.module_from_spec(spec)
spec.loader.exec_module(endpoint)
CONTRASTS = json.loads((RUNTIME / 'contracts' / 'CONTRASTS.json').read_text())


def fixture():
    expected = registry.campaign('GENERATED')
    terminals = {}
    outcomes = {}
    pairing = {'query_order': {}}
    for cell in expected:
        person = registry.PEOPLE.index(cell['outer_person'])
        case = 'case_%02d' % person
        queries = ['q_%02d_%03d' % (person, i) for i in range(200)]
        pairing['query_order'][case] = list(reversed(queries))
        seed = registry.SEEDS.index(cell['seed']) if cell['seed'] in registry.SEEDS else 0
        correct = 10 * person + 3 * seed + (20 if cell['mode'] == 'I' else 0)
        assignment = [int(i < correct) for i in range(200)]
        independent = [int(i < max(0, correct - 10)) for i in range(200)]
        token = registry.token(cell)
        terminals[token] = {'cell_key': cell, 'status': 'complete_valid', 'public_case_identity': case}
        outcomes[token] = {'query_ids': queries, 'metrics': {
            'assignment_accuracy': assignment, 'independent_accuracy': independent,
            'NLL': [1.0 + person / 100] * 200, 'Brier': [0.5] * 200,
            'Top5': [1] * 200,
            'assignment_minus_independent': [a - b for a, b in zip(assignment, independent)]}}
    return expected, terminals, outcomes, pairing


class ParticipantEndpointTests(unittest.TestCase):
    def setUp(self):
        self.expected, self.terminals, self.outcomes, self.pairing = fixture()

    def summarize(self):
        return endpoint.participant_endpoints(reporting, 'GENERATED', self.expected,
                                             self.terminals, self.outcomes, self.pairing, CONTRASTS)

    def test_ten_person_effects_and_seed_average_have_hand_computed_values(self):
        result = self.summarize()
        scores = {tuple(row['key']): row for row in result['condition_scores']}
        fixed = scores['GENERATED', 'F', 'T0', 'FULL']['participants']
        self.assertEqual(len(fixed), 10)
        self.assertTrue(all(row['replicate_cells_averaged'] == 3 for row in fixed))
        self.assertAlmostEqual(fixed[0]['metrics']['assignment_accuracy']['value'], 3 / 200)
        self.assertAlmostEqual(sum(row['metrics']['assignment_accuracy']['value'] for row in fixed) / 10, 48 / 200)
        c01 = result['paired_person_effects'][0]
        self.assertEqual(c01['independent_people'], 10)
        self.assertEqual(len(result['paired_person_effects']), 32)
        for row in c01['participants']:
            self.assertAlmostEqual(row['metrics']['assignment_accuracy_contrast']['left_minus_right']['value'], 20 / 200)
        serialized = json.dumps(result, allow_nan=False)
        self.assertNotIn('q_00_000', serialized)
        self.assertNotIn('sub-01', serialized)
        self.assertFalse(result['scientific_qualification_claim'])

    def test_one_failed_seed_removes_whole_condition_and_required_contrasts(self):
        cell = self.expected[0]
        self.terminals[registry.token(cell)]['status'] = 'failed'
        result = self.summarize()
        key = ('GENERATED', 'F', 'T0', 'FULL')
        self.assertNotIn(key, {tuple(row['key']) for row in result['condition_scores']})
        self.assertEqual(result['paired_person_effects'][0]['status'], 'unavailable')
        self.assertEqual(result['unavailable_conditions'][0]['required_cells'], 30)
        self.assertEqual(len(result['unavailable_conditions'][0]['missing']), 1)

    def test_person_case_rebinding_across_seeds_rejected(self):
        cell = self.expected[0]
        self.terminals[registry.token(cell)]['public_case_identity'] = 'different_case'
        with self.assertRaisesRegex(ValueError, 'retain its case'):
            self.summarize()

    def test_distinct_people_cannot_alias_one_case(self):
        for terminal in self.terminals.values():
            if terminal['cell_key']['outer_person'] == 'sub-02':
                terminal['public_case_identity'] = 'case_00'
        with self.assertRaisesRegex(ValueError, 'distinct public cases'):
            self.summarize()

    def test_duplicate_expected_cell_is_not_extra_replication(self):
        self.expected.append(self.expected[0])
        with self.assertRaisesRegex(ValueError, 'duplicate expected'):
            self.summarize()

    def test_terminal_cell_mismatch_is_rejected(self):
        self.terminals[registry.token(self.expected[0])]['cell_key'] = self.expected[1]
        with self.assertRaisesRegex(ValueError, 'exact cell'):
            self.summarize()

    def test_infinite_nll_is_retained_and_difference_is_undefined(self):
        for cell in self.expected:
            if cell['outer_person'] == 'sub-01':
                self.outcomes[registry.token(cell)]['metrics']['NLL'][0] = math.inf
        result = self.summarize()
        loss = result['paired_person_effects'][0]['participants'][0]['metrics']['NLL']
        self.assertEqual(loss['left']['status'], 'positive_infinity')
        self.assertEqual(loss['right']['status'], 'positive_infinity')
        self.assertEqual(loss['left_minus_right']['status'], 'undefined')
        json.dumps(result, allow_nan=False)

    def test_invalid_query_pairing_rejected_by_original_join(self):
        self.pairing['query_order']['case_00'][0] = 'foreign_query'
        with self.assertRaisesRegex(Refusal, 'common-image order'):
            self.summarize()

    def test_explicit_adapter_preserves_original_and_calls_it_once(self):
        # Exercise orchestration without executing the original 10,000-draw
        # bootstrap. The real original aggregation/contrast functions above run.
        summary = self.summarize()
        original = {'schema': 'neural055-complete-paired-report-v1',
                    'conditions': [{'key': row['key'], 'metrics': {'sentinel': 12}}
                                   for row in summary['condition_scores']],
                    'contrasts': [{'id': row['id'], 'status': row['status']}
                                  for row in summary['paired_person_effects']],
                    'population_pvalues': None, 'scientific_qualification_claim': False}
        saved = copy.deepcopy(original)
        calls = []
        facade = types.SimpleNamespace(**vars(reporting))
        def retained(*args):
            calls.append(args)
            return original
        facade.paired_report = retained
        result = endpoint.paired_report(facade, 'GENERATED', self.expected, self.terminals,
                                       self.outcomes, self.pairing, {}, CONTRASTS, {}, lambda stage: None)
        self.assertEqual(len(calls), 1)
        self.assertEqual(original, saved)
        result.pop('participant_endpoints')
        self.assertEqual(result, saved)


if __name__ == '__main__':
    unittest.main()
