"""Task-revision maintenance controls; invented source, no scientific execution."""
import copy
import json
from pathlib import Path
import runpy
import shutil
import unittest
from unittest import mock


ROOT = Path(__file__).absolute().parents[2]
fixtures = runpy.run_path(str(ROOT / "tests/framework/test_source_integrity.py"))
refresh = fixtures["refresh"]
encoded = fixtures["encoded"]
descriptor = fixtures["descriptor"]


class TaskIntegrityRefreshTests(unittest.TestCase):
    def setUp(self):
        fixture = fixtures["SourceIntegrityTests"]("test_valid_bundle_is_checked_without_execution")
        fixture.setUp()
        self.root = fixture.root
        self.addCleanup(shutil.rmtree, self.root)
        self.task_id = "NEURAL-INVENTED"
        self.home = "benchmarks/neural/" + self.task_id
        self.task_path = self.home + "/task.json"
        self.current_path = self.root / refresh.CURRENT
        self.original_current = json.loads(self.current_path.read_text())
        self.old_task = (self.root / self.task_path).read_bytes()
        self.history_path = self.home + "/historical/task.pre-understanding.v1.json"
        history = self.root / self.history_path
        history.parent.mkdir()
        history.write_bytes(self.old_task)
        self.contract_path = self.home + "/understanding.v1.json"
        self.objective = "infer_neural_or_behavioral_targets_from_permitted_observations"
        contract = {"schema_version": "neural-understanding/v1", "task_id": self.task_id,
                    "objective": self.objective}
        contract_body = encoded(contract)
        (self.root / self.contract_path).write_bytes(contract_body)
        self.revision = {"version": "neural-understanding/v1",
                         "previous_specification": descriptor(self.history_path, self.old_task),
                         "understanding_contract": descriptor(self.contract_path, contract_body)}
        self.task = {"id": self.task_id, "track": "neural", "objective": self.objective,
                     "evaluation": {"neural_understanding": {
                         "schema_version": "neural-understanding/v1", "objective": self.objective,
                         "contract_path": "understanding.v1.json",
                         "contract_sha256": self.revision["understanding_contract"]["sha256"],
                         "original_definition_path": "historical/task.pre-understanding.v1.json",
                         "original_definition_sha256": self.revision["previous_specification"]["sha256"]}}}
        self.registered = {
            "id": self.task_id, "track": "neural", "task_directory": self.home,
            "original_specification": descriptor("benchmarks/manifests/neural/" + self.task_id + ".json",
                                                  self.old_task),
            "specification_revision": self.revision,
        }
        self.save_task()
        self.closure_name = refresh.CLOSURES + "/invented/SOURCE.json"
        self.closure_path = self.root / self.closure_name
        self.closure_path.parent.mkdir(parents=True)
        self.closure = {"schema": "invented", "files": [descriptor(self.task_path, self.old_task)]}
        self.closure_path.write_bytes(encoded(self.closure))

    def save_task(self):
        body = encoded(self.task)
        (self.root / self.task_path).write_bytes(body)
        self.registered["specification"] = descriptor(self.task_path, body)
        (self.root / "benchmarks/registry.json").write_bytes(encoded({
            "schema_version": 1, "kind": "neuroscience_benchmark_registry", "tasks": [self.registered]}))

    def plan(self):
        return refresh.build_outputs(self.root, update_workflows=False)

    def apply_metadata(self):
        outputs, changes = self.plan()
        for name, body in outputs.items():
            (self.root / name).write_bytes(body)
        return outputs, changes

    def reject(self, message):
        with self.assertRaisesRegex(refresh.integrity.InvalidSource, message):
            self.plan()

    def test_neural_metadata_retains_originals_and_is_idempotent(self):
        before = self.closure_path.read_bytes()
        outputs, changes = self.apply_metadata()
        self.assertEqual(set(outputs), {refresh.CURRENT, self.closure_name})
        result = json.loads(outputs[self.closure_name])
        self.assertEqual(result["files"], [self.revision["previous_specification"]])
        lineage = result["neural_specification_revisions"][0]
        self.assertEqual(lineage, {
            "task_id": self.task_id, "version": "neural-understanding/v1",
            "role": "historical_source_evidence_only",
            "historical_specification": self.revision["previous_specification"],
            "current_specification": self.registered["specification"],
            "understanding_contract": self.revision["understanding_contract"],
        })
        updated = json.loads(outputs[refresh.CURRENT])
        original = self.original_current["packages"][0]
        self.assertEqual(updated["packages"][0]["files"], original["files"])
        self.assertEqual(updated["packages"][0]["historical_inventory"], original["historical_inventory"])
        self.assertEqual(updated["packages"][0]["registered_task"]["predecessor"],
                         original["registered_task"]["predecessor"])
        self.assertEqual((self.root / self.history_path).read_bytes(), self.old_task)
        self.assertEqual(changes[0]["previous"], descriptor(self.closure_name, before))
        self.assertEqual(changes[0]["current"], descriptor(self.closure_name, outputs[self.closure_name]))
        self.assertEqual(changes[0]["neural_tasks"], [self.task_id])
        self.assertEqual(changes[0]["paper_tasks"], [])
        self.assertEqual(self.plan(), ({}, []))
        self.assertEqual(refresh.integrity.check(self.root)["status"], "source_integrity_passed")

    def test_metadata_only_does_not_read_or_update_workflow_pins(self):
        workflow = self.root / refresh.WORKFLOWS[0]
        workflow.parent.mkdir(parents=True)
        stale = json.dumps({"path": self.closure_name, "bytes": 0, "sha256": "0" * 64}).encode()
        workflow.write_bytes(stale)
        outputs, _ = self.plan()
        self.assertNotIn(refresh.WORKFLOWS[0], outputs)
        self.assertEqual(workflow.read_bytes(), stale)
        with self.assertRaisesRegex(refresh.integrity.InvalidSource, "Stale workflow"):
            refresh.build_outputs(self.root)

    def test_neural_revision_fails_closed_without_generic_verifier(self):
        with mock.patch.object(refresh.integrity, "checked_specification_revision", None, create=True):
            self.reject("Neural specification revision verifier is unavailable")

    def test_unversioned_current_pin_cannot_be_rehashed(self):
        current = copy.deepcopy(self.original_current)
        current["packages"][0]["registered_task"].update(self.registered["specification"])
        self.current_path.write_bytes(encoded(current))
        self.reject("Unversioned registered task already changed")

    def test_closure_pin_cannot_be_rehashed_to_current_task(self):
        self.closure["files"][0] = copy.deepcopy(self.registered["specification"])
        self.closure_path.write_bytes(encoded(self.closure))
        self.reject("does not authenticate historical bytes")

    def test_forged_history_rejected_even_after_registry_rehash(self):
        forged = encoded({"id": self.task_id, "track": "neural", "forged": True})
        (self.root / self.history_path).write_bytes(forged)
        self.revision["previous_specification"] = descriptor(self.history_path, forged)
        self.registered["original_specification"] = descriptor(
            self.registered["original_specification"]["path"], forged)
        self.task["evaluation"]["neural_understanding"]["original_definition_sha256"] = self.revision["previous_specification"]["sha256"]
        self.save_task()
        self.reject("Refusing to rewrite registered task predecessor")

    def test_existing_closure_history_and_role_are_immutable(self):
        self.apply_metadata()
        original = json.loads(self.closure_path.read_text())
        for field, value in (("role", "direct_interpretation_result"),
                             ("historical_specification", self.registered["specification"])):
            with self.subTest(field=field):
                document = copy.deepcopy(original)
                document["neural_specification_revisions"][0][field] = value
                self.closure_path.write_bytes(encoded(document))
                self.reject("Refusing to replace existing closure history")

    def test_duplicate_or_orphaned_closure_lineage_rejected(self):
        self.apply_metadata()
        original = json.loads(self.closure_path.read_text())
        for duplicate in (True, False):
            with self.subTest(duplicate=duplicate):
                document = copy.deepcopy(original)
                if duplicate:
                    document["neural_specification_revisions"] *= 2
                else:
                    document["files"] = []
                self.closure_path.write_bytes(encoded(document))
                self.reject("Unexpected existing neural closure revision roster")

    def test_rehashed_semantic_task_change_is_rejected(self):
        self.task["objective"] = "historical_programme_score_is_direct_interpretation"
        self.save_task()
        self.reject("not bound to its understanding contract")

    def test_paper_path_cannot_alias_neural_task_identity(self):
        self.closure["files"][0]["path"] = "benchmarks/paper/" + self.task_id + "/task.json"
        self.closure_path.write_bytes(encoded(self.closure))
        self.reject("Closure task track or revision mismatch")

    def test_normalized_current_alias_retains_historical_candidate_identity(self):
        task_id, source_id = "NEURAL-ALIAS", "HOLD-ALIAS"
        home = "benchmarks/neural/" + task_id
        history_path = home + "/historical/task.pre-understanding.v1.json"
        # Historical expansion definitions may omit both id and track. The
        # reviewed binder normalizes only the new definition, not these bytes.
        old_body = encoded({"candidate_id": source_id, "source": "invented"})
        history = self.root / history_path
        history.parent.mkdir(parents=True)
        history.write_bytes(old_body)
        contract_path = home + "/understanding.v1.json"
        contract_body = encoded({"schema_version": "neural-understanding/v1",
                                 "task_id": task_id, "objective": self.objective})
        (self.root / contract_path).write_bytes(contract_body)
        revision = {"version": "neural-understanding/v1",
                    "previous_specification": descriptor(history_path, old_body),
                    "understanding_contract": descriptor(contract_path, contract_body)}
        task = copy.deepcopy(self.task)
        task.update(id=source_id, track="neural")
        binding = task["evaluation"]["neural_understanding"]
        binding["contract_sha256"] = revision["understanding_contract"]["sha256"]
        binding["original_definition_sha256"] = revision["previous_specification"]["sha256"]
        task_body = encoded(task)
        (self.root / home / "task.json").write_bytes(task_body)
        row = {"id": task_id, "specification_id": source_id, "track": "neural",
               "task_directory": home, "specification": descriptor(home + "/task.json", task_body),
               "original_specification": descriptor("benchmarks/manifests/neural/" + source_id + ".json", old_body),
               "specification_revision": revision}
        (self.root / "benchmarks/registry.json").write_bytes(encoded({
            "schema_version": 1, "kind": "neuroscience_benchmark_registry",
            "tasks": [self.registered, row]}))
        self.closure["files"].append(descriptor(home + "/task.json", old_body))
        self.closure_path.write_bytes(encoded(self.closure))
        outputs, _ = self.apply_metadata()
        closure = json.loads(outputs[self.closure_name])
        self.assertEqual(closure["files"][1], revision["previous_specification"])
        self.assertEqual(history.read_bytes(), old_body)
        self.assertEqual(self.plan(), ({}, []))


if __name__ == "__main__":
    unittest.main()
