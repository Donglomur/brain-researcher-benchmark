"""Generated whole-binder controls for two absent paper declarations.

The roster and scientific policies are invented. The real old binder constructs
their lineage; no paper, native payload, implementation or model is executed.
"""
import copy
from pathlib import Path
import runpy
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
support = runpy.run_path(str(ROOT / "tests/maintenance/test_paper_declaration_gaps.py"))
binder, binding, gaps = support["binder"], support["binding"], support["gaps"]
legacy = support["fixtures"]["fixtures"]


class DeclarationGapFixture(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="invented-declaration-gap-binding-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.identifiers = sorted(gaps.TASK_IDS)
        self.identifier = self.identifiers[0]
        self.home = "benchmarks/paper/" + self.identifier
        self.task_path = self.home + "/task.json"
        rows, improvements = [], {}
        for identifier in self.identifiers:
            home = "benchmarks/paper/" + identifier
            _, improvement, _, _, _ = legacy["scientific"]["fixture"]()
            improvement["task_id"] = identifier
            improvements[identifier] = improvement
            original = {"id": identifier, "track": "paper",
                        "input_assets": {"labels_visible": False, "signal": "invented source"},
                        "resources": {"max_threads": 1, "budget": "invented"}}
            original_raw = self.put(home + "/task.json", original)
            self.put(home + "/improvement.v1.json", improvement)
            rows.append({"id": identifier, "title": "Invented source declaration gap", "track": "paper",
                         "task_directory": home, "specification_id": identifier, "specification_alias": False,
                         "registration_class": "expansion",
                         "specification": binding.pin(home + "/task.json", original_raw),
                         "original_specification": binding.pin("retired/" + identifier + ".json", original_raw)})
        self.put(binding.REGISTRY, {"schema_version": 1, "kind": "neuroscience_benchmark_registry",
                                   "source_counts": {"paper": 2, "neural": 0, "total": 2},
                                   "tasks": rows, "implementations": []})
        self.put("src/neurobench/paper_improvement.py", (ROOT / "src/neurobench/paper_improvement.py").read_bytes())
        for name, body in legacy["old_binder"].build_outputs(self.root, expected_count=2).items():
            self.put(name, body)
        self.prior_registry = self.load(binding.REGISTRY)
        self.prior_rows = {row["id"]: row for row in self.prior_registry["tasks"]}
        self.cases = {identifier: SimpleNamespace(prior_row=self.prior_rows[identifier],
                                                  improvement=improvements[identifier])
                      for identifier in self.identifiers}
        self.record = support["record"](self.cases)
        self.record_pin = binding.pin(gaps.PATH, self.put(gaps.PATH, self.record))
        trusted_pin = mock.patch.object(binding, "SOURCE_DECLARATION_GAP_PIN", copy.deepcopy(self.record_pin))
        trusted_pin.start()
        self.addCleanup(trusted_pin.stop)
        self.before = self.snapshot()

    def put(self, relative, value):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = value if isinstance(value, bytes) else binding.encode(value)
        path.write_bytes(raw)
        return raw

    def load(self, relative):
        return binding.engine().loads_contract((self.root / relative).read_text())

    def snapshot(self):
        return {path.relative_to(self.root).as_posix(): path.read_bytes()
                for path in self.root.rglob("*") if path.is_file() and not path.is_symlink()}

    def adopt(self):
        return binder.write_or_check(self.root, write=True)

    def reject_without_writes(self, pattern=None):
        before = self.snapshot()
        with self.assertRaisesRegex((ValueError, OSError), pattern or "."):
            binder.write_or_check(self.root, write=True)
        self.assertEqual(self.snapshot(), before)

    def bound(self, identifier=None):
        identifier = self.identifier if identifier is None else identifier
        registry = self.load(binding.REGISTRY)
        row = next(row for row in registry["tasks"] if row["id"] == identifier)
        reader = binder.checker.Reader(self.root)
        read = lambda pin, label: binder.read_pinned(reader, pin, label)
        previous = binding.coverage(registry, read)
        return row, binding.context(row, self.load(row["specification"]["path"]), previous, read)

    def save_registry(self, registry):
        self.put(binding.REGISTRY, registry)


class DeclarationGapBindingTests(DeclarationGapFixture):
    def test_source_only_roster_is_valid_without_adopting_or_requiring_record(self):
        (self.root / gaps.PATH).unlink()
        calls = []
        previous = binding.coverage(self.prior_registry, lambda *args: calls.append(args))
        self.assertIsNone(previous)
        for row in self.prior_registry["tasks"]:
            self.assertFalse(binding.has_source_declaration_gap(row))
            self.assertIsNone(binding.context(row, self.load(row["specification"]["path"]), None,
                                              lambda *args: calls.append(args)))
        self.assertEqual(calls, [])

    def test_read_only_plan_emits_only_registry_current_and_exact_archives(self):
        outputs, report = binder.build_outputs(self.root)
        self.assertEqual(self.snapshot(), self.before)
        expected = {binding.REGISTRY, binding.SNAPSHOT}
        for identifier in self.identifiers:
            home = "benchmarks/paper/" + identifier
            expected.update((home + "/task.json", home + "/" + binding.HISTORY))
        self.assertEqual(set(outputs), expected)
        self.assertEqual(report["registered_tasks"], 2)
        self.assertEqual(report["paper_tasks"], 2)
        self.assertFalse(report["scientific_qualification"])
        self.assertEqual(binder.write_or_check(self.root)["status"], "planned")
        self.assertEqual(self.snapshot(), self.before)

    def test_adoption_preserves_original_lineage_and_independent_improvement(self):
        self.adopt()
        self.assertEqual((self.root / binding.SNAPSHOT).read_bytes(), self.before[binding.REGISTRY])
        registry = self.load(binding.REGISTRY)
        self.assertEqual(registry["paper_outcomes"]["source_declaration_gaps"], self.record_pin)
        self.assertEqual({row["id"] for row in registry["tasks"]}, set(self.identifiers))
        for identifier in self.identifiers:
            with self.subTest(identifier=identifier):
                home = "benchmarks/paper/" + identifier
                row, context = self.bound(identifier)
                self.assertEqual(set(row["paper_outcomes"]),
                                 {"schema_version", "previous_specification", "source_declaration_gap"})
                self.assertEqual(row["paper_outcomes"]["source_declaration_gap"], self.record_pin)
                self.assertEqual(row["specification_revision"], self.prior_rows[identifier]["specification_revision"])
                self.assertEqual((self.root / home / binding.HISTORY).read_bytes(), self.before[home + "/task.json"])
                self.assertEqual((self.root / home / "improvement.v1.json").read_bytes(),
                                 self.before[home + "/improvement.v1.json"])
                self.assertEqual(context["improvement_contract"], self.cases[identifier].improvement)
                self.assertEqual(context["members"], {home + "/" + binding.HISTORY})
                task = self.load(home + "/task.json")
                self.assertEqual(row["specification"], binding.pin(home + "/task.json", binding.encode(task)))
                self.assertIsNone(task["evaluation"]["contracts"]["reproduction"])
                self.assertIsNone(task["evaluation"]["paired_protocol"])
                self.assertEqual(task["input_assets"], {"labels_visible": False, "signal": "invented source"})
                public = binding.public_summary(row, context)
                self.assertEqual(public["availability"], "source_declaration_unavailable")
                self.assertIsNone(public["reproduction_eligibility"])
                self.assertIsNone(public["reproduction_contract"])
                self.assertIsNone(public["outcomes"])
                self.assertFalse(public["scientific_ineligibility_inferred"])
                self.assertFalse(public["improvement_unavailable_by_reproduction_dependency"])
                self.assertEqual(public["improvement_disposition"], self.cases[identifier].improvement["disposition"])
                self.assertEqual(len(public["cells"]), 4)
                for cell in public["cells"]:
                    self.assertEqual(set(cell), {"outcome", "condition", "pairing_status", "metadata_admitted",
                                                 "scientific_outcome", "receipt"})
                    self.assertEqual(cell["scientific_outcome"], "unknown")
                    self.assertFalse(cell["metadata_admitted"])
                    self.assertIsNone(cell["receipt"])
                for filename in (*binding.REPRODUCTION_FILES.values(), binding.OUTCOMES):
                    self.assertFalse((self.root / home / filename).exists())
                    self.assertNotIn(filename.encode(), binding.encode(task))

    def test_write_check_repeat_are_idempotent_with_full_legacy_validation(self):
        self.adopt()
        after = self.snapshot()
        self.assertEqual(binder.validate_existing(self.root)["paper_tasks"], 2)
        self.assertEqual(binder.write_or_check(self.root, check=True)["changed_files"], 0)
        self.assertEqual(binder.write_or_check(self.root)["changed_files"], 0)
        self.assertEqual(self.adopt()["changed_files"], 0)
        self.assertEqual(self.snapshot(), after)

    def test_valid_shaped_unreviewed_initial_record_cannot_self_pin(self):
        changed = copy.deepcopy(self.record)
        changed["entries"][self.identifier]["reason"] = "Invented substituted assessment prose"
        gaps.validate_record(changed)
        self.put(gaps.PATH, changed)
        self.reject_without_writes()
        self.assertFalse((self.root / binding.SNAPSHOT).exists())

    def test_initial_missing_record_and_conflicting_contract_files_fail_before_writes(self):
        raw = (self.root / gaps.PATH).read_bytes()
        (self.root / gaps.PATH).unlink()
        self.reject_without_writes()
        self.put(gaps.PATH, raw)
        for filename in (*binding.REPRODUCTION_FILES.values(), binding.OUTCOMES):
            with self.subTest(filename=filename):
                relative = self.home + "/" + filename
                self.put(relative, {})
                self.reject_without_writes()
                (self.root / relative).unlink()

    def test_adopted_missing_whole_row_or_global_binding_never_reverts_to_source_only(self):
        self.adopt()
        original = self.load(binding.REGISTRY)
        for mutate in (
            lambda registry: registry["tasks"][0].pop("paper_outcomes"),
            lambda registry: registry.pop("paper_outcomes"),
            lambda registry: registry["paper_outcomes"].pop("source_declaration_gaps"),
        ):
            with self.subTest(mutate=mutate):
                changed = copy.deepcopy(original)
                mutate(changed)
                self.save_registry(changed)
                self.reject_without_writes()
        self.save_registry(original)

    def test_adopted_dropped_task_cannot_recompute_coverage_to_hide_omission(self):
        self.adopt()
        registry = self.load(binding.REGISTRY)
        registry["tasks"].pop()
        registry["source_counts"].update(paper=1, total=1)
        registry["paper_outcomes"]["registered_count"] = 1
        self.save_registry(registry)
        self.reject_without_writes()

    def test_removing_all_outcome_bindings_cannot_downgrade_enrolled_history(self):
        self.adopt()
        registry = self.load(binding.REGISTRY)
        self.assertEqual(sum(pin["path"] == binding.SNAPSHOT
                             for pin in registry["historical_registries"]), 1)
        del registry["paper_outcomes"]
        for row in registry["tasks"]:
            del row["paper_outcomes"]
        with self.assertRaisesRegex(ValueError, "Enrolled pre-outcomes history requires"):
            binding.coverage(registry, lambda *_: self.fail("Downgrade must fail before metadata reads"))
        self.save_registry(registry)
        self.reject_without_writes("Enrolled pre-outcomes history requires")

    def test_row_global_pin_disagreement_wrong_path_and_typed_bytes_are_rejected(self):
        self.adopt()
        original = self.load(binding.REGISTRY)
        for field, value in (("sha256", "0" * 64), ("bytes", True),
                             ("path", "docs/provenance/../untrusted.json")):
            with self.subTest(field=field):
                changed = copy.deepcopy(original)
                changed["tasks"][0]["paper_outcomes"]["source_declaration_gap"][field] = value
                self.save_registry(changed)
                self.reject_without_writes()
        self.save_registry(original)

    def test_gap_cannot_mix_normal_unavailable_or_successor_selectors(self):
        self.adopt()
        original = self.load(binding.REGISTRY)
        for field in ("outcomes", "reproduction_contract", "primary_policy_revision", "primary_improvement_contract"):
            with self.subTest(field=field):
                changed = copy.deepcopy(original)
                changed["tasks"][0]["paper_outcomes"][field] = copy.deepcopy(self.record_pin)
                self.save_registry(changed)
                self.reject_without_writes()
        self.save_registry(original)
        foreign = copy.deepcopy(original["tasks"][0])
        foreign["id"] = "PAPER-FOREIGN-GENERATED"
        with self.assertRaises(ValueError):
            binding.has_source_declaration_gap(foreign)

    def test_adopted_record_archive_and_improvement_drift_are_not_repaired(self):
        self.adopt()
        for relative in (gaps.PATH, self.home + "/" + binding.HISTORY, self.home + "/improvement.v1.json"):
            with self.subTest(relative=relative):
                before = (self.root / relative).read_bytes()
                self.put(relative, before + b" ")
                self.reject_without_writes()
                self.put(relative, before)

    def test_rehashed_current_scientific_mutation_is_not_a_projection(self):
        self.adopt()
        current = self.load(self.task_path)
        current["input_assets"]["labels_visible"] = 0
        raw = self.put(self.task_path, current)
        registry = self.load(binding.REGISTRY)
        registry["tasks"][0]["specification"] = binding.pin(self.task_path, raw)
        self.save_registry(registry)
        self.reject_without_writes()

    def test_record_or_predecessor_mutation_after_coverage_is_read_again(self):
        self.adopt()
        registry = self.load(binding.REGISTRY)
        row = registry["tasks"][0]
        document = self.load(row["specification"]["path"])
        for relative in (gaps.PATH, self.home + "/" + binding.HISTORY):
            with self.subTest(relative=relative):
                reader = binder.checker.Reader(self.root)
                read = lambda pin, label: binder.read_pinned(reader, pin, label)
                previous = binding.coverage(registry, read)
                raw = (self.root / relative).read_bytes()
                self.put(relative, raw + b" ")
                with self.assertRaises(ValueError):
                    binding.context(row, document, previous, read)
                self.put(relative, raw)

    def test_adopted_unowned_sidecars_fail_binder_and_exact_namespace(self):
        self.adopt()
        allowed = {name for name in self.before if name.startswith(self.home + "/")}
        row, context = self.bound()
        allowed.update(context["members"])
        binder.checker.check_namespace(self.root, self.home, set(), allowed)
        for filename in (*binding.REPRODUCTION_FILES.values(), binding.OUTCOMES):
            with self.subTest(filename=filename):
                relative = self.home + "/" + filename
                self.put(relative, {})
                self.reject_without_writes()
                with self.assertRaisesRegex(ValueError, "Orphan source file"):
                    binder.checker.check_namespace(self.root, self.home, set(), allowed)
                (self.root / relative).unlink()

    def test_linked_record_refuses_without_following_or_writing(self):
        path = self.root / gaps.PATH
        target = self.root / "invented-record-target.json"
        target.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(target)
        self.reject_without_writes("[Ll]ink|[Ss]ymlink")
        self.assertTrue(path.is_symlink())

    def test_record_change_between_preflights_prevents_all_binder_writes(self):
        original_build = binder.build_outputs
        calls = 0
        observed = None

        def changed_build(root):
            nonlocal calls, observed
            calls += 1
            if calls == 2:
                self.put(gaps.PATH, (self.root / gaps.PATH).read_bytes() + b" ")
                observed = self.snapshot()
            return original_build(root)

        with mock.patch.object(binder, "build_outputs", side_effect=changed_build):
            with self.assertRaises(ValueError):
                self.adopt()
        self.assertEqual(calls, 2)
        self.assertEqual(self.snapshot(), observed)
        self.assertFalse((self.root / binding.SNAPSHOT).exists())


if __name__ == "__main__":
    unittest.main()
