"""Generated assessment controls; no neural arrays, fits, or model executions."""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('primary_panel', HERE / 'panel.py')
panel = importlib.util.module_from_spec(spec)
spec.loader.exec_module(panel)
SOURCE_TASK = HERE.parent.parent


def fixture():
    # Independent retained scope and method roster supply dimensions/eligibility.
    runtime = SOURCE_TASK / 'implementations/paper-method-011/full-motormint-v1/runtime'
    scope = json.loads((runtime / 'SCOPE.json').read_text())
    groups = {row['id']: row['behavior']['groups'] for row in scope['datasets']
              if row['id'] in ('Area2_Bump', 'MC_Cycle', 'MC_Maze', 'MC_RTT')}
    cases, assessments, support = [], [], {}
    for dataset in ('Area2_Bump', 'MC_Cycle', 'MC_Maze', 'MC_RTT'):
        methods = [('MINT', 1), ('Wiener_filter', 1), ('Kalman_filter', 1),
                   ('feedforward', 10), ('GRU', 10)]
        if dataset == 'MC_Maze':
            methods.append(('Naive_Bayes_regression', 1))
        for method, repeats in methods:
            names = [group for group in groups[dataset]
                     if method != 'Kalman_filter' or group.startswith(('position:', 'velocity:'))]
            dimensions = [f'{name}:{j}' for group in names
                          for name, width in [group.rsplit(':', 1)] for j in range(int(width))]
            for repeat in range(repeats):
                slot = f'{dataset}:{method}:{repeat}'
                ident = 'case:' + slot
                case = {'id': ident, 'module': 'primary_behavior', 'mode': 'behavior_causal',
                        'purpose': 'reproduce', 'dataset': dataset, 'method': method,
                        'repeat': repeat, 'outputs': [slot], 'output_dimensions': dimensions,
                        'output_identities': [{'key': slot, 'estimand': 'behavior_R2',
                            'kind': 'behavior', 'selector': [], 'dimensions': dimensions,
                            'source_support_sha256': 'a' * 64}]}
                case.update({key: 'b' * 64 for key in ('input_index_sha256',
                    'metric_recipe_sha256', 'source_recipe_sha256',
                    'reference_source_sha256', 'config_sha256')})
                cases.append(case)
                support[ident] = panel.digest({'dataset': dataset, 'generated_support': True})
                values = [.1 * [group.split(':')[0] for group in groups[dataset]].index(d.rsplit(':', 1)[0])
                          + (.01 * repeat if method in ('feedforward', 'GRU') else 0)
                          for d in dimensions]
                group_values = {name.split(':')[0]: sum(values[j] for j, d in enumerate(dimensions)
                    if d.rsplit(':', 1)[0] == name.split(':')[0]) / int(name.split(':')[1]) for name in names}
                reference = {'per_dimension_r2': values, 'groups': group_values}
                assessments.append({'case': ident, 'module': 'primary_behavior',
                    'outputs': [{'key': slot, 'kind': 'behavior', 'status': 'numerically_assessed',
                        'bank_agreement': True, 'reference': reference,
                        'commitments': {'input_index': case['input_index_sha256'],
                                        'recipe': case['metric_recipe_sha256'],
                                        'source_recipe': case['source_recipe_sha256'],
                                        'artifacts': None},
                        'candidate': {'ignored': 'Candidate is not an author-reference profile.'}}]})
    return cases, assessments, support


def group(profile, dataset, name):
    return next(row for row in profile['groups'] if row['dataset'] == dataset and row['group'] == name)


class PanelTests(unittest.TestCase):
    def test_complete_source_roster_and_equal_group_weighting(self):
        result = panel.build_reference_profile(*fixture())
        self.assertEqual(len(result['runs']), 93)
        self.assertEqual(len(result['groups']), 15)
        self.assertTrue(result['numerical_profile_complete'])
        area = result['datasets'][0]['methods']
        # Seven groups each weigh1/7, not102 pooled dimensions.
        self.assertAlmostEqual(area['MINT']['dataset_r2'], .3)
        self.assertAlmostEqual(area['feedforward']['dataset_r2'], .345)
        self.assertAlmostEqual(area['Kalman_filter']['dataset_r2'], .05)
        self.assertIsNone(result['global_scalar'])
        self.assertIsNone(result['paper_win'])
        self.assertFalse(result['scientific_qualification'])

    def test_ten_runs_mean_not_best_run_selection(self):
        cases, rows, support = fixture()
        for row in rows:
            out = row['outputs'][0]
            if out['key'].startswith('MC_RTT:feedforward:'):
                value = 1.0 if out['key'].endswith(':9') else 0.0
                out['reference'] = {'per_dimension_r2': [value, value], 'groups': {'velocity': value}}
        result = panel.build_reference_profile(cases, rows, support)
        self.assertAlmostEqual(group(result, 'MC_RTT', 'velocity')['method_r2']['feedforward'], .1)

    def test_missing_run_is_preserved_and_cannot_remove_competitor(self):
        cases, rows, support = fixture()
        rows = [r for r in rows if r['outputs'][0]['key'] != 'MC_Cycle:GRU:9']
        result = panel.build_reference_profile(cases, rows, support)
        self.assertFalse(result['numerical_profile_complete'])
        self.assertEqual(sum(r['status'] == 'missing_assessment' for r in result['runs']), 1)
        item = group(result, 'MC_Cycle', 'phase')
        self.assertIn('GRU', item['method_r2'])
        self.assertIsNone(item['method_r2']['GRU'])
        self.assertIsNone(item['strongest_original_reference_r2'])
        self.assertEqual(item['strongest_original_reference_methods'], [])
        self.assertIsNotNone(item['method_r2']['MINT'])

    def test_failed_undefined_run_keeps_reason(self):
        cases, rows, support = fixture()
        rows[0]['outputs'][0] = {'key': cases[0]['outputs'][0], 'status': 'undefined_metric',
                                'reason': 'Constant generated target has zero SST.'}
        result = panel.build_reference_profile(cases, rows, support)
        self.assertEqual(result['runs'][0]['status'], 'undefined_metric')
        self.assertIn('zero SST', result['runs'][0]['reason'])
        self.assertIsNone(result['datasets'][0]['methods']['MINT']['dataset_r2'])

    def test_omitted_or_duplicate_case_rejected(self):
        cases, rows, support = fixture()
        with self.assertRaisesRegex(ValueError, '93'):
            panel.build_reference_profile(cases[:-1], rows, support)
        cases[-1] = copy.deepcopy(cases[-2])
        with self.assertRaisesRegex(ValueError, 'unique'):
            panel.build_reference_profile(cases, rows, support)

    def test_same_shape_different_sample_mask_rejected(self):
        cases, rows, support = fixture()
        support[cases[1]['id']] = 'c' * 64
        with self.assertRaisesRegex(ValueError, 'identical sample support'):
            panel.build_reference_profile(cases, rows, support)

    def test_kalman_cannot_be_assigned_original_phase(self):
        cases, rows, support = fixture()
        case = next(c for c in cases if c['dataset'] == 'MC_Cycle' and c['method'] == 'Kalman_filter')
        case['output_dimensions'] = ['phase:0'] + case['output_dimensions']
        with self.assertRaisesRegex(ValueError, 'eligible dimensions'):
            panel.build_reference_profile(cases, rows, support)

    def test_reported_group_cannot_override_dimension_arithmetic(self):
        cases, rows, support = fixture()
        rows[0]['outputs'][0]['reference']['groups']['position'] = 1.0
        with self.assertRaisesRegex(ValueError, 'arithmetic'):
            panel.build_reference_profile(cases, rows, support)

    def test_nonfinite_boolean_and_impossible_r2_rejected(self):
        for value in (float('nan'), float('inf'), True, 1.1):
            with self.subTest(value=value):
                cases, rows, support = fixture()
                rows[0]['outputs'][0]['reference']['per_dimension_r2'][0] = value
                with self.assertRaises(ValueError):
                    panel.build_reference_profile(cases, rows, support)

    def test_assessment_aliases_and_untrusted_bank_flag_rejected(self):
        cases, rows, support = fixture()
        rows[-1] = copy.deepcopy(rows[0])
        with self.assertRaisesRegex(ValueError, 'unique known'):
            panel.build_reference_profile(cases, rows, support)
        cases, rows, support = fixture()
        rows[0]['outputs'][0]['bank_agreement'] = 1
        with self.assertRaisesRegex(ValueError, 'agreement'):
            panel.build_reference_profile(cases, rows, support)

    def test_all_tied_methods_retained_and_input_immutable(self):
        values = fixture()
        before = copy.deepcopy(values)
        result = panel.build_reference_profile(*values)
        tied = group(result, 'MC_Maze', 'position')['strongest_original_reference_methods']
        self.assertEqual(tied, ['feedforward', 'GRU'])
        self.assertEqual(values, before)

    def test_case_and_assessment_order_do_not_change_profile(self):
        cases, rows, support = fixture()
        a = panel.build_reference_profile(cases, rows, support)
        b = panel.build_reference_profile(list(reversed(cases)), list(reversed(rows)), support)
        self.assertEqual(a['runs'], b['runs'])
        self.assertEqual(a['groups'], b['groups'])
        self.assertEqual(a['datasets'], b['datasets'])

    def test_numeric_assessment_requires_complete_scorer_commitments(self):
        for removed in (None, 'input_index', 'recipe', 'source_recipe', 'artifacts'):
            with self.subTest(removed=removed):
                cases, rows, support = fixture()
                if removed is None:
                    del rows[0]['outputs'][0]['commitments']
                else:
                    del rows[0]['outputs'][0]['commitments'][removed]
                with self.assertRaisesRegex(ValueError, 'scorer commitments'):
                    panel.build_reference_profile(cases, rows, support)

    def test_reused_case_id_cannot_attribute_old_assessment_to_changed_case(self):
        for field in ('input_index_sha256', 'metric_recipe_sha256', 'source_recipe_sha256'):
            with self.subTest(field=field):
                cases, rows, support = fixture()
                cases[0][field] = 'c' * 64
                with self.assertRaisesRegex(ValueError, 'commitment must match current case'):
                    panel.build_reference_profile(cases, rows, support)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-task', type=Path, default=SOURCE_TASK)
    args, remaining = parser.parse_known_args()
    SOURCE_TASK = args.source_task.resolve()
    unittest.main(argv=[sys.argv[0], *remaining])
