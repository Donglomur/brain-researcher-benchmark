"""Separate-arm observation material and bounded, single-final attempt capture.

Operator-only materialization precedes participant requests. Native material has
only a sanitized index and PNGs; programme material has that same index and the
original aggregate JSON. Participant request dictionaries contain no paths.
There is no executor, renderer, browser, network, evaluator or feedback API here.
These are local file/API integrity checks, not hostile OS/provider isolation.
An operator ledger must enforce global attempt uniqueness; a random per-attempt
nonce distinguishes local manifests but does not constitute such a ledger.

Source patterns inspected: NEURAL-034 modality-viewer-transport-v1 uses bounded
O_NOFOLLOW/O_NONBLOCK regular-file capture and immutable condition journals;
WORM participant-transport-v2 binds externally assigned arms and final responses
to frozen input identity. Those patterns are used here without their dynamic
evaluator imports, process execution, sandbox profiles or task-specific aliases.
"""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
from functools import wraps
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import stat
import struct
import zlib


METHOD = "neural096-split-stratified-quarter-rate-contrasts/v1"
ARMS = ("native", "programme")
IDS = tuple(f"{split}-segment{segment}-eye{eye}-direction{direction}"
            for split in ("train", "val") for segment in range(6)
            for eye in range(2) for direction in (0, 180))
INDEX_KEYS = {"schema", "method", "unit_ids", "phase_bins", "quarter_bin_slices",
              "rate_units", "display_rate_max_hz", "cells", "precision", "scope"}
CELL_KEYS = {"cell_id", "source_split", "observation_segment", "is_eye", "theta",
             "n_long", "n_short", "supported", "missing_priors"}
PRECISION = {
    "programme": "original JSON numeric prior-specific means",
    "viewer": "SVG 1360x1180; 256 white-to-blue shade levels; shared global scale",
    "matched_underlying_observations": True, "identical_numerical_precision": False,
    "scoring_tolerance_changed": False, "image_provider_transport_qualified": False,
    "participant_isolation_qualified": False,
}
SCOPE = "Deterministic descriptive analysis; no learned neural understanding or inference is established."
LIMITS = [
    "One previously exposed animal/session; these are response-conditioned observations.",
    "Recording segments and original train/validation labels are not established randomization or independence blocks.",
    "Aggregate rates omit individual-trial detail in BOTH matched access arms.",
    "Typed SVG viewing has finite visual precision; numerical programme inputs retain numeric precision.",
    "No computed difference, reference summary or numerical answer is delivered.",
]
MAX_INDEX = 64 * 1024
MAX_MANIFEST = 64 * 1024
MAX_OBSERVATIONS = 4 * 1024**2
MAX_PNG = 7 * 1024**2
MAX_NATIVE_MATERIAL = 337 * 1024**2
MAX_PROGRAMME_MATERIAL = 5 * 1024**2
MAX_REQUESTS = 128
MAX_RESPONSE_BYTES = 512 * 1024**2
MAX_ANSWER = 128 * 1024
MAX_EVENT = 4096
RESPONSE_HEADER_RESERVE = 1024
INPUT_FIELDS = {"observation_manifest_sha256", "observation_sha256",
                "preparation_completion_sha256", "index_sha256"}
INSTRUCTION_FIELDS = {"instruction_sha256", "answer_contract_sha256"}


class AttemptError(ValueError):
    """Bounded constant-reason adapter refusal; no private path is reported."""


def need(ok, reason):
    if not ok:
        raise AttemptError(reason)


def _constant_io_errors(function):
    """Do not expose an operator pathname through a public API error string."""
    @wraps(function)
    def call(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except OSError:
            raise AttemptError("operator_io_failure") from None
    return call


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode("utf8")


def decode(body):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, "duplicate_json_key")
            result[key] = value
        return result
    def real(value):
        number = float(value)
        need(math.isfinite(number), "nonfinite_json")
        return number
    def constant(value):
        raise AttemptError("nonfinite_json")
    try:
        return json.loads(body, object_pairs_hook=pairs, parse_float=real, parse_constant=constant)
    except (UnicodeError, ValueError, RecursionError) as exc:
        if isinstance(exc, AttemptError):
            raise
        raise AttemptError("invalid_json") from exc


def pin(body):
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def digest(value):
    need(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None, "invalid_sha256")
    return value


def pin_shape(value, maximum, *, empty=False):
    need(type(value) is dict and set(value) == {"bytes", "sha256"}
         and type(value["bytes"]) is int and (0 if empty else 1) <= value["bytes"] <= maximum,
         "invalid_pin")
    digest(value["sha256"])


def exact(actual, expected):
    need(type(actual) is type(expected), "metadata_type")
    if type(expected) is dict:
        need(set(actual) == set(expected), "metadata_fields")
        for key in expected:
            exact(actual[key], expected[key])
    elif type(expected) is list:
        need(len(actual) == len(expected), "metadata_extent")
        for left, right in zip(actual, expected):
            exact(left, right)
    else:
        need(actual == expected, "metadata_value")


def plain(path):
    path = Path(path)
    need(path.is_absolute() and ".." not in path.parts, "operator_path")
    need(all(not part.is_symlink() for part in (path, *path.parents)), "linked_path")
    return path


def read_body(path, maximum, *, empty=False):
    """Capture one bounded ordinary single-link file without following links."""
    path = plain(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as handle:
        before = os.fstat(handle.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and (0 if empty else 1) <= before.st_size <= maximum, "ordinary_bounded_file")
        body = handle.read(maximum + 1)
        key = lambda value: tuple(getattr(value, name) for name in
                                 ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns"))
        need(len(body) == before.st_size and key(before) == key(os.fstat(handle.fileno()))
             == key(path.stat()), "file_changed_during_read")
    return body


def read_pin(path, expected, maximum):
    pin_shape(expected, maximum)
    body = read_body(path, expected["bytes"])
    need(pin(body) == expected, "file_integrity")
    return body


def write_new(path, body):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(body)
        handle.flush()
        os.fsync(handle.fileno())


def fresh(path):
    path = plain(path)
    need(not os.path.lexists(path) and path.parent.is_dir(), "fresh_output_required")
    need(not any((p / ".git").exists() for p in (path.parent, *path.parents)), "output_inside_git")
    return path


def inventory(root, layout):
    root = plain(root)
    for relative, expected in layout.items():
        folder = plain(root / relative)
        need(folder.is_dir(), "ordinary_directory")
        found = set()
        for child in folder.iterdir():
            need(len(found) < len(expected) and child.name in expected and not child.is_symlink(), "closed_inventory")
            rel = str(child.relative_to(root))
            mode = child.stat()
            need(stat.S_ISDIR(mode.st_mode) if rel in layout else
                 stat.S_ISREG(mode.st_mode) and mode.st_nlink == 1, "ordinary_inventory_entry")
            found.add(child.name)
        need(found == set(expected), "closed_inventory")


def _index(data, *, original):
    need(type(data) is dict and set(data) == INDEX_KEYS, "index_fields")
    exact({k: data[k] for k in ("schema", "method", "phase_bins", "quarter_bin_slices", "rate_units", "precision", "scope")},
          {"schema": "neural096-typed-svg-index/v1" if original else "neural096-attempt-index/v1",
           "method": METHOD, "phase_bins": 20, "quarter_bin_slices": [[0, 5], [5, 10], [10, 15], [15, 20]],
           "rate_units": "spikes/s/source unit", "precision": PRECISION, "scope": SCOPE})
    units = data["unit_ids"]
    need(type(units) is list and len(units) == 54
         and all(type(x) is int and -(2**63) <= x < 2**63 for x in units)
         and len(set(units)) == 54, "unit_metadata")
    scale = data["display_rate_max_hz"]
    try:
        finite_scale = type(scale) in (int, float) and math.isfinite(scale) and scale > 0
    except (OverflowError, ValueError):
        finite_scale = False
    need(finite_scale, "axis_scale")
    cells = data["cells"]
    need(type(cells) is list and len(cells) == 48, "complete_cell_roster")
    totals = {"train": 0, "val": 0}
    cleaned = []
    for i, row in enumerate(cells):
        need(type(row) is dict and set(row) == CELL_KEYS | ({"svg"} if original else set()), "index_cell_fields")
        split, segment, eye, direction = ("train" if i < 24 else "val", (i % 24)//4,
                                          bool((i % 4)//2), (i % 2)*180)
        exact({k: row[k] for k in ("cell_id", "source_split", "observation_segment", "is_eye", "theta")},
              {"cell_id": IDS[i], "source_split": split, "observation_segment": segment,
               "is_eye": eye, "theta": direction})
        if original:
            exact(row["svg"], "viewer/cells/" + IDS[i] + ".svg")
        need(all(type(row[k]) is int and 0 <= row[k] <= 204 for k in ("n_long", "n_short")), "support_counts")
        missing = [prior for prior in ("long", "short") if row["n_" + prior] == 0]
        exact(row["supported"], not missing)
        exact(row["missing_priors"], missing)
        totals[split] += row["n_long"] + row["n_short"]
        cleaned.append({key: row[key] for key in CELL_KEYS})
    exact(totals, {"train": 150, "val": 54})
    need(sum(row["supported"] for row in cleaned) == 27, "supported_cell_count")
    result = {**data, "schema": "neural096-attempt-index/v1", "cells": cleaned}
    return decode(encode(result))


def sanitize_index(original_body):
    need(type(original_body) is bytes and 0 < len(original_body) <= MAX_INDEX, "index_bound")
    result = encode(_index(decode(original_body), original=True))
    need(len(result) <= MAX_INDEX, "index_bound")
    return result


def _binding(binding, arm, original_index_body=None):
    keys = INPUT_FIELDS | ({"renderer_manifest_sha256"} if arm == "native" else set())
    need(type(binding) is dict and set(binding) == keys, "source_binding_fields")
    for value in binding.values():
        digest(value)
    if original_index_body is not None:
        need(pin(original_index_body)["sha256"] == binding["index_sha256"], "source_index_identity")
    return decode(encode(binding))


def _observations(body, sanitized):
    need(type(body) is bytes and 0 < len(body) <= MAX_OBSERVATIONS, "observation_bound")
    data = decode(body)
    need(type(data) is dict and set(data) == {"schema", "method", "unit_ids", "phase_bins", "quarter_bin_slices",
         "rate_units", "display_rate_max_hz", "cells", "information_condition", "limits"}, "observation_fields")
    exact({k: data[k] for k in ("schema", "method", "information_condition", "limits")},
          {"schema": "neural096-matched-prior-mean-observations/v1", "method": METHOD,
           "information_condition": "matched_prior_specific_aggregate_trajectories", "limits": LIMITS})
    for key in ("unit_ids", "phase_bins", "quarter_bin_slices", "rate_units", "display_rate_max_hz"):
        exact(data[key], sanitized[key])
    need(type(data["cells"]) is list and len(data["cells"]) == 48, "complete_cell_roster")
    maximum = 0.0
    for source, meta in zip(data["cells"], sanitized["cells"]):
        need(type(source) is dict and set(source) == CELL_KEYS | {"long_rate_hz", "short_rate_hz"}, "observation_cell_fields")
        exact({key: source[key] for key in CELL_KEYS}, meta)
        for prior in ("long", "short"):
            matrix = source[prior + "_rate_hz"]
            if not source["n_" + prior]:
                need(matrix is None, "missing_prior_must_be_null")
                continue
            need(type(matrix) is list and len(matrix) == 54, "unit_rows")
            for row in matrix:
                need(type(row) is list and len(row) == 20, "phase_columns")
                for value in row:
                    try:
                        finite = type(value) in (int, float) and math.isfinite(value) and value >= 0
                    except (OverflowError, ValueError):
                        finite = False
                    need(finite, "finite_nonnegative_rate")
                    maximum = max(maximum, float(value))
    need(data["display_rate_max_hz"] == (maximum if maximum else 1.0), "common_axis_scale")


def validate_png(body):
    """CRC/header/chunk validation only; no image decode or render is performed."""
    need(type(body) is bytes and 0 < len(body) <= MAX_PNG and body[:8] == b"\x89PNG\r\n\x1a\n", "png_bound_or_signature")
    offset, tags, idat_finished = 8, [], False
    while offset < len(body):
        need(len(tags) < 4096 and offset + 12 <= len(body), "png_chunk_bound")
        size = struct.unpack(">I", body[offset:offset+4])[0]
        kind = body[offset+4:offset+8]
        need(size <= MAX_PNG and offset + 12 + size <= len(body), "png_chunk_extent")
        payload = body[offset+8:offset+8+size]
        crc = struct.unpack(">I", body[offset+8+size:offset+12+size])[0]
        need(zlib.crc32(kind + payload) & 0xffffffff == crc, "png_crc")
        need(kind in (b"IHDR", b"IDAT", b"IEND"), "png_alternate_metadata_route")
        if not tags:
            need(kind == b"IHDR" and size == 13, "png_header")
            width, height, depth, color, compression, filtering, interlace = struct.unpack(">IIBBBBB", payload)
            need((width, height, depth, compression, filtering, interlace) == (1360, 1180, 8, 0, 0, 0)
                 and color in (2, 6), "png_fixed_projection")
        elif kind == b"IHDR":
            raise AttemptError("duplicate_png_header")
        elif kind == b"IDAT":
            need(not idat_finished and size > 0, "png_idat_order")
        else:
            need(size == 0 and b"IDAT" in tags and offset + 12 == len(body), "png_end")
            idat_finished = True
        tags.append(kind)
        offset += size + 12
    need(bool(tags) and tags[-1] == b"IEND" and offset == len(body), "png_complete")
    return {"width": 1360, "height": 1180, "format": "PNG", "pixel_decode_performed": False}


def _material_manifest(arm, binding, files, index):
    names = {"INDEX.json"} | ({"cells/" + key + ".png" for key in IDS} if arm == "native" else {"observations.json"})
    need(arm in ARMS and type(files) is dict and set(files) == names, "material_file_roster")
    _binding(binding, arm)
    for name, value in files.items():
        pin_shape(value, MAX_INDEX if name == "INDEX.json" else MAX_OBSERVATIONS if arm == "programme" else MAX_PNG)
    return {"schema": "neural096-arm-material/v1", "arm": arm, "method": METHOD,
            "source_binding": binding, "files": files, "index": pin(index),
            "participant_content": "sanitized_index_and_selected_png" if arm == "native" else "sanitized_index_and_original_numeric_aggregates",
            "OS_isolation_qualified": False, "provider_transport_qualified": False,
            "scientific_inference_qualified": False}


def _material_layout(arm):
    if arm == "native":
        return {"": {"INDEX.json", "MATERIAL.json", "cells"}, "cells": {key + ".png" for key in IDS}}
    return {"": {"INDEX.json", "MATERIAL.json", "observations.json"}}


@_constant_io_errors
def materialize_native(index_bytes, png_sources, source_binding, destination):
    """Operator-only copy from an externally verified frozen raster closure."""
    binding = _binding(source_binding, "native", index_bytes)
    index = sanitize_index(index_bytes)
    need(type(png_sources) is dict and set(png_sources) == set(IDS), "complete_png_source_roster")
    for entry in png_sources.values():
        need(type(entry) is dict and set(entry) == {"path", "bytes", "sha256"}, "png_source_fields")
        pin_shape({k: entry[k] for k in ("bytes", "sha256")}, MAX_PNG)
        plain(entry["path"])
    output = fresh(destination)
    output.mkdir(mode=0o700)
    (output / "cells").mkdir(mode=0o700)
    write_new(output / "INDEX.json", index)
    files = {"INDEX.json": pin(index)}
    total = len(index)
    for key in IDS:
        entry = png_sources[key]
        body = read_pin(entry["path"], {k: entry[k] for k in ("bytes", "sha256")}, MAX_PNG)
        validate_png(body)
        total += len(body)
        need(total + MAX_MANIFEST <= MAX_NATIVE_MATERIAL, "native_material_cap")
        name = "cells/" + key + ".png"
        write_new(output / name, body)
        files[name] = pin(body)
    manifest = encode(_material_manifest("native", binding, files, index))
    need(len(manifest) <= MAX_MANIFEST, "material_manifest_cap")
    write_new(output / "MATERIAL.json", manifest)
    inventory(output, _material_layout("native"))
    return {"arm": "native", "material_manifest": pin(manifest), "files": 50,
            "bytes": total + len(manifest), "observation_manifest_sha256": binding["observation_manifest_sha256"]}


@_constant_io_errors
def materialize_programme(index_bytes, observation_bytes, source_binding, destination):
    binding = _binding(source_binding, "programme", index_bytes)
    index = sanitize_index(index_bytes)
    need(pin(observation_bytes)["sha256"] == binding["observation_sha256"], "numeric_observation_identity")
    _observations(observation_bytes, decode(index))
    output = fresh(destination)
    output.mkdir(mode=0o700)
    files = {"INDEX.json": pin(index), "observations.json": pin(observation_bytes)}
    manifest = encode(_material_manifest("programme", binding, files, index))
    need(len(manifest) <= MAX_MANIFEST and len(index) + len(observation_bytes) + len(manifest) <= MAX_PROGRAMME_MATERIAL,
         "programme_material_cap")
    for name, body in (("INDEX.json", index), ("observations.json", observation_bytes), ("MATERIAL.json", manifest)):
        write_new(output / name, body)
    inventory(output, _material_layout("programme"))
    return {"arm": "programme", "material_manifest": pin(manifest), "files": 3,
            "bytes": len(index) + len(observation_bytes) + len(manifest),
            "observation_manifest_sha256": binding["observation_manifest_sha256"]}


def _material(root, frozen_sha):
    digest(frozen_sha)
    root = plain(root)
    body = read_body(root / "MATERIAL.json", MAX_MANIFEST)
    need(pin(body)["sha256"] == frozen_sha, "material_manifest_identity")
    manifest = decode(body)
    need(type(manifest) is dict and set(manifest) == {"schema", "arm", "method", "source_binding", "files", "index",
         "participant_content", "OS_isolation_qualified", "provider_transport_qualified", "scientific_inference_qualified"}, "material_fields")
    arm = manifest["arm"]
    need(arm in ARMS, "material_arm")
    inventory(root, _material_layout(arm))
    files = manifest["files"]
    # Build the expected manifest without opening any observation/image payload.
    expected = _material_manifest(arm, manifest["source_binding"], files, b"placeholder")
    expected["index"] = files["INDEX.json"]
    exact(manifest, expected)
    maximum = MAX_NATIVE_MATERIAL if arm == "native" else MAX_PROGRAMME_MATERIAL
    need(sum(item["bytes"] for item in files.values()) + len(body) <= maximum, "material_total_cap")
    return manifest, pin(body)


def _config(config):
    need(type(config) is dict and set(config) == {"attempt_id", "max_requests", "max_response_bytes", "max_final_answer_bytes", *INSTRUCTION_FIELDS}, "config_fields")
    need(type(config["attempt_id"]) is str and re.fullmatch(r"[A-Za-z0-9_-]{1,80}", config["attempt_id"]), "attempt_id")
    for key, upper in (("max_requests", MAX_REQUESTS), ("max_response_bytes", MAX_RESPONSE_BYTES), ("max_final_answer_bytes", MAX_ANSWER)):
        need(type(config[key]) is int and 1 <= config[key] <= upper, "config_limit")
    for key in INSTRUCTION_FIELDS:
        digest(config[key])
    return decode(encode(config))


@_constant_io_errors
def create_attempt(material_root, frozen_material_sha, config, attempt_root):
    material, material_pin = _material(material_root, frozen_material_sha)
    config = _config(config)
    root = fresh(attempt_root)
    source = plain(material_root)
    need(not root.is_relative_to(source) and not source.is_relative_to(root), "separate_attempt_and_material_roots")
    binding = material["source_binding"]
    manifest = {"schema": "neural096-participant-attempt/v1", "method": METHOD,
                "arm": material["arm"], "attempt_id": config["attempt_id"],
                "attempt_nonce": secrets.token_hex(16), "config": config,
                "material_manifest": material_pin,
                **{key: binding[key] for key in INPUT_FIELDS},
                **{key: config[key] for key in INSTRUCTION_FIELDS},
                "scoring_tolerance_changed": False, "OS_isolation_qualified": False,
                "provider_transport_qualified": False, "learned_neural_understanding_established": False}
    body = encode(manifest)
    need(len(body) <= MAX_MANIFEST, "attempt_manifest_cap")
    root.mkdir(mode=0o700)
    (root / "events").mkdir(mode=0o700)
    write_new(root / "LOCK", b"")
    write_new(root / "ATTEMPT.json", body)
    return {"attempt_manifest": pin(body), "arm": material["arm"],
            "observation_manifest_sha256": binding["observation_manifest_sha256"]}


@contextmanager
def _locked(root):
    root = plain(root)
    lock = plain(root / "LOCK")
    fd = os.open(lock, os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == 0, "ordinary_attempt_lock")
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    except BlockingIOError as exc:
        raise AttemptError("attempt_busy") from exc
    finally:
        os.close(fd)


def _attempt(root, frozen_sha):
    digest(frozen_sha)
    body = read_body(root / "ATTEMPT.json", MAX_MANIFEST)
    need(pin(body)["sha256"] == frozen_sha, "attempt_manifest_identity")
    value = decode(body)
    need(type(value) is dict and set(value) == {"schema", "method", "arm", "attempt_id", "attempt_nonce", "config",
         "material_manifest", *INPUT_FIELDS, *INSTRUCTION_FIELDS, "scoring_tolerance_changed", "OS_isolation_qualified", "provider_transport_qualified",
         "learned_neural_understanding_established"}, "attempt_fields")
    need(value["schema"] == "neural096-participant-attempt/v1" and value["method"] == METHOD and value["arm"] in ARMS,
         "attempt_schema_or_arm")
    _config(value["config"])
    need(value["attempt_id"] == value["config"]["attempt_id"] and type(value["attempt_nonce"]) is str
         and re.fullmatch(r"[0-9a-f]{32}", value["attempt_nonce"]), "attempt_identity")
    pin_shape(value["material_manifest"], MAX_MANIFEST)
    for key in INPUT_FIELDS:
        digest(value[key])
    for key in INSTRUCTION_FIELDS:
        exact(value[key], value["config"][key])
    for key in ("scoring_tolerance_changed", "OS_isolation_qualified", "provider_transport_qualified", "learned_neural_understanding_established"):
        need(value[key] is False, "unqualified_attempt_scope")
    return value, pin(body)


def _request(request, arm):
    need(type(request) is dict and type(request.get("kind")) is str, "invalid_request")
    kind = request["kind"]
    if kind in ("index", "observations"):
        need(set(request) == {"kind"}, "invalid_request_fields")
        need(kind == "index" or arm == "programme", "wrong_arm_request")
    elif kind == "view":
        need(set(request) == {"kind", "cell_id"} and type(request["cell_id"]) is str
             and request["cell_id"] in IDS, "exact_typed_selector_required")
        need(arm == "native", "wrong_arm_request")
    else:
        raise AttemptError("unknown_request_kind")
    return decode(encode(request))


def _state(root, manifest, manifest_pin):
    names = {"ATTEMPT.json", "LOCK", "events"}
    answer_exists = os.path.lexists(root / "ANSWER.bin")
    final_exists = os.path.lexists(root / "FINAL.json")
    if answer_exists:
        names.add("ANSWER.bin")
    if final_exists:
        names.add("FINAL.json")
    folder = plain(root / "events")
    need(folder.is_dir(), "events_directory")
    entries = []
    for entry in folder.iterdir():
        need(len(entries) < manifest["config"]["max_requests"] and not entry.is_symlink()
             and re.fullmatch(r"[0-9]{6}\.json", entry.name), "event_inventory")
        entries.append(entry.name)
    entries.sort()
    need(entries == [f"{i:06d}.json" for i in range(1, len(entries)+1)], "event_sequence")
    inventory(root, {"": names, "events": set(entries)})
    events, payload_bytes, charged_bytes, head = [], 0, 0, manifest_pin["sha256"]
    for sequence, name in enumerate(entries, 1):
        body = read_body(folder / name, MAX_EVENT)
        event = decode(body)
        need(type(event) is dict and set(event) == {"schema", "sequence", "attempt_manifest_sha256", "previous_sha256",
             "request", "status", "reason", "response", "payload_bytes", "charged_bytes"}, "event_fields")
        need(event["schema"] == "neural096-observation-event/v1" and type(event["sequence"]) is int
             and event["sequence"] == sequence and event["attempt_manifest_sha256"] == manifest_pin["sha256"]
             and event["previous_sha256"] == head, "event_chain")
        need(type(event["payload_bytes"]) is int and type(event["charged_bytes"]) is int, "event_bytes")
        if event["status"] == "delivered":
            _request(event["request"], manifest["arm"])
            pin_shape(event["response"], MAX_PNG if event["request"]["kind"] == "view" else MAX_OBSERVATIONS)
            need(event["reason"] is None and event["payload_bytes"] == event["response"]["bytes"]
                 and event["charged_bytes"] == event["payload_bytes"] + RESPONSE_HEADER_RESERVE, "delivered_event")
        else:
            need(event["status"] == "refused" and event["request"] == {"kind": "refused"}
                 and type(event["reason"]) is str and event["reason"] in {"invalid_request", "invalid_request_fields", "wrong_arm_request", "exact_typed_selector_required", "unknown_request_kind", "response_budget", "observation_integrity_or_io_failure"}
                 and event["response"] is None and event["payload_bytes"] == 0 and event["charged_bytes"] == 0, "refused_event")
        payload_bytes += event["payload_bytes"]
        charged_bytes += event["charged_bytes"]
        head = pin(body)["sha256"]
        events.append(event)
    need(charged_bytes <= manifest["config"]["max_response_bytes"], "response_budget")
    return {"events": len(events), "payload_bytes": payload_bytes, "charged_bytes": charged_bytes,
            "head_sha256": head, "records": events, "sealed": answer_exists or final_exists}


def _append_event(root, manifest_pin, state, request, status, reason, response=None):
    event = {"schema": "neural096-observation-event/v1", "sequence": state["events"] + 1,
             "attempt_manifest_sha256": manifest_pin["sha256"], "previous_sha256": state["head_sha256"],
             "request": request, "status": status, "reason": reason, "response": pin(response) if response is not None else None,
             "payload_bytes": len(response) if response is not None else 0,
             "charged_bytes": len(response) + RESPONSE_HEADER_RESERVE if response is not None else 0}
    body = encode(event)
    need(len(body) <= MAX_EVENT, "event_bound")
    write_new(root / "events" / f"{event['sequence']:06d}.json", body)
    return {"sequence": event["sequence"], "event": pin(body), "response": event["response"]}


@_constant_io_errors
def request_observation(material_root, attempt_root, frozen_attempt_sha, request):
    root = plain(attempt_root)
    with _locked(root):
        manifest, manifest_pin = _attempt(root, frozen_attempt_sha)
        state = _state(root, manifest, manifest_pin)
        need(not state["sealed"], "attempt_sealed")
        need(state["events"] < manifest["config"]["max_requests"], "request_budget")
        try:
            selected = _request(request, manifest["arm"])
        except AttemptError as exc:
            _append_event(root, manifest_pin, state, {"kind": "refused"}, "refused", str(exc))
            raise
        try:
            # No observation/image material is opened until the typed request passes.
            material, actual_pin = _material(material_root, manifest["material_manifest"]["sha256"])
            need(actual_pin == manifest["material_manifest"] and material["arm"] == manifest["arm"], "material_attempt_binding")
            for key in INPUT_FIELDS:
                need(material["source_binding"][key] == manifest[key], "material_attempt_binding")
            name = ("INDEX.json" if selected["kind"] == "index" else
                    "observations.json" if selected["kind"] == "observations" else "cells/" + selected["cell_id"] + ".png")
            item = material["files"][name]
            need(state["charged_bytes"] + item["bytes"] + RESPONSE_HEADER_RESERVE <= manifest["config"]["max_response_bytes"],
                 "response_budget")
            maximum = MAX_INDEX if selected["kind"] == "index" else MAX_OBSERVATIONS if selected["kind"] == "observations" else MAX_PNG
            body = read_pin(plain(material_root) / name, item, maximum)
            if selected["kind"] == "index":
                _index(decode(body), original=False)
            elif selected["kind"] == "view":
                validate_png(body)
            else:
                index_body = read_pin(plain(material_root) / "INDEX.json", material["files"]["INDEX.json"], MAX_INDEX)
                _observations(body, _index(decode(index_body), original=False))
                need(pin(body)["sha256"] == manifest["observation_sha256"], "numeric_observation_identity")
        except (AttemptError, OSError) as exc:
            reason = "response_budget" if isinstance(exc, AttemptError) and str(exc) == "response_budget" else "observation_integrity_or_io_failure"
            # Valid selectors with damaged material also consume the request cap.
            # A failed operator journal is fail-closed; no payload is delivered.
            _append_event(root, manifest_pin, state, {"kind": "refused"}, "refused", reason)
            if isinstance(exc, OSError):
                raise AttemptError("operator_io_failure") from None
            raise
        receipt = _append_event(root, manifest_pin, state, selected, "delivered", None, body)
        content_type = "image/png" if selected["kind"] == "view" else "application/json"
        need(len(encode({"content_type": content_type, "event_receipt": receipt})) <= RESPONSE_HEADER_RESERVE,
             "response_header_bound")
        return {"content_type": content_type, "body": body, "event_receipt": receipt}


def _log_summary(state):
    return {key: state[key] for key in ("events", "payload_bytes", "charged_bytes", "head_sha256")}


@_constant_io_errors
def submit_final(attempt_root, frozen_attempt_sha, answer_bytes):
    root = plain(attempt_root)
    with _locked(root):
        manifest, manifest_pin = _attempt(root, frozen_attempt_sha)
        state = _state(root, manifest, manifest_pin)
        need(not state["sealed"], "attempt_sealed")
        accepted = type(answer_bytes) is bytes and 0 < len(answer_bytes) <= manifest["config"]["max_final_answer_bytes"]
        receipt = {"schema": "neural096-final-capture/v1", "status": "captured" if accepted else "rejected",
                   "reason": None if accepted else "answer_type_or_size", "attempt_manifest": manifest_pin,
                   "arm": manifest["arm"], "attempt_nonce": manifest["attempt_nonce"],
                   **{key: manifest[key] for key in INPUT_FIELDS | INSTRUCTION_FIELDS}, "material_manifest": manifest["material_manifest"],
                   "answer": pin(answer_bytes) if accepted else None, "observation_log": _log_summary(state),
                   "grading_feedback_provided": False}
        if accepted:
            # Even malformed JSON is captured once; the operator grader decides
            # validity later. No format feedback can trigger another submission.
            write_new(root / "ANSWER.bin", answer_bytes)
        body = encode(receipt)
        need(len(body) <= MAX_MANIFEST, "final_receipt_cap")
        write_new(root / "FINAL.json", body)
        return {"receipt": receipt, "receipt_pin": pin(body)}


@_constant_io_errors
def verify_final(attempt_root, frozen_attempt_sha, frozen_final_sha256):
    """Readback requires the final pin retained independently at capture time.

    The caller must not derive that pin from the current FINAL.json. This binds
    the captured answer/journal to the first receipt, even if files are later
    changed together. Operator custody remains external to this local API.
    """
    digest(frozen_final_sha256)
    root = plain(attempt_root)
    with _locked(root):
        manifest, manifest_pin = _attempt(root, frozen_attempt_sha)
        body = read_body(root / "FINAL.json", MAX_MANIFEST)
        need(pin(body)["sha256"] == frozen_final_sha256, "final_receipt_identity")
        state = _state(root, manifest, manifest_pin)
        need(state["sealed"] and (root / "FINAL.json").is_file() and (root / "ANSWER.bin").is_file(), "no_captured_final_answer")
        receipt = decode(body)
        need(type(receipt) is dict and set(receipt) == {"schema", "status", "reason", "attempt_manifest", "arm", "attempt_nonce",
             *INPUT_FIELDS, *INSTRUCTION_FIELDS, "material_manifest", "answer", "observation_log", "grading_feedback_provided"}, "final_fields")
        need(receipt["schema"] == "neural096-final-capture/v1" and receipt["status"] == "captured"
             and receipt["reason"] is None and receipt["grading_feedback_provided"] is False, "no_captured_final_answer")
        exact(receipt["attempt_manifest"], manifest_pin)
        exact(receipt["material_manifest"], manifest["material_manifest"])
        for key in ("arm", "attempt_nonce", *INPUT_FIELDS, *INSTRUCTION_FIELDS):
            exact(receipt[key], manifest[key])
        exact(receipt["observation_log"], _log_summary(state))
        answer = read_pin(root / "ANSWER.bin", receipt["answer"], manifest["config"]["max_final_answer_bytes"])
        return {"manifest": manifest, "receipt": receipt, "receipt_pin": pin(body), "answer_bytes": answer,
                "log": _log_summary(state)}


get_final = verify_final
