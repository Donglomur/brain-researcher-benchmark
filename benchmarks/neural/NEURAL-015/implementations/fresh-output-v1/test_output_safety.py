"""Generated input-preservation regressions; no authentic data or model run."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("neural015_fresh_output", HERE / "evaluator.py")
e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)


def alignment():
    return {"movie_times": [0, .25, 1], "triggers": [
        {"movie_time_seconds": 0, "neural_sample_index": 100},
        {"movie_time_seconds": 1, "neural_sample_index": 2148}],
        "max_clock_residual_samples": 0}


class FreshOutputTests(unittest.TestCase):
    def test_private_alignment_and_score_outputs_ignore_permissive_umask(self):
        fixture_path = e.BASE / "tests" / "test_evaluator.py"
        fixture_spec = importlib.util.spec_from_file_location("generated_permission_fixture", fixture_path)
        fixture = importlib.util.module_from_spec(fixture_spec)
        fixture_spec.loader.exec_module(fixture)
        reference, submission = fixture.fixture()
        base = e.load_evaluator()
        for mask in (0, 0o022):
            for command in ("align", "score"):
                with self.subTest(mask=mask, command=command), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    source, response, output = root / "input.json", root / "response.json", root / "output.json"
                    value = alignment() if command == "align" else reference
                    source.write_text(json.dumps(value))
                    response.write_text(json.dumps(submission))
                    expected = base.align_onsets(**value) if command == "align" else base.evaluate(value, submission)
                    previous = os.umask(mask)
                    try:
                        self.assertEqual(e.main([command, str(source), "--submission", str(response),
                                                 "--output", str(output)]), 0)
                    finally:
                        os.umask(previous)
                    self.assertEqual(output.stat().st_mode & 0o777, 0o600)
                    self.assertEqual(json.loads(output.read_text()), expected)

    def test_existing_input_aliases_and_reports_are_preserved_before_input_access(self):
        for kind in ("input", "submission", "report", "hardlink", "symlink", "dangling"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source, submission, output = root / "input.json", root / "submission.json", root / "output.json"
                body = json.dumps(alignment()).encode()
                source.write_bytes(body)
                submission.write_bytes(b"original candidate bytes")
                if kind == "input": output = source
                elif kind == "submission": output = submission
                elif kind == "report": output.write_bytes(b"prior operator report")
                elif kind == "hardlink": output.hardlink_to(source)
                elif kind == "symlink": output.symlink_to(source)
                else: output.symlink_to(root / "missing.json")
                original = None if kind == "dangling" else output.read_bytes()
                with patch.object(e, "load_evaluator", side_effect=AssertionError("input boundary crossed")) as loader:
                    with contextlib.redirect_stderr(io.StringIO()):
                        code = e.main(["align", str(source), "--submission", str(submission), "--output", str(output)])
                self.assertEqual(code, 2)
                loader.assert_not_called()
                self.assertEqual(source.read_bytes(), body)
                self.assertEqual(submission.read_bytes(), b"original candidate bytes")
                if kind == "dangling": self.assertTrue(output.is_symlink())
                else: self.assertEqual(output.read_bytes(), original)

    def test_race_created_output_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "input.json", root / "output.json"
            body = json.dumps(alignment()).encode()
            source.write_bytes(body)
            base = e.load_evaluator()
            original_loader = base.load_json
            def create_then_read(path):
                output.write_bytes(b"concurrent operator result")
                return original_loader(path)
            with patch.object(base, "load_json", side_effect=create_then_read):
                with patch.object(e, "load_evaluator", return_value=base):
                    with contextlib.redirect_stderr(io.StringIO()):
                        code = e.main(["align", str(source), "--output", str(output)])
            self.assertEqual(code, 2)
            self.assertEqual(output.read_bytes(), b"concurrent operator result")
            self.assertEqual(source.read_bytes(), body)

    def test_fresh_alignment_uses_original_endpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "input.json", root / "output.json"
            body = json.dumps(alignment()).encode()
            source.write_bytes(body)
            self.assertEqual(e.main(["align", str(source), "--output", str(output)]), 0)
            self.assertEqual(json.loads(output.read_bytes()), {
                "word_onset_samples": [100, 612, 2148],
                "adjacent_clock_residual_samples": [0],
                "native_alignment_validated": False,
                "coverage_rule": "inclusive trigger span; no extrapolation"})
            self.assertEqual(source.read_bytes(), body)

    def test_changed_predecessor_source_refused_without_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "input.json", root / "output.json"
            source.write_text(json.dumps(alignment()))
            (root / "evaluator.py").write_text("raise AssertionError('unchecked code executed')")
            with patch.object(e, "BASE", root):
                with contextlib.redirect_stderr(io.StringIO()):
                    code = e.main(["align", str(source), "--output", str(output)])
            self.assertEqual(code, 2)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
