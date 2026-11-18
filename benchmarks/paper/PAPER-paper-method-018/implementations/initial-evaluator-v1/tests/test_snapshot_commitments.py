"""Generated-only regression controls for commitments to the consumed snapshot."""
import hashlib
import math
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import numpy as np
from test_evaluator import control_artifacts, e, save_npz


class SnapshotCommitmentTests(unittest.TestCase):
    def test_manifest_receipts_and_scoring_use_captured_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            control_artifacts(root)
            reference, submission = root / "reference.json", root / "submission.json"
            expected_reference = hashlib.sha256(reference.read_bytes()).hexdigest()
            expected_submission = hashlib.sha256(submission.read_bytes()).hexdigest()
            validate = e._validate_reference

            def replace_paths_after_capture(value, base):
                result = validate(value, base)
                reference.write_bytes(b'{"replacement": "not the scored reference"}')
                submission.write_bytes(b'{"replacement": "not the scored submission"}')
                return result

            with mock.patch.object(e, "_validate_reference", replace_paths_after_capture):
                result = e.evaluate(reference, submission)
            self.assertEqual(result["reference_sha256"], expected_reference)
            self.assertEqual(result["submission_sha256"], expected_submission)
            self.assertAlmostEqual(result["primary_value"], 2 * math.log(2) - 1)
            self.assertEqual(len(result["sessions"]), 10)
            self.assertFalse(result["scientifically_qualified"])
            self.assertFalse(result["full_contract_complete"])

    def test_counts_decode_authenticated_snapshot_after_file_replacement(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original = np.array([[[0, 1]], [[2, 3]]], dtype=np.int64)
            record = save_npz(root, "counts.npz", counts=original)
            snapshot = e._artifact(root, record, "counts")
            np.savez(root / "counts.npz", counts=np.full_like(original, 99))
            decoded = e._arrays(snapshot, {"counts"})["counts"]
            np.testing.assert_array_equal(decoded, original)
            self.assertNotEqual(e.file_sha256(root / "counts.npz"), record["sha256"])

    def test_predictions_decode_authenticated_snapshot_after_file_replacement(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original = {"log_rate": np.full((2, 1, 2), math.log(2)),
                        "posterior_mu": np.zeros((2, 1)), "posterior_logvar": np.zeros((2, 1))}
            record = save_npz(root, "predictions.npz", **original)
            snapshot = e._artifact(root, record, "predictions")
            np.savez(root / "predictions.npz", **{key: value + 5 for key, value in original.items()})
            decoded = e._arrays(snapshot, set(original))
            for key in original:
                np.testing.assert_array_equal(decoded[key], original[key])

    def test_replacement_before_capture_fails_digest(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            record = save_npz(root, "counts.npz", counts=np.zeros((1, 1, 1)))
            np.savez(root / "counts.npz", counts=np.ones((1, 1, 1)))
            with self.assertRaisesRegex(e.EvaluationError, "content digest mismatch"):
                e._artifact(root, record, "counts")

    def test_snapshot_parser_still_rejects_duplicate_and_nonfinite_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "manifest.json"
            for data in (b'{"x": 1, "x": 2}', b'{"x": NaN}', b'{"x": Infinity}'):
                path.write_bytes(data)
                with self.subTest(data=data), self.assertRaises(e.EvaluationError):
                    e._json_snapshot(path)


if __name__ == "__main__":
    unittest.main()
