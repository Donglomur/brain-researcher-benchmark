"""Focused stdlib-only destination tests; NumPy serialization is not executed."""
import contextlib
import hashlib
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
PACKAGE = ROOT.parent
REPOSITORY = PACKAGE.parents[4]
CURRENT_PINS = REPOSITORY / "benchmarks/integrity/current-closures/neural077-direct-response/SOURCE_PINS.json"


def verify_current_source():
    current = json.loads(CURRENT_PINS.read_text())
    if (current.get("schema") != "neural077_direct_response_current_source_v1"
            or current.get("package") != PACKAGE.relative_to(REPOSITORY).as_posix()):
        raise ValueError("Exact current source descriptor required")
    predecessor = (PACKAGE / "SOURCE_PINS.json").read_bytes()
    if (len(predecessor) != current["predecessor"]["bytes"]
            or hashlib.sha256(predecessor).hexdigest() != current["predecessor"]["sha256"]):
        raise ValueError("Historical source descriptor changed")
    original = json.loads(predecessor)
    if set(current["members"]) != set(original["members"]):
        raise ValueError("The complete original member roster is required")
    changed = {name for name, pin in current["members"].items()
               if pin != original["members"][name]}
    if changed != {"portable/response_contract.py", "test_collector_destination.py"}:
        raise ValueError("Only the response validator and its controls may change")
    for name, pin in current["members"].items():
        if Path(name).is_absolute() or ".." in Path(name).parts:
            raise ValueError("Source member must remain inside the package")
        body = (PACKAGE / name).read_bytes()
        if len(body) != pin["bytes"] or hashlib.sha256(body).hexdigest() != pin["sha256"]:
            raise ValueError("Current source member changed: " + name)


class CollectorDestinationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        verify_current_source()

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

    def test_response_identity_length_boundaries(self):
        parse = self.module.complete.__globals__["parse"]
        for identifier in ("x", "x" * 48):
            body = json.dumps({"trial_id": identifier, "target_probability": 0.25}).encode()
            self.assertEqual(parse(body, identifier), 0.25)
        for identifier in ("", "x" * 49):
            body = json.dumps({"trial_id": identifier, "target_probability": 0.25}).encode()
            with self.assertRaisesRegex(ValueError, "1 through 48"):
                parse(body, identifier)

    def test_invalid_identity_panel_prevents_output_creation(self):
        for label, replacements in (("empty", [""]),
                                    ("truncation_collision", ["x" * 48 + "a", "x" * 48 + "b"])):
            with self.subTest(label=label):
                ids = self.ids.copy()
                ids[:len(replacements)] = replacements
                self.manifest.write_text(json.dumps({"development_ids": ids}))
                self.responses.write_text("".join(json.dumps({"trial_id": identifier,
                    "target_probability": 0.25}) + "\n" for identifier in ids))
                target = self.root / (label + ".npz")
                with self.assertRaisesRegex(ValueError, "1 through 48"):
                    self.invoke(target)
                self.assertFalse(target.exists())
                self.assertEqual(self.calls, [])

    def test_maximum_length_panel_preserves_all_identities(self):
        ids = ["x" * 44 + f"{index:04d}" for index in range(400)]
        self.manifest.write_text(json.dumps({"development_ids": ids}))
        self.responses.write_text("".join(json.dumps({"trial_id": identifier,
            "target_probability": 0.25}) + "\n" for identifier in reversed(ids)))
        result = json.loads(self.invoke(self.root / "maximum.npz"))
        self.assertEqual(result["rows"], 400)
        self.assertEqual(self.calls[0][1]["trial_ids"], (ids, "<U48"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
