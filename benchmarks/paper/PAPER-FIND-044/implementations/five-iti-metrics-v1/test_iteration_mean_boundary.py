"""Generated complete five-ITI controls, not animal or simulation observations."""
import math
import unittest

import score


def panel(rows, observed):
    return {
        "schema": score.SCHEMA,
        "conditions_s": list(score.CONDITIONS),
        "prediction_stage": "after_source_filtering_and_censoring",
        "behavior_trials_to_learn": [list(observed)],
        "families": [{"name": "generated", "num_parameters": 0,
                      "candidates": [{"id": "complete", "trials_to_learn_by_iteration": rows}]}],
    }


def summary(document):
    return score.evaluate(document)["families"][0]["candidates"][0]


class IterationMeanBoundaryTests(unittest.TestCase):
    def test_complete_subnormal_panel_remains_valid(self):
        smallest = math.ulp(0.0)
        document = panel([[smallest] * 5 for _ in range(20)], [smallest] * 5)
        family = score.evaluate(document)["families"][0]
        self.assertEqual(family["selected_id"], "complete")
        self.assertEqual(family["candidates"][0]["mean_trials_to_learn"], [smallest] * 5)
        self.assertEqual(family["candidates"][0]["selection_log_rss"], 0.0)
        self.assertTrue(family["candidates"][0]["complete_prediction_support"])

    def test_mixed_subnormal_panel_keeps_positive_contributions(self):
        smallest = math.ulp(0.0)
        rows = [[smallest] * 5 for _ in range(19)] + [[20 * smallest] * 5]
        # The exact mean is 39/20 units, which rounds to two binary64 units.
        value = summary(panel(rows, [2 * smallest] * 5))
        self.assertEqual(value["mean_trials_to_learn"], [2 * smallest] * 5)
        self.assertEqual(value["selection_log_rss"], 0.0)

    def test_nonzero_subnormal_terms_preserve_constant_panel(self):
        onset = 21 * math.ulp(0.0)
        document = panel([[onset] * 5 for _ in range(20)], [onset] * 5)
        value = summary(document)
        self.assertEqual(value["mean_trials_to_learn"], [onset] * 5)
        self.assertEqual(value["selection_log_rss"], 0.0)

    def test_ordinary_complete_panel_keeps_mean_before_log(self):
        rows = [[1] * 5 for _ in range(10)] + [[9] * 5 for _ in range(10)]
        value = summary(panel(rows, [5] * 5))
        self.assertEqual(value["mean_trials_to_learn"], [5] * 5)
        self.assertEqual(value["selection_log_rss"], 0.0)
        self.assertEqual(value["AIC_k0"], -math.inf)
        self.assertEqual(value["source_nAnimals"], 5)

    def test_missing_iteration_still_propagates(self):
        rows = [[1] * 5 for _ in range(20)]
        rows[-1][2] = None
        value = summary(panel(rows, [1] * 5))
        self.assertEqual(value["mean_trials_to_learn"], [1, 1, None, 1, 1])
        self.assertEqual(value["selection_log_rss"], math.inf)
        self.assertEqual(value["source_nAnimals"], 5)
        self.assertEqual(value["raw_residual_count"], 4)
        self.assertFalse(value["complete_prediction_support"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
