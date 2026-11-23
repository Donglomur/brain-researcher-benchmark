"""Generated correlation-boundary regressions; no original scientific data."""

from fractions import Fraction
import importlib.util
from pathlib import Path
import sys
import unittest

spec = importlib.util.spec_from_file_location("find020_fig6_range", Path(__file__).with_name("fig6.py"))
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


class CorrelationRangeControls(unittest.TestCase):
    def test_weight_strict_boundary_does_not_round_above_into_equality(self):
        boundary = Fraction.from_float(0.01)
        epsilon = Fraction(1, 10 ** 100)
        for value, expected in ((boundary - epsilon, False),
                                (boundary, False), (boundary + epsilon, True)):
            with self.subTest(value=value):
                self.assertEqual(float(value), 0.01)
                self.assertEqual(value > 0.01, expected)
                self.assertEqual(m.like_to_like_eligible(value, 1), expected)

    def test_correlation_strict_boundary_does_not_round_above_into_equality(self):
        boundary = Fraction.from_float(0.2)
        epsilon = Fraction(1, 10 ** 100)
        for value, expected in ((boundary - epsilon, False),
                                (boundary, False), (boundary + epsilon, True)):
            with self.subTest(value=value):
                self.assertEqual(float(value), 0.2)
                self.assertEqual(value > 0.2, expected)
                self.assertEqual(m.like_to_like_eligible(1, value), expected)

    def test_out_of_range_real_cannot_round_to_valid_endpoint(self):
        epsilon = Fraction(1, 10 ** 100)
        for correlation in (Fraction(1) + epsilon, -Fraction(1) - epsilon):
            with self.subTest(correlation=correlation):
                # Demonstrate the former coercion hole independently of the fix.
                self.assertTrue(-1 <= float(correlation) <= 1)
                self.assertFalse(-1 <= correlation <= 1)
                with self.assertRaisesRegex(ValueError, "signal_correlation must lie"):
                    m.like_to_like_eligible(1, correlation)

    def test_in_range_real_support_and_signed_thresholds_are_preserved(self):
        for correlation in (1, 1.0, Fraction(1), Fraction(1) - Fraction(1, 10 ** 100)):
            with self.subTest(correlation=correlation):
                self.assertTrue(m.like_to_like_eligible(0.011, correlation))
        for weight, correlation in ((0.01, 1), (-1, 1), (1, 0.2), (1, -1), (1, Fraction(-1))):
            with self.subTest(weight=weight, correlation=correlation):
                self.assertFalse(m.like_to_like_eligible(weight, correlation))


if __name__ == "__main__":
    unittest.main()
