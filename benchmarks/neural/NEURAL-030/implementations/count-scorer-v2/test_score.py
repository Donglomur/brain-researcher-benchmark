"""Generated software controls only; no authentic observations or predictions."""
import copy
from decimal import Decimal, localcontext
import importlib.util
from pathlib import Path
import unittest

import numpy as np


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


HERE = Path(__file__).resolve().parent
score = load("neural030_score_v2", HERE / "score.py")
prior = load("neural030_score_prior", HERE.parent / "registered-runtime" / "score.py")


def oracle_deviance(y, prediction):
    # Decimal starts from the exact supplied binary floats, rather than rounded
    # decimal strings. This is independent of the replacement polynomial.
    with localcontext() as context:
        context.prec = 90
        target = Decimal.from_float(float(y))
        mean = Decimal.from_float(max(float(prediction), 1e-12))
        half = mean - target
        if target:
            half += target * (target.ln() - mean.ln())
        return float(2 * half)


class StableCountScoreTests(unittest.TestCase):
    def test_near_exact_counts_against_decimal(self):
        for target in (1, 2, 7, 10):
            for power in (12, 20, 26, 35, 45):
                for sign in (-1, 1):
                    mean = target + sign * 2.0 ** -power
                    with self.subTest(target=target, power=power, sign=sign):
                        value = score._metrics(np.array([float(target)]), np.array([mean]))
                        oracle = oracle_deviance(target, mean)
                        self.assertGreater(value["poisson_deviance"], 0)
                        self.assertLessEqual(abs(value["poisson_deviance"] - oracle), oracle * 5e-15)

    def test_predecessor_counterexample_is_retained(self):
        target, mean = 10.0, 10.0 + 2.0 ** -26
        old = prior._metrics(np.array([target]), np.array([mean]))["poisson_deviance"]
        oracle = oracle_deviance(target, mean)
        new = score._metrics(np.array([target]), np.array([mean]))["poisson_deviance"]
        self.assertGreater(abs(old - oracle), oracle * 0.01)
        self.assertLessEqual(abs(new - oracle), oracle * 5e-15)

    def test_zero_floor_and_exact_equal_positive_counts(self):
        self.assertEqual(score._metrics(np.array([0.0]), np.array([0.0]))["poisson_deviance"], 2e-12)
        self.assertEqual(score._metrics(np.array([10.0]), np.array([10.0]))["poisson_deviance"], 0.0)

    def test_paired_secondary_gain_preserves_small_residual_loss(self):
        expected = [{"trial_id": "a", "session_id": "s", "bin_count": 10, "counts": [10] * 10}]
        correct = [{"trial_id": "a", "counts": [10.0] * 10}]
        displaced = [{"trial_id": "a", "counts": [10.0 + 2.0 ** -26] * 10}]
        positive = score.score_predictions(expected, correct, baseline_predictions=displaced)["trial_results"][0]
        negative = score.score_predictions(expected, displaced, baseline_predictions=correct)["trial_results"][0]
        oracle = oracle_deviance(10, 10.0 + 2.0 ** -26)
        self.assertEqual(positive["mse_gain"], 2.0 ** -52)
        self.assertGreater(positive["poisson_deviance_gain"], 0)
        self.assertLessEqual(abs(positive["poisson_deviance_gain"] - oracle), oracle * 5e-15)
        self.assertEqual(negative["poisson_deviance_gain"], -positive["poisson_deviance_gain"])
        self.assertEqual(negative["mse_gain"], -positive["mse_gain"])

    def test_transition_and_distant_values_against_decimal(self):
        for target in (0, 1, 10, 1000):
            for mean in (0, 1e-12, 0.5, 1, 8.749999, 8.75, 8.750001,
                         11.249999, 11.25, 11.250001, 10000):
                with self.subTest(target=target, mean=mean):
                    actual = score._metrics(np.array([float(target)]), np.array([float(mean)]))["poisson_deviance"]
                    oracle = oracle_deviance(target, mean)
                    self.assertLessEqual(abs(actual - oracle), max(1e-24, abs(oracle) * 1e-12))

    def test_hierarchy_equal_trials_sessions_and_mice(self):
        # Different trial lengths, trials per session and sessions per mouse
        # distinguish the registered hierarchy from bin/trial/session pooling.
        expected = [
            {"trial_id": "a", "session_id": "s1", "bin_count": 10, "counts": [0] * 10},
            {"trial_id": "b", "session_id": "s1", "bin_count": 20, "counts": [0] * 20},
            {"trial_id": "c", "session_id": "s2", "bin_count": 10, "counts": [0] * 10},
            {"trial_id": "d", "session_id": "s3", "bin_count": 20, "counts": [0] * 20},
        ]
        prediction = [{"trial_id": row["trial_id"], "counts": [value] * row["bin_count"]}
                      for row, value in zip(expected, (1, 3, 2, 4))]
        baseline = [{"trial_id": row["trial_id"], "counts": [5] * row["bin_count"]} for row in expected]
        binding = {"verification_status": "operator_attested", "binding_id": "generated",
                   "evidence_sha256": "0" * 64,
                   "session_to_mouse": {"s1": "m1", "s2": "m1", "s3": "m2"}}
        result = score.score_predictions(expected, prediction, baseline_predictions=baseline, mouse_binding=binding)
        self.assertEqual(result["mouse_macro"]["mse"], 10.25)
        self.assertEqual(result["mouse_macro"]["mse_gain"], 14.75)
        self.assertEqual(result["mouse_macro"]["poisson_deviance"], 6.0)
        self.assertEqual(result["mouse_macro"]["poisson_deviance_gain"], 4.0)
        self.assertFalse(result["scientific_qualification"])
        self.assertEqual(result, prior.score_predictions(expected, prediction, baseline_predictions=baseline, mouse_binding=binding))

    def test_existing_roster_and_prediction_refusals(self):
        expected = [{"trial_id": "a", "session_id": "s", "bin_count": 10, "counts": [1] * 10}]
        valid = [{"trial_id": "a", "counts": [1.0] * 10}]
        invalid = ([], valid * 2, [{"trial_id": "foreign", "counts": [1.0] * 10}],
                   [{"trial_id": "a", "counts": [1.0] * 9}])
        for prediction in invalid:
            with self.subTest(prediction=prediction), self.assertRaises(ValueError):
                score.score_predictions(expected, prediction)
        for value in (-1, True, float("nan"), float("inf")):
            prediction = copy.deepcopy(valid)
            prediction[0]["counts"][0] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                score.score_predictions(expected, prediction)
        invalid_target = copy.deepcopy(expected)
        invalid_target[0]["counts"][0] = 0.5
        with self.assertRaises(ValueError):
            score.score_predictions(invalid_target, valid)
        with self.assertRaises(ValueError):
            score.score_predictions(expected, valid, baseline_predictions=[])


if __name__ == "__main__":
    unittest.main(verbosity=2)
