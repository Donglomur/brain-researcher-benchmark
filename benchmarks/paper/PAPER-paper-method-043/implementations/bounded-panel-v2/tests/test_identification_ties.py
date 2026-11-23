"""Generated exact-feature ties; no images, weights or fixture files."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np

spec = importlib.util.spec_from_file_location('bounded_tie_panel', Path(__file__).resolve().parents[1] / 'evaluator.py')
ev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ev)


class Features:
    def __init__(self, values):
        self.values = values

    def read(self, key, rows):
        if len(rows) > ev.FEATURE_BLOCK:
            raise AssertionError('feature read exceeds block bound')
        return self.values[rows]


class FortranFeatures(Features):
    def read(self, key, rows):
        return np.asfortranarray(super().read(key, rows))


class IdentificationTies(unittest.TestCase):
    def test_identical_real_rows_never_earn_success_at_short_final_block(self):
        for n, width in [(17, 7), (17, 129), (33, 513)]:
            with self.subTest(n=n, width=width):
                rng = np.random.default_rng(43)
                real = np.tile(rng.normal(size=width), (n, 1))
                predicted = rng.normal(size=(n, width))
                scores = ev.identification(Features(real), Features(predicted), 'clip', list(range(n)))
                np.testing.assert_array_equal(scores, np.zeros(n))

    def test_strict_ties_preserve_wins_and_denominator_across_partitions(self):
        n = 35
        base = np.random.default_rng(43).normal(size=129)
        real = np.tile(base, (n, 1))
        real[1::2] *= -1
        predicted = np.tile(base, (n, 1))
        # Even-index matches beat precisely the 17 opposite real rows;
        # odd-index matches beat none. Every identical row is a failed tie.
        expected = np.zeros(n)
        expected[::2] = 17 / 34
        for block in (1, 7, 16):
            with self.subTest(block=block), patch.object(ev, 'FEATURE_BLOCK', block):
                actual = ev.identification(Features(real), Features(predicted), 'clip', list(range(n)))
                np.testing.assert_array_equal(actual, expected)

    def test_noncontiguous_features_keep_the_same_strict_ties(self):
        rng = np.random.default_rng(43)
        base = rng.normal(size=258)
        real = np.tile(base, (17, 1))[:, ::2]
        predicted = rng.normal(size=(17, 258))[:, ::2]
        self.assertFalse(real.flags.c_contiguous)
        for bundle_type in (Features, FortranFeatures):
            for block in (1, 16):
                with self.subTest(bundle=bundle_type.__name__, block=block), patch.object(ev, 'FEATURE_BLOCK', block):
                    r, p = bundle_type(real), bundle_type(predicted)
                    self.assertTrue(ev._unit_block(r, 'clip', [0]).flags.c_contiguous)
                    np.testing.assert_array_equal(ev.identification(r, p, 'clip', list(range(17))), np.zeros(17))


if __name__ == '__main__':
    unittest.main()
