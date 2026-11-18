"""Generated, in-memory input counterexamples; no source data or model fits."""
import copy
import importlib.util
from pathlib import Path
import unittest
from unittest import mock

import numpy as np

_path = Path(__file__).resolve().parent / "controls.py"
_spec = importlib.util.spec_from_file_location("neural026_controls", _path)
controls = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(controls)


def design():
    cases = []
    for mouse in ("cfa17", "cfa19", "cfa20", "cfa22", "cfa24"):
        for area in ("M1", "S1"):
            for fold in range(5):
                query = [fold + 1 + 5 * i for i in range(4)]
                cases.append(dict(case_id=f"{mouse}_{area}_fold{fold}", mouse=mouse,
                    area=area, fold=fold, query_id=query,
                    train_id=[i for i in range(1, 21) if i not in query],
                    matched_counts={"1": 10, "2": 10}))
    return {"schema": "neural026_design_v1", "cases": cases}


def packet(case):
    values = {}
    for side in ("train", "query"):
        ids = np.array(case[side + "_id"], dtype=np.int64)
        n = len(ids)
        values[side + "_id"] = ids
        values[side + "_target"] = np.where(ids <= 10, 1, 2).astype(np.int8)
        # Whole trials carry distinct values; time and ROI structure distinguish
        # a trial permutation from a time-bin shift or shuffled output labels.
        values[side + "_x"] = (ids[:, None, None] * 10000
            + np.arange(51)[None, :, None] * 100
            + np.arange(128)[None, None, :]).astype(np.float32)
        values[side + "_z"] = np.broadcast_to(ids[:, None, None], (n, 51, 141)).astype(np.float64)
    values["train_y"] = np.broadcast_to(values["train_id"][:, None, None],
        (len(values["train_id"]), 51, 24)).astype(np.float32)
    return values


class ControlsTest(unittest.TestCase):
    def setUp(self):
        self.design = design()
        self.case = self.design["cases"][0]
        self.packet = packet(self.case)

    def build(self, mode, **kwargs):
        return controls.build_control(self.packet, self.design, self.case["case_id"],
            mode, max_array_working_bytes=16 * 1024**2, **kwargs)

    def test_full_capture_is_identical_owned_readonly(self):
        out, receipt = self.build("full")
        self.assertEqual(receipt["source_arrays"], receipt["view_arrays"])
        for key in self.packet:
            np.testing.assert_array_equal(out[key], self.packet[key])
            self.assertEqual(out[key].dtype, self.packet[key].dtype)
            self.assertFalse(np.shares_memory(out[key], self.packet[key]))
            self.assertFalse(out[key].flags.writeable)
        self.assertFalse(receipt["execution_verified"])

    def test_context_removes_only_calcium_and_preserves_original(self):
        original = {key: value.copy() for key, value in self.packet.items()}
        out, receipt = self.build("context_only")
        for key in self.packet:
            np.testing.assert_array_equal(self.packet[key], original[key])
            if key in ("train_x", "query_x"):
                self.assertFalse(np.any(out[key]))
                self.assertEqual(out[key].shape, original[key].shape)
                self.assertEqual(out[key].dtype, original[key].dtype)
            else:
                np.testing.assert_array_equal(out[key], original[key])
                self.assertEqual(receipt["source_arrays"][key], receipt["view_arrays"][key])

    def test_shift_is_whole_training_trial_within_target(self):
        out, receipt = self.build("training_trial_shift")
        index = np.array(receipt["training_row_permutation"])
        self.assertTrue(np.all(index != np.arange(len(index))))
        self.assertEqual(set(index), set(range(len(index))))
        np.testing.assert_array_equal(self.packet["train_target"][index], self.packet["train_target"])
        np.testing.assert_array_equal(out["train_x"], self.packet["train_x"][index])
        # Independent oracle: eight rows of each target rotate by four.
        expected = [4, 5, 6, 7, 0, 1, 2, 3, 12, 13, 14, 15, 8, 9, 10, 11]
        self.assertEqual(index.tolist(), expected)
        for key in self.packet.keys() - {"train_x"}:
            np.testing.assert_array_equal(out[key], self.packet[key])

    def test_complete_design_and_exact_case_support_required(self):
        self.design["cases"].pop()
        with self.assertRaisesRegex(ValueError, "fifty"):
            self.build("full")
        self.design = design()
        self.packet["query_id"] = np.array([21, 22, 23, 24])
        with self.assertRaisesRegex(ValueError, "frozen case"):
            self.build("full")

    def test_forbidden_query_targets_unknown_mode_and_nonfinite_refused(self):
        self.packet["query_y"] = np.zeros((4, 51, 24))
        with self.assertRaisesRegex(ValueError, "Exact public packet"):
            self.build("full")
        del self.packet["query_y"]
        with self.assertRaisesRegex(ValueError, "explicit input control"):
            self.build("query_shuffle")
        self.packet["train_x"][0, 0, 0] = np.nan
        with self.assertRaisesRegex(ValueError, "finite public covariates"):
            self.build("training_trial_shift")

    def test_insufficient_resource_declaration_refuses_before_copy(self):
        with mock.patch.object(controls.np, "array", side_effect=AssertionError("copied")):
            with self.assertRaisesRegex(ValueError, "working allowance"):
                controls.build_control(self.packet, self.design, self.case["case_id"],
                    "full", max_array_working_bytes=1)

    def test_object_array_and_nonarray_refused(self):
        self.packet["train_x"] = self.packet["train_x"].astype(object)
        with self.assertRaisesRegex(ValueError, "primitive numerical"):
            self.build("full")
        self.packet["train_x"] = []
        with self.assertRaisesRegex(ValueError, "primitive numerical"):
            self.build("full")

    def test_case_identity_changes_do_not_get_silently_relabelled(self):
        case = copy.deepcopy(self.case)
        self.design["cases"][0]["mouse"] = "cfa19"
        with self.assertRaisesRegex(ValueError, "biological unit"):
            self.build("full")
        self.design["cases"][0] = case
        with self.assertRaisesRegex(ValueError, "original complete-design case"):
            controls.build_control(self.packet, self.design, "cfa17_M1_fold99", "full",
                max_array_working_bytes=16 * 1024**2)


if __name__ == "__main__":
    unittest.main()
