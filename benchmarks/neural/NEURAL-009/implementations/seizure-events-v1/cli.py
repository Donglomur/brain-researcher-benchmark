#!/usr/bin/env python3
"""Operator-only CLI; never launches a candidate or reads native EEG."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import types

ROOT = Path(__file__).resolve().parent


def need(ok, message):
    if not ok:
        raise ValueError(message)


def pairs(items):
    result = {}
    for key, value in items:
        need(key not in result, "Duplicate JSON object key")
        result[key] = value
    return result


def forbidden_constant(value):
    raise ValueError("Non-finite JSON constant")


def read_bytes(path, cap):
    need(type(cap) is int and cap > 0, "A positive input byte budget is required")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        need(stat.S_ISREG(info.st_mode) and info.st_size <= cap,
             "Input must be a regular file within the declared byte budget")
        chunks = []
        total = 0
        while True:
            chunk = stream.read(min(65536, cap - total + 1))
            if not chunk:
                break
            total += len(chunk)
            need(total <= cap, "Input grew beyond the declared byte budget")
            chunks.append(chunk)
    return b"".join(chunks)


def read_json(path, cap):
    return json.loads(read_bytes(path, cap), object_pairs_hook=pairs,
                      parse_constant=forbidden_constant)


def load_verified_core(expected):
    need(isinstance(expected, str) and re.fullmatch(r"[0-9a-f]{64}", expected),
         "An independently obtained source-manifest hash is required")
    raw = read_bytes(ROOT / "source_manifest.json", 262144)
    need(hashlib.sha256(raw).hexdigest() == expected, "Source manifest identity mismatch")
    manifest = json.loads(raw, object_pairs_hook=pairs, parse_constant=forbidden_constant)
    need(manifest["schema"] == "neural009_current_source_v1", "Unexpected source manifest")
    captured = {}
    for row in manifest["files"]:
        name = row["path"]
        need(isinstance(name, str) and name not in captured and not name.startswith("/")
             and all(part not in ("", ".", "..") for part in name.split("/")),
             "Invalid source member path")
        path = ROOT / name
        need(not any(parent.is_symlink() for parent in [path, *path.parents] if parent != ROOT.parent),
             "Source members must not traverse symlinks")
        need(type(row["bytes"]) is int and 0 < row["bytes"] <= 262144,
             "Source member exceeds reviewed capture limit")
        body = read_bytes(path, row["bytes"])
        need(len(body) == row["bytes"] and hashlib.sha256(body).hexdigest() == row["sha256"],
             "Current source member identity mismatch")
        captured[name] = body
    need("core.py" in captured and "cli.py" in captured, "Executable source closure is incomplete")
    module = types.ModuleType("neural009_verified_core")
    module.__file__ = str(ROOT / "core.py")
    exec(compile(captured["core.py"], module.__file__, "exec"), module.__dict__)
    return module, manifest


def write_output(path, value, cap):
    body = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    need(type(cap) is int and 0 < len(body) <= cap, "Result exceeds declared output byte budget")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(body)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("verify-source", "public-support", "evaluate"))
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--admission")
    parser.add_argument("--candidate")
    parser.add_argument("--policy")
    parser.add_argument("--support")
    parser.add_argument("--expected-policy-sha256")
    parser.add_argument("--limits")
    parser.add_argument("--output")
    parser.add_argument("--max-input-bytes", type=int)
    parser.add_argument("--max-output-bytes", type=int)
    args = parser.parse_args(argv)
    try:
        core, manifest = load_verified_core(args.expected_manifest_sha256)
        if args.command == "verify-source":
            index, people, digest = core.source_index()
            print(json.dumps({"status": "source_verified", "recordings": len(index),
                              "biological_people": len(people), "source_members": len(manifest["files"]),
                              "source_index_sha256": digest,
                              "recommended_policy_sha256": core.canonical_sha256(core.recommended_policy()),
                              "scientific_qualification": False}, sort_keys=True))
            return 0
        need(args.admission and args.limits and args.output, "Admission, limits and fresh output are required")
        need(args.max_input_bytes is not None and args.max_input_bytes > 0
             and args.max_output_bytes is not None and args.max_output_bytes > 0,
             "Explicit positive input/output byte budgets are required")
        paths = [Path(value).resolve() for value in
                 (args.admission, args.candidate, args.policy, args.support, args.limits, args.output) if value]
        need(len(set(paths)) == len(paths), "Input and output roles must be distinct paths")
        need(not Path(args.output).exists() and not Path(args.output).is_symlink(),
             "Output must be a new path")
        if args.command == "evaluate":
            need(args.candidate and args.policy and args.support and args.expected_policy_sha256,
                 "Candidate, public support, policy and independently frozen policy hash are required")
            # Candidate structure is checked before the reference file is opened.
            candidate = read_json(args.candidate, args.max_input_bytes)
            core.validate_candidate(candidate)
            policy = read_json(args.policy, args.max_input_bytes)
            core.validate_policy(policy, args.expected_policy_sha256)
            if candidate["policy_sha256"] != args.expected_policy_sha256:
                raise core.CandidateError("Candidate is not bound to the frozen policy")
        limits = read_json(args.limits, args.max_input_bytes)
        if args.command == "evaluate":
            support = read_json(args.support, args.max_input_bytes)
            core.prevalidate_candidate(candidate, policy, support,
                                       expected_policy_sha256=args.expected_policy_sha256, limits=limits)
        admission = read_json(args.admission, args.max_input_bytes)
        if args.command == "public-support":
            index, people, index_sha = core.source_index()
            core._admit(admission, index, people, index_sha, limits)
            result = core.public_support(admission)
        else:
            result = core.evaluate(admission, policy, candidate,
                                   expected_policy_sha256=args.expected_policy_sha256, limits=limits)
        write_output(args.output, result, args.max_output_bytes)
        print(json.dumps({"status": "written", "command": args.command,
                          "scientific_qualification": False}, sort_keys=True))
        return 0
    except (ValueError, OSError, ImportError, RecursionError, KeyError, TypeError, MemoryError) as exc:
        print(json.dumps({"status": "refused", "error_type": type(exc).__name__,
                          "reason": str(exc), "scientific_qualification": False}, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
