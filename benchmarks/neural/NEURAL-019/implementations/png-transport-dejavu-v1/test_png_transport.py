"""New generated controls only. PNGs remain in memory; no authentic packets."""
import argparse
import base64
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import struct
import unittest

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("png_transport", HERE / "png_transport.py")
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
VIEWER_PATH = None
FONT_PATH = None


def generated():
    page = np.zeros((140, 137), dtype=np.uint16)
    page[0, 0], page[139, 136] = 3, 65535
    groups = np.arange(1340, dtype=np.int64) % 28
    velocity = np.zeros((1340, 140, 2), dtype=np.float64)
    velocity[-1, -1] = [-0.125, 0.0625]
    return dict(train_counts=np.broadcast_to(page, (1340, 140, 137)),
                assessment_counts=np.broadcast_to(page, (126, 140, 137)), train_velocity=velocity,
                train_trial_ids=np.asarray([f"generated-train-{i}" for i in range(1340)]),
                assessment_trial_ids=np.asarray([f"generated-query-{i}" for i in range(126)]),
                neural_unit_ids=np.asarray([f"generated-unit-{i}" for i in range(137)]),
                train_group_ids=groups, train_cv_fold_ids=groups % 4,
                neural_left_edges_ms=np.arange(-250, 450, 5), velocity_left_edges_ms=np.arange(-150, 550, 5),
                velocity_axes=np.asarray(["x", "y"]), velocity_units=np.asarray("m/s"),
                panel_fingerprint=np.asarray("a" * 64))


def view(role="assessment", trial=125, **kw):
    return dict(dict(action="view", role=role, trial=trial, unit_start=121, unit_stop=137,
                     bin_start=120, bin_stop=140), **kw)


def answer(trial):
    return dict(action="answer", trial=trial, velocity=[[trial - 63.5, -b / 8] for b in range(140)])


class NewControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.viewer = p.load_viewer(VIEWER_PATH)
        cls.font = Path(FONT_PATH).read_bytes()
        cls.renderer = p.Renderer(cls.font)
        cls.data = generated()

    def setUp(self):
        self.session = self.viewer.Session(self.data, max_actions=300)
        self.now = [0.0]
        self.transport = p.Transport(self.session, self.renderer, session_id="a" * 64,
                                     max_frames=300, deadline=100, clock=lambda: self.now[0])

    def raw(self, request, sequence=None, session_id="a" * 64):
        return p.encode(dict(session=session_id, sequence=self.transport._sequence if sequence is None else sequence,
                             request=request))

    def send(self, request, **kw):
        return json.loads(self.transport.exchange(self.raw(request, **kw)))

    def svg(self, **kw):
        return self.session.dispatch(p.encode(view(**kw)))

    def test_actual_png_and_full_crop_mechanics(self):
        result = self.svg()
        a, record = self.renderer.render(result)
        b, repeat = self.renderer.render(result)
        self.assertEqual(a, b)
        self.assertEqual(record, repeat)
        self.assertEqual(record["count_cells"], 320)
        self.assertEqual(record["svg_sha256"], p.pin(result["svg"].encode()))
        im = Image.open(io.BytesIO(a))
        im.load()
        self.assertEqual((im.mode, im.size), ("RGB", (1180, 528)))
        # Last unit/bin's five digits have visible ink inside the exact final cell.
        glyph = np.asarray(im.crop((1119, 457, 1165, 473)))
        self.assertGreater(int(np.all(glyph == 0, axis=2).sum()), 5)
        self.assertFalse(record["authentic_readability_qualified"])

    def test_png_only_payload_no_text_chunks_or_signal_numbers(self):
        frame = self.send(view())
        response = frame["response"]
        self.assertEqual(set(response), {"kind", "media_type", "png_base64", "width", "height", "role", "trial", "unit_range", "bin_range"})
        png = base64.b64decode(response["png_base64"], validate=True)
        chunks, offset = [], 8
        while offset < len(png):
            length = struct.unpack(">I", png[offset:offset + 4])[0]
            chunks.append(png[offset + 4:offset + 8])
            offset += 12 + length
        self.assertEqual(offset, len(png))
        self.assertEqual(set(chunks), {b"IHDR", b"IDAT", b"IEND"})
        self.assertEqual(self.transport.receipt()["delivered_images"], 1)
        self.assertNotIn("svg", response)

    def test_last_calibration_two_clocks_and_signed_values(self):
        result = self.svg(role="calibration", trial=1339)
        self.assertIn('data-calibration-bin="139">545 | -0.125 | 0.0625', result["svg"])
        self.assertIn('y="86">445</text>', result["svg"])
        png, record = self.renderer.render(result)
        self.assertEqual((record["width"], record["height"], record["count_cells"]), (1180, 928, 320))
        self.assertGreater(len(png), 1000)

    def test_first_coordinates_and_zero_nonzero_cells(self):
        result = self.svg(trial=0, unit_start=0, unit_stop=1, bin_start=0, bin_stop=1)
        self.assertIn('data-bin="0" data-unit="0">3</text>', result["svg"])
        _, record = self.renderer.render(result)
        self.assertEqual((record["width"], record["height"], record["count_cells"]), (760, 168, 1))

    def test_declared_subset_rejects_external_or_extra_primitives(self):
        result = self.svg()
        replacements = [("<svg ", '<svg onload="bad" '), ("</g>", '<script>x</script></g>'),
                        ("</g>", '<image href="file:///tmp/a"/></g>'),
                        ("<svg ", '<!DOCTYPE svg><svg '),
                        ('data-unit="136"', 'data-unit="135"')]
        for old, new in replacements:
            with self.subTest(new=new):
                bad = dict(result, svg=result["svg"].replace(old, new, 1))
                with self.assertRaises(ValueError):
                    self.renderer.render(bad)

    def test_whole_canvas_and_neighbor_cell_clipping_refused(self):
        result = self.svg(role="calibration", trial=1339, unit_start=136, unit_stop=137,
                          bin_start=139, bin_stop=140)
        # Valid source grammar can still exceed the short crop's pixel width.
        bad = dict(result, svg=result["svg"].replace("Training group 23;", "Training group " + "W" * 64 + ";"))
        with self.assertRaisesRegex(ValueError, "Glyph extent"):
            self.renderer.render(bad)
        original = self.renderer._font
        class WiderFont:
            # Exercise the real measured cell-boundary check without changing source geometry.
            def __getattr__(self, key):
                return getattr(original, key)
            def getbbox(self, text, *a, **kw):
                box = original.getbbox(text, *a, **kw)
                return (box[0], box[1], box[2] + (60 if text == "65535" else 0), box[3])
        self.renderer._font = WiderFont()
        try:
            with self.assertRaisesRegex(ValueError, "Glyph extent"):
                self.renderer.render(result)
        finally:
            self.renderer._font = original

    def test_unsupported_glyph_and_count_inconsistency_refused(self):
        result = self.svg(role="calibration", trial=1339)
        for svg in (result["svg"].replace("Training group 23;", "Training group Ω;"),
                    result["svg"].replace('>65535</text>', '>65536</text>')):
            with self.assertRaises(ValueError):
                self.renderer.render(dict(result, svg=svg))
        with self.assertRaises(ValueError):
            p.Renderer(self.font[:-1] + b"x")
        with self.assertRaises(ValueError):
            p.load_viewer(HERE / "png_transport.py")

    def test_session_sequence_utf8_and_duplicate_key_controls(self):
        first = self.raw(view())
        self.transport.exchange(first)
        with self.assertRaises(ValueError):
            self.transport.exchange(first)
        with self.assertRaises(ValueError):
            self.send(view(), session_id="b" * 64)
        for encoding in ("utf-16", "utf-32"):
            with self.assertRaises(ValueError):
                self.transport.exchange(self.raw(view()).decode().encode(encoding))
        raw = self.raw(view()).replace(b'"sequence":1', b'"sequence":1,"sequence":1')
        with self.assertRaises(ValueError):
            self.transport.exchange(raw)
        self.assertEqual(self.transport._sequence, 1)
        self.assertEqual(self.transport.receipt()["frame_attempts"], 6)
        self.assertEqual(self.transport.events()[-1]["status"], "refused")

    def test_complete_all_126_trajectories_unchanged_export(self):
        for trial in range(126):
            self.assertEqual(self.send(answer(trial))["response"]["answered"], trial + 1)
        self.assertEqual(self.send(dict(action="finish"))["response"]["velocity_values"], 35280)
        values, receipt = self.transport.export()
        self.assertEqual(set(values), {"velocity", "trial_ids", "velocity_left_edges_ms", "velocity_axes", "velocity_units", "panel_fingerprint"})
        self.assertEqual(values["velocity"].shape, (126, 140, 2))
        self.assertEqual(values["velocity"][125, 139].tolist(), [61.5, -17.375])
        self.assertTrue(receipt["source"]["closed"])
        self.assertFalse(receipt["scientific_mode_selected"])
        self.assertFalse(receipt["participant_isolation_qualified"])

    def test_incomplete_and_first_final_behavior_through_frames(self):
        with self.assertRaises(ValueError):
            self.transport.export()
        self.send(answer(0))
        with self.assertRaises(ValueError):
            self.send(answer(0))
        with self.assertRaises(ValueError):
            self.send(dict(action="finish"))
        self.assertEqual(self.session.receipt()["answered"], 1)

    def test_deadline_before_and_after_render_and_answer(self):
        self.now[0] = 100
        with self.assertRaises(ValueError):
            self.send(view())
        self.assertTrue(self.transport.receipt()["invalidated"])
        for action in (view(), answer(0)):
            session = self.viewer.Session(self.data, max_actions=300)
            times = iter([0, 0, 101])
            transport = p.Transport(session, self.renderer, session_id="a" * 64, max_frames=300,
                                    deadline=100, clock=lambda: next(times, 101))
            with self.assertRaises(ValueError):
                transport.exchange(p.encode(dict(session="a" * 64, sequence=0, request=action)))
            self.assertTrue(transport.receipt()["invalidated"])
            with self.assertRaises(ValueError):
                transport.export()
        class SlowRenderer:
            profile = self.renderer.profile
            def render(_, result):
                png = self.renderer.render(result)
                self.now[0] = 101
                return png
        self.now[0] = 0
        transport = p.Transport(self.viewer.Session(self.data, max_actions=300), SlowRenderer(),
                                session_id="a" * 64, max_frames=300, deadline=100, clock=lambda: self.now[0])
        with self.assertRaises(ValueError):
            transport.exchange(p.encode(dict(session="a" * 64, sequence=0, request=view())))
        self.assertEqual(transport.receipt()["delivered_images"], 0)
        self.assertTrue(transport.receipt()["invalidated"])

    def test_renderer_failure_never_returns_svg_or_numeric_fallback(self):
        class Refuse:
            profile = self.renderer.profile
            def render(_, result):
                raise ValueError("Generated unreadable image")
        self.transport._renderer = Refuse()
        with self.assertRaisesRegex(ValueError, "no SVG or numeric fallback"):
            self.send(view())
        self.assertEqual(self.transport.receipt()["delivered_images"], 0)
        self.assertNotIn("svg", json.dumps(self.transport.events()))
        with self.assertRaises(ValueError):
            self.transport.export()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--viewer", type=Path, required=True)
    parser.add_argument("--font", type=Path, required=True)
    args = parser.parse_args()
    VIEWER_PATH, FONT_PATH = args.viewer, args.font
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(NewControls)
    outcome = unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps({"renderer_profile": NewControls.renderer.profile, "generated_only": True,
                      "png_files_written": 0, "new_controls": outcome.testsRun}, sort_keys=True))
    raise SystemExit(not outcome.wasSuccessful())
