"""Generated adapter fixtures only; not executed during source preparation."""
import copy
import io
import math
import os
from pathlib import Path
import stat
import struct
import tempfile
import unittest
from unittest import mock
import warnings
import zipfile

import numpy as np

import metrics
import validator


class AdapterGeneratedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.directory = Path(self.tmp.name)
        self.path = self.directory / "candidate.npz"
        self.expected = {"case-a": np.array(["a0", "a1"]),
                         "case-b": np.array(["b0", "b1"])}
        self.labels = {case: np.array([0, 1], dtype=np.uint8) for case in self.expected}
        self.calls = []
        loss = -0.5 * (math.log(0.25) + math.log(0.75))
        rows = [{"person_id": c, "n": 2, "n_target": 1, "n_non_target": 1,
                 "balanced_accuracy": 0.5, "log_loss": loss} for c in sorted(self.expected)]
        self.reference = {"arms": {a: {"per_person": copy.deepcopy(rows),
                                      "participant_macro_balanced_accuracy": 0.5,
                                      "participant_macro_log_loss": loss}
                                   for a in metrics.REFERENCE_ARMS}}

    def tearDown(self):
        self.tmp.cleanup()

    def loader(self, case):
        self.calls.append(case)
        return self.labels[case]

    def write(self, ids=None, p=None, **extra):
        if ids is None:
            ids = np.array(["a0", "a1", "b0", "b1"])
        if p is None:
            p = np.array([0.1, 0.9, 0.2, 0.8])
        np.savez(self.path, trial_ids=ids, target_probability=p, **extra)

    def invalid_has_zero_private_loads(self):
        with self.assertRaises(validator.InvalidSubmission):
            validator.validate_and_score(self.path, self.expected, self.loader, self.reference)
        self.assertEqual(self.calls, [])

    def npy(self, value):
        buffer = io.BytesIO()
        np.save(buffer, value, allow_pickle=True)
        return buffer.getvalue()

    def test_valid_arbitrary_reordering(self):
        self.write(ids=np.array(["b1", "a0", "b0", "a1"]),
                   p=np.array([0.8, 0.1, 0.2, 0.9], dtype=np.float32))
        ordered = validator.validate(self.path, self.expected)
        np.testing.assert_array_equal(ordered["case-a"], np.array([0.1, 0.9], dtype=np.float32).astype(np.float64))
        np.testing.assert_array_equal(ordered["case-b"], np.array([0.2, 0.8], dtype=np.float32).astype(np.float64))
        result = validator.validate_and_score(self.path, self.expected, self.loader, self.reference)
        self.assertEqual(result["candidate"]["participant_macro_balanced_accuracy"], 1.0)
        self.assertEqual(self.calls, ["case-a", "case-b"])
        self.assertEqual(set(result["candidate_minus_reference"]), set(metrics.REFERENCE_ARMS))

    def test_zero_one_ties_and_negative_scores_accepted(self):
        self.write(p=np.array([1., 0., 0.5, 0.5]))
        ordered = validator.validate(self.path, self.expected)
        before = {case: values.copy() for case, values in ordered.items()}
        result = metrics.score_candidate(ordered, self.loader, self.reference)
        self.assertEqual(result["status"], "scored")
        self.assertEqual(result["candidate"]["participant_macro_balanced_accuracy"], 0.25)
        self.assertEqual(result["candidate_minus_reference"]["prior"]["participant_macro_balanced_accuracy"], -0.25)
        row = result["candidate"]["per_person"][1]
        self.assertEqual(row["confusion"], {"tn": 0, "fp": 1, "fn": 0, "tp": 1})
        expected_loss = math.fsum((-math.log1p(-(1-1e-15)), -math.log(1e-15),
                                   -math.log(0.5), -math.log(0.5))) / 4
        self.assertAlmostEqual(result["candidate"]["participant_macro_log_loss"], expected_loss, places=12)
        for case in ordered:
            np.testing.assert_array_equal(ordered[case], before[case])

    def test_empty_malformed_and_truncated_archives(self):
        for content in (b"", b"not a zip"):
            self.path.write_bytes(content)
            self.invalid_has_zero_private_loads()
        self.write()
        self.path.write_bytes(self.path.read_bytes()[:-12])
        self.invalid_has_zero_private_loads()

    def test_missing_case_and_extra_identity(self):
        self.write(ids=np.array(["a0", "a1"]), p=np.array([0.1, 0.9]))
        self.invalid_has_zero_private_loads()
        self.write(ids=np.array(["a0", "a1", "b0", "other"]))
        self.invalid_has_zero_private_loads()

    def test_duplicate_ids_and_extra_fields(self):
        self.write(ids=np.array(["a0", "a1", "a0", "b1"]))
        self.invalid_has_zero_private_loads()
        self.write(extra=np.array(1))
        self.invalid_has_zero_private_loads()

    def test_nan_outside_range_wrong_shape_and_dtype(self):
        for p in (np.array([0., np.nan, 0., 1.]), np.array([0., np.inf, 0., 1.]),
                  np.array([0., 1.01, 0., 1.]), np.ones((4, 1)), np.ones(4, dtype=np.int64)):
            self.write(p=p)
            self.invalid_has_zero_private_loads()

    def test_object_and_bytes_ids_rejected_before_numpy_load(self):
        for ids in (np.array(["a0", "a1", "b0", "b1"], dtype=object),
                    np.array([b"a0", b"a1", b"b0", b"b1"])):
            self.write(ids=ids)
            with mock.patch.object(validator.np, "load", side_effect=AssertionError("np.load before header rejection")):
                self.invalid_has_zero_private_loads()

    def test_duplicate_zip_member_and_linked_member(self):
        ids = self.npy(np.array(["a0", "a1", "b0", "b1"]))
        p = self.npy(np.array([0.1, 0.9, 0.2, 0.8]))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(self.path, "w") as z:
                z.writestr("trial_ids.npy", ids)
                z.writestr("trial_ids.npy", ids)
                z.writestr("target_probability.npy", p)
        self.invalid_has_zero_private_loads()
        with zipfile.ZipFile(self.path, "w") as z:
            linked = zipfile.ZipInfo("trial_ids.npy")
            linked.create_system = 3
            linked.external_attr = (stat.S_IFLNK | 0o777) << 16
            z.writestr(linked, ids)
            z.writestr("target_probability.npy", p)
        self.invalid_has_zero_private_loads()

    def test_symlink_hardlink_and_symlink_parent(self):
        real = self.directory / "real.npz"
        self.write()
        self.path.rename(real)
        self.path.symlink_to(real)
        self.invalid_has_zero_private_loads()
        self.path.unlink()
        os.link(real, self.path)
        self.invalid_has_zero_private_loads()
        self.path.unlink()
        linked_dir = self.directory / "alias"
        linked_dir.symlink_to(self.directory, target_is_directory=True)
        self.path = linked_dir / "real.npz"
        self.invalid_has_zero_private_loads()

    def test_header_huge_shape_and_header_length_rejected_before_load(self):
        ids = self.npy(np.array(["a0", "a1", "b0", "b1"]))
        header = repr({"descr": "<f8", "fortran_order": False, "shape": (10**12,)}).encode() + b"\n"
        bad_shape = b"\x93NUMPY\x01\x00" + struct.pack("<H", len(header)) + header
        bad_length = b"\x93NUMPY\x02\x00" + struct.pack("<I", 2**31) + b"\n"
        for content in (bad_shape, bad_length):
            with zipfile.ZipFile(self.path, "w") as z:
                z.writestr("trial_ids.npy", ids)
                z.writestr("target_probability.npy", content)
            with mock.patch.object(validator.np, "load", side_effect=AssertionError("np.load before header rejection")):
                self.invalid_has_zero_private_loads()

    def test_expanded_cap_before_numpy_load(self):
        with zipfile.ZipFile(self.path, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("trial_ids.npy", b"0" * (validator.MAX_EXPANDED_BYTES + 1))
            z.writestr("target_probability.npy", b"0")
        with mock.patch.object(validator.np, "load", side_effect=AssertionError("np.load before cap rejection")):
            self.invalid_has_zero_private_loads()

    def test_truncated_array_inside_valid_zip_before_numpy_load(self):
        with zipfile.ZipFile(self.path, "w") as z:
            z.writestr("trial_ids.npy", self.npy(np.array(["a0", "a1", "b0", "b1"])))
            z.writestr("target_probability.npy", self.npy(np.array([0.1, 0.9, 0.2, 0.8]))[:-1])
        with mock.patch.object(validator.np, "load", side_effect=AssertionError("np.load before size rejection")):
            self.invalid_has_zero_private_loads()

    def test_both_probability_vectors_validated_before_any_private_load(self):
        ordered = {"case-a": np.array([0.1, 0.9]), "case-b": np.array([0.2, np.nan])}
        with self.assertRaises(ValueError):
            metrics.score_candidate(ordered, self.loader, self.reference)
        self.assertEqual(self.calls, [])

    def test_bad_reference_identity_rejected_without_loading_targets(self):
        self.write()
        bad = copy.deepcopy(self.reference)
        bad["arms"]["eeg"]["per_person"][1]["person_id"] = "other-person"
        with self.assertRaises(ValueError):
            validator.validate_and_score(self.path, self.expected, self.loader, bad)
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
