"""Bounded generated engineering controls, not empirical reproduction."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
from scipy.io import savemat

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import evaluator as e


def voltage_trial(i=0, duration=20):
    n = duration * 20000
    baseline = np.tile(np.repeat([-65.5, -60.5, -55.5, -50.5], 5000), duration)
    rng = np.random.default_rng(128 + i)
    pos = 300 + i * 7
    while pos < n - 150:
        baseline[pos] = 10
        pos += int(rng.integers(450, 850))
    return e.Trial(f"trial-{i}", "mouse-A", "mouse-A_1", "PV", "Spont", 20000, baseline)


class CoreTests(unittest.TestCase):
    def test_native_source_is_exact_pin(self):
        self.assertEqual(e.digest(ROOT / "third_party/neuron_stat.py"), e.SOURCE_SHA256)

    def test_native_analytic_poisson_count_fixture(self):
        # Four trials with paired small-bin counts (0,0),(0,2),(2,0),(2,2).
        # small mean/variance=1; large mean=2, variance=2; root=1.
        result = e.dsr([[], [.002, .003], [0, .001], [0, .001, .002, .003]], .004, 2)
        self.assertEqual(result["phi"], 1)

    def test_native_independent_quadratic_fixture(self):
        # Small counts4/8 and8/4 across4 trials => root12-sqrt113.
        a = list(np.arange(4) / 1000) + list(np.arange(8, 16) / 1000)
        b = list(np.arange(8) / 1000) + list(np.arange(8, 12) / 1000)
        result = e.dsr([a, a, b, b], .016, 8)
        self.assertAlmostEqual(result["phi"], 12 - np.sqrt(113), places=13)

    def test_native_low_phi_path_matches_direct_pinned_function(self):
        rng = np.random.default_rng(92)
        raster = (rng.random((8, 1000)) < .04).astype(int)
        times = [np.flatnonzero(row) / 1000 for row in raster]
        result = e.dsr(times, 1, 50)
        direct = e.neuron_stats(raster, waiting_time_cut=1000, binsize=50, shift=50)
        if np.isfinite(direct):
            self.assertAlmostEqual(result["phi"], float(direct), places=14)
        else:
            self.assertIsNone(result["phi"])

    def test_dsr_collision_missing_and_invalid_inputs_refused(self):
        for spikes, duration in [([[.001, .0015], [.002]], .1), ([[.1], [.2]], .1),
                                 ([[np.nan], [.02]], .1), ([[], []], 1), ([[.01]], 1)]:
            with self.assertRaises(e.ContractError):
                e.dsr(spikes, duration)

    def test_cv2_independent_rational_values(self):
        self.assertAlmostEqual(e.cv2([1, 2, 3]), 1 / 6)
        self.assertAlmostEqual(e.cv2([.5, .25, 1]), 2 / 7)
        self.assertEqual(e.cv2([3, 3, 3]), 0)
        for x in ([1], [0, 1], [1, float("nan")]):
            with self.assertRaises(e.ContractError):
                e.cv2(x)

    def test_operational_integral_known_piecewise_rate(self):
        # Rate2Hz for.5s,4Hz for.25s,1Hz for1s => unit operational gaps.
        rate = np.repeat([2, 4, 1], [2, 1, 4])
        actual = e.operational_isis(rate, [0, .5, .75, 1.75], .25)
        np.testing.assert_allclose(actual, [1, 1, 1], rtol=0, atol=1e-15)

    def test_fraction_not_clipped_and_rate_not_normalized(self):
        op = e.operational_isis([10, 20, 10], [0, .1, .3], .1)
        np.testing.assert_allclose(op, [1, 3])
        self.assertAlmostEqual(e.cv2(op) / e.cv2([.1, .2]), 2.25)
        self.assertEqual(op.mean(), 2)

    def test_zero_and_negative_operational_rate_refused(self):
        for rate in ([0, 0, 0], [-1, 1, 1], [1, np.nan, 1]):
            with self.assertRaises(e.ContractError):
                e.operational_isis(rate, [0, .1, .2], .1)

    def test_crossings_and_overlapping_interpolation(self):
        x = np.full(1000, -60.0)
        x[200:202] = 10
        x[250:252] = 5
        clean, spikes = e.remove_spikes(x)
        np.testing.assert_array_equal(spikes, [200, 250])
        np.testing.assert_allclose(clean, -60)
        np.testing.assert_array_equal(x[200:202], [10, 10])  # no mutation
        x[20] = 10
        with self.assertRaises(e.ContractError):
            e.remove_spikes(x)

    def test_voltage_bin_boundary_counts(self):
        clean = np.full(1000, -60.0)
        voltage, rate = e.binned_voltage_rate(clean, [0, 499, 500, 999], 25)
        np.testing.assert_array_equal(voltage, [-60, -60])
        np.testing.assert_array_equal(rate, [80, 80])
        with self.assertRaises(e.ContractError):
            e.binned_voltage_rate(clean[:-1], [], 25)

    def test_spline_is_train_only_and_records_support(self):
        train = [e.remove_spikes(voltage_trial(i).voltage_mv) for i in range(2)]
        curve, meta = e.fit_voltage_curve(train, 25)
        first = curve(np.array([-60, -55]))
        rate, diagnostics = e.predict_rate(curve, meta, np.array([-100., -55., 100.]))
        np.testing.assert_array_equal(first, curve(np.array([-60, -55])))
        self.assertEqual(diagnostics["support_clamped_samples"], 2)
        self.assertTrue(np.isfinite(rate).all())

    def test_mat_adapter_and_digest_refusal(self):
        voltage = np.empty(2, dtype=object)
        voltage[:] = [np.arange(10, dtype=float) - 70, np.arange(12, dtype=float) - 70]
        data = {"Trial_MembranePotential": voltage,
                "Trial_MembranePotential_SamplingRate": [20000, 20000],
                "Trial_Type": ["Spont", "Spont"], "Cell_Type": ["PV", "PV"],
                "Mouse_Name": ["A", "B"], "Cell_Counter": [1, 2]}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "generated.mat"
            savemat(path, {"data": data}, long_field_names=True)
            trials = e.load_pala(path, verify_source=False)
            self.assertEqual([t.cell_id for t in trials], ["A_1", "B_2"])
            np.testing.assert_array_equal(trials[1].voltage_mv, voltage[1])
            with self.assertRaises(e.ContractError):
                e.load_pala(path)
        data["Trial_MembranePotential"] = np.zeros((2, 20))
        with self.assertRaises(e.ContractError):
            e.decode_pala(data)

    def test_no_cross_trial_or_half_interval(self):
        curve = lambda x: np.ones_like(x) * 5
        metadata = {"voltage_support_mv": [-70, -40]}
        v = np.full(400000, -60.)
        spikes = np.array([1000, 2000, 4000, 201000, 202000, 204000])
        t1 = e.Trial("one", "m", "c", "PV", "Spont", 20000, v)
        t2 = e.Trial("two", "m", "c", "PV", "Spont", 20000, v)
        result = e.paired_metrics([(t1, (v, spikes)), (t2, (v, spikes))], curve, metadata)
        self.assertEqual(result["isi_count"], 10)  #5 per trial, never11 joined
        self.assertEqual(len(result["segments"]), 4)
        for segment in result["segments"]:
            self.assertAlmostEqual(segment["raw_cv2"], 1 / 9)


class PopulationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.trials = [voltage_trial(i) for i in range(10)]
        cls.plan = {"recipe": e.RECIPE, "cells": {"mouse-A_1": {
            "calibration_trial_ids": [f"trial-{i}" for i in range(3)],
            "assessment_trial_ids": [f"trial-{i}" for i in range(3, 10)]}}}

    def test_full_pipeline_two_sensitivities_and_nesting(self):
        report = e.evaluate(self.trials, self.plan)
        self.assertFalse(report["scientific_qualified"])
        self.assertFalse(report["count_matches_paper_8_neurons_5_mice"])
        self.assertEqual(report["eligible_neurons"], 1)
        cell = report["cells"][0]
        self.assertEqual(len(cell["aligned_window_dsr"]), 2)
        self.assertEqual([x["voltage_fit"]["bin_ms"] for x in cell["voltage_sensitivities"]], [25, 50])
        self.assertEqual(len(cell["voltage_sensitivities"][0]["segments"]), 14)
        self.assertEqual(report["mouse_summaries"][0]["cell_ids"], ["mouse-A_1"])
        json.dumps(report, allow_nan=False)

    def test_population_thresholds_and_trial_coverage(self):
        eligible, ledger = e.audit_population(self.trials[:9])
        self.assertFalse(eligible)
        self.assertIn("fewer_than_10_trials", ledger[0]["reasons"])
        quiet = [e.Trial(t.trial_id, t.mouse_id, t.cell_id, t.cell_type, t.trial_type,
                         t.sampling_hz, np.full(400000, -60.)) for t in self.trials]
        eligible, ledger = e.audit_population(quiet)
        self.assertFalse(eligible)
        self.assertIn("mean_rate_below_20_Hz", ledger[0]["reasons"])
        with self.assertRaises(e.ContractError):
            e.evaluate(quiet, {"recipe": e.RECIPE, "cells": {}})

    def test_overlap_omission_and_missing_cell_refused(self):
        for kind in ["overlap", "omission", "missing_cell"]:
            plan = json.loads(json.dumps(self.plan))
            split = plan["cells"]["mouse-A_1"]
            if kind == "overlap":
                split["assessment_trial_ids"].append("trial-0")
            elif kind == "omission":
                split["assessment_trial_ids"].pop()
            else:
                plan["cells"] = {}
            with self.assertRaises(e.ContractError):
                e.evaluate(self.trials, plan)

    def test_mixed_duration_does_not_silently_shrink_cohort(self):
        bad = self.trials + [voltage_trial(10, 1)]
        with self.assertRaisesRegex(e.ContractError, "cohort not reduced"):
            e.audit_population(bad)
        t = self.trials[0]
        empty_id = e.Trial("", t.mouse_id, t.cell_id, t.cell_type, t.trial_type, t.sampling_hz, t.voltage_mv)
        with self.assertRaises(e.ContractError):
            e.audit_population([empty_id])


if __name__ == "__main__":
    unittest.main()
