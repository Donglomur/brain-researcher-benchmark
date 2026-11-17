"""Independent contract controls, derived before reading the implementation.

All fixtures are generated arithmetic controls. They are not acquired ABR data,
annotation validation, a trained baseline or an authentic reproduction result.
"""
import copy
import importlib.util
from pathlib import Path
import unittest

MODULE_PATH = Path(__file__).resolve().parents[1] / "abr_evaluator.py"
SPEC = importlib.util.spec_from_file_location("abr_independent_test_subject", MODULE_PATH)
abr = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(abr)


def prediction(case, value, *, abstain=False):
    return {"case_id": case, "threshold_db": value, "censoring": "none", "abstain": abstain,
            "uncertainty": {"lower_db": value - 5, "upper_db": value + 5, "coverage": 0.95}}


def reference():
    # Two series for animal A, one for B; unequal counts expose pooled scoring.
    return {
        "task_id": "NEURAL-SCOPE-20261114-ABR-TRANSFER",
        "contract_sha256": "3ac11adf902d863075f6c38ee76365321a1fe44f23fde898e7f13c6b6a3c0f86",
        "target_release": "zenodo:15619100", "evidence_kind": "generated_engineering_control",
        "animal_roster": [
            {"animal_id": "A", "genetic_background": "C57BL/6NTacCdh23+"},
            {"animal_id": "B", "genetic_background": "C57BL/6N"}],
        "cases": [
            {"case_id": "A-low", "animal_id": "A", "stimulus": {"kind": "tone", "frequency_hz": 3000},
             "annotation": {"kind": "exact", "value_db": 20}},
            {"case_id": "A-click", "animal_id": "A", "stimulus": {"kind": "click"},
             "annotation": {"kind": "exact", "value_db": 40}},
            {"case_id": "B-high", "animal_id": "B", "stimulus": {"kind": "tone", "frequency_hz": 42000},
             "annotation": {"kind": "exact", "value_db": 30}}]}


def predictions():
    return [prediction("A-low", 20), prediction("A-click", 60), prediction("B-high", 30)]


class IndependentEndpointTests(unittest.TestCase):
    def test_equal_animals_not_equal_cases(self):
        report = abr.evaluate(reference(), predictions(), bootstrap_replicates=200)
        # A: (0+20)/2=10; B:0. Equal-animal MAE=(10+0)/2=5.
        self.assertEqual(report["primary_mae_db"], 5)
        self.assertNotAlmostEqual(report["primary_mae_db"], 20 / 3)
        metrics = report["analysis"]["metrics"]
        self.assertEqual(metrics["absolute_error_db"]["animal_contributions"], {"A": 10, "B": 0})
        self.assertEqual(metrics["signed_error_db"]["value"], 5)
        self.assertEqual(metrics["within_5_db"]["value"], 0.75)
        self.assertEqual(metrics["within_10_db"]["value"], 0.75)
        self.assertEqual((report["expected_animals"], report["expected_cases"]), (2, 3))
        self.assertFalse(report["scientifically_qualified"])

    def test_abstention_does_not_remove_difficult_finite_prediction(self):
        rows = predictions()
        rows[1]["abstain"] = True
        report = abr.evaluate(reference(), rows, bootstrap_replicates=200)
        self.assertEqual(report["primary_mae_db"], 5)
        self.assertEqual(report["abstained_valid_predictions"], 1)
        self.assertEqual(report["abstention_fraction_all_cases"], 1 / 3)
        self.assertEqual(report["analysis"]["metrics"]["abstain"]["value"], 0.25)

    def test_declared_censoring_does_not_change_annotation_or_loss(self):
        rows = predictions()
        rows[1]["censoring"] = "right"
        report = abr.evaluate(reference(), rows, bootstrap_replicates=200)
        self.assertEqual(report["primary_mae_db"], 5)
        self.assertEqual(report["analysis"]["metrics"]["within_5_db"]["eligible_cases"], 3)

    def test_censoring_distance_and_exact_only_diagnostics(self):
        ref = reference()
        ref["cases"][1]["annotation"] = {"kind": "right_censored", "lower_db": 95,
                                                "semantics_evidence": "Generated right-censor control, not native semantics"}
        ref["cases"][2]["annotation"] = {"kind": "left_censored", "upper_db": 15,
                                                "semantics_evidence": "Generated left-censor control, not native semantics"}
        rows = [prediction("A-low", 25), prediction("A-click", 100), prediction("B-high", 20)]
        report = abr.evaluate(ref, rows, bootstrap_replicates=200)
        # A=(5+0)/2=2.5; B=5, so mean3.75. Bounds are not exact labels.
        self.assertEqual(report["primary_mae_db"], 3.75)
        metrics = report["analysis"]["metrics"]
        for key in ("signed_error_db", "within_5_db", "within_10_db", "interval_coverage"):
            self.assertEqual(metrics[key]["eligible_cases"], 1)
            self.assertEqual(metrics[key]["eligible_animals"], 1)
        self.assertEqual(metrics["signed_error_db"]["value"], 5)
        self.assertEqual(metrics["within_5_db"]["value"], 1)
        self.assertEqual(metrics["within_10_db"]["value"], 1)

    def test_paired_animal_differences_and_cluster_bootstrap(self):
        baseline = [prediction("A-low", 30), prediction("A-click", 40), prediction("B-high", 50)]
        report = abr.evaluate(reference(), predictions(), baseline, bootstrap_replicates=2000, seed=17)
        paired = report["paired_comparison"]
        # Candidate animal MAEs[10,0]; baseline[5,20]; paired deltas[5,-20].
        self.assertEqual(paired["baseline_primary_mae_db"], 12.5)
        self.assertEqual(paired["candidate_minus_baseline_mae_db"], -7.5)
        self.assertEqual(paired["animal_differences"], {"A": 5, "B": -20})
        # Exhaustive n=2 bootstrap means are -20,-7.5,-7.5,5.
        self.assertEqual(paired["bootstrap"]["lower"], -20)
        self.assertEqual(paired["bootstrap"]["upper"], 5)
        self.assertEqual(paired["bootstrap"]["animal_count"], 2)

    def test_missing_prediction_withholds_all_aggregate_scores(self):
        report = abr.evaluate(reference(), predictions()[:-1], bootstrap_replicates=200)
        self.assertIsNone(report["primary_mae_db"])
        self.assertIsNone(report["analysis"])
        self.assertEqual((report["expected_cases"], report["expected_animals"]), (3, 2))
        self.assertEqual(report["prediction_coverage"], 2 / 3)
        self.assertEqual(sum(row["status"] == "missing" for row in report["ledger"]), 1)

    def test_nonfinite_or_bad_required_uncertainty_invalidates_submission(self):
        for field, value in (("threshold_db", float("nan")), ("threshold_db", float("inf")),
                             ("threshold_db", True), ("uncertainty", {"lower_db": 20, "upper_db": 10, "coverage": 0.95})):
            with self.subTest(field=field, value=value):
                rows = predictions()
                rows[0][field] = value
                report = abr.evaluate(reference(), rows, bootstrap_replicates=200)
                self.assertIsNone(report["primary_mae_db"])
                self.assertEqual(report["valid_required_predictions"], 2)

    def test_duplicate_and_unknown_predictions_do_not_silently_disappear(self):
        for extra in (copy.deepcopy(predictions()[0]), prediction("extra", 50)):
            with self.subTest(case_id=extra["case_id"]):
                report = abr.evaluate(reference(), predictions() + [extra], bootstrap_replicates=200)
                self.assertFalse(report["submission_complete"])
                self.assertIsNone(report["primary_mae_db"])
                self.assertEqual(report["expected_cases"], 3)

    def test_missing_baseline_does_not_create_paired_complete_case_result(self):
        report = abr.evaluate(reference(), predictions(), predictions()[:-1], bootstrap_replicates=200)
        self.assertEqual(report["primary_mae_db"], 5)
        self.assertFalse(report["paired_comparison"]["baseline_complete"])
        self.assertIsNone(report["paired_comparison"]["candidate_minus_baseline_mae_db"])

    def test_click_cannot_be_converted_to_100_hz_tone(self):
        ref = reference()
        ref["cases"][1]["stimulus"] = {"kind": "tone", "frequency_hz": 100}
        with self.assertRaises(abr.ContractError):
            abr.evaluate(ref, predictions())

    def test_absent_rostered_animal_and_duplicate_reference_case_rejected(self):
        ref = reference()
        ref["cases"].pop()
        with self.assertRaises(abr.ContractError):
            abr.evaluate(ref, predictions())
        ref = reference()
        ref["cases"].append(copy.deepcopy(ref["cases"][0]))
        with self.assertRaises(abr.ContractError):
            abr.evaluate(ref, predictions())

    def test_unverified_full_roster_still_cannot_admit_authentic_score(self):
        ref = reference()
        ref["evidence_kind"] = "unverified_prepared_reference"
        ref["animal_roster"] = []
        ref["cases"] = []
        rows = []
        # A generated104-animal roster tests the gate, not the native census.
        for index in range(104):
            animal, case = f"animal-{index}", f"case-{index}"
            ref["animal_roster"].append({"animal_id": animal,
                 "genetic_background": "C57BL/6NTacCdh23+" if index < 54 else "C57BL/6N"})
            ref["cases"].append({"case_id": case, "animal_id": animal, "stimulus": {"kind": "click"},
                                 "annotation": {"kind": "exact", "value_db": 40}})
            rows.append(prediction(case, 40))
        report = abr.evaluate(ref, rows)
        self.assertTrue(report["submission_complete"])
        self.assertIsNone(report["primary_mae_db"])
        self.assertIsNone(report["analysis"])
        self.assertEqual(report["expected_animals"], 104)
        self.assertFalse(report["benchmark_runnable"])
        self.assertFalse(report["scientifically_qualified"])

    def test_paper_and_historical_nonmonotone_rules_are_distinct(self):
        result = abr.audit_threshold_rules([25, 30, 35, 40, 45, 50, 55, 60], [0, 0, 1, 0, 1, 1, 1, 1])
        self.assertEqual(result["historical_v0_1_1_db"], 35)
        self.assertEqual(result["declared_paper_rule_db"], 45)
        self.assertTrue(result["rules_disagree"])
        self.assertTrue(result["not_annotation_or_censoring_inference"])

    def test_rule_boundary_cases_do_not_invent_censoring(self):
        for levels, probabilities, historical, paper in (
            ([15, 20, 25], [0, 0, 0], 25, None),
            ([15, 20, 25], [1, 1, 1], 15, 15),
            ([15], [1], 15, None),
            ([15, 20], [0.5, 0.5], 20, None)):
            with self.subTest(levels=levels, probabilities=probabilities):
                result = abr.audit_threshold_rules(levels, probabilities)
                self.assertEqual(result["historical_v0_1_1_db"], historical)
                self.assertEqual(result["declared_paper_rule_db"], paper)
                self.assertTrue(result["not_annotation_or_censoring_inference"])


if __name__ == "__main__":
    unittest.main()
