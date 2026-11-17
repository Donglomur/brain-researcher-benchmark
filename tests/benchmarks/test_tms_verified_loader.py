"""Generated source-loader controls; no original inputs or reference statistics."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from contextlib import chdir
from pathlib import Path
import py_compile
import tempfile
import types
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "benchmarks/paper/PAPER-paper-signal-add-021/implementations/fixed-region-reference"
DESCRIPTOR = ROOT / "benchmarks/integrity/current-closures/trust-tms/SOURCE_BINDINGS.json"


def pin(body):
    return len(body), hashlib.sha256(body).hexdigest()


def producer():
    path = PACKAGE / "portable_regions.py"
    module = types.ModuleType("tms_loader_under_test")
    module.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), "exec", dont_inherit=True), module.__dict__)
    return module


class VerifiedLoaderChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = producer()

    def test_timestamp_valid_stale_bytecode_is_not_executed(self):
        accepted = b"VALUE = 1\n"
        cached = b"VALUE = 2\n"
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "dependency.py"
            path.write_bytes(cached)
            stamp = 1_700_000_000
            os.utime(path, (stamp, stamp))
            py_compile.compile(str(path), doraise=True,
                               invalidation_mode=py_compile.PycInvalidationMode.TIMESTAMP)
            path.write_bytes(accepted)
            os.utime(path, (stamp, stamp))
            # Establish that this fixture really is accepted by the old loader.
            old_spec = importlib.util.spec_from_file_location("old_cached_probe", path)
            old_module = importlib.util.module_from_spec(old_spec)
            old_spec.loader.exec_module(old_module)
            self.assertEqual(old_module.VALUE, 2)
            self.assertEqual(pin(path.read_bytes()), pin(accepted))
            loaded = self.source.pinned_module(path, pin(accepted), "verified_cached_probe")
            self.assertEqual(loaded.VALUE, 1)

    def test_verified_snapshot_is_not_reopened_for_execution(self):
        accepted = b"VALUE = 'verified'\n"
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "dependency.py"
            path.write_bytes(accepted)
            original_read = Path.read_bytes
            reads = []

            def replace_after_read(target):
                body = original_read(target)
                if target == path:
                    reads.append(str(target))
                    target.write_bytes(b"raise AssertionError('replacement executed')\n")
                return body

            with patch.object(Path, "read_bytes", replace_after_read):
                loaded = self.source.pinned_module(path, pin(accepted), "verified_snapshot")
            self.assertEqual(loaded.VALUE, "verified")
            self.assertEqual(reads, [str(path)])

    def test_source_mismatch_refuses_before_execution(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "dependency.py"
            path.write_bytes(b"raise AssertionError('unverified source executed')\n")
            with self.assertRaisesRegex(ValueError, "wrong immutable source"):
                self.source.pinned_module(path, pin(b"VALUE = 1\n"), "untrusted")

    def test_module_metadata_imports_and_annotation_semantics_are_preserved(self):
        body = b"import math\nVALUE = math.sqrt(9)\ndef identity(value: int): return value\n"
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "dependency.py"
            path.write_bytes(body)
            name = "generated_tms_dependency"
            loaded = self.source.pinned_module(path, pin(body), name)
            self.assertEqual(loaded.VALUE, 3)
            self.assertIs(loaded.identity.__annotations__["value"], int)
            self.assertEqual(loaded.__name__, name)
            self.assertEqual(loaded.__file__, str(path))
            self.assertEqual(loaded.__package__, "")
            self.assertEqual(loaded.__spec__.origin, str(path))
            self.assertIs(loaded.__loader__, loaded.__spec__.loader)
            self.assertEqual(loaded.__cached__, importlib.util.cache_from_source(str(path)))

    def test_relative_source_keeps_absolute_module_and_code_locations(self):
        body = b"def location(): return __file__\n"
        with tempfile.TemporaryDirectory() as temp, chdir(temp):
            path = Path("dependency.py")
            path.write_bytes(body)
            expected = str(path.resolve())
            loaded = self.source.pinned_module(path, pin(body), "relative_dependency")
            self.assertEqual(loaded.__file__, expected)
            self.assertEqual(loaded.location(), expected)
            self.assertEqual(loaded.location.__code__.co_filename, expected)

    def test_verified_bytes_honor_source_encoding_cookie(self):
        body = b'# coding: latin-1\nTEXT = "caf\xe9"\n'
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "dependency.py"
            path.write_bytes(body)
            loaded = self.source.pinned_module(path, pin(body), "encoded_dependency")
            self.assertEqual(loaded.TEXT, "caf\u00e9")

    def test_current_bindings_preserve_original_manifest_and_dependency_pins(self):
        descriptor = json.loads(DESCRIPTOR.read_bytes())
        for member in descriptor["members"]:
            body = (ROOT / member["path"]).read_bytes()
            self.assertEqual(pin(body), (member["bytes"], member["sha256"]))
        predecessor = descriptor["predecessor_manifest"]
        body = (ROOT / predecessor["path"]).read_bytes()
        self.assertEqual(pin(body), (predecessor["bytes"], predecessor["sha256"]))
        original = json.loads(body)
        self.assertEqual(self.source.VERIFIER_PIN,
                         tuple(original["local_files"]["projection_verify.py"][key]
                               for key in ("bytes", "sha256")))
        self.assertEqual(self.source.BEHAVIOR_PIN,
                         tuple(original["external_dependency"][key]
                               for key in ("bytes", "sha256")))
        self.assertFalse(descriptor["scientific_qualified"])
        self.assertFalse(descriptor["execution_authority"])


if __name__ == "__main__":
    unittest.main()
