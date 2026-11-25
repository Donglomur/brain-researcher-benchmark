"""Generated tiny NPZ controls; never allocate forged shape declarations."""
import hashlib
import io
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest import mock
import warnings
import zipfile

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "source"))
from find032 import artifacts, complete_capture
from find032.core import Custody, Refusal
from find032.products import ProductKey
from find032.roster import PARTICIPANTS


class Budget:
    def reserve(self, kind, amount):
        return kind, amount
    def observed(self, token, amount):
        pass
    def checkpoint(self):
        pass


def npy(array, version=(1, 0), *, shape=None, fortran=False, long_suffix=False, comment=""):
    array = np.asarray(array)
    header = repr({"descr": np.lib.format.dtype_to_descr(array.dtype),
                   "fortran_order": fortran, "shape": array.shape if shape is None else shape})
    if long_suffix:
        header = header.replace("'shape': (2, 2)", "'shape': (2L, 2L)")
    if comment:
        header += " #" + comment
    encoding = "utf-8" if version == (3, 0) else "latin1"
    raw = header.encode(encoding)
    width = 2 if version == (1, 0) else 4
    raw += b" " * (-(8 + width + len(raw) + 1) % 64) + b"\n"
    prefix = b"\x93NUMPY" + bytes(version) + struct.pack("<H" if width == 2 else "<I", len(raw))
    return prefix + raw + array.tobytes(order="F" if fortran else "C")


def archive(members):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as handle:
        for name, body in members.items():
            handle.writestr(name + ".npy", body)
    return stream.getvalue()


def invoke(raw, method, *, members=()):
    key = ProductKey(PARTICIPANTS[0], "sound", "replication", "random", "accuracy")
    name = artifacts.product_name(key)
    row = {"name": name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    row.update({"key": [key.participant, key.stimulus, key.pipeline, key.condition, key.score]}
               if method == "product" else {"npz_members": list(members)})
    with tempfile.TemporaryDirectory() as temporary:
        (Path(temporary) / name).write_bytes(raw)
        fd = os.open(temporary, os.O_RDONLY | os.O_DIRECTORY)
        try:
            function = artifacts.load_product if method == "product" else complete_capture._npz
            return function(fd, row, Budget(), Custody(), member_bytes=65536)
        finally:
            os.close(fd)


class MemberExtentTests(unittest.TestCase):
    def test_product_shape_is_bounded_before_decoder(self):
        for version in ((1, 0), (2, 0), (3, 0)):
            members = {"value": npy(np.empty((0,), dtype="f8"), version, shape=(2**60, 2)),
                       "train_times": npy(np.array([0., 1.]), version),
                       "test_times": npy(np.array([0., 1.]), version)}
            with self.subTest(version=version), mock.patch.object(np, "load", side_effect=AssertionError("decoder reached")) as decode:
                with self.assertRaisesRegex(Refusal, "declared array exceeds"):
                    invoke(archive(members), "product")
                decode.assert_not_called()

    def test_group_shape_is_bounded_before_decoder(self):
        for version in ((1, 0), (2, 0), (3, 0)):
            raw = archive({"subject_values": npy(np.empty((0,), dtype="f8"), version, shape=(33, 2**60, 141))})
            with self.subTest(version=version), mock.patch.object(np, "load", side_effect=AssertionError("decoder reached")) as decode:
                with self.assertRaisesRegex(Refusal, "declared array exceeds"):
                    invoke(raw, "group", members=("subject_values.npy",))
                decode.assert_not_called()

    def test_valid_products_retain_versions_order_and_python2_headers(self):
        expected = np.array([[.1, .2], [.3, .4]], dtype="f8")
        for version in ((1, 0), (2, 0), (3, 0)):
            for order in (False, True):
                members = {"value": npy(expected, version, fortran=order, long_suffix=version != (3, 0)),
                           "train_times": npy(np.array([0., 1.]), version),
                           "test_times": npy(np.array([0., 1.]), version)}
                with self.subTest(version=version, order=order), warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    _, actual, axes, _ = invoke(archive(members), "product")
                    np.testing.assert_array_equal(actual, expected)
                    np.testing.assert_array_equal(axes[0], [0., 1.])

    def test_empty_boolean_group_members_remain_valid(self):
        for version in ((1, 0), (2, 0), (3, 0)):
            raw = archive({"cluster_masks": npy(np.empty((0, 2, 2), dtype=bool), version)})
            actual, _ = invoke(raw, "group", members=("cluster_masks.npy",))
            self.assertEqual(actual["cluster_masks"].shape, (0, 2, 2))
            self.assertEqual(actual["cluster_masks"].dtype.kind, "b")

    def test_utf8_header_character_limit_remains_compatible(self):
        expected = np.array([[.1, .2], [.3, .4]], dtype="f8")
        members = {"value": npy(expected, (3, 0), comment="é" * 6000),
                   "train_times": npy(np.array([0., 1.]), (3, 0)),
                   "test_times": npy(np.array([0., 1.]), (3, 0))}
        _, actual, _, _ = invoke(archive(members), "product")
        np.testing.assert_array_equal(actual, expected)


if __name__ == "__main__":
    unittest.main()
