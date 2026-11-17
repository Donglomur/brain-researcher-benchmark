"""Generated arithmetic controls; no data, author code, fitting or model calls."""
import copy
from fractions import Fraction
import hashlib
import importlib.util
import itertools
import json
import math
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "benchmarks/shared/reward-spacing/programme"


class RewardCurrentBindingsTests(unittest.TestCase):
    def test_complete_current_package_and_preserved_predecessors_are_bound(self):
        path = ROOT / "benchmarks/integrity/current-closures/numeric-reward/SOURCE_BINDINGS.json"
        bindings = json.loads(path.read_bytes())
        self.assertEqual(bindings["schema"], "reward_numeric_current_source_bindings_v1")
        self.assertFalse(bindings["scientific_qualification"])
        self.assertFalse(bindings["authentic_execution_available"])
        self.assertFalse(bindings["execution_authority"])
        self.assertEqual(set(bindings["task_ids"]), {"PAPER-FIND-044", "NEURAL-045", "NEURAL-046"})
        actual = {str(path.relative_to(ROOT)) for path in PACKAGE.rglob("*")
                  if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"}
        self.assertEqual({row["path"] for row in bindings["current_package_files"]}, actual)
        for group in ("current_package_files", "historical_manifests", "source_tests", "canonical_tasks_unchanged"):
            for row in bindings[group]:
                with self.subTest(group=group, path=row["path"]):
                    body = (ROOT / row["path"]).read_bytes()
                    self.assertEqual(len(body), row["bytes"])
                    self.assertEqual(hashlib.sha256(body).hexdigest(), row["sha256"])
        historical = json.loads((PACKAGE / "SOURCE.json").read_bytes())
        old = {row["path"]: row for row in historical["files"]}
        for change in bindings["changed_files"]:
            name = str(Path(change["path"]).relative_to(PACKAGE.relative_to(ROOT)))
            self.assertEqual(change["predecessor"], {k: old[name][k] for k in ("bytes", "sha256")})
        self.assertEqual({row["path"] for row in bindings["historical_manifests"]},
                         {str(PACKAGE.relative_to(ROOT) / name) for name in ("SOURCE.json", "SOURCE_LOCK.json")})


class RewardReferenceMeanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        name = "_numeric_reward_central"
        spec = importlib.util.spec_from_file_location(
            name, PACKAGE / "central/__init__.py",
            submodule_search_locations=[str(PACKAGE / "central")])
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        cls.comparisons = __import__(name + ".comparisons", fromlist=["comparisons"])
        cls.io = __import__(name + ".io", fromlist=["io"])

    def summary(self, candidate, reference):
        closed = {
            "candidate": {"metrics": {"animals": {
                str(i): {"mse": value} for i, value in enumerate(candidate)}}},
            "reference": {"metrics": {"animals": {
                str(i): {"mse": value} for i, value in enumerate(reference)}}},
        }
        obligations = {"candidate": {
            family: {"status": "required_unscorable", "required": True,
                     "reason": "Invented control has no scientific reference.",
                     "support_receipt_sha256": "0" * 64}
            for family in self.comparisons.REFERENCE_FAMILIES}}
        obligations["candidate"]["R0"] = {
            "status": "available_engineering_only", "required": True}
        before = copy.deepcopy((closed, obligations))
        result = self.comparisons.reference_summary(
            "candidate", closed, {"candidate": {"R0": "reference"}},
            {"candidate": "candidate", "reference": "reference"}, obligations)
        self.assertEqual((closed, obligations), before)
        # Exercise the actual strict serializer used by the controller.
        self.assertEqual(json.loads(self.io.encode(result)), result)
        self.assertFalse(result["scientific_qualification"])
        self.assertFalse(result["strongest_reference_improvement_claim_qualified"])
        self.assertTrue(result["any_mandatory_reference_unscorable"])
        self.assertEqual(len(result["families"]), 9)
        self.assertEqual(result["canonical_denominator"], "R0")
        return result

    def assert_mean(self, candidate, reference):
        result = self.summary(candidate, reference)
        skills = [1 - c / r for c, r in zip(candidate, reference)]
        self.assertTrue(all(math.isfinite(x) for x in skills))
        # Independent exact-rational oracle for the already-rounded skills;
        # retain the existing per-animal ratio definition and equal weights.
        expected = float(sum(map(Fraction.from_float, skills), Fraction()) / len(skills))
        actual = result["families"]["R0"]["reference_relative_skill"]
        self.assertTrue(math.isfinite(actual))
        self.assertEqual(actual, expected)
        self.assertEqual(result["primary_status"], "engineering_score_only")
        return actual

    def test_same_large_finite_skills_have_finite_representable_mean(self):
        self.assertEqual(self.assert_mean([1e308] * 3, [1.0] * 3), -1e308)

    def test_mixed_sign_skills_do_not_overflow_before_division(self):
        for candidate in set(itertools.permutations([1e308, 1e308, 0.0])):
            with self.subTest(candidate=candidate):
                self.assert_mean(candidate, [1.0] * 3)

    def test_opposite_sign_skills_cancel_without_changing_weights(self):
        self.assertEqual(self.assert_mean([2.0, 0.0], [1.0, 1.0]), 0.0)

    def test_ordinary_unequal_reference_errors_keep_equal_animal_weights(self):
        self.assertEqual(self.assert_mean([0.5, 18.0, 1.5], [1.0, 9.0, 3.0]), 0.0)

    def test_cancellation_keeps_small_residual_independent_of_animal_order(self):
        for candidate in set(itertools.permutations([1e16, 0.0, 0.0])):
            with self.subTest(candidate=candidate):
                self.assert_mean(candidate, [1.0] * 3)

    def test_subnormal_mse_values_keep_the_existing_relative_skills(self):
        tiny = float.fromhex("0x0.0000000000001p-1022")
        self.assertEqual(self.assert_mean([2 * tiny, 3 * tiny, 0.0], [tiny] * 3),
                         -2 / 3)

    def test_zero_reference_preserves_undefined_status_and_paired_values(self):
        result = self.summary([1e308, 2.0], [1.0, 0.0])
        row = result["families"]["R0"]
        self.assertIsNone(row["reference_relative_skill"])
        self.assertEqual(row["undefined_reference_animals"], ["1"])
        self.assertEqual(row["paired_animals"]["1"],
                         {"candidate_mse": 2.0, "reference_mse": 0.0, "difference": 2.0})
        self.assertEqual(result["primary_status"], "undefined_zero_reference")

    def test_animal_join_still_refuses_mismatched_population(self):
        with self.assertRaisesRegex(self.io.Refusal, "reference summary animal join"):
            self.summary([1.0, 1.0], [1.0])

    def test_missing_primary_reference_stays_unscorable(self):
        result = self.comparisons.reference_summary(
            "candidate", {"candidate": {"metrics": {"animals": {}}}}, {},
            {"candidate": "candidate"},
            {"candidate": {"R0": {"status": "required_unscorable"}}})
        self.assertEqual(result["primary_status"], "required_unscorable")
        self.assertTrue(result["any_mandatory_reference_unscorable"])
        self.assertFalse(result["scientific_qualification"])
        self.assertNotIn("reference_relative_skill", result["families"]["R0"])


if __name__ == "__main__":
    unittest.main()
