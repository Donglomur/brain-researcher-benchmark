"""Focused portable-adapter controls; invented summaries, no posterior fitting."""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("_cardiac_portable_grade", HERE / "grade.py")
grade = importlib.util.module_from_spec(spec)
spec.loader.exec_module(grade)


def fixture(core):
    return {"schema_version": 1, "input_sha256": grade.INPUT_SHA256,
            "target": "salzburg_bambi091_six_student_t_targets",
            "models": {model: {
                "summary": {variable: {
                    "mean": 3.0, "sd_population": 2.0,
                    "hdi_94_low": 0.5, "hdi_94_high": 5.0,
                    "mcse_mean_batch": None
                } for variable in core.VARIABLES},
                "diagnostics": dict.fromkeys(("chains", "draws_per_chain", "tune_per_chain",
                                             "divergences", "max_rhat", "min_ess_bulk", "min_ess_tail"))
            } for model in core.MODELS}}


class PortableGradeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.core = grade.load_core()
        self.reference = self.root / "reference.json"
        self.submission = self.root / "candidate.json"
        self.target = fixture(self.core)
        self.reference.write_text(json.dumps(self.target))
        self.submission.write_text(json.dumps(self.target))
        body = self.reference.read_bytes()
        self.pin = {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}

    def tearDown(self):
        self.temp.cleanup()

    def evaluate(self):
        return grade.evaluate(self.core, self.submission, self.reference, self.pin)

    def args(self, output):
        return ["--submission", str(self.submission), "--reference", str(self.reference),
                "--reference-bytes", str(self.pin["bytes"]),
                "--reference-sha256", self.pin["sha256"], "--output", str(output)]

    def assert_no_reference_read(self):
        original = self.core.read_json
        def guarded(path, *args, **kwargs):
            self.assertNotEqual(Path(path), self.reference)
            return original(path, *args, **kwargs)
        with mock.patch.object(self.core, "read_json", guarded):
            result, status = self.evaluate()
        self.assertEqual(status, 2)
        self.assertEqual(result["status"], "invalid_submission")
        self.assertEqual(result["private_numeric_reference_loads"], 0)
        self.assertIsNone(result["metrics"])

    def test_complete_six_model_forwarding(self):
        candidate = copy.deepcopy(self.target)
        for model in self.core.MODELS:
            candidate["models"][model]["summary"]["beta"]["mean"] += 3
        self.submission.write_text(json.dumps(candidate))
        result, status = self.evaluate()
        self.assertEqual(status, 0)
        self.assertEqual(set(result["metrics"]["models"]), set(self.core.MODELS))
        self.assertAlmostEqual(result["metrics"]["primary_beta_mean_rmse_reference_sd"], 1.5)
        self.assertIsNone(result["scientific_success"])

    def test_missing_model_rejected_before_reference(self):
        self.target["models"].pop(self.core.MODELS[-1])
        self.submission.write_text(json.dumps(self.target))
        self.assert_no_reference_read()

    def test_wrong_original_input_rejected_before_reference(self):
        self.target["input_sha256"] = "0" * 64
        self.submission.write_text(json.dumps(self.target))
        self.assert_no_reference_read()

    def test_duplicate_field_rejected_before_reference(self):
        self.submission.write_text('{"schema_version":1,' + self.submission.read_text()[1:])
        self.assert_no_reference_read()

    def test_fifo_candidate_refuses_before_reader_dispatch(self):
        self.submission.unlink()
        os.mkfifo(self.submission)
        with mock.patch.object(self.core, "read_json", side_effect=AssertionError("reader must not open FIFO")):
            result, status = self.evaluate()
        self.assertEqual(status, 2)
        self.assertEqual(result["status"], "invalid_submission")
        self.assertEqual(result["private_numeric_reference_loads"], 0)

    def test_fifo_reference_is_operator_failure_before_reader_dispatch(self):
        self.reference.unlink()
        os.mkfifo(self.reference)
        original = self.core.read_json
        seen = []
        def guarded(path, *args, **kwargs):
            self.assertNotEqual(Path(path), self.reference)
            seen.append(Path(path))
            return original(path, *args, **kwargs)
        with mock.patch.object(self.core, "read_json", side_effect=guarded):
            with self.assertRaisesRegex(ValueError, "ordinary single-link JSON operand"):
                self.evaluate()
        self.assertEqual(seen, [self.submission])

    def test_reference_pin_mismatch_is_operator_failure(self):
        self.pin["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "private reference pin mismatch"):
            self.evaluate()

    def test_reference_wrong_input_is_operator_failure(self):
        self.target["input_sha256"] = "0" * 64
        self.reference.write_text(json.dumps(self.target))
        b = self.reference.read_bytes()
        self.pin = {"bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()}
        with self.assertRaisesRegex(ValueError, "reference must bind"):
            self.evaluate()

    def test_finite_unsupported_arithmetic_is_not_scored(self):
        candidate = copy.deepcopy(self.target)
        model = self.core.MODELS[0]
        candidate["models"][model]["summary"]["beta"]["mean"] = 1e308
        self.target["models"][model]["summary"]["beta"]["mean"] = -1e308
        self.reference.write_text(json.dumps(self.target))
        self.submission.write_text(json.dumps(candidate))
        b = self.reference.read_bytes()
        self.pin = {"bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()}
        result, status = self.evaluate()
        self.assertEqual(status, 2)
        self.assertEqual(result["status"], "unsupported_derived_numerics")
        self.assertIsNone(result["metrics"]["primary_beta_mean_rmse_reference_sd"])

    def test_actual_cli_path_writes_complete_private_grade_once(self):
        output = self.root / "grade.json"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(grade.main(self.args(output)), 0)
        result = json.loads(output.read_bytes())
        self.assertEqual(result["metrics"]["primary_beta_mean_rmse_reference_sd"], 0)
        self.assertEqual(result["benchmark_id"], "PAPER-ROOT-ADD-016")
        self.assertEqual(result["new_benchmark_ids"], 0)
        self.assertFalse(result["candidate_program_executed"])
        prior = output.read_bytes()
        with mock.patch.object(grade, "load_core", side_effect=AssertionError("must refuse first")):
            with self.assertRaises(FileExistsError):
                grade.main(self.args(output))
        self.assertEqual(output.read_bytes(), prior)

    def test_final_symlink_refuses_without_victim_creation(self):
        output, victim = self.root / "link.json", self.root / "victim.json"
        output.symlink_to(victim)
        with self.assertRaisesRegex(ValueError, "aliases"):
            grade.main(self.args(output))
        self.assertTrue(output.is_symlink())
        self.assertFalse(victim.exists())

    def test_relocated_bundle_authenticates_adjacent_helper(self):
        bundle = self.root / "bundle"
        bundle.mkdir()
        for name in ("grade.py", "summary_score.py"):
            shutil.copyfile(HERE / name, bundle / name)
        s = importlib.util.spec_from_file_location("_relocated_cardiac_grade", bundle / "grade.py")
        relocated = importlib.util.module_from_spec(s)
        s.loader.exec_module(relocated)
        self.assertEqual(relocated.load_core().MODELS, self.core.MODELS)
        helper = bundle / "summary_score.py"
        b = helper.read_bytes()
        helper.write_bytes(b.replace(b"import argparse", b"import argparsE", 1))
        with self.assertRaisesRegex(ValueError, "exact accepted helper"):
            relocated.load_core()


class PrivateWriterTests(unittest.TestCase):
    def test_report_is_owner_only_under_umask_zero_without_scoring(self):
        # Exercise the real CLI writer while stubbing both numerical entrypoints.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve(); root.chmod(0o755)
            output = root / "private-grade.json"
            args = ["--submission", str(root / "not-read-candidate.json"),
                    "--reference", str(root / "not-read-reference.json"),
                    "--reference-bytes", "1", "--reference-sha256", "a" * 64,
                    "--output", str(output)]
            previous_umask = os.umask(0)
            try:
                with mock.patch.object(grade, "load_core", return_value=object()) as loader, \
                     mock.patch.object(grade, "evaluate", return_value=({"status": "generated_writer_only"}, 0)) as evaluator, \
                     contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(grade.main(args), 0)
                loader.assert_called_once(); evaluator.assert_called_once()
                self.observed_mode = format(output.stat().st_mode & 0o777, "04o")
                self.assertEqual(self.observed_mode, "0600")
                self.assertFalse((root / "not-read-candidate.json").exists())
                self.assertFalse((root / "not-read-reference.json").exists())
                # A file appearing after the early existence check is preserved.
                output.unlink()
                def race(*unused):
                    output.write_bytes(b"generated intervening owner file")
                    return {"status": "generated_writer_only"}, 0
                with mock.patch.object(grade, "load_core", return_value=object()), \
                     mock.patch.object(grade, "evaluate", side_effect=race), \
                     contextlib.redirect_stdout(io.StringIO()):
                    with self.assertRaises(FileExistsError):
                        grade.main(args)
                self.assertEqual(output.read_bytes(), b"generated intervening owner file")
            finally:
                os.umask(previous_umask)


if __name__ == "__main__":
    unittest.main(verbosity=2)
