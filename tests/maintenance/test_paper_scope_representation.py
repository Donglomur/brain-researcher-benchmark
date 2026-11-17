"""Generated controls for exact task spelling and unavailable scope reasons.

The one real registered lowercase identifier is exercised with entirely invented
contracts in temporary roots. No actual task definition or scientific data is
modified or executed.
"""
import copy
import hashlib
from pathlib import Path
import runpy
import unittest


ROOT = Path(__file__).resolve().parents[2]
fixtures = runpy.run_path(str(ROOT / "tests/maintenance/test_paper_outcome_binder.py"))
structured = runpy.run_path(str(ROOT / "tests/framework/test_paper_reproduction_v2.py"))
primary_fixtures = runpy.run_path(str(ROOT / "tests/maintenance/test_paper_primary_scope_binding.py"))
binder, binding = fixtures["binder"], fixtures["binding"]
LOWER_ID = "paper-pcca-fa-bilateral-pfc-arousal-2026"
OLD_STATUS = "unavailable_primary_secondary_scope_mismatch"
NEUTRAL_STATUS = "unavailable_complete_primary_pairing"


class PaperScopeRepresentationTests(unittest.TestCase):
    def case(self, *, identifier=LOWER_ID, status=NEUTRAL_STATUS, proposal=None):
        case = fixtures["UnavailablePaperOutcomeBinderTests"](
            "test_marker_without_proposal_preserves_history_and_labels_all_cells_unknown")
        self.addCleanup(case.doCleanups)
        case.setUp(identifier=identifier)
        case.entry["paired_bundle_status"] = status
        case.entry["adoption_route"] = "full_primary_pairing_unavailable"
        case.scope_pin = binding.pin(binding.SCOPE_PATH, case.put(binding.SCOPE_PATH, case.scope))
        case.marker["root_scope_decision"]["raw_sha256"] = case.scope_pin["sha256"]
        case.marker["reason_code"] = binding.UNAVAILABLE_REASONS[status]
        if proposal is not None:
            if proposal == "paper-reproduction/v2":
                reproduction, improvement, _, _ = structured["fixture"]()
                reproduction["task_id"] = improvement["task_id"] = identifier
                self.assertEqual(improvement, case.improvement)
                case.reproduction = reproduction
            case.reproduction["same_task"]["target"]["description"] = case.entry["primary_scope"]
            self.reseal_proposal(case)
        projected = binding.project_task(case.prior_task, case.prior_row, case.improvement, case.entry,
                                         reproduction_version=proposal or "paper-reproduction/v1")
        case.marker["original_task_sha256"] = binding.pin(case.task_path, binding.encode(projected))["sha256"]
        case.save_marker()
        return case

    def reseal_proposal(self, case):
        filename = binding.REPRODUCTION_FILES[case.reproduction["schema_version"]]
        raw = case.put(case.home + "/" + filename, case.reproduction)
        case.marker["reproduction_proposal"] = {
            "path": filename, "raw_sha256": binding.pin(filename, raw)["sha256"],
            "contract_digest": binding.engine(case.reproduction).contract_digest(case.reproduction),
        }
        case.save_marker()

    def test_exact_lowercase_registered_identity_adopts_without_alias_or_qualification(self):
        case = self.case()
        prior_task = case.prior_task_bytes
        improvement = (case.root / case.home / "improvement.v1.json").read_bytes()
        binder.write_or_check(case.root, write=True)
        self.assertEqual(binder.validate_existing(case.root)["paper_tasks"], 1)
        row, bound = case.bound()
        self.assertEqual(row["id"], LOWER_ID)
        self.assertEqual(row["task_directory"], "benchmarks/paper/" + LOWER_ID)
        self.assertIs(row["specification_alias"], False)
        self.assertEqual(case.load(case.task_path)["evaluation"]["primary_bundle_status"], NEUTRAL_STATUS)
        self.assertEqual((case.root / case.home / binding.HISTORY).read_bytes(), prior_task)
        self.assertEqual((case.root / case.home / "improvement.v1.json").read_bytes(), improvement)
        summary = binding.public_summary(row, bound)
        self.assertEqual(summary["reason_code"], "full_primary_pairing_unavailable")
        self.assertEqual(summary["availability"], "unavailable")
        self.assertEqual(summary["scientific_outcomes"], {"reproduction": "unknown", "improvement": "unknown"})
        self.assertTrue(all(not cell["endpoint_eligible"] and cell["scientific_outcome"] == "unknown"
                            for cell in summary["cells"]))
        self.assertEqual(binder.write_or_check(case.root, check=True)["changed_files"], 0)

    def test_only_exact_legacy_lowercase_spelling_is_allowed_in_scope_maps(self):
        case = self.case()
        for identifier in ("paper-an-arbitrary-task", LOWER_ID + "-copy", LOWER_ID.upper().replace("PAPER-", "paper-", 1),
                           "Paper-FIND-024", LOWER_ID + "/task.json", "../" + LOWER_ID, "PAPER-" + "X" * 122):
            with self.subTest(identifier=identifier):
                scope = copy.deepcopy(case.scope)
                entry = scope["entries"].pop(LOWER_ID)
                entry["task_id"] = identifier
                scope["entries"][identifier] = entry
                with self.assertRaises(ValueError):
                    binding.scope_decisions(scope)

    def test_existing_safe_uppercase_id_still_accepts_neutral_status(self):
        case = self.case(identifier="PAPER-GENERATED_test-024")
        self.assertEqual(binding.scope_decisions(case.scope)["entries"][case.identifier]["paired_bundle_status"], NEUTRAL_STATUS)
        binder.write_or_check(case.root, write=True)
        self.assertEqual(case.bound()[0]["id"], "PAPER-GENERATED_test-024")

    def test_neutral_status_requires_explicit_unavailable_adoption_route(self):
        case = self.case()
        del case.entry["adoption_route"]
        with self.assertRaisesRegex(ValueError, "route|explicit"):
            binding.scope_decisions(case.scope)

    def test_neutral_status_cannot_select_normal_correction_route(self):
        case = self.case()
        case.entry["adoption_route"] = "normal_same_primary_unqualified"
        with self.assertRaisesRegex(ValueError, "route"):
            binding.scope_decisions(case.scope)

    def test_status_derived_reasons_reject_both_cross_wires_and_unknown_reason(self):
        for status, wrong in ((OLD_STATUS, "full_primary_pairing_unavailable"),
                              (NEUTRAL_STATUS, "primary_secondary_scope_mismatch"),
                              (NEUTRAL_STATUS, "invented_qualification_shortcut")):
            with self.subTest(status=status, reason=wrong):
                case = self.case(status=status)
                case.marker["reason_code"] = wrong
                case.save_marker()
                case.reject_without_writes("bind its corrected primary scope|reason")

    def test_old_reason_and_default_route_remain_valid(self):
        case = self.case(identifier="PAPER-FIND-013", status=OLD_STATUS)
        del case.entry["adoption_route"]
        case.scope_pin = binding.pin(binding.SCOPE_PATH, case.put(binding.SCOPE_PATH, case.scope))
        case.marker["root_scope_decision"]["raw_sha256"] = case.scope_pin["sha256"]
        case.save_marker()
        binder.write_or_check(case.root, write=True)
        row, bound = case.bound()
        self.assertEqual(case.load(case.task_path)["evaluation"]["primary_bundle_status"], OLD_STATUS)
        self.assertEqual(binding.public_summary(row, bound)["reason_code"], "primary_secondary_scope_mismatch")

    def test_old_mismatch_projection_retains_frozen_predecessor_bytes(self):
        case = self.case(identifier="PAPER-FIND-013", status=OLD_STATUS)
        raw = binding.encode(binding.project_task(case.prior_task, case.prior_row, case.improvement, case.entry))
        # Captured from the same invented fixture with the reviewed helper at
        # 3c82a890f95184fdabf0e4c23ee85356e452c46e, before this representation repair.
        self.assertEqual(len(raw), 6076)
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
                         "a00819b3f9d6a293080751a5484ac55028f1fbd33fdf5d38e40aa25d432ed476")

    def test_neutral_projection_changes_only_status_and_coverage_presentation(self):
        case = self.case(identifier="PAPER-FIND-013")
        old_entry = copy.deepcopy(case.entry)
        old_entry["paired_bundle_status"] = OLD_STATUS
        old = binding.project_task(case.prior_task, case.prior_row, case.improvement, old_entry)
        neutral = binding.project_task(case.prior_task, case.prior_row, case.improvement, case.entry)
        self.assertEqual({key for key in old if old[key] != neutral[key]},
                         {"status_basis", "primary_outputs", "evaluation", "success_criteria"})
        self.assertEqual(neutral["evaluation"]["primary_bundle_status"], NEUTRAL_STATUS)
        self.assertIn("coverage", neutral["status_basis"])
        self.assertNotIn("secondary improvement contract", neutral["status_basis"])
        self.assertTrue(neutral["primary_outputs"][2].startswith("Retained source work: "))
        self.assertEqual(neutral["success_criteria"][:5], old["success_criteria"][:5])
        self.assertNotIn("secondary implementations", neutral["success_criteria"][5])
        self.assertIn("declared coverage", neutral["success_criteria"][5])
        self.assertIn("do not become qualified AI results", neutral["success_criteria"][5])

    def test_exact_lowercase_identity_is_supported_in_disjoint_normal_and_passive_maps(self):
        case = self.case()
        scope = copy.deepcopy(case.scope)
        entry = scope["entries"].pop(LOWER_ID)
        scope["same_primary_corrections"] = {LOWER_ID: {
            "task_id": LOWER_ID, "disposition": "same_primary_unqualified",
            "paired_bundle_status": "same_primary_unqualified", "scientific_outcome": "unknown",
            "adoption_route": "normal_same_primary_unqualified", "projection_action": "revise_primary_scope",
            "primary_goal": entry["primary_goal"], "primary_scope": entry["primary_scope"],
            "remaining_source_limits": entry["remaining_source_limits"],
        }}
        self.assertIn(LOWER_ID, binding.scope_decisions(scope)["same_primary_corrections"])
        scope.pop("same_primary_corrections")
        scope["source_gap_confirmations"] = {LOWER_ID: {
            "task_id": LOWER_ID, "projection_action": "none", "scientific_outcome": "unknown",
            "adoption_route": "source_gap_confirmation",
        }}
        self.assertIn(LOWER_ID, binding.scope_decisions(scope)["source_gap_confirmations"])

    def test_qualified_or_unknown_unavailable_status_is_refused(self):
        for status in ("qualified", "same_primary_unqualified", "unavailable_future_policy"):
            with self.subTest(status=status):
                case = self.case()
                case.entry["paired_bundle_status"] = status
                with self.assertRaises(ValueError):
                    binding.scope_decisions(case.scope)

    def test_neutral_scope_cannot_use_a_normal_bundle(self):
        case = self.case()
        case.normal_outcomes["original_task_sha256"] = case.marker["original_task_sha256"]
        case.normal_outcomes["contracts"] = {
            "reproduction": binding.engine().contract_digest(case.reproduction),
            "improvement": binding.engine().contract_digest(case.improvement),
        }
        case.put(case.home + "/" + binding.REPRODUCTION, case.reproduction)
        case.put(case.home + "/" + binding.OUTCOMES, case.normal_outcomes)
        case.reject_without_writes("mixed-scope normal outcome bundle")

    def test_optional_v1_and_v2_proposals_keep_version_paths_and_unknown_primary_results(self):
        for version in binding.REPRODUCTION_FILES:
            with self.subTest(version=version):
                case = self.case(proposal=version)
                binder.write_or_check(case.root, write=True)
                row, bound = case.bound()
                self.assertEqual(row["paper_outcomes"]["reproduction_contract"]["path"],
                                 case.home + "/" + binding.REPRODUCTION_FILES[version])
                self.assertEqual(bound["availability"], "unavailable")
                self.assertEqual(bound["reproduction_contract"]["schema_version"], version)
                self.assertTrue(all(cell["scientific_outcome"] == "unknown" for cell in bound["summary"]["cells"]))
                response = binding.engine(case.reproduction).admit_outcome(case.marker, case.reproduction, case.improvement, {})
                self.assertFalse(response["metadata_admitted"])
                self.assertEqual(response["scientific_outcome"], "unknown")

    def test_v1_and_v2_proposals_still_reject_rehashed_wrong_primary_scope(self):
        for version in binding.REPRODUCTION_FILES:
            with self.subTest(version=version):
                case = self.case(proposal=version)
                case.reproduction["same_task"]["target"]["description"] = "Invented different original result."
                self.reseal_proposal(case)
                case.reject_without_writes("target must match the corrected primary scope")

    def test_v1_and_v2_proposals_still_reject_rehashed_wrong_source_paper(self):
        for version in binding.REPRODUCTION_FILES:
            with self.subTest(version=version):
                case = self.case(proposal=version)
                case.reproduction["source_paper"]["url"] = "https://example.invalid/a-different-original-paper"
                self.reseal_proposal(case)
                case.reject_without_writes("retain its source paper identity")

    def explicit_selection(self):
        fixture = primary_fixtures["PaperPrimaryScopeBindingTests"](
            "test_plan_is_read_only_and_write_preserves_contracts_metrics_and_history")
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        fixture.correction["disposition"] = "explicit_primary_selection"
        fixture.correction["adoption_route"] = "normal_same_primary_unqualified"
        fixture.save_scope()
        fixture.reseal()
        return fixture

    def test_explicit_primary_selection_preserves_source_label_without_promoting_outcomes(self):
        fixture = self.explicit_selection()
        binder.write_or_check(fixture.root, write=True)
        row, bound = fixture.bound()
        task = fixture.source.load(fixture.case.task_path)
        correction = task["source_scope_correction"]
        self.assertEqual(correction["source_disposition"], "explicit_primary_selection")
        self.assertEqual(correction["disposition"], "same_primary_unqualified")
        self.assertEqual(correction["scientific_outcome"], "unknown")
        public = binding.public_summary(row, bound)["primary_scope_correction"]
        self.assertEqual(public["source_disposition"], "explicit_primary_selection")
        self.assertEqual(public["disposition"], "same_primary_unqualified")
        self.assertEqual(bound["reproduction_contract"]["eligibility"], "source_unresolved")
        self.assertTrue(all(cell["scientific_outcome"] == "unknown" for cell in bound["summary"]["cells"]))
        self.assertEqual((fixture.root / fixture.home / "improvement.v1.json").read_bytes(), fixture.improvement_raw)
        self.assertEqual((fixture.root / fixture.home / binding.HISTORY).read_bytes(), fixture.prior_raw)
        self.assertEqual(binder.validate_existing(fixture.root)["paper_tasks"], 1)
        self.assertEqual(binder.write_or_check(fixture.root, check=True)["changed_files"], 0)

    def test_explicit_primary_selection_without_explicit_normal_route_is_refused(self):
        fixture = self.explicit_selection()
        del fixture.correction["adoption_route"]
        fixture.save_scope()
        fixture.case.reject_without_writes("requires an explicit reviewed normal route")

    def test_unknown_primary_selection_labels_cannot_choose_a_normal_route(self):
        fixture = self.explicit_selection()
        for label in ("explicit_selection", "same_primary_ready", "scientifically_verified"):
            with self.subTest(label=label):
                fixture.correction["disposition"] = label
                fixture.save_scope()
                fixture.case.reject_without_writes("cannot qualify an outcome")

    def test_explicit_primary_selection_retains_all_eight_original_anchor_guards(self):
        fixture = self.explicit_selection()
        for anchor in binding.engine().improvement.ANCHORS:
            with self.subTest(anchor=anchor):
                original = fixture.reproduction["same_task"][anchor]["description"]
                fixture.reproduction["same_task"][anchor]["description"] = "Invented substituted original " + anchor
                fixture.reseal()
                fixture.case.reject_without_writes("original scientific anchor differs")
                fixture.reproduction["same_task"][anchor]["description"] = original


if __name__ == "__main__":
    unittest.main()
