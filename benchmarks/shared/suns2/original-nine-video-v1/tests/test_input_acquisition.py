"""Generated archives and fake network only; no authentic source payloads."""

import copy
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from suns2_benchmark import input_acquisition as intake
from suns2_benchmark.constants import VIDEO_IDS


def fixture():
    names = ["1P_spike_tempolate.h5"] + [video + ".h5" for video in sorted(VIDEO_IDS)]
    names += ["GT Masks/"] + [f"GT Masks/FinalMasks_{video}.mat" for video in sorted(VIDEO_IDS)]
    payloads = {name: ((name.encode() + b"-generated-") * 7) for name in names if not name.endswith("/")}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name in names:
            info = zipfile.ZipInfo(name)
            info.create_system, info.create_version, info.extract_version = 0, 20, 20
            info.external_attr = 16 if name.endswith("/") else 32
            info.compress_type = zipfile.ZIP_STORED if name.endswith("/") else zipfile.ZIP_DEFLATED
            archive.writestr(info, b"" if name.endswith("/") else payloads[name])
    body = buffer.getvalue()
    end = intake.EOCD.unpack(body[-intake.EOCD.size:])
    eocd = {"entries": end[4], "central_directory_bytes": end[5],
            "central_directory_offset": end[6], "eocd_offset": len(body) - 22,
            "comment_bytes": end[7]}
    entries = []
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        for i, info in enumerate(archive.infolist()):
            entries.append({"index": i, "name": info.filename, "name_raw_hex": info.filename.encode().hex(),
                            "flags": info.flag_bits, "compression_method": info.compress_type,
                            "compressed_bytes": info.compress_size, "uncompressed_bytes": info.file_size,
                            "crc32_unverified": f"{info.CRC:08x}", "local_header_offset": info.header_offset,
                            "version_needed": info.extract_version, "directory": info.is_dir(), "symlink": False})
    identity = {"object_id": intake.OBJECT_ID, "archive_bytes": len(body),
                "published_MD5": hashlib.md5(body).hexdigest(),
                "expected_files": 19, "expected_directories": 1,
                "expected_expanded_bytes": sum(map(len, payloads.values())),
                "all_20_entries": entries, "EOCD": eocd,
                "retained_directory_SHA256": hashlib.sha256(body[end[6]:end[6]+end[5]]).hexdigest()}
    pins = {n: hashlib.sha256(v).hexdigest() for n, v in payloads.items() if n.startswith("GT Masks/")}
    return body, identity, payloads, pins


def response(status=200, body=b"", headers=None):
    values = {"Content-Length": str(len(body)), "ETag": '"generated-identity"'}
    values.update(headers or {})
    return (f"HTTP/1.1 {status} Generated\r\n" +
            "".join(f"{k}: {v}\r\n" for k, v in values.items()) + "\r\n").encode() + body


class FakeConnection:
    def __init__(self, content):
        self.content, self.offset, self.closed = content, 0, False

    def settimeout(self, _value):
        pass

    def recv(self, size):
        result = self.content[self.offset:self.offset+size]
        self.offset += len(result)
        return result

    def close(self):
        self.closed = True


class FakeWire:
    def __init__(self, responses):
        self.connections = [FakeConnection(value) for value in responses]
        self.calls = []

    def timeout(self):
        return 1

    def connect(self, url):
        self.calls.append(url)
        if len(self.calls) > len(self.connections):
            raise AssertionError("unexpected request or retry")
        return self.connections[len(self.calls)-1]


class GeneratedIntakeControls(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.body, self.identity, self.payloads, self.pins = fixture()
        self.r2 = f"https://{intake.R2_HOST}/figshare-com-storage/{intake.OBJECT_ID}/data_TUnCaT.zip?token=generated"

    def tearDown(self):
        self.temporary.cleanup()

    def wire(self, final, redirect_body=b"DO NOT READ"):
        return FakeWire([response(302, redirect_body, {"Location": self.r2}), final])

    def acquire(self, wire, identity=None):
        return intake.acquire_complete_archive(identity or self.identity, self.root/"raw", self.root/"evidence", wire=wire)

    def extract(self, identity=None, body=None, pins=None):
        archive = self.root / "source.zip"
        archive.write_bytes(self.body if body is None else body)
        return intake.extract_complete_archive(archive, identity or self.identity, self.root/"bank",
            expected_archive_sha256=hashlib.sha256(self.body).hexdigest(), expected_gt_pins=pins or self.pins)

    def test_success_streams_exact_archive_without_redirect_body(self):
        wire = self.wire(response(body=self.body, headers={"Content-Disposition": 'attachment; filename="data_TUnCaT.zip"'}))
        result = self.acquire(wire)
        self.assertEqual(result["archive_sha256"], hashlib.sha256(self.body).hexdigest())
        self.assertEqual(result["captured_body_bytes"], len(self.body))
        self.assertEqual(result["transaction_count"], 2)
        self.assertEqual(wire.connections[0].content[wire.connections[0].offset:], b"DO NOT READ")
        self.assertEqual((self.root/"raw/archive.zip").read_bytes(), self.body)
        self.assertTrue(all(conn.closed for conn in wire.connections))

    def test_bad_length_and_weak_etag_refuse_before_body(self):
        for headers in ({"Content-Length": "9"}, {"ETag": 'W/"weak"'}):
            with self.subTest(headers=headers), tempfile.TemporaryDirectory() as directory:
                wire = self.wire(response(body=self.body, headers=headers))
                with self.assertRaises(intake.IntakeRefusal):
                    intake.acquire_complete_archive(self.identity, Path(directory)/"raw", Path(directory)/"evidence", wire=wire)
                record = json.loads((Path(directory)/"evidence/ACQUISITION_RECEIPT.json").read_text())
                self.assertEqual(record["captured_body_bytes"], 0)
                self.assertEqual(wire.connections[1].content[wire.connections[1].offset:], self.body)

    def test_encoded_partial_and_chunked_responses_refused(self):
        for status, headers in ((206, {}), (200, {"Content-Encoding": "gzip"}),
                                (200, {"Transfer-Encoding": "chunked"})):
            with self.subTest(status=status, headers=headers), tempfile.TemporaryDirectory() as directory:
                wire = self.wire(response(status, self.body, headers))
                with self.assertRaises(intake.IntakeRefusal):
                    intake.acquire_complete_archive(self.identity, Path(directory)/"raw", Path(directory)/"evidence", wire=wire)
                self.assertFalse((Path(directory)/"raw/archive.zip").exists())

    def test_unsafe_redirects_and_relative_location_rejected(self):
        for url in ("http://example.com/no", "https://example.com/no", "/relative", self.r2.replace("49636131", "49636137")):
            with self.subTest(url=url), tempfile.TemporaryDirectory() as directory:
                wire = FakeWire([response(302, b"REDIRECT BODY", {"Location": url})])
                with self.assertRaises(intake.IntakeRefusal):
                    intake.acquire_complete_archive(self.identity, Path(directory)/"raw", Path(directory)/"evidence", wire=wire)
                self.assertEqual(len(wire.calls), 1)
                self.assertEqual(wire.connections[0].content[wire.connections[0].offset:], b"REDIRECT BODY")

    def test_three_redirects_exhaust_exact_transaction_cap(self):
        wire = FakeWire([response(302, b"IGNORED", {"Location": self.r2})]*3)
        with self.assertRaises(intake.IntakeRefusal):
            self.acquire(wire)
        receipt = json.loads((self.root/"evidence/ACQUISITION_RECEIPT.json").read_text())
        self.assertEqual(receipt["transaction_count"], 3)
        self.assertEqual(receipt["captured_body_bytes"], 0)

    def test_truncated_body_and_wrong_hash_preserve_written_bytes(self):
        for final in (response(body=self.body[:-3], headers={"Content-Length": str(len(self.body))}),
                      response(body=b"X"+self.body[1:])):
            with self.subTest(kind=len(final)), tempfile.TemporaryDirectory() as directory:
                wire = self.wire(final)
                with self.assertRaises(intake.IntakeRefusal):
                    intake.acquire_complete_archive(self.identity, Path(directory)/"raw", Path(directory)/"evidence", wire=wire)
                receipt = json.loads((Path(directory)/"evidence/ACQUISITION_RECEIPT.json").read_text())
                self.assertGreater(receipt["captured_body_bytes"], 0)
                self.assertEqual(receipt["written_body_bytes"], (Path(directory)/"raw/archive.zip").stat().st_size)
                self.assertEqual(receipt["status"], "partial_or_refused")

    def test_single_overrun_byte_is_captured_charged_and_refused(self):
        wire = self.wire(response(body=self.body+b"Z", headers={"Content-Length": str(len(self.body))}))
        with self.assertRaises(intake.IntakeRefusal):
            self.acquire(wire)
        receipt = json.loads((self.root/"evidence/ACQUISITION_RECEIPT.json").read_text())
        self.assertEqual(receipt["captured_body_bytes"], len(self.body)+1)
        self.assertEqual(receipt["written_overrun_bytes"], 1)
        self.assertEqual((self.root/"raw/overrun.bin").read_bytes(), b"Z")

    def test_header_cap_and_duplicate_critical_headers(self):
        for final in (b"HTTP/1.1 200 OK\r\nX: "+b"A"*17000,
                      b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nContent-Length: 3\r\n\r\nXX"):
            with self.subTest(length=len(final)), tempfile.TemporaryDirectory() as directory:
                wire = self.wire(final)
                with self.assertRaises(intake.IntakeRefusal):
                    intake.acquire_complete_archive(self.identity, Path(directory)/"raw", Path(directory)/"evidence", wire=wire)
                self.assertLessEqual((Path(directory)/"raw/02-headers.raw").stat().st_size, intake.HEADER_CAP)
                self.assertFalse((Path(directory)/"raw/archive.zip").exists())

    def test_complete_twenty_entry_extraction_and_old_GT_hash_join(self):
        with patch.object(intake, "OUTPUT_CHUNK", 32), patch.object(intake, "INPUT_CHUNK", 64):
            report = self.extract()
        self.assertEqual(report["written_payload_bytes"], sum(map(len, self.payloads.values())))
        self.assertEqual(len(report["members"]), 19)
        self.assertEqual(report["archive_logical_bytes_read"], len(self.body))
        self.assertTrue((self.root/"bank/GT Masks").is_dir())
        for name, payload in self.payloads.items():
            self.assertEqual((self.root/"bank"/name).read_bytes(), payload)
        self.assertFalse(report["MAT_arrays_loaded"])
        self.assertFalse(report["HDF5_arrays_loaded"])

    def test_directory_wrong_method_is_not_treated_as_empty_file(self):
        identity = copy.deepcopy(self.identity)
        identity["all_20_entries"][10]["compression_method"] = 8
        with self.assertRaises(intake.IntakeRefusal):
            self.extract(identity=identity)
        self.assertFalse((self.root/"bank").exists())

    def test_path_escape_case_collision_and_zip64_rejected_before_writes(self):
        for changed in ("path", "case", "zip64"):
            identity = copy.deepcopy(self.identity)
            if changed == "path":
                identity["all_20_entries"][0]["name"] = "../escape"
            elif changed == "case":
                identity["all_20_entries"][1]["name"] = identity["all_20_entries"][0]["name"].upper()
            else:
                identity["all_20_entries"][0]["version_needed"] = 45
            with self.subTest(changed=changed), self.assertRaises(intake.IntakeRefusal):
                intake._validate_roster(identity)

    def test_local_header_mismatch_refuses_preserves_provisional_bank(self):
        mutated = bytearray(self.body)
        mutated[0:4] = b"BAD!"
        with self.assertRaises(intake.IntakeRefusal) as caught:
            self.extract(body=bytes(mutated))
        self.assertEqual(caught.exception.receipt["status"], "partial_or_refused")
        self.assertEqual(caught.exception.receipt["written_payload_bytes"], 0)
        self.assertTrue((self.root/"bank").is_dir())

    def test_GT_byte_change_and_central_identity_change_fail_closed(self):
        bad_pins = dict(self.pins)
        bad_pins[next(iter(bad_pins))] = "0"*64
        with self.assertRaises(intake.IntakeRefusal) as caught:
            self.extract(pins=bad_pins)
        self.assertGreater(caught.exception.receipt["written_payload_bytes"], 0)
        self.assertIn("manual-mask identity", str(caught.exception))

    def test_changed_central_directory_is_refused_after_bounded_partial_writes(self):
        identity = copy.deepcopy(self.identity)
        identity["retained_directory_SHA256"] = "0"*64
        with self.assertRaises(intake.IntakeRefusal) as caught:
            self.extract(identity=identity)
        self.assertEqual(caught.exception.receipt["written_payload_bytes"], identity["expected_expanded_bytes"])
        self.assertEqual(caught.exception.receipt["status"], "partial_or_refused")

    def test_symlink_archive_source_is_refused(self):
        real = self.root/"actual.zip"
        real.write_bytes(self.body)
        linked = self.root/"source.zip"
        linked.symlink_to(real)
        with self.assertRaises(intake.IntakeRefusal):
            intake.extract_complete_archive(linked, self.identity, self.root/"bank",
                expected_archive_sha256=hashlib.sha256(self.body).hexdigest(), expected_gt_pins=self.pins)
        self.assertEqual(list((self.root/"bank").iterdir()), [])

    def test_hardlink_archive_source_is_refused(self):
        real = self.root/"actual.zip"
        real.write_bytes(self.body)
        linked = self.root/"linked.zip"
        os.link(real, linked)
        with self.assertRaises(intake.IntakeRefusal) as caught:
            intake.extract_complete_archive(linked, self.identity, self.root/"bank",
                expected_archive_sha256=hashlib.sha256(self.body).hexdigest(), expected_gt_pins=self.pins)
        self.assertEqual(caught.exception.receipt["written_payload_bytes"], 0)

    def test_incremental_expansion_bound_prevents_overrun_write(self):
        identity = copy.deepcopy(self.identity)
        first = identity["all_20_entries"][0]
        first["uncompressed_bytes"] -= 1
        identity["expected_expanded_bytes"] -= 1
        changed = bytearray(self.body)
        struct.pack_into("<I", changed, 22, first["uncompressed_bytes"])
        with self.assertRaises(intake.IntakeRefusal) as caught:
            self.extract(identity=identity, body=bytes(changed))
        self.assertIn("expansion overrun", str(caught.exception))
        self.assertLessEqual(caught.exception.receipt["written_payload_bytes"], first["uncompressed_bytes"])

    def test_compressed_trailing_byte_is_not_accepted_as_one_member(self):
        identity = copy.deepcopy(self.identity)
        first = identity["all_20_entries"][0]
        end = identity["all_20_entries"][1]["local_header_offset"]
        changed = bytearray(self.body[:end] + b"X" + self.body[end:])
        first["compressed_bytes"] += 1
        struct.pack_into("<I", changed, 18, first["compressed_bytes"])
        for entry in identity["all_20_entries"][1:]:
            entry["local_header_offset"] += 1
        identity["archive_bytes"] += 1
        identity["EOCD"]["central_directory_offset"] += 1
        identity["EOCD"]["eocd_offset"] += 1
        with self.assertRaises(intake.IntakeRefusal) as caught:
            self.extract(identity=identity, body=bytes(changed))
        self.assertIn("trailing compressed data", str(caught.exception))

    def test_overlapping_local_member_offset_refuses_before_second_output(self):
        identity = copy.deepcopy(self.identity)
        identity["all_20_entries"][1]["local_header_offset"] -= 1
        with self.assertRaises(intake.IntakeRefusal) as caught:
            self.extract(identity=identity)
        self.assertIn("noncontiguous", str(caught.exception))
        self.assertEqual(len(caught.exception.receipt["members"]), 1)


if __name__ == "__main__":
    unittest.main()
