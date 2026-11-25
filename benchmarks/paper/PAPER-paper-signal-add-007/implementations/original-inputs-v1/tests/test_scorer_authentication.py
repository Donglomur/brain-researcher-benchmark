"""Generated scorer identity controls; no evaluation arrays or model calls."""
import hashlib
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parents[1]
for name in ("source", "predictions"):
    spec = importlib.util.spec_from_file_location(name, HERE / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
spec = importlib.util.spec_from_file_location("icnet_grade_identity_controls", HERE / "grade.py")
grade = importlib.util.module_from_spec(spec)
spec.loader.exec_module(grade)

GOOD = b'def score_panel(manifest, root):\n    return {"marker": "original"}\n'
OTHER = b'def score_panel(manifest, root):\n    return {"marker": "replaced"}\n'


class ScorerAuthenticationTests(unittest.TestCase):
    def setup_source(self, root):
        adapter = root / "original-inputs-v1" / "grade.py"
        scorer = root / "source-equations-v1" / "scorer.py"
        scorer.parent.mkdir()
        scorer.write_bytes(GOOD)
        return adapter, scorer

    def test_consumes_exact_authenticated_code_after_path_replacement(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); adapter, scorer = self.setup_source(root)
            original_spec = importlib.util.spec_from_file_location
            def replace_after_authentication(name, path, *args, **kwargs):
                scorer.write_bytes(OTHER)
                return original_spec(name, path, *args, **kwargs)
            with mock.patch.object(grade, "__file__", str(adapter)), \
                 mock.patch.object(grade, "SCORER_SHA256", hashlib.sha256(GOOD).hexdigest()), \
                 mock.patch.object(grade.importlib.util, "spec_from_file_location", side_effect=replace_after_authentication):
                result = grade.grade({}, root)
            self.assertEqual(result["marker"], "original")
            self.assertEqual(result["retained_scorer_sha256"], hashlib.sha256(GOOD).hexdigest())

    def test_unchanged_scorer_preserves_result_and_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); adapter, scorer = self.setup_source(root)
            with mock.patch.object(grade, "__file__", str(adapter)), \
                 mock.patch.object(grade, "SCORER_SHA256", hashlib.sha256(GOOD).hexdigest()):
                result = grade.grade({}, root)
            self.assertEqual(result, {"marker": "original", "input_adapter_schema": "icnet-original-inputs/v1",
                                      "retained_scorer_sha256": hashlib.sha256(GOOD).hexdigest()})

    def test_wrong_source_hash_is_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); adapter, scorer = self.setup_source(root)
            scorer.write_bytes(b'raise AssertionError("must not execute")\n')
            with mock.patch.object(grade, "__file__", str(adapter)), \
                 mock.patch.object(grade, "SCORER_SHA256", hashlib.sha256(GOOD).hexdigest()):
                with self.assertRaisesRegex(grade.InputError, "scorer changed"):
                    grade.grade({}, root)


if __name__ == "__main__":
    unittest.main()
