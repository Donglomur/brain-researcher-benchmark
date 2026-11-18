"""Generated PNG and owned-process controls, without authentic EEG or models."""

from copy import deepcopy
import fcntl
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import transport as t


BASE = Path(__file__).resolve().parent
LIMITS = {"wall_seconds": 3, "max_actions": 8, "max_action_bytes": 512,
          "max_stdout_bytes": 4096, "max_response_bytes": 1048576, "max_wire_bytes": 4194304}
PROOFS = []


def fixture():
    p = t.collector.protocol
    ids = ["eeg" + str(i) for i in range(1, 80)]
    folds = p.fold_map(ids, "phase3-invented")
    description = {"schema": p.DESCRIPTION_SCHEMA, "assessment_id": "phase3-invented",
        "protocol_id": p.PROTOCOL, "source_version": p.SOURCE_VERSION,
        "fold_seed": "phase3-invented", "representation_sha256": "a" * 64,
        "detector_sha256": "b" * 64, "source_admission_sha256": "c" * 64,
        "montage": list(p.MONTAGE),
        "development_by_fold": {str(f): [next(r for r in ids if folds[r] != f)] for f in range(5)},
        "recordings": []}
    for rid in ids:
        duration = 31 if rid == "eeg1" else 30
        description["recordings"].append({"recording_id": rid, "eeg_sha256": "d" * 64,
            "sample_rate": {"num": 1, "den": 1}, "sample_count": duration,
            "sample_zero_annotation_second": 0, "units": "uV",
            "labels": [[1] * duration, [0] * duration, [0] * duration],
            "quality_flags": [False] * duration})
    def reader(_rid, start, stop):
        return [[n + col / 100 for col in range(18)] for n in range(start, stop)]
    reference = p.prepare_reference(description, reader, b"generated-process-fixture-key-0123456789")
    schedule = t.collector.freeze_reference(reference)
    digest = p.digest(schedule)
    packets = [p.packet(reference, rid, second, reader) for rid in reference.record_ids()
               for second in range(29, 31 if rid == "eeg1" else 30)]
    return t.collector.Collector(schedule, expected_schedule_sha256=digest), schedule, digest, packets


def command(mode="good", pages=1, extra_fd=None):
    result = [sys.executable, "-I", "-S", "-B", str(BASE / "fixture_participant.py"), mode, str(pages)]
    if extra_fd is not None:
        result.append(str(extra_fd))
    return result


def compact(receipt):
    return {k: receipt[k] for k in ("launch_id", "pid", "process_group_id", "session_id",
            "fresh_exec", "empty_cwd_at_launch", "scratch_removed", "collector_committed",
            "status", "wall_seconds", "cleanup") if k in receipt}


class ProcessControls(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        path = os.environ.get("HELSINKI_TRANSPORT_PROOF_PATH")
        if path:
            body = (json.dumps({"schema": "generated-helsinki-process-controls-v1",
                "scope": "Generated fixtures only; no neural model, authentic EEG or full isolation proof.",
                "records": PROOFS}, indent=2) + "\n").encode()
            assert len(body) <= 24576
            target = Path(path); assert not target.exists()
            target.write_bytes(body)

    def failed(self, mode, expected, *, limits=None, pages=0):
        owner, _, _, packets = fixture()
        with tempfile.TemporaryDirectory(prefix="helsinki-probe-") as root:
            with self.assertRaises(t.TransportError) as raised:
                t.run_case(owner, packets[0], argv=command(mode, pages),
                           limits=LIMITS if limits is None else limits, scratch_root=root)
            error = raised.exception
            self.assertIn(error.code, expected if isinstance(expected, tuple) else (expected,))
            self.assertIsNotNone(error.evidence)
            self.assertFalse(error.evidence["collector_committed"])
            self.assertTrue(error.evidence["cleanup"]["leader_reaped"])
            self.assertTrue(error.evidence["scratch_removed"])
            self.assertEqual(list(Path(root).iterdir()), [])
            self.assertEqual(owner._rows, [])
            with self.assertRaises(t.collector.CollectionError): owner.finish()
            with self.assertRaises(t.collector.CollectionError): owner.open_case(packets[1])
            PROOFS.append({"mode": mode, "expected_failure": error.code,
                           "lifecycle": compact(error.evidence)})
            return error.evidence

    def test_complete_frozen_schedule_through_actual_fresh_pixel_processes(self):
        owner, schedule, digest, packets = fixture()
        receipts = []
        with tempfile.TemporaryDirectory(prefix="helsinki-complete-probe-") as root:
            for i, packet in enumerate(packets):
                receipts.append(t.run_case(owner, packet, argv=command(pages=3 if i < 2 else 1),
                                          limits=LIMITS, scratch_root=root))
                self.assertEqual(list(Path(root).iterdir()), [])
        exported = owner.finish()
        rows = t.collector.admit_collection(schedule, exported, expected_schedule_sha256=digest,
            expected_collection_sha256=t.collector.protocol.digest(exported))
        self.assertEqual(len(rows), 80)
        self.assertEqual({r["probability"] for r in rows}, {0.25})
        self.assertEqual([r["case_id"] for r in rows], [r["case_id"] for r in schedule["bindings"]])
        self.assertEqual(len({r["pid"] for r in receipts}), 80)
        self.assertEqual(len({r["launch_id"] for r in receipts}), 80)
        self.assertEqual(sum(r["png_frames"] for r in receipts), 84)
        for receipt in receipts:
            self.assertTrue(receipt["fresh_exec"] and receipt["empty_cwd_at_launch"])
            self.assertEqual(receipt["pid"], receipt["session_id"])
            self.assertEqual(receipt["pid"], receipt["process_group_id"])
            self.assertTrue(receipt["cleanup"]["leader_reaped"] and receipt["cleanup"]["owned_group_absent"])
            self.assertFalse(receipt["cleanup"]["termination_requested"])
            self.assertTrue(receipt["collector_committed"] and receipt["scratch_removed"])
            self.assertEqual(receipt["cleanup"]["exit_code"], 0)
        PROOFS.append({"mode": "complete_generated_support", "infants": 79, "cases": 80,
            "png_frames": 84, "distinct_observed_pids": [r["pid"] for r in receipts],
            "all_clean_exit_and_group_absent": True, "source_reference_sha256": exported["source_reference_sha256"],
            "collection_sha256": t.collector.protocol.digest(exported),
            "first_two": [compact(r) for r in receipts[:2]],
            "first_wire_sha256": receipts[0]["wire_sha256"], "first_wire_events": receipts[0]["wire_events"]})

    def test_environment_and_explicitly_inheritable_fd_do_not_cross_exec(self):
        owner, _, _, packets = fixture()
        read_fd, write_fd = os.pipe()
        high_fd = fcntl.fcntl(read_fd, fcntl.F_DUPFD, 128)
        os.set_inheritable(high_fd, True)
        try:
            with tempfile.TemporaryDirectory(prefix="helsinki-fd-probe-") as root:
                with patch.dict(os.environ, {"HELSINKI_PARENT_SECRET": "generated-host-only-token"}):
                    receipt = t.run_case(owner, packets[0], argv=command(pages=0, extra_fd=high_fd),
                                         limits=LIMITS, scratch_root=root)
            self.assertTrue(receipt["collector_committed"])
            PROOFS.append({"mode": "environment_and_fd_exclusion", "lifecycle": compact(receipt)})
        finally:
            for fd in (read_fd, write_fd, high_fd): os.close(fd)

    def test_strict_json_framing_refuses_duplicate_invalid_partial_and_extra(self):
        for mode, code in (("duplicate", "duplicate_json_key"), ("utf8", "malformed_json_action"),
            ("partial", "participant_eof_before_answer"), ("two_frames", "multiple_or_extra_frames"),
            ("oversize", "action_byte_limit"), ("nonfinite", "nonfinite_json_number")):
            with self.subTest(mode=mode): self.failed(mode, code)

    def test_only_original_current_case_typed_actions_are_accepted(self):
        for mode in ("wrong_binding", "unknown_action", "future", "extra_field"):
            with self.subTest(mode=mode): self.failed(mode, "invalid_typed_action")

    def test_first_final_answer_cannot_be_revised_or_followed_by_output(self):
        self.failed("after_answer", "output_after_final_answer")

    def test_nonzero_exit_after_answer_withholds_collector_commit(self):
        self.failed("nonzero", "participant_nonzero_exit")

    def test_deadlines_cover_before_and_after_final_answer(self):
        limits = dict(LIMITS, wall_seconds=1)
        for mode in ("hang_before", "hang_after"):
            with self.subTest(mode=mode):
                receipt = self.failed(mode, "participant_deadline", limits=limits)
                self.assertTrue(receipt["cleanup"]["termination_requested"])
                self.assertTrue(receipt["cleanup"]["owned_group_absent"])
                self.assertLess(receipt["wall_seconds"], 1.2)

    def test_action_and_wire_budgets_fail_without_partial_export(self):
        self.failed("repeat", "action_limit", limits=dict(LIMITS, max_actions=2))
        owner, _, _, packets = fixture()
        session = owner.open_case(packets[0]); description = session.act({"action": "describe"})
        length = len(t._response(description, description["binding"]))
        self.failed("repeat", "wire_byte_limit", limits=dict(LIMITS,
            max_response_bytes=length + 100, max_wire_bytes=length + 100))
        self.failed("good", "response_byte_limit", limits=dict(LIMITS, max_response_bytes=100))

    def test_closed_input_is_bounded_and_uncommitted(self):
        self.failed("closed_input", "participant_closed_input")

    def test_residual_owned_process_group_is_rejected_and_cleanup_is_reported(self):
        receipt = self.failed("descendant", "residual_participant_process_group")
        self.assertTrue(receipt["cleanup"]["termination_requested"])
        # Group disappearance is recorded, not assumed on OSes with delayed zombie reaping.
        self.assertIs(type(receipt["cleanup"]["owned_group_absent"]), bool)

    def test_permission_error_during_exiting_group_probe_preserves_failure_and_reaps(self):
        real_killpg = os.killpg
        injected = []
        def transient_permission(pgid, sig):
            if sig == 0 and not injected:
                injected.append(pgid)
                raise PermissionError("generated transient group observation failure")
            return real_killpg(pgid, sig)
        with patch.object(t.os, "killpg", side_effect=transient_permission):
            receipt = self.failed("partial", "participant_eof_before_answer")
        self.assertEqual(injected, [receipt["pid"]])
        self.assertTrue(receipt["cleanup"]["group_probe_unavailable"])
        self.assertTrue(receipt["cleanup"]["leader_reaped"] and receipt["cleanup"]["owned_group_absent"])

    def test_wire_allowlist_refuses_accidental_host_schema_expansion(self):
        owner, _, _, packets = fixture()
        session = owner.open_case(packets[0]); original = session.act({"action": "describe"})
        for field in ("samples", "labels", "case_roster", "source_reference_sha256"):
            response = deepcopy(original); response[field] = []
            with self.subTest(field=field), self.assertRaises(t.TransportError):
                t._response(response, original["binding"])
        response = deepcopy(original); response["sample_clock"]["absolute_recording_offset"] = 10
        with self.assertRaises(t.TransportError): t._response(response, original["binding"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
