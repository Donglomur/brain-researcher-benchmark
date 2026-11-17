#!/usr/bin/env python3
"""NEURAL-080 explicit separate-process source operator.

No command acquires external assets or grants input/runtime qualification.
prepare, stage, execute and compare are separate invocations. Running --help
parses only ordinary CLI metadata and imports no scientific module.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


def _bootstrap():
    root = Path(__file__).resolve().parent
    for directory in reversed((root / "source", root / "source/private", root / "source/public")):
        sys.path.insert(0, str(directory))


def _strict_json(text):
    from io_contract import decode
    return decode(text.encode("utf-8"))


def _owner(text):
    from input_owner import Owner
    return Owner(_strict_json(text))


def _descriptor(path, size, sha):
    from generalization.artifacts import descriptor
    value = {"path": Path(path).name, "bytes": size, "sha256": sha}
    descriptor(value, 16 * 1024 * 1024)
    return value


def _configuration(args, owner):
    from input_owner import capture
    from io_contract import decode
    path = Path(args.config)
    if not path.is_absolute():
        raise ValueError("Explicit absolute configuration path required")
    row = _descriptor(path, args.bytes, args.sha256)
    body = capture(path.parent, row, owner, max_bytes=16 * 1024 * 1024)
    return path.parent, row, decode(body)


def _error_summary(error):
    if error is None:
        return None
    try:
        message = str(error)
    except BaseException as formatting_error:
        message = "Exception message unavailable: " + type(formatting_error).__name__
    return {"type": type(error).__name__[:80], "message": message[:160]}


def _failure_observation(owner, operation, error):
    """Bounded stderr custody; incomplete attempt projections are labelled."""
    maximum_bytes, maximum_attempts, maximum_secondary = 8192, 16, 4
    projected = []
    for row in owner.attempts[-maximum_attempts:]:
        secondary = row.get("secondary", [])
        projected.append({"operation": str(row.get("operation", ""))[:100],
            "state": str(row.get("state", ""))[:32], "first": _error_summary(row.get("first")),
            "secondary": [_error_summary(item) for item in secondary[:maximum_secondary]],
            "secondary_total": len(secondary), "secondary_projection_complete": len(secondary) <= maximum_secondary})
    observation = {"schema": "neural080_cli_failure_observation_v1", "operation": operation,
        "logical_usage": dict(owner.used), "logical_limits": dict(owner.limits),
        "primary": _error_summary(error), "attempt_total": len(owner.attempts), "attempts": projected,
        "attempt_projection_complete": len(owner.attempts) <= maximum_attempts,
        "report_byte_cap": maximum_bytes,
        "scope": "Actual cumulative logical counters; bounded attempt/error projection only. Raw exception still propagates. Failed scientific case is unavailable; native aggregate/whole-host costs remain unqualified."}
    while True:
        body = (json.dumps(observation, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
        if len(body) <= maximum_bytes:
            break
        if not observation["attempts"]:
            raise ValueError("Bounded CLI failure observation exceeds its explicit minimum capacity")
        observation["attempts"].pop(0)
        observation["attempt_projection_complete"] = False
    at = 0
    while at < len(body):
        written = os.write(2, body[at:])
        if written <= 0:
            raise OSError("Incomplete CLI failure observation write")
        at += written


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="operation", required=True)
    for operation in ("prepare", "stage", "execute", "compare"):
        command = commands.add_parser(operation)
        command.add_argument("--config", required=True)
        command.add_argument("--bytes", required=True, type=int)
        command.add_argument("--sha256", required=True)
        command.add_argument("--output", required=True)
        command.add_argument("--logical-limits", required=True,
                             help="JSON object with explicit read_bytes/write_bytes/retained_bytes/attempts")
        if operation == "prepare":
            command.add_argument("--roots", required=True,
                                 help="JSON object with metadata/recordings/media/logs/checkpoint absolute roots")
    worker = commands.add_parser("worker-reference")
    worker.add_argument("--case", required=True)
    worker.add_argument("--bytes", type=int, required=True)
    worker.add_argument("--sha256", required=True)
    worker.add_argument("--context-bytes", type=int, required=True)
    worker.add_argument("--context-sha256", required=True)
    worker.add_argument("--output", required=True)
    worker.add_argument("--logical-limits", required=True)
    args = parser.parse_args(argv)
    _bootstrap()
    owner = _owner(args.logical_limits)
    record = owner.begin("cli_phase:" + args.operation)
    try:
        if args.operation == "worker-reference":
            from generalization.worker import reference_case
            path = Path(args.case)
            if str(path) != "/view/CASE.json" or args.output != "/output":
                raise ValueError("Reference worker requires the actual isolated runner view/output paths")
            answer = reference_case(path.parent, _descriptor(path, args.bytes, args.sha256),
                                    _descriptor("CONTEXT.json", args.context_bytes, args.context_sha256),
                                    args.output, owner)
        else:
            config_root, config_pin, config = _configuration(args, owner)
            if args.operation == "prepare":
                from generalization.operator import prepare
                answer = prepare(config_root, config_pin, _strict_json(args.roots), args.output, owner)
            else:
                from generalization import campaign
                if type(config) is not dict:
                    raise ValueError("Closed phase configuration object required")
                if args.operation == "stage":
                    if set(config) != {"schema", "prepared_root", "prepared_manifest", "selection"} or config["schema"] != "neural080_stage_command_v1":
                        raise ValueError("Exact complete stage command configuration required")
                    answer = campaign.stage(config["prepared_root"], config["prepared_manifest"], config["selection"], args.output, owner)
                elif args.operation == "execute":
                    if set(config) != {"schema", "stage_root", "staged_manifest", "selection"} or config["schema"] != "neural080_execute_command_v1":
                        raise ValueError("Exact complete execute command configuration required")
                    answer = campaign.execute(config["stage_root"], config["staged_manifest"], config["selection"], args.output, owner)
                else:
                    if set(config) != {"schema", "execution_root", "execution_manifest"} or config["schema"] != "neural080_compare_command_v1":
                        raise ValueError("Exact complete compare command configuration required")
                    answer = campaign.compare(config["execution_root"], config["execution_manifest"], args.output, owner)
        print(json.dumps({"operation": args.operation, "output": answer["output"],
                          "manifest": answer["manifest"], "logical_usage": owner.used}, sort_keys=True))
    except BaseException as error:
        owner.failure(record, error)
        try:
            _failure_observation(owner, args.operation, error)
        except BaseException as report_error:
            owner.failure(record, report_error)
            try:
                setattr(error, "cli_reporting_failure", report_error)
            except BaseException:
                pass
        raise
    owner.complete(record)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
