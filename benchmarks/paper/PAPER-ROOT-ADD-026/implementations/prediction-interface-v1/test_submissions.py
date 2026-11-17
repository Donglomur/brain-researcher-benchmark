"""Generated-only full-support commitment and source-reduction controls.

One complete durable 2054-record panel contains only one small numeric CV output;
all other coordinates are explicit generated failures. The full successful
source reduction uses shared in-memory traces, never a large persisted fake bank.
"""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np

HERE = Path(__file__).resolve().parent
PRODUCER = Path(os.environ.get("TEMPORAL_PRODUCER_DIR", HERE.parent / "source-model-producer-v1"))
FIXTURE_ROOT = Path(os.environ.get("TEMPORAL_GENERATED_ROOT", HERE / ".generated-submissions"))
FIXTURE_ROOT.mkdir(parents=True, exist_ok=True)
FIXTURE_ROOT = FIXTURE_ROOT.resolve()
tempfile.tempdir = str(FIXTURE_ROOT)
os.environ["TEMPORAL_REPLAY_DIR"] = str(PRODUCER.parent / "source-cv-replay-v1")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


protocol_module = load("temporal_candidate_protocol_test", HERE / "protocol.py")
submission = load("temporal_candidate_submission_test", HERE / "submissions.py")
source_tests = load("temporal_source_generated_fixture", PRODUCER / "test_producer.py")

WRITTEN = 0
_real_write = submission._write


def measured_write(fd, name, raw):
    global WRITTEN
    if WRITTEN + len(raw) > 6 * 1024**2 - 300000:
        raise ValueError("generated write share would exceed prospective bound")
    WRITTEN += len(raw)
    return _real_write(fd, name, raw)


submission._write = measured_write


def replace_bytes(path, raw):
    global WRITTEN
    if WRITTEN + len(raw) > 6 * 1024**2 - 300000:
        raise ValueError("generated write share would exceed prospective bound")
    WRITTEN += len(raw)
    path.chmod(0o600)
    path.write_bytes(raw)
    path.chmod(0o444)


class SubmissionControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source_tests.ProducerControls.setUpClass()
        cls.source_fixture = source_tests.ProducerControls()
        cls.addClassCleanup(source_tests.ProducerControls.doClassCleanups)
        cls.source = protocol_module.Source(PRODUCER)
        cls.protocols = {
            branch: protocol_module.Protocol(plan, plan["plan_sha256"], cls.source_fixture.manifest,
                                             "3" * 64, "paper_data", cls.source)
            for branch, plan in cls.source_fixture.plans.items()
        }
        cls.protocol = cls.protocols["named_response_columns"]
        cls.context = submission._context(cls.protocol)
        cls.panel_temp = tempfile.TemporaryDirectory(prefix="candidate-complete-", dir=FIXTURE_ROOT)
        cls.addClassCleanup(cls.panel_temp.cleanup)
        cls.panel = Path(cls.panel_temp.name)
        cls.first_cv = next(j for j in cls.context["jobs"] if j["mode"] == "cv")
        writer = submission.Writer(cls.panel, cls.protocol)
        for job in cls.context["jobs"]:
            if job["id"] == cls.first_cv["id"]:
                writer.write(job["id"], predictions=[cls.source_fixture.observed] * 6)
            else:
                writer.write(job["id"], failure={"type": "candidate_declined", "message": "generated control"})
        cls.writer_accounting = writer.accounting
        cls.manifest_pin = submission.seal(cls.panel, cls.protocol)
        cls.manifest_raw = (cls.panel / "MANIFEST.json").read_bytes()
        cls.manifest = submission.parse(cls.manifest_raw)
        cls.metric_reference = None

    def fresh(self):
        tmp = tempfile.TemporaryDirectory(prefix="candidate-one-", dir=FIXTURE_ROOT)
        self.addCleanup(tmp.cleanup)
        return Path(tmp.name)

    def record(self, job_id=None):
        job_id = job_id or self.first_cv["id"]
        record = submission._base(self.protocol, self.context, job_id)
        record.update(status="submitted", predictions=[self.source_fixture.observed[:]] * 6)
        return record

    def test_full2054_commit_has_complete_support_and_honest_statuses(self):
        self.assertEqual(self.manifest["counts"], {"submitted": 1, "failed": 2053, "cv": 1896, "full": 158})
        self.assertEqual([r["job_id"] for r in self.manifest["records"]], [j["id"] for j in self.context["jobs"]])
        self.assertEqual(self.writer_accounting["committed_records"], 2054)
        self.assertEqual(self.writer_accounting["attempted_record_bytes"], sum(r["file"]["bytes"] for r in self.manifest["records"]))
        self.assertLess(self.writer_accounting["attempted_record_bytes"], 3 * 1024**2)

    def test_complete_authentication_precedes_private_target_read_and_scores_original_trace(self):
        calls = []
        original = self.protocol.targets
        def targets(root, job_id):
            calls.append(job_id)
            return original(root, job_id)
        with mock.patch.object(protocol_module.Protocol, "targets", autospec=True,
                               side_effect=lambda instance, root, job_id: targets(root, job_id)):
            result = submission.evaluate(self.panel, self.protocol, self.manifest_pin["sha256"], self.source_fixture.root, 17)
        self.assertEqual(calls, [self.first_cv["id"]])
        self.assertEqual(result["complete_job_count"], 2054)
        self.assertEqual(len(result["cv_cells"]), 1896)
        cell = next(c for c in result["cv_cells"] if c["job_id"] == self.first_cv["id"])
        self.assertEqual(cell["condition_r2"], [{"value": 1.0, "status": "finite"}] * 6)
        self.assertEqual(cell["fold_r2"], 1.0)
        self.assertEqual(len(result["failures"]), 2053)
        self.assertTrue(all(r["status"] == "undefined_incomplete_or_nonfinite" for r in result["figure3_regional_cv"]))
        self.assertFalse(result["scientific_qualification"])

    def test_malformed_last_coordinate_is_refused_before_any_target_read(self):
        last = self.manifest["records"][-1]
        path = self.panel / last["file"]["path"]
        original = path.read_bytes()
        altered = submission.parse(original)
        altered.pop("failure")
        altered.update(status="submitted", predictions=[[0.0]])
        raw = submission.encoded(altered)
        new_manifest = copy.deepcopy(self.manifest)
        new_manifest["records"][-1]["status"] = "submitted"
        new_manifest["records"][-1]["file"].update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        new_manifest["counts"].update(submitted=2, failed=2052)
        frozen = submission.encoded(new_manifest)
        replace_bytes(path, raw)
        replace_bytes(self.panel / "MANIFEST.json", frozen)
        try:
            with mock.patch.object(protocol_module.Protocol, "targets", autospec=True,
                                   side_effect=AssertionError("target read before complete intake")):
                with self.assertRaisesRegex(ValueError, "complete prediction row support"):
                    submission.evaluate(self.panel, self.protocol, hashlib.sha256(frozen).hexdigest(), self.source_fixture.root, 17)
        finally:
            replace_bytes(path, original)
            replace_bytes(self.panel / "MANIFEST.json", self.manifest_raw)

    def test_wrong_external_manifest_hash_precedes_targets(self):
        with mock.patch.object(protocol_module.Protocol, "targets", autospec=True,
                               side_effect=AssertionError("target read before commitment")):
            with self.assertRaisesRegex(ValueError, "hash differs"):
                submission.evaluate(self.panel, self.protocol, "0" * 64, self.source_fixture.root, 17)

    def test_missing_final_coordinate_and_extra_file_fail_closed(self):
        path = self.panel / self.manifest["records"][-1]["file"]["path"]
        moved = self.panel.parent / (path.name + ".owned-moved")
        path.rename(moved)
        try:
            with mock.patch.object(protocol_module.Protocol, "targets", autospec=True,
                                   side_effect=AssertionError("target read on incomplete panel")):
                with self.assertRaisesRegex(ValueError, "complete sealed directory"):
                    submission.evaluate(self.panel, self.protocol, self.manifest_pin["sha256"], self.source_fixture.root, 17)
        finally:
            moved.rename(path)
        extra = self.panel / "foreign.json"
        extra.touch()
        try:
            with self.assertRaisesRegex(ValueError, "unexpected submission directory entry"):
                submission.evaluate(self.panel, self.protocol, self.manifest_pin["sha256"], self.source_fixture.root, 17)
        finally:
            extra.unlink()

    def test_write_is_exclusive_and_caller_mutation_does_not_change_bytes(self):
        directory = self.fresh()
        writer = submission.Writer(directory, self.protocol)
        predictions = [[float(i % 5) for i in range(819)] for _ in range(6)]
        pin = writer.write(self.first_cv["id"], predictions=predictions)
        before = (directory / pin["path"]).read_bytes()
        predictions[0][0] = 99.0
        self.assertEqual((directory / pin["path"]).read_bytes(), before)
        self.assertEqual(hashlib.sha256(before).hexdigest(), pin["sha256"])
        with self.assertRaisesRegex(ValueError, "duplicate candidate coordinate"):
            writer.write(self.first_cv["id"], failure={"type": "candidate_declined", "message": "no retry"})
        self.assertEqual((directory / pin["path"]).read_bytes(), before)

    def test_partial_panel_cannot_be_sealed_and_sealed_panel_cannot_accept_writes(self):
        directory = self.fresh()
        submission.write_record(directory, self.protocol, self.first_cv["id"], failure={"type": "candidate_declined", "message": "generated"})
        with self.assertRaisesRegex(ValueError, "all 2054"):
            submission.seal(directory, self.protocol)
        with self.assertRaisesRegex(ValueError, "sealed panel"):
            submission.write_record(self.panel, self.protocol, self.first_cv["id"], failure={"type": "candidate_declined", "message": "generated"})

    def test_directory_replacement_is_refused_by_writer(self):
        directory = self.fresh()
        writer = submission.Writer(directory, self.protocol)
        held = directory.with_name(directory.name + "-held")
        directory.rename(held)
        directory.mkdir()
        try:
            with self.assertRaisesRegex(ValueError, "directory identity changed"):
                writer.write(self.first_cv["id"], failure={"type": "candidate_declined", "message": "generated"})
        finally:
            directory.rmdir()
            held.rename(directory)

    def test_symlink_and_hardlink_members_are_refused(self):
        for kind in ("symlink", "hardlink"):
            directory = self.fresh()
            original = self.panel / self.manifest["records"][0]["file"]["path"]
            destination = directory / "prediction-0000.json"
            if kind == "symlink":
                destination.symlink_to(original)
            else:
                os.link(original, destination)
            try:
                with self.assertRaisesRegex(ValueError, "single-link"):
                    submission.Writer(directory, self.protocol)
            finally:
                destination.unlink()

    def test_prediction_rows_types_shapes_finiteness_and_forbidden_truth_fields(self):
        base = self.record()
        for mutate in (
            lambda r: r["prediction_rows"].__setitem__(0, True),
            lambda r: r["prediction_identities"][0].__setitem__("temp_cond", False),
            lambda r: r["predictions"].pop(),
            lambda r: r["predictions"][0].pop(),
            lambda r: r["predictions"][0].__setitem__(2, float("nan")),
            lambda r: r["predictions"][0].__setitem__(2, True),
            lambda r: r.update(observations=r["predictions"]),
            lambda r: r.update(fit={"success": True}),
            lambda r: r.update(column_branch="source_positional_cv"),
            lambda r: r.update(method_sha256="4" * 64),
        ):
            record = copy.deepcopy(base)
            mutate(record)
            with self.assertRaises(ValueError):
                submission.validate_record(record, self.protocol, self.context, self.first_cv["id"])

    def test_candidate_failures_are_typed_bounded_and_never_optimizer_status(self):
        record = self.record()
        record.pop("predictions")
        record.update(status="failed", failure={"type": "candidate_execution_failed", "message": "generated exception"})
        submission.validate_record(record, self.protocol, self.context, self.first_cv["id"])
        for key, value in (("status", "converged"), ("failure", {"type": "success", "message": "x"}),
                           ("failure", {"type": "candidate_declined", "message": "x" * 2049})):
            altered = copy.deepcopy(record)
            altered[key] = value
            with self.assertRaises(ValueError):
                submission.validate_record(altered, self.protocol, self.context, self.first_cv["id"])

    def test_positional_context_refuses_named_record_and_full_always_named(self):
        positional = self.protocols["source_positional_cv"]
        context = submission._context(positional)
        with self.assertRaisesRegex(ValueError, "binding mismatch"):
            submission.validate_record(self.record(), positional, context, self.first_cv["id"])
        full = next(j for j in context["jobs"] if j["mode"] == "full")
        self.assertEqual(submission._base(positional, context, full["id"])["column_branch"], "named_response_columns")
        self.assertEqual(len(submission._base(positional, context, full["id"])["prediction_rows"]), 72)

    def test_wrong_target_identity_refused_without_adopting_candidate_truth(self):
        target = self.protocol.targets(self.source_fixture.root, self.first_cv["id"])
        target["source_data_sha256"] = "0" * 64
        with mock.patch.object(protocol_module.Protocol, "targets", autospec=True, return_value=target):
            with self.assertRaisesRegex(ValueError, "protected target"):
                submission.evaluate(self.panel, self.protocol, self.manifest_pin["sha256"], self.source_fixture.root, 17)

    def test_reducer_matches_actual_source_collect_with_generated_source_records(self):
        source_result = self.source_fixture.collect(seed=17)
        compact = {}
        for record in self.source_fixture.records(self.protocol.plan):
            compact[record["job"]["id"]] = {"status": "submitted", "fold_r2": record.get("fold_r2")}
        candidate = submission._reduce(self.protocol, self.context, compact, 17)
        for key in ("electrode_cv", "figure3_regional_cv", "bootstrap"):
            self.assertEqual(candidate[key], source_result[key])
        self.assertEqual(candidate["failures"], [])

    def test_full_failure_globally_gates_regions_without_discarding_cv(self):
        compact = {j["id"]: {"status": "submitted", "fold_r2": 0.5 if j["mode"] == "cv" else None} for j in self.context["jobs"]}
        compact[self.context["jobs"][0]["id"]]["status"] = "failed"
        result = submission._reduce(self.protocol, self.context, compact, 17)
        self.assertEqual(len(result["failures"]), 1)
        self.assertTrue(all(e["r2"] == 0.5 for e in result["electrode_cv"]))
        self.assertTrue(all(r["status"] == "undefined_incomplete_or_nonfinite" for r in result["figure3_regional_cv"]))

    def test_undefined_cv_is_not_global_failure_and_rng_skips_only_affected_group(self):
        compact = {j["id"]: {"status": "submitted", "fold_r2": (0.1 + (i % 17) / 100) if j["mode"] == "cv" else None}
                   for i, j in enumerate(self.context["jobs"])}
        compact[self.first_cv["id"]]["fold_r2"] = None
        result = submission._reduce(self.protocol, self.context, compact, 17)
        self.assertEqual(result["failures"], [])
        region = self.source.replay.cohort()[0]["varea"]
        affected = (region, self.first_cv["scaling"])
        rng = np.random.RandomState(17)
        for row in result["figure3_regional_cv"]:
            if (row["region"], row["scaling"]) == affected:
                self.assertEqual(row["status"], "undefined_incomplete_or_nonfinite")
                continue
            a = np.asarray([e["r2"] for e in result["electrode_cv"] if e["varea"] == row["region"] and e["scaling"] == row["scaling"]])
            samples = rng.choice(len(a), size=(1000, len(a)), replace=True)
            medians = np.median(a[samples], axis=1)
            self.assertEqual(row["median"], float(np.median(medians)))
            self.assertEqual(row["interval68"], np.nanpercentile(medians, [16, 84]).tolist())

    def test_zero_variance_source_r2_remains_undefined(self):
        observed = [0.0] * 819
        self.assertEqual(self.source.producer.native_r2(observed, observed),
                         {"value": None, "status": "undefined_source_r2", "zero_observed_variance": True})

    def test_invalid_seed_rejected_before_any_target_read(self):
        for seed in (-1, 2**32, True):
            with mock.patch.object(protocol_module.Protocol, "targets", autospec=True,
                                   side_effect=AssertionError("invalid seed opened target")):
                with self.assertRaisesRegex(ValueError, "bootstrap seed"):
                    submission.evaluate(self.panel, self.protocol, self.manifest_pin["sha256"], self.source_fixture.root, seed)


if __name__ == "__main__":
    suite = (unittest.TestSuite(SubmissionControls(name) for name in sys.argv[1:]) if len(sys.argv) > 1
             else unittest.defaultTestLoader.loadTestsFromTestCase(SubmissionControls))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    # Includes each successful/attempted _write and intentional mutation rewrite;
    # the source fixture also writes its one invented response/variable set.
    total = WRITTEN + getattr(source_tests.ProducerControls, "generated_fixture_bytes", 0)
    print(json.dumps({"generated_application_write_charge_bytes": total,
                      "limit_bytes": 6 * 1024**2,
                      "authentic_array_reads": 0,
                      "no_unchanged_suite_rerun_claim": True}))
    if total > 6 * 1024**2:
        raise SystemExit("generated fixture write share exceeded")
    raise SystemExit(0 if result.wasSuccessful() else 1)
