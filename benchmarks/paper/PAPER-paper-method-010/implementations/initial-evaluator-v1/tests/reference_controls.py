"""Independent mathematical controls, derived from the pinned source contract.

These generated controls do not establish empirical reproduction, native package
agreement beyond the checked formulas, or scientific qualification.
"""
import importlib.util
from pathlib import Path
import unittest

import numpy as np

_spec = importlib.util.spec_from_file_location(
    "rastermap_reference_control_evaluator", Path(__file__).resolve().parents[1] / "evaluator.py"
)
_evaluator = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_evaluator)
behavior_prediction = _evaluator.behavior_prediction
knn_indices = _evaluator.knn_indices
neighborhood_retention = _evaluator.neighborhood_retention
temporal_split = _evaluator.temporal_split
train_standardize = _evaluator.train_standardize


class IndependentGeometryControls(unittest.TestCase):
    def setUp(self):
        # Unequal distances remove any dependency on a nearest-neighbor tie rule.
        self.reference = np.array([[0.0], [1.0], [4.0], [10.0]])

    def test_exact_nonself_neighbors_have_hand_derived_identities(self):
        expected = np.array([[1], [0], [1], [2]])
        for block in (1, 3, 64):
            np.testing.assert_array_equal(knn_indices(self.reference, 1, block), expected)

    def test_reversal_and_scale_preserve_source_local_score(self):
        reversed_scaled = np.array([[20.0], [18.0], [12.0], [0.0]])
        for k in (1, 2):
            self.assertEqual(
                neighborhood_retention(
                    knn_indices(self.reference, k), knn_indices(reversed_scaled, k)
                ),
                1.0,
            )

    def test_permutation_distinguishes_neighborhood_scales(self):
        # Every closest neighbor changes; every two-neighbor set is preserved.
        shuffled = np.array([[0.0], [4.0], [1.0], [10.0]])
        for k, expected in ((1, 0.0), (2, 1.0)):
            self.assertEqual(
                neighborhood_retention(
                    knn_indices(self.reference, k), knn_indices(shuffled, k)
                ),
                expected,
            )

    def test_self_is_excluded_even_when_all_features_tie(self):
        actual = knn_indices(np.zeros((4, 2)), 2, 1)
        expected = np.array([[1, 2], [0, 2], [0, 1], [0, 1]])
        np.testing.assert_array_equal(actual, expected)


class IndependentTemporalControls(unittest.TestCase):
    def test_training_normalization_does_not_refit_on_test(self):
        activity = np.array([[0.0, 2.0, 100.0, 102.0], [3.0, 3.0, 8.0, 9.0]])
        transformed, receipt = train_standardize(activity, np.array([0, 1]))
        np.testing.assert_array_equal(transformed, [[-1, 1, 99, 101], [0, 0, 5, 6]])
        self.assertEqual(receipt["mean"], [1.0, 3.0])
        self.assertEqual(receipt["scale"], [1.0, 1.0])
        self.assertEqual(receipt["training_constant_neuron_count"], 1)
        changed = activity.copy()
        changed[:, 2:] = [[-10000, 20000], [30000, -40000]]
        transformed_changed, changed_receipt = train_standardize(changed, np.array([0, 1]))
        np.testing.assert_array_equal(transformed_changed[:, :2], transformed[:, :2])
        self.assertEqual(changed_receipt, receipt)

    def test_chronological_blocks_have_both_sided_purge_and_full_accounting(self):
        split = temporal_split(100, 3)
        np.testing.assert_array_equal(split["train"], np.arange(57))
        np.testing.assert_array_equal(split["validation"], np.arange(63, 77))
        np.testing.assert_array_equal(split["test"], np.arange(83, 100))
        np.testing.assert_array_equal(split["embargo"], [57, 58, 59, 60, 61, 62, 77, 78, 79, 80, 81, 82])
        np.testing.assert_array_equal(np.sort(np.concatenate(list(split.values()))), np.arange(100))
        self.assertGreater(split["validation"][0] - split["train"][-1], 2 * 3)
        self.assertGreater(split["test"][0] - split["validation"][-1], 2 * 3)

    def test_purge_cannot_create_empty_or_too_short_assessment_block(self):
        for samples, gap in ((30, 3), (100, 10), (100, -1), (100, 1.5)):
            with self.assertRaises(ValueError):
                temporal_split(samples, gap)


class IndependentBehaviorMetricControls(unittest.TestCase):
    def test_prospective_centered_r2_is_explicitly_not_source_uncentered_ve(self):
        split = temporal_split(30, 1)
        activity = np.zeros((1, 30))
        activity[0, split["test"]] = [1, 2, 3, 4, 5]
        # A zero behavior signal and zero training target produce a zero forecast.
        # SSE=55, centered test SST=10, hence centered R2=-4.5. The source
        # notebook's uncentered denominator would be55 and would report VE=0.
        report = behavior_prediction(activity, np.zeros((30, 1)), [0], split, 1)
        self.assertEqual(report["metric"], "centered_test_r2")
        self.assertEqual(report["direction"], "behavior_to_sorted_superneurons")
        self.assertEqual(report["per_group_r2"], [-4.5])
        self.assertEqual(report["macro_r2"], -4.5)
        source_uncentered_ve = 1.0 - 55.0 / 55.0
        self.assertEqual(source_uncentered_ve, 0.0)
        self.assertNotEqual(report["macro_r2"], source_uncentered_ve)

    def test_constant_test_target_remains_undefined(self):
        split = temporal_split(30, 1)
        report = behavior_prediction(np.ones((1, 30)), np.zeros((30, 1)), [0], split, 1)
        self.assertEqual(report["per_group_r2"], [None])
        self.assertIsNone(report["macro_r2"])
        self.assertEqual(report["undefined_constant_test_groups"], 1)


if __name__ == "__main__":
    unittest.main()
