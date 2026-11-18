#!/usr/bin/env python3
"""Build an unqualified NEURAL-079 source staging package; never import its code."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tempfile


PUBLIC_PREFIX = "benchmarks/neuroscience/neural-079/full-natural-video-encoding-v1/"
MARKER = "@SOURCE_ROOT@/"
MAX_FILE = 131072
MAX_READ = 2 * 1024**2
MAX_OUTPUT = 2 * 1024**2
AUTHORITY = {
    "PUBLIC_SOURCE_MANIFEST.json": (74277, "2d08529611f6dbf482da9fa818507b10d6ad52657047bde19957b61d4f80eea5"),
    "INSTALLED_SOURCE_MANIFEST.json": (27190, "54d2336ae970df347c6b7f92a1465692de844d5b5d2b356827e96fba9aad1811"),
}
EFFECTIVE_TEMPLATE = "templates/EFFECTIVE_RUNTIME_MANIFEST.template.json"
CLOSURE_TEMPLATE = "templates/RUNTIME_SOURCE_CLOSURE.template.json"
JOB_TEMPLATE = "templates/visual_shell.template.sh"


class ConstructionError(ValueError):
    """Source staging failed closed; no execution authority is implied."""


def require(condition, message):
    if not condition:
        raise ConstructionError(message)


def pin(body):
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def compact(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def strict_json(body):
    def pairs(rows):
        result = {}
        for key, value in rows:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    def nonfinite(_):
        raise ConstructionError("nonfinite JSON value")
    return json.loads(body, object_pairs_hook=pairs, parse_constant=nonfinite)


def relative(value):
    require(isinstance(value, str) and bool(value), "empty or non-string source path")
    p = PurePosixPath(value)
    require(not p.is_absolute() and str(p) == value, "source path is not canonical relative POSIX")
    require(all(x not in ("", ".", "..") for x in p.parts), "source path traversal")
    require("\\" not in value and "\x00" not in value, "source path separator")
    return value


def root_path(value, *, exists):
    p = Path(value)
    require(p.is_absolute(), "an absolute path is required")
    require(str(p) == str(value) and ".." not in p.parts, "noncanonical absolute path")
    # Resolve ancestors, including an output's existing parent, without following
    # a caller-supplied symlink and then pretending the original path was safe.
    require(p.resolve(strict=exists) == p, "root or ancestor is a symlink")
    if exists:
        require(p.is_dir(), "source root is not a directory")
    return p


def _pin_shape(value):
    require(isinstance(value, dict) and set(value) == {"bytes", "sha256"}, "invalid pin fields")
    require(type(value["bytes"]) is int and 0 <= value["bytes"] <= MAX_FILE, "invalid source extent")
    require(isinstance(value["sha256"], str) and re.fullmatch(r"[0-9a-f]{64}", value["sha256"]), "invalid SHA256")


def _read_pinned(root, rel, expected, budget):
    relative(rel)
    _pin_shape(expected)
    path = root / rel
    cursor = root
    for part in PurePosixPath(rel).parts[:-1]:
        cursor /= part
        require(stat.S_ISDIR(cursor.lstat().st_mode), "nonordinary source directory")
    budget[0] += expected["bytes"]
    require(budget[0] <= MAX_READ, "source read bound exceeded")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_size == expected["bytes"], "source type or extent mismatch")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            body = stream.read(expected["bytes"] + 1)
        require(pin(body) == expected, "source SHA256 mismatch")
        return body
    finally:
        os.close(fd)


def _unique_paths(paths):
    seen = set()
    for rel in paths:
        relative(rel)
        key = rel.casefold()
        require(key not in seen, "duplicate/case-colliding source path")
        require(not any(key.startswith(p + "/") or p.startswith(key + "/") for p in seen), "source file/directory collision")
        seen.add(key)


def inspect_archive(archive_root):
    """Authenticate exactly 101 projected members and historical metadata.

    Bodies are inert bytes. Nothing from this source archive is imported,
    executed, installed or interpreted as a recording/model artifact.
    """
    archive = root_path(archive_root, exists=True)
    budget = [0]
    authority = {}
    for rel, (size, sha) in AUTHORITY.items():
        authority[rel] = _read_pinned(archive, rel, {"bytes": size, "sha256": sha}, budget)
    manifest = strict_json(authority["PUBLIC_SOURCE_MANIFEST.json"])
    require(manifest["schema"] == "neural079_public_source_projection_manifest_v1", "wrong projection schema")
    require(manifest["canonical_task"] == "NEURAL-079" and manifest["execution_qualified"] is False, "wrong task/qualification")
    rows = manifest["mapping"]
    require(isinstance(rows, list) and len(rows) == 101, "projection does not contain 101 members")
    _unique_paths([r["original_path"] for r in rows])
    _unique_paths([r["public_path"] for r in rows])
    bodies, originals, transformed = {}, {}, {}
    for row in rows:
        require(set(row) == {"original", "original_path", "public", "public_path", "transformed"}, "unexpected projection fields")
        original = relative(row["original_path"])
        require(row["public_path"].startswith(PUBLIC_PREFIX), "unexpected public archive prefix")
        public = relative(row["public_path"][len(PUBLIC_PREFIX):])
        _pin_shape(row["original"])
        require(type(row["transformed"]) is bool, "invalid transformation flag")
        bodies[original] = _read_pinned(archive, public, row["public"], budget)
        originals[original] = row["original"]
        if row["transformed"]:
            transformed[public] = original
        else:
            require(public == "source/" + original, "unchanged source was relocated within archive")
            require(row["original"] == row["public"], "unchanged original/public pins differ")
    require(set(transformed) == {EFFECTIVE_TEMPLATE, CLOSURE_TEMPLATE, JOB_TEMPLATE}, "unexpected transformed members")
    require(sum(row["original"]["bytes"] for row in rows) == manifest["ordinary_installed_member_bytes"] == 1375100, "historical member extent mismatch")
    require(pin(authority["INSTALLED_SOURCE_MANIFEST.json"]) == {k: manifest["installed_manifest_original"][k] for k in ("bytes", "sha256")}, "historical manifest identity mismatch")
    return {"archive_root": str(archive), "bodies": bodies, "original_pins": originals,
            "transformed": transformed, "authority": authority, "read_bytes": budget[0]}


def render_maps(snapshot, destination_root):
    """Render a new source-only package in memory for a fresh destination.

    This is not a complete consumer/registry/qualification rebinding operation.
    The staging receipt explicitly leaves those deployment gates unresolved.
    """
    destination = root_path(destination_root, exists=False)
    archive = Path(snapshot["archive_root"])
    require(destination != archive and archive not in destination.parents, "destination must be outside the original archive")
    source_root = destination / "source"
    bodies = dict(snapshot["bodies"])
    transformed = snapshot["transformed"]
    effective_rel = transformed[EFFECTIVE_TEMPLATE]
    closure_rel = transformed[CLOSURE_TEMPLATE]
    job_rel = transformed[JOB_TEMPLATE]
    effective = strict_json(bodies[effective_rel])
    closure = strict_json(bodies[closure_rel])
    require(set(effective) == {"schema", "modules"} and effective["schema"] == "n079_exact_runtime_modules_v1", "invalid effective map")
    require(isinstance(effective["modules"], dict) and len(effective["modules"]) == 55, "expected 55 modules")
    require(isinstance(closure, list) and len(closure) == 72, "expected 72 closure rows")
    module_paths = []
    def decode_row(row):
        require(isinstance(row, dict) and set(row) == {"path", "pin"}, "invalid map row")
        require(isinstance(row["path"], str) and row["path"].startswith(MARKER), "missing leading source-root marker")
        rel = relative(row["path"][len(MARKER):])
        require(rel in bodies, "map names an unpublished member")
        require(row["pin"] == snapshot["original_pins"][rel], "template/original identity mismatch")
        return rel
    for name, row in effective["modules"].items():
        require(isinstance(name, str) and re.fullmatch(r"[A-Za-z_]\w*", name), "invalid module alias")
        rel = decode_row(row)
        require(rel not in transformed.values() and rel.endswith(".py"), "runtime module is not unchanged Python source")
        require(pin(bodies[rel]) == row["pin"], "runtime module source changed")
        module_paths.append(rel)
        row["path"] = str(source_root / rel)
    _unique_paths(module_paths)
    bodies[effective_rel] = compact(effective)
    closure_paths = []
    for row in closure:
        rel = decode_row(row)
        require(rel != closure_rel, "closure self-reference")
        closure_paths.append(rel)
        # The effective map has new path-dependent bytes; the job is the
        # explicitly public template (588B), never its historical 537B body.
        row["path"] = str(source_root / rel)
        row["pin"] = pin(bodies[rel])
    _unique_paths(closure_paths)
    require(set(module_paths).issubset(closure_paths), "closure omits runtime modules")
    require(effective_rel in closure_paths and job_rel in closure_paths, "closure omits rendered dependencies")
    bodies[closure_rel] = compact(closure)
    output = {"source/" + rel: body for rel, body in bodies.items()}
    for name, body in snapshot["authority"].items():
        output["provenance/" + name] = body
    receipt = {
        "schema": "neural079_source_staging_v1", "canonical_task": "NEURAL-079",
        "archive_root": snapshot["archive_root"], "destination_root": str(destination),
        "source_read_bytes": snapshot["read_bytes"], "source_members": 101,
        "unchanged_algorithm_members": 98, "runtime_modules": 55, "closure_members": 72,
        "execution_qualified": False, "scientifically_qualified": False,
        "readiness_promoted": False, "all_consumer_bindings_regenerated": False,
        "job_policy": "Unexecuted public template retained. N079_SITE_HOME and site/environment/resource policy remain operator-selected prerequisites; historical job-body parity is not claimed.",
        "remaining_gates": ["all consuming module/source/qualification/registry pins", "central source selection and entrypoint binding", "ten deferred cross-task exposure dependencies", "Linux isolation, observer, authority and provider roles", "external packages and numerical/reference qualification", "complete authentic inputs and protected evaluation"],
        "members": [{"path": rel, "pin": pin(output[rel])} for rel in sorted(output)],
        "rendered_maps": {"effective": {"path": "source/" + effective_rel, "pin": pin(bodies[effective_rel])}, "closure": {"path": "source/" + closure_rel, "pin": pin(bodies[closure_rel])}},
    }
    output["SOURCE_PACKAGE.json"] = compact(receipt)
    _unique_paths(output)
    require(sum(map(len, output.values())) <= MAX_OUTPUT, "source staging output bound exceeded")
    return output


def _sync_receipt(stream, body):
    stream.write(body)
    stream.flush()
    os.fsync(stream.fileno())


def _publish_marker(destination, body):
    """Commit only complete, fsynced receipt bytes without replacing a name."""
    fd, temporary = tempfile.mkstemp(prefix=".SOURCE_PACKAGE.", suffix=".pending", dir=destination)
    try:
        with os.fdopen(fd, "wb") as stream:
            _sync_receipt(stream, body)
        # link() is atomic and fails if the final name already exists. Unlike
        # replace()/rename(), it cannot overwrite an existing receipt.
        os.link(temporary, destination / "SOURCE_PACKAGE.json", follow_symlinks=False)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass  # Preserve the original failure; an owned .pending may remain.
        raise
    # The link is the commit point. Cleanup failure does not undo publication or
    # become an inaccurate "incomplete" outcome. Namespace power-loss durability
    # is not claimed; the receipt's file contents were fsynced before the link.
    warning = None
    try:
        os.unlink(temporary)
    except OSError as exc:
        warning = {"temporary_path": temporary, "error": type(exc).__name__ + ": " + str(exc)}
    return {"completion_marker_published": True, "temporary_cleanup_warning": warning}


def publish(output, destination_root):
    """Create only a fresh staging tree; atomically publish its receipt last.

    Pre-commit failures leave no new final receipt. Once the complete receipt is
    linked, publication is complete even if temporary cleanup is interrupted or
    reported as a warning. Ordinary trusted operator filesystem use is assumed;
    this is not an adversarial OS sandbox or a power-loss durability guarantee.
    """
    destination = root_path(destination_root, exists=False)
    require(not destination.exists(), "destination already exists")
    require(destination.parent.is_dir(), "destination parent must already exist")
    _unique_paths(output)
    require("SOURCE_PACKAGE.json" in output, "missing staging completion receipt")
    require(sum(map(len, output.values())) <= MAX_OUTPUT, "source staging output bound exceeded")
    receipt = strict_json(output["SOURCE_PACKAGE.json"])
    require(receipt.get("schema") == "neural079_source_staging_v1", "wrong staging receipt schema")
    require(receipt.get("destination_root") == str(destination), "rendered destination does not match publication destination")
    for flag in ("execution_qualified", "scientifically_qualified", "readiness_promoted"):
        require(receipt.get(flag) is False, "staging receipt claims qualification")
    expected_members = [{"path": rel, "pin": pin(output[rel])} for rel in sorted(set(output) - {"SOURCE_PACKAGE.json"})]
    require(receipt.get("members") == expected_members, "staging receipt does not describe actual output bytes")
    destination.mkdir(mode=0o700)
    order = sorted(set(output) - {"SOURCE_PACKAGE.json"})
    for rel in order:
        path = destination / rel
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(output[rel])
            stream.flush()
            os.fsync(stream.fileno())
    return _publish_marker(destination, output["SOURCE_PACKAGE.json"])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True)
    parser.add_argument("--destination", required=True)
    parser.add_argument("--materialize", action="store_true", help="write an unqualified staging tree; otherwise only authenticate and render in memory")
    args = parser.parse_args(argv)
    snapshot = inspect_archive(args.archive)
    output = render_maps(snapshot, args.destination)
    publication = publish(output, args.destination) if args.materialize else None
    print(json.dumps({"source_members": 101, "runtime_modules": 55, "closure_members": 72,
                      "source_read_bytes": snapshot["read_bytes"], "output_bytes": sum(map(len, output.values())),
                      "materialized": args.materialize, "publication": publication,
                      "receipt_pin": pin(output["SOURCE_PACKAGE.json"]),
                      "execution_qualified": False, "scientifically_qualified": False}, sort_keys=True))


if __name__ == "__main__":
    main()
