"""Generated participant preflight controls; no source responses or h5py."""
import copy
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

import evaluate as ev
import submission as sub


class SubmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name).resolve()
        cls.predictions = cls.root / "predictions"
        cls.predictions.mkdir()
        panel = {"schema": "neural039_movie10_panel_v1", "source_commit": ev.SOURCE_COMMIT,
                 "subjects": {}}
        for subject in ev.SUBJECTS:
            panel["subjects"][subject] = {
                "file": f"{subject}_movie10.h5", "bytes": 1, "sha256": "0" * 64,
                "datasets": {
                    "ses-001_task-bourne1": [16, 1000],
                    "ses-002_task-figures1_run-1": [16, 1000],
                    "ses-003_task-figures1_run-2": [16, 1000],
                    "ses-004_task-life1_run-1": [16, 1000],
                    "ses-005_task-life1_run-2": [16, 1000],
                    "ses-006_task-wolf1": [16, 1000],
                },
            }
        cls.queries = ev.queries(ev.validate_panel(panel))
        cls.query_path = cls.root / "queries.json"
        cls.query_bytes = ev.canonical(cls.queries)
        cls.query_path.write_bytes(cls.query_bytes)
        cls.query_hash = ev.digest(cls.query_bytes)
        cls.array_bytes = {}
        cls.fixture_bytes_written = len(cls.query_bytes)
        for case_id, query in cls.queries.items():
            folder = cls.predictions / case_id
            folder.mkdir()
            rows, columns = query["shape"]
            data = np.arange(rows * columns, dtype="<f4").reshape(rows, columns)
            stream = io.BytesIO()
            np.save(stream, data, allow_pickle=False)
            cls.array_bytes[case_id] = stream.getvalue()
            (folder / "predictions.npy").write_bytes(cls.array_bytes[case_id])
            meta = ev.canonical({"schema": "neural039_prediction_v2", "case_id": case_id,
                                 "query_sha256": ev.digest(ev.canonical(query))})
            (folder / "submission.json").write_bytes(meta)
            cls.fixture_bytes_written += len(meta) + len(cls.array_bytes[case_id])

    @classmethod
    def tearDownClass(cls):
        print(f"generated_fixture_bytes_written={cls.fixture_bytes_written}")
        cls.temp.cleanup()

    def test_full_public_preflight_preserves_original_admission(self):
        # All inputs are public metadata and generated candidate predictions.
        result = sub.preflight(self.query_path, self.query_hash, self.predictions, np)
        self.assertEqual(result["status"], "valid_predictions")
        self.assertEqual(result["cases"], 16)
        self.assertEqual(result["target_file_opens"], 0)
        self.assertIsNone(result["primary_score"])
        self.assertFalse(result["source_authenticity_verified"])
        self.assertFalse(result["runtime_or_training_provenance_verified"])
        self.assertEqual(set(result["prediction_pins"]), set(ev.CASES))
        for case_id, body in self.array_bytes.items():
            self.assertEqual(result["prediction_pins"][case_id],
                             {"bytes": len(body), "sha256": ev.digest(body)})

    def test_query_hash_checked_before_prediction_admission(self):
        with patch.object(ev, "admit", side_effect=AssertionError("Predictions opened")):
            with self.assertRaisesRegex(ValueError, "query digest"):
                sub.preflight(self.query_path, "f" * 64, self.predictions, np)

    def test_complete_case_roster_and_fixed_identity(self):
        query = copy.deepcopy(self.queries)
        del query[ev.CASES[-1]]
        with self.assertRaises(ValueError):
            sub.validate_queries(query)
        for field, value in (("condition", "historical_v1"), ("subject", "sub-99"),
                             ("tr_seconds", 1.5), ("dtype", "<f8"),
                             ("source_commit", "0" * 40), ("parcel_order", "sorted")):
            with self.subTest(field=field):
                query = copy.deepcopy(self.queries)
                query[ev.CASES[0]][field] = value
                with self.assertRaises(ValueError):
                    sub.validate_queries(query)

    def test_fixed_guards_contiguous_offsets_and_integer_shapes(self):
        for field, value in (("native_samples", True), ("start", 7), ("stop", 12), ("offset", 1)):
            with self.subTest(field=field):
                query = copy.deepcopy(self.queries)
                query[ev.CASES[0]]["runs"][0][field] = value
                with self.assertRaises(ValueError):
                    sub.validate_queries(query)
        for shape in ([True, 1000], [3, 999], [4, 1000]):
            with self.subTest(shape=shape):
                query = copy.deepcopy(self.queries)
                query[ev.CASES[0]]["shape"] = shape
                with self.assertRaises(ValueError):
                    sub.validate_queries(query)

    def test_repeat_viewing_and_native_order_cannot_be_dropped(self):
        case_id = "sub-01_hold-life"
        query = copy.deepcopy(self.queries)
        query[case_id]["runs"].pop()
        query[case_id]["shape"][0] = 3
        with self.assertRaisesRegex(ValueError, "Both original viewings"):
            sub.validate_queries(query)
        query = copy.deepcopy(self.queries)
        query[case_id]["runs"].reverse()
        for index, run in enumerate(query[case_id]["runs"]):
            run["offset"] = index * 3
        with self.assertRaisesRegex(ValueError, "Lexicographic"):
            sub.validate_queries(query)

    def test_film_and_segment_identity_are_not_just_row_counts(self):
        for key in ("ses-999_task-wolf1", "ses-001_task-bourne0", "ses-001_task-bourne1_run-2"):
            with self.subTest(key=key):
                query = copy.deepcopy(self.queries)
                query[ev.CASES[0]]["runs"][0]["key"] = key
                with self.assertRaises(ValueError):
                    sub.validate_queries(query)
        query = copy.deepcopy(self.queries)
        runs = query["sub-01_hold-life"]["runs"]
        runs[1]["key"] = "ses-999_task-life1_run-1"
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            sub.validate_queries(query)

    def test_malformed_public_query_precedes_prediction_reads(self):
        query = copy.deepcopy(self.queries)
        query[ev.CASES[-1]]["runs"] = []
        body = ev.canonical(query)
        with patch.object(ev, "read_bytes", return_value=body), \
                patch.object(ev, "admit", side_effect=AssertionError("Predictions opened")):
            with self.assertRaisesRegex(ValueError, "native run"):
                sub.preflight(self.query_path, ev.digest(body), self.predictions, np)

    def test_invalid_last_array_reuses_original_refusal(self):
        case_id = ev.CASES[-1]
        path = self.predictions / case_id / "predictions.npy"
        malformed = self.array_bytes[case_id] + b"trailing"
        try:
            path.write_bytes(malformed)
            type(self).fixture_bytes_written += len(malformed)
            with self.assertRaisesRegex(ValueError, "Exact NPY"):
                sub.preflight(self.query_path, self.query_hash, self.predictions, np)
        finally:
            path.write_bytes(self.array_bytes[case_id])
            type(self).fixture_bytes_written += len(self.array_bytes[case_id])


if __name__ == "__main__":
    unittest.main()
