"""Generated arithmetic controls; no recordings, models or private targets."""
from decimal import Decimal, localcontext
import importlib.util
import math
from pathlib import Path
import sys
import types
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from poisson_deviance import MAX_COUNT, deviance_term


def oracle(y, mu):
    # Independent direct definition at 150 decimal digits, with exact input
    # float conversion. This is not the implementation's atanh series.
    with localcontext() as context:
        context.prec = 150
        a, b = Decimal(y), Decimal.from_float(mu)
        return float(2 * (b if not y else a * (a / b).ln() - a + b))


class Calls:
    def __init__(self):
        self.counts = {}

    def enter(self, name):
        self.counts[name] = self.counts.get(name, 0) + 1


def original_solver():
    # Import only the actual predecessor's pure solver/constants/authority
    # modules under a test-only name; no live issuer or fitting call is made.
    package = '_neural092_deviance_predecessor'
    path = HERE.parent / 'registered-runtime' / 'programme' / 'gain'
    module = types.ModuleType(package)
    module.__path__ = [str(path)]
    sys.modules[package] = module
    name = package + '.solver'
    spec = importlib.util.spec_from_file_location(name, path / 'solver.py')
    solver = importlib.util.module_from_spec(spec)
    sys.modules[name] = solver
    spec.loader.exec_module(solver)
    return solver


class StableDevianceTests(unittest.TestCase):
    def assertOracle(self, y, mu):
        expected = oracle(y, mu)
        actual = deviance_term(y, mu)
        self.assertTrue(math.isfinite(actual))
        self.assertGreaterEqual(actual, 0)
        self.assertTrue(math.isclose(actual, expected, rel_tol=2e-13, abs_tol=0),
                        (y, mu, actual, expected))

    def test_original_cancellation_counterexample(self):
        old = original_solver()
        mu = math.nextafter(1., 2.)
        self.assertEqual(old.deviance_term(1, mu, Calls()), 0.)
        self.assertGreater(deviance_term(1, mu), 0.)
        self.assertOracle(1, mu)

    def test_original_ratio_overflow_counterexample(self):
        old = original_solver()
        with self.assertRaises(ArithmeticError):
            old.deviance_term(1, 1e-320, Calls())
        self.assertOracle(1, 1e-320)

    def test_original_large_integer_rounding_counterexample(self):
        old = original_solver()
        mu = float(2**63)
        self.assertEqual(old.deviance_term(MAX_COUNT, mu, Calls()), 0.)
        self.assertGreater(deviance_term(MAX_COUNT, mu), 0.)
        self.assertOracle(MAX_COUNT, mu)

    def test_near_perfect_gain_preserves_prediction_order(self):
        old = original_solver()
        candidate = math.nextafter(1., math.inf)
        reference = math.nextafter(candidate, math.inf)
        self.assertEqual(old.deviance_term(1, reference, Calls())
                         - old.deviance_term(1, candidate, Calls()), 0.)
        gain = deviance_term(1, reference) - deviance_term(1, candidate)
        self.assertGreater(gain, 0.)
        self.assertTrue(math.isclose(gain, oracle(1, reference) - oracle(1, candidate),
                                    rel_tol=2e-13, abs_tol=0))

    def test_near_equal_both_sides_and_integer_precision_boundary(self):
        for y in (1, 2, 17, 10**6, 2**53 - 1, 2**53 + 1, MAX_COUNT):
            for mu in (math.nextafter(float(y), 0.), float(y),
                       math.nextafter(float(y), math.inf),
                       float(y) * (1 - 1e-8), float(y) * (1 + 1e-8)):
                with self.subTest(y=y, mu=mu):
                    self.assertOracle(y, mu)

    def test_series_boundary_and_dynamic_range(self):
        for y in (1, 7, 1000, 2**53 + 1, MAX_COUNT):
            for ratio in (0.001, 0.5, 9/11, math.nextafter(9/11, 0.),
                          0.9, 1.1, 11/9, math.nextafter(11/9, math.inf), 2., 1000.):
                with self.subTest(y=y, ratio=ratio):
                    self.assertOracle(y, float(y) * ratio)
            for mu in (math.ulp(0.), 1e-320, 1e-310, sys.float_info.min,
                       1e-200, 1e200, 1e307):
                with self.subTest(y=y, mu=mu):
                    self.assertOracle(y, mu)

    def test_zero_counts_and_equality(self):
        for mu in (math.ulp(0.), 1e-200, 1., 1e307):
            self.assertEqual(deviance_term(0, mu), 2 * mu)
        for y in (1, 2, 2**53, 2**62):
            self.assertEqual(deviance_term(y, float(y)), 0.)

    def test_invalid_inputs_and_true_overflow_are_not_clipped(self):
        for y in (-1, MAX_COUNT + 1, 1.0, True):
            with self.assertRaises(ValueError):
                deviance_term(y, 1.)
        for mu in (0., -1., math.nan, math.inf, True, 1):
            with self.assertRaises(ValueError):
                deviance_term(1, mu)
        for y in (0, 1, MAX_COUNT):
            with self.assertRaises(ArithmeticError):
                deviance_term(y, sys.float_info.max)

    def test_accounting_includes_failed_attempts_and_series_steps(self):
        calls = Calls()
        with self.assertRaises(ValueError):
            deviance_term(-1, 1., calls)
        self.assertEqual(calls.counts, {'deviance_row': 1})
        deviance_term(1, 1.1, calls)
        self.assertGreater(calls.counts['deviance_series_term'], 0)
        self.assertLessEqual(calls.counts['deviance_series_term'], 32)
        deviance_term(MAX_COUNT, math.ulp(0.), calls)
        self.assertEqual(calls.counts['log_scalar'], 2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
