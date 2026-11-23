"""Generated paired-panel checks; no real images, neural data, weights or models."""
from __future__ import annotations

import contextlib
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import numpy as np

ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("_paired_under_test", ROOT / "table1_compare.py")
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)
COUNTS = {"generated_file_writes": 0, "generated_payload_reads": 0}


def rows():
    ids = [f"generated-{i:04}" for i in range(m.metric.GALLERY_SIZE)]
    return [{"subject": s, "target_ids": ids.copy(),
             "reconstruction_ids": ids.copy(), "selection_ids": ids.copy(),
             "target_features": (s, "target"), "selected_features": (s, "prediction"),
             "selection_cosines": (s, "cosines"),
             "selected_candidate_indices": (s, "indices")}
            for s in m.metric.SUBJECTS]


class ComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        n, d = m.metric.GALLERY_SIZE, m.metric.CLIP_DIM
        cls.targets = np.zeros((n, d), dtype="float32")
        cls.groups = np.arange(n) % 3
        cls.targets[:, :3] = -1
        cls.targets[np.arange(n), cls.groups] = 2
        cls.repeated = np.repeat(cls.targets[:1], n, axis=0)
        cls.cosines = np.zeros((n, 8), dtype="float64")
        cls.indices = np.zeros(n, dtype="int64")

    def arrays(self, prediction=None):
        return {(s, kind): value for s in m.metric.SUBJECTS for kind, value in (
            ("target", self.targets), ("prediction", self.targets if prediction is None else prediction),
            ("cosines", self.cosines), ("indices", self.indices))}

    def compare(self, old=None, new=None, old_rows=None, new_rows=None, **kw):
        return m.compare(rows() if old_rows is None else old_rows,
                         rows() if new_rows is None else new_rows,
                         (self.arrays() if old is None else old).__getitem__,
                         (self.arrays() if new is None else new).__getitem__,
                         max_working_bytes=256 * 1024**2, **kw)

    def test_complete_actual_arithmetic_with_nonuniform_subject_deltas(self):
        old = self.arrays(self.repeated)
        new = self.arrays()
        # Three subjects use correct repeated-class features; one uses the
        # negative target, which loses to every distractor under strict ties.
        new[("5", "prediction")] = -self.targets
        result = self.compare(old, new, include_image_counts=True)
        n = len(self.groups)
        sizes = np.bincount(self.groups)
        reference_counts = np.where(self.groups == 0, n - sizes[0], 0)
        correct_counts = n - sizes[self.groups]
        expected_reference = float(np.mean(reference_counts) / (n - 1))
        expected_correct = float(np.mean(correct_counts) / (n - 1))
        expected_candidate = float(np.mean([expected_correct, expected_correct, 0., expected_correct]))
        self.assertEqual(result["reference_clip_two_way"], expected_reference)
        self.assertEqual(result["candidate_clip_two_way"], expected_candidate)
        self.assertEqual(result["delta_clip_two_way"], expected_candidate - expected_reference)
        self.assertEqual(result["delta_percentage_points"], 100 * (expected_candidate - expected_reference))
        for row in result["subjects"]:
            expected = np.zeros(n, dtype=int) if row["subject"] == "5" else correct_counts
            self.assertEqual(row["image_ids"], rows()[0]["target_ids"])
            self.assertEqual(row["reference_success_counts"], reference_counts.tolist())
            self.assertEqual(row["candidate_success_counts"], expected.tolist())
            self.assertEqual(row["success_count_deltas"], (expected - reference_counts).tolist())
        self.assertFalse(result["scientific_qualification"])
        self.assertEqual(result["reproduction"], "unknown")
        self.assertEqual(result["improvement"], "unknown")
        self.assertNotIn("confidence_interval", result)

    def test_default_output_omits_operator_private_image_counts(self):
        # Actual helper return layout; mathematical path covered above.
        with mock.patch.object(m, "_score", return_value=(np.zeros(982, dtype="int64"), 0.)):
            result = self.compare()
        self.assertFalse(result["image_counts_included"])
        for row in result["subjects"]:
            self.assertNotIn("image_ids", row)
            self.assertNotIn("success_count_deltas", row)
        self.assertEqual(result["delta_clip_two_way"], 0.)

    def test_changed_cross_arm_identity_or_order_refused_before_arrays(self):
        for change in ("order", "membership"):
            candidate = rows()
            for row in candidate:
                for field in ("target_ids", "reconstruction_ids", "selection_ids"):
                    if change == "order":
                        row[field].reverse()
                    else:
                        row[field][0] = "a-different-case"
            loader = mock.Mock(side_effect=AssertionError("should not load"))
            with self.assertRaisesRegex(m.metric.MetricError, "identical ordered"):
                m.compare(rows(), candidate, loader, loader, max_working_bytes=256 * 1024**2)
            loader.assert_not_called()

    def test_targets_must_match_array_values_not_descriptor_names(self):
        new = self.arrays()
        altered = self.targets.copy()
        altered[0, 5] = 0.25
        new[("1", "target")] = altered
        with mock.patch.object(m, "_score", side_effect=AssertionError("must refuse first")):
            with self.assertRaisesRegex(m.metric.MetricError, "values must match"):
                self.compare(new=new)

    def test_complete_float32_finite_targets_required_in_each_arm(self):
        for arm in ("old", "new"):
            for variant in (self.targets[:-1], self.targets.astype("float64"),
                            np.full_like(self.targets, np.nan)):
                arrays = self.arrays(); arrays[("1", "target")] = variant
                with self.subTest(arm=arm, shape=variant.shape, dtype=variant.dtype):
                    with self.assertRaisesRegex(m.metric.MetricError, "target features"):
                        self.compare(**{arm: arrays})

    def test_each_arm_selection_is_checked_independently(self):
        for arm in ("old", "new"):
            arrays = self.arrays()
            invalid = self.indices.copy(); invalid[0] = 1
            arrays[("1", "indices")] = invalid
            with self.subTest(arm=arm):
                with self.assertRaisesRegex(m.metric.MetricError, "first maximum"):
                    self.compare(**{arm: arrays})

    def test_complete_four_subject_panels_and_workspace_required(self):
        for old_rows, new_rows in ((rows()[:-1], rows()), (rows(), rows()[:-1])):
            with self.assertRaisesRegex(m.metric.MetricError, "four subject"):
                self.compare(old_rows=old_rows, new_rows=new_rows)
        loader = mock.Mock(side_effect=AssertionError("should not load"))
        with self.assertRaisesRegex(m.metric.MetricError, "160 MiB"):
            m.compare(rows(), rows(), loader, loader, max_working_bytes=128 * 1024**2)
        loader.assert_not_called()

    def write(self, path, raw):
        path.write_bytes(raw)
        COUNTS["generated_file_writes"] += len(raw)

    def manifest(self, path):
        raw = json.dumps({"schema": m.metric.SCHEMA, "rows": []}).encode()
        self.write(path, raw)
        return raw

    def test_cli_uses_one_payload_budget_across_both_arms(self):
        with tempfile.TemporaryDirectory(dir=ROOT, prefix="generated-compare-") as temporary:
            root = Path(temporary)
            old = root / "old.json"; new = root / "new.json"
            self.manifest(old); self.manifest(new)
            stream = io.BytesIO(); np.save(stream, np.array([1, 2], dtype="float32"), allow_pickle=False)
            raw = stream.getvalue(); self.write(root / "x.npy", raw)
            desc = {"path": "x.npy", "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
            def fake_compare(a, b, load_old, load_new, **kw):
                np.testing.assert_array_equal(load_old(desc), [1, 2])
                COUNTS["generated_payload_reads"] += len(raw)
                load_new(desc)
                self.fail("the shared limit must refuse the second payload")
            with mock.patch.object(m, "compare", side_effect=fake_compare):
                with self.assertRaisesRegex(m.metric.MetricError, "cumulative payload read"):
                    m.main([str(old), str(new), "--max-read-bytes", str(2 * len(raw) - 1),
                            "--max-working-bytes", str(256 * 1024**2)])

    def test_cli_records_manifest_pins_and_total_payload_bytes(self):
        with tempfile.TemporaryDirectory(dir=ROOT, prefix="generated-compare-") as temporary:
            root = Path(temporary)
            old = root / "old.json"; new = root / "new.json"
            old_raw = self.manifest(old); new_raw = self.manifest(new)
            stream = io.BytesIO(); np.save(stream, np.array([1, 2], dtype="float32"), allow_pickle=False)
            raw = stream.getvalue(); self.write(root / "x.npy", raw)
            desc = {"path": "x.npy", "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
            def fake_compare(a, b, load_old, load_new, **kw):
                load_old(desc); load_new(desc)
                COUNTS["generated_payload_reads"] += 2 * len(raw)
                self.assertTrue(kw["include_image_counts"])
                return {"scientific_qualification": False}
            capture = io.StringIO()
            with mock.patch.object(m, "compare", side_effect=fake_compare), contextlib.redirect_stdout(capture):
                m.main([str(old), str(new), "--max-read-bytes", str(2 * len(raw) + 1),
                        "--max-working-bytes", str(256 * 1024**2), "--include-image-counts"])
            result = json.loads(capture.getvalue())
            self.assertEqual(result["payload_read_bytes"], 2 * len(raw))
            self.assertEqual(result["manifest_read_bytes"], len(old_raw) + len(new_raw))
            self.assertEqual(result["reference_manifest_sha256"], hashlib.sha256(old_raw).hexdigest())
            self.assertEqual(result["candidate_manifest_sha256"], hashlib.sha256(new_raw).hexdigest())

    def test_manifest_refuses_duplicate_schema_and_wrong_arm_kind(self):
        with tempfile.TemporaryDirectory(dir=ROOT, prefix="generated-compare-") as temporary:
            path = Path(temporary) / "packet.json"
            for raw in (b'{"schema":"x","schema":"y","rows":[]}',
                        b'{"schema":"other-panel","rows":[]}'):
                self.write(path, raw)
                with self.assertRaises(m.metric.MetricError):
                    m._read_manifest(path)


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(ComparisonTests))
    print(json.dumps({"tests": result.testsRun, "failures": len(result.failures),
                      "errors": len(result.errors), "costs": COUNTS,
                      "generated_only": True}, sort_keys=True))
    raise SystemExit(0 if result.wasSuccessful() else 1)
