import copy
import importlib.util
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location(
    "sae_imputation", Path(__file__).with_name("sae_imputation.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
impute = module.impute_sae_observations


class SAEControlInputs(unittest.TestCase):
    def test_zero_control_keeps_all_times_and_observed_features(self):
        rows = [None, [2.0, -1.0], None, [8.0, 3.0], None]
        before = copy.deepcopy(rows)
        result = impute(rows, "01010", "sae_zero_smooth", 2)
        self.assertEqual(result, [[0, 0], [2, -1], [0, 0], [8, 3], [0, 0]])
        self.assertEqual(rows, before)
        self.assertIsNot(result[1], rows[1])

    def test_full_gap_uses_two_available_endpoints_not_interpolation(self):
        rows = [[2.0, -4.0], None, None, None, [10.0, 8.0]]
        before = copy.deepcopy(rows)
        result = impute(rows, "10001", "sae_average_smooth", 2)
        self.assertEqual(result, [[2, -4], [6, 2], [6, 2], [6, 2], [10, 8]])
        self.assertEqual(rows, before)
        self.assertIsNot(result[1], result[2])

    def test_distinct_gaps_use_nearest_available_not_global_endpoints(self):
        rows = [[0.0], None, [4.0], None, None, [10.0]]
        self.assertEqual(impute(rows, "101001", "sae_average_smooth", 1),
                         [[0], [2], [4], [7], [7], [10]])

    def test_full_observation_preserves_each_control(self):
        rows = [[1.0, -2.0], [0.0, 4.0]]
        for method in ("sae_zero_smooth", "sae_average_smooth"):
            with self.subTest(method=method):
                result = impute(rows, "11", method, 2)
                self.assertEqual(result, rows)
                self.assertIsNot(result, rows)
                self.assertIsNot(result[0], rows[0])

    def test_unresolved_one_sided_and_empty_neighbor_support_refuse(self):
        for rows, mask in (([None, [2]], "01"), ([[2], None], "10"),
                           ([None, None], "00")):
            with self.subTest(mask=mask):
                with self.assertRaises(module.UnresolvedBoundaryError):
                    impute(rows, mask, "sae_average_smooth", 1)
        self.assertEqual(impute([None, None], "00", "sae_zero_smooth", 2),
                         [[0, 0], [0, 0]])

    def test_original_dropped_values_cannot_enter_either_control(self):
        for method in ("sae_zero_smooth", "sae_average_smooth"):
            with self.subTest(method=method):
                with self.assertRaisesRegex(module.ImputationError, "absent"):
                    impute([[1], [999], [3]], "101", method, 1)

    def test_mask_and_observation_support_fail_without_coercion(self):
        cases = [([[1]], "", "sae_zero_smooth", 1),
                 ([[1]], "x", "sae_zero_smooth", 1),
                 ([[1]], "1", "other", 1),
                 ([[1]], "1", "sae_zero_smooth", True),
                 ([[True]], "1", "sae_zero_smooth", 1),
                 ([[float("nan")]], "1", "sae_zero_smooth", 1),
                 ([[float("inf")]], "1", "sae_zero_smooth", 1),
                 ([[1, 2]], "1", "sae_zero_smooth", 1),
                 ([None], "1", "sae_zero_smooth", 1)]
        for args in cases:
            with self.subTest(args=args):
                with self.assertRaises(module.ImputationError):
                    impute(*args)

    def test_midpoint_of_finite_extremes_stays_finite(self):
        self.assertEqual(impute([[1e308], None, [1e308]], "101",
                                "sae_average_smooth", 1),
                         [[1e308], [1e308], [1e308]])


if __name__ == "__main__":
    unittest.main(verbosity=2)
