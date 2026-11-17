"""Authenticate missing paper declarations without fabricating scientific contracts.

Only explicit pinned JSON metadata is read through the caller's bounded reader.
Documentary assessment locators are never followed. Original lineage and the
retained improvement contract's semantic validation remain the caller's duties.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import PurePosixPath
import re


VERSION = "paper-outcome-source-declaration-gaps/v1"
PATH = "docs/provenance/paper-outcome-source-declaration-gaps.v1.json"
TASK_IDS = frozenset(("PAPER-paper-method-011", "PAPER-paper-method-replacement-009"))
NAMESPACE = "retained-engineering-evidence/comprehensive-revision-20261116-v2"
HISTORY = "historical/task.pre-outcomes.v1.json"
OBJECTIVE = "recreate_and_surpass_source_paper_same_task"
OLD_OBJECTIVE = "surpass_source_paper_same_task"
CONDITIONS = ("paper_data", "paper_data_author_code")
ANCHORS = ("target", "dataset", "cohort", "split", "inputs", "preprocessing", "metric", "aggregation")
MAX_RECORD_BYTES = 128 * 1024
MAX_MEMBER_BYTES = 8 * 1024 * 1024
SHA = re.compile(r"[0-9a-f]{64}\Z")
COMMIT = re.compile(r"[0-9a-f]{40}\Z")
_TOKEN = object()
_GENERIC_FIELDS = frozenset(("objective", "goal", "status_basis", "primary_outputs", "success_criteria",
                             "evaluation", "episode", "blocking_issues", "next_implementation_action",
                             "holds", "admission"))


def need(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, RecursionError, UnicodeError) as error:
        raise ValueError("Finite bounded JSON metadata required") from error


def contract_digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def closed(value, keys, label):
    need(type(value) is dict and set(value) == set(keys), "Closed " + label + " object required")


def text(value, label, *, maximum=16384):
    need(type(value) is str and bool(value.strip()) and len(value) <= maximum
         and not any(ord(char) < 32 and char not in "\n\r\t" for char in value), "Invalid " + label)


def texts(value, label, *, maximum=64):
    need(type(value) is list and 0 < len(value) <= maximum, "Invalid " + label)
    for item in value:
        text(item, label)


def safe_documentary_path(value):
    text(value, "documentary path", maximum=1024)
    need(value.startswith("dual-outcomes/") and not value.startswith("/")
         and "\\" not in value and all(ord(char) >= 32 for char in value)
         and all(part not in ("", ".", "..") for part in value.split("/"))
         and PurePosixPath(value).as_posix() == value, "Unsafe documentary assessment path")


def require_pin(value, expected_path, label, *, maximum=MAX_MEMBER_BYTES):
    closed(value, ("path", "bytes", "sha256"), label + " pin")
    need(value["path"] == expected_path and type(value["bytes"]) is int and 0 < value["bytes"] <= maximum
         and type(value["sha256"]) is str and SHA.fullmatch(value["sha256"]), "Invalid " + label + " pin")


def _provenance(value, assessments):
    closed(value, ("primary_scope", "predecessor_pin_role", "preserved_source_scope", "source_paper",
                   "same_task_anchor_descriptions", "structured_representation_status", "assessment_roles",
                   "outcome_availability", "scientific_cells", "scope_revision",
                   "primary_secondary_scope_mismatch", "core_two_outcome_completion", "future_recovery"),
           "source-declaration provenance")
    for field in ("primary_scope", "predecessor_pin_role", "preserved_source_scope",
                  "structured_representation_status", "future_recovery"):
        text(value[field], field)
    source = value["source_paper"]
    closed(source, ("title", "url"), "source paper")
    text(source["title"], "source paper title")
    text(source["url"], "source paper URL", maximum=4096)
    need(source["url"].startswith("https://"), "Public HTTPS source paper identity required")
    anchors = value["same_task_anchor_descriptions"]
    closed(anchors, ANCHORS, "same-task anchor descriptions")
    for key in ANCHORS:
        text(anchors[key], "same-task " + key)
    need(value["primary_scope"] == anchors["target"], "Primary scope must retain the original target description")
    roles = value["assessment_roles"]
    need(type(roles) is list and len(roles) == len(assessments), "Assessment roles must cover exact documentary records")
    paths = []
    for role in roles:
        need(type(role) is dict and {"path", "role"} <= set(role)
             and set(role) <= {"path", "role", "json_pointer", "locators"}, "Invalid assessment role")
        safe_documentary_path(role["path"])
        text(role["role"], "assessment role", maximum=128)
        if "json_pointer" in role:
            text(role["json_pointer"], "assessment JSON pointer", maximum=1024)
            need(role["json_pointer"].startswith("/"), "Relative document JSON pointer required")
        if "locators" in role:
            texts(role["locators"], "assessment locators", maximum=32)
        paths.append(role["path"])
    need(len(set(paths)) == len(paths) and set(paths) == {item["path"] for item in assessments},
         "Assessment role paths differ from documentary records")
    need(any(role["role"] == "independent_review" for role in roles), "An independent source assessment is required")
    availability = value["outcome_availability"]
    closed(availability, ("reproduction", "improvement", "primary_paired_admission", "condition_protocols"),
           "outcome availability")
    reproduction, improvement = availability["reproduction"], availability["improvement"]
    closed(reproduction, ("declaration_status", "declared_endpoint_eligibility", "source_assessment_disposition",
                          "scientific_ineligibility_inferred"), "reproduction absence")
    need(reproduction["declaration_status"] == "not_adopted"
         and reproduction["declared_endpoint_eligibility"] is None
         and reproduction["source_assessment_disposition"] == "source_unresolved"
         and reproduction["scientific_ineligibility_inferred"] is False,
         "Missing reproduction declaration cannot establish scientific eligibility")
    closed(improvement, ("declaration_status", "declared_disposition", "unavailable_by_reproduction_dependency",
                         "qualification_changed_by_this_record"), "retained improvement availability")
    need(improvement["declaration_status"] == "retained_existing_contract"
         and improvement["declared_disposition"] in ("source_unresolved", "design_ready", "improvement_ready", "ineligible")
         and improvement["unavailable_by_reproduction_dependency"] is False
         and improvement["qualification_changed_by_this_record"] is False,
         "Declaration gap must preserve independent improvement disposition")
    need(availability["primary_paired_admission"] == "unavailable_without_honest_reproduction_declaration",
         "Declaration gap cannot admit paired outcomes")
    closed(availability["condition_protocols"], CONDITIONS, "condition protocols")
    need(all(value == "not_established" for value in availability["condition_protocols"].values()),
         "Declaration gap cannot establish information protocols")
    cells = value["scientific_cells"]
    closed(cells, ("reproduction", "improvement"), "scientific cells")
    for outcome in cells.values():
        closed(outcome, CONDITIONS, "scientific condition cells")
        need(all(status == "unknown" for status in outcome.values()), "Declaration gap cannot qualify scientific outcomes")
    need(value["scope_revision"] is False and value["primary_secondary_scope_mismatch"] is False
         and value["core_two_outcome_completion"] == "not_established",
         "Declaration gap is neither scope mismatch nor completed outcomes")


def validate_record(document):
    """Validate the closed documentary record without reading assessment locators."""
    need(len(canonical(document)) <= MAX_RECORD_BYTES, "Source declaration record exceeds its bounded metadata limit")
    closed(document, ("schema_version", "source_base", "entries", "provenance"), "source declaration record")
    need(document["schema_version"] == VERSION and type(document["source_base"]) is str
         and COMMIT.fullmatch(document["source_base"]), "Invalid source declaration version or predecessor commit")
    closed(document["entries"], TASK_IDS, "source declaration task entries")
    top = document["provenance"]
    closed(top, ("canonical_path_proposal", "record_scope", "documentary_namespace", "documentary_namespace_rule",
                 "admission_rule", "preservation_rule", "qualification_limit"), "source declaration record provenance")
    need(top["canonical_path_proposal"] == PATH and top["documentary_namespace"] == NAMESPACE,
         "Source declaration record namespace mismatch")
    for field in set(top) - {"canonical_path_proposal", "documentary_namespace"}:
        text(top[field], "record provenance " + field)
    for identifier, entry in document["entries"].items():
        closed(entry, ("task_id", "reason_code", "reason", "source_relation", "remaining_source_limits",
                       "original_task", "retained_improvement", "accepted_source_assessments", "scientific_outcome",
                       "paired_outcome_admission", "reproduction_contract", "outcomes_contract", "provenance"),
               "source declaration entry")
        need(entry["task_id"] == identifier and entry["reason_code"] == "source_declaration_unavailable"
             and entry["source_relation"] == "same_primary_source_compatible"
             and entry["scientific_outcome"] == "unknown" and entry["paired_outcome_admission"] == "unavailable"
             and entry["reproduction_contract"] is None and entry["outcomes_contract"] is None,
             "Source declaration entry cannot fabricate contracts, scope mismatch or results")
        text(entry["reason"], "source declaration reason")
        texts(entry["remaining_source_limits"], "remaining source limits")
        home = "benchmarks/paper/" + identifier
        require_pin(entry["original_task"], home + "/task.json", "original task")
        retained = entry["retained_improvement"]
        closed(retained, ("path", "bytes", "sha256", "contract_digest"), "retained improvement")
        require_pin({key: retained[key] for key in ("path", "bytes", "sha256")},
                    home + "/improvement.v1.json", "retained improvement")
        need(type(retained["contract_digest"]) is str and SHA.fullmatch(retained["contract_digest"]),
             "Invalid canonical improvement digest")
        assessments = entry["accepted_source_assessments"]
        need(type(assessments) is list and 0 < len(assessments) <= 32, "Bounded documentary assessments required")
        for assessment in assessments:
            closed(assessment, ("path", "reviewed_task_source_commit", "documentary_namespace", "sha256", "bytes"),
                   "documentary assessment")
            safe_documentary_path(assessment["path"])
            need(assessment["documentary_namespace"] == NAMESPACE
                 and assessment["reviewed_task_source_commit"] == document["source_base"],
                 "Documentary assessment context differs from reviewed source")
            require_pin({key: assessment[key] for key in ("path", "bytes", "sha256")}, assessment["path"],
                        "documentary assessment")
        need(len({item["path"] for item in assessments}) == len(assessments), "Duplicate documentary assessment")
        _provenance(entry["provenance"], assessments)
    return copy.deepcopy(document)


class AuthenticatedGap:
    """An immutable metadata handle; snapshots always return fresh JSON values."""
    __slots__ = ("_encoded",)

    def __init__(self, payload, token=None):
        need(token is _TOKEN, "Use authenticate to obtain a source declaration handle")
        object.__setattr__(self, "_encoded", canonical(payload))

    def __setattr__(self, name, value):
        raise AttributeError("Authenticated source declaration metadata is immutable")

    def __delattr__(self, name):
        raise AttributeError("Authenticated source declaration metadata is immutable")

    def snapshot(self):
        return json.loads(self._encoded)


def authenticate(record_pin, previous_row, previous_specification_pin, read_pin, *, improvement_contract=None):
    """Authenticate fixed record, explicit same-byte archive and retained policy.

    ``read_pin(pin, label)`` must enforce bounded strict JSON and exact raw-byte
    identity. Existing original lineage and improvement semantics remain checked
    by the caller; no documentary locator or task implementation is opened here.
    """
    record_pin = copy.deepcopy(record_pin)
    previous_row = copy.deepcopy(previous_row)
    previous_specification_pin = copy.deepcopy(previous_specification_pin)
    improvement_contract = copy.deepcopy(improvement_contract)
    require_pin(record_pin, PATH, "source declaration record", maximum=MAX_RECORD_BYTES)
    need(callable(read_pin), "A bounded authenticated metadata reader is required")
    record = validate_record(read_pin(copy.deepcopy(record_pin), "Paper source declaration gaps"))
    need(type(previous_row) is dict and previous_row.get("id") in TASK_IDS
         and previous_row.get("track") == "paper", "Exact source declaration task identity required")
    identifier = previous_row["id"]
    home = "benchmarks/paper/" + identifier
    need(previous_row.get("task_directory") == home, "Source declaration task home mismatch")
    entry = record["entries"][identifier]
    need(canonical(previous_row.get("specification")) == canonical(entry["original_task"]),
         "Source declaration record differs from immutable prior task identity")
    require_pin(previous_specification_pin, home + "/" + HISTORY, "pre-outcomes archive")
    need(all(previous_specification_pin[key] == entry["original_task"][key] for key in ("bytes", "sha256")),
         "Pre-outcomes archive does not retain original task bytes")
    previous = copy.deepcopy(read_pin(copy.deepcopy(previous_specification_pin), "Pre-outcomes source declaration task"))
    need(type(previous) is dict and previous.get("id") == identifier and previous.get("track") == "paper"
         and previous.get("objective") == OLD_OBJECTIVE, "Invalid pre-outcomes source declaration task")
    retained = entry["retained_improvement"]
    improvement_pin = {key: retained[key] for key in ("path", "bytes", "sha256")}
    revision = previous_row.get("specification_revision")
    need(type(revision) is dict and revision.get("version") == "paper-improvement/v1"
         and canonical(revision.get("improvement_contract")) == canonical(improvement_pin),
         "Source declaration record differs from retained improvement identity")
    need(type(previous.get("evaluation")) is dict
         and canonical(previous["evaluation"].get("contract")) == canonical(improvement_pin),
         "Immutable predecessor does not bind the retained improvement")
    improvement = (copy.deepcopy(read_pin(copy.deepcopy(improvement_pin), "Retained source declaration improvement"))
                   if improvement_contract is None else improvement_contract)
    need(type(improvement) is dict and improvement.get("task_id") == identifier
         and improvement.get("schema_version") == "paper-improvement/v1"
         and improvement.get("objective") == OLD_OBJECTIVE
         and contract_digest(improvement) == retained["contract_digest"], "Retained improvement canonical identity mismatch")
    evidence = entry["provenance"]
    need(canonical(improvement.get("source_paper")) == canonical(evidence["source_paper"]),
         "Declaration gap must preserve the original source paper")
    anchors = improvement.get("same_task")
    need(type(anchors) is dict and all(type(anchors.get(key)) is dict
         and anchors[key].get("description") == evidence["same_task_anchor_descriptions"][key] for key in ANCHORS),
         "Declaration gap must preserve all original scientific anchors")
    need(improvement.get("disposition") == evidence["outcome_availability"]["improvement"]["declared_disposition"],
         "Declaration gap cannot change independent improvement disposition")
    return AuthenticatedGap({"record_pin": record_pin, "source_base": record["source_base"], "entry": entry,
                             "previous_specification": previous_specification_pin, "previous_task": previous,
                             "improvement_contract": improvement}, _TOKEN)


def _snapshot(authenticated):
    need(type(authenticated) is AuthenticatedGap, "Authenticated source declaration handle required")
    return authenticated.snapshot()


def project(base_dual_task, authenticated):
    """Remove only generic nonexistent-contract presentation from a dual task."""
    context = _snapshot(authenticated)
    previous, entry = context["previous_task"], context["entry"]
    identifier = entry["task_id"]
    need(type(base_dual_task) is dict and base_dual_task.get("id") == identifier
         and base_dual_task.get("objective") == OBJECTIVE, "Expected the matching generic dual-task projection")
    for key in set(previous) | set(base_dual_task):
        if key not in _GENERIC_FIELDS:
            need((key in previous) == (key in base_dual_task)
                 and canonical(previous.get(key)) == canonical(base_dual_task.get(key)),
                 "Generic projection changed inherited scientific field: " + key)
    evaluation = base_dual_task.get("evaluation")
    closed(evaluation, ("objective", "contracts", "paired_protocol", "information_conditions", "outcome_roles",
                        "author_baseline_role", "executor_ref", "scorer_ref", "binary_reward_registered"),
           "generic dual evaluation")
    need(evaluation.get("objective") == OBJECTIVE
         and evaluation.get("contracts") in ({"reproduction": "reproduction.v1.json", "improvement": "improvement.v1.json"},
                                             {"reproduction": "reproduction.v2.json", "improvement": "improvement.v1.json"})
         and evaluation.get("paired_protocol") == "outcomes.v1.json"
         and evaluation["information_conditions"] == list(CONDITIONS)
         and evaluation["outcome_roles"] == {"reproduction": "first_class_outcome", "improvement": "first_class_outcome"}
         and evaluation["author_baseline_role"] == "calibration"
         and evaluation["executor_ref"] is None and evaluation["scorer_ref"] is None
         and evaluation["binary_reward_registered"] is False, "Expected an unqualified generic dual outcome declaration")
    for field in ("episode", "blocking_issues", "next_implementation_action"):
        if field in previous:
            need(type(base_dual_task.get(field)) is dict
                 and "improvement" in base_dual_task[field]
                 and canonical(base_dual_task[field].get("improvement")) == canonical(previous[field]),
                 "Generic projection changed retained improvement field: " + field)
    if "holds" in previous:
        need(type(base_dual_task.get("holds")) is dict
             and "preserved_limits" in base_dual_task["holds"]
             and canonical(base_dual_task["holds"].get("preserved_limits")) == canonical(previous["holds"]),
             "Generic projection changed preserved scientific limits")
    if type(previous.get("admission")) is dict:
        current = base_dual_task.get("admission")
        need(type(current) is dict, "Generic projection changed original admission flags")
        for key in set(previous["admission"]) | set(current):
            if key not in ("delivery_unit", "reason"):
                need((key in previous["admission"]) == (key in current)
                     and canonical(previous["admission"].get(key)) == canonical(current.get(key)),
                     "Generic projection changed original admission flag: " + key)
    else:
        need(("admission" in previous) == ("admission" in base_dual_task)
             and canonical(previous.get("admission")) == canonical(base_dual_task.get("admission")),
             "Generic projection introduced an admission claim")
    result = copy.deepcopy(base_dual_task)
    result["status_basis"] = "The retained status describes the existing improvement declaration. A source-grounded reproduction declaration and its paired access protocols have not been adopted; their absence is not scientific ineligibility."
    result["source_declaration_gap"] = {
        "record": copy.deepcopy(context["record_pin"]), "task_entry_id": identifier,
        "reason_code": entry["reason_code"], "reason": entry["reason"], "source_relation": entry["source_relation"],
        "original_task": copy.deepcopy(entry["original_task"]),
        "retained_improvement": copy.deepcopy(entry["retained_improvement"]),
        "remaining_source_limits": copy.deepcopy(entry["remaining_source_limits"]),
        "reproduction_contract": None, "outcomes_contract": None,
        "scientific_outcome": "unknown", "paired_outcome_admission": "unavailable",
    }
    result["success_criteria"] = [
        "Reproduction remains an independent goal on this original scientific task. Recover and independently review a complete source-grounded reproduction declaration before assessing that outcome.",
        "This source-gap record supplies no missing finding, agreement rule, tolerance, evaluator or access protocol. Source presence and copied paper aggregates do not establish reproduction.",
        "The retained improvement.v1.json preserves its own original comparison, uncertainty and admission requirements. Its declared eligibility is independent of the absent reproduction declaration.",
        "Paired paper+data and paper+data+author-code protocols remain undeclared. No paired-outcome receipt can be admitted from this absence record.",
        "Original-data execution, granular-output verification and source-grounded scientific comparison remain separate qualification requirements. All scientific outcomes remain unknown.",
        "Author-baseline replay remains calibration. Historical reconstruction and source metadata do not become qualified AI reproduction or improvement results.",
    ]
    result["evaluation"]["contracts"]["reproduction"] = None
    result["evaluation"]["paired_protocol"] = None
    result["evaluation"]["reproduction_declaration_status"] = "source_declaration_unavailable"
    result["evaluation"]["paired_outcome_admission"] = "unavailable"
    for field in ("episode", "blocking_issues"):
        if field in previous:
            result[field]["reproduction_contract"] = None
            result[field]["paired_protocol"] = None
            result[field]["source_declaration_limits"] = copy.deepcopy(entry["remaining_source_limits"])
    if "next_implementation_action" in previous:
        result["next_implementation_action"]["reproduction"] = "Recover and independently review the missing source-specific reproduction declaration."
        result["next_implementation_action"]["paired_access"] = "Bind matched information conditions and budgets only after honest outcome declarations exist."
    if "holds" in previous:
        result["holds"]["interpretation"] = "Preserved source, observation, exposure and execution limits remain in force. The retained improvement criteria keep their scope; reproduction requirements have not yet been declared."
        result["holds"]["reproduction_contract"] = None
        result["holds"]["source_declaration_limits"] = copy.deepcopy(entry["remaining_source_limits"])
    return result


def public_summary(authenticated):
    """Expose declared absence and independent improvement status, never results."""
    context = _snapshot(authenticated)
    entry = context["entry"]
    return {
        "schema_version": VERSION, "task_id": entry["task_id"], "task_count": 1,
        "availability": "source_declaration_unavailable", "reason_code": entry["reason_code"],
        "reason": entry["reason"], "source_relation": entry["source_relation"],
        "record": context["record_pin"], "original_task": entry["original_task"],
        "previous_specification": context["previous_specification"], "retained_improvement": entry["retained_improvement"],
        "reproduction_contract": None, "outcomes_contract": None,
        "remaining_source_limits": entry["remaining_source_limits"],
        "reproduction_eligibility": None, "scientific_ineligibility_inferred": False,
        "improvement_disposition": context["improvement_contract"]["disposition"],
        "improvement_unavailable_by_reproduction_dependency": False,
        "paired_outcome_admission": "unavailable",
        "scientific_outcomes": {"reproduction": "unknown", "improvement": "unknown"},
        "cells": [{"outcome": outcome, "condition": condition, "pairing_status": "unavailable",
                   "metadata_admitted": False, "scientific_outcome": "unknown", "receipt": None}
                  for outcome in ("reproduction", "improvement") for condition in CONDITIONS],
        "assurance": "Authenticated declaration-gap metadata establishes no scientific eligibility, execution, source parity or result.",
    }
