#!/usr/bin/env python3
"""Assemble explicit local benchmark files; never run task code or acquire data."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys

ROOT = Path(__file__).resolve().parents[1]
DELIVERY = "authoring/delivery-20261105"
REGISTRY = "docs/neuroscience-benchmarks/build/registry.json"
COMPONENTS = ("task_contract", "submission_schema", "scorer", "data", "dependencies")
MANIFEST = "DELIVERY_MANIFEST.json"
DEFAULT_CAP = 64 * 1024 * 1024
CHUNK = 1024 * 1024


class DeliveryError(ValueError):
    pass


def need(value, message):
    if not value:
        raise DeliveryError(message)


def encode(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode()


def decode(body):
    def pairs(items):
        value = {}
        for key, item in items:
            need(key not in value, "Duplicate JSON key: " + key)
            value[key] = item
        return value
    def reject(value):
        raise DeliveryError("Nonfinite JSON number: " + value)
    return json.loads(body, object_pairs_hook=pairs, parse_constant=reject)


def relative(name):
    need(type(name) is str and name and "\\" not in name and "\0" not in name, "Invalid relative path")
    path = PurePosixPath(name)
    need(path.parts and not path.is_absolute() and ".." not in path.parts and str(path) == name,
         "Unsafe relative path: " + name)
    return path


def unlinked(root, name):
    path = Path(root)
    for part in relative(name).parts:
        path = path / part
        need(not path.is_symlink(), "Symlink path is not allowed: " + name)
    return path


def hash_shape(value):
    return type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def read_metadata(root, name, cap=2 * CHUNK):
    path = unlinked(root, name)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= cap,
             "Expected bounded ordinary JSON: " + name)
        with os.fdopen(fd, "rb", closefd=False) as stream:
            body = stream.read(cap + 1)
        after = os.fstat(fd)
        need(len(body) == before.st_size and all(getattr(before, k) == getattr(after, k) == getattr(path.lstat(), k)
             for k in ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")), "Metadata changed: " + name)
    finally:
        os.close(fd)
    return decode(body), {"path": name, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def validate_manifest(value, known_ids):
    need(type(value) is dict and value.get("schema") == "neurobench_delivery_v1", "Wrong delivery manifest schema")
    ids = value.get("task_ids")
    need(type(ids) is list and ids and all(type(i) is str for i in ids)
         and len(ids) == len(set(ids)) and not set(ids) - set(known_ids), "Unknown or duplicate canonical task IDs")
    files = value.get("files")
    need(type(files) is list and len(files) <= 4096, "Expected at most4096 explicit file records")
    targets, folded = {}, set()
    for item in files:
        need(type(item) is dict and {"source", "target", "visibility", "role", "bytes", "sha256"} <= set(item),
             "File record lacks exact source/target/visibility/role/bytes/sha256")
        source, target = relative(item["source"]), relative(item["target"])
        need(item["visibility"] in ("public", "private") and target.parts[0] == item["visibility"]
             and len(target.parts) > 1, "Target must be under its explicit public/private directory")
        need(item["target"].casefold() not in folded, "Duplicate or case-colliding export target: " + item["target"])
        need(type(item["role"]) is str and item["role"] and type(item["bytes"]) is int and item["bytes"] >= 0
             and hash_shape(item["sha256"]), "Invalid file identity or role: " + item["target"])
        need(type(item.get("executable", False)) is bool, "Executable flag must be boolean")
        need(source.parts[0] not in (".git",) and source.name not in ("implementation_status.json", "QUEUE.json"),
             "Canonical bookkeeping/hidden repository state is not a delivery input")
        if item["visibility"] == "public":
            need(not {p.lower() for p in source.parts} & {"private", "operator", "secrets"}
                 and source.name.lower() not in ("operator_assets.json", "private_assets.json"),
                 "Private/operator source cannot be exported as public: " + item["source"])
        targets[item["target"]] = item
        folded.add(item["target"].casefold())
    for target in targets:
        need(not any(str(parent).casefold() in folded for parent in PurePosixPath(target).parents),
             "File/directory target collision: " + target)
    components = value.get("components")
    need(type(components) is dict and set(components) == set(COMPONENTS), "Expected the five explicit construction components")
    for name, component in components.items():
        need(type(component) is dict and component.get("status") in ("complete", "partial", "missing"),
             "Invalid component status: " + name)
        names, blockers = component.get("targets"), component.get("blockers")
        need(type(names) is list and all(type(n) is str for n in names) and len(names) == len(set(names))
             and not set(names) - set(targets), "Component targets must name allowlisted files: " + name)
        need(type(blockers) is list and all(type(b) is str and b for b in blockers), "Component blockers must be explicit strings")
        need(component["status"] != "complete" or (names and not blockers), "Complete component needs files and no blockers: " + name)
        need(component["status"] == "complete" or blockers, "Incomplete component must name its blocker: " + name)
    return targets


def stub_signals(body, target, role):
    if not target.endswith(".py") or role in ("test", "tests", "generated_tests"):
        return []
    try:
        tree = ast.parse(body)
    except (SyntaxError, ValueError, UnicodeError) as error:
        return ["Python source does not parse: " + str(error)]
    def implementation(node):
        code = [n for n in node.body if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant)
                                            and isinstance(n.value.value, str))]
        return bool(code) and not all(isinstance(n, ast.Pass) or (isinstance(n, ast.Expr)
                                      and isinstance(n.value, ast.Constant) and n.value.value is Ellipsis) for n in code)

    # A stateless class may legitimately initialize nothing and implement its
    # behavior in other methods (including the original abcTau model adapters).
    # Do not rewrite pinned upstream code or disguise it as a test to pass this
    # heuristic. Empty scientific methods and constructor-only shells still fail.
    stateless_constructors = set()
    for cls in ast.walk(tree):
        if isinstance(cls, ast.ClassDef):
            methods = [n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
            if any(n.name != "__init__" and implementation(n) for n in methods):
                stateless_constructors.update(id(n) for n in methods if n.name == "__init__")
    signals = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Raise):
            exc = node.exc.func if isinstance(node.exc, ast.Call) else node.exc
            if isinstance(exc, ast.Name) and exc.id == "NotImplementedError":
                signals.append("NotImplementedError at line " + str(node.lineno))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not implementation(node) and id(node) not in stateless_constructors:
                signals.append("Empty function " + node.name + " at line " + str(node.lineno))
    return signals


def verify_file(root, item, destination=None):
    """Streaming identity check/opaque copy. No payload parsing or code execution."""
    path = unlinked(root, item["source"])
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    output = None
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == item["bytes"],
             "Expected ordinary file with exact declared size")
        if destination is not None:
            destination.parent.mkdir(parents=True, exist_ok=True)
            output = destination.open("xb")
        digest, total, source = hashlib.sha256(), 0, []
        inspect_python = item["target"].endswith(".py") and item["bytes"] <= 2 * CHUNK
        with os.fdopen(fd, "rb", closefd=False) as stream:
            while True:
                chunk = stream.read(min(CHUNK, item["bytes"] - total + 1))
                if not chunk:
                    break
                total += len(chunk)
                need(total <= item["bytes"], "Source grew beyond its pin")
                digest.update(chunk)
                if inspect_python:
                    source.append(chunk)
                if output is not None:
                    need(output.write(chunk) == len(chunk), "Incomplete export write")
        after = os.fstat(fd)
        need(total == item["bytes"] and digest.hexdigest() == item["sha256"], "Source digest differs from exact pin")
        need(all(getattr(before, k) == getattr(after, k) == getattr(path.lstat(), k)
                 for k in ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")), "Source changed during copy/check")
        if output is not None:
            output.flush()
            os.fsync(output.fileno())
            os.fchmod(output.fileno(), 0o555 if item.get("executable", False) else 0o444)
        signals = stub_signals(b"".join(source), item["target"], item["role"]) if inspect_python else []
        if item["target"].endswith(".py") and not inspect_python:
            signals = ["Python source exceeds bounded static inspection size"]
        return signals
    finally:
        if output is not None:
            output.close()
        os.close(fd)


def inspect(root, value, *, visibility="all", max_bytes=DEFAULT_CAP):
    registry, _ = read_metadata(root, REGISTRY, 8 * CHUNK)
    ids = [row["id"] for row in registry["tasks"]]
    need(len(ids) == len(set(ids)), "Duplicate registry ID")
    validate_manifest(value, ids)
    need(visibility in ("all", "public", "private") and type(max_bytes) is int and max_bytes > 0, "Invalid export scope/cap")
    selected = [f for f in value["files"] if visibility == "all" or f["visibility"] == visibility]
    total = sum(f["bytes"] for f in selected)
    need(total <= max_bytes, "Selected declared bytes " + str(total) + " exceed explicit cap " + str(max_bytes))
    records = []
    for item in selected:
        record = {k: item[k] for k in ("target", "visibility", "role", "bytes", "sha256")}
        try:
            signals = verify_file(root, item)
            record.update(status="verified", stub_signals=signals)
        except FileNotFoundError:
            record.update(status="missing_file", stub_signals=[])
        except (OSError, DeliveryError) as error:
            record.update(status="invalid_file", stub_signals=[], detail=str(error))
        if visibility != "public":
            record["source"] = item["source"]
        else:
            record.pop("detail", None)
        records.append(record)
    issues = [{"target": r["target"], "status": r["status"], "stub_signals": r["stub_signals"]}
              for r in records if r["status"] != "verified" or r["stub_signals"]]
    complete = all(c["status"] == "complete" for c in value["components"].values())
    return {"schema": "neurobench_delivery_check_v1", "task_ids": value["task_ids"], "visibility": visibility,
        "package_buildable": visibility == "all" and complete and not issues, "package_built": False,
        "components_declared_complete": complete, "selected_bytes": total, "byte_cap": max_bytes,
        "files": records, "file_issues": issues,
        "component_blockers": {k: v["blockers"] for k, v in value["components"].items() if v["blockers"]}
            if visibility != "public" else {},
        "historical_qualification_revalidated": False, "runtime_verified": False,
        "submission_ready": False, "new_scientific_executions": 0}


def assemble(root, value, source_pin, output, *, visibility="all", max_bytes=DEFAULT_CAP, allow_partial=False):
    result = inspect(root, value, visibility=visibility, max_bytes=max_bytes)
    need(result["package_buildable"] or allow_partial, "Incomplete/view-only export requires --allow-partial; inspect exact blockers first")
    name = str(relative(output))
    need(name.startswith(DELIVERY + "/"), "Exports must stay in the task-owned delivery directory")
    folder = unlinked(root, name)
    need(not folder.exists(), "Export directory must be fresh")
    by_target = {f["target"]: f for f in value["files"]}
    available = [r for r in result["files"] if r["status"] == "verified"]
    folder.mkdir(parents=True)
    exported = []
    # Failure keeps a partial directory WITHOUT a success manifest; no rollback or synthesis.
    for record in available:
        item = by_target[record["target"]]
        verify_file(root, item, unlinked(folder, item["target"]))
        exported.append({k: item[k] for k in ("target", "visibility", "role", "bytes", "sha256")})
    if visibility == "public":
        components = {k: {"status": "included" if any(t.startswith("public/") for t in v["targets"]) else "not_in_public_export",
                           "targets": [t for t in v["targets"] if t.startswith("public/")]}
                      for k, v in value["components"].items()}
    else:
        components = value["components"]
    metadata = {"schema": "neurobench_delivery_export_v1", "task_ids": value["task_ids"],
        "visibility": visibility, "package_built": result["package_buildable"], "files": exported,
        "components": components, "file_issues": result["file_issues"],
        "historical_qualification_revalidated": False, "runtime_verified": False,
        "submission_ready": False, "new_scientific_executions": 0}
    if visibility != "public":
        metadata.update(source_manifest=source_pin, historical_qualification=value.get("historical_qualification", {}))
        metadata.update({k: value[k] for k in ("interfaces", "asset_bindings", "scope", "limitations", "distribution", "source_only") if k in value})
    with (folder / MANIFEST).open("xb") as stream:
        stream.write(encode(metadata))
    os.chmod(folder / MANIFEST, 0o444)
    return {"export": name, **metadata}


def check_export(root, folder, max_bytes=DEFAULT_CAP):
    path = unlinked(root, str(relative(folder)))
    value, pin = read_metadata(path, MANIFEST)
    need(type(value) is dict and value.get("schema") == "neurobench_delivery_export_v1", "Wrong export schema")
    need(value.get("visibility") in ("all", "public", "private"), "Invalid export visibility")
    files = value.get("files")
    need(type(files) is list and len(files) <= 4096 and type(max_bytes) is int and max_bytes > 0, "Invalid export files/cap")
    registry, _ = read_metadata(root, REGISTRY, 8 * CHUNK)
    known_ids = [row["id"] for row in registry["tasks"]]
    ids = value.get("task_ids")
    need(type(ids) is list and ids and all(type(i) is str for i in ids)
         and len(ids) == len(set(ids)) and not set(ids) - set(known_ids), "Unknown or duplicate exported task IDs")
    if value["visibility"] == "all":
        validate_manifest({"schema": "neurobench_delivery_v1", "task_ids": ids,
            "files": [{**item, "source": item["target"]} for item in files],
            "components": value.get("components")}, known_ids)
    total, names, issues = 0, set(), []
    for item in files:
        target = relative(item["target"])
        need(target.parts[0] in ("public", "private") and len(target.parts) > 1
             and item["visibility"] == target.parts[0] and item["target"].casefold() not in names,
             "Invalid or colliding exported target")
        need(value["visibility"] == "all" or item["visibility"] == value["visibility"], "File violates export visibility")
        need(type(item["bytes"]) is int and item["bytes"] >= 0 and hash_shape(item["sha256"]), "Invalid exported file pin")
        names.add(item["target"].casefold())
        total += item["bytes"]
        need(total <= max_bytes, "Export exceeds explicit byte cap")
    # Reject extra files before treating an export as the declared allowlist.
    expected = {item["target"] for item in files} | {MANIFEST}
    expected_dirs = {str(p) for target in expected for p in PurePosixPath(target).parents if str(p) != "."}
    for base, directories, filenames in os.walk(path, followlinks=False):
        for name in directories + filenames:
            child = Path(base) / name
            need(not child.is_symlink(), "Symlink in export")
        for name in directories:
            need((Path(base) / name).relative_to(path).as_posix() in expected_dirs, "Unlisted export directory")
        for name in filenames:
            need((Path(base) / name).relative_to(path).as_posix() in expected, "Unlisted export file")
    for item in files:
        try:
            signals = verify_file(path, {**item, "source": item["target"]})
            if signals:
                issues.append({"target": item["target"], "status": "stub_signal", "details": signals})
        except (OSError, DeliveryError) as error:
            issues.append({"target": item["target"], "status": "missing_or_invalid", "detail": str(error)})
    file_targets = {item["target"] for item in files}
    component_complete = value.get("visibility") == "all" and all(
        isinstance(value.get("components", {}).get(k), dict)
        and value["components"][k].get("status") == "complete"
        and value["components"][k].get("targets")
        and not value["components"][k].get("blockers")
        and all(t in file_targets for t in value["components"][k]["targets"]) for k in COMPONENTS)
    built = bool(component_complete and not issues and not value.get("file_issues"))
    return {"schema": "neurobench_delivery_export_check_v1", "manifest": pin,
        "task_ids": value["task_ids"], "visibility": value["visibility"], "files_checked": len(files),
        "bytes_checked": total, "file_issues": issues, "package_built": built,
        # Keep the combined issue list and conservative build gate unchanged.
        # Static source findings do not mean pinned bytes failed verification.
        "file_integrity_issues": [issue for issue in issues if issue["status"] != "stub_signal"],
        "source_static_signals": [issue for issue in issues if issue["status"] == "stub_signal"],
        "package_claim_consistent": value.get("package_built") is built,
        "runtime_verified": False, "historical_qualification_revalidated": False, "submission_ready": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "assemble", "check-export"))
    parser.add_argument("--manifest")
    parser.add_argument("--output")
    parser.add_argument("--export")
    parser.add_argument("--visibility", choices=("all", "public", "private"), default="all")
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_CAP)
    parser.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args(argv)
    if args.action == "check-export":
        need(args.export and not args.manifest and not args.output, "check-export requires only --export")
        result = check_export(ROOT, args.export, args.max_bytes)
    else:
        need(args.manifest and not args.export, "Select one explicit delivery manifest")
        value, pin = read_metadata(ROOT, args.manifest)
        if args.action == "check":
            need(not args.output, "check never writes an export")
            result = inspect(ROOT, value, visibility=args.visibility, max_bytes=args.max_bytes)
            result["source_manifest"] = pin
        else:
            need(args.output, "assemble requires a fresh --output")
            result = assemble(ROOT, value, pin, args.output, visibility=args.visibility,
                              max_bytes=args.max_bytes, allow_partial=args.allow_partial)
    sys.stdout.buffer.write(encode(result))
    success = (result.get("package_built") or result.get("package_buildable")
               or (args.allow_partial and not result.get("file_issues")))
    return 0 if success and result.get("package_claim_consistent", True) else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({"error": str(error), "package_built": False}, sort_keys=True), file=sys.stderr)
        raise SystemExit(2)
