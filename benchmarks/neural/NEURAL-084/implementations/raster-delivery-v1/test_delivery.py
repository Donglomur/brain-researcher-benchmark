"""New generated raster/delivery controls; no authentic data or full-fold run."""
import copy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import struct
import sys
import unittest
import zlib

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("n084_raster_delivery", HERE / "delivery.py")
delivery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(delivery)
IMPL = Path(os.environ.get("NEURAL084_SOURCE_IMPLEMENTATIONS", str(HERE.parent)))
PANEL = IMPL / "full-panel-viewer-bridge-v1/panel.py"
VIEWER = IMPL / "typed-waveform-v1/viewer.py"
CANVAS = Path(os.environ.get("NEURAL084_CANVAS_SOURCE", str(HERE.parents[2] /
    "NEURAL-EXP-005/implementations/typed-raster-viewer-v1/viewer.py")))


def raw(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def qid(person, row):
    return f"{person * 100000 + row:064x}"


def donor_bytes():
    rows = []
    for person in range(2, 55):
        position = 0
        for session in (1, 2):
            for phase in ("train", "test"):
                for label in (1, 2, 3, 4):
                    for _ in range(25):
                        rows.append(dict(id=qid(person, position), person=person,
                                         session=session, phase=phase, label=label))
                        position += 1
    return raw(dict(schema="neural084_training_v1", rows=rows))


def pixels(png):
    """Independent PNG chunk/CRC/scanline reader for the emitted fixed RGB mode."""
    if png[:8] != b"\x89PNG\r\n\x1a\n":
        raise AssertionError("PNG signature")
    at, kinds, compressed = 8, [], bytearray()
    while at < len(png):
        n = struct.unpack(">I", png[at:at + 4])[0]
        kind, body = png[at + 4:at + 8], png[at + 8:at + 8 + n]
        crc = struct.unpack(">I", png[at + 8 + n:at + 12 + n])[0]
        if zlib.crc32(kind + body) != crc:
            raise AssertionError("PNG CRC")
        kinds.append(kind)
        if kind == b"IHDR":
            width, height, depth, color, compression, filtering, interlace = struct.unpack(">IIBBBBB", body)
            if (depth, color, compression, filtering, interlace) != (8, 2, 0, 0, 0):
                raise AssertionError("fixed RGB mode")
        if kind == b"IDAT":
            compressed.extend(body)
        at += n + 12
    if kinds != [b"IHDR", b"IDAT", b"IEND"] or at != len(png):
        raise AssertionError("no hidden SVG/text/ancillary chunks")
    decoded = zlib.decompress(compressed)
    stride = 1 + width * 3
    if len(decoded) != height * stride or any(decoded[y * stride] != 0 for y in range(height)):
        raise AssertionError("complete unfiltered scanlines")
    def pixel(x, y):
        offset = y * stride + 1 + x * 3
        return tuple(decoded[offset:offset + 3])
    return width, height, pixel


class DeliveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.training = donor_bytes()
        cls.folds = []
        for person in range(1, 55):
            pin = lambda path: dict(path=path, bytes=1, sha256="e" * 64)
            cls.folds.append(dict(schema="neural084_fold_v1", generation="generated-raster-controls-only",
                fold=f"fold{person:03d}", ids=[qid(person, i) for i in range(400)], classes=[1, 2, 3, 4],
                training=pin("training.npy"), queries=pin("queries.npy"),
                training_metadata=dict(path="training.json", bytes=len(cls.training),
                    sha256=hashlib.sha256(cls.training).hexdigest())))
        # Only fold001 opens. Other54-header metadata remain generated contract
        # fixtures, never a claim of authenticated donor bytes or full-fold run.
        cls.epoch = tuple(tuple((ch + 1) * math.sin(2 * math.pi * (5 + ch) * j / 100)
                               for j in range(400)) for ch in range(10))
        cls.viewer = delivery._load(VIEWER,
            (13035, "c3f7b05f1afd007096cbc31d0b5165fd9a6cbad26cbb07ce15e47cd6e2dce345"), "fixture_viewer")
        cls.canvas = delivery._canvas(CANVAS)

    def make(self, transport=None, limit=20000000):
        self.messages = []
        def capture(metadata, image):
            self.messages.append((json.loads(metadata), image))
            return True
        owner = delivery.RasterPanel(self.folds, transport or capture, max_requests=1000,
            max_capture_bytes=54 * 262144, max_delivery_bytes=limit, panel_source=PANEL,
            canvas_source=CANVAS, viewer_source=VIEWER, source_root=IMPL)
        owner.open_next(self.training, lambda _: self.epoch, lambda _: self.epoch)
        return owner

    def call(self, owner, action, **fields):
        return owner.dispatch(raw(dict(action=action, **fields)))

    def view(self, owner, channels=None, start=0, stop=400):
        return self.call(owner, "view", id=qid(1, 0), channels=channels or list(delivery.CHANNELS),
                         start=start, stop=stop)

    def frame(self, epoch=None, channels=None, start=0, stop=400):
        names = channels or list(delivery.CHANNELS)
        indices = [delivery.CHANNELS.index(c) for c in names]
        return dict(stage="query", id=qid(1, 0), kind="svg_waveform", channels=names,
                    start=start, stop=stop, svg=self.viewer._svg(epoch or self.epoch, indices,
                                                               start, stop, delivery.CHANNELS))

    def test_generated_full_and_zoom_png_delivery_has_no_svg_or_geometry(self):
        owner = self.make()
        self.call(owner, "begin_queries")
        self.view(owner)
        full, full_png = self.messages[-1]
        self.assertEqual((full["image"]["width"], full["image"]["height"]), (1000, 938))
        self.assertEqual(set(full["body"]), {"stage", "id", "channels", "start", "stop", "kind"})
        self.assertEqual(full["body"]["kind"], "png_waveform")
        self.assertEqual(hashlib.sha256(full_png).hexdigest(), full["image"]["sha256"])
        self.assertEqual(pixels(full_png)[:2], (1000, 938))
        self.view(owner, ["Pz", "Oz"], 120, 180)
        zoom, zoom_png = self.messages[-1]
        self.assertEqual(pixels(zoom_png)[:2], (1000, 250))
        self.assertEqual((zoom["body"]["start"], zoom["body"]["stop"], zoom["body"]["channels"]),
                         (120, 180, ["Pz", "Oz"]))
        for envelope, _ in self.messages:
            encoded = raw(envelope)
            for forbidden in (b"<svg", b"polyline", b"points", b"samples\":", b"scores\":"):
                self.assertNotIn(forbidden, encoded)
        target = os.environ.get("NEURAL084_RASTER_EVIDENCE")
        if target:
            root = Path(target)
            self.assertTrue(root.is_dir())
            for name, body in (("full-ten-channel.png", full_png), ("two-channel-zoom.png", zoom_png)):
                self.assertLessEqual(len(body), 131072)
                with (root / name).open("xb") as stream:
                    stream.write(body)

    def test_all400_selected_samples_and_original_common_bound_reach_pixels(self):
        epoch = tuple(tuple(10 if ch == 9 else (1 if j % 2 else -1) for j in range(400))
                      for ch in range(10))
        image, _, _ = delivery.rasterize(self.frame(epoch, ["P7", "O2"]), self.canvas)
        _, _, pixel = pixels(image)
        for j in range(400):
            x = round(112 + 868 * j / 399)
            self.assertEqual(pixel(x, 116 if j % 2 else 122), (18, 59, 115))
            self.assertEqual(pixel(x, 171), (18, 59, 115))
        zoom, _, _ = delivery.rasterize(self.frame(epoch, ["P7"], 0, 2), self.canvas)
        _, _, z = pixels(zoom)
        self.assertEqual(z(112, 122), (18, 59, 115))
        self.assertEqual(z(980, 116), (18, 59, 115))

    def test_public_training_last_row_and_query_retirement_are_preserved(self):
        owner = self.make()
        self.call(owner, "information")
        body = self.messages[-1][0]["body"]
        self.assertEqual((body["training_rows"], body["query_rows"], body["max_views_per_epoch"]), (21200, 400, 128))
        self.call(owner, "training", index=21199, channels=["O2"], start=398, stop=400)
        row = self.messages[-1][0]["body"]["row"]
        self.assertEqual((row["person"], row["session"], row["phase"], row["label"]), (54, 2, "test", 4))
        self.call(owner, "begin_queries")
        with self.assertRaisesRegex(ValueError, "retired"):
            self.call(owner, "training", index=0, channels=["P7"], start=0, stop=2)
        self.view(owner, ["P7"], 0, 2)
        self.assertNotIn("row", self.messages[-1][0]["body"])

    def test_first_final_response_and_partial_export_gate_survive_binding(self):
        owner = self.make()
        self.call(owner, "begin_queries")
        self.call(owner, "answer", id=qid(1, 0), scores=[-2, 3, 0, 0])
        self.assertEqual(self.messages[-1][0]["body"]["next_id"], qid(1, 1))
        with self.assertRaisesRegex(ValueError, "first-final"):
            self.call(owner, "answer", id=qid(1, 0), scores=[9, 0, 0, 0])
        with self.assertRaisesRegex(ValueError, "400"):
            self.call(owner, "finish")
        with self.assertRaisesRegex(ValueError, "all54"):
            owner.finish_collection()
        with self.assertRaisesRegex(ValueError, "complete acknowledged54"):
            owner.candidate_prediction("fold001")

    def assert_terminal(self, owner):
        for call in (lambda: self.call(owner, "information"), owner.finish_collection,
                     lambda: owner.open_next(self.training, lambda _: self.epoch, lambda _: self.epoch),
                     lambda: owner.candidate_prediction("fold001")):
            with self.assertRaises(ValueError):
                call()

    def test_render_failure_after_consumed_view_is_terminal(self):
        owner = self.make()
        self.call(owner, "begin_queries")
        owner._canvas._Canvas.png = lambda _: b"notPNG"
        with self.assertRaisesRegex(ValueError, "raster dimensions"):
            self.view(owner, ["P7"], 0, 2)
        self.assert_terminal(owner)
        self.assertEqual(len(self.messages), 1)

    def test_delivery_failure_and_false_ack_are_terminal_and_charged(self):
        for mode in ("false", "raise"):
            def reject(metadata, image):
                if mode == "raise":
                    raise OSError("generated sink disconnected")
                return False
            owner = self.make(reject)
            with self.assertRaises((OSError, ValueError)):
                self.call(owner, "information")
            self.assertGreater(owner._attempted, 0)
            self.assertEqual(owner._acknowledged, 0)
            self.assert_terminal(owner)

    def test_wire_budget_and_reentrant_sink_fail_without_export(self):
        owner = self.make(limit=1)
        with self.assertRaisesRegex(ValueError, "delivery byte allowance"):
            self.call(owner, "information")
        self.assert_terminal(owner)
        def nested(metadata, image):
            try:
                owner.dispatch(raw(dict(action="information")))
            except ValueError:
                pass
            return True
        owner = self.make(nested)
        with self.assertRaisesRegex(ValueError, "acknowledgement"):
            self.call(owner, "information")
        self.assert_terminal(owner)

    def test_strict_svg_rejects_external_markup_missing_samples_and_unknown_glyph(self):
        original = self.frame(channels=["P7"], start=0, stop=2)
        cases = [original["svg"].replace("<svg", '<!DOCTYPE svg><svg', 1),
                 original["svg"].replace('points="', 'onload="bad" points="', 1),
                 original["svg"].replace("physical unit unverified", "physical unit @nverified"),
                 original["svg"].replace("112,119 ", ""),
                 original["svg"].replace("112,119", "112,999999999"),
                 original["svg"].replace("980,", "979,", 1)]
        self.assertEqual(len(set(cases)), len(cases))
        for svg in cases:
            changed = dict(original, svg=svg)
            with self.assertRaises((ValueError, ETError)):
                delivery.rasterize(changed, self.canvas)


ETError = delivery.ET.ParseError


class BoundedLog:
    def __init__(self):
        self.count, self.exceeded = 0, False
    def write(self, text):
        body = text.encode("utf-8", "replace")
        keep = body[:max(0, 16000 - self.count)]
        sys.stdout.buffer.write(keep)
        self.count += len(keep)
        self.exceeded |= len(keep) != len(body)
    def flush(self):
        sys.stdout.flush()


if __name__ == "__main__":
    output = BoundedLog()
    suite = (unittest.defaultTestLoader.loadTestsFromNames(sys.argv[1:], sys.modules[__name__])
             if len(sys.argv) > 1 else unittest.defaultTestLoader.loadTestsFromTestCase(DeliveryTests))
    result = unittest.TextTestRunner(stream=output, verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() and not output.exceeded else 1)
