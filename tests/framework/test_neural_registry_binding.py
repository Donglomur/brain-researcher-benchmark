"""Neural registration lineage and refusal checks; no scientific implementation runs."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("neural_registry_binding_tests",
                                             ROOT / "scripts/maintenance/bind_neural_registry.py")
binder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(binder)


def put(root, name, document):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    body = binder.encode(document) if isinstance(document, dict) else document
    path.write_bytes(body)
    return binder.pin(name, body)


def contract(identifier):
    return {"schema_version": binder.VERSION, "task_id": identifier, "objective": binder.OBJECTIVE,
            "disposition": "partial_delivery", "valid_science_fixture": True}


def validate(document, task_id=None):
    return [] if document.get("valid_science_fixture") is True else ["fixture scientific validation failed"]


def summary(document):
    return {key: document[key] for key in ("schema_version", "objective", "disposition")}


ENGINE = types.SimpleNamespace(validate_contract=validate, summary=summary)


def fixture(root):
    rows = []
    for index in (1, 2):
        identifier = f"NEURAL-{index:03d}"
        identity = identifier if index == 1 else "PRIOR-ALIAS-002"
        home = "benchmarks/neural/" + identifier
        old = {"schema_version": 1, "id": identity, "title": "Original question " + identifier,
               "track": "neural", "status": "specification_only", "unrevised": True}
        old_body = binder.encode(old)
        old_pin = binder.pin(home + "/task.json", old_body)
        put(root, home + "/" + binder.HISTORY, old_body)
        contract_pin = put(root, home + "/understanding.v1.json", contract(identifier))
        task = {"schema_version": 1, "id": identity, "track": "neural", "title": "Revised question " + identifier,
                "status": "specification_only", "objective": binder.OBJECTIVE,
                "evaluation": {"neural_understanding": {
                    "schema_version": binder.VERSION, "objective": binder.OBJECTIVE,
                    "contract_path": "understanding.v1.json", "contract_sha256": contract_pin["sha256"],
                    "original_definition_path": binder.HISTORY,
                    "original_definition_sha256": hashlib.sha256(old_body).hexdigest()}},
                "admission": {"runnable": False, "research_qualified": False}}
        put(root, home + "/task.json", task)
        rows.append({"id": identifier, "title": old["title"], "track": "neural",
                     "task_directory": home, "specification": old_pin,
                     "original_specification": {**old_pin, "path": "private-unavailable/old-" + identifier + ".json"},
                     "specification_id": identity, "specification_alias": identity != identifier,
                     "runtime_manifest": {"path": "not-opened/manifest.json"},
                     "registration_class": "canonical" if index == 1 else "expansion",
                     "scientific_readiness": "unknown", "submission_readiness": "unknown"})
    rows.append({"id": "PAPER-001", "track": "paper", "arbitrary_current_paper_metadata": [1, 2, 3]})
    registry = {"schema_version": 1, "kind": "neuroscience_benchmark_registry",
                "tasks": rows, "implementation_ownership": ["unchanged"], "source_commit": "a" * 40}
    put(root, binder.REGISTRY, registry)
    return registry


class NeuralRegistryBindingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.original = fixture(self.root)
        self.original_body = (self.root / binder.REGISTRY).read_bytes()

    def bind(self, **kwargs):
        return binder.write_or_check(self.root, engine=ENGINE, **kwargs)

    def registry(self):
        return json.loads((self.root / binder.REGISTRY).read_bytes())

    def task_path(self, index=1):
        return f"benchmarks/neural/NEURAL-{index:03d}/task.json"

    def assert_untouched(self):
        self.assertEqual((self.root / binder.REGISTRY).read_bytes(), self.original_body)
        self.assertFalse((self.root / binder.SNAPSHOT).exists())

    def test_writes_only_registry_and_exact_snapshot_and_is_idempotent(self):
        tasks_before = {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob("*.json")
                        if path != self.root / binder.REGISTRY}
        result = self.bind(write=True)
        self.assertEqual(result["status"], "written")
        self.assertEqual(result["neural_registrations"], 2)
        self.assertFalse(result["benchmark_execution"])
        self.assertEqual((self.root / binder.SNAPSHOT).read_bytes(), self.original_body)
        current = self.registry()
        self.assertEqual(current["tasks"][-1], self.original["tasks"][-1])
        self.assertEqual(current["implementation_ownership"], ["unchanged"])
        for old, row in zip(self.original["tasks"][:2], current["tasks"][:2]):
            self.assertEqual(row["original_specification"], old["original_specification"])
            self.assertEqual(row["specification_id"], old["specification_id"])
            self.assertEqual(row["specification_alias"], old["specification_alias"])
            self.assertEqual(row["runtime_manifest"], old["runtime_manifest"])
            self.assertEqual(row["scientific_readiness"], "unknown")
            self.assertEqual(row["submission_readiness"], "not_qualified_by_binding")
            self.assertEqual(row["title"], "Revised question " + row["id"])
            self.assertEqual(row["specification_revision"]["previous_specification"]["sha256"], old["specification"]["sha256"])
        for relative, body in tasks_before.items():
            self.assertEqual((self.root / relative).read_bytes(), body)
        after = (self.root / binder.REGISTRY).read_bytes()
        self.assertEqual(self.bind()["status"], "current")
        self.assertEqual(self.bind(write=True)["changed_files"], [])
        self.assertEqual((self.root / binder.REGISTRY).read_bytes(), after)

    def test_default_check_reports_stale_and_writes_nothing(self):
        before = sorted(path.relative_to(self.root) for path in self.root.rglob("*"))
        result = self.bind()
        self.assertEqual(result["status"], "stale")
        self.assert_untouched()
        self.assertEqual(sorted(path.relative_to(self.root) for path in self.root.rglob("*")), before)

    def test_later_paper_edits_and_additions_are_preserved(self):
        self.bind(write=True)
        current = self.registry()
        current["tasks"][-1]["arbitrary_current_paper_metadata"] = ["new source revision"]
        current["tasks"].append({"id": "PAPER-NEW-2024", "track": "paper", "source": "new source"})
        put(self.root, binder.REGISTRY, current)
        before = (self.root / binder.REGISTRY).read_bytes()
        self.assertEqual(self.bind()["status"], "current")
        self.assertEqual((self.root / binder.REGISTRY).read_bytes(), before)
        self.assertEqual((self.root / binder.SNAPSHOT).read_bytes(), self.original_body)

    def test_missing_last_contract_refuses_without_partial_snapshot(self):
        (self.root / "benchmarks/neural/NEURAL-002/understanding.v1.json").unlink()
        with self.assertRaises(OSError):
            self.bind(write=True)
        self.assert_untouched()

    def test_malformed_source_binding_refuses_before_writes(self):
        name = self.task_path()
        original = (self.root / name).read_bytes()
        for change in (
            lambda doc: doc.update(id="another-task"),
            lambda doc: doc.update(track="paper"),
            lambda doc: doc.update(objective="promote_programme_result_to_interpretation"),
            lambda doc: doc["evaluation"]["neural_understanding"].update(contract_path="../../private/labels.json"),
            lambda doc: doc["evaluation"]["neural_understanding"].update(contract_sha256="f" * 64),
            lambda doc: doc["evaluation"]["neural_understanding"].update(original_definition_sha256="f" * 64),
            lambda doc: doc["evaluation"]["neural_understanding"].update(extra="unreviewed-binding"),
            lambda doc: doc["admission"].update(runnable=True),
            lambda doc: doc["admission"].update(research_qualified=True),
            lambda doc: doc["admission"].update(runnable=0),
            lambda doc: doc.pop("admission"),
        ):
            document = json.loads(original)
            change(document)
            put(self.root, name, document)
            with self.assertRaises(ValueError):
                self.bind(write=True)
            self.assert_untouched()
        put(self.root, name, original)

    def test_invalid_scientific_contract_refuses_before_binding(self):
        name = "benchmarks/neural/NEURAL-002/understanding.v1.json"
        document = contract("NEURAL-002")
        document["valid_science_fixture"] = False
        put(self.root, name, document)
        with self.assertRaisesRegex(ValueError, "invalid neural contract"):
            self.bind(write=True)
        self.assert_untouched()

    def test_history_tampering_and_rehashed_current_pins_cannot_replace_snapshot(self):
        self.bind(write=True)
        registry = self.registry()
        row = registry["tasks"][0]
        name = row["specification_revision"]["previous_specification"]["path"]
        altered = (self.root / name).read_bytes() + b" "
        altered_pin = put(self.root, name, altered)
        row["original_specification"].update(bytes=len(altered), sha256=altered_pin["sha256"])
        row["specification_revision"]["previous_specification"] = altered_pin
        put(self.root, binder.REGISTRY, registry)
        before = (self.root / binder.REGISTRY).read_bytes()
        with self.assertRaisesRegex(ValueError, "original neural registration drift"):
            self.bind(write=True)
        self.assertEqual((self.root / binder.REGISTRY).read_bytes(), before)
        self.assertEqual((self.root / binder.SNAPSHOT).read_bytes(), self.original_body)

    def test_existing_snapshot_pin_and_neural_roster_cannot_drift(self):
        self.bind(write=True)
        before = (self.root / binder.REGISTRY).read_bytes()
        for change in (
            lambda doc: doc["neural_understanding"]["pre_understanding_registry"].update(sha256="f" * 64),
            lambda doc: doc["tasks"].pop(0),
            lambda doc: doc["neural_understanding"].update(registered_count=True),
            lambda doc: doc["neural_understanding"].update(coverage_required=1),
            lambda doc: doc.pop("neural_understanding"),
            lambda doc: doc["tasks"][0].pop("specification_revision"),
        ):
            current = json.loads(before)
            change(current)
            put(self.root, binder.REGISTRY, current)
            with self.assertRaises(ValueError):
                self.bind(write=True)
            self.assertEqual((self.root / binder.SNAPSHOT).read_bytes(), self.original_body)
        put(self.root, binder.REGISTRY, before)

    def test_boolean_registry_schema_is_not_an_integer_schema_version(self):
        current = copy.deepcopy(self.original)
        current["schema_version"] = True
        put(self.root, binder.REGISTRY, current)
        with self.assertRaisesRegex(ValueError, "unsupported benchmark registry"):
            self.bind(write=True)
        self.assertFalse((self.root / binder.SNAPSHOT).exists())

    def test_duplicate_ids_and_json_keys_and_nonfinite_values_refuse(self):
        original_task = (self.root / self.task_path()).read_bytes()
        for body in (b'{"id":"A","id":"B"}', b'{"bad":NaN}', b'{"bad":1e9999}'):
            put(self.root, self.task_path(), body)
            with self.assertRaises(ValueError):
                self.bind(write=True)
            self.assert_untouched()
        put(self.root, self.task_path(), original_task)
        current = copy.deepcopy(self.original)
        duplicate = copy.deepcopy(current["tasks"][0])
        duplicate["id"] = duplicate["id"].lower()
        current["tasks"].append(duplicate)
        put(self.root, binder.REGISTRY, current)
        with self.assertRaisesRegex(ValueError, "duplicate registered"):
            self.bind(write=True)
        self.assertFalse((self.root / binder.SNAPSHOT).exists())

    def test_symlink_and_hardlink_sources_are_rejected(self):
        name = self.task_path()
        path = self.root / name
        original = path.read_bytes()
        outside = self.root / "untrusted.json"
        outside.write_bytes(original)
        for make_alias in (lambda: path.symlink_to(outside), lambda: os.link(outside, path)):
            path.unlink()
            make_alias()
            with self.assertRaisesRegex(ValueError, "single-link"):
                self.bind(write=True)
            self.assert_untouched()
            path.unlink()
            path.write_bytes(original)

    def test_output_parent_alias_and_private_original_locator_refuse(self):
        private = self.root / "private-outside"
        private.mkdir()
        (self.root / "docs").symlink_to(private, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "ordinary source directory"):
            self.bind(write=True)
        self.assert_untouched()
        (self.root / "docs").unlink()
        current = copy.deepcopy(self.original)
        current["tasks"][0]["original_specification"]["path"] = "/private/labels.json"
        put(self.root, binder.REGISTRY, current)
        with self.assertRaisesRegex(ValueError, "repository-relative"):
            self.bind(write=True)
        self.assertFalse((self.root / binder.SNAPSHOT).exists())

    def test_member_and_total_byte_limits_refuse_before_writes(self):
        for name, maximum in (("MEMBER_LIMIT", 32), ("TOTAL_LIMIT", 32)):
            with patch.object(binder, name, maximum), self.assertRaisesRegex(ValueError, "byte limit|read budget"):
                self.bind(write=True)
            self.assert_untouched()

    def test_changed_second_preflight_refuses_without_writes(self):
        original_build = binder.build_outputs
        calls = []

        def racing_build(*args, **kwargs):
            result = original_build(*args, **kwargs)
            calls.append(None)
            if len(calls) == 1:
                task = json.loads((self.root / self.task_path()).read_bytes())
                task["title"] = "Concurrent valid task change"
                put(self.root, self.task_path(), task)
            return result

        with patch.object(binder, "build_outputs", side_effect=racing_build):
            with self.assertRaisesRegex(ValueError, "inputs changed"):
                self.bind(write=True)
        self.assert_untouched()

    def test_interrupted_registry_replace_keeps_only_valid_retryable_snapshot(self):
        with patch.object(binder.os, "replace", side_effect=OSError("simulated registry write failure")):
            with self.assertRaisesRegex(OSError, "simulated"):
                self.bind(write=True)
        self.assertEqual((self.root / binder.REGISTRY).read_bytes(), self.original_body)
        self.assertEqual((self.root / binder.SNAPSHOT).read_bytes(), self.original_body)
        self.assertEqual(self.bind(write=True)["status"], "written")
        self.assertEqual(self.bind()["status"], "current")
        self.assertFalse(list((self.root / "benchmarks").glob(".neural-registry-*")))


if __name__ == "__main__":
    unittest.main()
