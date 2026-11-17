"""Independent, invented full-cohort controls for the Helsinki evaluator.

These are mathematical/source controls, not authentic neonatal EEG evaluations.
Expected scores below are hand-derived rational values, not scorer outputs.
"""

import copy
from fractions import Fraction
from pathlib import Path
import sys
import unittest


HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from protocol import ContractError, MONTAGE, PROTOCOL, fold_map, prepare_reference
from evaluate import evaluate


RECORDINGS = tuple(f"eeg{i}" for i in range(1, 80))
PRIVATE_KEY = b"generated-private-key-0123456789abcd"


def fixture(*, durations=None, labels=None, flags=None):
    """Construct all 79 invented recordings without reading native EEG files."""
    durations = durations or {}
    labels = labels or (lambda recording_id, second: (0, 0, 0))
    flags = flags or {}
    recordings = []
    for recording_id in RECORDINGS:
        duration = durations.get(recording_id, 30)
        columns = [labels(recording_id, second) for second in range(duration)]
        recordings.append({
            "recording_id": recording_id,
            "eeg_sha256": "d" * 64,
            "sample_rate": {"num": 1, "den": 1},
            "sample_count": duration,
            "sample_zero_annotation_second": 0,
            "units": "uV",
            "labels": [[row[expert] for row in columns] for expert in range(3)],
            "quality_flags": [second in flags.get(recording_id, ())
                              for second in range(duration)],
        })
    assignment = fold_map(RECORDINGS, "fixture-seed")
    development = {
        str(fold): [next(recording_id for recording_id in RECORDINGS
                         if assignment[recording_id] != fold)]
        for fold in sorted(set(assignment.values()))
    }
    descriptor = {
        "schema": "helsinki-complete-support-description-v1",
        "assessment_id": "generated-test",
        "protocol_id": PROTOCOL,
        "source_version": "zenodo:4940267-v4",
        "fold_seed": "fixture-seed",
        "representation_sha256": "a" * 64,
        "detector_sha256": "b" * 64,
        "source_admission_sha256": "c" * 64,
        "montage": list(MONTAGE),
        "development_by_fold": development,
        "recordings": recordings,
    }

    def read_samples(recording_id, start, stop):
        # Invented input: deterministic varying values, with the selected
        # invented flagged sample set to zero. No clinical signal is claimed.
        return [[0.0 if second in flags.get(recording_id, ())
                 else (second + 1) * (channel + 1) / 1000.0
                 for channel in range(18)] for second in range(start, stop)]

    reference = prepare_reference(descriptor, read_samples, PRIVATE_KEY)
    return reference, descriptor, read_samples


def predictions(reference, probability):
    return [dict(row, probability=probability) for row in reference.case_rows()]


class MetricControls(unittest.TestCase):
    def assertFractionAlmostEqual(self, actual, numerator, denominator=1):
        self.assertAlmostEqual(actual, float(Fraction(numerator, denominator)), places=13)

    def test_soft_vote_and_each_expert_have_distinct_known_scores(self):
        reference, _, _ = fixture(labels=lambda _rid, _second: (1, 0, 0))
        result = evaluate(reference, predictions(reference, 0.25))
        # q=1/3, p=1/4: (p-q)^2=1/144; expert losses=9/16,1/16,1/16.
        self.assertFractionAlmostEqual(result["primary_soft_vote_brier"], 1, 144)
        for actual, numerator in zip(result["expert_brier"], (9, 1, 1)):
            self.assertFractionAlmostEqual(actual, numerator, 16)
        self.assertEqual(len(result["expert_brier"]), 3)
        self.assertFractionAlmostEqual(result["expert_mean_brier"], 11, 48)
        self.assertFractionAlmostEqual(result["disagreement"], 2, 9)
        self.assertAlmostEqual(result["expert_mean_brier"],
                               result["primary_soft_vote_brier"] + result["disagreement"],
                               places=13)
        self.assertEqual(result["n_cases"], 79)
        self.assertEqual(len(result["infants"]), 79)

    def test_equal_infant_weight_is_not_pooled_window_weight(self):
        reference, _, _ = fixture(
            durations={"eeg79": 108},
            labels=lambda rid, _second: (1, 1, 1) if rid == "eeg79" else (0, 0, 0),
        )
        result = evaluate(reference, predictions(reference, 0))
        # 78 infants have one correct window; infant79 has 79 wrong windows.
        self.assertEqual(result["n_cases"], 157)
        self.assertFractionAlmostEqual(result["primary_soft_vote_brier"], 1, 79)
        self.assertNotAlmostEqual(result["primary_soft_vote_brier"], float(Fraction(79, 157)))
        by_id = {row["recording_id"]: row for row in result["infants"]}
        self.assertEqual(by_id["eeg79"]["n"], 79)
        self.assertFractionAlmostEqual(by_id["eeg79"]["soft_vote_brier"], 1)
        self.assertTrue(all(by_id[rid]["n"] == 1 for rid in RECORDINGS[:-1]))

    def test_target_is_the_final_second_not_window_start_or_next_second(self):
        reference, _, _ = fixture(
            durations={rid: 31 for rid in RECORDINGS},
            labels=lambda _rid, second: (1, 1, 1) if second == 29 else (0, 0, 0),
        )
        rows = predictions(reference, 0)
        # Each recording contributes k29 then k30. Only second29 is positive.
        for index, row in enumerate(rows):
            row["probability"] = 1 if index % 2 == 0 else 0
        result = evaluate(reference, rows)
        self.assertEqual(result["n_cases"], 158)
        self.assertFractionAlmostEqual(result["primary_soft_vote_brier"], 0)
        self.assertEqual(result["expert_brier"], [0.0, 0.0, 0.0])

    def test_original_quality_strata_do_not_censor_primary_support(self):
        reference, _, _ = fixture(
            durations={rid: 32 for rid in RECORDINGS},
            flags={rid: {30} for rid in RECORDINGS},
        )
        rows = predictions(reference, 0)
        # Canonical order has k29,k30,k31 per infant. One original flag at30
        # makes these: no flag, final flag, earlier flag; labels are all zero.
        for index, row in enumerate(rows):
            row["probability"] = 0 if index % 3 == 0 else 1
        result = evaluate(reference, rows)
        self.assertEqual(result["n_cases"], 237)
        self.assertFractionAlmostEqual(result["primary_soft_vote_brier"], 2, 3)
        for infant in result["infants"]:
            self.assertEqual(infant["n"], 3)
            self.assertFractionAlmostEqual(infant["soft_vote_brier"], 2, 3)
            self.assertEqual(set(infant["strata"]), {
                "no_flagged_context", "earlier_context_flagged", "final_second_flagged"})
            for stratum, expected in (("no_flagged_context", 0),
                                      ("earlier_context_flagged", 1),
                                      ("final_second_flagged", 1)):
                self.assertEqual(infant["strata"][stratum]["n"], 1)
                self.assertFractionAlmostEqual(infant["strata"][stratum]["soft_vote_brier"], expected)

    def test_empty_strata_are_undefined_not_zero(self):
        reference, _, _ = fixture()
        result = evaluate(reference, predictions(reference, 0.5))
        for infant in result["infants"]:
            for name in ("earlier_context_flagged", "final_second_flagged"):
                empty = infant["strata"][name]
                self.assertEqual(empty["n"], 0)
                self.assertIsNone(empty["soft_vote_brier"])
                self.assertIsNone(empty["expert_mean_brier"])
                self.assertIsNone(empty["disagreement"])

    def test_valid_constant_priors_are_scored_including_boundary_probabilities(self):
        reference, _, _ = fixture(labels=lambda _rid, _second: (1, 0, 0))
        for probability, numerator, denominator in ((0, 1, 9), (1, 4, 9), (0.5, 1, 36)):
            with self.subTest(probability=probability):
                result = evaluate(reference, predictions(reference, probability))
                self.assertFractionAlmostEqual(result["primary_soft_vote_brier"], numerator, denominator)


class CompletenessControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reference, cls.descriptor, reader = fixture()
        cls.reader = staticmethod(reader)

    def rows(self):
        return predictions(self.reference, 0.25)

    def test_one_missing_prediction_prevents_primary_score(self):
        with self.assertRaises(ContractError):
            evaluate(self.reference, self.rows()[:-1])

    def test_duplicate_replacing_another_case_is_not_complete(self):
        rows = self.rows()
        rows[-1] = dict(rows[0])
        with self.assertRaises(ContractError):
            evaluate(self.reference, rows)

    def test_extra_duplicate_prediction_is_rejected(self):
        rows = self.rows()
        rows.append(dict(rows[0]))
        with self.assertRaises(ContractError):
            evaluate(self.reference, rows)

    def test_extra_unrecognized_case_is_rejected(self):
        rows = self.rows()
        extra = dict(rows[0])
        extra["case_id"] = "0" * len(extra["case_id"])
        rows.append(extra)
        with self.assertRaises(ContractError):
            evaluate(self.reference, rows)

    def test_each_prediction_binding_is_checked(self):
        for key in ("case_id", "assessment_id", "protocol_id", "representation_sha256",
                    "fold", "input_sha256"):
            with self.subTest(key=key):
                rows = self.rows()
                value = rows[0][key]
                rows[0][key] = value + 1 if type(value) is int else "wrong-" + value
                with self.assertRaises(ContractError):
                    evaluate(self.reference, rows)

    def test_nonprobabilities_are_rejected_without_clipping(self):
        for value in (True, False, float("nan"), float("inf"), -float("inf"),
                      -1e-12, 1.0 + 1e-12, "0.25", None):
            with self.subTest(probability=value):
                rows = self.rows()
                rows[0]["probability"] = value
                with self.assertRaises(ContractError):
                    evaluate(self.reference, rows)

    def test_missing_or_extra_prediction_fields_are_rejected(self):
        for variant in ("missing", "extra"):
            with self.subTest(variant=variant):
                rows = self.rows()
                if variant == "missing":
                    del rows[0]["probability"]
                else:
                    rows[0]["unrecognized_field"] = "not in the prediction contract"
                with self.assertRaises(ContractError):
                    evaluate(self.reference, rows)

    def test_missing_infant_is_not_reweighted_to_seventy_eight(self):
        descriptor = copy.deepcopy(self.descriptor)
        descriptor["recordings"].pop()
        with self.assertRaises(ContractError):
            prepare_reference(descriptor, self.reader, PRIVATE_KEY)

    def test_missing_expert_cannot_become_two_expert_fallback(self):
        descriptor = copy.deepcopy(self.descriptor)
        descriptor["recordings"][0]["labels"].pop()
        with self.assertRaises(ContractError):
            prepare_reference(descriptor, self.reader, PRIVATE_KEY)

    def test_nonbinary_annotation_is_rejected(self):
        descriptor = copy.deepcopy(self.descriptor)
        descriptor["recordings"][0]["labels"][0][29] = 2
        with self.assertRaises(ContractError):
            prepare_reference(descriptor, self.reader, PRIVATE_KEY)


if __name__ == "__main__":
    unittest.main()
