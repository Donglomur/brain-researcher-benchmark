"""Complete generated panel controls for normalized squared-error underflow."""
from fractions import Fraction
import importlib.util
import math
from pathlib import Path
import unittest


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("latent_generated_fixtures", HERE / "test_evaluator.py")
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)
ev = fixtures.ev


def small_scale_case(target, prediction):
    owner = fixtures.fixture()
    for row in owner["trials"]:
        if row["split"] == "train":
            row["values"] = [row["values"][0] * 1e-150] * 15
        elif row["split"] == "assessment":
            row["values"] = [target] * 15
        else:
            row["values"] = [0.0] * 15
    candidate = ev.baseline_submission(owner)
    for row in candidate["predictions"]:
        row["values"] = [prediction] * 15
    return owner, candidate


class NormalizedUnderflowControls(unittest.TestCase):
    def expected(self, error, variance):
        return float(Fraction.from_float(error) ** 2 / Fraction.from_float(variance))

    def test_complete_candidate_error_survives_normalization(self):
        owner, candidate = small_scale_case(0.0, 1e-200)
        result = ev.score(owner, candidate, fixtures.PROGRAM)
        variance = result["per_original_unit"][0]["training_variance"]
        expected = self.expected(1e-200, variance)
        actual = result["equal_monkey_neural_nse"]
        self.assertGreater(actual, 0.0)
        self.assertTrue(math.isclose(actual, expected, rel_tol=1e-14, abs_tol=0.0))
        self.assertEqual(result["equal_monkey_condition_mean_nse"], 0.0)
        self.assertEqual(result["improvement_decision"], "withheld")

    def test_complete_condition_mean_error_survives_normalization(self):
        owner, candidate = small_scale_case(1e-200, 1e-200)
        result = ev.score(owner, candidate, fixtures.PROGRAM)
        variance = result["per_original_unit"][0]["training_variance"]
        expected = self.expected(1e-200, variance)
        self.assertEqual(result["equal_monkey_neural_nse"], 0.0)
        actual = result["equal_monkey_condition_mean_nse"]
        self.assertGreater(actual, 0.0)
        self.assertTrue(math.isclose(actual, expected, rel_tol=1e-14, abs_tol=0.0))
        self.assertEqual(result["equal_monkey_candidate_minus_condition_mean"], -actual)

    def test_normal_scale_arithmetic_and_complete_support_unchanged(self):
        owner = fixtures.fixture()
        result = ev.score(owner, fixtures.prediction(owner, {"A": 1, "F": 1}), fixtures.PROGRAM)
        self.assertEqual(result["equal_monkey_neural_nse"], 1.0)
        self.assertEqual(result["equal_monkey_condition_mean_nse"], 9.0)
        self.assertEqual(result["equal_monkey_candidate_minus_condition_mean"], -8.0)
        self.assertEqual([x["training_variance"] for x in result["per_original_unit"]], [1.0] * 3)
        self.assertEqual(result["per_monkey"]["A"]["assessment_trial_rows"], 72)
        self.assertEqual(result["per_monkey"]["F"]["assessment_trial_rows"], 144)


if __name__ == "__main__":
    unittest.main()
