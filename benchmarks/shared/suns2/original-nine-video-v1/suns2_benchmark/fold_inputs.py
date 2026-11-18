"""Trusted fold projection for the complete original SUNS2 TUnCaT panel.

This is an operator-side file projector, not a candidate sandbox. Authentication
receipts and their digests must come from the trusted coordinator. Generated
tests exercise this boundary; no authentic movies have been admitted here.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import unicodedata

from .constants import ASSISTANCE_CONDITIONS, TASK_SLUG, VIDEO_IDS

MATERIAL_SCHEMA = "suns2-authenticated-materials/v1"
CODE_SCHEMA = "suns2-official-code-allowlist/v1"
LOCK_SCHEMA = "suns2-frozen-procedure/v1"
FOLD_SCHEMA = "suns2-participant-fold/v1"
MAX_MANIFEST_BYTES = 1 << 20
MAX_DATA_FILE_BYTES = 32 << 20
MAX_CODE_FILE_BYTES = 1 << 20
MAX_CODE_BYTES = 8 << 20
MAX_CODE_FILES = 1024
MAX_DATA_BYTES = 280 << 20
CHUNK_BYTES = 1 << 20
CODE_RELEASES = {
    "v1.1.0": "71d1037859b85fb2e104d74f9307f7ac3ecaf19c",
    "v1.2.0": "128eb4738e026b89a341a6013e7bd7b6dc7c3216",
}
GROUND_TRUTH_COUNTS = dict(zip(VIDEO_IDS, (48, 40, 86, 42, 57, 81, 81, 47, 79)))
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_CODE_EXTENSIONS = {".py", ".m", ".bat", ".md", ".txt", ".yml", ".yaml"}
_CODE_EXTENSIONLESS_LICENSES = {"LICENSE", "SUNS2/LICENSE"}


class ProjectionError(ValueError):
    """Refusal without a completed participant input manifest."""


def _require(test, message):
    if not test:
        raise ProjectionError(message)


def _sha(value):
    _require(isinstance(value, str) and _HEX.fullmatch(value), "invalid SHA256")
    return value


def _keys(value, expected, context):
    _require(type(value) is dict and set(value) == set(expected), context + " keys")


def _integer(value, low, high, context):
    _require(type(value) is int and low <= value <= high, context)
    return value


def _relative(value):
    _require(isinstance(value, str) and 0 < len(value) <= 512, "invalid relative path")
    _require(value == unicodedata.normalize("NFC", value), "noncanonical Unicode path")
    _require("\\" not in value and "\x00" not in value and ":" not in value,
             "nonportable relative path")
    p = PurePosixPath(value)
    _require(not p.is_absolute() and str(p) == value and
             all(part not in ("", ".", "..") and not part.startswith(".")
                 for part in p.parts), "unsafe relative path")
    return p


def _canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True, allow_nan=False) + "\n").encode("ascii")


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def _json(data):
    try:
        return json.loads(data, object_pairs_hook=_pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(
                              ProjectionError("non-finite JSON constant")))
    except (ValueError, UnicodeError) as exc:
        raise ProjectionError("invalid JSON manifest") from exc


def _root_fd(path):
    p = Path(path)
    _require(p.is_absolute(), "root must be absolute")
    try:
        fd = os.open(p, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError as exc:
        raise ProjectionError("root is not an ordinary directory") from exc
    return fd


def _open_regular(root_fd, relative):
    parts = _relative(relative).parts
    directory = os.dup(root_fd)
    try:
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                            dir_fd=directory)
            os.close(directory)
            directory = child
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            os.close(fd)
            raise ProjectionError("material must be a regular single-link file")
        return fd
    except OSError as exc:
        raise ProjectionError("unsafe or absent source material") from exc
    finally:
        os.close(directory)


def _read_pinned_manifest(path, expected_digest):
    _sha(expected_digest)
    p = Path(path)
    _require(p.is_absolute(), "manifest must be absolute")
    root = _root_fd(p.parent)
    try:
        fd = _open_regular(root, p.name)
    finally:
        os.close(root)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        _require(0 < before.st_size <= MAX_MANIFEST_BYTES, "manifest size bound")
        data = stream.read(MAX_MANIFEST_BYTES + 1)
        after = os.fstat(stream.fileno())
    _require(len(data) == before.st_size and _identity(before) == _identity(after),
             "manifest changed while reading")
    _require(hashlib.sha256(data).hexdigest() == expected_digest,
             "manifest does not match trusted operator digest")
    return _json(data)


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _entry(entry, role):
    _keys(entry, ("video_id", "role", "path", "source_member", "bytes", "sha256", "shape"),
          "material entry")
    video = entry["video_id"]
    _require(video in VIDEO_IDS and entry["role"] == role, "material role or video ID")
    _relative(entry["path"])
    expected_member = video + ".h5" if role == "video" else "GT Masks/FinalMasks_" + video + ".mat"
    _require(entry["source_member"] == expected_member, "wrong original source member")
    _integer(entry["bytes"], 1, MAX_DATA_FILE_BYTES, "material size bound")
    _sha(entry["sha256"])
    expected_shape = [6000, 50, 50] if role == "video" else [50, 50, GROUND_TRUTH_COUNTS[video]]
    _require(type(entry["shape"]) is list and all(type(x) is int for x in entry["shape"])
             and entry["shape"] == expected_shape, "original shape qualification missing")


def validate_material_manifest(manifest):
    """Validate a trusted receipt's contract; this does not parse HDF5/MAT data."""
    _keys(manifest, ("schema", "task", "source", "authentication_receipt_sha256",
                     "status", "videos", "manual_masks", "common_support"), "material manifest")
    _require(manifest["schema"] == MATERIAL_SCHEMA and manifest["task"] == TASK_SLUG,
             "wrong material schema/task")
    _require(manifest["status"] == "authenticated_original_inputs", "movies are not authenticated")
    _sha(manifest["authentication_receipt_sha256"])
    source = manifest["source"]
    _keys(source, ("object_id", "version", "archive_bytes", "archive_sha256", "archive_md5"), "source")
    _require(type(source["object_id"]) is int and source["object_id"] == 49636131
             and type(source["version"]) is int and source["version"] == 3
             and type(source["archive_bytes"]) is int and source["archive_bytes"] == 248562067,
             "wrong original input object")
    _sha(source["archive_sha256"])
    _require(source["archive_md5"] == "e4aaf274478253cfea21580594ab2e36", "wrong published archive MD5")
    entries = []
    for key, role in (("videos", "video"), ("manual_masks", "manual_mask")):
        values = manifest[key]
        _require(type(values) is list and len(values) == 9, "complete nine-video support required")
        for row in values:
            _entry(row, role)
        _require([row["video_id"] for row in values] == list(VIDEO_IDS), "source fold order/support mismatch")
        entries.extend(values)
    paths = [row["path"].casefold() for row in entries]
    _require(len(set(paths)) == 18, "duplicate/colliding material paths")
    _require(len({row["sha256"] for row in entries}) == 18, "material content aliases another role/case")
    _require(sum(row["bytes"] for row in entries) <= MAX_DATA_BYTES, "aggregate material bound")
    _require(manifest["common_support"] == {
        "temporal_template": "quarantined_pending_provenance"}, "unsupported shared support policy")
    return manifest


def validate_code_manifest(manifest):
    _keys(manifest, ("schema", "task", "release", "commit", "source_role", "files"), "code manifest")
    _require(manifest["schema"] == CODE_SCHEMA and manifest["task"] == TASK_SLUG, "wrong code schema/task")
    _require(manifest["release"] in CODE_RELEASES and
             manifest["commit"] == CODE_RELEASES[manifest["release"]], "unqualified code release identity")
    _require(manifest["source_role"] == "reviewed_official_code_without_answers_or_weights", "code role unqualified")
    values = manifest["files"]
    _require(type(values) is list and 1 <= len(values) <= MAX_CODE_FILES, "code file count")
    paths, total = set(), 0
    for row in values:
        _keys(row, ("path", "bytes", "sha256"), "code file")
        p = _relative(row["path"])
        _require((p.suffix.lower() in _CODE_EXTENSIONS or str(p) in _CODE_EXTENSIONLESS_LICENSES) and
                 not {x.lower() for x in p.parts} & {"data", "results", "weights", "gt masks", "__pycache__"},
                 "code allowlist contains a data/result/weight path")
        _require(str(p).casefold() not in paths, "code path collision")
        paths.add(str(p).casefold())
        total += _integer(row["bytes"], 0, MAX_CODE_FILE_BYTES, "code file bound")
        _sha(row["sha256"])
    _require(total <= MAX_CODE_BYTES, "code aggregate bound")
    return manifest


def _lock_value(procedure_digest, condition, material_sha, code_sha):
    _sha(procedure_digest)
    _sha(material_sha)
    _require(condition in ASSISTANCE_CONDITIONS, "unknown assistance condition")
    if condition == "paper_data_official_code":
        _sha(code_sha)
    else:
        _require(code_sha is None, "paper/data condition cannot include code")
    return {"schema": LOCK_SCHEMA, "task": TASK_SLUG, "condition": condition,
            "procedure_digest": procedure_digest, "trusted_material_sha256": material_sha,
            "trusted_code_sha256": code_sha}


def _exclusive_json(path, value, mode=0o400):
    data = _canonical(value)
    _require(len(data) <= MAX_MANIFEST_BYTES, "receipt size bound")
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    except OSError as exc:
        raise ProjectionError("receipt/path already exists or is unsafe") from exc
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    return hashlib.sha256(data).hexdigest()


def freeze_procedure(lock_path, procedure_digest, condition, trusted_material_sha256,
                     trusted_code_sha256=None):
    """Create once in an operator-only directory before any fold is projected."""
    path = Path(lock_path)
    _require(path.is_absolute() and path.parent.is_dir() and not path.parent.is_symlink(),
             "lock parent must be an existing private directory")
    value = _lock_value(procedure_digest, condition, trusted_material_sha256, trusted_code_sha256)
    return _exclusive_json(path, value)


def _verify_file(root_fd, entry):
    fd = _open_regular(root_fd, entry["path"])
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        _require(before.st_size == entry["bytes"], "source size mismatch")
        digest, count = hashlib.sha256(), 0
        while count < entry["bytes"]:
            chunk = stream.read(min(CHUNK_BYTES, entry["bytes"] - count))
            _require(chunk, "source truncated")
            count += len(chunk)
            digest.update(chunk)
        _require(not stream.read(1), "source grew")
        after = os.fstat(stream.fileno())
    _require(_identity(before) == _identity(after), "source changed while hashing")
    _require(digest.hexdigest() == entry["sha256"], "source checksum mismatch")
    return before.st_dev, before.st_ino


def project_fold(material_manifest_path, trusted_material_sha256, bank_root, destination,
                 fold_index, condition, procedure_digest, lock_path, *,
                 code_manifest_path=None, trusted_code_sha256=None, code_root=None):
    """Project one new fold. Source and destination access need separate runtime admission.

    All source hashes are checked before a destination is created. A consumed fold
    claim is never silently retried. The output is a tiny participant manifest and
    an operator-only read-only bind specification; no payload files are copied or
    mounted and no participant process is launched. A later qualified runner must
    apply these exact file-level binds to a fresh namespace.
    """
    _integer(fold_index, 0, 8, "fold index")
    expected_lock = _lock_value(procedure_digest, condition, trusted_material_sha256, trusted_code_sha256)
    lock_digest = hashlib.sha256(_canonical(expected_lock)).hexdigest()
    _require(_read_pinned_manifest(lock_path, lock_digest) == expected_lock, "procedure lock mismatch")
    material = validate_material_manifest(_read_pinned_manifest(material_manifest_path, trusted_material_sha256))
    code = None
    if condition == "paper_data_official_code":
        _require(code_manifest_path is not None and code_root is not None, "code condition requires pinned allowlist/root")
        code = validate_code_manifest(_read_pinned_manifest(code_manifest_path, trusted_code_sha256))
    else:
        _require(code_manifest_path is None and code_root is None, "code supplied in paper/data condition")
    dest = Path(destination)
    _require(dest.is_absolute() and dest.parent.is_dir() and not dest.parent.is_symlink(), "destination parent")
    _require(not dest.exists() and not dest.is_symlink(), "destination must be new, not reused")
    roots = [Path(bank_root).resolve(strict=True)]
    if code is not None:
        roots.append(Path(code_root).resolve(strict=True))
    resolved_dest = dest.parent.resolve(strict=True) / dest.name
    for root in roots:
        _require(not resolved_dest.is_relative_to(root) and not root.is_relative_to(resolved_dest),
                 "participant destination overlaps protected source bank")
    bank_fd = _root_fd(bank_root)
    code_fd = None
    claim = Path(str(lock_path) + f".fold-{fold_index}.claim.json")
    claimed = False
    try:
        identities = set()
        for entry in material["videos"] + material["manual_masks"]:
            identity = _verify_file(bank_fd, entry)
            _require(identity not in identities, "source inode aliases another role/case")
            identities.add(identity)
        if code is not None:
            code_fd = _root_fd(code_root)
            private_hashes = {row["sha256"] for row in material["manual_masks"]}
            for entry in code["files"]:
                _require(entry["sha256"] not in private_hashes, "code aliases a manual mask")
                identity = _verify_file(code_fd, entry)
                _require(identity not in identities, "code inode aliases protected data")
                identities.add(identity)
        _exclusive_json(claim, {"schema": "suns2-fold-claim/v1", "lock_sha256": lock_digest,
                               "fold_index": fold_index, "state": "claimed"})
        claimed = True
        dest.mkdir(mode=0o700)
        participant_files = []
        bindings = []
        for row in material["videos"] + material["manual_masks"]:
            if row["role"] == "manual_mask" and row["video_id"] == VIDEO_IDS[fold_index]:
                continue
            relative = ("videos/" + row["video_id"] + ".h5" if row["role"] == "video"
                        else "training_masks/FinalMasks_" + row["video_id"] + ".mat")
            participant_files.append({"video_id": row["video_id"], "role": row["role"],
                                      "path": relative, "bytes": row["bytes"], "sha256": row["sha256"]})
            bindings.append({"source_root": str(roots[0]), "source_path": row["path"],
                             "target": relative, "read_only": True,
                             "bytes": row["bytes"], "sha256": row["sha256"]})
        code_files = []
        if code is not None:
            for row in code["files"]:
                relative = "official_code/" + row["path"]
                code_files.append({"path": relative, "bytes": row["bytes"], "sha256": row["sha256"]})
                bindings.append({"source_root": str(roots[1]), "source_path": row["path"],
                                 "target": relative, "read_only": True,
                                 "bytes": row["bytes"], "sha256": row["sha256"]})
        participant = {
            "schema": FOLD_SCHEMA, "task": TASK_SLUG, "condition": condition,
            "procedure_digest": procedure_digest, "fold_index": fold_index,
            "held_video": VIDEO_IDS[fold_index], "video_order": list(VIDEO_IDS),
            "files": participant_files, "code_files": code_files,
            "code_identity": None if code is None else {"release": code["release"], "commit": code["commit"]},
            "coordinates": {
                "movie_axes": ["time", "row", "col"],
                "mask_axes": ["col", "row", "neuron"],
                "relation": "movie[t,row,col] corresponds to Masks[col,row,neuron]",
                "projection_transform": "none; original movie and mask bytes are preserved",
                "qualification": "Source-derived contract; authentic movie payload coordinate join remains unqualified.",
            },
            "common_support": "Original temporal template quarantined pending provenance; not silently replaced.",
            "recipe_status": "Protected fold inputs are an execution adaptation; historical training-source parity is unqualified.",
            "exposure": "Original data/results are public; isolation does not establish absence of prior exposure.",
            "delivery_status": "Bind specification only; payloads are not mounted and candidate runtime is unqualified.",
        }
        manifest_digest = _exclusive_json(dest / "fold.json", participant, mode=0o444)
        os.chmod(dest, 0o555)
        _exclusive_json(Path(str(claim) + ".complete.json"), {
            "schema": "suns2-fold-projection-complete/v1", "fold_index": fold_index,
            "participant_manifest_sha256": manifest_digest, "lock_sha256": lock_digest,
            "bindings": bindings, "payload_bytes_copied": 0,
            "material_bytes_hashed": sum(x["bytes"] for x in material["videos"] + material["manual_masks"]),
            "code_bytes_hashed": 0 if code is None else sum(x["bytes"] for x in code["files"]),
            "runtime_requirements": [
                "Revalidate immutable bank identity before mounting; hash validation is time-specific.",
                "Mount exact selected files read-only, never the whole bank or a parent containing held masks.",
                "Fresh candidate process/namespace and writable state for each fold; no network or cross-fold reuse.",
                "Do not expose the operator lock, claims, binding receipts or authentication manifest to the candidate."],
            "note": "Bind specification only; no mount, candidate runtime or containment qualification."})
        return participant
    except Exception as exc:
        if claimed:
            _exclusive_json(Path(str(claim) + ".failed.json"), {
                "schema": "suns2-fold-projection-failed/v1", "fold_index": fold_index,
                "error_type": type(exc).__name__, "retry_policy": "Claim retained; no automatic retry."})
        raise
    finally:
        os.close(bank_fd)
        if code_fd is not None:
            os.close(code_fd)
