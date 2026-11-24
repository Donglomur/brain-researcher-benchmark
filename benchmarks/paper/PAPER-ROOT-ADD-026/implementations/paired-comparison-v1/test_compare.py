"""Generated complete-panel controls; no authentic bank, model or fitting."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

import compare

HERE = Path(__file__).resolve().parent
INTERFACE = Path(os.environ.get("TEMPORAL_INTERFACE_DIR", HERE.parent / "prediction-interface-v1"))
PRODUCER = INTERFACE.parent / "source-model-producer-v1"
ROOT = Path(os.environ.get("TEMPORAL_GENERATED_ROOT", HERE / ".generated"))
ROOT.mkdir(parents=True, exist_ok=True)
tempfile.tempdir = str(ROOT)
os.environ["TEMPORAL_REPLAY_DIR"] = str(INTERFACE.parent / "source-cv-replay-v1")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class PairControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = compare.Source(INTERFACE)
        cls.fixture_module = load("temporal026_pair_generated_fixture", PRODUCER / "test_producer.py")
        cls.fixture_module.ProducerControls.setUpClass()
        cls.addClassCleanup(cls.fixture_module.ProducerControls.doClassCleanups)
        cls.fixture = cls.fixture_module.ProducerControls()
        cls.origin = cls.source.protocol.Source(PRODUCER)
        cls.protocols = {}
        for branch, plan in cls.fixture.plans.items():
            for arm in ("paper_data", "paper_data_author_code"):
                cls.protocols[(branch, arm)] = [cls.source.protocol.Protocol(
                    plan, plan["plan_sha256"], cls.fixture.manifest, digit * 64, arm, cls.origin)
                    for digit in ("3", "4")]
        cls.reference, cls.candidate = cls.protocols[("named_response_columns", "paper_data")]
        cls.context = cls.source.submissions._context(cls.reference)

    def result(self, protocol, value, fail=None, undefined=None):
        context = self.source.submissions._context(protocol)
        compact, cells = {}, []
        for job in context["jobs"]:
            row = {"job_id": job["id"], "status": "submitted", "fold_r2": None}
            if job["mode"] == "cv":
                row.update(condition_r2=[{"value": value, "status": "finite"}] * 6,
                           rounded_condition_r2=[value] * 6, fold_r2=value)
            if job["id"] == fail:
                row = {"job_id": job["id"], "status": "failed", "fold_r2": None,
                       "failure": {"type": "candidate_declined", "message": "generated"}}
            if job["id"] == undefined:
                row.update(condition_r2=[{"value": None, "status": "undefined_source_r2"}] * 6,
                           rounded_condition_r2=None, fold_r2=None)
            compact[job["id"]] = row
            if job["mode"] == "cv":
                cells.append(row)
        # Execute the unchanged source reducer over all 2054 coordinates.
        reduced = self.source.submissions._reduce(protocol, context, compact, 17)
        return {"cv_cells": cells, **reduced, "generated_evaluator_seam": True}

    def paired(self, left, right, reference=None, candidate=None):
        reference, candidate = reference or self.reference, candidate or self.candidate
        with mock.patch.object(self.source.submissions, "evaluate", side_effect=[left, right]) as evaluate:
            result = compare.compare("reference-store", reference, "a" * 64,
                                     "candidate-store", candidate, "b" * 64,
                                     "one-protected-bank", 17, self.source)
            self.assertEqual(evaluate.call_count, 2)
            self.assertEqual(evaluate.call_args_list[0].args,
                             ("reference-store", reference, "a" * 64, "one-protected-bank", 17))
            self.assertEqual(evaluate.call_args_list[1].args,
                             ("candidate-store", candidate, "b" * 64, "one-protected-bank", 17))
        return result

    def test_complete_both_branches_and_both_assistance_arms(self):
        for (branch, arm), (reference, candidate) in self.protocols.items():
            with self.subTest(branch=branch, arm=arm):
                left, right = self.result(reference, .25), self.result(candidate, .5)
                result = self.paired(left, right, reference, candidate)
                pairs = result["paired_candidate_minus_reference"]
                self.assertEqual((len(pairs["cv_cells"]), len(pairs["electrodes"]), len(pairs["regions"])),
                                 (1896, 158, 6))
                self.assertTrue(all(r["fold_r2_delta"] == .25 for r in pairs["cv_cells"]))
                self.assertTrue(all(r["condition_r2_delta"] == [.25] * 6 for r in pairs["cv_cells"]))
                self.assertTrue(all(r["r2_delta"] == .25 for r in pairs["electrodes"]))
                self.assertTrue(all(r["descriptive_median_delta"] == .25 for r in pairs["regions"]))
                self.assertIs(result["reference"], left)
                self.assertIs(result["candidate"], right)
                self.assertFalse(result["scientific_qualification"])
                self.assertEqual(result["improvement_decision"], "unresolved")
                self.assertEqual(result["source_branch"], branch)
                self.assertEqual(result["condition"], arm)

    def test_branch_condition_and_fold_changes_refused_before_evaluation(self):
        wrong = [self.protocols[("source_positional_cv", "paper_data")][1],
                 self.protocols[("named_response_columns", "paper_data_author_code")][1]]
        metadata = {"schema": "temporal026-ordered-source-metadata/v1", "electrodes": [
            {"electrode_id": row["id"], "source_data_sha256": self.fixture.table_sha,
             "rows": self.fixture.rows} for row in self.fixture.cohort]}
        manifest = self.fixture.replay.freeze(metadata, 20261118)
        plan = self.origin.producer.make_plan(manifest, manifest["manifest_sha256"],
                    self.fixture.inputs, "named_response_columns", replay=self.origin.replay)
        wrong.append(self.source.protocol.Protocol(plan, plan["plan_sha256"], manifest,
                     "4" * 64, "paper_data", self.origin))
        for candidate in wrong:
            with mock.patch.object(self.source.submissions, "evaluate", side_effect=AssertionError("opened targets")):
                with self.assertRaisesRegex(ValueError, "identical original"):
                    compare.compare("r", self.reference, "a" * 64, "c", candidate,
                                    "b" * 64, "bank", 17, self.source)

    def test_full_failure_retained_and_gates_regions_without_dropping_cv(self):
        full = next(j["id"] for j in self.context["jobs"] if j["mode"] == "full")
        result = self.paired(self.result(self.reference, .25), self.result(self.candidate, .5, fail=full))
        self.assertEqual(result["candidate"]["failures"], [{"job": full, "status": "failed"}])
        pairs = result["paired_candidate_minus_reference"]
        self.assertTrue(all(r["descriptive_median_delta"] is None for r in pairs["regions"]))
        self.assertTrue(all(r["r2_delta"] == .25 for r in pairs["electrodes"]))

    def test_cv_failure_and_undefined_not_dropped_or_zeroed(self):
        cv = [j["id"] for j in self.context["jobs"] if j["mode"] == "cv"]
        result = self.paired(self.result(self.reference, .25),
                             self.result(self.candidate, .5, fail=cv[0], undefined=cv[1]))
        cells = result["paired_candidate_minus_reference"]["cv_cells"]
        self.assertEqual(len(cells), 1896)
        self.assertEqual(cells[0]["candidate_status"], "failed")
        self.assertEqual(cells[1]["candidate_status"], "submitted")
        self.assertTrue(all(r["fold_r2_delta"] is None for r in cells[:2]))
        self.assertEqual(cells[1]["condition_r2_delta"], [None] * 6)

    def test_changed_report_support_cannot_silently_zip(self):
        left, right = self.result(self.reference, .25), self.result(self.candidate, .5)
        for field in ("cv_cells", "electrode_cv", "figure3_regional_cv"):
            altered = copy.deepcopy(right)
            altered[field].pop()
            with self.assertRaisesRegex(ValueError, "complete ordered"):
                compare._pair(left, altered, self.context)
        altered = copy.deepcopy(right)
        altered["electrode_cv"][0]["subject"] = "foreign"
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            compare._pair(left, altered, self.context)

    def test_real_committed_complete_failure_panel(self):
        submission = self.source.submissions
        failure = {"type": "candidate_declined", "message": "generated integration control"}
        # Budget this complete generated store before writing any member.
        sizes = [len(submission._record_bytes(self.reference, self.context, job["id"], failure=failure))
                 for job in self.context["jobs"]]
        self.assertLess(sum(sizes) + submission.MAX_MANIFEST_BYTES, 5 * 1024**2)
        with tempfile.TemporaryDirectory(prefix="complete-paired-store-") as directory:
            writer = submission.Writer(directory, self.reference)
            for job in self.context["jobs"]:
                writer.write(job["id"], failure=failure)
            pin = submission.seal(directory, self.reference)
            type(self).store_write_bytes = writer.accounting["attempted_record_bytes"] + pin["bytes"]
            self.assertLess(type(self).store_write_bytes, 4 * 1024**2)
            with mock.patch.object(self.source.protocol.Protocol, "targets", side_effect=AssertionError("failure opened targets")):
                result = compare.compare(directory, self.reference, pin["sha256"],
                                         directory, self.reference, pin["sha256"],
                                         "unopened-bank", 17, self.source)
        self.assertTrue(result["same_method_identity"])
        self.assertEqual(len(result["reference"]["failures"]), 2054)
        self.assertEqual(len(result["candidate"]["failures"]), 2054)
        self.assertEqual(result["reference"]["candidate_status_counts"],
                         {"submitted": 0, "failed": 2054, "cv": 1896, "full": 158})
        self.assertTrue(all(row["fold_r2_delta"] is None
                            for row in result["paired_candidate_minus_reference"]["cv_cells"]))
        self.assertEqual(result["improvement_decision"], "unresolved")

    def test_invalid_seed_refused_before_evaluation(self):
        with mock.patch.object(self.source.submissions, "evaluate", side_effect=AssertionError("opened targets")):
            with self.assertRaisesRegex(ValueError, "bootstrap seed"):
                compare.compare("r", self.reference, "a" * 64, "c", self.candidate,
                                "b" * 64, "bank", True, self.source)


if __name__ == "__main__":
    suite = (unittest.TestSuite(PairControls(name) for name in sys.argv[1:]) if len(sys.argv) > 1
             else unittest.defaultTestLoader.loadTestsFromTestCase(PairControls))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps({"generated_fixture_write_bytes": PairControls.fixture.generated_fixture_bytes,
                      "generated_store_write_bytes": getattr(PairControls, "store_write_bytes", 0),
                      "authentic_data_reads": 0, "model_fits": 0,
                      "complete_panel_source_reduction": True,
                      "durable_store_authentication_retested": bool(getattr(PairControls, "store_write_bytes", 0)),
                      "evaluator_seam": "Analytical pair tests replace evaluate only; durable failure-panel test uses real seal/evaluate. Original Protocol, _context and _reduce execute."}))
    raise SystemExit(0 if result.wasSuccessful() else 1)
