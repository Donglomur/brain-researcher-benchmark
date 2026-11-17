"""Generated numerical and identity controls; no authentic neural observations."""
import copy
import importlib.util
import math
from pathlib import Path
import struct
import unittest

spec = importlib.util.spec_from_file_location("marmoset_scorer", Path(__file__).with_name("scorer.py"))
scorer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scorer)


def ident(n):
    return format(n, "032x")


def fixture(condition="wn_to_wn", second_seed=False):
    labels = [name for name, count in scorer.CLASSES.items() for _ in range(count)]
    cells = [{"cell_id": ident(i + 1), "published_class": label} for i, label in enumerate(labels)]
    # Unequal preparation sizes intentionally detect cell-weighted macro summaries.
    preparations = [{"dataset": d, "cells": roster} for d, roster in
                    zip(sorted(scorer.DATASETS), (cells[:51], cells[51:]))]
    domain = scorer.TARGET_DOMAIN[condition]
    streams = []
    for i, prep in enumerate(preparations):
        seeds = [None] if domain == "WN" else ([1, 2] if second_seed else [1])
        for seed in seeds:
            streams.append({"stream_id": ident(1000 + len(streams)), "dataset": prep["dataset"],
                "stimulus": domain, "seed": seed, "sequence_sha256": "a" * 64,
                "repeat_ids": [ident(2000), ident(2001)], "repeat_sequence_sha256": ["a" * 64] * 2,
                "frame_ids": [ident(3000 + j) for j in range(3)], "alignment_evidence_sha256": "b" * 64})
    policy = {"schema": "marmoset-protected-score-policy-v1", "task_id": scorer.TASK,
        "source_release": "10.12751/g-node.t43ph1", "condition": condition,
        "training_policy_sha256": "c" * 64, "cohort_evidence_sha256": "d" * 64,
        "complete_stream_census_sha256": "e" * 64, "rate_floor": 0.01,
        "coverage_policy": "all_cells_or_null", "preparations": preparations, "streams": streams}
    target = {"schema": "marmoset-target-counts-v1", "task_id": scorer.TASK, "condition": condition,
              "training_policy_sha256": "c" * 64, "unit": scorer.UNIT, "streams": []}
    candidate = {**target, "schema": "marmoset-predictions-v1", "model_sha256": "1" * 64, "streams": []}
    reference = {**candidate, "model_sha256": "2" * 64, "streams": []}
    for stream in streams:
        roster = next(p["cells"] for p in preparations if p["dataset"] == stream["dataset"])
        common = {"stream_id": stream["stream_id"], "cell_ids": [c["cell_id"] for c in roster],
                  "frame_ids": stream["frame_ids"], "dtype": "<f8"}
        for bundle, values in ((target, [0, 1, 2, 2, 3, 4]),
                               (candidate, [1, 2, 3]), (reference, [3, 2, 1])):
            packet = {**common, "values": struct.pack("<" + "d" * len(values) * len(roster), *(values * len(roster)))}
            if bundle is target:
                packet["repeat_ids"] = stream["repeat_ids"]
            bundle["streams"].append(packet)
    return policy, target, candidate, reference


def run_score(operands):
    return scorer.score(*operands, **{name + "_sha256": scorer.fingerprint(value)
        for name, value in zip(("policy", "targets", "candidate", "reference"), operands)})


def replace_first(packet, values):
    width = struct.calcsize("<" + scorer.DTYPES[packet["dtype"]])
    packet["values"] = struct.pack("<" + scorer.DTYPES[packet["dtype"]] * len(values), *values) + packet["values"][len(values) * width:]


class TestScore(unittest.TestCase):
    def test_complete_endpoint_and_likelihood_is_over_repeats(self):
        result = run_score(fixture())
        self.assertEqual(len(result["cells"]), 170)
        self.assertEqual([p["cells"] for p in result["preparations"]], [51, 119])
        self.assertAlmostEqual(result["equal_preparation_descriptive"]["paired_delta_r"], 2)
        row = result["cells"][0]
        actual = row["candidate_poisson_nll"]
        oracle = sum(lam - count * math.log(lam) + math.lgamma(count + 1)
                     for count, lam in zip([0, 1, 2, 2, 3, 4], [1, 2, 3] * 2)) / 6
        mean_wrong = sum(lam - count * math.log(lam) + math.lgamma(count + 1)
                         for count, lam in zip([1, 2, 3], [1, 2, 3])) / 3
        self.assertAlmostEqual(actual, oracle)
        self.assertNotAlmostEqual(actual, mean_wrong)
        self.assertEqual(row["repeat_observations"], 6)

    def test_equal_preparation_summary_and_paired_not_pooled(self):
        operands = fixture()
        packet = operands[2]["streams"][1]
        packet["values"] = struct.pack("<" + "d" * 119 * 3, *([3, 2, 1] * 119))
        result = run_score(operands)
        self.assertAlmostEqual(result["equal_preparation_descriptive"]["candidate_r"], 0)
        self.assertAlmostEqual(result["equal_preparation_descriptive"]["paired_delta_r"], 1)

    def test_constant_prediction_does_not_silently_shrink_denominator(self):
        operands = fixture()
        replace_first(operands[2]["streams"][0], [2, 2, 2])
        result = run_score(operands)
        self.assertEqual(len(result["cells"]), 170)
        self.assertEqual(result["cells"][0]["candidate_undefined"], ["constant_prediction"])
        self.assertEqual(result["preparations"][0]["candidate_r_defined_cells"], 50)
        self.assertIsNone(result["preparations"][0]["candidate_r_median_all_cells"])
        self.assertIsNone(result["equal_preparation_descriptive"]["paired_delta_r"])
        self.assertIsNotNone(result["equal_preparation_descriptive"]["reference_r"])

    def test_constant_target_retained_with_finite_likelihood(self):
        operands = fixture()
        replace_first(operands[1]["streams"][0], [0] * 6)
        result = run_score(operands)
        self.assertEqual(result["cells"][0]["reference_undefined"], ["constant_repeat_average_target"])
        self.assertEqual(result["cells"][0]["candidate_poisson_nll"], 2)

    def test_six_conditions_and_seed_specific_repeat_averages(self):
        for condition in scorer.TARGET_DOMAIN:
            with self.subTest(condition=condition):
                result = run_score(fixture(condition, second_seed=True))
                self.assertEqual(result["condition"], condition)
                self.assertTrue(result["historical_test_selected_cohort"])
        operands = fixture("wn_to_nm_source_only", second_seed=True)
        # Seed 2 has the reversed frozen sequence: averaging across seeds would
        # produce a constant target. Concatenation must retain perfect r=1.
        replace_first(operands[1]["streams"][1], [4, 3, 2, 2, 1, 0])
        replace_first(operands[2]["streams"][1], [3, 2, 1])
        row = run_score(operands)["cells"][0]
        self.assertAlmostEqual(row["candidate_r"], 1)
        self.assertEqual(row["updates"], 6)
        self.assertEqual(len(row["streams"]), 2)

    def test_missing_or_misordered_support_refuses(self):
        changes = [lambda p: p[2]["streams"].pop(),
                   lambda p: p[2]["streams"][0]["cell_ids"].reverse(),
                   lambda p: p[2]["streams"][0]["frame_ids"].reverse(),
                   lambda p: p[1]["streams"][0]["repeat_ids"].reverse(),
                   lambda p: p[2]["streams"][0].update(values=b""),
                   lambda p: p[0]["preparations"][0]["cells"].pop()]
        for change in changes:
            # Deep copy prevents intentional fixture identity aliases from
            # changing the frozen policy at the same time as a submitted packet.
            operands = tuple(copy.deepcopy(item) for item in fixture())
            change(operands)
            with self.assertRaises(scorer.InputError):
                run_score(operands)

    def test_wrong_domain_calibration_units_and_sequence_refuse(self):
        for change in (lambda p: p[2].update(condition="nm_to_wn_wn_assisted"),
                       lambda p: p[3].update(training_policy_sha256="9" * 64),
                       lambda p: p[2].update(unit="spikes_per_second"),
                       lambda p: p[0]["streams"][0].update(stimulus="NM"),
                       lambda p: p[0]["streams"][0].update(repeat_sequence_sha256=["a" * 64, "b" * 64]),
                       lambda p: p[0].update(coverage_policy="drop_undefined")):
            operands = fixture()
            change(operands)
            with self.assertRaises(scorer.InputError):
                run_score(operands)

    def test_nonfinite_negative_and_fractional_counts_refuse(self):
        for operand, value in ((1, -1), (1, 0.5), (1, math.nan), (2, math.inf), (2, -1)):
            operands = fixture()
            replace_first(operands[operand]["streams"][0], [value])
            with self.assertRaises(scorer.InputError):
                run_score(operands)

    def test_external_pins_detect_body_and_policy_mutation(self):
        operands = fixture()
        pins = {name + "_sha256": scorer.fingerprint(value) for name, value in
                zip(("policy", "targets", "candidate", "reference"), operands)}
        replace_first(operands[2]["streams"][0], [9])
        with self.assertRaisesRegex(scorer.InputError, "identity mismatch"):
            scorer.score(*operands, **pins)
        pins["candidate_sha256"] = scorer.fingerprint(operands[2])
        operands[0]["rate_floor"] = 0.1
        with self.assertRaisesRegex(scorer.InputError, "identity mismatch"):
            scorer.score(*operands, **pins)

    def test_floor_affects_poisson_not_correlation(self):
        operands = fixture()
        replace_first(operands[2]["streams"][0], [0, 0.001, 0.002])
        first = run_score(operands)["cells"][0]
        operands[0]["rate_floor"] = 1
        second = run_score(operands)["cells"][0]
        self.assertEqual(first["candidate_r"], second["candidate_r"])
        self.assertNotEqual(first["candidate_poisson_nll"], second["candidate_poisson_nll"])

    def test_large_and_tiny_nonconstant_correlation_and_count_precision(self):
        for x in ([1e-300, 2e-300, 3e-300], [1e308, 1.1e308, 1.2e308],
                  [2**53, 2**53 + 2, 2**53 + 4]):
            self.assertAlmostEqual(scorer.pearson(x, [0, 1, 2])["r"], 1)
        with self.assertRaises(scorer.InputError):
            scorer.number(2**53 + 1, count=True)
        self.assertGreater(scorer.poisson_nll(2**53, 2**53, 0.01), 0)
        for k in (1, 10, 255, 256, 1024):
            for lam in (0.01, 5, k, 2 * k):
                expected = lam - k * math.log(lam) + math.lgamma(k + 1)
                self.assertAlmostEqual(scorer.poisson_nll(k, lam, 0.01), expected, places=9)

    def test_no_operand_mutation_or_file_access(self):
        from unittest.mock import patch
        operands = fixture()
        before = [scorer.fingerprint(item) for item in operands]
        with patch("builtins.open", side_effect=AssertionError("scoring must not open files")):
            run_score(operands)
        self.assertEqual(before, [scorer.fingerprint(item) for item in operands])


if __name__ == "__main__":
    unittest.main(verbosity=2)
