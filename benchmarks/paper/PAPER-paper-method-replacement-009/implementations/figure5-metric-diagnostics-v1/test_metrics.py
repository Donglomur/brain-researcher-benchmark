"""Generated arithmetic controls only; no authentic data or model execution."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("figure5_diagnostics", Path(__file__).with_name("metrics.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class MetricControls(unittest.TestCase):
    def test_continuous_auc_and_ties(self):
        # All scores fall below .5: hard-label scoring cannot recover AUC=.75.
        result = m.score_case("choice", [0, 0, 1, 1], [.1, .3, .2, .4])
        self.assertEqual(result["metrics"]["auc"]["value"], .75)
        tied = m.score_case("choice", [0, 1], [.2, .2])
        self.assertEqual(tied["metrics"]["auc"]["value"], .5)
        one = m.score_case("choice", [1, 1], [.1, .9])
        self.assertEqual(one["metrics"]["auc"]["undefined_reason"], "single_class")

    def test_prior_is_correlation_not_goodness_of_fit(self):
        result = m.score_case("prior", [0, .5, 1], [10, 11, 12])
        self.assertAlmostEqual(result["metrics"]["pearson"]["value"], 1)
        inverse = m.score_case("prior", [0, .5, 1], [12, 11, 10])
        self.assertAlmostEqual(inverse["metrics"]["pearson"]["value"], -1)
        constant = m.score_case("prior", [0, .5, 1], [.5, .5, .5])
        self.assertIsNone(constant["metrics"]["pearson"]["value"])

    def test_dynamic_axes_have_materially_different_scores(self):
        # SSE=4. Global SST=10004; column SST=2 per column and column SSE=2.
        result = m.score_case("wheel-speed", [[0, 100], [2, 102]], [[1, 101], [1, 101]])
        self.assertAlmostEqual(result["metrics"]["r2_flattened"]["value"], 1 - 4 / 10004)
        self.assertEqual(result["metrics"]["r2_uniform_output_strict"]["value"], 0)
        self.assertGreater(result["reduction_difference"], .99)
        self.assertIsNone(result["original_panel_reduction"])

    def test_large_finite_prior_retains_correlation_sign(self):
        inverse = m.score_case("prior", [-1e200, 0, 1e200], [1e200, 0, -1e200])
        self.assertAlmostEqual(inverse["metrics"]["pearson"]["value"], -1)
        self.assertIsNone(inverse["metrics"]["pearson"]["undefined_reason"])
        # The unscaled sum also overflows for these finite observations.
        shifted = m.score_case("prior", [1e308, 1.1e308, 1.2e308], [3, 2, 1])
        self.assertAlmostEqual(shifted["metrics"]["pearson"]["value"], -1)

    def test_constant_output_cannot_disappear_into_average(self):
        result = m.score_case("whisker-motion-energy", [[0, 5], [2, 5]], [[0, 5], [2, 5]])
        self.assertEqual(result["metrics"]["r2_flattened"]["value"], 1)
        self.assertEqual(result["undefined_output_indices"], [1])
        self.assertIsNone(result["metrics"]["r2_uniform_output_strict"]["value"])
        self.assertEqual(result["per_output_r2"][1]["undefined_reason"], "constant_truth")

    def test_negative_r2_is_not_clamped(self):
        result = m.score_case("wheel-speed", [0, 1], [3, 4])
        self.assertEqual(result["metrics"]["r2_flattened"]["value"], -35)

    def test_shape_and_nonfinite_values_are_rejected_before_flattening(self):
        for truth, pred in [([[0, 1], [2, 3]], [[0], [1], [2], [3]]),
                            ([0, 1], [[0], [1]]),
                            ([[0], [1, 2]], [[0], [1, 2]]),
                            ([0, float("nan")], [0, 1]),
                            ([0, 1], [0, float("inf")]),
                            ([False, True], [0, 1]), ([], [])]:
            with self.subTest(truth=truth, pred=pred), self.assertRaises(m.MetricError):
                m.score_case("wheel-speed", truth, pred)
        with self.assertRaises(m.MetricError):
            m.score_case("prior", [[0, 1], [2, 3]], [[0, 1], [2, 3]])
        with self.assertRaises(m.MetricError):
            m.score_case("choice", [-1, 1], [.1, .9])


class PopulationControls(unittest.TestCase):
    def setUp(self):
        self.cases = [dict(case_id=str(i), session="session" + str(i), animal=animal,
                           target="choice", region="CA1", condition="fixed-method")
                      for i, animal in enumerate(("a", "a", "b"))]
        self.scores = {"0": m.score_case("choice", [0, 1], [.1, .9]),
                       "1": m.score_case("choice", [0, 1], [.1, .9]),
                       "2": m.score_case("choice", [0, 1], [.9, .1])}

    def test_session_and_animal_weighting_are_separate(self):
        report = m.summarize_group(self.cases, self.scores, "auc")
        self.assertAlmostEqual(report["equal_session_diagnostic"], 2 / 3)
        self.assertEqual(report["equal_animal_diagnostic"], .5)
        self.assertEqual(report["expected_animals"], 2)
        self.assertIsNone(report["original_panel_aggregation"])

    def test_missing_session_does_not_reduce_denominator(self):
        del self.scores["1"]
        report = m.summarize_group(self.cases, self.scores, "auc")
        self.assertEqual(report["expected_sessions"], 3)
        self.assertEqual(report["complete_sessions"], 2)
        self.assertFalse(report["complete_support"])
        self.assertIsNone(report["equal_session_diagnostic"])
        self.assertIsNone(report["equal_animal_diagnostic"])
        self.assertEqual(report["rows"][1]["reason"], "missing_score")
        self.assertEqual(report["animals"][0]["sessions"], ["session0", "session1"])
        self.assertIsNone(report["animals"][0]["value"])

    def test_undefined_session_remains_visible(self):
        self.scores["1"] = m.score_case("choice", [1, 1], [.1, .9])
        report = m.summarize_group(self.cases, self.scores, "auc")
        self.assertEqual(report["rows"][1]["status"], "undefined")
        self.assertEqual(report["rows"][1]["reason"], "single_class")
        self.assertIsNone(report["equal_animal_diagnostic"])

    def test_empty_duplicate_extra_and_mixed_groups_are_rejected(self):
        bad_censuses = [[], self.cases + [self.cases[0]],
                        [self.cases[0], dict(self.cases[1], region="PO")],
                        [self.cases[0], dict(self.cases[1], session="session0")],
                        [dict(self.cases[0], animal="")]]
        for cases in bad_censuses:
            with self.subTest(cases=cases), self.assertRaises(m.MetricError):
                m.summarize_group(cases, self.scores, "auc")
        with self.assertRaises(m.MetricError):
            m.summarize_group(self.cases, dict(self.scores, extra=self.scores["0"]), "auc")
        with self.assertRaises(m.MetricError):
            m.summarize_group(self.cases, self.scores, "pearson")


if __name__ == "__main__":
    unittest.main(verbosity=2)
