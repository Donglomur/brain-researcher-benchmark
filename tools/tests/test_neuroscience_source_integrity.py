"""Invented source-only controls; no benchmark modules or scientific inputs."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

CHECKER = Path(__file__).absolute().parents[1] / "check_neuroscience_source_integrity.py"
spec = importlib.util.spec_from_file_location("source_integrity_checker", CHECKER)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


def descriptor(path, body):
    return {"path": path, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


class SourceIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="invented-source-integrity-")).resolve()
        self.prefix = "benchmarks/neuroscience/invented"
        self.package = self.root / self.prefix
        self.package.mkdir(parents=True)
        self.canonical_path = "benchmarks/manifests/neural/NEURAL-INVENTED.json"
        self.canonical = {"id": "NEURAL-INVENTED"}
        self.source = b'raise RuntimeError("candidate source must never execute")\n'
        (self.package / "source.py").write_bytes(self.source)
        self.inventory = {"files": [descriptor("source.py", self.source)]}
        canonical_body = encoded(self.canonical)
        p = self.root / self.canonical_path
        p.parent.mkdir(parents=True)
        p.write_bytes(canonical_body)
        self.manifest = {"id": "NEURAL-INVENTED",
                         "canonical_specification": descriptor(self.canonical_path, canonical_body)}
        self.enrollment = {"id": "NEURAL-INVENTED", "root": self.prefix,
                           "inventory": "INVENTORY.json", "inventory_paths": "package",
                           "supplemental_files": []}
        self.registry = {"schema_version": 1, "scope": "invented engineering fixture",
                         "packages": [self.enrollment]}
        self.sync_inventory()

    def tearDown(self):
        result = self._outcome.result
        failed = any(test is self for test, _ in result.failures + result.errors)
        if failed:
            print("Preserved failed invented fixture:", self.root)
        else:
            shutil.rmtree(self.root)

    def sync_registry(self):
        (self.root / "benchmarks/source_integrity.json").write_bytes(encoded(self.registry))

    def sync_manifest(self):
        body = encoded(self.manifest)
        (self.package / "manifest.json").write_bytes(body)
        self.enrollment["supplemental_files"] = [descriptor("manifest.json", body)]
        self.sync_registry()

    def sync_inventory(self):
        body = encoded(self.inventory)
        (self.package / "INVENTORY.json").write_bytes(body)
        self.manifest["source_freeze"] = descriptor("INVENTORY.json", body)
        self.sync_manifest()

    def reject(self, message):
        with self.assertRaisesRegex(checker.InvalidSource, message):
            checker.check(self.root)

    def test_valid_bundle_is_checked_without_execution(self):
        result = checker.check(self.root)
        self.assertEqual(result["packages"], [{"id": "NEURAL-INVENTED", "source_files": 3, "python_files": 1}])
        self.assertFalse(result["benchmark_execution"])
        self.assertFalse(result["scientific_qualification_assessed"])

    def test_repository_relative_inventory(self):
        self.inventory["files"][0]["path"] = self.prefix + "/source.py"
        self.inventory["files"][0]["runtime_path"] = "source.py"
        self.enrollment["inventory_paths"] = "repository"
        self.sync_inventory()
        self.assertEqual(checker.check(self.root)["status"], "source_integrity_passed")

    def test_modified_body(self):
        (self.package / "source.py").write_bytes(b"pass\n")
        self.reject("hash or length mismatch")

    def test_missing_source(self):
        (self.package / "source.py").unlink()
        with self.assertRaises(FileNotFoundError):
            checker.check(self.root)

    def test_extra_file(self):
        (self.package / "unexpected.py").write_text("pass\n")
        self.reject("Missing or extra")

    def test_inventory_duplicate(self):
        self.inventory["files"].append(dict(self.inventory["files"][0]))
        self.sync_inventory()
        self.reject("Duplicate/self")

    def test_inventory_self_reference(self):
        self.inventory["files"][0]["path"] = "INVENTORY.json"
        self.sync_inventory()
        self.reject("Duplicate/self")

    def test_traversal(self):
        self.inventory["files"][0]["path"] = "../outside.py"
        self.sync_inventory()
        self.reject("traversal")

    def test_repository_member_escapes_package(self):
        self.enrollment["inventory_paths"] = "repository"
        self.inventory["files"][0]["path"] = "tools/unrelated.py"
        self.sync_inventory()
        self.reject("escapes")

    def test_runtime_path_disagreement(self):
        self.inventory["files"][0]["runtime_path"] = "other.py"
        self.sync_inventory()
        self.reject("Runtime path disagreement")

    def test_boolean_extent(self):
        self.inventory["files"][0]["bytes"] = True
        self.sync_inventory()
        self.reject("Invalid source extent")

    def test_bad_digest(self):
        self.inventory["files"][0]["sha256"] = "z" * 64
        self.sync_inventory()
        self.reject("Invalid source digest")

    def test_duplicate_json_key(self):
        (self.root / "benchmarks/source_integrity.json").write_text('{"packages":[],"packages":[]}\n')
        self.reject("Duplicate JSON key")

    def test_nonfinite_json(self):
        (self.root / "benchmarks/source_integrity.json").write_text('{"value":NaN}\n')
        self.reject("Nonfinite JSON")

    def test_empty_enrollment_is_not_success(self):
        self.registry["packages"] = []
        self.sync_registry()
        self.reject("Nonempty bounded")

    def test_duplicate_enrollment(self):
        self.registry["packages"].append(dict(self.enrollment))
        self.sync_registry()
        self.reject("Duplicate or invalid task")

    def test_manifest_identity(self):
        self.manifest["id"] = "WRONG"
        self.sync_manifest()
        self.reject("Manifest task ID")

    def test_canonical_identity_after_rehash(self):
        body = encoded({"id": "WRONG"})
        (self.root / self.canonical_path).write_bytes(body)
        self.manifest["canonical_specification"] = descriptor(self.canonical_path, body)
        self.sync_manifest()
        self.reject("Canonical task ID")

    def test_external_canonical_boundary(self):
        self.manifest["canonical_specification"]["path"] = "benchmarks/neuroscience/other/private.json"
        self.sync_manifest()
        self.reject("Unexpected external canonical")

    def test_manifest_wrong_freeze(self):
        self.manifest["source_freeze"]["path"] = "OTHER.json"
        self.sync_manifest()
        self.reject("different inventory")

    def test_stale_freeze_binding(self):
        (self.package / "INVENTORY.json").write_bytes(encoded(self.inventory) + b" ")
        self.reject("hash or length mismatch")

    def test_python_syntax_after_rehash(self):
        source = b"def broken(\n"
        (self.package / "source.py").write_bytes(source)
        self.inventory["files"][0] = descriptor("source.py", source)
        self.sync_inventory()
        with self.assertRaises(SyntaxError):
            checker.check(self.root)

    def test_symlink_member(self):
        (self.package / "source.py").unlink()
        (self.package / "source.py").symlink_to(self.root / self.canonical_path)
        self.reject("Symlink")

    def test_symlink_directory(self):
        (self.package / "linked").symlink_to(self.root, target_is_directory=True)
        self.reject("Directory symlink")

    def test_hardlinked_member(self):
        os.link(self.package / "source.py", self.root / "second-name.py")
        self.reject("Single-link regular")

    def test_member_bound_before_body_read(self):
        reader = checker.Reader(self.root)
        with mock.patch.object(checker, "MEMBER_LIMIT", 8):
            with self.assertRaisesRegex(checker.InvalidSource, "too large"):
                reader.read(self.prefix + "/source.py")
        self.assertEqual(reader.bytes_read, 0)

    def test_aggregate_bound_before_body_read(self):
        reader = checker.Reader(self.root)
        with mock.patch.object(checker, "TOTAL_LIMIT", 8):
            with self.assertRaisesRegex(checker.InvalidSource, "budget"):
                reader.read(self.prefix + "/source.py")
        self.assertEqual(reader.bytes_read, 0)

    def test_cached_source_must_not_change(self):
        reader = checker.Reader(self.root)
        reader.read(self.prefix + "/source.py")
        (self.package / "source.py").write_text("pass\n")
        with self.assertRaisesRegex(checker.InvalidSource, "Cached source changed"):
            reader.read(self.prefix + "/source.py")


if __name__ == "__main__":
    unittest.main()

