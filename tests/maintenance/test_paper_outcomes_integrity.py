"""Invented metadata controls for original, improvement and dual-outcome lineage.

The fixture's implementation raises if executed.  No paper, native input, model,
scientific result or task implementation is executed by these controls.
"""
import copy
import json
from pathlib import Path
import runpy
import shutil
import unittest


ROOT = Path(__file__).resolve().parents[2]
pre_endpoint_selection_fixture = runpy.run_path(
    str(ROOT / "tests/framework/test_catalog.py"))["pre_endpoint_selection_fixture"]
source = runpy.run_path(str(ROOT / "tests/framework/test_source_integrity.py"))
scientific = runpy.run_path(str(ROOT / "tests/framework/test_paper_reproduction.py"))
legacy = runpy.run_path(str(ROOT / "tests/maintenance/test_paper_improvement_bindings.py"))
checker, refresh = source["checker"], source["refresh"]
old_binder = legacy["builder"]
binding = checker.outcome_binding_module()


class PaperOutcomesIntegrityTests(unittest.TestCase):
    @pre_endpoint_selection_fixture
    def setUp(self):
        original = source["SourceIntegrityTests"]("test_valid_bundle_is_checked_without_execution")
        original.setUp()
        original.make_paper_revision()
        self.root = original.root
        self.addCleanup(shutil.rmtree, self.root)
        self.identifier = original.task_id
        self.home = "benchmarks/paper/" + self.identifier
        self.task_path = self.home + "/task.json"
        self.current_path = "benchmarks/integrity/current.json"
        self.history_path = self.home + "/" + checker.PAPER_HISTORY
        self.original_bytes = self.read(self.history_path)
        self.original_current = self.load(self.current_path)
        self.reproduction, self.improvement, self.outcomes, _, _ = scientific["fixture"]()
        for document in (self.reproduction, self.improvement, self.outcomes):
            document["task_id"] = self.identifier
        self.outcomes["contracts"] = {
            "reproduction": scientific["paper"].contract_digest(self.reproduction),
            "improvement": scientific["paper"].contract_digest(self.improvement),
        }
        self.put(self.home + "/improvement.v1.json", self.improvement)
        # Generate the previous-current definition with the actual old binder,
        # rather than manufacturing just enough fields to satisfy the new one.
        original_row = {
            "id": self.identifier, "title": "Invented lineage fixture", "track": "paper",
            "task_directory": self.home, "specification_id": self.identifier,
            "specification_alias": False, "registration_class": "expansion",
            "specification": binding.pin(self.task_path, self.original_bytes),
            "original_specification": binding.pin(original.original_canonical_path, self.original_bytes),
        }
        self.neural_id = "NEURAL-UNENROLLED-FIXTURE"
        implementations = [
            {"id": "paper-history", "owner_ids": [self.identifier], "related_task_ids": [],
             "role": "task_implementation", "scope_notes": "Invented historical paper component"},
            {"id": "mixed-history", "owner_ids": [self.neural_id], "related_task_ids": [self.identifier],
             "role": "shared_source_distribution", "scope_notes": "Invented shared component",
             "evaluation_roles": {self.neural_id: "active_evaluation"}},
            {"id": "neural-history", "owner_ids": [self.neural_id], "related_task_ids": [],
             "role": "neural_runtime", "evaluation_roles": {self.neural_id: "active_evaluation"}},
        ]
        initial = {"schema_version": 1, "kind": "neuroscience_benchmark_registry",
                   "source_counts": {"paper": 1, "neural": 1, "total": 2},
                   "tasks": [original_row, {"id": self.neural_id, "track": "neural"}],
                   "implementations": implementations}
        self.put(self.task_path, self.original_bytes)
        self.put(binding.REGISTRY, initial)
        self.put("src/neurobench/paper_improvement.py", (ROOT / "src/neurobench/paper_improvement.py").read_bytes())
        for name, body in old_binder.build_outputs(self.root, expected_count=1).items():
            self.put(name, body)
        self.prior_registry = self.load(binding.REGISTRY)
        self.prior_row = self.prior_registry["tasks"][0]
        self.prior_task_bytes = self.read(self.task_path)
        self.prior_task = self.load(self.task_path)
        self.prior_current = copy.deepcopy(self.original_current)
        self.prior_current["packages"][0]["registered_task"].update(
            self.prior_row["specification"], specification_revision=self.prior_row["specification_revision"])
        self.put(binding.SNAPSHOT, self.read(binding.REGISTRY))
        self.put(self.home + "/" + binding.HISTORY, self.prior_task_bytes)
        self.registry = copy.deepcopy(self.prior_registry)
        self.row = self.registry["tasks"][0]
        self.row["paper_outcomes"] = {
            "schema_version": binding.VERSION,
            "previous_specification": binding.pin(self.home + "/" + binding.HISTORY, self.prior_task_bytes),
        }
        self.registry["paper_outcomes"] = {
            "schema_version": binding.VERSION, "coverage_required": True, "registered_count": 1,
            "pre_outcomes_registry": binding.pin(binding.SNAPSHOT, self.read(binding.SNAPSHOT)),
        }
        self.registry.setdefault("historical_registries", []).append(self.registry["paper_outcomes"]["pre_outcomes_registry"])
        self.task = binding.project_task(self.prior_task, self.prior_row, self.improvement)
        self.save_current_task()
        self.save_reproduction()
        self.outcomes["original_task_sha256"] = self.row["specification"]["sha256"]
        self.save_outcomes()
        self.save_registry()
        self.current = copy.deepcopy(self.prior_current)
        self.sync_enrollment()
        self.closure_path = refresh.CLOSURES + "/invented-outcomes/SOURCE.json"
        self.put(self.closure_path, {"schema": "invented", "files": [
            binding.pin(self.task_path, self.original_bytes)]})

    def read(self, name):
        return (self.root / name).read_bytes()

    def load(self, name):
        return json.loads(self.read(name))

    def put(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = value if isinstance(value, bytes) else binding.encode(value)
        path.write_bytes(raw)
        return raw

    def save_registry(self):
        self.put(binding.REGISTRY, self.registry)

    def save_current_task(self):
        raw = self.put(self.task_path, self.task)
        self.row["specification"] = binding.pin(self.task_path, raw)

    def save_reproduction(self):
        name = self.home + "/" + binding.REPRODUCTION
        self.row["paper_outcomes"]["reproduction_contract"] = binding.pin(name, self.put(name, self.reproduction))

    def save_outcomes(self):
        name = self.home + "/" + binding.OUTCOMES
        self.row["paper_outcomes"]["outcomes"] = binding.pin(name, self.put(name, self.outcomes))

    def sync_enrollment(self):
        self.current["packages"][0]["registered_task"].update(
            self.row["specification"], paper_outcomes=copy.deepcopy(self.row["paper_outcomes"]))
        self.put(self.current_path, self.current)

    def check(self):
        return checker.check(self.root)

    def reject(self, message):
        with self.assertRaisesRegex(ValueError, message):
            self.check()

    def plan(self):
        return refresh.build_outputs(self.root, update_workflows=False)

    def apply_metadata(self):
        outputs, changes = self.plan()
        for name, raw in outputs.items():
            self.put(name, raw)
        return outputs, changes

    def test_three_definition_chain_preserves_original_source_without_execution(self):
        result = self.check()
        self.assertEqual(result["status"], "source_integrity_passed")
        self.assertFalse(result["benchmark_execution"])
        self.assertEqual(result["packages"][0]["changed_files"], 0)
        self.assertEqual(self.read(self.history_path), self.original_bytes)
        self.assertEqual(self.read(self.home + "/" + binding.HISTORY), self.prior_task_bytes)
        self.assertNotEqual(self.original_bytes, self.prior_task_bytes)
        self.assertNotEqual(self.prior_task_bytes, self.read(self.task_path))
        self.assertEqual(self.row["specification_revision"], self.prior_row["specification_revision"])

    def test_missing_enrolled_outcome_descriptor_is_rejected(self):
        del self.current["packages"][0]["registered_task"]["paper_outcomes"]
        self.put(self.current_path, self.current)
        self.reject("enrolled paper outcome registration")

    def test_stale_enrolled_descriptor_is_rejected(self):
        self.current["packages"][0]["registered_task"]["paper_outcomes"]["outcomes"]["sha256"] = "0" * 64
        self.put(self.current_path, self.current)
        self.reject("enrolled paper outcome registration")

    def test_unpinned_pre_outcomes_bytes_are_rejected(self):
        self.put(self.home + "/" + binding.HISTORY, self.prior_task_bytes + b" ")
        self.reject("Pre-outcomes definition source hash or length mismatch")

    def test_rehashed_archive_cannot_replace_immutable_prior_registry_identity(self):
        path = self.home + "/" + binding.HISTORY
        raw = self.put(path, self.prior_task_bytes + b" ")
        self.row["paper_outcomes"]["previous_specification"] = binding.pin(path, raw)
        self.save_registry()
        self.sync_enrollment()
        self.reject("Pre-outcomes definition differs from immutable prior registry")

    def test_rehashed_previous_current_cannot_bypass_original_lineage_checks(self):
        self.prior_task["evaluation"]["reproduction_role"] = "qualified_reproduction"
        previous_path = self.home + "/" + binding.HISTORY
        raw = self.put(previous_path, self.prior_task)
        self.prior_row["specification"] = binding.pin(self.task_path, raw)
        self.row["paper_outcomes"]["previous_specification"] = binding.pin(previous_path, raw)
        snapshot = self.put(binding.SNAPSHOT, self.prior_registry)
        self.registry["paper_outcomes"]["pre_outcomes_registry"] = binding.pin(binding.SNAPSHOT, snapshot)
        self.task = binding.project_task(self.prior_task, self.prior_row, self.improvement)
        self.save_current_task()
        self.outcomes["original_task_sha256"] = self.row["specification"]["sha256"]
        self.save_outcomes()
        self.save_registry()
        self.sync_enrollment()
        self.reject("Current paper task is not bound to its improvement contract")

    def test_rehashed_current_scientific_change_is_not_a_wording_projection(self):
        self.task["input_assets"] = {"replacement_cohort": "invented substitute"}
        self.save_current_task()
        self.outcomes["original_task_sha256"] = self.row["specification"]["sha256"]
        self.save_outcomes()
        self.save_registry()
        self.sync_enrollment()
        self.reject("deterministic dual-outcome projection")

    def test_outcome_descriptor_must_bind_raw_current_not_prior_task(self):
        self.outcomes["original_task_sha256"] = self.prior_row["specification"]["sha256"]
        self.save_outcomes()
        self.save_registry()
        self.sync_enrollment()
        self.reject("bind the raw current task identity")

    def test_rehashed_reproduction_bytes_do_not_excuse_stale_canonical_contract_digest(self):
        self.reproduction["findings"][0]["expected"] = 81.0
        self.save_reproduction()
        self.save_registry()
        self.sync_enrollment()
        self.reject("Invalid paper outcome contracts")

    def test_missing_global_coverage_fails_closed(self):
        del self.registry["paper_outcomes"]
        self.save_registry()
        self.reject("require coverage metadata")

    def test_new_objective_cannot_be_hidden_by_removing_all_outcome_metadata(self):
        del self.registry["paper_outcomes"]
        del self.row["paper_outcomes"]
        del self.current["packages"][0]["registered_task"]["paper_outcomes"]
        self.save_registry()
        self.put(self.current_path, self.current)
        self.reject("enrolled paper outcome registration")

    def test_only_registry_snapshot_may_use_existing_larger_registry_bound(self):
        self.prior_registry["invented_padding"] = "x" * checker.MEMBER_LIMIT
        raw = self.put(binding.SNAPSHOT, self.prior_registry)
        self.assertGreater(len(raw), checker.MEMBER_LIMIT)
        self.assertLess(len(raw), checker.REGISTRY_LIMIT)
        self.registry["paper_outcomes"]["pre_outcomes_registry"] = binding.pin(binding.SNAPSHOT, raw)
        self.save_registry()
        self.assertEqual(self.check()["status"], "source_integrity_passed")
        ordinary = self.home + "/oversized-metadata.json"
        raw = self.put(ordinary, {"padding": "x" * checker.MEMBER_LIMIT})
        with self.assertRaisesRegex(checker.InvalidSource, "Invalid .* extent"):
            checker.outcome_read_pin(checker.Reader(self.root), binding.pin(ordinary, raw), "Ordinary member")

    def test_refresher_adds_current_bindings_preserves_both_histories_and_is_idempotent(self):
        self.put(self.current_path, self.prior_current)
        prior_manifest = self.read(self.home + "/implementations/registered-runtime/manifest.json")
        outputs, changes = self.apply_metadata()
        self.assertEqual(set(outputs), {self.current_path, self.closure_path})
        current = self.load(self.current_path)["packages"][0]
        previous = self.prior_current["packages"][0]
        for field in ("files", "historical_inventory"):
            self.assertEqual(current[field], previous[field])
        for field in ("original_path", "predecessor", "specification_revision"):
            self.assertEqual(current["registered_task"][field], previous["registered_task"][field])
        self.assertEqual(current["registered_task"]["paper_outcomes"], self.row["paper_outcomes"])
        closure = self.load(self.closure_path)
        original_pin = self.row["specification_revision"]["previous_specification"]
        self.assertEqual(closure["files"], [original_pin])
        lineage = closure["paper_specification_revisions"][0]
        self.assertEqual(lineage["role"], "calibration_only")
        self.assertEqual(lineage["historical_specification"], original_pin)
        self.assertEqual(lineage["current_specification"], self.row["specification"])
        self.assertEqual(lineage["paper_outcomes"], self.row["paper_outcomes"])
        self.assertEqual(changes[0]["paper_tasks"], [self.identifier])
        self.assertEqual(self.read(self.history_path), self.original_bytes)
        self.assertEqual(self.read(self.home + "/" + binding.HISTORY), self.prior_task_bytes)
        self.assertEqual(self.read(self.home + "/implementations/registered-runtime/manifest.json"), prior_manifest)
        self.assertEqual(self.plan(), ({}, []))
        self.assertEqual(self.check()["status"], "source_integrity_passed")

    def test_refresher_cannot_replace_existing_pre_outcomes_enrollment_history(self):
        self.current["packages"][0]["registered_task"]["paper_outcomes"]["previous_specification"]["sha256"] = "0" * 64
        self.put(self.current_path, self.current)
        with self.assertRaisesRegex(ValueError, "preserved pre-outcomes definition"):
            self.plan()

    def test_refresher_cannot_replace_existing_pre_outcomes_closure_history(self):
        self.apply_metadata()
        closure = self.load(self.closure_path)
        closure["paper_specification_revisions"][0]["paper_outcomes"]["previous_specification"]["sha256"] = "0" * 64
        self.put(self.closure_path, closure)
        with self.assertRaisesRegex(ValueError, "pre-outcomes closure history"):
            self.plan()

    def test_old_binder_checks_and_preserves_new_definitions_byte_for_byte(self):
        retained = {name: self.read(name) for name in (
            binding.REGISTRY, old_binder.SNAPSHOT, binding.SNAPSHOT, self.task_path,
            self.history_path, self.home + "/" + binding.HISTORY,
            self.home + "/improvement.v1.json", self.home + "/" + binding.REPRODUCTION,
            self.home + "/" + binding.OUTCOMES)}
        outputs = old_binder.build_outputs(self.root, expected_count=1)
        self.assertEqual(outputs, {name: retained[name] for name in (old_binder.SNAPSHOT, binding.REGISTRY)})
        old_binder.write_or_check(self.root, check=True, expected_count=1)
        old_binder.write_or_check(self.root, expected_count=1)
        self.assertEqual({name: self.read(name) for name in retained}, retained)

    def test_old_binder_rejects_incomplete_outcome_metadata_without_downgrading(self):
        del self.registry["paper_outcomes"]
        self.save_registry()
        before = self.read(self.task_path)
        with self.assertRaisesRegex(ValueError, "coverage metadata"):
            old_binder.write_or_check(self.root, expected_count=1)
        self.assertEqual(self.read(self.task_path), before)

    def test_old_binder_cannot_rewrite_unbound_new_objective(self):
        del self.registry["paper_outcomes"]
        del self.row["paper_outcomes"]
        self.save_registry()
        before = self.read(self.task_path)
        with self.assertRaisesRegex(ValueError, "cannot overwrite"):
            old_binder.write_or_check(self.root, expected_count=1)
        self.assertEqual(self.read(self.task_path), before)

    def reject_implementation_change(self):
        self.save_registry()
        retained = {name: self.read(name) for name in (
            binding.REGISTRY, old_binder.SNAPSHOT, binding.SNAPSHOT, self.task_path,
            self.history_path, self.home + "/" + binding.HISTORY)}
        with self.assertRaisesRegex(ValueError, "implementation"):
            old_binder.write_or_check(self.root, expected_count=1)
        self.assertEqual({name: self.read(name) for name in retained}, retained)

    def test_old_binder_rejects_removed_historical_implementation(self):
        self.registry["implementations"] = [row for row in self.registry["implementations"]
                                            if row["id"] != "paper-history"]
        self.reject_implementation_change()

    def test_old_binder_rejects_historical_owner_drift(self):
        self.registry["implementations"][0]["owner_ids"] = [self.neural_id]
        self.reject_implementation_change()

    def test_old_binder_rejects_historical_related_owner_drift(self):
        self.registry["implementations"][1]["related_task_ids"] = []
        self.reject_implementation_change()

    def test_old_binder_rejects_promoted_historical_paper_evaluation_roles(self):
        original = copy.deepcopy(self.registry["implementations"])
        for identifier in ("paper-history", "mixed-history"):
            with self.subTest(implementation=identifier):
                self.registry["implementations"] = copy.deepcopy(original)
                row = next(row for row in self.registry["implementations"] if row["id"] == identifier)
                row["evaluation_roles"][self.identifier] = "qualified_reproduction"
                self.reject_implementation_change()

    def test_old_binder_rejects_promoted_historical_paper_global_role(self):
        self.registry["implementations"][0]["role"] = "qualified_reproduction"
        self.reject_implementation_change()

    def test_old_binder_rejects_rewritten_historical_paper_scope(self):
        self.registry["implementations"][0]["scope_notes"] = "Now a qualified reproduction result"
        self.reject_implementation_change()

    def test_old_binder_rejects_rehashed_original_registry_task_identity_drift(self):
        original = self.load(old_binder.SNAPSHOT)
        original["tasks"][0]["specification_id"] = "PAPER-FORGED-ORIGINAL"
        raw = self.put(old_binder.SNAPSHOT, original)
        original_pin = binding.pin(old_binder.SNAPSHOT, raw)
        for registry in (self.registry, self.prior_registry):
            registry["paper_improvement"]["pre_improvement_registry"] = original_pin
        raw = self.put(binding.SNAPSHOT, self.prior_registry)
        snapshot_pin = binding.pin(binding.SNAPSHOT, raw)
        self.registry["paper_outcomes"]["pre_outcomes_registry"] = snapshot_pin
        enrolled = [index for index, item in enumerate(self.registry["historical_registries"])
                    if item["path"] == binding.SNAPSHOT]
        self.assertEqual(len(enrolled), 1)
        self.registry["historical_registries"][enrolled[0]] = copy.deepcopy(snapshot_pin)
        self.save_registry()
        before = self.read(self.task_path)
        with self.assertRaisesRegex(ValueError,
                "historical registry identity/pin changed: " + self.identifier + "/specification_id$"):
            old_binder.write_or_check(self.root, expected_count=1)
        self.assertEqual(self.read(self.task_path), before)

    def test_old_binder_retains_neural_roles_and_later_additive_paper_implementation(self):
        original = copy.deepcopy(self.registry["implementations"])
        later = {"id": "later-paper-evaluator", "owner_ids": [self.identifier], "related_task_ids": [],
                 "role": "improvement_evaluator", "evaluation_roles": {self.identifier: "improvement_evaluator"},
                 "scope_notes": "Invented later addition; no result is asserted"}
        self.registry["implementations"].append(later)
        self.save_registry()
        before = self.read(binding.REGISTRY)
        old_binder.write_or_check(self.root, check=True, expected_count=1)
        old_binder.write_or_check(self.root, expected_count=1)
        self.assertEqual(self.read(binding.REGISTRY), before)
        rows = self.load(binding.REGISTRY)["implementations"]
        self.assertEqual(rows, original + [later])
        self.assertEqual(rows[1]["role"], "shared_source_distribution")
        self.assertEqual(rows[1]["evaluation_roles"][self.neural_id], "active_evaluation")
        self.assertEqual(rows[2]["role"], "neural_runtime")
        self.assertEqual(rows[2]["evaluation_roles"], {self.neural_id: "active_evaluation"})
        self.assertEqual(rows[-1]["role"], "improvement_evaluator")


if __name__ == "__main__":
    unittest.main()
