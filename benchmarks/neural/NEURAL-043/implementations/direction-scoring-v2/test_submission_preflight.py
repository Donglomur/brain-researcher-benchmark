"""Generated public-only controls. No authentic targets or observations."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from direction_scorer import ScoringError, validate_submission_cohort
from validate_submission import preflight_files


def packets(case_id="a", width=16, claim="held_block_within_session", trial_id="trial-a"):
    classes = [str(i) for i in range(width)]
    public = {"task": "NEURAL-043", "case_id": case_id, "classes": classes,
              "claim": claim, "feature_kind": "neural", "ids": [trial_id]}
    submission = {"case_id": case_id, "classes": classes, "ids": [trial_id],
                  "probabilities": [[1 / width] * width]}
    return submission, public


def validate(cases, expected=None, mode="frozen_program"):
    return validate_submission_cohort([x[0] for x in cases], [x[1] for x in cases],
                                     expected_case_ids=expected or [x[1]["case_id"] for x in cases],
                                     access_mode=mode)


class SubmissionPreflightControls(unittest.TestCase):
    def test_complete_public_only_summary_has_no_scores_or_targets(self):
        a, b = packets(), packets("b", width=25, trial_id="trial-b")
        result = validate([b, a], expected=["a", "b"], mode="direct_observation")
        self.assertEqual((result["n_cases"], result["n_predictions"]), (2, 2))
        self.assertEqual([len(s["classes"]) for s in result["strata"]], [16, 25])
        self.assertTrue(result["submission_structure_valid"])
        for field in ("targets_checked", "submission_sealed", "access_mode_delivery_verified",
                      "scientific_qualification"):
            self.assertFalse(result[field])
        self.assertNotIn("balanced_accuracy", result)
        self.assertNotIn("labels", json.dumps(result))

    def test_missing_failed_case_is_not_silently_dropped(self):
        with self.assertRaisesRegex(ScoringError, "complete expected"):
            validate([packets()], expected=["a", "failed-case"])

    def test_probabilities_reuse_current_scoring_constraints(self):
        for value in (True, float("nan"), float("inf"), -1, 2):
            case = packets()
            case[0]["probabilities"][0][0] = value
            with self.subTest(value=value), self.assertRaises(ScoringError):
                validate([case])
        case = packets()
        case[0]["probabilities"][0] = [0.] * 16
        with self.assertRaisesRegex(ScoringError, "simplex"):
            validate([case])

    def test_native_layout_order_and_claim_trial_uniqueness(self):
        a, b = packets(), packets("b", trial_id="trial-b")
        for packet in b:
            packet["classes"] = list(reversed(packet["classes"]))
        with self.assertRaisesRegex(ScoringError, "within native layout"):
            validate([a, b])
        with self.assertRaisesRegex(ScoringError, "duplicate held-out"):
            validate([a, packets("b")])
        with self.assertRaisesRegex(ScoringError, "inconsistent layout"):
            validate([a, packets("b", width=25, claim="held_mouse_anatomical_alignment")])

    def test_shared_trial_across_claims_remains_allowed(self):
        result = validate([packets(), packets("b", claim="held_mouse_anatomical_alignment")])
        self.assertEqual(len(result["strata"]), 2)

    def test_mixed_feature_families_rejected(self):
        a, b = packets(), packets("b", trial_id="trial-b")
        b[1]["feature_kind"] = "history_time"
        with self.assertRaisesRegex(ScoringError, "separately"):
            validate([a, b])

    def files(self, directory):
        submission, public = packets()
        paths = [Path(directory) / name for name in ("public.json", "submission.json", "roster.json")]
        for path, obj in zip(paths, ([public], [submission], ["a"])):
            path.write_text(json.dumps(obj))
        return paths

    def test_file_snapshot_identity_and_combined_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = self.files(directory)
            total = sum(p.stat().st_size for p in paths)
            result = preflight_files(*paths, access_mode="frozen_program", max_input_bytes=total)
            self.assertEqual(result["input_snapshots"]["submission"]["sha256"],
                             hashlib.sha256(paths[1].read_bytes()).hexdigest())
            with self.assertRaisesRegex(ScoringError, "combined input"):
                preflight_files(*paths, access_mode="frozen_program", max_input_bytes=total - 1)

    def test_ambiguous_json_and_nonfinite_values_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = self.files(directory)
            for content, message in (("{\"a\":1,\"a\":2}", "duplicate JSON"), ("[NaN]", "nonfinite JSON")):
                paths[1].write_text(content)
                with self.assertRaisesRegex(ScoringError, message):
                    preflight_files(*paths, access_mode="frozen_program")
            paths = self.files(directory)
            # Overflow tokens are valid JSON syntax but become nonfinite Python
            # floats. Reject them even outside the probability matrix.
            paths[0].write_text(paths[0].read_text().replace('"task":', '"unused_feature": 1e999, "task":'))
            with self.assertRaisesRegex(ScoringError, "nonfinite JSON"):
                preflight_files(*paths, access_mode="frozen_program")

    def test_fresh_process_cli_is_public_only_and_reports_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = self.files(directory)
            command = [sys.executable, "-B", str(Path(__file__).with_name("validate_submission.py")),
                       "--public", str(paths[0]), "--submission", str(paths[1]),
                       "--expected-cases", str(paths[2]), "--access-mode", "frozen_program"]
            good = subprocess.run(command, capture_output=True, text=True, timeout=10)
            self.assertEqual(good.returncode, 0, good.stderr)
            self.assertTrue(json.loads(good.stdout)["submission_structure_valid"])
            self.assertFalse(json.loads(good.stdout)["targets_checked"])
            paths[2].write_text('["a","failed-case"]')
            bad = subprocess.run(command, capture_output=True, text=True, timeout=10)
            self.assertEqual(bad.returncode, 2)
            self.assertEqual(bad.stdout, "")
            self.assertIn("complete expected", bad.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
