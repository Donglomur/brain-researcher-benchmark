"""Generated numerical controls for the shared six-model cardiac scorer."""
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCORER = ROOT / "benchmarks/paper/PAPER-ROOT-ADD-016/implementations/six-model-summary/summary_score.py"
spec = importlib.util.spec_from_file_location("_numeric_cardiac", SCORER)
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)


def fixture():
    return {
        "schema_version": 1,
        "input_sha256": "a" * 64,
        "target": "salzburg_bambi091_six_student_t_targets",
        "models": {
            name: {
                "summary": {
                    variable: {
                        "mean": 1.0 if variable in ("sigma", "nu") else 0.0,
                        "sd_population": 1.0,
                        "hdi_94_low": 0.0,
                        "hdi_94_high": 2.0,
                        "mcse_mean_batch": None,
                    }
                    for variable in core.VARIABLES
                },
                "diagnostics": dict.fromkeys((
                    "chains", "draws_per_chain", "tune_per_chain", "divergences",
                    "max_rhat", "min_ess_bulk", "min_ess_tail",
                )),
            }
            for name in core.MODELS
        },
    }


class CardiacRmsNumerics(unittest.TestCase):
    def score_differences(self, differences):
        self.assertEqual(len(differences), 6)
        reference = fixture()
        candidate = copy.deepcopy(reference)
        for name, difference in zip(core.MODELS, differences):
            candidate["models"][name]["summary"]["beta"]["mean"] = difference
        core.validate(candidate)
        core.validate(reference)
        return core.score(candidate, reference)

    def test_nonzero_unrepresentable_rms_is_not_a_successful_zero(self):
        smallest = math.ulp(0.0)
        for position in range(6):
            for sign in (-1, 1):
                with self.subTest(model=core.MODELS[position], sign=sign):
                    differences = [0.0] * 6
                    differences[position] = sign * smallest
                    result = self.score_differences(differences)
                    self.assertEqual(result["status"], "unsupported_derived_numerics")
                    self.assertIsNone(result["primary_beta_mean_rmse_reference_sd"])
                    self.assertIsNone(result["scientific_pass"])
                    self.assertIs(result["schema_valid"], True)
                    self.assertEqual(result["error_type"], "OverflowError")
                    json.dumps(result, allow_nan=False)

    def test_exact_agreement_still_scores_zero(self):
        result = self.score_differences([0.0] * 6)
        self.assertEqual(result["status"], "valid_summary_continuously_scored")
        self.assertEqual(result["primary_beta_mean_rmse_reference_sd"], 0.0)
        self.assertEqual(set(result["models"]), set(core.MODELS))
        self.assertEqual(sum(len(row["parameters"]) for row in result["models"].values()), 30)

    def test_supported_subnormal_rms_remains_positive(self):
        for differences in ([math.ulp(0.0)] * 6, [8 * math.ulp(0.0)] + [0.0] * 5):
            with self.subTest(differences=differences):
                result = self.score_differences(differences)
                self.assertEqual(result["status"], "valid_summary_continuously_scored")
                self.assertGreater(result["primary_beta_mean_rmse_reference_sd"], 0.0)
                self.assertEqual(result["primary_beta_mean_rmse_reference_sd"],
                                 math.hypot(*differences) / math.sqrt(6))

    def test_ordinary_rms_keeps_every_model_in_the_population(self):
        for differences in ([1.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                            [1.0, -2.0, 3.0, -4.0, 5.0, -6.0],
                            [1e-150, -2e-150, 0.0, 0.0, 0.0, 0.0],
                            [1e150, -2e150, 0.0, 0.0, 0.0, 0.0]):
            with self.subTest(differences=differences):
                result = self.score_differences(differences)
                self.assertEqual(result["status"], "valid_summary_continuously_scored")
                self.assertEqual(result["primary_beta_mean_rmse_reference_sd"],
                                 math.hypot(*differences) / math.sqrt(6))
                for name, difference in zip(core.MODELS, differences):
                    model = result["models"][name]
                    self.assertEqual(model["parameters"]["beta"]["mean_difference_reference_sd"], difference)
                    if name.startswith("raw__"):
                        expected = math.hypot(*(age * difference for age in range(18, 74))) / math.sqrt(56)
                        self.assertEqual(model["location_mean_rmse_age18_through73_response_units"], expected)


class CardiacConsumerBindings(unittest.TestCase):
    def load(self, name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_current_source_closure_and_shared_execution_binding(self):
        descriptor = ROOT / "benchmarks/integrity/current-closures/numeric-cardiac/SOURCE_BINDINGS.json"
        closure = json.loads(descriptor.read_bytes())
        for row in closure["files"] + closure["preserved_manifests"]:
            body = (ROOT / row["path"]).read_bytes()
            self.assertEqual({"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()},
                             {key: row[key] for key in ("bytes", "sha256")}, row["path"])
        shared = json.loads((ROOT / closure["paired_execution_dependency_manifest"]).read_bytes())["files"]
        for row in closure["files"]:
            if row["path"] in closure["shared_execution_sources"]:
                self.assertEqual(shared[row["path"]], {key: row[key] for key in ("bytes", "sha256")})

    def test_portable_adapter_reports_valid_but_unsupported_arithmetic(self):
        grade = self.load("_numeric_cardiac_grade", SCORER.with_name("grade.py"))
        loaded = grade.load_core()
        target = fixture()
        target["input_sha256"] = grade.INPUT_SHA256
        candidate = copy.deepcopy(target)
        candidate["models"][loaded.MODELS[-1]]["summary"]["beta"]["mean"] = math.ulp(0.0)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            submission, reference = root / "candidate.json", root / "reference.json"
            submission.write_text(json.dumps(candidate))
            reference.write_text(json.dumps(target))
            body = reference.read_bytes()
            pin = {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
            result, status = grade.evaluate(loaded, submission, reference, pin)
        self.assertEqual(status, 2)
        self.assertEqual(result["status"], "unsupported_derived_numerics")
        self.assertIs(result["submission_valid"], True)
        self.assertEqual(result["private_numeric_reference_loads"], 1)
        self.assertIsNone(result["metrics"]["primary_beta_mean_rmse_reference_sd"])

    def test_current_packet_binds_repaired_scorer_without_rewriting_history(self):
        paired = self.load("_numeric_cardiac_paired", SCORER.parent.parent / "matched-artifacts/paired.py")
        historical = paired.HERE / "PACKET_SPEC.json"
        original = historical.read_bytes()
        old_spec = paired.decode(original)
        self.assertEqual(old_spec["scorer"], paired.PREDECESSOR_SCORER)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            operands = root / "operands"
            operands.mkdir()
            binding = root / "binding.json"
            binding.write_text(json.dumps({
                "schema": "cardiac_private_reference_binding_v1",
                "benchmark_id": "PAPER-ROOT-ADD-016",
                "input_sha256": old_spec["scope"]["input_sha256"],
                "reference": {"path": "never-opened.json", "bytes": 1, "sha256": "a" * 64},
            }))
            packet = paired.configured(operands, binding)
            self.assertEqual(packet.spec["scorer"], paired.CURRENT_SCORER)
            self.assertEqual(packet.receipt("1" * 32)["scorer"], paired.CURRENT_SCORER)
            self.assertEqual(paired.pin(packet.checked_read(packet.spec["scorer"])),
                             {key: paired.CURRENT_SCORER[key] for key in ("bytes", "sha256")})
            self.assertFalse((operands / "never-opened.json").exists())
            old_spec["scorer"]["sha256"] = "b" * 64
            with self.assertRaisesRegex(ValueError, "scorer binding"):
                paired.Packet(old_spec, ROOT, operands=operands)
        self.assertEqual(historical.read_bytes(), original)


if __name__ == "__main__":
    unittest.main(verbosity=2)
