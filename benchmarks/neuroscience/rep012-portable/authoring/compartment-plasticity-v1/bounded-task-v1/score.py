#!/usr/bin/env python3
"""Operator artifact facade; no candidate program is imported or executed.

Invoke with python -I -B. The operator must bind --reference to the approved
private artifact; observed file pins are reported, not independent approval.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import sys
import tempfile
import types

CORE_SHA256 = "b3e9ba4bcc3492b31877399704f5d85f12b3dab01550f8a02be84dca2882b368"
OUTPUT_CAP = 131072


class BoundedSizeError(ValueError):
    """An otherwise ordinary file is empty or exceeds its admitted byte cap."""


def ordinary_path(value):
    path = Path(os.path.abspath(value))
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("Symlink path or ancestor is not admitted")
    return path


def read_bounded(value, cap):
    path = ordinary_path(value)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise ValueError("Ordinary single-link file required")
        if not 0 < before.st_size <= cap:
            raise BoundedSizeError("File must contain 1 through " + str(cap) + " bytes")
        parts, remaining = [], before.st_size
        while remaining:
            part = os.read(fd, min(65536, remaining))
            if not part:
                raise ValueError("Input truncated during read")
            parts.append(part)
            remaining -= len(part)
        after = os.fstat(fd)
        fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns", "st_nlink")
        if os.read(fd, 1) or any(getattr(before, key) != getattr(after, key) for key in fields):
            raise ValueError("Input changed during read")
        body = b"".join(parts)
        return body, {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
    finally:
        os.close(fd)


def load_core():
    path = Path(__file__).parent / "scorer_core.py"
    body, pin = read_bounded(path, 32768)
    if pin["sha256"] != CORE_SHA256:
        raise ValueError("Trusted scorer source pin changed")
    module = types.ModuleType("rep012_pinned_scorer")
    module.__file__ = str(path)
    # Only this exact trusted source body is compiled. Submission bytes remain JSON.
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module


def atomic_output(value, result, cap=OUTPUT_CAP):
    path = ordinary_path(value)
    if not path.parent.is_dir() or path.exists():
        raise ValueError("Existing ordinary parent and new output filename required")
    body = (json.dumps(result, allow_nan=False, ensure_ascii=True, indent=2) + "\n").encode("utf-8")
    if len(body) > cap:
        raise ValueError("Grade output byte cap exceeded")
    fd, temporary = tempfile.mkstemp(prefix=".rep012-grade-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        # Atomic publication without replacing an existing path.
        os.link(temporary, path, follow_symlinks=False)
    finally:
        os.unlink(temporary)
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--submission", required=True)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--input-manifest-sha256", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    result = {"status": "operator_error", "score": None, "candidate_code_executed": False}
    submission_pin = reference_pin = None
    try:
        core = load_core()
        core._sha(args.input_manifest_sha256)
        try:
            submission, submission_pin = read_bounded(args.submission, core.MAX_SUBMISSION_BYTES)
        except BoundedSizeError as exc:
            result = {"status": "invalid_submission", "score": None,
                      "full_reconstruction": False, "reason": str(exc),
                      "private_reference_decoded": False, "candidate_code_executed": False}
        else:
            try:
                core.validate_submission(submission, input_manifest_sha256=args.input_manifest_sha256)
            except (core.InvalidSubmission, core.UnsupportedSubmission):
                result = core.grade_submission(submission, b"", input_manifest_sha256=args.input_manifest_sha256)
            else:
                reference, reference_pin = read_bounded(args.reference, core.MAX_REFERENCE_BYTES)
                result = core.grade_submission(submission, reference, input_manifest_sha256=args.input_manifest_sha256)
    except (OSError, ValueError) as exc:
        result = {"status": "operator_error", "score": None, "reason": str(exc)[:512],
                  "candidate_code_executed": False}
    result.update(input_manifest_sha256=args.input_manifest_sha256,
                  submission_pin=submission_pin, reference_pin=reference_pin,
                  reference_approval_attested_by_facade=False,
                  scope="Finished result artifact only; operator supplies the approved private reference.")
    try:
        atomic_output(args.output, result)
    except (OSError, ValueError) as exc:
        print("Could not publish new bounded grade: " + str(exc)[:512], file=sys.stderr)
        return 1
    return 0 if result["status"] == "scored" else 2 if result["status"] in (
        "invalid_submission", "unsupported_submission") else 1


if __name__ == "__main__":
    raise SystemExit(main())
