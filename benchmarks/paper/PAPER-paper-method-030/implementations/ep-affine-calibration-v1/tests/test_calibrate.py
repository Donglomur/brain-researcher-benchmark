"""Generated algebra and admission controls; no authentic signals or fitting run."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("cellmincer_affine_component", ROOT / "calibrate.py")
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


def signal():
    return [-2.0, -1.0, 0.0, 1.0, 2.0] * 1000


def panel():
    catalogue = json.loads(c.POPULATION.read_text())
    x = signal()
    ep = [3 * v + 5 for v in x]
    methods = ["raw", "cellmincer", "support", "pmd", "n2s", "candidate"]
    return {
        "schema_version": 1, "task_id": c.TASK_ID, "population_sha256": c.POPULATION_SHA256,
        "reference_access": "grader_only", "optical_units": "fluorescence_arbitrary_units",
        "ep_units": "mV", "sampling_rate_hz": 500, "methods": methods,
        "fit_policy": "shared_explicit_indices_per_recording",
        "support_status": "operator_frozen_historical_equivalence_unresolved",
        "preparation_evidence_sha256": "a" * 64,
        "recordings": [
            {"recording_id": r["recording_id"], "cell_id": r["cell_id"],
             "alignment_evidence_sha256": "b" * 64,
             "fit_support_evidence_sha256": "c" * 64,
             "fit_sample_indices": list(range(c.N_FRAMES)), "ep_mv": ep,
             "optical_au": {method: x for method in methods}}
            for r in catalogue["recordings"]],
    }


class AffineAlgebra(unittest.TestCase):
    def test_known_gain_offset_and_all_frames(self):
        x = signal()
        y = [3 * v + 5 for v in x]
        out = c.affine_l2(y, x, list(range(c.N_FRAMES)))
        self.assertAlmostEqual(out["gain_mv_per_au"], 3)
        self.assertAlmostEqual(out["offset_mv"], 5)
        self.assertLess(out["fit_rmse_mv"], 1e-13)
        self.assertEqual(len(out["calibrated_mv"]), c.N_FRAMES)
        for observed, expected in zip(out["calibrated_mv"], y):
            self.assertAlmostEqual(observed, expected)

    def test_unselected_ep_cannot_change_fit(self):
        x = signal()
        y = [2 * v - 4 for v in x]
        indices = list(range(2500))
        before = c.affine_l2(y, x, indices)
        y[4000] = 1e200
        after = c.affine_l2(y, x, indices)
        self.assertEqual(before, after)
        self.assertEqual(after["fit_sample_count"], 2500)

    def test_unconstrained_negative_gain_is_not_silently_flipped_or_clipped(self):
        x = signal()
        out = c.affine_l2([-2 * v + 1 for v in x], x, list(range(c.N_FRAMES)))
        self.assertAlmostEqual(out["gain_mv_per_au"], -2)
        self.assertAlmostEqual(out["offset_mv"], 1)

    def test_zero_ep_and_tiny_optical_do_not_overflow_intermediate_ratio(self):
        x = [v * 1e-309 for v in signal()]
        out = c.affine_l2([0.0] * c.N_FRAMES, x, list(range(c.N_FRAMES)))
        self.assertEqual(out["gain_mv_per_au"], 0)
        self.assertEqual(out["offset_mv"], 0)
        self.assertEqual(out["fit_rmse_mv"], 0)

    def test_rescaling_preserves_fitted_voltage(self):
        x = signal()
        y = [3 * v + 5 for v in x]
        ordinary = c.affine_l2(y, x, list(range(c.N_FRAMES)))
        large = c.affine_l2(y, [v * 1e200 for v in x], list(range(c.N_FRAMES)))
        self.assertAlmostEqual(large["gain_mv_per_au"] / 1e-200, 3)
        for a, b in zip(ordinary["calibrated_mv"], large["calibrated_mv"]):
            self.assertAlmostEqual(a, b)

    def test_constant_fit_does_not_scale_unselected_extreme_optical_samples(self):
        x = [v * 1e-309 for v in signal()]
        x[-1] = 1e308
        out = c.affine_l2([5.0] * c.N_FRAMES, x, list(range(2500)))
        self.assertEqual(out["gain_mv_per_au"], 0)
        self.assertEqual(out["calibrated_mv"], [5.0] * c.N_FRAMES)

    def test_non_identifiable_support_and_unrepresentable_slope_fail(self):
        for x, y in [([1.0] * c.N_FRAMES, signal()),
                     ([v * 1e-309 for v in signal()], signal()),
                     ([v * 1e200 for v in signal()], [v * 1e-200 for v in signal()])]:
            with self.subTest(first=x[0]), self.assertRaises(c.CalibrationError):
                c.affine_l2(y, x, list(range(c.N_FRAMES)))

    def test_support_requires_ordered_distinct_native_indices(self):
        for support in [[], [0], [0, 0], [1, 0], [False, 1], [-1, 1], [0, 5000], [0.0, 1]]:
            with self.subTest(support=support), self.assertRaises(c.CalibrationError):
                c.affine_l2(signal(), signal(), support)

    def test_bad_samples_and_shortcuts_fail(self):
        for values in [signal()[:-1], [True] * c.N_FRAMES,
                       [math.nan] + signal()[1:], [math.inf] + signal()[1:],
                       ["1"] * c.N_FRAMES, [10 ** 1000] * c.N_FRAMES]:
            with self.subTest(kind=type(values[0]).__name__), self.assertRaises(c.CalibrationError):
                c.affine_l2(signal(), values, list(range(c.N_FRAMES)))


class CompletePanel(unittest.TestCase):
    def test_full_saved_panel_no_scientific_promotion(self):
        p = panel()
        before = copy.deepcopy(p)
        out = c.calibrate_panel(p)
        self.assertEqual(p, before)
        self.assertEqual(len(out["recordings"]), 22)
        self.assertEqual(len({r["cell_id"] for r in out["recordings"]}), 9)
        self.assertEqual(out["reference_access"], "grader_only")
        self.assertEqual(out["scientific_qualification"], "unknown")
        self.assertFalse(out["reproduction_verified"])
        self.assertFalse(out["improvement_verified"])
        self.assertTrue(out["electrical_reference_used_in_calibration"])
        self.assertNotEqual(out["alignment_policy"], "externally_frozen_no_test_ep_fit")
        for row in out["recordings"]:
            self.assertEqual(set(row["methods"]), set(p["methods"]))
            self.assertEqual(len({m["fit_indices_sha256"] for m in row["methods"].values()}), 1)
            self.assertTrue(all(len(m["calibrated_mv"]) == 5000 for m in row["methods"].values()))

    def test_population_and_method_omission_rejected(self):
        mutations = [lambda p: p["recordings"].pop(),
                     lambda p: p["recordings"].__setitem__(-1, p["recordings"][0]),
                     lambda p: p["methods"].remove("support"),
                     lambda p: p["recordings"][0]["optical_au"].pop("candidate"),
                     lambda p: p.__setitem__("population_sha256", "0" * 64)]
        for mutate in mutations:
            p = panel(); mutate(p)
            with self.assertRaises(c.CalibrationError):
                c.calibrate_panel(p)

    def test_method_specific_support_and_unbound_alignment_rejected(self):
        p = panel(); p["recordings"][0]["candidate_fit_indices"] = [0, 1]
        with self.assertRaisesRegex(c.CalibrationError, "method-specific"):
            c.calibrate_panel(p)
        p = panel(); p["recordings"][0]["alignment_evidence_sha256"] = None
        with self.assertRaisesRegex(c.CalibrationError, "evidence"):
            c.calibrate_panel(p)

    def test_units_access_and_historical_claim_cannot_be_relabelled(self):
        for key, value in [("ep_units", "V"), ("sampling_rate_hz", 50000),
                           ("reference_access", "participant"),
                           ("support_status", "historically_verified"),
                           ("fit_policy", "optimize_each_method")]:
            p = panel(); p[key] = value
            with self.subTest(key=key), self.assertRaises(c.CalibrationError):
                c.calibrate_panel(p)


if __name__ == "__main__":
    unittest.main(verbosity=2)
