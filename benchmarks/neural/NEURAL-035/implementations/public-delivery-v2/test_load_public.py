"""Generated controls only: no original traces, private targets or model calls."""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import numpy as np


HERE = Path(__file__).resolve().parent


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


loader = module(HERE / "load_public.py", "neural035_public_v2")


def identity(value):
    return hashlib.sha256(str(value).encode()).hexdigest()


def archive_bytes(calibration, validation):
    stream = io.BytesIO()
    np.savez_compressed(stream, calibration=calibration, validation=validation)
    return stream.getvalue()


def zip_members(members):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, body in members:
            archive.writestr(name, body)
    return stream.getvalue()


def npy_header(header, payload=b""):
    body = (header + "\n").encode("latin1")
    return b"\x93NUMPY\x01\x00" + struct.pack("<H", len(body)) + body + payload


class PublicDeliveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="neural035-generated-")
        cls.folder = Path(cls.temporary.name).resolve()
        cls.manifest = {"schema": "neural035-public-v1", "sessions": []}
        for i in range(14):
            n = 76 if i == 13 else 72
            sid = identity(f"generated-session-{i}")
            # Distinct sample/cell values detect axis or order changes. These
            # values are engineering fixtures, not astrocytic measurements.
            calibration = np.arange(4 * 300 * n, dtype=np.float64).reshape(4, 300, n)
            validation = np.full((1, 300, n), i + 0.25, dtype=np.float64)
            raw = archive_bytes(calibration, validation)
            (cls.folder / (sid + ".npz")).write_bytes(raw)
            cls.manifest["sessions"].append({
                "session_id": sid, "cell_ids": [identity(f"cell-{k}") for k in range(n)],
                "file": sid + ".npz", "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                "calibration_starts_seconds": [0, 30, 60, 90],
                "validation_starts_seconds": [150],
                "queries": [{"query_id": identity(f"query-{i}-{j}"), "start_seconds": start}
                            for j, start in enumerate((210, 270))]})
        (cls.folder / "MANIFEST.json").write_text(json.dumps(cls.manifest))

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def mutate(self, change):
        value = copy.deepcopy(self.manifest)
        change(value)
        return value

    def assert_before_archive_access(self, manifest):
        raw = json.dumps(manifest).encode()
        with patch.object(loader.safe, "read", return_value=raw), \
                patch.object(loader.safe, "captured", side_effect=AssertionError("archive accessed")):
            with self.assertRaises(ValueError):
                loader.load(self.folder, np)

    def test_complete_public_payload_preserves_order_values_and_session_local_ids(self):
        rows = loader.load(self.folder, np)
        self.assertEqual(len(rows), 14)
        self.assertEqual(sum(row["calibration"].shape[2] for row in rows), 1012)
        self.assertEqual(sum(len(row["metadata"]["queries"]) for row in rows), 28)
        self.assertEqual(sum(row[name].nbytes for row in rows for name in ("calibration", "validation")),
                         12_144_000)
        for i, row in enumerate(rows):
            n = len(row["metadata"]["cell_ids"])
            np.testing.assert_array_equal(row["calibration"],
                                          np.arange(4 * 300 * n).reshape(4, 300, n))
            np.testing.assert_array_equal(row["validation"], np.full((1, 300, n), i + 0.25))
            self.assertEqual(row["metadata"], self.manifest["sessions"][i])

    def test_predecessor_accepts_wrong_query_time_new_loader_rejects_before_read(self):
        old_path = HERE.parent / "delivery-source" / "load_public.py"
        # The predecessor imports its io_utils alias; restore import state after
        # the witness rather than changing participant/module isolation.
        with patch.object(sys, "path", list(sys.path)), patch.dict(sys.modules):
            old = module(old_path, "neural035_public_v1")
            wrong = self.mutate(lambda x: x["sessions"][-1]["queries"][1].update(start_seconds=150))
            with patch.object(old.safe, "strict", return_value=wrong):
                self.assertEqual(len(old.load(self.folder, np)), 14)
        self.assert_before_archive_access(wrong)

    def test_full_cohort_metadata_is_checked_before_first_archive(self):
        mutations = {
            "reduced cells": lambda x: x["sessions"][-1]["cell_ids"].pop(),
            "missing session": lambda x: x["sessions"].pop(),
            "unknown cell identity": lambda x: x["sessions"][-1]["cell_ids"].__setitem__(0, "mouse-A"),
            "duplicate cell": lambda x: x["sessions"][-1]["cell_ids"].__setitem__(0, x["sessions"][-1]["cell_ids"][1]),
            "duplicate session": lambda x: x["sessions"].__setitem__(-1, copy.deepcopy(x["sessions"][0])),
            "wrong calibration": lambda x: x["sessions"][-1].update(calibration_starts_seconds=[0, 30, 60, 210]),
            "wrong validation": lambda x: x["sessions"][-1].update(validation_starts_seconds=[270]),
            "float time": lambda x: x["sessions"][-1].update(validation_starts_seconds=[150.0]),
            "boolean time": lambda x: x["sessions"][-1].update(calibration_starts_seconds=[False, 30, 60, 90]),
            "duplicate query": lambda x: x["sessions"][-1]["queries"][1].update(query_id=x["sessions"][0]["queries"][0]["query_id"]),
            "extra query metadata": lambda x: x["sessions"][-1]["queries"][0].update(mouse="hidden"),
            "extra session metadata": lambda x: x["sessions"][-1].update(context="cxta"),
            "boolean size": lambda x: x["sessions"][-1].update(bytes=True),
            "bad checksum": lambda x: x["sessions"][-1].update(sha256="0"),
            "file traversal": lambda x: x["sessions"][-1].update(file="../private.npz"),
        }
        for label, change in mutations.items():
            with self.subTest(label=label):
                self.assert_before_archive_access(self.mutate(change))

    def test_hash_mismatch_rejected_on_actual_file_path(self):
        changed = self.mutate(lambda x: x["sessions"][0].update(sha256="0" * 64))
        with patch.object(loader.safe, "strict", return_value=changed):
            with self.assertRaisesRegex(ValueError, "SHA256"):
                loader.load(self.folder, np)

    def test_duplicate_manifest_fields_rejected(self):
        raw = b'{"schema":"neural035-public-v1","schema":"neural035-public-v1","sessions":[]}'
        with patch.object(loader.safe, "read", return_value=raw):
            with self.assertRaisesRegex(ValueError, "duplicate JSON"):
                loader.load(self.folder, np)

    def test_bad_npy_geometry_refused_before_numpy_allocation(self):
        headers = [
            "{'descr':'<f8','fortran_order':False,'shape':(4,300,10000000000)}",
            "{'descr':'|O','fortran_order':False,'shape':(4,300,72)}",
            "{'descr':'<f8','fortran_order':False,'shape':(4,300,72),'shape':(4,300,72)}",
            "{'descr':'<f8','fortran_order':False,'shape':(4,300,True)}",
        ]
        for header in headers:
            raw = zip_members([("calibration.npy", npy_header(header)),
                               ("validation.npy", b"placeholder")])
            with self.subTest(header=header), \
                    patch.object(loader.safe, "captured", return_value=raw), \
                    patch.object(np, "load", side_effect=AssertionError("NumPy allocation reached")):
                with self.assertRaises(ValueError):
                    loader.load(self.folder, np)

    def test_exact_payload_length_no_trailing_bytes(self):
        raw = archive_bytes(np.zeros((4, 300, 2)), np.zeros((1, 300, 2)))
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            members = [(name, archive.read(name)) for name in archive.namelist()]
        for suffix in (b"extra",):
            changed = [(name, body + suffix if name == "calibration.npy" else body)
                       for name, body in members]
            with self.assertRaisesRegex(ValueError, "payload length"):
                loader._archive_members(zip_members(changed), 2)
        shortened = [(name, body[:-8] if name == "calibration.npy" else body) for name, body in members]
        with self.assertRaisesRegex(ValueError, "payload length"):
            loader._archive_members(zip_members(shortened), 2)

    def test_query_member_and_oversized_header_rejected(self):
        with self.assertRaisesRegex(ValueError, "archive members"):
            loader._archive_members(zip_members([("calibration.npy", b"x"), ("query.npy", b"y")]), 2)
        with self.assertRaisesRegex(ValueError, "bounded NPY header"):
            loader._npy_header(b"\x93NUMPY\x02\x00" + struct.pack("<I", 100_000_000), (4, 300, 2))

    def test_nonfinite_public_trace_rejected(self):
        calibration = np.zeros((4, 300, 72), dtype=np.float64)
        calibration[0, 0, 0] = np.nan
        raw = archive_bytes(calibration, np.zeros((1, 300, 72), dtype=np.float64))
        with patch.object(loader.safe, "captured", return_value=raw):
            with self.assertRaisesRegex(ValueError, "finite native float64"):
                loader.load(self.folder, np)

    def test_fortran_order_remains_supported(self):
        calibration = np.asfortranarray(np.arange(4 * 300 * 2, dtype=np.float64).reshape(4, 300, 2))
        raw = archive_bytes(calibration, np.zeros((1, 300, 2), dtype=np.float64))
        members = loader._archive_members(raw, 2)
        np.testing.assert_array_equal(np.load(io.BytesIO(members["calibration"]), allow_pickle=False), calibration)


if __name__ == "__main__":
    print("Generated fixtures; NumPy " + np.__version__ + "; no authentic data or model execution.")
    unittest.main()
