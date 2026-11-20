"""Focused finite-offset correlation regressions; generated inputs, no model run."""
import importlib.util
from fractions import Fraction
import math
from pathlib import Path
import sys
import unittest


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def exact_correlation(a, b):
    """Independent exact-rational covariance of the supplied binary floats."""
    a, b = [Fraction(float(x)) for x in a], [Fraction(float(x)) for x in b]
    am, bm = sum(a) / len(a), sum(b) / len(b)
    a, b = [x - am for x in a], [x - bm for x in b]
    cross = sum(x * y for x, y in zip(a, b))
    energy = sum(x*x for x in a) * sum(x*x for x in b)
    if not energy:
        return None
    return (-1.0 if cross < 0 else 1.0) * math.sqrt(float(cross*cross / energy))


HERE = Path(__file__).parent
d = load("paper020_feature_decoding_v2_numerics", HERE / "decoding.py")
old = load("paper020_feature_decoding_v1_numerics", HERE.parent / "feature-decoding-v1/decoding.py")


class FiniteOffsetCorrelationTests(unittest.TestCase):
    def test_near_constant_offset_keeps_exact_positive_and_negative_correlation(self):
        predicted = [1.0, 1.0, math.nextafter(1.0, math.inf)]
        actual = [0.0, 0.0, 1.0]
        self.assertGreater(abs(old.feature_correlation(predicted, actual).value - 1.0), .01)
        for values in (predicted, [-x for x in predicted]):
            result = d.feature_correlation(values, actual)
            self.assertEqual(result.state, "defined")
            self.assertAlmostEqual(result.value, exact_correlation(values, actual), places=14)

    def test_finite_extremes_and_coordinate_permutations_match_rational_oracle(self):
        large = 1e308
        step = math.ulp(large)
        pairs = [
            ([large, large + step, large + 3*step], [0., 1., 3.]),
            ([-large, -large - step, -large - 3*step], [0., 1., 3.]),
            ([-large, 0., large], [-5., 1., 4.]),
            ([5e-324, 5e-324, 1e-323], [0., 0., 1.]),
        ]
        for predicted, actual in pairs:
            expected = exact_correlation(predicted, actual)
            for order in ((0, 1, 2), (2, 0, 1), (1, 2, 0)):
                p, a = [predicted[i] for i in order], [actual[i] for i in order]
                with self.subTest(predicted=p, actual=a):
                    self.assertAlmostEqual(d.feature_correlation(p, a).value, expected, places=14)
        self.assertEqual(d.feature_correlation([large]*3, [0., 1., 2.]).state, "constant_decoded")

    def test_complete_scoring_uses_corrected_kernel_without_changing_fold_axes(self):
        roster = d.FaceRoster(tuple(f"u{i}" for i in range(1000)), tuple(f"f{i}" for i in range(36)))
        positive = (1., 1., math.nextafter(1., math.inf))
        negative = tuple(-x for x in positive)
        predictions = d.DecodingPredictions(roster.unfamiliar, (positive,)*1000,
                                            roster.familiar, ((negative,)*36,)*1000)
        targets = {identity: (0., 0., 1.) for identity in roster.all_faces}
        result = d.score_feature_correlations(roster, predictions, targets)
        self.assertEqual(len(result.unfamiliar), 1000)
        self.assertEqual(len(result.familiar_by_fold), 1000)
        self.assertTrue(all(s.state == "defined" and abs(s.value - 1.) < 1e-14 for s in result.unfamiliar))
        self.assertTrue(all(len(row) == 36 and all(s.state == "defined" and abs(s.value + 1.) < 1e-14
                                                for s in row) for row in result.familiar_by_fold))


if __name__ == "__main__":
    unittest.main()
