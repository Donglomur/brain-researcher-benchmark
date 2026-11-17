"""Source/metadata controls only: never import or execute the captured pipeline."""
import dataclasses
import hashlib
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch


HERE = Path(__file__).absolute()
REPO = HERE.parents[9]
MODULE_PATH = HERE.parents[1] / "source-capture" / "capture.py"
SPEC = importlib.util.spec_from_file_location("paper020_central_capture_test", MODULE_PATH)
capture = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = capture
SPEC.loader.exec_module(capture)


class SourceCaptureControls(unittest.TestCase):
    def clock(self):
        origin = time.monotonic_ns()
        return {"origin_ns": origin, "deadline_ns": origin + 60_000_000_000}

    def test_exact_accepted_source_snapshot_without_importing_pipeline(self):
        before = set(sys.modules)
        result = capture.capture_source(str(REPO), **self.clock())
        self.assertEqual(set(sys.modules), before)
        self.assertEqual(len(result.members), 34)
        self.assertEqual(result.read_bytes, capture.REQUIRED_READ_LIMIT_BYTES)
        self.assertEqual(sum(m.size_bytes for m in result.members), 462268)
        self.assertEqual(len({m.staged_path for m in result.members}), 34)
        self.assertEqual(result.scientific_source_digest, capture.SCIENTIFIC_SOURCE_DIGEST)
        self.assertEqual(result.merge_receipt_pin.size_bytes, 2807)
        for member in result.members:
            self.assertEqual(hashlib.sha256(member.body).hexdigest(), member.sha256)
            self.assertEqual(len(member.body), member.size_bytes)
            self.assertTrue(member.source_path.endswith(member.staged_path))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            result.members[0].body = b"replacement"

    def test_incomplete_budget_and_invalid_clock_open_nothing(self):
        with patch.object(capture.os, "open", side_effect=AssertionError("must not open")):
            with self.assertRaises(capture.CaptureError) as caught:
                capture.capture_source(str(REPO), read_limit_bytes=capture.READ_LIMIT_BYTES - 1,
                                       **self.clock())
            self.assertEqual(caught.exception.read_bytes, 0)
            with self.assertRaisesRegex(capture.CaptureError, "required"):
                capture.capture_source(str(REPO))
            with self.assertRaisesRegex(capture.CaptureError, "not live"):
                capture.capture_source(str(REPO), origin_ns=1, deadline_ns=2)

    def test_clock_expiration_after_capture_is_failure_with_charge(self):
        # Exercise the production final clock gate without reading the 34-file
        # closure a second time. The private binding/reader seam uses no body.
        receipt = {"path": "receipt", "bytes": 1, "sha256": "0" * 64}
        fake = {"files": [], "merge_identity": {"observed_receipt": receipt}}
        with patch.object(capture.time, "monotonic_ns", side_effect=[15, 25]), \
             patch.object(capture._Tree, "__enter__", lambda self: self), \
             patch.object(capture._Tree, "read", return_value=b""), \
             patch.object(capture._Tree, "verify"), \
             patch.object(capture, "_binding", return_value=fake):
            with self.assertRaisesRegex(capture.CaptureError, "not live") as caught:
                capture.capture_source(str(REPO), origin_ns=10, deadline_ns=20)
            self.assertEqual(caught.exception.read_bytes, 0)

    def fixture(self):
        temp = tempfile.TemporaryDirectory(prefix="paper020-source-metadata-")
        self.addCleanup(temp.cleanup)
        # The host temporary-directory spelling may itself contain a symlink;
        # resolve only this newly invented fixture, never an original operand.
        root = Path(temp.name).resolve()
        (root / "sub").mkdir()
        (root / "sub" / "source.py").write_bytes(b"invented source\n")
        return root

    def reader(self, root):
        return capture._Tree(str(root), 64)

    def test_owned_source_is_stable_and_fds_close(self):
        root = self.fixture()
        with self.reader(root) as tree:
            self.assertEqual(tree.read("sub/source.py", 16,
                             hashlib.sha256(b"invented source\n").hexdigest()), b"invented source\n")
            tree.verify()
            fds = tuple(tree.fds)
        self.assertEqual(tree.read_bytes, 16)
        for fd in fds:
            with self.assertRaises(OSError):
                os.fstat(fd)

    def test_replacement_after_read_is_rejected(self):
        root = self.fixture()
        with self.reader(root) as tree:
            tree.read("sub/source.py", 16, hashlib.sha256(b"invented source\n").hexdigest())
            (root / "replacement").write_bytes(b"invented source\n")
            os.replace(root / "replacement", root / "sub" / "source.py")
            with self.assertRaisesRegex(capture.CaptureError, "changed"):
                tree.verify()

    def test_directory_replacement_after_read_is_rejected(self):
        root = self.fixture()
        with self.reader(root) as tree:
            tree.read("sub/source.py", 16, hashlib.sha256(b"invented source\n").hexdigest())
            (root / "sub").rename(root / "old")
            (root / "sub").mkdir()
            with self.assertRaisesRegex(capture.CaptureError, "directory path changed"):
                tree.verify()

    def test_symlinks_hardlinks_and_wrong_hash_are_rejected(self):
        root = self.fixture()
        (root / "link").symlink_to(root / "sub", target_is_directory=True)
        (root / "file-link").symlink_to(root / "sub" / "source.py")
        for name in ("link/source.py", "file-link"):
            with self.reader(root) as tree, self.assertRaises(OSError):
                tree.read(name, 16, "0" * 64)
            self.assertEqual(tree.read_bytes, 0)
        with self.reader(root) as tree, self.assertRaisesRegex(capture.CaptureError, "SHA-256"):
            tree.read("sub/source.py", 16, "0" * 64)
        self.assertEqual(tree.read_bytes, 16)
        os.link(root / "sub" / "source.py", root / "hard-link")
        with self.reader(root) as tree, self.assertRaisesRegex(capture.CaptureError, "single-link"):
            tree.read("sub/source.py", 16, "0" * 64)
        self.assertEqual(tree.read_bytes, 0)

    def test_noncanonical_path_and_size_fail_before_payload_read(self):
        root = self.fixture()
        for name in ("../source.py", "sub/../source.py", "/sub/source.py", "sub//source.py"):
            with self.reader(root) as tree, self.assertRaises(capture.CaptureError):
                tree.read(name, 16, "0" * 64)
            self.assertEqual(tree.read_bytes, 0)
        with self.reader(root) as tree, self.assertRaisesRegex(capture.CaptureError, "pinned size"):
            tree.read("sub/source.py", 17, "0" * 64)
        self.assertEqual(tree.read_bytes, 0)


if __name__ == "__main__":
    unittest.main()
