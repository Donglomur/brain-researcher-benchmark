"""Check enrolled public source bundles without importing benchmark modules."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat

MEMBER_LIMIT = 1024 * 1024
TOTAL_LIMIT = 16 * MEMBER_LIMIT
FILE_LIMIT = 512


class InvalidSource(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise InvalidSource(message)


def relative(value):
    require(type(value) is str and bool(value), "Path must be nonempty text")
    path = PurePosixPath(value)
    require(not path.is_absolute() and str(path) == value and "\\" not in value,
            "Path must be normalized and relative")
    require(all(part not in ("", ".", "..", ".git") for part in value.split("/")),
            "Path traversal is not allowed")
    require(all(ord(char) >= 32 and ord(char) != 127 for char in value), "Control character in path")
    return value


def strict_json(body):
    def unique(items):
        result = {}
        for key, value in items:
            require(key not in result, "Duplicate JSON key: " + key)
            result[key] = value
        return result
    def invalid(value):
        raise InvalidSource("Nonfinite JSON: " + value)
    return json.loads(body.decode("utf-8"), object_pairs_hook=unique, parse_constant=invalid)


def stamp(value):
    return (value.st_dev, value.st_ino, value.st_mode, value.st_nlink,
            value.st_size, value.st_mtime_ns, value.st_ctime_ns)


class Reader:
    """Bounded ordinary source reads, not a hostile-process filesystem sandbox."""
    def __init__(self, root):
        self.root = Path(root).absolute()
        require(self.root.is_dir() and not self.root.is_symlink(), "Ordinary repository root required")
        self.bytes_read = 0
        self.cache = {}

    def read(self, name):
        relative(name)
        path = self.root / name
        for part in (path, *path.parents):
            require(not part.is_symlink(), "Symlink is not a source member: " + name)
        before = path.lstat()
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1,
                "Single-link regular source file required: " + name)
        require(0 <= before.st_size <= MEMBER_LIMIT, "Source member too large: " + name)
        if name in self.cache:
            old_stamp, body = self.cache[name]
            require(stamp(before) == old_stamp, "Cached source changed: " + name)
            return body
        require(self.bytes_read + before.st_size + 1 <= TOTAL_LIMIT, "Source read budget exceeded")
        with path.open("rb") as handle:
            opened = os.fstat(handle.fileno())
            require(stamp(opened) == stamp(before), "Source changed while opening: " + name)
            body = handle.read(before.st_size + 1)
            self.bytes_read += len(body)
            require(stamp(opened) == stamp(os.fstat(handle.fileno())) == stamp(path.lstat()),
                    "Source changed during capture: " + name)
        require(len(body) == before.st_size, "Source extent changed: " + name)
        require(b"\x00" not in body, "Binary source member: " + name)
        body.decode("utf-8")
        self.cache[name] = (stamp(before), body)
        return body

    def checked(self, name, row):
        require(type(row) is dict and {"path", "bytes", "sha256"} <= row.keys(),
                "Incomplete source descriptor")
        require(type(row["bytes"]) is int and 0 <= row["bytes"] <= MEMBER_LIMIT,
                "Invalid source extent")
        digest = row["sha256"]
        require(type(digest) is str and len(digest) == 64 and
                all(char in "0123456789abcdef" for char in digest), "Invalid source digest")
        body = self.read(name)
        require(len(body) == row["bytes"] and hashlib.sha256(body).hexdigest() == digest,
                "Source hash or length mismatch: " + name)
        return body


def physical_members(root, prefix):
    base = root / prefix
    require(base.is_dir() and not base.is_symlink(), "Missing ordinary package: " + prefix)
    result = set()
    for current, directories, files in os.walk(base, followlinks=False):
        for name in directories:
            require(not (Path(current) / name).is_symlink(), "Directory symlink in package")
        for name in files:
            path = Path(current) / name
            require(path.is_file() and not path.is_symlink(), "Special or symlink package member")
            result.add(path.relative_to(root).as_posix())
            require(len(result) <= FILE_LIMIT, "Package member limit exceeded")
    require(len({name.casefold() for name in result}) == len(result), "Case-alias package paths")
    return result


def check_complete_inventory(reader, package, selected):
    """One explicitly enrolled source profile; no task code or native semantics."""
    profile = package["complete_inventory"]
    require(type(profile) is dict and set(profile) == {"profile", "path"} and
            profile == {"profile": "neuroformer_factory_v2", "path": "NATIVE_FACTORY_API.json"},
            "Unknown complete inventory profile")
    require(package["id"] == "PAPER-paper-method-replacement-013" and
            package["root"] == "benchmarks/neuroscience/paper-paper-method-replacement-013" and
            package["inventory"] == "TASK_SOURCE_FREEZE.json" and
            package["inventory_paths"] == "package", "Complete profile enrollment mismatch")
    prefix = package["root"]
    api_path = profile["path"]
    legacy = strict_json(reader.read(prefix + "/" + package["inventory"]))
    require(len(legacy["files"]) == 95, "Complete profile retains the 95-row legacy inventory")
    require({row["path"] for row in package["supplemental_files"]} ==
            {"manifest.json", "NATIVE_FACTORY.md", "NATIVE_FACTORY_API.json",
             "NATIVE_FACTORY_PREDECESSOR.json", "native_factory.py",
             "native_factory_runtime.py", "native_factory_v2.py"},
            "Complete profile requires the manifest and six fixed supplements")
    pins = [row for row in package["supplemental_files"] if row["path"] == api_path]
    require(len(pins) == 1, "Complete API needs independent registry supplement pin")
    api = strict_json(reader.checked(prefix + "/" + api_path, pins[0]))
    require(type(api) is dict and api.get("schema") == "neuroformer_fixed_historical_factory_api_v2",
            "Complete API schema mismatch")
    inventory = api.get("source_inventory")
    require(type(inventory) is dict and
            inventory.get("schema") == "neuroformer_factory_source_inventory_v2",
            "Complete inventory schema mismatch")
    for field, expected in (("count", 102), ("whole_package_count", 103),
                            ("unchanged_predecessors", 97)):
        require(type(inventory.get(field)) is int and inventory[field] == expected,
                "Complete inventory count mismatch: " + field)
    require(inventory.get("self_excluded") == api_path, "Complete inventory self exclusion mismatch")
    rows = inventory.get("files")
    require(type(rows) is list and len(rows) == 102, "Complete inventory needs 102 rows")
    members, total = {prefix + "/" + api_path}, 0
    for row in rows:
        require(type(row) is dict and set(row) == {"path", "bytes", "sha256", "git_mode"},
                "Closed complete inventory row required")
        name = prefix + "/" + relative(row["path"])
        require(name not in members, "Duplicate/self complete inventory member")
        require(row["git_mode"] == "100644", "Complete inventory mode must be 100644")
        require(name in selected, "Complete inventory member is not enrolled")
        body = reader.checked(name, row)
        require(stat.S_IMODE(reader.cache[name][0][2]) == 0o644,
                "Complete source permission mode must be 0644")
        total += len(body)
        members.add(name)
    require(stat.S_IMODE(reader.cache[prefix + "/" + api_path][0][2]) == 0o644,
            "Complete API permission mode must be 0644")
    require(type(inventory.get("total_bytes")) is int and inventory["total_bytes"] == total,
            "Complete inventory byte total mismatch")
    require(members == selected, "Complete inventory physical coverage mismatch")
    for key, expected in (("entry", "native_factory_v2.run_historical"),
                          ("historical_unselected_entry", "native_factory.run_historical")):
        require(api.get(key) == expected, "Complete API entry mismatch: " + key)
        module, function = expected.split(".")
        name = prefix + "/" + module + ".py"
        require(name in members, "Complete API entry source missing")
        tree = ast.parse(reader.read(name).decode("utf-8"), filename=name)
        require(sum(isinstance(node, ast.FunctionDef) and node.name == function
                    for node in tree.body) == 1, "Complete API entry function missing/ambiguous")
    for field in ("generic_registration_changed", "native_execution_qualified",
                  "scientific_execution_authorized", "new_callbacks_or_runtime_injection"):
        require(api.get(field) is False, "Complete API inactive flag mismatch: " + field)
    require(api.get("legacy_registered_dispatch_unchanged") is True,
            "Complete API legacy dispatch declaration changed")
    require(type(api.get("unchanged_predecessor_files")) is int and
            api["unchanged_predecessor_files"] == 97, "Complete API predecessor count mismatch")
    scope = api.get("retained_scope")
    expected_scope = {"slots": 46, "cells": 85, "wider_families": 7,
                      "existing_apis": 6, "existing_unavailable_dispositions": 20, "gates": 29}
    require(type(scope) is dict and set(scope) == set(expected_scope) and
            all(type(scope[key]) is int and scope[key] == value for key, value in expected_scope.items()),
            "Complete API retained scope mismatch")


def check(root, registry="benchmarks/source_integrity.json"):
    reader = Reader(root)
    config = strict_json(reader.read(registry))
    require(type(config) is dict and set(config) == {"schema_version", "scope", "packages"},
            "Closed registry schema required")
    require(type(config["schema_version"]) is int and config["schema_version"] == 1,
            "Unsupported registry version")
    packages = config["packages"]
    require(type(packages) is list and 0 < len(packages) <= 64, "Nonempty bounded package roster required")
    ids, roots, reports = set(), set(), []
    for package in packages:
        fields = {"id", "root", "inventory", "inventory_paths", "supplemental_files"}
        require(type(package) is dict and set(package) in (fields, fields | {"complete_inventory"}),
                "Closed package schema")
        task_id = package["id"]
        require(type(task_id) is str and task_id and task_id not in ids, "Duplicate or invalid task ID")
        prefix = relative(package["root"])
        require(prefix.startswith("benchmarks/neuroscience/") and prefix.count("/") == 2,
                "Expected direct neuroscience package")
        require(prefix.casefold() not in roots, "Duplicate package root")
        ids.add(task_id)
        roots.add(prefix.casefold())
        inventory_name = prefix + "/" + relative(package["inventory"])
        require(package["inventory_paths"] in ("repository", "package"), "Unknown inventory path style")
        inventory = strict_json(reader.read(inventory_name))
        require(type(inventory) is dict, "Inventory object required")
        rows = inventory.get("files")
        require(type(rows) is list and 0 < len(rows) <= FILE_LIMIT, "Bounded inventory files required")
        supplemental = package["supplemental_files"]
        require(type(supplemental) is list and len(supplemental) <= FILE_LIMIT, "Bounded supplement required")
        selected = {inventory_name}
        for row, style in [(row, package["inventory_paths"]) for row in rows] + [
                (row, "package") for row in supplemental]:
            require(type(row) is dict and "path" in row, "Source row required")
            name = relative(row["path"])
            if style == "package":
                name = prefix + "/" + name
            require(name.startswith(prefix + "/"), "Inventory member escapes its package")
            require(name not in selected, "Duplicate/self inventory member")
            if "runtime_path" in row:
                require(name == prefix + "/" + relative(row["runtime_path"]), "Runtime path disagreement")
            selected.add(name)
            reader.checked(name, row)
        require(len(selected) <= FILE_LIMIT and
                len({name.casefold() for name in selected}) == len(selected), "Ambiguous source membership")
        require(physical_members(reader.root, prefix) == selected, "Missing or extra package members: " + task_id)
        manifest_name = prefix + "/manifest.json"
        require(manifest_name in selected, "Package manifest is not covered")
        manifest = strict_json(reader.read(manifest_name))
        require(manifest.get("id") == task_id, "Manifest task ID mismatch")
        canonical = manifest.get("canonical_specification")
        require(type(canonical) is dict and "path" in canonical, "Canonical binding required")
        canonical_name = relative(canonical["path"])
        if not canonical_name.startswith("benchmarks/"):
            canonical_name = prefix + "/" + canonical_name
            require(canonical_name in selected, "Local canonical is not covered")
        else:
            require(canonical_name.startswith("benchmarks/manifests/") and
                    canonical_name.count("/") == 3, "Unexpected external canonical location")
        canonical_body = reader.checked(canonical_name, canonical)
        require(strict_json(canonical_body).get("id") == task_id, "Canonical task ID mismatch")
        if "canonical" in inventory:
            require(inventory["canonical"] == canonical, "Inventory canonical binding mismatch")
        if "source_freeze" in manifest:
            freeze = manifest["source_freeze"]
            require(type(freeze) is dict and "path" in freeze, "Freeze descriptor required")
            name = relative(freeze["path"])
            if not name.startswith("benchmarks/"):
                name = prefix + "/" + name
            require(name == inventory_name, "Manifest names a different inventory")
            reader.checked(name, freeze)
        if "complete_inventory" in package:
            check_complete_inventory(reader, package, selected)
        python_count = 0
        for name in sorted(selected):
            if name.endswith(".py"):
                ast.parse(reader.read(name).decode("utf-8"), filename=name)
                python_count += 1
        reports.append({"id": task_id, "source_files": len(selected), "python_files": python_count})
    return {"status": "source_integrity_passed", "packages": reports,
            "bytes_read": reader.bytes_read, "benchmark_execution": False,
            "scientific_qualification_assessed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).absolute().parents[1])
    args = parser.parse_args()
    try:
        result = check(args.root)
    except (InvalidSource, OSError, UnicodeError, ValueError, TypeError, KeyError, RecursionError, SyntaxError) as error:
        parser.exit(1, "Source integrity failed: " + str(error) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

