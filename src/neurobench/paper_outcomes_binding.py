"""Authenticate one paper task's two declared outcomes without running science.

The registry owns exact current and predecessor bytes.  The original improvement
lineage remains unchanged; the immediately previous current definition is a
separate, immutable predecessor.  The current projection refers to outcome files
by name, so the descriptor may bind its raw task digest without a hash cycle.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import types


VERSION = "paper-outcomes-binding/v1"
OBJECTIVE = "recreate_and_surpass_source_paper_same_task"
HISTORY = "historical/task.pre-outcomes.v1.json"
SNAPSHOT = "docs/provenance/registrations/paper-pre-outcomes-v1.json"
REPRODUCTION = "reproduction.v1.json"
REPRODUCTION_FILES = {"paper-reproduction/v1": REPRODUCTION,
                      "paper-reproduction/v2": "reproduction.v2.json"}
OUTCOMES = "outcomes.v1.json"
REGISTRY = "benchmarks/registry.json"
CONDITIONS = ("paper_data", "paper_data_author_code")
SCOPE_PATH = "docs/provenance/paper-outcome-scope-decisions.v1.json"
SCOPE_VERSION = "paper-outcome-scope-decisions/v1"
UNAVAILABLE = "paper-outcomes-unavailable/v1"
UNAVAILABLE_REASONS = {
    "unavailable_primary_secondary_scope_mismatch": "primary_secondary_scope_mismatch",
    "unavailable_complete_primary_pairing": "full_primary_pairing_unavailable",
}
NORMAL_SCOPE_DISPOSITIONS = frozenset(("same_primary_unqualified", "explicit_primary_selection"))
SCOPE_IDS = frozenset(("PAPER-EXP-20261113-005", "PAPER-FIND-REP-007", "PAPER-FIND-013", "PAPER-CANDIDATE-20261114-PLEXUS"))
SCOPE_ID = re.compile(r"(?:PAPER-[A-Za-z0-9_-]{1,121}|paper-pcca-fa-bilateral-pfc-arousal-2026)\Z")
SHA = re.compile(r"[0-9a-f]{64}\Z")
PRESERVED_ROW_FIELDS = (
    "id", "title", "track", "task_directory", "specification_id", "specification_alias",
    "registration_class", "registration_stage", "registry", "track_source",
    "original_specification", "specification_revision", "paper_improvement",
    "scientific_readiness", "submission_readiness", "declared_specification_status",
)


def need(condition, message):
    if not condition:
        raise ValueError(message)


def encode(value):
    return (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def pin(path, raw):
    return {"path": path, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def require_pin(value, path, label):
    need(type(value) is dict and set(value) == {"path", "bytes", "sha256"}, "Closed " + label + " pin required")
    need(value["path"] == path and type(value["bytes"]) is int and value["bytes"] >= 0
         and type(value["sha256"]) is str and SHA.fullmatch(value["sha256"]), "Invalid " + label + " pin")


def engine(reproduction=None):
    """Load only the two fixed, reviewed framework siblings, including under -I.

    Catalog and source checkers are also loaded as standalone files.  A private
    package permits the reproduction engine's relative import without modifying
    sys.path or importing a task implementation.  Executing source directly avoids
    bytecode writes during metadata-only checks.
    """
    version = "paper-reproduction/v1" if reproduction is None else reproduction.get("schema_version") if type(reproduction) is dict else None
    need(version in ("paper-reproduction/v1", "paper-reproduction/v2"), "Unsupported reproduction contract version")
    target = "paper_reproduction" if version == "paper-reproduction/v1" else "paper_reproduction_v2"
    directory = Path(__file__).resolve().parent
    suffix = hashlib.sha256(str(directory).encode()).hexdigest()[:16]
    package_name = "_neurobench_outcomes_" + suffix
    result_name = package_name + "." + target
    if result_name in sys.modules:
        return sys.modules[result_name]
    package = sys.modules.get(package_name)
    if package is None:
        package = types.ModuleType(package_name)
        package.__package__ = package_name
        package.__path__ = [str(directory)]
        sys.modules[package_name] = package
    created = []
    try:
        for name in ("paper_improvement", "paper_reproduction") + ((target,) if target != "paper_reproduction" else ()):
            if package_name + "." + name in sys.modules:
                continue
            path = directory / (name + ".py")
            need(path.is_file() and not path.is_symlink() and path.stat().st_size <= 1024 * 1024,
                 "Expected bounded framework source: " + name)
            spec = importlib.util.spec_from_file_location(package_name + "." + name, path)
            need(spec is not None, "Cannot load paper framework source")
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            created.append(spec.name)
            exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
            setattr(package, name, module)
    except BaseException:
        for name in created:
            sys.modules.pop(name, None)
        raise
    return sys.modules[result_name]


def project_task(previous, row, improvement, scope_entry=None, *, reproduction_version="paper-reproduction/v1",
                 primary_correction=None):
    """Return the reviewed dual-outcome wording, preserving scientific inputs.

    This projection intentionally does not depend on the reproduction contract or
    descriptor digest.  Scientific targets, admissible observations, resources,
    provenance, original histories and the improvement contract remain intact.
    Outcome-specific findings, tolerances and unresolved gaps live in the two
    contracts, not in invented generic scores here.
    """
    need(type(previous) is dict and type(row) is dict and type(improvement) is dict,
         "Paper projection requires metadata objects")
    identifier = row["id"]
    need(reproduction_version in REPRODUCTION_FILES, "Unsupported reproduction projection version")
    reproduction_file = REPRODUCTION_FILES[reproduction_version]
    need(row.get("track") == "paper" and improvement.get("task_id") == identifier,
         "Paper projection task identity mismatch")
    need(previous.get("objective") == "surpass_source_paper_same_task",
         "Pre-outcomes definition must retain its prior improvement objective")
    result = copy.deepcopy(previous)
    target = improvement["same_task"]["target"]["description"]
    result["objective"] = OBJECTIVE
    result["goal"] = "Recreate the original findings and separately exceed them on the same source-paper task: " + target
    result["status_basis"] = "The retained status describes the improvement contract; reproduction eligibility is separate."
    result["primary_outputs"] = [
        "Reproduction: executable submitted analysis and source-native outputs for the complete original finding and companion panel.",
        "Improvement: candidate outputs and a comparison on the same original task under improvement.v1.json.",
        "Separate evidence for both outcomes under matched paper+data and paper+data+author-code conditions.",
    ]
    result["success_criteria"] = [
        "Assess reproduction and improvement independently under " + reproduction_file + " and improvement.v1.json; do not combine their scores.",
        "Preserve the original task, full panel, permitted observations, metrics, aggregation and required companion controls.",
        "Reproduction requires a source-grounded computation and independently verified granular outputs; copying published findings alone is insufficient.",
        "Improvement requires the unchanged improvement contract's same-task comparison, uncertainty and admission rules.",
        "Use outcomes.v1.json for the matched information conditions and budgets; a declared contract or admitted receipt is not scientific qualification.",
        "Author-baseline replay remains calibration. Historical reconstruction attempts retain their original scope and are not promoted to new qualified AI reproduction results.",
    ]
    result["evaluation"] = {
        "objective": OBJECTIVE,
        "contracts": {"reproduction": reproduction_file, "improvement": "improvement.v1.json"},
        "paired_protocol": OUTCOMES,
        "information_conditions": list(CONDITIONS),
        "outcome_roles": {"reproduction": "first_class_outcome", "improvement": "first_class_outcome"},
        "author_baseline_role": "calibration",
        "executor_ref": None, "scorer_ref": None, "binary_reward_registered": False,
    }
    # Preserve the inherited statements verbatim but scope them explicitly.  In
    # particular, an improvement episode may correctly call reconstruction a
    # calibration; that statement must not become a universal reproduction rule.
    for field in ("episode", "blocking_issues"):
        if field in previous:
            result[field] = {"improvement": copy.deepcopy(previous[field]),
                             "reproduction_contract": reproduction_file,
                             "paired_protocol": OUTCOMES}
    if "next_implementation_action" in previous:
        result["next_implementation_action"] = {
            "improvement": copy.deepcopy(previous["next_implementation_action"]),
            "reproduction": "Resolve the task-specific source and execution gaps declared in " + reproduction_file + ".",
            "paired_access": "Verify the matched information conditions and budgets declared in outcomes.v1.json.",
        }
    if "holds" in previous:
        result["holds"] = {
            "preserved_limits": copy.deepcopy(previous["holds"]),
            "interpretation": "Source, observation, exposure and execution limits remain in force. Improvement-only criteria apply only to improvement; reproduction-specific gaps are declared in " + reproduction_file + ".",
            "reproduction_contract": reproduction_file,
        }
    if type(result.get("admission")) is dict:
        result["admission"]["delivery_unit"] = "one_registered_paper_task_two_independent_outcomes"
        result["admission"]["reason"] = "Source definitions and binding metadata do not establish execution or either scientific outcome."
    need(scope_entry is None or primary_correction is None, "A task cannot have both scope correction routes")
    if primary_correction is not None:
        need(primary_correction["task_id"] == identifier
             and primary_correction["disposition"] in NORMAL_SCOPE_DISPOSITIONS
             and (primary_correction["disposition"] != "explicit_primary_selection"
                  or primary_correction.get("adoption_route") == "normal_same_primary_unqualified"),
             "Unexpected same-primary correction")
        result["goal"] = primary_correction["primary_goal"]
        result["primary_scope"] = primary_correction["primary_scope"]
        result["scope_decision"] = {"path": SCOPE_PATH, "task_entry_id": identifier}
        result["source_scope_correction"] = {
            "disposition": "same_primary_unqualified",
            "retained_scope_notes": primary_correction.get("retained_secondary_scope"),
            "retained_source_roles": copy.deepcopy(primary_correction.get("retained_source_roles")),
            "remaining_source_limits": copy.deepcopy(primary_correction["remaining_source_limits"]),
            "scientific_outcome": "unknown",
        }
        if primary_correction["disposition"] == "explicit_primary_selection":
            result["source_scope_correction"]["source_disposition"] = "explicit_primary_selection"
        result["success_criteria"].append(
            "Apply the reviewed same-primary scope correction. A partial component or a prospective extension cannot alone establish the complete primary result; unchanged improvement criteria still apply.")
        result["evaluation"]["scope_disposition"] = "same_primary_unqualified"
        if type(result.get("holds")) is dict:
            result["holds"]["current_primary_source_limits"] = copy.deepcopy(primary_correction["remaining_source_limits"])
            result["holds"]["scope_correction_limit"] = "This scope correction grants no new observation access and changes no improvement metric, criterion or tolerance."
    if scope_entry is not None:
        need(scope_entry["task_id"] == identifier, "Unexpected primary scope correction")
        result["goal"] = scope_entry["primary_goal"]
        result["primary_scope"] = scope_entry["primary_scope"]
        result["retained_secondary_scope"] = scope_entry["retained_secondary_scope"]
        result["scope_decision"] = {"path": SCOPE_PATH, "task_entry_id": identifier}
        result["status_basis"] = "The retained status describes the preserved secondary improvement contract. Primary reproduction and same-result improvement require their own source-grounded eligibility decisions."
        result["primary_outputs"] = [
            "Reproduction: executable analysis and source-native outputs for the corrected primary empirical findings: " + scope_entry["primary_scope"],
            "Primary improvement: unavailable until a source-grounded same-result comparison is independently justified; no new score or direction is implied.",
            "Retained secondary work: " + scope_entry["retained_secondary_scope"],
        ]
        result["success_criteria"] = [
            "Recreate the corrected primary empirical findings with their source-defined populations, complete required panels and controls.",
            "Use an explicitly bound reproduction proposal only within its declared eligibility, comparison and execution limits; copying published findings is insufficient.",
            "The preserved improvement.v1.json retains its declared comparison and coverage. Use retained_secondary_scope for its relationship to the corrected primary findings; satisfying a secondary or partial-component criterion alone does not establish complete primary reproduction or improvement.",
            "The primary same-target outcome bundle is unavailable. Any primary improvement requires an independently justified source-grounded comparison; no replacement metric, direction or tolerance is invented.",
            "Keep the paper+data and paper+data+author-code outcomes separate. All scientific outcomes remain unknown until qualifying original-data execution and independent verification.",
            "Preserve prior task definitions, improvement criteria and useful secondary implementations with their original scopes. Historical attempts and source metadata do not become qualified AI results.",
        ]
        result["evaluation"]["contracts"] = {"reproduction": None, "improvement": None}
        result["evaluation"]["reproduction_proposal"] = "Only a proposal explicitly bound in outcomes.v1.json is adopted."
        result["evaluation"]["retained_secondary_improvement"] = "improvement.v1.json"
        result["evaluation"]["primary_bundle_status"] = scope_entry["paired_bundle_status"]
        if scope_entry["paired_bundle_status"] == "unavailable_complete_primary_pairing":
            result["status_basis"] = "The retained status describes the preserved improvement contract and its declared coverage. Complete primary reproduction and same-result improvement require their own source-grounded eligibility decisions."
            result["primary_outputs"][2] = "Retained source work: " + scope_entry["retained_secondary_scope"]
            result["success_criteria"][5] = "Preserve prior task definitions, improvement criteria and useful retained implementations with their declared coverage. Historical attempts and source metadata do not become qualified AI results."
        for field in ("episode", "blocking_issues"):
            if field in previous:
                result[field] = {"retained_secondary_improvement": copy.deepcopy(previous[field]),
                                 "primary_source_limits": copy.deepcopy(scope_entry["remaining_source_limits"]),
                                 "outcome_availability": OUTCOMES}
        if "next_implementation_action" in previous:
            result["next_implementation_action"] = {
                "retained_secondary_improvement": copy.deepcopy(previous["next_implementation_action"]),
                "primary": "Resolve the corrected primary source limits and establish a source-grounded reproduction interface; separately justify any primary improvement comparison.",
            }
        if "holds" in previous:
            result["holds"] = {"preserved_predecessor_limits": copy.deepcopy(previous["holds"]),
                               "interpretation": "Preserved source, observation, exposure and execution restrictions apply within their retained scope. Secondary or partial-component criteria cannot, alone, qualify or redefine the complete corrected primary findings; retain the exact relationship and coverage stated in retained_secondary_scope.",
                               "primary_source_limits": copy.deepcopy(scope_entry["remaining_source_limits"])}
    return result


class PreviousRows(dict):
    """An authenticated prior roster with separately pinned scope decisions."""
    scope_decisions = None
    scope_pin = None


def read_reproduction(member_pin, home, read_pin):
    """Admit only a fixed filename whose declared schema version agrees."""
    need(type(member_pin) is dict and member_pin.get("path") in
         {home + "/" + filename for filename in REPRODUCTION_FILES.values()},
         "Expected an explicit versioned reproduction filename")
    require_pin(member_pin, member_pin["path"], "reproduction contract")
    document = read_pin(member_pin, "Reproduction contract")
    need(type(document) is dict and document.get("schema_version") in REPRODUCTION_FILES,
         "Unsupported reproduction contract version")
    need(member_pin["path"] == home + "/" + REPRODUCTION_FILES[document["schema_version"]],
         "Reproduction filename must match its declared schema version")
    return document


def scope_decisions(value):
    need(type(value) is dict and value.get("schema_version") == SCOPE_VERSION,
         "Invalid paper scope-decision artifact")
    entries = value.get("entries")
    need(type(entries) is dict and SCOPE_IDS <= set(entries) and len(entries) <= 1000
         and all(type(identifier) is str and SCOPE_ID.fullmatch(identifier) for identifier in entries),
         "Scope decision must retain the adjudicated tasks and explicit bounded paper identities")
    for identifier, entry in entries.items():
        need(type(entry) is dict and entry.get("task_id") == identifier, "Invalid scope-decision task identity")
        need(entry.get("projection_action", "revise_primary_scope") == "revise_primary_scope",
             "A passive scope confirmation cannot be an active correction")
        need(entry.get("adoption_route", "full_primary_pairing_unavailable") == "full_primary_pairing_unavailable",
             "Scope decision adoption route differs from its unavailable map")
        need(entry.get("paired_bundle_status") != "unavailable_complete_primary_pairing"
             or entry.get("adoption_route") == "full_primary_pairing_unavailable",
             "Neutral full-primary unavailability requires an explicit reviewed route")
        for field in ("primary_goal", "primary_scope", "retained_secondary_scope"):
            need(type(entry.get(field)) is str and bool(entry[field].strip()), "Missing source-grounded scope field: " + field)
        need(type(entry.get("remaining_source_limits")) is list and all(type(item) is str and item.strip() for item in entry["remaining_source_limits"]), "Invalid remaining source limits")
        need(entry.get("primary_same_task_improvement") == "unavailable_until_independently_justified"
             and entry.get("paired_bundle_status") in UNAVAILABLE_REASONS
             and entry.get("scientific_outcome") == "unknown", "Scope decisions cannot qualify a primary outcome")
    corrections = value.get("same_primary_corrections", {})
    need(type(corrections) is dict and len(entries) + len(corrections) <= 1000
         and not (set(entries) & set(corrections)), "Primary correction routes must be bounded and disjoint")
    for identifier, entry in corrections.items():
        need(type(identifier) is str and SCOPE_ID.fullmatch(identifier)
             and type(entry) is dict and entry.get("task_id") == identifier, "Invalid same-primary correction identity")
        need(entry.get("projection_action", "revise_primary_scope") == "revise_primary_scope",
             "A passive scope confirmation cannot be an active correction")
        need(entry.get("adoption_route", "normal_same_primary_unqualified") == "normal_same_primary_unqualified",
             "Scope decision adoption route differs from its normal correction map")
        for field in ("primary_goal", "primary_scope"):
            need(type(entry.get(field)) is str and bool(entry[field].strip()), "Missing same-primary source field: " + field)
        need(type(entry.get("remaining_source_limits")) is list
             and all(type(item) is str and item.strip() for item in entry["remaining_source_limits"]),
             "Invalid same-primary source limits")
        need(entry.get("disposition") in NORMAL_SCOPE_DISPOSITIONS
             and entry.get("paired_bundle_status") == "same_primary_unqualified"
             and entry.get("scientific_outcome") == "unknown", "Same-primary correction cannot qualify an outcome")
        need(entry.get("disposition") != "explicit_primary_selection"
             or entry.get("adoption_route") == "normal_same_primary_unqualified",
             "Explicit primary selection requires an explicit reviewed normal route")
        notes, roles = entry.get("retained_secondary_scope"), entry.get("retained_source_roles")
        need(notes is None or type(notes) is str and bool(notes.strip()), "Invalid retained source scope notes")
        need(roles is None or type(roles) in (dict, list), "Invalid retained source roles")
    confirmations = value.get("source_gap_confirmations", {})
    need(type(confirmations) is dict and len(entries) + len(corrections) + len(confirmations) <= 1000
         and not ((set(entries) | set(corrections)) & set(confirmations)),
         "Passive confirmations must be bounded and separate from scope corrections")
    for identifier, entry in confirmations.items():
        need(type(identifier) is str and SCOPE_ID.fullmatch(identifier)
             and type(entry) is dict and entry.get("task_id") == identifier
             and entry.get("projection_action") == "none"
             and entry.get("adoption_route", "source_gap_confirmation") == "source_gap_confirmation"
             and entry.get("scientific_outcome", "unknown") == "unknown",
             "Invalid passive source-gap confirmation")
    return value


def coverage(registry, read_pin):
    """Authenticate coverage and immutable prior rows using bounded caller I/O.

    ``read_pin(pin, label)`` must authenticate all raw bytes against the exact
    closed pin and return a strict JSON object.  It must not follow evidence URLs
    or implementation entrypoints.  No registration count is manufactured here.
    """
    rows = registry.get("tasks")
    need(type(rows) is list and all(type(row) is dict for row in rows), "Invalid task roster for paper outcomes")
    meta = registry.get("paper_outcomes")
    if meta is None:
        need(not any("paper_outcomes" in row for row in rows), "Paper outcome rows require coverage metadata")
        return None
    base_keys = {"schema_version", "coverage_required", "registered_count", "pre_outcomes_registry"}
    need(type(meta) is dict and set(meta) in (base_keys, base_keys | {"scope_decisions"})
         and meta["schema_version"] == VERSION and meta["coverage_required"] is True
         and type(meta["registered_count"]) is int,
         "Invalid paper outcome coverage metadata")
    papers = [row for row in rows if row.get("track") == "paper"]
    need(meta["registered_count"] == len(papers) and len(papers) > 0,
         "Paper outcome coverage count differs from registered paper tasks")
    require_pin(meta["pre_outcomes_registry"], SNAPSHOT, "pre-outcomes registry")
    previous = read_pin(meta["pre_outcomes_registry"], "Pre-outcomes registry")
    need(type(previous) is dict and previous.get("schema_version") == 1
         and previous.get("kind") == "neuroscience_benchmark_registry" and "paper_outcomes" not in previous,
         "Invalid pre-outcomes registry snapshot")
    old_rows = previous.get("tasks")
    need(type(old_rows) is list and all(type(row) is dict and type(row.get("id")) is str for row in old_rows),
         "Invalid pre-outcomes task roster")
    old = PreviousRows((row["id"], row) for row in old_rows)
    current = {row["id"]: row for row in rows}
    need(len(old) == len(old_rows) and len(current) == len(rows)
         and set(old) <= set(current), "Paper outcome binding cannot replace prior task identities")
    old_paper = {identifier for identifier, row in old.items() if row.get("track") == "paper"}
    need(old_paper == {row["id"] for row in papers}, "Paper outcome binding must preserve the entire prior paper roster")
    need(not (SCOPE_IDS & old_paper) or "scope_decisions" in meta, "Corrected primary tasks require their exact public scope decisions")
    if "scope_decisions" in meta:
        require_pin(meta["scope_decisions"], SCOPE_PATH, "scope decisions")
        old.scope_decisions = scope_decisions(read_pin(meta["scope_decisions"], "Paper scope decisions"))
        old.scope_pin = meta["scope_decisions"]
        referenced = (set(old.scope_decisions["entries"]) | set(old.scope_decisions.get("same_primary_corrections", {}))
                      | set(old.scope_decisions.get("source_gap_confirmations", {})))
        need(bool(referenced & old_paper), "Scope decisions must apply to registered paper tasks")
    need(all("paper_outcomes" in row for row in papers)
         and all("paper_outcomes" not in row for row in rows if row.get("track") != "paper"),
         "Paper outcome binding requires exactly every registered paper task")
    for row in papers:
        prior = old[row["id"]]
        need("paper_outcomes" not in prior, "Pre-outcomes row must precede outcome adoption")
        for field in PRESERVED_ROW_FIELDS:
            need((field in row) == (field in prior) and encode(row.get(field)) == encode(prior.get(field)),
                 "Paper outcome binding changed prior " + field + ": " + row["id"])
    return old


def unavailable_summary(identifier):
    return {"task_id": identifier, "task_count": 1, "errors": [],
            "assurance": engine().ASSURANCE,
            "paired_metadata_admitted": {outcome: False for outcome in ("reproduction", "improvement")},
            "cells": [{"outcome": outcome, "condition": condition,
                       "eligibility": "unavailable", "endpoint_eligible": False,
                       "pairing_status": "unavailable", "condition_available": False,
                       "scientific_outcome": "unknown", "receipt": None}
                      for outcome in ("reproduction", "improvement") for condition in CONDITIONS]}


def validate_unavailable(outcomes, reproduction, improvement, row, previous_rows):
    """Authenticate full-primary unavailability without admitting a result."""
    keys = {"schema_version", "task_id", "original_task_sha256", "status", "reason_code", "reason",
            "primary_scope", "retained_secondary_improvement", "root_scope_decision"}
    need(type(outcomes) is dict and set(outcomes) in (keys, keys | {"reproduction_proposal"})
         and outcomes.get("schema_version") == UNAVAILABLE, "Invalid unavailable outcome marker")
    identifier, home = row["id"], row["task_directory"]
    need(getattr(previous_rows, "scope_decisions", None) is not None
         and identifier in previous_rows.scope_decisions["entries"],
         "Unavailable primary scope requires a registered source decision")
    entry = previous_rows.scope_decisions["entries"][identifier]
    need(outcomes["task_id"] == identifier and outcomes["original_task_sha256"] == row["specification"]["sha256"]
         and outcomes["status"] == "unavailable"
         and outcomes["reason_code"] == UNAVAILABLE_REASONS[entry["paired_bundle_status"]]
         and type(outcomes["reason"]) is str and bool(outcomes["reason"].strip())
         and outcomes["primary_scope"] == entry["primary_scope"], "Unavailable marker does not bind its corrected primary scope")
    need(outcomes["root_scope_decision"] == {"path": SCOPE_PATH, "raw_sha256": previous_rows.scope_pin["sha256"],
                                            "task_entry_id": identifier}, "Unavailable marker scope decision mismatch")
    module = engine()
    errors = module.improvement.contract_validate(improvement, task_id=identifier)
    need(not errors, "Invalid retained secondary improvement: " + "; ".join(errors))
    need(outcomes["retained_secondary_improvement"] == {
        "path": "improvement.v1.json", "raw_sha256": row["specification_revision"]["improvement_contract"]["sha256"],
        "contract_digest": module.contract_digest(improvement), "scope_description": entry["retained_secondary_scope"]},
        "Unavailable marker changed the retained secondary contract or scope")
    reproduction_pin = row["paper_outcomes"].get("reproduction_contract")
    need((reproduction is not None) == ("reproduction_proposal" in outcomes) == (reproduction_pin is not None),
         "Unavailable reproduction proposal must be explicitly and exactly bound")
    if reproduction is not None:
        errors = engine(reproduction).contract_validate(reproduction, task_id=identifier)
        need(not errors, "Invalid primary reproduction proposal: " + "; ".join(errors))
        need(reproduction["same_task"]["target"]["description"] == entry["primary_scope"],
             "Reproduction proposal target must match the corrected primary scope")
        need(reproduction["source_paper"]["url"] == improvement["source_paper"]["url"],
             "Primary reproduction proposal must retain its source paper identity")
        need(outcomes["reproduction_proposal"] == {"path": REPRODUCTION_FILES[reproduction["schema_version"]], "raw_sha256": reproduction_pin["sha256"],
                                                   "contract_digest": module.contract_digest(reproduction)},
             "Unavailable reproduction proposal identity mismatch")
    return unavailable_summary(identifier)


def context(row, document, previous_rows, read_pin, *, improvement_contract=None):
    """Validate current bytes and return prior lineage plus separate outcomes.

    Existing initial/historical lineage validators should receive previous_row
    and previous_document.  The exact prior current file is independently pinned
    at previous_pin; no current-path alias is used to impersonate old bytes.
    """
    if previous_rows is None:
        need("paper_outcomes" not in row and document.get("objective") != OBJECTIVE,
             "Unbound dual-outcome definition")
        return None
    if row.get("track") != "paper":
        need("paper_outcomes" not in row, "Neural task cannot carry paper outcome bindings")
        return None
    identifier, home = row["id"], row["task_directory"]
    need(home == "benchmarks/paper/" + identifier, "Paper outcome task home mismatch")
    binding = row.get("paper_outcomes")
    base_keys = {"schema_version", "previous_specification", "outcomes"}
    need(type(binding) is dict and set(binding) in (base_keys, base_keys | {"reproduction_contract"})
         and binding["schema_version"] == VERSION, "Invalid paper outcome task binding")
    prior = previous_rows[identifier]
    previous_pin = binding["previous_specification"]
    require_pin(previous_pin, home + "/" + HISTORY, "pre-outcomes definition")
    need(all(previous_pin[key] == prior["specification"][key] for key in ("bytes", "sha256")),
         "Pre-outcomes definition differs from immutable prior registry")
    previous_document = read_pin(previous_pin, "Pre-outcomes definition")
    improvement_pin = row["specification_revision"]["improvement_contract"]
    require_pin(improvement_pin, home + "/improvement.v1.json", "improvement contract")
    improvement = improvement_contract if improvement_contract is not None else read_pin(improvement_pin, "Improvement contract")
    scope = getattr(previous_rows, "scope_decisions", None)
    scope_entry = scope["entries"].get(identifier) if scope else None
    primary_correction = scope.get("same_primary_corrections", {}).get(identifier) if scope else None
    reproduction = read_reproduction(binding["reproduction_contract"], home, read_pin) if "reproduction_contract" in binding else None
    projected = project_task(previous_document, prior, improvement, scope_entry,
                             reproduction_version=reproduction["schema_version"] if reproduction is not None else "paper-reproduction/v1",
                             primary_correction=primary_correction)
    expected_current = pin(home + "/task.json", encode(projected))
    need(document == projected and row.get("specification") == expected_current,
         "Current paper definition differs from the deterministic dual-outcome projection")
    require_pin(binding["outcomes"], home + "/" + OUTCOMES, "paper outcomes")
    outcomes = read_pin(binding["outcomes"], "Paper outcomes")
    need(type(outcomes) is dict, "Paper outcomes must be an object")
    members = {previous_pin["path"], binding["outcomes"]["path"]}
    if "reproduction_contract" in binding:
        members.add(binding["reproduction_contract"]["path"])
    unavailable = outcomes.get("schema_version") == UNAVAILABLE
    need(unavailable == (scope_entry is not None), "Corrected primary scopes cannot use a mixed-scope normal outcome bundle")
    if unavailable:
        result = validate_unavailable(outcomes, reproduction, improvement, row, previous_rows)
    else:
        need(reproduction is not None, "Normal paper outcomes require a reproduction contract")
        module = engine(reproduction)
        errors = module.outcomes_validate(outcomes, reproduction, improvement)
        need(not errors, "Invalid paper outcome contracts for " + identifier + ": " + "; ".join(errors))
        need(outcomes["task_id"] == identifier and outcomes["original_task_sha256"] == expected_current["sha256"],
             "Paper outcomes must bind the raw current task identity")
        if primary_correction is not None:
            need(reproduction["eligibility"] == "source_unresolved"
                 and improvement["disposition"] != "improvement_ready",
                 "Reviewed same-primary correction retains unresolved source eligibility")
        result = module.summary(outcomes, reproduction, improvement)
    need(not result["errors"] and result["task_count"] == 1,
         "Invalid independent paper outcome summary")
    return {"previous_row": prior, "previous_document": previous_document, "previous_pin": previous_pin,
            "improvement_contract": improvement, "reproduction_contract": reproduction,
            "outcomes": outcomes, "summary": result, "availability": "unavailable" if unavailable else "available",
            "primary_scope_correction": primary_correction,
            "scope_decision_pin": getattr(previous_rows, "scope_pin", None),
            "members": members}


def public_primary_scope_correction(entry, scope_pin, task_id):
    """Project an authenticated scope entry without adding scientific claims."""
    result = {
        "disposition": "same_primary_unqualified", "primary_goal": entry["primary_goal"],
        "primary_scope": entry["primary_scope"],
        "remaining_source_limits": copy.deepcopy(entry["remaining_source_limits"]),
        "retained_scope_notes": entry.get("retained_secondary_scope"),
        "retained_source_roles": copy.deepcopy(entry.get("retained_source_roles")),
        "root_scope_decision": {"path": SCOPE_PATH, "raw_sha256": scope_pin["sha256"],
                                "task_entry_id": task_id},
        "scientific_outcome": "unknown",
    }
    if entry["disposition"] == "explicit_primary_selection":
        result["source_disposition"] = "explicit_primary_selection"
    return result


def public_summary(row, bound):
    """Expose declarations without treating metadata consistency as performance."""
    binding = row["paper_outcomes"]
    reproduction = bound["reproduction_contract"]
    result = {"schema_version": VERSION, "objective": OBJECTIVE,
            "availability": bound["availability"],
            "previous_specification": copy.deepcopy(binding["previous_specification"]),
            "reproduction_contract": copy.deepcopy(binding.get("reproduction_contract")),
            "improvement_contract": copy.deepcopy(row["specification_revision"]["improvement_contract"]),
            "outcomes": copy.deepcopy(binding["outcomes"]),
            "reproduction_eligibility": reproduction["eligibility"] if reproduction is not None else None,
            "reproduction_blocking_issues": copy.deepcopy(reproduction["blocking_issues"]) if reproduction is not None else [],
            "cells": copy.deepcopy(bound["summary"]["cells"]),
            "scientific_outcomes": {"reproduction": "unknown", "improvement": "unknown"},
            "assurance": bound["summary"]["assurance"]}
    if bound["availability"] == "unavailable":
        for field in ("reason_code", "reason", "primary_scope", "retained_secondary_improvement", "root_scope_decision"):
            result[field] = copy.deepcopy(bound["outcomes"][field])
    correction = bound.get("primary_scope_correction")
    if correction is not None:
        result["primary_scope_correction"] = public_primary_scope_correction(
            correction, bound["scope_decision_pin"], row["id"])
    return result
