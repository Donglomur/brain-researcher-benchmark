"""Generated arithmetic controls; no participant data or source model is loaded."""

import hashlib
import importlib
import json
import math
from pathlib import Path
import sys
import unittest

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "benchmarks/neural/NEURAL-070/implementations/registered-runtime"
CLOSURE = ROOT / "benchmarks/integrity/current-closures/numeric-neural070/SOURCE.json"


def load_metrics():
    names = lambda name: name == "n070" or name.startswith("n070.")
    saved = {name: module for name, module in sys.modules.items() if names(name)}
    old_path = list(sys.path)
    try:
        for name in saved:
            del sys.modules[name]
        sys.path.insert(0, str(PACKAGE / "programme"))
        return importlib.import_module("n070.metrics")
    finally:
        sys.path[:] = old_path
        for name in list(sys.modules):
            if names(name):
                del sys.modules[name]
        sys.modules.update(saved)


class FiniteCoordinateScores(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.metrics = load_metrics()

    def test_ordinary_exact_and_negative_scores_remain_unclipped(self):
        target = np.array([[0.0, 0.0], [1.0, 2.0], [2.0, 4.0]])
        prediction = target + np.array([1.0, 4.0])
        result = self.metrics.coordinate_scores(target, prediction)
        self.assertEqual(result["status"], "defined")
        # Independent SSE/SST calculation: [3/2, 48/8].
        np.testing.assert_array_equal(result["r2"], [-0.5, -5.0])
        np.testing.assert_array_equal(
            self.metrics.coordinate_scores(target, target)["r2"], [1.0, 1.0])

    def test_finite_prediction_square_overflow_is_not_a_defined_score(self):
        target = np.array([[0.0], [1.0], [2.0]])
        result = self.metrics.coordinate_scores(target, np.full_like(target, 1e308))
        self.assertEqual(result, {"status": "undefined_arithmetic_range", "r2": None})

    def test_finite_target_mean_overflow_is_not_perfect_performance(self):
        target = np.array([[1.2e308], [1.3e308], [1.4e308]])
        result = self.metrics.coordinate_scores(target, target)
        self.assertEqual(result, {"status": "undefined_arithmetic_range", "r2": None})

    def test_nonconstant_underflow_is_not_called_constant(self):
        target = np.array([[0.0], [1e-200], [2e-200]])
        result = self.metrics.coordinate_scores(target, target)
        self.assertEqual(result, {"status": "undefined_arithmetic_range", "r2": None})

    def test_constant_and_nonfinite_inputs_retain_specific_dispositions(self):
        target = np.ones((3, 1))
        self.assertEqual(self.metrics.coordinate_scores(target, target)["status"],
                         "undefined_constant_target_coordinate")
        for bad in (math.nan, math.inf, -math.inf):
            self.assertEqual(self.metrics.coordinate_scores(
                target, np.full_like(target, bad))["status"], "undefined_nonfinite")

    def test_integer_arrays_are_promoted_before_arithmetic(self):
        target = np.array([[0], [2**32], [2**33]], dtype=np.int64)
        result = self.metrics.coordinate_scores(target, np.zeros_like(target))
        self.assertEqual(result["status"], "defined")
        np.testing.assert_array_equal(result["r2"], [-1.5])

    def test_large_integer_precision_loss_cannot_produce_a_false_perfect_score(self):
        target = np.array([[2**53], [2**53 + 1], [2**53 + 2]], dtype=np.int64)
        prediction = target.copy()
        prediction[1, 0] -= 1
        result = self.metrics.coordinate_scores(target, prediction)
        self.assertEqual(result, {"status": "undefined_arithmetic_range", "r2": None})

    def test_mean_handles_maximum_finite_and_subnormal_values(self):
        maximum = sys.float_info.max
        tiny = math.ulp(0.0)
        self.assertEqual(self.metrics._mean([-maximum] * 3), -maximum)
        self.assertEqual(self.metrics._mean([tiny] * 10), tiny)
        with self.assertRaisesRegex(ValueError, "Representable arithmetic mean"):
            self.metrics._mean([tiny] + [0.0] * 10)

    def test_actual_extreme_coordinate_scores_survive_cell_aggregation(self):
        target = np.repeat(np.array([[0.0], [0.0], [1.0]]), 3, axis=1)
        denominator = ((target - target.mean(0)) ** 2).sum(0)[0]
        q = math.sqrt(sys.float_info.max * denominator / 3)
        prediction = np.full_like(target, q)
        result = self.metrics.cell(target,
            {name: prediction for name in self.metrics.MODELS},
            {name: target for name in self.metrics.REFERENCE_MODELS})
        self.assertEqual(result["status"], "defined")
        self.assertEqual(result["primary"], -sys.float_info.max)
        json.dumps(result, allow_nan=False)

    @unittest.skipUnless(np.dtype(np.longdouble).itemsize > 8,
                         "This platform has no floating dtype wider than binary64")
    def test_wider_floating_inputs_cannot_be_silently_rounded(self):
        target = np.array([[0], [1], [2]], dtype=np.longdouble)
        result = self.metrics.coordinate_scores(target, target)
        self.assertEqual(result, {"status": "undefined_arithmetic_range", "r2": None})

    def test_empty_or_nonreal_arrays_are_rejected(self):
        for target in (np.empty((0, 1)), np.empty((1, 0)),
                       np.array([[1j], [2j]]), np.ones((2, 1), dtype=bool)):
            with self.assertRaises(ValueError):
                self.metrics.coordinate_scores(target, target)

    def test_bad_candidate_and_bad_fixed_reference_prevent_complete_aggregate(self):
        target = np.array([[0.0], [1.0], [2.0]])
        for where in ("candidate", "reference"):
            candidates = {name: target.copy() for name in self.metrics.MODELS}
            references = {name: target.copy() for name in self.metrics.REFERENCE_MODELS}
            if where == "candidate":
                candidates[self.metrics.PRIMARY][:] = 1e308
            else:
                references[self.metrics.REFERENCE_MODELS[0]][:] = 1e308
            failed = self.metrics.cell(target, candidates, references)
            self.assertEqual(failed["status"], "undefined")
            self.assertIsNone(failed["primary"])
            good = self.metrics.cell(target,
                {name: target for name in self.metrics.MODELS},
                {name: target for name in self.metrics.REFERENCE_MODELS})
            cells = {(p, r): good for p in self.metrics.PARTICIPANTS for r in self.metrics.ROIS}
            cells[self.metrics.PARTICIPANTS[0], self.metrics.ROIS[0]] = failed
            report = self.metrics.complete_report(cells)
            self.assertEqual(report["aggregate_status"], "unavailable_full_denominator")
            self.assertIsNone(report["aggregate"])
            self.assertEqual(len(report["dispositions"]), 1)
            json.dumps(report, allow_nan=False)

    def test_finite_extreme_means_do_not_overflow_a_full_panel(self):
        target = np.array([[0.0], [1.0], [2.0]])
        cell = self.metrics.cell(target,
            {name: target for name in self.metrics.MODELS},
            {name: target for name in self.metrics.REFERENCE_MODELS})
        cell["primary"] = -1e308
        cells = {(p, r): cell for p in self.metrics.PARTICIPANTS for r in self.metrics.ROIS}
        report = self.metrics.complete_report(cells)
        self.assertEqual(report["aggregate_status"], "defined")
        self.assertEqual(report["aggregate"], -1e308)
        json.dumps(report, allow_nan=False)

    def test_reviewed_closure_and_predecessor_pins(self):
        manifest = json.loads(CLOSURE.read_text())
        for row in manifest["historical_descriptors"] + manifest["arithmetic_source_files"] + [manifest["regression_test"]]:
            body = (ROOT / row["path"]).read_bytes()
            self.assertEqual(len(body), row["bytes"], row["path"])
            self.assertEqual(hashlib.sha256(body).hexdigest(), row["sha256"], row["path"])
        original = json.loads((PACKAGE / "SOURCE_MANIFEST.json").read_text())
        previous = next(row for row in original["files"] if row["path"] == "programme/n070/metrics.py")
        current = next(row for row in manifest["arithmetic_source_files"] if row["path"].endswith("/metrics.py"))
        self.assertEqual(current["predecessor"]["sha256"], previous["sha256"])
        self.assertFalse(manifest["runtime_scientific_qualification"])


if __name__ == "__main__":
    unittest.main()
