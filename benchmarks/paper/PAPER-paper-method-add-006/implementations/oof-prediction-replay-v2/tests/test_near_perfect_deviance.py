"""Generated Poisson deviance controls; no recordings, fits or model run."""
import copy
from decimal import Decimal, localcontext
import importlib.util
from pathlib import Path
import unittest
import numpy as np

HERE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("rat_near_perfect_replay", HERE / "replay.py")
replay = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(replay)


def decimal_deviance(y, mu):
    with localcontext() as context:
        context.prec = 100
        yy, mm = Decimal.from_float(float(y)), Decimal.from_float(float(mu))
        return float(2 * (mm - yy + yy * (yy.ln() - mm.ln())))


class NearPerfectDevianceTests(unittest.TestCase):
    def test_nextafter_mismatch_retains_representable_deviance(self):
        y = np.array([[1., 2., 7.], [1., 2., 7.]])
        for direction in (np.inf, -np.inf):
            mu = np.nextafter(y, direction)
            actual = replay._mean_deviance(y, mu)
            expected = np.array([decimal_deviance(a, b) for a, b in zip(y[0], mu[0])])
            self.assertTrue(np.all(actual > 0))
            np.testing.assert_allclose(actual, expected, rtol=5e-16, atol=0)

    def test_complete_session_does_not_relabel_nonzero_constant_fold(self):
        n = 20
        z = np.zeros((n, 7)); z[:, 2] = 5
        reference = {"latents": z, "counts": np.ones((n, 2)),
                     "bin_ids": np.array([f"bin:{i}" for i in range(n)]),
                     "unit_ids": np.array(["ca1:1", "pfc:1"]),
                     "locations": np.array(["CA1", "PFC"])}
        author = {"bin_ids": reference["bin_ids"], "unit_ids": reference["unit_ids"],
                  "fold_ids": replay.source_fold_ids(n), "predictions": np.ones((n, 2))}
        candidate = copy.deepcopy(author)
        for direction in (np.inf, -np.inf):
            with self.subTest(direction=direction):
                candidate["predictions"][:] = np.nextafter(1., direction)
                result = replay.score_session(reference, author, candidate)
                self.assertEqual(result["retained_bin_count"], n)
                for region in ("CA1", "PFC"):
                    unit = result["regions"][region]["units"][0]
                    self.assertEqual(len(unit["candidate"]), 10)
                    self.assertTrue(all(v["status"] == "negative_infinity" for v in unit["candidate"]))
                    self.assertTrue(all(v["model_deviance"] > 0 for v in unit["candidate"]))
                    self.assertTrue(all(v["status"] == "undefined_zero_over_zero" for v in unit["author"]))
                    self.assertEqual(unit["paired_fold_d2_difference"], [None] * 10)

    def test_small_and_normal_errors_match_high_precision_equation(self):
        for relative in (0., 1e-12, -1e-12, 1e-5, -1e-5, 1e-4, -1e-4, .1, -.1, 1.):
            y = np.array([[1., 7.]])
            mu = y * (1 + relative)
            actual = replay._mean_deviance(y, mu)
            expected = np.array([decimal_deviance(a, b) for a, b in zip(y[0], mu[0])])
            np.testing.assert_allclose(actual, expected, rtol=2e-12, atol=0)


if __name__ == "__main__":
    unittest.main()
