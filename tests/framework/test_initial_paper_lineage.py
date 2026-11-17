"""Initial PAPER source lineage controls; no observations or models are read."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


fixture = load("initial_paper_repository_fixture", "tests/framework/test_repository_checks.py")
contract_fixture = load("initial_paper_contract_fixture", "tests/framework/test_paper_improvement.py")
checks, paper = fixture.checks, contract_fixture.paper


class InitialPaperContractTests(unittest.TestCase):
    def test_initial_contract_has_no_invented_history_and_preserves_comparison_rules(self):
        contract, result = contract_fixture.fixture()
        contract["legacy"] = {"role": "no_predecessor", "original_task": None,
                              "notes": "This is the first definition of this source-paper task."}
        contract_fixture.refreeze(contract, result)
        self.assertEqual(paper.validate_contract(contract), [])
        self.assertTrue(paper.compare(contract, result)["comparison_admitted"])
        self.assertIsNone(paper.compare(contract, result)["paper_win"])
        result["same_task"]["split"]["description"] = "A different easier split"
        self.assertFalse(paper.compare(contract, result)["comparison_admitted"])

    def test_legacy_variants_are_closed_and_cannot_mix_roles(self):
        for legacy in (
            {"role": "no_predecessor", "original_task": "historical/task.pre-improvement.v1.json", "notes": "Invalid"},
            {"role": "calibration_only", "original_task": None, "notes": "Invalid"},
            {"role": "no_predecessor", "original_task": None, "notes": "  "},
            {"role": "no_predecessor", "original_task": None, "notes": "Initial", "qualified": True},
        ):
            contract, _ = contract_fixture.fixture()
            contract["legacy"] = legacy
            with self.subTest(legacy=legacy):
                self.assertTrue(paper.validate_contract(contract))


class InitialPaperRepositoryTests(unittest.TestCase):
    @fixture.pre_endpoint_selection_fixture
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        profile = patch.object(checks, "CANONICAL_PER_TRACK", 1)
        profile.start()
        self.addCleanup(profile.stop)
        original_count = patch.object(checks, "PAPER_PRE_IMPROVEMENT_COUNT", 2)
        original_count.start()
        self.addCleanup(original_count.stop)
        self.registry = fixture.fixture(self.root)
        for row in self.registry["tasks"]:
            row["original_specification"] = {
                **row["specification"], "path": "former-source/" + row["id"] + ".json"}
        self.snapshot_path = "docs/provenance/registrations/paper-pre-improvement-v1.json"
        self.snapshot_pin = self.put(self.snapshot_path, self.registry)
        self.snapshot_bytes = (self.root / self.snapshot_path).read_bytes()
        for row in self.registry["tasks"]:
            if row["track"] == "paper":
                self.revise_historical(row)
        self.registry["paper_improvement"] = {
            "schema_version": checks.PAPER_REVISION, "objective": checks.PAPER_OBJECTIVE,
            "coverage_required": True, "registered_count": 3,
            "pre_improvement_registry": self.snapshot_pin}
        self.initial = self.add_initial("PAPER-NEW-003")
        for key in ("paper", "total", "expansion_drafts"):
            self.registry["source_counts"][key] += 1
        self.save_registry()

    def put(self, relative, value):
        pin = fixture.write_json(self.root / relative, value)
        pin["path"] = relative
        return pin

    def save_registry(self):
        self.put(checks.REGISTRY, self.registry)

    def revise_historical(self, row):
        directory = row["task_directory"]
        original = (self.root / row["specification"]["path"]).read_bytes()
        history = directory + "/historical/task.pre-improvement.v1.json"
        path = self.root / history
        path.parent.mkdir(parents=True)
        path.write_bytes(original)
        previous = {"path": history, "bytes": len(original), "sha256": hashlib.sha256(original).hexdigest()}
        contract = self.put(directory + "/improvement.v1.json", {
            "schema_version": checks.PAPER_REVISION, "task_id": row["id"],
            "objective": checks.PAPER_OBJECTIVE, "disposition": "source_unresolved",
            "legacy": {"role": "calibration_only", "original_task": "historical/task.pre-improvement.v1.json"}})
        row["specification_revision"] = {"version": checks.PAPER_REVISION,
                                          "previous_specification": previous, "improvement_contract": contract}
        row.update(scientific_readiness="source_unresolved", submission_readiness="not_qualified_by_binding")
        row["specification"] = self.put(row["specification"]["path"], {
            "id": row["id"], "track": "paper", "objective": checks.PAPER_OBJECTIVE,
            "status": "source_unresolved", "evaluation": {"objective": checks.PAPER_OBJECTIVE,
                "contract": contract, "disposition": "source_unresolved", "reproduction_role": "calibration_only",
                "calibration": {"historical_task": previous}}})

    def add_initial(self, identifier):
        directory = "benchmarks/paper/" + identifier
        contract, _ = contract_fixture.fixture()
        contract.update(task_id=identifier, disposition="source_unresolved",
                        blocking_issues=["Authentic native baseline qualification is not supplied by this fixture."])
        contract["legacy"] = {"role": "no_predecessor", "original_task": None,
                              "notes": "First source-paper benchmark definition; no earlier calibration task."}
        contract_pin = self.put(directory + "/improvement.v1.json", contract)
        specification = self.put(directory + "/task.json", {
            "id": identifier, "track": "paper", "objective": checks.PAPER_OBJECTIVE, "status": "source_unresolved",
            "evaluation": {"objective": checks.PAPER_OBJECTIVE, "contract": contract_pin,
                           "disposition": "source_unresolved", "reproduction_role": "not_applicable"},
            "admission": {"runnable": False, "research_qualified": False, "submission_ready": False}})
        snapshot_path = "docs/provenance/registrations/paper-initial/" + identifier + ".json"
        snapshot = self.put(snapshot_path, {
            "schema_version": checks.PAPER_INITIAL_REVISION, "task_id": identifier,
            "source_commit": "a" * 40, "specification": specification, "improvement_contract": contract_pin})
        (self.root / directory / "README.md").write_text("# Initial task source\n")
        row = {"id": identifier, "track": "paper", "task_directory": directory,
               "specification_id": identifier, "specification_alias": False, "registration_class": "expansion",
               "specification": specification, "original_specification": copy.deepcopy(specification),
               "registry": snapshot_path, "scientific_readiness": "source_unresolved",
               "submission_readiness": "not_qualified_by_binding", "runtime_manifest": None, "runtime_package": None,
               "specification_revision": {"version": checks.PAPER_INITIAL_REVISION,
                   "improvement_contract": contract_pin, "initial_registration": snapshot}}
        self.registry["tasks"].append(row)
        self.registry["historical_registries"].append(snapshot)
        return row

    def rebind_initial(self, *, mutate_task=None, mutate_contract=None, mutate_snapshot=None):
        row = self.initial
        revision = row["specification_revision"]
        document = json.loads((self.root / row["specification"]["path"]).read_bytes())
        if mutate_contract is not None:
            contract = json.loads((self.root / revision["improvement_contract"]["path"]).read_bytes())
            mutate_contract(contract)
            revision["improvement_contract"] = self.put(revision["improvement_contract"]["path"], contract)
            document["evaluation"]["contract"] = revision["improvement_contract"]
        if mutate_task is not None:
            mutate_task(document)
        row["specification"] = self.put(row["specification"]["path"], document)
        row["original_specification"] = copy.deepcopy(row["specification"])
        snapshot_path = revision["initial_registration"]["path"]
        snapshot = json.loads((self.root / snapshot_path).read_bytes())
        snapshot.update(specification=row["specification"], improvement_contract=revision["improvement_contract"])
        if mutate_snapshot is not None:
            mutate_snapshot(snapshot)
        revision["initial_registration"] = self.put(snapshot_path, snapshot)
        self.registry["historical_registries"] = [
            revision["initial_registration"] if item["path"] == snapshot_path else item
            for item in self.registry["historical_registries"]]
        self.save_registry()

    def build(self):
        return checks.check_repository(self.root, write=True)

    def test_initial_source_is_owned_without_fake_history_or_qualification(self):
        result = self.build()
        self.assertEqual(result["paper"], 3)
        self.assertFalse(result["scientific_execution"])
        self.assertFalse(result["scientific_qualification"])
        self.assertFalse((self.root / self.initial["task_directory"] / "historical").exists())
        self.assertEqual((self.root / self.snapshot_path).read_bytes(), self.snapshot_bytes)
        records = {row["path"]: row for row in json.loads((self.root / checks.INVENTORY).read_bytes())["files"]}
        revision = self.initial["specification_revision"]
        self.assertEqual(records[revision["initial_registration"]["path"]]["owner"], "registration-provenance")
        self.assertEqual(records[revision["improvement_contract"]["path"]]["owner"], "task:" + self.initial["id"])
        self.assertEqual(checks.check_repository(self.root)["source_check"], "passed")

    def test_historical_id_cannot_be_relabelled_initial_even_with_rehashed_documents(self):
        row = next(row for row in self.registry["tasks"] if row["id"] == "PAPER-002")
        self.registry["tasks"].remove(row)
        replacement = self.add_initial("PAPER-002")
        self.assertEqual(replacement["original_specification"], replacement["specification"])
        self.save_registry()
        with self.assertRaisesRegex(ValueError, "original paper roster count|restricted to new task identities"):
            self.build()

    def test_changing_snapshot_track_cannot_reclassify_an_old_id_as_new(self):
        row = next(row for row in self.registry["tasks"] if row["id"] == "PAPER-002")
        self.registry["tasks"].remove(row)
        self.add_initial("PAPER-002")
        snapshot = json.loads(self.snapshot_bytes)
        next(row for row in snapshot["tasks"] if row["id"] == "PAPER-002")["track"] = "neural"
        next(row for row in snapshot["tasks"] if row["id"] == "NEURAL-002")["track"] = "paper"
        # Even a rehashed track swap preserving the original census cannot make this ID new.
        self.registry["paper_improvement"]["pre_improvement_registry"] = self.put(self.snapshot_path, snapshot)
        self.save_registry()
        with self.assertRaisesRegex(ValueError, "restricted to new task identities"):
            self.build()

    def test_snapshot_track_count_tampering_is_rejected(self):
        snapshot = json.loads(self.snapshot_bytes)
        snapshot["source_counts"]["paper"] = True
        self.registry["paper_improvement"]["pre_improvement_registry"] = self.put(self.snapshot_path, snapshot)
        self.save_registry()
        with self.assertRaisesRegex(ValueError, "roster counts disagree"):
            self.build()

    def test_rehashed_snapshot_removal_cannot_reset_an_old_id_as_new(self):
        row = next(row for row in self.registry["tasks"] if row["id"] == "PAPER-002")
        self.registry["tasks"].remove(row)
        self.add_initial("PAPER-002")
        snapshot = json.loads(self.snapshot_bytes)
        snapshot["tasks"] = [row for row in snapshot["tasks"] if row["id"] != "PAPER-002"]
        for key in ("paper", "total", "expansion_drafts"):
            snapshot["source_counts"][key] -= 1
        self.registry["paper_improvement"]["pre_improvement_registry"] = self.put(self.snapshot_path, snapshot)
        self.save_registry()
        with self.assertRaisesRegex(ValueError, "original paper roster count"):
            self.build()

    def test_rehashed_initial_snapshot_cannot_change_original_identity(self):
        self.rebind_initial(mutate_snapshot=lambda doc: doc.update(task_id="PAPER-OTHER"))
        with self.assertRaisesRegex(ValueError, "identity or first-definition"):
            self.build()

    def test_current_definition_cannot_drift_without_matching_first_snapshot(self):
        path = self.initial["specification"]["path"]
        document = json.loads((self.root / path).read_bytes())
        document["title"] = "A later changed task definition"
        self.initial["specification"] = self.put(path, document)
        self.initial["original_specification"] = copy.deepcopy(self.initial["specification"])
        self.save_registry()
        with self.assertRaisesRegex(ValueError, "first-definition binding"):
            self.build()

    def test_initial_snapshot_must_be_exactly_enrolled(self):
        self.registry["historical_registries"].clear()
        self.save_registry()
        with self.assertRaisesRegex(ValueError, "not exactly enrolled"):
            self.build()

    def test_initial_profile_rejects_fake_calibration_and_admission(self):
        original = copy.deepcopy(self.registry)
        raw = {path.relative_to(self.root).as_posix(): path.read_bytes()
               for path in self.root.rglob("*.json")}
        mutations = (
            lambda d: d["evaluation"].update(calibration={"historical_task": {}}),
            lambda d: d["evaluation"].update(reproduction_role="calibration_only"),
            lambda d: d["admission"].update(runnable=True),
            lambda d: d["admission"].update(research_qualified=True),
            lambda d: d["admission"].update(submission_ready=True),
        )
        for index, mutation in enumerate(mutations):
            with self.subTest(index=index):
                self.rebind_initial(mutate_task=mutation)
                with self.assertRaises(ValueError):
                    self.build()
                self.registry = copy.deepcopy(original)
                self.initial = self.registry["tasks"][-1]
                for path, body in raw.items():
                    (self.root / path).write_bytes(body)

    def test_initial_legacy_cannot_claim_a_historical_predecessor(self):
        self.rebind_initial(mutate_contract=lambda d: d.update(legacy={
            "role": "calibration_only", "original_task": "historical/task.pre-improvement.v1.json", "notes": "Fake"}))
        with self.assertRaisesRegex(ValueError, "must declare no predecessor"):
            self.build()

    def test_old_revised_contract_still_requires_historical_calibration_role(self):
        row = self.registry["tasks"][0]
        revision = row["specification_revision"]
        contract = json.loads((self.root / revision["improvement_contract"]["path"]).read_bytes())
        contract["legacy"] = {"role": "no_predecessor", "original_task": None, "notes": "Forged reset"}
        revision["improvement_contract"] = self.put(revision["improvement_contract"]["path"], contract)
        self.save_registry()
        with self.assertRaisesRegex(ValueError, "historical binding mismatch"):
            self.build()

    def test_initial_requires_preserved_historical_roster_and_coverage(self):
        self.registry.pop("paper_improvement")
        self.save_registry()
        with self.assertRaisesRegex(ValueError, "complete paper coverage"):
            self.build()

    def test_rehashed_old_registry_pin_drift_is_rejected(self):
        snapshot = json.loads(self.snapshot_bytes)
        snapshot["tasks"][0]["original_specification"]["sha256"] = "b" * 64
        self.registry["paper_improvement"]["pre_improvement_registry"] = self.put(self.snapshot_path, snapshot)
        self.save_registry()
        with self.assertRaisesRegex(ValueError, "changed historical paper lineage"):
            self.build()

    def test_initial_identity_and_snapshot_paths_are_closed(self):
        self.initial["specification_alias"] = True
        self.initial["specification_id"] = "OLD-ID"
        self.save_registry()
        with self.assertRaises(ValueError):
            self.build()


if __name__ == "__main__":
    unittest.main()
