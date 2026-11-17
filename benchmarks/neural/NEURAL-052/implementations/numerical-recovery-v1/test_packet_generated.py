"""Small invented arrays/metadata only; no authentic packet preparation/load."""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import numpy as np

import data_io as data
import prepare_packet as prep
from interface import Invalid


def describe(path):
    b = path.read_bytes()
    return {"bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()}


def features_and_rows():
    features = {f"c{i:03}": {"image": f"image{i:03}.jpg", "image_features": [i/100] * 15,
                "animacy": 1 + i % 7, "size": i} for i in range(100)}
    rows = [{"concept": c, "image": features[c]["image"], "session": s, "run": 1,
             "trial_id": (s-1)*820+i, "within_run_position": i}
            for s in range(1,13) for i,c in enumerate(features)]
    return {"feature_names": data.FEATURE_NAMES.copy(), "concept_features": features}, rows


class GeneratedPacketChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_projection_exact_bit_identity_and_column_order(self):
        # Include a NaN payload and signed zero: structural copy must preserve
        # every bit, not impute or normalize it during construction.
        bits = np.arange(24, dtype="<u4").reshape(3, 8)
        bits[0, 1] = 0x7fc01234
        bits[1, 6] = 0x80000000
        values = bits.view("<f4")
        got = prep.project_columns_for_generated_checks(values, [6, 1, 4])
        expected = bits[:, [6, 1, 4]].T.copy()
        np.testing.assert_array_equal(got.view("<u4"), expected)
        self.assertEqual(got.shape, (3, 3))
        self.assertTrue(got.flags.c_contiguous)
        for bad in ([1, 1], [-1], [8], [True]):
            with self.subTest(bad=bad), self.assertRaises(data.InputError):
                prep.project_columns_for_generated_checks(values, bad)

    def test_primitive_reader_hash_header_extent_and_no_pickle(self):
        p = self.root / "small.npy"
        a = np.arange(24, dtype="<f4").reshape(3, 8)
        np.save(p, a, allow_pickle=False)
        d = describe(p)
        with mock.patch.object(data.np, "load", side_effect=AssertionError("pickle-capable reader forbidden")):
            np.testing.assert_array_equal(data.read_primitive_npy(p, d, [3, 8], 1000), a)
        for shape, cap in (([8, 3], 1000), ([3, 8], d["bytes"] - 1)):
            with self.assertRaises(data.InputError):
                data.read_primitive_npy(p, d, shape, cap)
        wrong = dict(d, sha256="0" * 64)
        with mock.patch.object(data.np, "fromfile", side_effect=AssertionError("must reject before decoding")):
            with self.assertRaises(data.InputError):
                data.read_primitive_npy(p, wrong, [3, 8], 1000)
        p.write_bytes(p.read_bytes() + b"trailing")
        with self.assertRaises(data.InputError):
            data.read_primitive_npy(p, describe(p), [3, 8], 1000)
        obj = self.root / "object.npy"
        np.save(obj, np.array([[{"not": "executed"}]], dtype=object), allow_pickle=True)
        with mock.patch.object(data.np, "fromfile", side_effect=AssertionError("object header must fail")):
            with self.assertRaises(data.InputError):
                data.read_primitive_npy(obj, describe(obj), [1, 1], 1000)
        fortran = self.root / "fortran.npy"
        np.save(fortran, np.asfortranarray(a), allow_pickle=False)
        with self.assertRaises(data.InputError):
            data.read_primitive_npy(fortran, describe(fortran), [3, 8], 1000)
        with self.assertRaises(data.InputError):
            data._stream_hash(io.BytesIO(b"too many bytes"), 3)
        with self.assertRaises(data.InputError):
            data._stream_hash(io.BytesIO(b"short"), 10)

    def test_same_open_reader_detects_payload_mutation_and_name_replacement(self):
        p = self.root / "small.npy"
        a = np.arange(24, dtype="<f4").reshape(3, 8)
        np.save(p, a, allow_pickle=False)
        d = describe(p)
        original = data.np.fromfile
        def modify(*args, **kwargs):
            result = original(*args, **kwargs)
            body = bytearray(p.read_bytes())
            body[-1] ^= 1
            p.write_bytes(body)
            return result
        with mock.patch.object(data.np, "fromfile", side_effect=modify), self.assertRaises(data.InputError):
            data.read_primitive_npy(p, d, [3, 8], 1000)
        np.save(p, a, allow_pickle=False)
        d = describe(p)
        replacement = self.root / "same-bytes.npy"
        replacement.write_bytes(p.read_bytes())
        def replace(*args, **kwargs):
            result = original(*args, **kwargs)
            os.replace(replacement, p)
            return result
        with mock.patch.object(data.np, "fromfile", side_effect=replace), self.assertRaises(data.InputError):
            data.read_primitive_npy(p, d, [3, 8], 1000)

    def test_submitted_wrong_manifest_rejected_before_any_numeric_access(self):
        (self.root / "private").mkdir()
        (self.root / "public/input").mkdir(parents=True)
        path = self.root / "public/input/INPUTS.json"
        path.write_text(json.dumps({"schema": "neural052_inputs_v1", "task_id": "NEURAL-052"}))
        binding = {"schema": "neural052_packet_binding_v1", "task_id": "NEURAL-052",
                   "design": data.DESIGN_PIN,
                   "inputs": dict(describe(path), file="public/input/INPUTS.json"), "files": []}
        (self.root / "private/PACKET_BINDING.json").write_text(json.dumps(binding))
        with mock.patch.object(data, "read_primitive_npy", side_effect=AssertionError("private numeric read")) as reader:
            with self.assertRaises(Invalid):
                data.load_packet(self.root, submitted_manifest_sha256="0" * 64)
            reader.assert_not_called()
        # Operator pin failure remains separate from a candidate wrong header.
        path.write_text("{}")
        with self.assertRaises(data.InputError):
            data.load_packet(self.root, submitted_manifest_sha256="0" * 64)

    def test_complete_features_rows_and_native_roi_support_are_enforced(self):
        f, rows = features_and_rows()
        c = data.validate_features(f)
        data.validate_rows(rows, c)
        bad = copy.deepcopy(f)
        bad["concept_features"]["c000"]["image_features"].pop()
        with self.assertRaises(data.InputError):
            data.validate_features(bad)
        bad = copy.deepcopy(f)
        bad["concept_features"]["c000"]["animacy"] = float("nan")
        with self.assertRaises(data.InputError):
            data.validate_features(bad)
        with self.assertRaises(data.InputError):
            data.validate_rows(rows[:-1], c)
        wrong = copy.deepcopy(rows)
        wrong[-1] = copy.deepcopy(wrong[0])
        with self.assertRaises(data.InputError):
            data.validate_rows(wrong, c)
        voxels = [{"projection_row": i, "native_row_index": i, "voxel_id": i, "subject_id": "01",
                   "V1": i < 1049, "IT": i >= 1049} for i in range(5130)]
        data.validate_voxels(voxels, "01")
        with self.assertRaises(data.InputError):
            data.validate_voxels(voxels[:-1], "01")
        swapped = copy.deepcopy(voxels)
        swapped[0], swapped[1] = swapped[1], swapped[0]
        with self.assertRaises(data.InputError):
            data.validate_voxels(swapped, "01")

    def test_bounded_fresh_npy_writer_and_path_guards(self):
        path = self.root / "small.npy"
        budget = prep._Budget()
        array = np.arange(24, dtype="<f4").reshape(3, 8)
        d = prep._write_npy(path, array, budget)
        self.assertEqual(data.pin(d), describe(path))
        self.assertEqual(budget.used, d["bytes"])
        np.testing.assert_array_equal(data.read_primitive_npy(path, d, [3, 8], 1000), array)
        with self.assertRaises(OSError):
            prep._write_npy(path, array, budget)
        small_budget = prep._Budget()
        small_budget.used = data.PACKET_CAP - 1
        bounded = self.root / "bounded.npy"
        with self.assertRaises(data.InputError):
            prep._write_npy(bounded, array, small_budget)
        self.assertEqual(bounded.stat().st_size, 0)
        self.assertLessEqual(small_budget.used, data.PACKET_CAP)
        for relative in ("../other", "/absolute", "a/../b", "a//b", "a\\b"):
            with self.subTest(relative=relative), self.assertRaises(data.InputError):
                data.safe_path(self.root, relative)
        (self.root / "link").symlink_to(path)
        with self.assertRaises(data.InputError):
            data.safe_path(self.root, "link")

    def test_production_has_no_reduced_design_or_overwrite_switch(self):
        (self.root / "public").mkdir()
        (self.root / "private").mkdir()
        with self.assertRaises(data.InputError):
            prep.prepare_packet(self.root, self.root / "shared", {"bytes": 1, "sha256": "0"*64},
                                {"bytes": 1, "sha256": "0"*64}, self.root)
        self.assertFalse((self.root / "public/input").exists())
        (self.root / "public/input").mkdir()
        with mock.patch.object(prep, "_source_metadata", side_effect=AssertionError("source touched before fresh path check")):
            with self.assertRaises(data.InputError):
                prep.prepare_packet(self.root, self.root / "shared", {}, data.DESIGN_PIN, self.root)


if __name__ == "__main__":
    unittest.main(verbosity=2)
