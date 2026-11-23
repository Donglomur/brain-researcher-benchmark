"""Generated arithmetic controls; no array files, models or native inputs."""
import copy
import importlib.util
import io
import itertools
from fractions import Fraction
import math
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("cellmincer_original_kernels", ROOT / "kernels.py")
k = importlib.util.module_from_spec(spec)
spec.loader.exec_module(k)
PIN = "a" * 64


def bin_operands():
    return dict(ep_thresholds_mv=["1", "2"],
                optical_thresholds_mv=[["0.8", "1.2"], ["1.8", "2.2"]],
                f1_values=[[0.8, 0.2], [0.1, 0.9]],
                bins=[{"id": "explicit-a", "p_indices": [0, 1], "weights": [1, 1]},
                      {"id": "explicit-b", "p_indices": [1], "weights": [1]}],
                grid_identity=PIN, bin_rule_identity=PIN)


def spectral_operands():
    raw = [[100, 1e10, 1], [4, 999, 4]]
    return dict(frequency_hz=[0, 125], window_ids=["a", "b", "c"],
                ep_power=[[1, 9, 1], [0, 0, 0]], raw_residual_power=raw,
                method_residual_power={"method": [[1, 1e20, 1], [1, 1, 1]],
                                       "identity": copy.deepcopy(raw)},
                ep_sum_frequency_indices=[0, 1], ep_power_threshold=2,
                time_weights=[1, 1, 1], db_power_reference=1, power_floor=None,
                transform_identity=PIN, time_grid_identity=PIN,
                mask_rule_identity=PIN, db_rule_identity=PIN)


def peak_operands():
    return dict(reference_ticks=[0, 10], reference_prominences_mv=["2", "2"],
                predicted_ticks=[0, 10, 100, 200],
                predicted_prominences_mv=["2", "1.1", "0.9", "2"],
                ep_thresholds_mv=["1"], threshold_relation=">=", ticks_per_second=1000,
                clock_identity=PIN, peak_set_identity=PIN, bin_rule_identity=PIN,
                bins=[{"id": "explicit", "p_indices": [0], "weights": [1]}])


class OriginalRules(unittest.TestCase):
    def test_strict_ticks_include_valid_sub_picosecond_margin(self):
        got = k.fuzzy_peak_score([0, 10], [0, 12], ticks_per_second=1000, clock_identity=PIN)
        self.assertEqual(got["f1"], 0.5)  # Exactly2ms is outside; the first pair still matches.
        self.assertEqual(k.fuzzy_peak_score([0, 10], [0, 11], ticks_per_second=1000,
                                           clock_identity=PIN)["f1"], 1)
        origin = 10**18
        self.assertEqual(k.fuzzy_peak_score([origin], [origin + 2 * 10**12 - 1],
                         ticks_per_second=10**15, clock_identity=PIN)["f1"], 1)
        self.assertFalse(got["clock_authenticated"])

    def test_existential_matching_and_undefined_support(self):
        got = k.fuzzy_peak_score([0], [-1, 1], ticks_per_second=1000, clock_identity=PIN)
        self.assertEqual((got["matched_reference_count"], got["matched_predicted_count"], got["f1"]), (1, 2, 1))
        for ref, pred in [([], [0]), ([0], []), ([], []), ([0], [2])]:
            with self.subTest(ref=ref, pred=pred), self.assertRaises(k.UndefinedMetric):
                k.fuzzy_peak_score(ref, pred, ticks_per_second=1000, clock_identity=PIN)
        for ref, clock in [([0, 0], 1000), ([True], 1000), ([0], 0)]:
            with self.assertRaises(k.InputError):
                k.fuzzy_peak_score(ref, [0], ticks_per_second=clock, clock_identity=PIN)

    def test_maximum_precedes_explicit_bin_mean(self):
        got = k.prominence_bin_profile(**bin_operands())
        self.assertEqual(got["supplied_grid_max_f1"], [0.8, 0.9])
        self.assertAlmostEqual(got["bins"][0]["mean_supplied_grid_max_f1"], 0.85)
        self.assertNotAlmostEqual(got["bins"][0]["mean_supplied_grid_max_f1"], 0.55)
        self.assertEqual(got["bins"][1]["mean_supplied_grid_max_f1"], 0.9)
        self.assertFalse(got["continuous_optimum_established"])
        self.assertFalse(got["historical_recipe_authenticated"])

    def test_bin_grid_and_full_threshold_support_are_required(self):
        changes = [lambda x: x["optical_thresholds_mv"][0].__setitem__(1, "1.2000000000000000000000000001"),
                   lambda x: x["optical_thresholds_mv"][0].__setitem__(0, "1e999999999"),
                   lambda x: x["f1_values"][1].__setitem__(0, None),
                   lambda x: x.__setitem__("bins", [{"id": "x", "p_indices": [1], "weights": [1]}]),
                   lambda x: x["bins"][0].__setitem__("weights", [1, 0]),
                   lambda x: x["bins"][0].__setitem__("p_indices", [0, 0])]
        for change in changes:
            operands = bin_operands(); change(operands)
            with self.assertRaises(k.InputError): k.prominence_bin_profile(**operands)

    def test_ep_only_common_mask_and_log_before_time_mean(self):
        got = k.residual_noise_profile(**spectral_operands())
        self.assertEqual(got["ep_eligible_mask"], [True, False, True])
        self.assertEqual(got["raw_mean_residual_db"][0], 10)
        self.assertEqual(got["methods"]["method"]["noise_reduction_db"][0], 10)
        self.assertNotAlmostEqual(got["raw_mean_residual_db"][0], 10 * math.log10(50.5))
        self.assertAlmostEqual(got["methods"]["method"]["noise_reduction_db"][1], 10 * math.log10(4))
        self.assertEqual(got["methods"]["identity"]["noise_reduction_db"], [0, 0])
        changed = spectral_operands()
        changed["method_residual_power"]["method"][0] = [1000, 0, 1000]
        self.assertEqual(k.residual_noise_profile(**changed)["ep_eligible_mask"], got["ep_eligible_mask"])
        self.assertEqual(got["frequency_hz"], [0, 125])
        self.assertNotIn("mean_above_100hz_db", got)
        self.assertNotIn("score", got)

    def test_explicit_time_weights_and_floor_change_only_declared_operands(self):
        x = spectral_operands(); x["time_weights"] = [1, 1, 3]
        self.assertEqual(k.residual_noise_profile(**x)["raw_mean_residual_db"][0], 5)
        x["method_residual_power"]["method"][0] = [0, 0, 0]
        with self.assertRaises(k.UndefinedMetric): k.residual_noise_profile(**x)
        x["power_floor"] = 1
        self.assertEqual(k.residual_noise_profile(**x)["methods"]["method"]["mean_residual_db"][0], 0)

    def test_no_policy_defaults_no_skipped_nonfinite_cells(self):
        x = spectral_operands(); del x["power_floor"]
        with self.assertRaises(TypeError): k.residual_noise_profile(**x)
        x = spectral_operands(); x["raw_residual_power"][0][1] = float("nan")
        with self.assertRaises(k.InputError): k.residual_noise_profile(**x)
        x = spectral_operands(); x["ep_power_threshold"] = 0
        with self.assertRaises(k.UndefinedMetric): k.residual_noise_profile(**x)
        x = spectral_operands(); x["method_residual_power"]["method"][0].pop()
        with self.assertRaises(k.InputError): k.residual_noise_profile(**x)
        x = spectral_operands(); x["ep_sum_frequency_indices"] = [0, 0]
        with self.assertRaises(k.InputError): k.residual_noise_profile(**x)

    def test_peak_search_recovers_interior_optimum_missed_by_endpoint_grid(self):
        x = peak_operands()
        got = k.peak_prominence_bin_profile(**x)
        self.assertEqual(got["supplied_peak_max_f1"], [0.8])
        self.assertEqual(got["threshold_states_evaluated"], [3])
        self.assertEqual(got["bins"][0]["mean_supplied_peak_max_f1"], 0.8)
        endpoint_grid = k.prominence_bin_profile(
            ep_thresholds_mv=["1"], optical_thresholds_mv=[["0.8", "1.2"]],
            f1_values=[[2/3, 0.5]], bins=x["bins"], grid_identity=PIN, bin_rule_identity=PIN)
        self.assertLess(endpoint_grid["supplied_grid_max_f1"][0], got["supplied_peak_max_f1"][0])
        self.assertTrue(got["supplied_peak_search_complete"])
        self.assertFalse(got["historical_recipe_authenticated"])
        self.assertNotIn("optimal_threshold", got)

    def test_peak_threshold_relation_is_explicit_and_applies_to_both_sets(self):
        x = peak_operands()
        x.update(reference_prominences_mv=["1", "2"], predicted_ticks=[0, 10, 100],
                 predicted_prominences_mv=["1", "2", "1"])
        self.assertEqual(k.peak_prominence_bin_profile(**x)["supplied_peak_max_f1"], [0.8])
        x["threshold_relation"] = ">"
        self.assertEqual(k.peak_prominence_bin_profile(**x)["supplied_peak_max_f1"], [1.0])

    def test_peak_search_respects_exact_near_ties_and_closed_interval(self):
        x = peak_operands()
        x["predicted_prominences_mv"] = ["2", "1.0000000000000000000000000001", "1", "2"]
        got = k.peak_prominence_bin_profile(**x)
        self.assertEqual(got["supplied_peak_max_f1"], [0.8])
        self.assertEqual(got["threshold_states_evaluated"], [3])
        # At >=, the peak tied to the upper endpoint can never be excluded;
        # at >, it is excluded at that endpoint. Lower-endpoint ties also count.
        x["predicted_prominences_mv"] = ["2", "0.8", "1.2", "2"]
        self.assertEqual(k.peak_prominence_bin_profile(**x)["threshold_states_evaluated"], [2])
        x["threshold_relation"] = ">"
        self.assertEqual(k.peak_prominence_bin_profile(**x)["threshold_states_evaluated"], [2])

    def test_peak_search_matches_exhaustive_small_grid_and_bins(self):
        # All peaks on this rational grid; twentieth-mV steps hit every open
        # interval and equality point. An independent existential count oracle
        # checks both membership conventions and strict 2ms timing.
        for relation, prominences in itertools.product((">=", ">"), itertools.product(("0.8", "1", "1.2"), repeat=3)):
            x = peak_operands()
            x.update(reference_ticks=[0, 10], predicted_ticks=[0, 11, 12, 100],
                     predicted_prominences_mv=["2", *prominences], threshold_relation=relation)
            scores = []
            for step in range(16, 25):
                q = Fraction(step, 20)
                pred = [t for t, v in zip(x["predicted_ticks"], x["predicted_prominences_mv"])
                        if (Fraction(v) >= q if relation == ">=" else Fraction(v) > q)]
                precision = Fraction(sum(any(abs(t-r) < 2 for r in [0, 10]) for t in pred), len(pred))
                recall = Fraction(sum(any(abs(t-r) < 2 for t in pred) for r in [0, 10]), 2)
                scores.append(float(2 * precision * recall / (precision + recall)))
            self.assertEqual(k.peak_prominence_bin_profile(**x)["supplied_peak_max_f1"], [max(scores)])
        x = peak_operands()
        x.update(ep_thresholds_mv=["1", "1.5"], bins=[{"id": "weighted", "p_indices": [0, 1], "weights": [1, 3]}])
        got = k.peak_prominence_bin_profile(**x)
        self.assertEqual(got["supplied_peak_max_f1"], [0.8, 0.5])
        self.assertAlmostEqual(got["bins"][0]["mean_supplied_peak_max_f1"], 0.575)

    def test_peak_search_does_not_drop_undefined_states(self):
        for changes in [dict(reference_prominences_mv=["0", "0"]),
                        dict(predicted_prominences_mv=["0.9"] * 4),
                        dict(predicted_ticks=[100, 200, 300, 400])]:
            x = peak_operands(); x.update(changes)
            with self.assertRaises(k.UndefinedMetric): k.peak_prominence_bin_profile(**x)

    def test_peak_search_validates_complete_peak_input_and_explicit_policy(self):
        changes = [dict(predicted_prominences_mv=["2"]),
                   dict(predicted_prominences_mv=["2", "1", "-1", "2"]),
                   dict(predicted_prominences_mv=["2", "1", "nan", "2"]),
                   dict(predicted_ticks=[0, 10, 10, 200]), dict(reference_ticks=[False, 10]),
                   dict(threshold_relation="automatic"), dict(ticks_per_second=True),
                   dict(ep_thresholds_mv=["1", "1"]), dict(peak_set_identity="unknown")]
        for change in changes:
            x = peak_operands(); x.update(change)
            with self.assertRaises(k.InputError): k.peak_prominence_bin_profile(**x)
        x = peak_operands(); del x["threshold_relation"]
        with self.assertRaises(TypeError): k.peak_prominence_bin_profile(**x)

    def test_numeric_overflow_and_disappearing_weight_refuse(self):
        x = spectral_operands(); x["ep_power"] = [[1e308] * 3, [1e308] * 3]
        with self.assertRaises(k.UndefinedMetric): k.residual_noise_profile(**x)
        x = spectral_operands(); x["time_weights"] = [1e308, 1, 1e-308]
        with self.assertRaises(k.UndefinedMetric): k.residual_noise_profile(**x)


if __name__ == "__main__":
    # Fixed small diagnostic budget, including failed controls. No fixture files.
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=0).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(OriginalRules))
    print(f"focused_controls={result.testsRun} failures={len(result.failures)} errors={len(result.errors)}")
    if not result.wasSuccessful():
        print(stream.getvalue()[:2048])
    raise SystemExit(0 if result.wasSuccessful() else 1)
