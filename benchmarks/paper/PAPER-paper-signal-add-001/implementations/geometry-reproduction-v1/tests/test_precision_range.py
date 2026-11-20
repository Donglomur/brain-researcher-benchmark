"""Focused arithmetic controls for the new projected-precision calculation."""
import importlib.util
import math
from pathlib import Path
import unittest

import numpy as np

_spec = importlib.util.spec_from_file_location(
    "stable_geometry", Path(__file__).resolve().parents[1] / "geometry.py")
geometry = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(geometry)


class PrecisionRangeTests(unittest.TestCase):
    def test_subnormal_covariance_has_representable_finite_precision(self):
        data = np.array([[-1e-160, 0.0], [1e-160, 0.0],
                         [0.0, -2e-160], [0.0, 2e-160]])
        # The old reciprocal-variance expression overflows on this input.
        with np.errstate(over="raise", divide="raise", invalid="raise"):
            result = geometry.geometry_from_coefficients(data, [0, 0, 1, 1], [1, 0])
        variance = result["covariance"][0][0]
        self.assertGreater(variance, 0)
        self.assertLess(variance, np.finfo(float).tiny)
        self.assertEqual(result["precision_status"], "finite")
        self.assertTrue(math.isfinite(result["projected_precision"]))
        self.assertTrue(math.isclose(result["projected_precision"],
                                    1 / math.sqrt(variance), rel_tol=1e-14))

    def test_ordinary_diagonal_metric_and_units_are_preserved(self):
        data = np.array([[-1.0, 0.0], [1.0, 0.0], [0.0, -2.0], [0.0, 2.0]])
        result = geometry.geometry_from_coefficients(data, [0, 0, 1, 1], [1, 1])
        self.assertTrue(math.isclose(result["projected_precision"],
                                    math.sqrt(15 / 16), rel_tol=1e-14))
        scaled = geometry.geometry_from_coefficients(data * 4, [0, 0, 1, 1], [1, 1])
        self.assertTrue(math.isclose(scaled["projected_precision"],
                                    result["projected_precision"] / 4, rel_tol=1e-14))
        self.assertEqual(scaled["angle_radians"], result["angle_radians"])

    def test_singular_covariance_keeps_undefined_precision(self):
        result = geometry.geometry_from_coefficients(
            [[-1.0, 0.0], [1.0, 0.0], [-2.0, 0.0], [2.0, 0.0]],
            [0, 0, 1, 1], [1, 0])
        self.assertIsNone(result["projected_precision"])
        self.assertEqual(result["precision_status"], "singular_at_numerical_tolerance")


if __name__ == "__main__":
    unittest.main()
