#!/usr/bin/env python3
"""Plan, check or explicitly bind separate paper reproduction/improvement metadata.

Only the deterministic current task projection, exact pre-outcomes archives and
registry bindings are written. Supplied scientific contracts are validated, never
generated or repaired here. No implementation, data or receipt is executed.
"""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]


def framework(name):
    if name not in ("paper_outcomes_binding", "repository_checks"):
        raise ValueError("Unknown outcome binding framework module")
    path = ROOT / "src/neurobench" / (name + ".py")
    spec = importlib.util.spec_from_file_location("_paper_outcome_binder_" + name, path)
    module = importlib.util.module_from_spec(spec)
    exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
    return module


binding = framework("paper_outcomes_binding")
checker = framework("repository_checks")


def root_path(root):
    root = Path(root).absolute()
    binding.need(root.is_dir() and not root.is_symlink()
                 and all(not parent.is_symlink() for parent in root.parents),
                 "Outcome binding requires a real repository root without linked ancestors")
    return root


def raw(reader, relative):
    pin, body = reader.file(relative, capture=True)
    return body, {key: pin[key] for key in ("path", "bytes", "sha256")}


def read_pinned(reader, pin, label):
    return checker.metadata_pin(reader, pin, pin["path"], label)


def roster(registry):
    binding.need(type(registry) is dict and registry.get("schema_version") == 1
                 and registry.get("kind") == "neuroscience_benchmark_registry", "Invalid current registry")
    rows = registry.get("tasks")
    binding.need(type(rows) is list and 0 < len(rows) <= 1000 and all(type(row) is dict for row in rows),
                 "Invalid registered task roster")
    ids = [row.get("id") for row in rows]
    binding.need(all(type(identifier) is str and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", identifier) for identifier in ids) and len(set(ids)) == len(ids)
                 and len({identifier.casefold() for identifier in ids}) == len(ids), "Duplicate registered task identity")
    papers = [row for row in rows if row.get("track") == "paper"]
    binding.need(papers and all(row.get("track") in ("paper", "neural") for row in rows), "Invalid outcome task tracks")
    counts = registry.get("source_counts")
    expected = {"paper": len(papers), "neural": len(rows) - len(papers), "total": len(rows)}
    binding.need(type(counts) is dict and all(type(counts.get(key)) is int and counts[key] == value for key, value in expected.items()),
                 "Outcome binding must retain exact registered task counts")
    for row in papers:
        home = "benchmarks/paper/" + row["id"]
        binding.need(row.get("task_directory") == home, "Paper task directory does not match its identity")
        binding.require_pin(row.get("specification"), home + "/task.json", "current task")
        revision = row.get("specification_revision")
        binding.need(type(revision) is dict and revision.get("version") in
                     ("paper-improvement/v1", "paper-improvement/initial-v1"), "Paper improvement lineage is required")
        binding.require_pin(revision.get("improvement_contract"), home + "/improvement.v1.json", "improvement contract")
    return papers


def prior_lineage(reader, registry, rows, contexts=None):
    """Validate unchanged original lineage, explicitly reading archived initials."""
    checker.paper_initial_registry(reader, registry, registry["tasks"])
    for row in rows:
        context = contexts.get(row["id"]) if contexts else None
        if context:
            previous_row, document = context["previous_row"], context["previous_document"]
        else:
            previous_row = row
            document = read_pinned(reader, row["specification"], "Current paper definition")
        if previous_row["specification_revision"]["version"] == "paper-improvement/initial-v1":
            checker.paper_initial_members(reader, previous_row, document,
                                          archived_definition_pin=context["previous_pin"] if context else None)
        else:
            checker.paper_revision_members(reader, previous_row, document)


def validate_existing(root=ROOT):
    """Authenticate all existing outcome bindings; return no replacement bytes.

    This API supports the legacy binder's no-downgrade check and small synthetic
    rosters. The registry's complete current paper roster is the coverage unit.
    """
    root = root_path(root)
    reader = checker.Reader(root)
    registry, _ = reader.document(binding.REGISTRY)
    papers = roster(registry)
    read_pin = lambda pin, label: read_pinned(reader, pin, label)
    previous = binding.coverage(registry, read_pin)
    binding.need(previous is not None, "Current paper outcome bindings are required")
    contexts = {}
    for row in papers:
        document = read_pin(row["specification"], "Current paper definition")
        contexts[row["id"]] = binding.context(row, document, previous, read_pin)
    # Use the full preserved registry for original/initial registration checks.
    previous_registry = read_pin(registry["paper_outcomes"]["pre_outcomes_registry"], "Pre-outcomes registry")
    prior_lineage(reader, previous_registry, papers, contexts)
    return {"status": "current", "registered_tasks": len(registry["tasks"]), "paper_tasks": len(papers),
            "scientific_qualification": False, "bytes_read": reader.bytes_read}


def build_outputs(root=ROOT):
    """Validate every supplied contract before returning deterministic outputs."""
    root = root_path(root)
    reader = checker.Reader(root)
    registry_raw, registry_pin = raw(reader, binding.REGISTRY)
    registry = binding.engine().loads_contract(registry_raw.decode("utf-8"))
    papers = roster(registry)
    read_pin = lambda pin, label: read_pinned(reader, pin, label)
    previous = binding.coverage(registry, read_pin)
    already_bound = previous is not None
    if already_bound:
        snapshot_pin = registry["paper_outcomes"]["pre_outcomes_registry"]
        snapshot_raw, observed = raw(reader, binding.SNAPSHOT)
        binding.need(observed == snapshot_pin, "Pre-outcomes snapshot changed during binding")
        snapshot = binding.engine().loads_contract(snapshot_raw.decode("utf-8"))
    else:
        snapshot_raw, snapshot = registry_raw, registry
        snapshot_pin = binding.pin(binding.SNAPSHOT, snapshot_raw)
        previous = binding.PreviousRows((row["id"], row) for row in registry["tasks"])
        if binding.SCOPE_IDS & set(previous) or checker.checked_path(root, binding.SCOPE_PATH, missing=True).exists():
            decision_raw, decision_pin = raw(reader, binding.SCOPE_PATH)
            previous.scope_decisions = binding.scope_decisions(binding.engine().loads_contract(decision_raw.decode("utf-8")))
            previous.scope_pin = decision_pin
        existing = checker.checked_path(root, binding.SNAPSHOT, missing=True)
        if existing.exists():
            old_snapshot, _ = raw(reader, binding.SNAPSHOT)
            binding.need(old_snapshot == snapshot_raw, "Refusing to replace an existing pre-outcomes registry snapshot")
        prior_lineage(reader, registry, papers)
    updated = copy.deepcopy(registry)
    updated_rows = {row["id"]: row for row in updated["tasks"]}
    outputs = {binding.SNAPSHOT: snapshot_raw}
    contexts = {}
    for row in papers:
        identifier, home = row["id"], row["task_directory"]
        prior = previous[identifier]
        improvement_pin = prior["specification_revision"]["improvement_contract"]
        improvement = read_pin(improvement_pin, "Improvement contract")
        if already_bound:
            current = read_pin(row["specification"], "Current paper definition")
            context = binding.context(row, current, previous, read_pin, improvement_contract=improvement)
            contexts[identifier] = context
            archived_raw, archive_pin = raw(reader, home + "/" + binding.HISTORY)
            previous_document = context["previous_document"]
        else:
            archived_raw, current_pin = raw(reader, home + "/task.json")
            binding.need(current_pin == prior["specification"], "Current paper bytes changed before outcome binding")
            previous_document = binding.engine().loads_contract(archived_raw.decode("utf-8"))
            archive_pin = binding.pin(home + "/" + binding.HISTORY, archived_raw)
            archive_path = checker.checked_path(root, archive_pin["path"], missing=True)
            if archive_path.exists():
                existing_archive, _ = raw(reader, archive_pin["path"])
                binding.need(existing_archive == archived_raw, "Refusing to replace a pre-outcomes task archive")
        scopes = previous.scope_decisions
        projected = binding.project_task(previous_document, prior, improvement,
                                         scopes["entries"].get(identifier) if scopes else None)
        current_body = binding.encode(projected)
        current_pin = binding.pin(home + "/task.json", current_body)
        outcomes_raw, outcomes_pin = raw(reader, home + "/" + binding.OUTCOMES)
        outcomes = binding.engine().loads_contract(outcomes_raw.decode("utf-8"))
        binding.need(type(outcomes) is dict, "Supplied paper outcomes must be an object")
        reproduction_pin = None
        reproduction_path = home + "/" + binding.REPRODUCTION
        if outcomes.get("schema_version") != binding.UNAVAILABLE or "reproduction_proposal" in outcomes:
            _, reproduction_pin = raw(reader, reproduction_path)
        else:
            binding.need(not checker.checked_path(root, reproduction_path, missing=True).exists(),
                         "An existing reproduction proposal must be explicitly bound")
        updated_rows[identifier]["specification"] = current_pin
        updated_rows[identifier]["paper_outcomes"] = {
            "schema_version": binding.VERSION, "previous_specification": archive_pin,
            "outcomes": outcomes_pin,
        }
        if reproduction_pin is not None:
            updated_rows[identifier]["paper_outcomes"]["reproduction_contract"] = reproduction_pin
        outputs[archive_pin["path"]] = archived_raw
        outputs[current_pin["path"]] = current_body
        # Only the exact pending immutable archive is read virtually. Scientific
        # sidecars and existing members still use the bounded authenticated reader.
        def planned_read(member_pin, label):
            if member_pin["path"] == archive_pin["path"]:
                binding.need(member_pin == archive_pin, "Pending archive pin mismatch")
                return binding.engine().loads_contract(archived_raw.decode("utf-8"))
            return read_pin(member_pin, label)
        binding.context(updated_rows[identifier], projected, previous, planned_read, improvement_contract=improvement)
    if already_bound:
        prior_lineage(reader, snapshot, papers, contexts)
    updated["paper_outcomes"] = {"schema_version": binding.VERSION, "coverage_required": True,
                                 "registered_count": len(papers), "pre_outcomes_registry": snapshot_pin}
    if previous.scope_pin is not None:
        updated["paper_outcomes"]["scope_decisions"] = previous.scope_pin
    outputs[binding.REGISTRY] = binding.encode(updated)
    for relative in outputs:
        checker.checked_path(root, relative, missing=True)
    return outputs, {"registered_tasks": len(registry["tasks"]), "paper_tasks": len(papers),
                     "scientific_qualification": False, "bytes_read": reader.bytes_read,
                     "input_registry": registry_pin}


def write_or_check(root=ROOT, *, write=False, check=False):
    binding.need(not (write and check), "Choose either write or check")
    root = root_path(root)
    outputs, report = build_outputs(root)
    destination_reader = checker.Reader(root)
    before = {}
    for relative in outputs:
        path = checker.checked_path(root, relative, missing=True)
        before[relative] = raw(destination_reader, relative)[0] if path.exists() else None
    stale = [path for path, body in outputs.items() if before[path] != body]
    if check:
        binding.need(not stale, "Paper outcome bindings are stale or missing: " + ", ".join(stale))
    if write:
        repeated, repeated_report = build_outputs(root)
        report["repeat_preflight_bytes_read"] = repeated_report["bytes_read"]
        binding.need(outputs == repeated, "Outcome binding inputs changed during preflight")
        for relative in outputs:
            path = checker.checked_path(root, relative, missing=True)
            binding.need((raw(destination_reader, relative)[0] if path.exists() else None) == before[relative],
                         "Outcome binding destination changed during preflight: " + relative)
        for relative in stale:
            body, path = outputs[relative], checker.checked_path(root, relative, missing=True)
            path.parent.mkdir(parents=True, exist_ok=True)
            if relative == binding.SNAPSHOT or relative.endswith("/" + binding.HISTORY):
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
    return {**report, "destination_bytes_read": destination_reader.bytes_read,
            "status": "written" if write else "current" if check else "planned",
            "changed_files": len(stale), "changed_paths": stale}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="Apply the fully validated deterministic metadata plan")
    mode.add_argument("--check", action="store_true", help="Require existing bytes to match the validated plan")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(write_or_check(args.root, write=args.write, check=args.check), indent=2))
        return 0
    except (ValueError, KeyError, TypeError, OSError, ImportError) as error:
        print("paper outcome binding refused: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
