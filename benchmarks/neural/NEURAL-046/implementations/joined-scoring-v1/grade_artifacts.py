"""Bounded, target-last artifact interface for the existing paired scorer.

The caller is a trusted custodian. Source provenance, producer closure, protected
storage and a single state directory are external obligations, not a sandbox.
No candidate, fit, dataset preparation or model service is run here.
"""
from __future__ import annotations

import argparse
from decimal import Decimal
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import stat


SCORER_SHA256 = "fefb92048a9145450fe12131bf08fc12e20ca86adffff008401fa44d2edf691b"
NAMES = ("public", "submission", "sensitivity", "binding", "closure", "private")
MANIFEST_CAP = 65536
FILE_CAP = 64 * 1024 * 1024
TOTAL_CAP = 256 * 1024 * 1024
HEX = re.compile(r"[0-9a-f]{64}\Z")


class ArtifactError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ArtifactError(message)


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate_json_member")
            result[key] = value
        return result

    def floating(token):
        value = float(token)
        require(math.isfinite(value), "nonfinite_number")
        require(value != 0 or Decimal(token) == 0, "literal_underflow")
        return value

    def constant(_):
        raise ArtifactError("nonfinite_number")

    try:
        result = json.loads(raw.decode("utf-8", errors="strict"),
                            object_pairs_hook=pairs, parse_float=floating,
                            parse_constant=constant)
        # Reject unpaired escaped surrogates as well as malformed input bytes.
        encode(result)
        return result
    except (UnicodeError, json.JSONDecodeError, RecursionError, OverflowError) as error:
        raise ArtifactError("invalid_json") from error


def plain_directory(path):
    path = Path(path).absolute()
    require(not any(p.is_symlink() for p in (path, *path.parents)), "linked_directory")
    require(path.is_dir(), "missing_directory")
    return path


def read_file(path, cap):
    """Read one regular, nonlinked bounded file; no pathname discovery."""
    path = Path(path)
    plain_directory(path.parent)
    # A FIFO must not block before fstat can reject its type.
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) |
                 getattr(os, "O_NONBLOCK", 0))
    with os.fdopen(fd, "rb") as handle:
        before = os.fstat(handle.fileno())
        require(stat.S_ISREG(before.st_mode), "nonregular_file")
        require(before.st_size <= cap, "file_size_cap")
        raw = handle.read(cap + 1)
        after = os.fstat(handle.fileno())
    require(len(raw) <= cap and len(raw) == before.st_size, "file_size_changed")
    require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns,
             before.st_ctime_ns) ==
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns,
             after.st_ctime_ns), "file_changed_during_read")
    return raw


def read_descriptor(root, descriptor):
    raw = read_file(root / descriptor["path"], descriptor["bytes"])
    require(len(raw) == descriptor["bytes"] and sha256(raw) == descriptor["sha256"],
            "artifact_identity_mismatch")
    return strict_json(raw)


def checked_manifest(raw):
    manifest = strict_json(raw)
    require(type(manifest) is dict and set(manifest) == {"schema", "inputs", "limits"},
            "manifest_fields")
    require(manifest["schema"] == "neural046-joined-artifacts-v1", "manifest_schema")
    limits = manifest["limits"]
    require(type(limits) is dict and set(limits) == {"max_file_bytes", "max_total_bytes",
            "max_report_bytes"}, "limit_fields")
    for name, bound in (("max_file_bytes", FILE_CAP), ("max_total_bytes", TOTAL_CAP),
                        ("max_report_bytes", FILE_CAP)):
        require(type(limits[name]) is int and 0 < limits[name] <= bound, "invalid_limit")
    inputs = manifest["inputs"]
    require(type(inputs) is dict and set(inputs) == set(NAMES), "input_roster")
    total = 0
    for name in NAMES:
        item = inputs[name]
        require(type(item) is dict and set(item) == {"path", "bytes", "sha256"},
                "descriptor_fields")
        require(item["path"] == name + ".json", "fixed_input_path")
        require(type(item["bytes"]) is int and 0 < item["bytes"] <= limits["max_file_bytes"],
                "descriptor_size")
        require(type(item["sha256"]) is str and HEX.fullmatch(item["sha256"]),
                "descriptor_sha256")
        total += item["bytes"]
    require(total <= limits["max_total_bytes"], "total_input_cap")
    return manifest


def load_scorer():
    path = Path(__file__).with_name("score.py")
    body = read_file(path, 131072)
    require(sha256(body) == SCORER_SHA256, "paired_scorer_source_changed")
    spec = importlib.util.spec_from_file_location("_neural046_paired_artifact_scorer", path)
    scorer = importlib.util.module_from_spec(spec)
    # Execute the bytes authenticated above without reopening the source path.
    exec(compile(body, str(path), "exec"), scorer.__dict__)
    return scorer


def exclusive_write(path, raw):
    """Commit only at a previously absent name; leave failures visible."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    parent = os.open(Path(path).parent, os.O_RDONLY)
    try:
        os.fsync(parent)
    finally:
        os.close(parent)


def grade_bundle(bundle, state_directory, report_path):
    """Validate public artifacts, consume this manifest, then open targets once.

    The state directory is custodian-owned and must be shared across all attempts
    for this manifest. Changing that directory bypasses the one-shot boundary.
    The marker persists after ANY failure once target access has begun.
    """
    root = plain_directory(bundle)
    state = plain_directory(state_directory)
    output = Path(report_path).absolute()
    plain_directory(output.parent)
    require(not output.exists() and not output.is_symlink(), "report_exists")
    raw_manifest = read_file(root / "manifest.json", MANIFEST_CAP)
    manifest = checked_manifest(raw_manifest)
    # Formatting changes do not create a fresh grading entitlement.
    identity = sha256(encode(manifest))
    marker = state / (identity + ".consumed.json")
    require(not marker.exists() and not marker.is_symlink(), "grading_already_consumed")
    values = {name: read_descriptor(root, manifest["inputs"][name])
              for name in NAMES if name != "private"}
    scorer = load_scorer()
    opened = False

    def load_private():
        nonlocal opened
        require(not opened, "private_callback_repeated")
        # score_joined calls here only after exact prediction/binding/closure checks.
        custody = {"schema": "neural046-target-access-consumed-v1",
                   "manifest_sha256": identity,
                   "manifest_file_sha256": sha256(raw_manifest),
                   "private_descriptor": manifest["inputs"]["private"],
                   "source_sha256": SCORER_SHA256,
                   "target_access_state": "consumed_before_private_read",
                   "scientific_qualification": False}
        exclusive_write(marker, encode(custody))
        opened = True
        return read_descriptor(root, manifest["inputs"]["private"])

    result = scorer.score_joined(values["public"], values["submission"],
                                 values["sensitivity"], values["binding"],
                                 values["closure"], load_private)
    require(opened, "private_callback_not_called")
    report = {"schema": "neural046-joined-artifact-report-v1", "result": result,
              "custody": {"manifest_sha256": identity,
                          "consumption_marker": marker.name,
                          "target_last_artifact_validation": True,
                          "operator_provenance_independently_verified": False,
                          "production_sandbox_qualified": False},
              "scientific_qualification": False}
    raw = encode(report)
    require(len(raw) <= manifest["limits"]["max_report_bytes"], "report_size_cap")
    exclusive_write(output, raw)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--state-directory", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args(argv)
    grade_bundle(args.bundle, args.state_directory, args.report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
