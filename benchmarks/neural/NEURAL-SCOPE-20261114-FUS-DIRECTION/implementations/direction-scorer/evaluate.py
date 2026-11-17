"""Bounded standalone evaluator; run only inside an independently admitted grader."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scorer import ConstructionError, CONDITIONS, evaluate, pin


def read_pinned(path, digest, cap):
    if not pin(digest):
        raise ValueError("expected lowercase SHA-256 required")
    before = os.lstat(path)
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or not 0 <= before.st_size <= cap:
        raise ValueError("operand must be bounded, ordinary and single-link")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        opened = os.fstat(fd)
        def identity(s):
            return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink)
        if identity(before) != identity(opened) or not stat.S_ISREG(opened.st_mode):
            raise ValueError("operand identity changed")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            body = stream.read(cap + 1)
        if len(body) > cap or identity(opened) != identity(os.fstat(fd)) or identity(opened) != identity(os.lstat(path)):
            raise ValueError("operand changed during capture")
    finally:
        os.close(fd)
    if hashlib.sha256(body).hexdigest() != digest:
        raise ValueError("operand digest mismatch")
    return body


def strict_json(body):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    def constant(value):
        raise ValueError("nonfinite JSON constant")
    return json.loads(body, object_pairs_hook=pairs, parse_constant=constant)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--intake", required=True)
    parser.add_argument("--intake-sha256", required=True)
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--predictions-sha256", required=True)
    parser.add_argument("--condition", choices=CONDITIONS, required=True)
    args = parser.parse_args(argv)
    # Capture the committed candidate before accessing the private intake.
    body = read_pinned(args.predictions, args.predictions_sha256, 16 * 1024 * 1024)
    malformed_json = False
    try:
        predictions = strict_json(body)
    except (ValueError, UnicodeError, RecursionError):
        predictions = None
        malformed_json = True
    intake = strict_json(read_pinned(args.intake, args.intake_sha256, 64 * 1024 * 1024))
    try:
        result = evaluate(intake, predictions, condition=args.condition)
    except ConstructionError as error:
        print(json.dumps({"status": "construction_invalid", "primary": None, "reason": str(error)}))
        return 2
    result["prediction_json_invalid"] = malformed_json
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
