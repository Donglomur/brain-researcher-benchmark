"""Generated arithmetic controls, not authentic animals or a scientific run."""
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import score


def candidate(identity, means):
    return {"id": identity, "trials_to_learn_by_iteration": [list(means) for _ in range(20)]}


def document():
    return {"schema": score.SCHEMA, "conditions_s": list(score.CONDITIONS),
            "prediction_stage": "after_source_filtering_and_censoring",
            "behavior_trials_to_learn": [[1, 100, 10, 10, 10]],
            "families": [{"name": "generated_family", "num_parameters": 1,
                          "candidates": [candidate("raw_winner", [2, 100, 10, 10, 10]),
                                         candidate("log_winner", [1, 110, 10, 10, 10])]}]}


class MetricsTests(unittest.TestCase):
    def test_log_selection_and_raw_aic_reverse_order(self):
        result = score.evaluate(document())["families"][0]
        a, b = result["candidates"]
        self.assertEqual(result["selected_id"], "log_winner")
        self.assertLess(b["selection_log_rss"], a["selection_log_rss"])
        self.assertLess(a["AIC_k0"], b["AIC_k0"])
        self.assertAlmostEqual(a["AIC_k0"], 5 * math.log(1 / 5))
        self.assertAlmostEqual(b["AIC_k0"], 5 * math.log(100 / 5))
        self.assertAlmostEqual(b["selection_log_rss"], math.log(1.1) ** 2)

    def test_original_missing_observation_weighting(self):
        behavior = [[1, 2, 3, 4, 5], [2, None, None, None, None]]
        got = score.source_metrics(behavior, [1, 2, 3, 4, 5], 2)
        self.assertEqual(got["source_nAnimals"], 6)
        self.assertEqual(got["raw_residual_count"], 6)
        self.assertAlmostEqual(got["raw_scale_mse"], 1 / 6)
        self.assertAlmostEqual(got["selection_log_rss"], math.log(2) ** 2)
        self.assertAlmostEqual(got["AIC_parameter_penalized"], 6 * math.log(1 / 6) + 4)
        self.assertAlmostEqual(got["AICc_parameter_penalized_source_value"],
                               6 * math.log(1 / 6) + 4 + 12 / 3)

    def test_missing_prediction_does_not_masquerade_as_complete(self):
        got = score.source_metrics([[1, 2, 3, 4, 5]], [None, 3, 3, 4, 5], 0)
        self.assertTrue(math.isinf(got["selection_log_rss"]))
        self.assertEqual(got["source_nAnimals"], 5)
        self.assertEqual(got["raw_residual_count"], 4)
        self.assertAlmostEqual(got["AIC_k0"], 5 * math.log(1 / 4))
        self.assertFalse(got["complete_prediction_support"])

    def test_all_missing_predictions_are_not_selected(self):
        data = document()
        data["families"][0]["candidates"] = [candidate("failed", [None] * 5)]
        got = score.evaluate(data)["families"][0]
        self.assertEqual(got["source_first_ranked_id"], "failed")
        self.assertIsNone(got["selected_id"])
        self.assertFalse(got["finite_selection_available"])
        self.assertTrue(math.isnan(got["candidates"][0]["AIC_k0"]))

    def test_mean_is_taken_before_log_and_nan_propagates(self):
        rows = [[1, 1, 1, 1, 1] for _ in range(10)] + [[9, 9, 9, 9, 9] for _ in range(10)]
        means = score.iteration_means(rows)
        self.assertEqual(means, [5] * 5)
        got = score.source_metrics([[5] * 5], means, 0)
        self.assertEqual(got["selection_log_rss"], 0)
        rows[-1][2] = None
        self.assertEqual(score.iteration_means(rows), [5, 5, None, 5, 5])

    def test_perfect_fit_retains_negative_infinite_aic(self):
        got = score.source_metrics([[1, 2, 3, 4, 5]], [1, 2, 3, 4, 5], 0)
        self.assertEqual(got["AIC_k0"], -math.inf)
        self.assertEqual(score.json_safe(got)["AIC_k0"], "-Infinity")
        json.dumps(score.json_safe(got), allow_nan=False)

    def test_small_sample_aicc_is_reported_without_claiming_validity(self):
        got = score.source_metrics([[1] * 5], [2] * 5, 4)
        self.assertEqual(got["AICc_parameter_penalized_source_value"], math.inf)
        self.assertFalse(got["AICc_sample_size_condition_met"])

    def test_ties_keep_source_order(self):
        data = document()
        data["families"][0]["candidates"] = [candidate("z", [2] * 5), candidate("a", [2] * 5)]
        got = score.evaluate(data)["families"][0]
        self.assertEqual(got["selected_id"], "z")
        self.assertEqual(got["log_rss_rank_zero_based"], [0, 1])

    def test_no_iti_subset_or_reorder(self):
        for conditions in ([60, 600], [60, 30, 300, 600, 3600]):
            data = document()
            data["conditions_s"] = conditions
            with self.assertRaises(ValueError):
                score.evaluate(data)

    def test_no_empty_iti_support(self):
        data = document()
        data["behavior_trials_to_learn"][0][4] = None
        with self.assertRaises(ValueError):
            score.evaluate(data)

    def test_failed_replicates_cannot_be_dropped(self):
        data = document()
        data["families"][0]["candidates"][0]["trials_to_learn_by_iteration"].pop()
        with self.assertRaises(ValueError):
            score.evaluate(data)

    def test_duplicate_identity_and_bad_domains(self):
        data = document()
        data["families"][0]["candidates"][1]["id"] = "raw_winner"
        with self.assertRaises(ValueError):
            score.evaluate(data)
        for invalid in (False, 0, -1, math.nan, math.inf, "4"):
            with self.assertRaises(ValueError):
                score.source_metrics([[1] * 5], [invalid, 1, 1, 1, 1], 0)
        with self.assertRaises(ValueError):
            score.source_metrics([[1] * 5], [1] * 5, True)

    def test_cli_and_input_binding(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "generated.json"
            output = Path(temp) / "score.json"
            source.write_text(json.dumps(document()))
            done = subprocess.run([sys.executable, str(Path(score.__file__)), "--input", str(source),
                                   "--output", str(output)], capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            result = json.loads(output.read_text())
            self.assertEqual(result["families"][0]["selected_id"], "log_winner")
            self.assertEqual(len(result["input_sha256"]), 64)
            self.assertFalse(result["source_preprocessing_authenticated"])
            self.assertFalse(result["paper_improvement_claim"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
