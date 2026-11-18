"""Generated controls only; no authentic signal, target or model execution."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import unittest
import zlib

import viewer


def encode(role, rows):
    return json.dumps({"role": role, "representation": viewer.REPRESENTATION, "rows": rows},
                      sort_keys=True, separators=(",", ":")).encode()


def decode_png(body):
    assert body[:8] == b"\x89PNG\r\n\x1a\n"
    position, kinds, compressed = 8, [], b""
    while position < len(body):
        length = struct.unpack(">I", body[position:position + 4])[0]
        kind = body[position + 4:position + 8]
        data = body[position + 8:position + 8 + length]
        crc = struct.unpack(">I", body[position + 8 + length:position + 12 + length])[0]
        assert crc == zlib.crc32(kind + data) & 0xffffffff
        kinds.append(kind)
        if kind == b"IHDR":
            width, height, depth, color, compression, filtering, interlace = struct.unpack(">IIBBBBB", data)
            assert (depth, color, compression, filtering, interlace) == (8, 2, 0, 0, 0)
        elif kind == b"IDAT":
            compressed += data
        position += 12 + length
    assert kinds == [b"IHDR", b"IDAT", b"IEND"] and position == len(body)
    raw = zlib.decompress(compressed)
    stride = width * 3 + 1
    assert len(raw) == height * stride
    assert all(raw[y * stride] == 0 for y in range(height))

    def pixel(x, y):
        begin = y * stride + 1 + x * 3
        return raw[begin:begin + 3]
    return width, height, pixel, raw


class ViewerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rows = {"training": [], "query": []}
        number = 1
        for group in range(32):
            for cell in viewer.CELLS:
                for label in range(26):
                    for _ in range(2):
                        row = {"id": f"{number:064x}", "cell": cell}
                        role = "training" if group < 31 else "query"
                        if role == "training":
                            row.update(group=f"{group + 100000:064x}", label=label)
                        rows[role].append(row)
                        number += 1
        cls.rows = rows
        cls.manifests = {role: encode(role, records) for role, records in rows.items()}
        cls.aliases = [row["id"] for records in rows.values() for row in records]
        cls.values = [0.0] * (viewer.CHANNELS * viewer.SAMPLES)
        cls.values[2 * 301 + 150] = 10.0
        cls.body = struct.pack("<18662f", *cls.values)
        cls.certificate = {"source_commit": viewer.SOURCE_COMMIT, "sampling_hz": 600, "units": "uV",
                           "channel_names": ["PO4", "TP8"] + [f"C{index}" for index in range(2, 62)],
                           "policy": "raw_fixed_window_v1",
                           "bad_channel_policy": "global_zero_PO4_TP8_before_average_reference"}

    def session(self, body=None, *, training=None, query=None):
        body = self.body if body is None else body
        pins = {alias: {"bytes": viewer.WINDOW_BYTES, "sha256": hashlib.sha256(body).hexdigest()}
                for alias in self.aliases}
        reads = []

        def read(alias):
            reads.append(alias)
            return body
        session = viewer.FoldViewer(self.manifests["training"] if training is None else training,
                                    self.manifests["query"] if query is None else query,
                                    pins, self.certificate, read)
        return session, reads, pins

    def request(self, **changes):
        request = {"role": "query", "id": self.rows["query"][0]["id"], "channel_start": 2,
                   "channel_count": 1, "sample_start": 0, "sample_stop": 301, "uv_per_division": 10}
        request.update(changes)
        return request

    def test_incumbent_contract_matches_without_importing_data_modules(self):
        legacy = Path(os.environ.get("MORSE_LEGACY_ROOT", Path(__file__).resolve().parents[1] / "registered-runtime"))
        path = legacy / "contract.py"
        spec = importlib.util.spec_from_file_location("morse_contract_for_view_test", path)
        contract = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(contract)
        self.assertEqual((contract.SOURCE_COMMIT, contract.RATE, contract.CHANNELS, contract.SAMPLES,
                          contract.CLASSES, contract.CELLS),
                         (viewer.SOURCE_COMMIT, viewer.RATE, viewer.CHANNELS, viewer.SAMPLES,
                          viewer.CLASSES, viewer.CELLS))

    def test_full_roster_and_training_support_are_required(self):
        for role in ("training", "query"):
            changed = encode(role, self.rows[role][:-1])
            with self.assertRaises(viewer.ViewerError):
                self.session(**{role: changed})
        records = json.loads(self.manifests["training"])["rows"]
        records[0]["label"] = 1
        with self.assertRaises(viewer.ViewerError):
            self.session(training=encode("training", records))
        records = json.loads(self.manifests["query"])["rows"]
        records[0]["cell"] = viewer.CELLS[1]
        with self.assertRaises(viewer.ViewerError):
            self.session(query=encode("query", records))

    def test_manifest_boundary_duplicates_order_and_cross_role_overlap(self):
        records = json.loads(self.manifests["query"])["rows"]
        records[0]["label"] = 3
        with self.assertRaises(viewer.ViewerError):
            self.session(query=encode("query", records))
        records = json.loads(self.manifests["query"])["rows"]
        records[0]["id"] = records[1]["id"]
        with self.assertRaises(viewer.ViewerError):
            self.session(query=encode("query", records))
        with self.assertRaises(viewer.ViewerError):
            self.session(query=encode("query", list(reversed(self.rows["query"]))))
        records = json.loads(self.manifests["query"])["rows"]
        records[0]["id"] = self.rows["training"][0]["id"]
        with self.assertRaises(viewer.ViewerError):
            self.session(query=encode("query", sorted(records, key=lambda row: row["id"])))
        with self.assertRaises(viewer.ViewerError):
            self.session(query=b'{"role":"query","role":"query"}')

    def test_png_retains_sample_geometry_and_physical_scale(self):
        session, reads, _ = self.session()
        response = session.view(self.request())
        width, height, pixel, _ = decode_png(response["image"])
        self.assertEqual((width, height), (1000, 128))
        self.assertEqual(pixel(500, 40), b"\x18\x18\x18")  # sample150,10uV,24pixels/division
        self.assertEqual(pixel(48, 64), b"\x18\x18\x18")
        self.assertEqual(pixel(952, 64), b"\x18\x18\x18")
        self.assertEqual(reads, [self.rows["query"][0]["id"]])
        self.assertEqual((response["metadata"]["time_start_ms"], response["metadata"]["time_last_ms"]), (0, 500))
        self.assertEqual(set(response), {"mime_type", "image", "metadata"})
        self.assertFalse(set(response["metadata"]) & {"label", "group", "participant", "source_identity", "values"})

    def test_each_sample_changes_render_and_clipping_is_visible(self):
        a, _, _ = self.session()
        values = list(self.values)
        values[2 * 301 + 150], values[2 * 301 + 149] = 0.0, 10.0
        b, _, _ = self.session(struct.pack("<18662f", *values))
        self.assertNotEqual(a.view(self.request())["image"], b.view(self.request())["image"])
        response = a.view(self.request(uv_per_division=0.5))
        _, _, _, raw = decode_png(response["image"])
        self.assertIn(b"\xdc\x22\x22", raw)
        self.assertEqual(response["metadata"]["uv_per_division"], 0.5)
        self.assertFalse(response["metadata"]["rendering"]["autoscaling"])

    def test_invalid_navigation_cannot_read_signals(self):
        session, reads, _ = self.session()
        for changes in ({"id": "f" * 64}, {"role": "training"}, {"sample_stop": 302},
                        {"sample_start": 300}, {"channel_start": 61, "channel_count": 2},
                        {"channel_count": 9}, {"uv_per_division": True}, {"sample_start": False},
                        {"source_path": "/private/targets"}):
            with self.assertRaises(viewer.ViewerError):
                session.view(self.request(**changes))
        self.assertEqual(reads, [])

    def test_fixed_gain_choices_cover_float32_extremes(self):
        largest = struct.unpack("<f", bytes.fromhex("ffff7f7f"))[0]
        for value, gain in ((2.0 ** -149, 2.0 ** -149), (largest, 2.0 ** 128)):
            values = [0.0] * (62 * 301)
            values[2 * 301 + 150] = value
            session, _, _ = self.session(struct.pack("<18662f", *values))
            response = session.view(self.request(uv_per_division=gain))
            _, _, pixel, raw = decode_png(response["image"])
            self.assertEqual(pixel(500, 40), b"\x18\x18\x18")
            self.assertNotIn(b"\xdc\x22\x22", raw)
            self.assertEqual(response["metadata"]["uv_per_division"], gain)

    def test_snapshot_hash_finiteness_and_fixed_zero_channels(self):
        session, _, pins = self.session()
        pins[self.rows["query"][0]["id"]]["sha256"] = "0" * 64
        session.view(self.request())  # Constructor snapshot is unaffected by caller mutation.
        session._read_window = lambda _: b"\x00" * viewer.WINDOW_BYTES
        with self.assertRaises(viewer.ViewerError):
            session.view(self.request())
        for position, value in ((3 * 301, float("nan")), (0, 1.0)):
            values = list(self.values)
            values[position] = value
            invalid, _, _ = self.session(struct.pack("<18662f", *values))
            with self.assertRaises(viewer.ViewerError):
                invalid.view(self.request())

    def test_calibration_is_optional_public_and_not_mutable_through_index(self):
        session, reads, _ = self.session()
        rows = session.index("training", 0, 1)
        self.assertEqual(set(rows[0]), {"id", "group", "cell", "label"})
        rows[0]["label"] = 25
        self.assertEqual(session.index("training", 0, 1)[0]["label"], 0)
        response = session.view(self.request(role="training", id=self.rows["training"][0]["id"]))
        self.assertEqual(response["metadata"]["label"], 0)
        self.assertIn("group", response["metadata"])
        self.assertEqual(len(reads), 1)

    def test_complete_immutable_probabilities_and_finalization(self):
        session, reads, _ = self.session()
        with self.assertRaises(viewer.ViewerError):
            session.finish()
        alias = self.rows["query"][0]["id"]
        for bad in ([1.0] * 26, [float("nan")] + [0.0] * 25, [True] + [0.0] * 25,
                    [1.0] + [0.0] * 24, [-1.0, 2.0] + [0.0] * 24):
            with self.assertRaises(viewer.ViewerError):
                session.answer({"id": alias, "probabilities": bad})
        probabilities = [1.0] + [0.0] * 25
        session.answer({"id": alias, "probabilities": probabilities})
        probabilities[0] = 0.0
        with self.assertRaises(viewer.ViewerError):
            session.answer({"id": alias, "probabilities": [1.0] + [0.0] * 25})
        with self.assertRaises(viewer.ViewerError):
            session.answer({"id": self.rows["training"][0]["id"], "probabilities": [1.0] + [0.0] * 25})
        for row in self.rows["query"][1:]:
            session.answer({"id": row["id"], "probabilities": [1.0] + [0.0] * 25})
        result = session.finish()
        self.assertEqual(result["count"], 312)
        self.assertEqual(result["predictions"][0]["probabilities"][0], 1.0)
        self.assertFalse(result["scientific_qualification"])
        self.assertEqual(reads, [])  # Calibration or viewing is never silently mandatory.
        self.assertEqual(result["prediction_sha256"], hashlib.sha256(viewer._json_bytes(result["predictions"])).hexdigest())
        for operation in (session.finish, lambda: session.index("query", 0, 1),
                          lambda: session.view(self.request()),
                          lambda: session.answer({"id": alias, "probabilities": [1.0] + [0.0] * 25})):
            with self.assertRaises(viewer.ViewerError):
                operation()

    def test_malformed_public_values_do_not_consume_answers_or_escape_refusal(self):
        session, reads, _ = self.session()
        for role in ([], {}, False):
            with self.assertRaises(viewer.ViewerError):
                session.index(role, 0, 1)
        alias = self.rows["query"][0]["id"]
        for value in (10 ** 400, -(10 ** 400)):
            with self.assertRaises(viewer.ViewerError):
                session.answer({"id": alias, "probabilities": [value] + [0.0] * 25})
        accepted = session.answer({"id": alias, "probabilities": [1.0] + [0.0] * 25})
        self.assertEqual(accepted["remaining"], 311)
        self.assertEqual(reads, [])


if __name__ == "__main__":
    unittest.main(verbosity=1)
