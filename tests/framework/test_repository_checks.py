"""Small ordinary-source fixtures; never run scientific or candidate code."""

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("repository_checks_under_test", ROOT / "src/neurobench/repository_checks.py")
checks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checks)


def write_json(path, document):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(document, indent=2) + "\n").encode()
    path.write_bytes(raw)
    return {"path": path, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def fixture(root):
    tasks = []
    for track in ("paper", "neural"):
        folder = root / "benchmarks" / track
        folder.mkdir(parents=True)
        (folder / "README.md").write_text("# Track navigation\n")
        for number, classification in ((1, "canonical"), (2, "expansion")):
            identifier = f"{track.upper()}-{number:03d}"
            directory = f"benchmarks/{track}/{identifier}"
            pin = write_json(root / directory / "task.json", {
                "id": identifier, "track": track,
                "private_payload_locator": "/private/never-open-this-receipt.json"})
            pin["path"] = directory + "/task.json"
            (root / directory / "README.md").write_text("# Task navigation\n")
            tasks.append({"id": identifier, "track": track, "task_directory": directory,
                          "specification": pin, "specification_id": identifier, "specification_alias": False,
                          "registration_class": classification, "scientific_readiness": "unknown",
                          "submission_readiness": "unknown", "runtime_manifest": None, "runtime_package": None})
    owned = "benchmarks/paper/PAPER-001/implementations/example"
    shared = "benchmarks/shared/diagnostic/example"
    artifacts = []
    for identifier, path, scope, owners, related in (
            ("owned", owned, "task", ["PAPER-001"], []),
            ("related", shared, "shared", [], ["NEURAL-001"])):
        (root / path).mkdir(parents=True)
        (root / path / "example.py").write_text("raise AssertionError('This source must never execute')\n")
        artifacts.append({"id": identifier, "path": path, "scope": scope, "owner_ids": owners,
                          "related_task_ids": related, "role": "invented source fixture",
                          "scope_notes": "No scientific result", "scientific_readiness": "unknown"})
    (root / "benchmarks/shared/README.md").write_text("# Shared source\n")
    registry = {"schema_version": 1, "kind": "neuroscience_benchmark_registry", "tasks": tasks,
                "source_counts": {"paper": 2, "neural": 2, "total": 4, "canonical_specifications": 2,
                                  "expansion_drafts": 2, "source_components": 1, "runtime_manifests": 0,
                                  "linked_runtime_manifests": 0},
                "implementations": artifacts, "components": [{"path": owned}],
                "historical_registries": [], "shared_contracts": []}
    write_json(root / checks.REGISTRY, registry)
    write_json(root / checks.CURRENT_BINDINGS, {"scope": "fixture source binding, no qualification"})
    write_json(root / checks.CURRENT_CLOSURES / "example" / "binding.json", {
        "private_payload_locator": "/private/never-open-this-binding.json"})
    rows = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            relative = path.relative_to(root).as_posix()
            rows.append({"old": relative, "new": relative})
    write_json(root / checks.RELOCATIONS, {"schema_version": 1, "files": rows})
    return registry


class RepositoryChecksTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.profile = patch.object(checks, "CANONICAL_PER_TRACK", 1)
        self.profile.start()
        self.addCleanup(self.profile.stop)
        self.registry = fixture(self.root)

    def build(self):
        return checks.check_repository(self.root, write=True)

    def check(self):
        return checks.check_repository(self.root)

    def save_registry(self):
        write_json(self.root / checks.REGISTRY, self.registry)

    def test_all_artifacts_and_task_specs_are_hashed_without_running_source(self):
        result = self.build()
        self.assertEqual(result["artifacts"], 2)
        self.assertEqual(result["artifact_files"], 2)
        self.assertEqual(result["current_binding_files"], 2)
        self.assertEqual(result["source_files"], 8)
        self.assertFalse(result["scientific_qualification"])
        self.assertEqual(self.check()["source_check"], "passed")
        runtime = self.root / ".neurobench"
        runtime.mkdir()
        (runtime / "not-source.bin").write_bytes(b"Local runtime output is not source.")
        self.assertEqual(self.check()["source_check"], "passed")

    def test_changed_source_and_mode_refuse(self):
        self.build()
        path = self.root / self.registry["implementations"][0]["path"] / "example.py"
        original = path.read_bytes()
        path.write_bytes(b"changed source\n")
        with self.assertRaisesRegex(ValueError, "Source content or mode drift"):
            self.check()
        path.write_bytes(original)
        path.chmod(0o755)
        with self.assertRaisesRegex(ValueError, "Source content or mode drift"):
            self.check()

    def test_missing_extra_and_orphan_source_refuse(self):
        self.build()
        artifact = self.root / self.registry["implementations"][0]["path"]
        path = artifact / "example.py"
        body = path.read_bytes()
        path.unlink()
        with self.assertRaisesRegex(ValueError, "Missing source path"):
            self.check()
        path.write_bytes(body)
        extra = artifact / "unexpected.py"
        extra.write_text("extra source\n")
        with self.assertRaisesRegex(ValueError, "Missing or unexpected"):
            self.check()
        extra.unlink()
        orphan = artifact.parent / "unregistered"
        orphan.mkdir()
        with self.assertRaisesRegex(ValueError, "Orphan source directory"):
            self.check()

    def test_unknown_owners_and_related_as_owner_misclassification_refuse(self):
        self.registry["implementations"][0]["owner_ids"] = ["PAPER-NOT-REGISTERED"]
        self.save_registry()
        with self.assertRaisesRegex(ValueError, "Unknown artifact owner"):
            self.build()
        self.registry["implementations"][0]["owner_ids"] = ["PAPER-001"]
        related = self.registry["implementations"][1]
        related["owner_ids"] = ["NEURAL-001"]
        self.save_registry()
        with self.assertRaisesRegex(ValueError, "Related task cannot also"):
            self.build()
        related["related_task_ids"] = []
        related["scope"] = "task"
        self.save_registry()
        with self.assertRaisesRegex(ValueError, "outside its owner home"):
            self.build()

    def test_explicit_framework_source_is_shared_without_scientific_ownership(self):
        path = "src/neurobench/description_validator"
        (self.root / path).mkdir(parents=True)
        (self.root / path / "validator.py").write_text("raise AssertionError('Do not execute')\n")
        row = {"id": "framework", "path": path, "scope": "shared", "owner_ids": [],
               "related_task_ids": [], "status": "shared_framework_source", "role": "source description validator",
               "scope_notes": "No scientific execution or qualification", "scientific_readiness": "unknown"}
        self.registry["implementations"].append(row)
        self.save_registry()
        self.assertEqual(self.build()["artifacts"], 3)
        self.assertEqual(self.check()["source_check"], "passed")
        for field, value in (("owner_ids", ["PAPER-001"]), ("related_task_ids", ["NEURAL-001"]),
                             ("status", "not-framework-source")):
            old = row[field]
            row[field] = value
            self.save_registry()
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "Shared artifact is misclassified"):
                self.build()
            row[field] = old

    def test_current_binding_metadata_drift_membership_and_aliases_refuse(self):
        self.build()
        path = self.root / checks.CURRENT_CLOSURES / "example" / "binding.json"
        original = path.read_bytes()
        path.write_text('{"modified": true}\n')
        with self.assertRaisesRegex(ValueError, "Source content or mode drift"):
            self.check()
        path.write_bytes(original)
        extra = path.parent / "unexpected.json"
        extra.write_text('{}\n')
        with self.assertRaisesRegex(ValueError, "Missing or unexpected"):
            self.check()
        extra.unlink()
        extra = path.parent / "unexpected.py"
        extra.write_text("Must not be read\n")
        with self.assertRaisesRegex(ValueError, "Unexpected current-binding"):
            self.check()
        extra.unlink()
        path.unlink()
        path.symlink_to(self.root / "missing-private-binding")
        with self.assertRaisesRegex(ValueError, "ordinary single-link"):
            self.check()

    def test_current_binding_readme_is_pinned_with_strict_member_names(self):
        directory = self.root / checks.CURRENT_CLOSURES / "example"
        readme = directory / "README.md"
        body = b"# Current source descriptor\nNo scientific qualification.\n"
        readme.write_bytes(body)
        result = self.build()
        self.assertEqual(result["current_binding_files"], 3)
        self.assertEqual(self.check()["source_check"], "passed")
        inventory = json.loads((self.root / checks.INVENTORY).read_text())
        row = next(row for row in inventory["files"]
                   if row["path"] == readme.relative_to(self.root).as_posix())
        self.assertEqual(row["owner"], "current-binding-metadata")
        self.assertEqual(row["bytes"], len(body))
        self.assertEqual(row["sha256"], hashlib.sha256(body).hexdigest())
        readme.write_bytes(body + b"Modified guide\n")
        with self.assertRaisesRegex(ValueError, "Source content or mode drift"):
            self.check()
        readme.write_bytes(body)
        rejected = directory / "rejected-members"
        rejected.mkdir()
        # Separate directory avoids README/readme aliasing on macOS filesystems.
        for name in ("notes.md", "readme.md", "README.MD", "README.txt", "source.py", "binding.JSON"):
            path = rejected / name
            path.write_text("Generated unsupported member\n")
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "Unexpected current-binding member"):
                self.build()
            path.unlink()
        rejected.rmdir()
        self.assertEqual(self.check()["source_check"], "passed")

    def test_current_binding_readme_rejects_symlinks_and_hardlinks(self):
        directory = self.root / checks.CURRENT_CLOSURES / "example"
        readme = directory / "README.md"
        target = self.root / "outside-binding-note.md"
        target.write_text("Generated fixture, not a current binding\n")
        for alias in ("symlink", "hardlink"):
            if alias == "symlink":
                readme.symlink_to(target)
            else:
                readme.hardlink_to(target)
            with self.subTest(alias=alias), self.assertRaisesRegex(ValueError, "ordinary single-link file"):
                self.build()
            readme.unlink()

    def test_outside_paths_and_source_aliases_refuse_before_inventory_write(self):
        row = self.registry["implementations"][0]
        original = row["path"]
        for path in ("../outside", "/outside", "benchmarks/../outside"):
            row["path"] = path
            self.save_registry()
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, "inside the repository"):
                self.build()
            self.assertFalse((self.root / checks.INVENTORY).exists())
        row["path"] = original
        self.save_registry()
        leaf = self.root / original / "example.py"
        leaf.unlink()
        leaf.symlink_to(self.root / "missing-private-source")
        with self.assertRaisesRegex(ValueError, "ordinary single-link"):
            self.build()
        leaf.unlink()
        target = self.root / "external-note.txt"
        target.write_text("Do not treat aliases as independent source")
        leaf.hardlink_to(target)
        with self.assertRaisesRegex(ValueError, "ordinary single-link"):
            self.build()

    def test_extra_inventory_entry_and_retired_roots_refuse(self):
        self.build()
        path = self.root / checks.INVENTORY
        data = json.loads(path.read_text())
        data["files"].append(dict(data["files"][0]))
        write_json(path, data)
        with self.assertRaisesRegex(ValueError, "Missing or unexpected"):
            self.check()
        (self.root / "authoring").symlink_to(self.root / "does-not-exist")
        with self.assertRaisesRegex(ValueError, "Retired active root"):
            self.build()

    def test_wrong_task_home_and_unexpected_task_directory_refuse(self):
        self.registry["tasks"][0]["task_directory"] = "benchmarks/neural/PAPER-001"
        self.save_registry()
        with self.assertRaisesRegex(ValueError, "Task home does not match"):
            self.build()
        self.registry["tasks"][0]["task_directory"] = "benchmarks/paper/PAPER-001"
        self.save_registry()
        (self.root / "benchmarks/paper/UNKNOWN").mkdir()
        with self.assertRaisesRegex(ValueError, "Orphan source directory"):
            self.build()

    def test_unregistered_top_level_benchmark_namespace_refuses(self):
        self.build()
        typo = self.root / "benchmarks/papre/PAPER-001/runner.py"
        typo.parent.mkdir(parents=True)
        typo.write_text("raise AssertionError('Do not execute')\n")
        for operation in (self.check, self.build):
            with self.subTest(operation=operation.__name__), self.assertRaisesRegex(
                    ValueError, "Orphan source directory: benchmarks/papre"):
                operation()
        typo.unlink()
        typo.parent.rmdir()
        typo.parent.parent.rmdir()
        stray = self.root / "benchmarks/unregistered.py"
        stray.write_text("raise AssertionError('Do not execute')\n")
        with self.assertRaisesRegex(ValueError, "Orphan source file: benchmarks/unregistered.py"):
            self.check()
        stray.unlink()
        # Runtime output remains outside the benchmark source namespace.
        (self.root / ".neurobench").mkdir()
        (self.root / ".neurobench/result.bin").write_bytes(b"generated runtime output")
        self.assertEqual(self.check()["source_check"], "passed")

    def test_byte_limits_and_non_source_payloads_refuse(self):
        with patch.object(checks, "MAX_READ_BYTES", 1), self.assertRaisesRegex(ValueError, "budget"):
            self.build()
        path = self.root / self.registry["implementations"][0]["path"] / "raw-array.npy"
        path.write_bytes(b"Not a source file")
        with self.assertRaisesRegex(ValueError, "Non-source member type"):
            self.build()


if __name__ == "__main__":
    unittest.main()
