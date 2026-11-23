"""Generated source controls. No authentic EEG, labels, images or model calls."""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zlib


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("image_reference", HERE / "reference.py")
ref = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ref)
RENDERER = None
WRITTEN_BYTES = 0


def chunk(kind, payload):
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload))


def png(pixels, *, filter_number=0, extra_before=b"", extra_after=b"", color=2):
    stride = ref.WIDTH * 3
    rows = bytearray()
    previous = bytes(stride)
    for y in range(ref.HEIGHT):
        row = pixels[y * stride:(y + 1) * stride]
        rows.append(filter_number)
        if not filter_number:
            rows.extend(row)
        else:
            for i, value in enumerate(row):
                left = row[i - 3] if i >= 3 else 0
                above = previous[i]
                corner = previous[i - 3] if i >= 3 else 0
                if filter_number == 1:
                    prediction = left
                elif filter_number == 2:
                    prediction = above
                elif filter_number == 3:
                    prediction = (left + above) // 2
                else:
                    distances = (abs(above - corner), abs(left - corner), abs(left + above - 2 * corner))
                    prediction = (left, above, corner)[min(range(3), key=lambda k: distances[k])]
                rows.append((value - prediction) & 255)
        previous = row
    header = struct.pack(">IIBBBBB", ref.WIDTH, ref.HEIGHT, 8, color, 0, 0, 0)
    return (ref.PNG_SIGNATURE + chunk(b"IHDR", header) + extra_before
            + chunk(b"IDAT", zlib.compress(rows, 6)) + extra_after + chunk(b"IEND", b""))


def flat_raster(post_pixels=0, missing=(), baseline_missing=False):
    raster = bytearray(b"\xff" * (ref.WIDTH * ref.HEIGHT * 3))
    for top in ref.TOPS:
        for x in range(ref.LEFT, ref.STOP):
            if x in missing or baseline_missing and x < 460:
                continue
            y = top + 90 - (post_pixels if x >= 460 else 0)
            at = (y * ref.WIDTH + x) * 3
            raster[at:at + 3] = bytes((20, 75, 170))
    return raster


def write_counted(path, content):
    global WRITTEN_BYTES
    path.write_bytes(content)
    WRITTEN_BYTES += len(content)


def fake_feature(value, coverage=1.0):
    return {"values": [value] * 30, "coverage": [coverage] * 30,
            "baseline_rms": [0.1, 0.1], "baseline_coverage": [1.0, 1.0]}


def fit_simple():
    return ref.fit_features([fake_feature(-0.5), fake_feature(0.5),
                             fake_feature(-0.5), fake_feature(0.5)],
                            [str(i) * 64 for i in range(4)], profile=ref.PROFILE)


class RasterControls(unittest.TestCase):
    def test_known_offset_and_independent_time_bins(self):
        features = ref.extract_features(flat_raster(18))
        self.assertEqual(features["coverage"], [1.0] * 30)
        for value in features["values"]:
            self.assertAlmostEqual(value, 0.2)
        self.assertEqual(features["baseline_coverage"], [1.0, 1.0])

    def test_missing_bin_stays_missing_without_interpolation(self):
        features = ref.extract_features(flat_raster(18, missing=range(572, 628)))
        self.assertIsNone(features["values"][2])
        self.assertEqual(features["coverage"][2], 0)
        self.assertAlmostEqual(features["values"][1], 0.2)
        self.assertAlmostEqual(features["values"][3], 0.2)
        self.assertIsNone(features["values"][17])

    def test_more_than_three_percent_missing_is_supported_and_reported(self):
        features = ref.extract_features(flat_raster(18, missing=range(572, 684)))
        probability, quality = ref.predict_features(features, fit_simple(), profile=ref.PROFILE)
        self.assertGreater(probability, 0.5)
        self.assertLess(quality["shared_support_fraction"], 1.0)
        self.assertEqual(sum(c == 0 for c in features["coverage"]), 4)

    def test_missing_baseline_refuses_even_if_postmarker_is_visible(self):
        features = ref.extract_features(flat_raster(18, baseline_missing=True))
        self.assertEqual(features["baseline_coverage"], [0.0, 0.0])
        self.assertEqual(features["coverage"], [0.0] * 30)
        with self.assertRaisesRegex(ValueError, "no shared visible support"):
            ref.predict_features(features, fit_simple(), profile=ref.PROFILE)

    def test_header_footer_marker_and_terminal_column_do_not_supply_signal(self):
        base = flat_raster(18)
        other = bytearray(base)
        for x, y in ((30, 54), (35, 774), (1300, 295), (179, 295), (400, 204)):
            at = (y * ref.WIDTH + x) * 3
            other[at:at + 3] = bytes((20, 75, 170))
        self.assertEqual(ref.extract_features(base), ref.extract_features(other))
        # A red event marker overwrites one blue column, which becomes missing.
        for top in ref.TOPS:
            for y in range(top, top + 181):
                at = (y * ref.WIDTH + 460) * 3
                other[at:at + 3] = bytes((170, 35, 35))
        features = ref.extract_features(other)
        self.assertAlmostEqual(features["coverage"][0], 55 / 56)
        self.assertAlmostEqual(features["values"][0], 0.2)

    def test_vertical_extent_center_is_raster_feature(self):
        raster = flat_raster(0)
        for top in ref.TOPS:
            for y in range(top + 45, top + 136):
                at = (y * ref.WIDTH + 600) * 3
                raster[at:at + 3] = bytes((20, 75, 170))
        features = ref.extract_features(raster)
        self.assertEqual(features["values"], [0.0] * 30)

    def test_original_renderer_clipped_plateau_has_no_hidden_amplitude(self):
        self.assertIsNotNone(RENDERER, "--renderer must identify public raster.py")
        s = importlib.util.spec_from_file_location("generated_fixture_renderer", RENDERER)
        renderer = importlib.util.module_from_spec(s)
        s.loader.exec_module(renderer)
        # At gain20, +100 native units exceeds the visible +60 limit.
        values = [0.0] * 1024
        for i in range(256 + 80, 256 + 230):
            values[i] = 100.0
        state = {"start_sample": -256, "stop_sample": 768, "units_per_division": 20,
                 "record": "query", "channels": ["Cz", "Pz"]}
        canonical = renderer.render({"channels": [values, values]}, state, "four_demo")
        features = ref.extract_features(ref.decode_png(canonical))
        # 100–150 ms is strictly inside the clipped plateau; 300–350ms is flat0.
        self.assertEqual(features["coverage"][2], 0)
        self.assertIsNone(features["values"][2])
        self.assertAlmostEqual(features["values"][6], 0.0)


class ModelControls(unittest.TestCase):
    def test_balanced_class_centroids_and_tie(self):
        model = fit_simple()
        self.assertEqual(model["means"][0], [-0.5] * 30)
        self.assertEqual(model["means"][1], [0.5] * 30)
        probability, _ = ref.predict_features(fake_feature(0), model, profile=ref.PROFILE)
        self.assertEqual(probability, 0.5)

    def test_asymmetric_class_support_cannot_advantage_one_distance(self):
        model = fit_simple()
        model["supports"][1][0], model["means"][1][0] = 0.0, None
        query = fake_feature(0.25)
        first, _ = ref.predict_features(query, model, profile=ref.PROFILE)
        query["values"][0] = -1.5
        model["means"][0][0] = 1.5
        second, _ = ref.predict_features(query, model, profile=ref.PROFILE)
        self.assertEqual(first, second)

    def test_less_support_shrinks_score_without_inventing_samples(self):
        model = fit_simple()
        full, _ = ref.predict_features(fake_feature(0.5), model, profile=ref.PROFILE)
        reduced, quality = ref.predict_features(fake_feature(0.5, 0.25), model, profile=ref.PROFILE)
        self.assertAlmostEqual(reduced - 0.5, (full - 0.5) / 4)
        self.assertEqual(quality["shared_support_fraction"], 0.25)

    def test_baseline_missingness_downweights_demo_support(self):
        demos = [fake_feature(-0.5), fake_feature(0.5), fake_feature(-0.5), fake_feature(0.5)]
        demos[0]["baseline_coverage"][0] = 0.5
        model = ref.fit_features(demos, [str(i) * 64 for i in range(4)], profile=ref.PROFILE)
        self.assertEqual(model["supports"][0][:15], [0.75] * 15)
        self.assertEqual(model["supports"][0][15:], [1.0] * 15)

    def test_query_cannot_change_frozen_model_or_demo_scales(self):
        model = fit_simple()
        before = ref.json_bytes(model)
        query = fake_feature(-0.5)
        query["baseline_rms"] = [999, 999]
        low, _ = ref.predict_features(query, model, profile=ref.PROFILE)
        query["values"] = [0.5] * 30
        high, _ = ref.predict_features(query, model, profile=ref.PROFILE)
        self.assertLess(low, 0.5)
        self.assertGreater(high, 0.5)
        self.assertEqual(ref.json_bytes(model), before)
        self.assertEqual(model["scales"], [0.1, 0.1])

    def test_degenerate_identical_demos_tie_and_flat_scale_floor(self):
        demos = [fake_feature(0) for _ in range(4)]
        for d in demos:
            d["baseline_rms"] = [0.0, 0.0]
        model = ref.fit_features(demos, [str(i) * 64 for i in range(4)], profile=ref.PROFILE)
        self.assertEqual(model["scales"], [ref.SCALE_FLOOR] * 2)
        self.assertEqual(ref.predict_features(fake_feature(1), model, profile=ref.PROFILE)[0], 0.5)

    def test_disjoint_demo_support_refuses_fit(self):
        demos = [fake_feature(0) for _ in range(4)]
        for i, d in enumerate(demos):
            support = range(15) if i % 2 == 0 else range(15, 30)
            d["coverage"] = [float(j in support) for j in range(30)]
            d["values"] = [0.0 if j in support else None for j in range(30)]
        with self.assertRaisesRegex(ValueError, "no shared supported features"):
            ref.fit_features(demos, [str(i) * 64 for i in range(4)], profile=ref.PROFILE)

    def test_invalid_models_refused(self):
        for mutate in (lambda m: m["scales"].__setitem__(0, float("nan")),
                       lambda m: m["supports"][0].__setitem__(0, 2.0),
                       lambda m: m["means"][0].__setitem__(0, None),
                       lambda m: m.__setitem__("source_sha256", "0" * 64),
                       lambda m: m["config"].__setitem__("profile", "different_view")):
            model = copy.deepcopy(fit_simple())
            mutate(model)
            with self.assertRaises(ValueError):
                ref.validate_model(model)

    def test_profile_declaration_required(self):
        with self.assertRaisesRegex(ValueError, "unsupported declared"):
            ref.predict_features(fake_feature(0), fit_simple(), profile="arbitrary_view")


class PNGControls(unittest.TestCase):
    def test_each_png_filter_roundtrips_known_pixels(self):
        raster = flat_raster(18)
        for filter_number in range(5):
            with self.subTest(filter_number=filter_number):
                self.assertEqual(ref.decode_png(png(raster, filter_number=filter_number)), raster)

    def test_metadata_does_not_change_extracted_features(self):
        raster = flat_raster(18)
        plain = png(raster)
        described = png(raster, extra_before=chunk(b"tEXt", b"target\0secret-is-ignored"))
        self.assertEqual(ref.extract_features(ref.decode_png(plain)),
                         ref.extract_features(ref.decode_png(described)))

    def test_bad_crc_trailing_alpha_critical_chunk_and_duplicate_header_rejected(self):
        raster = flat_raster()
        valid = png(raster)
        corrupt = bytearray(valid)
        corrupt[-1] ^= 1
        header = valid[8:33]
        invalid = [bytes(corrupt), valid + b"X", png(raster, color=6),
                   png(raster, extra_before=chunk(b"ABCD", b"")),
                   valid[:33] + header + valid[33:],
                   png(raster, extra_before=chunk(b"tRNS", b"\0" * 6))]
        for item in invalid:
            with self.assertRaises(ValueError):
                ref.decode_png(item)

    def test_decompression_overflow_and_multiple_streams_refused(self):
        header = chunk(b"IHDR", struct.pack(">IIBBBBB", ref.WIDTH, ref.HEIGHT, 8, 2, 0, 0, 0))
        size = ref.HEIGHT * (ref.WIDTH * 3 + 1)
        for data in (zlib.compress(b"\0" * (size + 1)),
                     zlib.compress(b"\0" * size) + zlib.compress(b"extra")):
            encoded = ref.PNG_SIGNATURE + header + chunk(b"IDAT", data) + chunk(b"IEND", b"")
            with self.assertRaisesRegex(ValueError, "decompressed length"):
                ref.decode_png(encoded)


class CLIControls(unittest.TestCase):
    def test_fit_and_predict_fresh_processes_with_model_freeze(self):
        global WRITTEN_BYTES
        with tempfile.TemporaryDirectory(prefix="erp-generated-", dir=HERE) as tmp:
            root = Path(tmp)
            paths = []
            for i, pixels in enumerate((-18, 18, -18, 18, 18)):
                path = root / f"opaque-{i}.png"
                write_counted(path, png(flat_raster(pixels)))
                paths.append(str(path))
            model_path = root / "reference.json"
            common = [sys.executable, "-I", "-S", "-B", str(HERE / "reference.py")]
            fit = subprocess.run(common + ["fit", "--profile", ref.PROFILE,
                                           "--demos", *paths[:4], "--output", str(model_path)],
                                 capture_output=True, text=True, timeout=20)
            self.assertEqual(fit.returncode, 0, fit.stderr)
            model_bytes = model_path.read_bytes()
            WRITTEN_BYTES += len(model_bytes)
            pin = json.loads(fit.stdout)["sha256"]
            self.assertEqual(pin, hashlib.sha256(model_bytes).hexdigest())
            predict_args = common + ["predict", "--profile", ref.PROFILE,
                                     "--model", str(model_path), "--model-sha256", pin,
                                     "--query", paths[4], "--trial-id", "opaque-generated"]
            prediction = subprocess.run(predict_args, capture_output=True, text=True, timeout=20)
            self.assertEqual(prediction.returncode, 0, prediction.stderr)
            result = json.loads(prediction.stdout)
            self.assertEqual(set(result), {"trial_id", "target_probability"})
            self.assertEqual(result["trial_id"], "opaque-generated")
            self.assertGreater(result["target_probability"], 0.5)
            self.assertEqual(model_path.read_bytes(), model_bytes)
            # Mutation must fail before a query path is even opened.
            bad_args = list(predict_args)
            bad_args[bad_args.index("--model-sha256") + 1] = "0" * 64
            bad_args[bad_args.index("--query") + 1] = str(root / "missing-query.png")
            failed = subprocess.run(bad_args, capture_output=True, text=True, timeout=20)
            self.assertEqual(failed.returncode, 2)
            self.assertEqual(failed.stdout, "")
            self.assertIn("model digest mismatch", failed.stderr)

    def test_duplicate_and_nonfinite_json_refused(self):
        for text in (b'{"x":1,"x":2}', b'{"x":NaN}'):
            with self.assertRaises(ValueError):
                ref.json_no_duplicates(text)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--renderer", type=Path, default=HERE.parent / "visual-viewer-v1" / "raster.py")
    args, rest = parser.parse_known_args()
    RENDERER = args.renderer.resolve(strict=True)
    outcome = unittest.main(argv=[sys.argv[0], *rest], exit=False)
    print(json.dumps({"generated_fixture_bytes_written": WRITTEN_BYTES,
                      "authentic_inputs": 0, "model_calls": 0,
                      "remaining_fixture_directories": len(list(HERE.glob("erp-generated-*")))}))
    raise SystemExit(not outcome.result.wasSuccessful())
