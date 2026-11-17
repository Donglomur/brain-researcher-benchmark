"""Small generated software controls; no recordings, weights or solver outputs."""
import copy
import importlib.util
import math
from pathlib import Path
import sys
import unittest

spec = importlib.util.spec_from_file_location("spinal_metrics", Path(__file__).with_name("metrics.py"))
metrics = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = metrics
spec.loader.exec_module(metrics)
Prediction = metrics.Prediction


def controls(values):
    return {name: Prediction(tuple(values), "hz" if name in metrics.RATE_METHODS else "arbitrary")
            for name in metrics.SOURCE_CONTROLS}


def observation(identity, target=(0., 1., 2.), candidate=(0., 1., 2.)):
    return {"neuron_id": identity, "target_hz": target, "support": [True] * len(target),
            "controls": controls(target), "candidate": Prediction(tuple(candidate), "hz")}


class MetricsControls(unittest.TestCase):
    def score(self, target=(0., 1., 2.), prediction=(2., 1., 0.), **kwargs):
        return metrics.score_neuron(target_hz=target, controls=kwargs.pop("controls", controls(target)),
                                    candidate=Prediction(tuple(prediction), kwargs.pop("unit", "hz")),
                                    support=kwargs.pop("support", [True] * len(target)),
                                    sampling_rate_hz=30, **kwargs)

    def test_hand_computed_correlation_error_and_bias_are_distinct(self):
        result = self.score()["methods"]["candidate"]
        self.assertAlmostEqual(result["correlation"]["value"], -1)
        self.assertAlmostEqual(result["rate_diagnostics"]["normalized_l1"], 4 / 3)
        self.assertEqual(result["rate_diagnostics"]["signed_bias"], 0)
        result = self.score(prediction=(0., 2., 4.))["methods"]["candidate"]
        self.assertAlmostEqual(result["correlation"]["value"], 1)
        self.assertAlmostEqual(result["rate_diagnostics"]["normalized_l1"], 1)
        self.assertAlmostEqual(result["rate_diagnostics"]["signed_bias"], 1)

    def test_count_per_bin_conversion_preserves_absolute_rate_diagnostics(self):
        result = self.score(prediction=(0., 1 / 30, 2 / 30), unit="expected_spikes_per_bin")
        self.assertEqual(result["methods"]["candidate"]["rate_diagnostics"]["normalized_l1"], 0)
        wrong = self.score(prediction=(0., 1 / 30, 2 / 30))["methods"]["candidate"]
        self.assertAlmostEqual(wrong["correlation"]["value"], 1)
        self.assertAlmostEqual(wrong["rate_diagnostics"]["signed_bias"], -29 / 30)

    def test_amplitude_uncalibrated_controls_have_correlation_only(self):
        result = self.score()
        for method in ("raw_fluorescence", "oasis"):
            self.assertAlmostEqual(result["methods"][method]["correlation"]["value"], 1)
            self.assertEqual(result["methods"][method]["rate_diagnostics"]["status"],
                             "amplitude_not_calibrated")

    def test_missing_cross_dataset_control_rejected(self):
        inputs = controls((0., 1., 2.))
        del inputs["gabaergic_cascade"]
        with self.assertRaisesRegex(ValueError, "five"):
            self.score(controls=inputs)

    def test_nonfinite_prediction_cannot_select_easier_support(self):
        for value in (math.nan, math.inf, -math.inf):
            with self.assertRaisesRegex(ValueError, "finite"):
                self.score(prediction=(0., value, 2.))
        with self.assertRaisesRegex(ValueError, "literal bool"):
            self.score(support=(1, 1, 1))

    def test_fixed_unscored_context_is_preserved(self):
        values = (math.nan, 0., 1., 2., math.nan)
        result = self.score(target=values, prediction=values, support=(False, True, True, True, False))
        self.assertEqual((result["total_bins"], result["scored_bins"]), (5, 3))
        self.assertAlmostEqual(result["methods"]["candidate"]["correlation"]["value"], 1)

    def test_constant_prediction_does_not_hide_absolute_rate_failure(self):
        result = self.score(prediction=(0., 0., 0.))["methods"]["candidate"]
        self.assertEqual(result["correlation"], {"value": None, "status": "constant_prediction"})
        self.assertEqual(result["rate_diagnostics"],
                         {"normalized_l1": 1., "signed_bias": -1., "status": "defined"})

    def test_zero_signal_and_empty_support_are_explicit(self):
        result = self.score(target=(0., 0., 0.))["methods"]["candidate"]
        self.assertEqual(result["correlation"]["status"], "constant_target")
        self.assertEqual(result["rate_diagnostics"]["status"], "zero_target_signal")
        result = self.score(support=(False, False, False))["methods"]["candidate"]
        self.assertEqual(result["correlation"]["status"], "insufficient_support")
        self.assertEqual(result["rate_diagnostics"]["status"], "insufficient_support")

    def test_large_and_small_finite_values_do_not_overflow_squares(self):
        for values in ((0., 1e308, 1.5e308), (0., 1e-308, 2e-308)):
            result = self.score(target=values, prediction=values)["methods"]["candidate"]
            self.assertAlmostEqual(result["correlation"]["value"], 1)
            self.assertEqual(result["rate_diagnostics"]["normalized_l1"], 0)
        result = self.score(target=(0., 1e-308, 2e-308), prediction=(1e308,) * 3)
        self.assertEqual(result["methods"]["candidate"]["rate_diagnostics"]["status"],
                         "unrepresentable_diagnostics")

    def test_unit_length_target_and_conversion_errors(self):
        with self.assertRaisesRegex(ValueError, "unit"):
            self.score(unit="probability")
        with self.assertRaisesRegex(ValueError, "bin count"):
            self.score(prediction=(1.,))
        with self.assertRaisesRegex(ValueError, "nonnegative"):
            self.score(target=(-1., 0., 1.))
        with self.assertRaisesRegex(ValueError, "finite"):
            self.score(prediction=(1e308,) * 3, unit="expected_spikes_per_bin")

    def test_equal_neuron_summaries_do_not_pool_time_bins(self):
        rows = [observation("short", candidate=(2., 1., 0.)),
                observation("long", target=(0., 1., 2.) * 100, candidate=(0., 1., 2.) * 100)]
        result = metrics.score_condition(expected_neurons={"short": "glutamatergic", "long": "glutamatergic"},
                                         observations=rows, sampling_rate_hz=30)
        summary = result["cohorts"]["glutamatergic"]["methods"]["candidate"]["correlation"]
        self.assertAlmostEqual(summary["mean"], 0)
        self.assertAlmostEqual(summary["median"], 0)
        self.assertEqual(summary["expected_neurons"], 2)

    def test_cohort_specific_reference_and_undefined_denominators(self):
        rows = [observation("e"), observation("i", candidate=(1., 1., 1.)), observation("c")]
        rows[0]["controls"]["glutamatergic_cascade"] = Prediction((2., 1., 0.), "hz")
        result = metrics.score_condition(expected_neurons={"e": "glutamatergic", "i": "gabaergic", "c": "cortex"},
                                         observations=rows, sampling_rate_hz=30)
        e = result["cohorts"]["glutamatergic"]["paired_candidate_minus_reference"]
        i = result["cohorts"]["gabaergic"]["paired_candidate_minus_reference"]
        c = result["cohorts"]["cortex"]["paired_candidate_minus_reference"]
        self.assertEqual(e["reference_method"], "glutamatergic_cascade")
        self.assertAlmostEqual(e["per_neuron_correlation_delta"]["e"], 2)
        self.assertEqual(i["correlation_delta"]["undefined_neurons"], 1)
        self.assertIsNone(i["correlation_delta"]["mean"])
        self.assertEqual(c["reference_method"], "default_cascade")

    def test_missing_duplicate_extra_neurons_and_partial_candidate_rejected(self):
        expected = {"a": "glutamatergic", "b": "gabaergic"}
        cases = [[observation("a")], [observation("a"), observation("a")],
                 [observation("a"), observation("b"), observation("extra")]]
        partial = [observation("a"), observation("b")]
        del partial[1]["candidate"]
        cases.append(partial)
        for rows in cases:
            with self.assertRaises(ValueError):
                metrics.score_condition(expected_neurons=expected, observations=rows, sampling_rate_hz=30)

    def test_reproduction_path_has_all_five_methods_without_improvement_claim(self):
        row = observation("a")
        del row["candidate"]
        result = metrics.score_condition(expected_neurons={"a": "glutamatergic"},
                                         observations=[row], sampling_rate_hz=30)
        cohort = result["cohorts"]["glutamatergic"]
        self.assertEqual(set(cohort["methods"]), set(metrics.SOURCE_CONTROLS))
        self.assertNotIn("paired_candidate_minus_reference", cohort)

    def test_mutating_candidate_never_replaces_reference_results(self):
        row = observation("a")
        first = metrics.score_condition(expected_neurons={"a": "glutamatergic"},
                                        observations=[row], sampling_rate_hz=30)
        changed = copy.deepcopy(row)
        changed["candidate"] = Prediction((2., 1., 0.), "hz")
        second = metrics.score_condition(expected_neurons={"a": "glutamatergic"},
                                         observations=[changed], sampling_rate_hz=30)
        for method in metrics.SOURCE_CONTROLS:
            self.assertEqual(first["per_neuron"]["a"]["methods"][method],
                             second["per_neuron"]["a"]["methods"][method])

    def test_extreme_finite_diagnostics_remain_finite_after_neuron_aggregation(self):
        rows = [observation(k, target=(0., 1e-308, 2e-308), candidate=(0., 1., 2.))
                for k in ("a", "b")]
        result = metrics.score_condition(expected_neurons={"a": "gabaergic", "b": "gabaergic"},
                                         observations=rows, sampling_rate_hz=30)
        summary = result["cohorts"]["gabaergic"]["methods"]["candidate"]["normalized_l1"]
        self.assertTrue(math.isfinite(summary["mean"]))
        self.assertTrue(math.isfinite(summary["median"]))
        self.assertAlmostEqual(summary["mean"] / 1e308, 1)
        self.assertAlmostEqual(summary["median"] / 1e308, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
