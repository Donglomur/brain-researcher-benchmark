"""Generated full-panel lifecycle controls; never launch Docker or read source data."""
from pathlib import Path
import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
from unittest.mock import patch
import numpy as np

HERE = Path(__file__).absolute().parent
REPO = HERE.parents[4]
spec = importlib.util.spec_from_file_location("neural023_program_adapter", HERE / "run.py")
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)


def npz(ids, values):
    stream = io.BytesIO()
    np.savez(stream, case_id=ids, velocity_m_s=values)
    return stream.getvalue()


class Lifecycle(unittest.TestCase):
    generated_bytes_written = 0

    @classmethod
    def setUpClass(cls):
        cls.ids = np.arange(3010, 25101, dtype="<u4")
        n = np.arange(22091)
        cls.truth = np.column_stack((n % 7 / 10, n % 11 / 20)).astype("<f8")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="neural023-program-generated-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.candidate = self.root / "submitted.py"
        self.candidate.write_text("raise RuntimeError('This generated candidate must never run on the host')\n")
        self.stage = self.root / "stage"
        self.plan_pin = a.stage(REPO, self.candidate, self.root / "nonexistent-public-inputs", self.stage, "sha256:" + "a" * 64)
        self.plan = json.loads((self.stage / "PLAN.json").read_text())
        self.events = []
        self.modules, self.scorer, self.dependencies = a.load_dependencies(REPO)
        self.target = self.root / "invented-target.npz"
        self.write(self.target, npz(self.ids, self.truth))
        self.scorer.TARGET = a.pin(self.target.read_bytes())
        science = self.scorer.load_modules(REPO / a.SCORER / "dependencies")
        metric = science["score_core"].score(self.truth, {"zero": np.zeros_like(self.truth)})["metrics"]["zero"]
        names = ("zero_velocity", "source_mean_velocity", "calibration_mean_velocity", "source_only_ridge",
                 "source_only_ridge_plus_calibration_mean_residual", "calibration_only_ridge", "balanced_pooled_ridge")
        self.reference = self.root / "invented-references.json"
        self.write(self.reference, a.encoded({"candidate_id": "NEURAL-023", "status": "fixed_reference_scored_and_independently_audited",
            "result": {"primary_metric": "mean_axis_r2", "metrics": {k: metric for k in names}}}))
        self.scorer.REFERENCE = a.pin(self.reference.read_bytes())
        original = self.scorer.snapshot
        def guarded(path, *args, **kwargs):
            if Path(path) in (self.target, self.reference):
                self.assertIn("independent_observation", self.events)
                self.events.append("private_input_read")
            return original(path, *args, **kwargs)
        self.scorer.snapshot = guarded
        self.addCleanup(patch.stopall)
        patch.object(a, "load_dependencies", return_value=(self.modules, self.scorer, self.dependencies)).start()
        self.submission = npz(self.ids, self.truth)
        self.fault = None
        self.config = self.configuration()

    def write(self, path, raw):
        path.write_bytes(raw)
        type(self).generated_bytes_written += len(raw)

    def configuration(self):
        exposure = {"schema": "osl_transport_exposure_v1", "role": "A", "image": self.plan["image"],
            "source": self.plan["source"], "command": self.plan["command"],
            "mounts": self.modules["bounds"].mount_identity(self.plan["mounts"]),
            "approved_image_inventory_sha256": "b" * 64, "boundary_audit": {"bytes": 1, "sha256": "c" * 64},
            "role_boundary_verified": True}
        path = self.root / "invented-exposure.json"
        self.write(path, a.encoded(exposure))
        return {"docker_binary": str(self.root / "DO-NOT-RUN"), "docker_socket": str(self.root / "NO-SOCKET"),
            "control_root": str(self.root / "control"), "quarantine_root": str(self.root / "quarantine"),
            "exposure_path": str(path), "exposure_pin": a.pin(path.read_bytes())}

    def provider(self, *args):
        owner = self
        class Fake:
            quarantine_root = Path(args[1])
            def execute_phase(self, request, mounts, deadline, journal):
                owner.events.append("fake_producer_closed")
                journal("FAKE-PRODUCER-CLOSED", {})
                root = self.quarantine_root / request["phase_id"]
                root.mkdir(parents=True)
                owner.write(root / "predictions.npz", owner.submission)
                result_body = a.encoded({"schema": "neural023_candidate_output_v1", "candidate_exit": 0})
                owner.write(root / "RESULT.json", result_body)
                manifest = {"schema": "osl_transport_output_manifest_v1", "phase_id": request["phase_id"],
                    "request_sha256": a.pin(a.encoded(request))["sha256"],
                    "files": {"predictions.npz": a.pin(owner.submission), "RESULT.json": a.pin(result_body)}}
                raw = a.encoded(manifest)
                owner.write(root / "OUTPUTS.json", raw)
                members = {**manifest["files"], "OUTPUTS.json": a.pin(raw)}
                self.receipt = {**{key: request[key] for key in ("phase_id", "action", "role", "image", "source", "exposure")},
                    "status": "captured", "request_sha256": a.pin(a.encoded(request))["sha256"],
                    "producer_closed_before_capture": True, "all_native_resources_closed": True, "cli_reaped": True,
                    "natural_exit": {"Status": "exited", "Running": False, "Dead": False, "Pid": 0, "ExitCode": 0, "OOMKilled": False},
                    "input_before": owner.modules["bounds"].mount_identity(mounts),
                    "input_after": owner.modules["bounds"].mount_identity(mounts),
                    "quarantine_root": str(root), "output_inventory": {"complete": True, "files": members}}
                if owner.fault == "closure":
                    self.receipt["producer_closed_before_capture"] = False
                elif owner.fault == "extra":
                    self.receipt["output_inventory"]["files"]["extra.txt"] = a.pin(b"x")
                elif owner.fault == "capture_tamper":
                    owner.write(root / "predictions.npz", b"changed after capture")
                self.receipt_pin = a.pin(a.encoded(self.receipt))
                return {"receipt": self.receipt, "receipt_pin": self.receipt_pin}
            def observe(self, phase, request, expected, deadline):
                owner.events.append("independent_observation")
                if owner.fault == "observation":
                    self.receipt["status"] = "failed"
                return {"receipt": self.receipt, "receipt_pin": self.receipt_pin}
        return Fake()

    def run_case(self, **kwargs):
        return a.execute(REPO, self.stage, self.plan_pin, self.config,
            kwargs.get("target", self.target), kwargs.get("reference", self.reference),
            self.root / kwargs.get("output", "result"), provider_factory=self.provider)

    def test_full_reordered_support_and_original_metrics(self):
        self.submission = npz(self.ids[::-1], self.truth[::-1])
        receipt = self.run_case()
        result = json.loads((self.root / "result/grade/score.json").read_text())
        self.assertEqual(receipt["status"], "scored_development_candidate")
        self.assertTrue(receipt["test_provider"])
        self.assertEqual(result["submission_rows"], 22091)
        self.assertEqual(result["primary_score"], 1)
        self.assertEqual(len(result["signed_reference_comparisons"]), 7)
        self.assertEqual(len(result["fixed_clock_blocks"]), 8)
        self.assertEqual(self.events[:2], ["fake_producer_closed", "independent_observation"])

    def test_negative_score_is_valid(self):
        self.submission = npz(self.ids, np.zeros_like(self.truth))
        receipt = self.run_case()
        self.assertEqual(receipt["status"], "scored_development_candidate")
        self.assertLess(json.loads((self.root / "result/grade/score.json").read_text())["primary_score"], 0)

    def test_missing_endpoint_before_operator_inputs(self):
        self.submission = npz(self.ids[:-1], self.truth[:-1])
        receipt = self.run_case(target=self.root / "absent-target", reference=self.root / "absent-reference")
        self.assertEqual(receipt["status"], "invalid_submission")
        self.assertEqual(receipt["private_target_loads"], 0)
        self.assertNotIn("private_input_read", self.events)

    def test_duplicate_endpoint_before_operator_inputs(self):
        ids = self.ids.copy(); ids[0] = ids[1]
        self.submission = npz(ids, self.truth)
        self.assertEqual(self.run_case()["status"], "invalid_submission")
        self.assertNotIn("private_input_read", self.events)

    def test_nonfinite_before_operator_inputs(self):
        values = self.truth.copy(); values[0, 1] = np.nan
        self.submission = npz(self.ids, values)
        self.assertEqual(self.run_case()["status"], "invalid_submission")
        self.assertNotIn("private_input_read", self.events)

    def test_malformed_before_operator_inputs(self):
        self.submission = b"not npz"
        self.assertEqual(self.run_case()["status"], "invalid_submission")
        self.assertNotIn("private_input_read", self.events)

    def test_unclosed_producer_refused(self):
        self.fault = "closure"
        with self.assertRaisesRegex(ValueError, "Removed producer"):
            self.run_case()
        self.assertNotIn("private_input_read", self.events)

    def test_changed_observation_refused(self):
        self.fault = "observation"
        with self.assertRaisesRegex(ValueError, "receipt identity"):
            self.run_case()
        self.assertNotIn("private_input_read", self.events)

    def test_extra_captured_member_refused(self):
        self.fault = "extra"
        with self.assertRaisesRegex(ValueError, "three-file"):
            self.run_case()
        self.assertNotIn("private_input_read", self.events)

    def test_capture_mutation_refused(self):
        self.fault = "capture_tamper"
        with self.assertRaisesRegex(ValueError, "pin mismatch"):
            self.run_case()
        self.assertNotIn("private_input_read", self.events)

    def test_mutation_after_validation_before_original_scorer_is_refused(self):
        original_run = self.scorer.run
        def change_then_score(root, submission, output, **kwargs):
            # A different, still fully valid full-panel NPZ arrives after the
            # adapter's initial validation. It must not change the scored file.
            self.write(submission, npz(self.ids, np.zeros_like(self.truth)))
            return original_run(root, submission, output, **kwargs)
        with patch.object(self.scorer, "run", change_then_score):
            receipt = self.run_case()
        self.assertEqual(receipt["status"], "operator_error")
        self.assertNotIn("private_input_read", self.events)
        grade = json.loads((self.root / "result/grade/receipt.json").read_text())
        self.assertIn("Pinned input mismatch", grade["error"])
        self.assertFalse((self.root / "result/grade/score.json").exists())

    def test_program_mutation_after_freeze_refused(self):
        (self.stage / "candidate.py").chmod(0o600)
        self.write(self.stage / "candidate.py", b"print('changed')\n")
        with self.assertRaisesRegex(ValueError, "pin mismatch"):
            self.run_case()
        self.assertEqual(self.events, [])

    def test_mount_injection_even_with_new_plan_pin_refused(self):
        path = self.stage / "PLAN.json"; path.chmod(0o600)
        self.plan["mounts"]["/private/target.npz"] = self.plan["mounts"]["/input/source.npz"]
        self.write(path, a.encoded(self.plan)); self.plan_pin = a.pin(path.read_bytes())
        with self.assertRaisesRegex(ValueError, "Only four"):
            self.run_case()
        self.assertEqual(self.events, [])

    def test_wrong_exposure_rejected_before_producer(self):
        path = Path(self.config["exposure_path"])
        exposure = json.loads(path.read_text()); exposure["image"] = "sha256:" + "d" * 64
        self.write(path, a.encoded(exposure)); self.config["exposure_pin"] = a.pin(path.read_bytes())
        with self.assertRaisesRegex(ValueError, "approved image"):
            self.run_case()
        self.assertEqual(self.events, [])

    def test_stage_does_not_read_public_payload_and_has_no_approval(self):
        self.assertFalse((self.root / "nonexistent-public-inputs").exists())
        proposed = json.loads((self.stage / "EXPOSURE_REQUEST.json").read_text())
        self.assertNotIn("role_boundary_verified", proposed)
        self.assertEqual(len(proposed["mounts"]), 6)

    def test_same_frozen_attempt_cannot_be_retried(self):
        self.submission = b"invalid"
        self.run_case()
        with self.assertRaises(FileExistsError):
            self.run_case(output="second-result")

    @classmethod
    def tearDownClass(cls):
        print(json.dumps({"generated_fixture_payload_bytes_written": cls.generated_bytes_written,
            "payload_counter_scope": "Test write() calls only; source/stage/transport metadata writes excluded",
            "authentic_payload_reads": 0, "candidate_host_executions": 0, "docker_executions": 0,
            "model_calls": 0}))


if __name__ == "__main__":
    unittest.main(verbosity=2)
