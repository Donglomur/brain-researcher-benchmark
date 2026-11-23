"""Generated full-panel comparison controls; no neural arrays or model calls."""
import argparse
import copy
import importlib.util
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
SOURCE_TASK = HERE.parent.parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


panel = load('comparison_panel', HERE / 'panel.py')
original_tests = None


def fixture():
    reference_cases, reference_rows, support = original_tests.fixture()
    cases, rows, candidate_support = [], [], {}
    reference_recipes, candidate_recipes = {}, {}
    for source in reference_cases:
        source['factors'] = {}
        source['uncertainty_requirements'] = []
        if source['method'] != 'MINT':
            continue
        source['uncertainty_requirements'] = [{'id': 'historical',
            'target': source['outputs'][0], 'kind': 'historical_absolute_trial_bootstrap',
            'policy_sha256': 'e' * 64}]
        groups = {}
        for column, dimension in enumerate(source['output_dimensions']):
            groups.setdefault(dimension.rsplit(':', 1)[0], []).append(column)
        phase = [j for j, d in enumerate(source['output_dimensions']) if d == 'phase:0']
        recipe = {'module': 'primary_behavior', 'outputs': [{
            'key': source['outputs'][0], 'kind': 'behavior', 'payload_id': 'generated',
            'parameters': {'groups': groups, 'circular_columns': phase,
                           'phase_period': 1.0 if phase else None}, 'value_selector': []}],
            'policy_evidence_sha256': 'f' * 64,
            'experiment_sha256': panel.digest({key: source[key] for key in
                ('module', 'dataset', 'method', 'repeat', 'factors', 'output_dimensions')}),
            'uncertainty_requirements': source['uncertainty_requirements']}
        reference_recipes[source['id']] = recipe
        source['metric_recipe_sha256'] = panel.digest(recipe)
        row = next(row for row in reference_rows if row['case'] == source['id'])
        row['outputs'][0]['commitments']['recipe'] = source['metric_recipe_sha256']
    for source in reference_cases:
        if source['method'] != 'MINT':
            continue
        case = copy.deepcopy(source)
        case['id'] = 'candidate:' + source['dataset']
        case['purpose'] = 'improve'
        case['uncertainty_requirements'] = [{'id': 'prospective',
            'target': source['outputs'][0], 'kind': 'prospective_paired_gain',
            'policy_sha256': 'c' * 64}]
        recipe = copy.deepcopy(reference_recipes[source['id']])
        recipe['uncertainty_requirements'] = case['uncertainty_requirements']
        candidate_recipes[case['id']] = recipe
        case['metric_recipe_sha256'] = panel.digest(recipe)
        # Decoder configuration differs without changing evaluation semantics.
        case['config_sha256'] = 'c' * 64
        cases.append(case)
        candidate_support[case['id']] = support[source['id']]
        row = copy.deepcopy(next(row for row in reference_rows if row['case'] == source['id']))
        row['case'] = case['id']
        row['outputs'][0]['commitments']['recipe'] = case['metric_recipe_sha256']
        original = row['outputs'][0]['reference']
        row['outputs'][0]['candidate'] = {
            'per_dimension_r2': [value + .02 for value in original['per_dimension_r2']],
            'groups': {name: value + .02 for name, value in original['groups'].items()}}
        rows.append(row)
    return (reference_cases, reference_rows, support, cases, rows, candidate_support,
            reference_recipes, candidate_recipes)


def compare(values):
    return panel.compare_candidate_profile(*values[:6], candidate_program_sha256='d' * 64,
        reference_metric_recipes=values[6], candidate_metric_recipes=values[7])


class ComparisonTests(unittest.TestCase):
    def test_complete_vector_uses_all_comparators_and_correct_group_weights(self):
        result = compare(fixture())
        self.assertEqual(len(result['groups']), 15)
        self.assertEqual(len(result['reference_profile']['runs']), 93)
        self.assertEqual(len(result['candidate_runs']), 4)
        self.assertTrue(result['numerical_comparison_complete'])
        area = original_tests.group(result, 'Area2_Bump', 'position')
        self.assertAlmostEqual(area['candidate_minus_MINT'], .02)
        # Both ten-run network averages beat this generated candidate by .025.
        self.assertAlmostEqual(area['candidate_minus_strongest_original'], -.025)
        self.assertEqual(area['strongest_original_reference_methods'], ['feedforward', 'GRU'])
        self.assertAlmostEqual(result['datasets'][0]['candidate_r2'], .32)
        phase = original_tests.group(result, 'MC_Cycle', 'phase')
        self.assertNotIn('Kalman_filter', phase['candidate_minus_method'])
        maze = original_tests.group(result, 'MC_Maze', 'position')
        self.assertIn('Naive_Bayes_regression', maze['candidate_minus_method'])
        self.assertIsNone(result['global_scalar'])
        self.assertIsNone(result['paper_win'])
        self.assertEqual(result['improvement'], 'unknown')
        self.assertFalse(result['scientific_qualification'])

    def test_failed_candidate_retains_all_groups_and_reason(self):
        values = list(fixture())
        row = values[4][1]['outputs'][0]
        row.update(status='undefined_metric', reason='Generated constant target.')
        result = compare(values)
        failed = result['candidate_runs'][1]
        self.assertEqual(failed['status'], 'undefined_metric')
        self.assertEqual(failed['reason'], 'Generated constant target.')
        for group in result['groups']:
            if group['dataset'] == 'MC_Cycle':
                self.assertIsNone(group['candidate_r2'])
                self.assertIsNone(group['candidate_minus_strongest_original'])
        self.assertEqual(len(result['groups']), 15)
        self.assertFalse(result['numerical_comparison_complete'])

    def test_missing_candidate_and_missing_comparator_cannot_be_dropped(self):
        values = list(fixture())
        values[4] = values[4][:-1]
        values[1] = [row for row in values[1] if row['outputs'][0]['key'] != 'MC_Cycle:GRU:9']
        result = compare(values)
        self.assertEqual(result['candidate_runs'][-1]['status'], 'missing_assessment')
        phase = original_tests.group(result, 'MC_Cycle', 'phase')
        self.assertAlmostEqual(phase['candidate_minus_MINT'], .02)
        self.assertIsNone(phase['candidate_minus_strongest_original'])
        self.assertIsNone(phase['candidate_minus_method']['GRU'])
        self.assertFalse(result['numerical_comparison_complete'])

    def test_all_four_original_candidate_cases_required(self):
        for mutation in ('missing', 'duplicate', 'wrong_method', 'wrong_purpose', 'acausal', 'partial'):
            with self.subTest(mutation=mutation):
                values = list(fixture())
                if mutation == 'missing': values[3] = values[3][:-1]
                elif mutation == 'duplicate': values[3][0] = copy.deepcopy(values[3][1])
                elif mutation == 'wrong_method': values[3][0]['method'] = 'GRU'
                elif mutation == 'wrong_purpose': values[3][0]['purpose'] = 'reproduce'
                elif mutation == 'acausal': values[3][0]['mode'] = 'behavior_acausal'
                elif mutation == 'partial': values[3][0]['output_dimensions'] = ['position:0']
                with self.assertRaises(ValueError): compare(values)

    def test_sample_mask_and_source_support_substitution_rejected(self):
        for changed in ('sample', 'source'):
            values = list(fixture())
            if changed == 'sample': values[5][values[3][0]['id']] = 'e' * 64
            else: values[3][0]['output_identities'][0]['source_support_sha256'] = 'e' * 64
            with self.assertRaisesRegex(ValueError, 'support'): compare(values)

    def test_candidate_cannot_change_input_metric_or_original_reference(self):
        for key in ('input_index_sha256', 'source_recipe_sha256', 'reference_source_sha256'):
            with self.subTest(key=key):
                values = list(fixture())
                values[3][0][key] = 'e' * 64
                with self.assertRaisesRegex(ValueError, 'pairing commitment'): compare(values)

    def test_stale_candidate_assessment_rejected(self):
        values = list(fixture())
        values[4][0]['outputs'][0]['commitments']['recipe'] = 'e' * 64
        with self.assertRaisesRegex(ValueError, 'commitment must match'): compare(values)

    def test_inconsistent_paired_mint_reference_rejected(self):
        values = list(fixture())
        reference = values[4][0]['outputs'][0]['reference']
        reference['per_dimension_r2'][0:2] = [.1, .1]
        reference['groups']['position'] = .1
        with self.assertRaisesRegex(ValueError, 'paired MINT values'): compare(values)

    def test_candidate_group_arithmetic_and_values_checked(self):
        for value in (True, float('nan'), float('inf'), 1.1, .8):
            values = list(fixture())
            values[4][0]['outputs'][0]['candidate']['per_dimension_r2'][0] = value
            with self.assertRaises(ValueError): compare(values)

    def test_candidate_assessments_cannot_alias_or_add_cases(self):
        values = list(fixture())
        values[4][-1] = copy.deepcopy(values[4][0])
        with self.assertRaisesRegex(ValueError, 'unique known'): compare(values)

    def test_input_immutability_and_order_independence(self):
        values = fixture()
        before = copy.deepcopy(values)
        result = compare(values)
        self.assertEqual(values, before)
        reversed_values = tuple(list(reversed(value)) if type(value) is list else value
                                for value in values)
        other = compare(reversed_values)
        for field in ('candidate_runs', 'groups', 'datasets'):
            self.assertEqual(result[field], other[field])

    def test_different_uncertainty_policies_keep_identical_metric_semantics(self):
        values = fixture()
        self.assertNotEqual(values[0][0]['metric_recipe_sha256'], values[3][0]['metric_recipe_sha256'])
        result = compare(values)
        run = result['candidate_runs'][0]
        self.assertEqual(run['uncertainty_requirements'][0]['kind'], 'prospective_paired_gain')
        self.assertEqual(run['reference_uncertainty_requirements'][0]['kind'],
                         'historical_absolute_trial_bootstrap')
        self.assertTrue(result['numerical_comparison_complete'])

    def test_metric_recipe_payload_cannot_drift_under_new_hash(self):
        for changed_period in (360.0, True):
            values = list(fixture())
            case = values[3][1]
            recipe = values[7][case['id']]
            recipe['outputs'][0]['parameters']['phase_period'] = changed_period
            case['metric_recipe_sha256'] = panel.digest(recipe)
            values[4][1]['outputs'][0]['commitments']['recipe'] = case['metric_recipe_sha256']
            with self.assertRaisesRegex(ValueError, 'identical scoring semantics'): compare(values)

    def test_unbound_recipe_and_missing_prospective_policy_rejected(self):
        for failure in ('hash', 'policy'):
            values = list(fixture())
            case = values[3][0]
            if failure == 'hash':
                case['metric_recipe_sha256'] = 'e' * 64
            else:
                case['uncertainty_requirements'] = []
                values[7][case['id']]['uncertainty_requirements'] = []
                case['metric_recipe_sha256'] = panel.digest(values[7][case['id']])
            with self.assertRaises(ValueError): compare(values)

    def test_declared_program_commitment_required(self):
        with self.assertRaisesRegex(ValueError, 'SHA256'):
            values = fixture()
            panel.compare_candidate_profile(*values[:6], candidate_program_sha256='unknown',
                reference_metric_recipes=values[6], candidate_metric_recipes=values[7])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-task', type=Path, default=SOURCE_TASK)
    args = parser.parse_args()
    SOURCE_TASK = args.source_task.resolve()
    original_tests = load('original_panel_tests', SOURCE_TASK / 'implementations/primary-profile-v1/test_panel.py')
    original_tests.panel = panel
    original_tests.SOURCE_TASK = SOURCE_TASK
    suite = unittest.TestSuite([
        unittest.defaultTestLoader.loadTestsFromTestCase(original_tests.PanelTests),
        unittest.defaultTestLoader.loadTestsFromTestCase(ComparisonTests)])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(not result.wasSuccessful())
