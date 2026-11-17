"""Check current task-owned source and explicit predecessor evidence without execution."""
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
REGISTRY_LIMIT = 4 * MEMBER_LIMIT
PAPER_REVISION = "paper-improvement/v1"
PAPER_OBJECTIVE = "surpass_source_paper_same_task"
PAPER_HISTORY = "historical/task.pre-improvement.v1.json"
PAPER_DISPOSITIONS = {"improvement_ready", "design_ready", "source_unresolved", "ineligible"}


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


def descriptor(row):
    require(type(row) is dict and {"path", "bytes", "sha256"} <= row.keys(),
            "Incomplete source descriptor")
    require(type(row["bytes"]) is int and 0 <= row["bytes"] <= MEMBER_LIMIT,
            "Invalid source extent")
    digest = row["sha256"]
    require(type(digest) is str and len(digest) == 64 and
            all(char in "0123456789abcdef" for char in digest), "Invalid source digest")


def same_pin(left, right):
    return all(left.get(key) == right.get(key) for key in ("bytes", "sha256"))


class Reader:
    """Bounded ordinary source reads, not a hostile-process filesystem sandbox."""
    def __init__(self, root):
        self.root = Path(root).absolute()
        require(self.root.is_dir() and not self.root.is_symlink(), "Ordinary repository root required")
        self.bytes_read = 0
        self.cache = {}

    def read(self, name, *, limit=None):
        if limit is None:
            limit = MEMBER_LIMIT
        relative(name)
        path = self.root / name
        for part in (path, *path.parents):
            require(not part.is_symlink(), "Symlink is not a source member: " + name)
        before = path.lstat()
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1,
                "Single-link regular source file required: " + name)
        require(0 <= before.st_size <= limit, "Source member too large: " + name)
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
        descriptor(row)
        body = self.read(name)
        require(len(body) == row["bytes"] and hashlib.sha256(body).hexdigest() == row["sha256"],
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


def historical_checked(reader, name, row, current):
    """Authenticate an old descriptor against explicit predecessor pins only.

    Current bytes are independently authenticated before this function. Old
    filesystem paths are never opened and changed source is never excused by a
    boolean declaration. Every predecessor descriptor must match its recorded pin.
    """
    descriptor(row)
    require(name in current, "Historical member is not in current package")
    require(same_pin(row, current[name]["predecessor"]),
            "Historical source hash or length mismatch: " + name)
    if "git_mode" in row:
        require(row["git_mode"] == current[name]["predecessor"]["git_mode"],
                "Historical source mode mismatch: " + name)
    return reader.checked(name, current[name])


def historical_member(package, value, style="package"):
    name = relative(value)
    if style == "repository":
        old_prefix = package["original_root"] + "/"
        require(name.startswith(old_prefix), "Inventory member escapes its package")
        name = name[len(old_prefix):]
    return package["root"] + "/" + name


def task_registry(reader):
    """Read only current public registration metadata, never old source locators."""
    document = strict_json(reader.read("benchmarks/registry.json", limit=REGISTRY_LIMIT))
    require(type(document) is dict and document.get("schema_version") == 1
            and document.get("kind") == "neuroscience_benchmark_registry",
            "Unsupported task registry for specification revision")
    rows = document.get("tasks")
    require(type(rows) is list and 0 < len(rows) <= 1000, "Bounded task registry required")
    result = {}
    for row in rows:
        require(type(row) is dict and type(row.get("id")) is str and row["id"] not in result,
                "Invalid or duplicate registered task identity")
        result[row["id"]] = row
    return result


def checked_paper_revision(reader, task_id, task_pin, task_doc, registered):
    """Authenticate an explicitly versioned PAPER revision and its exact predecessor.

    This verifies source lineage and binding only. Contract scientific validation
    remains the responsibility of the paper-improvement validator and catalog.
    """
    home = "benchmarks/paper/" + task_id
    revision = task_pin["specification_revision"]
    require(type(revision) is dict and set(revision) ==
            {"version", "previous_specification", "improvement_contract"}
            and revision["version"] == PAPER_REVISION, "Unsupported paper specification revision")
    previous, contract_pin = revision["previous_specification"], revision["improvement_contract"]
    for pin, name in ((previous, home + "/" + PAPER_HISTORY),
                      (contract_pin, home + "/improvement.v1.json")):
        require(type(pin) is dict and set(pin) == {"path", "bytes", "sha256"}
                and pin["path"] == name, "Paper revision member location or descriptor mismatch")
        descriptor(pin)
    require(same_pin(previous, task_pin["predecessor"]),
            "Historical paper specification does not match registered predecessor")
    historical_body = reader.checked(previous["path"], previous)
    historical_doc = strict_json(historical_body)
    expected_id = registered.get("specification_id", task_id) if type(registered) is dict else task_id
    require(type(historical_doc) is dict
            and historical_doc.get("id", historical_doc.get("candidate_id", historical_doc.get("task_id"))) == expected_id
            and historical_doc.get("track", "paper") == "paper"
            and historical_doc.get("objective") != PAPER_OBJECTIVE,
            "Historical paper specification identity or revision mismatch")
    contract = strict_json(reader.checked(contract_pin["path"], contract_pin))
    require(type(contract) is dict and contract.get("schema_version") == PAPER_REVISION
            and contract.get("task_id") == task_id and contract.get("objective") == PAPER_OBJECTIVE,
            "Paper improvement contract identity mismatch")
    legacy = contract.get("legacy")
    require(type(legacy) is dict and legacy.get("original_task") == PAPER_HISTORY
            and legacy.get("role") == "calibration_only", "Paper contract historical calibration mismatch")
    disposition = contract.get("disposition")
    require(type(disposition) is str and disposition in PAPER_DISPOSITIONS,
            "Unknown paper improvement disposition")
    evaluation = task_doc.get("evaluation")
    require(task_doc.get("objective") == PAPER_OBJECTIVE and task_doc.get("status") == disposition
            and type(evaluation) is dict and evaluation.get("objective") == PAPER_OBJECTIVE
            and evaluation.get("contract") == contract_pin
            and evaluation.get("disposition") == disposition
            and evaluation.get("reproduction_role") == "calibration_only",
            "Current paper task is not bound to its improvement contract")
    calibration = evaluation.get("calibration")
    require(type(calibration) is dict and calibration.get("historical_task") == previous,
            "Current paper task historical calibration binding mismatch")
    require(type(registered) is dict and registered.get("id") == task_id
            and registered.get("track") == "paper" and registered.get("task_directory") == home
            and registered.get("specification") == {key: task_pin[key] for key in ("path", "bytes", "sha256")}
            and registered.get("specification_revision") == revision,
            "Paper revision differs from current task registration")
    original = registered.get("original_specification")
    require(type(original) is dict and set(original) == {"path", "bytes", "sha256"}
            and original["path"] == task_pin["original_path"]
            and same_pin(original, task_pin["predecessor"]),
            "Paper revision changed its original registered identity")
    return historical_body


def check_complete_inventory(reader, package, selected, current):
    """One explicitly enrolled source profile; no task code or native semantics."""
    profile = package["complete_inventory"]
    require(type(profile) is dict and set(profile) == {"profile", "path"} and
            profile == {"profile": "neuroformer_factory_v2", "path": "NATIVE_FACTORY_API.json"},
            "Unknown complete inventory profile")
    require(package["id"] == "PAPER-paper-method-replacement-013" and
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
    api = strict_json(historical_checked(reader, prefix + "/" + api_path, pins[0], current))
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
        body = historical_checked(reader, name, row, current)
        require(stat.S_IMODE(reader.cache[name][0][2]) == 0o644,
                "Complete source permission mode must be 0644")
        # The retained API describes predecessor extents. Current extents and
        # hashes have already been authenticated by the outside current inventory.
        total += row["bytes"]
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


def check(root, registry="benchmarks/integrity/current.json"):
    reader = Reader(root)
    config = strict_json(reader.read(registry))
    return check_configuration(reader, config)


def check_configuration(reader, config):
    """Check an in-memory proposed registry before a maintenance write."""
    require(type(config) is dict and set(config) ==
            {"schema_version", "scope", "predecessor_commit", "packages"},
            "Closed current registry schema required")
    require(type(config["schema_version"]) is int and config["schema_version"] == 2,
            "Unsupported registry version")
    commit = config["predecessor_commit"]
    require(type(commit) is str and len(commit) == 40 and
            all(c in "0123456789abcdef" for c in commit), "Invalid predecessor commit")
    packages = config["packages"]
    require(type(packages) is list and 0 < len(packages) <= 64, "Nonempty bounded package roster required")
    implementation_ids, roots, reports = set(), set(), []
    for package in packages:
        fields = {"implementation_id", "task_id", "track", "root", "original_root",
                  "registered_task", "historical_inventory", "files"}
        require(type(package) is dict and set(package) in (fields, fields | {"complete_inventory"}),
                "Closed package schema")
        implementation_id = package["implementation_id"]
        require(type(implementation_id) is str and implementation_id and
                implementation_id not in implementation_ids, "Duplicate or invalid implementation ID")
        task_id = relative(package["task_id"])
        require("/" not in task_id, "Task ID must be one path component")
        track = package["track"]
        require(track in ("paper", "neural"), "Unknown task track")
        home = "benchmarks/" + track + "/" + task_id
        prefix = relative(package["root"])
        require(prefix.startswith(home + "/implementations/") and prefix.count("/") == 4,
                "Package root must match its task and track")
        original_root = relative(package["original_root"])
        require(original_root.startswith("benchmarks/neuroscience/") and original_root.count("/") == 2,
                "Invalid historical package origin")
        require(prefix.casefold() not in roots, "Duplicate package root")
        implementation_ids.add(implementation_id)
        roots.add(prefix.casefold())
        task_pin = package["registered_task"]
        task_fields = {"path", "bytes", "sha256", "original_path", "predecessor"}
        require(type(task_pin) is dict and set(task_pin) in
                (task_fields, task_fields | {"specification_revision"}),
                "Closed registered task descriptor required")
        require(task_pin["path"] == home + "/task.json", "Registered task location mismatch")
        require(relative(task_pin["original_path"]).startswith("benchmarks/manifests/" + track + "/")
                and task_pin["original_path"].count("/") == 3,
                "Invalid registered task predecessor location")
        task_predecessor = task_pin["predecessor"]
        require(type(task_predecessor) is dict and set(task_predecessor) == {"bytes", "sha256"},
                "Closed registered task predecessor required")
        descriptor({"path": task_pin["original_path"], **task_predecessor})
        revised = "specification_revision" in task_pin
        require(not revised or track == "paper", "Only paper tasks support specification revisions")
        if not revised:
            require(same_pin(task_pin, task_predecessor),
                    "Registered scientific task definition changed")
        task_body = reader.checked(task_pin["path"], task_pin)
        task_doc = strict_json(task_body)
        require(type(task_doc) is dict and task_doc.get("id") == task_id and task_doc.get("track") == track,
                "Canonical task ID or track mismatch")
        historical_task_body = task_body
        if revised:
            historical_task_body = checked_paper_revision(
                reader, task_id, task_pin, task_doc, task_registry(reader).get(task_id))

        rows = package["files"]
        require(type(rows) is list and 0 < len(rows) <= FILE_LIMIT, "Bounded current files required")
        current = {}
        for row in rows:
            require(type(row) is dict and set(row) ==
                    {"path", "bytes", "sha256", "git_mode", "predecessor"},
                    "Closed current source row required")
            name = prefix + "/" + relative(row["path"])
            require(name not in current, "Duplicate current inventory member")
            require(row["git_mode"] in ("100644", "100755"), "Invalid current source mode")
            predecessor = row["predecessor"]
            require(type(predecessor) is dict and set(predecessor) == {"bytes", "sha256", "git_mode"},
                    "Closed predecessor source pin required")
            descriptor({"path": row["path"], **predecessor})
            require(predecessor["git_mode"] in ("100644", "100755"), "Invalid predecessor source mode")
            current[name] = row
            reader.checked(name, row)
            require(stat.S_IMODE(reader.cache[name][0][2]) == int(row["git_mode"][-3:], 8),
                    "Current source permission mode mismatch: " + name)
        selected = set(current)
        require(len({name.casefold() for name in selected}) == len(selected), "Ambiguous source membership")
        require(physical_members(reader.root, prefix) == selected, "Missing or extra package members: " + task_id)

        history = package["historical_inventory"]
        require(type(history) is dict and set(history) ==
                {"path", "bytes", "sha256", "path_style", "supplemental_files"},
                "Closed historical inventory descriptor required")
        inventory_name = prefix + "/" + relative(history["path"])
        require(inventory_name in current, "Historical inventory is not covered")
        require(history["path_style"] in ("repository", "package"), "Unknown inventory path style")
        # Historical metadata stays exact. It is not silently rewritten to new
        # paths or treated as proof that changed current bytes match an old hash.
        inventory = strict_json(reader.checked(inventory_name, history))
        require(same_pin(history, current[inventory_name]["predecessor"]),
                "Historical inventory predecessor mismatch")
        require(type(inventory) is dict, "Inventory object required")
        old_rows = inventory.get("files")
        require(type(old_rows) is list and 0 < len(old_rows) <= FILE_LIMIT, "Bounded inventory files required")
        supplemental = history["supplemental_files"]
        require(type(supplemental) is list and len(supplemental) <= FILE_LIMIT, "Bounded supplement required")
        legacy_selected = {inventory_name}
        for row, style in [(row, history["path_style"]) for row in old_rows] + [
                (row, "package") for row in supplemental]:
            require(type(row) is dict and "path" in row, "Source row required")
            name = historical_member(package, row["path"], style)
            require(name.startswith(prefix + "/"), "Inventory member escapes its package")
            require(name not in legacy_selected, "Duplicate/self inventory member")
            if "runtime_path" in row:
                require(name == prefix + "/" + relative(row["runtime_path"]), "Runtime path disagreement")
            legacy_selected.add(name)
            historical_checked(reader, name, row, current)
        require(legacy_selected == selected, "Historical/current package membership mismatch")

        manifest_name = prefix + "/manifest.json"
        require(manifest_name in selected, "Package manifest is not covered")
        require(same_pin(current[manifest_name], current[manifest_name]["predecessor"]),
                "Historical package manifest changed")
        manifest = strict_json(reader.read(manifest_name))
        require(manifest.get("id") == task_id, "Manifest task ID mismatch")
        canonical = manifest.get("canonical_specification")
        require(type(canonical) is dict and "path" in canonical, "Canonical binding required")
        canonical_path = relative(canonical["path"])
        if canonical_path.startswith("benchmarks/"):
            require(canonical_path == task_pin["original_path"], "Unexpected external canonical location")
            descriptor(canonical)
            require(same_pin(canonical, task_predecessor), "Historical canonical binding mismatch")
            canonical_body = historical_task_body
        else:
            canonical_name = prefix + "/" + canonical_path
            require(canonical_name in selected, "Local canonical is not covered")
            require(same_pin(current[canonical_name], current[canonical_name]["predecessor"]),
                    "Package-local scientific contract changed")
            canonical_body = historical_checked(reader, canonical_name, canonical, current)
        require(strict_json(canonical_body).get("id") == task_id, "Canonical task ID mismatch")
        if "canonical" in inventory:
            require(inventory["canonical"] == canonical, "Inventory canonical binding mismatch")
        if "source_freeze" in manifest:
            freeze = manifest["source_freeze"]
            require(type(freeze) is dict and "path" in freeze, "Freeze descriptor required")
            name = historical_member(package, freeze["path"],
                                     "repository" if freeze["path"].startswith("benchmarks/") else "package")
            require(name == inventory_name, "Manifest names a different inventory")
            reader.checked(name, freeze)
        if "complete_inventory" in package:
            legacy_package = {"id": task_id, "root": prefix, "inventory": history["path"],
                              "inventory_paths": history["path_style"], "supplemental_files": supplemental,
                              "complete_inventory": package["complete_inventory"]}
            check_complete_inventory(reader, legacy_package, selected, current)
        python_count = 0
        for name in sorted(selected):
            if name.endswith(".py"):
                ast.parse(reader.read(name).decode("utf-8"), filename=name)
                python_count += 1
        reports.append({"implementation_id": implementation_id, "id": task_id,
                        "source_files": len(selected), "python_files": python_count,
                        "changed_files": sum(not same_pin(row, row["predecessor"]) or
                                             row["git_mode"] != row["predecessor"]["git_mode"]
                                             for row in current.values())})
    return {"status": "source_integrity_passed", "packages": reports,
            "bytes_read": reader.bytes_read, "benchmark_execution": False,
            "historical_pins_are_predecessor_evidence": True,
            "scientific_qualification_assessed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).absolute().parents[2])
    args = parser.parse_args()
    try:
        result = check(args.root)
    except (InvalidSource, OSError, UnicodeError, ValueError, TypeError, KeyError, RecursionError, SyntaxError) as error:
        parser.exit(1, "Source integrity failed: " + str(error) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

