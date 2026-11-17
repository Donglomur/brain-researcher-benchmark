#!/usr/bin/env python3
"""Authenticated finite native entry. No data or numerical work before admission."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import warnings


def read_small(path, size):
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb") as handle:
        before = os.fstat(handle.fileno())
        if not (stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= size):
            raise ValueError("entry source/protocol extent or identity")
        raw = handle.read(size + 1)
        after = os.fstat(handle.fileno())
    attrs = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
    if len(raw) != before.st_size or any(getattr(before, k) != getattr(after, k) for k in attrs):
        raise ValueError("entry source/protocol changed")
    return raw


def load(name, path, raw):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    exec(compile(raw, str(path), "exec"), module.__dict__)
    return module


def main(argv, entry_reads):
    if len(argv) != 4 or argv[0] != "--protocol" or argv[2] != "--protocol-sha256":
        raise ValueError("exact frozen protocol and SHA256 arguments required")
    protocol_path, sha = Path(argv[1]), argv[3]
    def entry_read(path, limit):
        entry_reads["attempts"] += 1
        entry_reads["requested_caps_including_eof"] += limit + 1
        try:
            body = read_small(path, limit)
        except BaseException:
            entry_reads["unknown_failed_allowance"] += limit + 1
            raise
        entry_reads["returned_bytes"] += len(body)
        return body
    raw = entry_read(protocol_path, 256 * 1024)
    if hashlib.sha256(raw).hexdigest() != sha:
        raise ValueError("entry protocol hash differs")
    p = json.loads(raw)
    source_directory = Path(__file__).resolve().parent
    guard_path = source_directory / "guard.py"
    pins = [pin for pin in p["source_files"] if pin["path"] == str(guard_path)]
    if len(pins) != 1:
        raise ValueError("one pinned sibling guard required")
    guard_raw = entry_read(guard_path, 65536)
    if len(guard_raw) != pins[0]["bytes"] or hashlib.sha256(guard_raw).hexdigest() != pins[0]["sha256"]:
        raise ValueError("entry guard hash differs")
    guard = load("temporal_fixed_control_guard", guard_path, guard_raw)
    admission = guard.bootstrap(protocol_path, sha)
    admission.entry_authentication_reads = entry_reads
    fixed_path = source_directory / "fixed_control.py"
    pins = [pin for pin in p["source_files"] if pin["path"] == str(fixed_path)]
    if len(pins) != 1:
        raise ValueError("one pinned fixed-control driver required")
    fixed = load("temporal_full_fixed_control", fixed_path, admission.read_pin(pins[0]))
    # Unexpected warnings terminate and receive one bounded error below instead
    # of producing an unbounded stream. Intended source undefined scores remain
    # structured values handled by the unchanged native_r2 implementation.
    warnings.simplefilter("error")
    try:
        result = fixed.execute(admission)
    except BaseException as exc:
        exc.guard_read_meters = admission.meters.snapshot()
        raise
    result["entry_authentication_reads"] = entry_reads
    return result


if __name__ == "__main__":
    entry_reads = {"returned_bytes": 0, "attempts": 0,
                   "requested_caps_including_eof": 0, "unknown_failed_allowance": 0,
                   "scope": "entry authentication reads before guard meters; not authentic data"}
    try:
        result = main(sys.argv[1:], entry_reads)
        print(json.dumps(result, sort_keys=True, allow_nan=False))
    except BaseException as exc:
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__,
                          "error": str(exc)[:2048], "automatic_retry": False,
                          "entry_authentication_reads": entry_reads,
                          "guard_reads": getattr(exc, "guard_read_meters", {
                              "status": "not_available", "actual_reads": "unknown",
                              "declared_allowances_retained": {"metadata": 67108864, "runtime": 67108864}}),
                          "scientific_qualification": False}), file=sys.stderr)
        sys.exit(1)
