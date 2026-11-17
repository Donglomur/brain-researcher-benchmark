"""Neural metadata lineage controls; fixtures contain no scientific observations."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "neural_repository_fixture", ROOT / "tests/framework/test_repository_checks.py")
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
checks = fixture.checks


class NeuralRepositoryLineageTests(unittest.TestCase):
    @fixture.pre_endpoint_selection_fixture
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        profile = patch.object(checks, "CANONICAL_PER_TRACK", 1)
        profile.start()
        self.addCleanup(profile.stop)
        self.registry = fixture.fixture(self.root)
        for row in self.registry["tasks"]:
            row["original_specification"] = {
                **row["specification"], "path": "former-source/" + row["id"] + ".json"}
        self.save_registry()
        self.original_registry = (self.root / checks.REGISTRY).read_bytes()
        self.snapshot_pin = self.put(checks.NEURAL_SNAPSHOT, self.registry)
        self.registry["neural_understanding"] = {
            "schema_version": checks.NEURAL_REVISION, "objective": checks.NEURAL_OBJECTIVE,
            "coverage_required": True, "registered_count": 2,
            "pre_understanding_registry": self.snapshot_pin}
        self.rows = [row for row in self.registry["tasks"] if row["track"] == "neural"]
        for row in self.rows:
            self.revise(row)
        self.save_registry()

    def put(self, relative, value):
        pin = fixture.write_json(self.root / relative, value)
        pin["path"] = relative
        return pin

    def save_registry(self):
        self.put(checks.REGISTRY, self.registry)

    def revise(self, row):
        directory = row["task_directory"]
        original = (self.root / row["specification"]["path"]).read_bytes()
        history = directory + "/" + checks.NEURAL_HISTORY
        path = self.root / history
        path.parent.mkdir(parents=True)
        path.write_bytes(original)
        previous = {"path": history, "bytes": len(original), "sha256": hashlib.sha256(original).hexdigest()}
        contract = self.put(directory + "/understanding.v1.json", {
            "schema_version": checks.NEURAL_REVISION, "objective": checks.NEURAL_OBJECTIVE,
            "task_id": row["id"], "private_locator": "/never-open-this-private-data.json"})
        row["specification_revision"] = {
            "version": checks.NEURAL_REVISION, "previous_specification": previous,
            "understanding_contract": contract}
        row.update(scientific_readiness="unknown", submission_readiness="not_qualified_by_binding")
        document = json.loads(original)
        document.update(objective=checks.NEURAL_OBJECTIVE, evaluation={"neural_understanding": {
            "schema_version": checks.NEURAL_REVISION, "objective": checks.NEURAL_OBJECTIVE,
            "contract_path": "understanding.v1.json", "contract_sha256": contract["sha256"],
            "original_definition_path": checks.NEURAL_HISTORY,
            "original_definition_sha256": previous["sha256"]}})
        row["specification"] = self.put(row["specification"]["path"], document)

    def build(self):
        return checks.check_repository(self.root, write=True)

    def mutate_current(self, mutation):
        row = self.rows[0]
        path = row["specification"]["path"]
        document = json.loads((self.root / path).read_bytes())
        mutation(document)
        row["specification"] = self.put(path, document)
        self.save_registry()

    def test_neural_revision_members_and_original_registry_are_owned_without_execution(self):
        result = self.build()
        self.assertFalse(result["scientific_execution"])
        self.assertFalse(result["scientific_qualification"])
        self.assertEqual(checks.check_repository(self.root)["source_check"], "passed")
        self.assertEqual((self.root / checks.NEURAL_SNAPSHOT).read_bytes(), self.original_registry)
        records = {row["path"]: row for row in json.loads((self.root / checks.INVENTORY).read_bytes())["files"]}
        maintenance_members = {
            "benchmarks/integrity/parallel-source-controls.v1.json",
            "scripts/maintenance/run_parallel_source_controls.py",
            "tests/maintenance/test_parallel_source_controls.py",
        }
        expected_members = maintenance_members | {
            "benchmarks/paper/PAPER-001/task.json",
            "benchmarks/paper/PAPER-002/task.json",
            "benchmarks/neural/NEURAL-001/task.json",
            "benchmarks/neural/NEURAL-002/task.json",
            "benchmarks/paper/PAPER-001/implementations/example/example.py",
            "benchmarks/shared/diagnostic/example/example.py",
            "benchmarks/integrity/current.json",
            "benchmarks/integrity/current-closures/example/binding.json",
            "docs/provenance/registrations/neural-pre-understanding-v1.json",
            "benchmarks/neural/NEURAL-001/historical/task.pre-understanding.v1.json",
            "benchmarks/neural/NEURAL-001/understanding.v1.json",
            "benchmarks/neural/NEURAL-002/historical/task.pre-understanding.v1.json",
            "benchmarks/neural/NEURAL-002/understanding.v1.json",
        }
        self.assertEqual(set(records), expected_members)
        self.assertEqual(result["source_files"], len(expected_members))
        # The shared fixture's maintenance sources must be read from this temporary root.
        for path in maintenance_members:
            raw = (self.root / path).read_bytes()
            self.assertEqual(records[path]["owner"], "generated-source-controls")
            self.assertEqual(records[path]["bytes"], len(raw))
            self.assertEqual(records[path]["sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(records[checks.NEURAL_SNAPSHOT]["owner"], "registration-provenance")
        for row in self.rows:
            for key in ("previous_specification", "understanding_contract"):
                pin = row["specification_revision"][key]
                self.assertEqual(records[pin["path"]]["owner"], "task:" + row["id"])
                self.assertEqual(records[pin["path"]]["sha256"], pin["sha256"])

    def test_history_or_contract_tampering_is_rejected_before_inventory_write(self):
        for key in ("previous_specification", "understanding_contract"):
            path = self.root / self.rows[0]["specification_revision"][key]["path"]
            original = path.read_bytes()
            path.write_bytes(original + b" ")
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "pin mismatch"):
                self.build()
            self.assertFalse((self.root / checks.INVENTORY).exists())
            path.write_bytes(original)

    def test_rehashing_history_and_current_original_cannot_replace_snapshot_identity(self):
        row = self.rows[0]
        previous = row["specification_revision"]["previous_specification"]
        forged = self.put(previous["path"], {"id": row["id"], "track": "neural", "forged": True})
        row["specification_revision"]["previous_specification"] = forged
        row["original_specification"].update(bytes=forged["bytes"], sha256=forged["sha256"])
        self.mutate_current(lambda doc: doc["evaluation"]["neural_understanding"].update(
            original_definition_sha256=forged["sha256"]))
        with self.assertRaisesRegex(ValueError, "lineage differs from the original registry"):
            self.build()

    def test_rehashed_current_binding_cannot_change_access_contract_or_history(self):
        row = self.rows[0]
        path = row["specification"]["path"]
        original = json.loads((self.root / path).read_bytes())
        for mutation in (
                lambda doc: doc.update(objective="programme_performance_proves_direct_interpretation"),
                lambda doc: doc["evaluation"]["neural_understanding"].update(contract_sha256="0" * 64),
                lambda doc: doc["evaluation"]["neural_understanding"].update(original_definition_sha256="0" * 64),
                lambda doc: doc["evaluation"]["neural_understanding"].update(contract_path="../other.json"),
                lambda doc: doc["evaluation"]["neural_understanding"].update(allow_changes=True)):
            document = copy.deepcopy(original)
            mutation(document)
            row["specification"] = self.put(path, document)
            self.save_registry()
            with self.subTest(document=document), self.assertRaisesRegex(ValueError, "not bound to its understanding"):
                self.build()

    def test_revision_rejects_wrong_track_version_and_open_descriptor(self):
        row = self.rows[0]
        original = copy.deepcopy(row["specification_revision"])
        for mutation, message in (
                (lambda value: value.update(version=checks.PAPER_REVISION), "Unsupported task"),
                (lambda value: value.update(version="neural-understanding/v2"), "Unsupported task"),
                (lambda value: value.update(allow_changes=True), "Unsupported task"),
                (lambda value: value["understanding_contract"].update(path="elsewhere.json"), "exact location"),
                (lambda value: value["understanding_contract"].update(bytes=True), "Invalid Neural"),
                (lambda value: value["previous_specification"].update(allow_changes=True), "Closed Historical")):
            row["specification_revision"] = copy.deepcopy(original)
            mutation(row["specification_revision"])
            self.save_registry()
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                self.build()

    def test_contract_identity_stays_bound_even_after_rehash(self):
        row = self.rows[0]
        path = row["specification_revision"]["understanding_contract"]["path"]
        contract = json.loads((self.root / path).read_bytes())
        contract["task_id"] = self.rows[1]["id"]
        row["specification_revision"]["understanding_contract"] = self.put(path, contract)
        self.mutate_current(lambda doc: doc["evaluation"]["neural_understanding"].update(
            contract_sha256=row["specification_revision"]["understanding_contract"]["sha256"]))
        with self.assertRaisesRegex(ValueError, "contract identity mismatch"):
            self.build()

    def test_revision_requires_original_snapshot_and_every_neural_binding(self):
        metadata = self.registry.pop("neural_understanding")
        self.save_registry()
        with self.assertRaisesRegex(ValueError, "requires its original registry snapshot"):
            self.build()
        self.registry["neural_understanding"] = metadata
        row = self.rows[1]
        del row["specification_revision"]
        row.update(scientific_readiness="unknown", submission_readiness="unknown")
        self.save_registry()
        with self.assertRaisesRegex(ValueError, "requires every neural revision"):
            self.build()

    def test_snapshot_roster_and_pinned_bytes_cannot_drift(self):
        path = self.root / checks.NEURAL_SNAPSHOT
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaisesRegex(ValueError, "Pre-understanding registry pin mismatch"):
            self.build()
        for replacement in (False, True):
            historical = json.loads(self.original_registry)
            if replacement:
                historical["tasks"][-1]["id"] = "NEURAL-REPLACEMENT"
            else:
                historical["tasks"] = [row for row in historical["tasks"] if row["id"] != self.rows[1]["id"]]
            self.registry["neural_understanding"]["pre_understanding_registry"] = self.put(checks.NEURAL_SNAPSHOT, historical)
            self.save_registry()
            with self.subTest(replacement=replacement), self.assertRaisesRegex(ValueError, "original registration roster"):
                self.build()

    def test_rehashed_snapshot_cannot_change_original_registration_fields(self):
        historical = json.loads(self.original_registry)
        previous = next(row for row in historical["tasks"] if row["id"] == self.rows[0]["id"])
        previous["original_specification"]["path"] = "forged-origin/NEURAL-001.json"
        self.registry["neural_understanding"]["pre_understanding_registry"] = self.put(checks.NEURAL_SNAPSHOT, historical)
        self.save_registry()
        with self.assertRaisesRegex(ValueError, "lineage differs from the original registry"):
            self.build()

    def test_binding_cannot_promote_readiness_and_unrelated_source_remains_checked(self):
        self.build()
        row = self.rows[0]
        row["scientific_readiness"] = "qualified"
        self.save_registry()
        with self.assertRaisesRegex(ValueError, "cannot grant scientific qualification"):
            self.build()
        row["scientific_readiness"] = "unknown"
        self.save_registry()
        self.build()
        source = self.root / self.registry["implementations"][0]["path"] / "example.py"
        source.write_text("changed source\n")
        with self.assertRaisesRegex(ValueError, "Source content or mode drift"):
            checks.check_repository(self.root)


if __name__ == "__main__":
    unittest.main()
