"""Public-only NEURAL-043 submission preflight. No targets, fit or scoring."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

from direction_scorer import MODES, ScoringError, validate_submission_cohort


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ScoringError("duplicate JSON key: " + key)
        result[key] = value
    return result


def _nonfinite(value):
    raise ScoringError("nonfinite JSON value: " + value)


def _finite_float(value):
    parsed = float(value)
    if not math.isfinite(parsed):
        _nonfinite(value)
    return parsed


def preflight_files(public_path, submission_path, roster_path, *, access_mode,
                    max_input_bytes=32 * 1024**2):
    """Parse bounded immutable snapshots and bind the summary to those bytes.

    The size limit covers the three JSON files combined. Raising it is an
    explicit caller resource choice, not a change to scientific eligibility.
    """
    if type(max_input_bytes) is not int or max_input_bytes < 1:
        raise ScoringError("max_input_bytes must be a positive integer")
    documents, inputs = {}, {}
    remaining = max_input_bytes
    for role, path in (("public", public_path), ("submission", submission_path),
                       ("expected_cases", roster_path)):
        with Path(path).open("rb") as stream:
            raw = stream.read(remaining + 1)
        if len(raw) > remaining:
            raise ScoringError("combined input byte limit exceeded")
        remaining -= len(raw)
        documents[role] = json.loads(raw, object_pairs_hook=_object, parse_constant=_nonfinite,
                                     parse_float=_finite_float)
        inputs[role] = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    result = validate_submission_cohort(documents["submission"], documents["public"],
                                        expected_case_ids=documents["expected_cases"],
                                        access_mode=access_mode)
    return {**result, "input_snapshots": inputs}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public", type=Path, required=True, help="JSON list of public case packets")
    parser.add_argument("--submission", type=Path, required=True, help="JSON list of submission packets")
    parser.add_argument("--expected-cases", type=Path, required=True,
                        help="independently frozen evaluator JSON list of complete case IDs")
    parser.add_argument("--access-mode", choices=MODES, required=True)
    parser.add_argument("--max-input-bytes", type=int, default=32 * 1024**2)
    args = parser.parse_args(argv)
    try:
        result = preflight_files(args.public, args.submission, args.expected_cases,
                                 access_mode=args.access_mode, max_input_bytes=args.max_input_bytes)
    except (OSError, ValueError, UnicodeError, RecursionError) as error:
        parser.error(str(error))
    json.dump(result, sys.stdout, sort_keys=True, allow_nan=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
