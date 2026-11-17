"""Generated ObjectStore descriptor-ownership controls; no native/data execution."""
import errno
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = "benchmarks/paper/PAPER-paper-method-006/implementations/registered-runtime"
SOURCE = PACKAGE + "/payload/legacy/k4bench/protocol.py"
DESCRIPTOR = "benchmarks/integrity/current-closures/trust-kilosort/SOURCE.json"


class ObjectStoreDescriptors(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # This reviewed module imports only the standard library and has no
        # startup I/O. Execute the exact source body, never a cached bytecode file.
        body = (ROOT / SOURCE).read_bytes()
        descriptor = json.loads((ROOT / DESCRIPTOR).read_text())
        pin = descriptor["members"][SOURCE]
        if (len(body), hashlib.sha256(body).hexdigest()) != (pin["bytes"], pin["sha256"]):
            raise AssertionError("Current ObjectStore source identity changed")
        name = "_kilosort_object_store_protocol_controls"
        module = types.ModuleType(name)
        module.__file__ = str(ROOT / SOURCE)
        sys.modules[name] = module
        exec(compile(body, module.__file__, "exec"), module.__dict__)
        cls.protocol = module

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="kilosort-object-store-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.meter = self.protocol.Meter(4096, 0, 0)
        self.store = self.protocol.ObjectStore(self.root, self.meter)
        self.opened = []
        real_open = os.open

        def tracked_open(*args, **kwargs):
            fd = real_open(*args, **kwargs)
            self.opened.append(fd)
            return fd

        self.track_open = mock.patch.object(self.protocol.os, "open", tracked_open)

    def assert_closed(self, fd):
        with self.assertRaises(OSError) as error:
            os.fstat(fd)
        self.assertEqual(error.exception.errno, errno.EBADF)

    def pin(self, name, body):
        return {"path": name, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}

    def test_nonregular_leaf_rejection_closes_leaf_and_directory(self):
        (self.root / "not-a-file").mkdir()
        with self.track_open:
            with self.assertRaises(self.protocol.Rejected) as error:
                self.store._open("not-a-file")
        self.assertEqual(error.exception.code, "not-regular-file")
        self.assertEqual(len(self.opened), 2)
        for fd in self.opened:
            self.assert_closed(fd)

    def test_leaf_metadata_failure_closes_all_owned_descriptors(self):
        (self.root / "object").write_bytes(b"generated")
        failure = OSError(errno.EIO, "generated fstat failure")
        with self.track_open, mock.patch.object(self.protocol.os, "fstat", side_effect=failure):
            with self.assertRaises(OSError) as error:
                self.store._open("object")
        self.assertIs(error.exception, failure)
        self.assertEqual(len(self.opened), 2)
        for fd in self.opened:
            self.assert_closed(fd)

    def test_success_transfers_only_regular_leaf_to_caller(self):
        body = b"generated immutable object"
        (self.root / "object").write_bytes(body)
        with self.track_open:
            fd = self.store._open("object")
        try:
            self.assertEqual(len(self.opened), 2)
            self.assertEqual(fd, self.opened[-1])
            self.assert_closed(self.opened[0])
            self.assertEqual(os.read(fd, len(body)), body)
        finally:
            os.close(fd)

    def test_successful_verified_read_closes_returned_leaf_once(self):
        body = b"generated immutable object"
        (self.root / "object").write_bytes(body)
        with self.track_open:
            self.assertEqual(self.store.read(self.pin("object", body), retain=True), body)
        self.assertEqual(self.meter.reads, len(body))
        self.assertEqual(len(self.opened), 2)
        for fd in self.opened:
            self.assert_closed(fd)

    def test_digest_refusal_closes_returned_leaf(self):
        body = b"generated"
        (self.root / "object").write_bytes(body)
        pin = self.pin("object", body)
        pin["sha256"] = "0" * 64
        with self.track_open:
            with self.assertRaises(self.protocol.Rejected) as error:
                self.store.read(pin, retain=True)
        self.assertEqual(error.exception.code, "digest-mismatch")
        self.assertEqual(len(self.opened), 2)
        for fd in self.opened:
            self.assert_closed(fd)

    def test_missing_member_and_symlink_refuse_without_open_leak(self):
        (self.root / "object").write_bytes(b"generated")
        (self.root / "alias").symlink_to("object")
        for name in ("missing", "alias"):
            with self.subTest(name=name):
                self.opened.clear()
                with self.track_open:
                    with self.assertRaises(OSError):
                        self.store._open(name)
                self.assertEqual(len(self.opened), 1)
                self.assert_closed(self.opened[0])

    def test_parent_traversal_failure_closes_last_directory(self):
        (self.root / "directory").mkdir()
        with self.track_open:
            with self.assertRaises(FileNotFoundError):
                self.store._open("directory/missing/object")
        self.assertEqual(len(self.opened), 2)
        for fd in self.opened:
            self.assert_closed(fd)

    def test_current_descriptor_preserves_historical_members(self):
        descriptor = json.loads((ROOT / DESCRIPTOR).read_text())
        self.assertFalse(descriptor["scientific_qualification"])
        self.assertFalse(descriptor["execution_authority"])
        self.assertEqual(descriptor["changed_members"], [SOURCE])
        for pin in descriptor["predecessor_manifests"]:
            body = (ROOT / pin["path"]).read_bytes()
            self.assertEqual((len(body), hashlib.sha256(body).hexdigest()),
                             (pin["bytes"], pin["sha256"]))
        frozen = json.loads((ROOT / PACKAGE / "SOURCE_FREEZE.json").read_text())
        original_prefix = "benchmarks/neuroscience/paper-method-006/"
        expected = {PACKAGE + "/" + path.removeprefix(original_prefix): pin
                    for path, pin in frozen["files"].items()}
        self.assertEqual(set(descriptor["members"]), set(expected))
        for path, pin in descriptor["members"].items():
            body = (ROOT / path).read_bytes()
            self.assertEqual((len(body), hashlib.sha256(body).hexdigest()),
                             (pin["bytes"], pin["sha256"]), path)
            if path != SOURCE:
                self.assertEqual(pin, expected[path], path)
        test_pin = descriptor["regression_test"]
        body = (ROOT / test_pin["path"]).read_bytes()
        self.assertEqual((len(body), hashlib.sha256(body).hexdigest()),
                         (test_pin["bytes"], test_pin["sha256"]))


if __name__ == "__main__":
    unittest.main()
