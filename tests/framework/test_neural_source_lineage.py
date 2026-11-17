"""Source-only neural revision controls; no task implementation is executed."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[2] / "src/neurobench/source_integrity.py"
SPEC = importlib.util.spec_from_file_location("neural_lineage_checker", SOURCE)
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def pin(path, body):
    return {"path": path, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


class NeuralSourceLineageTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="neural-lineage-control-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.task_id = "NEURAL-INVENTED"
        self.home = "benchmarks/neural/" + self.task_id
        self.task_path = self.home + "/task.json"
        self.history_path = self.home + "/" + checker.NEURAL_HISTORY
        self.contract_path = self.home + "/understanding.v1.json"
        self.original_path = "benchmarks/manifests/neural/" + self.task_id + ".json"
        self.prefix = self.home + "/implementations/registered-runtime"
        self.old_body = encoded({"id": self.task_id, "track": "neural", "question": "old source question"})
        self.write(self.history_path, self.old_body)
        self.contract = {"schema_version": checker.NEURAL_REVISION, "task_id": self.task_id,
                         "objective": checker.NEURAL_OBJECTIVE}
        self.revision = {"version": checker.NEURAL_REVISION,
                         "previous_specification": pin(self.history_path, self.old_body)}
        self.task = {"id": self.task_id, "track": "neural", "objective": checker.NEURAL_OBJECTIVE,
                     "evaluation": {"neural_understanding": {
                         "schema_version": checker.NEURAL_REVISION,
                         "objective": checker.NEURAL_OBJECTIVE,
                         "contract_path": "understanding.v1.json",
                         "contract_sha256": None,
                         "original_definition_path": checker.NEURAL_HISTORY,
                         "original_definition_sha256": hashlib.sha256(self.old_body).hexdigest()}}}
        self.registered = {"id": self.task_id, "track": "neural", "task_directory": self.home,
                           "specification_id": self.task_id,
                           "original_specification": pin(self.original_path, self.old_body),
                           "specification_revision": self.revision}
        source_body = b'raise RuntimeError("source-only check must not execute this")\n'
        inventory_body = encoded({"files": [pin("source.py", source_body)]})
        manifest_body = encoded({"id": self.task_id,
                                 "canonical_specification": pin(self.original_path, self.old_body),
                                 "source_freeze": pin("INVENTORY.json", inventory_body)})
        files = []
        for name, body in (("source.py", source_body), ("INVENTORY.json", inventory_body),
                           ("manifest.json", manifest_body)):
            self.write(self.prefix + "/" + name, body)
            row = {**pin(name, body), "git_mode": "100644"}
            row["predecessor"] = {key: row[key] for key in ("bytes", "sha256", "git_mode")}
            files.append(row)
        self.package = {"implementation_id": "neural-invented-source", "task_id": self.task_id,
                        "track": "neural", "root": self.prefix,
                        "original_root": "benchmarks/neuroscience/invented",
                        "registered_task": {"original_path": self.original_path,
                                            "predecessor": {key: self.registered["original_specification"][key]
                                                            for key in ("bytes", "sha256")}},
                        "historical_inventory": {**pin("INVENTORY.json", inventory_body),
                                                 "path_style": "package",
                                                 "supplemental_files": [pin("manifest.json", manifest_body)]},
                        "files": files}
        self.current = {"schema_version": 2, "scope": "invented source lineage control",
                        "predecessor_commit": "0" * 40, "packages": [self.package]}
        self.sync_contract()

    def write(self, path, body):
        destination = self.root / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(body)
        destination.chmod(0o644)

    def sync_contract(self):
        body = encoded(self.contract)
        self.write(self.contract_path, body)
        self.revision["understanding_contract"] = pin(self.contract_path, body)
        self.task["evaluation"]["neural_understanding"]["contract_sha256"] = hashlib.sha256(body).hexdigest()
        self.sync_task()

    def sync_task(self):
        body = encoded(self.task)
        self.write(self.task_path, body)
        self.registered["specification"] = pin(self.task_path, body)
        self.package["registered_task"].update(self.registered["specification"],
                                               specification_revision=self.revision)
        self.save_metadata()

    def save_metadata(self):
        self.write("benchmarks/integrity/current.json", encoded(self.current))
        self.write("benchmarks/registry.json", encoded({"schema_version": 1,
                   "kind": "neuroscience_benchmark_registry", "tasks": [self.registered]}))

    def reject(self, message):
        with self.assertRaisesRegex(checker.InvalidSource, message):
            checker.check(self.root)

    def test_current_and_historical_definitions_are_authenticated_without_execution(self):
        manifest = (self.root / self.prefix / "manifest.json").read_bytes()
        result = checker.check(self.root)
        self.assertEqual(result["status"], "source_integrity_passed")
        self.assertEqual(result["packages"][0]["changed_files"], 0)
        self.assertFalse(result["benchmark_execution"])
        self.assertFalse(result["scientific_qualification_assessed"])
        self.assertEqual((self.root / self.history_path).read_bytes(), self.old_body)
        self.assertEqual((self.root / self.prefix / "manifest.json").read_bytes(), manifest)
        self.assertEqual(checker.checked_specification_revision(
            checker.Reader(self.root), self.task_id, self.package["registered_task"],
            self.task, self.registered), self.old_body)
        self.assertFalse((self.root / self.original_path).exists())

    def test_rehash_cannot_replace_original_history(self):
        body = encoded({"id": self.task_id, "track": "neural", "question": "rewritten history"})
        self.write(self.history_path, body)
        self.revision["previous_specification"] = pin(self.history_path, body)
        self.task["evaluation"]["neural_understanding"]["original_definition_sha256"] = hashlib.sha256(body).hexdigest()
        self.sync_task()
        self.reject("does not match registered predecessor")

    def test_unrehashed_current_history_and_contract_tampering_is_rejected(self):
        for name in (self.task_path, self.history_path, self.contract_path):
            with self.subTest(path=name):
                original = (self.root / name).read_bytes()
                self.write(name, original + b" ")
                self.reject("hash or length mismatch")
                self.write(name, original)

    def test_rehashed_binding_changes_are_rejected(self):
        original = copy.deepcopy(self.task)
        binding_changes = {
            "schema_version": "neural-understanding/v2",
            "objective": "programme_performance_proves_direct_interpretation",
            "contract_path": "../NEURAL-OTHER/understanding.v1.json",
            "contract_sha256": "0" * 64,
            "original_definition_path": "task.json",
            "original_definition_sha256": "0" * 64,
            "unreviewed_extra_binding": True,
        }
        for field, value in binding_changes.items():
            with self.subTest(field=field):
                self.task = copy.deepcopy(original)
                self.task["evaluation"]["neural_understanding"][field] = value
                self.sync_task()
                self.reject("not bound")

    def test_rehashed_contract_identity_changes_are_rejected(self):
        original = copy.deepcopy(self.contract)
        for field, value in (("task_id", "NEURAL-OTHER"), ("schema_version", "neural-understanding/v2"),
                             ("objective", "different_scientific_task")):
            with self.subTest(field=field):
                self.contract = {**original, field: value}
                self.sync_contract()
                self.reject("contract identity mismatch")

    def test_contract_and_history_pins_cannot_name_another_task(self):
        for field, name in (("previous_specification", checker.NEURAL_HISTORY),
                            ("understanding_contract", "understanding.v1.json")):
            with self.subTest(field=field):
                original = self.revision[field]["path"]
                self.revision[field]["path"] = "benchmarks/neural/NEURAL-OTHER/" + name
                self.save_metadata()
                self.reject("member location")
                self.revision[field]["path"] = original

    def test_original_registry_identity_is_immutable(self):
        original = copy.deepcopy(self.registered["original_specification"])
        for field, value in (("path", "benchmarks/manifests/neural/NEURAL-OTHER.json"),
                             ("sha256", "0" * 64), ("bytes", 0)):
            with self.subTest(field=field):
                self.registered["original_specification"] = {**original, field: value}
                self.save_metadata()
                self.reject("original registered identity")

    def test_registry_task_revision_or_current_pin_cannot_disagree(self):
        original = copy.deepcopy(self.registered)
        for field, value in (("track", "paper"), ("task_directory", "benchmarks/neural/NEURAL-OTHER"),
                             ("specification_revision", {}), ("specification", {})):
            with self.subTest(field=field):
                self.registered = {**original, field: value}
                self.save_metadata()
                self.reject("differs from current task registration")

    def test_missing_authoritative_registry_task_is_rejected(self):
        self.registered = {"id": "NEURAL-OTHER"}
        self.save_metadata()
        self.reject("differs from current task registration")

    def test_wrong_version_and_wrong_track_exceptions_are_rejected(self):
        self.revision["version"] = "neural-understanding/v2"
        self.save_metadata()
        self.reject("Unsupported neural specification revision")
        self.revision["version"] = checker.PAPER_REVISION
        self.save_metadata()
        self.reject("Only paper tasks")

    def test_history_cannot_already_be_revised_or_have_a_different_identity(self):
        for changes in ({"id": "NEURAL-OTHER"}, {"track": "paper"},
                        {"objective": checker.NEURAL_OBJECTIVE}):
            with self.subTest(changes=changes):
                body = encoded({"id": self.task_id, "track": "neural", **changes})
                self.write(self.history_path, body)
                previous = pin(self.history_path, body)
                task_pin = copy.deepcopy(self.package["registered_task"])
                task_pin["predecessor"] = {key: previous[key] for key in ("bytes", "sha256")}
                task_pin["specification_revision"]["previous_specification"] = previous
                with self.assertRaisesRegex(checker.InvalidSource, "Historical neural specification identity"):
                    checker.checked_neural_revision(checker.Reader(self.root), self.task_id,
                                                    task_pin, self.task, self.registered)

    def test_direct_neural_helper_checks_current_track_identity_and_path(self):
        for field, value in (("id", "NEURAL-OTHER"), ("track", "paper"),
                             ("objective", "programme_only")):
            with self.subTest(field=field), self.assertRaisesRegex(checker.InvalidSource, "not bound"):
                checker.checked_neural_revision(checker.Reader(self.root), self.task_id,
                    self.package["registered_task"], {**self.task, field: value}, self.registered)
        with self.assertRaisesRegex(checker.InvalidSource, "not bound"):
            checker.checked_neural_revision(checker.Reader(self.root), self.task_id,
                {**self.package["registered_task"], "path": self.history_path}, self.task, self.registered)

    def test_revision_does_not_excuse_implementation_manifest_changes(self):
        path = self.prefix + "/manifest.json"
        self.write(path, (self.root / path).read_bytes() + b" ")
        self.reject("hash or length mismatch")


if __name__ == "__main__":
    unittest.main()
