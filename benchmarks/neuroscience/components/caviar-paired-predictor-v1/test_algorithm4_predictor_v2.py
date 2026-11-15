"""Invented deterministic component controls; no authentic neural data or fitting."""
import itertools
import math
import unittest
from dataclasses import replace
from unittest.mock import patch
import algorithm4_predictor_v2 as a

class ScriptedRandom:
    def __init__(self, normals, uniforms):
        self.normals, self.uniforms = iter(normals), iter(uniforms)
        self.normal_calls = self.uniform_calls = 0
    def normalvariate(self, mean, sd):
        assert mean == 0 and sd == 1
        self.normal_calls += 1
        return next(self.normals)
    def random(self):
        self.uniform_calls += 1
        return next(self.uniforms)

def target(tid="A", mu=3.0, sd=2.0, mean=(1.0, 1.0), cov=((1.0, 0.0), (0.0, 1.0))):
    return a.TargetPosterior(tid, a.WeightPosterior(mu, sd), a.PowerCurvePosterior(mean, cov))

def fixture(targets=None, rows=None, draws=1):
    targets = (target(),) if targets is None else targets
    rows = (("p1", (("A", 1.0),)), ("p2", (("A", 1.0),))) if rows is None else rows
    posterior = a.FixedPosterior(a.PosteriorMetadata("invented-q", "invented-no-fit", "h",
                                "nC", "mW"), targets)
    hologram = a.HeldHologram("h", tuple(a.PowerInput(pid, pairs) for pid, pairs in rows))
    return posterior, hologram, a.ProspectiveSettings(draws, 902, 3)

def scripted(args, normals, uniforms):
    rng = ScriptedRandom(normals, uniforms)
    with patch.object(a.random, "Random", return_value=rng):
        result = a.predict_paired(*args)
    return result, rng

class PredictorControls(unittest.TestCase):
    def test_joint_correlated_cholesky(self):
        _, chol = a._cholesky(a.PowerCurvePosterior((5.0, 5.0), ((4.0, 2.0), (2.0, 5.0))))
        rng = ScriptedRandom([1.0, -1.0], [])
        phi, attempts = a._sample_phi(rng, (5.0, 5.0), chol, "A", 0, 1)
        self.assertEqual(attempts, 1)
        self.assertAlmostEqual(phi[0], 7.0)
        self.assertAlmostEqual(phi[1], 4.0)

    def test_shared_phi_and_weight_across_powers(self):
        args = fixture(rows=(("low", (("A", 0.0),)), ("high", (("A", 2.0),))))
        r, rng = scripted(args, [0.0, 0.0, 1.0], [0.0, 0.0])
        self.assertEqual(r.literal_mean, (5.0, 5.0))
        self.assertAlmostEqual(r.rao_blackwell_mean[0], 3.0 * a.stable_logistic(-1.0))
        self.assertAlmostEqual(r.rao_blackwell_mean[1], 3.0 * a.stable_logistic(1.0))
        self.assertEqual((rng.normal_calls, rng.uniform_calls), (3, 2))

    def test_zero_power_has_no_training_mask(self):
        args = fixture(rows=(("zero", (("A", 0.0),)),))
        r, _ = scripted(args, [0.0, 0.0, 0.0], [0.0])
        self.assertEqual(r.literal_mean, (3.0,))
        self.assertGreater(r.rao_blackwell_mean[0], 0.0)

    def test_independent_uniforms_not_shared_spike(self):
        r, _ = scripted(fixture(), [0.0, 0.0, 0.0], [0.1, 0.9])
        self.assertEqual(r.literal_mean, (3.0, 0.0))
        self.assertEqual(r.rao_blackwell_mean, (1.5, 1.5))

    def test_zero_mu_exact_point_mass_even_large_sd(self):
        r, rng = scripted(fixture(targets=(target(mu=0.0, sd=1e308),)),
                          [0.0, 0.0], [0.0, 0.0])
        self.assertEqual(r.literal_mean, (0.0, 0.0))
        self.assertEqual(r.rao_blackwell_mean, (0.0, 0.0))
        self.assertEqual(r.removed_conditional_covariance_of_mean, ((0.0, 0.0), (0.0, 0.0)))
        self.assertEqual(rng.normal_calls, 2)

    def test_zero_sd_does_not_consume_weight_normal(self):
        r, rng = scripted(fixture(targets=(target(sd=0.0),)), [0.0, 0.0], [0.0, 0.0])
        self.assertEqual(r.literal_mean, (3.0, 3.0))
        self.assertEqual(rng.normal_calls, 2)

    def test_negative_gaussian_weight_is_not_clipped(self):
        r, _ = scripted(fixture(targets=(target(mu=1.0, sd=2.0),)),
                        [0.0, 0.0, -1.0], [0.0, 0.0])
        self.assertEqual(r.literal_mean, (-1.0, -1.0))
        self.assertEqual(r.rao_blackwell_mean, (0.5, 0.5))

    def test_explicit_target_id_join_and_power_order(self):
        args = fixture(targets=(target("A", 2, 0), target("B", 5, 0)),
                       rows=(("second", (("B", 2.0), ("A", 0.0))),
                             ("first", (("A", 2.0), ("B", 0.0)))))
        r, _ = scripted(args, [0.0] * 4, [0.0] * 4)
        self.assertEqual(r.power_ids, ("second", "first"))
        self.assertAlmostEqual(r.rao_blackwell_mean[0],
                               2 * a.stable_logistic(-1) + 5 * a.stable_logistic(1))
        self.assertAlmostEqual(r.rao_blackwell_mean[1],
                               2 * a.stable_logistic(1) + 5 * a.stable_logistic(-1))

    def test_rejection_then_accept_preserves_attempt_count(self):
        r, _ = scripted(fixture(), [-2.0, 0.0, 0.0, 0.0, 0.0], [0.0, 0.0])
        self.assertEqual((r.phi_attempts, r.accepted_target_draws), (2, 1))

    def test_exhaustion_after_successful_draw_has_no_partial_result(self):
        args = fixture(draws=2)
        with patch.object(a.random, "Random",
                          return_value=ScriptedRandom([0, 0, 0, -2, 0, -2, 0, -2, 0], [0, 0])):
            with self.assertRaises(a.SamplingExhausted) as context:
                a.predict_paired(*args)
        self.assertEqual((context.exception.target_id, context.exception.draw_index,
                          context.exception.attempts), ("A", 1, 3))

    def test_orthant_boundary_is_rejected_not_clipped(self):
        rng = ScriptedRandom([-1, 0], [])
        with self.assertRaises(a.SamplingExhausted):
            a._sample_phi(rng, (1, 1), (1, 0, 1), "A", 0, 1)

    def test_analytic_removed_covariance_and_j_squared_scaling(self):
        r, _ = scripted(fixture(draws=2), [0.0] * 6, [0.0] * 4)
        self.assertEqual(r.removed_conditional_covariance_of_mean,
                         ((2.125, 0.5), (0.5, 2.125)))
        self.assertEqual(r.rao_blackwell_mean, (1.5, 1.5))

    def test_exact_moment_enumeration_for_independent_spikes_shared_weight(self):
        # Two-point W matches Gaussian first/second moments, not its distribution.
        mu, sd, p = 3.0, 2.0, (0.25, 0.75)
        outcomes = []
        for w in (mu-sd, mu+sd):
            for s0, s1 in itertools.product((0, 1), repeat=2):
                prob = 0.5 * (p[0] if s0 else 1-p[0]) * (p[1] if s1 else 1-p[1])
                outcomes.append((prob, (w*s0, w*s1)))
        means = tuple(sum(prob*y[i] for prob, y in outcomes) for i in range(2))
        actual = tuple(tuple(sum(prob*(y[i]-means[i])*(y[j]-means[j])
                                 for prob, y in outcomes) for j in range(2)) for i in range(2))
        expected = a._conditional_covariance(mu, sd, p)
        self.assertEqual(means, (mu*p[0], mu*p[1]))
        for i in range(2):
            for j in range(2):
                self.assertAlmostEqual(actual[i][j], expected[i][j])

    def test_covariance_inputs_are_not_repaired(self):
        invalid = [((1, 0.1), (0.2, 1)), ((1, 1), (1, 1)),
                   ((1, 2), (2, 1)), ((0, 0), (0, 1)),
                   ((1, math.nan), (math.nan, 1)),
                   ((1e-308, 0), (0, 1e308))]
        for cov in invalid:
            with self.subTest(cov=cov), self.assertRaises(a.InvalidInput):
                a.predict_paired(*fixture(targets=(target(cov=cov),)))

    def test_shape_and_id_joins_fail_closed(self):
        for rows in [(("p", (("B", 1),)),),
                     (("p", (("A", 1), ("A", 2))),),
                     (("p", (("A", 1),)), ("p", (("A", 2),)))]:
            with self.subTest(rows=rows), self.assertRaises(a.InvalidInput):
                a.predict_paired(*fixture(rows=rows))
        args = fixture(targets=(target(), target()))
        with self.assertRaises(a.InvalidInput):
            a.predict_paired(*args)

    def test_weight_sd_is_typed_and_never_beta_inferred(self):
        bad = a.TargetPosterior("A", {"mean": 3, "beta": 4}, a.PowerCurvePosterior((1, 1), ((1, 0), (0, 1))))
        with self.assertRaises(a.InvalidInput):
            a.predict_paired(*fixture(targets=(bad,)))
        with self.assertRaises(a.InvalidInput):
            a.predict_paired(*fixture(targets=(target(sd=-1),)))

    def test_nonfinite_bool_and_negative_power_rejected(self):
        for value in (True, math.inf, math.nan, -0.1, 10**1000):
            with self.subTest(value=str(value)[:20]), self.assertRaises(a.InvalidInput):
                a.predict_paired(*fixture(rows=(("p", (("A", value),)),)))

    def test_bad_settings_and_metadata(self):
        posterior, hologram, settings = fixture()
        for setting in (replace(settings, draws=0), replace(settings, seed=True),
                        replace(settings, max_phi_attempts_per_target_draw=0)):
            with self.subTest(setting=setting), self.assertRaises(a.InvalidInput):
                a.predict_paired(posterior, hologram, setting)
        with self.assertRaises(a.InvalidInput):
            a.predict_paired(posterior, replace(hologram, hologram_id="different"), settings)
        with self.assertRaises(a.InvalidInput):
            a.predict_paired(replace(posterior, metadata=replace(posterior.metadata, response_unit="")),
                             hologram, settings)

    def test_stable_logistic_extreme_tails(self):
        self.assertEqual(a.stable_logistic(1000), 1.0)
        self.assertEqual(a.stable_logistic(-1000), 0.0)
        self.assertEqual(a.stable_logistic(0), 0.5)
        with self.assertRaises(a.InvalidInput):
            a.stable_logistic(math.inf)

    def test_intermediate_overflow_fails(self):
        args = fixture(rows=(("p", (("A", 1e308),)),))
        with self.assertRaises(a.NumericalFailure):
            scripted(args, [1.0, 0.0], [])
        with self.assertRaises(a.NumericalFailure):
            scripted(fixture(targets=(target(mu=1e200),)), [0.0, 0.0, 0.0], [0.0, 0.0])

    def test_unrepresentable_j_rejected_before_rng_creation(self):
        posterior, hologram, settings = fixture()
        with patch.object(a.random, "Random") as rng:
            with self.assertRaises(a.InvalidInput):
                a.predict_paired(posterior, hologram, replace(settings, draws=10**1000))
            rng.assert_not_called()

    def test_seed_replay_is_deterministic_in_this_python(self):
        args = fixture(targets=(target(mean=(3, 3)),), draws=4)
        first, second = a.predict_paired(*args), a.predict_paired(*args)
        self.assertEqual(first, second)
        self.assertEqual(first.accepted_target_draws, 4)

if __name__ == "__main__":
    unittest.main(verbosity=2)
