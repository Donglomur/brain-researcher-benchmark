"""Generated source-replacement controls; no data, targets or model execution."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock


PACKAGE = Path(__file__).resolve().parents[1]
EVALUATOR = PACKAGE.parent / "v1-transcript-evaluation-v1" / "evaluator.py"


class SourceSnapshotControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name).resolve()
        self.path = root / "v1-transcript-evaluation-v1" / "evaluator.py"
        self.path.parent.mkdir()
        self.path.write_bytes(EVALUATOR.read_bytes())
        module_path = root / "v1-author-export-bridge-v1" / "bridge.py"
        module_path.parent.mkdir()
        source = (PACKAGE / "bridge.py").read_bytes()
        spec = importlib.util.spec_from_file_location("generated_snapshot_bridge", module_path)
        self.bridge = importlib.util.module_from_spec(spec)
        exec(compile(source, str(module_path), "exec"), self.bridge.__dict__)

    def test_unchanged_frozen_source_loads(self):
        result = self.bridge._load_evaluator()
        self.assertEqual(result.TASK_ID, "PAPER-ROOT-ADD-002")
        self.assertTrue(callable(result.evaluate_bytes))

    def test_wrong_source_pin_is_refused(self):
        self.path.write_bytes(b"raise AssertionError('unverified source executed')\n")
        with self.assertRaisesRegex(RuntimeError, "identity mismatch"):
            self.bridge._load_evaluator()

    def test_replacement_after_authentication_is_not_executed(self):
        original_read = Path.read_bytes
        replaced = []

        def replace_after_read(path):
            source = original_read(path)
            if path == self.path and not replaced:
                replaced.append(True)
                path.write_bytes(b"UNVERIFIED_REPLACEMENT_EXECUTED = True\n")
            return source

        with mock.patch.object(Path, "read_bytes", replace_after_read):
            result = self.bridge._load_evaluator()
        self.assertEqual(replaced, [True])
        self.assertFalse(hasattr(result, "UNVERIFIED_REPLACEMENT_EXECUTED"))
        self.assertEqual(result.TASK_ID, "PAPER-ROOT-ADD-002")


if __name__ == "__main__":
    unittest.main()
