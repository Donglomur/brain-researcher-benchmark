"""Generated metadata controls for absent source declarations, without science."""
import copy
import importlib.util
from pathlib import Path
import runpy
import unittest


ROOT = Path(__file__).resolve().parents[2]
fixtures = runpy.run_path(str(ROOT / "tests/maintenance/test_paper_outcome_binder.py"))
binder, binding = fixtures["binder"], fixtures["binding"]
path = ROOT / "src/neurobench/paper_declaration_gaps.py"
spec = importlib.util.spec_from_file_location("_paper_declaration_gap_controls", path)
gaps = importlib.util.module_from_spec(spec)
exec(compile(path.read_bytes(), str(path), "exec"), gaps.__dict__)


def record(cases):
    entries = {}
    for identifier, case in cases.items():
        improvement = case.improvement
        descriptions = {key: improvement["same_task"][key]["description"] for key in gaps.ANCHORS}
        assessment = {"path": "dual-outcomes/generated/" + identifier + "/REVIEW.json",
                      "reviewed_task_source_commit": "a" * 40, "documentary_namespace": gaps.NAMESPACE,
                      "sha256": "b" * 64, "bytes": 17}
        entries[identifier] = {
            "task_id": identifier, "reason_code": "source_declaration_unavailable",
            "reason": "Generated missing source membership prevents an honest complete reproduction declaration.",
            "source_relation": "same_primary_source_compatible",
            "remaining_source_limits": ["Generated missing original panel member roster."],
            "original_task": copy.deepcopy(case.prior_row["specification"]),
            "retained_improvement": {**case.prior_row["specification_revision"]["improvement_contract"],
                                     "contract_digest": binding.engine().contract_digest(improvement)},
            "accepted_source_assessments": [assessment], "scientific_outcome": "unknown",
            "paired_outcome_admission": "unavailable", "reproduction_contract": None, "outcomes_contract": None,
            "provenance": {
                "primary_scope": descriptions["target"], "predecessor_pin_role": "Generated exact predecessor identities.",
                "preserved_source_scope": "Generated original panel remains the same scientific task.",
                "source_paper": copy.deepcopy(improvement["source_paper"]),
                "same_task_anchor_descriptions": descriptions,
                "structured_representation_status": "Generated substantive source gaps; no eligibility or schema judgment.",
                "assessment_roles": [{"path": assessment["path"], "role": "independent_review"}],
                "outcome_availability": {
                    "reproduction": {"declaration_status": "not_adopted", "declared_endpoint_eligibility": None,
                                     "source_assessment_disposition": "source_unresolved", "scientific_ineligibility_inferred": False},
                    "improvement": {"declaration_status": "retained_existing_contract",
                                    "declared_disposition": improvement["disposition"],
                                    "unavailable_by_reproduction_dependency": False, "qualification_changed_by_this_record": False},
                    "primary_paired_admission": "unavailable_without_honest_reproduction_declaration",
                    "condition_protocols": {condition: "not_established" for condition in gaps.CONDITIONS},
                },
                "scientific_cells": {outcome: {condition: "unknown" for condition in gaps.CONDITIONS}
                                     for outcome in ("reproduction", "improvement")},
                "scope_revision": False, "primary_secondary_scope_mismatch": False,
                "core_two_outcome_completion": "not_established", "future_recovery": "Recover an honest source-specific declaration.",
            },
        }
    return {"schema_version": gaps.VERSION, "source_base": "a" * 40, "entries": entries,
            "provenance": {"canonical_path_proposal": gaps.PATH, "record_scope": "Generated documentary absence record.",
                           "documentary_namespace": gaps.NAMESPACE, "documentary_namespace_rule": "External documentary metadata only.",
                           "admission_rule": "No paired outcome admission from a missing declaration.",
                           "preservation_rule": "Exact original science and improvement identities remain unchanged.",
                           "qualification_limit": "No scientific execution or result is established."}}


class PaperDeclarationGapTests(unittest.TestCase):
    def setUp(self):
        self.cases = {}
        for identifier in sorted(gaps.TASK_IDS):
            case = fixtures["UnavailablePaperOutcomeBinderTests"](
                "test_marker_without_proposal_preserves_history_and_labels_all_cells_unknown")
            self.addCleanup(case.doCleanups)
            case.setUp(identifier=identifier)
            # This fixture has no reproduction or outcomes declaration. Retained
            # actual-schema legacy metadata is the only scientific policy source.
            (case.root / case.home / binding.OUTCOMES).unlink()
            (case.root / binding.SCOPE_PATH).unlink()
            case.prior_task["input_assets"] = {"permitted_observations": ["invented signal"], "labels_visible": False}
            case.prior_task["resources"] = {"max_threads": 1, "unit": "invented metadata"}
            case.prior_task_bytes = case.put(case.task_path, case.prior_task)
            case.prior_row["specification"] = binding.pin(case.task_path, case.prior_task_bytes)
            case.archive_pin = binding.pin(case.home + "/" + gaps.HISTORY,
                                            case.put(case.home + "/" + gaps.HISTORY, case.prior_task_bytes))
            case.base = binding.project_task(case.prior_task, case.prior_row, case.improvement)
            self.cases[identifier] = case
        self.identifier = sorted(gaps.TASK_IDS)[0]
        self.case = self.cases[self.identifier]
        self.document = record(self.cases)
        self.write_record()
        self.calls = []

    def write_record(self):
        raw = binding.encode(self.document)
        self.record_pin = binding.pin(gaps.PATH, raw)
        for case in self.cases.values():
            case.put(gaps.PATH, raw)

    def reader(self, case):
        reader = binder.checker.Reader(case.root)
        allowed = {gaps.PATH, case.archive_pin["path"], case.home + "/improvement.v1.json"}

        def read_pin(pin, label):
            self.assertIn(pin["path"], allowed, "Documentary evidence or implementation was followed")
            self.calls.append(pin["path"])
            return binder.read_pinned(reader, pin, label)

        return read_pin

    def authenticate(self, case=None, **kwargs):
        case = self.case if case is None else case
        return gaps.authenticate(self.record_pin, case.prior_row, case.archive_pin, self.reader(case), **kwargs)

    def reject_record(self, mutation):
        document = copy.deepcopy(self.document)
        mutation(document)
        with self.assertRaises(ValueError):
            gaps.validate_record(document)

    def test_both_exact_tasks_authenticate_only_three_pinned_metadata_members(self):
        for identifier, case in self.cases.items():
            with self.subTest(identifier=identifier):
                self.calls.clear()
                handle = self.authenticate(case)
                self.assertEqual(handle.snapshot()["entry"]["task_id"], identifier)
                self.assertEqual(self.calls, [gaps.PATH, case.archive_pin["path"], case.home + "/improvement.v1.json"])
                self.assertFalse((case.root / case.home / binding.REPRODUCTION).exists())
                self.assertFalse((case.root / case.home / binding.OUTCOMES).exists())

    def test_previously_authenticated_improvement_avoids_duplicate_io_but_checks_digest(self):
        self.authenticate(improvement_contract=self.case.improvement)
        self.assertEqual(self.calls, [gaps.PATH, self.case.archive_pin["path"]])
        wrong = copy.deepcopy(self.case.improvement)
        wrong["comparison"]["primary_metric"] = "Invented replacement metric"
        with self.assertRaisesRegex(ValueError, "canonical identity mismatch"):
            self.authenticate(improvement_contract=wrong)

    def test_closed_record_and_exact_roster_reject_additions_omissions_and_identity_swaps(self):
        for mutation in (
            lambda d: d.update(unreviewed=True),
            lambda d: d["entries"].pop(self.identifier),
            lambda d: d["entries"].update({"PAPER-EXTRA": copy.deepcopy(d["entries"][self.identifier])}),
            lambda d: d["entries"][self.identifier].update(task_id="PAPER-OTHER"),
            lambda d: d.update(schema_version="paper-outcome-source-declaration-gaps/v999"),
            lambda d: d.update(source_base="not-a-commit"),
        ):
            with self.subTest(mutation=mutation):
                self.reject_record(mutation)

    def test_record_cannot_fabricate_contracts_scope_mismatch_eligibility_or_results(self):
        for key, value in (("reproduction_contract", "reproduction.v1.json"), ("outcomes_contract", {}),
                           ("source_relation", "primary_secondary_scope_mismatch"), ("reason_code", "schema_blocked"),
                           ("scientific_outcome", "qualified"), ("paired_outcome_admission", "available")):
            with self.subTest(key=key):
                self.reject_record(lambda d: d["entries"][self.identifier].update({key: value}))
        for key, value in (("scope_revision", True), ("primary_secondary_scope_mismatch", True),
                           ("scope_revision", 0), ("core_two_outcome_completion", "complete")):
            with self.subTest(provenance=key, value=value):
                self.reject_record(lambda d: d["entries"][self.identifier]["provenance"].update({key: value}))
        self.reject_record(lambda d: d["entries"][self.identifier]["provenance"]["scientific_cells"]["reproduction"].update(paper_data="success"))

    def test_documentary_locators_and_context_are_closed_safe_and_not_runtime_authority(self):
        for path in ("/private/review.json", "dual-outcomes/../secret.json", "dual-outcomes/a\nfile.json",
                     "benchmarks/paper/implementation.py", "dual-outcomes\\review.json"):
            with self.subTest(path=path):
                self.reject_record(lambda d: d["entries"][self.identifier]["accepted_source_assessments"][0].update(path=path))
        for key, value in (("documentary_namespace", "another-space"), ("reviewed_task_source_commit", "c" * 40),
                           ("bytes", True), ("sha256", "not-a-sha")):
            with self.subTest(key=key):
                self.reject_record(lambda d: d["entries"][self.identifier]["accepted_source_assessments"][0].update({key: value}))
        self.reject_record(lambda d: d["entries"][self.identifier]["accepted_source_assessments"][0].update(source_commit="a" * 40))

    def test_metadata_bounds_and_nonfinite_values_fail_before_reader(self):
        oversized = {**self.record_pin, "bytes": gaps.MAX_RECORD_BYTES + 1}
        with self.assertRaisesRegex(ValueError, "Invalid source declaration record pin"):
            gaps.authenticate(oversized, self.case.prior_row, self.case.archive_pin,
                              lambda *_: self.fail("Oversized record was read"))
        self.reject_record(lambda d: d["provenance"].update(record_scope="x" * gaps.MAX_RECORD_BYTES))
        self.reject_record(lambda d: d["entries"][self.identifier]["original_task"].update(bytes=float("nan")))
        self.reject_record(lambda d: d["entries"][self.identifier]["original_task"].update(bytes=True))

    def test_source_record_raw_pin_is_enforced(self):
        self.case.put(gaps.PATH, binding.encode(self.document) + b" ")
        with self.assertRaisesRegex(ValueError, "pin mismatch"):
            self.authenticate()

    def test_original_current_task_pin_and_archive_alias_must_identify_identical_bytes(self):
        self.document["entries"][self.identifier]["original_task"]["sha256"] = "0" * 64
        self.write_record()
        with self.assertRaisesRegex(ValueError, "immutable prior task identity"):
            self.authenticate()
        self.document["entries"][self.identifier]["original_task"] = copy.deepcopy(self.case.prior_row["specification"])
        self.write_record()
        wrong = {**self.case.archive_pin, "path": self.case.task_path}
        with self.assertRaisesRegex(ValueError, "pre-outcomes archive pin"):
            gaps.authenticate(self.record_pin, self.case.prior_row, wrong, self.reader(self.case))
        wrong = {**self.case.archive_pin, "sha256": "0" * 64}
        with self.assertRaisesRegex(ValueError, "retain original task bytes"):
            gaps.authenticate(self.record_pin, self.case.prior_row, wrong, self.reader(self.case))

    def test_improvement_raw_and_canonical_identities_are_independent_checks(self):
        self.document["entries"][self.identifier]["retained_improvement"]["sha256"] = "0" * 64
        self.write_record()
        with self.assertRaisesRegex(ValueError, "retained improvement identity"):
            self.authenticate()
        self.document["entries"][self.identifier]["retained_improvement"]["sha256"] = self.case.prior_row["specification_revision"]["improvement_contract"]["sha256"]
        self.document["entries"][self.identifier]["retained_improvement"]["contract_digest"] = "0" * 64
        self.write_record()
        with self.assertRaisesRegex(ValueError, "canonical identity mismatch"):
            self.authenticate()

    def test_rehashed_record_cannot_substitute_original_paper_or_any_anchor(self):
        provenance = self.document["entries"][self.identifier]["provenance"]
        provenance["source_paper"]["url"] = "https://example.invalid/wrong-paper"
        self.write_record()
        with self.assertRaisesRegex(ValueError, "original source paper"):
            self.authenticate()
        provenance["source_paper"] = copy.deepcopy(self.case.improvement["source_paper"])
        for anchor in gaps.ANCHORS:
            with self.subTest(anchor=anchor):
                original = provenance["same_task_anchor_descriptions"][anchor]
                provenance["same_task_anchor_descriptions"][anchor] = "Invented replacement " + anchor
                if anchor == "target":
                    provenance["primary_scope"] = provenance["same_task_anchor_descriptions"][anchor]
                self.write_record()
                with self.assertRaisesRegex(ValueError, "all original scientific anchors"):
                    self.authenticate()
                provenance["same_task_anchor_descriptions"][anchor] = original
                if anchor == "target":
                    provenance["primary_scope"] = original

    def test_handle_and_all_outputs_are_isolated_from_input_mutation(self):
        handle = self.authenticate()
        expected = gaps.project(self.case.base, handle)
        snapshot = handle.snapshot()
        snapshot["entry"]["reason"] = "mutated copy"
        self.document["entries"][self.identifier]["reason"] = "mutated input"
        self.case.prior_row["id"] = "mutated row"
        self.case.improvement["comparison"]["primary_metric"] = "mutated policy"
        self.assertEqual(gaps.project(self.case.base, handle), expected)
        with self.assertRaises(AttributeError):
            handle._encoded = b"{}"
        with self.assertRaises(AttributeError):
            del handle._encoded
        self.assertEqual(gaps.project(self.case.base, handle), expected)
        with self.assertRaisesRegex(ValueError, "Use authenticate"):
            gaps.AuthenticatedGap({})
        output = gaps.public_summary(handle)
        output["retained_improvement"]["sha256"] = "0" * 64
        self.assertNotEqual(gaps.public_summary(handle)["retained_improvement"]["sha256"], "0" * 64)

    def test_callback_mutation_cannot_change_already_captured_arguments_or_documents(self):
        read = self.reader(self.case)
        original_row = copy.deepcopy(self.case.prior_row)
        original_pin = copy.deepcopy(self.record_pin)
        archive = copy.deepcopy(self.case.archive_pin)
        observed = {}

        def mutating_reader(pin, label):
            document = read(pin, label)
            if pin["path"] == gaps.PATH:
                self.record_pin["sha256"] = "0" * 64
                self.case.prior_row["id"] = "mutated"
            if pin["path"] == archive["path"]:
                observed["previous"] = document
            if pin["path"].endswith("/improvement.v1.json"):
                observed["previous"]["resources"]["max_threads"] = 999
            return document

        handle = gaps.authenticate(self.record_pin, self.case.prior_row, archive, mutating_reader)
        snapshot = handle.snapshot()
        self.assertEqual(snapshot["record_pin"], original_pin)
        self.assertEqual(snapshot["entry"]["task_id"], original_row["id"])
        self.assertEqual(snapshot["previous_task"]["resources"]["max_threads"], 1)

    def test_projection_preserves_science_and_contains_no_nonexistent_contract_locators(self):
        handle = self.authenticate()
        base_before = binding.encode(self.case.base)
        result = gaps.project(self.case.base, handle)
        self.assertEqual(binding.encode(self.case.base), base_before)
        for field in ("goal", "input_assets", "resources", "status", "track", "id"):
            self.assertEqual(binding.encode(result[field]), binding.encode(self.case.base[field]))
        for field in ("episode", "blocking_issues", "next_implementation_action"):
            if field in self.case.prior_task:
                self.assertEqual(binding.encode(result[field]["improvement"]), binding.encode(self.case.prior_task[field]))
        if "holds" in self.case.prior_task:
            self.assertEqual(binding.encode(result["holds"]["preserved_limits"]), binding.encode(self.case.prior_task["holds"]))
        self.assertIsNone(result["evaluation"]["contracts"]["reproduction"])
        self.assertIsNone(result["evaluation"]["paired_protocol"])
        self.assertEqual(result["evaluation"]["contracts"]["improvement"], "improvement.v1.json")
        self.assertEqual(result["evaluation"]["reproduction_declaration_status"], "source_declaration_unavailable")
        self.assertNotIn(b"reproduction.v1.json", binding.encode(result))
        self.assertNotIn(b"reproduction.v2.json", binding.encode(result))
        self.assertNotIn(b"outcomes.v1.json", binding.encode(result))

    def test_projection_refuses_changed_scientific_fields_types_or_execution_claims(self):
        handle = self.authenticate()
        for mutate in (
            lambda task: task["input_assets"].update(labels_visible=0),
            lambda task: task["resources"].update(max_threads=2),
            lambda task: task.update(invented_metric="accuracy"),
            lambda task: task["evaluation"].update(executor_ref="candidate.py"),
            lambda task: task["evaluation"].update(binary_reward_registered=0),
            lambda task: task.update(admission={"research_qualified": True}),
        ):
            changed = copy.deepcopy(self.case.base)
            mutate(changed)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                gaps.project(changed, handle)

    def test_explicit_null_inherited_fields_require_present_preservation_keys(self):
        fields = {"episode": "improvement", "blocking_issues": "improvement",
                  "next_implementation_action": "improvement", "holds": "preserved_limits"}
        self.case.prior_task.update({field: None for field in fields})
        raw = self.case.put(self.case.task_path, self.case.prior_task)
        self.case.prior_row["specification"] = binding.pin(self.case.task_path, raw)
        self.case.archive_pin = binding.pin(self.case.home + "/" + gaps.HISTORY,
                                             self.case.put(self.case.home + "/" + gaps.HISTORY, raw))
        self.document = record(self.cases)
        self.write_record()
        base = binding.project_task(self.case.prior_task, self.case.prior_row, self.case.improvement)
        handle = self.authenticate()
        projected = gaps.project(base, handle)
        for field, nested in fields.items():
            with self.subTest(field=field):
                self.assertIn(nested, projected[field])
                self.assertIsNone(projected[field][nested])
                changed = copy.deepcopy(base)
                del changed[field][nested]
                with self.assertRaisesRegex(ValueError, "changed retained improvement|changed preserved scientific limits"):
                    gaps.project(changed, handle)

    def test_retained_improvement_disposition_stays_independent_and_all_cells_unknown(self):
        handle = self.authenticate()
        summary = gaps.public_summary(handle)
        self.assertEqual(summary["improvement_disposition"], self.case.improvement["disposition"])
        self.assertIs(summary["improvement_unavailable_by_reproduction_dependency"], False)
        self.assertIsNone(summary["reproduction_eligibility"])
        self.assertIs(summary["scientific_ineligibility_inferred"], False)
        self.assertEqual(summary["task_count"], 1)
        self.assertEqual(summary["paired_outcome_admission"], "unavailable")
        self.assertEqual(len(summary["cells"]), 4)
        self.assertTrue(all(cell["scientific_outcome"] == "unknown" and cell["receipt"] is None
                            and not cell["metadata_admitted"] for cell in summary["cells"]))
        self.assertFalse(hasattr(gaps, "admit_outcome"))


if __name__ == "__main__":
    unittest.main()
