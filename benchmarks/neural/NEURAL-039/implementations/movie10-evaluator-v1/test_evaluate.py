"""Generated software controls only: no scientific data, model or fit."""
import copy
import io
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import h5py
import numpy as np

import evaluate as ev


class EvaluatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / "source"
        self.source.mkdir()
        self.submission = self.root / "submission"
        self.submission.mkdir()
        self.panel = {"schema": "neural039_movie10_panel_v1", "source_commit": ev.SOURCE_COMMIT,
                      "subjects": {}}
        self.values = {}
        for subject in ev.SUBJECTS:
            datasets = {
                "ses-001_task-bourne1": [18, 1000],
                "ses-002_task-bourne2": [22, 1000],
                "ses-003_task-figures1_run-1": [19, 1000],
                "ses-004_task-figures1_run-2": [20, 1000],
                "ses-005_task-life1_run-1": [19, 1000],
                "ses-006_task-life1_run-2": [20, 1000],
                "ses-007_task-wolf1": [25, 1000],
            }
            path = self.source / f"{subject}_movie10.h5"
            with h5py.File(path, "w") as h:
                for index, (key, shape) in enumerate(datasets.items()):
                    # Integer-valued columns give independent, exact golden expectations.
                    value = (np.arange(shape[0])[:, None] + np.arange(1000)[None, :] + 40 * index).astype("<f4")
                    h.create_dataset(key, data=value)
                    self.values[subject, key] = value
            body = path.read_bytes()
            self.panel["subjects"][subject] = {"file": path.name, "bytes": len(body),
                                               "sha256": ev.digest(body), "datasets": datasets}
        self.panel_path = self.root / "panel.json"
        self.freeze_panel()
        self.query = ev.queries(self.panel)
        for case_id, query in self.query.items():
            folder = self.submission / case_id
            folder.mkdir()
            target = np.concatenate([self.values[query["subject"], r["key"]][r["start"]:r["stop"]]
                                     for r in query["runs"]])
            self.write_prediction(case_id, target)

    def tearDown(self):
        self.temp.cleanup()

    def freeze_panel(self):
        body = ev.canonical(self.panel)
        self.panel_path.write_bytes(body)
        self.panel = ev.read_panel(self.panel_path, ev.digest(body))

    def write_prediction(self, case_id, value):
        folder = self.submission / case_id
        np.save(folder / "predictions.npy", value, allow_pickle=False)
        (folder / "submission.json").write_bytes(ev.canonical({
            "schema": "neural039_prediction_v2", "case_id": case_id,
            "query_sha256": ev.digest(ev.canonical(self.query[case_id]))}))

    def score(self, validate_only=False):
        return ev.evaluate(self.panel, self.source, self.submission, np, h5py, validate_only)

    def test_full_panel_equal_person_film_weighting(self):
        case_id = "sub-05_hold-wolf"
        path = self.submission / case_id / "predictions.npy"
        self.write_prediction(case_id, -np.load(path, allow_pickle=False))
        result = self.score()
        self.assertEqual(result["status"], "scored")
        self.assertAlmostEqual(result["primary_score"], 0.875, places=12)
        for subject, expected in {"sub-01": 1.0, "sub-02": 1.0, "sub-03": 1.0, "sub-05": 0.5}.items():
            self.assertAlmostEqual(result["per_person"][subject], expected, places=12)
        self.assertEqual(len(result["per_case"]), 16)
        self.assertEqual(result["target_file_opens"], 4)
        self.assertTrue(all(len(v["parcel_correlations"]) == 1000 for v in result["per_case"].values()))

    def test_segments_concatenated_before_correlation(self):
        case_id = "sub-01_hold-bourne"
        path = self.submission / case_id / "predictions.npy"
        target = np.load(path, allow_pickle=False)
        prediction = target.copy()
        for run in self.query[case_id]["runs"]:
            start, stop = run["offset"], run["offset"] + run["stop"] - run["start"]
            prediction[start:stop] = prediction[start:stop][::-1]
        self.write_prediction(case_id, prediction)
        x, y = prediction[:, 0].tolist(), target[:, 0].tolist()
        mx, my = math.fsum(x) / len(x), math.fsum(y) / len(y)
        expected = math.fsum((a - mx) * (b - my) for a, b in zip(x, y)) / math.sqrt(
            math.fsum((a - mx) ** 2 for a in x) * math.fsum((b - my) ** 2 for b in y))
        result = self.score()
        self.assertEqual(result["status"], "scored")
        self.assertGreater(expected, 0.9)  # Each individual run has correlation -1.
        self.assertAlmostEqual(result["per_case"][case_id]["mean"], expected, places=12)

    def test_invalid_last_prediction_precedes_all_target_reads(self):
        path = self.submission / ev.CASES[-1] / "predictions.npy"
        value = np.load(path, allow_pickle=False)
        value[:, 17] = 3
        self.write_prediction(ev.CASES[-1], value)
        with patch.object(h5py, "File", side_effect=AssertionError("Target was opened")):
            result = self.score()
        self.assertEqual(result["status"], "candidate_invalid")
        self.assertIn("constant prediction", result["detail"])
        self.assertEqual(result["target_file_opens"], 0)

    def test_query_digest_rejects_native_tr_shift(self):
        case_id = ev.CASES[0]
        query = copy.deepcopy(self.query[case_id])
        query["runs"][0]["start"] += 1
        path = self.submission / case_id / "submission.json"
        path.write_bytes(ev.canonical({"schema": "neural039_prediction_v2", "case_id": case_id,
                                      "query_sha256": ev.digest(ev.canonical(query))}))
        result = self.score()
        self.assertEqual(result["status"], "candidate_invalid")
        self.assertEqual(result["target_file_opens"], 0)

    def test_constant_target_is_operator_failure_without_numeric_score(self):
        subject = ev.SUBJECTS[0]
        path = self.source / f"{subject}_movie10.h5"
        with h5py.File(path, "r+") as h:
            h["ses-007_task-wolf1"][:, 0] = 0
        self.panel["subjects"][subject]["sha256"] = ev.digest(path.read_bytes())
        result = self.score()
        self.assertEqual(result["status"], "operator_error")
        self.assertIsNone(result["primary_score"])
        self.assertIn("constant target", result["detail"])

    def test_source_inventory_cannot_silently_drop_complete_run(self):
        # Removing one Bourne segment and rebinding queries still fails against the HDF5.
        subject = ev.SUBJECTS[0]
        del self.panel["subjects"][subject]["datasets"]["ses-002_task-bourne2"]
        self.freeze_panel()
        self.query = ev.queries(self.panel)
        case_id = subject + "_hold-bourne"
        self.write_prediction(case_id, self.values[subject, "ses-001_task-bourne1"][8:-5])
        result = self.score()
        self.assertEqual(result["status"], "operator_error")
        self.assertIn("inventory differs", result["detail"])

    def test_manifest_rejects_missing_repeat_or_wrong_person(self):
        original = copy.deepcopy(self.panel)
        del self.panel["subjects"]["sub-01"]["datasets"]["ses-004_task-figures1_run-2"]
        with self.assertRaisesRegex(ValueError, "Both original viewings"):
            self.freeze_panel()
        self.panel = original
        self.panel["subjects"]["sub-01"]["file"] = "sub-02_movie10.h5"
        with self.assertRaisesRegex(ValueError, "participant source filename"):
            self.freeze_panel()

    def test_hash_drift_and_full_coverage_fail_closed(self):
        subject = ev.SUBJECTS[0]
        self.panel["subjects"][subject]["sha256"] = "0" * 64
        self.assertEqual(self.score()["status"], "operator_error")
        (self.submission / ev.CASES[-1] / "submission.json").unlink()
        result = self.score()
        self.assertEqual(result["status"], "candidate_invalid")
        self.assertEqual(result["target_file_opens"], 0)

    def test_array_parser_rejects_nonfinite_transposed_trailing_and_float64(self):
        shape = (3, 1000)
        valid = np.arange(3000, dtype="<f4").reshape(shape)
        bad = valid.copy()
        bad[0, 0] = np.nan
        for value in (bad, valid.T, valid.astype("<f8"), np.asfortranarray(valid)):
            with self.subTest(dtype=value.dtype, shape=value.shape, c_order=value.flags.c_contiguous):
                stream = io.BytesIO()
                np.save(stream, value, allow_pickle=False)
                with self.assertRaises(ValueError):
                    ev.array(stream.getvalue(), shape, np)
        stream = io.BytesIO()
        np.save(stream, valid, allow_pickle=False)
        with self.assertRaises(ValueError):
            ev.array(stream.getvalue() + b"extra", shape, np)

    def test_validate_only_never_opens_targets(self):
        with patch.object(h5py, "File", side_effect=AssertionError("Target was opened")):
            result = self.score(validate_only=True)
        self.assertEqual(result["status"], "valid_predictions")
        self.assertEqual(result["target_file_opens"], 0)

    def test_query_is_metadata_only_and_exact_guards(self):
        self.assertEqual(set(self.query), set(ev.CASES))
        for value in self.query.values():
            self.assertEqual(value["shape"][1], 1000)
            for run in value["runs"]:
                self.assertEqual(run["start"], 8)
                self.assertEqual(run["stop"], run["native_samples"] - 5)
            text = ev.canonical(value).decode()
            self.assertNotIn(str(self.source), text)
            self.assertNotIn("sha256", text)


if __name__ == "__main__":
    unittest.main()
