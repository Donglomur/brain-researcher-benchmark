"""Generated numerical regressions; no source archive or participant data."""
from decimal import Decimal, localcontext
from fractions import Fraction
import importlib.util
import math
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("root003_centering_endpoint", HERE / "endpoint.py")
e = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = e
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
    def test_near_offset_affine_correlation_and_sign(self):
        x = [1e16, 1e16 + 2, 1e16 + 8]
        for sign in (1., -1.):
            y = [sign * v for v in (0., 1., 4.)]
            self.assertAlmostEqual(e.pearson(x, y)["r"], sign, delta=2e-15)

    def test_near_offset_non_affine_matches_independent_exact_oracle(self):
        x = [1e16, 1e16 + 2, 1e16 + 8, 1e16 + 12]
        y = [2., 9., -3., 4.]
        expected = exact_r(x, y)
        for order in ([0, 1, 2, 3], [3, 1, 0, 2]):
            result = e.pearson([x[i] for i in order], [y[i] for i in order])
            self.assertAlmostEqual(result["r"], expected, delta=2e-15)
            self.assertEqual(result["n_items"], 4)
            self.assertIsNone(result["undefined_reason"])

    def test_extreme_subnormal_and_undefined_support_preserved(self):
        maximum = sys.float_info.max
        tiny = math.ulp(0.)
        for x, y in (([-maximum, 0., maximum], [1., 0., -1.]),
                     ([tiny, 2 * tiny, 5 * tiny], [0., 1., 4.])):
            self.assertAlmostEqual(e.pearson(x, y)["r"], exact_r(x, y), delta=2e-15)
        self.assertEqual(e.pearson([3.] * 3, [0., 1., 4.])["undefined_reason"],
                         "constant_prediction")
        self.assertIsNone(e.pearson([3.] * 3, [0., 1., 4.])["r"])
        for bad in (float("nan"), float("inf")):
            with self.assertRaises(e.InvalidPanel):
                e.pearson([0., bad, 4.], [0., 1., 4.])


if __name__ == "__main__":
    unittest.main(verbosity=2)
