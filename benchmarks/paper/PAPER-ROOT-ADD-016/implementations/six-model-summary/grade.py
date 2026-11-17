"""Portable operator adapter; no candidate execution, fitting or data acquisition."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import types

HELPER_BYTES = 9860
HELPER_SHA256 = "a622dc6b7780e49b20879fdf5fddb76aac62d6a20c1b93be993b57d0000ee99a"
INPUT_SHA256 = "6d122f256863197e49e9f7b39420cfe1c46741b3efa1fa66a6ec364337e48f11"


def load_core():
    path = Path(__file__).absolute().with_name("summary_score.py")
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("trusted helper path must not contain aliases")
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size != HELPER_BYTES:
        raise ValueError("ordinary single-link helper required")
    body = path.read_bytes()
    if (len(body), hashlib.sha256(body).hexdigest()) != (HELPER_BYTES, HELPER_SHA256):
        raise ValueError("exact accepted helper required")
    core = types.ModuleType("_portable_cardiac_core")
    core.__file__ = str(path)
    exec(compile(body, str(path), "exec"), core.__dict__)
    return core


def require_json_operand(path, cap):
    """Reject nonordinary operands before the inherited blocking open.

    The operator supplies a static trusted directory after producer closure;
    this check does not claim protection against concurrent namespace swaps.
    """
    info = Path(path).lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or not 0 < info.st_size <= cap:
        raise ValueError("bounded ordinary single-link JSON operand required")


def evaluate(core, submission, reference, expected_reference):
    """The operator reference is never opened for an invalid candidate."""
    try:
        require_json_operand(submission, core.MAX_BYTES)
        candidate, submission_pin = core.read_json(submission)
        core.validate(candidate)
        core.need(candidate["input_sha256"] == INPUT_SHA256,
                  "original Salzburg CSV fingerprint required")
    except (ValueError, UnicodeError, OSError) as error:
        return {"status": "invalid_submission", "submission_valid": False,
                "reason": str(error), "metrics": None,
                "private_numeric_reference_loads": 0,
                "scientific_success": None}, 2

    # Trusted operator source is pinned independently of candidate content.
    require_json_operand(reference, core.MAX_BYTES)
    target, reference_pin = core.read_json(reference)
    core.need(reference_pin == expected_reference, "private reference pin mismatch")
    core.validate(target)
    core.need(target["input_sha256"] == INPUT_SHA256,
              "reference must bind the original Salzburg CSV")
    metrics = core.score(candidate, target)
    scored = metrics["status"] == "valid_summary_continuously_scored"
    return {"status": "scored" if scored else metrics["status"],
            "submission_valid": True, "metrics": metrics,
            "submission_pin": submission_pin, "private_reference_pin": reference_pin,
            "private_numeric_reference_loads": 1, "scientific_success": None}, 0 if scored else 2


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission", required=True, type=Path)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--reference-bytes", required=True, type=int)
    parser.add_argument("--reference-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if not 0 < args.reference_bytes <= 200000 or re.fullmatch(r"[0-9a-f]{64}", args.reference_sha256) is None:
        raise ValueError("bounded exact operator reference pin required")
    if any(p.is_symlink() for p in (args.output, *args.output.parents)):
        raise ValueError("output path must not contain aliases")
    if args.output.exists():
        raise FileExistsError("fresh output required")
    core = load_core()
    result, status = evaluate(core, args.submission, args.reference,
                            {"bytes": args.reference_bytes, "sha256": args.reference_sha256})
    result.update(candidate_program_executed=False, model_fits=0,
                  benchmark_id="PAPER-ROOT-ADD-016", new_benchmark_ids=0,
                  scope="Six prescribed Salzburg posterior summaries; no model-fidelity, biological-causality, improvement or full-paper qualification.")
    encoded = (json.dumps(result, indent=2, allow_nan=False) + "\n").encode()
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    print(json.dumps({"status": result["status"], "output_bytes": len(encoded)}), flush=True)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
