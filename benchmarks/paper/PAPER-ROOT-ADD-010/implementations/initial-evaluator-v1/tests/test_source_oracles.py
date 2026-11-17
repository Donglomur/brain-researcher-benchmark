"""Independent hand-derived numerical controls; no empirical paper data.

Derivations were frozen from the pinned author calls and rsatoolbox v0.1.5
reference formulas before exercising this implementation. The latter is an
algorithm reference, not an established historical environment pin.
"""
import importlib.util
from pathlib import Path
import unittest

import numpy as np


SPEC = importlib.util.spec_from_file_location(
    "root010_source_oracles", Path(__file__).resolve().parents[1] / "sensor_rsa.py"
)
rsa = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rsa)


class SourceOracles(unittest.TestCase):
    def test_unequal_counts_pool_training_trials(self):
        # Run-wise A observations: [0], [2,2], [4,4,4]; B is always zero.
        # Held-out products are 0, 2*(12/4)=6, 4*(4/3)=16/3.
        # Mean=34/9. Averaging run means would instead produce 8/3.
        data, shapes, runs = [], [], []
        for run, copies, a in (("01", 1, 0), ("02", 2, 2), ("03", 3, 4)):
            for shape, value in (("A", a), ("B", 0)):
                for _ in range(copies):
                    data.append([[value]])
                    shapes.append(shape)
                    runs.append(run)
        result, counts = rsa.crossnobis(data, shapes, runs, shape_order=("A", "B"))
        self.assertAlmostEqual(result[0, 0], 34 / 9, places=13)
        self.assertEqual(counts["03"], {"A": 3, "B": 3})
        self.assertGreater(abs(result[0, 0] - 8 / 3), 1)

    def test_negative_crossvalidated_distance_retained(self):
        # Opposite contrasts across runs: (1-0)*(-1-0)=-1.
        data = np.array([1, 0, -1, 0], dtype=float).reshape(4, 1, 1)
        result, _ = rsa.crossnobis(data, ["A", "B", "A", "B"],
                                  ["01", "01", "02", "02"],
                                  shape_order=("A", "B"))
        self.assertEqual(result[0, 0], -1)

    def test_channel_average_is_not_channel_sum(self):
        # Identical noiseless contrasts [2,4] in each run: (4+16)/2=10.
        data = np.array([[2, 4], [0, 0], [2, 4], [0, 0]], float)[:, :, None]
        result, _ = rsa.crossnobis(data, ["A", "B", "A", "B"],
                                  ["01", "01", "02", "02"],
                                  shape_order=("A", "B"))
        self.assertEqual(result[0, 0], 10)

    def test_savgol_quadratic_preservation_including_edges(self):
        # Degree-2 smoothing should preserve a degree-2 trajectory at edges
        # as well as in the interior under the source's interpolation mode.
        t = np.linspace(-1, 1, 31)
        a = 1 + 2 * t + 3 * t ** 2
        data = np.stack((a, np.zeros_like(a), a, np.zeros_like(a)))[:, None, :]
        result, _ = rsa.crossnobis(data, ["A", "B", "A", "B"],
                                  ["01", "01", "02", "02"],
                                  shape_order=("A", "B"), smooth=True)
        np.testing.assert_allclose(result[:, 0], a ** 2, atol=1e-11, rtol=1e-12)

    def test_covariance_weighted_correlation_known_value(self):
        # For pairs 01,02,03,12,13,23 the identity-pattern covariance has
        # diagonal 4, shared-vertex entries 1 and disjoint-pair entries 0.
        # Solving that fixed six-by-six system gives the value below.
        x = np.array([[0, 1, 2, 3, 4, 5]], float)
        y = np.array([[1, 0, 4, 2, 8, 3]], float)
        result = rsa.corr_cov(x, y, n_shapes=4)[0, 0]
        self.assertAlmostEqual(result, 0.5765999761251577, places=13)
        self.assertGreater(abs(result - np.corrcoef(x[0], y[0])[0, 1]), 0.02)
        self.assertAlmostEqual(rsa.corr_cov(3 * x + 90, 7 * y - 12, n_shapes=4)[0, 0],
                               result, places=13)
        self.assertAlmostEqual(rsa.corr_cov(x, -x, n_shapes=4)[0, 0], -1, places=13)

    def test_undefined_and_incomplete_inputs_rejected(self):
        with self.assertRaisesRegex(ValueError, "constant"):
            rsa.corr_cov(np.ones((1, 6)), np.arange(6)[None, :], n_shapes=4)
        with self.assertRaisesRegex(ValueError, "every observed run"):
            rsa.crossnobis(np.zeros((3, 1, 1)), ["A", "B", "A"],
                           ["01", "01", "02"], shape_order=("A", "B"))

    def test_sensor_population_keeps_documented_missing_runs(self):
        self.assertEqual(rsa.SUBJECTS, tuple(f"sub-{i:02}" for i in range(1, 21)))
        self.assertEqual(set(rsa.RUNS["sub-10"]), {f"{i:02}" for i in range(1, 8)})
        self.assertEqual(set(rsa.RUNS["sub-11"]), {f"{i:02}" for i in range(1, 8)})
        self.assertEqual(sum(len(r) for r in rsa.RUNS.values()), 158)
        self.assertEqual(len(rsa.TIMES), 301)
        np.testing.assert_allclose(rsa.TIMES[[0, 25, 225, -1]], [-.1, 0, .8, 1.1])


if __name__ == "__main__":
    unittest.main()
