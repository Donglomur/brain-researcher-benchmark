"""Generated controller gates only; execute() is replaced before source work."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from suns2_benchmark import input_stage as stage


class ControllerControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.profile_path = self.root/"protocol.json"
        self.ledger_path = self.root/"ledger.json"
        self.profile = {"schema": "suns2-original-input-native-protocol/v1", "owner": "close_suns2_candidate",
                        "resource_ledger": str(self.ledger_path), "frozen_files": [],
                        "stages": {"acquire": {"native_id": "generated-one", "approval_id": "generated-approval"}},
                        "payload_reservations": [{"id": "generated-grant", "bytes": 17, "destination": str(self.root/"payload")}],
                        "execution_evidence": str(self.root/"evidence")}
        self.profile_path.write_text(json.dumps(self.profile))
        self.digest = hashlib.sha256(self.profile_path.read_bytes()).hexdigest()
        self.ledger = {"native_runs": [{"id": "generated-one", "owner": "close_suns2_candidate",
                        "status": "running", "approval_id": "generated-approval",
                        "protocol": {"sha256": self.digest, "path": str(self.profile_path)}}],
                        "reservations": [{"id": "generated-grant", "status": "active",
                        "owner": "close_suns2_candidate", "reserved_bytes": 17,
                        "destination": str(self.root/"payload")}]}
        self.save_ledger()

    def tearDown(self):
        self.temp.cleanup()

    def save_ledger(self):
        self.ledger_path.write_text(json.dumps(self.ledger))

    def invoke(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return stage.main(["--stage", "acquire", "--protocol", str(self.profile_path),
                               "--protocol-sha256", self.digest])

    def test_unapproved_lease_is_rejected_before_execute(self):
        self.ledger["native_runs"][0]["status"] = "succeeded"
        self.save_ledger()
        with patch.object(stage, "execute") as execute:
            with self.assertRaises(stage.StageRefusal):
                self.invoke()
            execute.assert_not_called()
        self.assertFalse((self.root/"evidence").exists())

    def test_wrong_reservation_destination_is_rejected_before_execute(self):
        self.ledger["reservations"][0]["destination"] = str(self.root/"elsewhere")
        self.save_ledger()
        with patch.object(stage, "execute") as execute:
            with self.assertRaises(stage.StageRefusal):
                self.invoke()
            execute.assert_not_called()

    def test_pinned_protocol_and_unique_JSON_keys_are_required(self):
        self.profile_path.write_text('{"schema":"x","schema":"y"}')
        with patch.object(stage, "execute") as execute:
            with self.assertRaises(stage.StageRefusal):
                self.invoke()
            execute.assert_not_called()
        duplicate = self.root/"duplicate.json"
        duplicate.write_text('{"key":1,"key":2}')
        with self.assertRaises(stage.StageRefusal):
            stage.bounded_json(duplicate)

    def test_success_receipt_is_durable_and_does_not_rerun(self):
        with patch.object(stage, "execute", return_value={"generated": True}) as execute:
            self.assertEqual(self.invoke(), 0)
            self.assertEqual(execute.call_count, 1)
            with self.assertRaises(FileExistsError):
                self.invoke()
            self.assertEqual(execute.call_count, 1)
        result = json.loads((self.root/"evidence/acquire-result.json").read_text())
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["authority"]["protocol_sha256"], self.digest)

    def test_failed_extraction_receipt_keeps_conservative_charge(self):
        error = ValueError("generated partial write")
        error.receipt = {"written_payload_bytes": 7, "conservative_payload_charge_bytes": 31,
                         "unverified_write_upper_bound_bytes": 24}
        with patch.object(stage, "execute", side_effect=error) as execute:
            self.assertEqual(self.invoke(), 1)
            self.assertEqual(execute.call_count, 1)
        result = json.loads((self.root/"evidence/acquire-result.json").read_text())
        self.assertEqual(result["status"], "failed_or_refused")
        self.assertEqual(result["receipt"]["conservative_payload_charge_bytes"], 31)

    def test_unknown_native_cleanup_is_not_promoted_to_success(self):
        error = ValueError("generated unverified native close")
        error.native_closure_unverified = True
        error.cleanup_errors = ["generated close failure"]
        with patch.object(stage, "execute", side_effect=error), \
             patch.object(stage.os, "_exit", side_effect=SystemExit(1)) as terminate:
            with self.assertRaises(SystemExit):
                self.invoke()
            terminate.assert_called_once_with(1)
        result = json.loads((self.root/"evidence/acquire-result.json").read_text())
        self.assertEqual(result["status"], "failed_or_refused")
        self.assertTrue(result["native_closure_unverified"])
        self.assertEqual(result["cleanup_errors"], ["generated close failure"])

    def prior_receipt(self):
        self.profile["process_evidence"] = str(self.root/"process")
        (self.root/"process").mkdir()
        identity = {"native_id": "generated-one", "approval_id": "generated-approval",
                    "protocol_sha256": self.digest, "owner": "close_suns2_candidate"}
        prior = {"stage": "acquire", "status": "succeeded", "authority": identity,
                 "result": {"generated": True}}
        prior_path = self.root/"previous.json"
        prior_path.write_text(json.dumps(prior))
        process = {"stage": "acquire", "authority": identity, "status": "succeeded",
                   "returncode": 0, "error": None, "capture_complete": True, "child_peak_RSS_bytes": 1}
        (self.root/"process/acquire-process.json").write_text(json.dumps(process))
        self.ledger["native_runs"][0].update(status="succeeded", exit_code=0)
        self.save_ledger()
        return prior_path, prior, process

    def test_prior_stage_requires_same_protocol_authority(self):
        path, prior, _ = self.prior_receipt()
        self.assertEqual(stage._prior_result(path, "acquire", self.profile, self.digest), {"generated": True})
        prior["authority"]["protocol_sha256"] = "0"*64
        path.write_text(json.dumps(prior))
        with self.assertRaises(stage.StageRefusal):
            stage._prior_result(path, "acquire", self.profile, self.digest)

    def test_prior_child_success_does_not_override_failed_wrapper_or_native_run(self):
        path, _, process = self.prior_receipt()
        process["status"] = "failed"
        (self.root/"process/acquire-process.json").write_text(json.dumps(process))
        with self.assertRaises(stage.StageRefusal):
            stage._prior_result(path, "acquire", self.profile, self.digest)
        process["status"] = "succeeded"
        (self.root/"process/acquire-process.json").write_text(json.dumps(process))
        self.ledger["native_runs"][0].update(status="failed", exit_code=1)
        self.save_ledger()
        with self.assertRaises(stage.StageRefusal):
            stage._prior_result(path, "acquire", self.profile, self.digest)

    def test_broken_capture_flush_cannot_skip_low_level_termination(self):
        class BrokenFlush(io.StringIO):
            def flush(self):
                raise BrokenPipeError("generated closed capture pipe")
        error = ValueError("generated native close uncertainty")
        error.native_closure_unverified = True
        with patch.object(stage, "execute", side_effect=error), \
             patch.object(stage.os, "_exit", side_effect=SystemExit(1)) as terminate, \
             contextlib.redirect_stdout(BrokenFlush()):
            with self.assertRaises(SystemExit):
                stage.main(["--stage", "acquire", "--protocol", str(self.profile_path),
                            "--protocol-sha256", self.digest])
            terminate.assert_called_once_with(1)
        result = json.loads((self.root/"evidence/acquire-result.json").read_text())
        self.assertEqual(result["status"], "failed_or_refused")
        self.assertTrue(result["native_closure_unverified"])


if __name__ == "__main__":
    unittest.main()
