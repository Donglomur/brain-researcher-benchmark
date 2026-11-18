"""Generated complete-coordinate arithmetic controls; no study data/model run."""
from decimal import Decimal, localcontext
from pathlib import Path
import sys
import unittest
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'neural-080' / 'full-generalization' / 'source'))
from stable_scale import fit_target_scale, TARGET_WIDTH
import legacy_rounded_scale as predecessor


class Owner:
    def __init__(self):
        self.bytes = 0

    def reserve(self, name, amount):
        assert name == 'retained_bytes' and type(amount) is int and amount >= 0
        self.bytes += amount


def matrix(values):
    return np.broadcast_to(np.asarray(values, dtype=np.float64)[:, None],
                           (len(values), TARGET_WIDTH)).copy()


def oracle(values, weights):
    with localcontext() as ctx:
        ctx.prec = 150
        x = [Decimal(float(v)) for v in values]
        w = [Decimal(float(v)) for v in weights]
        total = sum(w)
        mu = sum(a*b for a, b in zip(x, w)) / total
        variance = sum(b*(a-mu)**2 for a, b in zip(x, w)) / total
        return float(mu), float(variance.sqrt())


class Tests(unittest.TestCase):
    def test_adjacent_nonconstant_values_expose_predecessor_score_bias(self):
        values = [.1, np.nextafter(.1, np.inf)]
        x, weights = matrix(values), np.array([.5, .5])
        expected_mean, expected_sigma = oracle(values, weights)
        old, _ = predecessor.fit_target_scale(x, weights, Owner())
        new, standardized = fit_target_scale(x, weights, Owner())
        self.assertAlmostEqual(float(old.sigma[0] / expected_sigma), np.sqrt(2))
        np.testing.assert_array_equal(new.sigma, np.full(TARGET_WIDTH, expected_sigma))
        np.testing.assert_array_equal(new.mean, np.full(TARGET_WIDTH, expected_mean))
        # One-ULP original-unit residual: old denominator halves the squared risk.
        error = values[1] - values[0]
        self.assertAlmostEqual((error / old.sigma[0])**2, 2.0)
        self.assertEqual((error / new.sigma[0])**2, 4.0)
        # The mean rounds to one source value; preserve actual raw-unit roundtrip.
        np.testing.assert_array_equal(standardized * new.sigma + new.mean, x)
        np.testing.assert_array_equal(weights @ standardized, np.ones(TARGET_WIDTH))

    def test_unequal_weights_match_independent_decimal_moments(self):
        lo = .1
        values = [lo, np.nextafter(lo, np.inf), np.nextafter(np.nextafter(lo, np.inf), np.inf)]
        weights = np.array([.125, .25, .625])
        expected_mean, expected_sigma = oracle(values, weights)
        scale, _ = fit_target_scale(matrix(values), weights, Owner())
        np.testing.assert_array_equal(scale.mean, np.full(TARGET_WIDTH, expected_mean))
        np.testing.assert_allclose(scale.sigma, expected_sigma, rtol=2e-15, atol=0)

    def test_changes_of_units_preserve_standardized_residual_risk(self):
        weights = np.array([.125, .375, .5])
        base = np.array([-2., 1., 3.])
        values = matrix(base)
        scale, _ = fit_target_scale(values, weights, Owner())
        expected = ((values - 0.25) / scale.sigma)**2
        for factor in (1e-200, 1e-6, 1., 1e200):
            with self.subTest(factor=factor):
                changed, _ = fit_target_scale(values * factor, weights, Owner())
                actual = ((values * factor - 0.25 * factor) / changed.sigma)**2
                np.testing.assert_allclose(actual, expected, rtol=5e-15, atol=0)

    def test_ordinary_full_basis_agrees_and_input_is_not_mutated(self):
        x = np.random.default_rng(80).normal(size=(7, TARGET_WIDTH))
        before = x.copy()
        weights = np.array([1, 2, 3, 4, 5, 6, 7], dtype=np.float64)
        weights /= weights.sum()
        old, old_z = predecessor.fit_target_scale(x, weights, Owner())
        owner = Owner()
        new, new_z = fit_target_scale(x, weights, owner)
        np.testing.assert_allclose(new.mean, old.mean, rtol=0, atol=2e-15)
        np.testing.assert_allclose(new.sigma, old.sigma, rtol=2e-15, atol=0)
        np.testing.assert_allclose(new_z, old_z, rtol=0, atol=2e-14)
        np.testing.assert_array_equal(x, before)
        self.assertFalse(new.mean.flags.writeable)
        self.assertFalse(new.sigma.flags.writeable)
        self.assertGreater(owner.bytes, x.nbytes)

    def test_one_bad_coordinate_refuses_complete_case(self):
        x, w = matrix([0., 1., 2.]), np.array([.25, .25, .5])
        for value in (.1, np.nan, np.inf):
            with self.subTest(value=value):
                bad = x.copy()
                bad[:, 9021] = value
                with self.assertRaises(ValueError):
                    fit_target_scale(bad, w, Owner())

    def test_invalid_weights_and_incomplete_basis_refuse(self):
        x = matrix([0., 1.])
        for w in (np.array([0., 1.]), np.array([-.5, 1.5]),
                  np.array([.5, np.nan]), np.array([1., 1.]), np.array([1.])):
            with self.subTest(weights=w):
                with self.assertRaises(ValueError):
                    fit_target_scale(x, w, Owner())
        with self.assertRaises(ValueError):
            fit_target_scale(x[:, :-1], np.array([.5, .5]), Owner())


if __name__ == '__main__':
    unittest.main(verbosity=2)
