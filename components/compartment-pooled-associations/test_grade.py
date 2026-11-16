"""Invented-only controls for the portable REP012 boundary."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("portable_rep012_grade", HERE / "grade.py")
grade = importlib.util.module_from_spec(spec)
spec.loader.exec_module(grade)
INPUT_SHA = "a" * 64


def encode(value):
    return (json.dumps(value, allow_nan=False, sort_keys=True) + "\n").encode()


def invented():
    cohort = dict(member_count=2, raw_rows=8, unique_mice=1,
                  shared_mouse_ids=["INVENTED_MOUSE"], raw_row_ids_sha256="b" * 64)
    endpoints = []
    for name in ("apical_local", "basal_local", "apical_coincident", "basal_coincident"):
        endpoints.append(dict(endpoint_id=name, raw_rows=4, eligible_rows=3, paired_rows=2,
                              excluded_nan_rows=1, eligible_row_ids_sha256="c" * 64,
                              paired_row_ids_sha256="d" * 64,
                              r=.25, p=.5, paired_y_mean=2., paired_y_sd=.75))
    reference = dict(schema_version=1, task_id="PAPER-FIND-REP-012",
                     input_manifest_sha256=INPUT_SHA, cohort=cohort, endpoints=endpoints)
    candidate = dict(schema_version=1, task_id="PAPER-FIND-REP-012",
                     input_manifest_sha256=INPUT_SHA,
                     analysis_id="released_source_four_pooled_pearson_v1",
                     cohort=copy.deepcopy(cohort), endpoints=[])
    for row in endpoints:
        candidate["endpoints"].append(dict(endpoint_id=row["endpoint_id"], status="reported",
            reason=None, result={k: v for k, v in row.items() if k != "endpoint_id"}))
    return candidate, reference


class PortableBoundary(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="rep012-invented-")
        self.root = Path(self.temporary.name).resolve()
        self.candidate, self.reference = invented()
        self.submission = self.root / "submission.json"
        self.ref = self.root / "reference.json"
        self.submission.write_bytes(encode(self.candidate))
        self.ref.write_bytes(encode(self.reference))
        self.output = self.root / "grade.json"
        body = self.ref.read_bytes()
        self.ref_pin = (len(body), hashlib.sha256(body).hexdigest())

    def tearDown(self):
        self.temporary.cleanup()

    def argv(self, **changes):
        values = dict(submission=str(self.submission), reference=str(self.ref),
                      reference_bytes=str(self.ref_pin[0]), reference_sha256=self.ref_pin[1],
                      input_manifest_sha256=INPUT_SHA, output=str(self.output))
        values.update(changes)
        return [value for key, item in values.items() for value in ("--" + key.replace("_", "-"), str(item))]

    def invoke(self, **changes):
        code = grade.main(self.argv(**changes))
        return code, json.loads(self.output.read_bytes())

    def test_relocated_cli_has_no_workspace_dependency(self):
        folder = self.root / "relocated"
        folder.mkdir()
        for name in ("grade.py", "artifact_io.py", "scorer_core.py"):
            shutil.copyfile(HERE / name, folder / name)
        result = subprocess.run([sys.executable, "-I", "-S", "-B", str(folder / "grade.py"),
                                 *self.argv()], cwd=self.root, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(self.output.read_bytes())
        self.assertEqual(report["score"], 1.)
        self.assertTrue(report["full_reconstruction"])
        self.assertTrue(report["reference_pin_matched"])
        self.assertFalse(report["candidate_code_executed"])

    def test_invalid_candidate_does_not_read_missing_reference(self):
        self.submission.write_bytes(b'{"schema_version":1,"schema_version":1}')
        code, report = self.invoke(reference=self.root / "absent-private.json")
        self.assertEqual(code, 2)
        self.assertEqual(report["status"], "invalid_submission")
        self.assertFalse(report["private_reference_decoded"])
        self.assertIsNone(report["reference_pin"])

    def _assert_private_alias_never_read(self, submission):
        io = grade.load_io()
        original = io.read_bounded
        reads = []
        def observed(value, cap):
            reads.append(Path(value))
            if Path(value) in (self.ref, Path(submission)):
                raise AssertionError("Private alias was opened before rejection")
            return original(value, cap)
        io.read_bounded = observed
        with mock.patch.object(grade, "load_io", return_value=io):
            code = grade.main(self.argv(submission=submission))
        self.assertEqual(code, 1)
        self.assertNotIn(self.ref, reads)
        self.assertEqual(json.loads(self.output.read_bytes())["status"], "operator_error")

    def test_same_private_path_refuses_before_body_read(self):
        self._assert_private_alias_never_read(self.ref)

    def test_private_hardlink_alias_refuses_before_body_read(self):
        alias = self.root / "private-hardlink"
        os.link(self.ref, alias)
        self._assert_private_alias_never_read(alias)

    def test_reference_pin_mismatch_is_operator_error(self):
        code, report = self.invoke(reference_sha256="0" * 64)
        self.assertEqual(code, 1)
        self.assertEqual(report["status"], "operator_error")
        self.assertIsNone(report["score"])

    def test_reference_length_mismatch_is_operator_error(self):
        code, report = self.invoke(reference_bytes=self.ref_pin[0] + 1)
        self.assertEqual(code, 1)
        self.assertIsNone(report["score"])

    def test_wrong_private_semantics_never_penalize_candidate(self):
        self.reference["endpoints"][0]["paired_rows"] = 0
        body = encode(self.reference)
        self.ref.write_bytes(body)
        code, report = self.invoke(reference_bytes=len(body), reference_sha256=hashlib.sha256(body).hexdigest())
        self.assertEqual(code, 1)
        self.assertEqual(report["status"], "operator_error")
        self.assertTrue(report["reference_pin_matched"])

    def test_abstention_keeps_all_four_denominators(self):
        self.candidate["endpoints"][0].update(status="abstained", reason="INVENTED undefined", result=None)
        self.submission.write_bytes(encode(self.candidate))
        code, report = self.invoke()
        self.assertEqual(code, 0)
        self.assertEqual(report["score"], .5625)
        self.assertEqual(report["numeric_field_slots"], 16)
        self.assertEqual(report["endpoint_support_slots"], 24)
        self.assertEqual(report["cohort_slots"], 5)
        self.assertFalse(report["full_reconstruction"])

    def test_smaller_p_is_not_rewarded(self):
        self.candidate["endpoints"][0]["result"]["p"] = .001
        self.submission.write_bytes(encode(self.candidate))
        code, report = self.invoke()
        self.assertEqual(code, 0)
        self.assertLess(report["score"], 1.)
        self.assertFalse(report["full_reconstruction"])

    def test_boolean_counts_are_invalid_before_private_read(self):
        self.candidate["cohort"]["member_count"] = True
        self.submission.write_bytes(encode(self.candidate))
        code, report = self.invoke(reference=self.root / "absent-private.json")
        self.assertEqual(code, 2)
        self.assertFalse(report["private_reference_decoded"])

    def test_fifo_candidate_cannot_block(self):
        fifo = self.root / "candidate.fifo"
        os.mkfifo(fifo)
        code, report = self.invoke(submission=fifo)
        self.assertEqual(code, 1)
        self.assertIsNone(report["score"])

    def test_fifo_reference_cannot_block(self):
        fifo = self.root / "reference.fifo"
        os.mkfifo(fifo)
        code, report = self.invoke(reference=fifo)
        self.assertEqual(code, 1)
        self.assertIsNone(report["score"])

    def test_symlink_and_hardlink_submissions_refuse(self):
        link = self.root / "alias"
        link.symlink_to(self.submission)
        self.assertEqual(grade.main(self.argv(submission=link)), 1)
        other = self.root / "hardlink"
        os.link(self.submission, other)
        self.assertEqual(grade.main(self.argv(submission=other, output=self.root / "second.json")), 1)

    def test_existing_output_is_never_replaced(self):
        self.output.write_bytes(b"EXISTING_OPERATOR_RESULT")
        self.assertEqual(grade.main(self.argv()), 1)
        self.assertEqual(self.output.read_bytes(), b"EXISTING_OPERATOR_RESULT")

    def test_empty_and_oversized_are_invalid_before_private_read(self):
        for index, body in enumerate((b"", b" " * 32769)):
            self.submission.write_bytes(body)
            path = self.root / ("size-" + str(index) + ".json")
            self.assertEqual(grade.main(self.argv(reference=self.root / "absent-private.json", output=path)), 2)
            report = json.loads(path.read_bytes())
            self.assertFalse(report["private_reference_decoded"])
            self.assertIsNone(report["reference_pin"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
