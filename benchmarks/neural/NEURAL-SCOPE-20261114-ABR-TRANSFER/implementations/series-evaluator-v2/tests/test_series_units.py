"""Generated controls for repeat-induced bias in the ABR threshold endpoint."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "abr_evaluator.py"
SPEC = importlib.util.spec_from_file_location("abr_series_subject", MODULE_PATH)
abr = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(abr)


def reference():
    return {
        "task_id": abr.TASK_ID, "contract_sha256": abr.CONTRACT_SHA256,
        "target_release": abr.TARGET_RELEASE, "evidence_kind": "generated_engineering_control",
        "animal_roster": [
            {"animal_id": "A", "genetic_background": abr.BACKGROUNDS[0]},
            {"animal_id": "B", "genetic_background": abr.BACKGROUNDS[1]},
        ],
        "cases": [
            {"case_id": "A-tone", "animal_id": "A", "stimulus": {"kind": "tone", "frequency_hz": 3000},
             "annotation": {"kind": "exact", "value_db": 20}},
            {"case_id": "A-click", "animal_id": "A", "stimulus": {"kind": "click"},
             "annotation": {"kind": "exact", "value_db": 40}},
            {"case_id": "B-tone", "animal_id": "B", "stimulus": {"kind": "tone", "frequency_hz": 3000},
             "annotation": {"kind": "exact", "value_db": 30}},
        ],
    }


def prediction(case_id, value):
    return {"case_id": case_id, "threshold_db": value, "censoring": "none", "abstain": False,
            "uncertainty": {"lower_db": value - 5, "upper_db": value + 5, "coverage": 0.95}}


def predictions():
    return [prediction("A-tone", 20), prediction("A-click", 60), prediction("B-tone", 30)]


class SeriesUnitControls(unittest.TestCase):
    def test_repeat_can_dilute_v1_error_but_is_rejected_by_v2(self):
        ref, rows = reference(), predictions()
        self.assertEqual(abr.evaluate(ref, rows, bootstrap_replicates=20)["primary_mae_db"], 5)
        repeat = copy.deepcopy(ref["cases"][0])
        repeat["case_id"] = "A-tone-repeat"
        ref["cases"].append(repeat)
        rows.append(prediction("A-tone-repeat", 20))
        # A's old mean changes from (0+20)/2 to (0+20+0)/3 solely because
        # an existing zero-error stimulus was repeated. B still contributes 0.
        legacy = abr._v1.evaluate(ref, rows, bootstrap_replicates=20)
        self.assertAlmostEqual(legacy["primary_mae_db"], 10 / 3)
        with self.assertRaisesRegex(abr.ContractError, "multiple cases.*animal-by-stimulus"):
            abr.evaluate(ref, rows, bootstrap_replicates=20)

    def test_click_repeats_and_numerically_equal_tone_codes_cannot_bypass(self):
        for index in (0, 1):
            ref = reference()
            repeat = copy.deepcopy(ref["cases"][index])
            repeat["case_id"] += "-second-ear"
            if index == 0:
                repeat["stimulus"]["frequency_hz"] = 3000.0
            # Distinct annotations do not authorize extra primary cases either.
            repeat["annotation"]["value_db"] += 5
            ref["cases"].append(repeat)
            original = copy.deepcopy(ref)
            with self.subTest(index=index), self.assertRaises(abr.ContractError):
                abr.validate_reference(ref)
            self.assertEqual(ref, original)

    def test_valid_series_reuse_exact_v1_scores_and_paired_bootstrap(self):
        ref, rows = reference(), predictions()
        baseline = [prediction("A-tone", 30), prediction("A-click", 40), prediction("B-tone", 50)]
        report = abr.evaluate(ref, rows, baseline, bootstrap_replicates=200, seed=17)
        self.assertEqual(report["primary_mae_db"], 5)
        self.assertEqual(report["analysis"]["metrics"]["absolute_error_db"]["animal_contributions"], {"A": 10, "B": 0})
        self.assertEqual(report["paired_comparison"]["animal_differences"], {"A": 5, "B": -20})
        self.assertEqual(report["paired_comparison"]["candidate_minus_baseline_mae_db"], -7.5)
        self.assertEqual(report.pop("implementation_version"), "series-evaluator-v2")
        self.assertEqual(report.pop("case_unit"), "one assembled animal-by-stimulus series")
        self.assertEqual(report, abr._v1.evaluate(ref, rows, baseline, bootstrap_replicates=200, seed=17))

    def test_native_reference_stays_blocked_and_no_cartesian_census_is_invented(self):
        ref = reference()
        ref["evidence_kind"] = "unverified_prepared_reference"
        ref["animal_roster"] = [{"animal_id": f"g-{i}", "genetic_background": abr.BACKGROUNDS[i >= 54]} for i in range(104)]
        ref["cases"] = [{"case_id": f"g-{i}-click", "animal_id": f"g-{i}", "stimulus": {"kind": "click"},
                         "annotation": {"kind": "exact", "value_db": 30}} for i in range(104)]
        rows = [prediction(case["case_id"], 30) for case in ref["cases"]]
        report = abr.evaluate(ref, rows, bootstrap_replicates=20)
        self.assertEqual(report["status"], "native_semantics_and_population_gate_no_aggregate_score")
        self.assertEqual(report["expected_cases"], 104)
        self.assertIsNone(report["primary_mae_db"])
        self.assertIsNone(report["analysis"])
        self.assertFalse(report["scientifically_qualified"])

    def test_missing_prediction_remains_incomplete_even_with_valid_case_units(self):
        report = abr.evaluate(reference(), predictions()[:-1], bootstrap_replicates=20)
        self.assertEqual(report["status"], "incomplete_submission_no_aggregate_score")
        self.assertEqual(len(report["ledger"]), 3)
        self.assertIsNone(report["primary_mae_db"])

    def test_cli_reference_error_is_distinct_from_candidate_failure(self):
        ref = reference()
        repeat = copy.deepcopy(ref["cases"][0])
        repeat["case_id"] = "repeat"
        ref["cases"].append(repeat)
        with tempfile.TemporaryDirectory() as directory:
            reference_path, predictions_path = Path(directory) / "reference.json", Path(directory) / "predictions.json"
            reference_path.write_text(json.dumps(ref))
            predictions_path.write_text(json.dumps(predictions()))
            process = subprocess.run(
                [sys.executable, "-I", "-B", str(MODULE_PATH), "--reference", str(reference_path),
                 "--predictions", str(predictions_path), "--bootstrap-replicates", "20"],
                capture_output=True, text=True, timeout=10,
            )
        self.assertEqual(process.returncode, 2)
        self.assertEqual(process.stdout, "")
        self.assertIn("multiple cases for one animal-by-stimulus series", process.stderr)
        self.assertIn("A-tone", process.stderr)
        self.assertIn("repeat", process.stderr)


if __name__ == "__main__":
    unittest.main()
