#!/usr/bin/env python3
"""Portable preparation of one authenticated NEURAL-025 source session.

`check` authenticates source files without loading numerical libraries or data.
`prepare` writes private session outputs, never a fitted/scored benchmark packet.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import types

HERE = Path(__file__).resolve().parent
IMMUTABLE = {
    "_core/pairing.py": (7325, "0c93a2817521651a94621bfd09b76f3d54c802443b29aac0df0f27f98ee755bb"),
    "_core/reference_pair.py": (12710, "7120e948d960938f6d018b9972f2ff772976bbb581ba0a83b261b495e8944793"),
    "_core/session_collector.py": (12976, "def3924f709b82c17f90539738df51b0fa65a17435759ef2f9dfaf200cd8ff7f"),
    "_core/session_export.py": (6707, "275badb038aa74b34c59d4062f65a2af032b2a0b3401546da62191a5b2917a3d"),
    "_core/session_projection.py": (22327, "47b06abbade0101eb33c7cddd4d64b30249c9ec078fa635688e5644e0823806f"),
    "_core/metadata.py": (25602, "2c9f7f8bf65f754a451326a7ef1c400ce85d812b4adbd4149cf3b904ecd6e5f1"),
    "../locked-mat-admission-v2/admission.py": (34094, "ffe2d7d43386f53f92e9e97b07e422581d8fc05e2fa53471bdb9ba38bbcd7ab6"),
    "../train-only-decoding-v2/source_condition.py": (5966, "c7ce9b2e464c262550e6e224d7d81becb1094306ff5aeedf819068eb8d14ce11"),
}
MODULES = {
    "admission": "../locked-mat-admission-v2/admission.py",
    "metadata": "_core/metadata.py", "projection": "_core/session_projection.py",
    "collector": "_core/session_collector.py", "pairing": "_core/pairing.py",
    "reference": "_core/reference_pair.py", "export": "_core/session_export.py",
    "source_condition": "../train-only-decoding-v2/source_condition.py",
}
RESOURCES = {"logical_read_cap_bytes": 2147483648,
             "single_callback_read_cap_bytes": 8388608,
             "array_output_cap_bytes": 94371840,
             "json_output_cap_bytes": 4194304, "work_seconds": 750}


class Refusal(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise Refusal(message)


def ordinary(path):
    path = Path(os.path.abspath(os.path.expanduser(os.fspath(path))))
    require(not any(part.is_symlink() for part in (path, *path.parents)), "Symlink path refused")
    return path


def read_source(path, pin=None):
    path = ordinary(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
                0 < before.st_size <= 262144, "Source must be an ordinary bounded file")
        body = bytearray()
        while len(body) < before.st_size:
            part = os.read(fd, min(65536, before.st_size - len(body)))
            require(bool(part), "Short source read")
            body.extend(part)
        after = os.fstat(fd)
        require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns),
                "Source changed during verification")
    finally:
        os.close(fd)
    body = bytes(body)
    observed = {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
    require(pin is None or observed == pin, "Source pin mismatch: " + path.name)
    return body


def decode(body):
    def pairs(items):
        value = {}
        for key, item in items:
            require(key not in value, "Duplicate JSON key")
            value[key] = item
        return value
    return json.loads(body, object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(Refusal("Nonfinite JSON")))


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def verify_package(root=None):
    """Verify a closed relative source namespace; no imports or original reads."""
    root = ordinary(HERE if root is None else root)
    descriptor = decode(read_source(root / "SOURCE.json"))
    require(set(descriptor) == {"schema", "files", "recipe", "qualification"} and
            descriptor["schema"] == "calcium-session-portable-source-v1" and
            descriptor["qualification"] == "source_delivery_only", "Exact source descriptor required")
    names = set(IMMUTABLE) | {"prepare.py", "adapter.py"}
    require(set(descriptor["files"]) == names, "Unexpected source namespace")
    sources = {}
    for name, pin in descriptor["files"].items():
        require(set(pin) == {"bytes", "sha256"}, "Exact source pin fields")
        if name in IMMUTABLE:
            require(pin == dict(zip(("bytes", "sha256"), IMMUTABLE[name])),
                    "Immutable source pin changed")
        sources[name] = read_source(root / name, pin)
    recipe = decode(read_source(root / "RECIPE.json", descriptor["recipe"]))
    require(canonical(recipe) == canonical(expected_recipe()), "Unsupported recipe or endpoint substitution")
    return {"root": root, "descriptor": descriptor, "sources": sources, "recipe": recipe}


def expected_recipe():
    return {"schema": "calcium-session-portable-recipe-v1", "session_id": "cfa24_20220727_160603",
            "original": {"filename": "R,cfa24_20220727_160603,thresholded,DLC3.mat",
                         "figshare_file_id": 60332984, "bytes": 980063226,
                         "md5": "5c89cea4cae04adf8c21f46b740d2c4b",
                         "sha256": "f97834b22135ca1509be34913e29300dd4ebbcc52436173fb1cb63c9afdf29d0"},
            "raw_records": 416, "eligible_trials": 372, "author_exclusions": 44,
            "feature_variant": "smoothed_deconvolved_events", "target": "stored_joint_angles_24",
            "source_condition_schema": "calcium_processed_input_source_condition_v2",
            "resources": dict(RESOURCES), "fit_or_score": False, "whole_cohort_admitted": False}


def bind_paths(original, output, *, package_root=None):
    """Resolve filesystem bindings only; exact original authentication is in adapter."""
    original, output = ordinary(original), ordinary(output)
    package_root = ordinary(HERE if package_root is None else package_root)
    checkout = package_root.parents[4]
    require(not original.is_relative_to(checkout) and not output.is_relative_to(checkout),
            "Originals and prepared outputs must remain outside the checkout")
    info = original.stat()
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "Ordinary input file required")
    require(original != output and original.parent != output, "Output cannot replace original location")
    require(output.parent.is_dir() and not output.exists(), "Output must be a fresh child of an existing directory")
    return original, output


def create_output(output):
    output = ordinary(output)
    require(output.parent.is_dir() and not output.exists(), "Fresh output directory required")
    output.mkdir(mode=0o700)
    return output


def module_from(name, path, body):
    module = types.ModuleType("calcium_portable_" + name)
    module.__file__ = str(path)
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module


def run_native(plan):
    package = plan["package"]
    root, sources = package["root"], package["sources"]
    adapter = module_from("adapter", root / "adapter.py", sources["adapter.py"])
    adapter.validate_input_path(plan["original"])
    dependencies = {key: module_from(key, root / name, sources[name]) for key, name in MODULES.items()}
    record = dependencies["source_condition"].build_source_condition("smoothed_deconvolved_events")
    return adapter.prepare_session(dependencies, plan["original"], plan["output"],
                                   resource_config=dict(RESOURCES), source_condition=record)


def write_error(output, error):
    body = (json.dumps({"completed": False, "error": type(error).__name__,
                        "detail": str(error)[:1024], "scientific_qualification": False},
                       sort_keys=True, indent=2) + "\n").encode()
    # Retained sizes do not bound attempted writes after a short write. Leave
    # all adapter failures to its own receipt/allowance once any artifact exists.
    # The CLI diagnostic is only for an otherwise untouched fresh directory.
    if any(output.iterdir()):
        return
    fd = os.open(output / "CLI_ERROR.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        remaining = memoryview(body)
        while remaining:
            written = os.write(fd, remaining)
            require(written > 0, "Short error-receipt write")
            remaining = remaining[written:]
        os.fsync(fd)
    finally:
        os.close(fd)


def main(argv=None, *, native_runner=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check", help="Verify source/recipe only; no data or numerical imports")
    prepare = commands.add_parser("prepare", help="Prepare the one fixed source session")
    prepare.add_argument("--original", required=True)
    prepare.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    output = None
    try:
        package = verify_package()
        if args.command == "check":
            print(json.dumps({"source_verified": True, "runtime_probed": False,
                              "original_opened": False, "scientific_qualification": False}, sort_keys=True))
            return 0
        original, output_path = bind_paths(args.original, args.output)
        output = create_output(output_path)
        # Keyword injection exists for orchestration-only controls. The CLI has
        # no alternative processor flag; normal execution always uses run_native.
        receipt = (run_native if native_runner is None else native_runner)(
            {"package": package, "original": original, "output": output})
        require(type(receipt) is dict and receipt.get("completed") is True,
                "Complete authenticated session receipt required")
        print(json.dumps({"completed": True, "paired_trials": 372,
                          "scientific_qualification": False, "fit_or_score": False}, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        if output is not None:
            write_error(output, error)
        print("calcium preparation refused: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
