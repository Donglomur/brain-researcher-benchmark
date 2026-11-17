"""Generated scientific representation controls; no authentic source values."""
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
from cohort import Refusal, ARMS
from io_support import Budget
from preparation import neural_summary, eye_selection, finite_summary
from summary_delivery_v1 import feature_columns, project_summary_rows, write_typed_summary

NAMES = [f"invented_sensor_{i:03}" for i in range(271)]


def generated_features():
    neural = np.zeros((3, 542), dtype=np.float32)
    ocular = np.zeros((3, 6), dtype=np.float32)
    neural[:, :271] = np.arange(271, dtype=np.float32)[None, :]
    neural[:, 271:] = 1
    ocular[:, :3] = [0.25, -0.5, 0.01]
    ocular[:, 3:] = 1
    neural[1, 0], neural[1, 271] = 0, 0
    ocular[2, 2], ocular[2, 5] = 0, 0
    return {"neural": neural, "ocular": ocular}


class SummaryDeliveryControls(unittest.TestCase):
    def test_time_boundary_and_source_values_survive_projection(self):
        # A huge outside-window value detects either endpoint slipping by one.
        data = np.full((1, 271, 281), 9000.0)
        data[:, :, 40:80] = 2.5
        data[:, 0, 40] = np.nan
        means, fractions = neural_summary(data, np.arange(-20, 261) / 200, NAMES, NAMES)
        eye_times = np.round(-100 + np.arange(1681) * (1000 / 1200))
        mask = eye_selection(eye_times, 0)
        self.assertEqual(np.flatnonzero(mask).tolist(), list(range(240, 480)))
        eye = np.full((1, 3, 1681), -9000.0)
        eye[:, :, mask] = np.array([0.5, -0.25, 0.012])[None, :, None]
        eye[:, 2, 240] = np.nan
        eye_mean, eye_fraction = finite_summary(eye[:, :, mask])
        base = {"neural": np.column_stack((means, fractions)),
                "ocular": np.column_stack((eye_mean, eye_fraction))}
        got = project_summary_rows(base, "joint")
        np.testing.assert_array_equal(got[:, :271], np.full((1, 271), 2.5, np.float32))
        self.assertEqual(got[0, 271], np.float32(39 / 40))
        np.testing.assert_array_equal(got[0, 542:545], np.array([.5, -.25, .012], np.float32))
        self.assertEqual(got[0, 547], np.float32(239 / 240))

    def test_arm_projection_order_units_and_independent_storage(self):
        base = generated_features()
        for arm, width in ARMS.items():
            values = project_summary_rows(base, arm)
            columns = feature_columns(NAMES, arm)
            self.assertEqual(values.shape, (3, width))
            self.assertEqual([x["index"] for x in columns], list(range(width)))
            self.assertFalse(np.shares_memory(values, base["neural"]))
            self.assertFalse(np.shares_memory(values, base["ocular"]))
        columns = feature_columns(NAMES, "joint")
        self.assertEqual(columns[0]["unit"], "1")
        self.assertEqual(columns[0]["normalization"], "per_epoch_sensor_baseline_standard_deviation")
        self.assertEqual([x["unit"] for x in columns[542:545]], ["degree", "degree", "V"])
        self.assertEqual(columns[545]["channel"], "UADC009-2104")
        availability = project_summary_rows(base, "neural_availability")
        np.testing.assert_array_equal(availability, base["neural"][:, 271:])
        self.assertTrue(all(x["quantity"] == "availability" for x in
                            feature_columns(NAMES, "neural_availability")))

    def test_impossible_fraction_missing_mean_and_unpaired_rows_refuse(self):
        for mutate in (
            lambda b: b["neural"].__setitem__((0, 271), np.float32(.123)),
            lambda b: b["ocular"].__setitem__((0, 3), np.float32(.123)),
            lambda b: b["neural"].__setitem__((1, 0), 10),
            lambda b: b["ocular"].__setitem__((2, 2), 10),
            lambda b: b.__setitem__("ocular", b["ocular"][:2]),
            lambda b: b["neural"].__setitem__((0, 0), np.nan),
            lambda b: b.__setitem__("ocular", b["ocular"].astype(np.float64)),
        ):
            base = generated_features()
            mutate(base)
            with self.assertRaises(Refusal):
                project_summary_rows(base, "joint")

    def test_every_representable_source_count_is_allowed(self):
        for count in range(241):
            base = generated_features()
            base["ocular"][:, 3:] = np.float32(count / 240)
            if count == 0:
                base["ocular"][:, :3] = 0
            project_summary_rows(base, "ocular")
        for count in range(41):
            base = generated_features()
            base["neural"][:, 271:] = np.float32(count / 40)
            if count == 0:
                base["neural"][:, :271] = 0
            project_summary_rows(base, "neural")

    def test_export_binds_order_and_array_without_labels_or_conversion(self):
        from io_support import object_digest
        ids = [f"{i:032x}" for i in (9, 2, 7)]
        now = time.monotonic()
        budget = Budget({"artifact_write": 1024 * 1024}, now, now + 30)
        with tempfile.TemporaryDirectory() as parent:
            dest = Path(parent) / "typed"
            # Only invented sensor identity is substituted; array/storage code
            # and all row/missingness/axis validation run unchanged.
            with mock.patch("summary_delivery_v1.SENSOR_ORDER_SHA256", object_digest(NAMES)):
                pins = write_typed_summary(dest, generated_features(), "joint", NAMES, ids, budget)
            descriptor = json.loads(Path(pins["descriptor"]["path"]).read_text())
            self.assertEqual(descriptor["rows"], ids)
            self.assertEqual(descriptor["values"]["path"], "features.npy")
            self.assertNotIn("labels", descriptor)
            self.assertNotIn("targets", descriptor)
            values = np.load(pins["features"]["path"], allow_pickle=False)
            np.testing.assert_array_equal(values, project_summary_rows(generated_features(), "joint"))
            self.assertEqual(descriptor["values"]["sha256"], pins["features"]["sha256"])
            with self.assertRaises(Refusal):
                write_typed_summary(Path(parent) / "wrong-sensors", generated_features(),
                                    "joint", NAMES, ids, budget)


if __name__ == "__main__":
    unittest.main(verbosity=2)
