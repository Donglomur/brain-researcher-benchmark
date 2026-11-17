"""Independent source controls for complete FUS nine-map evidence delivery.

The invented fixture preserves all 49 registered rows and 20,622 declared slots.
It supplies no authentic data or physical clock/source authentication. PNG pixel
expectations, calibration order and query membership are calculated independently
of the implementation; production encoding helpers are not used as test oracles.
"""
import base64
import builtins
import copy
import hashlib
import json
from pathlib import Path
import struct
import types
import unittest
import zlib


ROOT = Path(__file__).resolve().parents[2]
TASK_HOME = ROOT / "benchmarks/neural/NEURAL-SCOPE-20261114-FUS-DIRECTION"
SOURCE = TASK_HOME / "implementations/fullfield-delivery-v1/delivery.py"
MODULE = types.ModuleType("fus_delivery_under_test")
MODULE.__file__ = str(SOURCE)
exec(compile(SOURCE.read_bytes(), str(SOURCE), "exec"), MODULE.__dict__)

FOLD_KEY = "fold_" + "f" * 32
RGB = bytes((0, 0, 0, 128, 128, 128, 255, 255, 255,
             255, 0, 255, 64, 64, 64, 192, 192, 192))
CONTRACT_SHA256 = "a0fc7cd1008f907df8d24c8a2133896d99b90915764debd141194022914f301f"
ROSTER_SHA256 = "deb726b85aa3c8894cfebe0485ce22ceb99fa55f97c3a52a22f4e4cccabacc8d"
CAPS = dict(max_map_bytes=1_000_000, max_packet_bytes=100_000,
            max_total_packet_bytes=100_000_000)


def decode_png_independently(encoded):
    """Decode only the required noninterlaced RGB8/filter-0 PNG representation."""
    png = base64.b64decode(encoded, validate=True)
    if png[:8] != b"\x89PNG\r\n\x1a\n":
        raise AssertionError("not PNG")
    at, width, height, compressed, kinds = 8, None, None, bytearray(), []
    while at < len(png):
        if at + 12 > len(png):
            raise AssertionError("truncated PNG chunk")
        size = struct.unpack(">I", png[at:at + 4])[0]
        kind = png[at + 4:at + 8]
        end = at + 8 + size
        if end + 4 > len(png):
            raise AssertionError("truncated PNG body")
        body = png[at + 8:end]
        crc = struct.unpack(">I", png[end:end + 4])[0]
        if zlib.crc32(kind + body) & 0xffffffff != crc:
            raise AssertionError("PNG CRC mismatch")
        kinds.append(kind)
        if kind == b"IHDR":
            if len(body) != 13 or width is not None:
                raise AssertionError("invalid IHDR")
            width, height, depth, color, compression, filtering, interlace = struct.unpack(
                ">IIBBBBB", body)
            if (depth, color, compression, filtering, interlace) != (8, 2, 0, 0, 0):
                raise AssertionError("not native RGB8 PNG")
        elif kind == b"IDAT":
            compressed.extend(body)
        elif kind == b"IEND":
            if body or end + 4 != len(png):
                raise AssertionError("invalid terminal PNG chunk")
        else:
            raise AssertionError("unexpected PNG metadata or encoding")
        at = end + 4
    if not kinds or kinds[0] != b"IHDR" or kinds[-1] != b"IEND":
        raise AssertionError("PNG order")
    inflated = zlib.decompress(bytes(compressed))
    stride = 1 + 3 * width
    if len(inflated) != height * stride:
        raise AssertionError("wrong native pixel extent")
    pixels = bytearray()
    for y in range(height):
        row = inflated[y * stride:(y + 1) * stride]
        if row[0] != 0:
            raise AssertionError("test oracle expects unfiltered scanlines")
        pixels.extend(row[1:])
    return width, height, bytes(pixels)


def invented_complete_intake():
    """Build from task metadata; never use production packet/partition helpers."""
    task = json.loads((TASK_HOME / "task.json").read_text())
    records, serial = [], 0
    for declared in task["full_population"]["declared_source_records"]:
        rid = "%s-S%d-R%d" % (declared["Monkey"], declared["Session"], declared["Run"])
        trials = []
        for index in range(declared["nTrials"]):
            direction = index // 2 if index < 16 else index % 8
            trials.append({
                "source_trial_id": "PRIVATE_SOURCE_" + rid + "_" + str(index),
                "source_order": index, "disposition": "eligible",
                "query_id": "q_%032x" % serial, "direction": direction,
                "timing": {"cue": 0, "memory_start": 2, "memory_end": 4, "go": 5,
                           "baseline_start": -2, "baseline_end": -1,
                           "acquisition_start": 3, "acquisition_end": 4},
                "exclusion_reason": None, "adjudication_sha256": None,
            })
            serial += 1
        records.append({
            "record_id": rid, "native_hz": 1 if trials else None,
            "reconciliation_sha256": "a" * 64,
            "clock_mapping_sha256": "b" * 64 if trials else None,
            "representation_sha256": "c" * 64 if trials else None, "trials": trials,
        })
    assert len(records) == 49 and serial == 20622
    return {"schema": "fus_adjudicated_intake_v1", "contract_sha256": CONTRACT_SHA256,
            "source_roster_sha256": ROSTER_SHA256, "source_archive_sha256": "d" * 64,
            "intake_review_sha256": "e" * 64, "records": records}


def load_existing_preparation_without_global_imports():
    """Load the unchanged producer in an isolated three-module import namespace."""
    modules = {}
    native_import = builtins.__import__

    def local_import(name, globals=None, locals=None, fromlist=(), level=0):
        if level == 0 and name in ("roster", "scorer", "fullfield"):
            return modules[name]
        return native_import(name, globals, locals, fromlist, level)

    home = TASK_HOME / "implementations/fullfield-preparation"
    for name in ("roster", "scorer", "fullfield"):
        path = home / (name + ".py")
        module = types.ModuleType("fus_independent_existing_" + name)
        module.__file__ = str(path)
        module.__dict__["__builtins__"] = {**vars(builtins), "__import__": local_import}
        modules[name] = module
        exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
    return modules["fullfield"]


class FUSDeliveryControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.intake = invented_complete_intake()
        cls.held = next(r for r in cls.intake["records"] if r["record_id"] == "L-S27-R99")
        cls.trials_by_qid = {t["query_id"]: t for t in cls.held["trials"]}
        cls.calibration_ids = [cls.held["trials"][i]["query_id"] for i in range(0, 16, 2)]
        cls.query_ids = [t["query_id"] for t in cls.held["trials"]
                         if t["query_id"] not in set(cls.calibration_ids)]

    def setUp(self):
        n = len(self.held["trials"])
        self.receipt = {
            "schema": "fus_fullfield_fold_receipt_v1", "status": "source_component_completed",
            "fold_key": FOLD_KEY, "roster_records": 49, "positive_records": 48,
            "declared_source_trials": 20622, "training_records": 47,
            "training_maps": 20622 - n, "training_valid_pixels": 6 * (20622 - n),
            "training_invalid_pixels": 0, "held_adjudicated_exclusions": 0,
            "scale": 2.0, "calibration_maps": 8, "query_maps": n - 8,
            "invalid_pixels": n, "saturated_pixels": 0,
            "native_source_authenticated": False, "full_resolution_delivery_qualified": False,
            "protected_evaluation_established": False, "scientifically_qualified": False,
        }

    def load_map(self, qid):
        t = self.trials_by_qid[qid]
        calibration = qid in self.calibration_ids
        value = {"schema": "fus_fullfield_map_v1", "fold_key": FOLD_KEY,
                 "query_id": qid, "role": "calibration" if calibration else "query",
                 "scale": 2.0, "shape": [2, 3], "spatial_pitch": [0.25, 0.5],
                 "spatial_pitch_unit": "mm", "native_hz": 1, "source_float": "binary32",
                 "rgb": RGB, "invalid_pixels": 1, "saturated_pixels": 0}
        if calibration:
            value["direction"] = t["direction"]
        return value

    def run_delivery(self, *, intake=None, receipt=None, loader=None, stage=None, **caps):
        outputs = []
        result = MODULE.prepare_packets(
            self.intake if intake is None else intake,
            self.receipt if receipt is None else receipt,
            self.load_map if loader is None else loader,
            outputs.append if stage is None else stage,
            held_record_id=self.held["record_id"], **{**CAPS, **caps})
        return result, outputs

    def test_complete_fold_and_independent_png_pixels(self):
        result, outputs = self.run_delivery()
        self.assertEqual(len(outputs), len(self.held["trials"]) - 8)
        self.assertEqual([json.loads(b)["query_id"] for b in outputs], self.query_ids)
        self.assertTrue(all(type(b) is bytes for b in outputs))
        first = json.loads(outputs[0])
        self.assertEqual(first["schema"], "fus_nine_map_packet_v1")
        self.assertEqual(first["fold_key"], FOLD_KEY)
        self.assertEqual(first["class_angles_degrees"], list(range(0, 360, 45)))
        self.assertEqual(len(first["calibration"]), 8)
        self.assertEqual([m["map_id"] for m in first["calibration"]], self.calibration_ids)
        self.assertEqual([m["direction_degrees"] for m in first["calibration"]],
                         list(range(0, 360, 45)))
        self.assertEqual(first["query"]["map_id"], self.held["trials"][1]["query_id"])
        self.assertNotIn("direction_degrees", first["query"])
        for value in [*first["calibration"], first["query"]]:
            self.assertEqual(decode_png_independently(value["png_base64"]), (3, 2, RGB))
            self.assertEqual(value["shape"], [2, 3])
            self.assertEqual(value["spatial_pitch"], [0.25, 0.5])
        self.assertIs(result["scientifically_qualified"], False)
        self.assertIs(result["protected_evaluation_established"], False)
        self.assertIs(result["native_source_authenticated"], False)
        self.assertIs(result["full_resolution_delivery_qualified"], False)

    def test_actual_fullfield_preparation_feeds_complete_packet_delivery(self):
        producer = load_existing_preparation_without_global_imports()
        record_by_id = {row["record_id"]: row for row in self.intake["records"]}
        loads, prepared = [], {}
        baseline = [2, 2, 2, 0, 2, 2]
        memory = [-2, 2, 6, 1, 0, 4]
        expected = bytes((0, 0, 0, 128, 128, 128, 255, 255, 255,
                          255, 0, 255, 64, 64, 64, 191, 191, 191))

        def normalized(rid):
            loads.append(rid)
            row = record_by_id[rid]
            return {
                "schema": "fus_normalized_fullfield_record_v1", "record_id": rid,
                "native_hz": row["native_hz"], "source_float": "binary32",
                "shape": [2, 3], "spatial_pitch": [0.25, 0.5], "spatial_pitch_unit": "mm",
                "acquisition_census_sha256": "b" * 64,
                "trials": [{"source_trial_id": t["source_trial_id"],
                            "source_order": t["source_order"], "frames": [
                                {"frame_id": "baseline", "source_order": 0,
                                 "start": -2, "end": -1, "complete": True, "pixels": baseline},
                                {"frame_id": "memory", "source_order": 1,
                                 "start": 3, "end": 4, "complete": True, "pixels": memory}]
                            } for t in row["trials"]],
            }

        def retain(payload):
            self.assertNotIn(payload["query_id"], prepared)
            self.assertEqual(payload["rgb"], expected)
            prepared[payload["query_id"]] = payload

        production_receipt = producer.prepare_fold(
            self.intake, normalized, retain, held_record_id=self.held["record_id"],
            fold_key=FOLD_KEY)
        positive = [r["record_id"] for r in self.intake["records"] if r["trials"]]
        self.assertEqual(loads, [rid for rid in positive if rid != self.held["record_id"]]
                         + [self.held["record_id"]])
        self.assertEqual(len(loads), 48)
        self.assertEqual(production_receipt["training_maps"], 20622 - len(self.held["trials"]))
        self.assertEqual(production_receipt["scale"], 2.0)
        self.assertEqual(production_receipt["training_valid_pixels"],
                         5 * production_receipt["training_maps"])
        self.assertEqual(production_receipt["training_invalid_pixels"],
                         production_receipt["training_maps"])
        result, packets = self.run_delivery(receipt=production_receipt, loader=prepared.__getitem__)
        self.assertEqual(len(packets), len(self.query_ids))
        self.assertEqual([json.loads(p)["query_id"] for p in packets], self.query_ids)
        for packet in (json.loads(packets[0]), json.loads(packets[-1])):
            for image in [*packet["calibration"], packet["query"]]:
                self.assertEqual(decode_png_independently(image["png_base64"]), (3, 2, expected))
        self.assertIs(result["scientifically_qualified"], False)

    def test_canonical_reproducible_wire_packets(self):
        _, first = self.run_delivery()
        _, second = self.run_delivery()
        self.assertEqual(first, second)
        for packet in first:
            self.assertEqual(packet, json.dumps(json.loads(packet), sort_keys=True,
                                               separators=(",", ":"), allow_nan=False).encode())

    def test_public_packet_has_only_declared_fields(self):
        _, packets = self.run_delivery()
        packet = json.loads(packets[0])
        self.assertEqual(set(packet), {"schema", "fold_key", "query_id", "class_angles_degrees",
                                       "context", "calibration", "query"})
        public = {"map_id", "shape", "spatial_pitch", "spatial_pitch_unit", "native_hz",
                  "source_float", "scale", "invalid_pixels", "saturated_pixels", "png_base64"}
        self.assertEqual(set(packet["query"]), public)
        for support in packet["calibration"]:
            self.assertEqual(set(support), public | {"direction_degrees"})
        self.assertNotIn(b"PRIVATE_SOURCE_", packets[0])
        self.assertNotIn(self.held["record_id"].encode(), packets[0])

    def test_complete_census_is_required_before_loading(self):
        calls = []
        incomplete = {**self.intake, "records": self.intake["records"][:-1]}
        with self.assertRaises(ValueError):
            self.run_delivery(intake=incomplete, loader=lambda q: calls.append(q))
        self.assertEqual(calls, [])

    def test_zero_record_cannot_be_omitted(self):
        incomplete = {**self.intake, "records": [r for r in self.intake["records"]
                                                if r["record_id"] != "L-S45-R1"]}
        with self.assertRaises(ValueError):
            self.run_delivery(intake=incomplete)

    def test_duplicate_physical_trial_identity_is_refused(self):
        intake = copy.deepcopy(self.intake)
        positive = [r for r in intake["records"] if r["trials"]]
        positive[1]["trials"][0]["source_trial_id"] = positive[0]["trials"][0]["source_trial_id"]
        with self.assertRaises(ValueError):
            self.run_delivery(intake=intake)

    def test_receipt_inconsistencies_are_refused(self):
        variants = {"roster_records": 48, "positive_records": 47,
                    "declared_source_trials": 20621, "training_records": 46,
                    "training_maps": 1, "calibration_maps": 7, "query_maps": 1,
                    "invalid_pixels": 0, "scale": 0.0,
                    "scientifically_qualified": True,
                    "native_source_authenticated": True}
        for name, value in variants.items():
            with self.subTest(field=name), self.assertRaises(ValueError):
                self.run_delivery(receipt={**self.receipt, name: value})

    def test_foreign_fold_maps_are_refused(self):
        def foreign(qid):
            return {**self.load_map(qid), "fold_key": "fold_" + "0" * 32}
        with self.assertRaises(ValueError):
            self.run_delivery(loader=foreign)

    def test_wrong_map_identity_and_role_are_refused(self):
        for field, value in (("query_id", "q_" + "f" * 32), ("role", "query")):
            with self.subTest(field=field):
                def corrupted(qid):
                    result = self.load_map(qid)
                    if qid == self.calibration_ids[0]:
                        result[field] = value
                    return result
                with self.assertRaises(ValueError):
                    self.run_delivery(loader=corrupted)

    def test_calibration_direction_cannot_be_swapped(self):
        def corrupted(qid):
            result = self.load_map(qid)
            if qid == self.calibration_ids[0]:
                result["direction"] = 1
            return result
        with self.assertRaises(ValueError):
            self.run_delivery(loader=corrupted)

    def test_private_or_unknown_map_fields_are_refused(self):
        for field in ("targetPos", "source_trial_id", "record_id", "unknown"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.run_delivery(loader=lambda q: {**self.load_map(q), field: "PRIVATE_SENTINEL"})

    def test_query_label_cannot_enter_packet(self):
        def corrupted(qid):
            result = self.load_map(qid)
            if qid in self.query_ids:
                result["direction"] = 0
            return result
        with self.assertRaises(ValueError):
            self.run_delivery(loader=corrupted)

    def test_wrong_rgb_extent_and_color_are_refused(self):
        for rgb in (RGB[:-1], RGB + b"\x00", bytes((1, 2, 3)) + RGB[3:], list(RGB)):
            with self.subTest(rgb_type=type(rgb).__name__), self.assertRaises(ValueError):
                self.run_delivery(loader=lambda q: {**self.load_map(q), "rgb": rgb})

    def test_invalid_and_saturated_counts_are_consistent(self):
        for key, value in (("invalid_pixels", 0), ("saturated_pixels", 6),
                           ("invalid_pixels", True), ("saturated_pixels", -1)):
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                self.run_delivery(loader=lambda q: {**self.load_map(q), key: value})

    def test_geometry_and_scale_cannot_change_between_maps(self):
        changes = (("shape", [3, 2]), ("spatial_pitch", [0.5, 0.25]),
                   ("spatial_pitch_unit", "cm"), ("native_hz", 2),
                   ("source_float", "binary64"), ("scale", 3.0))
        for key, value in changes:
            with self.subTest(key=key):
                def corrupted(qid):
                    result = self.load_map(qid)
                    if qid == self.query_ids[0]:
                        result[key] = value
                    return result
                with self.assertRaises(ValueError):
                    self.run_delivery(loader=corrupted)

    def test_resource_caps_refuse_instead_of_truncating(self):
        for name in CAPS:
            with self.subTest(cap=name), self.assertRaises(ValueError):
                self.run_delivery(**{name: 1})

    def test_exact_byte_budgets_and_receipt_account_for_repeated_support(self):
        receipt, packets = self.run_delivery()
        total = sum(len(packet) for packet in packets)
        self.assertEqual(receipt["total_packet_bytes"], total)
        self.assertEqual(receipt["packets"], [
            {"query_id": qid, "bytes": len(packet), "sha256": hashlib.sha256(packet).hexdigest()}
            for qid, packet in zip(self.query_ids, packets)])
        self.assertIs(receipt["publication_requires_success_and_operator_commit"], True)
        _, bounded = self.run_delivery(max_map_bytes=len(RGB),
                                       max_packet_bytes=max(map(len, packets)),
                                       max_total_packet_bytes=total)
        self.assertEqual(bounded, packets)
        staged = []
        with self.assertRaises(ValueError):
            self.run_delivery(max_total_packet_bytes=total - 1, stage=staged.append)
        self.assertLess(len(staged), len(packets))
        self.assertEqual(staged, packets[:len(staged)])
        with self.assertRaises(ValueError):
            self.run_delivery(max_map_bytes=len(RGB) - 1)
        with self.assertRaises(ValueError):
            self.run_delivery(max_packet_bytes=min(map(len, packets)) - 1)

    def test_invalid_resource_caps_are_not_coerced(self):
        for cap in (True, 0, -1, 1.5):
            with self.subTest(cap=cap), self.assertRaises(ValueError):
                self.run_delivery(max_map_bytes=cap)

    def test_stage_failure_propagates_without_success(self):
        class StageFailure(Exception):
            pass
        staged = []
        def stage(packet):
            staged.append(packet)
            raise StageFailure("invented storage failure")
        with self.assertRaises(StageFailure):
            self.run_delivery(stage=stage)
        self.assertEqual(len(staged), 1)

    def test_late_missing_or_malformed_query_cannot_complete(self):
        last = self.query_ids[-1]
        for missing in (False, True):
            staged = []
            def corrupted(qid):
                if qid == last:
                    if missing:
                        raise LookupError("invented missing final map")
                    return {**self.load_map(qid), "rgb": b""}
                return self.load_map(qid)
            with self.subTest(missing=missing), self.assertRaises((ValueError, LookupError)):
                self.run_delivery(loader=corrupted, stage=staged.append)
            self.assertLessEqual(len(staged), len(self.query_ids) - 1)


if __name__ == "__main__":
    unittest.main()
