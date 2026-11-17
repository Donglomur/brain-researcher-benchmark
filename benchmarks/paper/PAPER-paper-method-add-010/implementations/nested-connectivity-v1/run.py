#!/usr/bin/env python3
"""Bounded JSON entry points for prospective MEG nested evaluation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import types

# Load the sibling source explicitly so unrelated working-directory modules are
# not selected. Release integrity is checked by the separate current descriptor.
_core_path = Path(__file__).with_name("core.py")
_core_bytes = _core_path.read_bytes()
_core_sha256 = hashlib.sha256(_core_bytes).hexdigest()
core = types.ModuleType("meg_nested_core")
core.__file__ = str(_core_path)
exec(compile(_core_bytes, str(_core_path), "exec"), core.__dict__)


def pairs(values):
    result = {}
    for key, value in values:
        core.require(key not in result, "Duplicate JSON key")
        result[key] = value
    return result


def read_json(path, maximum, expected_sha=None):
    core.require(type(maximum) is int and 0 < maximum < sys.maxsize, "Invalid input byte limit")
    core.require("\0" not in os.fspath(path), "NUL in input path")
    raw = bytearray()
    with open(path, "rb") as stream:
        # A logical cap must not itself become a giant allocation request.
        # Retain at most cap+1 actual bytes, including one excess-byte probe.
        while len(raw) <= maximum:
            block = stream.read(min(65536, maximum + 1 - len(raw)))
            if not block:
                break
            raw.extend(block)
    core.require(len(raw) <= maximum, "Input exceeds explicit byte limit")
    sha = hashlib.sha256(raw).hexdigest()
    if expected_sha is not None:
        core.require(sha == expected_sha, "Protocol file differs from selected SHA-256")
    try:
        value = json.loads(raw, object_pairs_hook=pairs,
                           parse_constant=lambda _: (_ for _ in ()).throw(core.Refusal("Nonfinite JSON constant")))
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise core.Refusal("Malformed JSON input") from exc
    return value, sha


def write_new_json(path, value, maximum):
    # Output stays operator-side; never overwrite an input or existing result.
    core.require(type(maximum) is int and 0 < maximum < sys.maxsize, "Invalid output byte limit")
    try:
        body = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    except (ValueError, TypeError, RecursionError) as exc:
        raise core.Refusal("Output is not finite JSON") from exc
    core.require(len(body) <= maximum, "Output exceeds explicit byte limit")
    core.require("\0" not in os.fspath(path), "NUL in output path")
    destination = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=destination.parent,
                                         prefix=".meg-output-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(body)
        # Publish a complete body, refusing all existing names (including input
        # aliases). This is not a hostile-directory or power-loss durability claim.
        os.link(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("preflight", "fold", "evaluate", "score"))
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--protocol-sha256", required=True)
    parser.add_argument("--features", required=True)
    parser.add_argument("--labels")
    parser.add_argument("--predictions")
    parser.add_argument("--fold-id")
    parser.add_argument("--operator-offline-reference", action="store_true")
    parser.add_argument("--max-input-bytes", required=True, type=int)
    parser.add_argument("--max-output-bytes", required=True, type=int)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        core.sha(args.protocol_sha256)
        core.require(0 < args.max_input_bytes < sys.maxsize and 0 < args.max_output_bytes < sys.maxsize,
                     "Explicit byte limits must be positive and below sys.maxsize")
        p, protocol_file_sha = read_json(args.protocol, args.max_input_bytes, args.protocol_sha256)
        data, feature_file_sha = read_json(args.features, args.max_input_bytes)
        # This guard runs before target files are read or numerical libraries loaded.
        work = core.preflight(data, p, args.fold_id if args.command == "fold" else None)
        if args.command == "preflight":
            core.require(not args.labels and not args.predictions and not args.fold_id, "Preflight has no target/prediction/fold operands")
            result = {"schema": "meg_preflight_v1", "workload": work,
                      "scientific_qualification": False, "physical_provenance_verified": False}
        else:
            core.require(args.labels is not None, "This command requires labels")
            if args.command == "fold":
                core.require(args.fold_id is not None and not args.predictions, "Fold requires an ID and outer-training labels only")
            else:
                core.require(not args.fold_id, "Only fold accepts --fold-id")
            if args.command == "evaluate":
                core.require(args.operator_offline_reference and not args.predictions,
                             "Offline full-reference evaluation requires explicit operator route selection")
            if args.command == "score":
                core.require(args.predictions is not None, "Score requires a prediction table")
            labels, _ = read_json(args.labels, args.max_input_bytes)
            if args.command == "fold":
                result = core.fit_predict_fold(data, labels, p, args.fold_id)
            elif args.command == "evaluate":
                result = core.run_nested(data, labels, p)
            else:
                predictions, _ = read_json(args.predictions, args.max_input_bytes)
                result = core.score_predictions(data, labels, predictions, p)
        result["input_file_sha256"] = {"protocol": protocol_file_sha, "features": feature_file_sha}
        result["executed_core_sha256"] = _core_sha256
        write_new_json(args.output, result, args.max_output_bytes)
        return 0
    except (core.Refusal, OSError) as exc:
        print(json.dumps({"status": "refused", "reason": str(exc), "scientific_qualification": False}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
