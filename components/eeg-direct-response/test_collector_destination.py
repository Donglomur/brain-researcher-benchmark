"""Focused stdlib-only destination tests; NumPy serialization is not executed."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parent / "portable"


class CollectorDestinationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.ids = [f"invented-{i:03d}" for i in range(400)]
        self.manifest = self.root / "manifest.json"
        self.manifest.write_text(json.dumps({"development_ids": self.ids}))
        self.responses = self.root / "responses.jsonl"
        self.responses.write_text("".join(json.dumps({"trial_id": i, "target_probability": 0.25}) + "\n" for i in reversed(self.ids)))
        spec = importlib.util.spec_from_file_location("_eeg_collector_destination", ROOT / "assemble_predictions.py")
        self.module = importlib.util.module_from_spec(spec)
        self.old_path = list(sys.path)
        spec.loader.exec_module(self.module)
        self.calls = []
        self.numpy = types.ModuleType("numpy")
        self.numpy.float64 = object()
        self.numpy.asarray = lambda value, dtype: (list(value), dtype)
        def save(file, **arrays):
            self.calls.append((file, arrays))
            file.write(b"MOCK_NPZ_NOT_NUMPY")
        self.numpy.savez = save

    def tearDown(self):
        sys.path[:] = self.old_path
        self.temp.cleanup()

    def invoke(self, destination):
        argv = ["assemble_predictions.py", "--manifest", str(self.manifest), "--responses", str(self.responses), "--out", str(destination)]
        output = io.StringIO()
        with mock.patch.object(sys, "argv", argv), mock.patch.dict(sys.modules, {"numpy": self.numpy}), contextlib.redirect_stdout(output):
            self.module.main()
        return output.getvalue()

    def test_exact_filehandle_and_complete_order(self):
        target = self.root / "submission.npz"
        result = json.loads(self.invoke(target))
        self.assertEqual(result["rows"], 400)
        self.assertFalse(result["scoring_performed"])
        self.assertEqual(target.read_bytes(), b"MOCK_NPZ_NOT_NUMPY")
        handle, arrays = self.calls[0]
        self.assertTrue(handle.closed)
        self.assertEqual(handle.name, str(target))
        self.assertEqual(arrays["trial_ids"], (self.ids, "<U48"))
        self.assertEqual(arrays["target_probability"][0], [0.25] * 400)

    def test_existing_destination_preserved(self):
        target = self.root / "submission.npz"
        target.write_bytes(b"EXISTING")
        with self.assertRaises(FileExistsError):
            self.invoke(target)
        self.assertEqual(target.read_bytes(), b"EXISTING")
        self.assertEqual(self.calls, [])

    def test_implicit_suffix_collision_refused(self):
        sibling = self.root / "submission.npz"
        sibling.write_bytes(b"EXISTING")
        with self.assertRaisesRegex(ValueError, "explicit .npz"):
            self.invoke(self.root / "submission")
        self.assertEqual(sibling.read_bytes(), b"EXISTING")
        self.assertFalse((self.root / "submission").exists())
        self.assertEqual(self.calls, [])

    def test_dangling_symlink_not_followed(self):
        target = self.root / "submission.npz"
        victim = self.root / "outside.npz"
        target.symlink_to(victim)
        with self.assertRaises(FileExistsError):
            self.invoke(target)
        self.assertTrue(target.is_symlink())
        self.assertFalse(victim.exists())
        self.assertEqual(self.calls, [])

    def test_failure_preserves_partial_and_closes_handle(self):
        target = self.root / "submission.npz"
        seen = []
        def fail(file, **arrays):
            seen.append(file)
            file.write(b"PARTIAL")
            raise OSError("invented write failure")
        self.numpy.savez = fail
        with self.assertRaisesRegex(OSError, "invented write failure"):
            self.invoke(target)
        self.assertEqual(target.read_bytes(), b"PARTIAL")
        self.assertTrue(seen[0].closed)

    def test_incomplete_panel_prevents_output_creation(self):
        self.responses.write_text("\n".join(self.responses.read_text().splitlines()[:-1]) + "\n")
        target = self.root / "submission.npz"
        with self.assertRaisesRegex(ValueError, "All responses required"):
            self.invoke(target)
        self.assertFalse(target.exists())
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
