"""Independent arithmetic controls derived before inspecting implementation.

These generated vectors test the figure calculation, not an empirical result.
The source is Fig_2f.ipynb at c1d1788b54c737efe24402e02762eee10da0d0d7.
"""
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import evaluator as subject


class IndependentReferenceControls(unittest.TestCase):
    def setUp(self):
        # After centering, X=(-1,0,1), Y=-X and Z=(1,-2,1)/3.
        # Thus the dot products imply r(X,X)=1, r(X,Y)=-1, r(X,Z)=0.
        self.x = np.array([0.0, 1.0, 2.0])
        self.y = np.array([2.0, 1.0, 0.0])
        self.z = np.array([1.0, 0.0, 1.0])

    def test_literal_mask_cardinalities_and_boundary_difference(self):
        masks = subject.masks()
        self.assertEqual(masks.shape, (6, 46, 46))
        # Off-diagonal: 30^2 - (12^2 + 6^2 + 6^2 + 6^2) = 648.
        self.assertEqual(masks.sum(axis=(1, 2)).tolist(), [648, 9, 9, 144, 9, 36])
        self.assertTrue(masks[0, 0, 35])
        self.assertFalse(masks[0, 0, 36])
        self.assertTrue(masks[1, 36, 36])
        self.assertFalse(masks[1, 33, 33])
        self.assertTrue(masks[2, 26, 26])
        self.assertFalse(masks[2, 23, 23])
        self.assertTrue(masks[4, 17, 19])
        self.assertFalse(masks[4, 16, 17])
        self.assertTrue(masks[5, 40, 45])

    def test_cross_correlation_orientation_and_orthogonal_vector(self):
        near = np.tile(self.x[:, None], (1, 46))
        far = np.tile(self.x[:, None], (1, 46))
        near[:, 1] = self.y
        far[:, 1] = self.z
        actual = subject.population_correlations(near, far)
        np.testing.assert_allclose(actual[:2, :2], [[1, 0], [-1, 0]], atol=1e-14)

    def test_mask_mean_is_all_entries_not_diagonal_or_convenient_region(self):
        near = np.tile(self.x[:, None], (1, 46))
        far = near.copy()
        far[:, 34:37] = self.y[:, None]
        actual = subject.region_means(subject.population_correlations(near, far))
        # Off-diagonal mask contains 48 negative and 600 positive entries:
        # far bins 34/35 each pair with 24 near bins in other grey regions.
        # Far bin36 belongs to Pre-R2 but lies outside the off-diagonal mask.
        expected = [23 / 27, -1, 1, 1, 1, 1]
        np.testing.assert_allclose(actual, expected, atol=1e-14)

    def test_pearson_ignores_positive_scaling_and_constant_offset_per_bin(self):
        near = np.tile(self.x[:, None], (1, 46))
        far = near.copy()
        far[:, 34:37] = self.y[:, None]
        original = subject.population_correlations(near, far)
        offsets = np.arange(46)[None, :]
        actual = subject.population_correlations(2 * near + offsets, 3 * far - offsets)
        np.testing.assert_allclose(actual, original, atol=1e-14)

    def test_undefined_pearson_is_not_converted_to_zero(self):
        near = np.tile(self.x[:, None], (1, 46))
        far = near.copy()
        far[:, 0] = 1
        correlations = subject.population_correlations(near, far)
        self.assertTrue(np.isnan(correlations[:, 0]).all())
        np.testing.assert_allclose(correlations[:, 1:], 1, atol=1e-14)
        means = subject.region_means(correlations)
        self.assertTrue(np.isnan(means[0]))
        self.assertTrue(np.isnan(means[3]))
        np.testing.assert_allclose(means[[1, 2, 4, 5]], 1, atol=1e-14)

    def test_source_interpolation_compresses_internal_missing_days(self):
        values = np.tile(np.array([1.0, np.nan, 1.0, -1.0])[:, None], (1, 6))
        curves, counts = subject.normalize_learning(values)
        np.testing.assert_array_equal(counts, [3] * 6)
        np.testing.assert_allclose(curves[:, 333], 1, atol=1e-14)
        # After deletion, knots are (0,1), (1/2,1), (1,-1),
        # so at 666/999 = 2/3 the ordinate is exactly 1/3.
        np.testing.assert_allclose(curves[:, 666], 1 / 3, atol=1e-14)
        np.testing.assert_allclose(curves[:, [0, -1]], [[1, -1]] * 6, atol=1e-14)

    def test_equivalent_linear_two_and_three_day_curves(self):
        two, _ = subject.normalize_learning(np.tile([[1.0], [-1.0]], (1, 6)))
        three, _ = subject.normalize_learning(np.tile([[1.0], [0.0], [-1.0]], (1, 6)))
        np.testing.assert_allclose(two, three, atol=1e-14)
        np.testing.assert_allclose(two[0], 1 - 2 * np.linspace(0, 1, 1000), atol=1e-14)

    def test_single_valid_day_remains_undefined(self):
        values = np.full((3, 6), np.nan)
        values[1, :] = 0.5
        curves, counts = subject.normalize_learning(values)
        np.testing.assert_array_equal(counts, [1] * 6)
        self.assertTrue(np.isnan(curves).all())

    def test_eleven_animals_receive_equal_weight_and_population_sem(self):
        # Vary native session counts to ensure normalization cannot create
        # more independent observations for long-recorded animals.
        curves = []
        for animal in range(11):
            n_days = 2 + animal
            sign = 1 if animal < 10 else -1
            curve, _ = subject.normalize_learning(np.full((n_days, 6), sign, dtype=float))
            curves.append(curve)
        actual = subject.aggregate_animals(np.array(curves))
        np.testing.assert_allclose(actual['mean'], 9 / 11, atol=1e-14)
        # Population variance=40/121; source SEM=sqrt(40/121)/sqrt(11).
        np.testing.assert_allclose(actual['source_sem_ddof0'], np.sqrt(40 / 1331), atol=1e-14)

    def test_undefined_animal_is_not_silently_removed_from_group(self):
        curves = np.ones((11, 6, 1000))
        curves[3, 2, :] = np.nan
        actual = subject.aggregate_animals(curves)
        self.assertTrue(np.isnan(actual['mean'][2]).all())
        self.assertTrue(np.isnan(actual['source_sem_ddof0'][2]).all())
        np.testing.assert_allclose(actual['mean'][[0, 1, 3, 4, 5]], 1)


if __name__ == '__main__':
    unittest.main()
