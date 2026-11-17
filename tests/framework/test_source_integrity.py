"""Invented source-only controls; no benchmark modules or scientific inputs."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

CHECKER = Path(__file__).absolute().parents[2] / "src/neurobench/source_integrity.py"
spec = importlib.util.spec_from_file_location("source_integrity_checker", CHECKER)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)
REFRESH = CHECKER.parents[2] / "scripts/maintenance/refresh_paper_integrity.py"
refresh_spec = importlib.util.spec_from_file_location("paper_integrity_refresh", REFRESH)
refresh = importlib.util.module_from_spec(refresh_spec)
refresh_spec.loader.exec_module(refresh)


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


def descriptor(path, body):
    return {"path": path, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def current_registry(root, legacy):
    """Invented predecessor/current metadata; never execute fixture source."""
    packages = []
    for old in legacy["packages"]:
        task_id = old["id"]
        track = old["track"]
        home = f"benchmarks/{track}/{task_id}"
        registered_path = home + "/task.json"
        registered_body = (root / registered_path).read_bytes()
        task_pin = descriptor(registered_path, registered_body)
        task_pin.update(original_path=f"benchmarks/manifests/{track}/{task_id}.json",
                        predecessor={k: task_pin[k] for k in ("bytes", "sha256")})
        package = root / old["root"]
        rows = []
        for path in sorted(package.rglob("*")):
            if path.is_file():
                name = path.relative_to(package).as_posix()
                row = descriptor(name, path.read_bytes())
                row["git_mode"] = "100755" if path.stat().st_mode & 0o111 else "100644"
                row["predecessor"] = copy.deepcopy(old.get("_predecessors", {}).get(
                    name, {k: row[k] for k in ("bytes", "sha256", "git_mode")}))
                rows.append(row)
        history = descriptor(old["inventory"], (package / old["inventory"]).read_bytes())
        history.update(path_style=old["inventory_paths"], supplemental_files=old["supplemental_files"])
        item = {"implementation_id": old.get("implementation_id", old["root"].replace("/", "-")),
                "task_id": task_id, "track": track, "root": old["root"],
                "original_root": old["original_root"], "registered_task": task_pin,
                "historical_inventory": history, "files": rows}
        if "complete_inventory" in old:
            item["complete_inventory"] = old["complete_inventory"]
        packages.append(item)
    return {"schema_version": 2, "scope": "invented predecessor/current engineering fixtures",
            "predecessor_commit": "0" * 40, "packages": packages}


def write_current(root, legacy):
    path = root / "benchmarks/integrity/current.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    result = current_registry(root, legacy)
    path.write_bytes(encoded(result))
    return result


class SourceIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="invented-source-integrity-")).resolve()
        self.prefix = "benchmarks/neural/NEURAL-INVENTED/implementations/registered-runtime"
        self.original_prefix = "benchmarks/neuroscience/invented"
        self.package = self.root / self.prefix
        self.package.mkdir(parents=True)
        self.canonical_path = "benchmarks/neural/NEURAL-INVENTED/task.json"
        self.original_canonical_path = "benchmarks/manifests/neural/NEURAL-INVENTED.json"
        self.canonical = {"id": "NEURAL-INVENTED", "track": "neural"}
        self.source = b'raise RuntimeError("candidate source must never execute")\n'
        (self.package / "source.py").write_bytes(self.source)
        self.inventory = {"files": [descriptor("source.py", self.source)]}
        canonical_body = encoded(self.canonical)
        p = self.root / self.canonical_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(canonical_body)
        self.manifest = {"id": "NEURAL-INVENTED",
                         "canonical_specification": descriptor(self.original_canonical_path, canonical_body)}
        self.enrollment = {"id": "NEURAL-INVENTED", "track": "neural", "root": self.prefix,
                           "original_root": self.original_prefix, "implementation_id": "invented-source",
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
        write_current(self.root, self.registry)

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

    def make_paper_revision(self):
        """Create explicit old/current PAPER source metadata, with no scientific run."""
        old_home = self.package.parent.parent
        self.task_id = "PAPER-INVENTED"
        home = "benchmarks/paper/" + self.task_id
        new_home = self.root / home
        new_home.parent.mkdir(parents=True)
        old_home.rename(new_home)
        self.prefix = home + "/implementations/registered-runtime"
        self.package = self.root / self.prefix
        self.canonical_path = home + "/task.json"
        self.original_canonical_path = "benchmarks/manifests/paper/" + self.task_id + ".json"
        self.canonical = {"id": self.task_id, "track": "paper"}
        old_body = encoded(self.canonical)
        (self.root / self.canonical_path).write_bytes(old_body)
        self.enrollment.update(id=self.task_id, track="paper", root=self.prefix)
        self.manifest.update(id=self.task_id,
                             canonical_specification=descriptor(self.original_canonical_path, old_body))
        self.sync_inventory()
        current_path = self.root / "benchmarks/integrity/current.json"
        self.current = json.loads(current_path.read_text())
        self.history_path = home + "/" + checker.PAPER_HISTORY
        history = self.root / self.history_path
        history.parent.mkdir()
        history.write_bytes(old_body)
        self.contract_path = home + "/improvement.v1.json"
        self.contract = {"schema_version": checker.PAPER_REVISION, "task_id": self.task_id,
                         "objective": checker.PAPER_OBJECTIVE, "disposition": "source_unresolved",
                         "legacy": {"role": "calibration_only", "original_task": checker.PAPER_HISTORY}}
        contract_body = encoded(self.contract)
        (self.root / self.contract_path).write_bytes(contract_body)
        self.revision = {"version": checker.PAPER_REVISION,
                         "previous_specification": descriptor(self.history_path, old_body),
                         "improvement_contract": descriptor(self.contract_path, contract_body)}
        self.current_task = {**self.canonical, "objective": checker.PAPER_OBJECTIVE,
                             "status": "source_unresolved", "evaluation": {
                                 "objective": checker.PAPER_OBJECTIVE, "disposition": "source_unresolved",
                                 "contract": self.revision["improvement_contract"],
                                 "reproduction_role": "calibration_only",
                                 "calibration": {"historical_task": self.revision["previous_specification"]}}}
        self.registered = {"id": self.task_id, "track": "paper", "task_directory": home,
                           "original_specification": descriptor(self.original_canonical_path, old_body),
                           "specification_revision": self.revision}
        self.sync_paper_revision()

    def sync_paper_revision(self):
        body = encoded(self.current_task)
        (self.root / self.canonical_path).write_bytes(body)
        self.registered["specification"] = descriptor(self.canonical_path, body)
        self.current["packages"][0]["registered_task"].update(
            self.registered["specification"], specification_revision=self.revision)
        self.save_paper_metadata()

    def save_paper_metadata(self):
        (self.root / "benchmarks/integrity/current.json").write_bytes(encoded(self.current))
        (self.root / "benchmarks/registry.json").write_bytes(encoded({
            "schema_version": 1, "kind": "neuroscience_benchmark_registry", "tasks": [self.registered]}))

    def test_versioned_paper_retains_exact_historical_canonical(self):
        self.make_paper_revision()
        old_manifest = (self.package / "manifest.json").read_bytes()
        result = checker.check(self.root)
        self.assertEqual(result["status"], "source_integrity_passed")
        self.assertEqual(result["packages"][0]["changed_files"], 0)
        self.assertEqual((self.package / "manifest.json").read_bytes(), old_manifest)
        self.assertFalse(result["benchmark_execution"])

    def test_paper_revision_cannot_forge_predecessor(self):
        self.make_paper_revision()
        forged = encoded({**self.canonical, "goal": "forged history"})
        (self.root / self.history_path).write_bytes(forged)
        self.revision["previous_specification"].update(descriptor(self.history_path, forged))
        self.sync_paper_revision()
        self.reject("does not match registered predecessor")

    def test_paper_revision_rejects_tampered_current_task(self):
        self.make_paper_revision()
        (self.root / self.canonical_path).write_bytes(encoded(self.current_task) + b" ")
        self.reject("hash or length mismatch")

    def test_paper_revision_rehash_does_not_excuse_changed_objective_or_calibration(self):
        for field in ("objective", "calibration"):
            with self.subTest(field=field):
                if field == "objective":
                    self.make_paper_revision()
                self.current_task = copy.deepcopy(self.current_task)
                if field == "objective":
                    self.current_task["objective"] = "reproduction_is_success"
                else:
                    self.current_task["objective"] = checker.PAPER_OBJECTIVE
                    self.current_task["evaluation"]["calibration"]["historical_task"] = {}
                self.sync_paper_revision()
                self.reject("not bound|calibration binding")

    def test_paper_revision_requires_exact_authoritative_registration(self):
        self.make_paper_revision()
        self.registered["original_specification"]["sha256"] = "0" * 64
        self.save_paper_metadata()
        self.reject("original registered identity")

    def test_paper_revision_rejects_unknown_version_and_cross_task_history(self):
        self.make_paper_revision()
        self.revision["version"] = "paper-improvement/v2"
        self.save_paper_metadata()
        self.reject("Unsupported paper specification revision")
        self.revision["version"] = checker.PAPER_REVISION
        self.revision["previous_specification"]["path"] = "benchmarks/paper/PAPER-OTHER/" + checker.PAPER_HISTORY
        self.save_paper_metadata()
        self.reject("member location")

    def test_paper_revision_cannot_change_legacy_implementation_evidence(self):
        self.make_paper_revision()
        (self.package / "manifest.json").write_bytes(encoded(self.manifest) + b" ")
        self.reject("hash or length mismatch")

    def test_neural_task_cannot_use_paper_revision_exception(self):
        path = self.root / "benchmarks/integrity/current.json"
        current = json.loads(path.read_text())
        current["packages"][0]["registered_task"]["specification_revision"] = {"version": checker.PAPER_REVISION}
        path.write_bytes(encoded(current))
        self.reject("Only paper tasks")

    def test_refresh_preserves_history_retargets_closure_and_is_idempotent(self):
        self.make_paper_revision()
        old = copy.deepcopy(self.current)
        task_pin = old["packages"][0]["registered_task"]
        del task_pin["specification_revision"]
        task_pin.update(task_pin["predecessor"])
        (self.root / "benchmarks/integrity/current.json").write_bytes(encoded(old))
        closure_name = "benchmarks/integrity/current-closures/invented/SOURCE.json"
        closure_path = self.root / closure_name
        closure_path.parent.mkdir(parents=True)
        closure = {"schema": "invented", "files": [{"path": self.canonical_path, **task_pin["predecessor"]}]}
        closure_body = encoded(closure)
        closure_path.write_bytes(closure_body)
        workflow_name = refresh.WORKFLOWS[0]
        workflow_path = self.root / workflow_name
        workflow_path.parent.mkdir(parents=True)
        workflow_path.write_text("# exact source literal\n" + json.dumps(descriptor(closure_name, closure_body)) + "\n")
        outputs, changes = refresh.build_outputs(self.root)
        self.assertEqual(set(outputs), {"benchmarks/integrity/current.json", closure_name, workflow_name})
        refreshed = json.loads(outputs[closure_name])
        self.assertEqual(refreshed["files"][0], self.revision["previous_specification"])
        self.assertEqual(refreshed[refresh.REVISION_FIELD][0]["role"], "calibration_only")
        self.assertEqual(changes[0]["previous"], descriptor(closure_name, closure_body))
        self.assertIn(changes[0]["current"]["sha256"].encode(), outputs[workflow_name])
        self.assertEqual(json.loads(outputs["benchmarks/integrity/current.json"])["packages"][0]["files"], old["packages"][0]["files"])
        for name, body in outputs.items():
            (self.root / name).write_bytes(body)
        self.assertEqual(refresh.build_outputs(self.root), ({}, []))
        self.assertEqual(checker.check(self.root)["status"], "source_integrity_passed")

    def test_refresh_refuses_stale_closure_and_workflow_pins(self):
        self.make_paper_revision()
        closure_name = "benchmarks/integrity/current-closures/invented/SOURCE.json"
        closure_path = self.root / closure_name
        closure_path.parent.mkdir(parents=True)
        value = {"files": [{"path": self.canonical_path, "bytes": 0, "sha256": "0" * 64}]}
        closure_path.write_bytes(encoded(value))
        with self.assertRaisesRegex(refresh.integrity.InvalidSource, "does not authenticate historical"):
            refresh.build_outputs(self.root)
        value["files"][0] = {"path": self.canonical_path, **self.current["packages"][0]["registered_task"]["predecessor"]}
        closure_path.write_bytes(encoded(value))
        workflow = self.root / refresh.WORKFLOWS[0]
        workflow.parent.mkdir(parents=True)
        workflow.write_text(json.dumps({"path": closure_name, "bytes": 0, "sha256": "0" * 64}))
        with self.assertRaisesRegex(refresh.integrity.InvalidSource, "Stale workflow"):
            refresh.build_outputs(self.root)

    def test_valid_bundle_is_checked_without_execution(self):
        result = checker.check(self.root)
        self.assertEqual(result["packages"], [{"implementation_id": "invented-source", "id": "NEURAL-INVENTED",
                                              "source_files": 3, "python_files": 1, "changed_files": 0}])
        self.assertFalse(result["benchmark_execution"])
        self.assertFalse(result["scientific_qualification_assessed"])

    def test_repository_relative_inventory(self):
        self.inventory["files"][0]["path"] = self.original_prefix + "/source.py"
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
        (self.root / "benchmarks/integrity/current.json").write_text('{"packages":[],"packages":[]}\n')
        self.reject("Duplicate JSON key")

    def test_nonfinite_json(self):
        (self.root / "benchmarks/integrity/current.json").write_text('{"value":NaN}\n')
        self.reject("Nonfinite JSON")

    def test_empty_enrollment_is_not_success(self):
        self.registry["packages"] = []
        self.sync_registry()
        self.reject("Nonempty bounded")

    def test_duplicate_enrollment(self):
        self.registry["packages"].append(dict(self.enrollment))
        self.sync_registry()
        self.reject("Duplicate or invalid implementation")

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


    def test_task_home_metadata_is_outside_the_closed_package(self):
        home = self.package.parent.parent
        (home / "README.md").write_text("Task navigation, outside the implementation closure.\n")
        self.assertEqual(checker.check(self.root)["packages"][0]["source_files"], 3)

    def test_two_implementations_can_share_a_task_owner(self):
        other = self.package.parent / "alternative"
        shutil.copytree(self.package, other)
        second = copy.deepcopy(self.enrollment)
        second.update(root=other.relative_to(self.root).as_posix(), implementation_id="invented-alternative",
                      original_root="benchmarks/neuroscience/invented-alternative")
        self.registry["packages"].append(second)
        self.sync_registry()
        result = checker.check(self.root)
        self.assertEqual(len(result["packages"]), 2)
        self.assertEqual({row["id"] for row in result["packages"]}, {"NEURAL-INVENTED"})

    def test_current_change_requires_current_and_predecessor_pins(self):
        old = json.loads((self.root / "benchmarks/integrity/current.json").read_text())
        self.enrollment["_predecessors"] = {row["path"]: row["predecessor"] for row in old["packages"][0]["files"]}
        (self.package / "source.py").write_text('raise RuntimeError("changed source must still never execute")\n')
        self.sync_registry()
        read = checker.Reader.read
        def guarded(reader, name):
            self.assertFalse(name.startswith(self.original_prefix + "/"))
            self.assertNotEqual(name, self.original_canonical_path)
            return read(reader, name)
        with mock.patch.object(checker.Reader, "read", guarded):
            self.assertEqual(checker.check(self.root)["packages"][0]["changed_files"], 1)
        self.enrollment["_predecessors"]["source.py"]["sha256"] = "0" * 64
        self.sync_registry()
        self.reject("Historical source hash or length mismatch")

    def test_owner_track_and_old_runtime_root_mismatches_refuse(self):
        path = self.root / "benchmarks/integrity/current.json"
        original = json.loads(path.read_text())
        for field, value in (("task_id", "NEURAL-OTHER"), ("track", "paper"),
                             ("root", self.original_prefix)):
            with self.subTest(field=field):
                changed = copy.deepcopy(original)
                changed["packages"][0][field] = value
                path.write_bytes(encoded(changed))
                self.reject("root must match")
        path.write_bytes(encoded(original))

    def test_registered_scientific_field_cannot_change_with_only_a_new_current_pin(self):
        path = self.root / "benchmarks/integrity/current.json"
        current = json.loads(path.read_text())
        body = encoded({**self.canonical, "evaluation": {"primary_metric": "changed scientific endpoint"}})
        (self.root / self.canonical_path).write_bytes(body)
        task_pin = current["packages"][0]["registered_task"]
        original_predecessor = copy.deepcopy(task_pin["predecessor"])
        task_pin.update(descriptor(self.canonical_path, body))
        self.assertEqual(task_pin["predecessor"], original_predecessor)
        path.write_bytes(encoded(current))
        self.reject("Registered scientific task definition changed")

    def test_distinct_package_local_contract_is_preserved(self):
        local = encoded({"id": "NEURAL-INVENTED", "scope": "a distinct package-local contract"})
        (self.package / "CANONICAL_SPEC.json").write_bytes(local)
        self.inventory["files"].append(descriptor("CANONICAL_SPEC.json", local))
        self.manifest["canonical_specification"] = descriptor("CANONICAL_SPEC.json", local)
        self.sync_inventory()
        self.assertEqual(checker.check(self.root)["packages"][0]["source_files"], 4)
        old = json.loads((self.root / "benchmarks/integrity/current.json").read_text())
        self.enrollment["_predecessors"] = {row["path"]: row["predecessor"] for row in old["packages"][0]["files"]}
        (self.package / "CANONICAL_SPEC.json").write_bytes(local + b" ")
        self.sync_registry()
        self.reject("Package-local scientific contract changed")

    def test_duplicate_root_with_different_implementation_id_refuses(self):
        second = copy.deepcopy(self.enrollment)
        second["implementation_id"] = "different-identity-same-root"
        self.registry["packages"].append(second)
        self.sync_registry()
        self.reject("Duplicate package root")


class CompleteInventoryTests(unittest.TestCase):
    """Full 102+1 invented metadata; fixed profile never imports factory code."""
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="invented-factory-integrity-")).resolve()
        self.prefix = "benchmarks/paper/PAPER-paper-method-replacement-013/implementations/registered-runtime"
        self.original_prefix = "benchmarks/neuroscience/paper-paper-method-replacement-013"
        self.package = self.root / self.prefix
        self.package.mkdir(parents=True)
        task = "PAPER-paper-method-replacement-013"
        canonical_name = "benchmarks/paper/" + task + "/task.json"
        original_canonical = "benchmarks/manifests/paper/" + task + ".json"
        canonical = encoded({"id": task, "track": "paper"})
        (self.root / canonical_name).parent.mkdir(parents=True, exist_ok=True)
        (self.root / canonical_name).write_bytes(canonical)
        old = []
        for i in range(95):
            name = "old_%03d.py" % i
            body = b'raise RuntimeError("invented source must not execute")\n'
            (self.package / name).write_bytes(body)
            old.append(descriptor(name, body))
        inventory = encoded({"files": old})
        (self.package / "TASK_SOURCE_FREEZE.json").write_bytes(inventory)
        manifest = encoded({"id": task, "canonical_specification": descriptor(original_canonical, canonical),
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
        self.enrollment = {"id": task, "track": "paper", "root": self.prefix,
                           "original_root": self.original_prefix, "inventory": "TASK_SOURCE_FREEZE.json",
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
        write_current(self.root, self.registry)

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

