"""Generated participant-submission controls; no observations or fitted models."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


preflight = load("neural046_preflight_test", HERE / "preflight_submission.py")
prior = load("neural046_prior_test", HERE / "test_score.py")
WRITTEN = 0


def write(path, body):
    global WRITTEN
    path.write_bytes(body)
    WRITTEN += len(body)


class PreflightTests(unittest.TestCase):
    def test_public_only_complete_predictions_no_scoring_or_private_binding(self):
        public, submission, sensitivity, _, _ = prior.fixture()
        with patch.object(preflight.scorer, "score_joined", side_effect=AssertionError("graded")):
            report = preflight.validate_predictions(public, submission, sensitivity)
        self.assertEqual(report["query_cases"], 4)
        self.assertEqual(report["primary_models"], ["M0", "ME", "MEN", "MN"])
        self.assertEqual(report["sensitivity_models"], ["MEN_independently_tuned"])
        self.assertEqual(report["sensitivity_digest"], prior.scorer.digest(sensitivity))
        self.assertEqual(report["grading_target_loader_invocations"], 0)
        self.assertFalse(report["model_artifacts_authenticated"])
        self.assertFalse(report["producer_closure_verified"])
        self.assertFalse(report["private_case_binding_verified"])
        self.assertFalse(report["scientific_qualification"])
        self.assertNotIn("metrics", report)

    def test_opaque_ids_need_no_native_mapping(self):
        values = prior.fixture(opaque=True)
        report = preflight.validate_predictions(*values[:3])
        self.assertEqual(report["cell_id"], "F_X_opaque_ID")
        self.assertEqual(report["query_cases"], 4)

    def test_incomplete_primary_or_changed_public_binding_rejected(self):
        p, s, z, _, _ = prior.fixture()
        del s["predictions"]["MN"]["native-0"]
        with self.assertRaisesRegex(ValueError, "scalar_case_identity"):
            preflight.validate_predictions(p, s, z)
        p, s, z, _, _ = prior.fixture()
        p["query"].reverse()
        with self.assertRaisesRegex(ValueError, "input_digest"):
            preflight.validate_predictions(p, s, z)

    def test_missing_unknown_sensitivity_cases_and_slots_rejected(self):
        for mutation in ("missing", "extra_case", "extra_model", "absent_model"):
            p, s, z, _, _ = prior.fixture()
            if mutation == "missing":
                del z["MEN_independently_tuned"]["native-0"]
            elif mutation == "extra_case":
                z["MEN_independently_tuned"]["not-a-case"] = 0.
            elif mutation == "extra_model":
                z["extra"] = {}
            else:
                z.clear()
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                preflight.validate_predictions(p, s, z)

    def test_nonfinite_boolean_and_missing_sensitivity_values_rejected(self):
        for value in (True, None, float("inf"), float("nan")):
            p, s, z, _, _ = prior.fixture()
            z["MEN_independently_tuned"]["native-0"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                preflight.validate_predictions(p, s, z)

    def test_control_without_men_requires_empty_sensitivity(self):
        p, s, z, _, _ = prior.fixture(cell_id="F_X_neural_trained_nuisance_only")
        s["predictions"] = {"M0": s["predictions"]["M0"]}
        s["model_artifact_digests"] = {"M0": "0" * 64}
        with self.assertRaisesRegex(ValueError, "sensitivity_backfill"):
            preflight.validate_predictions(p, s, z)
        report = preflight.validate_predictions(p, s, {})
        self.assertEqual(report["primary_models"], ["M0"])
        self.assertEqual(report["sensitivity_models"], [])

    def test_wrong_task_is_not_accepted_as_scalar_submission(self):
        p, s, z, _, _ = prior.fixture()
        p["task"] = "NEURAL-045"
        with self.assertRaisesRegex(ValueError, "task"):
            preflight.validate_predictions(p, s, z)

    def test_three_file_cli_runs_without_operator_artifacts(self):
        p, s, z, _, _ = prior.fixture()
        with tempfile.TemporaryDirectory(prefix="neural046-preflight-") as directory:
            root = Path(directory).resolve()
            names = ("public", "submission", "sensitivity")
            for name, value in zip(names, (p, s, z)):
                write(root / (name + ".json"), preflight.adapter.encode(value))
            output = root / "preflight.json"
            command = [sys.executable, "-I", "-S", "-B", str(HERE / "preflight_submission.py")]
            for name in names:
                command += ["--" + name, str(root / (name + ".json"))]
            command += ["--report", str(output)]
            result = subprocess.run(command, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            global WRITTEN
            WRITTEN += output.stat().st_size
            report = json.loads(output.read_text())
            self.assertEqual(report["status"], "prediction_shape_and_coverage_valid")
            self.assertEqual(set(x.name for x in root.iterdir()),
                             {"public.json", "submission.json", "sensitivity.json", "preflight.json"})
            self.assertEqual(report, preflight.validate_predictions(p, s, z))

    def test_duplicate_json_and_existing_output_rejected(self):
        p, s, z, _, _ = prior.fixture()
        with tempfile.TemporaryDirectory(prefix="neural046-preflight-") as directory:
            root = Path(directory).resolve()
            inputs = [root / (name + ".json") for name in ("public", "submission", "sensitivity")]
            for path, value in zip(inputs, (p, s, z)):
                write(path, preflight.adapter.encode(value))
            output = root / "preflight.json"
            write(inputs[-1], b'{"duplicate":1,"duplicate":2}')
            with self.assertRaisesRegex(ValueError, "duplicate_json_member"):
                preflight.preflight_files(*inputs, output)
            self.assertFalse(output.exists())
            write(output, b"retain previous report\n")
            with self.assertRaisesRegex(ValueError, "report_exists"):
                preflight.preflight_files(*inputs, output)
            self.assertEqual(output.read_bytes(), b"retain previous report\n")


if __name__ == "__main__":
    try:
        unittest.main(verbosity=2)
    finally:
        print("GENERATED_ARTIFACT_BYTES_WRITTEN=" + str(WRITTEN))
