"""Generated NPY compatibility controls for the existing NEURAL-070 reader.

No collector, observation mode, authentic array, Engine or source-data execution
is involved. Native custody reads are replaced by an explicit in-memory fixture
shim; the actual numeric_io.array parsing and validation code is exercised.
"""
import argparse
import hashlib
import importlib.util
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch

import numpy as np


DEFAULT_PROGRAMME = (Path(__file__).resolve().parents[2]
                     / "benchmarks/neural/NEURAL-070/implementations/registered-runtime/programme")
parser = argparse.ArgumentParser(add_help=False)
parser.add_argument("--programme-root", type=Path, default=DEFAULT_PROGRAMME)
parser.add_argument("--numeric-source", type=Path)
OPTIONS, REMAINING = parser.parse_known_args()
sys.path.insert(0, str(OPTIONS.programme_root.resolve()))


def reader_module():
    source = OPTIONS.numeric_source or OPTIONS.programme_root / "n070/numeric_io.py"
    spec = importlib.util.spec_from_file_location("n070._numeric_io_regression", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def generated_npy(version=(1, 0), *, shape=(2, 2), dtype="<f8", fortran=False,
                  payload=None, extra_header=0):
    """Construct only primitive fixture bytes; do not reuse the production reader."""
    text = repr({"descr": dtype, "fortran_order": fortran, "shape": shape}).encode("ascii")
    prefix_length = 10 if version == (1, 0) else 12
    padding = (-(prefix_length + len(text) + extra_header + 1)) % 64
    text += b" " * (extra_header + padding) + b"\n"
    size_format = "<H" if version == (1, 0) else "<I"
    prefix = b"\x93NUMPY" + bytes(version) + struct.pack(size_format, len(text))
    if payload is None:
        payload = struct.pack("<dddd", 1., 2., 3., 4.)
    return prefix + text + payload


class Neural070PrimitiveIO(unittest.TestCase):
    def decode(self, body, *, shape=(2, 2), cap=8192):
        module = reader_module()
        descriptor = {"path": "generated.npy", "bytes": len(body),
                      "sha256": hashlib.sha256(body).hexdigest(), "shape": list(shape)}

        def fixture_read(path, limit, received_descriptor):
            self.assertEqual(path, Path("/generated-not-opened/generated.npy"))
            self.assertEqual(limit, len(body))
            self.assertEqual(received_descriptor, descriptor)
            return body

        # The production read/path functions require the native resource owner.
        # These narrow shims expose their boundary, not a claim of OS isolation.
        with patch.object(module, "read", fixture_read), patch.object(module, "relative", lambda p: p):
            return module.array(Path("/generated-not-opened"), descriptor, cap)

    def test_npy_v1_v2_and_both_memory_orders(self):
        for version in ((1, 0), (2, 0)):
            with self.subTest(version=version, fortran=False):
                actual = self.decode(generated_npy(version))
                np.testing.assert_array_equal(actual, [[1., 2.], [3., 4.]])
                self.assertEqual(actual.dtype, np.dtype("<f8"))
            with self.subTest(version=version, fortran=True):
                np.testing.assert_array_equal(self.decode(generated_npy(version, fortran=True)),
                                              [[1., 3.], [2., 4.]])

    def test_invalid_headers_and_extents_refuse_before_array_load(self):
        cases = [
            (generated_npy(shape=(2**40, 2)), (2**40, 2), 8192),
            (generated_npy(shape=(0, 2), payload=b""), (0, 2), 8192),
            (generated_npy((2, 0), dtype="|O"), (2, 2), 8192),
            (generated_npy((2, 0)) + b"x", (2, 2), 8192),
            (generated_npy(extra_header=5000), (2, 2), 8192),
            (generated_npy((2, 0)), (4, 1), 8192),
            (generated_npy(), (2, 2), 16),
            (generated_npy((3, 0)), (2, 2), 8192),
        ]
        for body, shape, cap in cases:
            with self.subTest(shape=shape, bytes=len(body), cap=cap):
                with patch.object(np, "load", side_effect=AssertionError("No array load before admission")) as load:
                    with self.assertRaises(ValueError):
                        self.decode(body, shape=shape, cap=cap)
                    load.assert_not_called()

    def test_nonfinite_payload_still_refuses_after_primitive_decode(self):
        for bad in (float("nan"), float("inf"), float("-inf")):
            for version in ((1, 0), (2, 0)):
                with self.subTest(value=bad, version=version), self.assertRaises(ValueError):
                    self.decode(generated_npy(version, payload=struct.pack("<dddd", 1., bad, 3., 4.)))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0], *REMAINING], verbosity=2)
