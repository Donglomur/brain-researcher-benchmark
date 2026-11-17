"""Independent generated controls; no authentic movie or model is executed."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from contextlib import contextmanager
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import warnings
from unittest.mock import patch

import h5py
import numpy as np

HERE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("deepcaimx_streaming", HERE / "streaming.py")
S = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(S)


def mapping(shape=(24000, 512, 512), start=18500, row=12, column=7):
    return {
        "schema": "deepcaimx-explicit-movie-mapping/v1",
        "task_id": "PAPER-paper-method-013", "recording_id": "501271265",
        "source_shape": list(shape), "frame_start_zero_based": start,
        "crop_row_start": row, "crop_column_start": column,
        "mapping_evidence": "Invented software fixture; no historical mapping claim",
    }


class VirtualMovie:
    """Create only requested slabs, and preserve every observed request."""
    shape = (24000, 512, 512)
    dtype = np.dtype("uint16")

    def __init__(self, value=None):
        self.calls = []
        self.value = value

    def __getitem__(self, slices):
        self.calls.append(slices)
        t, r, c = slices
        shape = (t.stop-t.start, r.stop-r.start, c.stop-c.start)
        if self.value is not None:
            return np.full(shape, self.value, dtype=np.uint16)
        values = np.full(shape, 1200, dtype=np.uint16)
        values[0, 0, 0] = 0
        values[-1, -1, -1] = 65535
        values[1, 2, 3] = 32768
        return values


class GeometryControls(unittest.TestCase):
    def test_complete_matlab_order_and_coverage(self):
        observed = [S.tile_geometry(i) for i in range(1053)]
        expected = [(t, r, c) for t in range(0, 5000, 400)
                    for c in range(0, 425, 53) for r in range(0, 425, 53)]
        self.assertEqual([tuple(row["start_zero_based"]) for row in observed], expected)
        self.assertEqual(len(set(expected)), 1053)
        self.assertEqual(observed[-1]["stop_exclusive"], [5200, 488, 488])
        self.assertEqual(observed[-1]["valid_stop_exclusive"], [5000, 488, 488])
        self.assertEqual(sum(row["valid_frames"] == 200 for row in observed), 81)

    def test_tile_index_rejects_invalid_integers_and_bools(self):
        for value in (-1, 1053, 10**100, True, 1.0, "1", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                S.tile_geometry(value)

    def test_first_middle_last_source_slices_and_axis_orientation(self):
        dataset = VirtualMovie()
        for index, starts, stops in (
            (0, (18500, 12, 7), (18900, 76, 71)),
            (10, (18500, 65, 60), (18900, 129, 124)),
            (81, (18900, 12, 7), (19300, 76, 71)),
            (1052, (23300, 436, 431), (23500, 500, 495)),
        ):
            with self.subTest(index=index):
                array, receipt = S.model_input(dataset, mapping(), index)
                self.assertEqual(array.shape, (1, 400, 64, 64, 1))
                self.assertEqual(array.dtype, np.dtype("float32"))
                request = dataset.calls[-1]
                self.assertEqual(tuple(s.start for s in request), starts)
                self.assertEqual(tuple(s.stop for s in request), stops)
                self.assertTrue(all(s.step is None for s in request))
                self.assertEqual(array[0, 0, 0, 0, 0], 0.0)
                self.assertEqual(array[0, 1, 2, 3, 0], np.float32(32768)/np.float32(65535))
                self.assertEqual(array[0, receipt["valid_frames"]-1, 63, 63, 0], 1.0)
                self.assertEqual(receipt["mapping_authentication"], "unestablished_by_this_component")
        self.assertEqual(len(dataset.calls), 4)

    def test_padding_participates_in_normalization(self):
        array, report = S.model_input(VirtualMovie(7), mapping(), 1052)
        np.testing.assert_array_equal(array[0, :200, :, :, 0], 1)
        np.testing.assert_array_equal(array[0, 200:, :, :, 0], 0)
        self.assertEqual(report["padded_minimum"], 0)
        self.assertEqual(report["padded_maximum"], 7)

    def test_source_zero_span_is_not_replaced(self):
        for value, index in ((0, 0), (7, 0), (0, 1052)):
            with self.subTest(value=value, index=index), self.assertRaisesRegex(ValueError, "span"):
                S.model_input(VirtualMovie(value), mapping(), index)

    def test_wrong_source_dtype_and_reader_return_are_refused(self):
        movie = VirtualMovie()
        movie.dtype = np.dtype("float32")
        with self.assertRaisesRegex(ValueError, "uint16"):
            S.model_input(movie, mapping(), 0)
        self.assertEqual(movie.calls, [])
        for wrong in (np.zeros((399, 64, 64), np.uint16), np.zeros((400, 64, 64), np.float32)):
            with self.subTest(shape=wrong.shape, dtype=wrong.dtype):
                with patch.object(VirtualMovie, "__getitem__", return_value=wrong), self.assertRaises(ValueError):
                    S.model_input(VirtualMovie(), mapping(), 0)

    def test_mapping_invalid_fields_shapes_and_bounds(self):
        changes = {
            "schema": "wrong", "task_id": "other", "recording_id": "unknown",
            "source_shape": [24000, 488, 488], "frame_start_zero_based": 19001,
            "crop_row_start": 25, "crop_column_start": -1, "mapping_evidence": "  ",
        }
        for key, value in changes.items():
            with self.subTest(key=key), self.assertRaises(ValueError):
                S.validate_mapping({**mapping(), key: value}, VirtualMovie.shape)
        for key in ("frame_start_zero_based", "crop_row_start", "crop_column_start"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                S.validate_mapping({**mapping(), key: True}, VirtualMovie.shape)
        for value in ({}, None, {**mapping(), "unknown": 1},
                      {**mapping(), "source_shape": [True, 512, 512]}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                S.validate_mapping(value, VirtualMovie.shape)
        with self.assertRaisesRegex(ValueError, "shapes differ"):
            S.validate_mapping(mapping(), (24001, 512, 512))

    def test_exact_edge_crop_and_last_full_interval_are_permitted(self):
        plan = mapping(start=19000, row=24, column=24)
        S.validate_mapping(plan, VirtualMovie.shape)
        array, report = S.model_input(VirtualMovie(), plan, 1052)
        self.assertEqual(report["source_slice_stop"], [24000, 512, 512])
        self.assertEqual(array.shape, (1, 400, 64, 64, 1))

    def test_iterator_covers_all_tiles_and_freezes_mapping(self):
        plan = mapping()
        seen = []
        def record(dataset, bound, index):
            seen.append((index, bound["crop_row_start"], tuple(bound["source_shape"])))
            return None, {"tile_index": index}
        with patch.object(S, "model_input", side_effect=record):
            iterator = S.iter_model_inputs(VirtualMovie(), plan)
            self.assertEqual(next(iterator)[1]["tile_index"], 0)
            plan["crop_row_start"] = 23
            plan["source_shape"][0] = 1
            rest = list(iterator)
        self.assertEqual([r[0] for r in seen], list(range(1053)))
        self.assertEqual(len(rest), 1052)
        self.assertTrue(all(r[1:] == (12, (24000, 512, 512)) for r in seen))

    def test_complete_panel_fixed_identity_order_and_single_handle(self):
        panel = {rid: {**mapping(), "recording_id": rid} for rid in reversed(S.RECORDINGS)}
        active, events = [], []
        @contextmanager
        def opener(rid):
            self.assertEqual(active, [])
            active.append(rid)
            events.append(("open", rid))
            try:
                yield VirtualMovie()
            finally:
                events.append(("close", active.pop()))
        def tiles(dataset, plan):
            for i in range(1053):
                yield None, (plan["recording_id"], i)
        with patch.object(S, "iter_model_inputs", side_effect=tiles):
            records = [record for _, record in S.iter_panel_inputs(opener, panel)]
        self.assertEqual(records, [(rid, i) for rid in S.RECORDINGS for i in range(1053)])
        self.assertEqual(events, [(kind, rid) for rid in S.RECORDINGS for kind in ("open", "close")])
        self.assertEqual(active, [])

    def test_panel_refuses_incomplete_or_mismatched_roster_before_open(self):
        panel = {rid: {**mapping(), "recording_id": rid} for rid in S.RECORDINGS}
        bad_panels = [{rid: row for rid, row in panel.items() if rid != S.RECORDINGS[-1]},
                      {**panel, "extra": mapping()},
                      {**panel, S.RECORDINGS[-1]: mapping()},
                      {**panel, S.RECORDINGS[-1]: None}]
        for bad in bad_panels:
            with self.subTest(keys=list(bad)), patch("builtins.open", side_effect=AssertionError("file opened")):
                with self.assertRaises(ValueError):
                    list(S.iter_panel_inputs(lambda _: self.fail("source opened"), bad))

    def test_panel_early_close_and_error_release_active_source(self):
        panel = {rid: {**mapping(), "recording_id": rid} for rid in S.RECORDINGS}
        closed = []
        @contextmanager
        def opener(rid):
            try:
                yield VirtualMovie()
            finally:
                closed.append(rid)
        def one_then_fail(dataset, plan):
            yield None, 0
            raise ValueError("injected reader error")
        with patch.object(S, "iter_model_inputs", side_effect=one_then_fail):
            stream = S.iter_panel_inputs(opener, panel)
            next(stream)
            stream.close()
            self.assertEqual(closed, [S.RECORDINGS[0]])
            with self.assertRaisesRegex(ValueError, "injected reader"):
                list(S.iter_panel_inputs(opener, panel))
        self.assertEqual(closed, [S.RECORDINGS[0], S.RECORDINGS[0]])


class OutputControls(unittest.TestCase):
    def outputs(self):
        seg = np.zeros((1, 416, 64, 64, 1), np.float32)
        for k in range(8):
            seg[0, 400+k, :, :, 0] = np.float32((k+1)/16)
            seg[0, 408+k, :, :, 0] = np.float32((k+1)/32)
        seg[0, 408, :, :, 0] = 0
        traces = np.broadcast_to(np.arange(1, 9, dtype=np.float32), (1, 396, 8)).copy()
        return seg, traces

    def test_distinct_raw_morphological_fields_and_source_joint_normalization(self):
        seg, traces = self.outputs()
        result = S.decode_outputs(seg, traces, 81)
        np.testing.assert_array_equal(result["raw_footprint_fields"][:, 0, 0], np.arange(1, 9)/16)
        np.testing.assert_array_equal(result["morphological_footprint_fields"][:, 0, 0], [0]+[k/32 for k in range(2, 9)])
        np.testing.assert_array_equal(result["raw_traces_time_roi"], traces[0])
        self.assertTrue(np.all(result["demo_display_traces_time_roi"][:, 0] == 0))
        np.testing.assert_allclose(result["demo_display_traces_time_roi"][0, 1:], np.arange(2, 9)/8.001, rtol=1e-7)
        self.assertEqual(traces[0, 0, 0], 1)
        self.assertEqual(seg[0, 401, 0, 0, 0], 0.125)
        result["raw_footprint_fields"][1] = 99
        result["raw_traces_time_roi"][0] = 99
        self.assertEqual(seg[0, 401, 0, 0, 0], 0.125)
        self.assertEqual(traces[0, 0, 0], 1)

    def test_trace_support_and_final_padding_are_not_interpolated(self):
        seg, trace = self.outputs()
        middle = S.decode_outputs(seg, trace, 81)
        np.testing.assert_array_equal(middle["trace_frame_indices_zero_based"], np.arange(402, 798))
        self.assertTrue(middle["trace_within_observed_interval"].all())
        last = S.decode_outputs(seg, trace, 1052)
        np.testing.assert_array_equal(last["trace_frame_indices_zero_based"], np.arange(4802, 5198))
        self.assertEqual(np.count_nonzero(last["trace_within_observed_interval"]), 198)
        self.assertEqual(last["raw_traces_time_roi"].shape, (396, 8))

    def test_zero_trace_safe_without_invented_amplitude(self):
        seg, trace = self.outputs()
        trace.fill(0)
        result = S.decode_outputs(seg, trace, 0)
        self.assertTrue(np.all(result["demo_display_traces_time_roi"] == 0))
        self.assertTrue(np.all(result["raw_traces_time_roi"] == 0))

    def test_wrong_shapes_nonfinite_and_negative_trace_refused(self):
        seg, trace = self.outputs()
        for badseg, badtrace in ((seg[:, :408], trace), (seg, trace[:, :395]),
                                 (seg.astype(complex), trace), (seg, trace.astype(complex))):
            with self.subTest(shapes=(badseg.shape, badtrace.shape)), self.assertRaises(ValueError):
                S.decode_outputs(badseg, badtrace, 0)
        for field, value in ((seg, np.nan), (trace, np.inf), (trace, -0.01)):
            saved = field.flat[0]
            field.flat[0] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                S.decode_outputs(seg, trace, 0)
            field.flat[0] = saved

    def test_output_dtype_is_not_silently_coerced(self):
        seg, trace = self.outputs()
        for dtype in (np.float64, np.float16, np.int32, np.uint16):
            for a, b in ((seg.astype(dtype), trace), (seg, trace.astype(dtype))):
                with self.subTest(dtype=dtype), self.assertRaisesRegex(ValueError, "float32"):
                    S.decode_outputs(a, b, 0)

    def test_negative_fields_cannot_cancel_and_large_positive_fields_stay_active(self):
        seg, trace = self.outputs()
        for index in (0, 400, 408):
            seg[0, index, 0, 0, 0] = -0.25
            seg[0, index, 0, 1, 0] = 0.25
            with self.subTest(index=index), self.assertRaisesRegex(ValueError, "negative"):
                S.decode_outputs(seg, trace, 0)
            seg[0, index, 0, 0, 0] = 0
        seg[0, 408:416, :, :, 0] = np.finfo(np.float32).max
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            result = S.decode_outputs(seg, trace, 0)
        self.assertTrue(np.all(result["demo_display_traces_time_roi"] > 0))


class FileControls(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.mapping = self.root / "mapping.json"
        self.mapping.write_text(json.dumps(mapping(shape=(5000, 512, 512), start=0, row=0, column=0)))
        self.movie = self.root / "source.h5"

    def tearDown(self):
        self.tmp.cleanup()

    def movie_fixture(self, **kwargs):
        with h5py.File(self.movie, "w") as source:
            dataset = source.create_dataset("data", shape=(5000, 512, 512), dtype="u2",
                                            chunks=kwargs.pop("chunks", (1, 512, 512)), fillvalue=7,
                                            **kwargs)
        self.assertLess(self.movie.stat().st_size, 65536)

    def test_real_hdf_and_npz_roundtrip_keeps_unqualified_mapping(self):
        self.movie_fixture()
        output = self.root / "tile.npz"
        report = S.export_tile(self.movie, self.mapping, 1052, output)
        with np.load(output, allow_pickle=False) as archive:
            self.assertEqual(set(archive.files), {"model_input", "receipt_utf8"})
            data = archive["model_input"]
            np.testing.assert_array_equal(data[0, :200, :, :, 0], 1)
            np.testing.assert_array_equal(data[0, 200:, :, :, 0], 0)
            self.assertEqual(json.loads(archive["receipt_utf8"].tobytes()), report)
        self.assertEqual(report["mapping_sha256"], hashlib.sha256(self.mapping.read_bytes()).hexdigest())
        self.assertEqual(report["scientific_qualification"], "unestablished")
        self.assertEqual(report["source_file_content_authentication"], "not_established")

    def test_actual_cli_success_and_overwrite_failure(self):
        self.movie_fixture()
        output = self.root / "cli.npz"
        command = [sys.executable, "-B", str(HERE / "streaming.py"), "--movie-hdf5", str(self.movie),
                   "--mapping", str(self.mapping), "--tile-index", "1052", "--output", str(output)]
        first = subprocess.run(command, text=True, capture_output=True, timeout=20)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(json.loads(first.stdout)["tile_index"], 1052)
        identity = hashlib.sha256(output.read_bytes()).hexdigest()
        second = subprocess.run(command, text=True, capture_output=True, timeout=20)
        self.assertNotEqual(second.returncode, 0)
        self.assertEqual(hashlib.sha256(output.read_bytes()).hexdigest(), identity)

    def test_output_alias_existing_output_and_dangling_symlink_refused(self):
        self.movie_fixture()
        for destination in (self.movie, self.mapping):
            original = destination.read_bytes()
            with self.subTest(destination=destination), self.assertRaisesRegex(ValueError, "already exists"):
                S.export_tile(self.movie, self.mapping, 1052, destination)
            self.assertEqual(destination.read_bytes(), original)
        alias = self.root / "alias.npz"
        alias.symlink_to(self.root / "missing")
        with self.assertRaisesRegex(ValueError, "already exists"):
            S.export_tile(self.movie, self.mapping, 1052, alias)
        self.assertTrue(alias.is_symlink())

    def test_symlink_inputs_refused(self):
        self.movie_fixture()
        for original, which in ((self.movie, "movie"), (self.mapping, "mapping")):
            alias = self.root / f"{which}-alias"
            alias.symlink_to(original)
            args = (alias, self.mapping) if which == "movie" else (self.movie, alias)
            with self.subTest(which=which), self.assertRaises(OSError):
                S.export_tile(*args, 1052, self.root / "unused.npz")
        self.assertFalse((self.root / "unused.npz").exists())

    def test_fifo_source_is_refused_without_waiting_for_a_writer(self):
        fifo = self.root / "unwritten-fifo"
        os.mkfifo(fifo)
        output = self.root / "never-created.npz"
        command = [sys.executable, "-B", str(HERE / "streaming.py"), "--movie-hdf5", str(fifo),
                   "--mapping", str(self.mapping), "--tile-index", "1052", "--output", str(output)]
        result = subprocess.run(command, text=True, capture_output=True, timeout=3)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ordinary source file required", result.stderr)
        self.assertFalse(output.exists())

    def test_mapping_bounded_duplicate_and_nonfinite_json_refused(self):
        for body in (b'{"a":1,"a":2}', b'{"a":NaN}', b' ' * 65537, b''):
            self.mapping.write_bytes(body)
            with self.subTest(body_length=len(body)), self.assertRaises(ValueError):
                S.read_mapping(self.mapping)

    def test_stable_mapping_capture_detects_changes(self):
        with self.assertRaisesRegex(ValueError, "changed during operation"):
            with S.ordinary_input(self.mapping):
                self.mapping.write_text("different mapping bytes")

    def test_missing_group_soft_external_and_virtual_dataset_refused(self):
        other = self.root / "other.h5"
        with h5py.File(other, "w") as f:
            f.create_dataset("actual", shape=(5000, 512, 512), dtype="u2", chunks=(1, 512, 512), fillvalue=7)
        for kind in ("missing", "group", "soft", "external", "virtual"):
            with self.subTest(kind=kind):
                with h5py.File(self.movie, "w") as f:
                    if kind == "group":
                        f.create_group("data")
                    elif kind == "soft":
                        f["data"] = h5py.SoftLink("missing")
                    elif kind == "external":
                        f["data"] = h5py.ExternalLink(str(other), "actual")
                    elif kind == "virtual":
                        layout = h5py.VirtualLayout((5000, 512, 512), dtype="u2")
                        layout[:] = h5py.VirtualSource(str(other), "actual", shape=(5000, 512, 512))
                        f.create_virtual_dataset("data", layout)
                with self.assertRaises(ValueError):
                    S.export_tile(self.movie, self.mapping, 1052, self.root / "bad.npz")
                self.assertFalse((self.root / "bad.npz").exists())

    def test_external_raw_storage_refused(self):
        with h5py.File(self.movie, "w") as f:
            f.create_dataset("data", shape=(5000, 512, 512), dtype="u2",
                             external=[("unread.raw", 0, h5py.h5f.UNLIMITED)])
        with self.assertRaisesRegex(ValueError, "external"):
            S.export_tile(self.movie, self.mapping, 1052, self.root / "bad.npz")

    def test_nonoriginal_chunk_and_filter_layout_refused_before_slab_read(self):
        for options in ({"chunks": (400, 64, 64)}, {"compression": "gzip"}, {"shuffle": True}):
            with self.subTest(options=options):
                self.movie_fixture(**options)
                with patch.object(S, "model_input", side_effect=AssertionError("slab reader reached")):
                    with self.assertRaisesRegex(ValueError, "layout|chunk|filter|compress"):
                        S.export_tile(self.movie, self.mapping, 1052, self.root / "bad.npz")

    def test_partial_output_removed_on_write_failure(self):
        self.movie_fixture()
        destination = self.root / "partial.npz"
        def fail(target, **arrays):
            target.write(b"partial")
            raise OSError("injected disk error")
        with patch.object(S.np, "savez", side_effect=fail), self.assertRaisesRegex(OSError, "injected"):
            S.export_tile(self.movie, self.mapping, 1052, destination)
        self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
