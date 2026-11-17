"""Bounded analytical engineering controls; never native scientific evidence."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("cellmincer_evaluator", ROOT / "evaluator.py")
e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)


def fixture():
    catalogue = e.load_catalogue()
    cells = sorted({r["cell_id"] for r in catalogue["recordings"]})
    panel = {
        "task_id": e.TASK_ID,
        "population_sha256": hashlib.sha256((ROOT / "population.json").read_bytes()).hexdigest(),
        "recordings": [{"recording_id": r["recording_id"], "cell_id": r["cell_id"],
                        "split": "test" if r["cell_id"] == cells[0] else "validation" if r["cell_id"] == cells[1] else "train"}
                       for r in catalogue["recordings"]],
        "methods": ["cellmincer", "n2s"],
        "alignment_policy": "externally_frozen_no_test_ep_fit",
        "spectral_policy": {"ep_power_ceiling_mv2": 5.0},
    }
    time = np.arange(5000) / 500
    ep = 0.8 * np.sin(time * 2 * np.pi * 3)
    ep[[100, 1000, 2000, 4000]] += 25
    raw = ep + 0.2 * np.sin(time * 2 * np.pi * 150)
    ids = [r["recording_id"] for r in panel["recordings"] if r["split"] == "test"]
    ref = {"reference_access": "grader_only", "units": "mV", "sampling_rate_hz": 500,
           "recordings": {rid: {"alignment_source": "frozen_external_calibration", "alignment_sha256": "a" * 64,
                                "ep_mv": ep.tolist(), "raw_mv": raw.tolist()} for rid in ids}}
    sub = {"units": "mV", "sampling_rate_hz": 500,
           "method_access": {m: {"electrical_targets_accessed": False, "fit_cell_ids": cells[2:]} for m in panel["methods"]},
           "recordings": {rid: {"cellmincer": ep.tolist(), "n2s": raw.tolist()} for rid in ids}}
    return panel, ref, sub


class Equations(unittest.TestCase):
    def test_published_existential_matching_is_not_one_to_one(self):
        score = e.fuzzy_events([0], [-0.001, 0.001])
        self.assertEqual((score["precision"], score["recall"], score["f1"]), (1, 1, 1))
        self.assertEqual(score["matched_predicted_count"], 2)

    def test_strict_two_millisecond_boundary(self):
        for origin in [0, 0.1, 9.0]:
            self.assertEqual(e.fuzzy_events([origin], [origin + 0.002])["f1"], 0)
            self.assertEqual(e.fuzzy_events([origin], [origin + 0.0019])["f1"], 1)

    def test_hand_computed_precision_recall(self):
        x = e.fuzzy_events([0.1, 0.2], [0.1001, 0.3, 0.4])
        self.assertAlmostEqual(x["precision"], 1 / 3)
        self.assertAlmostEqual(x["recall"], 1 / 2)
        self.assertAlmostEqual(x["f1"], 0.4)
        self.assertEqual(x["false_event_count"], 2)

    def test_empty_events_do_not_score_perfect(self):
        self.assertIsNone(e.fuzzy_events([], [])["f1"])
        self.assertEqual(e.fuzzy_events([0], [])["f1"], 0)
        self.assertEqual(e.fuzzy_events([], [0])["f1"], 0)

    def test_bad_event_order_rejected(self):
        with self.assertRaises(e.ContractError): e.fuzzy_events([0, 0], [0])
        with self.assertRaises(e.ContractError): e.fuzzy_events([1, 0], [0])
        with self.assertRaises(e.ContractError): e.fuzzy_events([0], [np.nan])

    def test_f1_star_optimum_is_inside_interval(self):
        # p=.9--1.1: nuisance prominence .95 must be removed, true1.05 retained.
        # Endpoints .8 and1.2 yield 2/3 and0; interior yields1.
        score = e.prominence_f1_star(([0.1], [1.0]), ([0.1, 0.3], [1.05, 0.95]), 1.0)
        self.assertEqual(score["f1_star"], 1)
        self.assertEqual(score["best_counts"]["predicted_count"], 1)
        self.assertEqual(score["threshold_states_evaluated"], 4)

    def test_extreme_correlation_is_stable(self):
        self.assertAlmostEqual(e.pearson([1e308, -1e308], [1e308, -1e308]), 1)
        self.assertEqual(e.fuzzy_events([0], [0], 1e-13)["f1"], 1)

    def test_prominence_plateau_policy(self):
        times, prom = e.peaks([0, 2, 2, 0, 0, 3, 0])
        np.testing.assert_allclose(times, [1 / 500, 5 / 500])
        np.testing.assert_allclose(prom, [2, 3])

    def test_correlation_and_lag_sign(self):
        x = np.zeros(100); x[[10, 40, 70]] = [1, 2, 1]
        y = np.roll(x, 2)
        out = e.lagged_correlations(x, y)
        self.assertAlmostEqual(max(out["pearson_r"]), 1)
        self.assertEqual(out["lags_seconds"][np.argmax(out["pearson_r"])], 2 / 500)
        self.assertIsNone(e.pearson(np.ones(5), np.ones(5)))

    def test_spectral_amplitude_halving_is_six_db(self):
        n = np.arange(512)
        ep = np.zeros(512)
        residual = np.sin(2 * np.pi * n * 10 / 64)
        out = e.residual_spectrum(ep, residual, residual / 2, 1.0)
        self.assertAlmostEqual(out["noise_reduction_db"][10], 20 * np.log10(2), places=10)
        self.assertEqual(out["eligible_windows"], 29)

    def test_no_spectral_windows_is_explicit(self):
        x = np.ones(128) * 100
        out = e.residual_spectrum(x, x, x, 0.01)
        self.assertEqual(out["status"], "undefined_no_eligible_windows")
        self.assertNotIn("noise_reduction_db", out)

    def test_identity_spectrum_no_gain(self):
        x = np.arange(128) * 0.001
        out = e.residual_spectrum(x, x + 1, x + 1, 1.0)
        np.testing.assert_allclose(out["noise_reduction_db"], 0)

    def test_boxcar_edges_and_spike_attenuation(self):
        np.testing.assert_allclose(e.boxcar_control([0, 3, 0]), [1, 1, 1])
        np.testing.assert_allclose(e.boxcar_control([3, 0, 0]), [2, 1, 0])


class PanelAndGrading(unittest.TestCase):
    def test_frozen_population_complete(self):
        x = e.load_catalogue()
        self.assertEqual(x["recording_count"], 22)
        self.assertEqual(x["cell_count"], 9)
        self.assertEqual(len({r["recording_id"] for r in x["recordings"]}), 22)
        for r in x["recordings"]:
            self.assertEqual(Path(r["raw_tiff"]["name"]).stem, Path(r["private_abf"]["name"]).stem)
            self.assertIn("/raw/", r["raw_tiff"]["name"])

    def test_end_to_end_generated_control(self):
        panel, ref, sub = fixture()
        out = e.evaluate(panel, ref, sub)
        self.assertEqual(out["scientific_qualification"], "unknown")
        self.assertFalse(out["native_reference_verified"])
        self.assertEqual((out["population_recordings"], out["test_recordings"], out["test_cells"]), (22, 2, 1))
        self.assertAlmostEqual(out["aggregate"]["cellmincer"]["cell_macro_zero_lag_r"]["mean"], 1)
        self.assertEqual(out["per_recording"][0]["methods"]["cellmincer"]["rmse_mv"], 0)
        json.dumps(out, allow_nan=False)

    def test_no_cell_cross_split(self):
        panel, _, _ = fixture()
        panel["recordings"][0]["split"] = "train"
        with self.assertRaisesRegex(e.ContractError, "cell leakage"): e.validate_panel(panel)

    def test_missing_recording_rejected(self):
        panel, ref, sub = fixture()
        del sub["recordings"][next(iter(sub["recordings"]))]
        with self.assertRaisesRegex(e.ContractError, "coverage"): e.evaluate(panel, ref, sub)

    def test_missing_baseline_rejected(self):
        panel, _, _ = fixture(); panel["methods"] = ["cellmincer"]
        with self.assertRaisesRegex(e.ContractError, "matched"): e.validate_panel(panel)

    def test_test_cell_fit_and_target_access_rejected(self):
        panel, ref, sub = fixture()
        sub["method_access"]["cellmincer"]["fit_cell_ids"] = [panel["recordings"][0]["cell_id"]]
        with self.assertRaisesRegex(e.ContractError, "train-only"): e.evaluate(panel, ref, sub)
        sub["method_access"]["cellmincer"]["fit_cell_ids"] = []
        sub["method_access"]["cellmincer"]["electrical_targets_accessed"] = True
        with self.assertRaisesRegex(e.ContractError, "forbidden"): e.evaluate(panel, ref, sub)

    def test_alignment_and_units_not_guessed(self):
        panel, ref, sub = fixture(); sub["units"] = "arbitrary"
        with self.assertRaisesRegex(e.ContractError, "aligned mV"): e.evaluate(panel, ref, sub)
        sub["units"] = "mV"; panel["alignment_policy"] = "fit_to_test_ep"
        with self.assertRaisesRegex(e.ContractError, "frozen alignment"): e.evaluate(panel, ref, sub)

    def test_nonfinite_or_truncated_arrays_rejected(self):
        panel, ref, sub = fixture(); rid = next(iter(sub["recordings"]))
        sub["recordings"][rid]["cellmincer"][0] = float("nan")
        with self.assertRaisesRegex(e.ContractError, "nonfinite"): e.evaluate(panel, ref, sub)
        sub["recordings"][rid]["cellmincer"] = [1, 2]
        with self.assertRaisesRegex(e.ContractError, "5000"): e.evaluate(panel, ref, sub)

    def test_subthreshold_false_events_separate_from_f1_star(self):
        ep = np.zeros(5000); vi = ep.copy(); vi[100] = 1
        out = e.trace_metrics(ep, ep, vi, {"ep_power_ceiling_mv2": 1})
        self.assertEqual(out["fixed_prominence_profiles"][0]["false_event_count"], 1)
        self.assertEqual(out["fixed_prominence_profiles"][0]["false_events_per_second"], 0.1)
        self.assertEqual(out["spike_threshold_20mv"]["false_event_count"], 0)

    def test_numeric_overflow_fails_closed(self):
        panel, ref, sub = fixture(); rid = next(iter(sub["recordings"]))
        sub["recordings"][rid]["cellmincer"] = [1e308, -1e308] * 2500
        with self.assertRaises(e.ContractError): e.evaluate(panel, ref, sub)

    def test_cell_aggregation_equal_weights(self):
        # Algebraic reducer reports missingness; no fabricated zero for constants.
        self.assertEqual(e._mean_available([0.5, None, 1.0]), {"mean": 0.75, "defined_count": 2, "total_count": 3})

    def test_unknown_spectral_policy_rejected(self):
        panel, _, _ = fixture()
        panel["spectral_policy"]["window"] = "boxcar"
        with self.assertRaisesRegex(e.ContractError, "unsupported spectral"): e.validate_panel(panel)

    def test_common_ep_support_and_constant_prediction_guard(self):
        panel, ref, sub = fixture()
        cells = sorted({r["cell_id"] for r in panel["recordings"]})
        template_ref = copy.deepcopy(next(iter(ref["recordings"].values())))
        template_pred = copy.deepcopy(next(iter(sub["recordings"].values())))
        # Add a second test cell with EP flat, but comparator false spikes.
        for r in panel["recordings"]:
            if r["cell_id"] == cells[2]:
                r["split"] = "test"
                rid = r["recording_id"]
                ref["recordings"][rid] = copy.deepcopy(template_ref)
                ref["recordings"][rid]["ep_mv"] = [0.0] * 5000
                sub["recordings"][rid] = copy.deepcopy(template_pred)
                sub["recordings"][rid]["cellmincer"] = [0.0] * 5000
        for access in sub["method_access"].values(): access["fit_cell_ids"] = cells[3:]
        out = e.evaluate(panel, ref, sub)
        for m in ["raw", "boxcar3", "cellmincer", "n2s"]:
            self.assertEqual(out["aggregate"][m]["cell_macro_f1_star"][0]["defined_count"], 1)
        self.assertGreater(out["aggregate"]["n2s"]["cell_macro_false_events_per_second_20mv"]["mean"], 0)
        self.assertEqual(out["aggregate"]["cellmincer"]["cell_macro_false_events_per_second_20mv"]["mean"], 0)
        # Make second-cell EP nonconstant but leave candidate constant.
        for rid in ref["recordings"]:
            if rid not in [r["recording_id"] for r in panel["recordings"] if r["cell_id"] == cells[0]]:
                ref["recordings"][rid]["ep_mv"] = template_ref["ep_mv"]
        out = e.evaluate(panel, ref, sub)
        self.assertIsNone(out["aggregate"]["cellmincer"]["cell_macro_zero_lag_r"]["mean"])
        self.assertEqual(out["aggregate"]["cellmincer"]["cell_macro_zero_lag_r"]["total_count"], 2)

    def test_cli_complete_path(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp); panel, ref, sub = fixture()
            for name, value in [("panel", panel), ("reference", ref), ("submission", sub)]:
                (path / f"{name}.json").write_text(json.dumps(value))
            cmd = [sys.executable, str(ROOT / "evaluator.py"), "--panel", str(path / "panel.json"),
                   "--private-reference", str(path / "reference.json"), "--submission", str(path / "submission.json"),
                   "--output", str(path / "result.json")]
            run = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads((path / "result.json").read_text())["test_recordings"], 2)


if __name__ == "__main__":
    unittest.main()
