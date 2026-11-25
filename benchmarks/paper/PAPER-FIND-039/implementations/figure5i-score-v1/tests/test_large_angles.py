"""Generated complete-panel controls for finite-radian cosine accuracy."""
import copy
import importlib.util
import math
from pathlib import Path
import sys
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
IMPLEMENTATIONS = PACKAGE.parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


score = load("large_angles_score", PACKAGE / "score.py")
fixtures = load("large_angles_fixture", PACKAGE / "tests" / "test_score.py")


class LargeAngleTests(unittest.TestCase):
    def test_complete_panel_large_finite_prediction_uses_cosine_difference(self):
        reference, author = fixtures.fixture()
        candidate = copy.deepcopy(author)
        for session in candidate["sessions"]:
            for fold in session["folds"]:
                fold["predicted_radians"] = [1e16] * len(fold["test_observation_ids"])
        result = score.score_panel(reference, candidate, author, author)
        expected = math.cos(-1e16)
        self.assertEqual(len(result["sessions"]), 61)
        for row in result["sessions"]:
            self.assertEqual(len(row["arms"]["candidate"]["fold_scores"]), 10)
            for value in row["arms"]["candidate"]["fold_scores"]:
                self.assertAlmostEqual(value, expected, places=14)
        for age in ("young", "aged"):
            self.assertAlmostEqual(result["age_strata"][age]["session_mean"]["candidate"], expected, places=14)
            self.assertEqual(result["age_strata"][age]["session_mean"]["author"], 1.0)

    def test_representable_large_differences_match_direct_libm(self):
        for target, predicted in ((1e16, 0.0), (1e16, 1e16 + 2.0),
                                  (1e100, 2.0), (sys.float_info.max, 0.0)):
            with self.subTest(target=target, predicted=predicted):
                self.assertEqual(score.cosine_score([target], [predicted]), math.cos(target - predicted))

    def test_normal_finite_angles_keep_declared_geometry(self):
        for target, predicted in ((0.0, 0.0), (0.0, math.pi), (0.0, math.pi / 2),
                                  (-math.pi + .2, math.pi + .2), (.25, -.125)):
            with self.subTest(target=target, predicted=predicted):
                self.assertAlmostEqual(score.cosine_score([target], [predicted]), math.cos(target - predicted), places=14)

    def test_unrepresentable_difference_retains_finite_cosine(self):
        # cos(2t) = 2 cos(t)^2 - 1 gives an independent finite oracle without
        # evaluating the overflowing double-angle input.
        for target in (sys.float_info.max, int(1e308)):
            with self.subTest(target_type=type(target).__name__):
                expected = 2.0 * math.cos(target) ** 2 - 1.0
                value = score.cosine_score([target], [-target])
                self.assertTrue(math.isfinite(value))
                self.assertGreaterEqual(value, -1.0)
                self.assertLessEqual(value, 1.0)
                self.assertAlmostEqual(value, expected, places=14)

    def test_paired_and_support_load_updated_scorer_identity(self):
        paired = load("large_angles_paired", IMPLEMENTATIONS / "figure5i-paired-v1" / "compare.py")
        core, support, path = paired._load_components(IMPLEMENTATIONS)
        audited = support._load_scorer(path)
        self.assertEqual(core.cosine_score([1e16], [0.0]), math.cos(1e16))
        self.assertEqual(audited.cosine_score([1e16], [0.0]), math.cos(1e16))


if __name__ == "__main__":
    unittest.main()
