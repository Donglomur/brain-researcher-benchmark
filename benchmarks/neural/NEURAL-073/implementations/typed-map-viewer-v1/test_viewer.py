"""Generated in-memory controls only; no authentic map or source catalogue I/O."""
import base64
import dataclasses
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import unittest
import xml.etree.ElementTree as ET
import zlib

spec = importlib.util.spec_from_file_location("n073_typed_viewer", Path(__file__).with_name("viewer.py"))
v = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = v
spec.loader.exec_module(v)

SHAPE = (4, 5, 16)
AFFINE = ((2., .2, 0., -10.), (0., 3., .1, 4.), (0., 0., -4., 5.), (0., 0., 0., 1.))
KEYS = ("0" * 31 + "1", "0" * 31 + "2")
LABELS = tuple("protocol_%02d" % i for i in range(25))


def limits(**changes):
    return dataclasses.replace(v.Limits(10000, 10000, 100000, 50000, 100, 60), **changes)


def image(values=None, shape=SHAPE, affine=AFFINE, units="mm"):
    if values is None:
        values = [0.] * (shape[0] * shape[1] * shape[2])
    body = b"".join(struct.pack("<d", n) for n in values)
    return v.CanonicalMap(body, shape, affine, units, hashlib.sha256(body).hexdigest())


def roster_digest(keys):
    return hashlib.sha256(json.dumps(list(keys), separators=(",", ":")).encode()).hexdigest()


def session(keys=KEYS, loader=None, selected=None, clock=None):
    kwargs = {} if clock is None else {"clock": clock}
    return v.ViewerSession(case_ids=keys, roster_sha256=roster_digest(keys),
                           class_labels=LABELS, ontology_sha256=roster_digest(LABELS),
                           loader=loader or (lambda key: image()),
                           limits=selected or limits(), **kwargs)


def render(map_, axis, index, selected=None, low=-1., high=1.):
    selected = selected or limits()
    map_.validate(selected)
    return v.render_slice(map_, axis=axis, index=index, low=low, high=high,
                          limits=selected, check_deadline=lambda: None)


def decode_png(svg):
    root = ET.fromstring(svg)
    image_node = root.find("{http://www.w3.org/2000/svg}image")
    url = image_node.attrib["href"]
    assert url.startswith("data:image/png;base64,")
    raw = base64.b64decode(url.split(",", 1)[1], validate=True)
    assert raw[:8] == b"\x89PNG\r\n\x1a\n"
    pos, kinds, payload, width, height = 8, [], b"", None, None
    while pos < len(raw):
        size = struct.unpack_from(">I", raw, pos)[0]
        kind, content = raw[pos+4:pos+8], raw[pos+8:pos+8+size]
        crc = struct.unpack_from(">I", raw, pos+8+size)[0]
        assert crc == zlib.crc32(kind+content) & 0xFFFFFFFF
        kinds.append(kind)
        if kind == b"IHDR":
            width, height, bits, color, c, f, interlace = struct.unpack(">IIBBBBB", content)
            assert (bits, color, c, f, interlace) == (8, 2, 0, 0, 0)
        elif kind == b"IDAT":
            payload += content
        pos += size+12
    assert pos == len(raw) and kinds == [b"IHDR", b"IDAT", b"IEND"]
    pixels = zlib.decompress(payload)
    assert len(pixels) == height * (1+3*width)
    rows = []
    for y in range(height):
        row = pixels[y*(1+3*width):(y+1)*(1+3*width)]
        assert row[0] == 0
        rows.append([tuple(row[1+3*x:4+3*x]) for x in range(width)])
    return width, height, rows


class ViewerChecks(unittest.TestCase):
    def test_native_planes_non_cubic_coordinate_oracle(self):
        values = [0.] * 320
        values[263] = 1.  # explicit C-order coordinate (3,1,7)
        values[79] = -1.  # explicit C-order coordinate (0,4,15)
        map_ = image(values)
        expected = {0: (5, 16, 3, (1, 8)),
                    1: (4, 16, 1, (3, 8)),
                    2: (4, 5, 7, (3, 3))}
        for axis, (width, height, index, red) in expected.items():
            svg = render(map_, axis, index)
            w, h, rows = decode_png(svg)
            self.assertEqual((w, h), (width, height))
            reds = [(x, y) for y, row in enumerate(rows) for x, color in enumerate(row)
                    if color == (255, 0, 0)]
            self.assertEqual(reds, [red])
            self.assertIn("no anatomical relabeling", svg)
            self.assertIn("2,0.20000000000000001,0,-10", svg)
        w, h, rows = decode_png(render(map_, 2, 15))
        self.assertEqual(rows[0][0], (0, 0, 255))
        self.assertEqual(rows[4][3], (255, 255, 255))

    def test_all_native_slices_accessible_without_sampling(self):
        map_ = image()
        total_pixels = 0
        for axis, count in enumerate(SHAPE):
            for index in range(count):
                w, h, rows = decode_png(render(map_, axis, index))
                self.assertTrue(all(c == (255, 255, 255) for row in rows for c in row))
                total_pixels += w * h
        self.assertEqual(total_pixels, 3 * 320)

    def test_map_identity_extent_finiteness_and_geometry_refused(self):
        good = image()
        invalid = [dataclasses.replace(good, sha256="a"*64),
                   dataclasses.replace(good, body=good.body[:-1]),
                   dataclasses.replace(good, body=bytearray(good.body)),
                   dataclasses.replace(good, shape=(True, 5, 64)),
                   dataclasses.replace(good, affine=((0,0,0,0),)*3+((0,0,0,1),)),
                   dataclasses.replace(good, units="<script>"),
                   image([float("nan")]+[0.]*319)]
        for bad in invalid:
            with self.subTest(bad=repr(bad)[:70]), self.assertRaises(v.ViewerError):
                bad.validate(limits())

    def test_complete_plane_and_svg_limits_fail_without_cropping(self):
        with self.assertRaisesRegex(v.ViewerError, "complete native planes"):
            image().validate(limits(max_plane_pixels=79))
        with self.assertRaisesRegex(v.ViewerError, "complete frame"):
            render(image(), 0, 0, limits(max_svg_bytes=1000))

    def test_exact_typed_indices_windows_and_no_metadata_fields(self):
        s = session()
        base = {"action":"slice", "case_id":KEYS[0], "axis":2, "index":0, "low":-1., "high":1.}
        variants = [dict(base, axis=True), dict(base, axis="axial"), dict(base, index=-1),
                    dict(base, index=16), dict(base, high=float("inf")), dict(base, low=1.),
                    dict(base, path="/private/answer-label.nii"), dict(base, case_id=KEYS[1])]
        for request in variants:
            with self.assertRaises(v.ViewerError):
                s.dispatch(request)
        self.assertEqual(s._actions, len(variants))

    def test_display_clipping_and_extreme_finite_window(self):
        values = [-100., 0., 100.]+[0.]*317
        _, _, rows = decode_png(render(image(values), 1, 0))
        # Axis1 plane: horizontal axis0, vertical axis2, so first three C-order
        # values are at image rows15,14,13 of column0.
        self.assertEqual(rows[15][0], (0,0,255))
        self.assertEqual(rows[14][0], (255,255,255))
        self.assertEqual(rows[13][0], (255,0,0))
        _, _, rows = decode_png(render(image(), 2, 0, low=-1e308, high=1e308))
        self.assertTrue(all(c == (255,255,255) for row in rows for c in row))

    def test_no_label_filename_digest_or_ancillary_png_projection(self):
        secret = "PRIVATE_TASK_FILENAME_AND_LABEL"
        def loader(key):
            unused_operator_metadata = secret
            return image()
        s = session(loader=loader)
        description = s.dispatch({"action":"describe"})
        frame = s.dispatch({"action":"slice", "case_id":KEYS[0], "axis":2,
                            "index":0, "low":-1, "high":1})
        rendered = json.dumps([description,frame])
        self.assertNotIn(secret, rendered)
        self.assertNotIn(image().sha256, rendered)
        self.assertNotIn("body", frame)
        decode_png(frame["svg"])
        bad = session(loader=lambda key: (_ for _ in ()).throw(RuntimeError(secret)))
        with self.assertRaises(v.ViewerError) as caught:
            bad.dispatch({"action":"describe"})
        self.assertEqual(str(caught.exception), "operator map unavailable")

    def test_blinded_roster_exact_digest_and_duplicates(self):
        for keys, expected in [(KEYS, "0"*64), ((KEYS[0], KEYS[0]), roster_digest((KEYS[0], KEYS[0]))),
                               (("sub-01_task-known",), roster_digest(("sub-01_task-known",)))]:
            with self.assertRaises(v.ViewerError):
                v.ViewerSession(case_ids=keys, roster_sha256=expected,
                                class_labels=LABELS, ontology_sha256=roster_digest(LABELS),
                                loader=lambda key:image(), limits=limits())

    def test_public_class_order_is_explicit_bound_and_not_refreshable(self):
        s = session()
        description = s.dispatch({"action":"describe"})
        self.assertEqual(description["class_labels"], list(LABELS))
        self.assertEqual(description["ontology_sha256"], roster_digest(LABELS))
        description["class_labels"].reverse()
        self.assertEqual(s.dispatch({"action":"describe"})["class_labels"], list(LABELS))
        for labels, pin in [(LABELS[::-1], roster_digest(LABELS)),
                            ((LABELS[0],)*25, roster_digest((LABELS[0],)*25)),
                            (("<script>",)+LABELS[1:], roster_digest(("<script>",)+LABELS[1:]))]:
            with self.assertRaises(v.ViewerError):
                v.ViewerSession(case_ids=KEYS, roster_sha256=roster_digest(KEYS),
                                class_labels=labels, ontology_sha256=pin,
                                loader=lambda key:image(), limits=limits())

    def test_response_is_immutable_and_duplicate_or_wrong_case_refused(self):
        s = session()
        probabilities = [1.]+[0.]*24
        s.dispatch({"action":"answer", "case_id":KEYS[0], "probabilities":probabilities})
        probabilities[0], probabilities[1] = 0., 1.
        with self.assertRaises(v.ViewerError):
            s.dispatch({"action":"answer", "case_id":KEYS[0], "probabilities":None})
        with self.assertRaises(v.ViewerError):
            s.finish()
        s.dispatch({"action":"answer", "case_id":KEYS[1], "probabilities":None})
        result = s.finish()
        self.assertEqual(result["records"][0]["probabilities"], [1.]+[0.]*24)
        self.assertIsNone(result["records"][1]["probabilities"])
        self.assertEqual(hashlib.sha256(v.json_body(result["records"]).encode()).hexdigest(),
                         result["response_sha256"])
        self.assertFalse(result["scientific_qualification"])
        with self.assertRaisesRegex(v.ViewerError, "closed"):
            s.finish()

    def test_malformed_probability_vectors_retain_case(self):
        s = session()
        bad_values = [[0.]*25, [1.]+[0.]*23, [True]+[0.]*24,
                      [float("nan")]+[0.]*24, [1.1,-.1]+[0.]*23, tuple([.04]*25)]
        for value in bad_values:
            with self.assertRaises(v.ViewerError):
                s.dispatch({"action":"answer", "case_id":KEYS[0], "probabilities":value})
        self.assertEqual(s.dispatch({"action":"describe"})["case_id"], KEYS[0])

    def test_oversized_json_integers_are_typed_refusals_without_case_advance(self):
        s = session()
        huge = 10 ** 400
        with self.assertRaises(v.ViewerError):
            s.dispatch({"action":"slice", "case_id":KEYS[0], "axis":2,
                        "index":0, "low":-1, "high":huge})
        with self.assertRaises(v.ViewerError):
            s.dispatch({"action":"answer", "case_id":KEYS[0],
                        "probabilities":[huge]+[0.]*24})
        self.assertEqual(s.dispatch({"action":"describe"})["case_id"], KEYS[0])
        s.dispatch({"action":"answer", "case_id":KEYS[0], "probabilities":[1.]+[0.]*24})
        self.assertEqual(s.dispatch({"action":"describe"})["case_id"], KEYS[1])

    def test_failed_actions_and_frames_consume_selected_budgets(self):
        s = session(selected=limits(max_frames_per_case=1, max_actions=3))
        with self.assertRaises(v.ViewerError):
            s.dispatch({"action":"slice", "case_id":KEYS[0], "axis":2,
                        "index":99, "low":-1, "high":1})
        with self.assertRaisesRegex(v.ViewerError, "frame budget"):
            s.dispatch({"action":"slice", "case_id":KEYS[0], "axis":2,
                        "index":0, "low":-1, "high":1})
        with self.assertRaises(v.ViewerError):
            s.dispatch({"action":"malformed"})
        with self.assertRaisesRegex(v.ViewerError, "action budget"):
            s.dispatch({"action":"describe"})

    def test_operator_deadline_checked_after_loader_and_during_render(self):
        now = [0.]
        def slow_loader(key):
            now[0] = 61.
            return image()
        s = session(loader=slow_loader, clock=lambda:now[0])
        with self.assertRaisesRegex(v.ViewerError, "deadline"):
            s.dispatch({"action":"describe"})
        calls = [0]
        def clock():
            calls[0] += 1
            return float(calls[0])
        s = session(clock=clock, selected=limits(wall_seconds=10))
        with self.assertRaisesRegex(v.ViewerError, "deadline"):
            s.dispatch({"action":"slice", "case_id":KEYS[0], "axis":0,
                        "index":0, "low":-1, "high":1})

    def test_full_9532_key_collection_is_complete_and_no_gold_or_maps_read(self):
        keys = tuple(format(i, "032x") for i in range(9532))
        def no_map(key):
            raise AssertionError("abstention collection must not read maps")
        s = session(keys=keys, loader=no_map)
        for key in keys:
            s.dispatch({"action":"answer", "case_id":key, "probabilities":None})
        result = s.finish()
        self.assertEqual(len(result["records"]), 9532)
        self.assertEqual([r["case_id"] for r in result["records"]], list(keys))
        self.assertEqual(sum(result["frames_by_case"]), 0)
        self.assertEqual(result["actions"], 9532)
        self.assertFalse(result["full_catalogue_qualified"])
        self.assertFalse(result["isolated_transport_qualified"])


if __name__ == "__main__":
    unittest.main(verbosity=1)
