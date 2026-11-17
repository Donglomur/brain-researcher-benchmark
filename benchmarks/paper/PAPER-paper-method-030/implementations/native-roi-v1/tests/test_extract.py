"""Small generated TIFF controls; no authentic optical/EP data or model runs."""
import copy
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import numpy as np
import tifffile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("native_roi_extract", ROOT / "extract.py")
extract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(extract)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def panel_fixture():
    rows = extract.read_json(extract.POPULATION)["recordings"]
    methods = ["raw", "cellmincer", "n2s", "candidate"]
    return {"schema_version": 1, "task_id": extract.TASK_ID,
            "population_sha256": digest(extract.POPULATION), "methods": methods,
            "recordings": [{"recording_id": row["recording_id"], "cell_id": row["cell_id"],
                "shape_yx": [2, 3], "roi": {}, "movies": {method: {
                    "path": method + ".tif", "sha256": "a" * 64,
                    **({"source_object": copy.deepcopy(row["raw_tiff"])} if method == "raw" else {})}
                    for method in methods}} for row in rows]}


class NativeTiff(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.path = self.base / "generated.tif"
        self.frames = np.arange(18, dtype=np.uint16).reshape(3, 2, 3)
        self.mask = np.array([[True, False, False], [False, False, True]])
        tifffile.imwrite(self.path, self.frames, photometric="minisblack", metadata=None)

    def tearDown(self):
        self.temporary.cleanup()

    def test_incremental_hand_computed_means_no_whole_stack_decode(self):
        with mock.patch.object(tifffile.TiffFile, "asarray", side_effect=AssertionError("whole stack decoded")):
            trace, receipt = extract.stream_roi_mean(self.path, digest(self.path), self.mask, 3)
        self.assertEqual(trace, [2.5, 8.5, 14.5])
        self.assertEqual(receipt["roi_pixels"], 2)
        self.assertEqual(receipt["shape_yx"], [2, 3])
        self.assertNotIn(str(self.base), json.dumps(receipt))

    def test_original_5000_frames_and_one_shared_roi_for_methods(self):
        frames = np.tile(self.frames[:1], (5000, 1, 1))
        tifffile.imwrite(self.path, frames, photometric="minisblack", metadata=None)
        raw, _ = extract.stream_roi_mean(self.path, digest(self.path), self.mask)
        denoised = self.base / "generated-denoised.tif"
        # Changing only an outside-ROI pixel cannot change the extracted trace.
        frames[:, 0, 1] = 1000
        tifffile.imwrite(denoised, frames, photometric="minisblack", metadata=None)
        method, _ = extract.stream_roi_mean(denoised, digest(denoised), self.mask)
        self.assertEqual(raw, [2.5] * 5000)
        self.assertEqual(raw, method)

    def test_content_size_and_frame_count_mismatch_rejected(self):
        for kwargs, message in [({"expected_sha256": "0" * 64, "expected_frames": 3}, "hash"),
                                ({"expected_sha256": digest(self.path), "expected_frames": 3, "expected_bytes": 1}, "byte count"),
                                ({"expected_sha256": digest(self.path)}, "page count")]:
            with self.subTest(message=message), self.assertRaisesRegex(extract.InputError, message):
                extract.stream_roi_mean(self.path, mask=self.mask, **kwargs)

    def test_gcs_checksum_is_independent_of_caller_sha256(self):
        expected = base64.b64encode(hashlib.md5(self.path.read_bytes(), usedforsecurity=False).digest()).decode()
        _, receipt = extract.stream_roi_mean(self.path, digest(self.path), self.mask, 3, source_md5_base64=expected)
        self.assertTrue(receipt["cached_gcs_md5_verified"])
        with self.assertRaisesRegex(extract.InputError, "GCS content"):
            extract.stream_roi_mean(self.path, digest(self.path), self.mask, 3, source_md5_base64="A" * 24)

    def test_wrong_spatial_shape_and_empty_mask_rejected(self):
        with self.assertRaisesRegex(extract.InputError, "grayscale"):
            extract.stream_roi_mean(self.path, digest(self.path), np.ones((3, 2), bool), 3)
        with self.assertRaisesRegex(extract.InputError, "nonempty"):
            extract.stream_roi_mean(self.path, digest(self.path), np.zeros((2, 3), bool), 3)

    def test_nonfinite_pixels_rejected_even_outside_roi(self):
        frames = self.frames.astype(float)
        frames[1, 0, 1] = np.nan
        tifffile.imwrite(self.path, frames, photometric="minisblack", metadata=None)
        with self.assertRaisesRegex(extract.InputError, "nonfinite"):
            extract.stream_roi_mean(self.path, digest(self.path), self.mask, 3)

    def test_color_pages_are_not_time_or_spatial_axes(self):
        tifffile.imwrite(self.path, np.zeros((2, 3, 3), np.uint8), photometric="rgb")
        with self.assertRaisesRegex(extract.InputError, "grayscale"):
            extract.stream_roi_mean(self.path, digest(self.path), self.mask, 1)

    def test_palette_indices_are_not_fluorescence_intensities(self):
        colormap = np.zeros((3, 256), np.uint16)
        colormap[0] = np.arange(256, dtype=np.uint16) * 257
        tifffile.imwrite(self.path, self.frames[0].astype(np.uint8), photometric="palette", colormap=colormap)
        with self.assertRaisesRegex(extract.InputError, "MINISBLACK"):
            extract.stream_roi_mean(self.path, digest(self.path), self.mask, 1)

    def test_orientation_cannot_silently_move_shared_roi(self):
        tifffile.imwrite(self.path, self.frames[0], photometric="minisblack", extratags=[(274, 'H', 1, 3, False)])
        with self.assertRaisesRegex(extract.InputError, "orientation"):
            extract.stream_roi_mean(self.path, digest(self.path), self.mask, 1)

    def test_mutation_during_read_rejected(self):
        original = tifffile.TiffPage.asarray
        changed = False
        def read_and_mutate(page, *args, **kwargs):
            nonlocal changed
            value = original(page, *args, **kwargs)
            if not changed:
                with self.path.open("ab") as handle:
                    handle.write(b"changed")
                changed = True
            return value
        with mock.patch.object(tifffile.TiffPage, "asarray", read_and_mutate):
            with self.assertRaisesRegex(extract.InputError, "changed during"):
                extract.stream_roi_mean(self.path, digest(self.path), self.mask, 3)

    def test_roi_binding_and_boolean_semantics(self):
        path = self.base / "roi.json"
        path.write_text(json.dumps(self.mask.astype(int).tolist()))
        roi = {"path": path.name, "sha256": digest(path), "source_raw_sha256": digest(self.path),
               "selection_policy": "raw_only_frozen_before_method_comparison", "evidence_sha256": "b" * 64}
        np.testing.assert_array_equal(extract.load_roi(roi, digest(self.path), (2, 3), self.base), self.mask)
        with self.assertRaisesRegex(extract.InputError, "different raw"):
            extract.load_roi(roi, "c" * 64, (2, 3), self.base)
        path.write_text("[[1, 0, 0], [0, 0, 2]]")
        roi["sha256"] = digest(path)
        with self.assertRaisesRegex(extract.InputError, "only 0/1"):
            extract.load_roi(roi, digest(self.path), (2, 3), self.base)


class CompletePanel(unittest.TestCase):
    def test_full_saved_population_validates_without_claiming_original_membership(self):
        rows, catalogue = extract.validate_panel(panel_fixture())
        self.assertEqual(len(rows), 22)
        self.assertEqual(len({r["cell_id"] for r in rows}), 9)
        self.assertEqual(set(catalogue), {r["recording_id"] for r in rows})

    def test_omitted_or_duplicated_recordings_rejected(self):
        for duplicate in [False, True]:
            panel = panel_fixture()
            if duplicate:
                panel["recordings"][-1] = copy.deepcopy(panel["recordings"][0])
            else:
                panel["recordings"].pop()
            with self.assertRaisesRegex(extract.InputError, "all 22"):
                extract.validate_panel(panel)

    def test_source_generation_and_method_coverage_rejected(self):
        panel = panel_fixture()
        panel["recordings"][0]["movies"]["raw"]["source_object"]["version"] = "different"
        with self.assertRaisesRegex(extract.InputError, "source object"):
            extract.validate_panel(panel)
        panel = panel_fixture()
        del panel["recordings"][0]["movies"]["candidate"]
        with self.assertRaisesRegex(extract.InputError, "method coverage"):
            extract.validate_panel(panel)

    def test_duplicate_json_keys_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "panel.json"
            path.write_text('{"methods": [], "methods": ["raw"]}')
            with self.assertRaisesRegex(extract.InputError, "duplicate JSON"):
                extract.read_json(path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
