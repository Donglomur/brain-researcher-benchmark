"""Focused generated dependency-loader controls, with no scientific fixtures."""
import builtins
from contextlib import contextmanager
import importlib.util
import marshal
import os
from pathlib import Path
import struct
import tempfile
import types
import unittest
from unittest.mock import patch

EXPORTER = Path(__file__).parents[1] / "native_order.py"
n = types.ModuleType("native_order_loader_controls")
n.__file__ = str(EXPORTER)
exec(compile(EXPORTER.read_bytes(), str(EXPORTER), "exec"), n.__dict__)
DEPENDENCIES = {
    "bridge": ("original-fold-bridge-v1/bridge.py", n.BRIDGE_SHA256),
    "scorer": ("original-row-score-v1/scorer.py", n.SCORER_SHA256),
}
SOURCES = {key: (EXPORTER.parent.parent / path).read_bytes()
           for key, (path, _) in DEPENDENCIES.items()}
FIXTURE_BYTES = 0
POISON = b"CACHE_POISON = 'unreviewed bytes'\n"


def write_fixture(path, data):
    global FIXTURE_BYTES
    FIXTURE_BYTES += len(data)
    if FIXTURE_BYTES > 131072:
        raise RuntimeError("generated loader fixture write forecast exceeded")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


@contextmanager
def fixture():
    with tempfile.TemporaryDirectory(prefix="native-order-loader-",
                                     dir=os.environ.get("STRUCTURED_LOADER_FIXTURE_ROOT")) as directory:
        root = Path(directory)
        paths = {}
        for key, (relative, _) in DEPENDENCIES.items():
            paths[key] = root / relative
            write_fixture(paths[key], SOURCES[key])
        yield root, paths


class CapturedLoaderTests(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        print("GENERATED_LOADER_FIXTURE_BYTES=" + str(FIXTURE_BYTES))

    def assert_original(self, module):
        self.assertFalse(hasattr(module, "CACHE_POISON"))
        self.assertFalse(hasattr(module.SCORER, "CACHE_POISON"))
        self.assertEqual(module.SCORER.TASK_ID, n.scorer.TASK_ID)
        self.assertEqual(module.SCORER.circular_error(2, 0), 1)

    def test_unchecked_stale_caches_for_both_dependencies_are_ignored(self):
        with fixture() as (root, paths):
            for key, path in paths.items():
                # A valid unchecked-hash .pyc which ordinary SourceFileLoader
                # really accepts despite the original reviewed .py on disk.
                payload = (importlib.util.MAGIC_NUMBER + struct.pack("<I", 1)
                           + b"generated"[:8] + marshal.dumps(compile(POISON, str(path), "exec")))
                write_fixture(Path(importlib.util.cache_from_source(str(path))), payload)
                spec = importlib.util.spec_from_file_location("cache_control_" + key, path)
                ordinary = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(ordinary)
                self.assertEqual(ordinary.CACHE_POISON, "unreviewed bytes")
            original_import = builtins.__import__
            original_spec = importlib.util.spec_from_file_location
            self.assert_original(n._load_dependencies(root))
            self.assertIs(builtins.__import__, original_import)
            self.assertIs(importlib.util.spec_from_file_location, original_spec)

    def test_bridge_replaced_after_capture_cannot_change_executed_bytes(self):
        with fixture() as (root, paths):
            read_bytes = Path.read_bytes

            def replace_after_read(path):
                data = read_bytes(path)
                if path == paths["bridge"]:
                    write_fixture(path, POISON)
                return data

            with patch.object(Path, "read_bytes", replace_after_read):
                self.assert_original(n._load_dependencies(root))
            self.assertEqual(paths["bridge"].read_bytes(), POISON)

    def test_scorer_replaced_after_bridge_recheck_executes_captured_bytes(self):
        with fixture() as (root, paths):
            read_bytes = Path.read_bytes
            reads = 0

            def replace_after_recheck(path):
                nonlocal reads
                data = read_bytes(path)
                if path == paths["scorer"]:
                    reads += 1
                    if reads == 2:
                        write_fixture(path, POISON)
                return data

            with patch.object(Path, "read_bytes", replace_after_recheck):
                self.assert_original(n._load_dependencies(root))
            self.assertEqual(reads, 2)
            self.assertEqual(paths["scorer"].read_bytes(), POISON)

    def test_scorer_replaced_before_bridge_recheck_fails_closed(self):
        with fixture() as (root, paths):
            read_bytes = Path.read_bytes
            reads = 0

            def replace_after_capture(path):
                nonlocal reads
                data = read_bytes(path)
                if path == paths["scorer"]:
                    reads += 1
                    if reads == 1:
                        write_fixture(path, POISON)
                return data

            with patch.object(Path, "read_bytes", replace_after_capture):
                with self.assertRaisesRegex(ValueError, "scorer differs from the reviewed dependency"):
                    n._load_dependencies(root)

    def test_both_initial_source_hashes_remain_required(self):
        with fixture() as (root, paths):
            write_fixture(paths["bridge"], POISON)
            with self.assertRaisesRegex(RuntimeError, "fold bridge dependency changed"):
                n._load_dependencies(root)
            write_fixture(paths["bridge"], SOURCES["bridge"])
            write_fixture(paths["scorer"], POISON)
            with self.assertRaisesRegex(RuntimeError, "row scorer dependency changed"):
                n._load_dependencies(root)


if __name__ == "__main__":
    unittest.main(verbosity=2)
