"""Generated-only controls; no original responses or fitted outputs are loaded."""
import copy
import importlib.util
from pathlib import Path
import unittest
from unittest import mock
from types import SimpleNamespace

import numpy as np

spec = importlib.util.spec_from_file_location("temporal_biological_controls", Path(__file__).with_name("biological.py"))
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)


def fixture():
    labels = np.array([17, 33, 67, 133, 267, 533])
    one = np.column_stack((np.full(6, 50), [58, 67, 84, 118, 187, 323]))
    starts = np.array([127, 135, 152, 186, 254, 391])
    two = np.column_stack((np.full(6, 50), np.full(6, 118), starts, starts + 68))
    variables = {"t": np.arange(819) / 512, "cond_temp": labels, "onepulse": one, "twopulse_repeat": two}
    recipe = {"schema": "temporal026-biological-reconstruction/v1", "auc_window_samples": 60,
              "reference_onepulse_condition": 3, "longest_onepulse_condition": 5,
              "isi_seconds": (labels / 1000).tolist(), "metric_window_samples": [40, 500],
              "normalization": "none", "duration_category_pool": "equal_mean_all_six",
              "fwhm_policy": "sampled_first_rise_first_decay_from_zero",
              "log_fit": "unweighted_linear_least_squares_on_log_seconds", "bootstrap_seed": 123,
              "reconstruction_status": "prospective_not_original_figure_execution"}
    wave = np.concatenate((np.arange(25) / 25, np.arange(25, 0, -1) / 25))
    first = np.zeros(819); first[50:100] = wave
    single = np.stack([first] * 6)
    ratios = 1 + .2 * np.log(labels / 1000)
    repeated = np.stack([first.copy() for _ in range(6)])
    for row, start, ratio in zip(repeated, starts, ratios):
        row[start:start + 50] += ratio * wave
    return variables, recipe, single, repeated, ratios


class BiologicalControls(unittest.TestCase):
    @staticmethod
    def population(count):
        v, recipe, one, two, _ = fixture()
        cats = ("BODIES", "BUILDINGS", "FACES", "OBJECTS", "SCENES", "SCRAMBLED")
        rows = [{"trial_type": trial, "img_cat": cat, "temp_cond": condition}
                for trial in ("onepulse", "twopulse_repeat") for cat in cats for condition in range(6)]
        traces = [((one if row["trial_type"] == "onepulse" else two)[row["temp_cond"]] *
                   (1 + cats.index(row["img_cat"]) / 10)).tolist() for row in rows]
        roster = [{"id": "e%d" % i, "subject": "s%d" % (i % 4), "varea": "V1-V3" if i == 0 else "LOTC"}
                  for i in range(count)]
        jobs = [{"id": x["id"] + "/DN-S/full", "electrode_id": x["id"], "model": "DN", "scaling": "S",
                 "mode": "full", "fold": None, "response_columns": "named_response_columns"} for x in roster]
        plan = {"plan_sha256": "a" * 64, "jobs": jobs, "scalings": ["none", "S"]}
        manifest = {"electrodes": [{"electrode_id": x["id"], "source_data_sha256": "b" * 64, "rows": rows} for x in roster]}
        components = [{"response": trace, "linear": trace, "drive": trace, "numerator": trace,
                       "normalization_pool": trace, "denominator": [1.] * 819,
                       "semisaturation": .1, "category_scale": 1.} for trace in traces]
        def results():
            for job in jobs:
                yield {"schema": b.io.RESULT_SCHEMA, "plan_sha256": plan["plan_sha256"], "job": job,
                       "source_data_sha256": "b" * 64, "train_rows": list(range(72)),
                       "prediction_rows": list(range(72)), "prediction_identities": rows,
                       "status": "converged", "fit": {"success": True}, "observations": traces,
                       "predictions": traces, "components": components}
        replay = SimpleNamespace(cohort=lambda: roster, CATEGORIES=cats, TRIALS=("onepulse", "twopulse_repeat"))
        return v, recipe, roster, plan, manifest, results, replay

    def test_recipe_is_explicit_and_externally_pinned(self):
        v, r, *_ = fixture()
        self.assertEqual(b.validate_recipe(r, b.io.digest(r), v), r)
        altered = copy.deepcopy(r); altered["auc_window_samples"] += 1
        with self.assertRaises(ValueError): b.validate_recipe(altered, b.io.digest(r), v)

    def test_missing_or_invented_historical_policy_refused(self):
        v, r, *_ = fixture()
        for field, replacement in [("reconstruction_status", "source_equivalent"),
                                   ("fwhm_policy", "unrecorded_default"), ("normalization", "zscore"),
                                   ("duration_category_pool", "best_category")]:
            bad = dict(r); bad[field] = replacement
            with self.assertRaises(ValueError): b.validate_recipe(bad, b.io.digest(bad), v)
        bad = dict(r); bad.pop("auc_window_samples")
        with self.assertRaises(ValueError): b.validate_recipe(bad, b.io.digest(bad), v)

    def test_reference_longest_and_isi_units_not_inferred(self):
        v, r, *_ = fixture()
        for field, value in [("reference_onepulse_condition", 2), ("longest_onepulse_condition", 4),
                             ("isi_seconds", v["cond_temp"].tolist()), ("auc_window_samples", 819)]:
            bad = dict(r); bad[field] = value
            with self.assertRaises(ValueError): b.validate_recipe(bad, b.io.digest(bad), v)

    def test_source_sequential_first_response_unequal_weights(self):
        v, _, _, _, _ = fixture()
        one = np.full((6, 819), 2.)
        two = np.stack([np.full(819, float(i + 4)) for i in range(6)])
        first = b.first_response(one, two, v["twopulse_repeat"], 3)
        expected = 2.
        for level in range(4, 10): expected = (expected + level) / 2
        self.assertEqual(first[60], expected)
        self.assertNotEqual(first[60], np.mean([2] + list(range(4, 10))))
        self.assertEqual(first[0], 2.)
        self.assertEqual(first[-1], 2.)

    def test_auc_uses_sample_spacing_and_keeps_signed_values(self):
        self.assertEqual(b.sample_auc([0, 2, 4]), 4.)
        self.assertEqual(b.sample_auc([0, -2, -4]), -4.)

    def test_full_recovery_and_log_one_second_output(self):
        v, r, one, two, ratios = fixture()
        result = b.trace_metrics(one, two, v, r)
        np.testing.assert_allclose(result["recovery_ratios"], ratios, rtol=1e-14, atol=1e-14)
        self.assertAlmostEqual(result["log_recovery"]["a"], .2, places=13)
        self.assertAlmostEqual(result["log_recovery"]["c"], 1., places=13)
        self.assertEqual(result["log_recovery"]["c"], result["log_recovery"]["extrapolated_1_second"])
        self.assertEqual(np.shape(result["isolated_second_responses"]), (6, 819))
        self.assertEqual(len(result["duration"]), 6)

    def test_zero_auc_does_not_silently_repair_or_drop(self):
        v, r, *_ = fixture()
        result = b.trace_metrics(np.zeros((6, 819)), np.zeros((6, 819)), v, r)
        self.assertEqual(result["recovery_ratios"], [None] * 6)
        self.assertIsNone(result["mean_recovery"])
        self.assertEqual(result["log_recovery"]["status"], "undefined_recovery")

    def test_sampled_crossings_declared_and_missing_crossing_retained(self):
        times = np.arange(7) / 10
        result = b.duration_metrics(np.array([0, 1, 2, 3, 2, 1, 0.]), times, 0, [0, 7])
        self.assertAlmostEqual(result["time_to_peak_seconds"], .3)
        self.assertAlmostEqual(result["fwhm_seconds"], .3)
        missing = b.duration_metrics(np.ones(7), times, 0, [0, 7])
        self.assertIsNone(missing["fwhm_seconds"])
        self.assertEqual(missing["status"], "missing_sampled_half_maximum_crossing")

    def test_average_traces_before_metrics_is_not_average_of_ratios(self):
        v, r, one, two, _ = fixture()
        first = one[0]
        a = np.stack([first] * 6)
        second_only = two - first
        a_two = a.copy()
        b_one = 3 * one
        b_two = 3 * (first + second_only)
        pooled = b.trace_metrics((a + b_one) / 2, (a_two + b_two) / 2, v, r)
        separate = np.array(b.trace_metrics(b_one, b_two, v, r)["recovery_ratios"]) / 2
        np.testing.assert_allclose(pooled["recovery_ratios"], separate * 1.5)
        self.assertFalse(np.allclose(pooled["recovery_ratios"], separate))

    def test_bootstrap_preserves_1000_draws_nesting_and_undefined(self):
        v, r, one, two, _ = fixture()
        rows = [{"id": "generated-e1", "subject": "generated-s1"}]
        value = b.regional_summary(np.array([[one, two]]), rows, v, r)
        self.assertEqual(value["participant_nesting"], {"generated-e1": "generated-s1"})
        self.assertEqual(len(value["bootstrap_metrics"]["mean_recovery"]["draws"]), 1000)
        self.assertEqual(value["bootstrap_metrics"]["mean_recovery"]["undefined_count"], 0)
        # A window deliberately excluding every rise preserves all undefined draws.
        bad = dict(r); bad["metric_window_samples"] = [75, 100]
        missing = b.regional_summary(np.array([[one, two]]), rows, v, bad)
        self.assertEqual(missing["bootstrap_metrics"]["fwhm_0"]["undefined_count"], 1000)
        self.assertIsNone(missing["bootstrap_metrics"]["fwhm_0"]["median"])

    def test_category_counts_cannot_substitute_for_identities(self):
        cats = ("BODIES", "BUILDINGS", "FACES", "OBJECTS", "SCENES", "SCRAMBLED")
        entries = [{"electrode_id": "e%d" % i, "preferred": "FACES", "nonpreferred": ["BODIES", "BUILDINGS", "OBJECTS", "SCENES"],
                    "threshold": .5, "scrambled": "excluded"} for i in range(26)]
        selection = {"schema": "temporal026-category-selection-input/v1", "entries": entries,
                     "selection_evidence": {"path": "provenance.json", "bytes": 1, "sha256": "a" * 64},
                     "pooling": "equal_mean_explicit_nonpreferred_categories"}
        roster = {x["electrode_id"] for x in entries}
        self.assertEqual(len(b.validate_selection(selection, b.io.digest(selection), roster, cats)), 26)
        for mutate in (lambda x: x["entries"][0].update(electrode_id="unknown"),
                       lambda x: x["entries"][0].update(threshold=1),
                       lambda x: x["entries"][0].update(nonpreferred=["SCRAMBLED"]),
                       lambda x: x["entries"].__setitem__(1, x["entries"][0])):
            bad = copy.deepcopy(selection); mutate(bad)
            with self.assertRaises(ValueError): b.validate_selection(bad, b.io.digest(bad), roster, cats)

    def test_complete_regional_output_keeps_category_gap_and_missing_fit_refuses(self):
        v, recipe, roster, plan, manifest, results, replay = self.population(1)
        report = b.summarize(plan, manifest, results(), v, recipe, b.io.digest(recipe), "V1-V3", "S", replay)
        self.assertEqual(report["status"], "complete_prospective_reconstruction")
        self.assertFalse(report["scientific_qualification"])
        self.assertFalse(report["historical_figure_execution"])
        self.assertEqual(report["category_family"]["status"], "pending_original_selection_identities_and_trial_protocol")
        self.assertEqual(set(report["regional"]), {"observations", "DN_predictions"})
        self.assertEqual(report["regional"]["observations"]["electrodes"], ["e0"])
        with self.assertRaises(ValueError):
            b.summarize(plan, manifest, [], v, recipe, b.io.digest(recipe), "V1-V3", "S", replay)

    def test_main_category_route_pools_all26_before_metrics_across_regions(self):
        v, recipe, roster, plan, manifest, results, replay = self.population(26)
        selection = {"schema": "temporal026-category-selection-input/v1",
                     "entries": [{"electrode_id": x["id"], "preferred": "FACES",
                                  "nonpreferred": ["BODIES", "BUILDINGS", "OBJECTS", "SCENES"],
                                  "threshold": .5, "scrambled": "excluded"} for x in roster],
                     "selection_evidence": {"path": "proof.json", "bytes": 1, "sha256": "c" * 64},
                     "pooling": "equal_mean_explicit_nonpreferred_categories"}
        calls = []
        def summarize_generated(traces, rows, variables, policy):
            calls.append((np.shape(traces), len(rows)))
            return {"electrodes": [r["id"] for r in rows]}
        with mock.patch.object(b, "regional_summary", side_effect=summarize_generated):
            report = b.summarize(plan, manifest, results(), v, recipe, b.io.digest(recipe), "selected-all", "S", replay,
                                 selection, b.io.digest(selection))
        self.assertEqual(report["population_scope"], "main_all26_selected_trace_first_pool")
        self.assertEqual(len(report["electrode_regions"]), 26)
        self.assertEqual(set(report["electrode_regions"].values()), {"V1-V3", "LOTC"})
        self.assertEqual(len(calls), 6)
        self.assertTrue(all(shape == (26, 2, 6, 819) and n == 26 for shape, n in calls))
        self.assertEqual(len(report["category_family"]["regional"]["observations"]["preferred"]["electrodes"]), 26)
        with self.assertRaises(ValueError):
            b.summarize(plan, manifest, results(), v, recipe, b.io.digest(recipe), "selected-all", "S", replay)


if __name__ == "__main__":
    unittest.main()
