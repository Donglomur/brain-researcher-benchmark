"""Analytical software controls only; no empirical data or fitted models."""
import importlib.util
import math
from pathlib import Path
import unittest

import numpy as np

spec = importlib.util.spec_from_file_location("geometry", Path(__file__).with_name("geometry.py"))
geometry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(geometry)


def draws():
    return {
        "sigma_uniform": np.full((2, 2), 0.5),
        "independent_normal": np.zeros((2, 200, 2)),
        "signal_normal": np.vstack((np.ones(200), np.full(200, 3))),
        "common_normal": np.full(400, 0.5),
        "permutations": np.tile(np.arange(200), (2, 2, 1)),
    }


class SourceTransformControls(unittest.TestCase):
    def test_source_parameters_and_all_dimension_signal_noise(self):
        d = draws()
        d["independent_normal"][0, 7, 1] = 1.25
        result = geometry.replay_simulation(d)
        data = np.asarray(result["data"])
        np.testing.assert_allclose(data[0], [13, 3])
        np.testing.assert_allclose(data[7], [13, 5.5])
        np.testing.assert_allclose(data[200], [6.6, 1.6])
        np.testing.assert_array_equal(result["labels"], np.repeat([0, 1], 200))

    def test_shuffles_preserve_exact_category_neuron_marginals(self):
        d = draws()
        d["independent_normal"] = np.arange(800).reshape(2, 200, 2) / 100
        d["permutations"][0] = np.arange(199, -1, -1)
        d["permutations"][1] = np.roll(np.arange(200), 17)
        result = geometry.replay_simulation(d)
        original, shuffled = np.asarray(result["data"]), np.asarray(result["data_scrambled"])
        self.assertFalse(np.array_equal(original, shuffled))
        for group in range(2):
            a, b = original[group * 200:(group + 1) * 200], shuffled[group * 200:(group + 1) * 200]
            np.testing.assert_array_equal(np.sort(a, axis=0), np.sort(b, axis=0))
        np.testing.assert_allclose(shuffled[0, 0], original[199, 0])
        np.testing.assert_allclose(shuffled[0, 1], original[183, 1])

    def test_invalid_draws_do_not_get_repaired(self):
        for field, replacement in [
            ("sigma_uniform", np.ones((2, 2))),
            ("common_normal", np.full(400, np.nan)),
            ("permutations", np.zeros((2, 2, 200), dtype=int)),
            ("permutations", np.tile(np.arange(200, dtype=float), (2, 2, 1))),
        ]:
            with self.subTest(field=field):
                d = draws()
                d[field] = replacement
                with self.assertRaises(ValueError):
                    geometry.replay_simulation(d)


class GeometryControls(unittest.TestCase):
    data = [[-2, -1], [2, -1], [-2, 1], [2, 1]]
    labels = [0, 0, 1, 1]

    def test_known_orthogonal_axes_precision_and_covariance(self):
        result = geometry.geometry_from_coefficients(self.data, self.labels, [0, 2])
        np.testing.assert_allclose(result["covariance"], [[16 / 3, 0], [0, 4 / 3]])
        self.assertAlmostEqual(result["angle_degrees"], 90)
        self.assertAlmostEqual(result["projected_precision"], math.sqrt(3) / 2)
        self.assertEqual(result["mean_projection_sd"], 0)
        parallel = geometry.geometry_from_coefficients(self.data, self.labels, [2, 0])
        self.assertAlmostEqual(parallel["angle_degrees"], 0)
        self.assertAlmostEqual(parallel["projected_precision"], math.sqrt(3) / 4)
        self.assertAlmostEqual(parallel["mean_projection_sd"], math.sqrt(8))

    def test_class_sd_average_is_neither_variance_nor_pooled_sd(self):
        result = geometry.geometry_from_coefficients([[-1, 0], [1, 0], [-3, 2], [3, 2]], self.labels, [1, 0])
        self.assertAlmostEqual(result["mean_projection_sd"], 2 * math.sqrt(2))
        self.assertNotAlmostEqual(result["mean_projection_sd"], math.sqrt(20 / 3))
        self.assertNotAlmostEqual(result["mean_projection_sd"], 10)

    def test_sign_scale_translation_and_rotation_invariance(self):
        data = np.asarray(self.data, dtype=float)
        beta = np.array([2.0, -1.0])
        rotation = np.array([[0.6, -0.8], [0.8, 0.6]])
        expected = geometry.geometry_from_coefficients(data, self.labels, beta)
        for x, b in [(data + [17, -31], beta), (data, -19 * beta), (data @ rotation, beta @ rotation)]:
            result = geometry.geometry_from_coefficients(x, self.labels, b)
            for key in ["angle_degrees", "mean_projection_sd", "projected_precision"]:
                self.assertAlmostEqual(result[key], expected[key], places=10)

    def test_covariance_units_are_retained(self):
        a = geometry.geometry_from_coefficients(self.data, self.labels, [2, 1])
        b = geometry.geometry_from_coefficients(np.asarray(self.data) * 3, self.labels, [2, 1])
        self.assertAlmostEqual(b["mean_projection_sd"], a["mean_projection_sd"] * 3)
        self.assertAlmostEqual(b["projected_precision"], a["projected_precision"] / 3)
        self.assertAlmostEqual(b["angle_degrees"], a["angle_degrees"])

    def test_degenerate_covariance_is_not_regularized(self):
        singular = geometry.geometry_from_coefficients([[-1, -1], [1, 1], [-2, -2], [2, 2]], self.labels, [1, 0])
        self.assertIsNone(singular["projected_precision"])
        self.assertEqual(singular["noise_axis_status"], "unique")
        isotropic = geometry.geometry_from_coefficients([[-1, -1], [-1, 1], [1, -1], [1, 1]], self.labels, [1, 0])
        self.assertIsNone(isotropic["angle_degrees"])
        self.assertIsNone(isotropic["noise_axis"])
        self.assertAlmostEqual(isotropic["projected_precision"], math.sqrt(3) / 2)

    def test_bad_class_layout_coefficients_and_arrays_are_rejected(self):
        cases = [
            (self.data, [0, 1, 0, 1], [1, 0]),
            (self.data, [0, 0, 0, 1], [1, 0]),
            (self.data, self.labels, [0, 0]),
            (self.data, self.labels, [1, 2, 3]),
            (self.data, self.labels, [complex(1, 1), 0]),
            (self.data, self.labels, [True, False]),
            ([[math.nan, 0], [1, 0], [2, 1], [3, 1]], self.labels, [1, 0]),
        ]
        for data, labels, beta in cases:
            with self.subTest(labels=labels, beta=beta):
                with self.assertRaises(ValueError):
                    geometry.geometry_from_coefficients(data, labels, beta)


if __name__ == "__main__":
    unittest.main(verbosity=2)
