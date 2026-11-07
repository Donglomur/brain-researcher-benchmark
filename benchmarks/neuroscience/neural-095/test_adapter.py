"""Generated qualification definitions only; no empirical input required."""
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

import validator
from validator import InvalidSubmission, validate, validate_and_score
from metrics import METHODS, score_candidate


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.ids = [f"dmfc-{i:06d}" for i in range(80)]
        condition = np.repeat(np.arange(40, dtype=np.int64), 2)
        self.private = {"case_id": np.array(self.ids), "tp_ms": np.full(80, 100.0),
                        "condition": condition, "context": condition // 5}
        self.references = {"scores": {}}
        for j, arm in enumerate(METHODS):
            error = float(5 - j)
            self.references["scores"][arm] = {
                "n": 80, "mae_ms": error, "rmse_ms": error, "eight_context_macro_mae_ms": error,
                "by_condition": {str(k): {"n": 2, "mae_ms": error} for k in range(40)},
                "by_context": {str(k): {"n": 10, "mae_ms": error} for k in range(8)}}
        self.loads = 0

    def tearDown(self):
        self.temp.cleanup()

    def loader(self):
        self.loads += 1
        return self.private

    def write(self, prediction=None, ids=None, **extra):
        path = self.root / "candidate.npz"
        np.savez(path, case_id=np.array(self.ids if ids is None else ids),
                 prediction_ms=np.full(80, 102.0) if prediction is None else prediction, **extra)
        return path

    def npy(self, values):
        buffer = io.BytesIO()
        np.save(buffer, values, allow_pickle=True)
        return buffer.getvalue()

    def archive(self, ids_body=None, prediction_body=None, mode=None, duplicate=False):
        path = self.root / "candidate.npz"
        ids_body = self.npy(np.array(self.ids)) if ids_body is None else ids_body
        prediction_body = self.npy(np.full(80, 101.0)) if prediction_body is None else prediction_body
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
                z.writestr("case_id.npy", ids_body)
                entry = zipfile.ZipInfo("prediction_ms.npy")
                entry.compress_type = zipfile.ZIP_DEFLATED
                if mode is not None:
                    entry.create_system = 3
                    entry.external_attr = mode << 16
                z.writestr(entry, prediction_body)
                if duplicate:
                    z.writestr("case_id.npy", ids_body)
        return path

    def invalid(self, path, before_allocation=False):
        context = (mock.patch.object(validator.np, "load", side_effect=AssertionError("Array allocation before header validation"))
                   if before_allocation else mock.patch.object(self, "unused", None, create=True))
        with context, self.assertRaises(InvalidSubmission):
            validate_and_score(path, self.ids, self.loader, self.references)
        self.assertEqual(self.loads, 0)

    def test_reordering_float32_and_arbitrary_values(self):
        values = np.linspace(-5, 150, 80, dtype=np.float32)
        path = self.write(values[::-1], self.ids[::-1])
        actual = validate(path, self.ids)
        np.testing.assert_array_equal(actual, values.astype(np.float64))
        result = validate_and_score(path, self.ids, self.loader, self.references)
        self.assertEqual(self.loads, 1)
        errors = [abs(float(v) - 100.0) for v in values]
        self.assertAlmostEqual(result["candidate"]["mae_ms"], math.fsum(errors) / 80)
        self.assertAlmostEqual(result["candidate"]["rmse_ms"], math.sqrt(math.fsum(e * e for e in errors) / 80))
        self.assertEqual(len(result["candidate"]["by_condition"]), 40)
        self.assertEqual(len(result["candidate"]["by_context"]), 8)
        # Unequal context sizes distinguish the macro estimand from trial pooling.
        condition = np.repeat(np.arange(40, dtype=np.int64), [3] * 20 + [1] * 20)
        self.private["condition"] = condition; self.private["context"] = condition // 5
        for report in self.references["scores"].values():
            for k in range(40):
                report["by_condition"][str(k)]["n"] = 3 if k < 20 else 1
            for k in range(8):
                report["by_context"][str(k)]["n"] = 15 if k < 4 else 5
        unequal = score_candidate(100.0 + self.private["context"], self.loader, self.references)["candidate"]
        self.assertAlmostEqual(unequal["mae_ms"], 2.5)
        self.assertAlmostEqual(unequal["eight_context_macro_mae_ms"], 3.5)
        self.assertAlmostEqual(unequal["rmse_ms"], math.sqrt(10.5))

    def test_negative_predictions_and_all_signed_comparisons(self):
        result = validate_and_score(self.write(np.full(80, -4.0)), self.ids, self.loader, self.references)
        self.assertEqual(result["status"], "scored")
        self.assertEqual(result["candidate"]["mae_ms"], 104.0)
        self.assertIsNone(result["scientific_pass_floor"])
        for j, arm in enumerate(METHODS):
            difference = 104.0 - (5 - j)
            for key in ("mae_ms", "rmse_ms", "eight_context_macro_mae_ms"):
                self.assertEqual(result["candidate_minus_reference"][arm][key], difference)
            self.assertTrue(all(v["mae_ms"] == difference for v in result["candidate_minus_reference"][arm]["by_condition"].values()))
        perfect = score_candidate(np.full(80, 100.0), self.loader, self.references)
        self.assertEqual(perfect["candidate"]["rmse_ms"], 0.0)
        self.assertTrue(all(row["mae_ms"] < 0 for row in perfect["candidate_minus_reference"].values()))

    def test_extreme_finite_representable_errors(self):
        result = validate_and_score(self.write(np.full(80, -1e308)), self.ids, self.loader, self.references)
        for key in ("mae_ms", "rmse_ms", "eight_context_macro_mae_ms"):
            self.assertEqual(result["candidate"][key], 1e308)
        self.assertFalse(result["prediction_values_modified"])

    def test_genuinely_unrepresentable_subtraction_stops(self):
        self.private["tp_ms"][:] = 1e308
        path = self.write(np.full(80, -1e308))
        np.testing.assert_array_equal(validate(path, self.ids), np.full(80, -1e308))
        with self.assertRaisesRegex(ValueError, "subtraction overflow"):
            validate_and_score(path, self.ids, self.loader, self.references)
        self.assertEqual(self.loads, 1)

    def test_missing_duplicate_extra_and_wrong_geometry(self):
        for ids in (self.ids[:-1], [self.ids[0]] * 80, self.ids[:-1] + ["dmfc-999999"]):
            with self.subTest(ids=ids[:2]):
                self.invalid(self.write(np.full(len(ids), 100.0), ids))
        self.invalid(self.write(np.full((80, 1), 100.0)), before_allocation=True)
        self.invalid(self.write(extra=np.array(1)), before_allocation=True)

    def test_nonfinite_and_wrong_dtype_rejected_before_private(self):
        for bad in (np.nan, np.inf, -np.inf):
            values = np.full(80, 100.0); values[-1] = bad
            self.invalid(self.write(values))
        for values in (np.ones(80, dtype=np.int64), np.ones(80, dtype=np.float16),
                       np.ones(80, dtype=np.complex128), np.array(["bad"] * 80, dtype=object)):
            self.invalid(self.write(values), before_allocation=True)

    def test_empty_badzip_truncated_npy_and_duplicate_members(self):
        path = self.root / "candidate.npz"
        for body in (b"", b"not a zip", b"PK\x03\x04"):
            path.write_bytes(body); self.invalid(path, before_allocation=True)
        self.invalid(self.archive(prediction_body=self.npy(np.ones(80))[:-1]), before_allocation=True)
        self.invalid(self.archive(duplicate=True), before_allocation=True)

    def test_member_links_and_outer_links(self):
        self.invalid(self.archive(mode=stat.S_IFLNK | 0o777), before_allocation=True)
        real = self.write()
        link = self.root / "symlink.npz"; link.symlink_to(real)
        self.invalid(link, before_allocation=True); link.unlink()
        hard = self.root / "hardlink.npz"; os.link(real, hard)
        self.invalid(hard, before_allocation=True); self.invalid(real, before_allocation=True)
        hard.unlink()
        directory_link = self.root / "directory-link"; directory_link.symlink_to(self.root, target_is_directory=True)
        self.invalid(directory_link / "candidate.npz", before_allocation=True)

    def test_header_caps_huge_shape_and_duplicate_header_keys(self):
        raw = b"\x93NUMPY\x02\x00" + struct.pack("<I", 5000) + b" " * 4999 + b"\n"
        self.invalid(self.archive(prediction_body=raw), before_allocation=True)
        for header in ("{'descr':'<f8','fortran_order':False,'shape':(999999999999,)}\n",
                       "{'descr':'<f8','descr':'<f8','fortran_order':False,'shape':(80,)}\n"):
            body = header.encode("ascii")
            raw = b"\x93NUMPY\x01\x00" + struct.pack("<H", len(body)) + body
            self.invalid(self.archive(prediction_body=raw), before_allocation=True)

    def test_expanded_cap_crc_and_trailing_member_bytes(self):
        self.invalid(self.archive(prediction_body=b"0" * (validator.MAX_EXPANDED_BYTES + 1)), before_allocation=True)
        self.invalid(self.archive(prediction_body=self.npy(np.ones(80)) + b"extra"), before_allocation=True)
        path = self.write()
        with zipfile.ZipFile(path) as z:
            info = z.getinfo("prediction_ms.npy")
            offset = info.header_offset
        raw = bytearray(path.read_bytes())
        filename_len, extra_len = struct.unpack_from("<HH", raw, offset + 26)
        data_start = offset + 30 + filename_len + extra_len
        raw[data_start + info.compress_size - 1] ^= 1
        path.write_bytes(raw)
        self.invalid(path, before_allocation=True)

    def test_bad_reference_rejected_without_private_load(self):
        malformed = copy.deepcopy(self.references)
        del malformed["scores"][METHODS[0]]["by_condition"]["39"]
        with self.assertRaises(ValueError):
            validate_and_score(self.write(), self.ids, self.loader, malformed)
        self.assertEqual(self.loads, 0)
        with self.assertRaises(ValueError):
            score_candidate(np.full(80, np.nan), self.loader, self.references)
        self.assertEqual(self.loads, 0)

    def test_private_join_and_missing_group_stop_whole_score(self):
        path = self.write()
        self.private["case_id"] = self.private["case_id"][::-1]
        with self.assertRaisesRegex(ValueError, "identity order"):
            validate_and_score(path, self.ids, self.loader, self.references)
        self.private["case_id"] = np.array(self.ids)
        self.private["condition"][-2:] = 38
        with self.assertRaisesRegex(ValueError, "All 40"):
            validate_and_score(path, self.ids, self.loader, self.references)


if __name__ == "__main__":
    unittest.main()
