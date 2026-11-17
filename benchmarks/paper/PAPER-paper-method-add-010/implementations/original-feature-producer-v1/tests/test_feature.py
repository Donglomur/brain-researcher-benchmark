"""Independent generated controls; no authentic signals or native DBA execution.

The analytic solver seam checks orchestration and a known mathematical value.
It does not establish installed tslearn parity or reproduce the paper's result.
"""
from __future__ import annotations

import importlib.metadata
import importlib.util
import math
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import numpy as np

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
SPEC = importlib.util.spec_from_file_location("fc_independent_producer", HERE / "producer.py")
P = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(P)
I = P.inputs


def independent_normalization(row):
    """Sample-SD standardization followed by closed-form OLS residuals.

    Uses Python scalar arithmetic and fsum, never scipy's zscore/detrend.
    """
    values = [float(x) for x in row]
    count = len(values)
    mean = math.fsum(values) / count
    sd = math.sqrt(math.fsum((x - mean) ** 2 for x in values) / (count - 1))
    standardized = [(x - mean) / sd for x in values]
    center = (count - 1) / 2
    zmean = math.fsum(standardized) / count
    slope = (math.fsum((t - center) * (x - zmean) for t, x in enumerate(standardized)) /
             math.fsum((t - center) ** 2 for t in range(count)))
    return np.asarray([x - zmean - slope * (t - center) for t, x in enumerate(standardized)])


def generated_matrix():
    q = np.tile([-1., 1., 1., -1.], 250)
    time = np.arange(1000)
    return np.stack((3 + 2*q + .01*time,
                     -7 + 3*q - .003*time,
                     11 + 5*q + .02*time,
                     -8 + 7*q - .001*time))


class FeatureControls(unittest.TestCase):
    def test_independent_sample_sd_then_linear_ols_and_six_pair_order(self):
        values = generated_matrix()
        expected = np.stack([independent_normalization(row) for row in values])
        # This fixture detects a second z-score after detrending.
        self.assertLess(float(np.std(expected[0], ddof=1)), .8)
        actual = P.preprocess(values)
        np.testing.assert_allclose(actual, expected, rtol=2e-13, atol=2e-13)
        calls = []
        def analytic_mean(pair):
            calls.append(pair.copy())
            return np.mean(pair, axis=0)[:, None]
        value, diagnostic = P.feature(values, dba=analytic_mean)
        expected_order = ((1, 0), (2, 0), (3, 0), (2, 1), (3, 1), (3, 2))
        self.assertEqual(len(calls), 6)
        for supplied, pair in zip(calls, expected_order):
            np.testing.assert_allclose(supplied, expected[list(pair)], rtol=2e-13, atol=2e-13)
        expected_value = max(((a + b) / 2) ** 2 for a, b in zip(expected[2], expected[0]))
        self.assertAlmostEqual(value, expected_value, places=12)
        self.assertEqual(diagnostic["status"], "finite")
        self.assertEqual(diagnostic["native_pair_calls"], 6)

    def test_identical_trace_analytic_barycenter_feature_is_999_over_1000(self):
        q = np.tile([-1., 1., 1., -1.], 250)
        values = np.stack((q, q+17, 3*q-4, 5*q+2))
        expected = q * math.sqrt(999/1000)
        calls = []
        def identical_trace_barycenter(pair):
            # DBA of two identical traces has that trace as a zero-cost solution.
            # The seam supplies the exact analytic solution without running DBA.
            np.testing.assert_allclose(pair[0], expected, rtol=2e-13, atol=2e-13)
            np.testing.assert_allclose(pair[1], expected, rtol=2e-13, atol=2e-13)
            calls.append(True)
            return expected[:, None].copy()
        value, diagnostic = P.feature(values, dba=identical_trace_barycenter)
        self.assertAlmostEqual(value, 999/1000, places=14)
        self.assertEqual(len(calls), 6)
        self.assertEqual(diagnostic["native_pair_calls"], 6)

    def test_unused_pair_exception_erases_previously_finite_selected_statistic(self):
        calls = []
        def late_failure(pair):
            calls.append(pair.copy())
            if len(calls) == 6:
                raise RuntimeError("generated unused-pair solver failure")
            return np.ones((1000, 1))
        value, diagnostic = P.feature(generated_matrix(), dba=late_failure)
        self.assertIsNone(value)
        self.assertEqual(diagnostic["status"], "source_SPI_failure")
        self.assertEqual(diagnostic["exception_type"], "RuntimeError")
        self.assertEqual(diagnostic["native_pair_calls"], 6)

    def test_unused_pair_nan_statistic_does_not_erase_selected_value(self):
        calls = []
        def one_nan(pair):
            calls.append(True)
            return np.full((1000, 1), np.nan if len(calls) == 6 else 2.)
        value, diagnostic = P.feature(generated_matrix(), dba=one_nan)
        self.assertEqual(value, 4.)
        self.assertEqual(diagnostic["status"], "finite")
        self.assertEqual(diagnostic["native_pair_calls"], 6)
        self.assertTrue(diagnostic["warnings"])

    def test_selected_nan_statistic_is_explicit_numerical_failure(self):
        calls = []
        def selected_nan(pair):
            calls.append(True)
            return np.full((1000, 1), np.nan if len(calls) == 2 else 2.)
        value, diagnostic = P.feature(generated_matrix(), dba=selected_nan)
        self.assertIsNone(value)
        self.assertEqual(diagnostic["status"], "source_SPI_failure")
        self.assertEqual(diagnostic["native_pair_calls"], 6)

    def test_constant_unused_roi_aborts_data_loading_before_any_solver(self):
        values = generated_matrix()
        values[1] = 7
        def unreachable(pair):
            raise AssertionError("solver reached after invalid Data load")
        with self.assertRaisesRegex(I.InputError, "standardization failed"):
            P.feature(values, dba=unreachable)

    def test_nonfinite_input_and_invalid_layout_abort_before_solver(self):
        bad = generated_matrix()
        bad[3, 17] = np.nan
        for values in (bad, generated_matrix()[:2], np.ones((4, 2)), np.ones((4, 10), dtype=bool)):
            with self.subTest(shape=values.shape), self.assertRaises(I.InputError):
                P.feature(values, dba=lambda pair: self.fail("solver reached invalid input"))

    def test_missing_native_backend_fails_without_fallback(self):
        with patch.object(P.importlib.metadata, "version", side_effect=importlib.metadata.PackageNotFoundError("tslearn")):
            with self.assertRaisesRegex(RuntimeError, "existing tslearn==0.6.3"):
                P.native_dba()
            with self.assertRaises(RuntimeError):
                P.feature(generated_matrix())

    def test_native_version_is_exact_and_import_route_returns_requested_solver(self):
        marker = lambda pair: pair
        package = types.ModuleType("tslearn")
        barycenters = types.ModuleType("tslearn.barycenters")
        barycenters.dtw_barycenter_averaging = marker
        package.barycenters = barycenters
        with patch.dict(sys.modules, {"tslearn": package, "tslearn.barycenters": barycenters}):
            with patch.object(P.importlib.metadata, "version", return_value="0.6.4"):
                with self.assertRaisesRegex(RuntimeError, "found 0.6.4"):
                    P.native_dba()
            with patch.object(P.importlib.metadata, "version", return_value="0.6.3") as version:
                self.assertIs(P.native_dba(), marker)
                version.assert_called_once_with("tslearn")


class PreparedAllocationControls(unittest.TestCase):
    def _record(self, root, name, header, payload=b""):
        path = root / name
        with path.open("wb") as stream:
            np.lib.format.write_array_header_1_0(stream, header)
            stream.write(payload)
        return {"file": name, "pin": I.pin_file(path, 130000)}

    def test_huge_declared_array_is_refused_before_np_load(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            record = self._record(root, "huge.npy", {"descr": "<f8", "fortran_order": False,
                                                     "shape": (4, 4, 10**12)})
            with patch.object(I.np, "load", side_effect=AssertionError("allocation was reached")):
                with self.assertRaisesRegex(I.InputError, "header shape/dtype/order"):
                    I.load_prepared(root, record)

    def test_short_payload_is_refused_before_np_load(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            record = self._record(root, "short.npy", {"descr": "<f8", "fortran_order": False,
                                                      "shape": (4, 4, 1000)}, b"\0"*8)
            with patch.object(I.np, "load", side_effect=AssertionError("allocation was reached")):
                with self.assertRaisesRegex(I.InputError, "payload extent"):
                    I.load_prepared(root, record)

    def test_exact_generated_prepared_array_round_trips(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "valid.npy"
            values = np.arange(16000, dtype="<f8").reshape(4, 4, 1000)
            with path.open("wb") as stream:
                np.save(stream, values, allow_pickle=False)
            record = {"file": path.name, "pin": I.pin_file(path, 130000)}
            np.testing.assert_array_equal(I.load_prepared(root, record), values)


if __name__ == "__main__":
    unittest.main()
