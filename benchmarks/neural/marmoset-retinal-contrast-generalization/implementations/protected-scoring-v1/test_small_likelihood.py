"""Generated complete-panel controls; no authentic observations or fitted models."""
from fractions import Fraction
import importlib.util
import math
from pathlib import Path
import struct
import unittest

spec = importlib.util.spec_from_file_location("marmoset_mean_fixtures", Path(__file__).with_name("test_scorer.py"))
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)


def zero_count_panel(*, two_seeds=False):
    operands = fixtures.fixture("wn_to_nm_source_only" if two_seeds else "wn_to_wn",
                                second_seed=two_seeds)
    operands[0]["rate_floor"] = math.ulp(0.0)
    for stream, packet in zip(operands[0]["streams"], operands[1]["streams"]):
        repeats = 4 if stream["seed"] == 2 else 2
        stream["repeat_ids"] = [fixtures.ident(2000 + i) for i in range(repeats)]
        stream["repeat_sequence_sha256"] = [stream["sequence_sha256"]] * repeats
        packet["repeat_ids"] = stream["repeat_ids"]
        extent = len(packet["cell_ids"]) * repeats * len(packet["frame_ids"])
        packet["values"] = struct.pack("<d", 0.0) * extent
    return operands


def fill(bundle, value_for_stream):
    for i, packet in enumerate(bundle["streams"]):
        packet["values"] = struct.pack("<d", value_for_stream(i)) * (
            len(packet["cell_ids"]) * len(packet["frame_ids"]))


class TestSmallLikelihood(unittest.TestCase):
    def test_positive_small_loss_survives_complete_cell_preparation_and_class_means(self):
        operands = zero_count_panel()
        tiny = math.ulp(0.0)
        for bundle in operands[2:]:
            fill(bundle, lambda _: tiny)
        result = fixtures.run_score(operands)
        self.assertEqual(len(result["cells"]), 170)
        for cell in result["cells"]:
            self.assertEqual(cell["candidate_poisson_nll"], tiny)
            self.assertEqual(cell["reference_poisson_nll"], tiny)
            self.assertIsNone(cell["candidate_r"])
        for group in result["preparations"] + result["class_descriptive"]:
            self.assertEqual(group["candidate_poisson_nll_per_observation"], tiny)
            self.assertEqual(group["reference_poisson_nll_per_observation"], tiny)

    def test_unequal_repeat_counts_preserve_subnormal_weighted_loss(self):
        operands = zero_count_panel(two_seeds=True)
        tiny = math.ulp(0.0)
        fill(operands[2], lambda i: tiny if i % 2 == 0 else 3 * tiny)
        fill(operands[3], lambda _: tiny)
        result = fixtures.run_score(operands)
        expected = float((Fraction(tiny) * 6 + Fraction(3 * tiny) * 12) / 18)
        self.assertEqual(expected, 2 * tiny)
        for cell in result["cells"]:
            self.assertEqual(cell["repeat_observations"], 18)
            self.assertEqual(cell["candidate_poisson_nll"], expected)
            self.assertEqual(cell["reference_poisson_nll"], tiny)
        for group in result["preparations"] + result["class_descriptive"]:
            self.assertEqual(group["candidate_poisson_nll_per_observation"], expected)

    def test_normal_point_losses_are_scaled_as_they_are_produced(self):
        # Instrument arithmetic consumption, not garbage-collector behavior.
        # A complete score must not accumulate every raw point loss before it
        # starts the established scale-before-sum reduction.
        from unittest.mock import patch
        counter = {"produced": 0, "scaled": 0, "max_pending": 0}
        original = fixtures.scorer.poisson_nll

        class PointLoss(float):
            def __truediv__(self, denominator):
                counter["scaled"] += 1
                return float(self) / denominator

        def tracked_loss(*args):
            value = original(*args)
            counter["produced"] += 1
            counter["max_pending"] = max(counter["max_pending"],
                                         counter["produced"] - counter["scaled"])
            return PointLoss(value)

        ordinary = fixtures.run_score(fixtures.fixture())
        with patch.object(fixtures.scorer, "poisson_nll", side_effect=tracked_loss):
            observed = fixtures.run_score(fixtures.fixture())
        self.assertEqual(observed, ordinary)
        self.assertEqual(counter["produced"], 2 * 170 * 2 * 3)
        self.assertEqual(counter["scaled"], counter["produced"])
        self.assertLessEqual(counter["max_pending"], 1)

    def test_normal_loss_and_complete_undefined_correlations_are_retained(self):
        operands = zero_count_panel(two_seeds=True)
        fill(operands[2], lambda i: 1.0 if i % 2 == 0 else 4.0)
        fill(operands[3], lambda _: 2.0)
        result = fixtures.run_score(operands)
        for cell in result["cells"]:
            self.assertEqual(cell["candidate_poisson_nll"], 3.0)
            self.assertEqual(cell["reference_poisson_nll"], 2.0)
            self.assertEqual(cell["candidate_undefined"],
                             ["constant_repeat_average_target"])
        self.assertIsNone(result["equal_preparation_descriptive"]["candidate_r"])
        self.assertEqual(sum(p["cells"] for p in result["preparations"]), 170)


if __name__ == "__main__":
    unittest.main(verbosity=2)
