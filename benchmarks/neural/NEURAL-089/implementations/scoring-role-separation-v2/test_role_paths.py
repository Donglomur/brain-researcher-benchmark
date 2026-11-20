"""Generated controls for protected/public role separation; no recording data."""
import hashlib
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


HERE = Path(__file__).resolve().parent
IO = load_module("neural089_role_guard_io", HERE / "io_contract.py")
with mock.patch.dict(sys.modules, {"io_contract": IO}):
    SCORE = load_module("neural089_role_guard_scorer", HERE / "scorer.py")


class RolePathTests(unittest.TestCase):
    def assert_alias_refused(self, submission, panel, targets):
        with mock.patch.object(SCORE, "read", side_effect=AssertionError("input body opened")) as reader:
            result = SCORE.score_files(submission, panel, targets, "a" * 64)
        self.assertEqual(result["status"], "operator_error")
        self.assertIsNone(result["metrics"])
        self.assertFalse(result["private_targets_read"])
        self.assertIn("input role alias", result["reason"])
        reader.assert_not_called()

    def test_identical_targets_paths_rejected_before_reads(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            targets = root / "targets.json"
            targets.write_bytes(b"protected body")
            for role in ("submission", "panel"):
                with self.subTest(role=role):
                    submission = targets if role == "submission" else root / "submission.json"
                    panel = targets if role == "panel" else root / "panel.json"
                    self.assert_alias_refused(submission, panel, targets)

    def test_resolved_targets_alias_rejected_before_reads(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "nested").mkdir()
            targets = root / "targets.json"
            targets.write_bytes(b"protected body")
            alias = root / "nested" / ".." / "targets.json"
            self.assert_alias_refused(alias, root / "panel.json", targets)

    def test_link_aliases_rejected_before_reads(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            targets = root / "targets.json"
            targets.write_bytes(b"protected body")
            symlink = root / "symlink.json"
            symlink.symlink_to(targets)
            hardlink = root / "hardlink.json"
            os.link(targets, hardlink)
            for alias in (symlink, hardlink):
                with self.subTest(alias=alias.name):
                    self.assert_alias_refused(root / "submission.json", alias, targets)

    def fixture(self, root):
        query = "a" * 24
        panel = {"schema_version": 1, "task_id": "NEURAL-089", "query_ids": [query]}
        panel_raw = IO.encoded(panel)
        targets = {"schema_version": 1, "task_id": "NEURAL-089",
                   "panel_sha256": hashlib.sha256(panel_raw).hexdigest(),
                   "targets": [{"query_id": query, "label": 0}]}
        submission = {"schema_version": 1, "task_id": "NEURAL-089",
                      "predictions": [{"query_id": query, "probabilities": [1.] + [0.] * 38}]}
        paths = {name: root / (name + ".json") for name in ("submission", "panel", "targets")}
        paths["panel"].write_bytes(panel_raw)
        paths["targets"].write_bytes(IO.encoded(targets))
        paths["submission"].write_bytes(IO.encoded(submission))
        return paths, hashlib.sha256(IO.encoded(targets)).hexdigest()

    def test_invalid_distinct_submission_does_not_open_targets(self):
        with tempfile.TemporaryDirectory() as directory:
            paths, digest = self.fixture(Path(directory))
            paths["submission"].write_bytes(b"not JSON")
            opened = []
            actual_read = SCORE.read
            def read(path, *args, **kwargs):
                opened.append(Path(path))
                if Path(path) == paths["targets"]:
                    raise AssertionError("protected targets opened before admission")
                return actual_read(path, *args, **kwargs)
            with mock.patch.object(SCORE, "read", side_effect=read):
                result = SCORE.score_files(paths["submission"], paths["panel"], paths["targets"], digest)
            self.assertEqual(result["status"], "invalid_submission")
            self.assertFalse(result["private_targets_read"])
            self.assertEqual(opened, [paths["panel"], paths["submission"]])

    def test_distinct_scoring_preserves_original_metrics(self):
        with tempfile.TemporaryDirectory() as directory:
            paths, digest = self.fixture(Path(directory))
            opened = []
            actual_read = SCORE.read
            def read(path, *args, **kwargs):
                opened.append(Path(path))
                return actual_read(path, *args, **kwargs)
            with mock.patch.object(SCORE, "read", side_effect=read):
                result = SCORE.score_files(paths["submission"], paths["panel"], paths["targets"], digest)
            self.assertEqual(opened, [paths["panel"], paths["submission"], paths["targets"]])
            self.assertEqual(result["status"], "scored")
            self.assertTrue(result["private_targets_read"])
            self.assertEqual(result["metrics"]["accuracy"], 1.)
            self.assertAlmostEqual(result["metrics"]["macro_f1_39"], 1 / 39)
            self.assertEqual(result["metrics"]["query_count"], 1)
            self.assertEqual(result["metrics"]["confusion_matrix"][0][0], 1)
            self.assertEqual(sum(map(sum, result["metrics"]["confusion_matrix"])), 1)


if __name__ == "__main__":
    unittest.main()
