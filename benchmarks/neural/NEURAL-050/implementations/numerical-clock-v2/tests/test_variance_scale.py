"""Generated controls for target-variance units; no AJILE12 inputs or AI runs."""
import importlib.util
from pathlib import Path
import unittest


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


e = load(Path(__file__).resolve().parents[1] / "evaluator.py", "neural050_variance")


def packet(scale=1.0):
    rows, pins = [], []
    for person in range(3):
        for day in range(2):
            patient, date, session = f"p{person}", f"2020-01-{day+1:02}", f"s{day}"
            pins.append({"patient": patient, "day": date, "session": session, "sha256": "0"*64})
            for i in range(12):
                start = float(day * 86400 + i * 4)
                gamma = float(i % 4)
                rows.append({"id": f"{patient}/{date}/{i}", "patient": patient, "day": date,
                             "session": session, "start_utc_s": start, "stop_utc_s": start + 2,
                             "local_seconds": 3600.0 + i*4, "state": "Eat", "gamma": gamma,
                             "movement": scale*(2 + 3*gamma)})
    return {"schema": "neural050-features-v1", "data_scope": "public_development_only",
            "protocol": e.PROTOCOL, "rows": rows, "source_pins": pins,
            "input_kind": "generated_engineering_control", "raw_manifest_sha256": "0"*64,
            "source_dataset": {"dandiset": "000055", "version": "0.220127.0436"}}


class VarianceScaleTests(unittest.TestCase):
    def test_small_nonconstant_targets_keep_normalized_increment(self):
        scale = 2.0**-30
        rows = [{"id": str(i), "patient": "p", "day": "d", "movement": i*scale}
                for i in range(3)]
        result = e.score_predictions(rows, {str(i): scale for i in range(3)},
                                     {str(i): i*scale for i in range(3)})[0]
        self.assertFalse(result["constant_target"])
        self.assertAlmostEqual(result["delta_r2"], 1.0)
        self.assertAlmostEqual(result["delta_mse"]/(scale*scale), 2/3)

    def test_complete_evaluator_retains_all_scaled_day_increments(self):
        ordinary = e.evaluate(packet())
        for scale in (2.0**-30, 1e-200):
            with self.subTest(movement_scale=scale):
                small = e.evaluate(packet(scale))
                self.assertEqual(len(small["day_metrics"]), 6)
                self.assertEqual(len(small["fold_audit"]), 3)
                for reference, scaled in zip(ordinary["day_metrics"], small["day_metrics"], strict=True):
                    self.assertIsNotNone(scaled["delta_r2"])
                    self.assertFalse(scaled["constant_target"])
                    self.assertAlmostEqual(scaled["delta_r2"], reference["delta_r2"], places=12)
                self.assertEqual(small["incremental_delta_r2"]["n_days_defined"], 6)
                self.assertEqual(small["scientific_qualification"], "unknown")

    def test_true_constant_targets_remain_undefined(self):
        rows = [{"id": str(i), "patient": "p", "day": "d", "movement": 2.0**-30}
                for i in range(4)]
        predictions = {str(i): 2.0**-30 for i in range(4)}
        result = e.score_predictions(rows, predictions, predictions)[0]
        self.assertTrue(result["constant_target"])
        self.assertIsNone(result["delta_r2"])
        self.assertEqual(result["baseline_mse"], 0.0)
        self.assertEqual(result["gamma_mse"], 0.0)

    def test_underflow_variance_retains_finite_normalized_increment(self):
        rows = [{"id": str(i), "patient": "p", "day": "d", "movement": i*1e-200}
                for i in range(3)]
        baseline = {str(i): 1e-200 for i in range(3)}
        augmented = {str(i): i*1e-200 for i in range(3)}
        result = e.score_predictions(rows, baseline, augmented)[0]
        self.assertFalse(result["constant_target"])
        self.assertEqual(result["baseline_mse"], 0.0)
        self.assertEqual(result["gamma_mse"], 0.0)
        self.assertEqual(result["delta_r2"], 1.0)

    def test_underflow_variance_equal_predictions_keep_zero_increment(self):
        rows = [{"id": str(i), "patient": "p", "day": "d", "movement": i*1e-200}
                for i in range(3)]
        predictions = {str(i): 1e-200 for i in range(3)}
        result = e.score_predictions(rows, predictions, predictions)[0]
        self.assertFalse(result["constant_target"])
        self.assertEqual(result["delta_r2"], 0.0)

    def test_overflow_variance_with_perfect_predictions_keeps_zero_increment(self):
        rows = [{"id": str(i), "patient": "p", "day": "d", "movement": i*1e200}
                for i in range(3)]
        predictions = {str(i): i*1e200 for i in range(3)}
        with e.np.errstate(over="ignore", invalid="ignore"):
            result = e.score_predictions(rows, predictions, predictions)[0]
        self.assertFalse(result["constant_target"])
        self.assertEqual(result["delta_r2"], 0.0)
        self.assertEqual(result["baseline_mse"], 0.0)

    def test_nonrepresentable_final_mse_is_refused(self):
        rows = [{"id": str(i), "patient": "p", "day": "d", "movement": i*1e200}
                for i in range(3)]
        baseline = {str(i): 1e200 for i in range(3)}
        augmented = {str(i): i*1e200 for i in range(3)}
        with e.np.errstate(over="ignore", invalid="ignore"):
            with self.assertRaisesRegex(ValueError, "baseline MSE is not representable"):
                e.score_predictions(rows, baseline, augmented)

    def test_ordinary_scale_preserves_independent_metric_values(self):
        rows = [{"id": str(i), "patient": "p", "day": "d", "movement": float(i)}
                for i in range(3)]
        result = e.score_predictions(rows, {str(i): 1.0 for i in range(3)},
                                     {str(i): float(i) for i in range(3)})[0]
        self.assertEqual(result["baseline_mse"], 2/3)
        self.assertEqual(result["gamma_mse"], 0.0)
        self.assertEqual(result["delta_mse"], 2/3)
        self.assertEqual(result["delta_r2"], 1.0)
        self.assertFalse(result["constant_target"])


if __name__ == "__main__":
    unittest.main()
