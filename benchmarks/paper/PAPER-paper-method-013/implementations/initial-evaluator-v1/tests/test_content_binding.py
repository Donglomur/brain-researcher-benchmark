"""Focused content-binding regressions; generated in-memory arrays only."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import warnings
import zipfile

import numpy as np

MODULE = Path(__file__).resolve().parents[1] / "evaluator.py"
spec = importlib.util.spec_from_file_location("deepcaimx_content_bound_v2", MODULE)
e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)


def npz_bytes(reverse=False):
    stream = io.BytesIO()
    masks = np.zeros((1, 488, 488), dtype=bool)
    masks[0, 0, 0] = True
    trace = np.arange(5000, dtype=float)[None, :]
    if reverse:
        trace = trace[:, ::-1]
    np.savez_compressed(stream, masks=masks, traces=trace)
    return stream.getvalue()


class ContentBindingTests(unittest.TestCase):
    def test_npz_decodes_authenticated_snapshot_when_path_changes(self):
        captured, replacement = npz_bytes(), npz_bytes(True)
        sha = hashlib.sha256(captured).hexdigest()
        original_load = np.load
        def replacement_at_decode(source, **kwargs):
            # A path reopen sees different predictions; a captured stream does not.
            return original_load(io.BytesIO(replacement) if isinstance(source, (str, Path)) else source,
                                 **kwargs)
        with patch.object(Path, "is_file", return_value=True), \
             patch.object(Path, "read_bytes", return_value=captured), \
             patch.object(e, "_sha256", return_value=sha), \
             patch.object(e.np, "load", side_effect=replacement_at_decode):
            masks, traces = e._load_arrays({"array_file": "predictions.npz", "array_sha256": sha},
                                           Path("/unused/submission.json"))
        self.assertEqual(int(masks.sum()), 1)
        np.testing.assert_array_equal(traces, np.arange(5000, dtype=float)[None, :])
        with patch.object(Path, "is_file", return_value=True), \
             patch.object(Path, "read_bytes", return_value=captured):
            with self.assertRaisesRegex(ValueError, "SHA256"):
                e._load_arrays({"array_file": "predictions.npz", "array_sha256": "0" * 64},
                               Path("/unused/submission.json"))

    def test_duplicate_npz_array_names_are_rejected(self):
        complete = npz_bytes()
        output = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(complete)) as source, \
             zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as target:
            for name in source.namelist():
                target.writestr(name, source.read(name))
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                target.writestr("traces.npy", source.read("traces.npy"))
        raw = output.getvalue()
        sha = hashlib.sha256(raw).hexdigest()
        original_load = np.load
        def captured_archive(source, **kwargs):
            return original_load(io.BytesIO(raw) if isinstance(source, (str, Path)) else source,
                                 **kwargs)
        with patch.object(Path, "is_file", return_value=True), \
             patch.object(Path, "read_bytes", return_value=raw), \
             patch.object(e, "_sha256", return_value=sha), \
             patch.object(e.np, "load", side_effect=captured_archive):
            with self.assertRaisesRegex(ValueError, "duplicate"):
                e._load_arrays({"array_file": "duplicate.npz", "array_sha256": sha},
                               Path("/unused/submission.json"))

    def test_score_receipts_identify_the_parsed_manifests(self):
        common = dict(schema_version=1, task_id=e.TASK_ID,
                      frame_labels_inclusive=e.FRAME_LABELS, frame_count=e.N_FRAMES,
                      image_shape=list(e.IMAGE_SHAPE), coordinate_system="zero_based_row_column")
        rows = [{"recording_id": rid, "depth_um": depth,
                 "runtime": {"wall_seconds": 1, "hardware_id": "generated",
                             "environment_id": "generated", "scope": "processing_excluding_data_loading_and_writing"}}
                for rid, depth in e.RECORDINGS.items()]
        reference = dict(common, reference_kind="author_constructed_fluorescence",
                         source_transformation_receipt="generated content-binding control",
                         recordings=rows)
        reference_raw = json.dumps(reference).encode()
        reference_sha = hashlib.sha256(reference_raw).hexdigest()
        methods = [dict(common, method_id=role, role=role,
                        implementation_identity="generated", recordings=rows)
                   for role in ("candidate", "baseline")]
        submission_raw = json.dumps({"policy_id": e.POLICY_ID,
                                     "reference_manifest_sha256": reference_sha,
                                     "methods": methods}).encode()
        paths = {Path("/unused/reference.json"): reference_raw,
                 Path("/unused/submission.json"): submission_raw}
        reads = []
        def capture_once(path):
            reads.append(path)
            if reads.count(path) > 1:
                return b'{"replacement":true}'
            return paths[path]
        masks = np.ones((1, 1, 1), dtype=bool)
        traces = np.array([[0., 1.]])
        with patch.object(Path, "read_bytes", autospec=True, side_effect=capture_once), \
             patch.object(Path, "read_text", autospec=True,
                          side_effect=lambda path, *args, **kwargs: capture_once(path).decode()), \
             patch.object(e, "_sha256", side_effect=AssertionError("manifest path was re-read")), \
             patch.object(e, "_load_arrays", return_value=(masks, traces)):
            result = e.evaluate(*paths)
        self.assertEqual(result["reference_manifest_sha256"], reference_sha)
        self.assertEqual(result["submission_manifest_sha256"], hashlib.sha256(submission_raw).hexdigest())
        self.assertEqual(len(reads), 2)
        self.assertEqual(result["methods"][0]["pooled_roi_counts"]["f1"], 1.)
        self.assertEqual(result["paired_comparisons"][0]["baseline_over_candidate_total_runtime"], 1.)


if __name__ == "__main__":
    unittest.main()
