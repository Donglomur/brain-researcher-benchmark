"""Generated numerical controls; no empirical observations or decoder inference."""
import copy
import importlib.util
import math
import os
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get("POSITION_SCORE_SOURCE", ROOT / "position_score.py"))
spec = importlib.util.spec_from_file_location("position_score_representable", SOURCE)
ps = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ps)


def complete_panel(epsilon=1e-200):
    reference = {"schema_version": 1, "kind": "generated_control", "phase": "learned", "mice": {}}
    candidate = {"schema_version": 1, "access_condition": "paper_and_data", "mice": {}}
    for multiple, mouse in enumerate(ps.MICE, 1):
        arms = {arm: {"frame_ids": [f"{mouse}:{arm}:{i}" for i in range(20)],
                      "trial_groups": [i // 2 for i in range(20)],
                      "positions": [0.0] * 20} for arm in ("L", "R")}
        author, submitted, shuffles = {}, {}, {}
        for condition in ps.CONDITIONS:
            target = condition[0]
            # Independent frozen grouped split: RandomState42 selects groups8,1.
            indices = [2, 3, 16, 17] if len(condition) == 1 else list(range(20))
            row = {"frame_ids": [arms[target]["frame_ids"][i] for i in indices],
                   "positions": [0.0] * len(indices)}
            prediction = {**copy.deepcopy(row), "positions": [
                multiple * epsilon * (1 + i % 2) for i in range(len(indices))]}
            if condition.endswith(" Shuffled"):
                shuffles[condition] = [f"{mouse}:{condition}:{i}" for i in range(50)]
                author[condition] = [{**copy.deepcopy(row), "shuffle_id": key}
                                     for key in shuffles[condition]]
                submitted[condition] = [{**copy.deepcopy(prediction), "shuffle_id": key}
                                        for key in shuffles[condition]]
            else:
                author[condition], submitted[condition] = row, prediction
        reference["mice"][mouse] = {"arms": arms, "author": author, "shuffle_ids": shuffles}
        candidate["mice"][mouse] = submitted
    return reference, candidate


class RepresentableRmseTests(unittest.TestCase):
    def assert_relative(self, actual, expected):
        self.assertTrue(math.isclose(actual, expected, rel_tol=1e-14, abs_tol=0.0),
                        f"{actual!r} differs from representable {expected!r}")

    def test_tiny_nonzero_errors_keep_source_and_fixed_support(self):
        epsilon = 1e-200
        prediction = [epsilon, epsilon, 2 * epsilon, 2 * epsilon]
        result = ps.source_error([0, 0, 0, 0], prediction, prediction)
        self.assert_relative(result["source_modal_filtered_rmse"], 2 * epsilon)
        self.assert_relative(result["author_support_rmse"], 2 * epsilon)
        self.assert_relative(result["full_bin_rmse"], math.sqrt(2.5) * epsilon)
        self.assertEqual((result["source_retained_frames"], result["source_excluded_frames"]), (2, 2))

    def test_complete_panel_reproduction_and_population_dispersion(self):
        reference, candidate = complete_panel()
        report = ps.score(reference, candidate)
        for multiple, mouse in enumerate(ps.MICE, 1):
            for condition in ps.CONDITIONS:
                cell = report["mice"][mouse]["conditions"][condition]
                expected = math.sqrt(2.5) * multiple * 1e-200
                self.assertEqual(cell["draw_count"], 50 if condition.endswith(" Shuffled") else 1)
                for draw in cell["draws"]:
                    self.assert_relative(draw["candidate"]["full_bin_rmse"], expected)
                    self.assert_relative(draw["reproduction_prediction_comparison"]["rmse_from_author"], expected)
                self.assertIsNone(cell["mean_over_draws"]["author"]["source_modal_filtered_rmse"])
        for condition in ps.CONDITIONS:
            summary = report["panel"][condition]["candidate"]["full_bin_rmse"]
            self.assert_relative(summary["population_std_ddof_0"], math.sqrt(3.125) * 1e-200)
        self.assertIsNone(report["superiority_decision"])
        self.assertIsNone(report["reproduction_decision"])

    def test_regular_errors_keep_literal_original_reduction(self):
        result = ps.source_error([0, 1, 0, 1], [.25, .25, .75, .75], [.25, .25, .75, .75])
        self.assertEqual(result["source_modal_filtered_rmse"], math.sqrt(.3125))
        self.assertEqual(result["full_bin_rmse"], math.sqrt(.3125))
        self.assertEqual(result["author_support_rmse"], math.sqrt(.3125))
        self.assertEqual(result["common_retained_frames"], 2)

    def test_true_zero_and_undefined_source_support_are_preserved(self):
        zero = ps.source_error([.25, .25, .75, .75], [.25, .25, .75, .75], [.25, .25, .75, .75])
        self.assertEqual(zero["source_modal_filtered_rmse"], 0.0)
        undefined = ps.source_error([0, 1], [.5, .5], [.25, .75])
        self.assertIsNone(undefined["source_modal_filtered_rmse"])
        self.assertEqual(undefined["full_bin_rmse"], .5)


if __name__ == "__main__":
    unittest.main()
