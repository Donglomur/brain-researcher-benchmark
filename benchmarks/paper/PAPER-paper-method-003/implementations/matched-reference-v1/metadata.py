#!/usr/bin/env python3
"""Metadata-only REVE preparation and fit-receipt checks.

These commands use the public validators without loading native.py, model
packages, signal arrays, weights, or a provider. A valid receipt is metadata
consistency, not proof of training, runtime admission, or paper reproduction.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
from types import ModuleType

HERE = Path(__file__).resolve().parent
MAX_JSON_BYTES = 8 * 1024 * 1024
SOURCES = {
    "recipe": (HERE / "recipe.py",
               "0c1bc432f3386d2a673e9f1f50776e4c4885d6d9609b1083068569c552dbe801"),
    "adapter": (HERE.parent / "opaque-submission-v1/adapter.py",
                "5e57a4de3f5a0d0015f04e576a78d8a13fe18f5df475864e0f0f62a82c6b4bcf"),
}


def _digest(value):
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise argparse.ArgumentTypeError("expected a lowercase SHA-256 identity")
    return value


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key: " + key)
        result[key] = value
    return result


def _finite(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("nonfinite JSON number")
    return result


def _reject_constant(value):
    raise ValueError("nonfinite JSON constant: " + value)


def _read(path, maximum):
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= maximum:
            raise ValueError("input must be a bounded ordinary nonempty file")
        raw = stream.read(maximum + 1)
        after = os.fstat(stream.fileno())
    keys = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
    if len(raw) != before.st_size or any(getattr(before, key) != getattr(after, key) for key in keys):
        raise ValueError("input changed while reading")
    return raw


def _document(path, expected_sha256=None):
    raw = _read(path, MAX_JSON_BYTES)
    if expected_sha256 is not None and hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("independently selected file SHA-256 differs")
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique,
                       parse_float=_finite, parse_constant=_reject_constant)
    if type(value) is not dict:
        raise ValueError("JSON object required")
    return value, raw


def _module(name):
    path, expected = SOURCES[name]
    raw = _read(path, 64 * 1024)
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("public metadata validator source changed: " + name)
    module = ModuleType("_reve_metadata_" + name)
    module.__file__ = str(path)
    exec(compile(raw, str(path), "exec"), module.__dict__)
    return module


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8") + b"\n"


def _write_new(path, value):
    raw = _canonical(value)
    if len(raw) > MAX_JSON_BYTES:
        raise ValueError("metadata output exceeds 8 MiB")
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "wb") as stream:
        stream.write(raw)
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def prepare_info(args):
    document, raw = _document(args.manifest, args.manifest_sha256)
    adapter = _module("adapter")
    info = adapter.packet_info(document, args.materials_identity, args.panel_identity)
    # The existing packet ABI commits canonical manifest bytes. Do not issue a
    # descriptor for a different physical manifest encoding.
    if info["manifest_pin"] != {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}:
        raise ValueError("public packet manifest must use its canonical JSON encoding")
    output = _write_new(args.output, info)
    return {"schema": "reve-metadata-preparation-v1", "status": "metadata_valid",
            "info": {"path": str(args.output), **output},
            "condition": info["condition"], "data_identity": info["data_identity"],
            "array_bodies_authenticated": False, "scientific_qualification": False}


def check_fit(args):
    info, _ = _document(args.info, args.info_sha256)
    document, _ = _document(args.fit_receipt)
    recipe = _module("recipe")
    recipe.validate_fit_receipt(document, info, args.fit_identity)
    return {"schema": "reve-fit-metadata-check-v1", "status": "metadata_valid",
            "fit_identity": document["identity"], "data_identity": document["data_identity"],
            "selected_stage": document["selected_stage"], "selected_epoch": document["selected_epoch"],
            "checkpoint_descriptor": document["checkpoint"], "checkpoint_body_authenticated": False,
            "training_execution_verified": False, "scientific_qualification": False}


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare-info", help="Validate one public manifest and write a fresh info JSON.")
    prepare.add_argument("--manifest", required=True, type=Path)
    prepare.add_argument("--manifest-sha256", required=True, type=_digest)
    prepare.add_argument("--materials-identity", required=True, type=_digest)
    prepare.add_argument("--panel-identity", required=True, type=_digest)
    prepare.add_argument("--output", required=True, type=Path)
    check = commands.add_parser("check-fit", help="Check a complete public-recipe receipt without loading its checkpoint.")
    check.add_argument("--info", required=True, type=Path)
    check.add_argument("--info-sha256", required=True, type=_digest)
    check.add_argument("--fit-receipt", required=True, type=Path)
    check.add_argument("--fit-identity", required=True, type=_digest)
    return parser


def main(argv=None):
    args = _parser().parse_args(argv)
    try:
        result = prepare_info(args) if args.command == "prepare-info" else check_fit(args)
        print(_canonical(result).decode("utf-8"), end="")
        return 0
    except (OSError, ValueError, TypeError, KeyError, RecursionError) as error:
        import sys
        print("REVE metadata refused: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
