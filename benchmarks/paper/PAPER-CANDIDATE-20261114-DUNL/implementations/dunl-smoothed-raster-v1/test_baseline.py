"""Generated implementation controls; no authentic neural observations."""
import copy
import hashlib
import math
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import baseline as b


def panel():
    h = b.endpoint()
    target = [0] * h.CODE_SAMPLES
    for index in h.SCHEDULE:
        target[index] = 1
    owner = {"profile": h.PROFILE, "channel_ids": [f"allocation_{i}" for i in range(11)],
             "trial_ids": {s: [f"{s}_{i}" for i in range(n)] for s, n in h.SPLITS.items()},
             "target_codes": {s: [[target.copy()] for _ in range(n)] for s, n in h.SPLITS.items()}}
    observed = {"profile": h.PROFILE, "context_id": h.context_id(owner),
                "channel_ids": owner["channel_ids"].copy(),
                "trial_ids": copy.deepcopy(owner["trial_ids"]),
                "observations": {s: [[[([0] * 600)] for _ in range(11)] for _ in range(n)]
                                 for s, n in h.SPLITS.items()}}
    return owner, observed


class RasterControls(unittest.TestCase):
    def test_odd_kernel_support_normalization_and_non_symmetric_orientation(self):
        self.assertEqual([len(b.smoothing_kernel(t)) for t in b.TAUS], [3, 27, 51, 77])
        for tau in b.TAUS:
            kernel = b.smoothing_kernel(tau)
            self.assertAlmostEqual(math.fsum(kernel), 1.0)
            self.assertEqual(kernel[0], 0)
            self.assertGreater(kernel[-1], 0)
        x = [0] * 600
        x[100] = 1
        smooth = b.smooth(x, 1)
        kernel = b.smoothing_kernel(1)
        self.assertEqual(smooth[99:102], list(kernel))
        self.assertEqual(sum(smooth[:99]) + sum(smooth[102:]), 0)

    def test_zero_padding_does_not_wrap_or_renormalize_edges(self):
        x = [0] * 600
        x[0] = 1
        result = b.smooth(x, 1)
        kernel = b.smoothing_kernel(1)
        self.assertEqual(result[:2], list(kernel[1:]))
        self.assertTrue(all(v == 0 for v in result[2:]))
        x = [0] * 600
        x[-1] = 1
        result = b.smooth(x, 1)
        self.assertEqual(result[-2:], list(kernel[:2]))
        self.assertLess(math.fsum(result), 1)

    def test_plateau_midpoint_down_and_inclusive_height(self):
        self.assertEqual(b.peak_indices([0, .2, .2, 0, .3, .3, .3, 0], .2), (1, 5))
        self.assertEqual(b.peak_indices([0, .2, 0], .2), (1,))
        self.assertEqual(b.peak_indices([0, .2, 0], .2000000001), ())

    def test_endpoint_plateaus_and_monotonic_signals_are_not_peaks(self):
        for values in ([.5, .5, 0, .5, .5], [0, .1, .2, .3], [.3, .2, .1, 0], [0, 0, 0]):
            self.assertEqual(b.peak_indices(values, 0), ())

    def test_peak_finding_before_truncation_preserves_boundary_peak(self):
        values = [0] * 600
        values[575] = .3
        self.assertEqual(b.cropped_peaks(values, .3), {575})
        self.assertEqual(b.peak_indices(values[:576], .3), ())
        values[575:578] = [.3, .3, .3]
        self.assertEqual(b.cropped_peaks(values, .3), set())  # midpoint576 is outside
        with self.assertRaises(b.Refusal):
            b.cropped_peaks(values[:576], .3)

    def test_full_grid_both_splits_and_all_allocated_channels(self):
        owner, observed = panel()
        report = b.curves(owner, observed)
        self.assertEqual(set(report["splits"]), {"train", "test"})
        self.assertIsNone(report["selected_setting"])
        self.assertNotIn("overall", report)
        self.assertFalse(report["scientific_qualification"])
        self.assertEqual((len(b.THRESHOLDS), b.THRESHOLDS[0], b.THRESHOLDS[-1]), (20, .025, .3))
        for split, count in (("train", 330), ("test", 220)):
            split_result = report["splits"][split]
            self.assertEqual(split_result["rows"], count)
            self.assertEqual([c["smoothing_tau"] for c in split_result["curves"]], list(b.TAUS))
            for curve in split_result["curves"]:
                self.assertEqual(len(curve["points"]), 20)
                for point in curve["points"]:
                    self.assertEqual(point["rows"], count)
                    self.assertEqual((point["missed_event_fraction"], point["false_event_fraction"]), (1, 1))

    def test_no_group_norm_on_raster_comparator_and_row_mean_not_pooling(self):
        owner, observed = panel()
        observed["observations"]["test"][0][0][0][100] = 1
        h, rows = b._owner_and_rasters(owner, observed)
        self.assertEqual(sum(any(x) for _, x in rows["test"]), 1)
        with mock.patch.object(b, "smooth", side_effect=lambda values, tau: values), \
                mock.patch.object(b, "TAUS", (1,)), mock.patch.object(b, "THRESHOLDS", (.3,)):
            point = b.curves(owner, observed)["splits"]["test"]["curves"][0]["points"][0]
        self.assertEqual(point["mean_hit_exact"], [1, 3520])
        self.assertEqual(point["mean_false_exact"], [219, 220])

    def test_geometry_and_identity_refusals_before_smoothing(self):
        mutations = (
            lambda x: x["observations"]["train"].pop(),
            lambda x: x["observations"]["test"][0].pop(),
            lambda x: x["observations"]["test"][0][0][0].pop(),
            lambda x: x["channel_ids"].reverse(),
            lambda x: x.update(context_id="0" * 64),
        )
        for mutate in mutations:
            owner, observed = panel()
            mutate(observed)
            with mock.patch.object(b, "smooth", side_effect=AssertionError("must reject before calculation")):
                with self.assertRaises(b.Refusal):
                    b.curves(owner, observed)

    def test_future_role_overlap_and_boolean_nonfinite_observations_refused(self):
        owner, observed = panel()
        owner["trial_ids"]["test"][0] = owner["trial_ids"]["train"][0]
        with self.assertRaises(b.Refusal):
            b.curves(owner, observed)
        for value in (True, float("nan"), float("inf"), -1, 2):
            x = [0] * 600
            x[30] = value
            with self.assertRaises(b.Refusal):
                b.smooth(x, 1)

    def test_endpoint_binding_and_target_independent_context(self):
        h = b.endpoint()
        self.assertEqual(hashlib.sha256(Path(h.__file__).read_bytes()).hexdigest(), b.ENDPOINT_SHA256)
        owner, observed = panel()
        context = observed["context_id"]
        owner["target_codes"]["test"][0][0][100] = 0
        self.assertEqual(h.context_id(owner), context)
        with mock.patch.object(b, "ENDPOINT_SHA256", "0" * 64):
            b.endpoint.cache_clear()
            with self.assertRaises(b.Refusal):
                b.endpoint()
        b.endpoint.cache_clear()

    def test_value_digests_bind_inputs_without_changing_public_context(self):
        owner, observed = panel()
        with mock.patch.object(b, "TAUS", (1,)), mock.patch.object(b, "THRESHOLDS", (.3,)):
            first = b.curves(owner, observed)
            observed["observations"]["test"][0][0][0][100] = 1
            changed_observation = b.curves(owner, observed)
            owner["target_codes"]["test"][0][0][100] = 0
            changed_target = b.curves(owner, observed)
        self.assertEqual(first["context_id"], changed_target["context_id"])
        self.assertNotEqual(first["raster_content_sha256"], changed_observation["raster_content_sha256"])
        self.assertEqual(first["owner_content_sha256"], changed_observation["owner_content_sha256"])
        self.assertNotEqual(changed_observation["owner_content_sha256"], changed_target["owner_content_sha256"])
        self.assertEqual(changed_observation["raster_content_sha256"], changed_target["raster_content_sha256"])


if __name__ == "__main__":
    unittest.main()
