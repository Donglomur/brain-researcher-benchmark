"""Generated regressions for scale-invariant descriptive correlation."""
import importlib.util
import math
from pathlib import Path
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("find046_scale_evaluator", PACKAGE / "evaluator.py")
ev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ev)


class CorrelationScaleControls(unittest.TestCase):
    def test_positive_scale_does_not_create_zero_or_missing_correlation(self):
        for scale in (1e-200, 1e-100, 1.0, 1e100, 1e200):
            with self.subTest(scale=scale):
                x = [-scale, 0.0, scale]
                self.assertAlmostEqual(ev.pearson_complete_vectors(x, x), 1.0)
                self.assertAlmostEqual(ev.pearson_complete_vectors(x, list(reversed(x))), -1.0)

    def test_extreme_finite_differences_and_independent_units(self):
        self.assertAlmostEqual(ev.pearson_complete_vectors([-1e308, 0.0, 1e308],
                                                          [-1e-300, 0.0, 1e-300]), 1.0)
        self.assertAlmostEqual(ev.pearson_complete_vectors([1e200, 2e200, 3e200],
                                                          [1e-200, 3e-200, 2e-200]), 0.5)

    def test_missing_constant_and_short_vectors_remain_undefined(self):
        for x, y in (([1, None, 3], [1, 2, 3]), ([0, 0, 0], [1, 2, 3]),
                     ([1e200] * 3, [1, 2, 3]), ([1], [2])):
            with self.subTest(x=x, y=y):
                self.assertIsNone(ev.pearson_complete_vectors(x, y))
        with self.assertRaises(ev.ContractError):
            ev.pearson_complete_vectors([1, 2], [1])

    def test_evaluate_retains_finite_serum_correlation_across_units(self):
        rows, behavior, serum = [], [], []
        for day, amplitude in (("20240101", 1), ("20240102", 2), ("20240103", 3)):
            serum.append({"rat": "G127", "session_date": day,
                          "estradiol_conc": amplitude * 1e200})
            for block in (1, 2, 3):
                trace = [0.0] * 301
                if block == 2:
                    trace[101:111] = [float(amplitude)] * 10
                rows.append([1.0] + trace)
                behavior.append({"trial_id": str(block), "unique_day": day,
                                 "block": block, "stage": "Proestrus", "prev_trial_type": 0})
        population = {"cpin": rows, "behavior": behavior}
        payload = {"schema_version": 1, "input_kind": "generated_engineering_control",
                   "figure2_ratlist": ["G127"], "figure2_serum_ratlist": ["G127"],
                   "figure2": {"G127": population}, "figure2_serum": {"G127": population},
                   "serum_table": serum,
                   "figure3_manifest": {"ratlist": list(ev.FIGURE3_RATS),
                                        "best_fits_supplied": True, "sessions": []}}
        report = ev.evaluate(payload)
        result = report["figure2i_serum_contrasts"]
        self.assertEqual(result["n_joined_source_included_sessions"], 3)
        self.assertEqual(len(result["source_shaped_arrays"]["delta_good"]), 3)
        self.assertTrue(math.isfinite(result["pearson_r"]))
        self.assertAlmostEqual(result["pearson_r"], 1.0)
        self.assertFalse(report["research_qualified"])
        self.assertFalse(report["binary_reward_registered"])


if __name__ == "__main__":
    unittest.main()
