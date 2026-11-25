"""Generated complete-pair RMS regressions; no authentic calcium observations."""
import ast
import copy
import hashlib
import importlib.util
import math
import os
from pathlib import Path
import sys
import unittest

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = Path(os.environ.get('NEUROBENCH_SOURCE_ROOT', HERE.parents[4]))
ORIGINAL_PACKAGE = REPO / 'benchmarks/neural/NEURAL-029/implementations/neural029-programme'
sys.path.insert(0, str(ORIGINAL_PACKAGE))
from source_identity_join import bind_public_identity


def module(path):
    spec = importlib.util.spec_from_file_location('neural029_rms_controls', path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


core = module(Path(os.environ.get('NEURAL029_CORE_FILE', HERE / 'core.py')))


def fixture(value=0., prediction=0., baseline=0., warp=0., scale=1., cells=1):
    # Reuse only the existing literal generated metadata function; importing or
    # running the larger executor/FakeDocker suite is unnecessary here.
    source = ast.parse((ORIGINAL_PACKAGE / 'tests.py').read_text())
    function = next(node for node in source.body if isinstance(node, ast.FunctionDef)
                    and node.name == 'raw_fixture')
    scope = {}
    exec(compile(ast.Module(body=[function], type_ignores=[]), '<generated-metadata>', 'exec'), scope)
    index = scope['raw_fixture']()
    public = {'schema': 'neural029-public-v1', 'time_seconds': [i / 20 for i in range(61)], 'pairs': []}
    targets, predictions = [], []
    for number, pair in enumerate(index['pairs']):
        pair['source_cells_index1'] = pair['target_cells_index1'] = list(range(1, cells + 1))
        pair['registration_rows_source_target'] = [[i, i] for i in range(1, cells + 1)] + [[0, cells + 1]]
        for side in ('source', 'target'):
            pair[side + '_shape'][1] = cells
            pair[side + '_file']['bytes'] = math.prod(pair[side + '_shape']) * 8
        key = hashlib.sha256(str(number).encode()).hexdigest()
        public['pairs'].append({'pair_id': key,
            'cell_ids': [hashlib.sha256(('cell' + str(i)).encode()).hexdigest() for i in range(cells)],
            'query_ids': [hashlib.sha256(str(i).encode()).hexdigest() for i in range(2)],
            'source_delay_seconds': 1, 'target_delay_seconds': 2, 'reward_type': 'DAT',
            'calibration_trials': 4, 'validation_trials': 1,
            'file': {'path': 'public/' + key + '.npz', 'bytes': 1, 'sha256': '0' * 64}})
        y = np.broadcast_to(value, (2, cells, 61)).copy()
        x = np.broadcast_to(prediction, y.shape).copy()
        targets.append({'pair_id': key, 'mouse_id': pair['mouse_id'], 'target': y,
            'baseline': np.broadcast_to(baseline, (cells, 61)).copy(),
            'fixed_warp_baseline': np.broadcast_to(warp, (cells, 61)).copy(),
            'training_scale_squared': scale})
        predictions.append({'pair_id': key, 'values': x.tolist()})
    return ({'schema': 'neural029-predictions-v1', 'predictions': predictions}, public,
            {'pairs': targets, 'identity': bind_public_identity(index, public, '0' * 64)})


def grade(arguments):
    candidate, public, private = arguments
    return core.grade(candidate, public, lambda: private, np)


class CompleteRmsControls(unittest.TestCase):
    def assert_relative(self, actual, expected):
        self.assertNotEqual(actual, 0.)
        self.assertTrue(math.isclose(actual, expected, rel_tol=2e-15), (actual, expected))

    def test_representable_tiny_candidate_rmse_is_not_perfect(self):
        result = grade(fixture(prediction=1e-200))
        self.assert_relative(result['primary_nrmse'], 1e-200)
        for pair in result['pairs']:
            self.assert_relative(pair['rmse'], 1e-200)
            self.assert_relative(pair['nrmse'], 1e-200)
        self.assertEqual(len(result['pairs']), 3)
        self.assertEqual(len(result['mice']), 2)
        self.assertFalse(result['scientific_execution_qualified'])

    def test_tiny_baseline_and_warp_errors_remain_nonzero(self):
        result = grade(fixture(baseline=1e-200, warp=2e-200))
        self.assertEqual(result['primary_nrmse'], 0.)
        self.assert_relative(result['baseline_nrmse'], 1e-200)
        self.assert_relative(result['fixed_warp_nrmse'], 2e-200)
        self.assert_relative(result['candidate_minus_baseline'], -1e-200)
        self.assert_relative(result['candidate_minus_fixed_warp'], -2e-200)

    def test_tiny_nonconstant_targets_retain_defined_r_squared(self):
        y = np.stack([np.full((1, 61), -1e-200), np.full((1, 61), 1e-200)])
        result = grade(fixture(value=y))
        for pair in result['pairs']:
            self.assertFalse(pair['undefined_target_variance'])
            # The retained NumPy centering may leave roundoff at the unit scale.
            self.assertLessEqual(abs(pair['r_squared']), 4 * math.ulp(1.))

    def test_large_rms_is_scored_when_only_its_square_overflows(self):
        result = grade(fixture(prediction=1e200))
        self.assert_relative(result['primary_nrmse'], 1e200)
        self.assert_relative(result['pairs'][0]['rmse'], 1e200)

    def test_normalized_root_survives_underflowed_square_ratio(self):
        result = grade(fixture(prediction=1e-100, scale=1e200))
        self.assert_relative(result['primary_nrmse'], 1e-200)

    def test_subnormal_square_does_not_distort_representable_rms(self):
        result = grade(fixture(prediction=2e-162))
        self.assert_relative(result['primary_nrmse'], 2e-162)
        self.assert_relative(result['pairs'][0]['rmse'], 2e-162)

    def test_constant_nonzero_targets_have_undefined_r_squared(self):
        for value in (0.1, 1e-200):
            result = grade(fixture(value=value, prediction=value))
            self.assertTrue(all(p['undefined_target_variance'] for p in result['pairs']))
            self.assertTrue(all(p['r_squared'] is None for p in result['pairs']))

    def test_distinct_constant_cells_still_have_zero_within_cell_variance(self):
        values = np.array([0.1, -0.3]).reshape(1, 2, 1)
        result = grade(fixture(value=values, prediction=values, cells=2))
        self.assertTrue(all(p['registered_cells'] == 2 for p in result['pairs']))
        self.assertTrue(all(p['undefined_target_variance'] for p in result['pairs']))
        self.assertTrue(all(p['r_squared'] is None for p in result['pairs']))

    def test_true_zero_and_undefined_normalization_are_retained(self):
        result = grade(fixture())
        self.assertEqual(result['primary_nrmse'], 0.)
        self.assertTrue(all(p['undefined_target_variance'] for p in result['pairs']))
        self.assertTrue(all(p['r_squared'] is None for p in result['pairs']))
        absent = grade(fixture(prediction=1., scale=0.))
        self.assertIsNone(absent['primary_nrmse'])
        self.assertTrue(all(p['undefined_normalization'] for p in absent['pairs']))

    def test_final_unrepresentable_normalized_value_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'representable normalized'):
            grade(fixture(prediction=1e-200, scale=1e308))

    def test_ordinary_values_keep_existing_metric_arithmetic(self):
        y = np.tile(np.arange(61, dtype=float), (2, 1, 1))
        result = grade(fixture(value=y, prediction=y + 3, baseline=y[0] + 1,
                               warp=y[0] + 2, scale=4.))
        self.assertEqual(result['primary_nrmse'], 1.5)
        self.assertEqual(result['baseline_nrmse'], .5)
        self.assertEqual(result['fixed_warp_nrmse'], 1.)
        self.assertEqual(result['candidate_minus_baseline'], 1.)
        self.assertEqual(result['candidate_minus_fixed_warp'], .5)
        self.assertEqual(result['pairs'][0]['r_squared'], 1 - 9 / 310)


if __name__ == '__main__':
    unittest.main(verbosity=2)
