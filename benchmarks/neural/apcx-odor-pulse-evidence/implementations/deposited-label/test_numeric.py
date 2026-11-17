"""Invented-only range controls; no native inputs, dependencies, or fitting."""
import json
import math
import sys
import unittest

import grader
import participant_core as core
import released_profile as profile


MAX_FINITE = sys.float_info.max
MIN_SUBNORMAL = math.ulp(0.0)


def invented(targets=(2, 4, 6), sessions=((50,), (50,), (50,))):
    trials = []
    for animal, session_sizes in enumerate(sessions):
        for session, size in enumerate(session_sizes):
            for index in range(size):
                trials.append({
                    "animal": f"INVENTED_ANIMAL_{animal}",
                    "session": f"INVENTED_SESSION_{animal}_{session}",
                    "trial": index, "target": targets[animal],
                    "spikes": [[0] * 90], "units": [0],
                    "old_flags_owner_only": {0: []},
                    "diagnostic_reference_owner_only": {},
                })
    return profile.invented_packet(trials, bytes(range(32)), "matched")


class NumericControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.regular = invented()
        cls.zero = invented(targets=(0, 0, 0))
        cls.unequal = invented(sessions=((50,), (50, 75), (100,)))

    def records(self, fixture, predict):
        return [{"case_id": c["case_id"], "count": predict(c)} for c in fixture[1]["cases"]]

    def grade(self, fixture, records):
        packet, owner = fixture
        return grader.grade(owner, profile.submission(packet, records))

    def assert_complete(self, report, owner):
        self.assertEqual(report["status"], "COMPLETE_DEPOSITED_LABEL_SCORE_ONLY")
        self.assertEqual(report["coverage"], 1.0)
        self.assertEqual(report["valid_unique_cases"], len(owner["cases"]))
        self.assertEqual(report["required_cases"], len(owner["cases"]))
        self.assertEqual(len(report["animal_metrics"]), 3)
        self.assertEqual(set(report["session_metrics"]), set(owner["sessions"]))
        self.assertFalse(report["scientific_qualification"])
        self.assertFalse(report["physical_delivery_claim"])
        self.assertTrue(report["historical_selection_caveat_required"])
        self.assertEqual(report["benchmark_count_delta"], 0)
        self.assertEqual(report["remaining_physical_primary_holds"], list(core.HOLDS))
        self.assertEqual(report["errors"], [])
        json.dumps(report, allow_nan=False)

    def metric_groups(self, report):
        return [report["pooled_metrics"], *report["animal_metrics"].values(),
                *report["session_metrics"].values()]

    def test_maxfinite_complete_submission_keeps_every_case_and_finite_score(self):
        report = self.grade(self.regular, self.records(self.regular, lambda c: MAX_FINITE))
        self.assert_complete(report, self.regular[1])
        self.assertEqual(report["primary_metric"]["value"], MAX_FINITE)
        self.assertEqual(report["animal_macro_mae"], MAX_FINITE)
        for metrics in self.metric_groups(report):
            self.assertEqual(metrics["rmse"], MAX_FINITE)
            self.assertEqual(metrics["mae"], MAX_FINITE)
            self.assertIsNone(metrics["r_squared"])

    def test_repeated_minimum_subnormals_are_not_erased_by_means(self):
        report = self.grade(self.zero, self.records(self.zero, lambda c: MIN_SUBNORMAL))
        self.assert_complete(report, self.zero[1])
        self.assertEqual(report["primary_metric"]["value"], MIN_SUBNORMAL)
        self.assertEqual(report["animal_macro_mae"], MIN_SUBNORMAL)
        for metrics in self.metric_groups(report):
            self.assertEqual(metrics["rmse"], MIN_SUBNORMAL)
            self.assertEqual(metrics["mae"], MIN_SUBNORMAL)

    def test_opposite_maxfinite_predictions_obey_existing_negative_clip(self):
        records = self.records(self.zero, lambda c: MAX_FINITE if c["split_rank"] % 2 else -MAX_FINITE)
        report = self.grade(self.zero, records)
        self.assert_complete(report, self.zero[1])
        for metrics in self.metric_groups(report):
            self.assertEqual(metrics["mae"], MAX_FINITE / 2)
            self.assertAlmostEqual(metrics["rmse"] / MAX_FINITE, math.sqrt(0.5), places=15)
        self.assertEqual(report["clipping_policy"], "Finite negative counts clipped at0; no data-derived upper clip.")

    def test_negative_maxfinite_counts_remain_valid_and_clip_to_zero(self):
        report = self.grade(self.zero, self.records(self.zero, lambda c: -MAX_FINITE))
        self.assert_complete(report, self.zero[1])
        self.assertEqual(report["primary_metric"]["value"], 0.0)
        self.assertEqual(report["animal_macro_mae"], 0.0)

    def test_unequal_trial_and_session_counts_keep_equal_animal_weight(self):
        errors = {f"INVENTED_ANIMAL_{i}": value for i, value in enumerate((1, 2, 4))}
        report = self.grade(self.unequal, self.records(self.unequal, lambda c: c["count"] + errors[c["animal"]]))
        self.assert_complete(report, self.unequal[1])
        self.assertEqual(report["required_cases"], 55)
        self.assertEqual([m["n"] for m in report["animal_metrics"].values()], [10, 25, 20])
        self.assertAlmostEqual(report["primary_metric"]["value"], 7 / 3, places=15)
        self.assertAlmostEqual(report["animal_macro_mae"], 7 / 3, places=15)
        self.assertAlmostEqual(report["pooled_metrics"]["rmse"], math.sqrt(430 / 55), places=15)
        self.assertAlmostEqual(report["pooled_metrics"]["mae"], 140 / 55, places=15)

    def test_opposite_residual_signs_contribute_to_both_error_metrics(self):
        report = self.grade(self.regular, self.records(self.regular, lambda c: c["count"] + (2 if c["split_rank"] % 2 else -2)))
        self.assert_complete(report, self.regular[1])
        self.assertEqual(report["primary_metric"]["value"], 2.0)
        self.assertEqual(report["animal_macro_mae"], 2.0)

    def test_ordinary_regression_and_classification_have_independent_answers(self):
        cases = [{"case_id": str(i), "count": i} for i in range(4)]
        predictions = {str(i): {"count": p} for i, p in enumerate((1, 1, 2, 2))}
        metrics = grader._metrics(cases, predictions)
        self.assertEqual(metrics["rmse"], math.sqrt(0.5))
        self.assertEqual(metrics["mae"], 0.5)
        self.assertAlmostEqual(metrics["r_squared"], 0.6, places=15)
        self.assertEqual(metrics["r_squared_status"], "DEFINED")
        classified = grader._classification(
            [{"case_id": "low", "high": 0}, {"case_id": "high", "high": 1}],
            {"low": {"prob_high": 0.25}, "high": {"prob_high": 0.75}})
        self.assertEqual(classified["balanced_accuracy"], 1.0)
        self.assertEqual(classified["log_loss"], -math.log(0.75))

    def test_existing_prediction_types_and_nonfinite_rejections_remain(self):
        for invalid in (True, "1", None, float("nan"), float("inf"), -float("inf"), 10**1000):
            with self.subTest(type=type(invalid).__name__, value=str(invalid)[:20]):
                records = self.records(self.regular, lambda c: c["count"])
                records[0]["count"] = invalid
                report = self.grade(self.regular, records)
                self.assertEqual(report["status"], "INCOMPLETE_OR_INVALID_NO_AGGREGATE_SCORE")
                self.assertIsNone(report["primary_metric"])
                self.assertIn("NONFINITE_OR_NONNUMERIC_COUNT", [r["reason"] for r in report["errors"]])

    def test_missing_duplicate_and_partial_probability_still_have_no_score(self):
        records = self.records(self.regular, lambda c: c["count"])
        partial_probability = [dict(r) for r in records]
        partial_probability[0]["prob_high"] = 0.5
        for invalid in (records[:-1], records + [dict(records[0])], partial_probability):
            with self.subTest(records=len(invalid)):
                report = self.grade(self.regular, invalid)
                self.assertEqual(report["status"], "INCOMPLETE_OR_INVALID_NO_AGGREGATE_SCORE")
                self.assertIsNone(report["primary_metric"])

    def test_maxfinite_paired_bootstrap_keeps_signed_difference_and_all_trials(self):
        maximum = self.records(self.zero, lambda c: MAX_FINITE)
        exact = self.records(self.zero, lambda c: 0)
        for first, second, expected in ((maximum, exact, MAX_FINITE),
                                        (exact, maximum, -MAX_FINITE),
                                        (maximum, maximum, 0.0)):
            with self.subTest(expected=expected):
                report = grader.paired_conditional_bootstrap(self.zero[1], first, second, replicates=21)
                self.assertEqual(report["status"], "CONDITIONAL_RELEASE_TRIAL_BOOTSTRAP_ONLY")
                self.assertEqual(report["replicates"], 21)
                self.assertEqual(report["observed_difference"], expected)
                self.assertEqual(report["percentile_95_interval"], [expected, expected])
                self.assertTrue(report["all_draws_finite"])
                self.assertFalse(report["population_confidence_interval"])
                self.assertFalse(report["chronological_block_claim"])
                json.dumps(report, allow_nan=False)

    def test_minimum_subnormal_paired_bootstrap_keeps_degenerate_interval(self):
        tiny = self.records(self.zero, lambda c: MIN_SUBNORMAL)
        exact = self.records(self.zero, lambda c: 0)
        for first, second, expected in ((tiny, exact, MIN_SUBNORMAL), (exact, tiny, -MIN_SUBNORMAL)):
            with self.subTest(expected=expected):
                report = grader.paired_conditional_bootstrap(self.zero[1], first, second, replicates=21)
                self.assertEqual(report["observed_difference"], expected)
                self.assertEqual(report["percentile_95_interval"], [expected, expected])
                self.assertTrue(report["all_draws_finite"])

    def test_percentile_signed_and_subnormal_interpolation_retains_same_weights(self):
        self.assertEqual(grader._percentile([MIN_SUBNORMAL, 2 * MIN_SUBNORMAL], 0.5), 2 * MIN_SUBNORMAL)
        self.assertEqual(grader._percentile([-MAX_FINITE, MAX_FINITE], 0.5), 0.0)
        self.assertEqual(grader._percentile([-MIN_SUBNORMAL, MIN_SUBNORMAL], 0.5), 0.0)
        self.assertEqual(grader._percentile([2.0, 6.0], 0.25), 3.0)


if __name__ == "__main__":
    unittest.main()
