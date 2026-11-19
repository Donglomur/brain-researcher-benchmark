"""Generated initial-registration controls for the SMC successor binding.

The scientific documents and approved identity table are invented in this test
process. They do not reproduce any SMC finding. Real accepted source identities
are independently checked outside these hermetic tests. Task sources raise if
executed, and the initial roster size is reduced only in the fixture checker.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
pre_endpoint_selection_fixture = runpy.run_path(
    str(ROOT / "tests/framework/test_catalog.py"))["pre_endpoint_selection_fixture"]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    exec(compile(path.read_bytes(), str(path), "exec"), result.__dict__)
    return result


binder = module("_successor_binding_controls", ROOT / "scripts/maintenance/bind_paper_outcomes.py")
binding = binder.binding
source_integrity = module("_successor_source_controls", ROOT / "src/neurobench/source_integrity.py")
scientific = runpy.run_path(str(ROOT / "tests/framework/test_paper_reproduction.py"))


class SuccessorFixture(unittest.TestCase):
    """Reusable tiny initial-registration fixture for metadata and view tests."""

    @pre_endpoint_selection_fixture
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="invented-smc-primary-binding-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.identifier = binding.PRIMARY_SUCCESSOR_TASK
        self.home = "benchmarks/paper/" + self.identifier
        self.task_path = self.home + "/task.json"
        self.history = self.home + "/" + binding.HISTORY
        self.module = binding.primary_successor_module()
        reproduction, old, self.outcomes, _, _ = scientific["fixture"]()
        for document in (reproduction, old, self.outcomes):
            document["task_id"] = self.identifier
        old["legacy"] = {"role": "no_predecessor", "original_task": None,
                         "notes": "Invented initial policy with no older benchmark."}
        old["disposition"] = "design_ready"
        old["blocking_issues"] = ["Generated metadata cannot qualify a scientific run."]
        self.old = old
        self.primary = copy.deepcopy(old)
        self.primary["same_task"]["inputs"]["description"] = "Invented reviewed full-window primary inputs"
        self.primary["same_task"]["target"]["description"] = "Invented reviewed current primary target"
        for key, value in self.primary["same_task"].items():
            reproduction["same_task"][key] = copy.deepcopy(value)
        reproduction["eligibility"] = "source_unresolved"
        reproduction["blocking_issues"] = ["Generated metadata is not a real source recovery."]
        self.reproduction = reproduction
        self.old_pin = self.put_pin(self.home + "/improvement.v1.json", old)
        old_scientific = {"scope": "Invented initial scientific declaration"}
        self.old_scientific_pin = self.put_pin(self.home + "/docs/scientific-contract.json", old_scientific)
        self.prior_task = {
            "schema_version": 1, "id": self.identifier, "track": "paper", "title": "Invented initial SMC policy",
            "status": "design_ready", "objective": "surpass_source_paper_same_task",
            "scientific_question": "Invented retained question", "paper_identity": copy.deepcopy(old["source_paper"]),
            "official_code": {"url": "https://example.invalid/invented-source"},
            "primary_outputs": ["Invented author-restricted output"],
            "input_assets": {"observation_boundary": "Invented retained access", "target_exposure": "Invented disclosure"},
            "allowed_candidate_methods": "Invented retained methods",
            "evaluation": {"objective": "surpass_source_paper_same_task", "contract": self.old_pin,
                           "disposition": "design_ready", "reproduction_role": "not_applicable"},
            "resources": {"native_baseline_protocol": "Invented unchanged author protocol", "participant_budget": None},
            "holds": ["Invented retained hold"], "next_implementation_action": "Invented previous next action",
            "provenance": {"scientific_contract": self.old_scientific_pin, "registration_role": "Initial source task"},
            "admission": {"runnable": False, "research_qualified": False, "submission_ready": False},
        }
        self.prior_task_bytes = self.put(self.task_path, self.prior_task)
        task_pin = binding.pin(self.task_path, self.prior_task_bytes)
        registration_path = "docs/provenance/registrations/paper-initial/" + self.identifier + ".json"
        self.registration_pin = self.put_pin(registration_path, {
            "schema_version": "paper-improvement/initial-v1", "task_id": self.identifier,
            "source_commit": "a" * 40, "specification": task_pin, "improvement_contract": self.old_pin})
        self.prior_row = self.row(self.prior_task, task_pin, registration_path, "expansion")
        self.prior_row.update(
            original_specification=copy.deepcopy(task_pin), scientific_readiness="design_ready",
            submission_readiness="not_qualified_by_binding",
            specification_revision={"version": "paper-improvement/initial-v1", "improvement_contract": self.old_pin,
                                    "initial_registration": self.registration_pin},
            documentation=[{"label": "Retained original scientific declaration", "path": self.old_scientific_pin["path"]}])
        neural = {key: {} for key in ("input_assets", "evaluation", "resources", "provenance")}
        neural.update(schema_version=1, id="NEURAL-INVENTED", track="neural", title="Invented prior neural task",
                      status="specification_only", primary_outputs=[], holds=[], next_implementation_action="none",
                      admission={"runnable": False, "research_qualified": False})
        neural_pin = self.put_pin("benchmarks/neural/NEURAL-INVENTED/task.json", neural)
        neural_row = self.row(neural, neural_pin, None, "canonical")
        neural_row["original_specification"] = copy.deepcopy(neural_pin)
        prior_registration = {"schema_version": 1, "kind": "neuroscience_benchmark_registry",
                              "source_counts": {"paper": 0, "neural": 1, "total": 1,
                                                "canonical_specifications": 1, "expansion_drafts": 0},
                              "tasks": [neural_row]}
        pre_pin = self.put_pin("docs/provenance/registrations/paper-pre-improvement-v1.json", prior_registration)
        self.prior_registry = {
            "schema_version": 1, "kind": "neuroscience_benchmark_registry", "source_commit": "a" * 40,
            "source_counts": {"paper": 1, "neural": 1, "total": 2, "canonical_specifications": 1,
                              "expansion_drafts": 1, "runtime_manifests": 0, "linked_runtime_manifests": 0,
                              "source_components": 0},
            "paper_improvement": {"schema_version": "paper-improvement/v1",
                                  "objective": "surpass_source_paper_same_task", "coverage_required": True,
                                  "registered_count": 1, "pre_improvement_registry": pre_pin},
            "tasks": [self.prior_row, neural_row], "historical_registries": [pre_pin, self.registration_pin],
            "implementations": [], "shared_contracts": [], "components": [],
        }
        self.put(binding.REGISTRY, self.prior_registry)
        count_patch = mock.patch.object(binder.checker, "PAPER_PRE_IMPROVEMENT_COUNT", 0)
        count_patch.start()
        self.addCleanup(count_patch.stop)
        # Source selectors in this fixture reference inert generated files with
        # their own actual hashes. No genuine source identity is impersonated.
        for function in ("candidate_interface", "author_reproduction_routes"):
            route = getattr(self.module, function)()
            for key, value in route.items():
                if type(value) is dict and set(value) == {"path", "bytes", "sha256"}:
                    data = (b'{"invented": "not executable scientific policy"}\n' if value["path"].endswith(".json") else
                            b'raise AssertionError("Generated task source must never execute")\n')
                    route[key] = self.put_pin(value["path"], data)
            patcher = mock.patch.object(self.module, function, return_value=route)
            patcher.start()
            self.addCleanup(patcher.stop)
        replacements = {pointer: "Invented reviewed correction " + pointer for pointer in self.module.FIELDS}
        replacements["/primary_outputs"] = ["Invented reproduction output", "Invented offline improvement output"]
        replacements["/holds"] = ["Invented unresolved offline source qualification"]
        proposal = {"schema": "smc-temporal-task-projection-proposal/v1", "task_id": self.identifier,
                    "base_task_raw_sha256": task_pin["sha256"], "field_replacements": replacements}
        self.documents = {"previous_task": self.prior_task, "previous_improvement": self.old,
                          "previous_scientific": old_scientific, "primary_improvement": self.primary,
                          "primary_scientific": {"scope": "Invented reviewed scientific successor"},
                          "reproduction": self.reproduction, "projection": proposal}
        table = {}
        for name, document in self.documents.items():
            suffix = self.module._APPROVED[name][0]
            data = binding.encode(document)
            table[name] = (suffix, len(data), hashlib.sha256(data).hexdigest(), self.module._digest(document))
            if name != "previous_task":
                self.put(self.home + "/" + suffix, data)
        table_patch = mock.patch.object(self.module, "_APPROVED", table)
        table_patch.start()
        self.addCleanup(table_patch.stop)
        decision = "Invented explicit policy decision for generated metadata controls.\n"
        decision_patch = mock.patch.object(self.module, "ROOT_DECISION", (len(decision.encode()), hashlib.sha256(decision.encode()).hexdigest()))
        decision_patch.start()
        self.addCleanup(decision_patch.stop)
        self.revision_pin = self.put_pin(self.module.DESCRIPTOR, self.module.descriptor(decision))
        self.primary_pin = self.module._pin("primary_improvement")
        self.reproduction_pin = self.module._pin("reproduction")
        def planned(pin, label):
            if pin["path"] == self.history:
                self.assertEqual(pin, binding.pin(self.history, self.prior_task_bytes))
                return copy.deepcopy(self.prior_task)
            return self.read_pin(pin, label)
        selected = self.module.authenticate(revision_pin=self.revision_pin, primary_pin=self.primary_pin,
            reproduction_pin=self.reproduction_pin, previous_pin=self.module._pin("previous_task"),
            retained_improvement_pin=self.old_pin, read_pin=planned)
        self.projected = self.module.project(binding.project_task(self.prior_task, self.prior_row, self.primary), selected)
        self.outcomes["original_task_sha256"] = binding.pin(self.task_path, binding.encode(self.projected))["sha256"]
        self.outcomes["contracts"] = {"reproduction": binding.engine().contract_digest(self.reproduction),
                                      "improvement": binding.engine().contract_digest(self.primary)}
        self.outcomes["pairing"] = {name: {"status": "unresolved", "rationale": "Invented metadata only", "protocol": None}
                                    for name in ("reproduction", "improvement")}
        self.put(self.home + "/" + binding.OUTCOMES, self.outcomes)
        self.assertEqual(binding.engine().outcomes_validate(self.outcomes, self.reproduction, self.primary), [])
        self.before = self.snapshot()

    def row(self, doc, task_pin, registration, classification):
        return {"id": doc["id"], "title": doc["title"], "track": doc["track"],
                "task_directory": str(Path(task_pin["path"]).parent), "specification_id": doc["id"],
                "specification_alias": False, "registration_class": classification,
                "registration_stage": "registered_construction_draft" if registration else "canonical_source_specification",
                "registry": registration, "track_source": "registry" if registration else "canonical_specification",
                "declared_specification_status": doc["status"], "specification": task_pin,
                "scientific_readiness": "unknown", "submission_readiness": "unknown",
                "runtime_manifest": None, "runtime_package": None, "runtime_manifest_status": None}

    def put(self, relative, value):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        data = value if isinstance(value, bytes) else binding.encode(value)
        path.write_bytes(data)
        return data

    def put_pin(self, relative, value):
        return binding.pin(relative, self.put(relative, value))

    def load(self, relative):
        return json.loads((self.root / relative).read_bytes())

    def read_pin(self, pin, label):
        return binder.read_pinned(binder.checker.Reader(self.root), pin, label)

    def snapshot(self):
        return {path.relative_to(self.root).as_posix(): path.read_bytes()
                for path in self.root.rglob("*") if path.is_file() and not path.is_symlink()}

    def adopt(self):
        return binder.write_or_check(self.root, write=True)

    def context(self):
        registry = self.load(binding.REGISTRY)
        row = registry["tasks"][0]
        reader = binder.checker.Reader(self.root)
        read = lambda pin, label: binder.read_pinned(reader, pin, label)
        previous = binding.coverage(registry, read)
        return row, binding.context(row, self.load(self.task_path), previous, read)

    def reject_without_writes(self, pattern=None):
        before = self.snapshot()
        with self.assertRaisesRegex((ValueError, OSError), pattern or "."):
            binder.write_or_check(self.root, write=True)
        self.assertEqual(self.snapshot(), before)


class PrimarySuccessorBindingTests(SuccessorFixture):
    def test_plan_serves_only_exact_pending_archive_without_writing(self):
        self.assertFalse((self.root / self.history).exists())
        outputs, report = binder.build_outputs(self.root)
        self.assertEqual(self.snapshot(), self.before)
        self.assertEqual(set(outputs), {binding.REGISTRY, binding.SNAPSHOT, self.task_path, self.history})
        self.assertEqual(outputs[self.history], self.prior_task_bytes)
        self.assertEqual(outputs[self.task_path], binding.encode(self.projected))
        self.assertFalse(report["scientific_qualification"])

    def test_initial_lineage_current_policy_and_idempotence_are_distinct(self):
        self.adopt()
        row, context = self.context()
        self.assertEqual(context["improvement_contract"], self.primary)
        self.assertEqual(context["retained_improvement_contract"], self.old)
        self.assertEqual(row["title"], self.projected["title"])
        self.assertEqual(context["previous_row"]["title"], self.prior_row["title"])
        self.assertEqual(row["specification_revision"], self.prior_row["specification_revision"])
        self.assertEqual(row["original_specification"], self.prior_row["original_specification"])
        self.assertEqual(self.load(binding.SNAPSHOT), self.prior_registry)
        self.assertEqual((self.root / self.history).read_bytes(), self.prior_task_bytes)
        self.assertEqual(self.load(self.old_pin["path"]), self.old)
        self.assertEqual(binder.validate_existing(self.root)["registered_tasks"], 2)
        after = self.snapshot()
        self.assertEqual(binder.write_or_check(self.root, check=True)["changed_files"], 0)
        self.assertEqual(self.adopt()["changed_files"], 0)
        self.assertEqual(self.snapshot(), after)

    def test_source_integrity_context_authenticates_current_and_prior_documents(self):
        self.adopt()
        row = self.load(binding.REGISTRY)["tasks"][0]
        result = source_integrity.outcome_context(source_integrity.Reader(self.root), row, self.load(self.task_path))
        self.assertEqual(result["previous_document"], self.prior_task)
        self.assertEqual(result["improvement_contract"], self.primary)
        self.assertEqual(result["retained_improvement_contract"], self.old)

    def test_current_summary_and_new_metadata_members_have_exact_roles(self):
        self.adopt()
        row, context = self.context()
        public = binding.public_summary(row, context)
        self.assertEqual(public["improvement_contract"], self.primary_pin)
        self.assertEqual(public["retained_improvement_contract"], self.old_pin)
        self.assertEqual(public["retained_improvement_role"], "retained_pre_outcomes_policy")
        self.assertEqual(public["candidate_interface"]["role"], "primary_offline_candidate")
        self.assertEqual(public["author_reproduction_routes"]["role"], "author_source_reproduction_and_calibration")
        self.assertEqual(public["primary_policy_provenance"]["projection"], self.module._pin("projection"))
        self.assertTrue(all(cell["scientific_outcome"] == "unknown" and cell["receipt"] is None
                            and not cell["endpoint_eligible"] for cell in public["cells"]))
        expected = {self.history, self.home + "/outcomes.v1.json", self.reproduction_pin["path"],
                    self.module.DESCRIPTOR, self.module.PROJECTION, self.primary_pin["path"],
                    self.module._pin("primary_scientific")["path"]}
        self.assertEqual(context["members"], expected)
        initial_members = binder.checker.paper_initial_members(binder.checker.Reader(self.root),
            context["previous_row"], context["previous_document"], archived_definition_pin=context["previous_pin"])
        self.assertFalse(initial_members & context["members"])
        self.assertFalse({item["path"] for item in row["documentation"]} & context["members"])

    def test_missing_public_successor_is_not_a_legacy_fallback(self):
        (self.root / self.module.DESCRIPTOR).unlink()
        self.reject_without_writes("Missing source path")

    def test_initial_changed_descriptor_or_policy_is_rejected_before_writes(self):
        descriptor = self.load(self.module.DESCRIPTOR)
        descriptor["scientific_outcome"] = "qualified"
        self.put(self.module.DESCRIPTOR, descriptor)
        self.reject_without_writes("differs from reviewed policy")

    def test_rehashed_current_policy_does_not_change_accepted_identity(self):
        changed = copy.deepcopy(self.primary)
        changed["same_task"]["inputs"]["description"] = "Unreviewed broader access"
        self.put(self.primary_pin["path"], changed)
        self.reject_without_writes("selector does not bind accepted")

    def test_adopted_selector_pair_is_mandatory_and_closed(self):
        self.adopt()
        original = self.load(binding.REGISTRY)
        for field in (*binding.PRIMARY_SUCCESSOR_FIELDS, "reproduction_contract"):
            changed = copy.deepcopy(original)
            del changed["tasks"][0]["paper_outcomes"][field]
            self.put(binding.REGISTRY, changed)
            self.reject_without_writes("require both explicit")
        changed = copy.deepcopy(original)
        changed["tasks"][0]["paper_outcomes"]["invented_policy"] = True
        self.put(binding.REGISTRY, changed)
        self.reject_without_writes("Invalid paper outcome task binding")

    def test_non_smc_task_cannot_claim_successor_selectors(self):
        selected = {"primary_policy_revision": self.revision_pin, "primary_improvement_contract": self.primary_pin,
                    "reproduction_contract": self.reproduction_pin}
        with self.assertRaisesRegex(ValueError, "restricted"):
            binding.has_primary_successor({"id": "PAPER-INVENTED-OTHER", "paper_outcomes": selected})

    def test_title_shape_exception_does_not_authorize_a_forged_current_title(self):
        self.adopt()
        registry = self.load(binding.REGISTRY)
        registry["tasks"][0]["title"] = "Unreviewed current title"
        self.put(binding.REGISTRY, registry)
        self.reject_without_writes("current title differs")

    def test_current_task_and_outcomes_cannot_rehash_an_unreviewed_title(self):
        self.adopt()
        registry = self.load(binding.REGISTRY)
        changed = self.load(self.task_path)
        changed["title"] = "Unreviewed current title"
        registry["tasks"][0]["title"] = changed["title"]
        registry["tasks"][0]["specification"] = self.put_pin(self.task_path, changed)
        outcomes = self.load(self.home + "/outcomes.v1.json")
        outcomes["original_task_sha256"] = registry["tasks"][0]["specification"]["sha256"]
        registry["tasks"][0]["paper_outcomes"]["outcomes"] = self.put_pin(self.home + "/outcomes.v1.json", outcomes)
        self.put(binding.REGISTRY, registry)
        self.reject_without_writes("current title differs")

    def test_outcomes_must_bind_final_task_and_current_policy(self):
        outcomes = copy.deepcopy(self.outcomes)
        outcomes["contracts"]["improvement"] = binding.engine().contract_digest(self.old)
        self.put(self.home + "/outcomes.v1.json", outcomes)
        self.reject_without_writes("Invalid paper outcome contracts")
        outcomes = copy.deepcopy(self.outcomes)
        outcomes["original_task_sha256"] = self.prior_row["specification"]["sha256"]
        self.put(self.home + "/outcomes.v1.json", outcomes)
        self.reject_without_writes("raw current task identity")

    def test_existing_archive_is_authenticated_and_never_replaced(self):
        self.put(self.history, self.prior_task_bytes + b" ")
        self.reject_without_writes("Refusing to replace")

    def test_existing_archive_uses_normal_authenticated_reader(self):
        self.put(self.history, self.prior_task_bytes)
        read = binder.read_pinned
        archive_reads = []
        def observed(reader, selected, label):
            if selected["path"] == self.history:
                archive_reads.append(selected)
            return read(reader, selected, label)
        with mock.patch.object(binder, "read_pinned", side_effect=observed):
            binder.build_outputs(self.root)
        self.assertGreaterEqual(len(archive_reads), 2)

    def test_existing_archive_change_during_authentication_is_not_virtualized(self):
        self.put(self.history, self.prior_task_bytes)
        authenticate = self.module.authenticate
        def mutate_then_authenticate(**kwargs):
            self.put(self.history, self.prior_task_bytes + b" ")
            return authenticate(**kwargs)
        with mock.patch.object(self.module, "authenticate", side_effect=mutate_then_authenticate):
            with self.assertRaisesRegex(ValueError, "pin mismatch"):
                binder.write_or_check(self.root, write=True)
        self.assertEqual((self.root / self.task_path).read_bytes(), self.prior_task_bytes)
        self.assertFalse((self.root / binding.SNAPSHOT).exists())

    def test_adopted_predecessor_policy_is_not_repaired_or_repointed(self):
        self.adopt()
        self.put(self.old_pin["path"], binding.encode(self.old) + b" ")
        self.reject_without_writes("pin mismatch")

    def test_optional_retained_argument_cannot_inject_the_current_policy(self):
        self.adopt()
        registry = self.load(binding.REGISTRY)
        row = registry["tasks"][0]
        previous = binding.coverage(registry, self.read_pin)
        with self.assertRaisesRegex(ValueError, "Retained improvement differs"):
            binding.context(row, self.load(self.task_path), previous, self.read_pin, improvement_contract=self.primary)

    def test_another_scope_projection_cannot_compose_with_fixed_smc_policy(self):
        self.adopt()
        registry = self.load(binding.REGISTRY)
        row = registry["tasks"][0]
        previous = binding.coverage(registry, self.read_pin)
        previous.scope_decisions = {"entries": {}, "same_primary_corrections": {self.identifier: {}}}
        with self.assertRaisesRegex(ValueError, "cannot combine"):
            binding.context(row, self.load(self.task_path), previous, self.read_pin)

    def test_binder_atomically_enrolls_exact_snapshot_and_preserves_prior_history(self):
        history_before = copy.deepcopy(self.prior_registry["historical_registries"])
        registry_before = (self.root / binding.REGISTRY).read_bytes()
        self.adopt()
        current = self.load(binding.REGISTRY)
        snapshot_pin = current["paper_outcomes"]["pre_outcomes_registry"]
        self.assertEqual(current["historical_registries"], history_before + [snapshot_pin])
        self.assertEqual((self.root / binding.SNAPSHOT).read_bytes(), registry_before)
        self.assertEqual(binder.write_or_check(self.root, check=True)["changed_files"], 0)
        self.assertEqual(self.adopt()["changed_files"], 0)
        self.assertEqual(self.load(binding.REGISTRY)["historical_registries"], history_before + [snapshot_pin])

    def test_conflicting_or_duplicate_snapshot_enrollment_is_never_repaired(self):
        self.adopt()
        original = self.load(binding.REGISTRY)
        selected = original["paper_outcomes"]["pre_outcomes_registry"]
        prior_history = [item for item in original["historical_registries"] if item["path"] != binding.SNAPSHOT]
        for entries in ([dict(selected, sha256="0" * 64)], [selected, selected],
                        [dict(selected, bytes=float(selected["bytes"]))]):
            changed = copy.deepcopy(original)
            changed["historical_registries"] = prior_history + entries
            self.put(binding.REGISTRY, changed)
            with self.subTest(entries=entries):
                self.reject_without_writes("snapshot enrollment|enrolled pre-outcomes")

    def test_missing_adopted_enrollment_fails_validation_and_plan_repairs_only_registry(self):
        self.adopt()
        current = self.load(binding.REGISTRY)
        current["historical_registries"] = [item for item in current["historical_registries"]
                                           if item["path"] != binding.SNAPSHOT]
        self.put(binding.REGISTRY, current)
        snapshot_before = (self.root / binding.SNAPSHOT).read_bytes()
        with self.assertRaisesRegex(ValueError, "snapshot enrollment"):
            binder.validate_existing(self.root)
        report = binder.write_or_check(self.root)
        self.assertEqual(report["changed_paths"], [binding.REGISTRY])
        self.assertEqual(self.adopt()["changed_paths"], [binding.REGISTRY])
        self.assertEqual((self.root / binding.SNAPSHOT).read_bytes(), snapshot_before)
        self.assertEqual(binder.validate_existing(self.root)["paper_tasks"], 1)

    def ownership_fixture(self):
        """Complete tiny source namespace with zero canonical tasks per track."""
        registry = self.load(binding.REGISTRY)
        registry["tasks"][1]["registration_class"] = "expansion"
        registry["source_counts"].update(canonical_specifications=0, expansion_drafts=2)
        pre_pin = registry["paper_improvement"]["pre_improvement_registry"]
        before = self.load(pre_pin["path"])
        before["tasks"][0]["registration_class"] = "expansion"
        before["source_counts"].update(canonical_specifications=0, expansion_drafts=1)
        registry["paper_improvement"]["pre_improvement_registry"] = self.put_pin(pre_pin["path"], before)
        # Pre-improvement provenance has its own exact ownership branch; only
        # initial registrations and the new outcome snapshot use this list.
        registry["historical_registries"] = [self.registration_pin]
        registry["implementations"] = [
            {"id": "invented-" + suffix, "path": self.home + "/implementations/" + suffix,
             "scope": "task", "owner_ids": [self.identifier], "related_task_ids": [],
             "scientific_readiness": "unknown", "role": "generated source control",
             "scope_notes": "Inert generated source; never executed."}
            for suffix in ("source-matched-nlb-v1", "offline-nlb-outcomes-v1")]
        self.put(binding.REGISTRY, registry)
        for relative in ("benchmarks/paper/README.md", "benchmarks/neural/README.md",
                         "benchmarks/shared/README.md", "benchmarks/README.md"):
            self.put(relative, b"# Generated source namespace\n")
        checks = binder.checker
        self.put(checks.CURRENT_BINDINGS, {"generated": "source identities only"})
        self.put(checks.CURRENT_CLOSURES + "/generated/binding.json", {"generated": True})
        self.put(checks.PARALLEL_CONTROL_MANIFEST, {"generated": True})
        for relative in checks.PARALLEL_CONTROL_SOURCES[1:] + checks.WORKFLOW_SYNTAX_SOURCES:
            self.put(relative, b'raise AssertionError("Generated control source must never execute")\n')
        self.put(checks.RELOCATIONS, {"schema_version": 1, "files": []})
        self.adopt()

    def test_full_source_inventory_reuses_exact_historically_enrolled_snapshot_once(self):
        self.ownership_fixture()
        checks = binder.checker
        with mock.patch.object(checks, "CANONICAL_PER_TRACK", 0):
            written = checks.check_repository(self.root, write=True)
            self.assertFalse(written["scientific_qualification"])
            self.assertEqual(checks.check_repository(self.root)["source_check"], "passed")
        registry = self.load(binding.REGISTRY)
        inventory = self.load(checks.INVENTORY)
        records = [row for row in inventory["files"] if row["path"] == binding.SNAPSHOT]
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["owner"], "registration-provenance")
        self.assertEqual({key: records[0][key] for key in ("path", "bytes", "sha256")},
                         registry["paper_outcomes"]["pre_outcomes_registry"])

    def test_inventory_rejects_missing_conflicting_duplicate_and_cross_namespace_snapshot(self):
        self.ownership_fixture()
        checks = binder.checker
        original = self.load(binding.REGISTRY)
        selected = original["paper_outcomes"]["pre_outcomes_registry"]
        old_history = [row for row in original["historical_registries"] if row["path"] != binding.SNAPSHOT]
        variants = []
        for entries in ([], [dict(selected, sha256="0" * 64)], [selected, selected],
                        [dict(selected, bytes=float(selected["bytes"]))],
                        [{"path": binding.SNAPSHOT}]):
            changed = copy.deepcopy(original)
            changed["historical_registries"] = old_history + entries
            variants.append(changed)
        shared_duplicate = copy.deepcopy(original)
        shared_duplicate["shared_contracts"].append(selected)
        variants.append(shared_duplicate)
        for index, changed in enumerate(variants):
            self.put(binding.REGISTRY, changed)
            with self.subTest(index=index), mock.patch.object(checks, "CANONICAL_PER_TRACK", 0):
                with self.assertRaises(ValueError):
                    checks.check_repository(self.root, write=True)
            self.assertFalse((self.root / checks.INVENTORY).exists())


if __name__ == "__main__":
    unittest.main()
