"""Exact, bounded candidate-submission intake for the nine-video task.

This loader authenticates submitted bytes against their manifest and binds the
declared procedure digest. It does not prove that the declared procedure
actually produced those bytes; execution provenance is a separate contract.
"""
import hashlib
import json
import os
from pathlib import Path
import stat

from .constants import ASSISTANCE_CONDITIONS, VIDEO_IDS
from . import candidate_mat5

MANIFEST_NAME = "submission.json"
MANIFEST_SCHEMA = "suns2-candidate-submission/v1"
MAX_MANIFEST_BYTES = 64 * 1024


class CandidateSubmissionError(ValueError):
    """Submission identity, filesystem boundary or mask interface refusal."""


def _need(ok, message):
    if not ok:
        raise CandidateSubmissionError(message)


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _digest(value):
    return type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        _need(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value):
    raise CandidateSubmissionError("nonfinite JSON literal is not admitted")


def _stamp(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _regular(info, cap):
    _need(stat.S_ISREG(info.st_mode), "submission entries must be regular files")
    _need(info.st_nlink == 1, "hardlinked submission files are not admitted")
    _need(0 <= info.st_size <= cap, "submission file byte cap exceeded")


def _open_directory(path, *, directory_fd=None):
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open(path, flags, dir_fd=directory_fd)
    try:
        info = os.fstat(fd)
        _need(stat.S_ISDIR(info.st_mode), "expected submission directory")
        return fd, _stamp(info)
    except BaseException:
        os.close(fd)
        raise


def _open_canonical_directory(path):
    """Open every absolute component without following symlink ancestors."""
    fd, stamp = _open_directory(path.anchor)
    try:
        for component in path.parts[1:]:
            next_fd, stamp = _open_directory(component, directory_fd=fd)
            os.close(fd)
            fd = next_fd
        return fd, stamp
    except BaseException:
        os.close(fd)
        raise


def _check_census(directory_fd, expected):
    """Reject at the first unknown entry without unbounded list allocation."""
    remaining = set(expected)
    with os.scandir(directory_fd) as entries:
        for entry in entries:
            _need(entry.name in remaining, "submission census has extra or duplicate entries")
            remaining.remove(entry.name)
    _need(not remaining, "submission census has missing entries")


def _verify_directory_path(path, expected_stamp):
    fd, stamp = _open_canonical_directory(path)
    try:
        _need(stamp == expected_stamp, "submission directory path changed during intake")
    finally:
        os.close(fd)


def _read_regular(directory_fd, name, cap, seen, *, expected_bytes=None, expected_sha256=None):
    before = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    _regular(before, cap)
    if expected_bytes is not None:
        _need(before.st_size == expected_bytes, "manifest file size mismatch")
    identity = (before.st_dev, before.st_ino)
    _need(identity not in seen, "aliased submission file identity")
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory_fd)
    try:
        opened = os.fstat(fd)
        _regular(opened, cap)
        _need(_stamp(opened) == _stamp(before), "submission entry changed before open")
        remaining = opened.st_size
        blocks = []
        while remaining:
            chunk = os.read(fd, min(65536, remaining))
            _need(bool(chunk), "submission file truncated during read")
            blocks.append(chunk)
            remaining -= len(chunk)
        data = b"".join(blocks)
        after = os.fstat(fd)
        _need(_stamp(after) == _stamp(opened), "submission file changed during read")
        entry_after = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        _need(_stamp(entry_after) == _stamp(opened), "submission directory entry changed during read")
        if expected_sha256 is not None:
            _need(_sha256(data) == expected_sha256, "manifest file SHA256 mismatch")
        seen.add(identity)
        return data, _stamp(opened)
    finally:
        os.close(fd)


def _parse_manifest(data, expected_condition, expected_procedure_digest):
    try:
        manifest = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_object,
                              parse_constant=_reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise CandidateSubmissionError("malformed submission JSON") from exc
    _need(type(manifest) is dict and set(manifest) == {"schema", "condition", "procedure_digest", "cases"},
          "unexpected submission manifest fields")
    _need(manifest["schema"] == MANIFEST_SCHEMA, "submission schema mismatch")
    _need(manifest["condition"] == expected_condition, "assistance condition mismatch")
    _need(manifest["procedure_digest"] == expected_procedure_digest, "frozen procedure digest mismatch")
    cases = manifest["cases"]
    _need(type(cases) is list and len(cases) == len(VIDEO_IDS), "exact nine-case support required")
    records = {}
    for row in cases:
        _need(type(row) is dict and set(row) == {"video_id", "path", "sha256", "bytes"}, "unexpected case fields")
        video = row["video_id"]
        _need(type(video) is str and video in VIDEO_IDS and video not in records, "unknown or duplicate video ID")
        _need(row["path"] == f"masks/{video}.mat", "case path must match its exact video ID")
        _need(_digest(row["sha256"]), "invalid case SHA256")
        _need(type(row["bytes"]) is int and 128 <= row["bytes"] <= candidate_mat5.MAX_MAT_BYTES,
              "invalid candidate file byte count")
        records[video] = row
    _need(set(records) == set(VIDEO_IDS), "missing or extra video IDs")
    return manifest, records


def load_candidate_submission(directory, expected_condition, expected_procedure_digest):
    """Return ``(masks_by_video_id, verified_metadata)`` for one frozen condition.

    Only canonical paths and POSIX no-follow directory-relative reads are
    supported. The caller must supply the procedure digest frozen before hidden
    fold scoring; this function does not execute or inspect that procedure.
    """
    _need(type(expected_condition) is str and expected_condition in ASSISTANCE_CONDITIONS,
          "unknown expected assistance condition")
    _need(_digest(expected_procedure_digest), "invalid expected procedure digest")
    _need(all(hasattr(os, flag) for flag in ("O_DIRECTORY", "O_NOFOLLOW", "O_NONBLOCK")),
          "platform lacks required no-follow filesystem controls")
    root_fd = masks_fd = None
    try:
        root = Path(directory).absolute()
        canonical = root.resolve(strict=True)
        _need(root == canonical, "submission root or ancestor is an alias")
        root_fd, root_stamp = _open_canonical_directory(root)
        _need(_stamp(os.stat(root, follow_symlinks=False)) == root_stamp, "submission root changed during open")
        _check_census(root_fd, {MANIFEST_NAME, "masks"})
        masks_fd, masks_stamp = _open_directory("masks", directory_fd=root_fd)
        expected_files = {f"{video}.mat" for video in VIDEO_IDS}
        _check_census(masks_fd, expected_files)
        seen = set()
        manifest_bytes, manifest_stamp = _read_regular(root_fd, MANIFEST_NAME, MAX_MANIFEST_BYTES, seen)
        manifest, records = _parse_manifest(manifest_bytes, expected_condition, expected_procedure_digest)
        # Validate the entire filesystem inventory before opening any MAT body.
        initial = {}
        identities = set(seen)
        for video in VIDEO_IDS:
            name = f"{video}.mat"
            info = os.stat(name, dir_fd=masks_fd, follow_symlinks=False)
            _regular(info, candidate_mat5.MAX_MAT_BYTES)
            _need(info.st_size == records[video]["bytes"], "manifest file size mismatch")
            identity = (info.st_dev, info.st_ino)
            _need(identity not in identities, "aliased submission file identity")
            identities.add(identity)
            initial[name] = _stamp(info)
        arrays, verified_cases = {}, []
        for video in VIDEO_IDS:
            row = records[video]
            name = f"{video}.mat"
            data, captured_stamp = _read_regular(masks_fd, name, candidate_mat5.MAX_MAT_BYTES, seen,
                expected_bytes=row["bytes"], expected_sha256=row["sha256"])
            _need(captured_stamp == initial[name], "mask entry changed after inventory")
            try:
                masks, mat_metadata = candidate_mat5.load_candidate_mat(data)
            except (candidate_mat5.CandidateMATError, ValueError, TypeError, OverflowError) as exc:
                raise CandidateSubmissionError(f"candidate MAT refused for {video}: {exc}") from exc
            arrays[video] = masks
            verified_cases.append({**row, "mat": mat_metadata})
        _check_census(root_fd, {MANIFEST_NAME, "masks"})
        _check_census(masks_fd, expected_files)
        _need(_stamp(os.fstat(root_fd)) == root_stamp and _stamp(os.fstat(masks_fd)) == masks_stamp,
              "submission directory changed during intake")
        _verify_directory_path(root, root_stamp)
        _need(_stamp(os.stat(root, follow_symlinks=False)) == root_stamp and
              _stamp(os.stat("masks", dir_fd=root_fd, follow_symlinks=False)) == masks_stamp,
              "submission directory identity changed during intake")
        _need(_stamp(os.stat(MANIFEST_NAME, dir_fd=root_fd, follow_symlinks=False)) == manifest_stamp,
              "manifest changed after read")
        for name, stamp in initial.items():
            _need(_stamp(os.stat(name, dir_fd=masks_fd, follow_symlinks=False)) == stamp,
                  "mask file changed after read")
        return arrays, {"schema": "suns2-verified-candidate-submission/v1",
            "condition": manifest["condition"], "procedure_digest": manifest["procedure_digest"],
            "manifest_sha256": _sha256(manifest_bytes), "manifest_bytes": len(manifest_bytes),
            "case_order": list(VIDEO_IDS), "cases": verified_cases,
            "total_source_MAT_bytes": sum(records[v]["bytes"] for v in VIDEO_IDS),
            "exact_support_and_file_census_verified": True,
            "procedure_production_provenance_verified": False,
            "limits": {"source_bytes_per_MAT": candidate_mat5.MAX_MAT_BYTES,
                       "expanded_bytes_per_MAT": candidate_mat5.MAX_EXPANDED_BYTES,
                       "manifest_bytes": MAX_MANIFEST_BYTES}}
    except CandidateSubmissionError:
        raise
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise CandidateSubmissionError(f"candidate filesystem or manifest refused: {exc}") from exc
    finally:
        if masks_fd is not None:
            os.close(masks_fd)
        if root_fd is not None:
            os.close(root_fd)


def load_trusted_mask(path, expected_variable, expected_sha256, expected_bytes):
    """Read a trusted operator-selected, pinned reference; no candidate lookup.

    Caller authorization and reference-spec provenance are external to this API.
    This function authenticates one canonical regular file before numeric decode.
    It does not execute code or treat candidate manifest fields as references.
    """
    _need(type(expected_variable) is str and expected_variable in ("Masks", "FinalMasks"),
          "unsupported trusted mask variable")
    _need(_digest(expected_sha256), "invalid trusted mask digest")
    _need(type(expected_bytes) is int and 128 <= expected_bytes <= candidate_mat5.MAX_MAT_BYTES,
          "invalid trusted mask byte count")
    parent_fd = None
    try:
        target = Path(path).absolute()
        _need(target == target.resolve(strict=True), "trusted mask path or ancestor is an alias")
        parent_fd, parent_stamp = _open_canonical_directory(target.parent)
        data, file_stamp = _read_regular(parent_fd, target.name, candidate_mat5.MAX_MAT_BYTES, set(),
                                        expected_bytes=expected_bytes, expected_sha256=expected_sha256)
        masks, metadata = candidate_mat5.load_candidate_mat(data, expected_variable=expected_variable)
        _need(_stamp(os.fstat(parent_fd)) == parent_stamp and
              _stamp(os.stat(target.parent, follow_symlinks=False)) == parent_stamp,
              "trusted mask directory changed during intake")
        _verify_directory_path(target.parent, parent_stamp)
        _need(_stamp(os.stat(target.name, dir_fd=parent_fd, follow_symlinks=False)) == file_stamp,
              "trusted mask changed after read")
        return masks, {**metadata, "sha256": expected_sha256, "bytes": expected_bytes,
                       "expected_variable": expected_variable, "source_bytes_authenticated": True}
    except CandidateSubmissionError:
        raise
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise CandidateSubmissionError(f"trusted mask refused: {exc}") from exc
    finally:
        if parent_fd is not None:
            os.close(parent_fd)
