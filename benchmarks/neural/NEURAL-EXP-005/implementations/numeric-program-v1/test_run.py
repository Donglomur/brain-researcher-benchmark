"""Generated numeric delivery/full support controls; no authentic EEG or model."""

from contextlib import redirect_stdout
from copy import deepcopy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import resource
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("_helsinki_numeric_controls", HERE / "run.py")
r = importlib.util.module_from_spec(spec); spec.loader.exec_module(r)
fixture_path = HERE.parent / "raster-collection-v1/test_collector.py"
fixture_body = r.shared.loader.read_pinned(fixture_path,
    "a92edb4a39d4c3e648704f443b1e648e9c56720840dd72d5b3a3129da2b55375")
helper = r.shared.loader._module(fixture_path, fixture_body, "_helsinki_numeric_fixture",
                                {"collector": r.collector})
LIMITS = {"wall_seconds": 3, "max_actions": 1, "max_action_bytes": 1024,
          "max_stdout_bytes": 4096, "max_response_bytes": 1048576, "max_wire_bytes": 2097152}
NOTES, WRITTEN = [], 0


def write(path, value):
    global WRITTEN
    body = value if isinstance(value, bytes) else r.shared._bytes(value) + b"\n"
    path.write_bytes(body); WRITTEN += len(body)


class NumericControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.started = time.monotonic()
        cls.temp = tempfile.TemporaryDirectory(prefix="numeric-controls-",
            dir=os.environ.get("HELSINKI_NUMERIC_SCRATCH_ROOT"))
        cls.root = Path(cls.temp.name)
        cls.reference, cls.schedule, _, cls.packets = helper.fixture()
        cls.executable = str(Path(sys.executable).resolve())
        cls.program = str((HERE / "fixture_program.py").resolve())
        cls.argv = [cls.executable, "-I", "-S", "-B", cls.program, "{task_instructions}"]
        cls.artifacts = [{"path": p, "sha256": hashlib.sha256(Path(p).read_bytes()).hexdigest()}
                         for p in (cls.executable, cls.program)]
        cls.plan = r.freeze_plan(cls.reference, argv=cls.argv, artifacts=cls.artifacts,
                                limits=LIMITS, max_document_bytes=2097152)
        cls.pin = r.digest(cls.plan)
        cls.output = cls.seal = None

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()
        proof = os.environ.get("HELSINKI_NUMERIC_PROOF_PATH")
        if proof:
            receipt = {"scope": "Generated controls only; no authentic data, provider, model or qualified comparator",
                "notes": NOTES, "temporary_fixture_bytes_written": WRITTEN,
                "wall_seconds": time.monotonic() - cls.started,
                "max_self_rss_native_units": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                "max_child_rss_native_units": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
                "rss_native_units": "bytes on macOS, KiB on Linux", "maximum_concurrent_children": 1}
            target = Path(proof); assert not target.exists()
            target.write_text(json.dumps(receipt, indent=2) + "\n")

    def complete(self):
        if self.__class__.output is None:
            self.__class__.output, self.__class__.seal = r.collect(self.reference, iter(self.packets),
                self.plan, self.pin, scratch_root=self.root)
            NOTES.append({"actual_complete_generated_processes": self.seal["resource_totals"]["processes"],
                          "case_count": self.output["case_count"], "resource_totals": self.seal["resource_totals"]})
        return deepcopy(self.output), deepcopy(self.seal)

    def owner(self):
        return r.collector.Collector(self.schedule, expected_schedule_sha256=r.protocol.digest(self.schedule))

    def command(self, mode="good"):
        return [str(HERE / "PARTICIPANT.md") if x == "{task_instructions}" else x for x in self.argv] + [mode]

    def test_complete_numeric_process_collection_and_existing_infant_score(self):
        output, seal = self.complete()
        self.assertEqual((output["mode"], output["case_count"]), (r.MODE, 80))
        self.assertEqual(seal["resource_totals"]["processes"], 80)
        self.assertEqual(output["rows"], [dict(row, probability=0.25) for row in self.reference.case_rows()])
        report = r.score(self.reference, self.plan, self.pin, output, seal, r.digest(seal))
        self.assertEqual((report["n_infants"], report["n_cases"]), (79, 80))
        self.assertAlmostEqual(report["primary_soft_vote_brier"], 1 / 144, places=13)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), [])

    def test_numeric_wire_is_exact_complete_payload_before_launch(self):
        for mutation in ("private_field", "changed_last_channel", "future_sample", "wrong_flag"):
            packet = deepcopy(self.packets[0])
            if mutation == "private_field": packet["labels"] = [1]
            if mutation == "changed_last_channel": packet["samples"][-1][-1] += 1
            if mutation == "future_sample": packet["samples"].append(list(packet["samples"][-1]))
            if mutation == "wrong_flag": packet["quality_flags"][-1] = True
            with self.subTest(mutation=mutation), patch.object(r.subprocess, "Popen") as launch:
                with self.assertRaises(r.collector.viewer.ViewError):
                    r.run_case(self.owner(), packet, argv=self.command(), limits=LIMITS, scratch_root=self.root)
                launch.assert_not_called()

    def test_fresh_process_packet_response_and_failure_lifecycles(self):
        owner = self.owner()
        receipt = r.run_case(owner, self.packets[0], argv=self.command(), limits=LIMITS, scratch_root=self.root)
        self.assertTrue(receipt["fresh_exec"] and receipt["empty_cwd_at_launch"] and receipt["scratch_removed"])
        self.assertTrue(receipt["cleanup"]["leader_reaped"] and receipt["cleanup"]["owned_group_absent"])
        packet_event = receipt["wire_events"][0]
        self.assertEqual(packet_event["sha256"], hashlib.sha256(r.shared._bytes(self.packets[0]) + b"\n").hexdigest())
        for mode in ("wrong_binding", "nonfinite", "numeric_view", "extra", "nonzero"):
            with self.subTest(mode=mode):
                owner = self.owner()
                with self.assertRaises(r.RunError) as ctx:
                    r.run_case(owner, self.packets[0], argv=self.command(mode), limits=LIMITS, scratch_root=self.root)
                evidence = ctx.exception.receipt
                self.assertFalse(evidence["collector_committed"])
                self.assertTrue(evidence["cleanup"]["leader_reaped"] and evidence["cleanup"]["owned_group_absent"])
                self.assertTrue(evidence["scratch_removed"])
                with self.assertRaises(r.collector.CollectionError): owner.finish()
        NOTES.append({"actual_extra_generated_processes": 6, "failure_modes": ["wrong_binding", "nonfinite", "numeric_view", "extra", "nonzero"]})

    def test_plan_and_mode_changes_refuse_before_launch(self):
        for field, value in (("mode", r.collector.MODE), ("schema", r.shared.PLAN_SCHEMA),
                             ("instructions_sha256", "0" * 64), ("reference_sha256", "0" * 64),
                             ("case_count", 79)):
            plan = deepcopy(self.plan); plan[field] = value
            with self.subTest(field=field), patch.object(r, "run_case") as launch:
                with self.assertRaises(r.RunError):
                    r.collect(self.reference, iter(self.packets), plan, r.digest(plan), scratch_root=self.root)
                launch.assert_not_called()
        with patch.object(r, "run_case") as launch:
            with self.assertRaises(r.RunError):
                r.collect(self.reference, iter(self.packets), self.plan, "0" * 64, scratch_root=self.root)
            launch.assert_not_called()

    def test_changed_frozen_training_artifact_refuses_before_launch(self):
        artifact = self.root / "generated-training-artifact.json"
        write(artifact, b"first\n")
        artifacts = self.artifacts + [{"path": str(artifact), "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest()}]
        plan = r.freeze_plan(self.reference, argv=self.argv, artifacts=artifacts,
                             limits=LIMITS, max_document_bytes=2097152)
        write(artifact, b"changed\n")
        try:
            with patch.object(r, "run_case") as launch:
                with self.assertRaises(r.RunError):
                    r.collect(self.reference, iter(self.packets), plan, r.digest(plan), scratch_root=self.root)
                launch.assert_not_called()
        finally:
            artifact.unlink()

    def test_incomplete_reordered_and_extra_support_withhold_score(self):
        # Reuse actual full-process output; do not replay the80-case campaign.
        original, complete = self.complete()
        for mutation in ("missing", "extra", "reorder", "cross_mode"):
            output, seal = deepcopy(original), deepcopy(complete)
            if mutation == "missing": output["rows"].pop()
            if mutation == "extra": output["rows"].append(deepcopy(output["rows"][-1]))
            if mutation == "reorder": output["rows"][0], output["rows"][1] = output["rows"][1], output["rows"][0]
            if mutation == "cross_mode": output.update(schema=r.collector.COLLECTION_SCHEMA, mode=r.collector.MODE)
            output["case_count"] = len(output["rows"]); output["rows_sha256"] = r.protocol.digest(output["rows"])
            seal["collection_sha256"] = r.protocol.digest(output)
            with self.subTest(mutation=mutation), self.assertRaises((r.RunError, r.collector.CollectionError)):
                r.score(self.reference, self.plan, self.pin, output, seal, r.digest(seal))
        with self.assertRaises(r.RunError):
            r.collect(self.reference, iter([]), self.plan, self.pin, scratch_root=self.root)

    def test_numeric_byte_budget_failure_has_no_commit(self):
        limits = dict(LIMITS, max_response_bytes=100)
        owner = self.owner()
        with self.assertRaises(r.RunError) as ctx:
            r.run_case(owner, self.packets[0], argv=self.command(), limits=limits, scratch_root=self.root)
        self.assertFalse(ctx.exception.receipt["collector_committed"])
        self.assertTrue(ctx.exception.receipt["cleanup"]["leader_reaped"])
        NOTES.append({"actual_byte_limit_processes": 1})

    def test_resource_totals_and_scoring_on_complete_generated_rows(self):
        # Pure scorer admission control; do not repeat the actual process run.
        _, output = helper.completed(self.schedule, r.protocol.digest(self.schedule), self.packets)
        output.update(schema=r.COLLECTION_SCHEMA, mode=r.MODE)
        seal = {"schema": r.COMPLETE_SCHEMA, "status": "complete", "task_id": "NEURAL-EXP-005", "mode": r.MODE,
            "plan_sha256": self.pin, "reference_sha256": self.reference.reference_sha256,
            "schedule_sha256": self.plan["schedule_sha256"], "case_count": 80,
            "collection_sha256": r.protocol.digest(output), "case_receipts_sha256": "a" * 64,
            "source_pins": r.source_pins(), "resource_totals": {"wall_seconds": 0.0,
                "participant_stdout_bytes": 0, "host_wire_bytes": 0, "processes": 80}}
        report = r.score(self.reference, self.plan, self.pin, output, seal, r.digest(seal))
        self.assertAlmostEqual(report["primary_soft_vote_brier"], 1 / 144, places=13)
        for key, value in (("wall_seconds", -1), ("processes", 79), ("host_wire_bytes", True),
                           ("participant_stdout_bytes", -1)):
            changed = deepcopy(seal); changed["resource_totals"][key] = value
            with self.subTest(key=key), self.assertRaises(r.RunError):
                r.score(self.reference, self.plan, self.pin, output, changed, r.digest(changed))
        NOTES.append({"scorer_resource_admission_generated_cases": 80, "actual_processes": 0})

    def test_cli_freeze_and_separate_score_with_existing_prepared_reference(self):
        output, seal = self.complete()
        with tempfile.TemporaryDirectory(dir=self.root) as directory:
            root = Path(directory)
            for name, value in (("reference.json", self.reference.document), ("case.key", helper.KEY),
                    ("spec.json", {k: self.plan[k] for k in ("argv", "artifacts", "limits", "max_document_bytes")}),
                    ("collection.json", output), ("COMPLETED.json", seal)):
                write(root / name, value)
            common = ["--reference", str(root / "reference.json"), "--case-key", str(root / "case.key"),
                      "--read-limit", "2097152"]
            with redirect_stdout(io.StringIO()):
                self.assertEqual(r.main(["freeze", *common, "--participant-spec", str(root / "spec.json"),
                                         "--output", str(root / "plan.json")]), 0)
                self.assertEqual(r.main(["score", *common, "--plan", str(root / "plan.json"),
                    "--plan-sha256", self.pin, "--collection", str(root / "collection.json"),
                    "--completion", str(root / "COMPLETED.json"), "--completion-sha256", r.digest(seal),
                    "--output", str(root / "score.json")]), 0)
            self.assertAlmostEqual(json.loads((root / "score.json").read_text())["primary_soft_vote_brier"], 1 / 144)
            # Include writes through production persistence in the ledger.
            global WRITTEN
            WRITTEN += (root / "plan.json").stat().st_size + (root / "score.json").stat().st_size

    def test_cli_collection_source_wiring_and_failed_persistence(self):
        # Metadata executor only at this command/persistence seam. Actual numeric
        # wire/lifecycle/full80 collection is independently exercised above.
        observed = []
        class GeneratedSource:
            def __init__(self, root): observed.append(str(root))
            def __enter__(self): return self
            def __exit__(self, *_): observed.append("closed")
            def read_samples(self, rid, start, stop):
                return [[n + channel / 100 for channel in range(18)] for n in range(start, stop)]
        def metadata_execute(owner, packet, **_):
            session = owner.open_case(packet)
            session.act({"action": "answer", "case_id": packet["case_id"],
                         "input_sha256": packet["input_sha256"], "probability": 0.25})
            owner.commit_current()
            return {"status": "committed", "collector_committed": True, "wall_seconds": 0.0,
                    "participant_stdout_bytes": 0, "host_wire_bytes": 0, "generated_metadata_stub": True}
        real_load = r.shared._load
        def generated_load(relative, imports=None):
            if relative == "source-admission-v1/source_adapter.py":
                return SimpleNamespace(SourceCorpus=GeneratedSource)
            return real_load(relative, imports)
        with tempfile.TemporaryDirectory(dir=self.root) as directory:
            root = Path(directory)
            for name, value in (("reference.json", self.reference.document), ("case.key", helper.KEY),
                                ("plan.json", self.plan)):
                write(root / name, value)
            command = ["collect", "--reference", str(root / "reference.json"), "--case-key", str(root / "case.key"),
                "--read-limit", "2097152", "--plan", str(root / "plan.json"), "--plan-sha256", self.pin,
                "--source-root", str(root / "generated-source"), "--scratch-root", str(root)]
            actual_write = r.shared.write_prepared_new
            persisted = []
            def counted_write(path, document, limit):
                persisted.append((Path(path), len(r.shared._bytes(document)) + 1))
                actual_write(path, document, limit)
                if path.name == "COMPLETED.json" and path.parent.name == "failed":
                    raise OSError("generated post-write persistence failure")
            with patch.object(r.shared, "_load", side_effect=generated_load), \
                    patch.object(r, "run_case", side_effect=metadata_execute), \
                    patch.object(r.shared, "write_prepared_new", side_effect=counted_write), \
                    redirect_stdout(io.StringIO()):
                self.assertEqual(r.main([*command, "--output", str(root / "complete")]), 0)
                with self.assertRaises(OSError):
                    r.main([*command, "--output", str(root / "failed")])
            self.assertEqual(observed, [str(root / "generated-source"), "closed"] * 2)
            self.assertEqual(json.loads((root / "complete/collection.json").read_text())["case_count"], 80)
            self.assertFalse((root / "failed/COMPLETED.json").exists())
            self.assertFalse(json.loads((root / "failed/FAILED.json").read_text())["complete_output_eligible"])
            global WRITTEN
            WRITTEN += sum(size for _, size in persisted)
            NOTES.append({"cli_collection_generated_metadata_cases": 160, "actual_processes": 0,
                          "post_write_failure_retained_as_failed_bundle": True})


if __name__ == "__main__":
    unittest.main(verbosity=2)
