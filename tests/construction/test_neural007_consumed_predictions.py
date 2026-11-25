"""Generated-only regression for full-night prediction header custody.

No original EEG, target annotations, fitted model or numerical library is read.
"""
import argparse
import hashlib
import importlib.util
from pathlib import Path
import struct
import sys
import tempfile
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
PROGRAM = ROOT / "benchmarks/neural/NEURAL-007/implementations/whole-night-programme/program"


def load_scorer(program):
    name = "_sleep_prediction_header_controls"
    package = types.ModuleType(name)
    package.__path__ = [str(program)]
    package.__package__ = name
    sys.modules[name] = package
    spec = importlib.util.spec_from_file_location(name + ".scorer", program / "scorer.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def generated_npy(shape=(2, 5), dtype="<f8", fortran=False):
    header = repr({"descr": dtype, "fortran_order": fortran, "shape": shape}).encode("ascii")
    # All selected mutations deliberately retain equal header/payload extent.
    header = header + b" " * (117 - len(header)) + b"\n"
    return b"\x93NUMPY\x01\x00" + struct.pack("<H", len(header)) + header + struct.pack("<10d", *([.2] * 10))


class Meter:
    def __init__(self):
        self.read_bytes = 0

    def read(self, count):
        self.read_bytes += count
        if self.read_bytes > 16384:
            raise ValueError("Generated control read ceiling")


class ConsumedPredictionHeaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scorer = load_scorer(PROGRAM)

    def artifact(self, root, body):
        path = root / "predictions.npy"
        path.write_bytes(body)
        return {"path": str(path), "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}

    def test_complete_probabilities_unchanged(self):
        with tempfile.TemporaryDirectory(prefix="sleep-header-generated-") as temp:
            artifact = self.artifact(Path(temp).resolve(), generated_npy())
            meter = Meter()
            self.assertEqual(list(self.scorer.array_rows(artifact, 2, 5, "<f8", meter)), [[.2] * 5] * 2)
            self.assertGreater(meter.read_bytes, artifact["bytes"])

    def replaced_header(self, replacement):
        with tempfile.TemporaryDirectory(prefix="sleep-header-generated-") as temp:
            root = Path(temp).resolve()
            frozen = self.artifact(root, replacement)
            path = Path(frozen["path"])
            path.write_bytes(generated_npy())
            original = self.scorer.npy_header

            def swap_after_header(*args, **kwargs):
                header = original(*args, **kwargs)
                # The trusted descriptor belongs to replacement. The first open
                # sees a different valid header; the consumed open must recheck.
                path.write_bytes(replacement)
                return header

            with mock.patch.object(self.scorer, "npy_header", side_effect=swap_after_header):
                iterator = self.scorer.array_rows(frozen, 2, 5, "<f8", Meter())
                try:
                    with self.assertRaises(ValueError):
                        next(iterator)  # Refusal must precede yielding any probability.
                finally:
                    iterator.close()

    def test_replaced_geometry_rejected_before_rows(self):
        self.replaced_header(generated_npy(shape=(1, 10)))

    def test_replaced_fortran_layout_rejected_before_rows(self):
        self.replaced_header(generated_npy(fortran=True))

    def test_replaced_dtype_rejected_before_rows(self):
        self.replaced_header(generated_npy(dtype="<i8"))

    def test_complete_content_digest_still_required(self):
        with tempfile.TemporaryDirectory(prefix="sleep-header-generated-") as temp:
            artifact = self.artifact(Path(temp).resolve(), generated_npy())
            artifact["sha256"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "entire numeric content"):
                list(self.scorer.array_rows(artifact, 2, 5, "<f8", Meter()))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--program-root", type=Path)
    options, remaining = parser.parse_known_args()
    if options.program_root is not None:
        PROGRAM = options.program_root.resolve(strict=True)
    unittest.main(argv=[sys.argv[0], *remaining])
