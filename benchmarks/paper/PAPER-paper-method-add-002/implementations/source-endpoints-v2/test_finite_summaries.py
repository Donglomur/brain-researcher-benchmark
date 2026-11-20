"""New summary-arithmetic regressions only; no original observations or fitting."""
import importlib.util
import hashlib
import math
from pathlib import Path
import unittest
import numpy as np

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("finite_slice_endpoints", HERE / "endpoints.py")
E = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(E)
LEGACY_PATH = HERE.parent / "source-endpoints-v1" / "endpoints.py"
LEGACY_BYTES = LEGACY_PATH.read_bytes()
if hashlib.sha256(LEGACY_BYTES).hexdigest() != "5e33cbf59c352951d53c0b4d544ab3ff0887c51b6a0e5eff171be43c6f62d049":
    raise ValueError("unchanged v1 source required for arithmetic regression")
OLD_SPEC = importlib.util.spec_from_file_location("preserved_slice_endpoints", LEGACY_PATH)
OLD = importlib.util.module_from_spec(OLD_SPEC)
exec(compile(LEGACY_BYTES, str(LEGACY_PATH), "exec"), OLD.__dict__)


class FiniteSummaries(unittest.TestCase):
    def test_representable_extreme_mean_and_sd(self):
        target = np.zeros((2, 2, 2)); target[1] = 1e-100
        prediction = target.copy(); prediction[:, 1] = 1.0
        with np.errstate(over="ignore", invalid="ignore"):
            old = OLD.trajectory_r2(target, prediction)
        self.assertTrue(np.isfinite(old["r2"]).all())
        self.assertTrue(np.isinf(old["population_sd"]))
        result = E.trajectory_r2(target, prediction)
        # Trial0 is exact. Trial1 has SSE≈4 and SST=1e-200: R²≈−4e200.
        # Two equally weighted observations therefore have mean≈−2e200, SD≈2e200.
        np.testing.assert_allclose(result["r2"], [1.0, -4e200], rtol=1e-14)
        self.assertTrue(np.isfinite([result["mean"], result["population_sd"]]).all())
        self.assertAlmostEqual(result["mean"] / -2e200, 1.0, places=13)
        self.assertAlmostEqual(result["population_sd"] / 2e200, 1.0, places=13)
        # A constant finite vector must not overflow its intermediate sum.
        target = np.zeros((2, 5, 2)); target[1] = 1e-154
        result = E.trajectory_r2(target, np.full_like(target, .5))
        self.assertAlmostEqual(result["mean"] / -1e308, 1.0, places=13)
        self.assertEqual(result["population_sd"], 0.0)

    def test_ordinary_weights_and_unrepresentable_r2(self):
        target = np.array([[[0., 0.], [0., 0.]], [[2., 0.], [2., 0.]]])
        prediction = target.copy(); prediction[:, 1, 0] = 1.
        result = E.trajectory_r2(target, prediction)
        np.testing.assert_array_equal(result["r2"], [1., 0.])
        self.assertEqual(result["mean"], .5)
        self.assertEqual(result["population_sd"], .5)  # population SD, not sample SD
        old = OLD.trajectory_r2(target, prediction)
        for key in ("r2", "sse", "sst"):
            np.testing.assert_array_equal(result[key], old[key])
        self.assertEqual(result["mean"], old["mean"])
        self.assertEqual(result["population_sd"], old["population_sd"])
        target = np.zeros((2, 1, 2)); target[1] = 5e-155
        with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
            with self.assertRaisesRegex(ValueError, "R2 overflow"):
                E.trajectory_r2(target, np.full_like(target, .5))

    def test_full_fold_and_trial_aggregation_stays_finite(self):
        # Every source trial retains all80 bins and both coordinates. True first
        # positions are preserved. No inference, neural data or fitted decoder.
        movement = np.zeros((150, 511, 2)); movement[66:145] = 1e-154
        plan = E.source_schedule("straight")
        prediction = np.full((20, 5, 80, 53, 2), .1)
        prediction[:, :, 0] = 0.
        summary, details = E.score_condition(movement, "straight", prediction, plan["test"])
        # SST=1.975e−308 and SSE≈1.58, so every occurrence is≈−8e307.
        self.assertEqual(summary["repeated_test_occurrences"], 5300)
        np.testing.assert_array_equal(details["trial_test_counts"], np.full(265, 20))
        np.testing.assert_allclose(details["r2"] / -8e307, 1.0, rtol=1e-13)
        np.testing.assert_allclose(details["trial_mean_r2"] / -8e307, 1.0, rtol=1e-13)
        self.assertAlmostEqual(summary["mean_trial_fold_repeat_r2"] / -8e307, 1.0, places=12)
        self.assertEqual(summary["mean_within_fold_population_sd"], 0.0)
        self.assertTrue(np.isfinite(details["trial_mean_r2"]).all())
        # One independent trial now has a small positive R², while every other
        # trial stays near−8e307. A global normalization scale must not erase or
        # quantize the first trial's own representable repeated-occurrence mean.
        movement[:, 0] = 0.; movement[66, 0] = 1.
        small_target = movement[65:-5, 0:1].copy()
        small_prediction = small_target.copy()
        # Both coordinates have one unit impulse in80 bins, hence SST=1.975.
        # Put a single error just below sqrt(SST) on a later zero-valued bin.
        error = np.sqrt(1.975)
        for _ in range(8):
            error = np.nextafter(error, 0.)
        small_prediction[2, 0, 0] = error
        small_score = float(E.trajectory_r2(small_target, small_prediction)["r2"][0])
        self.assertGreater(small_score, 0.)
        self.assertLess(small_score, 1e-14)
        for repeat in range(20):
            for fold in range(5):
                locations = np.flatnonzero(plan["test"][repeat, fold] == 0)
                if len(locations):
                    prediction[repeat, fold, :, locations[0]] = small_prediction[:, 0]
        _, mixed = E.score_condition(movement, "straight", prediction, plan["test"])
        occurrences = mixed["r2"][plan["test"] == 0]
        self.assertTrue(np.isfinite(occurrences).all())
        self.assertTrue((occurrences > 0.).all())
        self.assertTrue((occurrences < 1e-14).all())
        # Test the grouping arithmetic independently of low-level SSE/SST
        # reduction layout: a near-zero R² need not be bit-identical when
        # computed in a one-trial array and in the full fold geometry.
        expected_mean = math.fsum(map(float, occurrences)) / len(occurrences)
        np.testing.assert_allclose(mixed["trial_mean_r2"][0], expected_mean, rtol=1e-14, atol=0)
        np.testing.assert_allclose(mixed["trial_mean_r2"][1:] / -8e307, 1., rtol=1e-13)


if __name__ == "__main__":
    unittest.main()
