"""Pinned primitive packet loading; no fitting, normalization or scoring.

Production loading has no alternate input path and no reduced-panel switch.
The trusted package binding is read before the public manifest; all JSON and
member pins are admitted before numeric arrays. A submitted manifest mismatch
raises Invalid before any NPY load. Operator/private failures are InputError.
"""
from __future__ import annotations

import hashlib
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat

import numpy as np

from interface import Invalid, capture_regular, decode_json

SUBJECTS = ("01", "02", "03")
NATIVE_COLUMNS = 9840
SELECTED_ROWS = 1200
COUNTS = {"01": {"native": 211339, "union": 5130, "V1": 1049, "IT": 4081},
          "02": {"native": 226950, "union": 4962, "V1": 1104, "IT": 3858},
          "03": {"native": 189164, "union": 4218, "V1": 839, "IT": 3379}}
FEATURE_NAMES = ["red_mean", "green_mean", "blue_mean", "red_sd", "green_sd", "blue_sd",
                 "encoded_luma_sd", "horizontal_gradient_energy", "vertical_gradient_energy",
                 "radial_power_0_to_0.0625", "radial_power_0.0625_to_0.125", "radial_power_0.125_to_0.25",
                 "radial_power_0.25_to_0.5", "radial_power_0.5_to_nyquist_diagonal", "zero_non_dc_power"]
DESIGN_PIN = {"bytes": 773647, "sha256": "3e4e7fec421ab57c61e19b66859f0434b314357de5c44dcf2957f6a5057108ec"}
COLUMN_PROOF_PIN = {"bytes": 2580, "sha256": "7c8696473b3d6e64b808836253f88571b1a3747a4c23aad9411413cf99ff95f2"}
HASH = re.compile(r"[0-9a-f]{64}\Z")
MAX_METADATA = 12_000_000
PACKET_CAP = 90_000_000


class InputError(ValueError):
    """Operator/source/packet integrity failure, not a candidate reward."""


def pin(d):
    if (not isinstance(d, dict) or type(d.get("bytes")) is not int or d["bytes"] < 0
            or not isinstance(d.get("sha256"), str) or HASH.fullmatch(d["sha256"]) is None):
        raise InputError("invalid byte/SHA256 descriptor")
    return {"bytes": d["bytes"], "sha256": d["sha256"]}


def safe_path(root, relative):
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise InputError("invalid relative source path")
    parts = PurePosixPath(relative)
    if parts.is_absolute() or any(p in ("", ".", "..") for p in relative.split("/")):
        raise InputError("noncanonical source path")
    base = Path(root)
    cursor = base
    for item in parts.parts:
        cursor = cursor / item
        if cursor.is_symlink():
            raise InputError("symlink in source path")
    return cursor


def checked_bytes(path, descriptor, cap=MAX_METADATA):
    expected = pin(descriptor)
    if expected["bytes"] > cap:
        raise InputError("source metadata exceeds bound")
    try:
        body = capture_regular(path, cap=cap)
    except Invalid as exc:
        raise InputError("source metadata capture failed") from exc
    if len(body) != expected["bytes"] or hashlib.sha256(body).hexdigest() != expected["sha256"]:
        raise InputError("source metadata pin mismatch")
    return body


def checked_json(path, descriptor, cap=MAX_METADATA):
    try:
        return decode_json(checked_bytes(path, descriptor, cap), cap=cap)
    except Invalid as exc:
        raise InputError("source metadata JSON invalid") from exc


def _stable(a, b):
    return all(getattr(a, k) == getattr(b, k) for k in
               ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns", "st_mode"))


def _stream_hash(stream, expected_bytes):
    stream.seek(0)
    digest = hashlib.sha256()
    seen = 0
    while True:
        part = stream.read(min(1_048_576, expected_bytes + 1 - seen))
        if not part:
            break
        seen += len(part)
        if seen > expected_bytes:
            raise InputError("NPY grew beyond authenticated extent")
        digest.update(part)
    if seen != expected_bytes:
        raise InputError("NPY byte extent changed")
    return digest.hexdigest()


def read_primitive_npy(path, descriptor, shape, cap):
    """Authenticate before/after decoding through the same regular open FD.

    This bounded low-level primitive is also exercised on tiny generated NPYs.
    Production callers supply frozen complete shapes; there is no pickle/mmap
    or reopening by pathname inside NumPy.
    """
    expected = pin(descriptor)
    if (expected["bytes"] > cap or not isinstance(shape, (tuple, list)) or len(shape) != 2
            or any(type(n) is not int or n <= 0 for n in shape)):
        raise InputError("NPY extent bound")
    fd = None
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size != expected["bytes"]:
            raise InputError("NPY must be pinned bounded regular file")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            if _stream_hash(stream, expected["bytes"]) != expected["sha256"]:
                raise InputError("NPY hash before decode")
            stream.seek(0)
            version = np.lib.format.read_magic(stream)
            if version == (1, 0):
                actual_shape, fortran, dtype = np.lib.format.read_array_header_1_0(stream, max_header_size=65536)
            elif version == (2, 0):
                actual_shape, fortran, dtype = np.lib.format.read_array_header_2_0(stream, max_header_size=65536)
            else:
                raise InputError("unsupported NPY version")
            if (tuple(actual_shape) != tuple(shape) or fortran or dtype.str != "<f4" or dtype.hasobject
                    or stream.tell() + math.prod(shape) * 4 != expected["bytes"]):
                raise InputError("NPY header/extent mismatch")
            # Fixed-count primitive read avoids rereading an allocation-controlling
            # header after validation. No pickle-capable decoder is invoked.
            array = np.fromfile(stream, dtype="<f4", count=math.prod(shape))
            if array.size != math.prod(shape):
                raise InputError("incomplete NPY primitive payload")
            array = array.reshape(tuple(shape))
            if stream.tell() != expected["bytes"] or array.shape != tuple(shape) or array.dtype.str != "<f4":
                raise InputError("NPY decoded shape or trailing bytes")
            if _stream_hash(stream, expected["bytes"]) != expected["sha256"]:
                raise InputError("NPY hash after decode")
        after, named = os.fstat(fd), os.lstat(path)
        if not stat.S_ISREG(named.st_mode) or not _stable(before, after) or not _stable(after, named):
            raise InputError("NPY changed during same-open verification")
        return array
    except (OSError, ValueError, EOFError, OverflowError) as exc:
        if isinstance(exc, InputError):
            raise
        raise InputError("primitive NPY capture/decode failed") from exc
    finally:
        if fd is not None:
            os.close(fd)


def validate_features(record):
    if not isinstance(record, dict) or set(record) != {"feature_names", "concept_features"}:
        raise InputError("feature packet fields")
    if record["feature_names"] != FEATURE_NAMES:
        raise InputError("exact 15 feature names/order required")
    concepts = record["concept_features"]
    if not isinstance(concepts, dict) or len(concepts) != 100:
        raise InputError("complete 100 concept feature panel required")
    images = set()
    for name, value in concepts.items():
        if not isinstance(name, str) or not name or "\0" in name or not isinstance(value, dict):
            raise InputError("concept identity")
        if set(value) != {"image", "image_features", "animacy", "size"}:
            raise InputError("feature record fields")
        image = value["image"]
        if not isinstance(image, str) or not image or image in images:
            raise InputError("one distinct image per concept")
        images.add(image)
        vector = value["image_features"]
        if not isinstance(vector, list) or len(vector) != 15:
            raise InputError("15 image features required")
        try:
            nums = vector + [value["animacy"], value["size"]]
            if any(type(x) not in (int, float) or not math.isfinite(x) for x in nums):
                raise InputError("finite numeric independent features required")
        except OverflowError as exc:
            raise InputError("feature numerical range") from exc
        if not 1 <= value["animacy"] <= 7 or not 0 <= value["size"] <= 519:
            raise InputError("semantic rating range")
    return concepts


def validate_rows(rows, concepts):
    if not isinstance(rows, list) or len(rows) != SELECTED_ROWS:
        raise InputError("all 1200 selected trials required")
    seen, tids = set(), set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"concept", "image", "session", "run", "trial_id", "within_run_position"}:
            raise InputError("trial row fields")
        c = row["concept"]
        if not isinstance(c, str) or c not in concepts or row["image"] != concepts[c]["image"]:
            raise InputError("trial concept/image join")
        if any(type(row[k]) is not int for k in ("session", "run", "trial_id", "within_run_position")):
            raise InputError("integer trial identifiers required")
        if (not 1 <= row["session"] <= 12 or not 1 <= row["run"] <= 10
                or not 0 <= row["trial_id"] < NATIVE_COLUMNS or not 0 <= row["within_run_position"] < NATIVE_COLUMNS):
            raise InputError("native trial identifier range")
        key = (c, row["session"])
        if key in seen or row["trial_id"] in tids:
            raise InputError("duplicate trial or concept/session")
        seen.add(key)
        tids.add(row["trial_id"])
    if len(seen) != 1200:
        raise InputError("incomplete concept/session cross product")


def validate_voxels(voxels, sid):
    if sid not in SUBJECTS or not isinstance(voxels, list) or len(voxels) != COUNTS[sid]["union"]:
        raise InputError("complete native ROI union required")
    previous = -1
    ids = set()
    for i, row in enumerate(voxels):
        if not isinstance(row, dict) or set(row) != {"projection_row", "native_row_index", "voxel_id", "subject_id", "V1", "IT"}:
            raise InputError("native voxel fields")
        if (any(type(row[k]) is not int for k in ("projection_row", "native_row_index", "voxel_id"))
                or row["projection_row"] != i or not previous < row["native_row_index"] < COUNTS[sid]["native"]
                or row["voxel_id"] < 0 or row["voxel_id"] in ids or row["subject_id"] != sid
                or type(row["V1"]) is not bool or type(row["IT"]) is not bool or not (row["V1"] or row["IT"])):
            raise InputError("native voxel identity/order/mask")
        previous = row["native_row_index"]
        ids.add(row["voxel_id"])
    for roi in ("V1", "IT"):
        if sum(r[roi] for r in voxels) != COUNTS[sid][roi]:
            raise InputError("complete ROI support count")
    if any(r["V1"] and r["IT"] for r in voxels):
        raise InputError("unexpected overlap in fixed source ROI panel")


def packet_metadata(package_root, submitted_manifest_sha256=None):
    """Resolve trusted binding/public manifest, without opening numeric arrays."""
    root = Path(package_root)
    try:
        binding = decode_json(capture_regular(safe_path(root, "private/PACKET_BINDING.json")))
    except Invalid as exc:
        raise InputError("missing/invalid operator packet binding") from exc
    if (not isinstance(binding, dict) or binding.get("schema") != "neural052_packet_binding_v1"
            or binding.get("task_id") != "NEURAL-052" or pin(binding.get("design")) != DESIGN_PIN):
        raise InputError("operator packet identity")
    desc = binding.get("inputs")
    if not isinstance(desc, dict) or desc.get("file") != "public/input/INPUTS.json":
        raise InputError("fixed public INPUTS path required")
    expected = pin(desc)
    manifest = checked_json(safe_path(root, desc["file"]), desc)
    if submitted_manifest_sha256 is not None and submitted_manifest_sha256 != expected["sha256"]:
        raise Invalid("submission refers to a different input manifest")
    if (not isinstance(manifest, dict) or manifest.get("schema") != "neural052_inputs_v1"
            or manifest.get("task_id") != "NEURAL-052" or manifest.get("feature_names") != FEATURE_NAMES
            or pin(manifest.get("design")) != DESIGN_PIN):
        raise InputError("public packet contract identity")
    members = binding.get("files")
    if not isinstance(members, list) or len(members) != 7:
        raise InputError("all seven packet member pins required")
    by_file = {}
    for d in members:
        pin(d)
        if not isinstance(d.get("file"), str) or not d["file"].startswith("public/input/") or d["file"] in by_file:
            raise InputError("packet binding member path")
        safe_path(root, d["file"])
        by_file[d["file"]] = pin(d)
    references = [manifest.get("features")]
    subjects = manifest.get("subjects")
    if (not isinstance(subjects, list) or len(subjects) != 3 or any(not isinstance(s, dict) for s in subjects)
            or [s.get("subject_id") for s in subjects] != list(SUBJECTS)):
        raise InputError("complete ordered participant panel")
    for s in subjects:
        references.extend((s.get("metadata"), s.get("responses")))
    seen = set()
    for d in references:
        if not isinstance(d, dict) or not isinstance(d.get("file"), str):
            raise InputError("packet reference descriptor")
        full = "public/input/" + d["file"]
        safe_path(root, full)
        if full in seen or by_file.get(full) != pin(d):
            raise InputError("public/private packet member binding mismatch")
        seen.add(full)
    if seen != set(by_file) or sum(d["bytes"] for d in members) + expected["bytes"] > PACKET_CAP:
        raise InputError("packet member extent")
    return root, binding, manifest, expected["sha256"]


def load_packet(package_root, submitted_manifest_sha256=None):
    root, binding, manifest, manifest_sha = packet_metadata(package_root, submitted_manifest_sha256)
    input_root = root / "public/input"
    f = manifest["features"]
    features = validate_features(checked_json(safe_path(input_root, f["file"]), f))
    admitted = []
    # All identities and JSON are verified before any response array is opened.
    for s in manifest["subjects"]:
        sid = s["subject_id"]
        d = s["metadata"]
        metadata = checked_json(safe_path(input_root, d["file"]), d)
        if not isinstance(metadata, dict) or set(metadata) != {"subject_id", "rows", "voxels"} or metadata["subject_id"] != sid:
            raise InputError("subject metadata identity")
        validate_rows(metadata["rows"], features)
        validate_voxels(metadata["voxels"], sid)
        response = s["responses"]
        if response.get("shape") != [1200, COUNTS[sid]["union"]] or response.get("dtype") != "<f4":
            raise InputError("prepared response shape/type")
        admitted.append((s, metadata))
    subjects = []
    for s, metadata in admitted:
        d, sid = s["responses"], s["subject_id"]
        array = read_primitive_npy(safe_path(input_root, d["file"]), d, d["shape"], PACKET_CAP)
        if not np.isfinite(array).all():
            raise InputError("nonfinite prepared responses; no rows/voxels silently dropped")
        voxels = metadata["voxels"]
        subjects.append({"subject_id": sid, "responses": array, "rows": metadata["rows"],
                         "voxel_ids": [v["voxel_id"] for v in voxels],
                         "roi_masks": {r: np.array([v[r] for v in voxels], dtype=bool) for r in ("V1", "IT")}})
    return subjects, features, manifest_sha
