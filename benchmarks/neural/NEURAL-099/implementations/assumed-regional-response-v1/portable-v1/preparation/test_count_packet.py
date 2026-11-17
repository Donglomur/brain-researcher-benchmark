"""Tiny generated private files only; no authentic count packet or full allocation."""

import copy
import hashlib
import importlib.util
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch


_spec = importlib.util.spec_from_file_location("neural099_count_packet", Path(__file__).with_name("count_packet.py"))
packet = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(packet)


def case(key, asset="asset-a", animal="animal-a", row=0, trial=19, region="MGv", clusters=2):
    return {"case_id": key, "asset_id": asset, "animal_id": animal,
            "source_trial_row": row, "source_trial_id": trial,
            "trial_start_seconds": -0.5 + row, "trial_stop_seconds": -0.4999 + row,
            "region": region, "source_cluster_count": clusters}


def count_row(key, history=1, response=7):
    return {"case_id": key, "history_counts": [history] * 100,
            "response_counts": [response] * 100}


class PacketCodecTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="neural099-generated-packet-")
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "counts.u64le"
        self.cases = [case("a0"), case("a1", row=1, trial=23)]
        self.rows = [count_row("a0", 1, 0x0102030405060708), count_row("a1", 3, 11)]
        self.bound = 3200

    def write(self):
        return packet.write_packet(self.path, self.cases, iter(self.rows), max_bytes=self.bound)

    def test_wire_shape_little_endian_checksum_and_private_roundtrip(self):
        binding = self.write()
        self.assertEqual(binding["bytes"], 3200)
        self.assertEqual(binding["case_count"], 2)
        self.assertEqual(binding["window_order"], ["history", "response"])
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
        with self.path.open("rb") as handle:
            payload = handle.read(3201)
        self.assertEqual(len(payload), 3200)
        self.assertEqual(payload[:8], b"\x01\x00\x00\x00\x00\x00\x00\x00")
        self.assertEqual(payload[800:808], b"\x08\x07\x06\x05\x04\x03\x02\x01")
        self.assertEqual(binding["sha256"], hashlib.sha256(payload).hexdigest())
        with packet.verify_packet(self.path, self.cases, binding, max_bytes=self.bound) as reader:
            self.assertEqual(reader.case_ids, ("a0", "a1"))
            row = reader.read_private("a1")
            self.assertEqual(row["history_counts"], [3] * 100)
            self.assertEqual(row["response_counts"], [11] * 100)
        with self.assertRaises(ValueError):
            reader.read_private("a0")

    def test_history_projection_reads_only_current_history_bytes_and_no_targets(self):
        binding = self.write()
        with packet.verify_packet(self.path, self.cases, binding, max_bytes=self.bound) as reader:
            real_pread = os.pread
            with patch.object(packet.os, "pread", wraps=real_pread) as read:
                projected = reader.history_projection("a1", released_case_id="a1")
                self.assertEqual(read.call_count, 1)
                self.assertEqual(read.call_args.args[1:], (800, 1600))
            self.assertEqual(set(projected), {"case", "history_rates"})
            visible_fields = {"case_id", "animal_id", "asset_id", "region",
                              "source_trial_row", "source_cluster_count"}
            self.assertEqual(set(projected["case"]), visible_fields)
            self.assertEqual(projected["case"],
                             {field: self.cases[1][field] for field in visible_fields})
            self.assertEqual(reader.read_private("a1")["case"], self.cases[1])
            self.assertEqual(projected["history_rates"], [1500] * 100)
            self.assertNotIn("response_counts", projected)
            with patch.object(packet.os, "pread", side_effect=AssertionError("No read expected")):
                with self.assertRaises(ValueError):
                    reader.history_projection("a1", released_case_id="a0")
                with self.assertRaises(ValueError):
                    reader.history_projection("missing", released_case_id="missing")

    def test_counts_uint64_extremes_and_exact_nominal_rates(self):
        cases = [case("one", clusters=3)]
        rows = [count_row("one", packet.UINT64_MAX, 0)]
        binding = packet.write_packet(self.path, cases, rows, max_bytes=1600)
        with packet.verify_packet(self.path, cases, binding, max_bytes=1600) as reader:
            self.assertEqual(reader.read_private("one")["history_counts"][0], 2 ** 64 - 1)
            self.assertEqual(reader.read_private("one")["response_counts"], [0] * 100)
            expected = float(packet.Fraction((2 ** 64 - 1) * 1000, 3))
            self.assertEqual(reader.history_projection("one", released_case_id="one")["history_rates"],
                             [expected] * 100)

    def test_checksum_tampering_and_trailing_or_truncated_files_refuse(self):
        binding = self.write()
        with self.path.open("r+b") as handle:
            handle.seek(808)
            handle.write(b"\xff")
        with self.assertRaisesRegex(ValueError, "checksum"):
            packet.verify_packet(self.path, self.cases, binding, max_bytes=self.bound)
        for suffix, content in (("short", bytes(3199)), ("long", bytes(3201))):
            path = self.path.with_name(suffix)
            path.write_bytes(content)
            with self.subTest(suffix=suffix), self.assertRaisesRegex(ValueError, "extent"):
                packet.verify_packet(path, self.cases, binding, max_bytes=self.bound)

    def test_metadata_and_endian_binding_tampering_refuse_before_file_open(self):
        binding = self.write()
        altered_cases = copy.deepcopy(self.cases)
        altered_cases[0]["source_trial_id"] += 1
        attempts = []
        changed = copy.deepcopy(binding)
        changed["dtype"] = "uint64-big-endian"
        attempts.append((self.cases, changed))
        changed = copy.deepcopy(binding)
        changed["case_count"] = True
        attempts.append((self.cases, changed))
        changed = copy.deepcopy(binding)
        changed["window_order"] = ["response", "history"]
        attempts.append((self.cases, changed))
        attempts.append((altered_cases, binding))
        for cases, descriptor in attempts:
            with self.subTest(descriptor=descriptor), patch.object(packet.os, "open", side_effect=AssertionError("No open expected")):
                with self.assertRaises(ValueError):
                    packet.verify_packet(self.path, cases, descriptor, max_bytes=self.bound)

    def test_signature_mutation_closes_reader_before_data_release(self):
        binding = self.write()
        reader = packet.verify_packet(self.path, self.cases, binding, max_bytes=self.bound)
        self.addCleanup(reader.close)
        # Explicit timestamp change is deterministic even on coarse filesystems.
        status = self.path.stat()
        os.utime(self.path, ns=(status.st_atime_ns, status.st_mtime_ns + 1_000_000_000))
        with patch.object(packet.os, "pread", side_effect=AssertionError("No read expected")):
            with self.assertRaisesRegex(ValueError, "changed"):
                reader.history_projection("a0", released_case_id="a0")
        with self.assertRaisesRegex(ValueError, "closed"):
            reader.read_private("a0")

    def test_signature_mutation_during_row_read_refuses_returned_bytes(self):
        binding = self.write()
        reader = packet.verify_packet(self.path, self.cases, binding, max_bytes=self.bound)
        self.addCleanup(reader.close)
        real_pread = os.pread

        def changed_during_read(fd, size, offset):
            payload = real_pread(fd, size, offset)
            status = self.path.stat()
            os.utime(self.path, ns=(status.st_atime_ns, status.st_mtime_ns + 1_000_000_000))
            return payload

        with patch.object(packet.os, "pread", side_effect=changed_during_read):
            with self.assertRaisesRegex(ValueError, "changed"):
                reader.history_projection("a0", released_case_id="a0")
        with self.assertRaisesRegex(ValueError, "closed"):
            reader.read_private("a0")

    def test_exclusive_destination_symlink_and_byte_bound_refuse(self):
        self.write()
        before = self.path.read_bytes()
        with self.assertRaises(FileExistsError):
            self.write()
        self.assertEqual(self.path.read_bytes(), before)
        link = self.path.with_name("link")
        link.symlink_to(self.path)
        binding = packet._binding(packet.validate_cases(self.cases), 3200, hashlib.sha256(before).hexdigest())
        with self.assertRaises(OSError):
            packet.verify_packet(link, self.cases, binding, max_bytes=self.bound)
        small = self.path.with_name("too-small")
        with self.assertRaises(ValueError):
            packet.write_packet(small, self.cases, self.rows, max_bytes=3199)
        self.assertFalse(small.exists())

    def test_nonregular_fifo_is_rejected_without_waiting_for_a_writer(self):
        binding = self.write()
        fifo = self.path.with_name("fifo")
        os.mkfifo(fifo, 0o600)
        with self.assertRaisesRegex(ValueError, "regular"):
            packet.verify_packet(fifo, self.cases, binding, max_bytes=self.bound)
        with self.assertRaisesRegex(ValueError, "regular"):
            packet.verify_packet(Path(self.directory.name), self.cases, binding, max_bytes=self.bound)

    def test_partial_system_writes_and_short_checksum_reads_are_handled(self):
        real_write, real_read = os.write, os.read

        def short_write(fd, data):
            return real_write(fd, data[:73])

        with patch.object(packet.os, "write", side_effect=short_write):
            binding = self.write()

        def short_read(fd, size):
            return real_read(fd, min(size, 79))

        with patch.object(packet.os, "read", side_effect=short_read):
            with packet.verify_packet(self.path, self.cases, binding, max_bytes=self.bound) as reader:
                self.assertEqual(reader.read_private("a0")["history_counts"], [1] * 100)

    def test_short_positional_reads_accumulate_within_current_history_extent(self):
        binding = self.write()
        real_pread = os.pread
        requested = []

        def short_pread(fd, size, offset):
            requested.append((size, offset))
            return real_pread(fd, min(size, 73), offset)

        with packet.verify_packet(self.path, self.cases, binding, max_bytes=self.bound) as reader:
            with patch.object(packet.os, "pread", side_effect=short_pread):
                result = reader.history_projection("a1", released_case_id="a1")
            self.assertEqual(result["history_rates"], [1500] * 100)
            self.assertGreater(len(requested), 1)
            self.assertTrue(all(1600 <= offset < 2400 and offset + size == 2400
                                for size, offset in requested))

    def test_failure_mid_write_retains_unadmitted_partial_private_file(self):
        real_write = os.write
        calls = []

        def interrupted(fd, data):
            calls.append(len(data))
            if len(calls) == 1:
                return real_write(fd, data[:17])
            raise OSError("generated interrupted write")

        with patch.object(packet.os, "write", side_effect=interrupted):
            with self.assertRaisesRegex(OSError, "interrupted"):
                self.write()
        self.assertEqual(self.path.stat().st_size, 17)
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)

    def test_mutation_during_checksum_closes_preflight_without_reader(self):
        binding = self.write()
        real_read = os.read
        changed = []

        def mutate_after_read(fd, size):
            payload = real_read(fd, size)
            if not changed:
                status = self.path.stat()
                os.utime(self.path, ns=(status.st_atime_ns, status.st_mtime_ns + 1_000_000_000))
                changed.append(True)
            return payload

        with patch.object(packet.os, "read", side_effect=mutate_after_read):
            with self.assertRaisesRegex(ValueError, "changed"):
                packet.verify_packet(self.path, self.cases, binding, max_bytes=self.bound)

    def test_stream_row_identity_count_range_shape_and_extent_are_strict(self):
        wrong_cases = [copy.deepcopy(self.rows), copy.deepcopy(self.rows), copy.deepcopy(self.rows),
                       copy.deepcopy(self.rows), self.rows[:1], self.rows + self.rows[:1],
                       copy.deepcopy(self.rows)]
        wrong_cases[0][0]["case_id"] = "other"
        wrong_cases[1][0]["history_counts"][0] = True
        wrong_cases[2][0]["response_counts"][0] = 2 ** 64
        wrong_cases[3][0]["history_counts"] = [0] * 99
        wrong_cases[6][0]["response_counts"][0] = -1
        for index, rows in enumerate(wrong_cases):
            path = self.path.with_name("partial-%s" % index)
            with self.subTest(index=index), self.assertRaises(ValueError):
                packet.write_packet(path, self.cases, rows, max_bytes=self.bound)
            self.assertTrue(path.exists())
            self.assertLessEqual(path.stat().st_size, self.bound)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_ragged_regions_complete_trials_and_stable_identities(self):
        valid = [case("m0", region="MGm"), case("v0", region="MGv"),
                 case("m1", region="MGm", row=1, trial=23), case("v1", region="MGv", row=1, trial=23),
                 case("b0", asset="asset-b", animal="animal-b", region="SG")]
        self.assertEqual(len(packet.validate_cases(valid)), 5)
        invalid = [list(reversed(valid)), valid[:2] + valid[3:], [valid[2]],
                   [case("x", region=" ")], [case("x", clusters=0)],
                   [case("x"), case("y", row=1, trial=19)],
                   [case("x"), case("y", row=1, trial=23, animal="different")],
                   [case("x"), case("y", row=1, trial=23, clusters=3)]]
        altered = copy.deepcopy(valid)
        altered[1]["trial_start_seconds"] += 0.00001
        invalid.append(altered)
        for cases in invalid:
            with self.subTest(cases=cases), self.assertRaises(ValueError):
                packet.validate_cases(cases)


if __name__ == "__main__":
    unittest.main(verbosity=2)
