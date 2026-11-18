"""Generated preparation checks only: no native inputs, RF fits or models."""
import importlib.util
from pathlib import Path
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("preparation", ROOT / "preparation.py")
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


def fixture():
    # Interleaved days make source-sorted training differ from original row order.
    days = np.array([3, 1, 2, 1, 3, 2, 7, 7])
    times = np.array([-3., -2., -1., 0., 1., 2., 3.])
    native = np.zeros((8, 3, 7), dtype=np.float64)
    for i in range(8):
        native[i, 0] = i + np.arange(7)
        native[i, 1] = 3 * i + 2 * np.arange(7)
    native[:, -1, 0] = [1, 2, 1, 2, 1, 2, 1, 2]
    # Labels at time coordinate zero are deliberately different and unused.
    native[:, -1, 3] = 99
    args = dict(event_days=days, times=times, channel_coordinates=np.arange(3),
                row_ids=np.array([f"row-{i}" for i in range(8)]), participant="EC01",
                source_sha256="a" * 64, kind="generated_control")
    return native, args


class PreparationTests(unittest.TestCase):
    def test_sorted_days_all_rows_labels_and_endpoint_abi(self):
        native, args = fixture()
        a, m = p.prepare_arrays(native, **args)
        self.assertEqual(m["train_source_indices"], [1, 3, 2, 5, 0, 4])
        self.assertEqual(m["test_source_indices"], [6, 7])
        self.assertEqual(m["native_events"], m["train_events"] + m["test_events"])
        self.assertEqual(a["train_labels"].tolist(), [1, 1, 0, 1, 0, 0])
        self.assertEqual(a["test_labels"].tolist(), [0, 1])
        train_i, test_i = p.endpoint.source_day_indices(a["native_days"])
        self.assertEqual(a["train_row_ids"].tolist(), a["native_row_ids"][train_i].tolist())
        self.assertEqual(a["test_row_ids"].tolist(), a["native_row_ids"][test_i].tolist())
        p.endpoint.binary_labels(a["train_labels"], 6, "train")
        p.endpoint.binary_labels(a["test_labels"], 2, "test")
        observed, _ = p.endpoint.observed_channels(2, 0.5, 0)
        outputs = p.endpoint.decoder_inputs(a["test_z"], a["train_mean"], a["train_scale"],
                    {name: a["test_z"] for name in p.endpoint.IMPUTERS}, observed)
        expected = native[test_i, :-1, 1:6].astype(np.float32).reshape(2, -1)
        np.testing.assert_allclose(outputs["fully_observed"], expected, rtol=2e-7, atol=2e-6)
        self.assertEqual(m["historical_paper_day7_mapping"], "unresolved")

    def test_population_statistics_and_inclusive_time_window(self):
        native, args = fixture()
        a, m = p.prepare_arrays(native, **args)
        train = native[[1, 3, 2, 5, 0, 4], :-1, 1:6]
        np.testing.assert_array_equal(a["selected_times"], [-2, -1, 0, 1, 2])
        np.testing.assert_allclose(a["train_mean"], train.mean(axis=(0, 2)), rtol=0, atol=1e-14)
        np.testing.assert_allclose(a["train_scale"], train.std(axis=(0, 2), ddof=0), rtol=0, atol=1e-14)
        self.assertEqual(m["label_native_time_index"], 0)

    def test_test_perturbations_cannot_refit_statistics_or_drop_rows(self):
        native, args = fixture()
        a, _ = p.prepare_arrays(native, **args)
        native[6:, :2, 1:6] = 100000 * native[6:, :2, 1:6]
        native[6:, -1, 0] = [2, 1]
        b, _ = p.prepare_arrays(native, **args)
        for key in ("train_z", "train_mean", "train_scale", "train_quality", "train_labels", "train_row_ids"):
            np.testing.assert_array_equal(a[key], b[key])
        self.assertFalse(b["test_quality"].any())
        self.assertEqual(b["test_labels"].tolist(), [1, 0])
        self.assertEqual(len(b["test_z"]), 2)
        self.assertTrue(np.any(b["test_z"] != 0))

    def test_zero_range_train_rows_still_enter_decoder_support(self):
        native, args = fixture()
        native[1, 0, 1:6] = 100
        a, _ = p.prepare_arrays(native, **args)
        self.assertFalse(a["train_quality"][0, 0])
        self.assertEqual(len(a["train_z"]), 6)
        raw_eligible = native[[3, 2, 5, 0, 4], 0, 1:6]
        self.assertAlmostEqual(a["train_mean"][0], raw_eligible.mean())
        self.assertTrue(np.any(a["train_z"][0, 0] != 0))

    def test_observed_condition_ignores_quality_but_not_mask_and_has_no_hidden_truth(self):
        native, args = fixture()
        a, _ = p.prepare_arrays(native, **args)
        cond, order = p.source_condition(a, dropout=0.5, repeat=0)
        altered = dict(a)
        altered["test_z"] = a["test_z"].copy()
        hidden = sorted(set(range(2)) - set(order))
        altered["test_z"][:, hidden] += 1000
        altered["test_quality"] = np.zeros_like(a["test_quality"])
        cond2, order2 = p.source_condition(altered, dropout=0.5, repeat=0)
        np.testing.assert_array_equal(cond, cond2)
        self.assertEqual(order, order2)
        np.testing.assert_array_equal(cond[:, :2, :][:, hidden], 0)
        np.testing.assert_array_equal(cond[:, 2:, :][:, hidden], 0)
        np.testing.assert_array_equal(cond[:, 2:, :][:, order], a["test_z"].astype(np.float32)[:, order])

    def test_ignored_source_fields_do_not_change_preparation(self):
        native, args = fixture()
        a, _ = p.prepare_arrays(native, **args)
        native[:, :2, [0, 6]] = np.nan
        native[:, -1, 1:] = np.nan
        b, _ = p.prepare_arrays(native, **args)
        for key in a:
            np.testing.assert_array_equal(a[key], b[key])

    def test_refuse_source_schema_and_undefined_normalization(self):
        native, args = fixture()
        cases = [dict(args, channel_coordinates=[1, 2, 3]),
                 dict(args, channel_coordinates=[0.0, 1.0, 2.0]),
                 dict(args, row_ids=["duplicate"] * 8),
                 dict(args, event_days=[1] * 8),
                 dict(args, times=[-3, -2, -1, 0, 0, 2, 3]),
                 dict(args, times=np.array([0, 1, 2, 3, 2, 5, 6], dtype=np.uint64)),
                 dict(args, source_sha256="unbound"),
                 dict(args, kind="authentic_input")]
        for altered in cases:
            with self.subTest(altered=altered):
                with self.assertRaises(ValueError):
                    p.prepare_arrays(native, **altered)
        for mutation in ("bad_label", "all_zero_channel", "nonfinite_signal"):
            x = native.copy()
            if mutation == "bad_label": x[0, -1, 0] = 0
            elif mutation == "all_zero_channel": x[:6, 0, 1:6] = 0
            else: x[0, 0, 3] = np.nan
            with self.subTest(mutation=mutation):
                with self.assertRaises(ValueError):
                    p.prepare_arrays(x, **args)

    def test_source_squeeze_singleton_partitions_are_not_silently_repaired(self):
        native, args = fixture()
        for days in ([3, 1, 2, 1, 3, 2, 3, 7], [7, 7, 7, 7, 7, 7, 7, 1]):
            with self.subTest(days=days):
                with self.assertRaisesRegex(ValueError, "nonsingleton"):
                    p.prepare_arrays(native, **dict(args, event_days=days))


if __name__ == "__main__":
    unittest.main(verbosity=2)
