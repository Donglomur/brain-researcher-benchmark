#!/usr/bin/env python3
"""Check complete SMC predictions using a participant's public panel only.

This is a local formatting check, not an operator freeze, score or provenance
decision. No target, other-condition packet or model asset is accepted.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import stat


TASK_ID = "PAPER-SMC-RNN-2024"
SOURCE_PINS = {
    "scorer.py": "48638a595755138b32ff9c228804fd8c19c9ff874cd254f135fc5245ee9a25f8",
    "reference_panel.json": "209a15e2189499a9e68264df5c9f81057dd919564d98a46fb64d75b3f39af2f3",
}
METHODS = {"reproduction": ("causal", "noncausal"), "improvement": ("offline",)}
MAX_PANEL_BYTES = 1024 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def regular_size(path):
    """Reject directories, symlinks and devices before any content read."""
    info = Path(path).lstat()
    require(stat.S_ISREG(info.st_mode), "input must be a regular file")
    return info.st_size


def file_hash(path, limit):
    require(type(limit) is int and limit > 0, "positive file byte limit required")
    require(0 < regular_size(path) <= limit, "empty file or file byte limit exceeded")
    digest = hashlib.sha256()
    size = 0
    with Path(path).open("rb") as handle:
        while block := handle.read(min(1024 * 1024, limit + 1 - size)):
            size += len(block)
            require(size <= limit, "file grew beyond byte limit")
            digest.update(block)
    return digest.hexdigest()


def load_validator(source_dir=None):
    source_dir = (Path(source_dir) if source_dir is not None else
                  Path(__file__).resolve().parent.parent / "source-matched-nlb-v1")
    for name, expected in SOURCE_PINS.items():
        require(file_hash(source_dir / name, MAX_PANEL_BYTES) == expected,
                "retained validation source differs: " + name)
    spec = importlib.util.spec_from_file_location("_smc_participant_validator", source_dir / "scorer.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_submissions(values):
    submissions = {}
    for value in values:
        require("=" in value, "submission must use KEY=PATH")
        key, path = value.split("=", 1)
        require(key not in submissions and bool(path), "duplicate key or empty submission path")
        submissions[key] = Path(path)
    return submissions


def check_submissions(panel, panel_sha256, outcome, submissions, *, max_bytes, source_dir=None):
    require(outcome in METHODS, "unsupported outcome")
    require(isinstance(submissions, dict) and set(submissions) == set(METHODS[outcome]),
            "provide both causal/noncausal for reproduction or offline for improvement")
    require(type(max_bytes) is int and max_bytes > 0, "positive total prediction byte limit required")
    require(isinstance(panel_sha256, str) and re.fullmatch(r"[0-9a-f]{64}", panel_sha256) is not None,
            "public panel SHA256 required")
    require(file_hash(panel, MAX_PANEL_BYTES) == panel_sha256, "public panel differs from supplied pin")
    sizes = {key: regular_size(path) for key, path in submissions.items()}
    require(all(value > 0 for value in sizes.values()) and sum(sizes.values()) <= max_bytes,
            "complete prediction set exceeds byte limit or contains an empty file")

    validator = load_validator(source_dir)
    manifest = validator.read_json(panel)
    require(isinstance(manifest, dict), "public panel must be a JSON object")
    validator.validate_panel(manifest)
    checked = {}
    for key in METHODS[outcome]:
        path = submissions[key]
        before = file_hash(path, sizes[key])
        expected = validator.validate_submission(path, manifest)
        require(file_hash(path, sizes[key]) == before, "prediction changed during preflight")
        # Match the current continuous operator: six required arrays or all eight.
        with validator.h5py.File(path, "r") as handle:
            present = set(handle[validator.DATASET])
        checked[key] = {
            "sha256": before,
            "bytes": sizes[key],
            "arrays": {name: expected[name] for name in sorted(present)},
        }
    require(file_hash(panel, MAX_PANEL_BYTES) == panel_sha256, "public panel changed during preflight")
    # Recheck every file at the end, including an earlier method in a paired set.
    for key in METHODS[outcome]:
        require(file_hash(submissions[key], sizes[key]) == checked[key]["sha256"],
                "prediction changed during complete-set preflight")
    return {
        "schema": "smc_participant_submission_preflight_v1",
        "task_id": TASK_ID,
        "outcome": outcome,
        "public_panel_sha256": panel_sha256,
        "validation_source_sha256": SOURCE_PINS,
        "submissions": checked,
        "format_valid": True,
        "operator_frozen": False,
        "target_accessed": False,
        "scientific_outcome": "unknown",
        "limits": [
            "Local format validation only; operator freeze and scoring remain required.",
            "Shape checks do not establish semantic trial, neuron or bin ordering.",
            "No source-method execution, access-condition, reproduction, improvement or SOTA claim.",
            "This is not an isolation boundary against a hostile or concurrently mutating process.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", type=Path, required=True)
    parser.add_argument("--panel-sha256", required=True,
                        help="SHA256 supplied with this condition's public test panel.")
    parser.add_argument("--outcome", choices=METHODS, required=True)
    parser.add_argument("--submission", action="append", required=True,
                        help="KEY=PATH; both causal/noncausal or one offline.")
    parser.add_argument("--max-bytes", type=int, required=True,
                        help="Total physical byte cap across submitted HDF5 files.")
    parser.add_argument("--source-dir", type=Path,
                        help="Optional relocated retained validator; exact source pins still required.")
    args = parser.parse_args(argv)
    try:
        report = check_submissions(args.panel, args.panel_sha256, args.outcome,
            parse_submissions(args.submission), max_bytes=args.max_bytes, source_dir=args.source_dir)
    except (ValueError, OSError) as error:
        parser.exit(2, "Submission preflight failed: " + str(error) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
