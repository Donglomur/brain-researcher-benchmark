#!/usr/bin/env python3
"""Operator CLI for released-profile REVE fits and compatibility checks.

Execution, isolation and resource admission belong to the enclosing operator.
This entrypoint does not install dependencies or admit a scientific campaign.
"""
from __future__ import annotations

import argparse
from types import ModuleType
import json
import math
import os
from pathlib import Path
import stat
import sys

MAX_JSON_BYTES = 8 * 1024 * 1024
HERE = Path(__file__).resolve().parent


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _finite_float(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("nonfinite JSON number")
    return result


def _reject_constant(value):
    raise ValueError(f"nonfinite JSON constant: {value}")


def _read_json(path):
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    with os.fdopen(os.open(path, flags), "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_JSON_BYTES:
            raise ValueError("JSON input must be an ordinary file of at most 8 MiB")
        body = stream.read(MAX_JSON_BYTES + 1)
        after = os.fstat(stream.fileno())
    if len(body) > MAX_JSON_BYTES:
        raise ValueError("JSON input exceeds 8 MiB")
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError("JSON input changed while reading")
    document = json.loads(
        body.decode("utf-8"),
        object_pairs_hook=_unique_object,
        parse_float=_finite_float,
        parse_constant=_reject_constant,
    )
    if type(document) is not dict:
        raise ValueError("JSON input must be an object")
    return document


def _write_json(path, document):
    if type(document) is not dict:
        raise ValueError("native result must be a JSON object")
    body = (json.dumps(document, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")
    if len(body) > MAX_JSON_BYTES:
        raise ValueError("JSON result exceeds 8 MiB")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    with os.fdopen(os.open(path, flags, 0o600), "wb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError("JSON output must be an ordinary file")
        stream.write(body)


def _native_module():
    # Keep source loading free of pyc writes. Native scientific imports occur
    # inside the selected API, after its own profile and admission checks.
    sys.dont_write_bytecode = True
    path = HERE / "native.py"
    module = ModuleType("_reve_operator_native")
    module.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
    return module


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("fit", "predict", "compatibility"):
        sub = commands.add_parser(name, aliases=["compat"] if name == "compatibility" else [])
        sub.add_argument("--info", type=Path, required=True, help="Existing admitted info JSON.")
        sub.add_argument("--packet", type=Path, required=True)
        sub.add_argument("--author-source", type=Path, required=True)
        sub.add_argument("--profile", choices=("cuda-fp16", "cpu-fp32-math"))
        sub.add_argument("--overlay", type=Path, help="Required for the CPU profile.")
        sub.add_argument("--output", type=Path, required=True, help="Fresh directory; parent must exist.")
        if name in ("fit", "compatibility"):
            sub.add_argument("--encoder", type=Path, required=True)
            sub.add_argument("--seed", type=int, required=True)
        else:
            sub.add_argument("--checkpoint", type=Path, required=True)
            sub.add_argument("--fit-receipt", type=Path, required=True)
            sub.add_argument("--fit-identity", required=True)
    return parser


def main(argv=None):
    parser = _parser()
    args = parser.parse_args(argv)
    compatibility = args.command in ("compatibility", "compat")
    if compatibility and args.profile != "cpu-fp32-math":
        parser.error("compatibility requires explicit --profile cpu-fp32-math")
    profile = args.profile or "cuda-fp16"
    if profile == "cpu-fp32-math" and args.overlay is None:
        parser.error("cpu-fp32-math requires --overlay")
    try:
        info = _read_json(args.info)
        receipt = _read_json(args.fit_receipt) if args.command == "predict" else None
        native = _native_module()
        # Never reuse a partial outcome or overwrite another invocation.
        args.output.mkdir(mode=0o700, parents=False, exist_ok=False)
        common = {
            "info": info,
            "packet_root": args.packet,
            "source": args.author_source,
            "profile": profile,
            "overlay": args.overlay,
        }
        if args.command == "predict":
            result = native.predict_selected(
                **common,
                checkpoint_path=args.checkpoint,
                fit_receipt=receipt,
                expected_fit_identity=args.fit_identity,
            )
            result_path = args.output / "predictions.json"
        else:
            checkpoint = args.output / "classifier.pt"
            operation = native.training_compatibility if compatibility else native.fit_reference
            result = operation(
                **common,
                encoder_path=args.encoder,
                seed=args.seed,
                checkpoint_output=checkpoint,
            )
            if not stat.S_ISREG(checkpoint.lstat().st_mode):
                raise ValueError("native checkpoint output must be an ordinary file")
            result_path = args.output / ("compatibility.json" if compatibility else "fit.json")
        _write_json(result_path, result)
    except (OSError, ValueError, TypeError, RuntimeError, ImportError, KeyError, RecursionError) as error:
        print(f"REVE operator refused: {error}", file=sys.stderr)
        return 2
    print(json.dumps({"status": "ok", "command": args.command, "result": str(result_path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
