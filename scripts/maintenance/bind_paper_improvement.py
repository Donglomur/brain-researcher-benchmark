#!/usr/bin/env python3
"""Bind every registered paper task to its same-task source-paper improvement contract.

Metadata only; standard library only. All contracts, provenance pins, destinations,
and historical bytes are validated before any mutation. --check never writes.
Original task and registry bytes are preserved once, never regenerated or replaced.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = "benchmarks/registry.json"
SNAPSHOT = "docs/provenance/registrations/paper-pre-improvement-v1.json"
VERSION = "paper-improvement/v1"
INITIAL_VERSION = "paper-improvement/initial-v1"
OBJECTIVE = "surpass_source_paper_same_task"
HISTORY = "historical/task.pre-improvement.v1.json"
EXPECTED_COUNT = 116
SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
# Source metadata remains available without carrying over former evaluation,
# readiness, reproduction success, or proposed different-task improvement rules.
SOURCE_FIELDS = (
    "source_id", "canonical_position_one_based", "paper_identity", "paper",
    "input_assets", "data", "data_source", "data_contract", "participant_inputs",
    "official_code", "official_repository", "code", "provenance", "source_pins",
    "source_family_ids", "source_families", "source_revision_limit", "source_rights",
    "publication_context", "rights", "resources", "resource_estimate", "runtime_storage",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def encode(value):
    return (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def strict_json(body, name):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, f"duplicate JSON key in {name}: {key}")
            result[key] = value
        return result

    def constant(value):
        raise ValueError(f"nonfinite JSON value in {name}: {value}")

    try:
        document = json.loads(body, object_pairs_hook=pairs, parse_constant=constant)
        # This also rejects finite-looking JSON numbers that overflow Python floats.
        json.dumps(document, allow_nan=False)
    except (UnicodeError, json.JSONDecodeError, TypeError) as error:
        raise ValueError(f"invalid JSON in {name}: {error}") from error
    require(isinstance(document, dict), f"JSON object required: {name}")
    return document


def safe_path(root, relative):
    require(isinstance(relative, str) and bool(relative), "nonempty repository-relative path required")
    parts = PurePosixPath(relative).parts
    require(not relative.startswith("/") and "\\" not in relative and "\x00" not in relative
            and all(part not in (".", "..") for part in relative.split("/"))
            and PurePosixPath(relative).as_posix() == relative,
            "unsafe repository-relative path: " + relative)
    path = root
    for part in parts:
        path = path / part
        require(not path.is_symlink(), "symlink path is not allowed: " + relative)
        if path != root / relative and path.exists():
            require(path.is_dir(), "non-directory path parent: " + relative)
    require(not path.exists() or path.is_file(), "regular file required: " + relative)
    return path


def read_file(root, relative):
    path = safe_path(root, relative)
    require(path.is_file(), "missing required file: " + relative)
    return path.read_bytes()


def pin(relative, body):
    return {"path": relative, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def validate_pin(value, relative, body, label):
    require(isinstance(value, dict), "missing pin: " + label)
    require(type(value.get("bytes")) is int and value["bytes"] >= 0
            and isinstance(value.get("sha256"), str) and SHA256.fullmatch(value["sha256"]),
            "invalid bytes/hash pin: " + label)
    require(value.get("path") == relative and value["bytes"] == len(body)
            and value["sha256"] == hashlib.sha256(body).hexdigest(), "stale pin: " + label)


def is_initial(row):
    revision = row.get("specification_revision")
    return isinstance(revision, dict) and revision.get("version") == INITIAL_VERSION


def task_rows(registry, expected_count, *, allow_initial=False):
    require(type(expected_count) is int and expected_count > 0, "positive expected count required")
    rows = registry.get("tasks")
    require(isinstance(rows, list), "registry tasks must be a list")
    ids = []
    for row in rows:
        require(isinstance(row, dict), "registry task must be an object")
        identifier = row.get("id")
        require(isinstance(identifier, str) and SAFE_ID.fullmatch(identifier), "unsafe task ID")
        ids.append(identifier)
    require(len(ids) == len(set(ids)) and len(ids) == len({i.casefold() for i in ids}),
            "registry task IDs must be unique, including case")
    paper = [row for row in rows if row.get("track") == "paper"]
    historical = [row for row in paper if not (allow_initial and is_initial(row))]
    require(len(historical) == expected_count,
            f"historical paper registration count must be exactly {expected_count}; found {len(historical)}")
    if not allow_initial:
        require(not any(is_initial(row) for row in paper), "historical registry cannot contain initial paper registrations")
    for row in paper:
        identifier = row["id"]
        directory = "benchmarks/paper/" + identifier
        require(row.get("task_directory") == directory, "unexpected paper task_directory: " + identifier)
        require(isinstance(row.get("specification"), dict)
                and row["specification"].get("path") == directory + "/task.json",
                "unexpected paper specification path: " + identifier)
        require(isinstance(row.get("title"), str) and row["title"].strip(), "missing registry title: " + identifier)
    return paper


def validate_identity(row, document):
    identifier = row["id"]
    identity = document.get("id", document.get("candidate_id", document.get("task_id")))
    require(isinstance(identity, str) and SAFE_ID.fullmatch(identity), "invalid specification identity: " + identifier)
    require(identity == row.get("specification_id")
            and type(row.get("specification_alias")) is bool
            and row["specification_alias"] == (identity != identifier), "specification identity/alias drift: " + identifier)
    require(document.get("track", "paper") == "paper", "specification track drift: " + identifier)
    if "title" in document:
        require(document["title"] == row["title"], "specification title drift: " + identifier)
    else:
        require(row.get("registration_class") == "expansion", "canonical specification title missing: " + identifier)
    return identity


def load_validator(root):
    path = safe_path(root, "src/neurobench/paper_improvement.py")
    require(path.is_file(), "paper improvement validator is required: " + str(path))
    spec = importlib.util.spec_from_file_location("_paper_improvement_binding_validator", path)
    require(spec is not None and spec.loader is not None, "cannot load paper improvement validator")
    module = importlib.util.module_from_spec(spec)
    # Some stdlib decorators inspect the defining module during import.
    sys.modules[spec.name] = module
    # SourceFileLoader.exec_module can create __pycache__ even during --check.
    # Execute the reviewed local source directly without bytecode side effects.
    exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
    require(callable(getattr(module, "contract_validate", None)), "contract_validate API is required")
    return module.contract_validate


def validate_initial_rows(root, registry, rows, validate):
    """Preserve first-definition registrations using the shared strict lineage API.

    These are new identities after the original paper revision. They are not
    inputs to the historical task rewriter and never acquire invented history.
    """
    initial = [row for row in rows if is_initial(row)]
    if not initial:
        return
    require(type(registry.get("schema_version")) is int and registry["schema_version"] == 1
            and registry.get("kind") == "neuroscience_benchmark_registry",
            "initial paper registration requires the current registry schema")
    tasks = registry["tasks"]
    require(all(row.get("track") in ("paper", "neural")
                and row.get("registration_class") in ("canonical", "expansion") for row in tasks),
            "initial paper registration requires complete current roster classifications")
    expected_counts = {"paper": sum(row["track"] == "paper" for row in tasks),
                       "neural": sum(row["track"] == "neural" for row in tasks), "total": len(tasks),
                       "canonical_specifications": sum(row["registration_class"] == "canonical" for row in tasks),
                       "expansion_drafts": sum(row["registration_class"] == "expansion" for row in tasks)}
    counts = registry.get("source_counts")
    require(type(counts) is dict and all(type(counts.get(key)) is int and counts[key] == value
                                        for key, value in expected_counts.items()),
            "initial paper registration current roster counts disagree")
    # Load the reviewed framework beside this maintenance script, including in
    # compact test roots. This imports no implementation and creates no pycache.
    path = safe_path(ROOT, "src/neurobench/repository_checks.py")
    spec = importlib.util.spec_from_file_location("_paper_initial_binding_lineage", path)
    require(spec is not None and spec.loader is not None, "cannot load initial paper lineage validator")
    checker = importlib.util.module_from_spec(spec)
    exec(compile(path.read_bytes(), str(path), "exec"), checker.__dict__)
    reader = checker.Reader(root)
    checker.paper_initial_registry(reader, registry, registry["tasks"])
    for row in initial:
        home, identifier = row["task_directory"], row["id"]
        require(not safe_path(root, home + "/" + HISTORY).exists(),
                "initial paper registration cannot contain a fabricated predecessor: " + identifier)
        document, _ = reader.document(home + "/task.json")
        validate_identity(row, document)
        checker.paper_initial_members(reader, row, document)
        contract, _ = reader.document(home + "/improvement.v1.json")
        errors = validate(contract, task_id=identifier)
        require(isinstance(errors, list) and all(isinstance(error, str) for error in errors),
                "invalid contract validator result")
        require(not errors, "invalid initial improvement contract " + identifier + ": " + "; ".join(errors))


def implementation_rows(registry, registered_ids):
    rows = registry.get("implementations")
    require(isinstance(rows, list), "registry implementations must be a list")
    seen = set()
    for row in rows:
        require(isinstance(row, dict) and isinstance(row.get("id"), str) and row["id"] not in seen,
                "invalid/duplicate implementation ID")
        seen.add(row["id"])
        for key in ("owner_ids", "related_task_ids"):
            values = row.get(key, [])
            require(isinstance(values, list) and all(isinstance(item, str) for item in values)
                    and len(values) == len(set(values)), "invalid implementation " + key)
            require(set(values) <= registered_ids, "unregistered implementation " + key)
    return rows


def current_task(original, row, contract, contract_pin, history_pin, implementation_ids):
    identity = validate_identity(row, original)
    target = contract["same_task"]["target"]["description"]
    metric = contract["comparison"]["primary_metric"]
    task = {
        "schema_version": 1, "id": identity, "track": "paper", "title": row["title"],
        "status": contract["disposition"], "objective": OBJECTIVE,
        "goal": "Surpass the source-paper result on the same task: " + target,
        "primary_outputs": [
            "Candidate method and outputs for the source task: " + target,
            "Source-paper comparison for " + metric + ": " + contract["same_task"]["metric"]["description"],
        ],
        "success_criteria": list(contract["comparison"]["paper_win_requires"]) + [
            "The bound improvement contract must be improvement_ready and its complete same-task comparison and admission requirements must pass.",
            "Reproduction is calibration only; reconstructing a numerical result, changing the task or split, or achieving stronger significance alone is not success.",
        ],
    }
    for field in SOURCE_FIELDS:
        if field in original:
            task[field] = copy.deepcopy(original[field])
    for field in ("input_assets", "resources", "provenance"):
        task.setdefault(field, {"status": "not_recorded_in_historical_specification"})
    task.update({
        "evaluation": {
            "objective": OBJECTIVE, "contract": contract_pin, "disposition": contract["disposition"],
            "reproduction_role": "calibration_only",
            "calibration": {"historical_task": history_pin, "implementation_ids": implementation_ids,
                            "runtime_manifest": copy.deepcopy(row.get("runtime_manifest"))},
            "executor_ref": None, "scorer_ref": None, "binary_reward_registered": False,
        },
        "episode": copy.deepcopy(contract["episode"]),
        "blocking_issues": copy.deepcopy(contract["blocking_issues"]),
        "holds": {"task_specific": copy.deepcopy(contract["blocking_issues"])},
        "next_implementation_action": {
            "action": contract["disposition_reason"] + " " + " ".join(contract["blocking_issues"]),
            "basis": "Current source-paper improvement contract disposition and blockers",
            "execution_authorized_by_manifest": False,
        },
        "legacy": {"role": "calibration_only", "original_task": history_pin,
                   "notes": contract["legacy"]["notes"]},
        "admission": {"runnable": False, "research_qualified": False, "full_contract_complete": False,
                      "delivery_unit": "one_registered_source_paper_improvement_contract", "new_scientific_runs": 0,
                      "reason": "Binding metadata does not execute or qualify an improvement evaluator."},
    })
    return task


def build_outputs(root=ROOT, expected_count=EXPECTED_COUNT, *, validator=None):
    """Return all deterministic output bytes after a complete read-only preflight.

    ``expected_count`` and ``validator`` support bounded metadata test fixtures;
    the command line always requires the original 116 historical registrations
    and the real validator. Explicit initial registrations are validated and
    preserved separately; they never change that historical roster requirement.
    """
    root = Path(root).absolute()
    require(root.is_dir() and not root.is_symlink(), "repository root must be a real directory")
    # Reject symlink ancestors too, including a linked checkout parent.
    require(all(not parent.is_symlink() for parent in root.parents), "repository root has a symlink ancestor")
    current_bytes = read_file(root, REGISTRY)
    current = strict_json(current_bytes, REGISTRY)
    rows = task_rows(current, expected_count, allow_initial=True)
    historical_rows = [row for row in rows if not is_initial(row)]
    current_by_id = {row["id"]: row for row in historical_rows}
    metadata = current.get("paper_improvement")
    snapshot_path = safe_path(root, SNAPSHOT)
    if metadata is not None:
        require(isinstance(metadata, dict) and metadata.get("schema_version") == VERSION
                and metadata.get("objective") == OBJECTIVE and metadata.get("coverage_required") is True
                and type(metadata.get("registered_count")) is int
                and metadata.get("registered_count") == len(rows), "invalid paper improvement coverage metadata")
        snapshot_bytes = read_file(root, SNAPSHOT)
        validate_pin(metadata.get("pre_improvement_registry"), SNAPSHOT, snapshot_bytes, "pre-improvement registry")
    elif snapshot_path.exists():
        snapshot_bytes = snapshot_path.read_bytes()
        require(snapshot_bytes == current_bytes, "refusing to clobber unrelated pre-improvement registry snapshot")
    else:
        snapshot_bytes = current_bytes
    require(not any(is_initial(row) for row in rows) or metadata is not None,
            "initial paper registrations require the preserved historical coverage metadata")
    original_registry = strict_json(snapshot_bytes, SNAPSHOT)
    require("paper_improvement" not in original_registry, "historical registry must predate improvement binding")
    originals = task_rows(original_registry, expected_count)
    require([row["id"] for row in originals] == [row["id"] for row in historical_rows], "paper registration IDs/order changed from historical registry")
    registered_ids = {row["id"] for row in current["tasks"]}
    old_ids = {row["id"] for row in original_registry["tasks"]}
    implementations = implementation_rows(current, registered_ids)
    old_implementations = implementation_rows(original_registry, old_ids)
    require({row["id"] for row in old_implementations} <= {row["id"] for row in implementations},
            "historical implementation removed from current registry")
    old_impl_by_id = {row["id"]: row for row in old_implementations}
    paper_ids = set(current_by_id)
    all_paper_ids = {row["id"] for row in rows}
    task_root = root / "benchmarks/paper"
    require(task_root.is_dir() and not task_root.is_symlink(), "paper task directory is missing or linked")
    for filename in ("task.json", "improvement.v1.json"):
        actual = {path.parent.name for path in task_root.glob("*/" + filename)}
        require(actual == all_paper_ids, filename + " must cover exactly the registered paper IDs")
    validate = validator if validator is not None else load_validator(root)
    validate_initial_rows(root, current, rows, validate)
    outputs = {SNAPSHOT: snapshot_bytes}
    registry = copy.deepcopy(current)
    registry_rows = {row["id"]: row for row in registry["tasks"]}
    for original_row in originals:
        identifier = original_row["id"]
        row = current_by_id[identifier]
        directory = original_row["task_directory"]
        task_path = directory + "/task.json"
        history_path = directory + "/" + HISTORY
        contract_path = directory + "/improvement.v1.json"
        task_bytes = read_file(root, task_path)
        validate_pin(row.get("specification"), task_path, task_bytes, identifier + " current specification")
        current_doc = strict_json(task_bytes, task_path)
        validate_identity(row, current_doc)
        for key in ("id", "title", "track", "task_directory", "specification_id", "specification_alias", "original_specification"):
            require(row.get(key) == original_row.get(key), "historical registry identity/pin changed: " + identifier + "/" + key)
        historical_file = safe_path(root, history_path)
        if metadata is not None:
            historical_bytes = read_file(root, history_path)
            revision = row.get("specification_revision")
            require(isinstance(revision, dict) and revision.get("version") == VERSION,
                    "missing paper specification revision: " + identifier)
            validate_pin(revision.get("previous_specification"), history_path, historical_bytes,
                         identifier + " previous specification")
        else:
            require("specification_revision" not in row and "paper_improvement" not in row,
                    "partial paper binding without coverage metadata: " + identifier)
            historical_bytes = task_bytes
            if historical_file.exists():
                require(historical_file.read_bytes() == historical_bytes, "refusing to clobber historical task: " + identifier)
        old_pin = original_row.get("specification")
        validate_pin(old_pin, task_path, historical_bytes, identifier + " historical specification")
        original_pin = original_row.get("original_specification")
        require(isinstance(original_pin, dict) and isinstance(original_pin.get("path"), str),
                "missing original specification pin: " + identifier)
        # The old source locator is intentionally retained, even if relocated away.
        safe_path(root, original_pin["path"])
        validate_pin(original_pin, original_pin["path"], historical_bytes, identifier + " original specification")
        original_doc = strict_json(historical_bytes, history_path)
        validate_identity(original_row, original_doc)
        require(original_doc.get("objective") != OBJECTIVE,
                "historical task already has the improvement objective: " + identifier)
        contract_bytes = read_file(root, contract_path)
        contract = strict_json(contract_bytes, contract_path)
        errors = validate(contract, task_id=identifier)
        require(isinstance(errors, list) and all(isinstance(error, str) for error in errors), "invalid contract validator result")
        require(not errors, "invalid improvement contract " + identifier + ": " + "; ".join(errors))
        require(contract.get("schema_version") == VERSION and contract.get("objective") == OBJECTIVE
                and contract.get("task_id") == identifier, "improvement contract identity drift: " + identifier)
        require(contract.get("legacy", {}).get("original_task") == HISTORY
                and contract["legacy"].get("role") == "calibration_only", "invalid legacy calibration binding: " + identifier)
        contract_pin, history_pin = pin(contract_path, contract_bytes), pin(history_path, historical_bytes)
        implementation_ids = [item["id"] for item in old_implementations if identifier in item["owner_ids"]]
        doc = current_task(original_doc, original_row, contract, contract_pin, history_pin, implementation_ids)
        body = encode(doc)
        outputs[history_path] = historical_bytes
        outputs[task_path] = body
        updated_row = registry_rows[identifier]
        updated_row.update({
            "specification": pin(task_path, body), "declared_specification_status": contract["disposition"],
            "scientific_readiness": contract["disposition"], "submission_readiness": "not_qualified_by_binding",
            "specification_revision": {"version": VERSION, "previous_specification": history_pin,
                                       "improvement_contract": contract_pin},
            "paper_improvement": {"schema_version": VERSION, "objective": OBJECTIVE,
                                  "disposition": contract["disposition"], "disposition_reason": contract["disposition_reason"],
                                  "contract": contract_pin, "legacy_evaluation_role": "calibration_only",
                                  "blocking_issues": copy.deepcopy(contract["blocking_issues"])},
        })
    for row in registry["implementations"]:
        original = old_impl_by_id.get(row["id"])
        if original is None:
            # A later implementation may be an actual improvement evaluator;
            # this migration only classifies preserved pre-improvement artifacts.
            continue
        require(row.get("owner_ids") == original.get("owner_ids")
                and row.get("related_task_ids", []) == original.get("related_task_ids", []),
                "implementation task ownership changed: " + row["id"])
        affected = paper_ids.intersection(original["owner_ids"] + original.get("related_task_ids", []))
        if not affected:
            continue
        roles = copy.deepcopy(row.get("evaluation_roles", {}))
        require(isinstance(roles, dict), "implementation evaluation_roles must be an object")
        for identifier in sorted(affected):
            roles[identifier] = "calibration_only"
        row["evaluation_roles"] = roles
        all_tasks = set(original["owner_ids"] + original.get("related_task_ids", []))
        if all_tasks <= paper_ids:
            row["role"] = "calibration_only"
            row["scope_notes"] = ((original.get("scope_notes") or "") + " "
                "Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.").strip()
    registry["paper_improvement"] = {
        "schema_version": VERSION, "objective": OBJECTIVE, "coverage_required": True,
        "registered_count": len(rows), "pre_improvement_registry": pin(SNAPSHOT, snapshot_bytes),
    }
    outputs[REGISTRY] = encode(registry)
    # Validate every destination before returning a plan, including absent parents.
    for relative in outputs:
        safe_path(root, relative)
    return outputs


def write_or_check(root=ROOT, check=False, *, expected_count=EXPECTED_COUNT, validator=None):
    root = Path(root).absolute()
    outputs = build_outputs(root, expected_count=expected_count, validator=validator)
    before = {}
    for relative in outputs:
        path = safe_path(root, relative)
        before[relative] = path.read_bytes() if path.exists() else None
    stale = [relative for relative, body in outputs.items() if before[relative] != body]
    if check:
        require(not stale, "paper improvement bindings stale or missing: " + ", ".join(stale))
    else:
        # Catch concurrent input changes before the first write as well. Contract
        # pins are checked against a second read-only plan, not just output files.
        require(outputs == build_outputs(root, expected_count=expected_count, validator=validator),
                "binding inputs changed during preflight")
        for relative in outputs:
            path = safe_path(root, relative)
            require((path.read_bytes() if path.exists() else None) == before[relative],
                    "output changed during preflight: " + relative)
        for relative in stale:
            body, path = outputs[relative], safe_path(root, relative)
            path.parent.mkdir(parents=True, exist_ok=True)
            if relative == SNAPSHOT or relative.endswith("/" + HISTORY):
                # Historical bytes are immutable. Existing identical bytes never
                # enter `stale`; exclusive creation also protects against a race.
                with path.open("xb") as handle:
                    handle.write(body)
            else:
                descriptor, temporary = tempfile.mkstemp(prefix="." + path.name + ".", dir=path.parent)
                try:
                    with os.fdopen(descriptor, "wb") as handle:
                        handle.write(body)
                    os.replace(temporary, path)
                finally:
                    if os.path.exists(temporary):
                        os.unlink(temporary)
    registry = strict_json(outputs[REGISTRY], REGISTRY)
    counts = {}
    for row in registry["tasks"]:
        if row.get("track") == "paper":
            # Both historical rewrites and preserved initial registrations have
            # authenticated this value against their actual contract. A display
            # summary is optional for initial profiles and is not a count source.
            disposition = row["scientific_readiness"]
            counts[disposition] = counts.get(disposition, 0) + 1
    return {"status": "current" if check else "written", "paper_registrations": sum(counts.values()),
            "dispositions": dict(sorted(counts.items())), "changed_files": len(stale),
            "pre_improvement_registry": registry["paper_improvement"]["pre_improvement_registry"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate inputs and compare generated bytes without writing")
    parser.add_argument("--root", type=Path, default=ROOT, help="repository root (default: this checkout)")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(write_or_check(args.root, check=args.check), indent=2))
        return 0
    except (ValueError, KeyError, TypeError, OSError, ImportError) as error:
        print("paper improvement binding failed: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
