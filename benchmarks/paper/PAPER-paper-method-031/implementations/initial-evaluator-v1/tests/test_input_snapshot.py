"""Generated CLI metadata custody controls, with array evaluation replaced explicitly.

The NumPy dependency is an inert injected module because these controls exercise
only the JSON read/hash/call boundary, not movie arithmetic or scientific data.
"""
from contextlib import redirect_stderr
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("fast_metadata_controls", Path(__file__).resolve().parents[1] / "evaluate.py")
module = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {"numpy": types.ModuleType("numpy")}):
    spec.loader.exec_module(module)


class InputSnapshotTests(unittest.TestCase):
    def inputs(self, root):
        panel = root / "panel.json"
        submissions = root / "submissions.json"
        output = root / "report.json"
        panel.write_bytes(b'{"marker":"old"}')
        submissions.write_bytes(b'{"marker":"old"}')
        args = ["--panel", str(panel), "--panel-sha256", hashlib.sha256(panel.read_bytes()).hexdigest(),
                "--submissions", str(submissions), "--output", str(output)]
        return panel, submissions, output, args

    def test_panel_hash_and_parse_use_one_snapshot(self):
        with tempfile.TemporaryDirectory(prefix="fast-generated-metadata-") as folder:
            panel, submissions, output, args = self.inputs(Path(folder))
            original_open = Path.open
            changed = []
            class ReplacingReader:
                def __init__(self, handle): self.handle = handle
                def __enter__(self): return self
                def __exit__(self, *args): return self.handle.__exit__(*args)
                def read(self, *args):
                    value = self.handle.read(*args)
                    if value and not changed:
                        changed.append(True)
                        panel.write_bytes(b'{"marker":"new"}')
                    return value
            def opening(path, *args, **kwargs):
                handle = original_open(path, *args, **kwargs)
                mode = args[0] if args else kwargs.get("mode", "r")
                return ReplacingReader(handle) if path == panel and mode == "rb" else handle
            def observe(parsed_panel, parsed_submissions, *unused):
                return {"seen_panel": parsed_panel, "seen_submissions": parsed_submissions}
            with patch.object(Path, "open", opening), patch.object(module, "evaluate", observe):
                self.assertEqual(module.main(args), 0)
            self.assertEqual(changed, [True])
            self.assertEqual(json.loads(output.read_text())["seen_panel"], {"marker": "old"})

    def test_submission_pin_describes_bytes_passed_to_evaluator(self):
        with tempfile.TemporaryDirectory(prefix="fast-generated-metadata-") as folder:
            panel, submissions, output, args = self.inputs(Path(folder))
            expected = hashlib.sha256(submissions.read_bytes()).hexdigest()
            def observe(parsed_panel, parsed_submissions, *unused):
                submissions.write_bytes(b'{"marker":"new"}')
                return {"seen_submissions": parsed_submissions}
            with patch.object(module, "evaluate", observe):
                self.assertEqual(module.main(args), 0)
            report = json.loads(output.read_text())
            self.assertEqual(report["seen_submissions"], {"marker": "old"})
            self.assertEqual(report["input_pins"]["submissions_sha256"], expected)

    def test_mismatched_panel_hash_still_refuses_before_evaluation(self):
        with tempfile.TemporaryDirectory(prefix="fast-generated-metadata-") as folder:
            panel, submissions, output, args = self.inputs(Path(folder))
            args[3] = "0" * 64
            with patch.object(module, "evaluate") as evaluate, redirect_stderr(io.StringIO()):
                self.assertEqual(module.main(args), 2)
                evaluate.assert_not_called()
            self.assertFalse(output.exists())

    def test_unchanged_utf8_metadata_keeps_both_pins(self):
        with tempfile.TemporaryDirectory(prefix="fast-generated-metadata-") as folder:
            panel, submissions, output, args = self.inputs(Path(folder))
            submissions.write_text('{"signal":"α"}', encoding="utf-8")
            expected = hashlib.sha256(submissions.read_bytes()).hexdigest()
            with patch.object(module, "evaluate", lambda p, s, *unused: {"seen_submissions": s}):
                self.assertEqual(module.main(args), 0)
            report = json.loads(output.read_text())
            self.assertEqual(report["seen_submissions"], {"signal": "α"})
            self.assertEqual(report["input_pins"], {"panel_sha256": args[3], "submissions_sha256": expected})


if __name__ == "__main__":
    unittest.main()
