"""Generated controls only: no recording, private target, model or native run."""
import importlib
import json
import math
from pathlib import Path
import sys
import unittest
from fractions import Fraction
from unittest.mock import patch

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "registered-runtime" / "programme"))
sys.path.insert(0, str(HERE))
s = importlib.import_module("statistics_v2")


def generated_arrays(prediction=None):
    target = np.repeat(np.array([[-0.5], [0.5]]), 2, axis=1)
    prediction = target if prediction is None else np.full_like(target, prediction)
    targets = {(p, r): target for p in s.PARTICIPANTS for r in s.ROIS}
    candidates = {(p, r, s.PRIMARY): prediction for p in s.PARTICIPANTS for r in s.ROIS}
    references = {(p, r, m): target for p in s.PARTICIPANTS for r in s.ROIS for m in s.REFERENCE_MODELS}
    return targets, candidates, references


class Arithmetic(unittest.TestCase):
    def test_preserved_counterexample_uses_actual_coordinate_scores(self):
        targets, candidates, references = generated_arrays(5e153)
        key = (s.PARTICIPANTS[0], s.ROIS[0])
        scores = s.coordinate_scores(targets[key], candidates[key + (s.PRIMARY,)])
        self.assertEqual(scores["status"], "defined")
        self.assertTrue(np.isfinite(scores["r2"]).all())
        with np.errstate(over="ignore"):
            self.assertFalse(math.isfinite(float(scores["r2"].mean())))
        # Independent SSE/SST: 2*(5e153)^2 / (2*0.5^2) ~= 1e308.
        self.assertAlmostEqual(s._mean(scores["r2"]) / -1e308, 1.0)
        draw = s._score_draw(targets, candidates, references, list(range(10)), [0, 1])
        self.assertEqual(draw["status"], "defined")
        self.assertEqual(len(draw["values"]), 3)
        for family in s.FAMILIES:
            self.assertEqual(set(draw["values"][family]), set(s.ROIS))
            for value in draw["values"][family].values():
                self.assertAlmostEqual(value / -1e308, 1.0)
        json.dumps(draw, allow_nan=False)

    def test_ten_person_mean_does_not_overflow(self):
        self.assertFalse(math.isfinite(sum([-1e308] * 10) / 10))
        self.assertEqual(s._mean([-1e308] * 10), -1e308)

    def test_paired_values_are_not_separately_rounded(self):
        a = [1.0, 1.0]
        b = [1.0, math.nextafter(1.0, 0.0)]
        self.assertEqual(s._mean(a) - s._mean(b), 0.0)
        self.assertEqual(s._paired_mean(a, b), 2 ** -54)

    def test_mean_and_quantile_underflow_refuse_nonzero_as_zero(self):
        tiny = math.ulp(0.0)
        with self.assertRaises(s.ArithmeticRangeError):
            s._mean([tiny, 0.0, 0.0])
        with self.assertRaises(s.ArithmeticRangeError):
            s._linear_quantile([0.0, tiny], Fraction(1, 4))
        self.assertEqual(s._mean([tiny] * 10), tiny)
        self.assertEqual(s._mean([-tiny, tiny]), 0.0)

    def test_signed_extreme_interpolation_and_ordinary_quantile(self):
        self.assertEqual(s._linear_quantile([-1e308, 1e308], Fraction(1, 2)), 0.0)
        self.assertEqual(s._linear_quantile([-1e308, 1e308], Fraction(1, 4)), -5e307)
        for q in (0, 0.25, 0.5, 0.75, 1):
            self.assertAlmostEqual(s._linear_quantile([7, -2, 3, 11, 0], q),
                                   float(np.quantile([7, -2, 3, 11, 0], q)))

    def test_constant_resample_and_bad_reference_block_draw(self):
        args = generated_arrays()
        result = s._score_draw(*args, list(range(10)), [0, 0])
        self.assertEqual(result["status"], "undefined_coordinate_score")
        args[2][s.PARTICIPANTS[9], s.ROIS[-1], s.REFERENCE_MODELS[1]] = np.full((2, 2), np.inf)
        result = s._score_draw(*args, list(range(10)), [0, 1])
        self.assertEqual(result["status"], "undefined_coordinate_score")

    def test_exact_ten_people_and_arithmetic_failure_propagation(self):
        args = generated_arrays()
        with self.assertRaises(ValueError):
            s._score_draw(*args, [0] * 9, [0, 1])
        with patch.object(s, "_mean", side_effect=s.ArithmeticRangeError("generated")):
            result = s._score_draw(*args, list(range(10)), [0, 1])
        self.assertEqual(result["status"], "undefined_arithmetic_range")

    def test_nonfinite_and_misaligned_support_refused(self):
        for value in (math.inf, -math.inf, math.nan):
            with self.assertRaises(s.ArithmeticRangeError):
                s._mean([value])
        with self.assertRaises(ValueError):
            s._paired_mean([1, 2], [1])


class Orchestration(unittest.TestCase):
    """Stub per-draw computation to test the actual 20000-draw dispatcher cheaply."""

    def test_floor_is_not_weakened_for_generated_tests(self):
        for draws in (1, 19999, True):
            with self.assertRaises(ValueError):
                s.crossed_bootstrap({}, {}, {}, ["a"], {"a": "g"}, draws, 2)

    def test_full_requested_count_and_no_replacement_of_failed_draws(self):
        calls = []
        valid = {"status": "defined", "values": {f: dict.fromkeys(s.ROIS, 1.0) for f in s.FAMILIES}}

        def score(*args):
            people, indices = args[-2:]
            self.assertEqual(len(people), 10)
            # Source-equivalent adjacent videos are resampled together.
            self.assertEqual(indices.count(0), indices.count(1))
            calls.append((people.tolist(), indices))
            return {"status": "undefined_coordinate_score", "values": None} if len(calls) == 7 else valid

        with patch.object(s, "_score_draw", side_effect=score), patch.object(s, "_linear_quantile") as quantile:
            result = s.crossed_bootstrap({}, {}, {}, ["a", "b", "c"],
                                         {"a": "g", "b": "g", "c": "h"}, 20000, 81)
        self.assertEqual(len(calls), 20000)
        self.assertEqual(result["undefined_draws"], 1)
        self.assertIsNone(result["intervals"])
        quantile.assert_not_called()
        # Independently replay the first RNG calls, including order and extents.
        rng = np.random.default_rng(81)
        expected_people = rng.integers(0, 10, size=10).tolist()
        expected_groups = rng.integers(0, 2, size=2)
        self.assertEqual(calls[0], (expected_people, [i for g in expected_groups for i in ((0, 1) if g == 0 else (2,))]))

    def test_full_families_exact_bonferroni_tails_and_interval_failure(self):
        valid = {"status": "defined", "values": {f: dict.fromkeys(s.ROIS, -1e308) for f in s.FAMILIES}}
        probabilities = []

        def quantile(values, probability):
            self.assertEqual(len(values), 20000)
            probabilities.append(probability)
            return -1e308

        with patch.object(s, "_score_draw", return_value=valid), patch.object(s, "_linear_quantile", side_effect=quantile):
            result = s.crossed_bootstrap({}, {}, {}, ["a"], {"a": "g"}, 20000, 2)
        self.assertEqual(result["status"], "descriptive_uncalibrated")
        self.assertEqual(set(result["intervals"]), set(s.FAMILIES))
        self.assertEqual(len(probabilities), 3 * 46 * 2)
        self.assertEqual(set(probabilities), {Fraction(1, 1840), Fraction(1839, 1840)})
        self.assertFalse(result["refitting"])
        json.dumps(result, allow_nan=False)
        with patch.object(s, "_score_draw", return_value=valid), patch.object(s, "_linear_quantile", side_effect=s.ArithmeticRangeError("generated")):
            result = s.crossed_bootstrap({}, {}, {}, ["a"], {"a": "g"}, 20000, 2)
        self.assertEqual(result["status"], "unavailable_interval_arithmetic_range")
        self.assertIsNone(result["intervals"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
