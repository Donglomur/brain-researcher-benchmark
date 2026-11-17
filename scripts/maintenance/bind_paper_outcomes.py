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


def gap_sidecars_absent(root, row):
    """An explicit missing-contract route cannot adopt physical substitutes."""
    if row["id"] in binding.SOURCE_DECLARATION_GAP_IDS:
        for filename in (*binding.REPRODUCTION_FILES.values(), binding.OUTCOMES):
            path = checker.checked_path(root, row["task_directory"] + "/" + filename, missing=True)
            binding.need(not path.exists(), "Source declaration gap cannot contain reproduction or outcomes sidecars")


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


def snapshot_enrollment(registry, snapshot_pin, *, add=False):
    """Enroll the exact snapshot once without replacing any historical record."""
    history = registry.get("historical_registries", [])
    binding.need(type(history) is list and all(type(item) is dict for item in history),
                 "Invalid pre-outcomes snapshot enrollment inventory")
    existing = [item for item in history if item.get("path") == binding.SNAPSHOT]
    binding.need(len(existing) <= 1, "Duplicate pre-outcomes snapshot enrollment")
    if existing:
        binding.require_pin(existing[0], binding.SNAPSHOT, "enrolled pre-outcomes snapshot")
        binding.need(existing[0] == snapshot_pin, "Conflicting pre-outcomes snapshot enrollment")
    else:
        binding.need(add, "Missing pre-outcomes snapshot enrollment")
        registry.setdefault("historical_registries", []).append(copy.deepcopy(snapshot_pin))


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
    snapshot_enrollment(registry, registry["paper_outcomes"]["pre_outcomes_registry"])
    contexts = {}
    for row in papers:
        gap_sidecars_absent(root, row)
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
        if (binding.SOURCE_DECLARATION_GAP_IDS & {row["id"] for row in papers}
                or checker.checked_path(root, binding.SOURCE_DECLARATION_GAP_PATH, missing=True).exists()):
            binding.bind_source_declaration_gaps(previous, binding.SOURCE_DECLARATION_GAP_PIN, read_pin)
        existing = checker.checked_path(root, binding.SNAPSHOT, missing=True)
        if existing.exists():
            old_snapshot, _ = raw(reader, binding.SNAPSHOT)
            binding.need(old_snapshot == snapshot_raw, "Refusing to replace an existing pre-outcomes registry snapshot")
        prior_lineage(reader, registry, papers)
    updated = copy.deepcopy(registry)
    snapshot_enrollment(updated, snapshot_pin, add=True)
    updated_rows = {row["id"]: row for row in updated["tasks"]}
    outputs = {binding.SNAPSHOT: snapshot_raw}
    contexts = {}
    for row in papers:
        identifier, home = row["id"], row["task_directory"]
        gap_sidecars_absent(root, row)
        prior = previous[identifier]
        improvement_pin = prior["specification_revision"]["improvement_contract"]
        improvement = read_pin(improvement_pin, "Improvement contract")
        archive_pending = False
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
            archive_pending = not archive_path.exists()
            if not archive_pending:
                existing_archive, _ = raw(reader, archive_pin["path"])
                binding.need(existing_archive == archived_raw, "Refusing to replace a pre-outcomes task archive")
        # A prospective successor must authenticate its immutable predecessor
        # before that archive is written. No other member may be read virtually.
        def planned_read(member_pin, label):
            if archive_pending and member_pin["path"] == archive_pin["path"]:
                binding.need(member_pin == archive_pin, "Pending archive pin mismatch")
                return binding.engine().loads_contract(archived_raw.decode("utf-8"))
            return read_pin(member_pin, label)
        scopes = previous.scope_decisions
        if identifier in binding.SOURCE_DECLARATION_GAP_IDS:
            # Explicit, reviewed documentary absence is distinct from a normal
            # bundle or a scope mismatch. No missing contract is manufactured.
            module = binding.declaration_gap_module()
            record_pin = previous.source_declaration_gap_pin
            binding.need(record_pin is not None, "Source declaration gap record is required before adoption")
            handle = module.authenticate(record_pin, prior, archive_pin, planned_read,
                                         improvement_contract=improvement)
            captured = handle.snapshot()
            projected = module.project(binding.project_task(captured["previous_task"], prior,
                                                            captured["improvement_contract"]), handle)
            new_binding = {"schema_version": binding.VERSION, "previous_specification": archive_pin,
                           "source_declaration_gap": copy.deepcopy(record_pin)}
            current_body = binding.encode(projected)
            current_pin = binding.pin(home + "/task.json", current_body)
            updated_rows[identifier]["specification"] = current_pin
            updated_rows[identifier]["paper_outcomes"] = new_binding
            outputs[archive_pin["path"]] = archived_raw
            outputs[current_pin["path"]] = current_body
            binding.context(updated_rows[identifier], projected, previous, planned_read, improvement_contract=improvement)
            continue
        outcomes_raw, outcomes_pin = raw(reader, home + "/" + binding.OUTCOMES)
        outcomes = binding.engine().loads_contract(outcomes_raw.decode("utf-8"))
        binding.need(type(outcomes) is dict, "Supplied paper outcomes must be an object")
        reproduction_pin = None
        reproduction = None
        if already_bound:
            selected = row["paper_outcomes"].get("reproduction_contract")
            reproduction_paths = [selected["path"]] if selected is not None else []
        else:
            reproduction_paths = [home + "/" + filename for filename in binding.REPRODUCTION_FILES.values()
                                  if checker.checked_path(root, home + "/" + filename, missing=True).exists()]
        if outcomes.get("schema_version") != binding.UNAVAILABLE or "reproduction_proposal" in outcomes:
            binding.need(len(reproduction_paths) == 1, "Exactly one explicit versioned reproduction contract is required")
            _, reproduction_pin = raw(reader, reproduction_paths[0])
            reproduction = binding.read_reproduction(reproduction_pin, home, read_pin)
        else:
            binding.need(not reproduction_paths,
                         "An existing reproduction proposal must be explicitly bound")
        new_binding = {"schema_version": binding.VERSION, "previous_specification": archive_pin,
                       "outcomes": outcomes_pin}
        if reproduction_pin is not None:
            new_binding["reproduction_contract"] = reproduction_pin
        selected_improvement = improvement
        successor = None
        if identifier == binding.PRIMARY_SUCCESSOR_TASK:
            # This one adopted task requires the reviewed offline policy. Missing
            # descriptors or policies fail; the old policy is never a fallback.
            module = binding.primary_successor_module()
            if already_bound:
                selected = row["paper_outcomes"]
                revision_pin = selected["primary_policy_revision"]
                primary_pin = selected["primary_improvement_contract"]
            else:
                _, revision_pin = raw(reader, module.DESCRIPTOR)
                _, primary_pin = raw(reader, home + "/improvement.temporal-scope.v1.json")
            new_binding.update(primary_policy_revision=revision_pin, primary_improvement_contract=primary_pin)
            binding.has_primary_successor({**row, "paper_outcomes": new_binding})
            binding.need(not scopes or (identifier not in scopes["entries"]
                         and identifier not in scopes.get("same_primary_corrections", {})),
                         "SMC temporal successor cannot combine another primary scope projection")
            successor = module.authenticate(revision_pin=revision_pin, primary_pin=primary_pin,
                reproduction_pin=reproduction_pin, previous_pin=archive_pin,
                retained_improvement_pin=improvement_pin, read_pin=planned_read)
            binding.need(binding.engine().contract_digest(improvement) == binding.engine().contract_digest(successor.retained_improvement),
                         "Retained improvement differs from authenticated SMC lineage")
            selected_improvement = successor.primary_improvement
        projected = binding.project_task(previous_document, prior, selected_improvement,
                                         scopes["entries"].get(identifier) if scopes else None,
                                         reproduction_version=reproduction["schema_version"] if reproduction is not None else "paper-reproduction/v1",
                                         primary_correction=scopes.get("same_primary_corrections", {}).get(identifier) if scopes else None)
        if successor is not None:
            projected = module.project(projected, successor)
            updated_rows[identifier]["title"] = projected["title"]
        current_body = binding.encode(projected)
        current_pin = binding.pin(home + "/task.json", current_body)
        updated_rows[identifier]["specification"] = current_pin
        updated_rows[identifier]["paper_outcomes"] = new_binding
        outputs[archive_pin["path"]] = archived_raw
        outputs[current_pin["path"]] = current_body
        binding.context(updated_rows[identifier], projected, previous, planned_read, improvement_contract=improvement)
    if already_bound:
        prior_lineage(reader, snapshot, papers, contexts)
    updated["paper_outcomes"] = {"schema_version": binding.VERSION, "coverage_required": True,
                                 "registered_count": len(papers), "pre_outcomes_registry": snapshot_pin}
    if previous.scope_pin is not None:
        updated["paper_outcomes"]["scope_decisions"] = previous.scope_pin
    if previous.source_declaration_gap_pin is not None:
        updated["paper_outcomes"]["source_declaration_gaps"] = previous.source_declaration_gap_pin
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
