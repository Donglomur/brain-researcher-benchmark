"""Invented archive boundary tests. No neural data or NumPy import."""
from dataclasses import FrozenInstanceError
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import stat
import struct
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import warnings
import zipfile

path = Path(__file__).with_name("training_projection.py")
spec = importlib.util.spec_from_file_location("training_projection", path)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


def npy(value):
    header = b"{'descr': '|u1', 'fortran_order': False, 'shape': (1,), }"
    header += b" " * ((-10-len(header)-1) % 64) + b"\n"
    return b"\x93NUMPY\x01\x00" + struct.pack("<H", len(header)) + header + bytes([value])


class ProjectionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        # macOS /var is a symlink: use a canonical operator-owned directory.
        self.root = Path(self.directory.name).resolve()
        self.source = self.root / "public.npz"
        self.output = self.root / "train.npz"
        self.payloads = {f + ".npy": npy(i) for i, f in enumerate(m.PUBLIC_FIELDS)}
        self.make()

    def make(self, pairs=None, compression=zipfile.ZIP_STORED):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(self.source, "w", compression=compression) as z:
                for name, body in (pairs or self.payloads.items()):
                    z.writestr(name, body)

    def run_projection(self, **kw):
        body = self.source.read_bytes()
        options = dict(source_path=self.source, destination_path=self.output,
                       expected_bytes=len(body), expected_sha256=hashlib.sha256(body).hexdigest(),
                       deadline_monotonic=time.monotonic() + 10)
        options.update(kw)
        return m.derive_training_packet(**options)

    def clean_failure(self):
        self.assertFalse(self.output.exists())
        self.assertEqual(list(self.root.glob(".train-packet-*")), [])

    def test_only_eight_training_members_are_copied_byte_for_byte(self):
        result = self.run_projection()
        with zipfile.ZipFile(self.output) as z:
            self.assertEqual(z.namelist(), [x + ".npy" for x in m.TRAIN_FIELDS])
            for name in z.namelist():
                self.assertEqual(z.read(name), self.payloads[name])
        self.assertEqual(result.output_sha256, hashlib.sha256(self.output.read_bytes()).hexdigest())
        self.assertEqual(result.output_bytes, self.output.stat().st_size)
        self.assertEqual(result.verified_members, 13)
        self.assertTrue(result.crc_checked_all_members)
        self.assertFalse(result.numerical_arrays_decoded)
        self.assertEqual(result.decompressed_bytes, sum(map(len, self.payloads.values())))
        self.assertGreater(result.source_stream_bytes, result.source_bytes)
        self.assertLessEqual(result.source_stream_bytes, m.SOURCE_READ_CAP_BYTES)
        self.assertEqual(stat.S_IMODE(self.output.stat().st_mode), 0o600)
        self.assertEqual(self.output.stat().st_nlink, 1)
        with self.assertRaises(FrozenInstanceError):
            result.output_bytes = 0

    def test_output_is_deterministic_across_directory_order_and_compression(self):
        first = self.run_projection()
        self.output.unlink()
        self.make(list(reversed(list(self.payloads.items()))), zipfile.ZIP_DEFLATED)
        second = self.run_projection()
        self.assertEqual(first.output_sha256, second.output_sha256)
        self.assertNotEqual(first.source_sha256, second.source_sha256)

    def test_wrong_source_pin_refuses_before_output(self):
        with self.assertRaisesRegex(m.ProjectionError, "digest differs"):
            self.run_projection(expected_sha256="0"*64)
        self.clean_failure()

    def test_size_pin_and_non_integer_caps_refuse(self):
        for change in ({"expected_bytes": self.source.stat().st_size+1},
                       {"expected_bytes": True}, {"output_cap_bytes": True},
                       {"output_cap_bytes": m.SOURCE_CAP_BYTES+1}):
            with self.subTest(change=change), self.assertRaises(m.ProjectionError):
                self.run_projection(**change)
        self.clean_failure()

    def test_existing_destination_is_preserved(self):
        self.output.write_bytes(b"previous work")
        with self.assertRaisesRegex(m.ProjectionError, "already exists"):
            self.run_projection()
        self.assertEqual(self.output.read_bytes(), b"previous work")

    def test_missing_duplicate_unexpected_and_path_members_refuse(self):
        pairs = list(self.payloads.items())
        variants = [pairs[:-1], pairs+[pairs[0]],
                    pairs[:-1]+[("unknown.npy", npy(1))],
                    pairs[:-1]+[("../panel_fingerprint.npy", npy(1))]]
        for entries in variants:
            with self.subTest(names=[x[0] for x in entries]):
                self.make(entries)
                with self.assertRaises(m.ProjectionError):
                    self.run_projection()
                self.clean_failure()

    def test_symlink_source_or_parent_and_hardlink_source_refuse(self):
        link = self.root / "link.npz"
        link.symlink_to(self.source)
        with self.assertRaisesRegex(m.ProjectionError, "Symlink"):
            self.run_projection(source_path=link)
        parent = self.root / "alias"
        parent.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(m.ProjectionError, "Symlink"):
            self.run_projection(destination_path=parent / "train.npz")
        link.unlink()
        os.link(self.source, link)
        with self.assertRaisesRegex(m.ProjectionError, "single-link"):
            self.run_projection()
        self.clean_failure()

    def test_member_symlink_refuses(self):
        with zipfile.ZipFile(self.source, "w") as z:
            for name, body in self.payloads.items():
                info = zipfile.ZipInfo(name)
                info.create_system = 3
                info.external_attr = ((stat.S_IFLNK if name == "eval_trial_ids.npy"
                                       else stat.S_IFREG) | 0o600) << 16
                z.writestr(info, body)
        with self.assertRaisesRegex(m.ProjectionError, "type or encoding"):
            self.run_projection()
        self.clean_failure()

    def test_discarded_eval_member_crc_is_checked(self):
        body = bytearray(self.source.read_bytes())
        with zipfile.ZipFile(io.BytesIO(body)) as z:
            item = z.getinfo("eval_counts_heldin.npy")
        offset = item.header_offset
        name_size, extra_size = struct.unpack_from("<HH", body, offset+26)
        body[offset+30+name_size+extra_size+item.file_size-1] ^= 1
        self.source.write_bytes(body)
        with self.assertRaises(zipfile.BadZipFile):
            self.run_projection()
        self.clean_failure()

    def test_magic_is_checked_even_in_discarded_member(self):
        self.payloads["eval_valid_mask.npy"] = b"not NPY but otherwise valid ZIP"
        self.make()
        with self.assertRaisesRegex(m.ProjectionError, "NPY"):
            self.run_projection()
        self.clean_failure()

    def test_output_and_expansion_caps_leave_no_partial_file(self):
        with self.assertRaisesRegex(m.ProjectionError, "Output byte cap"):
            self.run_projection(output_cap_bytes=100)
        self.clean_failure()

    def test_repeated_source_read_budget_refuses(self):
        with patch.object(m, "SOURCE_READ_CAP_BYTES", self.source.stat().st_size + 10):
            with self.assertRaisesRegex(m.ProjectionError, "source read cap"):
                self.run_projection()
        self.clean_failure()
        with patch.object(m, "DECOMPRESSED_CAP_BYTES", 100):
            with self.assertRaises(m.ProjectionError):
                self.run_projection()
        self.clean_failure()

    def test_expired_and_mid_operation_deadlines_leave_no_partial_file(self):
        with self.assertRaisesRegex(m.ProjectionError, "deadline"):
            self.run_projection(deadline_monotonic=-1)
        self.clean_failure()
        calls = 0
        def clock():
            nonlocal calls
            calls += 1
            return 0 if calls < 15 else 101
        with patch.object(m.time, "monotonic", side_effect=clock):
            with self.assertRaisesRegex(m.ProjectionError, "deadline"):
                self.run_projection(deadline_monotonic=100)
        self.clean_failure()

    def test_source_mutation_after_authentication_refuses(self):
        original = m.BoundedOutput.write
        changed = False
        def mutate(writer, body):
            nonlocal changed
            if not changed:
                changed = True
                with self.source.open("ab") as f:
                    f.write(b"drift")
            return original(writer, body)
        with patch.object(m.BoundedOutput, "write", mutate):
            with self.assertRaisesRegex(m.ProjectionError, "identity changed"):
                self.run_projection()
        self.clean_failure()

    def test_oversized_directory_refuses_before_zip_parser(self):
        body = bytearray(self.source.read_bytes())
        struct.pack_into("<I", body, len(body)-22+12, m.DIRECTORY_CAP_BYTES+1)
        self.source.write_bytes(body)
        with patch.object(m.zipfile, "ZipFile", side_effect=AssertionError("must not parse")):
            with self.assertRaisesRegex(m.ProjectionError, "end directory"):
                self.run_projection()
        self.clean_failure()

    def test_atomic_publish_race_preserves_other_destination(self):
        real_link = os.link
        def race(source, destination, **kw):
            self.output.write_bytes(b"other operator output")
            return real_link(source, destination, **kw)
        with patch.object(m.os, "link", side_effect=race):
            with self.assertRaises(FileExistsError):
                self.run_projection()
        self.assertEqual(self.output.read_bytes(), b"other operator output")
        self.assertEqual(list(self.root.glob(".train-packet-*")), [])

    def test_post_publish_sync_failure_removes_only_own_output(self):
        real_sync = os.fsync
        calls = 0
        def fail_second(fd):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("directory sync failed")
            return real_sync(fd)
        with patch.object(m.os, "fsync", side_effect=fail_second):
            with self.assertRaisesRegex(OSError, "sync failed"):
                self.run_projection()
        self.clean_failure()


if __name__ == "__main__":
    unittest.main(verbosity=2)
