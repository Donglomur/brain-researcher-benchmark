"""Generated software controls only; no recorded neurons or model execution."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np
from scipy.ndimage import gaussian_filter

SPEC = importlib.util.spec_from_file_location("gcamp8_metrics", Path(__file__).with_name("metrics.py"))
metrics = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(metrics)


class RateMetricsTests(unittest.TestCase):
    def score(self, prediction, target, **kwargs):
        base = dict(valid_mask=np.ones(len(target), dtype=bool), sampling_rate_hz=30., smoothing_seconds=.05)
        base.update(kwargs)
        return metrics.score_rates(prediction, target, **base)

    def test_author_demo_parity_including_noncontiguous_mask(self):
        target = np.array([0., 3., 0., 1., 0., 2., 0., 4., 0.])
        pred = np.array([1., 0., 2., 1., 4., 0., 3., 1., 0.])
        mask = np.array([False, True, True, False, True, True, True, True, False])
        got = self.score(pred, target, valid_mask=mask)
        y, p = target[mask], pred[mask]
        # Independent source-demo expression, gaussian_filter rather than the
        # implementation's gaussian_filter1d; ground truth is already prepared.
        ys, ps = gaussian_filter(y, sigma=1.5), gaussian_filter(p, sigma=1.5)
        self.assertAlmostEqual(got["pearson"], np.corrcoef(y, p)[0, 1], places=14)
        self.assertAlmostEqual(got["smoothed_normalized_absolute_error"], np.abs(ps-ys).sum()/ys.sum(), places=14)
        self.assertAlmostEqual(got["smoothed_normalized_bias"], (ps-ys).sum()/ys.sum(), places=14)

    def test_error_requires_author_extra_smoothing(self):
        target, pred = np.array([0., 1., 0., 1., 0.]), np.array([1., 0., 1., 0., 1.])
        got = self.score(pred, target)
        self.assertLess(got["smoothed_normalized_absolute_error"], np.abs(pred-target).sum()/target.sum())
        self.assertAlmostEqual(got["pearson"], -1.)

    def test_positive_affine_prediction_preserves_primary_not_bias(self):
        target = np.array([0., 2., 0., 1., 3.])
        got = self.score(3*target+1, target)
        self.assertAlmostEqual(got["pearson"], 1.)
        self.assertAlmostEqual(got["smoothed_normalized_bias"], 2+len(target)/target.sum())

    def test_condition_units_and_reflect_boundaries(self):
        target = np.array([1., 0., 0., 0., 2.])
        pred = target[::-1]
        a = self.score(pred, target)
        b = self.score(pred, target, sampling_rate_hz=60., smoothing_seconds=.025)
        self.assertEqual(a["smoothed_normalized_absolute_error"], b["smoothed_normalized_absolute_error"])
        # A constant offset survives the reflect filter at both edges.
        got = self.score(target+2, target)
        self.assertAlmostEqual(got["smoothed_normalized_bias"], 10/3)

    def test_nonfinite_prediction_cannot_remove_samples(self):
        with self.assertRaisesRegex(ValueError, "nonfinite"):
            self.score([0., np.nan, 1.], [0., 1., 2.])
        got = self.score([np.nan, 1., 2.], [np.nan, 1., 2.], valid_mask=np.array([False, True, True]))
        self.assertAlmostEqual(got["pearson"], 1.)
        self.assertEqual(got["samples_scored"], 2)

    def test_undefined_cases_are_not_dropped_or_zero_filled(self):
        a = self.score([1., 2.], [0., 0.])
        self.assertIsNone(a["pearson"])
        self.assertEqual(a["pearson_reason"], "constant_target")
        self.assertIsNone(a["smoothed_normalized_absolute_error"])
        self.assertEqual(a["normalization_reason"], "zero_target_sum")
        b = self.score([1., 1.], [0., 1.])
        self.assertEqual(b["pearson_reason"], "constant_prediction")
        self.assertEqual(self.score([2.], [1.])["pearson_reason"], "fewer_than_two_samples")
        self.assertEqual(self.score([], [])["pearson_reason"], "no_valid_samples")

    def test_bad_inputs_rejected(self):
        for kwargs in ({"valid_mask": np.array([1, 1])}, {"valid_mask": np.array([True])},
                       {"sampling_rate_hz": True}, {"sampling_rate_hz": float("inf")},
                       {"smoothing_seconds": 0}, {"smoothing_seconds": -1}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.score([1., 2.], [0., 1.], **kwargs)
        for pred, target in (([[1, 2]], [[1, 2]]), ([1j, 2j], [0, 1]), ([1, 2], [-1, 1])):
            with self.subTest(pred=pred), self.assertRaises(ValueError):
                self.score(pred, target)

    def test_pair_uses_same_support_without_lag_optimization(self):
        target = np.array([0., 1., 0., 3., 0.])
        got = metrics.compare_rates(target, np.roll(target, 1), target,
            valid_mask=np.ones(5, dtype=bool), sampling_rate_hz=30., smoothing_seconds=.05)
        self.assertAlmostEqual(got["candidate"]["pearson"], 1.)
        self.assertGreater(got["candidate_minus_author"]["pearson"], 1.)
        self.assertEqual(got["candidate"]["support_sha256"], got["author"]["support_sha256"])
        json.dumps(got, allow_nan=False)

    def test_cli_generated_packet_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            np.savez(root/"input.npz", prediction=[0., 1., 2.], target=[0., 1., 2.], valid_mask=[True]*3)
            command = [sys.executable, "-I", "-B", str(Path(__file__).with_name("metrics.py")),
                       "--input", str(root/"input.npz"), "--output", str(root/"score.json"),
                       "--sampling-rate-hz", "30", "--smoothing-seconds", "0.05"]
            subprocess.run(command, check=True, capture_output=True)
            result = json.loads((root/"score.json").read_text())
            self.assertEqual(result["pearson"], 1.)
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
