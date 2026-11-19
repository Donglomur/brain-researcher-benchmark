"""Portable generated controls; no original data or author source is needed."""
import copy
import unittest

import numpy as np

from inner_preparation import Scaling, iter_inner_preparation, source_inner_indices


def fixture(n=23):
    row = np.arange(n, dtype=np.float64)[:, None]
    col = np.arange(78, dtype=np.float64)[None, :]
    y = ((row + 1) * ((col % 9) - 4) + ((row * row + col) % 11)) / 7
    y[:, 0] = 3.5
    z = np.column_stack((row[:, 0] / 3, (row[:, 0] % 5) - 2,
                         row[:, 0] ** 2 / 13, np.full(n, -4.0)))
    ids = tuple(f"outer-fit/original-row-{3*i+2}" for i in range(n))
    layout = {
        "neural": [{"id": f"unit-{j:03d}", "unit": "declared-neural-unit"}
                   for j in range(78)],
        "behavior": [{"id": k, "unit": unit} for k, unit in zip(
            ["position_x", "position_y", "velocity_x", "velocity_y"],
            ["mm", "mm", "mm/s", "mm/s"])],
    }
    return y, z, ids, layout

class InnerPreparationControls(unittest.TestCase):

    def test_selection_perturbation_cannot_change_its_training_transform(self):
        y, z, ids, layout = fixture()
        sc = Scaling(True, True, True, True)
        original = next(iter_inner_preparation(y, z, ids, layout, scaling=sc))
        yc, zc = y.copy(), z.copy()
        yc[list(original.selection_indices)] += 1e6
        zc[list(original.selection_indices)] -= 1e6
        changed = next(iter_inner_preparation(yc, zc, ids, layout, scaling=sc))
        for field in ("y_train", "z_train", "y_mean", "y_std", "z_mean", "z_std"):
            np.testing.assert_array_equal(getattr(original, field), getattr(changed, field))
        self.assertFalse(np.array_equal(original.y_selection_scaled, changed.y_selection_scaled))

    def test_sample_sd_constant_channels_and_raw_selection_are_preserved(self):
        y, z, ids, layout = fixture()
        got = next(iter_inner_preparation(y, z, ids, layout,
                                         scaling=Scaling(False, True, False, True)))
        train = y[list(got.train_indices), :]
        self.assertAlmostEqual(got.y_std[1], np.std(train[:, 1], ddof=1))
        self.assertNotAlmostEqual(got.y_std[1], np.std(train[:, 1], ddof=0))
        self.assertEqual(got.y_std[0], 0)
        self.assertEqual(got.z_std[3], 0)
        np.testing.assert_array_equal(got.y_train[:, 0], np.zeros(train.shape[0]))
        np.testing.assert_array_equal(got.y_selection_raw, y[list(got.selection_indices)])
        self.assertTrue(np.all(got.y_selection_raw[:, 0] == 3.5))

    def test_simultaneous_neural_column_permutation_retains_identity_and_math(self):
        y, z, ids, layout = fixture()
        permutation = np.arange(78)[::-1]
        permuted_layout = copy.deepcopy(layout)
        permuted_layout["neural"] = [layout["neural"][i] for i in permutation]
        sc = Scaling(True, True, True, True)
        a = next(iter_inner_preparation(y, z, ids, layout, scaling=sc))
        b = next(iter_inner_preparation(y[:, permutation], z, ids, permuted_layout, scaling=sc))
        np.testing.assert_allclose(b.y_train, a.y_train[:, permutation], rtol=2e-14, atol=2e-14)
        self.assertEqual(b.channel_layout, permuted_layout)
        self.assertEqual(b.train_sample_ids, a.train_sample_ids)

    def test_profile_refuses_invalid_support_without_dropping_rows(self):
        y, z, ids, layout = fixture()
        sc = Scaling(True, True, True, True)
        broken_y = y.copy(); broken_y[0, 1] = np.nan
        bad_layout = copy.deepcopy(layout); bad_layout["neural"][1] = bad_layout["neural"][0]
        bad_behavior = copy.deepcopy(layout); bad_behavior["behavior"].reverse()
        cases = [(broken_y, z, ids, layout), (y, z[:-1], ids, layout),
                 (y.astype(np.float32), z, ids, layout), (y, z, ids[:-1], layout),
                 (y, z, (ids[0],) * len(ids), layout), (y, z, ids, bad_layout),
                 (y, z, ids, bad_behavior), (y[:3], z[:3], ids[:3], layout)]
        for number, args in enumerate(cases):
            with self.subTest(case=number):
                with self.assertRaises(ValueError):
                    list(iter_inner_preparation(*args, scaling=sc))
        with self.assertRaises(ValueError):
            Scaling(1, True, True, True)
        with self.assertRaises(ValueError):
            list(iter_inner_preparation(y, z, ids, layout, scaling=None))

    def test_odd_tail_coverage_and_complement(self):
        first, second = source_inner_indices(23)
        self.assertEqual(first, (tuple(range(12, 23)), tuple(range(12))))
        self.assertEqual(second, (tuple(range(12)), tuple(range(12, 23))))
        for n in (4, 5, 20, 21, 39):
            folds = source_inner_indices(n)
            self.assertEqual(sorted(folds[0][1] + folds[1][1]), list(range(n)))
            for train, selection in folds:
                self.assertGreaterEqual(len(train), 2)
                self.assertFalse(set(train) & set(selection))
                self.assertEqual(sorted(train + selection), list(range(n)))


if __name__ == "__main__":
    unittest.main()

