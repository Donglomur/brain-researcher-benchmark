"""Generated scale controls for the unchanged population-SD d-prime metric."""
import argparse
import importlib.util
from pathlib import Path
import sys
import unittest

import numpy as np

SOURCE = Path(__file__).resolve().parents[1] / "evaluator.py"


class DprimeStabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("dprime_stability_source", SOURCE)
        cls.e = importlib.util.module_from_spec(spec)
        raw = SOURCE.read_bytes()
        exec(compile(raw, str(SOURCE), "exec"), cls.e.__dict__)

    def test_extreme_scales_preserve_signed_per_neuron_effect(self):
        x = np.array([[1., 3.], [-1., 1.]])
        y = np.array([[-1., 1.], [1., 3.]])
        for scale in (1., 1e200, 1e-200):
            with self.subTest(scale=scale), np.errstate(over="ignore", under="ignore", invalid="ignore"):
                actual = self.e.dprime(x * scale, y * scale)
                np.testing.assert_allclose(actual, [2., -2.], rtol=2e-15, atol=0)
                self.assertTrue(np.isfinite(actual).all())
        # Different neuron scales must not be pooled into one common scalar.
        actual = self.e.dprime([[1e200, 3e200], [-1e-200, 1e-200]],
                               [[-1e200, 1e200], [1e-200, 3e-200]])
        np.testing.assert_allclose(actual, [2., -2.], rtol=2e-15, atol=0)

    def test_weighted_population_sd_and_small_defined_dispersion(self):
        # Means1.5 and0.5, both population SD sqrt(3)/2: d-prime=2/sqrt(3).
        for scale in (1., 1e200, 1e-200):
            x = np.array([[0., 2.]]) * scale
            with self.subTest(scale=scale):
                np.testing.assert_allclose(self.e.dprime(x, x, [1, 3], [3, 1]),
                                           [2 / np.sqrt(3)], rtol=2e-15, atol=0)
        np.testing.assert_allclose(self.e.dprime([[1., 3.]], [[-1., 1.]],
                                                [1e308, 1e308], [1e308, 1e308]),
                                   [2.], rtol=2e-15, atol=0)
        # The first arm is constant; only the much smaller second arm has SD.
        np.testing.assert_allclose(self.e.dprime([[1., 1.]], [[1e-200, 3e-200]]),
                                   [2e200], rtol=2e-15, atol=0)
        # The original unequal-SD formula is arithmetic SD, not pooled variance.
        np.testing.assert_allclose(self.e.dprime([[2, 6]], [[0, 2]]), [2.])

    def test_zero_variance_and_invalid_weights_keep_original_policy(self):
        for value in (0., 0.1, 1e200, 1e-200):
            actual = self.e.dprime(np.full((1, 2), value), np.full((1, 10), value),
                                   [0.3, 0.7], list(range(1, 11)))
            self.assertTrue(np.isnan(actual[0]))
        for weights in ([0, 1], [-1, 1], [float("inf"), 1]):
            with self.subTest(weights=weights), self.assertRaises(self.e.ContractError):
                self.e.dprime([[0., 2.]], [[0., 2.]], weights, [1, 1])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--source", type=Path)
    args, remaining = parser.parse_known_args()
    if args.source is not None:
        SOURCE = args.source
    unittest.main(argv=[sys.argv[0], *remaining])
