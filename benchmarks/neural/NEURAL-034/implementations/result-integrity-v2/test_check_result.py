"""Generated operator-record controls; no source data, targets, or execution."""

import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest import mock


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("neural034_result_v2", HERE / "check_result.py")
INSPECTOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INSPECTOR)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    body = (json.dumps(value, sort_keys=True, allow_nan=False) + "\n").encode()
    path.write_bytes(body)
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


class ResultIntegrity(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve() / "generated-result"
        attempt = self.root / "attempt"
        attempt.mkdir(parents=True)
        program = b"# Generated inert source; never executed.\n"
        (attempt / "program.py").write_bytes(program)
        program_sha = hashlib.sha256(program).hexdigest()
        previous = None
        commits, units, rows = [], [], []
        for fold in range(7):
            unit = f"fold-{fold:02d}"
            folder = attempt / unit
            probabilities = [{"query_id": format(fold * 20 + i, "024x"), "probability": 0.2}
                             for i in range(20)]
            output = write(folder / "probabilities.json", {
                "schema_version": 1, "probabilities": probabilities})
            commitment = write(folder / "commit.json", {
                "status": "removed_producer_output_committed", "program_sha256": program_sha,
                "previous_commit_sha256": previous, "producer_removed_before_capture": True,
                "all_candidate_holder_volume_absent": True, "output": output})
            previous = commitment["sha256"]
            commits.append(previous)
            execution = write(folder / "execution.json", {
                "candidate_id": "NEURAL-034", "unit_id": unit, "status": "unit_committed",
                "all_owned_absent": True, "program_sha256": program_sha,
                "commit_sha256": previous, "output": output})
            units.append({"unit_id": unit, "status": "unit_committed", "all_owned_absent": True,
                          "execution_sha256": execution["sha256"]})
            rows.extend({"fold": fold, **row} for row in probabilities)
        aggregate = write(attempt / "probabilities.json", {"schema_version": 1, "probabilities": rows})
        write(attempt / "aggregate_commit.json", {
            "status": "all_seven_removed_producers_committed", "all_units_absent_before_private_grade": True,
            "program_sha256": program_sha, "submission_sha256": aggregate["sha256"],
            "unit_commit_sha256": commits, "last_commit_sha256": previous})
        self.grade = {
            "status": "scored", "score": {"balanced_accuracy": 0.5, "log_loss": 2.0},
            "co_primary_metrics": {"balanced_accuracy": 0.5, "log_loss": 2.0},
            "directions": {"balanced_accuracy": "higher", "log_loss": "lower"},
            "per_mouse": [{"fold": i, "balanced_accuracy": 0.5, "log_loss": 2.0} for i in range(7)],
            "reference_metrics": {name: {"balanced_accuracy": 0.25, "log_loss": 1.0}
                                  for name in INSPECTOR.COMPARATORS},
            "signed_candidate_minus_reference": {name: {"balanced_accuracy": 0.25, "log_loss": 1.0}
                                                for name in INSPECTOR.COMPARATORS},
        }
        grade = write(attempt / "grade/score.json", self.grade)
        inner = write(attempt / "execution.json", {
            "status": "program_scored", "all_owned_absent": True, "private_grade_dispatched": True,
            "units": units, "program_sha256": program_sha,
            "grade": {"score_sha256": grade["sha256"], "submission_sha256": aggregate["sha256"],
                      "absence_verified": True}})
        write(self.root / "outer_execution.json", {
            "candidate_id": "NEURAL-034", "status": "program_scored",
            "inner_execution_sha256": inner["sha256"], "all_owned_absent": True,
            "all_process_groups_absent_and_reaped": True, "all_owned_cli_processes_absent": True,
            "controller_direct_handle_reaped": True})

    def replace_grade(self, grade):
        """Keep record hashes coherent; tests must catch semantic contradictions."""
        updated = write(self.root / "attempt/grade/score.json", grade)
        path = self.root / "attempt/execution.json"
        inner = json.loads(path.read_bytes())
        inner["grade"]["score_sha256"] = updated["sha256"]
        updated = write(path, inner)
        path = self.root / "outer_execution.json"
        outer = json.loads(path.read_bytes())
        outer["inner_execution_sha256"] = updated["sha256"]
        write(path, outer)

    def test_complete_result_retains_mixed_metrics_and_every_control(self):
        result = INSPECTOR.check(self.root)
        self.assertEqual(result["co_primary_metrics"], {"balanced_accuracy": 0.5, "log_loss": 2.0})
        self.assertEqual(result["reference_metrics"], self.grade["reference_metrics"])
        self.assertEqual(result["signed_candidate_minus_reference"], self.grade["signed_candidate_minus_reference"])
        self.assertEqual(result["per_mouse"], self.grade["per_mouse"])
        # Positive accuracy difference is favorable; positive loss is adverse.
        self.assertEqual(result["signed_candidate_minus_reference"]["glial"],
                         {"balanced_accuracy": 0.25, "log_loss": 1.0})
        self.assertNotIn("scientific_success", result)
        self.assertFalse(result["actual_runtime_independently_attested_by_this_checker"])

    def test_preserved_predecessor_accepts_false_comparison_successor_rejects_it(self):
        grade = copy.deepcopy(self.grade)
        grade["signed_candidate_minus_reference"]["behavior"]["log_loss"] = -1.0
        self.replace_grade(grade)
        self.assertEqual(INSPECTOR.predecessor().check(self.root)["cases"], 140)
        with self.assertRaisesRegex(ValueError, "behavior: exact candidate-minus-reference"):
            INSPECTOR.check(self.root)

    def test_each_comparator_and_metric_rejects_one_ulp_disagreement(self):
        for name in INSPECTOR.COMPARATORS:
            for metric in ("balanced_accuracy", "log_loss"):
                grade = copy.deepcopy(self.grade)
                grade["signed_candidate_minus_reference"][name][metric] = math.nextafter(
                    grade["signed_candidate_minus_reference"][name][metric], math.inf)
                self.replace_grade(grade)
                with self.subTest(name=name, metric=metric), self.assertRaisesRegex(ValueError, "exact candidate-minus-reference"):
                    INSPECTOR.check(self.root)

    def test_reference_pairs_require_domains_and_exact_nonboolean_numbers(self):
        invalid = [{"balanced_accuracy": True, "log_loss": 1.0},
                   {"balanced_accuracy": 1.01, "log_loss": 1.0},
                   {"balanced_accuracy": -0.01, "log_loss": 1.0},
                   {"balanced_accuracy": 0.25, "log_loss": -1.0},
                   {"balanced_accuracy": "0.25", "log_loss": 1.0},
                   {"balanced_accuracy": 0.25},
                   {"balanced_accuracy": 0.25, "log_loss": 1.0, "extra": 0}]
        for value in invalid:
            grade = copy.deepcopy(self.grade)
            grade["reference_metrics"]["constant"] = value
            self.replace_grade(grade)
            with self.subTest(value=value), self.assertRaises(ValueError):
                INSPECTOR.check(self.root)

    def test_missing_extra_or_absent_references_are_not_six_controls(self):
        for case in ("absent", "missing", "extra"):
            grade = copy.deepcopy(self.grade)
            if case == "absent":
                del grade["reference_metrics"]
            elif case == "missing":
                del grade["reference_metrics"]["time_scrambled"]
            else:
                grade["reference_metrics"]["other"] = {"balanced_accuracy": 0.25, "log_loss": 1.0}
            self.replace_grade(grade)
            with self.subTest(case=case), self.assertRaisesRegex(ValueError, "all six reference"):
                INSPECTOR.check(self.root)

    def test_score_alias_and_directions_cannot_contradict_primary(self):
        for key, value in (("score", {"balanced_accuracy": 0.75, "log_loss": 2.0}),
                           ("score", {"balanced_accuracy": 0.5, "log_loss": True}),
                           ("score", None), ("directions", None),
                           ("directions", {"balanced_accuracy": "higher", "log_loss": "higher"})):
            grade = copy.deepcopy(self.grade)
            grade[key] = value
            self.replace_grade(grade)
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                INSPECTOR.check(self.root)

    def test_references_cannot_hide_nonfinite_exponent(self):
        grade = copy.deepcopy(self.grade)
        grade["reference_metrics"]["amplitude"]["log_loss"] = float("inf")
        with self.assertRaisesRegex(ValueError, "finite nonboolean"):
            INSPECTOR.comparisons(grade)

    def test_original_closure_requirement_is_retained(self):
        path = self.root / "outer_execution.json"
        outer = json.loads(path.read_bytes())
        outer["all_owned_absent"] = False
        write(path, outer)
        with self.assertRaisesRegex(ValueError, "closed all_owned_absent"):
            INSPECTOR.check(self.root)

    def test_changed_predecessor_cannot_execute(self):
        path = self.root / "wrong-predecessor.py"
        path.write_text("raise AssertionError('must not execute')\n")
        with mock.patch.object(INSPECTOR, "PREDECESSOR", path):
            with self.assertRaisesRegex(ValueError, "reviewed predecessor inspector identity"):
                INSPECTOR.check(self.root)


if __name__ == "__main__":
    unittest.main()
