"""Independent generated storage-boundary controls; no authentic input access."""
import io
import json
from pathlib import Path
import runpy
import struct
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import numpy as np

import packet


def generated_members():
    result = {}
    for name, (shape, dtype) in packet.ARRAY_LAYOUT.items():
        stream = io.BytesIO()
        np.save(stream, np.zeros(shape, dtype=dtype), allow_pickle=False)
        result[name + ".npy"] = stream.getvalue()
    return result


def make_zip(members, compression=zipfile.ZIP_DEFLATED):
    stream = io.BytesIO()
    items = members.items() if isinstance(members, dict) else members
    with zipfile.ZipFile(stream, "w", compression=compression) as archive:
        for name, body in items:
            archive.writestr(name, body)
    return stream.getvalue()


def raw_npy(shape=(204, 54, 20), dtype="<u4", fortran=False,
            payload=b"", extra_header=""):
    text = repr({"descr": dtype, "fortran_order": fortran, "shape": shape})
    header = (text + extra_header).encode("latin1")
    header += b" " * ((64 - (10 + len(header) + 1) % 64) % 64) + b"\n"
    return b"\x93NUMPY\x01\x00" + struct.pack("<H", len(header)) + header + payload


class PacketBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # These zeros exercise only container/layout behavior, not physiology.
        cls.members = generated_members()

    def test_generated_numeric_npz_roundtrip(self):
        arrays = packet.decode_arrays(make_zip(self.members))
        self.assertEqual(set(arrays), packet.ARRAY_NAMES)
        for name, (shape, dtype) in packet.ARRAY_LAYOUT.items():
            self.assertEqual(arrays[name].shape, shape)
            self.assertEqual(arrays[name].dtype, np.dtype(dtype))
            self.assertTrue(np.all(arrays[name] == 0))

    def test_dangerous_npy_header_rejected_before_array_allocation(self):
        invalid = {
            "huge_declared_shape": raw_npy(shape=(10**12,)),
            "object_dtype": raw_npy(dtype="|O"),
            "fortran_layout": raw_npy(fortran=True),
            "wrong_numeric_dtype": raw_npy(dtype="<f8"),
            "truncated_numeric_payload": raw_npy(),
            "oversized_header": raw_npy(extra_header=" " * 1200),
            "trailing_numeric_payload": self.members["counts.npy"] + b"x",
        }
        for name, body in invalid.items():
            with self.subTest(name=name):
                members = dict(self.members)
                members["counts.npy"] = body
                with patch.object(packet.np, "load", side_effect=AssertionError("allocated")) as load:
                    with self.assertRaises(packet.PacketError):
                        packet.decode_arrays(make_zip(members))
                    load.assert_not_called()

    def test_names_count_and_declared_expansion_checked_before_loading(self):
        replacements = [
            {**self.members, "extra.npy": b"x"},
            {("../counts.npy" if name == "counts.npy" else name): body
             for name, body in self.members.items()},
            {**self.members, "counts.npy": b"x" * (packet.MAX_EXPANDED_ARRAY_BYTES + 1)},
        ]
        for members in replacements:
            with self.subTest(names=tuple(members)):
                with patch.object(packet.np, "load", side_effect=AssertionError("allocated")) as load:
                    with self.assertRaises(packet.PacketError):
                        packet.decode_arrays(make_zip(members))
                    load.assert_not_called()

    def test_corrupt_member_crc_refused_before_loading(self):
        body = bytearray(make_zip(self.members, compression=zipfile.ZIP_STORED))
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            entry = archive.getinfo("counts.npy")
            start = entry.header_offset
            name_length, extra_length = struct.unpack_from("<HH", body, start + 26)
            payload_start = start + 30 + name_length + extra_length
            body[payload_start + entry.file_size - 1] ^= 1
        with patch.object(packet.np, "load", side_effect=AssertionError("allocated")) as load:
            with self.assertRaises(packet.PacketError):
                packet.decode_arrays(bytes(body))
            load.assert_not_called()

    def test_json_duplicate_nonfinite_and_extreme_exponent_refused(self):
        for body in (b'{"x":1,"x":2}', b'{"x":{"a":1,"a":2}}',
                     b'{"x":NaN}', b'{"x":Infinity}', b'{"x":-Infinity}',
                     b'{"x":1e999}', b'{"x":-1e999}'):
            with self.subTest(body=body), self.assertRaises(packet.PacketError):
                packet.strict_json(body)
        self.assertEqual(packet.strict_json(b'{"x":1e-3,"y":2}'), {"x":0.001,"y":2})

    def test_self_authored_receipt_cannot_assert_original_provenance(self):
        body = json.dumps({"source_sha256": packet.SOURCE_SHA256}).encode()
        body += b" " * (packet.RECEIPT_BYTES - len(body))
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "receipt.json").write_bytes(body)
            with patch.object(packet, "decode_arrays", side_effect=AssertionError("decoded")) as decode:
                with self.assertRaisesRegex(packet.PacketError, "receipt identity"):
                    packet.load_original_packet(directory)
                decode.assert_not_called()

    def test_modified_body_is_rejected_in_generated_receipt_join(self):
        # Override the immutable expected pin ONLY inside this generated test.
        # This reaches the downstream join without reading an authentic receipt
        # and does not qualify an actual packet or introduce a runtime bypass.
        metadata = b"{}"
        arrays = make_zip(self.members)
        receipt = {
            "schema": "neural096_source_preparation_receipt_v1",
            "status": "complete_source_observations_prepared",
            "source_sha256": packet.SOURCE_SHA256,
            "files": [
                {"path":"observations.json", "bytes":len(metadata),
                 "sha256":packet.sha256(metadata)},
                {"path":"observations.npz", "bytes":len(arrays),
                 "sha256":packet.sha256(arrays)},
            ],
        }
        body = json.dumps(receipt, sort_keys=True).encode()
        original_pin = packet.RECEIPT_SHA256
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / "receipt.json").write_bytes(body)
            (base / "observations.json").write_bytes(b"[]")
            (base / "observations.npz").write_bytes(arrays)
            with patch.object(packet, "RECEIPT_BYTES", len(body)), \
                 patch.object(packet, "RECEIPT_SHA256", packet.sha256(body)), \
                 patch.object(packet, "decode_arrays", side_effect=AssertionError("decoded")) as decode:
                with self.assertRaisesRegex(packet.PacketError, "packet file changed"):
                    packet.load_original_packet(directory)
                decode.assert_not_called()
        self.assertEqual(packet.RECEIPT_SHA256, original_pin)

    def test_bounded_file_refuses_symlink_and_oversize(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "small"
            link = Path(directory) / "link"
            file.write_bytes(b"ab")
            link.symlink_to(file)
            with self.assertRaisesRegex(packet.PacketError, "ordinary file"):
                packet.bounded_file(link, 2)
            with self.assertRaisesRegex(packet.PacketError, "size outside"):
                packet.bounded_file(file, 1)
            self.assertEqual(packet.bounded_file(file, 2), b"ab")

    def test_module_has_no_packet_read_on_import(self):
        with patch.object(Path, "open", side_effect=AssertionError("file read")), \
             patch.object(np, "load", side_effect=AssertionError("array load")):
            namespace = runpy.run_path(packet.__file__, run_name="packet_import_check")
        self.assertEqual(namespace["RECEIPT_SHA256"], packet.RECEIPT_SHA256)


if __name__ == "__main__":
    unittest.main()
