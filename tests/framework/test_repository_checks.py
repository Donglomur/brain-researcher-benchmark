"""Small ordinary-source fixtures; never run scientific or candidate code."""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import runpy
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
pre_endpoint_selection_fixture = runpy.run_path(
    str(ROOT / "tests/framework/test_catalog.py"))["pre_endpoint_selection_fixture"]
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
    write_json(root / checks.PARALLEL_CONTROL_MANIFEST, {
        "scope": "generated source control metadata only",
        "private_payload_locator": "/private/never-open-this-control.json"})
    for relative in checks.PARALLEL_CONTROL_SOURCES[1:] + checks.WORKFLOW_SYNTAX_SOURCES:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("raise AssertionError('CI sources must only be hashed')\n")
    rows = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            relative = path.relative_to(root).as_posix()
            rows.append({"old": relative, "new": relative})
    write_json(root / checks.RELOCATIONS, {"schema_version": 1, "files": rows})
    return registry


class RepositoryChecksTests(unittest.TestCase):
    @pre_endpoint_selection_fixture
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.profile = patch.object(checks, "CANONICAL_PER_TRACK", 1)
        self.profile.start()
        self.addCleanup(self.profile.stop)
        self.registry = fixture(self.root)

    def viewer_provider_fixture(self):
        members, pins = {}, {}
        for relative in checks.NEURAL_VIEWER_MEMBERS:
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            raw = (b"raise AssertionError('provider source must never execute')\n"
                   if relative.endswith(".py") else
                   b'{"private_payload_locator":"/private/never-open-provider.json"}\n')
            path.write_bytes(raw)
            pins[relative] = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
            members[relative] = "artifact:provider-generated-dependency"
        document = {"schema": "neural-viewer-provider-dependencies/v1", "members": pins}
        write_json(self.root / checks.NEURAL_VIEWER_BINDINGS, document)
        members[checks.NEURAL_VIEWER_BINDINGS] = "artifact:provider-generated-descriptor"
        return document, members, {checks.NEURAL_VIEWER_PROVIDER}

    def test_viewer_provider_exact_sources_enroll_without_execution(self):
        document, members, boundaries = self.viewer_provider_fixture()
        reader = checks.Reader(self.root)
        first = checks.NEURAL_VIEWER_MEMBERS[0]
        prior = {"path": first, **document["members"][first], "mode": "100644"}
        expected = {first: prior}
        with patch.object(reader, "document", wraps=reader.document) as read:
            checks.neural_viewer_provider_pins(reader, boundaries, members, expected)
        read.assert_called_once_with(checks.NEURAL_VIEWER_BINDINGS)
        self.assertEqual(set(expected), set(checks.NEURAL_VIEWER_MEMBERS))
        self.assertIs(expected[first], prior)
        for relative in checks.NEURAL_VIEWER_MEMBERS:
            actual, _ = reader.file(relative)
            self.assertTrue(all(actual[key] == expected[relative][key]
                                for key in ("path", "bytes", "sha256")))

    def test_viewer_provider_stale_source_prevents_inventory_refresh(self):
        _, members, boundaries = self.viewer_provider_fixture()

        def focused_plan(reader):
            expected = {}
            checks.neural_viewer_provider_pins(reader, boundaries, members, expected)
            return {"registry": {}, "relocation_ledger": {}, "counts": {},
                    "canonical_per_track": {}, "expansion_per_track": {}, "artifacts": [],
                    "members": members, "expected_pins": expected}

        # Isolate this edge's real Reader/expected_pins/write path; the existing
        # registry/namespace controls exercise the separate prepare validation.
        with patch.object(checks, "prepare", side_effect=focused_plan):
            checks.check_repository(self.root, write=True)
            inventory = self.root / checks.INVENTORY
            preserved = inventory.read_bytes()
            path = self.root / checks.NEURAL_VIEWER_MEMBERS[-1]
            original = path.read_bytes()
            for changed in (b"!" + original[1:], original + b" "):
                with self.subTest(bytes=len(changed)):
                    path.write_bytes(changed)
                    with self.assertRaisesRegex(ValueError, "Declared source pin mismatch"):
                        checks.check_repository(self.root, write=True)
                    self.assertEqual(inventory.read_bytes(), preserved)

    def test_viewer_provider_conflicting_pin_refuses_without_mutation(self):
        document, members, boundaries = self.viewer_provider_fixture()
        last = checks.NEURAL_VIEWER_MEMBERS[-1]
        expected = {last: {"path": last, **document["members"][last], "sha256": "0" * 64}}
        preserved = copy.deepcopy(expected)
        with self.assertRaisesRegex(ValueError, "Conflicting viewer provider"):
            checks.neural_viewer_provider_pins(checks.Reader(self.root), boundaries, members, expected)
        self.assertEqual(expected, preserved)

    def test_viewer_provider_non_source_and_unowned_targets_refuse(self):
        document, members, boundaries = self.viewer_provider_fixture()
        for substitute in ("/private/unowned-payload.nwb", "benchmarks/shared/unowned/data.bin"):
            changed = copy.deepcopy(document)
            changed["members"][substitute] = changed["members"].pop(checks.NEURAL_VIEWER_MEMBERS[0])
            write_json(self.root / checks.NEURAL_VIEWER_BINDINGS, changed)
            with self.subTest(path=substitute), self.assertRaisesRegex(ValueError, "exactly four source"):
                checks.neural_viewer_provider_pins(checks.Reader(self.root), boundaries, members, {})
        write_json(self.root / checks.NEURAL_VIEWER_BINDINGS, document)
        del members[checks.NEURAL_VIEWER_MEMBERS[0]]
        with self.assertRaisesRegex(ValueError, "not owned source"):
            checks.neural_viewer_provider_pins(checks.Reader(self.root), boundaries, members, {})

    def test_viewer_provider_closed_schema_and_pin_fields_refuse(self):
        document, members, boundaries = self.viewer_provider_fixture()
        changes = []
        changed = copy.deepcopy(document)
        changed["schema"] = "historical-viewer-provider/v0"
        changes.append(changed)
        changed = copy.deepcopy(document)
        changed["private_payload_locator"] = "/private/never-follow.json"
        changes.append(changed)
        for field, value in (("bytes", True), ("bytes", -1), ("bytes", checks.MAX_FILE_BYTES + 1),
                             ("sha256", "A" * 64), ("extra", "not-source-metadata")):
            changed = copy.deepcopy(document)
            changed["members"][checks.NEURAL_VIEWER_MEMBERS[0]][field] = value
            changes.append(changed)
        for index, changed in enumerate(changes):
            write_json(self.root / checks.NEURAL_VIEWER_BINDINGS, changed)
            expected = {}
            with self.subTest(case=index), self.assertRaisesRegex(ValueError, "viewer provider"):
                checks.neural_viewer_provider_pins(checks.Reader(self.root), boundaries, members, expected)
            self.assertEqual(expected, {})

    def test_viewer_provider_registration_is_conditional_and_requires_descriptor(self):
        _, members, boundaries = self.viewer_provider_fixture()
        reader = checks.Reader(self.root)
        expected = {"historical-retained-pin": {"sha256": "a" * 64}}
        preserved = copy.deepcopy(expected)
        with patch.object(reader, "document", side_effect=AssertionError("unregistered read")):
            checks.neural_viewer_provider_pins(reader, set(), members, expected)
        self.assertEqual(expected, preserved)
        del members[checks.NEURAL_VIEWER_BINDINGS]
        with self.assertRaisesRegex(ValueError, "requires its owned source descriptor"):
            checks.neural_viewer_provider_pins(reader, boundaries, members, expected)
        self.assertEqual(expected, preserved)

    def build(self):
        return checks.check_repository(self.root, write=True)

    def check(self):
        return checks.check_repository(self.root)

    def save_registry(self):
        write_json(self.root / checks.REGISTRY, self.registry)

    def revise_paper(self, index=0):
        row = self.registry["tasks"][index]
        directory = row["task_directory"]
        original = (self.root / row["specification"]["path"]).read_bytes()
        previous_path = directory + "/historical/task.pre-improvement.v1.json"
        path = self.root / previous_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(original)
        previous = {**row["specification"], "path": previous_path}
        row["original_specification"] = {**row["specification"], "path": "former-source/" + row["id"] + ".json"}
        contract_path = directory + "/improvement.v1.json"
        contract = {"schema_version": checks.PAPER_REVISION, "task_id": row["id"],
                    "objective": checks.PAPER_OBJECTIVE, "disposition": "source_unresolved",
                    "legacy": {"role": "calibration_only", "original_task": "historical/task.pre-improvement.v1.json"}}
        contract_pin = write_json(self.root / contract_path, contract)
        contract_pin["path"] = contract_path
        row["specification_revision"] = {"version": checks.PAPER_REVISION, "previous_specification": previous,
                                         "improvement_contract": contract_pin}
        row.update(scientific_readiness="source_unresolved", submission_readiness="not_qualified_by_binding")
        document = {"id": row["specification_id"], "track": "paper", "objective": checks.PAPER_OBJECTIVE,
                    "status": "source_unresolved", "evaluation": {"contract": contract_pin,
                    "objective": checks.PAPER_OBJECTIVE, "disposition": "source_unresolved",
                    "calibration": {"historical_task": previous}, "reproduction_role": "calibration_only"}}
        pin = write_json(self.root / row["specification"]["path"], document)
        pin["path"] = row["specification"]["path"]
        row["specification"] = pin
        self.save_registry()
        return row

    def test_all_artifacts_and_task_specs_are_hashed_without_running_source(self):
        result = self.build()
        self.assertEqual(result["artifacts"], 2)
        self.assertEqual(result["artifact_files"], 2)
        self.assertEqual(result["current_binding_files"], 2)
        self.assertEqual(result["source_files"], 12)
        self.assertFalse(result["scientific_qualification"])
        self.assertEqual(self.check()["source_check"], "passed")
        runtime = self.root / ".neurobench"
        runtime.mkdir()
        (runtime / "not-source.bin").write_bytes(b"Local runtime output is not source.")
        self.assertEqual(self.check()["source_check"], "passed")

    def revise_neural095(self):
        row = self.registry["tasks"][2]
        old_directory = row["task_directory"]
        home = "benchmarks/neural/NEURAL-095"
        (self.root / old_directory).rename(self.root / home)
        relocations = json.loads((self.root / checks.RELOCATIONS).read_bytes())
        for item in relocations["files"]:
            if item["new"].startswith(old_directory + "/"):
                item["new"] = home + item["new"][len(old_directory):]
        write_json(self.root / checks.RELOCATIONS, relocations)
        row.update(id="NEURAL-095", task_directory=home, specification_id="NEURAL-095")
        old = json.loads((self.root / home / "task.json").read_bytes())
        old["id"] = "NEURAL-095"
        row["specification"] = write_json(self.root / home / "task.json", old)
        row["specification"]["path"] = home + "/task.json"
        self.registry["implementations"][1]["related_task_ids"] = ["NEURAL-095"]
        for neural in self.registry["tasks"][2:]:
            neural["original_specification"] = {**neural["specification"], "path": "former/" + neural["id"] + ".json"}
        snapshot = write_json(self.root / checks.NEURAL_SNAPSHOT, self.registry)
        snapshot["path"] = checks.NEURAL_SNAPSHOT
        self.registry["neural_understanding"] = {"schema_version": checks.NEURAL_REVISION,
            "objective": checks.NEURAL_OBJECTIVE, "coverage_required": True,
            "registered_count": 2, "pre_understanding_registry": snapshot}
        for neural in self.registry["tasks"][2:]:
            directory = neural["task_directory"]
            original = (self.root / neural["specification"]["path"]).read_bytes()
            history = directory + "/" + checks.NEURAL_HISTORY
            (self.root / history).parent.mkdir(parents=True)
            (self.root / history).write_bytes(original)
            prior = {**neural["specification"], "path": history}
            document = {"schema_version": checks.NEURAL_REVISION, "task_id": neural["id"],
                "objective": checks.NEURAL_OBJECTIVE, "evidence": []}
            contract_path = directory + "/understanding.v1.json"
            contract = write_json(self.root / contract_path, document)
            contract["path"] = contract_path
            neural["specification_revision"] = {"version": checks.NEURAL_REVISION,
                "previous_specification": prior, "understanding_contract": contract}
            neural["submission_readiness"] = "not_qualified_by_binding"
            current = {"id": neural["id"], "track": "neural", "objective": checks.NEURAL_OBJECTIVE,
                "evaluation": {"neural_understanding": {"schema_version": checks.NEURAL_REVISION,
                    "objective": checks.NEURAL_OBJECTIVE, "contract_path": "understanding.v1.json",
                    "contract_sha256": contract["sha256"], "original_definition_path": checks.NEURAL_HISTORY,
                    "original_definition_sha256": prior["sha256"]}}}
            pin = write_json(self.root / directory / "task.json", current)
            pin["path"] = directory + "/task.json"
            neural["specification"] = pin
        self.route_row = row
        self.route_contract = json.loads((self.root / home / "understanding.v1.json").read_bytes())
        self.route_task = json.loads((self.root / home / "task.json").read_bytes())
        for name in ("current-operator-routes.v1.json", "operator.py", "test_operator.py"):
            (self.root / home / name).write_bytes(b"Source fixture only; never execute.\n")
        self.route_task["operator_route"] = {"path": home + "/current-operator-routes.v1.json",
            "sha256": hashlib.sha256((self.root / home / "current-operator-routes.v1.json").read_bytes()).hexdigest(),
            "launcher": home + "/operator.py", "selection": "explicit_opt_in_source_route_only", "execution_authority": False}
        for identifier, name in (("dmfc095-current-route-v1", "current-operator-routes.v1.json"),
                                 ("dmfc095-current-launcher-v1", "operator.py")):
            self.route_contract["evidence"].append({"id": identifier, "kind": "local_source", "path": home + "/" + name,
                "sha256": hashlib.sha256((self.root / home / name).read_bytes()).hexdigest()})
        self.save_neural095()
        return home

    def save_neural095(self):
        home = self.route_row["task_directory"]
        contract = write_json(self.root / home / "understanding.v1.json", self.route_contract)
        contract["path"] = home + "/understanding.v1.json"
        self.route_row["specification_revision"]["understanding_contract"] = contract
        self.route_task["evaluation"]["neural_understanding"]["contract_sha256"] = contract["sha256"]
        current = write_json(self.root / home / "task.json", self.route_task)
        current["path"] = home + "/task.json"
        self.route_row["specification"] = current
        self.save_registry()

    def test_neural095_current_sources_are_owned_and_control_drift_refuses(self):
        home = self.revise_neural095()
        self.build()
        inventory = json.loads((self.root / checks.INVENTORY).read_bytes())
        for name in ("current-operator-routes.v1.json", "operator.py", "test_operator.py"):
            record = next(item for item in inventory["files"] if item["path"] == home + "/" + name)
            self.assertEqual(record["owner"], "task:NEURAL-095")
        self.assertEqual(self.check()["source_check"], "passed")
        (self.root / home / "test_operator.py").write_bytes(b"Changed control source\n")
        with self.assertRaisesRegex(ValueError, "Source content or mode drift"):
            self.check()

    def test_neural095_route_evidence_and_fixed_paths_are_required(self):
        self.revise_neural095()
        task, contract = copy.deepcopy(self.route_task), copy.deepcopy(self.route_contract)
        variants = [
            lambda: self.route_task["operator_route"].update(execution_authority=True),
            lambda: self.route_task["operator_route"].update(launcher="benchmarks/neural/NEURAL-095/other.py"),
            lambda: self.route_task["operator_route"].update(extra_allowance=True),
            lambda: self.route_task["operator_route"].update(sha256="0" * 64),
            lambda: self.route_contract["evidence"][0].update(kind="local_review"),
            lambda: self.route_contract["evidence"][1].update(sha256="0" * 64),
            lambda: self.route_contract["evidence"].append(copy.deepcopy(self.route_contract["evidence"][0])),
        ]
        for index, change in enumerate(variants):
            self.route_task, self.route_contract = copy.deepcopy(task), copy.deepcopy(contract)
            change()
            self.save_neural095()
            with self.subTest(index=index), self.assertRaisesRegex(ValueError, "neural operator route|Neural operator route"):
                self.build()

    def test_neural095_root_admission_remains_closed_and_rejects_links(self):
        home = self.revise_neural095()
        extra = self.root / home / "extra.py"
        extra.write_bytes(b"unowned\n")
        with self.assertRaisesRegex(ValueError, "Orphan source file"):
            self.build()
        extra.unlink()
        for name in ("current-operator-routes.v1.json", "operator.py", "test_operator.py"):
            path = self.root / home / name
            raw = path.read_bytes()
            path.unlink()
            target = self.root / "link-target"
            target.write_bytes(raw)
            path.symlink_to(target)
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "ordinary single-link file"):
                self.build()
            path.unlink()
            path.write_bytes(raw)

    def test_parallel_control_sources_are_explicitly_owned_and_content_bound(self):
        self.build()
        inventory = json.loads((self.root / checks.INVENTORY).read_text())
        records = {item["path"]: item for item in inventory["files"]}
        for relative in checks.PARALLEL_CONTROL_SOURCES:
            with self.subTest(path=relative):
                self.assertEqual(records[relative]["owner"], "generated-source-controls")
                path = self.root / relative
                original = path.read_bytes()
                path.write_bytes(original + b" ")
                with self.assertRaisesRegex(ValueError, "Source content or mode drift"):
                    self.check()
                path.write_bytes(original)
        self.assertEqual(self.check()["source_check"], "passed")

    def test_parallel_control_namespace_remains_closed_and_members_are_ordinary(self):
        self.build()
        unexpected = self.root / "benchmarks/integrity/parallel-source-controls.v2.json"
        unexpected.write_text("{}")
        with self.assertRaisesRegex(ValueError, "Orphan source file"):
            self.check()
        unexpected.unlink()
        target = self.root / "alias-target.py"
        target.write_text("source alias must be refused")
        for relative in checks.PARALLEL_CONTROL_SOURCES:
            with self.subTest(path=relative):
                path = self.root / relative
                original = path.read_bytes()
                path.unlink()
                with self.assertRaisesRegex(ValueError, "Missing source path"):
                    self.check()
                path.symlink_to(target)
                with self.assertRaisesRegex(ValueError, "ordinary single-link file"):
                    self.check()
                path.unlink()
                path.write_bytes(original)
        self.assertEqual(self.check()["source_check"], "passed")

    def test_exp003_control_group_is_exactly_owned_and_content_bound(self):
        baseline = self.build()
        for relative in checks.EXP003_CONTROL_SOURCES:
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("raise AssertionError('EXP controls must only be hashed')\n")
        result = self.build()
        self.assertEqual(result["source_files"], baseline["source_files"] + 3)
        self.assertEqual(result["artifacts"], baseline["artifacts"])
        self.assertFalse(result["scientific_qualification"])
        records = {item["path"]: item for item in json.loads(
            (self.root / checks.INVENTORY).read_text())["files"]}
        for relative in checks.EXP003_CONTROL_SOURCES:
            with self.subTest(path=relative):
                path = self.root / relative
                original = path.read_bytes()
                self.assertEqual(records[relative]["owner"], "generated-exp003-r-controls")
                self.assertEqual(records[relative]["bytes"], len(original))
                self.assertEqual(records[relative]["sha256"], hashlib.sha256(original).hexdigest())
                path.write_bytes(original + b" ")
                with self.assertRaisesRegex(ValueError, "Source content or mode drift"):
                    self.check()
                path.write_bytes(original)
        self.assertEqual(self.check()["source_check"], "passed")

    def test_exp003_control_group_refuses_partial_alias_and_unknown_metadata(self):
        workflow = self.root / checks.EXP003_CONTROL_WORKFLOW
        workflow.parent.mkdir(parents=True, exist_ok=True)
        workflow.write_text("name: fixture\n")
        with self.assertRaisesRegex(ValueError, "Missing source path"):
            self.build()
        workflow.unlink()
        for relative in checks.EXP003_CONTROL_SOURCES:
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("source fixture\n")
        self.build()
        target = self.root / "alias-target.py"
        target.write_text("source alias must be refused\n")
        for relative in checks.EXP003_CONTROL_SOURCES:
            with self.subTest(path=relative):
                path = self.root / relative
                original = path.read_bytes()
                path.unlink()
                with self.assertRaisesRegex(ValueError, "Missing source path"):
                    self.build()
                path.symlink_to(target)
                with self.assertRaisesRegex(ValueError, "ordinary single-link file"):
                    self.build()
                path.unlink()
                path.write_bytes(original)
        unexpected = self.root / "benchmarks/integrity/exp003-generated-r.environment.v2.json"
        unexpected.write_text("{}")
        with self.assertRaisesRegex(ValueError, "Orphan source file"):
            self.build()
        unexpected.unlink()
        self.assertEqual(self.check()["source_check"], "passed")

    def test_versioned_paper_metadata_is_owned_and_preserves_historical_bytes(self):
        row = self.revise_paper()
        result = self.build()
        self.assertEqual(result["source_files"], 14)
        self.assertFalse(result["scientific_qualification"])
        self.assertEqual(self.check()["source_check"], "passed")
        inventory = json.loads((self.root / checks.INVENTORY).read_text())
        records = {item["path"]: item for item in inventory["files"]}
        for key in ("previous_specification", "improvement_contract"):
            pin = row["specification_revision"][key]
            self.assertEqual(records[pin["path"]]["owner"], "task:" + row["id"])
            self.assertEqual(records[pin["path"]]["sha256"], pin["sha256"])

    def test_forged_paper_history_cannot_be_enrolled_with_a_new_pin(self):
        row = self.revise_paper()
        old = row["specification_revision"]["previous_specification"]
        forged = write_json(self.root / old["path"], {"id": row["id"], "track": "paper", "forged": True})
        forged["path"] = old["path"]
        row["specification_revision"]["previous_specification"] = forged
        self.save_registry()
        with self.assertRaisesRegex(ValueError, "does not preserve its original"):
            self.build()

    def test_paper_revision_rejects_rehashed_current_objective_change(self):
        row = self.revise_paper()
        path = row["specification"]["path"]
        document = json.loads((self.root / path).read_text())
        document["objective"] = "reproduction_is_success"
        row["specification"] = write_json(self.root / path, document)
        row["specification"]["path"] = path
        self.save_registry()
        with self.assertRaisesRegex(ValueError, "not bound to its improvement"):
            self.build()

    def test_paper_revision_requires_exact_version_paths_and_closed_pins(self):
        row = self.revise_paper()
        original = copy.deepcopy(row["specification_revision"])
        for change, error in (
                (lambda revision: revision.update(version="paper-improvement/v2"), "Unsupported task"),
                (lambda revision: revision.update(authorized=True), "Unsupported task"),
                (lambda revision: revision["previous_specification"].update(path="elsewhere.json"), "exact location"),
                (lambda revision: revision["improvement_contract"].update(bytes=True), "Invalid Paper"),
                (lambda revision: revision["improvement_contract"].update(allow_changes=True), "Closed Paper")):
            row["specification_revision"] = copy.deepcopy(original)
            change(row["specification_revision"])
            self.save_registry()
            with self.subTest(error=error), self.assertRaisesRegex(ValueError, error):
                self.build()

    def test_rehashed_paper_evaluation_requires_current_objective_disposition_and_history(self):
        row = self.revise_paper()
        path = row["specification"]["path"]
        original = json.loads((self.root / path).read_text())
        for mutation in (
                lambda evaluation: evaluation.update(objective="reproduce_source_paper"),
                lambda evaluation: evaluation.update(disposition="improvement_ready"),
                lambda evaluation: evaluation["calibration"].update(historical_task=row["original_specification"]),
                lambda evaluation: evaluation.update(calibration=None)):
            document = copy.deepcopy(original)
            mutation(document["evaluation"])
            row["specification"] = write_json(self.root / path, document)
            row["specification"]["path"] = path
            self.save_registry()
            with self.subTest(evaluation=document["evaluation"]), self.assertRaisesRegex(
                    ValueError, "not bound to its improvement"):
                self.build()

    def test_paper_contract_and_history_drift_are_rejected_before_inventory_write(self):
        row = self.revise_paper()
        for key in ("previous_specification", "improvement_contract"):
            path = self.root / row["specification_revision"][key]["path"]
            original = path.read_bytes()
            path.write_bytes(original + b" ")
            with self.subTest(member=key), self.assertRaisesRegex(ValueError, "pin mismatch"):
                self.build()
            path.write_bytes(original)
        contract_pin = row["specification_revision"]["improvement_contract"]
        path = contract_pin["path"]
        contract = json.loads((self.root / path).read_text())
        for disposition in ("qualified", [], {}):
            contract["disposition"] = disposition
            new_pin = write_json(self.root / path, contract)
            new_pin["path"] = path
            row["specification_revision"]["improvement_contract"] = new_pin
            self.save_registry()
            with self.subTest(disposition=disposition), self.assertRaisesRegex(
                    ValueError, "identity or disposition mismatch"):
                self.build()

    def test_paper_revisions_cannot_relax_neural_readiness_or_admit_neural_history(self):
        paper = self.revise_paper()
        neural = self.registry["tasks"][2]
        neural["specification_revision"] = copy.deepcopy(paper["specification_revision"])
        self.save_registry()
        with self.assertRaisesRegex(ValueError, "Unsupported task specification revision"):
            self.build()
        del neural["specification_revision"]
        neural["scientific_readiness"] = "source_unresolved"
        self.save_registry()
        with self.assertRaisesRegex(ValueError, "cannot grant scientific qualification"):
            self.build()
        neural["scientific_readiness"] = "unknown"
        self.save_registry()
        self.build()
        self.assertEqual(self.check()["source_check"], "passed")
        history = self.root / neural["task_directory"] / "historical/task.pre-improvement.v1.json"
        history.parent.mkdir()
        history.write_text("{}\n")
        with self.assertRaisesRegex(ValueError, "Orphan source directory"):
            self.build()

    def test_pre_improvement_registry_snapshot_is_pinned_and_full_coverage_required(self):
        snapshot_path = "docs/provenance/registrations/paper-pre-improvement-v1.json"
        pin = write_json(self.root / snapshot_path, copy.deepcopy(self.registry))
        pin["path"] = snapshot_path
        self.revise_paper(0)
        self.registry["paper_improvement"] = {"schema_version": checks.PAPER_REVISION,
            "objective": checks.PAPER_OBJECTIVE, "coverage_required": True, "registered_count": 2,
            "pre_improvement_registry": pin}
        self.save_registry()
        with self.assertRaisesRegex(ValueError, "requires every paper revision"):
            self.build()
        self.revise_paper(1)
        self.assertEqual(self.build()["source_files"], 17)
        self.assertEqual(self.check()["source_check"], "passed")
        inventory = json.loads((self.root / checks.INVENTORY).read_text())
        self.assertIn(snapshot_path, {item["path"] for item in inventory["files"]})
        path = self.root / snapshot_path
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaisesRegex(ValueError, "Pre-improvement registry pin mismatch"):
            self.build()

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

    def test_source_count_limit_is_inclusive_and_overflow_preserves_inventory(self):
        count = self.build()["source_files"]
        inventory = (self.root / checks.INVENTORY).read_bytes()
        artifacts = self.registry["implementations"]
        artifact_count = len(checks.artifact_members(self.root, artifacts))
        with patch.object(checks, "MAX_FILES", count):
            self.assertEqual(self.check()["source_files"], count)
        with patch.object(checks, "MAX_FILES", artifact_count):
            self.assertEqual(len(checks.artifact_members(self.root, artifacts)), artifact_count)

        extra = self.root / artifacts[0]["path"] / "extra.py"
        extra.write_text("raise AssertionError('This source must never execute')\n")
        with patch.object(checks, "MAX_FILES", count):
            with self.assertRaisesRegex(ValueError, "Source file count limit exceeded"):
                self.build()
        self.assertEqual((self.root / checks.INVENTORY).read_bytes(), inventory)
        with patch.object(checks, "MAX_FILES", artifact_count):
            with self.assertRaisesRegex(ValueError, "Source file count limit exceeded"):
                checks.artifact_members(self.root, artifacts)
        self.assertEqual((self.root / checks.INVENTORY).read_bytes(), inventory)

    def test_cumulative_reader_limit_is_inclusive_and_cache_preserves_budget(self):
        for name, raw in (("first.py", b"abc"), ("second.py", b"de"), ("third.py", b"f")):
            (self.root / name).write_bytes(raw)
        with patch.object(checks, "MAX_READ_BYTES", 5):
            reader = checks.Reader(self.root)
            first, _ = reader.file("first.py")
            second, _ = reader.file("second.py")
            self.assertEqual((first["bytes"], second["bytes"], reader.bytes_read), (3, 2, 5))
            cached, _ = reader.file("first.py")
            self.assertEqual(cached, first)
            self.assertEqual(reader.bytes_read, 5)
            with self.assertRaisesRegex(ValueError, "Source read budget exceeded"):
                reader.file("third.py")
            self.assertEqual(reader.bytes_read, 5)

    def test_member_limit_remains_independent_of_cumulative_budget(self):
        (self.root / "member.py").write_bytes(b"abc")
        with patch.object(checks, "MAX_READ_BYTES", 5), patch.object(checks, "MAX_FILE_BYTES", 2):
            reader = checks.Reader(self.root)
            with self.assertRaisesRegex(ValueError, "Source member exceeds byte limit"):
                reader.file("member.py")
            self.assertEqual(reader.bytes_read, 0)

    def test_byte_limits_and_non_source_payloads_refuse(self):
        with patch.object(checks, "MAX_READ_BYTES", 1), self.assertRaisesRegex(ValueError, "budget"):
            self.build()
        path = self.root / self.registry["implementations"][0]["path"] / "raw-array.npy"
        path.write_bytes(b"Not a source file")
        with self.assertRaisesRegex(ValueError, "Non-source member type"):
            self.build()

    def test_owned_source_patch_is_hashed_without_application(self):
        relative = self.registry["implementations"][0]["path"] + "/source.patch"
        raw = b"--- a/source.py\n+++ b/source.py\n@@ -1 +1 @@\n-old\n+new\n"
        (self.root / relative).write_bytes(raw)
        self.build()
        inventory = json.loads((self.root / checks.INVENTORY).read_text())
        record = next(item for item in inventory["files"] if item["path"] == relative)
        self.assertEqual(record["sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(record["bytes"], len(raw))
        self.assertEqual(self.check()["source_check"], "passed")
        (self.root / relative).write_bytes(raw.replace(b"+new", b"+changed"))
        with self.assertRaisesRegex(ValueError, "Source content or mode drift"):
            self.check()


if __name__ == "__main__":
    unittest.main()
