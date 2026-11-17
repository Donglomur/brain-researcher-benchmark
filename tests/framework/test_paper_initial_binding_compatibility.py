"""Initial paper profiles coexist with the exact historical 116-task migration."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


fixtures = module("initial_paper_catalog_fixtures", ROOT / "tests/framework/test_catalog.py")
bindings = module("initial_paper_binding_fixtures", ROOT / "tests/maintenance/test_paper_improvement_bindings.py")
engine = module("initial_paper_contract_engine", ROOT / "src/neurobench/paper_improvement.py")
builder = bindings.builder
INITIAL_ID = "PAPER-INITIAL-2024"


class InitialPaperBindingCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=Path(tempfile.gettempdir()).resolve())
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        fixtures.fixture(self.root)
        original = self.registry()
        for row in original["tasks"]:
            if row["track"] == "paper":
                bindings.put(self.root, row["task_directory"] + "/improvement.v1.json", bindings.contract(row["id"]))
        self.bind()
        self.history = (self.root / builder.SNAPSHOT).read_bytes()
        self.add_initial()

    def registry(self):
        return json.loads((self.root / builder.REGISTRY).read_bytes())

    def save_registry(self, document):
        bindings.put(self.root, builder.REGISTRY, document)

    def bind(self, check=False):
        return builder.write_or_check(self.root, check=check, validator=engine.contract_validate)

    def snapshot(self):
        return {path.relative_to(self.root).as_posix(): path.read_bytes()
                for path in self.root.rglob("*") if path.is_file()}

    def add_initial(self, identifier=INITIAL_ID, *, replace_registered_id=False):
        home = "benchmarks/paper/" + identifier
        contract = bindings.contract(identifier)
        contract["legacy"] = {"role": "no_predecessor", "original_task": None,
                              "notes": "First source-paper improvement registration; no historical reproduction task exists."}
        contract_path = home + "/improvement.v1.json"
        contract_pin = builder.pin(contract_path, bindings.put(self.root, contract_path, contract))
        task = {"schema_version": 1, "id": identifier, "title": "New original paper endpoint",
                "track": "paper", "status": contract["disposition"], "objective": builder.OBJECTIVE,
                "evaluation": {"objective": builder.OBJECTIVE, "contract": contract_pin,
                               "disposition": contract["disposition"], "reproduction_role": "not_applicable"},
                "admission": {"runnable": False, "research_qualified": False, "submission_ready": False}}
        task_path = home + "/task.json"
        specification = builder.pin(task_path, bindings.put(self.root, task_path, task))
        registration_path = "docs/provenance/registrations/paper-initial/" + identifier + ".json"
        registration = {"schema_version": builder.INITIAL_VERSION, "task_id": identifier,
                        "source_commit": "d" * 40, "specification": specification, "improvement_contract": contract_pin}
        registration_pin = builder.pin(registration_path, bindings.put(self.root, registration_path, registration))
        row = fixtures.catalog.task_row(identifier, task["title"], "paper", specification,
                                        "registered_construction_draft", registration_path, task)
        row.update(registration_class="expansion", original_specification=copy.deepcopy(specification),
                   specification_revision={"version": builder.INITIAL_VERSION, "improvement_contract": contract_pin,
                                           "initial_registration": registration_pin},
                   scientific_readiness=contract["disposition"], submission_readiness="not_qualified_by_binding")
        registry = self.registry()
        if replace_registered_id:
            replaced = next(old for old in registry["tasks"] if old["id"] == identifier)
            registry["tasks"] = [old for old in registry["tasks"] if old["id"] != identifier]
            registry["source_counts"][replaced["track"]] -= 1
            registry["source_counts"]["total"] -= 1
            registry["source_counts"]["canonical_specifications" if replaced["registration_class"] == "canonical"
                                      else "expansion_drafts"] -= 1
        registry["tasks"].append(row)
        registry["tasks"].sort(key=lambda record: record["id"])
        registry["historical_registries"].append(registration_pin)
        registry["paper_improvement"]["registered_count"] += 1
        for field in ("paper", "total", "expansion_drafts"):
            registry["source_counts"][field] += 1
        self.save_registry(registry)
        return row

    def initial_row(self):
        return next(row for row in self.registry()["tasks"] if row["id"] == INITIAL_ID)

    def assert_refuses_without_writes(self):
        before = self.snapshot()
        for check in (True, False):
            with self.assertRaises((ValueError, OSError)):
                self.bind(check=check)
            self.assertEqual(self.snapshot(), before)

    def repin_initial_registration(self, registry, document):
        row = next(row for row in registry["tasks"] if row["id"] == INITIAL_ID)
        name = row["specification_revision"]["initial_registration"]["path"]
        current_pin = builder.pin(name, bindings.put(self.root, name, document))
        row["specification_revision"]["initial_registration"] = current_pin
        registry["historical_registries"] = [current_pin if item["path"] == name else item
                                             for item in registry["historical_registries"]]
        self.save_registry(registry)

    def test_initial_files_and_registry_row_are_preserved_without_fabricated_history(self):
        before = self.snapshot()
        row = self.initial_row()
        self.assertNotIn("paper_improvement", row)  # Optional display summary is not count authority.
        checked = self.bind(check=True)
        self.assertEqual(checked["paper_registrations"], 117)
        self.assertEqual(checked["dispositions"], {"source_unresolved": 117})
        self.assertEqual(checked["changed_files"], 0)
        self.assertEqual(self.bind()["changed_files"], 0)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.initial_row(), row)
        self.assertEqual((self.root / builder.SNAPSHOT).read_bytes(), self.history)
        self.assertFalse((self.root / row["task_directory"] / builder.HISTORY).exists())
        outputs = builder.build_outputs(self.root, validator=engine.contract_validate)
        self.assertFalse(any(name.startswith(row["task_directory"] + "/") for name in outputs))
        self.assertNotIn(row["specification_revision"]["initial_registration"]["path"], outputs)

    def test_historical_contract_rebinding_preserves_initial_bytes_and_old_history(self):
        initial = self.initial_row()
        protected = {name: body for name, body in self.snapshot().items()
                     if name.startswith(initial["task_directory"] + "/")
                     or name == initial["specification_revision"]["initial_registration"]["path"]
                     or name.endswith("/" + builder.HISTORY)}
        name = "benchmarks/paper/PAPER-001/improvement.v1.json"
        changed = json.loads((self.root / name).read_bytes())
        changed["disposition_reason"] += "; original endpoint still requires native source recovery"
        bindings.put(self.root, name, changed)
        with self.assertRaisesRegex(ValueError, "stale or missing"):
            self.bind(check=True)
        self.assertGreater(self.bind()["changed_files"], 0)
        self.assertEqual(self.bind(check=True)["changed_files"], 0)
        self.assertEqual(self.initial_row(), initial)
        for name, body in protected.items():
            self.assertEqual((self.root / name).read_bytes(), body, name)
        self.assertEqual((self.root / builder.SNAPSHOT).read_bytes(), self.history)

    def test_missing_initial_snapshot_or_contract_refuses(self):
        row = self.initial_row()
        for name in (row["specification_revision"]["initial_registration"]["path"],
                     row["specification_revision"]["improvement_contract"]["path"]):
            body = (self.root / name).read_bytes()
            (self.root / name).unlink()
            self.assert_refuses_without_writes()
            bindings.put(self.root, name, body)

    def test_forged_initial_snapshot_is_rejected_even_when_its_outer_pin_is_updated(self):
        before = self.snapshot()
        registry = self.registry()
        name = self.initial_row()["specification_revision"]["initial_registration"]["path"]
        snapshot = json.loads(before[name])
        mutations = (
            lambda doc: doc.update(task_id="PAPER-001"),
            lambda doc: doc.update(source_commit="not-a-source-commit"),
            lambda doc: doc.update(extra="unreviewed"),
            lambda doc: doc["specification"].update(sha256="f" * 64),
            lambda doc: doc["improvement_contract"].update(sha256="e" * 64),
        )
        for change in mutations:
            with self.subTest(change=change):
                altered = copy.deepcopy(snapshot)
                change(altered)
                self.repin_initial_registration(copy.deepcopy(registry), altered)
                self.assert_refuses_without_writes()
        bindings.put(self.root, name, before[name])
        self.save_registry(registry)

    def test_initial_profile_and_enrollment_are_closed(self):
        original = self.registry()
        mutations = (
            lambda row, registry: row["specification_revision"].update(previous_specification=row["specification"]),
            lambda row, registry: row.update(specification_alias=True),
            lambda row, registry: row.update(registration_class="canonical"),
            lambda row, registry: row.update(registry="docs/private/initial.json"),
            lambda row, registry: row.update(original_specification={**row["specification"], "sha256": "f" * 64}),
            lambda row, registry: registry["historical_registries"].append(row["specification_revision"]["initial_registration"]),
            lambda row, registry: registry["historical_registries"].pop(),
            lambda row, registry: registry["paper_improvement"].update(registered_count=116),
        )
        for change in mutations:
            with self.subTest(change=change):
                current = copy.deepcopy(original)
                row = next(row for row in current["tasks"] if row["id"] == INITIAL_ID)
                change(row, current)
                self.save_registry(current)
                self.assert_refuses_without_writes()
        self.save_registry(original)

    def test_incomplete_or_mistyped_current_roster_counts_refuse_before_writes(self):
        original = self.registry()
        for field in ("paper", "neural", "total", "canonical_specifications", "expansion_drafts"):
            with self.subTest(field=field):
                for value in (original["source_counts"][field] - 1, True):
                    changed = copy.deepcopy(original)
                    changed["source_counts"][field] = value
                    self.save_registry(changed)
                    self.assert_refuses_without_writes()
        self.save_registry(original)

    def test_initial_history_file_and_unregistered_current_contract_refuse(self):
        name = self.initial_row()["task_directory"] + "/" + builder.HISTORY
        bindings.put(self.root, name, b'{"invented_predecessor":true}\n')
        self.assert_refuses_without_writes()
        (self.root / name).unlink()
        orphan = "benchmarks/paper/PAPER-UNREGISTERED/improvement.v1.json"
        bindings.put(self.root, orphan, bindings.contract("PAPER-UNREGISTERED"))
        self.assert_refuses_without_writes()

    def test_old_neural_identity_cannot_be_relabelled_as_new_paper(self):
        self.add_initial("NEURAL-001", replace_registered_id=True)
        with self.assertRaisesRegex(ValueError, "restricted to new task identities"):
            self.bind(check=True)
        self.assert_refuses_without_writes()

    def test_earlier_paper_identity_cannot_use_initial_profile(self):
        current = self.registry()
        old = next(row for row in current["tasks"] if row["id"] == "PAPER-001")
        old["specification_revision"] = copy.deepcopy(self.initial_row()["specification_revision"])
        self.save_registry(current)
        with self.assertRaisesRegex(ValueError, "historical paper registration count must be exactly 116"):
            self.bind(check=True)
        self.assert_refuses_without_writes()

    def test_initial_contract_semantics_are_validated_before_any_historical_rebinding(self):
        registry = self.registry()
        row = next(row for row in registry["tasks"] if row["id"] == INITIAL_ID)
        path = row["task_directory"] + "/improvement.v1.json"
        contract = json.loads((self.root / path).read_bytes())
        contract["comparison"]["direction"] = "invalid-direction"
        contract_pin = builder.pin(path, bindings.put(self.root, path, contract))
        row["specification_revision"]["improvement_contract"] = contract_pin
        task_path = row["specification"]["path"]
        task = json.loads((self.root / task_path).read_bytes())
        task["evaluation"]["contract"] = contract_pin
        row["specification"] = row["original_specification"] = builder.pin(task_path, bindings.put(self.root, task_path, task))
        registration_path = row["specification_revision"]["initial_registration"]["path"]
        registration = json.loads((self.root / registration_path).read_bytes())
        registration.update(specification=row["specification"], improvement_contract=contract_pin)
        self.repin_initial_registration(registry, registration)
        with self.assertRaisesRegex(ValueError, "invalid initial improvement contract"):
            self.bind(check=True)
        self.assert_refuses_without_writes()


if __name__ == "__main__":
    unittest.main()
