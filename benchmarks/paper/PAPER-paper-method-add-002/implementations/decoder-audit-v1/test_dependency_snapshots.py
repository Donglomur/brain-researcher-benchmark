"""Generated dependency-loader regressions; no data, fits or model execution.

Fixture pins are explicitly rebound to generated Python modules. Production
loader statements and checks are otherwise used intact, including top-level
bridge/audited-producer imports and representation.original_audit().
"""
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("SLICETCA_TEST_IMPLEMENTATIONS", str(HERE.parent)))
WRITTEN = 0


def put(path, raw):
    global WRITTEN
    WRITTEN += len(raw)
    if WRITTEN > 1024 ** 2:
        raise AssertionError("generated source write budget exceeded")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)


def pin(source, name, raw):
    pattern = rf"({name}\s*=\s*['\"])[a-f0-9]{{64}}(['\"])"
    source, count = re.subn(pattern, lambda m: m[1] + hashlib.sha256(raw).hexdigest() + m[2], source)
    if count != 1:
        raise AssertionError("one generated dependency pin required: " + name)
    return source


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    # The entrypoint is a source capture; assertions concern its real nested loaders.
    exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
    return module


class DependencySnapshots(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.templates = {
            "bridge": (ROOT / "submission-bridge-v1/bridge.py").read_text(),
            "producer": (ROOT / "decoder-audit-v1/audited_producer.py").read_text(),
            "audit": (ROOT / "decoder-audit-v1/audit_packet.py").read_text(),
            "representation": (ROOT / "decoder-audit-v1/representation_audit.py").read_text(),
        }

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=HERE)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.original = self.root / "source-producer-v1/producer.py"
        generated = b"from types import SimpleNamespace\nendpoints = SimpleNamespace()\nSNAPSHOT_SENTINEL = 'trusted'\n"
        put(self.original, generated)
        self.bridge = self.root / "submission-bridge-v1/bridge.py"
        bridge = pin(self.templates["bridge"], "PRODUCER_SHA", generated)
        bridge += "\nSNAPSHOT_SENTINEL = 'trusted'\n"
        put(self.bridge, bridge.encode())
        self.producer = self.root / "decoder-audit-v1/audited_producer.py"
        producer = pin(self.templates["producer"], "PRODUCER_SHA256", generated)
        put(self.producer, producer.encode())
        self.audit = self.root / "decoder-audit-v1/audit_packet.py"
        audit = pin(self.templates["audit"], "BRIDGE_SHA256", bridge.encode())
        audit = pin(audit, "AUDITED_PRODUCER_SHA256", producer.encode())
        audit += "\nSNAPSHOT_SENTINEL = 'trusted'\n"
        put(self.audit, audit.encode())
        self.representation = self.root / "decoder-audit-v1/representation_audit.py"
        representation = pin(self.templates["representation"], "AUDIT_SHA256", audit.encode())
        put(self.representation, representation.encode())

    def replacement_after_capture(self, target, callback):
        ordinary = Path.read_bytes
        replaced = []
        def capture_then_replace(path):
            raw = ordinary(path)
            if path == target and not replaced:
                put(target, b"endpoints = object()\nSNAPSHOT_SENTINEL = 'untrusted'\n")
                replaced.append(True)
            return raw
        with mock.patch.object(Path, "read_bytes", capture_then_replace):
            result = callback()
        self.assertEqual(replaced, [True])
        self.assertIn(b"untrusted", ordinary(target))
        return result

    def test_bridge_executes_captured_producer(self):
        result = self.replacement_after_capture(self.original, lambda: load(self.bridge, "generated_bridge"))
        self.assertEqual(result.p.SNAPSHOT_SENTINEL, "trusted")

    def test_audited_producer_executes_captured_original(self):
        result = self.replacement_after_capture(self.original, lambda: load(self.producer, "generated_producer"))
        self.assertEqual(result.p.SNAPSHOT_SENTINEL, "trusted")

    def test_audit_loader_executes_captured_bridge(self):
        result = self.replacement_after_capture(self.bridge, lambda: load(self.audit, "generated_audit"))
        self.assertEqual(result.b.SNAPSHOT_SENTINEL, "trusted")

    def test_representation_executes_captured_audit(self):
        representation = load(self.representation, "generated_representation")
        result = self.replacement_after_capture(self.audit, representation.original_audit)
        self.assertEqual(result.SNAPSHOT_SENTINEL, "trusted")

    def test_unchanged_chain_preserves_module_paths_and_bindings(self):
        representation = load(self.representation, "generated_representation_stable")
        audit = representation.original_audit()
        self.assertEqual(audit.b.p.SNAPSHOT_SENTINEL, "trusted")
        self.assertEqual(audit.a.p.SNAPSHOT_SENTINEL, "trusted")
        self.assertEqual(Path(audit.__file__), self.audit)
        self.assertEqual(Path(audit.b.__file__), self.bridge)
        self.assertEqual(audit.b.PRODUCER_SHA, audit.a.PRODUCER_SHA256)
        self.assertEqual(audit.b.digest({"a": 1}), hashlib.sha256(b'{"a":1}\n').hexdigest())

    def test_wrong_source_hash_still_refused(self):
        put(self.original, b"raise AssertionError('untrusted source must not execute')\n")
        for path, name in ((self.bridge, "wrong_bridge"), (self.producer, "wrong_producer")):
            with self.subTest(path=path.name):
                with self.assertRaisesRegex(ValueError, "identity differs"):
                    load(path, name)

    @classmethod
    def tearDownClass(cls):
        print({"generated_source_cumulative_write_bytes": WRITTEN,
               "authentic_inputs": 0, "fits": 0})


if __name__ == "__main__":
    unittest.main(verbosity=2)
