"""Generated controls for raster composition, never authentic EEG/model results.

The PNG decoder and geometric expectations below are independent of the raster
implementation. All signals, probabilities and labels are deliberately invented.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
import types
import unittest
import zlib

HERE = Path(__file__).resolve().parents[1]
PRESENTATION_SHA256 = "7a9f8ed31f5554c58c5cef13f23b446ddc59f707f7c1891faa849b7e69767613"
SECRET = b"GENERATED raster key only; not deployment"
SUCCESS_KEYS = {"case_id", "status", "endpoint_tick", "view_id", "representation",
                "image_mime_type", "image_png", "image_sha256"}
PREVIEW_LIMIT = 4 * 1024 * 1024


def load_module(name, path, expected_sha256=None):
    body = path.read_bytes()
    if expected_sha256 is not None:
        assert hashlib.sha256(body).hexdigest() == expected_sha256, str(path)
    module = types.ModuleType(name)
    module.__file__ = str(path)
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module


def decode_png(blob):
    """Strict independent RGB8 PNG parser with CRC, zlib and row checks."""
    assert type(blob) is bytes and blob[:8] == b"\x89PNG\r\n\x1a\n"
    cursor, kinds, compressed, dimensions = 8, [], bytearray(), None
    while cursor < len(blob):
        assert cursor + 12 <= len(blob)
        size = struct.unpack(">I", blob[cursor:cursor + 4])[0]
        kind = blob[cursor + 4:cursor + 8]
        stop = cursor + 8 + size
        assert stop + 4 <= len(blob)
        data = blob[cursor + 8:stop]
        assert struct.unpack(">I", blob[stop:stop + 4])[0] == zlib.crc32(kind + data) & 0xffffffff
        kinds.append(kind)
        if kind == b"IHDR":
            assert dimensions is None and size == 13
            width, height, depth, color, compression, filtering, interlace = struct.unpack(">IIBBBBB", data)
            assert width > 0 and height > 0 and (depth, color, compression, filtering, interlace) == (8, 2, 0, 0, 0)
            dimensions = width, height
        elif kind == b"IDAT":
            compressed.extend(data)
        elif kind == b"IEND":
            assert size == 0 and stop + 4 == len(blob)
        else:
            raise AssertionError("Unexpected PNG chunk, including textual metadata: " + repr(kind))
        cursor = stop + 4
    assert kinds[0] == b"IHDR" and kinds[-1] == b"IEND" and kinds.count(b"IHDR") == kinds.count(b"IEND") == 1
    assert b"IDAT" in kinds and dimensions is not None
    width, height = dimensions
    inflater = zlib.decompressobj()
    raw = inflater.decompress(bytes(compressed)) + inflater.flush()
    assert inflater.eof and not inflater.unused_data and not inflater.unconsumed_tail
    stride = width * 3 + 1
    assert len(raw) == stride * height
    assert all(raw[y * stride] == 0 for y in range(height))
    return width, height, b"".join(raw[y * stride + 1:(y + 1) * stride] for y in range(height))


def pixel(image, x, y):
    width, height, body = image
    assert 0 <= x < width and 0 <= y < height
    offset = (y * width + x) * 3
    return tuple(body[offset:offset + 3])


def crop(image, x, y, width, height):
    return tuple(pixel(image, xx, yy) for yy in range(y, y + height) for xx in range(x, x + width))


def has_ink(image, x, y, width, height):
    return any(p != (255, 255, 255) for p in crop(image, x, y, width, height))


def fixture(labels=("Fp1-F7",), *, ticks=2, rate=30, width=301, row_height=101,
            low=-10, high=10):
    channels = [{"index": i * 2, "label": label} for i, label in enumerate(labels)]
    rows = [{"recording_id": name, "biological_person": indexed["biological_person"],
             "native_sample_rate_hz": rate, "native_sample_count": ticks * rate // 10,
             "observed_ticks": ticks, "predictor_channels": channels}
            for name, indexed in sorted(INDEX.items())]
    support = {"schema": "neural009_public_support_v1", "task_id": "NEURAL-009",
               "source_index_sha256": INDEX_SHA, "folds": D.core._folds(PEOPLE), "records": rows}
    protocol = {"schema": "neural009_typed_svg_protocol_v1", "lookback_ticks": ticks,
                "width_px": width, "channel_height_px": row_height, "max_svg_bytes": 131072,
                "max_total_svg_bytes_per_record": 524288, "max_actions_per_record": ticks + 20,
                "max_views_per_tick": 4, "max_window_samples": ticks * rate // 10,
                "max_window_values": ticks * rate // 10 * len(labels),
                "scales_uv": {row["recording_id"]:
                    [{"index": channel["index"], "minimum": low, "maximum": high}
                     for channel in channels] for row in rows}}
    limits = {"max_record_ticks": ticks, "max_total_ticks": 686 * ticks,
              "max_prediction_segments": 686 * ticks}
    return support, protocol, limits


def raster_protocol(**overrides):
    result = {"schema": "neural009_causal_raster_v1", "gutter_px": 192,
              "header_px": 44, "footer_px": 20, "font_scale": 1,
              "max_image_pixels": 4194304, "max_png_bytes": PREVIEW_LIMIT,
              "max_total_png_bytes_per_record": PREVIEW_LIMIT * 4}
    result.update(overrides)
    return result


def build(data=None, raster=None):
    support, protocol, limits = data or fixture()
    cohort = P.Cohort(support, POLICY, protocol,
        expected_support_sha256=P.digest(support), expected_policy_sha256=P.digest(POLICY),
        expected_protocol_sha256=P.digest(protocol), recipe_sha256="a" * 64,
        limits=limits, secret=SECRET, dependencies=D)
    protocol = raster or raster_protocol()
    return cohort, R.RasterDelivery(cohort, protocol, expected_protocol_sha256=P.digest(protocol))


def open_generated(cohort, *, case=None, values=None):
    case = case or cohort.case_ids()[0]
    row = cohort._records[cohort._join[case]]
    signals = values or [[0] * row["native_sample_count"] for _ in row["predictor_channels"]]
    assert len(signals) == len(row["predictor_channels"])
    assert all(len(v) == row["native_sample_count"] for v in signals)

    class GeneratedReader(D.reader.RecordWindow):
        def __init__(self):
            self.sample_rate_hz = row["native_sample_rate_hz"]
            self.sample_count = row["native_sample_count"]
            self.observed_ticks = row["observed_ticks"]
            self.calls, self.closed = [], False

        def window(self, start, stop, *, available_through_tick):
            self.calls.append((start, stop, available_through_tick))
            assert stop <= min(self.sample_count, available_through_tick * self.sample_rate_hz // 10 + 1)
            return {"schema": "neural009_calibrated_causal_window_v1", "sample_start": start,
                    "sample_stop": stop, "sample_rate_hz": self.sample_rate_hz,
                    "available_through_tick": available_through_tick,
                    "channels": [{"channel_index": channel["index"], "label": channel["label"],
                                  "unit": "uV", "samples": signal[start:stop]}
                                 for channel, signal in zip(row["predictor_channels"], signals)]}

        def close(self):
            self.closed = True

    reader = GeneratedReader()
    cohort._start(case, lambda: reader)
    return case, reader


def view(delivery, case, end=1, lookback=1):
    return delivery.dispatch({"action": "view", "case_id": case, "end_tick": end, "lookback_ticks": lookback})


def answer(delivery, case, tick, probability):
    return delivery.dispatch({"action": "answer", "case_id": case, "tick": tick, "probability": probability})


class RasterControls(unittest.TestCase):
    def assert_png_reply(self, reply):
        self.assertEqual(set(reply), SUCCESS_KEYS)
        self.assertEqual(reply["status"], "view")
        self.assertEqual(reply["image_mime_type"], "image/png")
        self.assertEqual(reply["representation"], "inactive_raster_png_not_native_qualified")
        self.assertEqual(reply["image_sha256"], hashlib.sha256(reply["image_png"]).hexdigest())
        return decode_png(reply["image_png"])

    def test_calibration_duplicate_bands_and_visible_context(self):
        cohort, delivery = build(fixture(("Fp1-F7", "Fp1-F7")))
        case, _ = open_generated(cohort, values=[[10, 0, -10, 10, 0, -10], [-10, 0, 10, -10, 0, 10]])
        image = self.assert_png_reply(view(delivery, case))
        self.assertEqual(image[:2], (501, 266))
        self.assertEqual(pixel(image, 500, 265), (255, 255, 255))
        for x, y in [(192, 44), (292, 94), (392, 144), (492, 44),
                     (192, 245), (292, 195), (392, 145), (492, 245)]:
            self.assertEqual(pixel(image, x, y), (0, 0, 0))
        for y in (4, 13, 22, 31):
            self.assertTrue(has_ink(image, 8, y, 160, 7), "Missing visible header line")
        for top in (44, 145):
            for y in (top + 4, top + 13, top + 22):
                self.assertTrue(has_ink(image, 8, y, 120, 7), "Missing channel label or calibrated scale")
        self.assertTrue(has_ink(image, 8, 250, 220, 7), "Missing visible qualification footer")
        delivery.abort_active()

    def test_case_sensitive_and_xml_sensitive_labels_are_pixels(self):
        images = []
        for label in ("A", "a", "a<&>"):
            cohort, delivery = build(fixture((label,)))
            case, _ = open_generated(cohort)
            reply = view(delivery, case)
            image = self.assert_png_reply(reply)
            images.append(crop(image, 8, 48, 36, 7))
            public = json.dumps({k: v for k, v in reply.items() if k != "image_png"})
            self.assertNotIn(label + ";", public)
            delivery.abort_active()
        self.assertNotEqual(images[0], images[1], "Lowercase label was silently uppercased")
        self.assertNotEqual(images[1], images[2], "XML-sensitive label content was omitted")

    def test_scale_text_changes_without_changing_zero_signal_geometry(self):
        images = []
        for extent in (10, 20):
            cohort, delivery = build(fixture(low=-extent, high=extent))
            case, _ = open_generated(cohort)
            images.append(self.assert_png_reply(view(delivery, case)))
            delivery.abort_active()
        self.assertNotEqual(crop(images[0], 8, 57, 120, 16), crop(images[1], 8, 57, 120, 16))
        self.assertEqual(crop(images[0], 192, 44, 301, 101), crop(images[1], 192, 44, 301, 101))

    def test_first_endpoint_excludes_changed_future_samples(self):
        blobs = []
        for future in (-10, 10):
            cohort, delivery = build()
            case, reader = open_generated(cohort, values=[[0, 1, 2, 3, future, future]])
            reply = view(delivery, case)
            self.assert_png_reply(reply)
            self.assertEqual(reader.calls, [(0, 4, 1)])
            blobs.append(reply["image_png"])
            delivery.abort_active()
        self.assertEqual(blobs[0], blobs[1])

    def test_one_sample_and_dense_traces_remain_visible(self):
        cohort, delivery = build(fixture(ticks=1, rate=10))
        case, _ = open_generated(cohort, values=[[0]])
        image = self.assert_png_reply(view(delivery, case))
        self.assertEqual(pixel(image, 192, 94), (0, 0, 0))
        delivery.abort_active()
        cohort, delivery = build(fixture(ticks=2, rate=1000))
        case, _ = open_generated(cohort, values=[[10 if i % 2 == 0 else -10 for i in range(200)]])
        image = self.assert_png_reply(view(delivery, case))
        self.assertEqual(pixel(image, 192, 44), (0, 0, 0))
        self.assertEqual(pixel(image, 492, 44), (0, 0, 0))
        self.assertTrue(has_ink(image, 192, 144, 301, 1))
        delivery.abort_active()

    def test_participant_reply_excludes_svg_arrays_and_source_identity(self):
        cohort, delivery = build()
        case, _ = open_generated(cohort)
        reply = view(delivery, case)
        self.assert_png_reply(reply)
        public = json.dumps({k: v for k, v in reply.items() if k != "image_png"})
        for forbidden in ("svg", "polyline", "samples", "source_index", "predictor_channels",
                          "reference_intervals", "recording_id", "biological_person", "chb01", INDEX_SHA):
            self.assertNotIn(forbidden, public)
        for name, indexed in INDEX.items():
            self.assertNotIn(name, public)
            self.assertNotIn(indexed["publisher_sha256"], public)
        self.assertNotIn(b"tEXt", reply["image_png"][:64])
        delivery.abort_active()

    def test_causal_refusal_view_accounting_and_irreversible_answer(self):
        cohort, delivery = build()
        case, reader = open_generated(cohort)
        self.assertEqual(view(delivery, case, end=2)["status"], "refused")
        self.assertEqual(reader.calls, [])
        self.assert_png_reply(view(delivery, case))
        state = cohort._state[cohort._join[case]]
        self.assertEqual((state["ticks"], state["views"], state["actions"]), (0, 1, 2))
        self.assertEqual(answer(delivery, case, 1, .5)["next_endpoint_tick"], 2)
        self.assertEqual(answer(delivery, case, 1, .1)["status"], "refused")
        self.assertEqual((state["ticks"], state["views"]), (1, 0))
        self.assert_png_reply(view(delivery, case, end=2, lookback=2))
        self.assertTrue(answer(delivery, case, 2, .5)["record_complete"])
        self.assertTrue(reader.closed)
        self.assertEqual(state["runs"], [[0, 2, .5]])
        self.assertIsNone(delivery.finish()["candidate"])

    def test_unsupported_glyph_and_nonfitting_label_retain_failure(self):
        for label in ("Fp1-\u03bc", "A" * 80):
            cohort, delivery = build(fixture((label,)))
            case, reader = open_generated(cohort)
            reply = view(delivery, case)
            self.assertEqual(reply["status"], "failed")
            self.assertEqual(reply["reason"], "raster_refused")
            self.assertNotIn("svg", reply)
            self.assertNotIn("image_png", reply)
            self.assertTrue(reader.closed)
            state = cohort._state[cohort._join[case]]
            self.assertEqual((state["status"], state["ticks"]), ("failed", 0))
            self.assertIsNone(delivery.finish()["candidate"])

    def test_per_image_and_cumulative_byte_caps_retain_failure(self):
        cohort, delivery = build(raster=raster_protocol(max_png_bytes=128, max_total_png_bytes_per_record=128))
        case, _ = open_generated(cohort)
        reply = view(delivery, case)
        self.assertEqual(reply["reason"], "raster_refused")
        self.assertIsNone(delivery.finish()["candidate"])
        cohort, delivery = build(raster=raster_protocol(max_png_bytes=300000, max_total_png_bytes_per_record=300000))
        case, _ = open_generated(cohort)
        first = view(delivery, case)
        self.assert_png_reply(first)
        self.assertGreater(len(first["image_png"]) * 2, 300000)
        second = view(delivery, case)
        self.assertEqual(second["reason"], "raster_refused")
        self.assertNotIn("image_png", second)
        self.assertEqual(cohort._state[cohort._join[case]]["status"], "failed")

    def test_frozen_protocol_commitment_and_geometry_refuse_before_view(self):
        cohort, _ = build()
        with self.assertRaises(R.RasterRefused):
            R.RasterDelivery(cohort, raster_protocol(), expected_protocol_sha256="0" * 64)
        with self.assertRaises(R.RasterRefused):
            build(raster=raster_protocol(header_px=1))
        with self.assertRaises(R.RasterRefused):
            build(raster=raster_protocol(max_image_pixels=4194305))
        self.assertTrue(all(v["status"] == "not_started" for v in cohort._state.values()))

    def test_complete686_probabilities_keep_existing_candidate_interface(self):
        cohort, delivery = build()
        for case in delivery.case_ids():
            open_generated(cohort, case=case)
            self.assertEqual(answer(delivery, case, 1, .5)["status"], "accepted")
            self.assertTrue(answer(delivery, case, 2, .1)["record_complete"])
        result = delivery.finish()
        candidate = result["candidate"]
        self.assertEqual(candidate["schema"], "neural009_candidate_v1")
        self.assertEqual(len(candidate["records"]), 686)
        self.assertEqual({r["biological_person"] for r in candidate["records"]}, set(PEOPLE))
        self.assertTrue(all(r["score_runs"] == [[0, 1, .5], [1, 2, .1]] for r in candidate["records"]))
        self.assertTrue(all(r["predicted_intervals"] == [[0, 1]] for r in candidate["records"]))
        alias_rows = [r for r in candidate["records"] if r["recording_id"].startswith("chb21/")]
        self.assertTrue(alias_rows and all(r["fold_id"] == "chb01" for r in alias_rows))
        self.assertFalse(result["scientific_qualification"])
        self.assertFalse(result["mode_activated"])


def make_preview(path):
    cohort, delivery = build(fixture(("Fp1-F7", "Fp1-F7", "a<&>"), ticks=20, rate=30,
                                    width=800, row_height=96),
                             raster_protocol(gutter_px=240, header_px=84, footer_px=28, font_scale=2))
    values = [[(i % 21) - 10 for i in range(60)],
              [10 - (i % 21) for i in range(60)],
              [8 if i % 2 else -8 for i in range(60)]]
    case, _ = open_generated(cohort, values=values)
    for tick in range(1, 20):
        answer(delivery, case, tick, 0)
    reply = view(delivery, case, end=20, lookback=20)
    assert reply["status"] == "view", reply
    png = reply["image_png"]
    assert len(png) <= PREVIEW_LIMIT
    dimensions = decode_png(png)[:2]
    assert dimensions == (1048, 400)
    with path.open("xb") as handle:
        handle.write(png)
    delivery.abort_active()
    return {"path": str(path), "bytes": len(png), "sha256": hashlib.sha256(png).hexdigest(),
            "width": dimensions[0], "height": dimensions[1], "scope": "invented signals and labels only"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--implementations", type=Path, required=True)
    parser.add_argument("--preview", type=Path, required=True)
    args = parser.parse_args()
    P = load_module("generated_causal_presentation", args.implementations / "causal-presentation-v1" / "presentation.py",
                    PRESENTATION_SHA256)
    D = P.Dependencies(args.implementations)
    INDEX, PEOPLE, INDEX_SHA = D.core.source_index()
    POLICY = D.core.recommended_policy()
    R = load_module("generated_causal_raster", HERE / "raster.py")
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(RasterControls))
    receipt = {"schema": "neural009_generated_raster_controls_v1", "tests_run": result.testsRun,
               "failures": len(result.failures), "errors": len(result.errors),
               "scientific_qualification": False, "authentic_data": False,
               "model_or_provider_run": False, "preview": None}
    if result.wasSuccessful():
        receipt["preview"] = make_preview(args.preview)
    print(json.dumps(receipt, sort_keys=True))
    sys.exit(0 if result.wasSuccessful() else 1)
