"""Generated complete-output controls; no authentic packet or Docker execution."""
from pathlib import Path
import copy
import importlib.util
import io
import json
import math
import os
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import numpy as np

HERE = Path(__file__).absolute().parent
REPO = HERE.parents[4]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


a = module("neural019_program_adapter", HERE / "run.py")


def npz(values):
    stream = io.BytesIO()
    np.savez(stream, **values)
    return stream.getvalue()


class NeverResolve:
    def __fspath__(self):
        raise AssertionError("Private path resolved before complete validation")


class Lifecycle(unittest.TestCase):
    fixture_payload_bytes_written = 0

    def write(self, path, body):
        path.write_bytes(body)
        type(self).fixture_payload_bytes_written += len(body)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="neural019-program-generated-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.candidate = self.root / "submitted.py"
        self.write(self.candidate, b"raise RuntimeError('Generated candidate must never run on the host')\n")
        self.public_root = self.root / "public"
        self.public_root.mkdir()
        self.stage = self.root / "stage"
        self.plan_pin = a.stage(REPO, self.candidate, self.public_root, self.stage, "sha256:" + "a" * 64)
        self.plan = json.loads((self.stage / "PLAN.json").read_text())
        self.modules, self.scorer, self.dependencies = a.load_dependencies(REPO)
        self.events, self.fault = [], None
        self.groups = np.repeat([8, 13, 18, 20, 23, 31, 34, 37], [2, 3, 5, 7, 11, 17, 31, 50])
        self.public = {"trial_ids": np.asarray([f"generated-{i:03d}" for i in range(126)]),
            "velocity_left_edges_ms": np.arange(-150, 550, 5), "velocity_axes": np.asarray(["x", "y"]),
            "velocity_units": np.asarray("m/s"), "panel_fingerprint": np.asarray("1" * 64)}
        clock = np.arange(140, dtype=np.float64) - 69.5
        scales = (1 + np.arange(126) % 7)[:, None]
        self.truth = np.stack((scales * clock, -2 * scales * clock), axis=-1)
        self.values = self.truth + np.asarray([3.0, -4.0])
        self.submission = npz(dict(self.public, velocity=self.values))
        # This intentionally small invented packet holds only scorer metadata,
        # never claims authentic full-input preparation or train-count delivery.
        self.packet = self.public_root / "public.npz"
        self.write(self.packet, npz({"assessment_trial_ids" if k == "trial_ids" else k: v for k, v in self.public.items()}))
        self.target = self.root / "invented-target.npz"
        self.write(self.target, npz(dict(self.public, velocity=self.truth, trial_types=self.groups)))
        self.reference_grade, self.reference_commit = self.root / "invented-grade.json", self.root / "invented-commit.json"
        assets = copy.deepcopy(self.scorer.ASSETS)
        assets["public"]["packet"] = a.pin(self.packet.read_bytes())
        assets["private"]["targets"] = a.pin(self.target.read_bytes())
        grade = {"status": "scored_with_independent_arithmetic_check", "scientific_score_computed": True,
            "all_public_submissions_validated_before_targets": True, "target_loader_invocations": 1,
            "new_fits": 0, "pass_threshold": None, "trial_count": 126, "groups": 8, "units": "m/s",
            "metrics": {}, "validations": {}, "independent_arithmetic": {"passed": True, "checks": 704,
                "trials": 126, "groups": 8, "fits_performed_by_auditor": 0, "reference_core_imported_by_auditor": False,
                "tolerance": {"absolute": 1e-10, "relative_to_independent_value": 1e-10}, "metrics": {}}}
        for index, arm in enumerate(self.scorer.ARMS):
            value = float(index - 2)
            grade["metrics"][arm] = {"macro_r2": value, "defined": True, "pooled": {"uniform_axis_r2": value},
                "per_type": [{"trial_type": int(g), "trials": int((self.groups == g).sum())} for g in np.unique(self.groups)]}
            grade["independent_arithmetic"]["metrics"][arm] = {"macro_r2": value, "pooled": {"uniform_axis_r2": value}}
            grade["validations"][arm] = {"status": "public_submission_valid", "cases": 126, "bins": 140,
                "axes": ["x", "y"], "units": "m/s", "target_loader_invocations": 0}
        commit = {"source_freeze_sha256": self.scorer.REFERENCE_FREEZE, "status": "predictions_frozen_before_private_grade",
            "producer_removed_and_absent": True, "producer_execution_sha256": "a" * 64,
            "files": {name: {"bytes": 1, "sha256": "b" * 64} for name in self.scorer.REFERENCE_FILES}}
        self.write(self.reference_grade, a.encoded(grade)); self.write(self.reference_commit, a.encoded(commit))
        assets["private"]["reference_grade"] = a.pin(self.reference_grade.read_bytes())
        assets["private"]["reference_commit"] = a.pin(self.reference_commit.read_bytes())
        self.scorer.ASSETS = assets  # Test-only invented pins; production has no override.
        original = self.scorer.pinned
        def observe_input(path, *args):
            if path in (self.target, self.reference_grade, self.reference_commit):
                self.assertIn("independent_observation", self.events)
                self.events.append("private_input_read")
            return original(path, *args)
        self.scorer.pinned = observe_input
        patcher = patch.object(a, "load_dependencies", return_value=(self.modules, self.scorer, self.dependencies))
        patcher.start(); self.addCleanup(patcher.stop)
        exposure = {"schema": "osl_transport_exposure_v1", "role": "A", "image": self.plan["image"],
            "source": self.plan["source"], "command": self.plan["command"],
            "mounts": self.modules["bounds"].mount_identity(self.plan["mounts"]),
            "approved_image_inventory_sha256": "b" * 64, "boundary_audit": {"bytes": 1, "sha256": "c" * 64},
            "role_boundary_verified": True}
        self.exposure = self.root / "invented-exposure.json"; self.write(self.exposure, a.encoded(exposure))
        self.config = {"docker_binary": str(self.root / "DO-NOT-RUN"), "docker_socket": str(self.root / "NO-SOCKET"),
            "control_root": str(self.root / "control"), "quarantine_root": str(self.root / "quarantine"),
            "exposure_path": str(self.exposure), "exposure_pin": a.pin(self.exposure.read_bytes())}

    def provider(self, *args):
        owner = self
        class Fake:
            quarantine_root = Path(args[1])
            def execute_phase(self, request, mounts, deadline, journal):
                owner.events.append("fake_producer_closed"); journal("FAKE-PRODUCER-CLOSED", {})
                root = self.quarantine_root / request["phase_id"]; root.mkdir(parents=True)
                owner.write(root / "predictions.npz", owner.submission)
                result = a.encoded({"schema": "neural019_candidate_output_v1", "candidate_exit": 0})
                owner.write(root / "RESULT.json", result)
                manifest = {"schema": "osl_transport_output_manifest_v1", "phase_id": request["phase_id"],
                    "request_sha256": a.pin(a.encoded(request))["sha256"],
                    "files": {"predictions.npz": a.pin(owner.submission), "RESULT.json": a.pin(result)}}
                raw = a.encoded(manifest); owner.write(root / "OUTPUTS.json", raw)
                self.receipt = {**{k: request[k] for k in ("phase_id", "action", "role", "image", "source", "exposure")},
                    "status": "captured", "request_sha256": a.pin(a.encoded(request))["sha256"],
                    "producer_closed_before_capture": True, "all_native_resources_closed": True, "cli_reaped": True,
                    "deadline_exceeded": False, "timing": {"original_deadline": deadline, "started": request["clock"]["origin"],
                        "finished": request["clock"]["origin"] + 1, "phase_deadline": deadline},
                    "natural_exit": {"Status": "exited", "Running": False, "Dead": False, "Pid": 0, "ExitCode": 0, "OOMKilled": False},
                    "input_before": owner.modules["bounds"].mount_identity(mounts),
                    "input_after": owner.modules["bounds"].mount_identity(mounts), "quarantine_root": str(root),
                    "output_inventory": {"complete": True, "files": {**manifest["files"], "OUTPUTS.json": a.pin(raw)}}}
                if owner.fault == "closure": self.receipt["producer_closed_before_capture"] = False
                if owner.fault == "cleanup": self.receipt["all_native_resources_closed"] = False
                if owner.fault == "late": self.receipt["deadline_exceeded"] = True
                if owner.fault == "extra": self.receipt["output_inventory"]["files"]["extra"] = a.pin(b"x")
                if owner.fault == "tamper": owner.write(root / "predictions.npz", b"changed after capture")
                self.receipt_pin = a.pin(a.encoded(self.receipt))
                return {"receipt": self.receipt, "receipt_pin": self.receipt_pin}
            def observe(self, *args):
                owner.events.append("independent_observation")
                if owner.fault == "observation": self.receipt["status"] = "failed"
                return {"receipt": self.receipt, "receipt_pin": self.receipt_pin}
        return Fake()

    def run_case(self, unavailable=False, output="result"):
        private = [NeverResolve()] * 3 if unavailable else [self.target, self.reference_grade, self.reference_commit]
        return a.execute(REPO, self.stage, self.plan_pin, self.config, *private, self.root / output, provider_factory=self.provider)

    def test_full_reordered_support_and_original_scalar_metric(self):
        self.submission = npz(dict(self.public, trial_ids=self.public["trial_ids"][::-1], velocity=np.asfortranarray(self.values[::-1])))
        result = self.run_case(); score = json.loads((self.root / "result/SCORE.json").read_text())
        self.assertEqual((result["status"], score["trial_count"], score["groups"]), ("scored", 126, 8))
        # Independent scalar endpoint; unequal group sizes catch pooled substitution.
        groups = []
        for group in np.unique(self.groups):
            axes = []
            for axis in range(2):
                truth = [float(x) for x in self.truth[self.groups == group, :, axis].flat]
                predicted = [float(x) for x in self.values[self.groups == group, :, axis].flat]
                mean = math.fsum(truth) / len(truth)
                axes.append(1 - math.fsum((x-y)**2 for x,y in zip(truth,predicted)) / math.fsum((x-mean)**2 for x in truth))
            groups.append(math.fsum(axes) / 2)
        self.assertAlmostEqual(score["primary_metric"], math.fsum(groups) / 8, places=12)
        self.assertEqual(len(score["signed_differences"]), 4)
        self.assertEqual(self.events[:2], ["fake_producer_closed", "independent_observation"])

    def test_missing_trial_rejected_before_private_paths(self):
        self.submission = npz(dict(self.public, trial_ids=self.public["trial_ids"][:-1], velocity=self.values[:-1]))
        self.assertEqual(self.run_case(True)["status"], "invalid_submission")
        self.assertNotIn("private_input_read", self.events)

    def test_wrong_clock_rejected_before_private_paths(self):
        self.submission = npz(dict(self.public, velocity=self.values, velocity_left_edges_ms=np.arange(-145, 555, 5)))
        self.assertEqual(self.run_case(True)["status"], "invalid_submission")

    def test_duplicate_identity_rejected_before_private_paths(self):
        ids = self.public["trial_ids"].copy(); ids[0] = ids[1]
        self.submission = npz(dict(self.public, trial_ids=ids, velocity=self.values))
        self.assertEqual(self.run_case(True)["status"], "invalid_submission")

    def test_nonfinite_rejected_before_private_paths(self):
        values = self.values.copy(); values[-1, -1, -1] = np.nan
        self.submission = npz(dict(self.public, velocity=values))
        self.assertEqual(self.run_case(True)["status"], "invalid_submission")

    def test_malformed_rejected_before_private_paths(self):
        self.submission = b"not an archive"
        self.assertEqual(self.run_case(True)["status"], "invalid_submission")

    def test_unclosed_producer_refused(self):
        self.fault = "closure"
        with self.assertRaisesRegex(ValueError, "Removed producer"): self.run_case(True)

    def test_changed_observation_refused(self):
        self.fault = "observation"
        with self.assertRaisesRegex(ValueError, "receipt identity"): self.run_case(True)

    def test_incomplete_cleanup_refused_before_private_paths(self):
        self.fault = "cleanup"
        with self.assertRaisesRegex(ValueError, "complete owned-resource closure"): self.run_case(True)

    def test_late_capture_refused_before_private_paths(self):
        self.fault = "late"
        with self.assertRaisesRegex(ValueError, "unchanged original deadline"): self.run_case(True)

    def test_extra_output_refused(self):
        self.fault = "extra"
        with self.assertRaisesRegex(ValueError, "three-file"): self.run_case(True)

    def test_capture_mutation_refused(self):
        self.fault = "tamper"
        with self.assertRaisesRegex(ValueError, "pin mismatch"): self.run_case(True)

    def test_second_snapshot_bound_to_transport_pin(self):
        original = self.scorer.evaluate
        def mutate(action, submission, *args, **kwargs):
            self.write(submission, npz(dict(self.public, velocity=np.zeros_like(self.values))))
            return original(action, submission, *args, **kwargs)
        with patch.object(self.scorer, "evaluate", mutate):
            result = self.run_case(True)
        self.assertEqual(result["status"], "invalid_submission")
        self.assertEqual(result["private_target_loads"], 0)
        self.assertIn("captured submission identity", json.loads((self.root / "result/SCORE.json").read_text())["error"])

    def test_source_changed_after_freeze_refused(self):
        path = self.stage / "program.py"; path.chmod(0o600); self.write(path, b"changed\n")
        with self.assertRaisesRegex(ValueError, "pin mismatch"): self.run_case(True)
        self.assertEqual(self.events, [])

    def test_mount_injection_refused(self):
        self.plan["mounts"]["/private"] = self.plan["mounts"]["/input/public.npz"]
        path = self.stage / "PLAN.json"; path.chmod(0o600); self.write(path, a.encoded(self.plan)); self.plan_pin = a.pin(path.read_bytes())
        with self.assertRaisesRegex(ValueError, "Only two"): self.run_case(True)
        self.assertEqual(self.events, [])

    def test_wrong_exposure_refused(self):
        value = json.loads(self.exposure.read_text()); value["image"] = "sha256:" + "d" * 64
        self.write(self.exposure, a.encoded(value)); self.config["exposure_pin"] = a.pin(self.exposure.read_bytes())
        with self.assertRaisesRegex(ValueError, "approved image"): self.run_case(True)
        self.assertEqual(self.events, [])

    def test_no_retry_of_consumed_stage(self):
        self.submission = b"invalid"; self.run_case(True)
        with self.assertRaises(FileExistsError): self.run_case(True, output="second")

    def test_worker_preserves_two_candidate_threads_and_envelope(self):
        worker = module("neural019_worker_control", HERE / "worker.py")
        sandbox = self.root / "worker"; sandbox.mkdir(); (sandbox / "output").mkdir()
        self.write(sandbox / "request.json", a.encoded({"phase_id": "generated-worker"}))
        self.write(sandbox / "output/predictions.npz", self.submission)
        def mapped(path): return sandbox / str(path).lstrip("/")
        with patch.object(worker, "Path", mapped), patch.object(worker.subprocess, "run", return_value=types.SimpleNamespace(returncode=0)) as child:
            self.assertEqual(worker.main(), 0)
        self.assertEqual(child.call_args.args[0][-4:], ["--input", "/input", "--out", "/output"])
        for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
            self.assertEqual(child.call_args.kwargs["env"][key], "2")
            self.assertEqual(self.modules["provider"].fixed_environment(False)[key], "1")
        manifest = json.loads((sandbox / "output/OUTPUTS.json").read_text())
        self.assertEqual(set(manifest["files"]), {"predictions.npz", "RESULT.json"})
        self.assertEqual(manifest["files"]["predictions.npz"], a.pin(self.submission))

    def test_stage_preserves_real_input_pins_without_reading_them(self):
        self.assertEqual(sum(next(iter(self.plan["mounts"]["/input/" + name]["files"].values()))["bytes"]
            for name in ("public.npz", "public_manifest.json")), 59349239)
        self.assertFalse((self.public_root / "public_manifest.json").exists())
        proposal = json.loads((self.stage / "EXPOSURE_REQUEST.json").read_text())
        self.assertNotIn("role_boundary_verified", proposal)

    def test_worker_rejects_candidate_extra_before_adding_envelope(self):
        worker = module("neural019_worker_extra_control", HERE / "worker.py")
        sandbox = self.root / "worker-extra"; sandbox.mkdir(); (sandbox / "output").mkdir()
        self.write(sandbox / "request.json", a.encoded({"phase_id": "generated-worker-extra"}))
        self.write(sandbox / "output/predictions.npz", self.submission)
        self.write(sandbox / "output/unpermitted.txt", b"extra")
        with patch.object(worker, "Path", lambda p: sandbox / str(p).lstrip("/")), patch.object(worker.subprocess, "run", return_value=types.SimpleNamespace(returncode=0)):
            self.assertEqual(worker.main(), 3)
        self.assertFalse((sandbox / "output/RESULT.json").exists())
        self.assertFalse((sandbox / "output/OUTPUTS.json").exists())

    @classmethod
    def tearDownClass(cls):
        print(json.dumps({"python_version": sys.version, "numpy_version": np.__version__,
            "generated_fixture_payload_bytes_written": cls.fixture_payload_bytes_written,
            "counter_scope": "Test write() calls only, excluding operator stage/receipt metadata and worker envelope writes",
            "authentic_payload_reads": 0, "native_or_docker_runs": 0, "candidate_host_executions": 0, "model_calls": 0}))


if __name__ == "__main__":
    unittest.main(verbosity=2)
