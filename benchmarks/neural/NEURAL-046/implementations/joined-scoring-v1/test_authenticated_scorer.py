"""Generated source-loading controls; no neural inputs, fitting or scoring."""
import ast
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "_neural046_authenticated_grader_controls", HERE / "grade_artifacts.py")
grader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(grader)


class AuthenticatedScorerTests(unittest.TestCase):
    def test_valid_authenticated_bytes_retain_module_file(self):
        body = b"ORIGIN = 'authenticated scorer bytes'\n"
        with tempfile.TemporaryDirectory(prefix="n046-source-valid-") as directory:
            root = Path(directory).resolve()
            path = root / "score.py"
            path.write_bytes(body)
            with patch.object(grader, "__file__", str(root / "grade_artifacts.py")), \
                    patch.object(grader, "SCORER_SHA256", hashlib.sha256(body).hexdigest()):
                scorer = grader.load_scorer()
            self.assertEqual(scorer.ORIGIN, "authenticated scorer bytes")
            self.assertEqual(Path(scorer.__file__), path)

    def test_replacement_after_authentication_cannot_change_executed_bytes(self):
        body = b"ORIGIN = 'authenticated scorer bytes'\n"
        replacement = b"ORIGIN = 'replacement scorer pathname'\n"
        with tempfile.TemporaryDirectory(prefix="n046-source-replaced-") as directory:
            root = Path(directory).resolve()
            path = root / "score.py"
            path.write_bytes(body)
            read_file = grader.read_file
            reads = []

            def read_then_replace(source, cap):
                raw = read_file(source, cap)
                reads.append(str(source))
                path.write_bytes(replacement)
                return raw

            with patch.object(grader, "__file__", str(root / "grade_artifacts.py")), \
                    patch.object(grader, "SCORER_SHA256", hashlib.sha256(body).hexdigest()), \
                    patch.object(grader, "read_file", read_then_replace):
                scorer = grader.load_scorer()
            self.assertEqual(reads, [str(path)])
            self.assertEqual(path.read_bytes(), replacement)
            self.assertEqual(scorer.ORIGIN, "authenticated scorer bytes")

    def test_unmatched_source_hash_is_refused_before_execution(self):
        with tempfile.TemporaryDirectory(prefix="n046-source-mismatch-") as directory:
            root = Path(directory).resolve()
            path = root / "score.py"
            path.write_bytes(b"raise AssertionError('unmatched source executed')\n")
            with patch.object(grader, "__file__", str(root / "grade_artifacts.py")), \
                    patch.object(grader, "SCORER_SHA256", "0" * 64), \
                    self.assertRaisesRegex(grader.ArtifactError, "paired_scorer_source_changed"):
                grader.load_scorer()

    def test_participant_preflight_pins_current_artifact_adapter(self):
        tree = ast.parse((HERE / "preflight_submission.py").read_text())
        pins = [node.value.value for node in tree.body
                if isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == "ADAPTER_SHA256"
                        for target in node.targets)]
        self.assertEqual(pins, [hashlib.sha256((HERE / "grade_artifacts.py").read_bytes()).hexdigest()])


if __name__ == "__main__":
    unittest.main(verbosity=2)
