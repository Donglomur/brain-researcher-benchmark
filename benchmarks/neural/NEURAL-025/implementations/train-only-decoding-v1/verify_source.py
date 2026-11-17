#!/usr/bin/env python3
"""Inspect an explicitly trusted current source descriptor without imports."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys


PACKAGE = "benchmarks/neural/NEURAL-025/implementations/train-only-decoding-v1"
DESCRIPTOR = "benchmarks/integrity/current-closures/construction-calcium-pipeline/SOURCE.json"


def checked(root, relative):
    name = PurePosixPath(relative)
    if (not isinstance(relative, str) or name.is_absolute() or
            str(name) != relative or any(x in ("", ".", "..") for x in name.parts)):
        raise ValueError("Noncanonical source path")
    current = root
    for part in name.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("Source aliases are not admitted")
    if not current.is_file():
        raise ValueError("Missing regular source member")
    return current


def capture(path, limit):
    with path.open("rb") as source:
        body = source.read(limit + 1)
    if len(body) > limit:
        raise ValueError("Source member exceeds inspection bound")
    return body


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate descriptor key")
        result[key] = value
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[5])
    args = parser.parse_args(argv)
    try:
        root = args.repo_root.resolve(strict=True)
        expected = args.expected_sha256
        if len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected):
            raise ValueError("Expected descriptor hash is malformed")
        body = capture(checked(root, DESCRIPTOR), 131072)
        if hashlib.sha256(body).hexdigest() != expected:
            raise ValueError("Current descriptor hash mismatch")
        descriptor = json.loads(body, object_pairs_hook=unique)
        if descriptor["schema"] != "neural025_current_source_v1" or descriptor["task_id"] != "NEURAL-025":
            raise ValueError("Wrong descriptor identity")
        rows = descriptor["members"]
        if not isinstance(rows, list) or not 1 <= len(rows) <= 32:
            raise ValueError("Invalid source roster")
        seen = set()
        total = 0
        for row in rows:
            relative = row["path"]
            if relative in seen or type(row["bytes"]) is not int or not 0 <= row["bytes"] <= 1048576:
                raise ValueError("Malformed source identity")
            seen.add(relative)
            data = capture(checked(root, relative), 1048576)
            total += len(data)
            if total > 2097152:
                raise ValueError("Aggregate inspection bound exceeded")
            if len(data) != row["bytes"] or hashlib.sha256(data).hexdigest() != row["sha256"]:
                raise ValueError("Current source member differs: " + relative)
        package = root / PACKAGE
        actual = set()
        for candidate in package.rglob("*"):
            if candidate.is_symlink():
                raise ValueError("Package contains an alias")
            if candidate.is_file():
                actual.add(candidate.relative_to(root).as_posix())
            elif not candidate.is_dir():
                raise ValueError("Package contains a non-source member")
        if actual != {x for x in seen if x.startswith(PACKAGE + "/")}:
            raise ValueError("Package has missing or extra members")
        print(json.dumps({"status": "current_source_inspection_passed", "members": len(rows),
                          "bytes_read": total + len(body), "source_execution": False,
                          "scientific_qualification": False}))
        return 0
    except (OSError, ValueError, KeyError, TypeError, RecursionError) as exc:
        print(json.dumps({"status": "refused", "reason": str(exc)[:1000]}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
