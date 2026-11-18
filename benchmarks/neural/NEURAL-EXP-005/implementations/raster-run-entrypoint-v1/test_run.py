"""Changed entrypoint seams only; no authentic data or80-case process replay."""

from contextlib import redirect_stdout
from copy import deepcopy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("_nexp005_entrypoint_controls", HERE / "run.py")
r = importlib.util.module_from_spec(spec); spec.loader.exec_module(r)
helper_path = HERE.parent / "raster-collection-v1/test_collector.py"
helper_body = r.loader.read_pinned(helper_path,
    "a92edb4a39d4c3e648704f443b1e648e9c56720840dd72d5b3a3129da2b55375")
helper = r.loader._module(helper_path, helper_body, "_nexp005_package_fixture", {"collector": r.collector})
LIMITS = {"wall_seconds": 3, "max_actions": 8, "max_action_bytes": 512,
          "max_stdout_bytes": 4096, "max_response_bytes": 1048576, "max_wire_bytes": 4194304}
WRITTEN = 0
NOTES = []


def generated_write(path, body):
    global WRITTEN
    WRITTEN += len(body)
    path.write_bytes(body)


def metadata_commit(owner, packet, **_):
    """Stub only for new dispatcher accounting, not process/model evidence."""
    session = owner.open_case(packet)
    session.act({"action": "answer", "case_id": packet["case_id"],
                 "input_sha256": packet["input_sha256"], "probability": 0.25})
    return {"status": "committed", "collector_committed": True,
            "commit_receipt": owner.commit_current(), "fixture_executor": True}


class PackageControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="helsinki-package-",
            dir=os.environ.get("HELSINKI_RUN_ENTRYPOINT_SCRATCH_ROOT"))
        cls.root = Path(cls.temp.name)
        cls.reference, cls.schedule, _, cls.packet_list = helper.fixture()
        cls.artifact = cls.root / "generated-config.txt"
        generated_write(cls.artifact, b"config-v1\n")
        executable = str(Path(sys.executable).resolve())
        entry = str((HERE / "fixture_entry.py").resolve())
        participant = str((HERE.parent / "raster-process-transport-v1/fixture_participant.py").resolve())
        cls.argv = [executable, "-I", "-S", "-B", entry, participant, "{task_instructions}"]
        cls.artifacts = [{"path": p, "sha256": hashlib.sha256(Path(p).read_bytes()).hexdigest()}
                         for p in (executable, entry, participant, str(cls.artifact))]
        cls.plan = r.freeze_plan(cls.reference, argv=cls.argv, artifacts=cls.artifacts,
                                limits=LIMITS, max_document_bytes=2097152)
        cls.plan_pin = r.digest(cls.plan)
        cls.output = cls.seal = None

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()
        path = os.environ.get("HELSINKI_RUN_ENTRYPOINT_PROOF_PATH")
        if path:
            body = (json.dumps({"schema": "helsinki-entrypoint-generated-controls-v1",
                "scope": "New glue only; executed controls and actual process use are listed in notes. No authentic source/model.",
                "temporary_fixture_bytes_written_upper": WRITTEN, "notes": NOTES}, indent=2) + "\n").encode()
            assert len(body) <= 8192
            target = Path(path); assert not target.exists(); target.write_bytes(body)

    def collect_stub(self, packets=None):
        with patch.object(r.transport, "run_case", side_effect=metadata_commit):
            return r.collect(self.reference, iter(self.packet_list if packets is None else packets),
                self.plan, self.plan_pin, scratch_root=self.root)

    def complete(self):
        # Reuse one in-memory generated dispatcher result across readback controls.
        if self.__class__.output is None:
            self.__class__.output, self.__class__.seal = self.collect_stub()
        return deepcopy(self.__class__.output), deepcopy(self.__class__.seal)

    def test_plan_freezes_inputs_and_explicit_external_prerequisites(self):
        argv, artifacts, limits = deepcopy(self.argv), deepcopy(self.artifacts), dict(LIMITS)
        plan = r.freeze_plan(self.reference, argv=argv, artifacts=artifacts, limits=limits,
                             max_document_bytes=2097152)
        argv[0] = "/changed"; artifacts[0]["sha256"] = "0" * 64; limits["max_actions"] = 1
        self.assertEqual(plan, self.plan)
        self.assertEqual(plan["external_prerequisites"], r.EXTERNAL_PREREQUISITES)
        self.assertEqual(plan["case_count"], 80)
        self.assertNotIn("labels", plan)

    def test_manifest_reference_schedule_prompt_and_artifact_drift_prevent_launch(self):
        for field, changed in (("reference_sha256", "0" * 64), ("schedule_sha256", "0" * 64),
            ("instructions_sha256", "0" * 64), ("case_count", 79), ("mode", "direct_numeric")):
            plan = deepcopy(self.plan); plan[field] = changed
            with self.subTest(field=field), patch.object(r.transport, "run_case") as execute:
                with self.assertRaises(r.RunError):
                    r.collect(self.reference, iter(self.packet_list), plan, r.digest(plan), scratch_root=self.root)
                execute.assert_not_called()
        with self.assertRaises(r.RunError):
            r.collect(self.reference, iter(self.packet_list), self.plan, "0" * 64, scratch_root=self.root)
        generated_write(self.artifact, b"config-v2\n")
        try:
            with patch.object(r.transport, "run_case") as execute:
                with self.assertRaises(r.RunError):
                    r.collect(self.reference, iter(self.packet_list), self.plan, self.plan_pin, scratch_root=self.root)
                execute.assert_not_called()
        finally:
            generated_write(self.artifact, b"config-v1\n")

    def test_new_dispatcher_preserves_complete_order_and_defers_scorer_loading(self):
        loads = []
        real_load = r._load
        def observed(relative, imports=None):
            loads.append(relative); return real_load(relative, imports)
        with patch.object(r, "_load", side_effect=observed):
            output, seal = self.collect_stub()
            self.assertEqual(loads, [])
            self.assertEqual([x["case_id"] for x in output["rows"]],
                             [x["case_id"] for x in self.schedule["bindings"]])
            report = r.score(self.reference, self.plan, self.plan_pin, output, seal, r.digest(seal))
        self.assertEqual(loads, ["complete-support-evaluator/evaluate.py"])
        self.assertEqual((report["n_infants"], report["n_cases"]), (79, 80))
        self.assertAlmostEqual(report["primary_soft_vote_brier"], 1 / 144, places=13)
        NOTES.append({"control": "new_dispatcher_and_separate_grade", "cases": 80,
            "executor": "metadata_commit_stub; no process campaign", "unchanged_generated_brier": report["primary_soft_vote_brier"]})

    def test_missing_extra_and_reordered_packets_never_return_complete_output(self):
        for label, packets in (("missing", self.packet_list[:-1]),
            ("extra", self.packet_list + self.packet_list[:1]),
            ("reordered", [self.packet_list[1], self.packet_list[0]] + self.packet_list[2:])):
            with self.subTest(label=label), self.assertRaises(r.RunError) as raised:
                self.collect_stub(packets)
            self.assertFalse(raised.exception.receipt["complete_output_eligible"])

    def test_case_failure_stops_without_prefetch_or_partial_success(self):
        seen = []
        def stream():
            for index, packet in enumerate(self.packet_list):
                seen.append(index); yield packet
        def execute(owner, packet, **kwargs):
            if len(seen) == 2:
                raise r.transport.TransportError("generated_failure", {"cleanup": {"leader_reaped": True}})
            return metadata_commit(owner, packet, **kwargs)
        with patch.object(r.transport, "run_case", side_effect=execute), self.assertRaises(r.RunError) as raised:
            r.collect(self.reference, stream(), self.plan, self.plan_pin, scratch_root=self.root)
        self.assertEqual(seen, [0, 1])
        self.assertEqual(raised.exception.receipt["committed_cases_before_failure"], 1)
        self.assertFalse(raised.exception.receipt["complete_output_eligible"])

    def test_actual_single_png_process_with_lazy_source_failure_has_no_complete_output(self):
        global WRITTEN
        calls = []; receipts = []; real = r.transport.run_case
        def reader(rid, start, stop):
            calls.append((rid, start, stop))
            if len(calls) > 1: raise ValueError("generated stop after first new entrypoint process")
            return [[n + col / 100 for col in range(18)] for n in range(start, stop)]
        def execute(*args, **kwargs):
            receipt = real(*args, **kwargs); receipts.append(receipt); return receipt
        with patch.object(r.transport, "run_case", side_effect=execute), self.assertRaises(r.RunError) as raised:
            r.collect(self.reference, r.packets(self.reference, reader), self.plan, self.plan_pin,
                      scratch_root=self.root)
        WRITTEN += 1  # Existing generated participant's removed cwd marker.
        self.assertEqual(len(receipts), 1); self.assertEqual(len(calls), 2)
        self.assertEqual(receipts[0]["png_frames"], 1)
        self.assertTrue(receipts[0]["cleanup"]["leader_reaped"] and receipts[0]["cleanup"]["owned_group_absent"])
        self.assertFalse(raised.exception.receipt["complete_output_eligible"])
        NOTES.append({"control": "one_actual_entrypoint_PNG_process", "pid": receipts[0]["pid"],
            "png_frames": 1, "wire_sha256": receipts[0]["wire_sha256"], "cleanup": receipts[0]["cleanup"],
            "collection_status": "failed at deliberately stopped generated reader; no complete output"})

    def test_separate_score_refuses_unprotected_or_mismatched_completion_and_rows(self):
        output, seal = self.complete()
        with self.assertRaises(r.RunError):
            r.score(self.reference, self.plan, self.plan_pin, output, seal, "0" * 64)
        for field in ("reference_sha256", "schedule_sha256", "plan_sha256"):
            changed = deepcopy(seal); changed[field] = "0" * 64
            with self.subTest(field=field), self.assertRaises(r.RunError):
                r.score(self.reference, self.plan, self.plan_pin, output, changed, r.digest(changed))
        bad = deepcopy(output); bad["rows"][0]["probability"] = 0.9
        with self.assertRaises(r.collector.CollectionError):
            r.score(self.reference, self.plan, self.plan_pin, bad, seal, r.digest(seal))

    def test_private_writer_refuses_overwrite_and_respects_limit(self):
        global WRITTEN
        target = self.root / "tiny-private.json"
        body = {"generated": True}; WRITTEN += len(r._bytes(body)) + 1
        r.write_new(target, body, 128)
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
        with self.assertRaises(FileExistsError): r.write_new(target, body, 128)
        with self.assertRaises(r.RunError): r.write_new(self.root / "oversize.json", body, 1)
        self.assertFalse((self.root / "oversize.json").exists())

    def test_cli_freeze_and_separate_score_dispatch_use_protected_inputs(self):
        global WRITTEN
        spec = {"argv": self.argv, "artifacts": self.artifacts, "limits": LIMITS, "max_document_bytes": 2097152}
        frozen = self.root / "cli-plan.json"
        common = ["--reference", str(self.root / "prepared-reference.json"), "--case-key", str(self.root / "case-key"),
                  "--read-limit", "2097152"]
        WRITTEN += len(r._bytes(self.plan)) + 1
        with patch.object(r, "_restore", return_value=self.reference), \
             patch.object(r, "read_json", return_value=spec), redirect_stdout(io.StringIO()):
            self.assertEqual(r.main(["freeze", *common, "--participant-spec", str(self.root / "spec.json"),
                                     "--output", str(frozen)]), 0)
        self.assertEqual(r.read_json(frozen, 2097152), self.plan)
        output, seal = self.complete(); bundle = self.root / "success-cli-metadata"; bundle.mkdir()
        documents = {str(frozen): self.plan, str(bundle / "collection.json"): output,
                     str(bundle / "COMPLETED.json"): seal}
        saved = []
        with patch.object(r, "_restore", return_value=self.reference), \
             patch.object(r, "read_json", side_effect=lambda path, _: documents[str(path)]), \
             patch.object(r, "write_new", side_effect=lambda path, report, limit: saved.append((path, report))), \
             redirect_stdout(io.StringIO()):
            code = r.main(["score", *common, "--plan", str(frozen), "--plan-sha256", self.plan_pin,
                "--collection", str(bundle / "collection.json"), "--completion", str(bundle / "COMPLETED.json"),
                "--completion-sha256", r.digest(seal), "--output", str(self.root / "in-memory-score.json")])
        self.assertEqual(code, 0); self.assertEqual(len(saved), 1)
        self.assertAlmostEqual(saved[0][1]["primary_soft_vote_brier"], 1 / 144, places=13)

    def test_private_json_refuses_duplicate_and_nonfinite_metadata(self):
        for index, body in enumerate((b'{"x":1,"x":2}', b'{"x":NaN}')):
            path = self.root / ("bad-json-" + str(index)); generated_write(path, body)
            with self.assertRaises(r.RunError): r.read_json(path, 128)

    def test_cli_persistence_failure_removes_success_seal_and_saved_grade_refuses_failed_bundle(self):
        global WRITTEN
        output, seal = self.complete()
        target = self.root / "failed-cli-bundle"
        source = self.root / "unavailable-authentic-source"
        source.mkdir()
        class FakeSource:
            def __init__(self, _): pass
            def __enter__(self): return self
            def __exit__(self, *_): pass
            def read_samples(self, *_): raise AssertionError("no authentic sample access")
        real_write = r.write_new
        def failing_write(path, document, limit):
            global WRITTEN
            if path.name == "collection.json": document = {"generated": "deliberate withheld fixture"}
            WRITTEN += len(r._bytes(document)) + 1
            real_write(path, document, limit)
            if path.name == "COMPLETED.json": raise OSError("generated postwrite failure")
        base = ["--reference", str(self.root / "private-reference.json"), "--case-key", str(self.root / "private-key"),
                "--read-limit", "2097152", "--plan", str(self.root / "plan.json"), "--plan-sha256", self.plan_pin]
        with patch.object(r, "_restore", return_value=self.reference), patch.object(r, "read_json", return_value=self.plan), \
             patch.object(r, "_load", return_value=SimpleNamespace(SourceCorpus=FakeSource)), \
             patch.object(r, "collect", return_value=(output, seal)), patch.object(r, "write_new", side_effect=failing_write):
            with self.assertRaises(OSError):
                r.main(["collect", *base, "--source-root", str(source), "--scratch-root", str(self.root), "--output", str(target)])
        self.assertTrue((target / "FAILED.json").exists())
        self.assertFalse((target / "COMPLETED.json").exists())
        with patch.object(r, "_restore", return_value=self.reference), patch.object(r, "read_json", return_value=self.plan):
            with self.assertRaises(r.RunError):
                r.main(["score", *base, "--collection", str(target / "collection.json"),
                    "--completion", str(target / "COMPLETED.json"), "--completion-sha256", r.digest(seal),
                    "--output", str(self.root / "forbidden-score.json")])
        self.assertFalse((self.root / "forbidden-score.json").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
