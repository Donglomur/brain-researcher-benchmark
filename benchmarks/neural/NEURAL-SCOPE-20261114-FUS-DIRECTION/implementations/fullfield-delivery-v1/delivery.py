"""Complete-fold, identical nine-map packets for the declared FUS condition.

Inputs are evaluator-private outputs of the existing full-field preparation
component. This module does not decode native MAT clocks, authenticate biological
inputs, run participants, or qualify a provider's full-resolution image route.
All emitted packets are private staging artifacts until successful completion.
"""
import base64
import builtins
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import struct
import types
import zlib


class DeliveryError(ValueError):
    """The complete delivery cannot be admitted; staged output is incomplete."""


_DEPENDENCIES = {
    "roster": (2755, "0f1ac943d56edc5305be4ba74f5d27c8cfa626e555092b7a51a1f6f2641dd4c9"),
    "scorer": (14874, "11d1b2a330d5c32c6c2ea93c5c54de5d58c9d4d31008ccafd235afa3a732ad50"),
}
_FOLD = re.compile(r"fold_[0-9a-f]{32}\Z")
_ID = re.compile(r"q_[0-9a-f]{32}\Z")
_MAP_KEYS = frozenset(("schema", "fold_key", "query_id", "role", "scale", "shape",
                       "spatial_pitch", "spatial_pitch_unit", "native_hz",
                       "source_float", "rgb", "invalid_pixels", "saturated_pixels"))
_METADATA = ("shape", "spatial_pitch", "spatial_pitch_unit", "native_hz",
             "source_float", "scale")
_RECEIPT_KEYS = frozenset(("schema", "status", "fold_key", "roster_records",
    "positive_records", "declared_source_trials", "training_records",
    "training_maps", "training_valid_pixels", "training_invalid_pixels",
    "held_adjudicated_exclusions", "scale", "calibration_maps", "query_maps",
    "invalid_pixels", "saturated_pixels", "native_source_authenticated",
    "full_resolution_delivery_qualified", "protected_evaluation_established",
    "scientifically_qualified"))
_HOLDS = ("native_source_authenticated", "full_resolution_delivery_qualified",
          "protected_evaluation_established", "scientifically_qualified")
CONTEXT = (
    "Infer the peripheral target direction from one complete memory-period "
    "functional-ultrasound response map and eight labeled calibration maps. "
    "Functional ultrasound measures a vascular proxy for activity. Angles use "
    "x-right/y-up: 0,45,90,135,180,225,270,315 degrees. Every PNG contains the "
    "complete native field; grayscale is the fixed response encoding and magenta "
    "marks invalid pixels. No resizing, cropping or discarded pixels is allowed. "
    "Return this opaque query_id and eight finite nonnegative class probabilities "
    "summing to one in that angle order. Use a fresh context for this query."
)


def _require(condition, message):
    if not condition:
        raise DeliveryError(message)


def _keys(value, expected, description):
    _require(type(value) is dict and set(value) == expected, description + ": exact keys required")


def _positive_int(value, description):
    _require(type(value) is int and value > 0, description + ": positive integer required")


def _nonnegative_int(value, description):
    _require(type(value) is int and value >= 0, description + ": nonnegative integer required")


def _finite(value):
    try:
        return type(value) in (float, int) and math.isfinite(value)
    except OverflowError:
        return False


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def _scorer():
    """Execute verified source bytes without ambient bare-name imports or pyc."""
    directory = Path(__file__).resolve().parent.parent / "fullfield-preparation"
    sources = {}
    for name, (size, digest) in _DEPENDENCIES.items():
        path = directory / (name + ".py")
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            _require(stat.S_ISREG(os.fstat(fd).st_mode), "dependency must be a regular source file")
            with os.fdopen(fd, "rb", closefd=False) as stream:
                body = stream.read(size + 1)
            _require(len(body) == size and hashlib.sha256(body).hexdigest() == digest,
                     "dependency source identity mismatch")
            sources[name] = (path, body)
        finally:
            os.close(fd)
    modules = {}
    original_import = builtins.__import__

    def private_import(name, globals=None, locals=None, fromlist=(), level=0):
        if level == 0 and name in _DEPENDENCIES:
            _require(name in modules, "dependency order mismatch")
            return modules[name]
        return original_import(name, globals, locals, fromlist, level)

    for name in ("roster", "scorer"):
        path, body = sources[name]
        module = types.ModuleType("_fus_delivery_" + name)
        module.__file__ = str(path)
        module.__dict__["__builtins__"] = {**vars(builtins), "__import__": private_import}
        exec(compile(body, str(path), "exec"), module.__dict__)
        modules[name] = module
    return modules["scorer"]


def _chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)


def _png(rgb, shape):
    """Lossless RGB8, native dimensions, filter zero, no auxiliary chunks."""
    height, width = shape
    stride = width * 3
    filtered = b"".join(b"\x00" + rgb[row * stride:(row + 1) * stride] for row in range(height))
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", header)
            + _chunk(b"IDAT", zlib.compress(filtered, level=9)) + _chunk(b"IEND", b""))


def _map(payload, *, trial, calibration, fold_key, scale, rate, max_bytes):
    expected = _MAP_KEYS | ({"direction"} if calibration else set())
    _keys(payload, expected, "prepared map")
    _require(payload["schema"] == "fus_fullfield_map_v1", "prepared map schema")
    _require(payload["fold_key"] == fold_key and payload["query_id"] == trial["query_id"],
             "map fold or opaque identity mismatch")
    _require(type(payload["query_id"]) is str and _ID.fullmatch(payload["query_id"]), "opaque map identity")
    _require(payload["role"] == ("calibration" if calibration else "query"), "map role mismatch")
    if calibration:
        _require(type(payload["direction"]) is int and payload["direction"] == trial["direction"],
                 "calibration direction differs from frozen earliest eligible support")
    _require(_finite(payload["scale"]) and payload["scale"] > 0
             and type(payload["scale"]) is type(scale) and payload["scale"] == scale,
             "map differs from frozen training-only scale")
    _require(type(payload["native_hz"]) is int and payload["native_hz"] == rate,
             "native acquisition rate mismatch")
    _require(payload["source_float"] in ("binary32", "binary64"), "source float format")
    shape = payload["shape"]
    _require(type(shape) is list and len(shape) == 2 and all(type(v) is int and 0 < v < 2**31 for v in shape),
             "native y,x image shape required")
    pixels = shape[0] * shape[1]
    _require(3 * pixels <= max_bytes, "native map exceeds byte budget; do not resize")
    rgb = payload["rgb"]
    _require(type(rgb) is bytes and len(rgb) == 3 * pixels, "complete native RGB bytes required")
    pitch = payload["spatial_pitch"]
    _require(type(pitch) is list and len(pitch) == 2 and all(_finite(v) and v > 0 for v in pitch),
             "native spatial pitch required")
    unit = payload["spatial_pitch_unit"]
    _require(type(unit) is str and 0 < len(unit) <= 64 and unit.strip() == unit
             and all(ord(c) >= 32 for c in unit), "spatial pitch unit required")
    invalid = 0
    for pos in range(0, len(rgb), 3):
        r, g, b = rgb[pos:pos + 3]
        if (r, g, b) == (255, 0, 255):
            invalid += 1
        else:
            _require(r == g == b, "pixel must be grayscale or the fixed invalid magenta")
    _require(type(payload["invalid_pixels"]) is int and payload["invalid_pixels"] == invalid,
             "invalid-pixel count disagrees with full image")
    _nonnegative_int(payload["saturated_pixels"], "saturated-pixel count")
    _require(payload["saturated_pixels"] <= pixels - invalid, "saturation count exceeds valid pixels")
    result = {"map_id": trial["query_id"], **{key: payload[key] for key in _METADATA},
              "invalid_pixels": invalid, "saturated_pixels": payload["saturated_pixels"],
              "png_base64": base64.b64encode(_png(rgb, shape)).decode("ascii")}
    if calibration:
        result["direction_degrees"] = 45 * trial["direction"]
    # Copy geometry lists: a later callback must not mutate cached calibration metadata.
    result["shape"] = list(shape)
    result["spatial_pitch"] = list(pitch)
    return result


def prepare_packets(intake, fold_receipt, load_map, stage_packet, *, held_record_id,
                    max_map_bytes, max_packet_bytes, max_total_packet_bytes):
    """Stage one complete fold as one immutable nine-map byte packet per query.

    The operator must establish that intake, receipt and maps came from the same
    accepted preparation. Consistency checks here do not authenticate biological
    source, a caller's custody, or callback behavior outside this function.

    load_map(qid) is called once for each of eight calibration maps, then once
    for every query in frozen source order. stage_packet(bytes) must remain
    private until this function returns successfully. A late error leaves any
    earlier staged packets incomplete. Callback exceptions propagate unchanged.
    Byte budgets constrain individual native RGB, individual packet, and total
    staged packet sizes; they are not RSS, physical I/O, or execution deadlines.
    """
    for value, label in ((max_map_bytes, "map budget"), (max_packet_bytes, "packet budget"),
                         (max_total_packet_bytes, "total packet budget")):
        _positive_int(value, label)
    _require(callable(load_map) and callable(stage_packet), "explicit map source and private packet staging callbacks")
    scorer = _scorer()
    try:
        partitions = scorer.validate_intake(intake)
    except scorer.ConstructionError as error:
        raise DeliveryError("complete frozen intake refused: " + str(error)) from error
    _require(type(held_record_id) is str, "explicit private held record required")
    matches = [part for part in partitions if part[0]["record_id"] == held_record_id
               and part[0]["declared_trials"] > 0]
    _require(len(matches) == 1, "held record must be one of the 48 positive records")
    _, record, queries, calibration_count, excluded = matches[0]
    query_ids = {trial["query_id"] for trial in queries}
    calibration = [trial for trial in record["trials"] if trial["disposition"] == "eligible"
                   and trial["query_id"] not in query_ids]
    calibration.sort(key=lambda trial: trial["direction"])
    _require(len(calibration) == calibration_count == 8
             and [trial["direction"] for trial in calibration] == list(range(8)),
             "exact earliest eight-direction calibration required")
    _keys(fold_receipt, _RECEIPT_KEYS, "prepared fold receipt")
    # Keep validated scalar fields independent of subsequent caller callbacks.
    fold_receipt = dict(fold_receipt)
    _require(fold_receipt["schema"] == "fus_fullfield_fold_receipt_v1"
             and fold_receipt["status"] == "source_component_completed", "prepared fold receipt schema/status")
    fold_key = fold_receipt["fold_key"]
    _require(type(fold_key) is str and _FOLD.fullmatch(fold_key), "opaque fold key required")
    for key, value in (("roster_records", 49), ("positive_records", 48),
                       ("declared_source_trials", 20622), ("training_records", 47),
                       ("held_adjudicated_exclusions", excluded), ("calibration_maps", 8),
                       ("query_maps", len(queries))):
        _require(type(fold_receipt[key]) is int and fold_receipt[key] == value,
                 "prepared fold population/counter mismatch: " + key)
    expected_training = sum(len(part[2]) + part[3] for part in partitions
                            if part[0]["record_id"] != held_record_id)
    _require(type(fold_receipt["training_maps"]) is int and fold_receipt["training_maps"] == expected_training,
             "complete training-map count mismatch")
    _positive_int(fold_receipt["training_valid_pixels"], "training valid pixels")
    for key in ("training_invalid_pixels", "invalid_pixels", "saturated_pixels"):
        _nonnegative_int(fold_receipt[key], key)
    _require(all(fold_receipt[key] is False for key in _HOLDS), "preparation qualification flags changed")
    scale = fold_receipt["scale"]
    _require(_finite(scale) and scale > 0, "positive finite frozen scale required")
    intake_digest = hashlib.sha256(_json(intake)).hexdigest()
    receipt_digest = hashlib.sha256(_json(fold_receipt)).hexdigest()
    rate = record["native_hz"]
    calibration = [{"query_id": trial["query_id"], "direction": trial["direction"]}
                   for trial in calibration]
    queries = [{"query_id": trial["query_id"], "direction": trial["direction"]}
               for trial in queries]
    images = []
    metadata = None
    invalid_total = saturated_total = 0
    for trial in calibration:
        item = _map(load_map(trial["query_id"]), trial=trial, calibration=True,
                    fold_key=fold_key, scale=scale, rate=rate, max_bytes=max_map_bytes)
        signature = _json({key: item[key] for key in _METADATA})
        if metadata is None:
            metadata = signature
        _require(signature == metadata, "calibration maps have incompatible native geometry/metadata")
        images.append(item)
        invalid_total += item["invalid_pixels"]
        saturated_total += item["saturated_pixels"]
    total_bytes, packet_records = 0, []
    for trial in queries:
        item = _map(load_map(trial["query_id"]), trial=trial, calibration=False,
                    fold_key=fold_key, scale=scale, rate=rate, max_bytes=max_map_bytes)
        _require(_json({key: item[key] for key in _METADATA}) == metadata,
                 "query differs from the calibration native geometry/metadata")
        wire = _json({"schema": "fus_nine_map_packet_v1", "fold_key": fold_key,
                      "query_id": trial["query_id"], "class_angles_degrees": list(range(0, 360, 45)),
                      "context": CONTEXT, "calibration": images, "query": item})
        _require(len(wire) <= max_packet_bytes, "nine-map packet exceeds byte budget; do not crop or omit maps")
        _require(total_bytes + len(wire) <= max_total_packet_bytes,
                 "complete-fold packet byte budget exhausted; partial fold is not admitted")
        stage_packet(wire)
        total_bytes += len(wire)
        packet_records.append({"query_id": trial["query_id"], "bytes": len(wire),
                               "sha256": hashlib.sha256(wire).hexdigest()})
        invalid_total += item["invalid_pixels"]
        saturated_total += item["saturated_pixels"]
    _require(invalid_total == fold_receipt["invalid_pixels"]
             and saturated_total == fold_receipt["saturated_pixels"],
             "complete held-map pixel counters disagree with preparation receipt")
    return {"schema": "fus_nine_map_delivery_receipt_v1", "status": "source_component_completed",
            "fold_key": fold_key, "held_record_id": held_record_id,
            "roster_records": 49, "positive_records": 48, "declared_source_trials": 20622,
            "calibration_maps": 8, "query_packets": len(packet_records), "maps_per_packet": 9,
            "total_packet_bytes": total_bytes, "packets": packet_records,
            "input_receipt_sha256": receipt_digest,
            "intake_sha256": intake_digest,
            "native_source_authenticated": False, "full_resolution_delivery_qualified": False,
            "protected_evaluation_established": False, "scientifically_qualified": False,
            "publication_requires_success_and_operator_commit": True}
