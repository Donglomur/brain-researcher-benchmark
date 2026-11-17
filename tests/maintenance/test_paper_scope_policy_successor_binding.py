"""Synthetic four-policy binding controls; no source or scientific execution.

Only the standalone selector's fixture identity table is replaced. The binder,
normal v2 validators, scope routing, historical checks and read paths stay real.
"""
import copy
import hashlib
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
support = runpy.run_path(str(ROOT / "tests/maintenance/test_paper_primary_successor_binding.py"))
binder, binding = support["binder"], support["binding"]
FixtureMethods = support["SuccessorFixture"]


class ScopePolicyFixture(FixtureMethods):
    @support["pre_endpoint_selection_fixture"]
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="invented-four-policy-binding-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.ids = sorted(binding.SCOPE_POLICY_SUCCESSOR_TASKS)
        self.module = binding.primary_successor_module(self.ids[0])
        self.scope = {"schema_version": binding.SCOPE_VERSION, "entries": {}, "same_primary_corrections": {}}
        for identifier in binding.SCOPE_IDS:
            self.scope["entries"][identifier] = {
                "task_id": identifier, "primary_goal": "Invented held goal", "primary_scope": "Invented held scope",
                "retained_secondary_scope": "Invented secondary", "remaining_source_limits": ["No source evidence"],
                "primary_same_task_improvement": "unavailable_until_independently_justified",
                "paired_bundle_status": "unavailable_primary_secondary_scope_mismatch", "scientific_outcome": "unknown"}
        rows, historical, self.cases, self.docs, self.projected = [], [], {}, {}, {}
        for identifier in self.ids:
            home = "benchmarks/paper/" + identifier
            reproduction, old, outcomes, _, _ = support["scientific"]["fixture"]()
            for document in (reproduction, old, outcomes):
                document["task_id"] = identifier
            old.update(disposition="design_ready" if identifier.endswith("add-010") else "source_unresolved",
                       blocking_issues=["Invented prior source gap"],
                       legacy={"role": "no_predecessor", "original_task": None, "notes": "Invented initial policy"})
            current = copy.deepcopy(old)
            current["episode"]["candidate_freeze"] = "Invented reviewed current freeze"
            current["blocking_issues"][0] = "Invented reviewed current source gap"
            reproduction.update(schema_version="paper-reproduction/v2", eligibility="source_unresolved",
                                blocking_issues=["Invented unresolved complete source panel"])
            reproduction["same_task"].update(copy.deepcopy(current["same_task"]))
            old_pin = self.put_pin(home + "/improvement.v1.json", old)
            scientific_pin = self.put_pin(home + "/docs/scientific-contract.json", {"scope": "Invented original science"})
            previous = {
                "schema_version": 1, "id": identifier, "track": "paper", "title": "Invented unchanged title " + identifier,
                "status": old["disposition"], "objective": "surpass_source_paper_same_task", "goal": "Invented old goal",
                "scientific_question": "Invented retained question", "paper_identity": copy.deepcopy(old["source_paper"]),
                "official_code": {"url": "https://example.invalid/inert-source"}, "primary_outputs": ["Invented old output"],
                "success_criteria": ["Invented previous criteria"], "input_assets": {"immutable": "Invented inputs"},
                "evaluation": {"objective": "surpass_source_paper_same_task", "contract": old_pin,
                               "disposition": old["disposition"], "reproduction_role": "not_applicable"},
                "episode": copy.deepcopy(old["episode"]), "blocking_issues": copy.deepcopy(old["blocking_issues"]),
                "resources": {"participant_budget": None}, "holds": ["Invented old hold"],
                "next_implementation_action": "Invented old action", "legacy": {"unchanged": "Invented history"},
                "provenance": {"scientific_contract": scientific_pin, "registration_role": "Initial source task"},
                "admission": {"runnable": False, "research_qualified": False, "submission_ready": False}}
            task_pin = self.put_pin(home + "/task.json", previous)
            registration = "docs/provenance/registrations/paper-initial/" + identifier + ".json"
            registration_pin = self.put_pin(registration, {"schema_version": "paper-improvement/initial-v1",
                "task_id": identifier, "source_commit": "a" * 40, "specification": task_pin, "improvement_contract": old_pin})
            row = self.row(previous, task_pin, registration, "expansion")
            row.update(original_specification=copy.deepcopy(task_pin), scientific_readiness=old["disposition"],
                submission_readiness="not_qualified_by_binding", specification_revision={
                    "version": "paper-improvement/initial-v1", "improvement_contract": old_pin,
                    "initial_registration": registration_pin}, documentation=[{"label": "Original science", "path": scientific_pin["path"]}])
            rows.append(row)
            historical.append(registration_pin)
            entry = {"task_id": identifier, "primary_goal": "Invented selected goal " + identifier,
                "primary_scope": current["same_task"]["target"]["description"], "remaining_source_limits": ["Invented full-panel gap"],
                "disposition": "same_primary_unqualified", "paired_bundle_status": "same_primary_unqualified",
                "scientific_outcome": "unknown", "adoption_route": "normal_same_primary_unqualified"}
            self.scope["same_primary_corrections"][identifier] = entry
            changes = []
            for pointer, before, after in (("/episode/candidate_freeze", old["episode"]["candidate_freeze"], current["episode"]["candidate_freeze"]),
                                           ("/blocking_issues/0", old["blocking_issues"][0], current["blocking_issues"][0])):
                changes.append({"json_pointer": pointer, "predecessor_value": before, "successor_value": after,
                    "predecessor_value_canonical_sha256": self.module._digest(before), "successor_value_canonical_sha256": self.module._digest(after)})
            delta = {"task_id": identifier, "field_replacements": changes}
            base = binding.project_task(previous, row, current, reproduction_version="paper-reproduction/v2", primary_correction=entry)
            documents = {"previous_task": previous, "previous_improvement": old,
                         "primary_improvement": current, "reproduction": reproduction}
            case = {name: self.identity(value) for name, value in documents.items()}
            case.update(descriptor=[1, "0" * 64, "0" * 64], delta_canonical=self.module._digest(delta),
                        base_projection_canonical=self.module._digest(base), scope_entry_canonical=self.module._digest(entry),
                        deltas=[x["json_pointer"] for x in changes])
            self.cases[identifier] = case
            self.docs[identifier] = {"documents": documents, "delta": delta, "base": base, "outcomes": outcomes, "row": row}
        neural = {"id": "NEURAL-INVENTED", "track": "neural", "title": "Invented retained neural task", "status": "specification_only"}
        neural_pin = self.put_pin("benchmarks/neural/NEURAL-INVENTED/task.json", neural)
        neural_row = self.row(neural, neural_pin, None, "canonical")
        neural_row["original_specification"] = copy.deepcopy(neural_pin)
        empty = {"schema_version": 1, "kind": "neuroscience_benchmark_registry",
                 "source_counts": {"paper": 0, "neural": 1, "total": 1, "canonical_specifications": 1, "expansion_drafts": 0},
                 "tasks": [neural_row]}
        pre_pin = self.put_pin("docs/provenance/registrations/paper-pre-improvement-v1.json", empty)
        self.prior_registry = {"schema_version": 1, "kind": "neuroscience_benchmark_registry", "source_commit": "a" * 40,
            "source_counts": {"paper": 4, "neural": 1, "total": 5}, "tasks": rows + [neural_row],
            "paper_improvement": {"schema_version": "paper-improvement/v1", "objective": "surpass_source_paper_same_task",
                "coverage_required": True, "registered_count": 4, "pre_improvement_registry": pre_pin},
            "historical_registries": [pre_pin] + historical, "implementations": [], "shared_contracts": [], "components": []}
        self.put(binding.REGISTRY, self.prior_registry)
        self.scope_pin = self.put_pin(binding.SCOPE_PATH, self.scope)
        for patcher in (mock.patch.object(binder.checker, "PAPER_PRE_IMPROVEMENT_COUNT", 0),
                        mock.patch.object(self.module, "_APPROVED", self.cases),
                        mock.patch.object(self.module, "SCOPE_PIN", self.scope_pin),
                        mock.patch.object(self.module, "SCOPE_CANONICAL", self.module._digest(self.scope))):
            patcher.start()
            self.addCleanup(patcher.stop)
        for identifier, item in self.docs.items():
            home = "benchmarks/paper/" + identifier
            documents = item["documents"]
            descriptor = self.module.descriptor(identifier, item["delta"])
            self.cases[identifier]["descriptor"] = self.identity(descriptor)
            documents["descriptor"] = descriptor
            pins = self.module.approved_pins(identifier)
            item["pins"] = pins
            for name in ("primary_improvement", "reproduction", "descriptor"):
                self.put(pins[name]["path"], documents[name])
            def read(pin, label):
                if pin == pins["previous_task"]:
                    return copy.deepcopy(documents["previous_task"])
                return self.read_pin(pin, label)
            selected = self.module.authenticate(task_id=identifier, revision_pin=pins["descriptor"], primary_pin=pins["primary_improvement"],
                reproduction_pin=pins["reproduction"], previous_pin=pins["previous_task"],
                retained_improvement_pin=pins["previous_improvement"], read_pin=read)
            projected = self.module.project(item["base"], selected)
            self.projected[identifier] = projected
            outcomes = item["outcomes"]
            outcomes["original_task_sha256"] = binding.pin(home + "/task.json", binding.encode(projected))["sha256"]
            outcomes["contracts"] = {"reproduction": self.module._digest(documents["reproduction"]),
                                     "improvement": self.module._digest(documents["primary_improvement"])}
            outcomes["pairing"] = {name: {"status": "unresolved", "rationale": "Invented metadata only", "protocol": None}
                                   for name in ("reproduction", "improvement")}
            self.put(home + "/outcomes.v1.json", outcomes)
            self.assertEqual(binding.engine(documents["reproduction"]).outcomes_validate(outcomes, documents["reproduction"], documents["primary_improvement"]), [])
        self.before = self.snapshot()

    def identity(self, value):
        raw = binding.encode(value)
        return [len(raw), hashlib.sha256(raw).hexdigest(), self.module._digest(value)]

    def context(self, identifier=None):
        identifier = identifier or self.ids[0]
        registry = self.load(binding.REGISTRY)
        row = next(row for row in registry["tasks"] if row["id"] == identifier)
        reader = binder.checker.Reader(self.root)
        read = lambda pin, label: binder.read_pinned(reader, pin, label)
        previous = binding.coverage(registry, read)
        return row, binding.context(row, self.load(row["specification"]["path"]), previous, read)


class ScopePolicySuccessorBindingTests(ScopePolicyFixture):
    def test_plan_authenticates_virtual_archive_only_and_writes_nothing(self):
        outputs, report = binder.build_outputs(self.root)
        self.assertEqual(self.snapshot(), self.before)
        self.assertEqual(len(outputs), 10)
        self.assertFalse(report["scientific_qualification"])
        for identifier, item in self.docs.items():
            pins = item["pins"]
            self.assertFalse((self.root / pins["previous_task"]["path"]).exists())
            self.assertEqual(outputs[pins["previous_task"]["path"]], binding.encode(item["documents"]["previous_task"]))
            self.assertEqual(outputs["benchmarks/paper/" + identifier + "/task.json"], binding.encode(self.projected[identifier]))

    def test_all_four_current_policy_retained_lineage_and_repeat_binding(self):
        self.adopt()
        for identifier, item in self.docs.items():
            with self.subTest(identifier=identifier):
                row, bound = self.context(identifier)
                self.assertEqual(bound["improvement_contract"], item["documents"]["primary_improvement"])
                self.assertEqual(bound["retained_improvement_contract"], item["documents"]["previous_improvement"])
                self.assertEqual(row["specification_revision"], item["row"]["specification_revision"])
                self.assertEqual(row["title"], item["row"]["title"])
                self.assertEqual(bound["primary_policy_provenance"], {"scope_decision": self.scope_pin})
                self.assertIsNone(bound["candidate_interface"])
                self.assertIsNone(bound["author_reproduction_routes"])
                self.assertEqual(len(bound["members"]), 5)
                public = binding.public_summary(row, bound)
                self.assertEqual(public["improvement_contract"], item["pins"]["primary_improvement"])
                self.assertEqual(public["retained_improvement_contract"], item["pins"]["previous_improvement"])
                self.assertEqual({x["scientific_outcome"] for x in public["cells"]}, {"unknown"})
                self.assertEqual(self.load(item["pins"]["previous_improvement"]["path"]), item["documents"]["previous_improvement"])
        frozen = self.snapshot()
        self.assertEqual(binder.write_or_check(self.root, check=True)["changed_files"], 0)
        self.assertEqual(self.snapshot(), frozen)

    def test_all_four_missing_or_partial_selectors_reject_including_equal_anchor_fc(self):
        self.adopt()
        registry = self.load(binding.REGISTRY)
        for row in (r for r in registry["tasks"] if r["track"] == "paper"):
            for field in binding.PRIMARY_SUCCESSOR_FIELDS | {"reproduction_contract"}:
                altered = copy.deepcopy(row)
                del altered["paper_outcomes"][field]
                with self.subTest(task=row["id"], field=field), self.assertRaises(ValueError):
                    binding.has_primary_successor(altered)
        fc = self.docs["PAPER-paper-method-add-010"]["documents"]
        self.assertEqual(fc["previous_improvement"]["same_task"], fc["primary_improvement"]["same_task"])

    def test_all_four_wrong_case_stale_and_open_selectors_reject(self):
        self.adopt()
        rows = [r for r in self.load(binding.REGISTRY)["tasks"] if r["track"] == "paper"]
        for index, row in enumerate(rows):
            for field in binding.PRIMARY_SUCCESSOR_FIELDS | {"reproduction_contract"}:
                for value in (rows[(index + 1) % 4]["paper_outcomes"][field],
                              {**row["paper_outcomes"][field], "sha256": "0" * 64},
                              {**row["paper_outcomes"][field], "extra": True}):
                    altered = copy.deepcopy(row)
                    altered["paper_outcomes"][field] = value
                    with self.subTest(task=row["id"], field=field), self.assertRaises(ValueError):
                        binding.has_primary_successor(altered)

    def test_non_four_tasks_and_smc_cannot_select_scope_policy(self):
        pin = self.docs[self.ids[0]]["pins"]
        declared = {"primary_policy_revision": pin["descriptor"], "primary_improvement_contract": pin["primary_improvement"],
                    "reproduction_contract": pin["reproduction"]}
        for identifier in ("PAPER-ORDINARY", "PAPER-SMC-RNN-2024", "NEURAL-001"):
            with self.subTest(identifier=identifier), self.assertRaises(ValueError):
                binding.has_primary_successor({"id": identifier, "paper_outcomes": declared})
        with self.assertRaises(ValueError):
            binding.primary_successor_module("../unreviewed")

    def test_four_titles_have_no_smc_deferral(self):
        self.adopt()
        registry = self.load(binding.REGISTRY)
        registry["tasks"][0]["title"] = "Changed title"
        with self.assertRaisesRegex(ValueError, "changed prior title"):
            binding.coverage(registry, self.read_pin)

    def test_missing_real_policy_metadata_never_uses_virtual_archive_read(self):
        for name in ("primary_improvement", "descriptor", "reproduction"):
            pin = self.docs[self.ids[0]]["pins"][name]
            body = (self.root / pin["path"]).read_bytes()
            (self.root / pin["path"]).unlink()
            self.reject_without_writes()
            self.put(pin["path"], body)

    def test_explicit_v2_required_and_ambiguous_reproduction_rejected(self):
        item = self.docs[self.ids[0]]
        home = "benchmarks/paper/" + self.ids[0]
        self.put(home + "/reproduction.v1.json", {**item["documents"]["reproduction"], "schema_version": "paper-reproduction/v1"})
        self.reject_without_writes("Exactly one")
        (self.root / item["pins"]["reproduction"]["path"]).unlink()
        self.reject_without_writes()

    def test_rehashed_global_authority_does_not_replace_accepted_scope(self):
        altered = copy.deepcopy(self.scope)
        altered["extra_annotation"] = "Rehashed same entries"
        self.put(binding.SCOPE_PATH, altered)
        self.reject_without_writes("exact reviewed scope authority")

    def test_missing_normal_correction_or_unavailable_route_refuses(self):
        altered = copy.deepcopy(self.scope)
        del altered["same_primary_corrections"][self.ids[0]]
        self.put(binding.SCOPE_PATH, altered)
        self.reject_without_writes("normal scope correction")
        altered = copy.deepcopy(self.scope)
        altered["same_primary_corrections"][self.ids[0]]["adoption_route"] = "full_primary_pairing_unavailable"
        self.put(binding.SCOPE_PATH, altered)
        self.reject_without_writes("normal correction map")

    def test_outcomes_must_use_current_policy_digest_even_when_anchors_equal(self):
        identifier = "PAPER-paper-method-add-010"
        item = self.docs[identifier]
        outcomes = copy.deepcopy(item["outcomes"])
        outcomes["contracts"]["improvement"] = self.module._digest(item["documents"]["previous_improvement"])
        self.put("benchmarks/paper/" + identifier + "/outcomes.v1.json", outcomes)
        self.reject_without_writes("Invalid paper outcome contracts")

    def test_current_instruction_projection_preserves_exact_predecessor_sections(self):
        self.adopt()
        for identifier, item in self.docs.items():
            row, bound = self.context(identifier)
            document = self.load(row["specification"]["path"])
            self.assertEqual(document["episode"]["improvement"], item["documents"]["primary_improvement"]["episode"])
            self.assertEqual(document["retained_pre_scope_policy"]["sections"]["episode"], item["documents"]["previous_task"]["episode"])
            for field in ("input_assets", "resources", "provenance", "legacy"):
                self.assertEqual(document[field], item["documents"]["previous_task"][field])
            self.assertFalse(document["admission"]["runnable"])


if __name__ == "__main__":
    unittest.main()
