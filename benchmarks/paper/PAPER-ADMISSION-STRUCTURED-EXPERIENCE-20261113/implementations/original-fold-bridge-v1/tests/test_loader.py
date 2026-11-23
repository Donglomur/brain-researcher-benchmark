"""Generated direct-import regressions; no scientific fixtures or model runs."""
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

BRIDGE = Path(__file__).parents[1] / "bridge.py"
SCORER = BRIDGE.parent.parent / "original-row-score-v1/scorer.py"
BRIDGE_SOURCE = BRIDGE.read_bytes()
SCORER_SOURCE = SCORER.read_bytes()
POISON = b"CACHE_POISON = 'unreviewed scorer'\n"
FIXTURE_BYTES = 0


def write_fixture(path, data):
    global FIXTURE_BYTES
    FIXTURE_BYTES += len(data)
    if FIXTURE_BYTES > 98304:
        raise RuntimeError("generated direct-loader fixture budget exceeded")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


@contextmanager
def fixture():
    with tempfile.TemporaryDirectory(prefix="structured-direct-loader-",
                                     dir=os.environ.get("STRUCTURED_BRIDGE_FIXTURE_ROOT")) as directory:
        root = Path(directory)
        bridge = root / "original-fold-bridge-v1/bridge.py"
        scorer = root / "original-row-score-v1/scorer.py"
        write_fixture(bridge, BRIDGE_SOURCE)
        write_fixture(scorer, SCORER_SOURCE)
        yield bridge, scorer


def load_bridge(path):
    module = types.ModuleType("structured_direct_bridge_control")
    module.__file__ = str(path)
    exec(compile(BRIDGE_SOURCE, str(path), "exec"), module.__dict__)
    return module


class DirectLoaderTests(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        print("GENERATED_DIRECT_LOADER_FIXTURE_BYTES=" + str(FIXTURE_BYTES))

    def assert_reviewed_scorer(self, bridge, path):
        self.assertFalse(hasattr(bridge.SCORER, "CACHE_POISON"))
        self.assertEqual(bridge.SCORER.__file__, str(path))
        self.assertEqual(bridge.SCORER.circular_error(39, 0), 0.25)
        self.assertEqual(bridge.SCORER.TASK_ID,
                         "PAPER-ADMISSION-STRUCTURED-EXPERIENCE-20261113")

    def test_unchecked_scorer_cache_cannot_override_reviewed_source(self):
        with fixture() as (bridge, scorer):
            payload = (importlib.util.MAGIC_NUMBER + struct.pack("<I", 1)
                       + b"control!" + marshal.dumps(compile(POISON, str(scorer), "exec")))
            write_fixture(Path(importlib.util.cache_from_source(str(scorer))), payload)
            # Establish that ordinary SourceFileLoader really accepts this cache.
            spec = importlib.util.spec_from_file_location("unchecked_cache_control", scorer)
            ordinary = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(ordinary)
            self.assertEqual(ordinary.CACHE_POISON, "unreviewed scorer")
            self.assert_reviewed_scorer(load_bridge(bridge), scorer)

    def test_replacement_after_capture_cannot_change_executed_scorer(self):
        with fixture() as (bridge, scorer):
            read_bytes = Path.read_bytes
            reads = 0

            def replace_after_read(path):
                nonlocal reads
                body = read_bytes(path)
                if path == scorer:
                    reads += 1
                    write_fixture(path, POISON)
                return body

            with patch.object(Path, "read_bytes", replace_after_read):
                self.assert_reviewed_scorer(load_bridge(bridge), scorer)
            self.assertEqual(reads, 1)
            self.assertEqual(scorer.read_bytes(), POISON)

    def test_initial_source_mismatch_still_refuses(self):
        with fixture() as (bridge, scorer):
            write_fixture(scorer, POISON)
            with self.assertRaisesRegex(ValueError, "scorer differs from the reviewed dependency"):
                load_bridge(bridge)


if __name__ == "__main__":
    unittest.main(verbosity=2)
