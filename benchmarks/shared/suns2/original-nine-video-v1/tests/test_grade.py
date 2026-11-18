"""Coordinator controls using generated MAT files only."""

import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from scipy.io import savemat

from suns2_benchmark import grade
from suns2_benchmark.constants import VIDEO_IDS, TASK_SLUG

PROCEDURE = "f" * 64


def write_json(path, value):
    raw = (json.dumps(value, indent=2) + "\n").encode()
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def mat_record(path, variable, value):
    savemat(str(path), {variable: value}, do_compression=True)
    raw = path.read_bytes()
    return {"path": str(path), "variable": variable,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


class GradingControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="suns2-generated-grade-")
        self.root = Path(self.temp.name).resolve()
        self.reference = self.root / "operator"
        self.reference.mkdir()
        self.submission = self.root / "candidate"
        (self.submission / "masks").mkdir(parents=True)
        self.spec_path = self.root / "operator-reference.json"
        truth = np.zeros((50, 50, 2), dtype=bool)
        truth[13, 7, 0] = True
        truth[18, 9, 1] = True
        author = truth[:, :, :1]
        cases, outputs = [], []
        for video in VIDEO_IDS:
            g = mat_record(self.reference / f"{video}-gt.mat", "FinalMasks", truth)
            a = mat_record(self.reference / f"{video}-author.mat", "Masks", author)
            c = mat_record(self.submission / "masks" / f"{video}.mat", "Masks", truth)
            cases.append({"video_id": video, "ground_truth": g,
                          "author_prediction": a})
            outputs.append({"video_id": video, "path": f"masks/{video}.mat",
                            "bytes": c["bytes"], "sha256": c["sha256"]})
        self.spec = {"schema": "suns2-operator-reference/v1", "task": TASK_SLUG,
                     "cases": cases,
                     "expected_reference": {
                         "cases": {v: {"recall": 0.5, "precision": 1.0, "f1": 2 / 3}
                                   for v in VIDEO_IDS}, "mean_f1": 2 / 3},
                     "provenance": {"input_manifest_sha256": "a" * 64,
                                    "saved_result_sha256": "b" * 64}}
        self.digest = write_json(self.spec_path, self.spec)
        self.manifest = {"schema": "suns2-candidate-submission/v1",
                         "condition": "paper_data", "procedure_digest": PROCEDURE,
                         "cases": outputs}
        write_json(self.submission / "submission.json", self.manifest)

    def tearDown(self):
        self.temp.cleanup()

    def run_grade(self, **overrides):
        arguments = dict(reference_spec_path=self.spec_path,
                         reference_spec_sha256=self.digest,
                         submission_directory=self.submission,
                         expected_condition="paper_data",
                         expected_procedure_digest=PROCEDURE)
        arguments.update(overrides)
        return grade.grade_submission(**arguments)

    def test_complete_generated_panel_raises_both_metrics(self):
        result = self.run_grade()
        self.assertEqual(result["status"], "scored_complete_panel")
        self.assertTrue(result["scores"]["descriptive_outcome"][
            "same_panel_geometry_improvement"])
        self.assertEqual(result["scores"]["descriptive_outcome"][
            "original_mean_delta_exact"]["numerator"], "1")
        self.assertEqual(result["scores"]["descriptive_outcome"][
            "original_mean_delta_exact"]["denominator"], "3")
        self.assertFalse(result["execution_scope"]["candidate_production_attested"])
        self.assertFalse(result["execution_scope"]["participant_code_executed"])
        self.assertEqual(len(result["reference_members"]), 18)
        self.assertNotIn(str(self.reference), json.dumps(result))

    def test_wrong_operator_pin_never_loads_mask_bodies(self):
        with patch.object(grade, "load_trusted_mask") as refs, \
             patch.object(grade, "load_candidate_submission") as candidate:
            with self.assertRaises(grade.GradingError):
                self.run_grade(reference_spec_sha256="0" * 64)
            refs.assert_not_called()
            candidate.assert_not_called()

    def test_incomplete_candidate_never_decodes_protected_reference(self):
        self.manifest["cases"].pop()
        write_json(self.submission / "submission.json", self.manifest)
        with patch.object(grade, "load_trusted_mask") as refs:
            with self.assertRaises(ValueError):
                self.run_grade()
            refs.assert_not_called()

    def test_wrong_condition_or_procedure_never_decodes_reference(self):
        for override in ({"expected_condition": "paper_data_official_code"},
                         {"expected_procedure_digest": "e" * 64}):
            with self.subTest(override=override), \
                 patch.object(grade, "load_trusted_mask") as refs:
                with self.assertRaises(ValueError):
                    self.run_grade(**override)
                refs.assert_not_called()

    def test_candidate_file_cannot_be_reference(self):
        self.spec["cases"][0]["ground_truth"]["path"] = str(
            self.submission / "masks" / f"{VIDEO_IDS[0]}.mat")
        self.digest = write_json(self.spec_path, self.spec)
        with patch.object(grade, "load_trusted_mask") as refs:
            with self.assertRaises(grade.GradingError):
                self.run_grade()
            refs.assert_not_called()

    def test_late_bad_reference_support_preflights_before_decode(self):
        self.spec["cases"][-1]["video_id"] = VIDEO_IDS[0]
        self.digest = write_json(self.spec_path, self.spec)
        with patch.object(grade, "load_trusted_mask") as refs:
            with self.assertRaises(grade.GradingError):
                self.run_grade()
            refs.assert_not_called()

    def test_reference_reconstruction_mismatch_is_not_a_win(self):
        self.spec["expected_reference"]["cases"][VIDEO_IDS[-1]]["f1"] = 0.1
        self.digest = write_json(self.spec_path, self.spec)
        with self.assertRaisesRegex(grade.GradingError, "reconstruction mismatch"):
            self.run_grade()

    def test_duplicate_operator_json_key_rejected(self):
        raw = self.spec_path.read_text().replace('"task":', '"task": "bad", "task":', 1)
        self.spec_path.write_text(raw)
        self.digest = hashlib.sha256(raw.encode()).hexdigest()
        with self.assertRaisesRegex(grade.GradingError, "Duplicate JSON key"):
            self.run_grade()

    def test_cli_writes_report_exclusively_and_does_not_attest_generation(self):
        output = self.root / "operator-report.json"
        argv = ["--reference-spec", str(self.spec_path),
                "--reference-spec-sha256", self.digest,
                "--submission", str(self.submission),
                "--condition", "paper_data", "--procedure-digest", PROCEDURE,
                "--output", str(output)]
        with contextlib.redirect_stdout(io.StringIO()):
            grade.main(argv)
        report = json.loads(output.read_bytes())
        self.assertFalse(report["execution_scope"]["native_admission_attested_by_this_function"])
        with self.assertRaises(FileExistsError):
            grade._write_report(output, report)


if __name__ == "__main__":
    unittest.main()
