"""Compose the actual report and claim checker on invented full-support values."""
import importlib.util
from pathlib import Path
import unittest


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fixture = load("test_paired_sleep_contribution")
claims = load("neural008_numeric_claims")


class SleepClaimsIntegration(unittest.TestCase):
    def test_all_six_targets_compose_with_full_person_assertions(self):
        grade, support, profile, _ = fixture.fixture()
        report = fixture.c.assess(grade, support, profile)
        targets = report["neural008_numeric_claim_targets"]
        assertions = [{"id": key, "value": value["aggregate"], "per_person": value["per_person"]}
                      for key, value in targets.items()]
        result = claims.check_claims(assertions, targets)
        self.assertEqual(result["counts"]["consistent"], 6)
        self.assertEqual(result["verification_denominator"], 6)
        self.assertEqual(result["numeric_verification_rate"], 1)
        self.assertEqual(result["scientific_claim_validity"], "not_assessed")

    def test_null_definedness_abstention_and_unsupported_are_distinct(self):
        grade, support, profile, _ = fixture.fixture(missing_rem=True)
        targets = fixture.c.assess(grade, support, profile)["neural008_numeric_claim_targets"]
        rem = "mode_interaction:eog_gain:rem_recall"
        f1 = "mode_interaction:eog_gain:macro_f1"
        result = claims.check_claims([{"id": rem, "value": None}, {"id": f1, "abstain": True},
                                      {"id": "internal_neural_understanding", "value": 1}], targets)
        self.assertEqual(result["counts"]["undefined_assertions"], 1)
        self.assertEqual(result["counts"]["finite_assertions"], 0)
        self.assertEqual(result["counts"]["consistent"], 1)
        self.assertEqual(result["counts"]["abstain"], 1)
        self.assertEqual(result["counts"]["unsupported"], 1)
        self.assertEqual(result["counts"]["not_submitted"], 4)
        self.assertEqual(result["verification_denominator"], 1)

    def test_wrong_negative_assertion_is_not_scientific_failure_of_panel(self):
        grade, support, profile, _ = fixture.fixture()
        report = fixture.c.assess(grade, support, profile)
        targets = report["neural008_numeric_claim_targets"]
        key = "frozen_program:eog_gain:macro_f1"
        self.assertGreater(targets[key]["aggregate"], 0)
        result = claims.check_claims([{"id": key, "value": -.5}], targets)
        self.assertEqual(result["counts"]["inconsistent"], 1)
        self.assertEqual(report["status"], "complete_descriptive_comparison")
        self.assertFalse(report["research_qualified"])


if __name__ == "__main__":
    unittest.main()
