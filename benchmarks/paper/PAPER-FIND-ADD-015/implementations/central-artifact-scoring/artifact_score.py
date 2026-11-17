"""Trusted external ZIP intake for the unchanged complete optogenetics scorer.

This module never executes participant code. NumPy and the pinned scientific
core are loaded only by the actual scoring CLI, not by interface-only tests.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import types

PROFILE = "opto-central-public-protocol-reconstruction-v1"
CORE_PIN = {"bytes": 22233, "sha256": "a8a99ffe05eeb2e43b951b2557cc973808f0681fec9e82bcb1afe758e98e4071"}
SCHEMA_PIN = {"bytes": 106057, "sha256": "c7fbeee502fe9d37bc265add04e68ce5300229ec5861588e32788d4b822148cc"}
REFERENCE_PINS = {
    "windows.npz": {"bytes": 1154804, "sha256": "e5f613eb0104de986662d888e5cafd79cbf071f8c438f2b056cea90373643085"},
    "paired_vectors.npz": {"bytes": 197066, "sha256": "411ee6051939957a2f616ca0dee17ac77dd811594cecbdb47538570addaee775"},
    "report.json": {"bytes": 24606, "sha256": "d87baf65f48631badbbd0e3d84ff824e7f10b0a7f9c0c7b824f4c102e85bdf09"},
}
SUBMISSION_CAP = 2_700_000
SCORE_CAP = 1_000_000
PHYSICAL = ("st_dev", "st_ino", "st_uid", "st_gid", "st_mode", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns")


class Refusal(ValueError):
    pass


def need(ok, message):
    if not ok:
        raise Refusal(message)


def ordinary_path(value):
    path = Path(value).absolute()
    need(".." not in path.parts and not any(p.is_symlink() for p in (path, *path.parents)),
         "Canonical path without symbolic-link ancestors required")
    return path


def pin(body):
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def capture(value, cap, expected=None):
    path = ordinary_path(value)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and 0 < before.st_size <= cap, "Bounded nonempty single-link ordinary file required")
        chunks = []; remaining = before.st_size
        while remaining:
            chunk = os.read(fd, min(65536, remaining))
            need(bool(chunk), "Complete source read required")
            chunks.append(chunk); remaining -= len(chunk)
        need(not os.read(fd, 1), "Source grew during capture")
        identity = tuple(getattr(before, k) for k in PHYSICAL)
        need(identity == tuple(getattr(os.fstat(fd), k) for k in PHYSICAL)
             == tuple(getattr(path.lstat(), k) for k in PHYSICAL), "Source changed during capture")
        body = b"".join(chunks)
        if expected is not None:
            need(pin(body) == expected, "Exact source identity mismatch")
        return body
    finally:
        os.close(fd)


def fresh_output(value):
    path = ordinary_path(value)
    need(not path.exists() and path.parent.is_dir(), "Fresh output with existing parent required")
    return path


def save(path, body):
    need(0 < len(body) <= SCORE_CAP, "Complete score exceeds byte cap")
    fd = os.open(fresh_output(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        view = memoryview(body)
        while view:
            count = os.write(fd, view)
            need(count > 0, "Complete output write required")
            view = view[count:]
        os.fsync(fd); os.fchmod(fd, 0o400)
    finally:
        os.close(fd)


def load_science(core_path, schema_path):
    # Authenticate source and schema before executing any supplied source bytes.
    body = capture(core_path, CORE_PIN["bytes"], CORE_PIN)
    schema = capture(schema_path, SCHEMA_PIN["bytes"], SCHEMA_PIN)
    need(sys.implementation.name == "cpython" and sys.version_info[:3] == (3, 12, 8),
         "Declared central runtime requires CPython3.12.8")
    module = types.ModuleType("opto_accepted_central_score_core")
    module.__file__ = str(ordinary_path(core_path))
    exec(compile(body, module.__file__, "exec"), module.__dict__)
    need(module.np.__version__ == "2.2.6", "Declared central runtime requires NumPy2.2.6")
    need(module.SUBMISSION_CAP == SUBMISSION_CAP and module.SCORE_CAP == SCORE_CAP,
         "Accepted core extents required")
    return module, module.strict_json(schema)


def score_artifact(submission, reference_root, output, core, spec, *, reference_pins=REFERENCE_PINS):
    """The CLI fixes all pins; injected core/pins support generated interface tests.

The accepted core owns full public ZIP/NPY/report validation and arithmetic.
Only its post-admission callback can open the three private reference bodies.
"""
    target = fresh_output(output)
    reads = attempts = calls = 0
    submission_pin = None
    try:
        body = capture(submission, SUBMISSION_CAP)
        submission_pin = pin(body)

        def loader():
            nonlocal reads, attempts, calls
            calls += 1
            need(calls == 1, "Only one private reference callback is permitted")
            # Even private-root filesystem inspection stays behind the callback.
            root = ordinary_path(reference_root)
            need(root.is_dir(), "Private reference directory required")
            refs = {}
            for name in ("windows.npz", "paired_vectors.npz", "report.json"):
                expected = reference_pins[name]
                attempts += 1
                raw = capture(root / name, expected["bytes"])
                reads += 1
                need(pin(raw) == expected, "Exact private reference identity mismatch")
                refs[name] = raw
            return refs

        # The complete accepted core, not a replacement reduced score, is called.
        result = core.grade(body, spec, loader)
        need(type(result) is dict and result.get("status") in ("scored", "invalid_submission"),
             "Declared core status required")
        expected_counts = (1, 3) if result["status"] == "scored" else (0, 0)
        need((calls, reads) == expected_counts
             and result.get("private_loader_calls") == calls
             and result.get("private_reference_reads") == reads,
             "Public-before-private callback/read counts must agree")
        score_body = core.json_bytes(result)
        need(0 < len(score_body) <= SCORE_CAP, "Complete score exceeds byte cap")
        code = 0 if result["status"] == "scored" else 2
    except Exception as exc:
        # Failures after private loading are infrastructure errors, never a
        # malformed-candidate score. Partial read attempts are disclosed.
        result = {"status": "operator_error", "submission_valid": None,
                  "reason": type(exc).__name__ + ": " + str(exc)[:512],
                  "private_loader_calls": calls, "private_reference_reads": reads,
                  "private_reference_read_attempts": attempts,
                  "scientific_success": None, "performance_floor": None}
        score_body = encoded(result); code = 1
    save(target, score_body)
    return {"status": result["status"], "profile_id": PROFILE,
            "submission": submission_pin, "score_file": str(target), "score_pin": pin(score_body),
            "private_loader_calls": calls, "private_reference_reads": reads,
            "private_reference_read_attempts": attempts,
            "execution_kind": "trusted_external_artifact",
            "protected_execution_attested": False,
            "generated_numerical_controls_run_by_this_adapter": 0}, code


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    for name in ("core", "schema", "submission", "reference-root", "output"):
        result.add_argument("--" + name, required=True, type=Path)
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    fresh_output(args.output)
    core, spec = load_science(args.core, args.schema)
    summary, code = score_artifact(args.submission, args.reference_root, args.output, core, spec)
    print(encoded(summary).decode(), end="")
    return code


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(encoded({"status": "operator_error", "reason": type(exc).__name__ + ": " + str(exc)[:512]}).decode(), file=sys.stderr, end="")
        raise SystemExit(1)
