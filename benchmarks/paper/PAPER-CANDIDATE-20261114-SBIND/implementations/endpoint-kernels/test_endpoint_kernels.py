"""Generated arithmetic and identity controls, never authentic data/model runs."""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from endpoint_kernels import (MetricError, wfci1_behavior_mse, neural_mse,
                              wfci2_behavior_f1, fus_trial_accuracy)


CHANNELS = tuple(f"channel-{i}" for i in range(14))
BINARY_CHANNELS = ("left-hand", "right-hand", "left-lick", "right-lick")


def logits(labels, width=2):
    return tuple(tuple(1.0 if j == label else 0.0 for j in range(width)) for label in labels)


class EndpointTests(unittest.TestCase):
    def test_continuous_mse_uses_every_frame_and_keeps_all_fourteen_outputs(self):
        # Errors for channel j are j and j+2, giving j*j+2*j+2.
        truth = [("first", (0,) * 14), ("last", (0,) * 14)]
        pred = [("last", tuple(j + 2 for j in range(14))),
                ("first", tuple(range(14)))]
        result = wfci1_behavior_mse(("first", "last"), truth, pred, channel_ids=CHANNELS)
        self.assertEqual(result.n_samples, 2)
        self.assertEqual(result.output_ids, CHANNELS)
        for j, actual in enumerate(result.values):
            self.assertAlmostEqual(actual, j * j + 2 * j + 2)
        reverse = wfci1_behavior_mse(("first", "last"), truth, pred[::-1], channel_ids=CHANNELS)
        self.assertEqual(result, reverse)

    def test_pixel_mask_is_explicit_and_full_field_remains_required(self):
        zeros = (0,) * 16384
        pred = list(zeros)
        pred[0], pred[127], pred[16383] = 3, 4, 12
        result = neural_mse(("frame",), [("frame", zeros)], [("frame", pred)],
                            brain_pixel_indices=(16383, 0))
        self.assertEqual(result.output_ids, ("pixel:16383", "pixel:0"))
        self.assertEqual(result.values, (144, 9))
        complete = neural_mse(("frame",), [("frame", zeros)], [("frame", pred)],
                               brain_pixel_indices=tuple(range(16384)))
        self.assertEqual(len(complete.values), 16384)
        self.assertEqual(sum(complete.values), 169)
        for bad in ((), (0, 0), (-1,), (16384,), (True,)):
            with self.subTest(mask=bad), self.assertRaises(MetricError):
                neural_mse(("frame",), [("frame", zeros)], [("frame", pred)],
                           brain_pixel_indices=bad)
        with self.assertRaises(MetricError):
            neural_mse(("frame",), [("frame", zeros[:4])], [("frame", pred[:4])],
                       brain_pixel_indices=(0,))

    def test_f1_hand_counted_not_accuracy_or_micro_average(self):
        truth = [("a", (1, 0, 0, 1)), ("b", (1, 0, 0, 0)),
                 ("c", (1, 0, 0, 0)), ("d", (0, 0, 1, 0))]
        pred = [("a", logits((1, 0, 1, 1))), ("b", logits((0, 0, 0, 1))),
                ("c", logits((0, 0, 0, 0))), ("d", logits((0, 0, 1, 0)))]
        result = wfci2_behavior_f1(("a", "b", "c", "d"), truth, pred,
                                   channel_ids=BINARY_CHANNELS)
        self.assertEqual(result.confusion, ((1, 0, 2), (0, 0, 0), (1, 1, 0), (1, 1, 0)))
        self.assertEqual(result.values, (0.5, 0.0, 2 / 3, 2 / 3))
        self.assertEqual(result.n_samples, 4)

    def test_argmax_tie_uses_first_class_and_binary_width_is_fixed(self):
        truth = [("a", (1, 1, 1, 1))]
        result = wfci2_behavior_f1(("a",), truth, [("a", ((0.5, 0.5),) * 4)],
                                   channel_ids=BINARY_CHANNELS)
        self.assertEqual(result.values, (0, 0, 0, 0))
        with self.assertRaises(MetricError):
            wfci2_behavior_f1(("a",), truth, [("a", ((1, 2, 3),) * 4)],
                              channel_ids=BINARY_CHANNELS)

    def test_fus_counts_trials_once_and_requires_final_state(self):
        truth = [("trial-1", (29, 0)), ("trial-2", (29, 1)), ("trial-3", (29, 1))]
        pred = [("trial-3", (29, (0, 1))), ("trial-1", (29, (1, 0))),
                ("trial-2", (29, (1, 0)))]
        result = fus_trial_accuracy(("trial-1", "trial-2", "trial-3"), truth, pred, directions=2)
        self.assertEqual(result.values, (2 / 3,))
        self.assertEqual(result.n_samples, 3)
        with self.assertRaises(MetricError):
            fus_trial_accuracy(("trial-1",), [("trial-1", (28, 0))],
                                [("trial-1", (28, (1, 0)))], directions=2)
        with self.assertRaises(MetricError):
            fus_trial_accuracy(("trial-1",), [("trial-1", (29, 2))],
                                [("trial-1", (29, (1, 0)))], directions=2)

    def test_eight_direction_uses_one_complete_label_not_axis_accuracy(self):
        result = fus_trial_accuracy(("x", "y"), [("x", (29, 7)), ("y", (29, 6))],
                                    [("x", (29, logits((7,), 8)[0])),
                                     ("y", (29, logits((7,), 8)[0]))], directions=8)
        self.assertEqual(result.values, (0.5,))
        with self.assertRaises(MetricError):
            fus_trial_accuracy(("x",), [("x", (29, 7))],
                                [("x", (29, logits((1,), 2)[0]))], directions=8)

    def test_missing_extra_duplicate_rows_and_support_are_not_silently_dropped(self):
        rows = [("a", (0,) * 14), ("b", (0,) * 14)]
        for support, pred in ((("a", "b"), rows[:1]), (("a",), rows),
                              (("a", "b"), rows + rows[:1]), (("a", "a"), rows),
                              ((), [])):
            with self.subTest(support=support, count=len(pred)), self.assertRaises(MetricError):
                wfci1_behavior_mse(support, rows, pred, channel_ids=CHANNELS)
        with self.assertRaises(MetricError):
            wfci1_behavior_mse(("a", "b"), rows + rows[:1], rows, channel_ids=CHANNELS)

    def test_nonfinite_or_malformed_operands_fail_including_masked_pixels(self):
        for value in (float("nan"), float("inf"), True, "0"):
            with self.subTest(value=value), self.assertRaises(MetricError):
                wfci1_behavior_mse(("a",), [("a", (0,) * 14)],
                                    [("a", (value,) * 14)], channel_ids=CHANNELS)
        bad_field = [0] * 16384
        bad_field[-1] = float("nan")
        with self.assertRaises(MetricError):
            neural_mse(("a",), [("a", (0,) * 16384)], [("a", bad_field)],
                       brain_pixel_indices=(0,))
        with self.assertRaises(MetricError):
            wfci1_behavior_mse(("a",), [("a", (-1e308,) * 14)],
                                [("a", (1e308,) * 14)], channel_ids=CHANNELS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
