"""Generated reduced-feature controls; no authentic arrays or decomposition fits.

Full 511-row, 20×5 / 20×2 schedules are retained. Only the isolated legacy
producer's source-window adapter is replaced in parity tests, permitting three
generated features. The public audited API still requires all 182 features.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest
from unittest import mock

import numpy as np


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("audited_producer_generated_test", HERE / "audited_producer.py")
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)
old_spec = importlib.util.spec_from_file_location("independent_legacy_generated_test", a.PRODUCER_PATH)
old = importlib.util.module_from_spec(old_spec)
old_spec.loader.exec_module(old)


def fixture():
    rng = np.random.RandomState(193)
    x = rng.normal(size=(80, 511, 3))
    full = np.empty((150, 511, 2))
    initial = rng.normal(size=(511, 2))
    increment = x[:-1] @ np.array([[0.4, -0.2], [0.1, 0.3], [-0.4, 0.7]]) + np.array([0.1, -0.2])
    increment += 0.05 * rng.normal(size=increment.shape)
    y = a.e.integrate_displacements(increment, initial)
    full[:65] = initial
    full[65:145] = y
    full[145:] = y[-1]
    angles = (np.arange(511) % 3).astype(np.float64)
    return x, y, full, angles


class DigestAndBounds(unittest.TestCase):
    def test_shape_dtype_value_framing_and_noncontiguous_order(self):
        value = np.arange(24, dtype=np.float64).reshape(4, 6)[:, ::2]
        record = a.array_digest(value)
        header = {k: record[k] for k in ("shape", "dtype", "bytes")}
        expected = hashlib.sha256(json.dumps(header, sort_keys=True, separators=(",", ":")).encode() + b"\n" + value.tobytes(order="C")).hexdigest()
        self.assertEqual(record["sha256"], expected)
        self.assertEqual(record, a.array_digest(np.array(value, order="F")))
        self.assertNotEqual(record["sha256"], a.array_digest(value.reshape(-1))["sha256"])
        self.assertNotEqual(record["sha256"], a.array_digest(value.astype(np.float32))["sha256"])
        changed = value.copy(); changed[0, 0] = 1
        self.assertNotEqual(record["sha256"], a.array_digest(changed)["sha256"])
        for bad in [np.array([], dtype=float), np.array([np.nan]), np.array([np.inf]), np.array([True]), np.array(["1"]), np.array([1], dtype=object)]:
            with self.assertRaises(ValueError):
                a.array_digest(bad)

    def test_public_original_shape_required_before_fit(self):
        _, _, full, angles = fixture()
        small = np.zeros((150, 511, 3))
        with mock.patch.object(a.p, "fit_velocity", side_effect=AssertionError("must not fit")):
            with self.assertRaisesRegex(ValueError, "full source layouts"):
                a.repeated_decoding(small, full, recipe="source_code_ridge1")
            with self.assertRaisesRegex(ValueError, "full source layouts"):
                a.condition_average_control(small, full, angles, recipe="source_code_ridge1")

    def test_invalid_support_and_recipe_refused_before_fit(self):
        x, y, full, _ = fixture()
        with mock.patch.object(a.p, "fit_velocity", side_effect=AssertionError("must not fit")):
            for train, test in [([0, 1], [1, 2]), ([0, 0], [2, 3]), ([0, 511], [2, 3]), ([0.0, 1.0], [2, 3]), ([True, False], [2, 3])]:
                with self.assertRaises(ValueError):
                    a.decoder_fold(x, y, train, test, recipe="source_code_ridge1")
            with self.assertRaisesRegex(ValueError, "explicit"):
                a._repeated_windowed(x, y, full, recipe="invented")
            broken = full.copy(); broken[65, 0, 0] += 1
            with self.assertRaisesRegex(ValueError, "scoring movement"):
                a._repeated_windowed(x, y, broken, recipe="source_code_ridge1")

    def test_ols_fold_parameters_displacements_and_support_binding(self):
        x, y, _, _ = fixture()
        plan = a.e.source_schedule("curved")
        train, test = plan["train"][0, 0], plan["test"][0, 0]
        row = a.decoder_fold(x, y, train, test, recipe="paper_ols0")
        model = old.fit_velocity(x[:, train], y[:, train], recipe="paper_ols0")
        np.testing.assert_array_equal(row["decoder"]["weight"], model["weight"])
        np.testing.assert_array_equal(row["prediction"], old.predict_positions(model, x[:, test], y[0, test]))
        np.testing.assert_array_equal(row["displacement"], x[:-1, test] @ model["weight"].T + model["bias"])
        record = row["fit_record"]
        self.assertFalse(record["bias_penalized"])
        self.assertEqual(record["feature_count"], 3)
        self.assertEqual(record["training_observations"], 79 * len(train))
        self.assertEqual(record["inputs"]["neural_features"], a.array_digest(x[:-1, train]))
        self.assertEqual(record["inputs"]["target_displacements"], a.array_digest(np.diff(y[:, train], axis=0)))
        self.assertEqual(record["outputs"]["weight"], a.array_digest(model["weight"]))
        self.assertEqual(record["provenance"], "source_observed_record_not_execution_authentication")
        changed = a.make_fit_record(model, x[:, train], y[:, train], train, test[::-1])
        self.assertNotEqual(record["inputs"]["test_indices"], changed["inputs"]["test_indices"])
        wrong = dict(model, bias_penalized=True)
        with self.assertRaisesRegex(ValueError, "intercept penalty"):
            a.make_fit_record(wrong, x[:, train], y[:, train], train, test)


class RepeatedParity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.x, cls.y, cls.full, cls.angles = fixture()
        cls.actual = a._repeated_windowed(cls.x, cls.y, cls.full, recipe="source_code_ridge1")
        with mock.patch.object(old.endpoints, "source_windows", return_value=(cls.x, cls.y)):
            cls.expected = old.repeated_decoding(None, cls.full, recipe="source_code_ridge1")

    def test_complete_original_schedules_predictions_and_summaries_match(self):
        for reach, occurrences in [("straight", 5300), ("curved", 4900)]:
            row = self.actual["conditions"][reach]
            expected = self.expected["conditions"][reach]
            np.testing.assert_array_equal(row["prediction"], expected["prediction"])
            np.testing.assert_array_equal(row["test_indices"], expected["test_indices"])
            self.assertEqual(row["summary"], expected["summary"])
            self.assertEqual(row["summary"]["repeated_test_occurrences"], occurrences)
            for name in row["details"]:
                np.testing.assert_array_equal(row["details"][name], expected["details"][name])

    def test_all_two_hundred_fits_and_displacements_reconstruct_predictions(self):
        for reach in a.e.CONDITIONS:
            row = self.actual["conditions"][reach]
            audit = row["decoder_audit"]
            plan = a.e.source_schedule(reach)
            np.testing.assert_array_equal(audit["train_indices"], plan["train"])
            self.assertEqual(audit["weight"].shape, (20, 5, 2, 3))
            self.assertEqual(audit["bias"].shape, (20, 5, 2))
            self.assertTrue(audit["bias_penalized"])
            self.assertEqual(len(audit["fit_records"]), 20)
            for repeat in range(20):
                self.assertEqual(len(audit["fit_records"][repeat]), 5)
                for fold in range(5):
                    test = plan["test"][repeat, fold]
                    delta = self.x[:-1, test] @ audit["weight"][repeat, fold].T + audit["bias"][repeat, fold]
                    np.testing.assert_allclose(audit["displacement"][repeat, fold], delta, rtol=8e-15, atol=8e-15)
                    np.testing.assert_allclose(row["prediction"][repeat, fold], a.e.integrate_displacements(delta, self.y[0, test]), rtol=8e-15, atol=8e-15)
                    record = audit["fit_records"][repeat][fold]
                    self.assertEqual(record["inputs"]["train_indices"], a.array_digest(plan["train"][repeat, fold]))
                    self.assertEqual(record["inputs"]["test_indices"], a.array_digest(test))
                    self.assertEqual(record["outputs"]["weight"], a.array_digest(audit["weight"][repeat, fold]))
                    self.assertEqual(record["outputs"]["bias"], a.array_digest(audit["bias"][repeat, fold]))


class AverageParity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.x, cls.y, cls.full, cls.angles = fixture()
        cls.actual = a._condition_average_windowed(cls.x, cls.y, cls.angles, recipe="source_code_ridge1")
        with mock.patch.object(old.endpoints, "source_windows", return_value=(cls.x, cls.y)):
            cls.expected = old.condition_average_control(None, None, cls.angles, recipe="source_code_ridge1")

    def test_complete_twenty_reversed_half_outputs_match_original(self):
        for reach in a.e.CONDITIONS:
            row = self.actual["conditions"][reach]
            old_row = self.expected["conditions"][reach]
            np.testing.assert_array_equal(row["r2"], old_row["r2"])
            self.assertEqual(row["mean_condition_half_repeat_r2"], old_row["mean_condition_half_repeat_r2"])
            for repeat in range(20):
                for half in range(2):
                    actual = row["rows"][repeat][half]
                    expected = old_row["rows"][repeat][half]
                    for key in expected:
                        np.testing.assert_array_equal(actual[key], expected[key])

    def test_split_first_means_counts_fit_records_and_odd_middle_support(self):
        for reach in a.e.CONDITIONS:
            for pair in self.actual["conditions"][reach]["rows"]:
                for row in pair:
                    labels = row["condition_labels"]
                    for side, position in [("train", 0), ("test", 1)]:
                        ids = row[side + "_indices"]
                        groups = [ids[self.angles[ids] == label] for label in labels]
                        np.testing.assert_array_equal(row["group_counts"][position], [len(group) for group in groups])
                        np.testing.assert_array_equal(row["neural_" + side + "_mean"], np.stack([self.x[:, group].mean(axis=1) for group in groups], axis=1))
                        np.testing.assert_array_equal(row["movement_" + side + "_mean"], np.stack([self.y[:, group].mean(axis=1) for group in groups], axis=1))
                    self.assertEqual(row["fit_record"]["inputs"]["neural_features"], a.array_digest(row["neural_train_mean"][:-1]))
                    self.assertEqual(row["fit_record"]["inputs"]["target_displacements"], a.array_digest(np.diff(row["movement_train_mean"], axis=0)))
                    np.testing.assert_array_equal(row["target"], row["movement_test_mean"])
                    np.testing.assert_array_equal(row["prediction"], a.e.integrate_displacements(row["displacement"], row["movement_test_mean"][0]))
                held_overlap = np.intersect1d(pair[0]["test_indices"], pair[1]["test_indices"])
                self.assertEqual(len(held_overlap), 1 if reach == "straight" else 0)
                self.assertEqual(len(np.intersect1d(pair[0]["train_indices"], pair[1]["train_indices"])), 0)

    def test_missing_angle_from_one_half_rejected(self):
        angles = np.zeros(511)
        angles[2] = 1
        with self.assertRaisesRegex(ValueError, "missing from a half"):
            a.averaged_half(self.x, self.y, angles, np.array([0, 1]), np.array([2, 3]), recipe="source_code_ridge1")


if __name__ == "__main__":
    unittest.main(verbosity=2)
