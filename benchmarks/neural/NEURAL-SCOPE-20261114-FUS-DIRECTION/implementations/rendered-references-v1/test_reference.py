"""Small generated software controls; no authentic data or model outcomes."""
import base64
import copy
import importlib.util
import json
import math
from pathlib import Path
import struct
import unittest
import zlib


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("fus_rendered_reference", HERE / "reference.py")
ref = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ref)


def png(values):
    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))
    pixels = b"".join(bytes((v, v, v)) if v is not None else bytes((255, 0, 255)) for v in values)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", len(values), 1, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"\0" + pixels)) + chunk(b"IEND", b""))


def fixture(arrays=None):
    if arrays is None:
        arrays = [[255 if p == c else 0 for p in range(8)] for c in range(8)]
        arrays.append(arrays[3])
    maps = []
    for i, values in enumerate(arrays):
        maps.append({"map_id": "q_" + format(i + 1, "032x"), "shape": [1, len(values)],
                     "spatial_pitch": [0.1, 0.2], "spatial_pitch_unit": "mm", "native_hz": 2,
                     "source_float": "binary32", "scale": 1.0,
                     "invalid_pixels": sum(v is None for v in values), "saturated_pixels": 0,
                     "png_base64": base64.b64encode(png(values)).decode()})
        if i < 8:
            maps[-1]["direction_degrees"] = 45 * i
    return {"schema": "fus_nine_map_packet_v1", "fold_key": "fold_" + "a" * 32,
            "query_id": maps[-1]["map_id"], "class_angles_degrees": list(range(0, 360, 45)),
            "context": "generated software fixture", "calibration": maps[:8], "query": maps[-1]}


def wire(packet):
    return json.dumps(packet, allow_nan=False, separators=(",", ":")).encode()


def predict(packet, method="squared_distance", **kwargs):
    return ref.predict(wire(packet), method=method, max_packet_bytes=20000, max_map_pixels=100, **kwargs)


def gauss_solve(matrix, target):
    # Independent pivoted elimination oracle, not the production Cholesky solver.
    rows = [list(a) + [b] for a, b in zip(matrix, target)]
    n = len(rows)
    for col in range(n):
        pivot = max(range(col, n), key=lambda i: abs(rows[i][col]))
        rows[col], rows[pivot] = rows[pivot], rows[col]
        value = rows[col][col]
        rows[col] = [x / value for x in rows[col]]
        for i in range(n):
            if i != col:
                scale = rows[i][col]
                rows[i] = [a - scale * b for a, b in zip(rows[i], rows[col])]
    return [r[-1] for r in rows]


class References(unittest.TestCase):
    def test_exact_support_identity_and_scorer_abi(self):
        p = fixture()
        for method in ("squared_distance", "cosine"):
            row = predict(p, method)
            self.assertEqual(set(row), {"query_id", "probabilities"})
            self.assertEqual(row["query_id"], p["query_id"])
            self.assertEqual(row["probabilities"], [0, 0, 0, 1, 0, 0, 0, 0])
        self.assertEqual(predict(p, "uniform")["probabilities"], [0.125] * 8)

    def test_ridge_closed_form_all_registered_lambdas(self):
        # For eight bipolar basis images K = I/4 + J/4, and H K H = H/4.
        for lam in ref.RIDGES:
            values = predict(fixture(), "linear_ridge", ridge_lambda=lam)["probabilities"]
            alpha = 0.25 / (0.25 + lam)
            expected = [0.125 + alpha * (int(i == 3) - 0.125) for i in range(8)]
            for actual, wanted in zip(values, expected):
                self.assertAlmostEqual(actual, wanted, places=12)

    def test_ridge_independent_intercept_system_with_masks(self):
        arrays = [[None if (c + p) % 5 == 0 else (c * 17 + p * 39) % 256
                   for p in range(6)] for c in range(9)]
        # Explicit feature vectors; invalid response is zero, invalid mask is one.
        features = [[(0 if v is None else (2 * v / 255 - 1)) / math.sqrt(12)
                     for v in a] + [int(v is None) / math.sqrt(12) for v in a] for a in arrays]
        dot = lambda a, b: sum(x * y for x, y in zip(a, b))
        lam = 0.1
        matrix = [[dot(a, b) + lam * int(i == j) for j, b in enumerate(features[:8])] + [1]
                  for i, a in enumerate(features[:8])] + [[1] * 8 + [0]]
        raw = []
        for c in range(8):
            fit = gauss_solve(matrix, [int(c == i) for i in range(8)] + [0])
            raw.append(fit[8] + sum(fit[j] * dot(features[j], features[-1]) for j in range(8)))
        positive = [max(0, x) for x in raw]
        expected = [x / sum(positive) for x in positive]
        actual = predict(fixture(arrays), "linear_ridge", ridge_lambda=lam)["probabilities"]
        for a, b in zip(actual, expected):
            self.assertAlmostEqual(a, b, places=12)

    def test_common_mask_never_uses_invalid_color_as_signal(self):
        arrays = [[c * 30, None if c == 0 else 255] for c in range(8)] + [[90, 0]]
        self.assertEqual(predict(fixture(arrays))["probabilities"], [0, 0, 0, 1, 0, 0, 0, 0])
        arrays[0][0] = None
        for method in ("squared_distance", "cosine"):
            self.assertEqual(predict(fixture(arrays), method)["probabilities"], [0.125] * 8)

    def test_degenerate_and_invalid_evidence_keeps_all_classes(self):
        for arrays in ([[[128] * 3] * 9, [[None] * 3] * 9,
                        [[0] * 3] * 8 + [[None] * 3]]):
            for method in ref.METHODS:
                options = {"ridge_lambda": 0.001} if method == "linear_ridge" else {}
                self.assertEqual(predict(fixture(arrays), method, **options)["probabilities"], [0.125] * 8)

    def test_exact_ties_share_mass_and_support_order_is_fixed(self):
        packet = fixture([[30]] * 2 + [[100]] * 6 + [[30]])
        self.assertEqual(predict(packet)["probabilities"], [0.5, 0.5, 0, 0, 0, 0, 0, 0])
        packet["calibration"].reverse()
        with self.assertRaises(ref.ReferenceError):
            predict(packet)

    def test_independent_queries_and_global_pixel_permutation(self):
        original = fixture()
        before = wire(original)
        result = predict(original, "linear_ridge", ridge_lambda=0.01)
        predict(fixture([[i * 20] for i in range(9)]), "linear_ridge", ridge_lambda=100)
        self.assertEqual(result, predict(original, "linear_ridge", ridge_lambda=0.01))
        self.assertEqual(before, wire(original))
        arrays = [[255 if p == c else 0 for p in range(8)] for c in range(8)]
        arrays.append(arrays[3])
        permuted = fixture([list(reversed(a)) for a in arrays])
        self.assertEqual(result, predict(permuted, "linear_ridge", ridge_lambda=0.01))

    def test_private_fields_and_identity_geometry_errors_refused(self):
        changes = [lambda p: p["query"].update(direction_degrees=0),
                   lambda p: p.update(source_record="private"),
                   lambda p: p["query"].update(map_id=p["calibration"][0]["map_id"]),
                   lambda p: p["query"].update(shape=[2, 4]),
                   lambda p: p["query"].update(scale=2.0),
                   lambda p: p["query"].update(invalid_pixels=1),
                   lambda p: p["calibration"].pop(),
                   lambda p: p["query"].update(native_hz=True)]
        for change in changes:
            packet = fixture()
            change(packet)
            with self.assertRaises(ref.ReferenceError):
                predict(packet)

    def test_corrupt_png_trailing_stream_and_expansion_refused(self):
        for mode in ("crc", "trailing", "expansion"):
            packet = fixture()
            body = bytearray(base64.b64decode(packet["query"]["png_base64"]))
            if mode == "crc":
                body[29] ^= 1
            elif mode == "trailing":
                body.extend(b"x")
            else:
                # Valid header/CRC with two decoded rows in a declared one-row image.
                compressed = zlib.compress(b"\0" * 50)
                chunk = struct.pack(">I", len(compressed)) + b"IDAT" + compressed
                chunk += struct.pack(">I", zlib.crc32(b"IDAT" + compressed))
                body = body[:33] + chunk + body[-12:]
            packet["query"]["png_base64"] = base64.b64encode(body).decode()
            with self.assertRaises(ref.ReferenceError):
                predict(packet)

    def test_budget_duplicate_json_and_configuration_refused(self):
        packet = wire(fixture())
        for kwargs in ({"max_packet_bytes": len(packet) - 1, "max_map_pixels": 100},
                       {"max_packet_bytes": 20000, "max_map_pixels": 7}):
            with self.assertRaises(ref.ReferenceError):
                ref.predict(packet, method="uniform", **kwargs)
        with self.assertRaises(ref.ReferenceError):
            ref.predict(b'{"schema":"bad",' + packet[1:], method="uniform",
                        max_packet_bytes=20000, max_map_pixels=100)
        for lam in (None, 0, True, -1, 0.2, float("nan")):
            with self.assertRaises(ref.ReferenceError):
                predict(fixture(), "linear_ridge", ridge_lambda=lam)

    def test_existing_delivery_png_is_accepted_without_transformation(self):
        spec = importlib.util.spec_from_file_location("fus_original_delivery",
                          HERE.parent / "fullfield-delivery-v1" / "delivery.py")
        delivery = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(delivery)
        packet = fixture()
        original = copy.deepcopy(packet)
        for item in packet["calibration"] + [packet["query"]]:
            values, mask = ref.png_pixels(item["png_base64"], item["shape"])
            rgb = b"".join(bytes((v, v, v)) for v in values)
            item["png_base64"] = base64.b64encode(delivery._png(rgb, item["shape"])).decode()
        packet["context"] = delivery.CONTEXT
        self.assertEqual(predict(packet), predict(original))


if __name__ == "__main__":
    unittest.main()
