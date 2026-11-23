"""Generated public-query checks; no reference, key, observations or targets."""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


PATH = Path(__file__).resolve().parents[1] / "preflight.py"
spec = importlib.util.spec_from_file_location("neural015_public_preflight", PATH)
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


def fixture():
    # Public shape fixture only: these are arbitrary aliases, not HMAC evidence.
    rows = []
    for index in range(26):
        count = 3 + index % 4
        rows.append({"case_id": hashlib.sha256(("generated-case-%d" % index).encode()).hexdigest(),
                     "fold_id": hashlib.sha256(("generated-fold-%d" % (index % 5)).encode()).hexdigest(),
                     "grid_start_sample": 8, "grid_stop_sample_exclusive": 8 + count * 3 - 1,
                     "grid_step_samples": 3, "n_grid_points": count})
    query = {"task_id": p.TASK, "delivery_profile": p.PROFILE,
             "protocol_sha256": "a" * 64, "recordings": rows}
    submission = {"task_id": p.TASK, "delivery_profile": p.PROFILE,
                  "query_sha256": p.digest(query), "predictions": [
                      {"case_id": row["case_id"], "fold_id": row["fold_id"],
                       "neural": [(index + j) / 40 for j in range(row["n_grid_points"])]}
                      for index, row in enumerate(rows)]}
    return query, submission


class PublicPreflightTests(unittest.TestCase):
    def test_complete_distinct_response_can_be_in_any_row_order_without_mutation(self):
        query, submission = fixture()
        submission["predictions"].reverse()
        before = copy.deepcopy((query, submission))
        report = p.validate_submission(query, submission)
        self.assertEqual((query, submission), before)
        self.assertEqual(report["recordings_checked"], 26)
        self.assertEqual(report["grid_probabilities_checked"], 115)
        self.assertEqual(report["submission_sha256"], p.digest(submission))
        self.assertEqual(report["validation"], "public-schema-only")
        for flag in ("operator_provenance_authenticated", "protected_score_computed", "scientific_admission"):
            self.assertIs(report[flag], False)

    def test_wrong_query_binding_rejected_even_when_geometry_still_fits(self):
        query, submission = fixture()
        query["protocol_sha256"] = "b" * 64
        with self.assertRaisesRegex(p.ContractError, "binding"):
            p.validate_submission(query, submission)

    def test_missing_extra_duplicate_unknown_cases_rejected(self):
        for kind in ("missing", "extra", "duplicate", "unknown"):
            query, submission = fixture()
            rows = submission["predictions"]
            if kind == "missing": rows.pop()
            elif kind == "extra": rows.append(copy.deepcopy(rows[0]))
            elif kind == "duplicate": rows[1] = copy.deepcopy(rows[0])
            else: rows[0]["case_id"] = "0" * 64
            with self.subTest(kind=kind), self.assertRaises(p.ContractError):
                p.validate_submission(query, submission)

    def test_wrong_fold_and_incomplete_vectors_reject(self):
        for kind in ("fold", "short", "long", "nonlist"):
            query, submission = fixture()
            row = submission["predictions"][0]
            if kind == "fold": row["fold_id"] = submission["predictions"][1]["fold_id"]
            elif kind == "short": row["neural"].pop()
            elif kind == "long": row["neural"].append(0.5)
            else: row["neural"] = "0.5"
            with self.subTest(kind=kind), self.assertRaises(p.ContractError):
                p.validate_submission(query, submission)

    def test_probability_bounds_finiteness_and_type(self):
        for value in (True, False, None, "0.5", -0.1, 1.1, float("nan"), float("inf"), 10 ** 1000):
            query, submission = fixture()
            submission["predictions"][0]["neural"][0] = value
            with self.subTest(kind=type(value).__name__), self.assertRaises(p.ContractError):
                p.validate_submission(query, submission)
        query, submission = fixture()
        for row in submission["predictions"]:
            row["neural"] = [1] * len(row["neural"])
        self.assertEqual(p.validate_submission(query, submission)["recordings_checked"], 26)

    def test_query_coverage_aliases_and_geometry_are_checked(self):
        for field, value in (("grid_start_sample", -1), ("grid_start_sample", True),
                             ("grid_stop_sample_exclusive", 8), ("grid_step_samples", 0),
                             ("grid_step_samples", 3.0), ("n_grid_points", 99),
                             ("case_id", "source-recording-id"), ("fold_id", "A" * 64)):
            query, submission = fixture()
            query["recordings"][0][field] = value
            submission["query_sha256"] = p.digest(query)
            with self.subTest(field=field, value=value), self.assertRaises(p.ContractError):
                p.validate_submission(query, submission)
        for kind in ("missing", "duplicate"):
            query, submission = fixture()
            if kind == "missing": query["recordings"].pop()
            else: query["recordings"][1] = copy.deepcopy(query["recordings"][0])
            submission["query_sha256"] = p.digest(query)
            with self.subTest(kind=kind), self.assertRaises(p.ContractError):
                p.validate_submission(query, submission)

    def test_exact_fields_reject_extra_private_or_control_content(self):
        for position in ("query", "grid", "submission", "prediction"):
            query, submission = fixture()
            target = {"query": query, "grid": query["recordings"][0],
                      "submission": submission, "prediction": submission["predictions"][0]}[position]
            target["word_onset_samples"] = []
            with self.subTest(position=position), self.assertRaises(p.ContractError):
                p.validate_submission(query, submission)

    def test_duplicate_json_keys_and_nonfinite_literals_reject(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "generated.json"
            for body in ('{"a": 1, "a": 2}', '{"x": NaN}', '{"x": Infinity}'):
                path.write_text(body)
                with self.subTest(body=body), self.assertRaises(p.ContractError):
                    p.load_json(path)

    def test_cli_public_inputs_only_private_report_and_no_overwrite(self):
        query, submission = fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            query_path, submission_path, output = root / "query.json", root / "response.json", root / "report.json"
            query_path.write_text(json.dumps(query))
            submission_path.write_text(json.dumps(submission))
            before = (query_path.read_bytes(), submission_path.read_bytes())
            args = [str(query_path), str(submission_path), "--output", str(output)]
            old_mask = os.umask(0)
            try:
                self.assertEqual(p.main(args), 0)
            finally:
                os.umask(old_mask)
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads(output.read_text()), p.validate_submission(query, submission))
            with patch.object(p, "load_json", side_effect=AssertionError("inputs opened after overwrite refusal")):
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(p.main(args), 2)
            self.assertEqual((query_path.read_bytes(), submission_path.read_bytes()), before)

    def test_invalid_cli_response_leaves_no_report(self):
        query, submission = fixture()
        submission["predictions"].pop()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            q, s, out = root / "q.json", root / "s.json", root / "must-not-exist.json"
            q.write_text(json.dumps(query))
            s.write_text(json.dumps(submission))
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(p.main([str(q), str(s), "--output", str(out)]), 2)
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
