"""Generated controls for the retained 42-field optogenetic scorer.

Uses public schema identities and invented numeric arrays only. No protected
reference, native runtime, candidate program, or central Decimal scorer runs.
"""

import hashlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import warnings

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "benchmarks/paper/PAPER-FIND-ADD-015/implementations/registered-runtime"
BINDINGS = ROOT / "benchmarks/integrity/current-closures/numeric-opto/SOURCE_BINDINGS.json"
CONTRAST = "multiopto_high_minus_low_delta_equal_experiment_rmse"
HI, LO, GROUP = "multiopto_hi__delta", "multiopto_lo__delta", "multiopto__experiment_id"
module_spec = importlib.util.spec_from_file_location("opto_numeric_control", RUNTIME / "numeric_score.py")
scorer = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(scorer)
SPEC = json.loads((RUNTIME / "submission_schema.json").read_text())["fields"]


def generated(dtype):
    return {
        key: np.array(field["values"], dtype=field["dtype"])
        if field["kind"] == "identity" else np.zeros(field["shape"], dtype=dtype)
        for key, field in SPEC.items()
    }


class OptoNumericControls(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="opto-numeric-control-")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.candidate_path = self.directory / "generated-candidate.npz"
        self.reference_path = self.directory / "generated-reference.npz"

    def score(self, candidate, reference):
        np.savez(self.candidate_path, **candidate)
        np.savez(self.reference_path, **reference)
        # The wrapper rejects stderr. Detect warnings as well as nonfinite JSON.
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            accepted, digest = scorer.read_submission(self.candidate_path, SPEC)
            result = scorer.score_validated(accepted, digest, self.reference_path, SPEC)
        self.assertEqual(result["status"], "scored")
        self.assertIs(result["submission_valid"], True)
        self.assertEqual(result["private_numeric_reference_loads"], 1)
        self.assertIsNone(result["scientific_success"])
        self.assertIsNone(result["reward_floor"])
        self.assertEqual(result["submission_sha256"], hashlib.sha256(self.candidate_path.read_bytes()).hexdigest())
        json.dumps(result, allow_nan=False)
        return result

    def test_zero_and_exact_reconstruction_for_all_permitted_dtypes(self):
        self.assertEqual(len(SPEC), 42)
        for dtype in (np.float32, np.float64, ">f4", ">f8"):
            for value in (0.0, 1.25):
                with self.subTest(dtype=dtype, value=value):
                    candidate = generated(dtype)
                    for key, field in SPEC.items():
                        if field["kind"] == "numeric":
                            candidate[key].fill(value)
                    result = self.score(candidate, candidate)
                    self.assertTrue(all(row["value"] == 0 for row in result["metrics"].values()))
                    self.assertTrue(all(row["rmse"] == row["mae"] == row["max_abs_error"] == 0
                                        for row in result["all_numeric_field_errors"].values()))

    def test_float32_extreme_contrast_candidate_reference_and_swaps(self):
        magnitude = float(np.float32(3e38))
        for candidate_dtype in (np.float32, np.float64):
            for reference_dtype in (np.float32, np.float64):
                for candidate_sign, reference_sign in ((1, 0), (0, 1), (-1, 0), (0, -1), (1, -1), (1, 1)):
                    with self.subTest(candidate_dtype=candidate_dtype, reference_dtype=reference_dtype,
                                      candidate_sign=candidate_sign, reference_sign=reference_sign):
                        candidate, reference = generated(candidate_dtype), generated(reference_dtype)
                        for arrays, sign in ((candidate, candidate_sign), (reference, reference_sign)):
                            arrays[HI].fill(sign * magnitude)
                            arrays[LO].fill(-sign * magnitude)
                        result = self.score(candidate, reference)
                        expected = abs(candidate_sign - reference_sign) * 2 * magnitude
                        self.assertTrue(math.isclose(result["metrics"][CONTRAST]["value"], expected, rel_tol=1e-14))

    def test_float64_near_bound_and_cross_float32_rounding(self):
        candidate, reference = generated(np.float64), generated(np.float64)
        below_bound = np.nextafter(np.float64(1e100), np.float64(0))
        candidate[HI].fill(below_bound)
        candidate[LO].fill(-below_bound)
        reference[HI].fill(-below_bound)
        reference[LO].fill(below_bound)
        result = self.score(candidate, reference)
        self.assertTrue(math.isclose(result["metrics"][CONTRAST]["value"], 4 * below_bound, rel_tol=1e-14))
        # Preserve float64 values that would be lost by narrowing operands first.
        candidate, reference = generated(np.float64), generated(np.float32)
        candidate[HI].fill(1 + 2**-30)
        candidate[LO].fill(1)
        reference[HI].fill(1)
        reference[LO].fill(1)
        result = self.score(candidate, reference)
        self.assertEqual(result["metrics"][CONTRAST]["value"], 2**-30)

    def test_ordinary_values_preserve_equal_experiment_weighting(self):
        candidate, reference = generated(np.float32), generated(np.float64)
        groups = np.unique(reference[GROUP])
        expected_errors = []
        for index, group in enumerate(groups):
            mask = reference[GROUP] == group
            error = index + 1
            candidate[HI][mask] = 8 + 3 * error
            candidate[LO][mask] = 4 + error
            reference[HI][mask] = 7
            reference[LO][mask] = 3
            expected_errors.append(2 * error)
        # Public identities have unequal cell counts; an overall cell mean is a
        # different scientific weighting and must not replace the group mean.
        self.assertGreater(len(set(np.count_nonzero(reference[GROUP] == group) for group in groups)), 1)
        result = self.score(candidate, reference)
        self.assertEqual(result["metrics"][CONTRAST]["value"], sum(expected_errors) / len(groups))
        per_experiment = result["metrics"]["multiopto_high_power_equal_experiment_delta_rmse"]["per_experiment"]
        self.assertEqual([row["rmse"] for row in per_experiment], [1 + 3 * (i + 1) for i in range(len(groups))])
        self.assertEqual(sum(row["n_cells"] for row in per_experiment), candidate[HI].size)
        self.assertEqual(result["primary_metric"], "fig2_equal_experiment_delta_rmse")
        self.assertEqual(set(result["metrics"]), {
            "fig2_equal_experiment_delta_rmse", "multiopto_high_power_equal_experiment_delta_rmse",
            "multiopto_low_power_equal_experiment_delta_rmse", CONTRAST,
            "multivis_cell_condition_delta_rmse", "fig4_normalized_integral_rmse",
        })
        self.assertEqual(set(result["all_numeric_field_errors"]),
                         {key for key, field in SPEC.items() if field["kind"] == "numeric"})

    def test_nonfinite_bound_and_unpermitted_numeric_types_are_rejected(self):
        for dtype, value in ((np.float32, np.nan), (np.float32, np.inf), (np.float64, -np.inf),
                             (np.float64, 1e100), (np.float64, -1e100), (np.float64, 1e101),
                             (np.float16, 1), (np.int64, 1), (np.complex128, 1), (object, 1)):
            with self.subTest(dtype=dtype, value=value):
                candidate = generated(np.float64)
                candidate[HI] = np.full(SPEC[HI]["shape"], value, dtype=dtype)
                np.savez(self.candidate_path, **candidate)
                with warnings.catch_warnings():
                    warnings.simplefilter("error")
                    with self.assertRaises(ValueError):
                        scorer.read_submission(self.candidate_path, SPEC)

    def test_schema_and_identity_rejections_precede_reference_access(self):
        cases = []
        candidate = generated(np.float32)
        del candidate[HI]
        cases.append(("missing", candidate))
        candidate = generated(np.float32)
        candidate["extra"] = np.zeros(1)
        cases.append(("extra", candidate))
        candidate = generated(np.float32)
        candidate[HI] = candidate[HI][:-1]
        cases.append(("shape", candidate))
        candidate = generated(np.float32)
        candidate[GROUP] = candidate[GROUP][::-1]
        self.assertFalse(np.array_equal(candidate[GROUP], generated(np.float32)[GROUP]))
        cases.append(("identity_order", candidate))
        candidate = generated(np.float32)
        candidate[HI].fill(np.nan)
        cases.append(("nonfinite", candidate))
        self.assertFalse(self.reference_path.exists())
        for label, candidate in cases:
            with self.subTest(case=label):
                np.savez(self.candidate_path, **candidate)
                output = self.directory / (label + ".json")
                process = subprocess.run([
                    sys.executable, "-B", str(RUNTIME / "numeric_score.py"),
                    "--submission", str(self.candidate_path), "--expected", str(self.reference_path),
                    "--spec", str(RUNTIME / "submission_schema.json"), "--output", str(output),
                ], capture_output=True, text=True, timeout=10)
                self.assertEqual(process.returncode, 2, process.stderr)
                self.assertEqual(process.stderr, "")
                result = json.loads(output.read_text())
                self.assertEqual(result["status"], "invalid_submission")
                self.assertIs(result["submission_valid"], False)
                self.assertIsNone(result["metrics"])
                self.assertEqual(result["private_numeric_reference_loads"], 0)
        self.assertFalse(self.reference_path.exists())

    def test_cli_extreme_float32_produces_finite_json_without_stderr(self):
        candidate, reference = generated(np.float32), generated(np.float64)
        candidate[HI].fill(3e38)
        candidate[LO].fill(-3e38)
        np.savez(self.candidate_path, **candidate)
        np.savez(self.reference_path, **reference)
        output = self.directory / "grade.json"
        process = subprocess.run([
            sys.executable, "-B", str(RUNTIME / "numeric_score.py"),
            "--submission", str(self.candidate_path), "--expected", str(self.reference_path),
            "--spec", str(RUNTIME / "submission_schema.json"), "--output", str(output),
        ], capture_output=True, text=True, timeout=10)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(process.stderr, "")
        result = json.loads(output.read_text(), parse_constant=lambda value: self.fail(value))
        self.assertTrue(math.isclose(result["metrics"][CONTRAST]["value"], 6.0000000109955115e38, rel_tol=1e-14))

    def test_current_bindings_and_historical_qualification_are_separate(self):
        descriptor = json.loads(BINDINGS.read_text())
        self.assertEqual(descriptor["task_id"], "PAPER-FIND-ADD-015")
        self.assertFalse(descriptor["historical_qualification_transferred"])
        self.assertFalse(descriptor["native_execution_qualified"])
        for group in ("current_files", "unchanged_contract_and_lineage"):
            for pin in descriptor[group]:
                with self.subTest(group=group, path=pin["path"]):
                    body = (ROOT / pin["path"]).read_bytes()
                    self.assertEqual(len(body), pin["bytes"])
                    self.assertEqual(hashlib.sha256(body).hexdigest(), pin["sha256"])
        historical = json.loads((RUNTIME / "execution_pins.json").read_text())
        predecessor = next(row for row in historical["files"] if row["path"].endswith("/numeric_score.py"))
        self.assertEqual(predecessor["bytes"], 6101)
        self.assertEqual(predecessor["sha256"], "354e6903e2ef6d2abe91b7ed2160d515fa1e3d42ac169b0e72212c8aafda6c9c")


if __name__ == "__main__":
    unittest.main(verbosity=2)
