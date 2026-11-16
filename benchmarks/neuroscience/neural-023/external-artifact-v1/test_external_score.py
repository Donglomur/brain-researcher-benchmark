"""Generated relocation/interface checks; no provider asset bodies are read."""
from pathlib import Path
import contextlib
import hashlib
import importlib.util
import io
import json
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np

HERE = Path(__file__).resolve().parent


class RelocationChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = Path(tempfile.mkdtemp(prefix="neural023-relocated-")).resolve()
        cls.delivery = cls.temp / "arbitrary-source-location"
        cls.delivery.mkdir()
        shutil.copyfile(HERE / "external_score.py", cls.delivery / "external_score.py")
        shutil.copytree(HERE / "dependencies", cls.delivery / "dependencies")
        spec = importlib.util.spec_from_file_location("relocated_neural023", cls.delivery / "external_score.py")
        cls.a = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.a)
        cls.sources = cls.delivery / "dependencies"
        cls.modules = cls.a.load_modules(cls.sources)
        cls.ids = np.arange(3010, 25101, dtype="<u4")
        n = np.arange(22091)
        cls.truth = np.column_stack((n % 7 / 10, n % 11 / 20)).astype("<f8")
        cls.assets = cls.temp / "separate-operator-assets"
        cls.assets.mkdir()
        cls.target = cls.assets / "target.npz"
        np.savez(cls.target, case_id=cls.ids, velocity_m_s=cls.truth)
        m = cls.modules["score_core"].score(cls.truth, {"x": np.zeros_like(cls.truth)})["metrics"]["x"]
        names = ("zero_velocity", "source_mean_velocity", "calibration_mean_velocity", "source_only_ridge",
                 "source_only_ridge_plus_calibration_mean_residual", "calibration_only_ridge", "balanced_pooled_ridge")
        cls.reference = cls.assets / "reference.json"
        cls.reference.write_text(json.dumps({"candidate_id": "NEURAL-023", "status": "fixed_reference_scored_and_independently_audited",
                                            "result": {"primary_metric": "mean_axis_r2", "metrics": {k: m for k in names}}}))
        cls.target_pin = cls.pin(cls.target)
        cls.reference_pin = cls.pin(cls.reference)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp)

    @staticmethod
    def pin(path):
        b = path.read_bytes()
        return {"bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()}

    def candidate(self, valid=True, complete=True):
        p = self.temp / (self.id().split(".")[-1] + ".npz")
        if not valid:
            p.write_bytes(b"invalid")
        else:
            stop = 22091 if complete else 22090
            np.savez(p, case_id=self.ids[:stop], velocity_m_s=self.truth[:stop])
        return p

    def run_fixture(self, candidate, target=None, reference=None):
        out = self.temp / (self.id().split(".")[-1] + "-output")
        with patch.object(self.a, "TARGET", self.target_pin), patch.object(self.a, "REFERENCE", self.reference_pin):
            receipt = self.a.run(self.sources, candidate, out,
                                 target=target or self.target, reference=reference or self.reference)
        score = json.loads((out / "score.json").read_text()) if (out / "score.json").exists() else None
        return receipt, score

    def test_relocated_full_support(self):
        receipt, score = self.run_fixture(self.candidate())
        self.assertEqual(receipt["status"], "scored_development_candidate")
        self.assertEqual(score["submission_rows"], 22091)
        self.assertEqual(score["primary_score"], 1)
        self.assertEqual(len(score["fixed_clock_blocks"]), 8)
        self.assertEqual(len(score["signed_reference_comparisons"]), 7)

    def test_malformed_before_missing_operator_paths(self):
        receipt, score = self.run_fixture(self.candidate(False),
                                          self.temp / "missing" / "target", self.temp / "missing" / "reference")
        self.assertEqual(receipt["status"], "invalid_submission")
        self.assertEqual(score["private_target_loads"], 0)

    def test_incomplete_before_missing_operator_paths(self):
        receipt, score = self.run_fixture(self.candidate(complete=False),
                                          self.temp / "missing" / "target", self.temp / "missing" / "reference")
        self.assertEqual(receipt["status"], "invalid_submission")
        self.assertEqual(score["private_target_loads"], 0)

    def test_wrong_reference_identity(self):
        other = self.assets / "different-reference.json"
        other.write_text("{}")
        receipt, score = self.run_fixture(self.candidate(), reference=other)
        self.assertEqual(receipt["status"], "operator_error")
        self.assertIsNone(score)

    def test_wrong_target_identity(self):
        other = self.assets / "different-target.npz"
        other.write_bytes(b"wrong")
        receipt, score = self.run_fixture(self.candidate(), target=other)
        self.assertEqual(receipt["status"], "operator_error")
        self.assertIsNone(score)

    def test_missing_dependency_no_fallback(self):
        p = self.sources / "bundle.py"
        held = p.with_name("bundle-held.py")
        p.rename(held)
        try:
            with self.assertRaises(FileNotFoundError):
                self.a.load_modules(self.sources)
        finally:
            held.rename(p)

    def test_changed_dependency_refused(self):
        p = self.sources / "score_core.py"
        original = p.read_bytes()
        p.write_bytes(original + b"\n")
        try:
            with self.assertRaisesRegex(ValueError, "Pinned input mismatch"):
                self.a.load_modules(self.sources)
        finally:
            p.write_bytes(original)

    def test_cli_explicit_paths_and_tighter_cpu(self):
        import resource
        import signal
        out = self.temp / "cli-output"
        candidate = self.candidate()
        argv = [str(self.delivery / "external_score.py"), "--source-root", str(self.sources),
                "--submission", str(candidate), "--target", str(self.target),
                "--reference", str(self.reference), "--output", str(out)]
        captured = io.StringIO()
        with patch.object(self.a, "TARGET", self.target_pin), patch.object(self.a, "REFERENCE", self.reference_pin), patch.object(sys, "argv", argv), patch.object(resource, "getrlimit", return_value=(5, resource.RLIM_INFINITY)), patch.object(resource, "setrlimit") as limit, patch.object(signal, "getitimer", return_value=(0.0, 0.0)), patch.object(signal, "signal"), patch.object(signal, "setitimer") as timer, contextlib.redirect_stdout(captured):
            rc = self.a.main()
        self.assertEqual(rc, 0)
        limit.assert_called_once_with(resource.RLIMIT_CPU, (5, resource.RLIM_INFINITY))
        self.assertEqual(timer.call_args.args, (signal.ITIMER_REAL, 0))
        self.assertEqual(json.loads(captured.getvalue())["status"], "scored_development_candidate")
        self.assertEqual(json.loads((out / "score.json").read_text())["submission_rows"], 22091)


if __name__ == "__main__":
    unittest.main(verbosity=2)
