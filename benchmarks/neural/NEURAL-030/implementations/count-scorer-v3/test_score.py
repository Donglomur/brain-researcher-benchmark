"""Generated numeric regressions only; no original count data or model execution."""
import importlib.util
import math
import os
from pathlib import Path
import unittest


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


HERE = Path(__file__).resolve().parent
REPO = Path(os.environ.get("NEUROBENCH_SOURCE_ROOT", HERE.parents[4]))
score = load("neural030_representable_v3", HERE / "score.py")
prior = load("neural030_representable_prior", REPO / "benchmarks/neural/NEURAL-030/implementations/count-scorer-v2/score.py")


def panel(values):
    expected, predictions = [], []
    for index, value in enumerate(values):
        trial = "trial-" + str(index)
        expected.append({"trial_id": trial, "session_id": "s", "bin_count": 10, "counts": [0] * 10})
        predictions.append({"trial_id": trial, "counts": [value] * 10})
    return expected, predictions


class RepresentableCountScoreTests(unittest.TestCase):
    def test_nonzero_trial_loss_cannot_become_perfect_mse(self):
        expected, predictions = panel([1e-200])
        self.assertEqual(prior.score_predictions(expected, predictions)["trial_results"][0]["mse"], 0.0)
        with self.assertRaisesRegex(ValueError, "nonzero MSE.*representability"):
            score.score_predictions(expected, predictions)

    def test_candidate_and_comparator_unrepresentable_losses_are_refused(self):
        expected, tiny = panel([1e-200])
        _, perfect = panel([0.0])
        for candidate, baseline in ((tiny, perfect), (perfect, tiny)):
            with self.subTest(candidate_tiny=candidate is tiny):
                with self.assertRaisesRegex(ValueError, "nonzero MSE.*representability"):
                    score.score_predictions(expected, candidate, baseline_predictions=baseline)

    def test_representable_subnormal_survives_trial_session_mouse_means(self):
        expected, predictions = panel([2.0 ** -537, 2.0 ** -537])
        binding = {"verification_status": "operator_attested", "binding_id": "generated-only",
                   "evidence_sha256": "0" * 64, "session_to_mouse": {"s": "m"}}
        old = prior.score_predictions(expected, predictions, mouse_binding=binding)
        self.assertEqual(old["session_results"][0]["mse"], 0.0)
        current = score.score_predictions(expected, predictions, mouse_binding=binding)
        minimum = math.ldexp(1.0, -1074)
        self.assertTrue(all(row["mse"] == minimum for row in current["trial_results"]))
        self.assertEqual(current["session_results"][0]["mse"], minimum)
        self.assertEqual(current["mouse_results"][0]["mse"], minimum)
        self.assertEqual(current["mouse_macro"]["mse"], minimum)
        self.assertFalse(current["scientific_qualification"])

    def test_exact_zero_small_gain_and_true_cancellation_remain_valid(self):
        expected, perfect = panel([0.0])
        _, displaced = panel([2.0 ** -500])
        result = score.score_predictions(expected, perfect, baseline_predictions=displaced)
        row = result["trial_results"][0]
        self.assertEqual(row["mse"], 0.0)
        self.assertEqual(row["mse_gain"], 2.0 ** -1000)
        self.assertEqual(row["poisson_deviance"], 2e-12)
        self.assertEqual(score._mean_metrics([{"gain": 1.0}, {"gain": -1.0}], ["gain"]), {"gain": 0.0})
        with self.assertRaisesRegex(ValueError, "nonzero aggregate metric.*representability"):
            score._mean_metrics([{"mse": math.ldexp(1.0, -1074)}, {"mse": 0.0}], ["mse"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
