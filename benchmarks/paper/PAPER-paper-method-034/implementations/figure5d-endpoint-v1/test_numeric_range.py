"""Generated complete-support range controls; no data, decoder or model run."""
import importlib.util
import math
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("range_panel", HERE / "panel.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def support():
    return {"schema": "marble_figure5d_support_v1", "task_id": m.endpoint.TASK_ID,
            "panel": "Figure 5d", "animal": "rat1", "unit": "m",
            "source_sha256": "a" * 64,
            "training_row_ids": ["fit/" + str(i) for i in range(36)],
            "query_row_ids": ["query/" + str(i) for i in range(2000)]}


def summarize(predictions):
    s = support()
    return m.endpoint.error_summary(s, predictions,
            {"row_ids": s["query_row_ids"], "position_m": [0.0] * 2000})


class NumericalRangeControls(unittest.TestCase):
    def test_finite_mean_survives_total_overflow(self):
        result = summarize([1e308] * 2000)
        self.assertEqual(result["mean_absolute_error_m"], 1e308)
        self.assertEqual(result["absolute_error_sd_population_m"], 0.0)
        self.assertEqual(result["absolute_error_sd_sample_m"], 0.0)

    def test_varying_tiny_errors_do_not_become_zero_deviation(self):
        result = summarize([0.0] * 1000 + [2e-200] * 1000)
        self.assertEqual(result["mean_absolute_error_m"], 1e-200)
        self.assertAlmostEqual(result["absolute_error_sd_population_m"] / 1e-200, 1.0)
        self.assertAlmostEqual(result["absolute_error_sd_sample_m"] / 1e-200,
                               math.sqrt(2000 / 1999))

    def test_large_varying_errors_keep_finite_deviation_and_panel_mean(self):
        s = support()
        predictions = {"cebra-time": [0.0] * 2000,
                       "cebra-behaviour": [0.0] * 2000,
                       "marble": [0.0] * 1000 + [1e308] * 1000}
        result = m.summarize_panel(s, predictions,
                 {"row_ids": s["query_row_ids"], "position_m": [0.0] * 2000})
        score = result["method_scores"]["marble"]
        self.assertEqual(score["mean_absolute_error_m"], 5e307)
        self.assertEqual(score["absolute_error_sd_population_m"], 5e307)
        pair = result["paired_descriptive_comparisons"]["marble_minus_cebra-time"]
        self.assertEqual(pair["mean_absolute_error_difference_m"], 5e307)
        self.assertEqual(pair["paired_rows"], 2000)
        self.assertIsNone(result["scientific_improvement_awarded"])

    def test_normal_last_row_closed_form_is_unchanged(self):
        result = summarize([0.0] * 1999 + [2000.0])
        self.assertEqual(result, {"samples": 2000, "mean_absolute_error_m": 1.0,
            "absolute_error_sd_population_m": math.sqrt(1999),
            "absolute_error_sd_sample_m": math.sqrt(2000)})


if __name__ == "__main__":
    unittest.main(verbosity=2)
