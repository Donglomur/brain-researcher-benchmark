"""Generated source-replacement controls; no EEG or authentic target inputs."""
import importlib.util
import os
from pathlib import Path
import tempfile
from types import ModuleType
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("NEURAL084_SOURCE_IMPLEMENTATIONS", HERE.parent))
CORE = "full-cohort-scoring-v1/score.py"
IO = "delivery-source/public/io_utils.py"
PAIR = "paired-access-scoring-v1/score.py"


def mirror(root):
    for name in (CORE, IO, PAIR):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((ROOT / name).read_bytes())


def load(root, replace=None):
    path = root / PAIR
    body = path.read_bytes()
    module = ModuleType("generated_paired_source_capture")
    module.__file__ = str(path)
    original_open = Path.open
    replaced = []

    class CapturedRead:
        def __init__(self, stream):
            self.stream = stream

        def __enter__(self):
            self.stream.__enter__()
            return self

        def __exit__(self, *args):
            return self.stream.__exit__(*args)

        def read(self, *args):
            raw = self.stream.read(*args)
            # Replace only AFTER the original bytes were captured for the
            # identity check, and before their caller can load the pathname.
            if not replaced:
                with original_open(root / replace, "wb") as target:
                    target.write(b"SOURCE_MARKER = 'unreviewed'\nio = object()\n")
                replaced.append(True)
            return raw

    def opening(path, mode="r", *args, **kwargs):
        stream = original_open(path, mode, *args, **kwargs)
        if replace is not None and Path(path) == root / replace and mode == "rb" and not replaced:
            return CapturedRead(stream)
        return stream

    with mock.patch.dict(os.environ, {"NEURAL084_SOURCE_IMPLEMENTATIONS": str(root)}):
        with mock.patch.object(Path, "open", opening):
            try:
                exec(compile(body, str(path), "exec"), module.__dict__)
            except Exception:
                if replace is not None:
                    assert replaced, "generated replacement must exercise the verified-read boundary"
                raise
    if replace is not None:
        assert replaced, "generated replacement must exercise the verified-read boundary"
    return module


class SourceCaptureTests(unittest.TestCase):
    def test_scorer_path_replacement_never_executes_new_bytes(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get("NEURAL084_TEST_TMP")) as temp:
            root = Path(temp)
            mirror(root)
            module = load(root, CORE)
            self.assertFalse(hasattr(module.s, "SOURCE_MARKER"))
            self.assertTrue(callable(module.s.grade))

    def test_io_path_replacement_rejected_before_execution(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get("NEURAL084_TEST_TMP")) as temp:
            root = Path(temp)
            mirror(root)
            with self.assertRaises(ValueError):
                load(root, IO)

    def test_complete_panel_semantics_and_input_pins(self):
        # Reuse the existing generated full54 fixture without any EEG arrays.
        spec = importlib.util.spec_from_file_location(
            "generated_source_capture_fixture", ROOT / "full-cohort-scoring-v1/test_score.py")
        fixture = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fixture)
        f = fixture.FullCohortTests
        f.setUpClass()
        p = load(ROOT)
        modes = dict(restricted="candidate", program="cca", cca="cca",
                     constant="constant", **{"frequency-permuted": "frequency-permuted"})
        report = p.grade(f.pool_raw, lambda mode, fold: f.outputs[modes[mode]][fold],
                         lambda pin: f.gold_raw)
        expected = sum(f.expected_correct.values()) / 21600
        self.assertEqual(report["counts"], dict(people=54, phases=216, queries=21600, modes=5))
        self.assertAlmostEqual(report["modes"]["restricted"]["score"], expected)
        self.assertEqual(report["modes"]["program"]["score"], 1)
        self.assertAlmostEqual(report["comparisons"]["program_minus_restricted"]["mean"], 1 - expected)
        self.assertEqual(report["source"]["pool"], p.io.pin(f.pool_raw))
        self.assertEqual(report["source"]["gold"], p.io.pin(f.gold_raw))
        self.assertEqual(report["source"]["predictions"]["restricted"]["fold054"],
                         p.io.pin(f.outputs["candidate"]["fold054"]))
        self.assertEqual(report["source"]["scoring_dependencies"], p.SOURCE_PINS)
        self.assertEqual(len(report["modes"]["restricted"]["phases"]), 216)
        self.assertEqual(len(report["modes"]["restricted"]["people"]), 54)


if __name__ == "__main__":
    unittest.main(verbosity=2)
