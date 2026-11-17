"""Generated numerical controls. Never opens empirical responses or targets."""
import importlib.util
import json
import math
from pathlib import Path
import sys
import unittest

import numpy as np

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("temporal_dn_core_test", HERE / "model.py")
model = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = model
SPEC.loader.exec_module(model)


class NumericalCoreControls(unittest.TestCase):
    def parameters(self, mode="none"):
        p = model.parameter_spec(mode)[1]
        p[0] = 0
        return p

    def pulse(self, size=96):
        result = np.zeros(size)
        result[4:16] = 1
        return result

    def test_original_parameter_roster_and_bounds(self):
        names, initial, lower, upper = model.parameter_spec("none")
        self.assertEqual(names, ("shift", "scale", "tau", "n", "sigma", "tau_a"))
        np.testing.assert_array_equal(initial, [30, 1, .01, 1.5, .15, .07])
        np.testing.assert_array_equal(lower, [0, .01, .001, .1, 0, .01])
        np.testing.assert_array_equal(upper, [70, 200, 1, 5, 1, 2])
        for mode in ("S", "P"):
            n, p, lo, hi = model.parameter_spec(mode)
            self.assertEqual(n[6:], tuple("sf_" + x.lower() for x in model.CATEGORIES))
            np.testing.assert_array_equal(p[6:], np.ones(6))
            np.testing.assert_array_equal(lo[6:], np.full(6, .01))
            np.testing.assert_array_equal(hi[6:], np.full(6, 200))
        initial[:] = 0
        self.assertEqual(model.parameter_spec()[1][0], 30)

    def test_half_open_pulse_intervals_and_overlap(self):
        one = [[2, 5], [0, 1]]
        two = [[1, 4, 3, 6], [0, 1, 7, 8]]
        np.testing.assert_array_equal(model.stimulus_timecourse("onepulse", 0, one, two, 8), [0, 0, 1, 1, 1, 0, 0, 0])
        np.testing.assert_array_equal(model.stimulus_timecourse("twopulse_repeat", 0, one, two, 8), [0, 1, 1, 1, 1, 1, 0, 0])
        np.testing.assert_array_equal(model.stimulus_timecourse("twopulse_repeat", 1, one, two, 8), [1, 0, 0, 0, 0, 0, 0, 1])

    def test_prediction_matches_manual_discrete_convolutions(self):
        p = self.parameters()
        p[:] = [0, 1.7, .025, 1.2, .23, .09]
        stim = self.pulse(48)
        stim[20:24] = -.3
        times = [i / 512 for i in range(len(stim))]
        irf = [t / p[2] * math.exp(-t / p[2]) / p[2] for t in times]
        irf = [x / sum(irf) for x in irf]
        norm = [math.exp(-t / p[5]) for t in times]
        norm = [x / sum(norm) for x in norm]
        linear = [sum(stim[j] * irf[i-j] for j in range(i+1)) for i in range(len(stim))]
        pool = [sum(linear[j] * norm[i-j] for j in range(i+1)) for i in range(len(stim))]
        expected = [p[1] * abs(x)**p[3] / (p[4]**p[3] + abs(z)**p[3]) for x, z in zip(linear, pool)]
        np.testing.assert_allclose(model.predict(stim, p), expected, rtol=2e-14, atol=2e-14)

    def test_shift_truncates_to_samples_not_seconds(self):
        stim = self.pulse()
        a = self.parameters(); a[0] = 3.9
        b = a.copy(); b[0] = 3.
        c = b.copy(); c[0] = 4.
        np.testing.assert_array_equal(model.predict(stim, a), model.predict(stim, b))
        self.assertFalse(np.array_equal(model.predict(stim, b), model.predict(stim, c)))
        self.assertTrue(np.array_equal(model.predict(stim, b)[:7], np.zeros(7)))

    def test_response_scaling_is_exact_final_multiplier(self):
        stim = self.pulse(); p = self.parameters("P"); p[8] = 3.5
        expected = 3.5 * model.predict(stim, p[:6])
        np.testing.assert_allclose(model.predict(stim, p, scaling="P", category="FACES"), expected, rtol=0, atol=0)
        parts = model.predict(stim, p, scaling="P", category="FACES", components=True)
        plain = model.predict(stim, p[:6], components=True)
        np.testing.assert_array_equal(parts["drive"], plain["drive"])
        np.testing.assert_array_equal(parts["denominator"], plain["denominator"])

    def test_stimulus_scaling_is_not_response_scaling(self):
        stim = self.pulse(); p = self.parameters("S"); p[8] = 4.
        source_stim = np.zeros(len(stim)); source_stim[4:16] = 4.
        actual = model.predict(stim, p, scaling="S", category="FACES", pulse_windows=((4, 16),))
        np.testing.assert_array_equal(actual, model.predict(source_stim, p[:6]))
        alternate = model.predict(stim, p, scaling="P", category="FACES")
        self.assertGreater(float(np.max(np.abs(actual - alternate))), .1)

    def test_stimulus_scaling_discards_outside_windows_and_does_not_add_overlap(self):
        stim = np.ones(40); p = self.parameters("S"); p[6] = 2
        windows = ((2, 7), (5, 9))
        expected_stim = np.zeros(40); expected_stim[2:9] = 2
        actual = model.predict(stim, p, scaling="S", category="BODIES", pulse_windows=windows)
        np.testing.assert_array_equal(actual, model.predict(expected_stim, p[:6]))

    def test_normalization_uses_signed_linear_drive_before_absolute_power(self):
        stim = np.zeros(100); stim[3:20] = 1; stim[20:40] = -1
        p = self.parameters(); p[5] = .3
        parts = model.predict(stim, p, components=True)
        time = np.arange(len(stim)) / 512
        irf = np.exp(-time / p[5]); irf /= irf.sum()
        wrong = p[4]**p[3] + np.convolve(np.abs(parts["linear"]), irf)[:len(stim)]**p[3]
        self.assertGreater(float(np.max(np.abs(wrong-parts["denominator"]))), .01)

    def test_original819_shape_is_preserved(self):
        stim = self.pulse(819)
        out = model.predict(stim, self.parameters(), components=True)
        self.assertEqual(set(out), {"response", "drive", "numerator", "normalization_pool", "denominator", "linear", "semisaturation", "category_scale"})
        self.assertTrue(all(out[k].shape == (819,) and np.isfinite(out[k]).all() for k in ("response", "drive", "numerator", "normalization_pool", "denominator", "linear")))
        np.testing.assert_array_equal(out["drive"], out["numerator"])
        np.testing.assert_allclose(out["denominator"], out["semisaturation"] + np.abs(out["normalization_pool"])**self.parameters()[3])
        self.assertEqual(out["category_scale"], 1.)

    def test_inputs_and_global_error_mode_are_unchanged(self):
        stim = self.pulse(); parameters = self.parameters()
        before_s, before_p, errors = stim.copy(), parameters.copy(), np.geterr().copy()
        model.predict(stim, parameters)
        np.testing.assert_array_equal(stim, before_s)
        np.testing.assert_array_equal(parameters, before_p)
        self.assertEqual(np.geterr(), errors)

    def test_scalar_objective_is_sum_not_mean_or_residual_vector(self):
        x = np.stack([self.pulse(48), self.pulse(48)])
        p = self.parameters(); prediction = model.predict(x[0], p)
        y = np.stack([prediction + 2, prediction - 3])
        score = model.objective(p, x, y)
        self.assertIsInstance(score, float)
        self.assertAlmostEqual(score, 48 * (4 + 9))

    def test_per_row_categories_and_windows_are_used(self):
        x = np.stack([self.pulse(48), self.pulse(48)])
        p = self.parameters("S"); p[6:8] = [1, 3]
        windows = [((4, 16),), ((4, 8),)]
        cats = ["BODIES", "BUILDINGS"]
        y = np.stack([model.predict(s, p, scaling="S", category=c, pulse_windows=w) for s, c, w in zip(x, cats, windows)])
        self.assertEqual(model.objective(p, x, y, scaling="S", categories=cats, pulse_windows=windows), 0.)
        self.assertGreater(model.objective(p, x, y, scaling="S", categories=cats[::-1], pulse_windows=windows), 0.)

    def test_actual_generated_fit_and_export(self):
        x = np.stack([self.pulse(96), self.pulse(96)])
        initial = model.parameter_spec()[1]
        y = np.stack([model.predict(s, initial) for s in x])
        result = model.fit(x, y, max_nfev=3)
        self.assertTrue(result.success)
        self.assertGreater(result.status, 0)
        self.assertEqual(result.objective_sse, 0.)
        self.assertEqual(result.cost, 0.)
        self.assertEqual(result.nfev, 1)
        np.testing.assert_array_equal(result.parameters, initial)
        self.assertFalse(result.parameters.flags.writeable)
        record = result.as_dict()
        self.assertEqual(record["objective_contract"], model.SOURCE_OBJECTIVE)
        self.assertEqual(record["solver_options"]["x_scale"], 1.)
        self.assertEqual(record["solver_options"]["method"], "trf")
        self.assertFalse(record["source_default_max_nfev_preserved"])
        self.assertFalse(record["historical_runtime_parity"])
        json.dumps(record, allow_nan=False)

    def test_exhausted_generated_fit_retains_failure_and_scalar_squared_cost(self):
        x = np.stack([self.pulse(96), self.pulse(96)])
        initial = model.parameter_spec()[1]
        y = np.stack([model.predict(s, initial) + .05 for s in x])
        result = model.fit(x, y, max_nfev=1)
        self.assertFalse(result.success)
        self.assertEqual(result.status, 0)
        self.assertEqual(result.nfev, 1)
        self.assertAlmostEqual(result.cost, .5 * result.objective_sse**2, places=14)

    def test_invalid_numeric_inputs_refuse(self):
        stim = self.pulse(); p = self.parameters()
        for bad in ([True]*4, [0., np.nan], [0., np.inf], ["0", "1"], []):
            with self.subTest(stimulus=bad), self.assertRaises(model.ModelError):
                model.predict(bad, p)
        for bad in ([1, 2], [0, 1, 0, 1.5, .15, .07], [0, -1, .01, 1.5, .15, .07]):
            with self.subTest(parameters=bad), self.assertRaises(model.ModelError):
                model.predict(stim, bad)
        for bad in (0, -1, np.inf, True):
            with self.subTest(rate=bad), self.assertRaises(model.ModelError):
                model.predict(stim, p, sample_rate=bad)

    def test_zero_sigma_nonfinite_source_boundary_is_explicit_failure(self):
        p = self.parameters(); p[4] = 0
        with self.assertRaisesRegex(model.ModelError, "no epsilon"):
            model.predict(self.pulse(), p)

    def test_invalid_scaling_and_metadata_refuse(self):
        stim = self.pulse(); p = self.parameters("S")
        for mode, category, windows in (("other", "FACES", ((4,16),)), ("S", "faces", ((4,16),)), ("S", "FACES", None), ("S", "FACES", ((4.5,16),)), ("S", "FACES", ((4,1000),))):
            with self.subTest(mode=mode,category=category,windows=windows), self.assertRaises(model.ModelError):
                model.predict(stim, p, scaling=mode, category=category, pulse_windows=windows)
        with self.assertRaises(model.ModelError):
            model.objective(p, [stim,stim], [stim,stim], scaling="S", categories=["FACES"], pulse_windows=[((4,16),)]*2)

    def test_invalid_pulse_tables_and_fit_shapes_refuse(self):
        for trial, condition, one in (("unknown",0,[[1,2]]), ("onepulse",-1,[[1,2]]), ("onepulse",0,[[1.5,2]]), ("onepulse",0,[[1,2,3]])):
            with self.subTest(trial=trial,condition=condition,one=one), self.assertRaises(model.ModelError):
                model.stimulus_timecourse(trial, condition, one, [[1,2,3,4]], 8)
        with self.assertRaises(model.ModelError):
            model.fit([[0.,1.]], [[0.,1.,2.]])
        for limit in (0, 501, True, 1.5):
            with self.subTest(limit=limit), self.assertRaises(model.ModelError):
                model.fit([[0.,1.]], [[0.,1.]], max_nfev=limit)


if __name__ == "__main__":
    unittest.main()
