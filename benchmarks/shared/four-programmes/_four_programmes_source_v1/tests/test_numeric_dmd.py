"""Small generated DMD controls; no original/native programme is executed."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import numpy as np


PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / 'current/source/extensions'))
from critical_init.numerics import dmd


class DmdIndexTests(unittest.TestCase):
    def setUp(self):
        time = np.arange(193, dtype=float)
        self.data = np.vstack((np.sin(time / 7) + np.cos(time / 11),
                               np.cos(time / 5) - np.sin(time / 13)))

    def compute(self, valid_times=None, normalization='conventional_pairs', **kwargs):
        arguments = dict(lag=2, ridge=0.25, components=2, block=64,
                         valid_times=valid_times, normalization=normalization)
        arguments.update(kwargs)
        return dmd(self.data, **arguments)

    def assert_same_result(self, actual, expected):
        np.testing.assert_allclose(actual['operator'], expected['operator'], rtol=1e-13, atol=1e-13)
        np.testing.assert_allclose(actual['eigenvalues'], expected['eigenvalues'], rtol=1e-13, atol=1e-13)
        for field in ('pair_count', 'normalization', 'ridge', 'lag', 'interpretation'):
            self.assertEqual(actual[field], expected[field], field)

    def test_rejects_noninteger_elements_before_conversion(self):
        invalid = [
            [0.1, 1.9, 2.0, 3.0], [0.0, 1.0, 2.0],
            [False, True, True], [0, 1, True, 3],
            ['0', '1', '2', '3'], [0, 1, '2', 3],
            [b'0', b'1', b'2'], [0, 1, complex(2, 0)],
            [0, 1, np.float64(2)], [0, 1, np.bool_(True)],
            np.array([False, True]), np.array([0, 1, 2], dtype=float),
            np.array([0, True, 2], dtype=object),
            [float('nan')], [float('inf')],
        ]
        for normalization in ('conventional_pairs', 'held_source_blocks'):
            for values in invalid:
                with self.subTest(normalization=normalization, values=repr(values)):
                    with self.assertRaisesRegex(ValueError, 'integer source time indices'):
                        self.compute(values, normalization)
            with self.subTest(normalization=normalization, values='generator'):
                with self.assertRaisesRegex(ValueError, 'integer source time indices'):
                    self.compute((value for value in [0, 1, 2.5]), normalization)

        class Coercible:
            called = False

            def __int__(self):
                self.called = True
                return 2

        value = Coercible()
        with self.assertRaisesRegex(ValueError, 'integer source time indices'):
            self.compute([0, 1, value])
        self.assertFalse(value.called)

    def test_python_and_numpy_integer_support_preserve_full_result(self):
        support = list(range(128))
        for normalization in ('conventional_pairs', 'held_source_blocks'):
            expected = self.compute(support, normalization)
            alternatives = [
                tuple(support), range(128), set(support),
                (value for value in support),
                np.array(support, dtype=np.int16),
                np.array(support, dtype=np.int64),
                np.array(support, dtype=np.uint64),
                np.array([np.int64(value) for value in support], dtype=object),
            ]
            for values in alternatives:
                with self.subTest(normalization=normalization, type=type(values).__name__):
                    self.assert_same_result(self.compute(values, normalization), expected)

    def test_invalid_indices_are_rejected_before_pca(self):
        with patch('numpy.linalg.eigh', side_effect=AssertionError('PCA must not run')):
            with self.assertRaisesRegex(ValueError, 'integer source time indices'):
                self.compute([0, 1, 2.5], components=1)

    def test_duplicates_and_order_retain_set_support_semantics(self):
        support = [value for value in range(128) if value not in (3, 65, 100)]
        for normalization in ('conventional_pairs', 'held_source_blocks'):
            with self.subTest(normalization=normalization):
                expected = self.compute(support, normalization)
                self.assert_same_result(self.compute(support[::-1] + support, normalization), expected)

    def test_conventional_full_operator_matches_outer_product_reference(self):
        support = {0, 1, 2, 4, 5, 6, 8, 9, 10}
        pairs = [(start, start + 2) for start in sorted(support) if start + 2 in support]
        gram = sum(np.outer(self.data[:, a], self.data[:, a]) for a, _ in pairs) / len(pairs)
        cross = sum(np.outer(self.data[:, b], self.data[:, a]) for a, b in pairs) / len(pairs)
        expected = cross @ np.linalg.inv(gram + 0.25 * np.eye(2))
        actual = self.compute(sorted(support))
        self.assertEqual(actual['pair_count'], len(pairs))
        np.testing.assert_allclose(actual['operator'], expected, rtol=1e-13, atol=1e-13)

    def test_held_full_operator_and_weighting_match_outer_product_reference(self):
        # For this 193-column, lag-2, block-64 control the source windows are
        # [0, 64) and [64, 128); the final partial window remains excluded.
        for support in (None, set(range(193)) - {3, 65, 100}):
            with self.subTest(support='unrestricted' if support is None else 'restricted'):
                windows = [[(a, a + 2) for a in range(start, stop - 2)
                            if support is None or (a in support and a + 2 in support)]
                           for start, stop in ((0, 64), (64, 128))]
                weights = [64 if support is None else len(window) for window in windows]
                gram = sum(weight * sum(np.outer(self.data[:, a], self.data[:, a])
                                        for a, _ in window)
                           for weight, window in zip(weights, windows)) / sum(weights)
                cross = sum(weight * sum(np.outer(self.data[:, b], self.data[:, a])
                                         for a, b in window)
                            for weight, window in zip(weights, windows)) / sum(weights)
                expected = cross @ np.linalg.inv(gram + 0.25 * np.eye(2))
                actual = self.compute(support, 'held_source_blocks')
                self.assertEqual(actual['pair_count'], sum(map(len, windows)))
                np.testing.assert_allclose(actual['operator'], expected, rtol=1e-13, atol=1e-13)

    def test_out_of_range_integer_support_is_still_rejected(self):
        for normalization in ('conventional_pairs', 'held_source_blocks'):
            for values in ([-1, 0, 1], [0, 1, 193], [np.uint64(2**64 - 1)]):
                with self.subTest(normalization=normalization, values=values):
                    with self.assertRaisesRegex(ValueError, 'valid source time indices'):
                        self.compute(values, normalization)

    def test_empty_and_pairless_support_keep_existing_guards(self):
        for normalization, message in (
                ('conventional_pairs', 'no complete DMD pairs'),
                ('held_source_blocks', 'no admitted source DMD block pairs')):
            for support in ([], np.array([], dtype=np.int64), [0], [0, 3, 6]):
                with self.subTest(normalization=normalization, support=repr(support)):
                    with self.assertRaisesRegex(ValueError, message):
                        self.compute(support, normalization)

    def test_truncated_operator_is_unchanged_for_numpy_integer_support(self):
        for normalization in ('conventional_pairs', 'held_source_blocks'):
            with self.subTest(normalization=normalization):
                expected = self.compute(list(range(128)), normalization, components=1)
                actual = self.compute(np.arange(128, dtype=np.int64), normalization, components=1)
                self.assertEqual(actual['operator'].shape, (1, 1))
                self.assert_same_result(actual, expected)


if __name__ == '__main__':
    unittest.main()
