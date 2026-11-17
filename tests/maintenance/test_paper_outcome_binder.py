"""Small, invented controls for the explicit paper outcome metadata binder.

The shared fixture supplies real legacy lineage and an implementation which
raises if executed. These controls exercise metadata only, with no native data.
"""
import copy
import importlib.util
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
fixtures = runpy.run_path(str(ROOT / "tests/maintenance/test_paper_outcomes_integrity.py"))
spec = importlib.util.spec_from_file_location(
    "_paper_outcome_binder_controls", ROOT / "scripts/maintenance/bind_paper_outcomes.py")
binder = importlib.util.module_from_spec(spec)
exec(compile(spec.loader.get_source(spec.name), str(spec.origin), "exec"), binder.__dict__)
binding = binder.binding


class PaperOutcomeBinderTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures["PaperOutcomesIntegrityTests"](
            "test_three_definition_chain_preserves_original_source_without_execution")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.home = self.fixture.home
        self.task_path = self.fixture.task_path
        self.history = self.home + "/" + binding.HISTORY
        # Start immediately before outcome adoption, retaining the independently
        # supplied sidecars whose identity is the deterministic new definition.
        self.fixture.put(self.task_path, self.fixture.prior_task_bytes)
        self.fixture.put(binding.REGISTRY, self.fixture.prior_registry)
        (self.root / binding.SNAPSHOT).unlink()
        (self.root / self.history).unlink()
        self.before = self.snapshot()

    def snapshot(self):
        return {path.relative_to(self.root).as_posix(): path.read_bytes()
                for path in self.root.rglob("*") if path.is_file() and not path.is_symlink()}

    def put(self, name, value):
        return self.fixture.put(name, value)

    def reject_without_writes(self, expression=None):
        before = self.snapshot()
        if expression is None:
            context = self.assertRaises(ValueError)
        else:
            context = self.assertRaisesRegex(ValueError, expression)
        with context:
            binder.write_or_check(self.root, write=True)
        self.assertEqual(self.snapshot(), before)

    def test_default_plan_is_read_only_and_names_only_metadata_outputs(self):
        report = binder.write_or_check(self.root)
        self.assertEqual(report["status"], "planned")
        self.assertEqual(report["registered_tasks"], 2)
        self.assertEqual(report["paper_tasks"], 1)
        self.assertFalse(report["scientific_qualification"])
        self.assertGreater(report["bytes_read"], 0)
        self.assertEqual(set(report["changed_paths"]), {
            binding.REGISTRY, binding.SNAPSHOT, self.task_path, self.history})
        self.assertEqual(self.snapshot(), self.before)

    def test_check_before_adoption_refuses_and_does_not_write(self):
        with self.assertRaisesRegex(ValueError, "stale or missing"):
            binder.write_or_check(self.root, check=True)
        self.assertEqual(self.snapshot(), self.before)

    def test_write_preserves_all_predecessors_and_supplied_contract_bytes(self):
        outputs, report = binder.build_outputs(self.root)
        self.assertEqual(self.snapshot(), self.before)
        written = binder.write_or_check(self.root, write=True)
        self.assertEqual(written["status"], "written")
        self.assertEqual(written["changed_files"], 4)
        after = self.snapshot()
        self.assertEqual(after[binding.SNAPSHOT], self.before[binding.REGISTRY])
        self.assertEqual(after[self.history], self.before[self.task_path])
        self.assertNotEqual(after[self.task_path], self.before[self.task_path])
        for name, body in self.before.items():
            if name not in (binding.REGISTRY, self.task_path):
                self.assertEqual(after[name], body, name)
        for name, body in outputs.items():
            self.assertEqual(after[name], body, name)
        self.assertFalse(report["scientific_qualification"])
        self.assertEqual(binder.validate_existing(self.root)["paper_tasks"], 1)

    def test_write_then_check_and_repeat_write_are_idempotent(self):
        binder.write_or_check(self.root, write=True)
        after = self.snapshot()
        self.assertEqual(binder.write_or_check(self.root, check=True)["changed_files"], 0)
        self.assertEqual(binder.write_or_check(self.root)["changed_files"], 0)
        self.assertEqual(binder.write_or_check(self.root, write=True)["changed_files"], 0)
        self.assertEqual(self.snapshot(), after)

    def test_current_raw_bytes_must_match_registered_pin(self):
        self.put(self.task_path, self.fixture.prior_task_bytes + b" ")
        self.reject_without_writes("pin mismatch|bytes changed")

    def test_improvement_contract_cannot_change_while_rebinding(self):
        name = self.home + "/improvement.v1.json"
        self.put(name, self.fixture.read(name) + b" ")
        self.reject_without_writes("pin mismatch")

    def test_descriptor_must_bind_new_raw_task_not_predecessor(self):
        outcomes = copy.deepcopy(self.fixture.outcomes)
        outcomes["original_task_sha256"] = self.fixture.prior_row["specification"]["sha256"]
        self.put(self.home + "/" + binding.OUTCOMES, outcomes)
        self.reject_without_writes("raw current task identity")

    def test_supplied_reproduction_contract_digest_must_match_descriptor(self):
        reproduction = copy.deepcopy(self.fixture.reproduction)
        reproduction["findings"][0]["expected"] = 81.0
        self.put(self.home + "/" + binding.REPRODUCTION, reproduction)
        self.reject_without_writes("Invalid paper outcome contracts")

    def test_existing_wrong_snapshot_is_never_replaced(self):
        self.put(binding.SNAPSHOT, b"{}\n")
        self.reject_without_writes("replace an existing pre-outcomes registry")

    def test_existing_wrong_task_archive_is_never_replaced(self):
        self.put(self.history, b"{}\n")
        self.reject_without_writes("replace a pre-outcomes task archive")

    def test_existing_identical_immutable_archives_are_reused(self):
        self.put(binding.SNAPSHOT, self.before[binding.REGISTRY])
        self.put(self.history, self.before[self.task_path])
        report = binder.write_or_check(self.root, write=True)
        self.assertEqual(set(report["changed_paths"]), {binding.REGISTRY, self.task_path})
        self.assertEqual(binder.write_or_check(self.root, check=True)["changed_files"], 0)

    def test_task_directory_cannot_redirect_metadata_writes(self):
        registry = copy.deepcopy(self.fixture.prior_registry)
        registry["tasks"][0]["task_directory"] = "benchmarks/paper/../redirected"
        self.put(binding.REGISTRY, registry)
        self.reject_without_writes("directory does not match")

    def test_duplicate_task_identity_cannot_collapse_coverage(self):
        registry = copy.deepcopy(self.fixture.prior_registry)
        registry["tasks"][1]["id"] = registry["tasks"][0]["id"]
        self.put(binding.REGISTRY, registry)
        self.reject_without_writes("Duplicate registered task identity")

    def test_declared_task_counts_cannot_inflate_coverage(self):
        registry = copy.deepcopy(self.fixture.prior_registry)
        registry["source_counts"]["paper"] += 1
        self.put(binding.REGISTRY, registry)
        self.reject_without_writes("exact registered task counts")

    def test_linked_current_task_is_rejected_before_any_write(self):
        original = self.root / self.task_path
        target = self.root / "untouched-task.json"
        target.write_bytes(original.read_bytes())
        original.unlink()
        original.symlink_to(target)
        self.reject_without_writes("[Ll]ink|[Ss]ymlink")
        self.assertTrue(original.is_symlink())

    def test_linked_archive_destination_is_rejected_before_any_write(self):
        target = self.root / "untouched-archive.json"
        target.write_bytes(self.fixture.prior_task_bytes)
        (self.root / self.history).symlink_to(target)
        self.reject_without_writes("[Ll]ink|[Ss]ymlink")
        self.assertTrue((self.root / self.history).is_symlink())

    def test_adopted_archive_drift_is_not_silently_repaired(self):
        binder.write_or_check(self.root, write=True)
        self.put(self.history, self.fixture.prior_task_bytes + b" ")
        self.reject_without_writes("pin mismatch")

    def test_duplicate_json_keys_are_rejected_before_any_write(self):
        name = self.home + "/" + binding.OUTCOMES
        body = self.fixture.read(name)
        # Both values agree: accepting this still permits ambiguous producer
        # identities when downstream tools disagree about duplicate-key policy.
        duplicate = b'{"task_id": "' + self.fixture.identifier.encode() + b'",'
        self.put(name, duplicate + body[1:])
        self.reject_without_writes("[Dd]uplicate")

    def test_sidecar_change_between_preflights_prevents_metadata_writes(self):
        build = binder.build_outputs
        calls = 0
        changed = None

        def change_then_build(root):
            nonlocal calls, changed
            calls += 1
            if calls == 2:
                outcomes = copy.deepcopy(self.fixture.outcomes)
                outcomes["original_task_sha256"] = "0" * 64
                self.put(self.home + "/" + binding.OUTCOMES, outcomes)
                changed = self.snapshot()
            return build(root)

        with mock.patch.object(binder, "build_outputs", side_effect=change_then_build):
            with self.assertRaisesRegex(ValueError, "raw current task identity"):
                binder.write_or_check(self.root, write=True)
        self.assertEqual(calls, 2)
        self.assertEqual(self.snapshot(), changed)
        self.assertFalse((self.root / binding.SNAPSHOT).exists())

    def test_destination_change_after_second_plan_prevents_metadata_writes(self):
        build = binder.build_outputs
        calls = 0
        changed = None

        def build_then_change(root):
            nonlocal calls, changed
            result = build(root)
            calls += 1
            if calls == 2:
                self.put(self.task_path, self.fixture.prior_task_bytes + b" ")
                changed = self.snapshot()
            return result

        with mock.patch.object(binder, "build_outputs", side_effect=build_then_change):
            with self.assertRaisesRegex(ValueError, "destination changed during preflight"):
                binder.write_or_check(self.root, write=True)
        self.assertEqual(calls, 2)
        self.assertEqual(self.snapshot(), changed)
        self.assertFalse((self.root / binding.SNAPSHOT).exists())

    def test_conflicting_modes_refuse_without_writes(self):
        with self.assertRaisesRegex(ValueError, "Choose either write or check"):
            binder.write_or_check(self.root, write=True, check=True)
        self.assertEqual(self.snapshot(), self.before)


class UnavailablePaperOutcomeBinderTests(unittest.TestCase):
    """One invented special-ID roster with all four invented public decisions."""

    snapshot = PaperOutcomeBinderTests.snapshot
    reject_without_writes = PaperOutcomeBinderTests.reject_without_writes

    def setUp(self, identifier="PAPER-FIND-013"):
        temporary = tempfile.TemporaryDirectory(prefix="invented-unavailable-paper-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.identifier = identifier
        self.home = "benchmarks/paper/" + self.identifier
        self.task_path = self.home + "/task.json"
        self.reproduction, self.improvement, self.normal_outcomes, _, _ = fixtures["scientific"]["fixture"]()
        for document in (self.reproduction, self.improvement, self.normal_outcomes):
            document["task_id"] = self.identifier
        original_raw = self.put(self.task_path, {"id": self.identifier, "track": "paper"})
        self.put(self.home + "/improvement.v1.json", self.improvement)
        original_row = {
            "id": self.identifier, "title": "Invented scope correction", "track": "paper",
            "task_directory": self.home, "specification_id": self.identifier,
            "specification_alias": False, "registration_class": "expansion",
            "specification": binding.pin(self.task_path, original_raw),
            "original_specification": binding.pin("retired/invented-primary.json", original_raw),
        }
        self.put(binding.REGISTRY, {
            "schema_version": 1, "kind": "neuroscience_benchmark_registry",
            "source_counts": {"paper": 1, "neural": 0, "total": 1},
            "tasks": [original_row], "implementations": [],
        })
        self.put("src/neurobench/paper_improvement.py", (ROOT / "src/neurobench/paper_improvement.py").read_bytes())
        for name, body in fixtures["old_binder"].build_outputs(self.root, expected_count=1).items():
            self.put(name, body)
        self.prior_registry = self.load(binding.REGISTRY)
        self.prior_row = self.prior_registry["tasks"][0]
        self.prior_task = self.load(self.task_path)
        self.prior_task_bytes = (self.root / self.task_path).read_bytes()
        self.scope = {"schema_version": binding.SCOPE_VERSION, "entries": {
            identifier: {
                "task_id": identifier,
                "primary_goal": "Recreate the invented primary empirical finding for " + identifier,
                "primary_scope": "Invented primary source panel and its controls for " + identifier,
                "retained_secondary_scope": "Invented distinct secondary numeric endpoint for " + identifier,
                "remaining_source_limits": ["Invented primary source panel has not been recovered."],
                "primary_same_task_improvement": "unavailable_until_independently_justified",
                "paired_bundle_status": "unavailable_primary_secondary_scope_mismatch",
                "scientific_outcome": "unknown",
            } for identifier in sorted(binding.SCOPE_IDS | {self.identifier})}}
        self.scope_pin = binding.pin(binding.SCOPE_PATH, self.put(binding.SCOPE_PATH, self.scope))
        self.entry = self.scope["entries"][self.identifier]
        self.projected = binding.project_task(self.prior_task, self.prior_row, self.improvement, self.entry)
        self.current_pin = binding.pin(self.task_path, binding.encode(self.projected))
        self.marker = {
            "schema_version": binding.UNAVAILABLE, "task_id": self.identifier,
            "original_task_sha256": self.current_pin["sha256"], "status": "unavailable",
            "reason_code": "primary_secondary_scope_mismatch",
            "reason": "Invented secondary numeric endpoint cannot establish the primary empirical finding.",
            "primary_scope": self.entry["primary_scope"],
            "retained_secondary_improvement": {
                "path": "improvement.v1.json",
                "raw_sha256": self.prior_row["specification_revision"]["improvement_contract"]["sha256"],
                "contract_digest": binding.engine().contract_digest(self.improvement),
                "scope_description": self.entry["retained_secondary_scope"],
            },
            "root_scope_decision": {"path": binding.SCOPE_PATH, "raw_sha256": self.scope_pin["sha256"],
                                    "task_entry_id": self.identifier},
        }
        self.save_marker()
        self.before = self.snapshot()

    def put(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        body = value if isinstance(value, bytes) else binding.encode(value)
        path.write_bytes(body)
        return body

    def load(self, name):
        return binding.engine().loads_contract((self.root / name).read_text())

    def save_marker(self):
        self.put(self.home + "/" + binding.OUTCOMES, self.marker)

    def add_proposal(self):
        self.reproduction["same_task"]["target"]["description"] = self.entry["primary_scope"]
        body = self.put(self.home + "/" + binding.REPRODUCTION, self.reproduction)
        self.marker["reproduction_proposal"] = {
            "path": binding.REPRODUCTION, "raw_sha256": binding.pin(binding.REPRODUCTION, body)["sha256"],
            "contract_digest": binding.engine().contract_digest(self.reproduction),
        }
        self.save_marker()

    def bound(self):
        registry = self.load(binding.REGISTRY)
        row = registry["tasks"][0]
        reader = binder.checker.Reader(self.root)
        read_pin = lambda pin, label: binder.read_pinned(reader, pin, label)
        previous = binding.coverage(registry, read_pin)
        return row, binding.context(row, self.load(self.task_path), previous, read_pin)

    def test_marker_without_proposal_preserves_history_and_labels_all_cells_unknown(self):
        report = binder.write_or_check(self.root, write=True)
        self.assertEqual(report["paper_tasks"], 1)
        self.assertFalse(report["scientific_qualification"])
        self.assertEqual(self.load(self.task_path)["goal"], self.entry["primary_goal"])
        self.assertEqual((self.root / self.home / binding.HISTORY).read_bytes(), self.prior_task_bytes)
        self.assertEqual((self.root / binding.SNAPSHOT).read_bytes(), self.before[binding.REGISTRY])
        self.assertEqual((self.root / self.home / "improvement.v1.json").read_bytes(),
                         self.before[self.home + "/improvement.v1.json"])
        row, bound = self.bound()
        self.assertNotIn("reproduction_contract", row["paper_outcomes"])
        self.assertIsNone(bound["reproduction_contract"])
        public = binding.public_summary(row, bound)
        self.assertEqual(public["availability"], "unavailable")
        self.assertEqual(public["scientific_outcomes"], {"reproduction": "unknown", "improvement": "unknown"})
        self.assertEqual(len(public["cells"]), 4)
        for cell in public["cells"]:
            self.assertEqual(cell["scientific_outcome"], "unknown")
            self.assertFalse(cell["endpoint_eligible"])
            self.assertFalse(cell["condition_available"])
            self.assertIsNone(cell["receipt"])
        self.assertEqual(binder.validate_existing(self.root)["paper_tasks"], 1)
        self.assertEqual(binder.write_or_check(self.root, check=True)["changed_files"], 0)

    def test_explicit_primary_proposal_does_not_admit_any_primary_receipt(self):
        self.add_proposal()
        proposal_before = (self.root / self.home / binding.REPRODUCTION).read_bytes()
        binder.write_or_check(self.root, write=True)
        row, bound = self.bound()
        self.assertEqual(bound["reproduction_contract"], self.reproduction)
        self.assertEqual((self.root / self.home / binding.REPRODUCTION).read_bytes(), proposal_before)
        public = binding.public_summary(row, bound)
        self.assertEqual(public["reproduction_eligibility"], self.reproduction["eligibility"])
        self.assertEqual(public["availability"], "unavailable")
        self.assertTrue(all(cell["scientific_outcome"] == "unknown" for cell in public["cells"]))
        result = binding.engine().admit_outcome(self.marker, self.reproduction, self.improvement, {})
        self.assertFalse(result["metadata_admitted"])
        self.assertIsNone(result["criterion_satisfied"])
        self.assertEqual(result["scientific_outcome"], "unknown")
        self.assertTrue(result["errors"])

    def test_unbound_existing_proposal_is_rejected(self):
        self.put(self.home + "/" + binding.REPRODUCTION, self.reproduction)
        self.reject_without_writes("proposal must be explicitly bound")

    def test_marker_task_digest_must_bind_corrected_current_definition(self):
        self.marker["original_task_sha256"] = self.prior_row["specification"]["sha256"]
        self.save_marker()
        self.reject_without_writes("bind its corrected primary scope")

    def test_marker_primary_scope_cannot_be_replaced_with_secondary_scope(self):
        self.marker["primary_scope"] = self.entry["retained_secondary_scope"]
        self.save_marker()
        self.reject_without_writes("bind its corrected primary scope")

    def test_marker_cannot_reference_another_tasks_source_decision(self):
        self.marker["root_scope_decision"]["task_entry_id"] = "PAPER-FIND-REP-007"
        self.save_marker()
        self.reject_without_writes("scope decision mismatch")

    def test_marker_requires_actual_raw_scope_artifact_identity(self):
        self.marker["root_scope_decision"]["raw_sha256"] = "0" * 64
        self.save_marker()
        self.reject_without_writes("scope decision mismatch")

    def test_adopted_scope_artifact_bytes_cannot_change(self):
        binder.write_or_check(self.root, write=True)
        self.put(binding.SCOPE_PATH, (self.root / binding.SCOPE_PATH).read_bytes() + b" ")
        self.reject_without_writes("Paper scope decisions pin mismatch")

    def test_scope_artifact_cannot_qualify_an_outcome(self):
        self.scope["entries"][self.identifier]["scientific_outcome"] = "success"
        self.put(binding.SCOPE_PATH, self.scope)
        self.reject_without_writes("cannot qualify a primary outcome")

    def test_scope_artifact_requires_all_four_decisions_even_for_one_task_roster(self):
        del self.scope["entries"]["PAPER-FIND-REP-007"]
        self.put(binding.SCOPE_PATH, self.scope)
        self.reject_without_writes("retain the adjudicated tasks")

    def test_normal_bundle_cannot_pair_primary_with_secondary(self):
        self.normal_outcomes["original_task_sha256"] = self.current_pin["sha256"]
        self.normal_outcomes["contracts"] = {
            "reproduction": binding.engine().contract_digest(self.reproduction),
            "improvement": binding.engine().contract_digest(self.improvement),
        }
        self.put(self.home + "/" + binding.REPRODUCTION, self.reproduction)
        self.put(self.home + "/" + binding.OUTCOMES, self.normal_outcomes)
        self.reject_without_writes("mixed-scope normal outcome bundle")

    def test_closed_marker_rejects_extra_claimed_scientific_result(self):
        self.marker["scientific_outcome"] = "qualified"
        self.save_marker()
        self.reject_without_writes("Invalid unavailable outcome marker")

    def test_retained_secondary_raw_digest_cannot_be_substituted(self):
        self.marker["retained_secondary_improvement"]["raw_sha256"] = "0" * 64
        self.save_marker()
        self.reject_without_writes("changed the retained secondary contract or scope")

    def test_optional_proposal_raw_and_canonical_identities_are_both_required(self):
        self.add_proposal()
        self.marker["reproduction_proposal"]["raw_sha256"] = "0" * 64
        self.save_marker()
        self.reject_without_writes("proposal identity mismatch")
        self.marker["reproduction_proposal"]["raw_sha256"] = binding.pin(
            binding.REPRODUCTION, (self.root / self.home / binding.REPRODUCTION).read_bytes())["sha256"]
        self.marker["reproduction_proposal"]["contract_digest"] = "0" * 64
        self.save_marker()
        self.reject_without_writes("proposal identity mismatch")

    def test_secondary_proposal_cannot_be_adopted_by_rehashing_all_its_identities(self):
        self.add_proposal()
        self.reproduction["same_task"]["target"]["description"] = self.entry["retained_secondary_scope"]
        raw = self.put(self.home + "/" + binding.REPRODUCTION, self.reproduction)
        self.marker["reproduction_proposal"] = {
            "path": binding.REPRODUCTION, "raw_sha256": binding.pin(binding.REPRODUCTION, raw)["sha256"],
            "contract_digest": binding.engine().contract_digest(self.reproduction),
        }
        self.save_marker()
        self.reject_without_writes("primary scope|corrected primary")

    def additional_scope_fixture(self):
        fixture = type(self)("test_marker_without_proposal_preserves_history_and_labels_all_cells_unknown")
        self.addCleanup(fixture.doCleanups)
        fixture.setUp(identifier="PAPER-FIND-024")
        return fixture

    def test_additional_reviewed_scope_entry_dispatches_without_hardcoded_task_set(self):
        fixture = self.additional_scope_fixture()
        self.assertNotIn(fixture.identifier, binding.SCOPE_IDS)
        self.assertEqual(set(fixture.scope["entries"]), binding.SCOPE_IDS | {fixture.identifier})
        binder.write_or_check(fixture.root, write=True)
        row, bound = fixture.bound()
        self.assertEqual(bound["availability"], "unavailable")
        self.assertEqual(fixture.load(fixture.task_path)["goal"], fixture.entry["primary_goal"])
        self.assertEqual(row["id"], "PAPER-FIND-024")
        self.assertTrue(all(cell["scientific_outcome"] == "unknown" for cell in bound["summary"]["cells"]))
        self.assertEqual(binder.validate_existing(fixture.root)["paper_tasks"], 1)

    def test_additional_marker_requires_its_own_explicit_scope_entry(self):
        fixture = self.additional_scope_fixture()
        del fixture.scope["entries"][fixture.identifier]
        raw = fixture.put(binding.SCOPE_PATH, fixture.scope)
        fixture.marker["root_scope_decision"]["raw_sha256"] = binding.pin(binding.SCOPE_PATH, raw)["sha256"]
        fixture.save_marker()
        fixture.reject_without_writes("mixed-scope normal outcome bundle")

    def test_additional_marker_cannot_mutate_task_identity(self):
        fixture = self.additional_scope_fixture()
        fixture.marker["task_id"] = "PAPER-FIND-013"
        fixture.save_marker()
        fixture.reject_without_writes("bind its corrected primary scope")

    def test_primary_proposal_cannot_change_paper_url_with_recomputed_identities(self):
        self.add_proposal()
        self.reproduction["source_paper"]["url"] = "https://example.invalid/a-different-paper"
        raw = self.put(self.home + "/" + binding.REPRODUCTION, self.reproduction)
        self.marker["reproduction_proposal"] = {
            "path": binding.REPRODUCTION, "raw_sha256": binding.pin(binding.REPRODUCTION, raw)["sha256"],
            "contract_digest": binding.engine().contract_digest(self.reproduction),
        }
        self.save_marker()
        self.reject_without_writes("retain its source paper identity")


if __name__ == "__main__":
    unittest.main()
