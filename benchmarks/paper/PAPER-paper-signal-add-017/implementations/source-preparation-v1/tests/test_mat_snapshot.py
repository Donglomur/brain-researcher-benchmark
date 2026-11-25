"""Generated MAT descriptor-stability controls; no authentic recording."""
import hashlib
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from scipy.io import savemat

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import source_preparation as p

MEMBER = "S01/OnlineImagery_Sess01_2class_Base/S01_OnlineImagery_Sess01_2class_Base_R01.mat"


def mat_bytes(value):
    data = np.zeros((128, 2048), dtype=np.uint8)
    data[0, :] = value
    events = np.empty((1, 4), dtype=[("type", "O"), ("sample", "O"), ("value", "O")])
    for index, event in enumerate((("Target", 1.0, 1.0), ("TrialEnd", 1025.0, 0.0),
                                   ("Target", 1025.0, 4.0), ("TrialEnd", 2049.0, 0.0))):
        events[0, index] = event
    output = io.BytesIO()
    savemat(output, {"eeg": {"data": data, "fsample": 1024.0, "nChans": 128.0,
                             "nSamples": 2048.0}, "event": events}, do_compression=True)
    return output.getvalue()


def replace_contents(path, payload):
    before = path.stat()
    path.write_bytes(payload)
    # Make the metadata change deterministic even on coarser timestamp stores.
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns + 1_000_000_000))


class MatSnapshotTests(unittest.TestCase):
    def test_unchanged_pinned_mat_preserves_complete_trials_and_car(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.mat"
            original = mat_bytes(1)
            path.write_bytes(original)
            trials = p.read_mat(path, MEMBER, hashlib.sha256(original).hexdigest(), {"1": 1, "4": 1})
            self.assertEqual([t.source_label for t in trials], [1, 4])
            self.assertEqual([t.start_sample_zero_based for t in trials], [0, 1024])
            self.assertTrue(all(t.eeg.shape == (128, 1024) for t in trials))
            for trial in trials:
                np.testing.assert_array_equal(trial.eeg[0], np.full(1024, 127 / 128))
                np.testing.assert_array_equal(trial.eeg[1:], np.full((127, 1024), -1 / 128))

    def test_mutation_between_hash_and_decode_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.mat"
            original, changed = mat_bytes(1), mat_bytes(2)
            path.write_bytes(original)
            actual_loadmat = p.loadmat
            def changed_decode(handle, **kwargs):
                replace_contents(path, changed)
                return actual_loadmat(handle, **kwargs)
            with patch.object(p, "loadmat", side_effect=changed_decode):
                with self.assertRaisesRegex(ValueError, "source MAT changed"):
                    p.read_mat(path, MEMBER, hashlib.sha256(original).hexdigest(), {"1": 1, "4": 1})

    def test_mutation_during_decode_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.mat"
            original, changed = mat_bytes(1), mat_bytes(2)
            path.write_bytes(original)
            actual_loadmat = p.loadmat
            def changed_decode(handle, **kwargs):
                decoded = actual_loadmat(handle, **kwargs)
                replace_contents(path, changed)
                return decoded
            with patch.object(p, "loadmat", side_effect=changed_decode):
                with self.assertRaisesRegex(ValueError, "source MAT changed"):
                    p.read_mat(path, MEMBER, hashlib.sha256(original).hexdigest(), {"1": 1, "4": 1})

    def test_wrong_content_pin_still_refuses_before_decode(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.mat"
            path.write_bytes(mat_bytes(1))
            with patch.object(p, "loadmat") as decode:
                with self.assertRaisesRegex(ValueError, "checksum"):
                    p.read_mat(path, MEMBER, "0" * 64, {"1": 1, "4": 1})
                decode.assert_not_called()


if __name__ == "__main__":
    unittest.main()
