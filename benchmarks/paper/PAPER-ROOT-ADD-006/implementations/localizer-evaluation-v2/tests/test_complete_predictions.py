"""Complete prediction-panel controls; generated arrays only."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("localizer_complete_panel", ROOT / "localizer_score.py")
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


def full_panel():
    labels = np.repeat(np.arange(1, 8), 60)
    logits = np.zeros((420, 1, 1, 7))
    for trial, label in enumerate(labels):
        logits[trial, 0, 0, (label - 1) % 3] = 1.
    return labels, logits


class CompletePredictionPanels(unittest.TestCase):
    def test_masked_nonfinite_unused_channel_is_rejected(self):
        labels, logits = full_panel()
        logits[-1, 0, 0, 6] = np.nan
        prediction = np.ma.array(logits, mask=False)
        prediction.mask[-1, 0, 0, 6] = True
        with self.assertRaisesRegex(ValueError, "masked prediction"):
            s.score_participant(prediction, labels, [0], [0])

    def test_masked_finite_winning_channel_is_rejected(self):
        labels, logits = full_panel()
        prediction = np.ma.array(logits, mask=False)
        prediction.mask[60, 0, 0, 1] = True
        with self.assertRaisesRegex(ValueError, "masked prediction"):
            s.score_participant(prediction, labels, [0], [0])

    def test_inactive_mask_and_plain_array_preserve_all_outcome_trials(self):
        labels, logits = full_panel()
        plain = s.score_participant(logits, labels, [0], [0])
        unmasked = s.score_participant(np.ma.array(logits, mask=False), labels, [0], [0])
        for key in ("accuracy", "by_class_accuracy", "tied_outcome_trials", "diagonal"):
            np.testing.assert_array_equal(plain[key], unmasked[key])
        np.testing.assert_array_equal(plain["accuracy"], [[1.]])
        np.testing.assert_array_equal(plain["by_class_accuracy"], np.ones((3, 1, 1)))
        np.testing.assert_array_equal(plain["tied_outcome_trials"], [[0]])

    def test_readonly_npy_memory_map_preserves_complete_scoring(self):
        labels, logits = full_panel()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "logits.npy"
            np.save(path, logits, allow_pickle=False)
            mapped = np.load(path, mmap_mode="r", allow_pickle=False)
            self.assertFalse(mapped.flags.writeable)
            result = s.score_participant(mapped, labels, [0], [0])
            np.testing.assert_array_equal(result["accuracy"], [[1.]])
            np.testing.assert_array_equal(result["by_class_accuracy"], np.ones((3, 1, 1)))


if __name__ == "__main__":
    unittest.main()
