"""Focused generated controls for finite paired rate differences."""
import importlib.util
import json
import math
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location("paired_rate_metrics_v2", Path(__file__).with_name("metrics.py"))
metrics = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(metrics)

class PairedRateDifferenceBounds(unittest.TestCase):
    def test_opposite_finite_biases_cannot_produce_infinite_delta(self):
        kwargs = dict(valid_mask=[True], sampling_rate_hz=30.0, smoothing_seconds=.05)
        # Moderate rates keep filtering finite; target normalization produces
        # opposite finite biases near +/-1e308 before the paired subtraction.
        candidate = metrics.score_rates([1e154], [1e-154], **kwargs)
        author = metrics.score_rates([-1e154], [1e-154], **kwargs)
        self.assertTrue(math.isfinite(candidate["smoothed_normalized_bias"]))
        self.assertTrue(math.isfinite(author["smoothed_normalized_bias"]))
        self.assertTrue(math.isinf(candidate["smoothed_normalized_bias"]
                                   - author["smoothed_normalized_bias"]))
        with self.assertRaisesRegex(ValueError, "nonfinite paired metric difference"):
            metrics.compare_rates([1e154], [-1e154], [1e-154], **kwargs)

    def test_finite_and_undefined_paired_results_are_preserved(self):
        kwargs = dict(valid_mask=[True], sampling_rate_hz=30.0, smoothing_seconds=.05)
        result = metrics.compare_rates([3.0], [-1.0], [1.0], **kwargs)
        delta = result["candidate_minus_author"]
        self.assertIsNone(delta["pearson"])
        self.assertAlmostEqual(delta["smoothed_normalized_absolute_error"], 0.0)
        self.assertAlmostEqual(delta["smoothed_normalized_bias"], 4.0)
        json.dumps(result, allow_nan=False)
        undefined = metrics.compare_rates([1.0], [2.0], [0.0], **kwargs)
        self.assertEqual(undefined["candidate_minus_author"], {
            "pearson": None, "smoothed_normalized_absolute_error": None,
            "smoothed_normalized_bias": None})
        json.dumps(undefined, allow_nan=False)

if __name__ == "__main__":
    unittest.main(verbosity=2)
