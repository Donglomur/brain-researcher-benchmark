#!/usr/bin/env python3
"""Portable finished-artifact assessment for PAPER-FIND-REP-012.

Run with Python 3.11+ and -I -S -B. No candidate code or scientific inputs are
executed. The operator selects the approved reference identity independently.
"""
import argparse
import hashlib
import os
from pathlib import Path
import stat
import sys
import types

IO_PIN = (5699, "a8cad32aeb96b319dbe360c913aea8433840a65d72c8667d48aa52f94269270a")


def load_io():
    """Load only the exact inherited I/O facade adjacent to this file."""
    path = Path(os.path.abspath(__file__)).parent / "artifact_io.py"
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("Unlinked trusted source path required")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size != IO_PIN[0]:
            raise ValueError("Exact ordinary trusted I/O source required")
        body = os.read(fd, IO_PIN[0] + 1)
        after = os.fstat(fd)
        fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns", "st_nlink")
        if (len(body), hashlib.sha256(body).hexdigest()) != IO_PIN or any(
                getattr(before, k) != getattr(after, k) for k in fields):
            raise ValueError("Trusted I/O source changed")
    finally:
        os.close(fd)
    module = types.ModuleType("rep012_portable_io")
    module.__file__ = str(path)
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module


def assess(io, args):
    core = io.load_core()
    core._sha(args.input_manifest_sha256)
    core._sha(args.reference_sha256)
    if not 0 < args.reference_bytes <= core.MAX_REFERENCE_BYTES:
        raise ValueError("Reference length must be in 1..32768")
    expected = {"bytes": args.reference_bytes, "sha256": args.reference_sha256}
    submission_pin = reference_pin = None
    # Reject reference-as-submission by metadata before reading candidate bytes.
    # Missing reference files remain deferred until candidate syntax is valid.
    left, right = io.ordinary_path(args.submission), io.ordinary_path(args.reference)
    if left == right:
        raise ValueError("Submission and reference must be distinct files")
    candidate_stat = os.lstat(left)
    try:
        reference_stat = os.lstat(right)
    except FileNotFoundError:
        reference_stat = None
    if reference_stat is not None and (candidate_stat.st_dev, candidate_stat.st_ino) == (
            reference_stat.st_dev, reference_stat.st_ino):
        raise ValueError("Submission and reference must be distinct files")
    try:
        submission, submission_pin = io.read_bounded(left, core.MAX_SUBMISSION_BYTES)
    except io.BoundedSizeError as exc:
        result = {"status": "invalid_submission", "score": None, "reason": str(exc),
                  "full_reconstruction": False, "private_reference_decoded": False}
    else:
        try:
            candidate = core.validate_submission(submission, input_manifest_sha256=args.input_manifest_sha256)
        except (core.InvalidSubmission, core.UnsupportedSubmission):
            result = core.grade_submission(submission, b"", input_manifest_sha256=args.input_manifest_sha256)
        else:
            # Private reference bytes are reached only for a valid candidate.
            # Source and inputs remain under a serialized, closed-producer boundary.
            reference, reference_pin = io.read_bounded(right, core.MAX_REFERENCE_BYTES)
            if reference_pin != expected:
                raise ValueError("Operator-selected reference identity mismatch")
            try:
                approved = core.validate_reference(reference, input_manifest_sha256=args.input_manifest_sha256)
            except (core.InvalidSubmission, core.UnsupportedSubmission) as exc:
                result = {"status": "operator_error", "score": None, "reason": str(exc),
                          "full_reconstruction": False, "private_reference_decoded": True}
            else:
                result = core.score_submission(candidate, approved)
                result["private_reference_decoded"] = True
    result.update(submission_pin=submission_pin, reference_pin=reference_pin,
                  reference_pin_matched=(reference_pin == expected),
                  candidate_code_executed=False)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--submission", required=True)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--reference-bytes", type=int, required=True)
    parser.add_argument("--reference-sha256", required=True)
    parser.add_argument("--input-manifest-sha256", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        io = load_io()
    except (OSError, ValueError) as exc:
        print("Cannot load trusted evaluator: " + type(exc).__name__, file=sys.stderr)
        return 1
    try:
        result = assess(io, args)
    except (OSError, ValueError) as exc:
        result = {"status": "operator_error", "score": None,
                  "reason": str(exc)[:512], "candidate_code_executed": False}
    result.update(task_id="PAPER-FIND-REP-012", input_manifest_sha256=args.input_manifest_sha256,
                  scope="Four exposed processed-source pooled associations; finished JSON only.",
                  reference_selection="Trusted operator input; hash matching does not establish scientific approval.",
                  full_paper_reproduced=False, benchmark_qualification_established=False)
    try:
        io.atomic_output(args.output, result)
    except (OSError, ValueError) as exc:
        print("Could not publish new grade: " + type(exc).__name__, file=sys.stderr)
        return 1
    return 0 if result["status"] == "scored" else 2 if result["status"] in (
        "invalid_submission", "unsupported_submission") else 1


if __name__ == "__main__":
    raise SystemExit(main())
