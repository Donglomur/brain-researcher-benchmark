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


class CompleteInventoryTests(unittest.TestCase):
    """Full 102+1 invented metadata; fixed profile never imports factory code."""
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="invented-factory-integrity-")).resolve()
        self.prefix = "benchmarks/neuroscience/paper-paper-method-replacement-013"
        self.package = self.root / self.prefix
        self.package.mkdir(parents=True)
        task = "PAPER-paper-method-replacement-013"
        canonical_name = "benchmarks/manifests/paper/INVENTED.json"
        canonical = encoded({"id": task})
        (self.root / canonical_name).parent.mkdir(parents=True)
        (self.root / canonical_name).write_bytes(canonical)
        old = []
        for i in range(95):
            name = "old_%03d.py" % i
            body = b'raise RuntimeError("invented source must not execute")\n'
            (self.package / name).write_bytes(body)
            old.append(descriptor(name, body))
        inventory = encoded({"files": old})
        (self.package / "TASK_SOURCE_FREEZE.json").write_bytes(inventory)
        manifest = encoded({"id": task, "canonical_specification": descriptor(canonical_name, canonical),
                            "source_freeze": descriptor("TASK_SOURCE_FREEZE.json", inventory)})
        (self.package / "manifest.json").write_bytes(manifest)
        for name in ("native_factory.py", "native_factory_v2.py"):
            (self.package / name).write_text('raise RuntimeError("factory must not execute")\ndef run_historical():\n    pass\n')
        (self.package / "native_factory_runtime.py").write_text("pass\n")
        (self.package / "NATIVE_FACTORY.md").write_text("Invented source fixture.\n")
        (self.package / "NATIVE_FACTORY_PREDECESSOR.json").write_text("{}\n")
        rows = []
        for path in sorted(self.package.iterdir()):
            row = descriptor(path.name, path.read_bytes()); row["git_mode"] = "100644"
            rows.append(row)
        self.api = {"schema": "neuroformer_fixed_historical_factory_api_v2",
                    "entry": "native_factory_v2.run_historical",
                    "historical_unselected_entry": "native_factory.run_historical",
                    "generic_registration_changed": False, "native_execution_qualified": False,
                    "scientific_execution_authorized": False, "new_callbacks_or_runtime_injection": False,
                    "legacy_registered_dispatch_unchanged": True, "unchanged_predecessor_files": 97,
                    "retained_scope": {"slots": 46, "cells": 85, "wider_families": 7,
                                       "existing_apis": 6, "existing_unavailable_dispositions": 20, "gates": 29},
                    "source_inventory": {"schema": "neuroformer_factory_source_inventory_v2",
                                         "files": rows, "count": 102, "whole_package_count": 103,
                                         "self_excluded": "NATIVE_FACTORY_API.json",
                                         "total_bytes": sum(row["bytes"] for row in rows),
                                         "unchanged_predecessors": 97}}
        self.enrollment = {"id": task, "root": self.prefix, "inventory": "TASK_SOURCE_FREEZE.json",
                           "inventory_paths": "package", "supplemental_files": [],
                           "complete_inventory": {"profile": "neuroformer_factory_v2", "path": "NATIVE_FACTORY_API.json"}}
        self.registry = {"schema_version": 1, "scope": "invented", "packages": [self.enrollment]}
        self.sync_api()

    def tearDown(self):
        result = self._outcome.result
        if any(test is self for test, _ in result.failures + result.errors):
            print("Preserved failed invented fixture:", self.root)
        else:
            shutil.rmtree(self.root)

    def sync_api(self):
        (self.package / "NATIVE_FACTORY_API.json").write_bytes(encoded(self.api))
        names = ("manifest.json", "NATIVE_FACTORY.md", "NATIVE_FACTORY_API.json", "NATIVE_FACTORY_PREDECESSOR.json",
                 "native_factory.py", "native_factory_runtime.py", "native_factory_v2.py")
        self.enrollment["supplemental_files"] = [descriptor(name, (self.package / name).read_bytes()) for name in names]
        (self.root / "benchmarks/source_integrity.json").write_bytes(encoded(self.registry))

    def reject(self, pattern):
        with self.assertRaisesRegex(checker.InvalidSource, pattern):
            checker.check(self.root)

    def test_full_profile_positive_no_execution(self):
        result = checker.check(self.root)
        self.assertEqual(result["packages"][0]["source_files"], 103)
        self.assertFalse(result["benchmark_execution"])

    def test_profile_is_explicit_not_filename_selected(self):
        del self.enrollment["complete_inventory"]
        self.api["schema"] = "uninterpreted when unenrolled"
        self.sync_api()
        self.assertEqual(checker.check(self.root)["status"], "source_integrity_passed")

    def test_unknown_profile(self):
        self.enrollment["complete_inventory"]["profile"] = "unreviewed"
        self.sync_api(); self.reject("Unknown complete")

    def test_wrong_api_selector(self):
        self.enrollment["complete_inventory"]["path"] = "OTHER.json"
        self.sync_api(); self.reject("Unknown complete")

    def test_independent_api_pin(self):
        (self.package / "NATIVE_FACTORY_API.json").write_bytes(encoded(self.api) + b" ")
        self.reject("hash or length mismatch")

    def test_api_schema(self):
        self.api["schema"] = "other"; self.sync_api(); self.reject("API schema")

    def test_inventory_schema(self):
        self.api["source_inventory"]["schema"] = "other"
        self.sync_api(); self.reject("inventory schema")

    def test_counts_and_extent(self):
        for key in ("count", "whole_package_count", "unchanged_predecessors", "total_bytes"):
            with self.subTest(key=key):
                old = self.api["source_inventory"][key]
                self.api["source_inventory"][key] = float(old)
                self.sync_api(); self.reject("count mismatch|byte total")
                self.api["source_inventory"][key] = old

    def test_total_extent_value(self):
        self.api["source_inventory"]["total_bytes"] += 1
        self.sync_api(); self.reject("byte total")

    def test_self_name(self):
        self.api["source_inventory"]["self_excluded"] = "other.json"
        self.sync_api(); self.reject("self exclusion")

    def test_rows_missing_duplicate_self_traversal(self):
        original = list(self.api["source_inventory"]["files"])
        changes = [original[:-1], original[:-1] + [dict(original[0])],
                   original[:-1] + [dict(original[-1], path="NATIVE_FACTORY_API.json")],
                   original[:-1] + [dict(original[-1], path="../outside.py")]]
        for rows in changes:
            with self.subTest(rows=len(rows), last=rows[-1]["path"]):
                self.api["source_inventory"]["files"] = rows
                self.sync_api(); self.reject("102 rows|Duplicate/self|traversal")

    def test_complete_row_hash_and_mode(self):
        row = self.api["source_inventory"]["files"][0]
        for key, value in (("sha256", "0" * 64), ("git_mode", "100755"), ("bytes", True)):
            with self.subTest(key=key):
                old = row[key]; row[key] = value
                self.sync_api(); self.reject("hash or length|mode must|Invalid source extent")
                row[key] = old

    def test_actual_source_and_api_modes(self):
        for name in ("native_factory_v2.py", "NATIVE_FACTORY_API.json"):
            with self.subTest(name=name):
                p = self.package / name; p.chmod(0o755)
                self.reject("permission mode")
                p.chmod(0o644)

    def test_entry_declaration_and_function(self):
        self.api["entry"] = "native_factory.run_historical"
        self.sync_api(); self.reject("entry mismatch")
        self.api["entry"] = "native_factory_v2.run_historical"
        body = b"pass\n"; (self.package / "native_factory_v2.py").write_bytes(body)
        for row in self.api["source_inventory"]["files"]:
            if row["path"] == "native_factory_v2.py":
                row.update(descriptor(row["path"], body))
        self.api["source_inventory"]["total_bytes"] = sum(row["bytes"] for row in self.api["source_inventory"]["files"])
        self.sync_api(); self.reject("entry function")

    def test_inactive_flags_typed(self):
        for field in ("generic_registration_changed", "native_execution_qualified", "scientific_execution_authorized",
                      "new_callbacks_or_runtime_injection"):
            with self.subTest(field=field):
                self.api[field] = 0
                self.sync_api(); self.reject("inactive flag")
                self.api[field] = False

    def test_legacy_flag_and_retained_scope(self):
        self.api["legacy_registered_dispatch_unchanged"] = 1
        self.sync_api(); self.reject("legacy dispatch")
        self.api["legacy_registered_dispatch_unchanged"] = True
        self.api["retained_scope"]["cells"] = 85.0
        self.sync_api(); self.reject("retained scope")


if __name__ == "__main__":
    unittest.main()

