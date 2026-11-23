"""Generated T1 boundary controls; no scientific signals or estimator replay.

NumPy supplies array containers only. SciPy stage doubles and a stub kernel
isolate the finite-output boundary; these tests do not qualify numerical-library
versions, convolution/Hilbert parity, physiological inputs, or a native run.
"""
import argparse
from contextlib import contextmanager
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch

import numpy as np

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument("--program-source", type=Path)
args, remaining = parser.parse_known_args()
sys.argv = [sys.argv[0], *remaining]
PROGRAM = args.program_source or Path(__file__).resolve().parents[1] / "program"
sys.path.insert(0, str(PROGRAM))
spec = importlib.util.spec_from_file_location("neural042_pac_tool_under_test", PROGRAM / "pac_tool.py")
tool_source = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool_source)
from core import Refusal


@contextmanager
def primitive(convolve=None, hilbert=None):
    """Stage doubles make an invalid intermediate reproducible on any host."""
    scipy = types.ModuleType("scipy")
    scipy.__version__ = "1.15.3"  # Stub identity, not an installed-library claim.
    signal = types.ModuleType("scipy.signal")
    signal.convolve = Mock(side_effect=convolve or (lambda values, *_a, **_k: values.copy()))
    signal.hilbert = Mock(side_effect=hilbert or (lambda values: values.astype(np.complex128)))
    scipy.signal = signal
    tool = tool_source.Tool(Mock(), 100_000)
    with patch.dict(sys.modules, {"scipy": scipy, "scipy.signal": signal}), \
            patch.object(tool, "_np", return_value=np), \
            patch.object(tool, "kernel", return_value=np.array([1.0], dtype=np.float64)):
        yield tool, signal


class AnalyticBoundaryTests(unittest.TestCase):
    def test_finite_complete_rows_retain_values(self):
        values = np.linspace(-1, 1, 2000, dtype=np.float64).reshape(2, 1000)
        with primitive(hilbert=lambda x: x + 0.25j * x) as (tool, signal):
            actual = tool.analytic(values, 3, 5)
        np.testing.assert_array_equal(actual, values + 0.25j * values)
        self.assertEqual(actual.dtype, np.dtype(np.complex128))
        self.assertEqual(signal.convolve.call_count, 2)
        self.assertEqual(signal.hilbert.call_count, 2)

    def test_nonfinite_filtered_row_refuses_before_hilbert(self):
        values = np.ones((1, 1000), dtype=np.float64)
        for bad in (float("inf"), float("nan")):
            with self.subTest(value=bad), primitive(
                    convolve=lambda x, *_a, **_k: np.full(x.shape, bad)) as (tool, signal):
                with self.assertRaisesRegex(Refusal, "finite complete filtered output"):
                    tool.analytic(values, 3, 5)
                signal.hilbert.assert_not_called()

    def test_nonfinite_analytic_row_refuses(self):
        values = np.ones((1, 1000), dtype=np.float64)
        for bad in (complex(float("inf"), 0), complex(0, float("nan"))):
            with self.subTest(value=bad), primitive(
                    hilbert=lambda x: np.full(x.shape, bad, dtype=np.complex128)) as (tool, _):
                with self.assertRaisesRegex(Refusal, "finite complete analytic output"):
                    tool.analytic(values, 3, 5)

    def test_filtered_shape_refuses_before_transform(self):
        values = np.ones((1, 1000), dtype=np.float64)
        with primitive(convolve=lambda x, *_a, **_k: x[:-1]) as (tool, signal):
            with self.assertRaisesRegex(Refusal, "finite complete filtered output"):
                tool.analytic(values, 3, 5)
            signal.hilbert.assert_not_called()

    def test_transform_shape_cannot_broadcast_single_value(self):
        values = np.ones((1, 1000), dtype=np.float64)
        with primitive(hilbert=lambda _x: np.array([1j])) as (tool, _):
            with self.assertRaisesRegex(Refusal, "finite complete analytic output"):
                tool.analytic(values, 3, 5)

    def test_nonfinite_input_refuses_before_stages(self):
        values = np.ones((1, 1000), dtype=np.float64)
        values[0, 0] = np.nan
        with primitive() as (tool, signal):
            with self.assertRaisesRegex(Refusal, "finite exact numerical input"):
                tool.analytic(values, 3, 5)
            signal.convolve.assert_not_called()
            signal.hilbert.assert_not_called()

    def test_invalid_later_row_does_not_return_partial_array(self):
        values = np.ones((2, 1000), dtype=np.float64)
        with primitive() as (tool, signal):
            signal.hilbert.side_effect = [np.ones(1000, dtype=np.complex128),
                                         np.full(1000, complex(0, np.inf))]
            with self.assertRaises(Refusal):
                tool.analytic(values, 3, 5)
            self.assertEqual(signal.hilbert.call_count, 2)

    def test_declared_undefined_mi_semantics_remain(self):
        # MATHEMATICS.md intentionally treats these as unsupported MI, not a
        # changed analytical failure policy. This patch only guards analytic().
        for counts, sums in ((np.zeros(18, dtype=int), np.zeros(18)),
                             (np.ones(18, dtype=int), np.zeros(18)),
                             (np.ones(18, dtype=int), np.full(18, np.inf))):
            with primitive() as (tool, _), patch.object(tool, "histogram", return_value=(counts, sums)):
                self.assertIsNone(tool.mi(None, None))


if __name__ == "__main__":
    unittest.main()
