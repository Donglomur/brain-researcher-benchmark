"""Generated finite numerical boundary controls; no original participant data."""
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("small_error_evaluator", ROOT / "evaluator.py")
e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)


def panel(target, deltas, unequal=False):
    roster = ["generated-a", "generated-b", "generated-c"]
    first, second = "Postcentral_gyrus", "Precentral_gyrus"
    supports = [[first, second], [first], [second]] if unequal else [[first]] * 3
    records = [{"ID": pid, "region": region, "PAF": 5.0, "INT": target}
               for pid, regions in zip(roster, supports) for region in regions]
    reference = {"task_id": e.TASK_ID, "component": "parameter_table_statistics",
                 "expected_participants": roster, "participant_region": records}
    folds = []
    for index, pid in enumerate(roster):
        predictions = [{"ID": pid, "region": row["region"], "metric": metric,
                        "prediction": row[metric] + (deltas[index] if metric == "INT" else 0)}
                       for row in records if row["ID"] == pid for metric in e.METRICS]
        folds.append({"fold": str(index), "train_participants": [p for p in roster if p != pid],
                      "test_participants": [pid], "predictions": predictions})
    return reference, {"folds": folds}


class SmallPredictionErrors(unittest.TestCase):
    def test_complete_unequal_panel_retains_representable_root_error(self):
        reference, submission = panel(1e-200, [1e-200, 3e-200, 3e-200], unequal=True)
        result = e.evaluate_heldout(reference, submission)
        score = result["scores"]["INT"]
        actual = score["candidate"]["root_participant_macro_mse"]
        self.assertTrue(math.isclose(actual / 1e-200, math.sqrt(19 / 3), rel_tol=2e-15))
        self.assertNotEqual(actual / 1e-200, math.sqrt(5))  # pooled-row weighting is wrong
        self.assertEqual(score["scored_participant_count"], 3)
        self.assertEqual([r["region_count"] for r in score["participants"]], [2, 1, 1])
        self.assertEqual(score["train_only_region_mean"]["root_participant_macro_mse"], 0)
        self.assertTrue(all(r["candidate"]["mse"] == 0 for r in score["participants"]))

    def test_training_mean_retains_representable_subnormal_target(self):
        smallest = math.nextafter(0.0, 1.0)
        reference, submission = panel(smallest, [0, 0, 0])
        score = e.evaluate_heldout(reference, submission)["scores"]["INT"]
        self.assertTrue(all(r["train_only_region_mean"]["mae"] == 0 for r in score["participants"]))
        self.assertEqual(score["candidate"]["root_participant_macro_mse"], 0)

    def test_normal_zero_and_overflow_policies_unchanged(self):
        reference, submission = panel(10.0, [1, 3, 3], unequal=True)
        score = e.evaluate_heldout(reference, submission)["scores"]["INT"]
        self.assertEqual(score["candidate"]["root_participant_macro_mse"], math.sqrt(19 / 3))
        reference, submission = panel(10.0, [0, 0, 0])
        self.assertEqual(e.evaluate_heldout(reference, submission)["scores"]["INT"]["candidate"]["root_participant_macro_mse"], 0)
        submission["folds"][0]["predictions"][1]["prediction"] = 1e308
        with self.assertRaises(e.ContractError):
            e.evaluate_heldout(reference, submission)

    def test_real_cli_preserves_small_nonzero_root_error(self):
        reference, submission = panel(1e-200, [1e-200, 1e-200, 1e-200])
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory / "reference.json").write_text(json.dumps(reference))
            (directory / "submission.json").write_text(json.dumps(submission))
            command = [sys.executable, "-B", str(ROOT / "evaluator.py"), "score-heldout",
                       "--reference", str(directory / "reference.json"), "--submission",
                       str(directory / "submission.json"), "--output", str(directory / "score.json")]
            completed = subprocess.run(command, capture_output=True, text=True, timeout=10)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            value = json.loads((directory / "score.json").read_text())
            actual = value["scores"]["INT"]["candidate"]["root_participant_macro_mse"]
            self.assertTrue(math.isclose(actual / 1e-200, 1.0, rel_tol=2e-15))


if __name__ == "__main__":
    unittest.main()
