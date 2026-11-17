"""Versioned contract filenames through real metadata binding and CLI readers.

All contracts and array identities come from generated framework fixtures. No
scientific arrays, native task code, receipt comparisons or models are executed.
"""
import hashlib
import importlib.util
from pathlib import Path
import runpy
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
fixtures = runpy.run_path(str(ROOT / "tests/maintenance/test_paper_outcome_binder.py"))
structured = runpy.run_path(str(ROOT / "tests/framework/test_paper_reproduction_v2.py"))
binder, binding = fixtures["binder"], fixtures["binding"]
VERSION = "paper-reproduction/v2"
FILENAME = "reproduction.v2.json"


def module(name):
    path = ROOT / "src/neurobench" / (name + ".py")
    spec = importlib.util.spec_from_file_location("_paper_version_controls_" + name, path)
    result = importlib.util.module_from_spec(spec)
    exec(compile(path.read_bytes(), str(path), "exec"), result.__dict__)
    return result


cli, catalog = module("cli"), module("catalog")


class PaperOutcomeVersionTests(unittest.TestCase):
    def setUp(self):
        self.case = fixtures["PaperOutcomeBinderTests"](
            "test_default_plan_is_read_only_and_names_only_metadata_outputs")
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.source = self.case.fixture
        self.root, self.home = self.case.root, self.case.home
        self.identifier = self.source.identifier
        self.path = self.home + "/" + FILENAME
        self.improvement_before = (self.root / self.home / "improvement.v1.json").read_bytes()
        self.v1_before = (self.root / self.home / binding.REPRODUCTION).read_bytes()
        self.reproduction, improvement, self.outcomes, _ = structured["fixture"]()
        for document in (self.reproduction, improvement, self.outcomes):
            document["task_id"] = self.identifier
        # The generated v2 example adds structured reproduction output; it must
        # not silently redefine the already authenticated improvement contract.
        self.assertEqual(improvement, self.source.improvement)
        projected = binding.project_task(self.source.prior_task, self.source.prior_row,
                                         improvement, reproduction_version=VERSION)
        self.outcomes["original_task_sha256"] = binding.pin(self.case.task_path, binding.encode(projected))["sha256"]
        self.outcomes["contracts"] = {
            "reproduction": binding.engine(self.reproduction).contract_digest(self.reproduction),
            "improvement": binding.engine().contract_digest(improvement),
        }
        (self.root / self.home / binding.REPRODUCTION).unlink()
        self.case.put(self.path, self.reproduction)
        self.case.put(self.home + "/" + binding.OUTCOMES, self.outcomes)

    def bound(self):
        registry = self.source.load(binding.REGISTRY)
        row = registry["tasks"][0]
        reader = binder.checker.Reader(self.root)
        read_pin = lambda pin, label: binder.read_pinned(reader, pin, label)
        previous = binding.coverage(registry, read_pin)
        bound = binding.context(row, self.source.load(self.case.task_path), previous, read_pin)
        return row, bound

    def test_structured_v2_binds_exact_filename_preserves_history_and_stays_unknown(self):
        report = binder.write_or_check(self.root, write=True)
        self.assertFalse(report["scientific_qualification"])
        self.assertEqual(binder.validate_existing(self.root)["paper_tasks"], 1)
        row, bound = self.bound()
        self.assertEqual(row["paper_outcomes"]["reproduction_contract"]["path"], self.path)
        self.assertEqual(bound["reproduction_contract"], self.reproduction)
        self.assertIn("indexed_array_family", {finding["kind"] for finding in self.reproduction["findings"]})
        self.assertTrue(all(cell["scientific_outcome"] == "unknown" and cell["receipt"] is None
                            for cell in bound["summary"]["cells"]))
        current = self.source.load(self.case.task_path)
        self.assertEqual(current["evaluation"]["contracts"]["reproduction"], FILENAME)
        self.assertEqual((self.root / self.home / "improvement.v1.json").read_bytes(), self.improvement_before)
        self.assertEqual((self.root / self.home / binding.HISTORY).read_bytes(), self.source.prior_task_bytes)
        self.assertEqual(binder.write_or_check(self.root, check=True)["changed_files"], 0)

    def test_cli_reads_selected_v2_source_and_uses_v2_summary(self):
        binder.write_or_check(self.root, write=True)
        row, bound = self.bound()
        view = {"id": self.identifier, "track": "paper", "specification": row["specification"],
                "paper_outcomes": binding.public_summary(row, bound),
                "paper_improvement": {"contract": row["specification_revision"]["improvement_contract"]}}
        # The binder/context above authenticated the actual small complete
        # roster. Supply that verified public view to isolate the CLI's pinned
        # reader; the separate catalog suite covers full-roster navigation.
        with mock.patch.object(cli, "public_catalog_module", return_value=catalog), \
             mock.patch.object(catalog, "load", return_value={"tasks": [view]}), \
             mock.patch.object(cli, "read", side_effect=AssertionError("permissive reread")), \
             mock.patch.object(cli.subprocess, "run", side_effect=AssertionError("implementation executed")):
            self.assertEqual(cli.paper_contract(self.identifier, self.root, outcome="reproduction"), self.reproduction)
            self.assertEqual(cli.paper_contract(self.identifier, self.root), self.source.improvement)
            report = cli.paper_outcomes(self.identifier, self.root)
        self.assertEqual(report["binding"]["reproduction_contract"]["path"], self.path)
        self.assertEqual(report["summary"]["task_count"], 1)
        self.assertTrue(all(cell["scientific_outcome"] == "unknown" for cell in report["summary"]["cells"]))

    def test_v1_default_projection_bytes_match_frozen_pre_version_projection(self):
        default = binding.encode(binding.project_task(self.source.prior_task, self.source.prior_row,
                                                       self.source.improvement))
        explicit = binding.encode(binding.project_task(self.source.prior_task, self.source.prior_row,
                                                        self.source.improvement, reproduction_version="paper-reproduction/v1"))
        self.assertEqual(default, explicit)
        # Captured from project_task at immutable commit 66d7587cb283719ce06bfdad42e706033fea9b0e,
        # using this same invented fixture, before version-filename support.
        self.assertEqual(len(default), 4819)
        self.assertEqual(hashlib.sha256(default).hexdigest(),
                         "63ffd8d6cde01303e0d586506a37e2fe44ab079d15e6610e0f41aa9c2a1892dd")

    def test_unknown_schema_version_is_refused(self):
        self.reproduction["schema_version"] = "paper-reproduction/v999"
        self.case.put(self.path, self.reproduction)
        self.case.reject_without_writes("[Uu]nsupported reproduction")

    def test_v2_content_in_v1_filename_is_refused(self):
        (self.root / self.path).rename(self.root / self.home / binding.REPRODUCTION)
        self.case.reject_without_writes("filename.*schema|schema.*filename")

    def test_v1_content_in_v2_filename_is_refused(self):
        self.case.put(self.path, self.v1_before)
        self.case.reject_without_writes("filename.*schema|schema.*filename")

    def test_two_allowed_filenames_are_ambiguous_even_when_both_are_valid(self):
        self.case.put(self.home + "/" + binding.REPRODUCTION, self.v1_before)
        self.case.reject_without_writes("[Ee]xactly one|[Aa]mbiguous")

    def test_unrecognized_filename_is_not_implicitly_selected(self):
        (self.root / self.path).rename(self.root / self.home / "reproduction.v999.json")
        self.case.reject_without_writes("[Ee]xactly one|[Mm]issing")

    def test_selected_source_raw_pin_is_checked_after_adoption(self):
        binder.write_or_check(self.root, write=True)
        self.case.put(self.path, (self.root / self.path).read_bytes() + b" ")
        self.case.reject_without_writes("[Pp]in mismatch")

    def test_adopted_selector_ignores_unselected_file_but_namespace_rejects_it(self):
        binder.write_or_check(self.root, write=True)
        row, bound = self.bound()
        allowed = bound["members"] | {
            row["specification"]["path"],
            row["specification_revision"]["previous_specification"]["path"],
            row["specification_revision"]["improvement_contract"]["path"],
        }
        boundaries = {self.home + "/implementations/registered-runtime"}
        binder.checker.check_namespace(self.root, self.home, boundaries, allowed)
        unselected = self.home + "/" + binding.REPRODUCTION
        self.case.put(unselected, b'{"schema_version":"paper-reproduction/v1","task_id":"PAPER-WRONG"}\n')
        before = self.case.snapshot()
        self.assertEqual(binder.write_or_check(self.root, check=True)["changed_files"], 0)
        self.assertEqual(binder.write_or_check(self.root, write=True)["changed_files"], 0)
        self.assertEqual(self.case.snapshot(), before)
        selected_row, selected = self.bound()
        self.assertEqual(selected_row["paper_outcomes"]["reproduction_contract"]["path"], self.path)
        self.assertEqual(selected["reproduction_contract"], self.reproduction)
        self.assertEqual(binding.engine(selected["reproduction_contract"]).CONTRACT_VERSION, VERSION)
        with self.assertRaisesRegex(ValueError, "Orphan source file:.*reproduction.v1.json"):
            binder.checker.check_namespace(self.root, self.home, boundaries, allowed)

    def test_missing_or_corrupt_adopted_v2_never_falls_back_to_existing_v1(self):
        binder.write_or_check(self.root, write=True)
        self.case.put(self.home + "/" + binding.REPRODUCTION, self.v1_before)
        selected = self.root / self.path
        original = selected.read_bytes()
        for change in ("corrupt", "missing"):
            with self.subTest(change=change):
                if change == "corrupt":
                    selected.write_bytes(original + b" ")
                else:
                    selected.unlink()
                self.case.reject_without_writes()
                with self.assertRaises(ValueError):
                    binder.validate_existing(self.root)
                self.assertEqual((self.root / self.home / binding.REPRODUCTION).read_bytes(), self.v1_before)
                selected.write_bytes(original)

    def test_rehashed_wrong_filename_cannot_retarget_adopted_binding(self):
        binder.write_or_check(self.root, write=True)
        registry = self.source.load(binding.REGISTRY)
        row = registry["tasks"][0]
        wrong_path = self.home + "/" + binding.REPRODUCTION
        (self.root / self.path).rename(self.root / wrong_path)
        row["paper_outcomes"]["reproduction_contract"] = binding.pin(wrong_path, (self.root / wrong_path).read_bytes())
        self.case.put(binding.REGISTRY, registry)
        self.case.reject_without_writes("filename.*schema|schema.*filename")

    def marker_fixture(self):
        marker = fixtures["UnavailablePaperOutcomeBinderTests"](
            "test_marker_without_proposal_preserves_history_and_labels_all_cells_unknown")
        marker.setUp()
        self.addCleanup(marker.doCleanups)
        reproduction, improvement, _, _ = structured["fixture"]()
        reproduction["task_id"] = marker.identifier
        improvement["task_id"] = marker.identifier
        self.assertEqual(improvement, marker.improvement)
        reproduction["same_task"]["target"]["description"] = marker.entry["primary_scope"]
        raw = marker.put(marker.home + "/" + FILENAME, reproduction)
        marker.marker["reproduction_proposal"] = {
            "path": FILENAME, "raw_sha256": binding.pin(FILENAME, raw)["sha256"],
            "contract_digest": binding.engine(reproduction).contract_digest(reproduction),
        }
        projected = binding.project_task(marker.prior_task, marker.prior_row, marker.improvement,
                                         marker.entry, reproduction_version=VERSION)
        marker.marker["original_task_sha256"] = binding.pin(marker.task_path, binding.encode(projected))["sha256"]
        marker.save_marker()
        return marker, reproduction

    def test_optional_v2_proposal_uses_its_exact_versioned_filename(self):
        marker, reproduction = self.marker_fixture()
        before = (marker.root / marker.home / "improvement.v1.json").read_bytes()
        binder.write_or_check(marker.root, write=True)
        row, bound = marker.bound()
        self.assertEqual(row["paper_outcomes"]["reproduction_contract"]["path"], marker.home + "/" + FILENAME)
        self.assertEqual(bound["reproduction_contract"], reproduction)
        self.assertEqual(bound["availability"], "unavailable")
        self.assertTrue(all(cell["scientific_outcome"] == "unknown" for cell in bound["summary"]["cells"]))
        self.assertEqual((marker.root / marker.home / "improvement.v1.json").read_bytes(), before)
        self.assertEqual(binder.validate_existing(marker.root)["paper_tasks"], 1)

    def test_optional_v2_proposal_cannot_claim_v1_locator(self):
        marker, _ = self.marker_fixture()
        marker.marker["reproduction_proposal"]["path"] = binding.REPRODUCTION
        marker.save_marker()
        marker.reject_without_writes("proposal identity mismatch")


if __name__ == "__main__":
    unittest.main()
