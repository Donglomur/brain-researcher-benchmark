"""Generated stdlib controls for the secondary MotorMINT Pearson diagnostic.

Only the named public numerical/validation function bodies are executed. No
package initialization, native bank, campaign, data or protected reference runs.
"""
import ast
from decimal import Decimal, localcontext
import hashlib
import json
import math
from pathlib import Path
import random
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = Path('benchmarks/paper/PAPER-paper-method-011/implementations/paper-method-011/full-motormint-v1')
SCORING = PACKAGE / 'runtime/mintbench/scoring.py'
VALIDATION = PACKAGE / 'runtime/mintbench/validation.py'
BINDINGS = Path('benchmarks/integrity/current-closures/numeric-motormint/SOURCE_BINDINGS.json')
HISTORICAL_SCORING = {
    'bytes': 15797,
    'sha256': 'cf52f9bd90a2545c35df0cc48d6b7af4d1b664ae9b85a877b2fc35c4bf362c1f',
}


def load_functions(path, names, namespace):
    tree = ast.parse(path.read_bytes(), filename=str(path))
    bodies = [node for node in tree.body
              if isinstance(node, ast.FunctionDef) and node.name in names]
    if {node.name for node in bodies} != set(names):
        raise AssertionError('Exact reviewed numerical function set')
    exec(compile(ast.Module(body=bodies, type_ignores=[]), str(path), 'exec'), namespace)


def decimal_pearson(truth, prediction):
    """Independent high-precision centered-sums definition on the supplied values."""
    with localcontext() as context:
        context.prec = 100
        y = [Decimal(value) for value in truth]
        p = [Decimal(value) for value in prediction]
        my, mp = sum(y) / len(y), sum(p) / len(p)
        y = [value - my for value in y]
        p = [value - mp for value in p]
        denominator = (sum(value * value for value in y)
                       * sum(value * value for value in p)).sqrt()
        return float(sum(a * b for a, b in zip(y, p)) / denominator)


class MotorMintPearsonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        namespace = {'math': math}
        load_functions(ROOT / VALIDATION, {'need', 'finite', 'vector', 'matrix'}, namespace)
        load_functions(ROOT / SCORING, {'_centered_unit_vector', 'behavior_diagnostics'}, namespace)
        cls.diagnostics = staticmethod(namespace['behavior_diagnostics'])

    def result(self, truth, prediction):
        return self.diagnostics({
            'truth': [[value] for value in truth],
            'prediction': [[value] for value in prediction],
            'circular_columns': [], 'phase_period': 2 * math.pi,
        })['per_dimension'][0]

    def assert_pearson(self, truth, prediction, expected=None):
        row = self.result(truth, prediction)
        expected = decimal_pearson(truth, prediction) if expected is None else expected
        self.assertIsInstance(row['pearson'], float)
        self.assertTrue(math.isfinite(row['pearson']))
        self.assertGreaterEqual(row['pearson'], -1.0)
        self.assertLessEqual(row['pearson'], 1.0)
        self.assertAlmostEqual(row['pearson'], expected, delta=3e-14)
        self.assertIsNone(row['undefined_reason'])
        return row

    def test_reported_finite_denominator_overflow_witnesses(self):
        first = self.assert_pearson([-100., 0., 100.], [-1e153, 0., 1e153], 1.)
        self.assertEqual(first['mean_absolute_error'], 2e153 / 3)
        same = self.assert_pearson([-1e100, 0., 1e100], [-1e100, 0., 1e100], 1.)
        self.assertEqual(same['mean_absolute_error'], 0.)

    def test_positive_negative_and_zero_correlation(self):
        self.assert_pearson([-3, -1, 1, 3], [-6, -2, 2, 6], 1.)
        self.assert_pearson([-3, -1, 1, 3], [6, 2, -2, -6], -1.)
        self.assert_pearson([-1, -1, 1, 1], [-1, 1, -1, 1], 0.)

    def test_subnormal_and_maximum_finite_scales(self):
        tiny = math.ulp(0.)
        self.assert_pearson([-tiny, 0., tiny], [-1., 0., 1.], 1.)
        self.assert_pearson([tiny, 2 * tiny, 3 * tiny], [3., 2., 1.], -1.)
        large = sys.float_info.max
        self.assert_pearson([-large, 0., large], [-large, 0., large], 1.)
        self.assert_pearson([large / 2, large * .75, large], [1., 3., 2.])

    def test_translation_at_float_resolution_and_exact_integer_differences(self):
        offset = 1e200
        step = math.ulp(offset)
        for sign in (-1, 1):
            truth = [sign * (offset + index * step) for index in (0, 1, 3, 7)]
            self.assert_pearson(truth, [2., -1., 4., 3.])
        for sign in (-1, 1):
            truth = [sign * (2**100 + index) for index in (0, 1, 3, 7)]
            self.assert_pearson(truth, [2, -1, 4, 3])
            truth[0] = float(truth[0])
            self.assert_pearson(truth, [2, -1, 4, 3])

    def test_generated_scale_translation_and_symmetry_against_decimal(self):
        randomizer = random.Random(11016)
        exponents = (-1000, -500, -20, 0, 20, 500, 1000)
        for index in range(42):
            truth = [randomizer.randrange(-100, 101) / 32 for _ in range(17)]
            prediction = [value / 2 + randomizer.randrange(-100, 101) / 64 for value in truth]
            y = [math.ldexp(value + 16, exponents[index % 7]) for value in truth]
            p = [math.ldexp(value - 16, exponents[(index * 3 + 1) % 7]) for value in prediction]
            with self.subTest(index=index):
                forward = self.assert_pearson(y, p)
                reverse = self.assert_pearson(p, y)
                self.assertAlmostEqual(forward['pearson'], reverse['pearson'], delta=1e-15)
                self.assertAlmostEqual(forward['pearson'], decimal_pearson(truth, prediction), delta=3e-14)

    def test_every_row_participates_in_nonperfect_correlation(self):
        truth = [-2., -1., 0., 1., 2., 3.]
        prediction = [-2., -1., 0., 1., 2., -9.]
        row = self.assert_pearson(truth, prediction)
        self.assertLess(row['pearson'], 0.)
        self.assertEqual(row['mean_absolute_error'], 2.)

    def test_constant_and_single_row_policy_remains_explicit(self):
        for truth, prediction in (([2., 2.], [1., 3.]), ([1., 3.], [2., 2.]),
                                  ([0., 0.], [0., 0.]), ([4.], [9.])):
            with self.subTest(truth=truth, prediction=prediction):
                row = self.result(truth, prediction)
                self.assertIsNone(row['pearson'])
                self.assertEqual(row['undefined_reason'], 'Undefined constant truth/prediction variance')

    def test_circular_policy_units_and_dimension_order_remain_unchanged(self):
        value = self.diagnostics({
            'truth': [[0., -1.], [3., 0.], [6., 1.]],
            'prediction': [[9., -2.], [5., 0.], [4., 2.]],
            'circular_columns': [0], 'phase_period': 10.,
        })
        self.assertTrue(value['original_units_preserved'])
        self.assertEqual(value['per_dimension'][0], {
            'mean_absolute_error': 5 / 3, 'pearson': None,
            'undefined_reason': 'Circular correlation requires independently bound native policy',
        })
        self.assertEqual(value['per_dimension'][1]['mean_absolute_error'], 2 / 3)
        self.assertAlmostEqual(value['per_dimension'][1]['pearson'], 1.)
        self.assertIsNone(value['per_dimension'][1]['undefined_reason'])

    def test_validation_still_rejects_nonfinite_boolean_and_incomplete_support(self):
        for truth, prediction in (([1., float('nan')], [1., 2.]),
                                  ([1., 2.], [1., float('inf')]),
                                  ([True, 2.], [1., 2.]),
                                  ([1., 2.], [1.]), ([], [])):
            with self.subTest(truth=truth, prediction=prediction):
                with self.assertRaises(ValueError):
                    self.result(truth, prediction)
        with self.assertRaises(ValueError):
            self.diagnostics({'truth': [[1.], [2., 3.]], 'prediction': [[1.], [2.]],
                              'circular_columns': [], 'phase_period': 10.})

    def test_explicit_current_binding_retains_historical_and_disabled_contracts(self):
        bindings = json.loads((ROOT / BINDINGS).read_bytes())
        self.assertEqual(bindings['schema'], 'motormint_current_numeric_source_bindings_v1')
        self.assertEqual(bindings['task_id'], 'PAPER-paper-method-011')
        self.assertFalse(bindings['execution_authority'])
        self.assertFalse(bindings['scientific_qualification'])
        self.assertEqual(bindings['historical_scoring'], dict(path=str(SCORING), **HISTORICAL_SCORING))
        self.assertEqual([row['path'] for row in bindings['current_sources']], [str(SCORING)])
        for group in ('current_sources', 'unchanged_dependencies', 'historical_manifests',
                      'unchanged_contracts', 'regression_tests'):
            for pin in bindings[group]:
                with self.subTest(group=group, path=pin['path']):
                    body = (ROOT / pin['path']).read_bytes()
                    self.assertEqual(len(body), pin['bytes'])
                    self.assertEqual(hashlib.sha256(body).hexdigest(), pin['sha256'])
        manifest = json.loads((ROOT / PACKAGE / 'SOURCE_MANIFEST.json').read_bytes())
        self.assertEqual(manifest['files']['runtime/mintbench/scoring.py'], HISTORICAL_SCORING)
        self.assertEqual(manifest['runtime_files']['mintbench/scoring.py'], HISTORICAL_SCORING)
        status = json.loads((ROOT / PACKAGE / 'PUBLIC_STATUS.json').read_bytes())
        self.assertEqual(status['canonical_task'], 'PAPER-paper-method-011')
        self.assertEqual(status['deployment'], 'disabled')
        self.assertFalse(status['scientific_qualification'])
        self.assertFalse(status['submission_ready'])
        self.assertEqual(len(status['all_original_gates']), 17)
        self.assertTrue(all(gate['status'] == 'unresolved' and not gate['scope_removal_allowed']
                            for gate in status['all_original_gates']))
        self.assertFalse(json.loads((ROOT / PACKAGE / 'DEPLOYMENT.json').read_bytes())['enabled'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
