"""Generated controls only: no authentic arrays are opened."""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import numpy as np

from suns2_benchmark.coordinates import (
    original_masks_to_movie_instances,
    movie_instances_to_original_masks,
)


class CoordinateControls(unittest.TestCase):
    def test_asymmetric_movie_to_mat_join(self):
        movie = np.zeros((2, 50, 50), dtype=np.uint8)
        movie[1, 7, 13] = 1
        original = np.zeros((50, 50, 1), dtype=np.uint8)
        original[13, 7, 0] = 1
        aligned = original_masks_to_movie_instances(original)
        self.assertEqual(int((movie[1] * aligned[0]).sum()), 1)
        self.assertEqual(int((movie[1] * original[:, :, 0]).sum()), 0)
        self.assertTrue(np.array_equal(
            movie_instances_to_original_masks(aligned), original))

    def test_instances_preserved_and_empty_output_supported(self):
        original = np.zeros((50, 50, 3), dtype=bool)
        original[2, 9, 0] = True
        original[8, 3, 1] = True
        original[17, 12, 2] = True
        result = original_masks_to_movie_instances(original)
        self.assertEqual(result.shape, (3, 50, 50))
        self.assertEqual(result[1, 3, 8], True)
        empty = np.zeros((50, 50, 0), dtype=bool)
        self.assertEqual(original_masks_to_movie_instances(empty).shape,
                         (0, 50, 50))

    def test_wrong_shape_type_and_values_rejected(self):
        for value in (np.zeros((49, 50, 1), dtype=bool),
                      np.zeros((50, 50, 1), dtype=np.float64),
                      np.full((50, 50, 1), 2, dtype=np.uint8),
                      np.zeros((50, 50, 513), dtype=bool)):
            with self.assertRaises(ValueError):
                original_masks_to_movie_instances(value)
        with self.assertRaises(ValueError):
            movie_instances_to_original_masks(
                np.zeros((1, 50, 49), dtype=bool))


if __name__ == "__main__":
    unittest.main()
