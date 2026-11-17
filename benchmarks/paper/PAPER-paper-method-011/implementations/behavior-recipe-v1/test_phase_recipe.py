"""Generated software controls; no authentic arrays, targets, or native models."""
import copy
import importlib.util
import math
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
RUNTIME = HERE.parent / 'paper-method-011/full-motormint-v1/runtime'
sys.path.insert(0, str(RUNTIME))
from mintbench import bindings, numerics
from mintbench.validation import digest


def source_case(dataset='MC_Cycle', *, linear=False):
    dimensions = bindings.dimensions(dataset)
    if linear:
        dimensions = [d for d in dimensions if not d.startswith('phase:')]
        key = 'MC_Cycle:linear:on:causal:1'
        module = 'factorial_ablations'
        factors = {'readout': 'linear', 'interpolation': 'on', 'direction': 'causal'}
        selector, selected = ['per_dimension_r2', 0], ['angular_velocity:0']
    else:
        key, module, factors = 'behavior', 'primary_behavior', {}
        selector, selected = [], dimensions
    case = {'module': module, 'dataset': dataset, 'method': 'MINT', 'repeat': 0,
            'factors': factors, 'output_dimensions': dimensions,
            'mode': 'behavior_causal', 'outputs': [key], 'uncertainty_requirements': []}
    case['output_identities'] = [{'key': key, 'estimand': 'behavior_R2',
                                 'kind': 'behavior', 'selector': selector,
                                 'dimensions': selected, 'source_support_sha256': '1' * 64}]
    groups = {}
    for column, dimension in enumerate(dimensions):
        groups.setdefault(dimension.rsplit(':', 1)[0], []).append(column)
    phase = [j for j, d in enumerate(dimensions) if d.startswith('phase:')]
    recipe = {'experiment_sha256': digest(bindings.experiment(case)),
              'outputs': [{'key': key, 'kind': 'behavior', 'value_selector': selector,
                           'parameters': {'groups': groups, 'circular_columns': phase,
                                          'phase_period': 1.0 if phase else None}}],
              'uncertainty_requirements': []}
    return case, recipe


def historical_validator():
    spec = importlib.util.spec_from_file_location(
        'mintbench._historical_phase_bindings',
        HERE / 'historical/bindings.before-phase-repair.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.validate_recipe


class PhaseRecipeTests(unittest.TestCase):
    def test_generated_witness_changes_endpoint_and_old_validator_accepts_it(self):
        case, correct = source_case()
        incorrect = copy.deepcopy(correct)
        incorrect['outputs'][0]['parameters'].update(circular_columns=[], phase_period=None)
        historical_validator()(case, incorrect)
        with self.assertRaisesRegex(ValueError, 'circular columns'):
            bindings.validate_recipe(case, incorrect)
        # Hand calculation for phase measured in cycles: a wrap crossing is an
        # error of .02, not .98. The scoring banks remain unchanged.
        payload = {'truth': [[.99], [.01], [.02]], 'prediction': [[.01], [.01], [.02]],
                   'groups': {'phase': [0]}, 'circular_columns': [0], 'phase_period': 1.0}
        circular = numerics.evaluate('behavior', payload)['value']['groups']['phase']
        linear = numerics.evaluate('behavior', dict(payload, circular_columns=[],
                                                   phase_period=None))['value']['groups']['phase']
        self.assertGreater(circular, 0.14)
        self.assertLess(linear, -0.50)
        self.assertGreater(circular - linear, .65)

    def test_primary_original_phase_is_accepted(self):
        case, recipe = source_case()
        bindings.validate_recipe(case, recipe)
        self.assertEqual(case['output_dimensions'][0], 'phase:0')
        self.assertEqual(len(case['output_dimensions']), 13)

    def test_no_nonphase_or_partial_circular_assignment(self):
        for columns in ([], [1], [0, 1], [0, 0], [True], [0.0]):
            with self.subTest(columns=columns):
                case, recipe = source_case()
                recipe['outputs'][0]['parameters']['circular_columns'] = columns
                with self.assertRaises(ValueError):
                    bindings.validate_recipe(case, recipe)

    def test_phase_period_must_be_finite_positive_not_boolean(self):
        for period in (None, True, 0, -1, math.inf, math.nan):
            with self.subTest(period=period):
                case, recipe = source_case()
                recipe['outputs'][0]['parameters']['phase_period'] = period
                with self.assertRaises((ValueError, TypeError)):
                    bindings.validate_recipe(case, recipe)

    def test_source_units_are_not_inferred(self):
        # Arithmetic periods are accepted without claiming native equivalence.
        for period in (1.0, math.tau, 360.0):
            case, recipe = source_case()
            recipe['outputs'][0]['parameters']['phase_period'] = period
            bindings.validate_recipe(case, recipe)

    def test_other_primary_datasets_remain_linear(self):
        for dataset in ('Area2_Bump', 'MC_Maze', 'MC_RTT'):
            with self.subTest(dataset=dataset):
                case, recipe = source_case(dataset)
                bindings.validate_recipe(case, recipe)
                recipe['outputs'][0]['parameters'].update(circular_columns=[0], phase_period=1.0)
                with self.assertRaises(ValueError):
                    bindings.validate_recipe(case, recipe)

    def test_source_linear_readout_phase_exclusion_is_preserved(self):
        case, recipe = source_case(linear=True)
        self.assertEqual(len(case['output_dimensions']), 12)
        bindings.validate_recipe(case, recipe)
        recipe['outputs'][0]['parameters']['phase_period'] = 1.0
        with self.assertRaisesRegex(ValueError, 'no phase period'):
            bindings.validate_recipe(case, recipe)

    def test_valid_input_is_not_mutated(self):
        case, recipe = source_case()
        before = copy.deepcopy((case, recipe))
        bindings.validate_recipe(case, recipe)
        self.assertEqual((case, recipe), before)

    def test_nlb_velocity_readout_retains_its_separate_recipe(self):
        case = {'module': 'nlb_neural_state', 'dataset': 'MC_Maze', 'method': 'MINT',
                'repeat': 0, 'factors': {}, 'output_dimensions': ['velocity:0', 'velocity:1'],
                'mode': 'neural_acausal', 'outputs': ['MC_Maze:velocity_R2'],
                'uncertainty_requirements': []}
        case['output_identities'] = [{'key': case['outputs'][0], 'estimand': 'nlb_velocity_R2',
                                     'kind': 'behavior', 'selector': ['groups', 'velocity'],
                                     'dimensions': case['output_dimensions'],
                                     'source_support_sha256': '1' * 64}]
        recipe = {'experiment_sha256': digest(bindings.experiment(case)),
                  'outputs': [{'key': case['outputs'][0], 'kind': 'behavior',
                               'value_selector': ['groups', 'velocity'],
                               'parameters': {'ridge': 1.0, 'metric': {
                                   'groups': {'velocity': [0, 1]},
                                   'circular_columns': [], 'phase_period': None}}}],
                  'uncertainty_requirements': []}
        bindings.validate_recipe(case, recipe)


if __name__ == '__main__':
    unittest.main()
