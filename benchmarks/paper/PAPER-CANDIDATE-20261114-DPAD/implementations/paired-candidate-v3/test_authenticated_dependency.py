"""Generated source/cache controls; no scientific data or predictions."""
import hashlib
import importlib.util
import marshal
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent


def fixture(root):
    for relative in ("initial-evaluator-v1/evaluator.py", "paired-candidate-v2/paired.py",
                     "paired-candidate-v3/paired.py"):
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((HERE.parent / relative).read_bytes())
    return root / "paired-candidate-v3/paired.py", root / "initial-evaluator-v1/evaluator.py"


def load(path):
    spec = importlib.util.spec_from_file_location("_dpad_generated_dependency", path)
    module = importlib.util.module_from_spec(spec)
    exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
    return module


class AuthenticatedDependencyTests(unittest.TestCase):
    def test_valid_predecessor_still_supplies_same_interface(self):
        with tempfile.TemporaryDirectory() as temp:
            path, legacy = fixture(Path(temp))
            module = load(path)
            self.assertEqual(hashlib.sha256(legacy.read_bytes()).hexdigest(), module.LEGACY_SHA256)
            self.assertEqual(module.e.channel_cc, module.channel_cc)
            self.assertAlmostEqual(module.channel_cc([[0], [1], [2]], [[2], [3], [4]])["mean_cc"], 1.)

    def test_timestamp_valid_untrusted_bytecode_is_ignored(self):
        with tempfile.TemporaryDirectory() as temp:
            path, legacy = fixture(Path(temp))
            identity = legacy.stat()
            cache = Path(importlib.util.cache_from_source(str(legacy)))
            cache.parent.mkdir()
            code = compile("raise RuntimeError('unchecked cached code executed')", str(legacy), "exec")
            cache.write_bytes(importlib.util.MAGIC_NUMBER + struct.pack("<III", 0,
                int(identity.st_mtime) & 0xffffffff, identity.st_size) + marshal.dumps(code))
            module = load(path)
            self.assertEqual(hashlib.sha256(legacy.read_bytes()).hexdigest(), module.LEGACY_SHA256)
            self.assertTrue(callable(module.e.read_json))

    def test_path_replacement_after_authentication_does_not_change_executed_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            path, legacy = fixture(Path(temp))
            original_read = Path.read_bytes
            replaced = []

            def read_then_replace(candidate):
                body = original_read(candidate)
                if candidate.resolve() == legacy.resolve() and not replaced:
                    replaced.append(True)
                    legacy.write_text("raise RuntimeError('replacement code executed')\n")
                return body

            with mock.patch.object(Path, "read_bytes", read_then_replace):
                module = load(path)
            self.assertEqual(replaced, [True])
            self.assertTrue(callable(module.e.read_json))

    def test_changed_source_is_still_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path, legacy = fixture(Path(temp))
            legacy.write_text("raise RuntimeError('must never execute')\n")
            with self.assertRaisesRegex(RuntimeError, "predecessor evaluator changed"):
                load(path)


if __name__ == "__main__":
    unittest.main()
