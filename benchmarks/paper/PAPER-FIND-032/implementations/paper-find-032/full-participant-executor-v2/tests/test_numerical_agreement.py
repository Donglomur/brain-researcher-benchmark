"""Generated complete-product controls; no recordings or protected references.

Only artifacts, products, core, and roster definitions are imported. These
controls do not qualify participant execution or scientific conclusions.
"""
from pathlib import Path
import json
import sys
import unittest

import numpy as np


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'source'))
from find032.artifacts import numerical_agreement
from find032.core import Refusal
from find032.products import endpoint_products, validate_matrix


KEYS = tuple(sorted(endpoint_products('complete')))
ACCURACY_KEY = next(key for key in KEYS if key.score == 'accuracy')
AXES = (np.array([0., 1.]), np.array([0., 1.]))


def complete_fixture(value=0, dtype=np.uint8):
    """All 990 required products; confusion rows are valid one-hot probabilities."""
    products = {}
    for key in KEYS:
        if key.score == 'confusion':
            array = np.zeros((5, 2, 2, 4, 4), dtype=dtype)
            array[..., int(value)] = 1
        else:
            array = np.full((2, 2), value, dtype=dtype)
        validate_matrix(array, *AXES, confusion=key.score == 'confusion')
        products[key] = array
    return products


class NumericalAgreement(unittest.TestCase):
    def assert_complete_report(self, report, *, error, within, tolerance):
        self.assertEqual(set(report), {'diagnostic_only', 'qualified_reward',
            'all_cells_present', 'endpoint', 'tolerance', 'products', 'scientific_conclusion'})
        self.assertIs(report['diagnostic_only'], True)
        self.assertIsNone(report['qualified_reward'])
        self.assertIs(report['all_cells_present'], True)
        self.assertEqual(report['endpoint'], 'complete')
        self.assertEqual(report['tolerance'], tolerance)
        self.assertEqual(report['scientific_conclusion'],
                         'not inferred from significance or numerical agreement')
        self.assertEqual(len(report['products']), 990)
        self.assertEqual([row['key'] for row in report['products']],
            [[key.participant, key.stimulus, key.pipeline, key.condition, key.score] for key in KEYS])
        for row in report['products']:
            self.assertEqual(set(row), {'key', 'maximum_absolute_error', 'within_tolerance'})
            self.assertIs(type(row['maximum_absolute_error']), float)
            self.assertEqual(row['maximum_absolute_error'], error)
            self.assertIs(row['within_tolerance'], within)
        json.dumps(report, allow_nan=False)

    def test_uint8_complete_valid_fixture_has_symmetric_unit_error(self):
        zero = complete_fixture(0)
        one = complete_fixture(1)
        forward = numerical_agreement(zero, one, absolute_tolerance=1)
        reverse = numerical_agreement(one, zero, absolute_tolerance=1)
        self.assertEqual(forward, reverse)
        self.assert_complete_report(forward, error=1., within=True, tolerance=1)
        self.assert_complete_report(numerical_agreement(zero, one, absolute_tolerance=.5),
                                    error=1., within=False, tolerance=.5)

    def test_supported_integer_float_and_mixed_types_agree(self):
        dtypes = (np.uint8, np.uint16, np.uint32, np.uint64,
                  np.int8, np.int16, np.int32, np.int64,
                  np.float16, np.float32, np.float64, np.longdouble)
        for dtype in dtypes:
            for reference_dtype in (dtype, np.float64):
                with self.subTest(candidate=np.dtype(dtype).name,
                                  reference=np.dtype(reference_dtype).name):
                    zero = complete_fixture(0, dtype)
                    one = complete_fixture(1, reference_dtype)
                    forward = numerical_agreement(zero, one, absolute_tolerance=0)
                    reverse = numerical_agreement(one, zero, absolute_tolerance=0)
                    self.assertEqual(forward, reverse)
                    self.assert_complete_report(forward, error=1., within=False, tolerance=0)

    def test_identical_complete_products_have_zero_error(self):
        products = complete_fixture()
        report = numerical_agreement(products, products, absolute_tolerance=0)
        self.assert_complete_report(report, error=0., within=True, tolerance=0)

    def test_float32_subtraction_uses_at_least_float64_precision(self):
        candidate, reference = complete_fixture(dtype=np.float32), complete_fixture(dtype=np.float32)
        candidate[ACCURACY_KEY][0, 0] = np.float32(.7)
        reference[ACCURACY_KEY][0, 0] = np.float32(.1)
        expected = float(candidate[ACCURACY_KEY][0, 0]) - float(reference[ACCURACY_KEY][0, 0])
        report = numerical_agreement(candidate, reference, absolute_tolerance=expected)
        row = next(row for row in report['products'] if row['key'][-1] == 'accuracy')
        self.assertEqual(row['maximum_absolute_error'], expected)
        self.assertIs(row['within_tolerance'], True)

    @unittest.skipUnless(np.finfo(np.longdouble).eps < np.finfo(np.float64).eps,
                         'host longdouble has no precision beyond float64')
    def test_wider_float_precision_is_retained_at_tolerance_boundary(self):
        candidate, reference = complete_fixture(dtype=np.longdouble), complete_fixture(dtype=np.longdouble)
        candidate[ACCURACY_KEY][0, 0] = np.nextafter(np.longdouble(.5), np.longdouble(1))
        validate_matrix(candidate[ACCURACY_KEY], *AXES)
        report = numerical_agreement(candidate, reference, absolute_tolerance=.5)
        row = next(row for row in report['products'] if row['key'][-1] == 'accuracy')
        # The JSON float rounds to .5, but the decision uses the input precision.
        self.assertEqual(row['maximum_absolute_error'], .5)
        self.assertIs(row['within_tolerance'], False)

    def test_finite_inputs_with_nonfinite_difference_are_refused(self):
        candidate, reference = complete_fixture(dtype=np.float64), complete_fixture(dtype=np.float64)
        # A direct diagnostic call must also refuse overflow outside the product
        # probability domain, even when both input arrays are individually finite.
        candidate[ACCURACY_KEY][0, 0] = np.finfo(np.float64).max
        reference[ACCURACY_KEY][0, 0] = -np.finfo(np.float64).max
        for a, b in ((candidate, reference), (reference, candidate)):
            with self.subTest(direction=a is candidate), self.assertRaisesRegex(Refusal, 'finite.*difference'):
                numerical_agreement(a, b, absolute_tolerance=1)

    def test_population_shape_and_input_finiteness_checks_remain(self):
        products = complete_fixture(dtype=np.float64)
        missing = dict(products)
        del missing[ACCURACY_KEY]
        with self.assertRaisesRegex(Refusal, 'complete preselected endpoint'):
            numerical_agreement(missing, products, absolute_tolerance=1)
        for bad in (np.zeros((1, 2)), np.full((2, 2), np.nan), np.full((2, 2), np.inf)):
            changed = dict(products)
            changed[ACCURACY_KEY] = bad
            with self.subTest(array=repr(bad)), self.assertRaisesRegex(Refusal, 'complete finite'):
                numerical_agreement(changed, products, absolute_tolerance=1)

    def test_tolerance_validation_remains(self):
        products = complete_fixture()
        for tolerance in (-1, np.nan, np.inf, True, '1'):
            with self.subTest(tolerance=tolerance), self.assertRaisesRegex(Refusal, 'finite tolerance'):
                numerical_agreement(products, products, absolute_tolerance=tolerance)


if __name__ == '__main__':
    unittest.main(verbosity=2)
