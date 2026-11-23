"""Generated ObjectStore descriptor-ownership controls; no native/data execution."""
from copy import deepcopy
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

    def assert_current_descriptor(self, descriptor=None, reader=None):
        descriptor = descriptor or json.loads((ROOT / DESCRIPTOR).read_text())
        reader = reader or (lambda path: (ROOT / path).read_bytes())
        self.assertFalse(descriptor["scientific_qualification"])
        self.assertFalse(descriptor["execution_authority"])
        # These original byte identities are retained, not refreshed from current
        # files when a later source generation is published.
        anchors = {
            "SOURCE_FREEZE.json": (13083, "15b9127b865743b6373d6040850eacb6671898553a92ee3610f25414a0782d93"),
            "ACCEPTED_SOURCE_MANIFEST.json": (30460, "47d9ec892bfe27b53d38fc09597ce252ea6594706cc4659d56640c384b1dda01"),
            "INSTALLED_SOURCE_RESOLUTION.json": (62403, "5cba82ed4458ee4a89af7bca8e7aacb7bf7b25fa21568799d4de3fcfa6e3db11"),
            "ACCEPTED_SOURCE_API.json": (125877, "32f6693ae720834e8ddf6418ab021abf70b0b3ce85e506a4b37309e9e52e871f"),
        }
        history_root = "benchmarks/integrity/current-closures/trust-kilosort/history/original-v1/"
        historical = {}
        self.assertEqual(len(descriptor["predecessor_manifests"]), len(anchors))
        for pin in descriptor["predecessor_manifests"]:
            name = Path(pin["original_path"]).name
            self.assertNotIn(name, historical)
            self.assertEqual(pin["original_path"], PACKAGE + "/" + name)
            self.assertEqual(pin["path"], history_root + name)
            self.assertEqual((pin["bytes"], pin["sha256"]), anchors[name])
            self.assertEqual(pin["captured_from_commit"], descriptor["comparison_commit"])
            body = reader(pin["path"])
            self.assertEqual((len(body), hashlib.sha256(body).hexdigest()), anchors[name])
            historical[name] = json.loads(body)
        self.assertEqual(set(historical), set(anchors))
        freeze_pin = descriptor["current_source_freeze"]
        self.assertEqual(freeze_pin["path"], PACKAGE + "/SOURCE_FREEZE.json")
        raw = reader(freeze_pin["path"])
        self.assertEqual((len(raw), hashlib.sha256(raw).hexdigest()),
                         (freeze_pin["bytes"], freeze_pin["sha256"]))
        frozen = json.loads(raw)
        original_prefix = "benchmarks/neuroscience/paper-method-006/"
        def translated(document):
            self.assertTrue(all(path.startswith(original_prefix) for path in document["files"]))
            return {PACKAGE + "/" + path.removeprefix(original_prefix): pin
                    for path, pin in document["files"].items()}
        expected = translated(frozen)
        previous = translated(historical["SOURCE_FREEZE.json"])
        current = descriptor["members"]
        self.assertEqual(set(current), set(expected))
        for path, pin in current.items():
            body = reader(path)
            self.assertEqual((len(body), hashlib.sha256(body).hexdigest()),
                             (pin["bytes"], pin["sha256"]), path)
        # The ObjectStore correction remains the only override of the current
        # package freeze. R2 and its current metadata are in that freeze itself.
        overrides = sorted(path for path in current if current[path] != expected[path])
        self.assertEqual(overrides, [SOURCE])
        self.assertEqual(descriptor["changed_members"], overrides)
        changes = sorted(path for path in set(previous) | set(current)
                         if previous.get(path) != current.get(path))
        reviewed_changes = sorted(PACKAGE + "/" + path for path in (
            "ACCEPTED_SOURCE_API.json", "ACCEPTED_SOURCE_MANIFEST.json",
            "INSTALLED_SOURCE_RESOLUTION.json", "README.md",
            "payload/legacy/banks/r2/bank.py", "payload/legacy/k4bench/protocol.py",
            "tests/test_source20_admission.py"))
        self.assertEqual(changes, reviewed_changes)
        self.assertEqual(descriptor["historical_changed_members"], changes)
        test_pin = descriptor["regression_test"]
        self.assertEqual(test_pin["path"], "tests/benchmarks/test_kilosort_object_store.py")
        body = reader(test_pin["path"])
        self.assertEqual((len(body), hashlib.sha256(body).hexdigest()),
                         (test_pin["bytes"], test_pin["sha256"]))

    def test_current_descriptor_preserves_historical_members(self):
        self.assert_current_descriptor()

    def test_historical_metadata_cannot_be_rebased_to_current(self):
        for index in range(4):
            descriptor = json.loads((ROOT / DESCRIPTOR).read_text())
            pin = descriptor["predecessor_manifests"][index]
            body = (ROOT / pin["original_path"]).read_bytes()
            pin.update(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
            with self.subTest(manifest=pin["original_path"]), self.assertRaises(AssertionError):
                self.assert_current_descriptor(descriptor)

    def test_changed_historical_snapshot_bytes_are_rejected(self):
        descriptor = json.loads((ROOT / DESCRIPTOR).read_text())
        path = descriptor["predecessor_manifests"][0]["path"]
        def changed_reader(member):
            body = (ROOT / member).read_bytes()
            return body + b"\n" if member == path else body
        with self.assertRaises(AssertionError):
            self.assert_current_descriptor(descriptor, changed_reader)

    def test_member_omission_or_unreported_change_is_rejected(self):
        original = json.loads((ROOT / DESCRIPTOR).read_text())
        for mutation in ("omitted_member", "omitted_history_change", "omitted_override", "stale_bank"):
            descriptor = deepcopy(original)
            if mutation == "omitted_member":
                del descriptor["members"][PACKAGE + "/tests/test_source20_admission.py"]
            elif mutation == "omitted_history_change":
                descriptor["historical_changed_members"].pop()
            elif mutation == "omitted_override":
                descriptor["changed_members"] = []
            else:
                descriptor["members"][PACKAGE + "/payload/legacy/banks/r2/bank.py"]["sha256"] = "0" * 64
            with self.subTest(mutation=mutation), self.assertRaises(AssertionError):
                self.assert_current_descriptor(descriptor)

    def test_current_freeze_has_separate_content_binding(self):
        descriptor = json.loads((ROOT / DESCRIPTOR).read_text())
        descriptor["current_source_freeze"]["sha256"] = descriptor["predecessor_manifests"][0]["sha256"]
        with self.assertRaises(AssertionError):
            self.assert_current_descriptor(descriptor)


if __name__ == "__main__":
    unittest.main()
