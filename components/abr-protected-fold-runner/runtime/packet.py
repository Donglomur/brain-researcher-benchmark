"""Complete public-animal validation and layout projection; no private preparation."""
import collections
import hashlib
import json
import math
import re

PROFILE = {"animals": 104, "stacks": 936, "records": 16226,
           "class_0": 54, "class_1": 50}


STIMULI = {100: "click", **{x: "tone_%d_hz" % x for x in
            (3000, 6000, 12000, 18000, 24000, 30000, 36000, 42000)}}


MAX_SAMPLE_COLUMNS = 32768


class PacketError(ValueError):
    pass


def need(ok, message):
    if not ok:
        raise PacketError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def validate_animal(value):
    need(type(value) is dict and set(value) == {"schema", "animal_id", "representation", "records"}
         and value["schema"] == "abr-background-animal/v1" and
         value["representation"] == "within_release_sample_index_float64", "public animal exact shape")
    need(type(value["animal_id"]) is str and re.fullmatch(r"animal_[0-9a-f]{64}", value["animal_id"]),
         "opaque animal ID")
    rows = value["records"]; need(type(rows) is list and 1 <= len(rows) <= 4096, "ragged records")
    ids = set(); counts = collections.defaultdict(list)
    for row in rows:
        need(type(row) is dict and set(row) == {"record_id", "stimulus", "level", "repeat_index", "sample_indices", "samples"},
             "no private/source field in public record")
        rid = row["record_id"]
        need(type(rid) is str and re.fullmatch(r"record_[0-9a-f]{64}", rid) and rid not in ids,
             "opaque unique record ID"); ids.add(rid)
        need(row["stimulus"] in STIMULI.values() and type(row["level"]) in (int, float)
             and math.isfinite(row["level"]) and type(row["repeat_index"]) is int and row["repeat_index"] >= 0,
             "finite layout fields")
        values = row["samples"]; indices = row["sample_indices"]
        need(type(values) is list and 1 <= len(values) <= MAX_SAMPLE_COLUMNS and
             type(indices) is list and all(type(x) is int for x in indices) and
             indices == list(range(len(values))), "all sample indices, no masking/cropping")
        need(all(type(x) in (int, float) and math.isfinite(x) for x in values), "all finite numerical samples")
        counts[(row["stimulus"], row["level"])].append(row["repeat_index"])
    need(all(sorted(v) == list(range(len(v))) for v in counts.values()), "complete repeat indices")
    return value


def layout_only(value):
    """Same admitted layout, no waveform values, summary, digest or gain proxy."""
    validate_animal(value)
    return {"schema": "abr-background-layout/v1", "animal_id": value["animal_id"],
            "records": [{k: v for k, v in row.items() if k != "samples"} for row in value["records"]]}

