"""Bounded engineering tests of CLI and source-rule boundary contracts."""
import importlib.util
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / "abr_evaluator.py"
spec = importlib.util.spec_from_file_location("abr_evaluator_interface", MODULE)
abr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(abr)


class SourceRuleBoundaries(unittest.TestCase):
    def test_nonmonotone_disagreement(self):
        result = abr.audit_threshold_rules([25, 30, 35, 40, 45, 50, 55, 60], [0, 0, 1, 0, 1, 1, 1, 1])
        self.assertEqual(result["historical_v0_1_1_db"], 35)
        self.assertEqual(result["declared_paper_rule_db"], 45)
        self.assertTrue(result["rules_disagree"])

    def test_negative_and_positive_boundaries_are_not_labels(self):
        result = abr.audit_threshold_rules([15, 20, 25], [0, 0, 0])
        self.assertEqual(result["historical_v0_1_1_db"], 25)
        self.assertIsNone(result["declared_paper_rule_db"])
        self.assertTrue(result["not_annotation_or_censoring_inference"])
        result = abr.audit_threshold_rules([25, 15, 20], [1, 1, 1])
        self.assertEqual(result["historical_v0_1_1_db"], 15)
        self.assertEqual(result["declared_paper_rule_db"], 15)

    def test_single_and_half_probability(self):
        self.assertIsNone(abr.audit_threshold_rules([15], [1])["declared_paper_rule_db"])
        self.assertIsNone(abr.audit_threshold_rules([15, 20], [0.5, 0.5])["declared_paper_rule_db"])

    def test_rule_shape_validation(self):
        for levels, probabilities in [([], []), ([15, 20], [1]), ([15, 15], [0, 1]), ([15], [1.1]), ([15], [True])]:
            with self.subTest(levels=levels, probabilities=probabilities), self.assertRaises(abr.ContractError):
                abr.audit_threshold_rules(levels, probabilities)


class StrictJSONInterface(unittest.TestCase):
    def test_duplicate_keys_and_nonfinite_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            for content in ['{"case_id":"a","case_id":"b"}', '{"threshold_db": NaN}', '{"threshold_db": Infinity}']:
                path.write_text(content)
                with self.subTest(content=content), self.assertRaises(abr.ContractError):
                    abr._load(path)

    def test_cli_engineering_report_and_missing_prediction(self):
        reference = {"task_id": abr.TASK_ID, "contract_sha256": abr.CONTRACT_SHA256,
                     "target_release": abr.TARGET_RELEASE, "evidence_kind": "generated_engineering_control",
                     "animal_roster": [{"animal_id": "g-a", "genetic_background": abr.BACKGROUNDS[0]}],
                     "cases": [{"case_id": "g-c", "animal_id": "g-a", "stimulus": {"kind": "click"},
                                "annotation": {"kind": "exact", "value_db": 30}}]}
        predictions = [{"case_id": "g-c", "threshold_db": 35, "censoring": "none", "abstain": True,
                        "uncertainty": {"lower_db": 25, "upper_db": 45, "coverage": 0.95}}]
        with tempfile.TemporaryDirectory() as directory:
            reference_path, prediction_path = Path(directory) / "reference.json", Path(directory) / "prediction.json"
            reference_path.write_text(json.dumps(reference))
            for rows, exit_code, expected in [(predictions, 0, 5), ([], 1, None)]:
                prediction_path.write_text(json.dumps(rows))
                process = subprocess.run([sys.executable, str(MODULE), "--reference", str(reference_path), "--predictions", str(prediction_path),
                                          "--bootstrap-replicates", "10"], capture_output=True, text=True,
                                         env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, timeout=10)
                self.assertEqual(process.returncode, exit_code, process.stderr)
                result = json.loads(process.stdout)
                self.assertEqual(result["primary_mae_db"], expected)
                self.assertFalse(result["scientifically_qualified"])
                self.assertEqual(result["expected_cases"], 1)

    def test_cli_malformed_reference_is_not_a_score(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text('{"task_id": "a", "task_id": "b"}')
            process = subprocess.run([sys.executable, str(MODULE), "--reference", str(path), "--predictions", str(path)],
                                     capture_output=True, text=True, timeout=10)
            self.assertEqual(process.returncode, 2)
            self.assertIn("duplicate JSON key", process.stderr)
            self.assertEqual(process.stdout, "")


class NumericRangeControls(unittest.TestCase):
    def setUp(self):
        self.reference = {"task_id": abr.TASK_ID, "contract_sha256": abr.CONTRACT_SHA256,
                          "target_release": abr.TARGET_RELEASE, "evidence_kind": "generated_engineering_control",
                          "animal_roster": [{"animal_id": "g-a", "genetic_background": abr.BACKGROUNDS[0]}],
                          "cases": [{"case_id": f"g-{i}", "animal_id": "g-a", "stimulus": {"kind": "click"},
                                     "annotation": {"kind": "exact", "value_db": 30}} for i in range(3)]}
        self.predictions = [{"case_id": f"g-{i}", "threshold_db": 1e308, "censoring": "none", "abstain": False,
                             "uncertainty": {"lower_db": 25, "upper_db": 45, "coverage": 0.95}} for i in range(3)]

    def test_large_finite_mean_is_representable(self):
        result = abr.evaluate(self.reference, self.predictions, bootstrap_replicates=10)
        self.assertEqual(result["primary_mae_db"], 1e308)
        json.dumps(result, allow_nan=False)

    def test_unrepresentable_integer_is_invalid_and_keeps_ledger(self):
        self.predictions[0]["threshold_db"] = 10 ** 1000
        result = abr.evaluate(self.reference, self.predictions, bootstrap_replicates=10)
        self.assertIsNone(result["primary_mae_db"])
        self.assertFalse(result["submission_complete"])
        self.assertEqual(len(result["ledger"]), 3)
        json.dumps(result, allow_nan=False)

    def test_unrepresentable_derived_width_withholds_aggregate(self):
        self.predictions[0]["uncertainty"].update(lower_db=-1e308, upper_db=1e308)
        result = abr.evaluate(self.reference, self.predictions, bootstrap_replicates=10)
        self.assertIsNone(result["primary_mae_db"])
        self.assertEqual(result["status"], "numeric_range_exceeded_no_aggregate_score")
        self.assertEqual(len(result["ledger"]), 3)
        json.dumps(result, allow_nan=False)

    def test_extreme_paired_bootstrap_interpolation(self):
        result = abr.animal_bootstrap({"a": -1e308, "b": 1e308}, replicates=100, seed=0)
        self.assertEqual(result["estimate"], 0)
        json.dumps(result, allow_nan=False)

    def test_bad_animal_id_is_reference_error(self):
        reference = copy.deepcopy(self.reference)
        reference["cases"][0]["animal_id"] = []
        with self.assertRaises(abr.ContractError):
            abr.evaluate(reference, self.predictions, bootstrap_replicates=10)


if __name__ == "__main__":
    unittest.main()
