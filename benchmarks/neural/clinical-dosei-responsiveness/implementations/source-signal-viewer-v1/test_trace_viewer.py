"""Generated renderer controls only; never actual source packets or EEG."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import unittest
import zlib

spec = importlib.util.spec_from_file_location("viewer", Path(__file__).with_name("trace_viewer.py"))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


def fixture(times=None):
    times = list(range(-1000, 0, 4)) if times is None else times
    values = [[float((i % 35)-17), float(8-(i % 17))] if i % 2 == 0 else [None, None]
              for i in range(len(times))]
    masks = [[value is not None for value in pair] for pair in values]
    packet = {"schema": "dosei_paired_observation_v1", "condition": "native_marker_relative_30s_v1",
              "case_id": "a"*64, "channels": ["Intellivue/EEG_1", "Intellivue/EEG_2"],
              "units": "microvolt", "interval_ms": [-30000, 0], "relative_time_ms": list(times),
              "values_uv": values, "observation_mask": masks,
              "source_endpoint_mask": [[False, False] for _ in times],
              "coverage": {"source_prefix_missing_ms": 29000 if times else 30000,
                           "full_interval_recorded": False, "row_count": len(times)}}
    return packet


def profile(packet):
    # A generated shape fixture, not proof that these synthetic rows are real.
    return {"schema": "dosei_renderer_source_profile_v1", "source_proof_sha256": m.SOURCE_PROOF,
            "source_cohort_sha256": m.SOURCE_COHORT, "array_identity_binding_sha256": "b"*64,
            "case_id": packet["case_id"],
            "observation_sha256": hashlib.sha256(m.canonical_packet(packet)).hexdigest(),
            "source_quality_values": [[0, 1, 16], [0, 1, 16]], "display_policy": m.POLICY}


def png_pixels(raw):
    assert raw[:8] == b"\x89PNG\r\n\x1a\n"
    offset = 8; chunks = []; compressed = b""
    while offset < len(raw):
        size = struct.unpack(">I", raw[offset:offset+4])[0]
        kind, body = raw[offset+4:offset+8], raw[offset+8:offset+8+size]
        assert zlib.crc32(kind+body) == struct.unpack(">I", raw[offset+8+size:offset+12+size])[0]
        if kind == b"IHDR": assert struct.unpack(">IIBBBBB", body) == (m.WIDTH, m.HEIGHT, 8, 2, 0, 0, 0)
        if kind == b"IDAT": compressed += body
        chunks.append(kind); offset += size+12
    assert offset == len(raw) and chunks == [b"IHDR", b"IDAT", b"IEND"]
    pixels = zlib.decompress(compressed)
    assert len(pixels) == m.HEIGHT*(m.WIDTH*3+1)
    assert all(pixels[row*(m.WIDTH*3+1)] == 0 for row in range(m.HEIGHT))
    return pixels


class Viewer(unittest.TestCase):
    def test_sparse_connections_preserve_points_and_blank_strip(self):
        packet = fixture([-20, -16, -12, -8, -4])
        m.validate_packet(packet)
        points, lines, blanks = m.geometry(packet, -20, 0)
        self.assertEqual([row[0] for row in points[0]], [-20, -12, -4])
        self.assertEqual([(row[0], row[2]) for row in lines[0]], [(-20, -12), (-12, -4)])
        self.assertEqual(blanks[0], [-16, -8])
        self.assertEqual(len(packet["relative_time_ms"]), 5)

    def test_duplicate_long_gap_endpoint_and_view_edges_break_lines(self):
        packet = fixture([-24, -20, -20, -16, -12, -8, -4])
        # Consecutive visible observations bracket a repeated table timestamp.
        packet["values_uv"] = [[1.0, 2.0] for _ in range(7)]
        packet["observation_mask"] = [[True, True] for _ in range(7)]
        points, lines, _ = m.geometry(packet, -24, 0)
        self.assertFalse(any(a == b for a, _, b, _ in lines[0]))
        self.assertEqual(len(points[0]), 7)
        packet["source_endpoint_mask"][3][0] = True; packet["values_uv"][3][0] = 187.5
        _, lines, _ = m.geometry(packet, -24, 0)
        self.assertFalse(any(a == -16 or b == -16 for a, _, b, _ in lines[0]))
        packet = fixture([-20, -16, -12, -8, -4])
        packet["values_uv"][2] = [None, None]; packet["observation_mask"][2] = [False, False]
        _, lines, _ = m.geometry(packet, -20, 0)
        self.assertEqual(lines[0], [])
        _, lines, _ = m.geometry(fixture([-20, -16, -12, -8, -4]), -16, -4)
        self.assertEqual(lines[0], [])

    def test_profile_required_without_visual_fallback(self):
        packet = fixture()
        for change in ({"source_proof_sha256": "f"*64}, {"display_policy": "points_only"},
                       {"case_id": "c"*64}, {"observation_sha256": "d"*64},
                       {"source_quality_values": [[False, 1, 16], [0, 1, 16]]},
                       {"array_identity_binding_sha256": None}):
            p = profile(packet); p.update(change)
            with self.assertRaises(m.ViewerRefusal): m.TraceViewer(packet, p)
        with self.assertRaises(m.ViewerRefusal): m.TraceViewer(packet, {})

    def test_typed_zoom_gain_preserve_input_and_exclude_arbitrary_tools(self):
        packet = fixture(); before = copy.deepcopy(packet)
        view = m.TraceViewer(packet, profile(packet))
        _, receipt = view.action({"action": "window", "start_ms": -1000, "end_ms": 0})
        self.assertEqual(receipt["window_ms"], [-1000, 0])
        _, receipt = view.action({"action": "gain", "limit_uv": 25})
        self.assertEqual(receipt["gain_limit_uv"], 25)
        self.assertEqual(packet, before)
        for command in ({"action": "execute", "code": "1+1"}, {"action": "filter"},
                        {"action": "view", "path": "/private"},
                        {"action": "window", "start_ms": -20, "end_ms": 1},
                        {"action": "gain", "limit_uv": True}):
            with self.assertRaises(m.ViewerRefusal): view.action(command)
        self.assertEqual((view.start, view.end, view.gain), (-1000, 0, 25))

    def test_png_integrity_calibration_and_explicit_gain_clipping(self):
        packet = fixture(); packet["values_uv"][0][0] = 187.5; packet["source_endpoint_mask"][0][0] = True
        view = m.TraceViewer(packet, profile(packet))
        raw, receipt = view.action({"action": "window", "start_ms": -1000, "end_ms": 0})
        pixels = png_pixels(raw)
        self.assertLess(len(raw), 2097152)
        self.assertIn(bytes((190, 85, 0)), pixels)
        self.assertFalse(receipt["source_provenance_authenticated_by_renderer"])
        self.assertEqual(receipt["units"], "microvolt")
        _, clipped = view.action({"action": "gain", "limit_uv": 25})
        self.assertEqual(clipped["clipped_at_view_gain"], [True, False])
        self.assertFalse(clipped["source_values_changed"])

    def test_empty_missing_and_endpoint_packets_do_not_disappear(self):
        for packet in (fixture([]), fixture([-8, -4])):
            packet["values_uv"] = [[None, None] for _ in packet["relative_time_ms"]]
            packet["observation_mask"] = [[False, False] for _ in packet["relative_time_ms"]]
            raw, receipt = m.TraceViewer(packet, profile(packet)).action({"action": "view"})
            png_pixels(raw)
            self.assertEqual(receipt["case_id"], packet["case_id"])

    def test_packet_clock_masks_and_private_field_refusals(self):
        for change in ("private", "time", "nan", "flag", "boolinterval", "shape"):
            packet = fixture()
            if change == "private": packet["target"] = 3
            if change == "time": packet["relative_time_ms"][1] += 1
            if change == "nan": packet["values_uv"][0][0] = float("nan")
            if change == "flag": packet["source_endpoint_mask"][1][0] = True
            if change == "boolinterval": packet["interval_ms"][1] = False
            if change == "shape": packet["observation_mask"].pop()
            with self.assertRaises(m.ViewerRefusal): m.validate_packet(packet)

    def test_complete_maximum_window_and_duplicate_rows_render_bounded(self):
        times = [-30000+4*i-(4 if i >= 3750 else 0) for i in range(7501)]
        packet = fixture(times)
        packet["coverage"] = {"source_prefix_missing_ms": 0, "full_interval_recorded": True,
                              "row_count": 7501}
        view = m.TraceViewer(packet, profile(packet))
        raw, receipt = view.action({"action": "view"})
        png_pixels(raw)
        self.assertEqual(receipt["window_ms"], [-30000, 0])
        self.assertLess(len(raw), 2097152)
        self.assertEqual(len(packet["relative_time_ms"]), 7501)

    def test_gain_clips_original_segment_geometry_without_vertex_clamping(self):
        self.assertEqual(m.clip_display_segment(-1000, 100.0, -996, -100.0, 25),
                         (-998.5, 25.0, -997.5, -25.0))
        self.assertEqual(m.clip_display_segment(-1000, -100.0, -996, 100.0, 25),
                         (-998.5, -25.0, -997.5, 25.0))
        self.assertEqual(m.clip_display_segment(-8, 0.0, -4, 100.0, 25), (-8.0, 0.0, -7.0, 25.0))
        self.assertIsNone(m.clip_display_segment(-8, 100.0, -4, 101.0, 25))
        self.assertIsNone(m.clip_display_segment(-8, -100.0, -4, -101.0, 25))
        self.assertEqual(m.clip_display_segment(-8, 10.0, -4, 10.0, 25), (-8, 10.0, -4, 10.0))


if __name__ == "__main__": unittest.main()
