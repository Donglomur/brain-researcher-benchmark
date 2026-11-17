"""Invented full-roster regressions; no authentic data or protected targets."""
import importlib.util
import math
from fractions import Fraction
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parent


def load_scorer(name, filename):
    package = types.ModuleType(name)
    package.__path__ = [str(ROOT / "neural003")]
    sys.modules[name] = package
    for part, source in (("prediction_schema", "neural003/prediction_schema.py"),
                         ("scoring", filename)):
        spec = importlib.util.spec_from_file_location(name + "." + part, ROOT / source)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    return module


OLD = load_scorer("original_fixture", "fixtures/scoring_before_overflow.py")
NEW = load_scorer("successor_fixture", "neural003/scoring.py")
ARMS = ("eeg", "contrast_instruction")
MAX = sys.float_info.max


def case(prediction, counts=lambda person: 2):
    outputs, expected, targets = {}, {}, {}
    for person in range(26):
        ids = tuple(format(person * 20000 + index, "032x")
                    for index in range(counts(person)))
        targets[person] = [{"trial_id": ident, "rt_seconds": 1.0} for ident in ids]
        for arm in ARMS:
            expected[(person, arm)] = ids
            outputs[(person, arm)] = [
                {"trial_id": ident, "rt_seconds": prediction(person, arm, index)}
                for index, ident in enumerate(ids)]
    return outputs, expected, targets


def exact_mean(values):
    values = tuple(values)
    return float(sum((Fraction.from_float(v) for v in values), Fraction()) / len(values))


class ScoringRegression(unittest.TestCase):
    def score(self, fixture, scorer=NEW):
        outputs, expected, targets = fixture
        calls = []
        def release():
            calls.append(True)
            return targets
        result = scorer.grade(outputs, expected, release)
        self.assertEqual(calls, [True])
        self.assertEqual(result["people"], 26)
        self.assertEqual(len(result["per_person"]), 26)
        self.assertFalse(result["qualification"])
        self.assertTrue(result["constant_outputs_valid"])
        self.assertFalse(result["positive_eeg_gain_required"])
        return result

    def assert_exact_extreme_means(self, result):
        for arm in ARMS:
            self.assertEqual(result["macro_mae_seconds"][arm],
                             exact_mean(row[arm] for row in result["per_person"]))
        self.assertEqual(result["paired_gain_seconds"],
                         exact_mean(result["paired_person_gains"]))
        self.assertTrue(all(math.isfinite(row[arm])
                            for row in result["per_person"] for arm in ARMS))
        self.assertTrue(math.isfinite(result["paired_gain_seconds"]))

    def test_ordinary_results_and_equal_person_weighting_unchanged(self):
        fixture = case(lambda p, a, i: 1.0 + (p % 5) / 4 if a == "eeg" else 2.5,
                       counts=lambda p: 1 if p == 0 else 3)
        new = self.score(fixture)
        self.assertEqual(new, self.score(fixture, OLD))
        self.assertEqual(new["macro_mae_seconds"]["eeg"],
                         math.fsum((p % 5) / 4 for p in range(26)) / 26)
        pooled = math.fsum(row["eeg"] * row["trials"] for row in new["per_person"]) / 76
        self.assertNotEqual(new["macro_mae_seconds"]["eeg"], pooled)

    def test_per_person_overflow_with_maximum_finite_constants(self):
        fixture = case(lambda p, a, i: MAX if a == "eeg" else MAX / 2)
        with self.assertRaises(OverflowError):
            self.score(fixture, OLD)
        result = self.score(fixture)
        self.assertEqual(result["macro_mae_seconds"]["eeg"], MAX)
        self.assertEqual(result["paired_gain_seconds"], -MAX / 2)
        self.assert_exact_extreme_means(result)

    def test_macro_overflow_with_one_trial_per_person(self):
        fixture = case(lambda p, a, i: 1.0 if a == "eeg" else 1e308, counts=lambda p: 1)
        with self.assertRaises(OverflowError):
            self.score(fixture, OLD)
        result = self.score(fixture)
        self.assertEqual(result["paired_gain_seconds"], 1e308)
        self.assert_exact_extreme_means(result)

    def test_signed_gain_cancellation_preserves_small_residual(self):
        def prediction(person, arm, index):
            if person < 12:
                return MAX if arm == "contrast_instruction" else 1.0
            if person < 24:
                return MAX if arm == "eeg" else 1.0
            return 1e290 if person == 24 and arm == "contrast_instruction" else 1.0
        result = self.score(case(prediction, counts=lambda p: 1))
        self.assert_exact_extreme_means(result)
        self.assertGreater(result["paired_gain_seconds"], 0.0)
        self.assertEqual(result["paired_gain_seconds"], 1e290 / 26)

    def test_zero_and_negative_gains_remain_valid(self):
        for eeg, comparator in ((2.0, 2.0), (3.0, 2.0)):
            fixture = case(lambda p, a, i: eeg if a == "eeg" else comparator)
            result = self.score(fixture)
            self.assertEqual(result, self.score(fixture, OLD))
            self.assertLessEqual(result["paired_gain_seconds"], 0.0)

    def test_incomplete_or_nonfinite_outputs_cannot_release_targets(self):
        for fault in ("missing", "infinity", "nan", "landmark", "wrong_id"):
            outputs, expected, targets = case(lambda p, a, i: 1.0)
            if fault == "missing":
                del outputs[(25, "eeg")]
            elif fault == "wrong_id":
                outputs[(0, "eeg")][0]["trial_id"] = "f" * 32
            else:
                outputs[(0, "eeg")][0]["rt_seconds"] = {
                    "infinity": math.inf, "nan": math.nan, "landmark": 0.1}[fault]
            called = []
            with self.assertRaises(ValueError):
                NEW.grade(outputs, expected, lambda: called.append(True) or targets)
            self.assertEqual(called, [])

    def test_maximum_with_tiny_fractional_terms_uses_exact_fallback(self):
        fixture = case(lambda p, a, i: MAX if i < 2 else 1.25,
                       counts=lambda p: 3)
        result = self.score(fixture)
        expected = exact_mean((MAX, MAX, 0.25))
        self.assertTrue(all(row["eeg"] == expected for row in result["per_person"]))
        self.assertEqual(result["paired_gain_seconds"], 0.0)
        self.assert_exact_extreme_means(result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
