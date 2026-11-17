"""Invented same-primary scope corrections retain unresolved scientific status."""
import copy
from pathlib import Path
import runpy
import unittest


ROOT = Path(__file__).resolve().parents[2]
fixtures = runpy.run_path(str(ROOT / "tests/maintenance/test_paper_outcome_binder.py"))
binder, binding = fixtures["binder"], fixtures["binding"]
legacy = fixtures["fixtures"]["old_binder"]


class PaperPrimaryScopeBindingTests(unittest.TestCase):
    def setUp(self):
        self.case = fixtures["PaperOutcomeBinderTests"](
            "test_default_plan_is_read_only_and_names_only_metadata_outputs")
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.source = self.case.fixture
        self.root, self.home = self.case.root, self.case.home
        self.identifier = self.source.identifier
        self.initial_registry = (self.root / legacy.SNAPSHOT).read_bytes()
        self.original_improvement = copy.deepcopy(self.source.improvement)
        self.improvement = copy.deepcopy(self.original_improvement)
        self.improvement.update(disposition="source_unresolved",
                                disposition_reason="Invented complete primary source remains unresolved.",
                                blocking_issues=["Invented complete source panel is missing."])
        self.build_prior(self.improvement)
        self.reproduction = copy.deepcopy(self.source.reproduction)
        self.reproduction.update(eligibility="source_unresolved",
                                 eligibility_reason="Invented primary source panels remain unresolved.",
                                 blocking_issues=["Invented complete source panel is missing."])
        self.outcomes = copy.deepcopy(self.source.outcomes)
        self.correction = {
            "task_id": self.identifier, "disposition": "same_primary_unqualified",
            "projection_action": "revise_primary_scope",
            "primary_goal": "Recreate the complete invented primary panel and separately assess its unchanged improvement criteria.",
            "primary_scope": "Invented original population, panel and source-defined controls, including unresolved companions.",
            "remaining_source_limits": ["Invented companion panel cannot yet be reconstructed from pinned source."],
            "retained_secondary_scope": "Invented component remains a partial calculation within this same original finding.",
            "retained_source_roles": {
                "legacy": {"endpoint_eligible": False, "observed_count": 0},
                "components": [{"role": "partial_primary", "scientific_result": None}],
            },
            "paired_bundle_status": "same_primary_unqualified", "scientific_outcome": "unknown",
        }
        self.scope = {"schema_version": binding.SCOPE_VERSION, "entries": {
            identifier: {
                "task_id": identifier, "primary_goal": "Invented corrected primary goal.",
                "primary_scope": "Invented corrected primary panel.",
                "retained_secondary_scope": "Invented distinct secondary result.",
                "remaining_source_limits": ["Invented sources remain unresolved."],
                "primary_same_task_improvement": "unavailable_until_independently_justified",
                "paired_bundle_status": "unavailable_primary_secondary_scope_mismatch",
                "scientific_outcome": "unknown",
            } for identifier in sorted(binding.SCOPE_IDS)},
            "same_primary_corrections": {self.identifier: self.correction}}
        self.save_scope()
        self.reseal()
        self.before = self.case.snapshot()

    def build_prior(self, improvement):
        # Rebuild the wholly invented predecessor through the real legacy binder
        # before adoption. No already-authenticated scientific contract is edited.
        self.case.put(binding.REGISTRY, self.initial_registry)
        self.case.put(self.case.task_path, self.source.original_bytes)
        self.case.put(self.home + "/improvement.v1.json", improvement)
        for relative in (legacy.SNAPSHOT, self.source.history_path):
            (self.root / relative).unlink()
        for name, body in legacy.build_outputs(self.root, expected_count=1).items():
            self.case.put(name, body)
        self.prior_registry = self.source.load(binding.REGISTRY)
        self.prior_row = self.prior_registry["tasks"][0]
        self.prior_task = self.source.load(self.case.task_path)
        self.prior_raw = (self.root / self.case.task_path).read_bytes()
        self.improvement_raw = (self.root / self.home / "improvement.v1.json").read_bytes()

    def save_scope(self):
        self.scope_raw = self.case.put(binding.SCOPE_PATH, self.scope)

    def reseal(self, *, correction=True):
        self.case.put(self.home + "/" + binding.REPRODUCTION, self.reproduction)
        self.projected = binding.project_task(self.prior_task, self.prior_row, self.improvement,
                                              primary_correction=self.correction if correction else None)
        self.outcomes["original_task_sha256"] = binding.pin(self.case.task_path, binding.encode(self.projected))["sha256"]
        self.outcomes["contracts"] = {
            "reproduction": binding.engine().contract_digest(self.reproduction),
            "improvement": binding.engine().contract_digest(self.improvement),
        }
        self.case.put(self.home + "/" + binding.OUTCOMES, self.outcomes)

    def bound(self):
        registry = self.source.load(binding.REGISTRY)
        row = registry["tasks"][0]
        reader = binder.checker.Reader(self.root)
        read_pin = lambda pin, label: binder.read_pinned(reader, pin, label)
        previous = binding.coverage(registry, read_pin)
        return row, binding.context(row, self.source.load(self.case.task_path), previous, read_pin)

    def test_plan_is_read_only_and_write_preserves_contracts_metrics_and_history(self):
        report = binder.write_or_check(self.root)
        self.assertEqual(report["status"], "planned")
        self.assertEqual(self.case.snapshot(), self.before)
        binder.write_or_check(self.root, write=True)
        self.assertEqual((self.root / self.home / "improvement.v1.json").read_bytes(), self.improvement_raw)
        self.assertEqual((self.root / self.home / binding.HISTORY).read_bytes(), self.prior_raw)
        self.assertEqual((self.root / self.source.history_path).read_bytes(), self.source.original_bytes)
        self.assertEqual(self.source.load(self.home + "/improvement.v1.json")["comparison"], self.original_improvement["comparison"])
        self.assertEqual(self.source.load(self.home + "/" + binding.REPRODUCTION)["findings"], self.source.reproduction["findings"])
        task = self.source.load(self.case.task_path)
        self.assertEqual(task["goal"], self.correction["primary_goal"])
        self.assertEqual(task["primary_scope"], self.correction["primary_scope"])
        self.assertEqual(task["scope_decision"], {"path": binding.SCOPE_PATH, "task_entry_id": self.identifier})
        self.assertEqual(task["source_scope_correction"]["remaining_source_limits"], self.correction["remaining_source_limits"])
        row, bound = self.bound()
        self.assertEqual(self.source.load(self.home + "/" + binding.OUTCOMES)["original_task_sha256"], row["specification"]["sha256"])
        self.assertEqual(bound["availability"], "available")
        self.assertEqual(bound["reproduction_contract"]["eligibility"], "source_unresolved")
        self.assertTrue(all(cell["scientific_outcome"] == "unknown" for cell in bound["summary"]["cells"]))
        summary = binding.public_summary(row, bound)["primary_scope_correction"]
        self.assertEqual(summary["primary_goal"], self.correction["primary_goal"])
        self.assertEqual(summary["root_scope_decision"]["raw_sha256"], binding.pin(binding.SCOPE_PATH, self.scope_raw)["sha256"])

    def test_checked_and_repeated_writes_are_idempotent(self):
        binder.write_or_check(self.root, write=True)
        before = self.case.snapshot()
        self.assertEqual(binder.validate_existing(self.root)["paper_tasks"], 1)
        self.assertEqual(binder.write_or_check(self.root, check=True)["changed_files"], 0)
        self.assertEqual(binder.write_or_check(self.root, write=True)["changed_files"], 0)
        self.assertEqual(self.case.snapshot(), before)

    def test_adopted_prior_row_boolean_cannot_be_replaced_with_equal_integer(self):
        binder.write_or_check(self.root, write=True)
        prior_snapshot = (self.root / binding.SNAPSHOT).read_bytes()
        registry = self.source.load(binding.REGISTRY)
        row = registry["tasks"][0]
        self.assertIs(row["specification_alias"], False)
        row["specification_alias"] = 0
        self.case.put(binding.REGISTRY, registry)
        self.case.reject_without_writes("prior specification_alias")
        self.assertEqual((self.root / binding.SNAPSHOT).read_bytes(), prior_snapshot)

    def test_adopted_prior_row_missing_optional_field_cannot_become_null(self):
        binder.write_or_check(self.root, write=True)
        prior_snapshot = (self.root / binding.SNAPSHOT).read_bytes()
        registry = self.source.load(binding.REGISTRY)
        row = registry["tasks"][0]
        self.assertNotIn("track_source", row)
        row["track_source"] = None
        self.case.put(binding.REGISTRY, registry)
        self.case.reject_without_writes("prior track_source")
        self.assertEqual((self.root / binding.SNAPSHOT).read_bytes(), prior_snapshot)

    def test_active_and_mismatch_maps_cannot_overlap(self):
        entry = copy.deepcopy(next(iter(self.scope["entries"].values())))
        entry["task_id"] = self.identifier
        self.scope["entries"][self.identifier] = entry
        self.save_scope()
        self.case.reject_without_writes("bounded and disjoint")

    def test_unknown_or_qualified_statuses_are_refused(self):
        for field, value in (("disposition", "qualified"), ("paired_bundle_status", "ready"),
                             ("scientific_outcome", "success")):
            with self.subTest(field=field):
                original = self.correction[field]
                self.correction[field] = value
                self.save_scope()
                self.case.reject_without_writes("cannot qualify an outcome")
                self.correction[field] = original

    def test_task_swap_in_active_map_is_refused(self):
        self.correction["task_id"] = "PAPER-FIND-013"
        self.save_scope()
        self.case.reject_without_writes("same-primary correction identity")

    def test_none_projection_action_cannot_be_activated(self):
        self.correction["projection_action"] = "none"
        self.save_scope()
        self.case.reject_without_writes("projection|[Aa]ctive")

    def test_rehashed_reproduction_eligibility_cannot_be_promoted(self):
        self.reproduction.update(eligibility="eligible", eligibility_reason="Invented dishonest promotion.", blocking_issues=[])
        self.reseal()
        self.case.reject_without_writes("retains unresolved source eligibility")

    def test_valid_but_ready_improvement_cannot_be_promoted_by_scope_correction(self):
        self.improvement = copy.deepcopy(self.original_improvement)
        self.build_prior(self.improvement)
        self.reseal()
        self.case.reject_without_writes("retains unresolved source eligibility")

    def test_original_source_paper_mismatch_still_fails_after_rehash(self):
        self.reproduction["source_paper"]["url"] = "https://example.invalid/another-original-paper"
        self.reseal()
        self.case.reject_without_writes("same original source paper")

    def test_all_eight_original_anchor_mismatches_still_fail_after_rehash(self):
        for anchor in binding.engine().improvement.ANCHORS:
            with self.subTest(anchor=anchor):
                original = self.reproduction["same_task"][anchor]["description"]
                self.reproduction["same_task"][anchor]["description"] = "Invented changed original " + anchor
                self.reseal()
                self.case.reject_without_writes("original scientific anchor differs")
                self.reproduction["same_task"][anchor]["description"] = original

    def test_retained_structured_roles_keep_their_types_and_cannot_be_rewritten(self):
        binder.write_or_check(self.root, write=True)
        registry = self.source.load(binding.REGISTRY)
        row = registry["tasks"][0]
        task = self.source.load(self.case.task_path)
        retained = task["source_scope_correction"]["retained_source_roles"]
        self.assertIs(retained["legacy"]["endpoint_eligible"], False)
        self.assertIs(type(retained["legacy"]["observed_count"]), int)
        self.assertIsNone(retained["components"][0]["scientific_result"])
        _, bound = self.bound()
        public = binding.public_summary(row, bound)["primary_scope_correction"]["retained_source_roles"]
        self.assertEqual(binding.encode(public), binding.encode(self.correction["retained_source_roles"]))
        # False == 0 in Python; the exact raw projected definition must still
        # distinguish their JSON types after all current-file pins are refreshed.
        retained["legacy"]["endpoint_eligible"] = 0
        raw = self.case.put(self.case.task_path, task)
        row["specification"] = binding.pin(self.case.task_path, raw)
        self.outcomes["original_task_sha256"] = row["specification"]["sha256"]
        outcome_path = self.home + "/" + binding.OUTCOMES
        row["paper_outcomes"]["outcomes"] = binding.pin(outcome_path, self.case.put(outcome_path, self.outcomes))
        self.case.put(binding.REGISTRY, registry)
        self.case.reject_without_writes("deterministic dual-outcome projection")

    def test_scalar_retained_roles_are_refused(self):
        self.correction["retained_source_roles"] = True
        self.save_scope()
        self.case.reject_without_writes("Invalid retained source roles")

    def test_absent_active_map_keeps_generic_projection_bytes(self):
        generic = binding.encode(binding.project_task(self.prior_task, self.prior_row, self.improvement))
        artifact = copy.deepcopy(self.scope)
        artifact.pop("same_primary_corrections")
        artifact["source_gap_confirmations"] = {self.identifier: {
            **copy.deepcopy(self.correction), "projection_action": "none"}}
        validated = binding.scope_decisions(artifact)
        passive = validated.get("same_primary_corrections", {}).get(self.identifier)
        actual = binding.encode(binding.project_task(self.prior_task, self.prior_row, self.improvement,
                                                     primary_correction=passive))
        self.assertEqual(actual, generic)

    def test_passive_only_confirmation_adopts_without_changing_generic_task_bytes(self):
        generic = binding.encode(binding.project_task(self.prior_task, self.prior_row, self.improvement))
        self.scope.pop("same_primary_corrections")
        self.scope["source_gap_confirmations"] = {self.identifier: {
            "task_id": self.identifier, "projection_action": "none",
            "remaining_source_limits": ["Invented original inputs remain unresolved."],
            "scientific_outcome": "unknown",
        }}
        self.save_scope()
        self.reseal(correction=False)
        binder.write_or_check(self.root, write=True)
        self.assertEqual((self.root / self.case.task_path).read_bytes(), generic)
        self.assertEqual(binder.validate_existing(self.root)["paper_tasks"], 1)
        self.assertEqual(binder.write_or_check(self.root, check=True)["changed_files"], 0)
        row, bound = self.bound()
        self.assertIsNone(bound["primary_scope_correction"])
        self.assertNotIn("primary_scope_correction", binding.public_summary(row, bound))

    def test_passive_and_active_maps_cannot_share_the_same_identity(self):
        self.scope["source_gap_confirmations"] = {self.identifier: {
            "task_id": self.identifier, "projection_action": "none", "scientific_outcome": "unknown"}}
        self.save_scope()
        self.case.reject_without_writes("separate from scope corrections")

    def test_unavailable_map_rejects_normal_adoption_route(self):
        next(iter(self.scope["entries"].values()))["adoption_route"] = "normal_same_primary_unqualified"
        with self.assertRaisesRegex(ValueError, "route differs from its unavailable map"):
            binding.scope_decisions(self.scope)

    def test_normal_map_rejects_unavailable_adoption_route(self):
        self.correction["adoption_route"] = "full_primary_pairing_unavailable"
        with self.assertRaisesRegex(ValueError, "route differs from its normal correction map"):
            binding.scope_decisions(self.scope)

    def test_passive_map_rejects_active_adoption_route(self):
        self.scope["source_gap_confirmations"] = {"PAPER-PASSIVE-FIXTURE": {
            "task_id": "PAPER-PASSIVE-FIXTURE", "projection_action": "none",
            "adoption_route": "normal_same_primary_unqualified", "scientific_outcome": "unknown"}}
        with self.assertRaisesRegex(ValueError, "Invalid passive source-gap confirmation"):
            binding.scope_decisions(self.scope)

    def test_explicit_unavailable_route_is_not_reclassified_by_legacy_disposition(self):
        identifier = sorted(binding.SCOPE_IDS)[0]
        entry = self.scope["entries"][identifier]
        entry["disposition"] = "same_primary_unqualified"
        entry["adoption_route"] = "full_primary_pairing_unavailable"
        validated = binding.scope_decisions(self.scope)
        self.assertEqual(validated["entries"][identifier]["adoption_route"], "full_primary_pairing_unavailable")
        self.assertEqual(validated["entries"][identifier]["paired_bundle_status"],
                         "unavailable_primary_secondary_scope_mismatch")
        self.assertNotIn(identifier, validated["same_primary_corrections"])

    def test_unchanged_generic_identity_cannot_bind_the_corrected_task(self):
        self.reseal(correction=False)
        self.case.reject_without_writes("raw current task identity")


if __name__ == "__main__":
    unittest.main()
