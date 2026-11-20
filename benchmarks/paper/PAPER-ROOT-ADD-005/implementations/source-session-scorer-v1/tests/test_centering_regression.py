"""Generated numerical controls for source-session Pearson maps only."""
from decimal import Decimal, localcontext
from fractions import Fraction
import importlib.util
import math
from pathlib import Path
import sys
import unittest

import numpy as np

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("root005_centering_scorer", HERE / "scorer.py")
e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)

def exact_r(x, y):
    a = [Fraction.from_float(float(v)) for v in x]
    b = [Fraction.from_float(float(v)) for v in y]
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    a, b = [v - ma for v in a], [v - mb for v in b]
    cross = sum(u * v for u, v in zip(a, b))
    aa, bb = sum(v * v for v in a), sum(v * v for v in b)
    with localcontext() as context:
        context.prec = 80
        def dec(value):
            return Decimal(value.numerator) / Decimal(value.denominator)
        return float(dec(cross) / (dec(aa) * dec(bb)).sqrt())


class CenteringRegression(unittest.TestCase):
    def test_near_offset_columns_match_exact_oracle_and_sign(self):
        x = [1e16, 1e16 + 2, 1e16 + 8, 1e16 + 12]
        y = [2., 9., -3., 4.]
        affine = [0., 1., 4., 6.]
        observed = np.column_stack((x, x, x))
        predicted = np.column_stack((y, affine, -np.asarray(affine)))
        expected = np.array([exact_r(x, y), 1., -1.])
        for order in ([0, 1, 2, 3], [3, 1, 0, 2]):
            np.testing.assert_allclose(e.pearson_columns(observed[order], predicted[order]),
                                       expected, rtol=0, atol=2e-15)

    def test_mixed_extreme_and_subnormal_columns_are_independent(self):
        maximum, tiny = sys.float_info.max, math.ulp(0.)
        observed = np.column_stack(([-maximum, 0., maximum], [tiny, 2*tiny, 5*tiny],
                                    [3., 3., 3.]))
        predicted = np.column_stack(([1., 0., -1.], [0., 1., 4.], [0., 1., 4.]))
        result = e.pearson_columns(observed, predicted)
        np.testing.assert_allclose(result[:2], [-1., 1.], rtol=0, atol=2e-15)
        self.assertTrue(np.isnan(result[2]))
        for bad in (float("nan"), float("inf")):
            broken = observed.copy()
            broken[0, 1] = bad
            with self.assertRaises(ValueError):
                e.pearson_columns(broken, predicted)

    def test_full_twelve_fold_maps_keep_signed_delta_and_support(self):
        sessions = np.repeat([f"s{i:02}" for i in range(12)], 3)
        observed = np.tile([1e16, 1e16 + 2, 1e16 + 8], 12)[:, None]
        author = np.tile([0., 1., 4.], 12)[:, None]
        result = e.score_maps(observed, author, -author, sessions)
        np.testing.assert_allclose(result["author_mean_fold_pearson_r"], [1.], atol=2e-15)
        np.testing.assert_allclose(result["candidate_mean_fold_pearson_r"], [-1.], atol=2e-15)
        np.testing.assert_allclose(result["paired_mean_fold_delta_r"], [-2.], atol=4e-15)
        self.assertEqual(result["author_defined_folds_per_voxel"], [12])
        self.assertEqual(result["candidate_defined_folds_per_voxel"], [12])
        self.assertEqual(len(result["candidate_fold_pearson_r"]), 12)


if __name__ == "__main__":
    unittest.main(verbosity=2)
