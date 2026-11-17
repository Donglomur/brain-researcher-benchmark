"""Generated binding controls; the scientific grader is deliberately stubbed.

No original observation, neural value, image, NumPy import or model is used.
These controls exercise dispatch/integrity, not scientific grading accuracy.
"""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import os
import tempfile
import unittest
from unittest.mock import patch

import attempt_grade as bridge


class AttemptGradeControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="n096-attempt-grade-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        for name in ("operator-bundle", "generated-private-preparation", "generated-sealed-attempt",
                     "native-material", "programme-material"):
            (self.root / name).mkdir()
        self.completion = "a" * 64
        self.attempt_sha = "b" * 64
        self.observation_pin = bridge.pin(b"generated aggregate identity only")
        self.manifest = {
            "schema": "neural096-observation-delivery-manifest/v1",
            "source_binding": {
                "preparation_completion_sha256": self.completion,
                "preparation_receipt": bridge.pin(b"generated preparation receipt"),
                "observation": self.observation_pin,
            },
            "files": {"programme/observations.json": self.observation_pin},
        }
        self.manifest_path = self.root / "operator-bundle/observation-manifest.json"
        body = bridge.encoded(self.manifest)
        self.manifest_path.write_bytes(body)
        self.manifest_sha = bridge.pin(body)["sha256"]
        self.final = {
            "manifest": {"arm": "native", "observation_manifest_sha256": self.manifest_sha,
                         "observation_sha256": self.observation_pin["sha256"],
                         "preparation_completion_sha256": self.completion},
            "receipt": {"schema": "generated final capture"},
            "receipt_pin": bridge.pin(b"generated sealed final receipt"),
            "answer_bytes": b'{"generated_answer":true}\n',
            "log": {"requests": 0},
        }
        self.grader_calls = []
        self.loader = patch.object(bridge, "_attempt_module", return_value=SimpleNamespace(
            verify_final=lambda *_: deepcopy(self.final)))
        self.loader.start()
        self.addCleanup(self.loader.stop)
        self.grader_loader = patch.object(bridge, "_grader_module", return_value=SimpleNamespace(
            grade_submission=self.fake_grade))
        self.grader_mock = self.grader_loader.start()
        self.addCleanup(self.grader_loader.stop)

    def fake_grade(self, prepared, completion, submission, output):
        body = submission.read_bytes()
        self.grader_calls.append((prepared, completion, body))
        result = {"submission": bridge.pin(body), "generated_score": 0.0}
        output.write_bytes(bridge.encoded(result))
        return result

    def run_bridge(self, output="grade", **changes):
        args = {"prepared_directory": self.root / "generated-private-preparation",
                "completion_sha256": self.completion,
                "observation_manifest": self.manifest_path,
                "observation_manifest_sha256": self.manifest_sha,
                "attempt_directory": self.root / "generated-sealed-attempt",
                "attempt_manifest_sha256": self.attempt_sha,
                "final_receipt_sha256": self.final["receipt_pin"]["sha256"],
                "output_directory": self.root / output,
                "participant_material_roots": [self.root / "native-material", self.root / "programme-material"]}
        args.update(changes)
        return bridge.grade_attempt(**args)

    def test_both_arms_dispatch_identical_bytes_to_unchanged_grader(self):
        for arm in ("native", "programme"):
            with self.subTest(arm=arm):
                self.final["manifest"]["arm"] = arm
                result = self.run_bridge(output=arm)
                folder = self.root / arm
                self.assertEqual(result["arm"], arm)
                self.assertFalse(result["participant_feedback_delivered"])
                self.assertFalse(result["full_task_completed"])
                self.assertEqual({p.name for p in folder.iterdir()},
                                 {"SUBMISSION.json", "GRADE.json", "RECEIPT.json"})
                self.assertEqual((folder / "SUBMISSION.json").read_bytes(), self.final["answer_bytes"])
                receipt = bridge.strict_json((folder / "RECEIPT.json").read_bytes())
                self.assertEqual(receipt["final_receipt"], self.final["receipt_pin"])
                self.assertFalse(receipt["native_tolerance_relaxed"])
        self.assertEqual(len(self.grader_calls), 2)
        self.assertEqual(self.grader_calls[0][2], self.grader_calls[1][2])

    def test_operator_manifest_must_match_frozen_identity_before_dispatch(self):
        with self.assertRaisesRegex(bridge.AttemptGradeError, "frozen identity"):
            self.run_bridge(observation_manifest_sha256="c" * 64)
        self.grader_mock.assert_not_called()
        self.assertFalse((self.root / "grade").exists())

    def test_preparation_cannot_be_substituted(self):
        with self.assertRaisesRegex(bridge.AttemptGradeError, "another preparation"):
            self.run_bridge(completion_sha256="c" * 64)
        self.grader_mock.assert_not_called()

    def test_capture_time_final_commitment_must_match_before_dispatch(self):
        with self.assertRaisesRegex(bridge.AttemptGradeError, "independently frozen final identity"):
            self.run_bridge(final_receipt_sha256="d" * 64)
        self.grader_mock.assert_not_called()
        self.assertFalse((self.root / "grade").exists())

    def test_attempt_condition_must_match_all_operator_bindings(self):
        for field in ("observation_manifest_sha256", "observation_sha256",
                      "preparation_completion_sha256"):
            with self.subTest(field=field):
                saved = self.final["manifest"][field]
                self.final["manifest"][field] = "c" * 64
                with self.assertRaisesRegex(bridge.AttemptGradeError, "attempt condition differs"):
                    self.run_bridge()
                self.final["manifest"][field] = saved
        self.grader_mock.assert_not_called()
        self.assertFalse((self.root / "grade").exists())

    def test_malformed_answer_reaches_grader_without_rewriting_and_failure_is_retained(self):
        self.final["answer_bytes"] = b"not valid JSON\n"
        calls = []
        def refuse(_, __, submission, ___):
            calls.append(submission.read_bytes())
            raise ValueError("generated malformed answer refusal")
        self.grader_mock.return_value.grade_submission = refuse
        with self.assertRaisesRegex(ValueError, "malformed answer refusal"):
            self.run_bridge()
        self.assertEqual(calls, [b"not valid JSON\n"])
        self.assertEqual({p.name for p in (self.root / "grade").iterdir()},
                         {"SUBMISSION.json", "FAILURE.json"})
        with self.assertRaisesRegex(bridge.AttemptGradeError, "fresh output"):
            self.run_bridge()
        self.assertEqual(len(calls), 1)

    def test_grade_must_commit_to_captured_answer(self):
        def wrong(_, __, ___, output):
            result = {"submission": bridge.pin(b"different answer")}
            output.write_bytes(bridge.encoded(result))
            return result
        self.grader_mock.return_value.grade_submission = wrong
        with self.assertRaisesRegex(bridge.AttemptGradeError, "captured answer bytes"):
            self.run_bridge()
        self.assertTrue((self.root / "grade/FAILURE.json").is_file())

    def test_saved_grade_and_return_must_match_with_types(self):
        def mismatch(_, __, submission, output):
            result = {"submission": bridge.pin(submission.read_bytes()), "flag": 1}
            output.write_bytes(bridge.encoded({**result, "flag": True}))
            return result
        self.grader_mock.return_value.grade_submission = mismatch
        with self.assertRaisesRegex(bridge.AttemptGradeError, "saved grade differs"):
            self.run_bridge()

    def test_submission_copy_mutation_is_detected(self):
        def mutate(prepared, completion, submission, output):
            result = self.fake_grade(prepared, completion, submission, output)
            submission.write_bytes(b"changed by generated grader")
            return result
        self.grader_mock.return_value.grade_submission = mutate
        with self.assertRaisesRegex(bridge.AttemptGradeError, "submission copy changed"):
            self.run_bridge()

    def test_sealed_attempt_mutation_during_grading_is_detected(self):
        def mutate(prepared, completion, submission, output):
            result = self.fake_grade(prepared, completion, submission, output)
            self.final["receipt_pin"] = bridge.pin(b"changed final receipt")
            return result
        self.grader_mock.return_value.grade_submission = mutate
        with self.assertRaisesRegex(bridge.AttemptGradeError, "sealed attempt changed"):
            self.run_bridge()

    def test_nonfinite_and_duplicate_manifest_json_are_refused(self):
        for body in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":1e400}'):
            with self.subTest(body=body):
                self.manifest_path.write_bytes(body)
                with self.assertRaises(bridge.AttemptGradeError):
                    self.run_bridge(observation_manifest_sha256=bridge.pin(body)["sha256"])
        self.grader_mock.assert_not_called()

    def test_extra_grader_output_cannot_receive_success_receipt(self):
        def extra(prepared, completion, submission, output):
            result = self.fake_grade(prepared, completion, submission, output)
            (output.parent / "unexpected.json").write_bytes(b"{}")
            return result
        self.grader_mock.return_value.grade_submission = extra
        with self.assertRaisesRegex(bridge.AttemptGradeError, "before success receipt"):
            self.run_bridge()
        self.assertFalse((self.root / "grade/RECEIPT.json").exists())
        self.assertTrue((self.root / "grade/FAILURE.json").is_file())

    def test_private_output_cannot_overlap_declared_participant_or_input_roots(self):
        for folder in ("native-material", "programme-material", "generated-sealed-attempt",
                       "generated-private-preparation", "operator-bundle"):
            with self.subTest(folder=folder):
                before = {p.name for p in (self.root / folder).iterdir()}
                with self.assertRaisesRegex(bridge.AttemptGradeError, "overlaps protected input"):
                    self.run_bridge(output=folder + "/grade")
                self.assertEqual({p.name for p in (self.root / folder).iterdir()}, before)
                self.assertFalse((self.root / folder / "grade").exists())
        self.grader_mock.assert_not_called()

    def test_private_output_cannot_be_written_inside_git(self):
        (self.root / ".git").mkdir()
        with self.assertRaisesRegex(bridge.AttemptGradeError, "outside Git repositories"):
            self.run_bridge()
        self.grader_mock.assert_not_called()
        self.assertFalse((self.root / "grade").exists())

    def test_nonregular_grader_output_is_refused_without_blocking(self):
        for kind in ("symlink", "fifo"):
            with self.subTest(kind=kind):
                def nonregular(_, __, submission, output):
                    result = {"submission": bridge.pin(submission.read_bytes())}
                    if kind == "symlink":
                        output.symlink_to(submission)
                    else:
                        os.mkfifo(output, 0o600)
                    return result
                self.grader_mock.return_value.grade_submission = nonregular
                with self.assertRaisesRegex(bridge.AttemptGradeError, "ordinary path"):
                    self.run_bridge(output="nonregular-" + kind)
                self.assertFalse((self.root / ("nonregular-" + kind) / "RECEIPT.json").exists())

    def test_symlink_manifest_refused_without_grader_import(self):
        alias = self.root / "alias.json"
        alias.symlink_to(self.manifest_path)
        with self.assertRaisesRegex(bridge.AttemptGradeError, "ordinary path"):
            self.run_bridge(observation_manifest=alias)
        self.grader_mock.assert_not_called()

    def test_oversized_capture_refused_before_private_output(self):
        self.final["answer_bytes"] = b"x" * (bridge.MAX_ANSWER_BYTES + 1)
        with self.assertRaisesRegex(bridge.AttemptGradeError, "bounded captured answer"):
            self.run_bridge()
        self.assertFalse((self.root / "grade").exists())
        self.grader_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
