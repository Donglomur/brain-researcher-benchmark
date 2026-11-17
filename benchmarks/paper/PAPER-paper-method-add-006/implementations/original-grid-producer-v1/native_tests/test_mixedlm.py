"""Required genuine generated MixedLM seam; missing dependency fails, never skips.

This separate suite has not been executed locally. It requires an independently
admitted environment with statsmodels and does not read authentic rat data.
"""
import importlib.util
import importlib.metadata
from pathlib import Path
import sys
import unittest

import numpy as np
import statsmodels  # explicit failure if the native dependency is unavailable

SPEC = importlib.util.spec_from_file_location(
    'geometry_results_native_mixedlm', Path(__file__).resolve().parents[1] / 'geometry_results.py')
G = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = G
SPEC.loader.exec_module(G)


class NativeMixedLMControl(unittest.TestCase):
    def test_balanced_random_intercept_fixed_effects_equal_independent_ols(self):
        expected_versions = {"numpy": "2.2.6", "scipy": "1.15.3", "scikit-learn": "1.6.1",
                             "statsmodels": "0.14.5", "pandas": "2.2.3", "patsy": "1.0.1"}
        self.assertEqual({key: importlib.metadata.version(key) for key in expected_versions}, expected_versions)
        # Identical complete time grids for every group make fixed-effect GLS
        # estimates equal the pooled OLS solution in this random-intercept model.
        # This is an independent algebraic oracle, not a call to MixedLM twice.
        time = np.arange(8, dtype=float)
        subject_intercepts = np.array([-2.1, -1.2, -.8, -.2, .3, .9, 1.3, 1.8])
        residual = np.random.RandomState(644).normal(0, .15, (8, 8))
        data = 3 + .3 * time - .02 * time ** 2 + subject_intercepts[:, None] + residual
        design = np.tile(np.column_stack([np.ones(8), time, time ** 2]), (8, 1))
        expected, *_ = np.linalg.lstsq(design, data.ravel(), rcond=None)
        result = G.mixed_trend(data, quadratic=True)
        coefficients = [result['fixed_parameters'][name] for name in
                        ('Intercept', 'time', 'time_squared')]
        np.testing.assert_allclose(coefficients, expected, rtol=1e-7, atol=1e-8)
        np.testing.assert_allclose(result['fitted_values'], design[:8] @ expected,
                                   rtol=1e-7, atol=1e-8)
        self.assertTrue(result['converged'])
        self.assertTrue(result['reml'])
        self.assertEqual(result['observations'], 64)
        self.assertEqual(result['independent_animals'], 8)
        self.assertEqual(result['runtime']['statsmodels'], statsmodels.__version__)
        self.assertTrue(all(np.isfinite(p) and 0 <= p <= 1 for p in result['fixed_pvalues'].values()))


if __name__ == '__main__':
    unittest.main()
