"""Generated Pearson/identification regressions; no images, files or model runs."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ROOT = Path(__file__).resolve().parents[1]
core = load('stable_neuropictor_core', ROOT / 'evaluator.py')
bounded = load('stable_neuropictor_bounded',
               ROOT.parent / 'bounded-panel-v2' / 'evaluator.py')


class Features:
    def __init__(self, values):
        self.values = values

    def read(self, key, rows):
        if len(rows) > bounded.FEATURE_BLOCK:
            raise AssertionError('feature read exceeds the existing block bound')
        return self.values[rows]


class StableNormalization(unittest.TestCase):
    def test_exact_translation_preserves_pearson_and_distance(self):
        real = np.array([[0., 0., 1.], [0., 1., 1.]])
        offset = np.array([[2.**52], [-2.**52]])
        translated = real + offset
        np.testing.assert_array_equal(translated - offset, real)
        correlation = core.paired_correlation(real, translated)
        np.testing.assert_allclose(correlation, [1., 1.], rtol=0, atol=2e-15)
        np.testing.assert_allclose(1 - correlation, [0., 0.], rtol=0, atol=2e-15)
        # Independent centered vectors [-1,-1,2] and [-2,1,1] give r=1/2.
        np.testing.assert_allclose(core.paired_correlation(real, translated[::-1]),
                                   [.5, .5], rtol=0, atol=2e-15)

    def test_translated_equivalent_rows_remain_failed_identification_ties(self):
        x = np.array([0., 0., 1.])
        real = np.stack([x, x + 2.**52])
        predicted = np.stack([x, x])
        # Pearson ignores each row's offset: every real row ties with the
        # matching row for every prediction. Strict comparison awards no wins.
        for block in (1, 2, 16):
            with self.subTest(block=block):
                np.testing.assert_array_equal(
                    core.two_way_identification(real, predicted, block_size=block),
                    [0., 0.])
                with patch.object(bounded, 'FEATURE_BLOCK', block):
                    np.testing.assert_array_equal(
                        bounded.identification(Features(real), Features(predicted),
                                               'clip', [0, 1]), [0., 0.])

    def test_extreme_and_subnormal_rows_remain_finite_and_signed(self):
        largest = np.finfo(np.float64).max
        tiny = np.nextafter(0., 1.)
        rows = np.array([[-largest, 0., largest],
                         [tiny, tiny, 2*tiny],
                         [0., 0., 1.]])
        # Only the first row needs half-differences. Applying that fallback to
        # every row would erase representable subnormal variation in row two.
        with np.errstate(over='raise', invalid='raise', divide='raise'):
            normalized = core._unit_rows(rows)
            self.assertTrue(np.isfinite(normalized).all())
            np.testing.assert_allclose(core.paired_correlation(rows, rows),
                                       np.ones(3), rtol=0, atol=2e-15)
            np.testing.assert_allclose(core.paired_correlation(rows, -rows),
                                       -np.ones(3), rtol=0, atol=2e-15)

    def test_constant_and_nonfinite_rows_still_fail(self):
        for value in (0., .1, np.finfo(np.float64).max,
                      np.nextafter(0., 1.), np.inf, np.nan):
            with self.subTest(value=value), self.assertRaises(core.ValidationError):
                core._unit_rows(np.full((1, 3), value))

    def test_strided_inputs_are_not_modified(self):
        storage = np.array([[0., 17., 0., 18., 1., 19.],
                            [2.**52, 20., 2.**52, 21., 2.**52+1., 22.]])
        before = storage.copy()
        rows = storage[:, ::2]
        self.assertFalse(rows.flags.c_contiguous)
        np.testing.assert_allclose(core.paired_correlation(rows, rows[::-1]),
                                   [1., 1.], rtol=0, atol=2e-15)
        np.testing.assert_array_equal(storage, before)


if __name__ == '__main__':
    unittest.main()
