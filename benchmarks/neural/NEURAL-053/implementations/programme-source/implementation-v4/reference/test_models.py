"""Invented engineering arrays only; no authentic NEURAL-053 data or models.

Run from this directory: python3 -B -m unittest -v test_models.py
All arrays stay in memory. Conservative fixture reservation for this full run:
3 MiB cumulative, 2 MiB live, 0 retained numeric files. This is a logical fixture
provision including intermediate arrays, not measured process RSS or OS I/O.
"""

import importlib.util
import math
from pathlib import Path
import sys
import unittest

import numpy as np

import models as m


class ReferenceControls(unittest.TestCase):
    def simple(self):
        return (np.array([[-2., 1., 7.], [-1., 2., 7.], [1., 3., 7.], [2., 4., 7.]]),
                np.array([1, 1, 2, 2], dtype=np.int64))

    def test_01_exact_grid_and_label_refusals(self):
        grid = m.setting_grid()
        self.assertEqual([x["rank"] for x in grid], list(range(16)))
        self.assertEqual([sum(x["family"] == f for x in grid) for f in ("ridge", "shrinkage_lda", "fourier_ridge")], [4, 3, 9])
        x, y = self.simple()
        for bad in (y - 1, np.array([1, 1, 1, 2]), np.array([1, 1, 1, 1]), y.astype(float)):
            with self.assertRaises(m.ReferenceError):
                m.fit_reference("ridge", {"alpha": 1}, x, bad, 2, 0, "ocular")
        with self.assertRaises(m.ReferenceError):
            m.fit_reference("ridge", {"alpha": 0.3}, x, y, 2, 0, "ocular")
        with self.assertRaises(m.ReferenceError):
            m.fit_reference("ridge", {"alpha": True}, x, y, 2, 0, "ocular")

    def test_02_population_scale_and_exact_ridge_objective(self):
        x, y = self.simple()
        fit = m.fit_reference("ridge", {"alpha": 1}, x, y, 2, 0, "ocular")
        self.assertEqual(fit["solve"]["system"], "primal_ridge")
        np.testing.assert_array_equal(fit["standardization"]["variance"], np.mean((x - x.mean(0)) ** 2, axis=0))
        z = m._transform(fit["standardization"], x)
        zc = z - z.mean(0)
        Y = np.eye(2)[y - 1]
        expected = np.linalg.solve(zc.T @ zc + len(x) * np.eye(3), zc.T @ (Y - Y.mean(0)))
        np.testing.assert_allclose(fit["weights"], expected, atol=1e-14, rtol=1e-13)
        wrong_NC = np.linalg.solve(zc.T @ zc + len(x) * 2 * np.eye(3), zc.T @ (Y - Y.mean(0)))
        self.assertGreater(float(np.linalg.norm(expected - wrong_NC)), 0.01)
        changed = x.copy(); changed[:, 2] = 1e300
        np.testing.assert_array_equal(m.score_reference(fit, x), m.score_reference(fit, changed))
        self.assertFalse(fit["weights"].flags.writeable)

    def test_03_dual_matches_independent_primal(self):
        x = np.array([[-3., 1., 0., 2., 1., 0.], [-1., 0., 2., 4., 2., 1.],
                      [1., 2., 1., 1., 3., 2.], [3., 3., 3., 0., 4., 3.]])
        y = np.array([1, 1, 2, 2])
        fit = m.fit_reference("ridge", {"alpha": 0.01}, x, y, 2, 0, "ocular")
        self.assertEqual(fit["solve"]["system"], "dual_ridge")
        z = m._transform(fit["standardization"], x); zc = z - z.mean(0)
        Y = np.eye(2)[y - 1]
        primal = np.linalg.solve(zc.T @ zc + 4 * 0.01 * np.eye(6), zc.T @ (Y - Y.mean(0)))
        np.testing.assert_allclose(fit["weights"], primal, atol=1e-12, rtol=1e-12)
        self.assertLessEqual(fit["solve"]["original_primal_residual_frobenius"], fit["solve"]["original_primal_residual_bound"])

    def test_04_all_constant_and_lda_zero_within_fallbacks(self):
        x = np.full((4, 2), 7.0); y = np.array([1, 1, 2, 2])
        for family, params in [("ridge", {"alpha": 1}), ("shrinkage_lda", {"gamma": 0.1}), ("fourier_ridge", {"q": 1, "alpha": 1})]:
            fit = m.fit_reference(family, params, x, y, 2, 0, "ocular")
            self.assertEqual(fit["fallback"], "all_constant_inputs")
            changed = np.array([[1e308, -1e308]])
            np.testing.assert_array_equal(m.calibrated_probabilities(m.score_reference(fit, changed), 1), [[0.5, 0.5]])
        x = np.array([[-1., -2.], [-1., -2.], [1., 2.], [1., 2.]])
        fit = m.fit_reference("shrinkage_lda", {"gamma": 0.1}, x, y, 2, 0, "ocular")
        self.assertEqual(fit["fallback"], "zero_within_class_identity")
        self.assertEqual(fit["covariance_tau"], 0)
        self.assertEqual(fit["covariance_denominator"], 2)
        self.assertTrue(np.isfinite(m.score_reference(fit, x)).all())

    def test_05_lda_denominator_and_shrinkage(self):
        x, y = self.simple()
        fit = m.fit_reference("shrinkage_lda", {"gamma": 0.5}, x, y, 2, 0, "ocular")
        z = m._transform(fit["standardization"], x)[:, :2]
        centers = np.stack([z[y == label].mean(0) for label in [1, 2]], axis=1)
        centered = z - centers[:, y - 1].T
        S = centered.T @ centered / 2
        tau = np.trace(S) / 2
        cov = 0.5 * S + 0.5 * tau * np.eye(2)
        expected = np.linalg.solve(cov, centers)
        np.testing.assert_allclose(fit["weights"][:2], expected, rtol=1e-12, atol=1e-12)
        self.assertEqual(fit["covariance_tau"], tau)

    def test_06_fourier_seed_law_and_settings_coupling(self):
        # Small D, exact required M=1024; no reduced Fourier fixture is used.
        G, phase, seed = m.fourier_basis(2, 0, "ocular")
        G2, phase2, seed2 = m.fourier_basis(2, 0, "ocular")
        np.testing.assert_array_equal(G, G2); np.testing.assert_array_equal(phase, phase2)
        self.assertEqual(seed, seed2)
        seed_bytes = bytes.fromhex(seed)
        u1 = m._uniform_open(seed_bytes + b"/normal/0/0/0")
        u2 = m._uniform_open(seed_bytes + b"/normal/0/0/1")
        self.assertEqual(G[0, 0], math.sqrt(-2 * math.log(u1)) * math.cos(2 * math.pi * u2))
        other, _, other_seed = m.fourier_basis(2, 1, "ocular")
        self.assertNotEqual(seed, other_seed); self.assertFalse(np.array_equal(G, other))
        self.assertTrue(np.all((phase > 0) & (phase < 2 * math.pi)))

    def test_07_fourier_fit_exact1024_and_original_residual(self):
        x, y = self.simple()
        fit = m.fit_reference("fourier_ridge", {"q": 0.5, "alpha": 0.01}, x, y, 2, 0, "ocular")
        self.assertEqual(fit["fourier_features"], 1024)
        self.assertEqual(fit["weights"].shape, (1024, 2))
        self.assertEqual(fit["solve"]["system"], "dual_ridge")
        self.assertEqual(fit["ell"], 0.5 * math.sqrt(3))
        self.assertLessEqual(fit["solve"]["original_primal_residual_frobenius"], fit["solve"]["original_primal_residual_bound"])
        self.assertTrue(np.isfinite(m.score_reference(fit, x)).all())

    def test_08_solver_and_finite_refusals(self):
        with self.assertRaises(m.ReferenceError):
            m._checked_cholesky(np.array([[0., 1.], [1., 0.]]), np.ones((2, 1)), "invented_indefinite")
        x, y = self.simple(); x[0, 0] = np.nan
        with self.assertRaises(m.ReferenceError):
            m.fit_reference("ridge", {"alpha": 1}, x, y, 2, 0, "ocular")
        with self.assertRaises(m.ReferenceError):
            m.log_probabilities([[math.inf, 0]], 1)

    def test_09_balanced_metrics_logloss_ties_and_grid_completeness(self):
        scores = np.zeros((8, 2)); y = np.array([1, 1, 2, 2, 1, 1, 2, 2])
        groups = np.array(["a"] * 4 + ["b"] * 4)
        metric = m.training_only_metrics(scores, y, groups, 2, 1, 2, 2)
        self.assertEqual(metric["top1_fraction"], [4, 8])
        self.assertAlmostEqual(metric["mean_log_loss"], math.log(2), 14)
        records = []
        for entry in m.setting_grid():
            for temperature in m.TEMPERATURES:
                records.append({**metric, "rank": entry["rank"], "temperature": temperature})
        self.assertEqual(m.select_setting(records)["rank"], 0)
        self.assertEqual(m.select_setting(records)["temperature"], 0.1)
        with self.assertRaises(m.ReferenceError): m.select_setting(records[:-1])
        with self.assertRaises(m.ReferenceError): m.training_only_metrics(scores[:-1], y[:-1], groups[:-1], 2, 1, 2, 2)
        logs = m.log_probabilities([[1000., -1000.]], 1)
        self.assertEqual(logs[0, 1], -2000.)
        self.assertEqual(m.calibrated_probabilities([[1000., -1000.]], 1)[0, 1], 0.)

    def test_10_historical_source_mathematics(self):
        x, y = self.simple()
        fit = m.fit_reference("historical_centroid", {}, x, y, 2, 0, "ocular")
        mean, scale = x.mean(0), x.std(0); scale[scale == 0] = 1
        z = (x - mean) / scale
        centers = np.stack([z[y == label].mean(0) for label in [1, 2]])
        original_logits = (z @ centers.T - 0.5 * np.sum(centers * centers, axis=1)) / x.shape[1]
        np.testing.assert_allclose(m.score_reference(fit, x), original_logits, atol=1e-14)
        with self.assertRaises(m.ReferenceError):m.export_plan(fit, 0.1)

    def test_11_export_actual_sibling_evaluator(self):
        path = Path(__file__).resolve().parent.parent / "method" / "plan.py"
        if not path.exists():
            self.fail("required actual sibling evaluator absent; integration unverified")
        spec = importlib.util.spec_from_file_location("neural053_engineering_plan", path)
        module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module)
        x, y = self.simple()
        for family, params in [("ridge", {"alpha": 1}), ("shrinkage_lda", {"gamma": 0.5}),
                               ("fourier_ridge", {"q": 1, "alpha": 0.01}), ("historical_centroid", {})]:
            fit = m.fit_reference(family, params, x, y, 2, 0, "ocular")
            plan = module.load_plan(m.export_plan(fit, 1))
            expected = np.exp(m.log_probabilities(m.score_reference(fit, x), 1))
            for backend in ("scalar", "vectorized"):
                actual = module.evaluate(plan, x, backend=backend)
                np.testing.assert_allclose(actual, expected, rtol=1e-12, atol=1e-12)

    def test_12_streaming_validation_requires_exact_complete_support(self):
        support = [(f"row{i}", "a" if i < 4 else "b", 1 + (i % 4) // 2) for i in range(8)]
        accumulator = m.TrainingMetricAccumulator(support, 2, 1, 2, 2)
        scores = np.zeros((8, 2))
        accumulator.update(scores[:3], [x[0] for x in support[:3]])
        with self.assertRaises(m.ReferenceError): accumulator.finalize()
        with self.assertRaises(m.ReferenceError): accumulator.update(scores[:1], ["row0"])
        with self.assertRaises(m.ReferenceError): accumulator.update(scores[:1], ["query-row"])
        accumulator.update(scores[3:], [x[0] for x in support[3:]])
        result = accumulator.finalize()
        self.assertEqual(result["top1_fraction"], [4, 8])
        self.assertAlmostEqual(result["mean_log_loss"], math.log(2), 14)


if __name__ == "__main__":
    unittest.main(verbosity=2)
