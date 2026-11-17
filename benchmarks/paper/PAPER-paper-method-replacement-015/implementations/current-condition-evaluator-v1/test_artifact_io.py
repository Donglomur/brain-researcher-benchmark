"""Generated-file controls for bounded, pinned operator artifacts.

No released calcium traces, target arrays, models, or scientific scores are used.
Archive corruption controls exercise admission before numerical evaluation.
"""
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock
import warnings
import zipfile

import numpy as np

import artifact_io


def sha256(payload):
    return hashlib.sha256(payload).hexdigest()


def npy_array(values, dtype="<f8"):
    stream = io.BytesIO()
    np.save(stream, np.asarray(values, dtype=dtype), allow_pickle=False)
    return stream.getvalue()


def custom_npy(header, body, version=(1, 0)):
    """Build a small NPY wire fixture without asking NumPy to admit its header."""
    header = header.encode("latin1") if isinstance(header, str) else header
    width = 2 if version == (1, 0) else 4
    prefix_length = 8 + width
    padding = (-(prefix_length + len(header) + 1)) % 64
    header = header + b" " * padding + b"\n"
    return (b"\x93NUMPY" + bytes(version)
            + len(header).to_bytes(width, "little") + header + body)


def stored_npz(entries, compression=zipfile.ZIP_STORED):
    stream = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(stream, "w", compression=compression) as archive:
            for name, payload in entries:
                archive.writestr(name, payload)
    return stream.getvalue()


class FileFixture(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="spinal-artifact-control-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def file(self, relative, payload):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        return path

    def pin(self, relative, payload):
        self.file(relative, payload)
        return {"path": relative, "bytes": len(payload), "sha256": sha256(payload)}


class JsonAdmissionTests(FileFixture):
    def test_valid_utf8_object_returns_original_byte_identity(self):
        payload = '{ "label": "μ", "rows": [{"n": 3}], "rate": 2.5 }\n'.encode()
        result, identity = artifact_io.read_json(
            self.file("manifest.json", payload), expected_sha=sha256(payload))
        self.assertEqual(result, {"label": "μ", "rows": [{"n": 3}], "rate": 2.5})
        self.assertEqual(identity, sha256(payload))

    def test_hash_checks_exact_serialization_and_is_not_optional_when_supplied(self):
        payload = b'{"n": 3}\n'
        path = self.file("manifest.json", payload)
        for identity in (sha256(b'{"n":3}'), "0" * 64, "A" * 64, "x", ""):
            with self.subTest(identity=identity), self.assertRaises(ValueError):
                artifact_io.read_json(path, expected_sha=identity)

    def test_duplicate_keys_are_rejected_at_all_nesting_levels(self):
        cases = [b'{"n":1,"n":2}', b'{"outer":{"n":1,"n":2}}',
                 b'{"rows":[{"n":1,"n":2}]}', b'{"n":1,"\\u006e":2}']
        for payload in cases:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                artifact_io.read_json(self.file("manifest.json", payload))

    def test_nonfinite_literals_and_exponent_overflow_are_rejected(self):
        for token in ("NaN", "Infinity", "-Infinity", "1e400", "-1e400"):
            payload = ('{"nested":[{"value":' + token + '}]}').encode()
            with self.subTest(token=token), self.assertRaises(ValueError):
                artifact_io.read_json(self.file("manifest.json", payload))

    def test_nonobjects_and_trailing_documents_are_rejected(self):
        for payload in (b"[]", b"null", b"1", b'"object"', b"{} {}", b'{"a":}'):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                artifact_io.read_json(self.file("manifest.json", payload))

    def test_byte_limit_includes_utf8_encoding_and_boundary(self):
        payload = json.dumps({"label": "μ"}, ensure_ascii=False).encode()
        path = self.file("manifest.json", payload)
        self.assertEqual(artifact_io.read_json(path, limit=len(payload))[0], {"label": "μ"})
        with self.assertRaises(ValueError):
            artifact_io.read_json(path, limit=len(payload) - 1)

    def test_symlink_directory_and_missing_json_are_rejected(self):
        target = self.file("real.json", b"{}")
        link = self.root / "link.json"
        link.symlink_to(target)
        for path in (link, self.root, self.root / "missing.json"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                artifact_io.read_json(path)


class PinnedFileTests(FileFixture):
    def test_nested_regular_file_is_returned_as_exact_immutable_bytes(self):
        payload = b"generated immutable artifact\x00\xff"
        result = artifact_io.read_pinned(self.root, self.pin("nested/source.bin", payload))
        self.assertIs(type(result), bytes)
        self.assertEqual(result, payload)

    def test_pin_schema_requires_exact_fields_and_typed_identity(self):
        pin = self.pin("source.bin", b"abc")
        variants = [None, [], {**pin, "extra": 1}, {k: v for k, v in pin.items() if k != "sha256"},
                    {**pin, "path": 3}, {**pin, "sha256": 3}, {**pin, "sha256": "A" * 64},
                    {**pin, "bytes": True}, {**pin, "bytes": 3.0}, {**pin, "bytes": 0},
                    {**pin, "bytes": -1}]
        for candidate in variants:
            with self.subTest(pin=candidate), self.assertRaises(ValueError):
                artifact_io.read_pinned(self.root, candidate)

    def test_traversal_absolute_and_noncanonical_paths_are_rejected(self):
        pin = self.pin("nested/source.bin", b"abc")
        paths = ["../source.bin", str(self.root / "nested/source.bin"),
                 "./nested/source.bin", "nested/../nested/source.bin", "nested//source.bin",
                 "nested/source.bin/", "nested\\source.bin", "", "."]
        for path in paths:
            with self.subTest(path=path), self.assertRaises(ValueError):
                artifact_io.read_pinned(self.root, {**pin, "path": path})

    def test_wrong_size_wrong_digest_and_post_pin_replacement_are_rejected(self):
        pin = self.pin("source.bin", b"abc")
        for candidate in ({**pin, "bytes": 2}, {**pin, "bytes": 4}, {**pin, "sha256": "0" * 64}):
            with self.subTest(pin=candidate), self.assertRaises(ValueError):
                artifact_io.read_pinned(self.root, candidate)
        self.file("source.bin", b"xyz")
        with self.assertRaises(ValueError):
            artifact_io.read_pinned(self.root, pin)

    def test_pin_budget_checked_before_artifact_read(self):
        pin = self.pin("source.bin", b"abc")
        self.assertEqual(artifact_io.read_pinned(self.root, pin, limit=3), b"abc")
        with self.assertRaises(ValueError):
            artifact_io.read_pinned(self.root, pin, limit=2)

    def test_symlink_file_parent_and_root_are_rejected(self):
        payload = b"abc"
        pin = self.pin("real/source.bin", payload)
        (self.root / "file-link.bin").symlink_to(self.root / "real/source.bin")
        (self.root / "parent-link").symlink_to(self.root / "real", target_is_directory=True)
        root_link = self.root / "root-link"
        root_link.symlink_to(self.root / "real", target_is_directory=True)
        for root, path in ((self.root, "file-link.bin"), (self.root, "parent-link/source.bin"),
                           (root_link, "source.bin")):
            with self.subTest(root=root, path=path), self.assertRaises(ValueError):
                artifact_io.read_pinned(root, {**pin, "path": path})

    def test_nonregular_artifact_and_non_directory_root_are_rejected(self):
        pin = self.pin("source.bin", b"abc")
        directory = self.root / "directory"
        directory.mkdir()
        fifo = self.root / "fifo"
        os.mkfifo(fifo)
        for path in ("directory", "fifo", "missing.bin"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                artifact_io.read_pinned(self.root, {**pin, "path": path})
        with self.assertRaises(ValueError):
            artifact_io.read_pinned(self.root / "source.bin", pin)

    def test_decode_uses_pinned_snapshot_after_backing_file_changes(self):
        first = stored_npz([("rate.npy", npy_array([1.25, 2.5]))])
        second = stored_npz([("rate.npy", npy_array([91.25, 92.5]))])
        pin = self.pin("prediction.npz", first)
        admitted = artifact_io.read_pinned(self.root, pin)
        self.file("prediction.npz", second)
        decoded = artifact_io.read_npz_bytes(admitted, {"rate": ("float64", 2)})["rate"]
        np.testing.assert_array_equal(decoded, [1.25, 2.5])
        self.assertEqual(sha256(admitted), pin["sha256"])
        self.assertFalse(decoded.flags.writeable)
        with self.assertRaises(ValueError):
            decoded[0] = 99
        with self.assertRaises(ValueError):
            decoded.setflags(write=True)


class NpzAdmissionTests(unittest.TestCase):
    def reject(self, payload, expected=None):
        with self.assertRaises((ValueError, zipfile.BadZipFile, SyntaxError)):
            artifact_io.read_npz_bytes(payload, expected or {"rate": ("float64", 3)})

    def test_normal_numpy_savez_accepts_all_five_array_roles(self):
        stream = io.BytesIO()
        np.savez(stream, rate=np.array([1.0, 2.0, 3.0], dtype="<f8"),
                 count=np.array([1, 0, 2], dtype="<i8"),
                 support=np.array([True, False, True]),
                 small=np.array([1, 2, 3], dtype="u1"),
                 big_endian=np.array([1.5, 2.5, 3.5], dtype=">f8"))
        decoded = artifact_io.read_npz_bytes(stream.getvalue(), {
            "rate": ("float64", 3), "count": ("int64", 3), "support": ("bool", 3),
            "small": ("numeric", 3), "big_endian": ("float64", 3)})
        self.assertEqual(set(decoded), {"rate", "count", "support", "small", "big_endian"})
        np.testing.assert_array_equal(decoded["count"], [1, 0, 2])
        np.testing.assert_array_equal(decoded["support"], [True, False, True])
        np.testing.assert_array_equal(decoded["big_endian"], [1.5, 2.5, 3.5])
        for values in decoded.values():
            self.assertEqual(values.shape, (3,))
            self.assertFalse(values.flags.writeable)

    def test_npy_version_two_is_supported(self):
        payload = custom_npy("{'descr': '<f8', 'fortran_order': False, 'shape': (3,)}",
                             struct.pack("<3d", 1.5, 2.5, 3.5), version=(2, 0))
        decoded = artifact_io.read_npz_bytes(stored_npz([("rate.npy", payload)]), {"rate": ("float64", 3)})
        np.testing.assert_array_equal(decoded["rate"], [1.5, 2.5, 3.5])

    def test_archive_must_have_exact_member_set_without_duplicates(self):
        values = npy_array([1, 2, 3])
        cases = [[], [("wrong.npy", values)], [("rate.npy", values), ("extra.npy", values)],
                 [("rate.npy", values), ("rate.npy", values)], [("../rate.npy", values)],
                 [("rate.npy/", b"")], [("rate", values)]]
        for entries in cases:
            with self.subTest(names=[name for name, _ in entries]):
                self.reject(stored_npz(entries))

    def test_compressed_and_encrypted_entries_are_rejected(self):
        entries = [("rate.npy", npy_array([1, 2, 3]))]
        self.reject(stored_npz(entries, compression=zipfile.ZIP_DEFLATED))
        encrypted = bytearray(stored_npz(entries))
        central = encrypted.index(b"PK\x01\x02")
        encrypted[6:8] = (1).to_bytes(2, "little")
        encrypted[central + 8:central + 10] = (1).to_bytes(2, "little")
        self.reject(bytes(encrypted))

    def test_invalid_zip_and_crc_corruption_are_rejected(self):
        for payload in (b"", b"not a zip", stored_npz([])[:-4]):
            with self.subTest(payload=payload):
                self.reject(payload)
        corrupt = bytearray(stored_npz([("rate.npy", npy_array([1, 2, 3]))]))
        central = corrupt.index(b"PK\x01\x02")
        corrupt[central - 1] ^= 1
        self.reject(bytes(corrupt))

    def test_archive_and_declared_bin_count_budgets_are_enforced(self):
        self.reject(b"x" * (32 * 1024 * 1024 + 1))
        payload = stored_npz([("rate.npy", npy_array([1, 2, 3]))])
        for bins in (0, -1, 1_000_001, True, 3.0):
            with self.subTest(bins=bins):
                self.reject(payload, {"rate": ("float64", bins)})
        with self.assertRaises(ValueError):
            artifact_io.read_npz_bytes(payload, {})
        with self.assertRaises(ValueError):
            artifact_io.read_npz_bytes(payload, {str(i): ("float64", 3) for i in range(6)})

    def test_shape_requires_exact_one_dimensional_integer_tuple(self):
        for shape in ("(1, 3)", "(3, 1)", "()", "[3]", "(2,)", "(3.0,)", "(True,)"):
            n = 1 if shape == "(True,)" else 3
            header = "{'descr': '<f8', 'fortran_order': False, 'shape': " + shape + "}"
            payload = custom_npy(header, b"\x00" * (8 * n))
            with self.subTest(shape=shape):
                self.reject(stored_npz([("rate.npy", payload)]), {"rate": ("float64", n)})

    def test_header_requires_unique_exact_keys_and_c_order(self):
        headers = [
            "{'descr': '<f8', 'fortran_order': False, 'shape': (3,), 'extra': 1}",
            "{'descr': '<f8', 'shape': (3,)}",
            "{'descr': '<f8', 'fortran_order': True, 'shape': (3,)}",
            "{'descr': '<f8', 'fortran_order': 0, 'shape': (3,)}",
            "{'descr': '<f8', 'fortran_order': False, 'shape': (8,), 'shape': (3,)}",
            "{'descr': '|O', 'descr': '<f8', 'fortran_order': False, 'shape': (3,)}",
            "{'descr': [('field','<f8')], 'fortran_order': False, 'shape': (3,)}",
            "[]", "{'descr': '<f8'",
        ]
        for header in headers:
            with self.subTest(header=header):
                self.reject(stored_npz([("rate.npy", custom_npy(header, b"\x00" * 24))]))

    def test_header_and_version_bounds_reject_truncated_or_oversized_claims(self):
        valid = npy_array([1, 2, 3])
        payloads = [b"\x93NUMPY\x01\x00", b"\x93NUMPY\x01\x00\x08",
                    b"\x93NUMPY\x01\x00\x00\x00",
                    b"\x93NUMPY\x01\x00" + (4097).to_bytes(2, "little"),
                    b"\x93NUMPY\x01\x00\x20\x00{}",
                    b"NOTNPY" + valid[6:], valid[:6] + b"\x03\x00" + valid[8:]]
        for payload in payloads:
            with self.subTest(prefix=payload[:12]):
                self.reject(stored_npz([("rate.npy", payload)]))

    def test_numeric_roles_reject_complex_strings_objects_and_wrong_widths(self):
        for dtype in ("<c16", "S8", "U2", "V8", "datetime64[ns]", "bool"):
            header = repr({"descr": np.dtype(dtype).str, "fortran_order": False, "shape": (3,)})
            body = b"\x00" * (3 * np.dtype(dtype).itemsize)
            with self.subTest(dtype=dtype):
                self.reject(stored_npz([("rate.npy", custom_npy(header, body))]), {"rate": ("numeric", 3)})
        stream = io.BytesIO()
        np.save(stream, np.array([{"generated": 1}] * 3, dtype=object), allow_pickle=True)
        self.reject(stored_npz([("rate.npy", stream.getvalue())]), {"rate": ("numeric", 3)})
        for dtype, policy in (("<f4", "float64"), ("<u8", "int64"), ("<i4", "int64"),
                              ("u1", "bool"), ("<f8", "unknown")):
            with self.subTest(dtype=dtype, policy=policy):
                self.reject(stored_npz([("rate.npy", npy_array([1, 2, 3], dtype))]), {"rate": (policy, 3)})

    def test_npy_payload_extent_must_match_header_exactly(self):
        valid = npy_array([1, 2, 3])
        for payload in (valid[:-1], valid + b"\x00", valid + npy_array([4, 5, 6])):
            with self.subTest(length=len(payload)):
                self.reject(stored_npz([("rate.npy", payload)]))


class NpzDirectoryPreflightTests(unittest.TestCase):
    """Reject oversized directory claims before ZipFile allocates ZipInfo objects.

    An archive comment is legal ZIP, but outside this intentionally narrow
    operator format: its ordinary, comment-free EOCD must occupy the last 22 bytes.
    Local ZIP64 size fields from numpy.savez are a separate supported feature.
    """
    def fixture(self):
        return stored_npz([("rate.npy", npy_array([1, 2, 3]))])

    def altered_eocd(self, payload, **changes):
        names = ("signature", "disk", "directory_disk", "disk_count", "count",
                 "directory_bytes", "directory_offset", "comment_bytes")
        fields = dict(zip(names, struct.unpack("<4s4H2LH", payload[-22:])))
        fields.update(changes)
        return payload[:-22] + struct.pack("<4s4H2LH", *(fields[name] for name in names))

    def reject_before_zipfile(self, payload):
        with mock.patch.object(artifact_io.zipfile, "ZipFile",
                               side_effect=AssertionError("directory was opened before admission")) as opened:
            with self.assertRaises(ValueError):
                artifact_io.read_npz_bytes(payload, {"rate": ("float64", 3)})
            opened.assert_not_called()

    def test_large_declared_entry_counts_are_rejected_without_directory_allocation(self):
        payload = self.fixture()
        for count in (10_000, 65_534, 65_535):
            with self.subTest(count=count):
                self.reject_before_zipfile(self.altered_eocd(payload, count=count, disk_count=count))
        self.reject_before_zipfile(self.altered_eocd(payload, count=1, disk_count=2))

    def test_excessive_directory_bytes_are_rejected_before_zipfile(self):
        # A real, tiny one-entry ZIP with a large member comment: valid ZIP,
        # but a directory beyond the operator format's 8 KiB metadata budget.
        stream = io.BytesIO()
        entry = zipfile.ZipInfo("rate.npy")
        entry.comment = b"generated metadata" * 512
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_STORED) as archive:
            archive.writestr(entry, npy_array([1, 2, 3]))
        self.reject_before_zipfile(stream.getvalue())
        self.reject_before_zipfile(self.altered_eocd(self.fixture(), directory_bytes=0xFFFFFFFF))

    def test_inconsistent_directory_extent_and_missing_final_eocd_are_rejected_early(self):
        payload = self.fixture()
        fields = struct.unpack("<4s4H2LH", payload[-22:])
        malformed = [self.altered_eocd(payload, directory_offset=fields[6] + 1),
                     self.altered_eocd(payload, directory_bytes=fields[5] - 1),
                     self.altered_eocd(payload, directory_offset=0xFFFFFFFF),
                     payload[:-1], payload + b"unaccounted trailing bytes", payload[:15]]
        for index, candidate in enumerate(malformed):
            with self.subTest(case=index):
                self.reject_before_zipfile(candidate)

    def test_legal_zip_archive_comment_is_outside_operator_contract(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_STORED) as archive:
            archive.writestr("rate.npy", npy_array([1, 2, 3]))
            archive.comment = b"This ordinary ZIP comment is intentionally unsupported."
        # Distinguish a format restriction from claiming the commented ZIP is corrupt.
        with zipfile.ZipFile(io.BytesIO(stream.getvalue())) as archive:
            self.assertEqual(archive.namelist(), ["rate.npy"])
            self.assertTrue(archive.comment)
        self.reject_before_zipfile(stream.getvalue())

    def test_multidisk_and_zip64_end_directories_are_rejected_before_zipfile(self):
        payload = self.fixture()
        for changes in ({"disk": 1}, {"directory_disk": 1}):
            with self.subTest(changes=changes):
                self.reject_before_zipfile(self.altered_eocd(payload, **changes))
        fields = struct.unpack("<4s4H2LH", payload[-22:])
        # Genuine ZIP64 end record and locator, in addition to the ordinary EOCD.
        end64 = struct.pack("<4sQ2H2L4Q", b"PK\x06\x06", 44, 45, 45, 0, 0,
                            1, 1, fields[5], fields[6])
        locator = struct.pack("<4sLQL", b"PK\x06\x07", 0, len(payload) - 22, 1)
        self.reject_before_zipfile(payload[:-22] + end64 + locator + payload[-22:])

    def test_numpy_savez_local_zip64_headers_remain_accepted(self):
        stream = io.BytesIO()
        np.savez(stream, rate=np.array([1.25, 2.5, 3.75], dtype="<f8"))
        payload = stream.getvalue()
        self.assertEqual(payload[:4], b"PK\x03\x04")
        # NumPy's current normal writer uses ZIP64 local sizes even for tiny files.
        self.assertEqual(struct.unpack_from("<2L", payload, 18), (0xFFFFFFFF, 0xFFFFFFFF))
        decoded = artifact_io.read_npz_bytes(payload, {"rate": ("float64", 3)})
        np.testing.assert_array_equal(decoded["rate"], [1.25, 2.5, 3.75])

    def test_planted_zip64_locator_cannot_override_bounded_ordinary_eocd(self):
        payload = self.fixture()
        # CPython inspects this position for a locator even without ZIP64
        # sentinel values in the ordinary EOCD. Preserve every admitted EOCD
        # field and its exact directory extent while planting the locator.
        locator = struct.pack("<4sLQL", b"PK\x06\x07", 0, 0, 1)
        deceptive = payload[:-42] + locator + payload[-22:]
        self.assertEqual(deceptive[-22:], payload[-22:])
        self.assertEqual(len(deceptive), len(payload))
        self.reject_before_zipfile(deceptive)


if __name__ == "__main__":
    unittest.main()
