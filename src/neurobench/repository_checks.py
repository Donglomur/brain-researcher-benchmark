"""Check current source ownership without executing or following scientific inputs."""

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tempfile

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = "benchmarks/registry.json"
RELOCATIONS = "docs/provenance/relocations/2026-11-16.json"
INVENTORY = "benchmarks/integrity/source-ownership.json"
CURRENT_BINDINGS = "benchmarks/integrity/current.json"
CURRENT_CLOSURES = "benchmarks/integrity/current-closures"
CANONICAL_PER_TRACK = 100
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_READ_BYTES = 128 * 1024 * 1024
MAX_FILES = 12000
MAX_TREE_ENTRIES = 30000
MAX_DEPTH = 32
SOURCE_SUFFIXES = {"", ".py", ".json", ".md", ".txt", ".m", ".r", ".yaml", ".yml",
                   ".sh", ".lock", ".toml", ".in", ".author", ".list", ".template",
                   ".rst", ".c", ".dockerignore"}
RETIRED_ROOTS = ("authoring", "components", "artifacts-build", "verification", "results", "tools",
                 "benchmarks/neuroscience", "benchmarks/manifests",
                 "benchmarks/scientific_components", "benchmarks/scientific_contracts")
# Runtime outputs are not source. This checker never traverses this directory.
RUNTIME_ROOTS = (".neurobench",)
PAPER_REVISION = "paper-improvement/v1"
PAPER_OBJECTIVE = "surpass_source_paper_same_task"
PAPER_DISPOSITIONS = {"improvement_ready", "design_ready", "source_unresolved", "ineligible"}


def need(value, message):
    if not value:
        raise ValueError(message)


def relative_path(value):
    need(isinstance(value, str) and value and "\\" not in value
         and not any(ord(c) < 32 for c in value), "Invalid source path")
    path = PurePosixPath(value)
    need(not path.is_absolute() and str(path) == value and value != "."
         and ".." not in path.parts, "Source path must be normalized and inside the repository: " + value)
    return path


def info_or_none(path):
    try:
        return path.lstat()
    except FileNotFoundError:
        return None


def checked_path(root, relative, *, directory=False, missing=False):
    parts = relative_path(relative).parts
    current = root
    need(stat.S_ISDIR(root.lstat().st_mode), "Repository root must be an ordinary directory")
    for index, part in enumerate(parts):
        current = current / part
        info = info_or_none(current)
        if info is None:
            need(missing, "Missing source path: " + relative)
            continue
        if index < len(parts) - 1 or directory:
            need(stat.S_ISDIR(info.st_mode), "Source directory alias or conflicting type: " + relative)
        else:
            need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1,
                 "Source must be an ordinary single-link file: " + relative)
    return current


def fingerprint(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


class Reader:
    def __init__(self, root):
        self.root = Path(root).absolute()
        self.bytes_read = 0
        self.pins = {}
        self.identities = {}

    def file(self, relative, *, capture=False):
        path = checked_path(self.root, relative)
        before = path.lstat()
        if relative in self.pins and not capture:
            need(fingerprint(before) == self.identities[relative], "Source changed during check: " + relative)
            return self.pins[relative], None
        need(before.st_size <= MAX_FILE_BYTES, "Source member exceeds byte limit: " + relative)
        need(self.bytes_read + before.st_size <= MAX_READ_BYTES, "Source read budget exceeded")
        self.bytes_read += before.st_size
        digest = hashlib.sha256()
        chunks = []
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            need(fingerprint(os.fstat(descriptor)) == fingerprint(before), "Source changed before read: " + relative)
            remaining = before.st_size
            while remaining:
                block = os.read(descriptor, min(remaining, 128 * 1024))
                need(block, "Source shortened during read: " + relative)
                digest.update(block)
                if capture:
                    chunks.append(block)
                remaining -= len(block)
            need(not os.read(descriptor, 1), "Source grew during read: " + relative)
            need(fingerprint(os.fstat(descriptor)) == fingerprint(before), "Source changed during read: " + relative)
        finally:
            os.close(descriptor)
        need(fingerprint(path.lstat()) == fingerprint(before), "Source replaced during read: " + relative)
        pin = {"path": relative, "mode": "100755" if before.st_mode & 0o111 else "100644",
               "bytes": before.st_size, "sha256": digest.hexdigest()}
        self.pins[relative] = pin
        self.identities[relative] = fingerprint(before)
        return pin, b"".join(chunks) if capture else None

    def document(self, relative):
        pin, raw = self.file(relative, capture=True)
        def unique(items):
            result = {}
            for key, value in items:
                need(key not in result, "Duplicate JSON key in " + relative)
                result[key] = value
            return result
        document = json.loads(raw, object_pairs_hook=unique,
                              parse_constant=lambda value: need(False, "Non-JSON number in " + relative))
        need(isinstance(document, dict), "Expected a metadata object: " + relative)
        return document, pin


def unique_ids(values, known, label):
    need(isinstance(values, list) and all(isinstance(v, str) for v in values)
         and len(set(values)) == len(values), label + " must be unique strings")
    need(set(values) <= known, "Unknown " + label)
    return values


def metadata_pin(reader, pin, expected_path, label):
    """Authenticate one explicitly owned metadata file without following its locators."""
    need(type(pin) is dict and set(pin) == {"path", "bytes", "sha256"},
         "Closed " + label + " pin required")
    need(pin["path"] == expected_path, label + " is outside its exact location")
    need(type(pin["bytes"]) is int and 0 <= pin["bytes"] <= MAX_FILE_BYTES
         and isinstance(pin["sha256"], str) and re.fullmatch(r"[0-9a-f]{64}", pin["sha256"]),
         "Invalid " + label + " pin")
    document, actual = reader.document(expected_path)
    need(all(actual[k] == pin[k] for k in ("path", "bytes", "sha256")), label + " pin mismatch")
    return document


def paper_revision_members(reader, row, document):
    """Bind the authorized paper revision to exact historical and current metadata.

    This establishes source lineage only. The catalog's contract validator owns
    scientific comparison semantics; the metadata cannot qualify execution.
    """
    revision = row.get("specification_revision")
    need(row["track"] == "paper" and type(revision) is dict
         and set(revision) == {"version", "previous_specification", "improvement_contract"}
         and revision["version"] == PAPER_REVISION, "Unsupported task specification revision")
    directory = row["task_directory"]
    previous = revision["previous_specification"]
    old = metadata_pin(reader, previous, directory + "/historical/task.pre-improvement.v1.json",
                       "Historical paper specification")
    original = row.get("original_specification")
    need(type(original) is dict and type(original.get("bytes")) is int
         and all(original.get(key) == previous[key] for key in ("bytes", "sha256")),
         "Paper revision does not preserve its original specification")
    relative_path(original.get("path"))
    old_identity = old.get("id", old.get("candidate_id", old.get("task_id")))
    need(old_identity == row["specification_id"] and old.get("track", "paper") == "paper"
         and old.get("objective") != PAPER_OBJECTIVE, "Historical paper specification identity mismatch")
    contract_pin = revision["improvement_contract"]
    contract = metadata_pin(reader, contract_pin, directory + "/improvement.v1.json",
                            "Paper improvement contract")
    need(contract.get("schema_version") == PAPER_REVISION and contract.get("task_id") == row["id"]
         and contract.get("objective") == PAPER_OBJECTIVE
         and type(contract.get("disposition")) is str
         and contract.get("disposition") in PAPER_DISPOSITIONS,
         "Paper improvement contract identity or disposition mismatch")
    legacy = contract.get("legacy")
    need(type(legacy) is dict and legacy.get("role") == "calibration_only"
         and legacy.get("original_task") == "historical/task.pre-improvement.v1.json",
         "Paper improvement contract historical binding mismatch")
    evaluation = document.get("evaluation")
    need(document.get("objective") == PAPER_OBJECTIVE and type(evaluation) is dict
         and evaluation.get("objective") == PAPER_OBJECTIVE
         and evaluation.get("contract") == contract_pin
         and evaluation.get("disposition") == contract["disposition"]
         and evaluation.get("reproduction_role") == "calibration_only"
         and type(evaluation.get("calibration")) is dict
         and evaluation["calibration"].get("historical_task") == previous
         and document.get("status") == contract["disposition"],
         "Current paper definition is not bound to its improvement contract")
    need(row["scientific_readiness"] == contract["disposition"]
         and row["submission_readiness"] == "not_qualified_by_binding",
         "Paper source binding cannot grant scientific qualification")
    return {previous["path"], contract_pin["path"]}


def check_namespace(root, prefix, boundaries, allowed_files):
    """Check ownership outside artifact boundaries without entering those closures."""
    stack = [prefix]
    visited = 0
    while stack:
        relative = stack.pop()
        if relative in boundaries:
            checked_path(root, relative, directory=True)
            continue
        path = checked_path(root, relative, directory=True)
        with os.scandir(path) as entries:
            for entry in entries:
                visited += 1
                need(visited <= MAX_TREE_ENTRIES, "Ownership namespace exceeds entry limit")
                child = relative + "/" + entry.name
                mode = entry.stat(follow_symlinks=False).st_mode
                if stat.S_ISDIR(mode):
                    need(any(p.startswith(child + "/") or p == child for p in boundaries | allowed_files),
                         "Orphan source directory: " + child)
                    stack.append(child)
                else:
                    checked_path(root, child)
                    need(child in allowed_files, "Orphan source file: " + child)


def artifact_members(root, artifacts, *, binding_metadata_only=False):
    members = {}
    folded = {}
    visited = 0
    for artifact in artifacts:
        stack = [(artifact["path"], 0)]
        while stack:
            relative, depth = stack.pop()
            need(depth <= MAX_DEPTH, "Source directory depth limit exceeded")
            path = checked_path(root, relative, directory=True)
            with os.scandir(path) as entries:
                for entry in entries:
                    visited += 1
                    need(visited <= MAX_TREE_ENTRIES, "Source tree entry limit exceeded")
                    child = relative + "/" + entry.name
                    need(child.casefold() not in folded or folded[child.casefold()] == child,
                         "Case-ambiguous source member: " + child)
                    folded[child.casefold()] = child
                    info = entry.stat(follow_symlinks=False)
                    if stat.S_ISDIR(info.st_mode):
                        stack.append((child, depth + 1))
                    else:
                        checked_path(root, child)
                        if binding_metadata_only:
                            need(Path(child).suffix == ".json" or Path(child).name == "README.md",
                                 "Unexpected current-binding member: " + child)
                        need(Path(child).suffix.lower() in SOURCE_SUFFIXES, "Non-source member type: " + child)
                        need(child not in members, "Overlapping source ownership: " + child)
                        members[child] = "artifact:" + artifact["id"]
                        need(len(members) <= MAX_FILES, "Source file count limit exceeded")
    return members


def prepare(reader):
    root = reader.root
    for relative in RETIRED_ROOTS:
        need(info_or_none(root / relative) is None, "Retired active root is present: " + relative)
    # Check the parent namespace too: a misspelled track must not disappear
    # from the ownership inventory simply because it is outside both tracks.
    check_namespace(root, "benchmarks", {
        "benchmarks/paper", "benchmarks/neural", "benchmarks/shared",
        "benchmarks/catalog", "benchmarks/integrity",
    }, {"benchmarks/README.md", REGISTRY})
    registry, registry_pin = reader.document(REGISTRY)
    need(registry.get("schema_version") == 1 and registry.get("kind") == "neuroscience_benchmark_registry",
         "Unsupported current registry")
    tasks = registry.get("tasks")
    need(isinstance(tasks, list) and 0 < len(tasks) <= 1000, "Invalid task inventory")
    by_id, task_paths, members, expected_pins = {}, {}, {}, {}
    classes = {"canonical": Counter(), "expansion": Counter()}
    allowed_files = {"paper": {"benchmarks/paper/README.md"}, "neural": {"benchmarks/neural/README.md"}}
    for row in tasks:
        identifier, track = row["id"], row["track"]
        need(isinstance(identifier, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,199}", identifier)
             and identifier.casefold() != "readme.md", "Unsafe task ID")
        need(identifier not in by_id and track in allowed_files, "Duplicate task or unknown track")
        directory = f"benchmarks/{track}/{identifier}"
        need(row["task_directory"] == directory, "Task home does not match its owner and track")
        need(directory.casefold() not in task_paths, "Case-ambiguous task home")
        task_paths[directory.casefold()] = directory
        checked_path(root, directory, directory=True)
        classification = row["registration_class"]
        need(classification in classes, "Unknown task registration class")
        classes[classification][track] += 1
        pin = row["specification"]
        need(pin["path"] == directory + "/task.json", "Task specification is outside its exact home")
        document, actual = reader.document(pin["path"])
        need(all(actual[k] == pin[k] for k in ("path", "bytes", "sha256")), "Task specification pin mismatch: " + identifier)
        identity = document.get("id", document.get("candidate_id", document.get("task_id")))
        need(identity == row["specification_id"] and row["specification_alias"] == (identity != identifier),
             "Task specification identity or alias mismatch: " + identifier)
        need(document.get("track", track) == track, "Task specification track mismatch")
        if "specification_revision" in row:
            revision_members = paper_revision_members(reader, row, document)
            for path in revision_members:
                need(path not in members, "Duplicate paper revision metadata")
                members[path] = "task:" + identifier
            allowed_files[track].update(revision_members)
        else:
            need(row["scientific_readiness"] == row["submission_readiness"] == "unknown",
                 "Source registry cannot grant scientific qualification")
            need(track != "paper" or not registry.get("paper_improvement", {}).get("coverage_required"),
                 "Paper improvement coverage requires every paper revision")
        members[pin["path"]] = "task:" + identifier
        allowed_files[track].update((directory + "/README.md", pin["path"]))
        for item in row.get("documentation", []):
            path = item["path"]
            relative_path(path)
            need(path.startswith(directory + "/docs/") and path not in members,
                 "Task documentation is outside its exact owner or duplicated")
            checked_path(root, path)
            members[path] = "task:" + identifier
            allowed_files[track].add(path)
        by_id[identifier] = row
    need(all(classes["canonical"][track] == CANONICAL_PER_TRACK for track in allowed_files),
         "Expected exactly 100 canonical specifications per track")
    counts = registry["source_counts"]
    actual_counts = {track: sum(v[track] for v in classes.values()) for track in allowed_files}
    actual_counts.update(total=len(tasks), canonical_specifications=sum(classes["canonical"].values()),
                         expansion_drafts=sum(classes["expansion"].values()))
    need(all(type(counts.get(k)) is int and counts[k] == v for k, v in actual_counts.items()),
         "Registry task counts disagree with exact ownership")
    need(all(type(counts.get(k)) is int and counts[k] >= 0 for k in
             ("source_components", "runtime_manifests", "linked_runtime_manifests")),
         "Source lineage counts must be nonnegative integers")
    artifacts = registry.get("implementations")
    need(isinstance(artifacts, list) and len(artifacts) <= 2048, "Invalid artifact inventory")
    ids, paths, descriptors = set(), set(), []
    for row in artifacts:
        identifier, path = row["id"], row["path"]
        need(isinstance(identifier, str) and identifier and identifier not in ids, "Duplicate or missing artifact ID")
        ids.add(identifier)
        relative_path(path)
        owners = unique_ids(row["owner_ids"], set(by_id), "artifact owner ID")
        related = unique_ids(row.get("related_task_ids", []), set(by_id), "related task ID")
        need(not set(owners) & set(related), "Related task cannot also be an artifact owner")
        scope = row["scope"]
        need(scope in ("task", "shared", "unresolved"), "Unknown artifact scope")
        if scope == "task":
            need(len(owners) == 1, "Task artifact must have one owner")
            home = by_id[owners[0]]["task_directory"]
            need(path.startswith((home + "/implementations/", home + "/contracts/")),
                 "Task artifact is outside its owner home")
        else:
            framework_source = (scope == "shared" and row.get("status") == "shared_framework_source"
                                and not owners and not related and path.startswith("src/neurobench/"))
            need(path.startswith("benchmarks/shared/") or framework_source,
                 "Shared artifact is misclassified under a task home or outside a declared framework source")
            need(scope != "unresolved" or not owners, "Unresolved artifact cannot claim owners")
        need(row.get("scientific_readiness") == "unknown", "Artifact cannot claim scientific qualification")
        need(isinstance(row.get("role"), str) and row["role"].strip(), "Artifact needs an explicit role")
        need(isinstance(row.get("scope_notes"), str) and row["scope_notes"].strip(), "Artifact needs scope notes")
        folded = path.casefold()
        need(all(folded != p and not folded.startswith(p + "/") and not p.startswith(folded + "/") for p in paths),
             "Artifact roots overlap or alias")
        paths.add(folded)
        checked_path(root, path, directory=True)
        descriptors.append({k: row[k] for k in ("id", "path", "scope", "owner_ids", "role")}
                           | {"related_task_ids": related})
    boundaries = {r["path"] for r in artifacts}
    for track in allowed_files:
        check_namespace(root, "benchmarks/" + track, boundaries, allowed_files[track])
    if info_or_none(root / "benchmarks/shared") is not None or any(p.startswith("benchmarks/shared/") for p in boundaries):
        check_namespace(root, "benchmarks/shared", boundaries, {"benchmarks/shared/README.md"})
    components = registry.get("components")
    need(isinstance(components, list) and len(components) == counts["source_components"], "Component lineage count mismatch")
    seen_components = set()
    for component in components:
        path = component["path"]
        need(path not in seen_components, "Duplicate component lineage path")
        seen_components.add(path)
        checked_path(root, path, directory=True)
        need(any(path == p or path.startswith(p + "/") or p.startswith(path + "/") for p in boundaries),
             "Component lineage has no registered artifact closure")
    runtime_count = 0
    for task in tasks:
        pin = task.get("runtime_manifest")
        if pin:
            runtime_count += 1
            package = task["runtime_package"]
            need(package in boundaries and pin["path"] == package + "/manifest.json", "Runtime manifest has no explicit artifact")
            artifact = next(r for r in artifacts if r["path"] == package)
            need(task["id"] in artifact["owner_ids"], "Runtime source is not owned by its registered task")
            expected_pins[pin["path"]] = pin
        else:
            need(task.get("runtime_package") is None, "Runtime package lacks a manifest")
    need(runtime_count == counts["runtime_manifests"] == counts["linked_runtime_manifests"], "Runtime lineage count mismatch")
    for key in ("historical_registries", "shared_contracts"):
        for item in registry.get(key, []):
            path = item["path"]
            need(path.startswith("docs/provenance/registrations/"), "Historical registration path is outside provenance")
            checked_path(root, path)
            need(path not in members, "Duplicate source metadata path")
            members[path] = "registration-provenance"
            if "sha256" in item:
                expected_pins[path] = item
    if "paper_improvement" in registry:
        improvement = registry["paper_improvement"]
        need(type(improvement) is dict
             and set(improvement) == {"schema_version", "objective", "coverage_required", "registered_count",
                                     "pre_improvement_registry"}
             and improvement["schema_version"] == PAPER_REVISION
             and improvement["objective"] == PAPER_OBJECTIVE and improvement["coverage_required"] is True
             and type(improvement["registered_count"]) is int
             and improvement["registered_count"] == actual_counts["paper"],
             "Invalid paper improvement coverage metadata")
        history_pin = improvement["pre_improvement_registry"]
        history_path = "docs/provenance/registrations/paper-pre-improvement-v1.json"
        metadata_pin(reader, history_pin, history_path, "Pre-improvement registry")
        need(history_path not in members, "Duplicate paper registry provenance")
        members[history_path] = "registration-provenance"
        expected_pins[history_path] = history_pin
    artifact_files = artifact_members(root, artifacts)
    need(not set(members) & set(artifact_files), "Artifact overlaps task or provenance metadata")
    members.update(artifact_files)
    # These are live source-binding descriptors, not additional benchmark artifacts.
    # Hash JSON descriptors and their exact README.md guides without following
    # any source or private-payload locators.
    check_namespace(root, "benchmarks/integrity", {CURRENT_CLOSURES}, {CURRENT_BINDINGS, INVENTORY})
    checked_path(root, CURRENT_BINDINGS)
    binding_files = artifact_members(root, [{"path": CURRENT_CLOSURES, "id": "current-bindings"}], binding_metadata_only=True)
    binding_files[CURRENT_BINDINGS] = "current-binding-metadata"
    binding_files = dict.fromkeys(binding_files, "current-binding-metadata")
    need(not set(members) & set(binding_files), "Current binding metadata overlaps artifact source")
    members.update(binding_files)
    need(len(members) <= MAX_FILES, "Source file count limit exceeded")
    ledger, ledger_pin = reader.document(RELOCATIONS)
    need(ledger.get("schema_version") == 1 and isinstance(ledger.get("files"), list)
         and len(ledger["files"]) <= MAX_TREE_ENTRIES, "Invalid relocation ledger")
    old_paths, new_paths = set(), set()
    for item in ledger["files"]:
        old, new = str(relative_path(item["old"])), str(relative_path(item["new"]))
        need(old not in old_paths and new.casefold() not in new_paths, "Duplicate relocation ledger path")
        old_paths.add(old)
        new_paths.add(new.casefold())
        checked_path(root, new)
    # The ledger describes original bodies. Its old hashes are not current runtime qualifications.
    return {"registry": registry_pin, "relocation_ledger": ledger_pin,
            "counts": actual_counts | {"artifacts": len(artifacts), "source_components": len(components),
                                       "artifact_files": len(artifact_files), "current_binding_files": len(binding_files),
                                       "source_files": len(members)},
            "canonical_per_track": dict(classes["canonical"]), "expansion_per_track": dict(classes["expansion"]),
            "artifacts": sorted(descriptors, key=lambda r: r["id"]), "members": members, "expected_pins": expected_pins}


def check_repository(root=ROOT, *, write=False):
    reader = Reader(root)
    stored = None
    if not write:
        stored, _ = reader.document(INVENTORY)
        need(stored.get("schema_version") == 1 and stored.get("kind") == "current_source_ownership", "Unsupported source inventory")
    plan = prepare(reader)
    if stored is not None:
        need(stored.get("registry") == plan["registry"], "Current registry changed; review and explicitly rebuild its source inventory")
        need(stored.get("relocation_ledger") == plan["relocation_ledger"], "Relocation ledger changed")
        records = stored.get("files")
        need(isinstance(records, list) and len(records) == len(plan["members"]), "Missing or unexpected source inventory member")
        expected = {r["path"]: r for r in records}
        need(len(expected) == len(records) and set(expected) == set(plan["members"]), "Missing or unexpected source inventory member")
        need(all(expected[p].get("owner") == owner for p, owner in plan["members"].items()), "Source ownership inventory mismatch")
    records = []
    for path, owner in sorted(plan["members"].items()):
        pin, _ = reader.file(path)
        if path in plan["expected_pins"]:
            source_pin = plan["expected_pins"][path]
            need(all(pin[k] == source_pin[k] for k in ("path", "bytes", "sha256")), "Declared source pin mismatch: " + path)
        record = pin | {"owner": owner}
        if stored is not None:
            need(record == expected[path], "Source content or mode drift: " + path)
        records.append(record)
    current = {"schema_version": 1, "kind": "current_source_ownership",
               "scope": "Current declared source bytes and ownership only; no benchmark execution or scientific qualification.",
               "registry": plan["registry"], "relocation_ledger": plan["relocation_ledger"],
               "counts": plan["counts"] | {"source_bytes": sum(r["bytes"] for r in records)},
               "canonical_per_track": plan["canonical_per_track"], "expansion_per_track": plan["expansion_per_track"],
               "artifacts": plan["artifacts"], "files": records, "scientific_qualification": False}
    raw = (json.dumps(current, indent=2, ensure_ascii=False) + "\n").encode()
    need(len(raw) <= MAX_FILE_BYTES, "Source inventory exceeds metadata limit")
    if write:
        target = checked_path(reader.root, INVENTORY, missing=True)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".source-ownership-", delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(raw)
            temporary.chmod(0o644)
            os.replace(temporary, target)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()
    else:
        need(stored == current, "Unexpected source inventory field or aggregate drift")
    return {"source_check": "written" if write else "passed", **current["counts"],
            "canonical_per_track": plan["canonical_per_track"], "expansion_per_track": plan["expansion_per_track"],
            "bytes_read": reader.bytes_read, "read_limit_bytes": MAX_READ_BYTES,
            "scientific_qualification": False, "scientific_execution": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Explicitly build a new current inventory after reviewing source changes")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(check_repository(write=args.write), sort_keys=True))
        return 0
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as error:
        print(json.dumps({"source_check": "refused", "reason": str(error), "scientific_qualification": False}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
