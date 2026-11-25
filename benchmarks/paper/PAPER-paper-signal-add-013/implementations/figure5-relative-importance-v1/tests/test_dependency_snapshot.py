"""Generated controls for the authenticated Figure5 baseline dependency."""
import hashlib
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get("BOLD_CONTRIBUTIONS_PATH", HERE / "contributions.py"))
BASELINE = Path(os.environ.get("BOLD_BASELINE_PATH", HERE.parent / "figure5-baseline-v1" / "baseline.py"))
spec = importlib.util.spec_from_file_location("bold_dependency_snapshot_test", SOURCE)
contributions = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contributions)


class BaselineDependencySnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline_body = BASELINE.read_bytes()
        if hashlib.sha256(cls.baseline_body).hexdigest() != contributions.BASELINE_SHA256:
            raise AssertionError("test requires the unchanged accepted baseline source")

    def test_path_replacement_cannot_change_authenticated_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "baseline.py"
            path.write_bytes(self.baseline_body)
            original_read = Path.read_bytes
            replacement = b'raise RuntimeError("unverified replacement executed")\n'
            def replace_after_read(target):
                body = original_read(target)
                if target == path:
                    target.write_bytes(replacement)
                return body
            with mock.patch.object(Path, "read_bytes", replace_after_read):
                loaded = contributions._baseline(path)
            self.assertEqual(loaded.STRATA, ("concordant", "discordant"))
            self.assertEqual(len(loaded.SUBJECTS), 40)
            self.assertEqual(path.read_bytes(), replacement)

    def test_changed_bytes_fail_before_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "baseline.py"
            path.write_bytes(b'raise RuntimeError("unverified source executed")\n')
            with self.assertRaisesRegex(ValueError, "identity changed"):
                contributions._baseline(path)

    def test_unchanged_dependency_keeps_public_constants_and_origin(self):
        loaded = contributions._baseline(BASELINE)
        self.assertEqual(loaded.PREDICTORS, ("oef", "cbf", "cbv"))
        self.assertEqual(loaded.STRATA, ("concordant", "discordant"))
        self.assertEqual(Path(loaded.__file__), BASELINE)
        self.assertEqual(loaded.SOURCE_SHA256, contributions.NOTEBOOK_SHA256)


if __name__ == "__main__":
    unittest.main()
