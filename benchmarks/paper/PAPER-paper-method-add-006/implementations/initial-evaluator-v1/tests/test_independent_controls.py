"""Independent closed-form controls, derived before inspecting evaluator code.

These small arrays check the pinned rat GLM/geometry definitions. They are
engineering controls, not observations from the W-track population.
"""
import importlib.util
import itertools
import math
from pathlib import Path
import sys
import unittest

import numpy as np


MODULE = Path(__file__).resolve().parents[1] / "evaluator.py"
SPEC = importlib.util.spec_from_file_location("add006_independent_evaluator", MODULE)
ev = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = ev
SPEC.loader.exec_module(ev)


class IndependentGeometryControls(unittest.TestCase):
    def test_isotropic_signal_plus_noise_closed_form(self):
        p = 40
        got = ev.geometry_from_covariance(2 * np.eye(2), np.eye(2), np.eye(2), training_samples=p)
        expected = {
            "dimensionality": 2,
            "alignment": 0.25,
            "signal_noise_factor": 1,
            "signal_signal_factor": 1,
            "normalized_task_dimension": 1,
            "normalized_latent_dimension": 1,
            "weighted_factorization": 0.5,
            "generalization_error": math.atan(math.sqrt(1 + 4 * math.pi / p)) / math.pi,
            "theory_error": math.atan(math.sqrt(1 + 4 * math.pi / p)) / math.pi,
        }
        for key, value in expected.items():
            with self.subTest(metric=key):
                self.assertAlmostEqual(got[key], value, places=12)

    def test_weighted_factorization_includes_diagonal_and_signal_strength(self):
        # x=z0+noise, but latent coordinates are rescaled by diag(1,2).
        got = ev.geometry_from_covariance(
            2 * np.eye(2), np.diag([1., 2.]), np.diag([1., 4.]), training_samples=40
        )
        self.assertAlmostEqual(got["weighted_factorization"], 17 / 25, places=12)
        self.assertAlmostEqual(got["normalized_latent_dimension"], 25 / 34, places=12)
        self.assertAlmostEqual(got["normalized_task_dimension"], 1, places=12)
        self.assertAlmostEqual(got["signal_noise_factor"], 1, places=12)
        self.assertAlmostEqual(got["signal_signal_factor"], 1, places=12)

    def test_noiseless_signal_has_infinite_snf_but_finite_error(self):
        got = ev.geometry_from_covariance(np.eye(2), np.eye(2), np.eye(2), training_samples=25)
        self.assertEqual(got["signal_noise_factor"], float("inf"))
        self.assertAlmostEqual(
            got["generalization_error"], math.atan(math.sqrt(math.pi / 25)) / math.pi, places=12
        )

    def test_joint_covariance_must_be_valid_not_only_diagonal_blocks(self):
        with self.assertRaises(ValueError):
            ev.geometry_from_covariance(np.eye(2), 2 * np.eye(2), np.eye(2))

    def test_singular_latent_covariance_is_not_silently_pseudoinverted(self):
        with self.assertRaises(ValueError):
            ev.geometry_from_covariance(2 * np.eye(2), np.eye(2), np.diag([1., 0.]))

    def test_nonfinite_input_fails(self):
        bad = np.eye(2)
        bad[0, 0] = np.nan
        with self.assertRaises(ValueError):
            ev.geometry_from_covariance(bad, np.eye(2), np.eye(2))

    def test_empirical_covariance_translation_invariance(self):
        # Full four-dimensional +/-1 factorial has exactly independent columns.
        f = np.array(list(itertools.product((-1., 1.), repeat=4)))
        z, noise = f[:, :2], f[:, 2:]
        x = z + noise
        got = ev.covariance_geometry(x + [100., -42.], z + [-15., 73.], 40)
        expected = ev.geometry_from_covariance(2 * np.eye(2), np.eye(2), np.eye(2), training_samples=40)
        for key in expected:
            if isinstance(expected[key], (float, int)):
                self.assertAlmostEqual(got[key], expected[key], places=12)

    def test_pr_uses_source_epsilon_and_all_constant_convention(self):
        x = np.array([[-1., -10.], [-1., 10.], [1., -10.], [1., 10.]])
        a, b = (1 / 1.01) ** 2, (10 / 10.01) ** 2
        self.assertAlmostEqual(ev.participation_ratio(x), (a + b) ** 2 / (a*a + b*b), places=12)
        self.assertEqual(ev.participation_ratio(np.full((4, 3), 7.)), 0.)


class IndependentBasisControls(unittest.TestCase):
    def test_occupancy_threshold_is_strictly_greater_than_twenty(self):
        z = np.zeros((41, 7))
        z[:, 2] = 5
        z[:20, 0] = 10
        z[:20, 3] = 6
        z[:20, 4] = 9
        params = ev.BasisParameters(10, 3, 100, 40, min_count=20)
        before = z.copy()
        basis = ev.fit_basis(z, params)
        np.testing.assert_array_equal(basis["position"], [[0., 0.]])
        np.testing.assert_array_equal(basis["vx"], [0.])
        np.testing.assert_array_equal(basis["vy"], [0.])
        np.testing.assert_array_equal(z, before)

    def test_trajectory_gating_and_normalized_gaussian_variance(self):
        params = ev.BasisParameters(10, 3, 100, 40, min_count=20)
        basis = {"position": np.array([[0., 0.], [10., 0.]]),
                 "vx": np.array([-3., 3.]), "vy": np.array([0., 6.])}
        z = np.array([[0., 5., 5., 3., 0., 1., 0.],
                      [0., 5., 5., 3., 0., 0., 1.]])
        a = math.exp(-25 / 200) / (200 * math.pi)
        b = math.exp(-125 / 200) / (200 * math.pi)
        c = 1 / math.sqrt(80 * math.pi)
        d = c * math.exp(-36 / 80)
        expected = [[a, b, 0, 0, d, c, c, d], [0, 0, a, b, d, c, c, d]]
        np.testing.assert_allclose(ev.design_matrix(z, basis, params), expected, rtol=1e-13, atol=1e-15)


if __name__ == "__main__":
    unittest.main()
