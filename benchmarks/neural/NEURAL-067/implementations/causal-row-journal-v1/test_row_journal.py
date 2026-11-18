"""Generated row/journal controls; no authentic data, fitting or processes."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import io_utils as io
import row_journal as c


class Budget:
    def __init__(self):
        self.reads = 0
        self.written = 0
    def read(self, n):
        self.reads += n
    def debit(self, n, receipt=False):
        self.written += n
    def tick(self):
        pass


def row(ordinal=0):
    return {"token": "generated-token", "ordinal": ordinal, "observation": {"spikes": [1] * 176}}


def journal(path):
    return c.Journal(path, "generated-run", "neural", 2, {"bytes": 736, "sha256": "0" * 64}, Budget())


class RowJournalTests(unittest.TestCase):
    def test_recovered_formats_and_all_arm_domains(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td).resolve() / "cache"
            raw = b"".join(c.ROW.pack(*([i] * 176), t, trial) for i,t,trial in [(1,0.,4),(2,.02,4),(3,.04,5)])
            p.write_bytes(raw)
            self.assertEqual(c.ROW.size, 368)
            for arm in c.ARMS:
                cursor = c.Rows(p, io.identity(raw), "generated-run", arm, 3, Budget())
                first, second, third = cursor.next(), cursor.next(), cursor.next()
                expected = {"spikes"} if arm == "neural" else {"elapsed_run_s", "observed_segment_age_s", "segment_started_now"}
                if arm in ("neural_clock", "shifted_neural_clock"):
                    expected.add("spikes")
                self.assertEqual(set(first["observation"]), expected)
                self.assertEqual(set(first), {"token", "ordinal", "observation"})
                if arm != "neural":
                    self.assertEqual(second["observation"]["observed_segment_age_s"], .02)
                    self.assertEqual(third["observation"]["observed_segment_age_s"], 0.)
                self.assertIsNone(cursor.next())

    def test_cache_identity_and_nonmonotonic_time_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td).resolve() / "cache"
            raw = c.ROW.pack(*([1] * 176), .02, 1) * 2
            p.write_bytes(raw)
            with self.assertRaises(ValueError):
                c.Rows(p, {"bytes": len(raw), "sha256": "0" * 64}, "generated", "neural", 2, Budget())
            cursor = c.Rows(p, io.identity(raw), "generated", "neural", 2, Budget())
            cursor.next()
            with self.assertRaises(ValueError):
                cursor.next()

    def test_complete_chain_and_seven_action_order(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td).resolve() / "journal"
            j = journal(p)
            vector = [1., 2., 3., 4., 5., 6., 7.]
            j.append(row(), vector)
            j.append(row(1), [0.] * 7)
            pin = j.seal()
            body = p.read_bytes()
            self.assertEqual(pin, io.identity(body))
            self.assertEqual(len(body), 4096 + 2 * 160)
            first, second = body[4096:4256], body[4256:]
            self.assertEqual(c.ACTION.unpack(first[:64]), (0, *vector))
            self.assertEqual(first[128:], hashlib.sha256(first[:128]).digest())
            self.assertEqual(second[96:128], first[128:])
            self.assertEqual(p.stat().st_mode & 0o777, 0o444)
            self.assertTrue(j.closed)
            self.assertIsNone(j.fd)

    def test_failed_fsync_poisoned_journal_cannot_be_retried(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td).resolve() / "journal"
            j = journal(p)
            with patch.object(c.os, "fsync", side_effect=OSError("generated fsync failure")):
                with self.assertRaises(OSError):
                    j.append(row(), [0.] * 7)
            self.assertTrue(j.closed)
            self.assertIsNone(j.fd)
            self.assertEqual(j.i, 0)
            retained = p.read_bytes()
            with self.assertRaises(ValueError):
                j.append(row(), [0.] * 7)
            self.assertEqual(p.read_bytes(), retained)
            with self.assertRaises(ValueError):
                j.seal()

    def test_partial_write_error_preserves_failed_file_and_closes(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td).resolve() / "journal"
            j = journal(p)
            original_write = os.write
            calls = 0
            def fail_after_prefix(fd, data):
                nonlocal calls
                calls += 1
                if calls == 1:
                    return original_write(fd, data[:8])
                raise OSError("generated partial write failure")
            with patch.object(c.os, "write", side_effect=fail_after_prefix):
                with self.assertRaises(OSError):
                    j.append(row(), [0.] * 7)
            self.assertEqual(p.stat().st_size, 4104)
            self.assertTrue(j.closed)
            self.assertIsNone(j.fd)
            self.assertEqual(j.i, 0)

    def test_post_fsync_deadline_failure_is_not_a_committed_action(self):
        with tempfile.TemporaryDirectory() as td:
            j = journal(Path(td).resolve() / "journal")
            with patch.object(j.budget, "tick", side_effect=[None, TimeoutError("generated deadline")]):
                with self.assertRaises(TimeoutError):
                    j.append(row(), [0.] * 7)
            self.assertEqual(j.i, 0)
            self.assertTrue(j.closed)
            self.assertIsNone(j.fd)

    def test_seal_permission_error_closes_descriptor(self):
        with tempfile.TemporaryDirectory() as td:
            j = journal(Path(td).resolve() / "journal")
            j.append(row(), [0.] * 7)
            j.append(row(1), [0.] * 7)
            with patch.object(c.os, "fchmod", side_effect=OSError("generated permission failure")):
                with self.assertRaises(OSError):
                    j.seal()
            self.assertTrue(j.closed)
            self.assertIsNone(j.fd)
            with self.assertRaises(ValueError):
                j.seal()

    def test_seal_read_failure_does_not_produce_successful_pin(self):
        with tempfile.TemporaryDirectory() as td:
            j = journal(Path(td).resolve() / "journal")
            j.append(row(), [0.] * 7)
            j.append(row(1), [0.] * 7)
            with patch.object(c, "capture", side_effect=ValueError("generated post-close identity mismatch")):
                with self.assertRaises(ValueError):
                    j.seal()
            self.assertTrue(j.closed)
            self.assertIsNone(j.fd)

    def test_incomplete_future_duplicate_and_nonfinite_actions_refuse(self):
        with tempfile.TemporaryDirectory() as td:
            j = journal(Path(td).resolve() / "journal")
            for r, vector in [(row(1), [0.] * 7), (row(), [0.] * 6), (row(), [float("inf")] * 7), (row(), [True] * 7)]:
                with self.assertRaises(ValueError):
                    j.append(r, vector)
            j.append(row(), [0.] * 7)
            with self.assertRaises(ValueError):
                j.append(row(), [0.] * 7)
            with self.assertRaises(ValueError):
                j.seal()
            j.close()

    def test_existing_destination_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td).resolve() / "journal"
            p.write_bytes(b"prior evidence")
            with self.assertRaises(FileExistsError):
                journal(p)
            self.assertEqual(p.read_bytes(), b"prior evidence")

    def test_initial_deadline_failure_permanently_closes(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td).resolve() / "journal"
            j = journal(p)
            before = p.read_bytes()
            with patch.object(j.budget, "tick", side_effect=TimeoutError("generated initial deadline")):
                with self.assertRaises(TimeoutError):
                    j.append(row(), [0.] * 7)
            self.assertTrue(j.closed)
            self.assertIsNone(j.fd)
            self.assertIsNone(j.close_error)
            self.assertEqual(j.i, 0)
            self.assertEqual(p.read_bytes(), before)
            with self.assertRaises(ValueError):
                j.append(row(), [0.] * 7)

    def test_close_failure_marks_logical_closure_and_unknown_descriptor(self):
        with tempfile.TemporaryDirectory() as td:
            j = journal(Path(td).resolve() / "journal")
            fd = j.fd
            error = OSError("generated close failure")
            try:
                with patch.object(c.os, "close", side_effect=error):
                    with self.assertRaises(OSError) as caught:
                        j.close()
                self.assertIs(caught.exception, error)
                self.assertTrue(j.closed)
                self.assertIsNone(j.fd)
                self.assertEqual(j.close_error, {"descriptor": fd, "type": "OSError", "descriptor_state": "unknown"})
                with self.assertRaises(ValueError):
                    j.append(row(), [0.] * 7)
                with self.assertRaises(ValueError):
                    j.seal()
            finally:
                # The mocked os.close did not close it; this is fixture-only cleanup.
                os.close(fd)

    def test_append_original_error_remains_primary_when_close_also_fails(self):
        with tempfile.TemporaryDirectory() as td:
            j = journal(Path(td).resolve() / "journal")
            fd = j.fd
            original = OSError("generated fsync failure")
            cleanup = OSError("generated close failure")
            try:
                with patch.object(c.os, "fsync", side_effect=original), patch.object(c.os, "close", side_effect=cleanup):
                    with self.assertRaises(OSError) as caught:
                        j.append(row(), [0.] * 7)
                self.assertIs(caught.exception, original)
                self.assertIs(caught.exception.__cause__, cleanup)
                self.assertTrue(j.closed)
                self.assertEqual(j.i, 0)
                self.assertEqual(j.close_error["descriptor_state"], "unknown")
            finally:
                os.close(fd)

    def test_seal_original_error_remains_primary_when_close_also_fails(self):
        with tempfile.TemporaryDirectory() as td:
            j = journal(Path(td).resolve() / "journal")
            j.append(row(), [0.] * 7)
            j.append(row(1), [0.] * 7)
            fd = j.fd
            original = OSError("generated seal failure")
            cleanup = OSError("generated close failure")
            try:
                with patch.object(c.os, "fchmod", side_effect=original), patch.object(c.os, "close", side_effect=cleanup):
                    with self.assertRaises(OSError) as caught:
                        j.seal()
                self.assertIs(caught.exception, original)
                self.assertIs(caught.exception.__cause__, cleanup)
                self.assertTrue(j.closed)
                self.assertEqual(j.close_error["descriptor_state"], "unknown")
            finally:
                os.close(fd)

    def test_constructor_original_error_remains_primary_when_close_fails(self):
        with tempfile.TemporaryDirectory() as td:
            obj = c.Journal.__new__(c.Journal)
            original = OSError("generated header fsync failure")
            cleanup = OSError("generated close failure")
            with patch.object(c.os, "fsync", side_effect=original), patch.object(c.os, "close", side_effect=cleanup):
                with self.assertRaises(OSError) as caught:
                    obj.__init__(Path(td).resolve() / "journal", "generated", "neural", 2,
                                 {"bytes": 736, "sha256": "0" * 64}, Budget())
            try:
                self.assertIs(caught.exception, original)
                self.assertIs(caught.exception.__cause__, cleanup)
                self.assertTrue(obj.closed)
                self.assertIsNone(obj.fd)
                self.assertEqual(obj.close_error["descriptor_state"], "unknown")
            finally:
                os.close(obj.close_error["descriptor"])


if __name__ == "__main__":
    unittest.main()
