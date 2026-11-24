#!/usr/bin/env python3
"""Total fixed-view, four-demo ERP image uncertainty reference (standard library only)."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import struct
import sys
import zlib

PROFILE = "neural077-initial-cz-pz-gain20-v1"
METHOD = "visible-bin-centroid-zero-support-half-v1"
WIDTH, HEIGHT = 1400, 820
LEFT, STOP = 180, 1300  # x=1300 is the exclusive +750-ms endpoint.
TOPS = (205, 465)
LABELS = (0, 1, 0, 1)
MAX_PNG_BYTES = 4 * 1024 * 1024
MAX_MODEL_BYTES = 64 * 1024
SCALE_FLOOR = 1.0 / 90.0  # One vertical pixel in normalized display amplitude.
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
CONFIG = {
    "profile": PROFILE,
    "feature": "two_channels_x_fifteen_postmarker_50ms_visible_column_means",
    "baseline": "visible_pre_marker_column_mean_per_image_channel",
    "scale": "median_four_demo_baseline_RMS_per_channel_with_one_pixel_floor",
    "missingness": "no_interpolation; shared_min_query_and_two_class_coverages",
    "distance": "common_support_weighted_mean_squared_standardized_difference",
    "zero_shared_support": "probability_half_with_explicit_audit_flag; no_imputation",
    "score": "sigmoid_half_distance_difference_shrunk_by_common_support_fraction",
}


def need(condition, message):
    if not condition:
        raise ValueError(message)


def source_sha256():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def bounded_read(path, limit):
    with Path(path).open("rb") as handle:
        data = handle.read(limit + 1)
    need(len(data) <= limit, "input exceeds byte limit")
    return data


def paeth(left, above, upper_left):
    p = left + above - upper_left
    a, b, c = abs(p - left), abs(p - above), abs(p - upper_left)
    return left if a <= b and a <= c else above if b <= c else upper_left


def decode_png(data):
    """Decode bounded opaque 8-bit RGB PNGs; verify format, not view semantics."""
    need(type(data) is bytes and len(data) <= MAX_PNG_BYTES, "invalid PNG bytes")
    need(data.startswith(PNG_SIGNATURE), "invalid PNG signature")
    position, seen_header, seen_idat, closed_idat = 8, False, False, False
    compressed = bytearray()
    ended = False
    while position < len(data):
        need(position + 12 <= len(data), "truncated PNG chunk")
        size = struct.unpack_from(">I", data, position)[0]
        kind = data[position + 4:position + 8]
        end = position + 12 + size
        need(end <= len(data), "truncated PNG payload")
        need(all(65 <= c <= 90 or 97 <= c <= 122 for c in kind), "invalid PNG chunk type")
        need(65 <= kind[2] <= 90, "invalid PNG reserved chunk bit")
        payload = data[position + 8:end - 4]
        crc = struct.unpack_from(">I", data, end - 4)[0]
        need(zlib.crc32(kind + payload) & 0xffffffff == crc, "PNG checksum mismatch")
        if not seen_header:
            need(kind == b"IHDR" and size == 13, "PNG must start with IHDR")
            header = struct.unpack(">IIBBBBB", payload)
            need(header == (WIDTH, HEIGHT, 8, 2, 0, 0, 0), "requires fixed-size opaque RGB8 PNG")
            seen_header = True
        elif kind == b"IHDR":
            raise ValueError("duplicate PNG header")
        elif kind == b"IDAT":
            need(not closed_idat, "nonconsecutive PNG image chunks")
            seen_idat = True
            compressed.extend(payload)
        elif kind == b"IEND":
            need(size == 0 and seen_idat and end == len(data), "invalid PNG end or trailing bytes")
            ended = True
            break
        else:
            if seen_idat:
                closed_idat = True
            # Transparency changes the observed pixels; this profile is opaque.
            need(kind != b"tRNS", "PNG transparency unsupported")
            need(kind[0] & 32, "unsupported critical PNG chunk")
        position = end
    need(ended and compressed, "incomplete PNG")
    stride = WIDTH * 3
    expected = HEIGHT * (stride + 1)
    decoder = zlib.decompressobj()
    raw = decoder.decompress(bytes(compressed), expected + 1)
    need(len(raw) == expected and decoder.eof and not decoder.unconsumed_tail
         and not decoder.unused_data, "invalid PNG decompressed length or stream")
    pixels = bytearray(HEIGHT * stride)
    previous = bytearray(stride)
    for y in range(HEIGHT):
        at = y * (stride + 1)
        filter_type = raw[at]
        need(filter_type in range(5), "invalid PNG filter")
        row = bytearray(raw[at + 1:at + 1 + stride])
        if filter_type:
            for i in range(stride):
                left = row[i - 3] if i >= 3 else 0
                above = previous[i]
                upper_left = previous[i - 3] if i >= 3 else 0
                if filter_type == 1:
                    predictor = left
                elif filter_type == 2:
                    predictor = above
                elif filter_type == 3:
                    predictor = (left + above) // 2
                else:
                    predictor = paeth(left, above, upper_left)
                row[i] = (row[i] + predictor) & 255
        pixels[y * stride:(y + 1) * stride] = row
        previous = row
    return pixels


def extract_features(pixels):
    """Use visible blue pixels only; absent columns remain unobserved.

    Amplitude is a fraction of the fixed +/-90-pixel panel range. The midpoint
    of a column's blue extent is a raster feature, not an original EEG sample.
    """
    need(type(pixels) in (bytes, bytearray) and len(pixels) == WIDTH * HEIGHT * 3,
         "invalid RGB raster")
    values, coverage, baseline_rms, baseline_coverage = [], [], [], []
    for top in TOPS:
        trace = []
        for x in range(LEFT, STOP):
            low, high = 181, -1
            for row in range(181):
                at = ((top + row) * WIDTH + x) * 3
                red, green, blue = pixels[at], pixels[at + 1], pixels[at + 2]
                if blue > red + 30 and blue > green + 20 and blue > 100:
                    low, high = min(low, row), max(high, row)
            trace.append((90.0 - 0.5 * (low + high)) / 90.0 if high >= 0 else None)
        pre = [value for value in trace[:280] if value is not None]
        baseline_coverage.append(len(pre) / 280.0)
        center = statistics.fmean(pre) if pre else None
        baseline_rms.append(math.sqrt(statistics.fmean((v - center) ** 2 for v in pre))
                            if pre else None)
        for start in range(280, 1120, 56):
            visible = [v for v in trace[start:start + 56] if v is not None]
            # A wholly hidden baseline cannot identify the image's residual offset.
            supported = bool(visible) and center is not None
            values.append(statistics.fmean(visible) - center if supported else None)
            coverage.append(len(visible) / 56.0 if supported else 0.0)
    return {"values": values, "coverage": coverage, "baseline_rms": baseline_rms,
            "baseline_coverage": baseline_coverage}


def feature_png(path):
    data = bounded_read(path, MAX_PNG_BYTES)
    return extract_features(decode_png(data)), hashlib.sha256(data).hexdigest()


def fit_features(demos, demo_sha256, *, profile):
    """Fit only four ordered, balanced demos; no query argument or access."""
    need(profile == PROFILE, "unsupported declared view profile")
    need(len(demos) == 4 and len(demo_sha256) == 4, "exactly four ordered demos required")
    need(all(re.fullmatch(r"[0-9a-f]{64}", value or "") for value in demo_sha256),
         "invalid demo digest")
    for demo in demos:
        validate_features(demo)
    means, supports = [], []
    for label in (0, 1):
        examples = [demos[i] for i in range(4) if LABELS[i] == label]
        row, support = [], []
        for j in range(30):
            reliability = [d["coverage"][j] * d["baseline_coverage"][j // 15] for d in examples]
            weight = sum(reliability)
            row.append(sum(w * d["values"][j] for d, w in zip(examples, reliability)
                           if d["coverage"][j] > 0) / weight if weight else None)
            support.append(weight / 2.0)
        means.append(row)
        supports.append(support)
    scales = []
    for channel in (0, 1):
        rms = [d["baseline_rms"][channel] for d in demos
               if d["baseline_rms"][channel] is not None]
        scales.append(max(SCALE_FLOOR, statistics.median(rms)) if rms else SCALE_FLOOR)
    model = {"schema": METHOD, "config": CONFIG, "source_sha256": source_sha256(),
             "demonstration_labels": list(LABELS), "demonstration_sha256": list(demo_sha256),
             "means": means, "supports": supports, "scales": scales}
    validate_model(model)
    need(any(min(supports[0][j], supports[1][j]) > 0 for j in range(30)),
         "demos have no shared supported features")
    return model


def finite_number(value):
    return type(value) in (int, float) and math.isfinite(value)


def validate_features(features):
    """Admit the extractor's complete30-feature domain before any fallback."""
    need(type(features) is dict and set(features) ==
         {"values", "coverage", "baseline_rms", "baseline_coverage"}, "invalid feature fields")
    for name, count in (("values", 30), ("coverage", 30), ("baseline_rms", 2), ("baseline_coverage", 2)):
        need(type(features[name]) is list and len(features[name]) == count, "invalid feature shape")
    for channel in range(2):
        coverage, rms = features["baseline_coverage"][channel], features["baseline_rms"][channel]
        need(finite_number(coverage) and 0 <= coverage <= 1, "invalid baseline coverage")
        need((coverage == 0 and rms is None) or
             (coverage > 0 and finite_number(rms) and 0 <= rms <= 1), "invalid baseline RMS")
    for j, (value, coverage) in enumerate(zip(features["values"], features["coverage"])):
        need(finite_number(coverage) and 0 <= coverage <= 1, "invalid feature coverage")
        need((coverage == 0 and value is None) or
             (coverage > 0 and finite_number(value) and -2 <= value <= 2 and
              features["baseline_coverage"][j // 15] > 0), "invalid supported feature")


def validate_model(model):
    keys = {"schema", "config", "source_sha256", "demonstration_labels",
            "demonstration_sha256", "means", "supports", "scales"}
    need(type(model) is dict and set(model) == keys, "invalid model fields")
    need(model["schema"] == METHOD and model["config"] == CONFIG, "model configuration mismatch")
    need(model["source_sha256"] == source_sha256(), "model source mismatch")
    need(model["demonstration_labels"] == list(LABELS)
         and all(type(v) is int for v in model["demonstration_labels"]), "invalid demo labels")
    need(type(model["demonstration_sha256"]) is list and len(model["demonstration_sha256"]) == 4
         and all(type(v) is str and re.fullmatch(r"[0-9a-f]{64}", v)
                 for v in model["demonstration_sha256"]), "invalid demo digests")
    need(type(model["scales"]) is list and len(model["scales"]) == 2
         and all(finite_number(v) and SCALE_FLOOR <= v <= 2 for v in model["scales"]),
         "invalid channel scales")
    for name in ("means", "supports"):
        need(type(model[name]) is list and len(model[name]) == 2
             and all(type(row) is list and len(row) == 30 for row in model[name]),
             "invalid class feature shape")
    for label in (0, 1):
        for value, support in zip(model["means"][label], model["supports"][label]):
            need(finite_number(support) and 0 <= support <= 1, "invalid feature support")
            need((support == 0 and value is None) or
                 (support > 0 and finite_number(value) and -2 <= value <= 2),
                 "invalid supported feature")

    need(any(min(model["supports"][0][j], model["supports"][1][j]) > 0 for j in range(30)),
         "invalid model: demos have no shared supported features")


def predict_features(query, model, *, profile):
    """Fixed common-support distance; query never changes any model parameter."""
    need(profile == PROFILE, "unsupported declared view profile")
    validate_model(model)
    validate_features(query)
    weights = [min(query["coverage"][j], model["supports"][0][j], model["supports"][1][j])
               * query["baseline_coverage"][j // 15] for j in range(30)]
    total = sum(weights)
    quality = {"shared_support_fraction": total / 30.0,
               "baseline_coverage": list(query["baseline_coverage"]),
               "coverage": list(query["coverage"]),
               "shared_weights": weights,
               "no_shared_support": total == 0}
    if total == 0:
        return 0.5, quality
    distances = []
    for label in (0, 1):
        distance = sum(weights[j] * ((query["values"][j] - model["means"][label][j])
                                    / model["scales"][j // 15]) ** 2
                       for j in range(30) if weights[j] > 0) / total
        distances.append(distance)
    margin = max(-60.0, min(60.0, 0.5 * (distances[0] - distances[1])))
    raw = 1.0 / (1.0 + math.exp(-margin))
    support_fraction = total / 30.0
    probability = 0.5 + support_fraction * (raw - 0.5)
    need(math.isfinite(probability) and 0 <= probability <= 1, "invalid prediction")
    return probability, quality


def json_bytes(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def json_no_duplicates(data):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, "duplicate JSON field")
            result[key] = value
        return result
    return json.loads(data, object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError("nonfinite JSON")))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    fit = commands.add_parser("fit", help="freeze four-demo reference before query access")
    fit.add_argument("--profile", required=True, choices=(PROFILE,))
    fit.add_argument("--demos", nargs=4, required=True, metavar="PNG")
    fit.add_argument("--output", required=True)
    predict = commands.add_parser("predict", help="classify one identical fixed-view query")
    predict.add_argument("--profile", required=True, choices=(PROFILE,))
    predict.add_argument("--model", required=True)
    predict.add_argument("--model-sha256", required=True)
    predict.add_argument("--query", required=True)
    predict.add_argument("--trial-id", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "fit":
            pairs = [feature_png(path) for path in args.demos]
            model = fit_features([pair[0] for pair in pairs], [pair[1] for pair in pairs], profile=args.profile)
            data = json_bytes(model)
            with Path(args.output).open("xb") as handle:
                handle.write(data)
            print(json.dumps({"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}))
        else:
            need(re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", args.trial_id), "invalid trial ID")
            need(re.fullmatch(r"[0-9a-f]{64}", args.model_sha256), "invalid expected model digest")
            data = bounded_read(args.model, MAX_MODEL_BYTES)
            need(hashlib.sha256(data).hexdigest() == args.model_sha256, "model digest mismatch")
            model = json_no_duplicates(data)
            validate_model(model)  # Complete model admission before opening query.
            query, _ = feature_png(args.query)
            probability, quality = predict_features(query, model, profile=args.profile)
            print(json.dumps({"trial_id": args.trial_id, "target_probability": probability,
                              "quality": quality}, allow_nan=False))
    except (ValueError, OSError, zlib.error, struct.error, TypeError, KeyError) as exc:
        print("reference_failed: " + type(exc).__name__ + ": " + str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
