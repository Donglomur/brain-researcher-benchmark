"""Generated finite-average controls; no real data, model or scientific score."""
from fractions import Fraction
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import score
from numerical_core import _mean


def exact_mean(values):
    return float(sum(Fraction.from_float(float(v)) for v in values) / len(values))


class SubnormalMeanControls(unittest.TestCase):
    def test_complete_panel_retains_positive_representable_raw_error(self):
        # Squared residuals alternate one/four minimum positive float64 units.
        # Their exact float-input mean is representable, unlike each /102 term.
        small = float.fromhex("0x1p-537")
        column = np.tile(np.array([small, 2 * small]), 51)[:, None]
        squared = np.square(column[:, 0])
        self.assertTrue(np.all(squared > 0))
        expected = exact_mean(squared)
        self.assertGreater(expected, 0)
        truth = {s: {r: column.copy() for r in score.ROIS} for s in score.SUBJECTS}
        prediction = {s: {r: np.zeros_like(column) for r in score.ROIS} for s in score.SUBJECTS}
        result = score.score_arrays(truth, prediction)
        self.assertEqual(result["panel"], {"participants": 10, "rois_per_participant": 8, "videos": 102})
        self.assertEqual(result["primary"]["value"], 0)
        self.assertEqual(result["raw_mse"]["value"], expected)
        for person in result["participants"].values():
            for cell in person["raw_mse_by_roi"].values():
                self.assertEqual(cell, {"status": "defined", "value": expected})

    def test_subnormal_and_cancellation_means_match_exact_float_inputs(self):
        unit = float.fromhex("0x0.0000000000001p-1022")
        for values in ([unit, 2 * unit], [unit, 4 * unit, 0],
                       [unit, -unit], [unit, 0], [unit] * 8):
            with self.subTest(values=values):
                self.assertEqual(_mean(values), exact_mean(values))

    def test_normal_reduction_order_and_extreme_convex_mean_remain(self):
        values = [1.1, 0.03, -0.7, 10.5, 0.0001]
        self.assertEqual(_mean(values), math.fsum(v / len(values) for v in values))
        largest = sys.float_info.max
        large_values = [largest, largest, math.nextafter(largest, 0)]
        self.assertEqual(_mean(large_values), exact_mean(large_values))
        column = np.arange(102, dtype=float)[:, None]
        truth = {s: {r: column.copy() for r in score.ROIS} for s in score.SUBJECTS}
        prediction = {s: {r: column + 1 for r in score.ROIS} for s in score.SUBJECTS}
        result = score.score_arrays(truth, prediction)
        self.assertEqual(result["raw_mse"]["value"], 1.0)
        self.assertAlmostEqual(result["primary"]["value"], 1.0)


if __name__ == "__main__":
    unittest.main()
