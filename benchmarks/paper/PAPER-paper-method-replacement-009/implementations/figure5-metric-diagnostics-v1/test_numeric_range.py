"""Generated range controls for the unchanged dynamic R2 definitions."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("range_metrics", Path(__file__).with_name("metrics.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class DynamicRangeControls(unittest.TestCase):
    def test_tiny_varying_truth_is_not_misclassified_as_constant(self):
        for scale in (1e-200, float.fromhex("0x0.0000000000001p-1022")):
            with self.subTest(scale=scale):
                perfect = m.score_case("wheel-speed", [0.0, scale], [0.0, scale])
                wrong = m.score_case("wheel-speed", [0.0, scale], [0.0, 0.0])
                self.assertEqual(perfect["metrics"]["r2_flattened"]["value"], 1.0)
                self.assertEqual(wrong["metrics"]["r2_flattened"]["value"], -1.0)
                self.assertEqual(perfect["undefined_output_indices"], [])

    def test_finite_large_r2_and_uniform_mean_survive_squared_overflow(self):
        score = m.score_case("wheel-speed", [[-1.0, -1.0], [1.0, 1.0]],
                            [[1e154, 1e154], [1e154, 1e154]])
        self.assertEqual(score["metrics"]["r2_flattened"]["value"], -1e308)
        self.assertEqual(score["metrics"]["r2_uniform_output_strict"]["value"], -1e308)
        self.assertEqual(score["reduction_difference"], 0.0)

    def test_complete_session_animal_means_do_not_overflow_their_sum(self):
        score = m.score_case("wheel-speed", [-1.0, 1.0], [1e154, 1e154])
        cases = [dict(case_id=str(i), session="s" + str(i), animal="a" + str(i),
                      target="wheel-speed", region="CA1", condition="generated")
                 for i in range(3)]
        result = m.summarize_group(cases, {str(i): score for i in range(3)}, "r2_flattened")
        self.assertTrue(result["complete_support"])
        self.assertEqual(result["equal_session_diagnostic"], -1e308)
        self.assertEqual(result["equal_animal_diagnostic"], -1e308)

    def test_constant_and_unrepresentable_scores_remain_undefined(self):
        constant = m.score_case("wheel-speed", [1.0, 1.0], [0.0, 0.0])
        self.assertEqual(constant["metrics"]["r2_flattened"]["undefined_reason"], "constant_truth")
        huge = m.score_case("wheel-speed", [-1e-200, 1e-200], [1e308, 1e308])
        self.assertEqual(huge["metrics"]["r2_flattened"]["undefined_reason"], "nonfinite_arithmetic")

    def test_ordinary_distinct_reductions_are_preserved(self):
        score = m.score_case("wheel-speed", [[0, 100], [2, 102]], [[1, 101], [1, 101]])
        self.assertEqual(score["metrics"]["r2_flattened"]["value"], 1 - 4 / 10004)
        self.assertEqual(score["metrics"]["r2_uniform_output_strict"]["value"], 0)
        self.assertIsNone(score["original_panel_reduction"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
