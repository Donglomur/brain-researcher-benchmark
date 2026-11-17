"""Required real-tslearn numerical seam; generated signals, never source data.

This separate hosted-CI command requires its locked native environment. Missing
or mismatched tslearn is an error, never a skip or an analytical replacement.
The ordinary 40 construction controls deliberately remain dependency-light.
"""
from __future__ import annotations

import importlib.metadata
import importlib.util
import math
from pathlib import Path
import sys
import unittest

import numpy as np

if importlib.metadata.version("tslearn") != "0.6.3":
    raise RuntimeError("Required native seam needs the locked tslearn==0.6.3 environment")

from tslearn.barycenters import dtw_barycenter_averaging
from tslearn.metrics import dtw

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
SPEC = importlib.util.spec_from_file_location("fc_real_native_producer", HERE / "producer.py")
P = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(P)


def scalar_normalization(row):
    """Independent sample-SD standardization followed by scalar OLS residuals."""
    values = [float(value) for value in row]
    n = len(values)
    mean = math.fsum(values) / n
    sd = math.sqrt(math.fsum((value - mean) ** 2 for value in values) / (n - 1))
    z = [(value - mean) / sd for value in values]
    mean_z = math.fsum(z) / n
    center = (n - 1) / 2
    slope = (math.fsum((t - center) * (value - mean_z) for t, value in enumerate(z)) /
             math.fsum((t - center) ** 2 for t in range(n)))
    return np.asarray([value - mean_z - slope * (t - center) for t, value in enumerate(z)])


def mean_squared_dtw_objective(pair, barycenter):
    return math.fsum(float(dtw(row, barycenter)) ** 2 for row in pair) / len(pair)


class RealPinnedBarycenter(unittest.TestCase):
    def test_original_shape_real_dba_matches_analytic_identical_signal(self):
        q = np.tile(np.asarray([-1., 1., 1., -1.]), 250)
        raw = np.repeat(q[None, :], 4, axis=0)
        self.assertEqual(raw.shape, (4, 1000))
        self.assertIs(P.native_dba(), dtw_barycenter_averaging)
        normalized = P.preprocess(raw)
        expected = q * math.sqrt(999 / 1000)
        np.testing.assert_allclose(normalized, np.repeat(expected[None, :], 4, axis=0),
                                   rtol=2e-12, atol=2e-12)
        # This is the real pinned implementation, with all original defaults.
        direct = dtw_barycenter_averaging(normalized[[2, 0]])
        self.assertEqual(direct.shape, (1000, 1))
        np.testing.assert_allclose(direct[:, 0], expected, rtol=2e-12, atol=2e-12)
        actual, diagnostic = P.feature(raw)  # No dba seam/injection argument.
        self.assertEqual(diagnostic["status"], "finite")
        self.assertEqual(diagnostic["native_pair_calls"], 6)
        self.assertAlmostEqual(actual, 0.999, delta=2e-12)
        self.assertAlmostEqual(actual, float(np.nanmax(direct ** 2)), delta=2e-12)

    def test_real_warped_pulses_match_direct_source_operation_not_mean_proxy(self):
        t = np.arange(1000, dtype=np.float64) / 1000
        # Smooth asymmetric pulses avoid long flat plateaus/path ties. All four
        # original ROI rows and all1000 samples are used by the production path.
        cs = np.exp(-((t - .31) / .052) ** 2) + .21 * np.exp(-((t - .58) / .093) ** 2) + .017 * np.sin(17 * t)
        pfc = np.exp(-((t - .46) / .052) ** 2) + .21 * np.exp(-((t - .73) / .093) ** 2) + .013 * np.sin(19 * t)
        ips = np.sin(9 * t) + .23 * np.cos(23 * t) + .1 * t
        visual = np.exp(-((t - .21) / .08) ** 2) + .4 * np.sin(6 * t)
        # Negative selected pulses make square-before-max distinguishable from
        # the incorrect square(max(barycenter)) statistic as well.
        raw = np.vstack((-cs, ips, -pfc, visual))
        self.assertEqual(raw.shape, (4, 1000))
        self.assertIs(P.native_dba(), dtw_barycenter_averaging)
        normalized = P.preprocess(raw)
        independent = np.vstack([scalar_normalization(row) for row in raw])
        np.testing.assert_allclose(normalized, independent, rtol=2e-12, atol=2e-12)
        pair = normalized[[2, 0]]  # First source cache fill is PFC,CS.
        direct = dtw_barycenter_averaging(pair)
        self.assertEqual(direct.shape, (1000, 1))
        self.assertTrue(bool(np.isfinite(direct).all()))
        direct_value = float(np.nanmax(direct ** 2))
        self.assertGreater(abs(float(np.min(direct))), abs(float(np.max(direct))))
        self.assertGreater(abs(direct_value - float(np.max(direct) ** 2)), 1e-3)
        actual, diagnostic = P.feature(raw)  # Full six-pair source route.
        self.assertEqual(diagnostic["status"], "finite")
        self.assertEqual(diagnostic["native_pair_calls"], 6)
        self.assertAlmostEqual(actual, direct_value, delta=2e-11 * max(1., abs(direct_value)))

        initial = np.mean(pair, axis=0)
        proxy_value = float(np.max(initial ** 2))
        # This validates fixture discrimination; it is not a scientific gain.
        self.assertGreater(abs(direct_value - proxy_value), 1e-3)
        initial_cost = mean_squared_dtw_objective(pair, initial)
        native_cost = mean_squared_dtw_objective(pair, direct[:, 0])
        self.assertLessEqual(native_cost, initial_cost + 1e-9 * max(1., initial_cost))


if __name__ == "__main__":
    unittest.main()
