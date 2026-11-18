"""Closed, independently pinned original-paper endpoint selections.

Source metadata only. No task module, data, runtime, scientific comparison, or
network is accessed. The adoption pin is deliberately absent until all accepted
source definitions and semantic reviews are frozen; a valid-shaped authority
cannot approve itself. Opaque author notes are evidence, never executable policy.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re


BASE_COMMIT = "9953b581a9c3a8c1b38b2a961ce6723f10739630"
AUTHORITY_PATH = "docs/provenance/paper-primary-endpoint-selections.v2.json"
AUTHORITY_VERSION = "paper-primary-endpoint-selections/v2"
POLICY_PATH = "docs/provenance/paper-primary-endpoint-selection-policy.v2.json"
POLICY_SHA256 = "1f1781fb0dff7e53a4d6827122b55634c1c27fa5016ac81e75c2e8c2fb3e1702"
SELECTION_KIND = "original_author_reported_computational_endpoint"
RETAINED_DESIGN_READY = frozenset(("PAPER-paper-method-replacement-005", "PAPER-paper-signal-add-012"))
# Filled only by the integrator after independent semantic review of the exact
# complete batch. Never derive these from the file currently occupying the path.
AUTHORITY_PIN = {'path': 'docs/provenance/paper-primary-endpoint-selections.v2.json', 'bytes': 353386, 'sha256': 'f91b92195f19040c06f925d5950ffb4ce78c0311f4a5c9840e657091a09de2c5'}
AUTHORITY_CANONICAL = '4c1884f1df82dc7984bccef7308c1738d39200cb05a81adfc2276278d1a3a604'
TASKS = frozenset((
    "PAPER-CANDIDATE-20261114-NPVC", "PAPER-CANDIDATE-20261114-PLEXUS",
    "PAPER-EXP-20261113-002", "PAPER-EXP-20261113-004", "PAPER-FIND-036",
    "PAPER-FIND-039", "PAPER-FIND-ADD-003", "PAPER-FIND-REP-003",
    "PAPER-FIND-REP-009", "PAPER-ROOT-ADD-003", "PAPER-ROOT-ADD-005",
    "PAPER-ROOT-ADD-010", "PAPER-ROOT-ADD-016", "PAPER-ROOT-ADD-020",
    "PAPER-ROOT-ADD-025", "PAPER-ROOT-ADD-026", "PAPER-paper-method-011",
    "PAPER-paper-method-012", "PAPER-paper-method-add-006",
    "PAPER-paper-method-replacement-005", "PAPER-paper-method-replacement-009",
    "PAPER-paper-method-replacement-011", "PAPER-paper-method-replacement-016",
    "PAPER-paper-signal-add-001", "PAPER-paper-signal-add-012",
    "PAPER-paper-signal-add-019",
))
SHA = re.compile(r"[0-9a-f]{64}\Z")
MAX_MEMBER_BYTES = 1024 * 1024
MAX_AUTHORITY_BYTES = 1024 * 1024
_SEAL = object()
_BINDING_KEYS = frozenset(("schema_version", "previous_specification",
                           "reproduction_contract", "outcomes", "endpoint_selection"))
_ENTRY_KEYS = frozenset(("task_id", "previous_registry_row", "predecessor_task",
                         "retained_documents", "selected_documents", "scope",
                         "access_policy", "review", "remaining_blockers", "reviewed_evidence"))
_SELECTED_KEYS = frozenset(("task", "reproduction", "improvement", "outcomes",
                            "selection", "access_conditions"))


def need(condition, message):
    if not condition:
        raise ValueError(message)


def _strict_json(value, active=None):
    active = set() if active is None else active
    if type(value) in (dict, list):
        need(id(value) not in active, "Endpoint metadata cannot contain cycles")
        active.add(id(value))
        if type(value) is dict:
            need(all(type(key) is str for key in value), "Endpoint JSON keys must be strings")
            values = value.values()
        else:
            values = value
        for item in values:
            _strict_json(item, active)
        active.remove(id(value))
    elif type(value) in (int, float):
        try:
            finite = math.isfinite(value)
        except OverflowError:
            finite = False
        need(finite, "Endpoint JSON numbers must be finite")
    else:
        need(type(value) in (str, bool, type(None)), "Endpoint metadata must be strict JSON")


def canonical(value):
    _strict_json(value)
    try:
        return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                         ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Endpoint selection must contain strict finite JSON") from exc


def closed(value, keys, label):
    need(type(value) is dict and set(value) == set(keys), "Closed " + label + " required")


def text(value, label):
    need(type(value) is str and bool(value.strip()), "Nonempty " + label + " required")


def digest(value, label):
    need(type(value) is str and SHA.fullmatch(value), "Invalid " + label + " digest")


def strings(value, label, *, nonempty=False):
    need(type(value) is list and (not nonempty or bool(value))
         and all(type(item) is str and item.strip() for item in value)
         and len(value) == len(set(value)), "Unique " + label + " strings required")


def require_pin(value, expected_path=None, *, maximum=MAX_MEMBER_BYTES):
    closed(value, ("path", "bytes", "sha256"), "endpoint raw pin")
    path = value["path"]
    need(type(path) is str and path and not path.startswith("/") and "\\" not in path
         and all(part not in ("", ".", "..") for part in path.split("/")),
         "Endpoint pin must have a safe repository-relative path")
    need(expected_path is None or path == expected_path, "Unexpected endpoint member path")
    need(type(value["bytes"]) is int and 0 < value["bytes"] <= maximum,
         "Endpoint member exceeds its bounded metadata size")
    digest(value["sha256"], "raw member")


def member(value, expected_path=None):
    closed(value, ("pin", "canonical_sha256"), "endpoint member identity")
    require_pin(value["pin"], expected_path)
    digest(value["canonical_sha256"], "canonical member")


def read_member(value, read_pin, label):
    member(value)
    document = read_pin(copy.deepcopy(value["pin"]), label)
    need(type(document) is dict and canonical(document) == value["canonical_sha256"],
         label + " parsed identity differs from independently accepted bytes")
    return document


def has_endpoint_selection(row):
    declared = row.get("paper_outcomes")
    if type(declared) is not dict or "endpoint_selection" not in declared:
        return False
    need(row.get("track") == "paper" and row.get("id") in TASKS,
         "Endpoint selection is restricted to the reviewed paper batch")
    need(set(declared) == _BINDING_KEYS and declared["schema_version"] == "paper-outcomes-binding/v1",
         "Endpoint selection requires a complete unmixed outcome binding")
    home = "benchmarks/paper/" + row["id"]
    require_pin(declared["endpoint_selection"], home + "/primary-endpoint-v1/selection.v1.json")
    require_pin(declared["outcomes"], home + "/primary-endpoint-v1/outcomes.v1.json")
    require_pin(declared["previous_specification"], home + "/historical/task.pre-outcomes.v1.json")
    require_pin(declared["reproduction_contract"])
    need(declared["reproduction_contract"]["path"] in {
        home + "/primary-endpoint-v1/reproduction.v1.json",
        home + "/primary-endpoint-v1/reproduction.v2.json"},
        "Endpoint reproduction must use a reviewed versioned filename")
    return True


class Authority:
    """Immutable serialized snapshot, reauthenticated on every access."""
    __slots__ = ("_payload", "_pin_payload", "_seal")

    def __init__(self, document, authority_pin, seal):
        need(seal is _SEAL, "Endpoint authority must be authenticated")
        object.__setattr__(self, "_payload", json.dumps(document, sort_keys=True, separators=(",", ":"),
                                                      ensure_ascii=False, allow_nan=False).encode())
        object.__setattr__(self, "_pin_payload", json.dumps(authority_pin, sort_keys=True).encode())
        object.__setattr__(self, "_seal", seal)

    def __setattr__(self, name, value):
        raise AttributeError("Endpoint authority snapshots are immutable")

    def _snapshot(self):
        need(self._seal is _SEAL and hashlib.sha256(self._payload).hexdigest() == AUTHORITY_CANONICAL,
             "Endpoint authority snapshot no longer matches its accepted canonical identity")
        need(json.loads(self._pin_payload) == AUTHORITY_PIN,
             "Endpoint authority snapshot no longer matches its accepted raw identity")
        return json.loads(self._payload)

    @property
    def ids(self):
        return frozenset(self._snapshot()["entries"])

    def entry(self, identifier):
        document = self._snapshot()
        need(identifier in document["entries"], "Task has no adopted endpoint selection")
        return document["entries"][identifier]

    @property
    def pin(self):
        self._snapshot()
        return json.loads(self._pin_payload)

    @property
    def policy_pin(self):
        return self._snapshot()["scope_policy"]["pin"]


def selection_ids(authority):
    need(authority is None or type(authority) is Authority, "Invalid endpoint authority handle")
    return frozenset() if authority is None else authority.ids


def _access_policy(value):
    closed(value, ("status", "common_input_ids", "author_code_only_ids", "evaluator_only_ids",
                   "assisted_common_input_ids", "paper_data", "paper_data_author_code",
                   "original_information_limits", "source_evidence_ids"), "normalized access policy")
    need(value["status"] == "declared_uninstantiated", "Source-only access cannot instantiate a protocol")
    for key in set(value) - {"status"}:
        strings(value[key], "access " + key, nonempty=key in ("common_input_ids", "author_code_only_ids",
                                                            "original_information_limits", "source_evidence_ids"))
    common, code, private = (set(value[key]) for key in ("common_input_ids", "author_code_only_ids", "evaluator_only_ids"))
    need(not (common & code or common & private or code & private), "Source access roles must be disjoint")
    need(set(value["assisted_common_input_ids"]) <= common, "Common model/code assistance must be disclosed")
    need(value["paper_data"] == value["common_input_ids"]
         and value["paper_data_author_code"] == value["common_input_ids"] + value["author_code_only_ids"],
         "Paired conditions must have exactly the reviewed author-code difference")


def _entry(identifier, value):
    closed(value, _ENTRY_KEYS, "endpoint authority entry")
    need(value["task_id"] == identifier, "Endpoint entry identity mismatch")
    home = "benchmarks/paper/" + identifier
    previous = value["previous_registry_row"]
    need(type(previous) is dict and previous.get("id") == identifier and previous.get("track") == "paper"
         and previous.get("task_directory") == home and type(previous.get("paper_outcomes")) is dict,
         "Endpoint predecessor must be an exact prior registered paper row")
    predecessor = value["predecessor_task"]
    closed(predecessor, ("route", "source_commit", "source_path", "identity"), "endpoint predecessor")
    need(predecessor["route"] in ("git_blob", "packaged_file")
         and predecessor["source_commit"] == BASE_COMMIT
         and predecessor["source_path"] == home + "/task.json", "Unknown endpoint predecessor provenance")
    expected = home + ("/task.json" if predecessor["route"] == "git_blob"
                       else "/historical/primary-biological-20261117-v1/task.json")
    member(predecessor["identity"], expected)
    need(all(predecessor["identity"]["pin"][key] == previous["specification"][key]
             for key in ("bytes", "sha256")), "Predecessor task differs from fixed source registry")
    require_pin(previous["specification"], home + "/task.json")
    selected = value["selected_documents"]
    closed(selected, _SELECTED_KEYS, "selected endpoint documents")
    for key, filename in (("task", "task.json"), ("improvement", "primary-endpoint-v1/improvement.v1.json"),
                          ("outcomes", "primary-endpoint-v1/outcomes.v1.json"),
                          ("selection", "primary-endpoint-v1/selection.v1.json"),
                          ("access_conditions", "primary-endpoint-v1/access-conditions.v1.json")):
        member(selected[key], home + "/" + filename)
    member(selected["reproduction"])
    need(selected["reproduction"]["pin"]["path"] in {
        home + "/primary-endpoint-v1/reproduction.v1.json", home + "/primary-endpoint-v1/reproduction.v2.json"},
        "Unsupported selected reproduction filename")
    retained = value["retained_documents"]
    need(type(retained) is list and 1 <= len(retained) <= 8, "Bounded retained source documents required")
    retained_paths = set()
    for record in retained:
        closed(record, ("role", "scope", "identity"), "retained source record")
        text(record["role"], "retained role"); text(record["scope"], "retained scope")
        member(record["identity"])
        path = record["identity"]["pin"]["path"]
        need(path in {home + "/" + filename for filename in
                      ("improvement.v1.json", "reproduction.v1.json", "reproduction.v2.json", "outcomes.v1.json")}
             and path not in retained_paths, "Unknown or duplicate retained source path")
        retained_paths.add(path)
    required = [previous["specification_revision"]["improvement_contract"]]
    required.extend(previous["paper_outcomes"][key] for key in ("reproduction_contract", "outcomes")
                    if key in previous["paper_outcomes"])
    by_path = {record["identity"]["pin"]["path"]: record["identity"]["pin"] for record in retained}
    need(all(by_path.get(pin["path"]) == pin for pin in required), "Original source contracts must remain exactly retained")
    extras = value["reviewed_evidence"]
    need(type(extras) is list and len(extras) <= 16, "Bounded reviewed endpoint evidence required")
    extra_paths = []
    selected_paths = {record["pin"]["path"] for record in selected.values()}
    for record in extras:
        closed(record, ("role", "identity"), "reviewed endpoint evidence")
        text(record["role"], "reviewed evidence role")
        member(record["identity"])
        path = record["identity"]["pin"]["path"]
        prefix = home + "/primary-endpoint-v1/"
        need(path.startswith(prefix) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,119}\.json", path[len(prefix):])
             and path not in selected_paths and path not in extra_paths,
             "Reviewed evidence must be distinct explicitly pinned task-local JSON")
        extra_paths.append(path)
    need(extra_paths == sorted(extra_paths), "Reviewed evidence identities require stable path order")
    scope = value["scope"]
    closed(scope, ("kind", "primary_scope", "target_description", "retained_secondary_scope", "source_locator", "source_evidence_ids"),
           "endpoint scope")
    need(scope["kind"] == SELECTION_KIND, "Selection is a new original-paper endpoint scope")
    for key in ("primary_scope", "target_description", "retained_secondary_scope", "source_locator"):
        text(scope[key], "scope " + key)
    strings(scope["source_evidence_ids"], "endpoint evidence", nonempty=True)
    _access_policy(value["access_policy"])
    closed(value["review"], ("semantic_review_sha256", "complete_task_delta_sha256"), "endpoint review identities")
    for key in value["review"]:
        digest(value["review"][key], key)
    strings(value["remaining_blockers"], "remaining endpoint blockers", nonempty=True)


def _registration_identity(row, previous):
    """Normalize only a validated append-only documentation suffix for comparison.

    Existing catalog and ownership checks separately authenticate filesystem
    existence and reject symlinks; this callback has only JSON metadata access.
    Neither the current row nor the frozen predecessor is modified.
    """
    identity = {key: val for key, val in row.items()
                if key not in ("specification", "paper_outcomes", "title")}
    if "documentation" not in row:
        need("documentation" not in previous,
             "Endpoint documentation cannot remove its registered prefix")
        return identity
    records = row["documentation"]
    prior = previous.get("documentation", [])
    need(type(records) is list and type(prior) is list,
         "Endpoint documentation must preserve its registered list")
    need(len(records) >= len(prior) and records[:len(prior)] == prior,
         "Endpoint documentation must preserve its exact registered prefix and order")
    need("documentation" in previous or bool(records),
         "Endpoint documentation cannot add an empty absent field")
    home = previous["task_directory"] + "/docs/"
    seen = set()
    for record in records:
        closed(record, ("label", "path"), "endpoint documentation record")
        text(record["label"], "endpoint documentation label")
        path = record["path"]
        need(type(path) is str and path.startswith(home) and "\\" not in path
             and not any(ord(char) < 32 or ord(char) == 127 for char in path)
             and all(part not in ("", ".", "..") for part in path.split("/")),
             "Endpoint documentation must have a normalized task-owned docs path")
        need(path not in seen, "Endpoint documentation paths must be unique")
        seen.add(path)
    if "documentation" in previous:
        identity["documentation"] = prior
    else:
        del identity["documentation"]
    return identity


def authenticate_authority(authority_pin, previous_rows, registry_rows, read_pin):
    """Adopt only a fully populated, independently pinned complete batch.

    The Git predecessor route is reviewed provenance: its immutable commit/path,
    raw/canonical task identities, prior row and complete task delta are frozen
    in the authority after source review. It never launches Git or fetches old
    bytes at runtime. The packaged route additionally authenticates old bytes.
    """
    declarations = [row for row in registry_rows if type(row.get("paper_outcomes")) is dict
                    and "endpoint_selection" in row["paper_outcomes"]]
    if authority_pin is None:
        need(AUTHORITY_PIN is None and not declarations,
             "Adopted endpoint selections cannot omit their authority or selector")
        return None
    need(AUTHORITY_PIN is not None and AUTHORITY_CANONICAL is not None,
         "Endpoint authority is not adopted: exact scientific source freeze and review are pending")
    require_pin(authority_pin, AUTHORITY_PATH, maximum=MAX_AUTHORITY_BYTES)
    need(authority_pin == AUTHORITY_PIN, "Endpoint authority differs from independently accepted raw identity")
    document = read_pin(copy.deepcopy(authority_pin), "Original-paper endpoint selection authority")
    need(type(document) is dict and canonical(document) == AUTHORITY_CANONICAL,
         "Endpoint authority parsed identity differs from independently accepted authority")
    closed(document, ("schema_version", "source_commit", "scope_policy_sha256", "scope_policy", "source_scope_authority",
                      "source_gap_authority", "entries"), "endpoint authority")
    need(document["schema_version"] == AUTHORITY_VERSION and document["source_commit"] == BASE_COMMIT
         and document["scope_policy_sha256"] == POLICY_SHA256, "Unreviewed endpoint authority version or policy")
    member(document["scope_policy"], POLICY_PATH)
    need(document["scope_policy"]["pin"]["sha256"] == POLICY_SHA256,
         "Published selection policy must preserve the exact root-adopted policy bytes")
    read_member(document["scope_policy"], read_pin, "Portable original-paper endpoint selection policy")
    for key, pin_name, doc_name in (("source_scope_authority", "scope_pin", "scope_decisions"),
                                     ("source_gap_authority", "source_declaration_gap_pin", "source_declaration_gaps")):
        declared = document[key]
        actual_pin, actual_doc = getattr(previous_rows, pin_name, None), getattr(previous_rows, doc_name, None)
        member(declared)
        need(declared["pin"] == actual_pin and actual_doc is not None
             and declared["canonical_sha256"] == canonical(actual_doc),
             "Endpoint authority must preserve exact preceding scope and declaration-gap records")
    entries = document["entries"]
    need(type(entries) is dict and set(entries) == TASKS, "Endpoint adoption requires the complete reviewed batch")
    rows = {row["id"]: row for row in registry_rows}
    need(TASKS <= set(rows) and len(rows) == len(registry_rows), "Endpoint registered identities must be preserved")
    for identifier, entry in entries.items():
        _entry(identifier, entry)
        row = rows[identifier]
        need(has_endpoint_selection(row), "Adopted endpoint cannot fall back to its retained prior scope")
        old = entry["previous_registry_row"]
        selected = entry["selected_documents"]
        selected_task = read_member(selected["task"], read_pin, "Selected endpoint task")
        text(selected_task.get("title"), "selected endpoint task title")
        need(row.get("title") == selected_task["title"],
             "Endpoint registration title differs from authenticated selected task")
        need(_registration_identity(row, old)
             == {key: val for key, val in old.items() if key not in ("specification", "paper_outcomes", "title")},
             "Endpoint selection cannot change registration identity, status, resources or lineage")
        need(row["specification"] == selected["task"]["pin"]
             and row["paper_outcomes"]["endpoint_selection"] == selected["selection"]["pin"]
             and row["paper_outcomes"]["reproduction_contract"] == selected["reproduction"]["pin"]
             and row["paper_outcomes"]["outcomes"] == selected["outcomes"]["pin"]
             and row["paper_outcomes"]["previous_specification"] == old["paper_outcomes"]["previous_specification"],
             "Current endpoint registry pins differ from reviewed selected source")
    need({row["id"] for row in declarations} == TASKS, "Unexpected or missing endpoint selection")
    return Authority(document, authority_pin, _SEAL)


def context(row, document, previous_rows, read_pin, engine, *, improvement_contract=None):
    authority = getattr(previous_rows, "endpoint_selections", None)
    need(type(authority) is Authority and row["id"] in authority.ids, "Current endpoint requires an authenticated authority")
    need(has_endpoint_selection(row), "Adopted endpoint selector is missing or mixed")
    identifier, home = row["id"], row["task_directory"]
    entry = authority.entry(identifier)
    selected = entry["selected_documents"]
    loaded = {key: read_member(value, read_pin, "Selected endpoint " + key) for key, value in selected.items()}
    need(canonical(document) == selected["task"]["canonical_sha256"] and document == loaded["task"]
         and row["specification"] == selected["task"]["pin"], "Current task differs from reviewed endpoint source")
    for extra in entry["reviewed_evidence"]:
        read_member(extra["identity"], read_pin, "Required endpoint evidence: " + extra["role"])
    predecessor = entry["predecessor_task"]
    if predecessor["route"] == "packaged_file":
        read_member(predecessor["identity"], read_pin, "Immutable preceding primary task")
    retained = {record["identity"]["pin"]["path"]:
                read_member(record["identity"], read_pin, "Retained " + record["role"])
                for record in entry["retained_documents"]}
    retained_pin = row["specification_revision"]["improvement_contract"]
    retained_improvement = retained[retained_pin["path"]]
    need(improvement_contract is None or canonical(improvement_contract) == canonical(retained_improvement),
         "Provided retained improvement differs from reviewed source")
    prior = previous_rows[identifier]
    previous_pin = row["paper_outcomes"]["previous_specification"]
    need(all(previous_pin[key] == prior["specification"][key] for key in ("bytes", "sha256")),
         "Pre-outcomes lineage changed during endpoint selection")
    previous_document = read_pin(copy.deepcopy(previous_pin), "Retained pre-outcomes task")
    reproduction, improvement, outcomes = (loaded[key] for key in ("reproduction", "improvement", "outcomes"))
    version = reproduction.get("schema_version")
    need(version in ("paper-reproduction/v1", "paper-reproduction/v2"), "Unsupported selected reproduction schema")
    need(selected["reproduction"]["pin"]["path"] == home + "/primary-endpoint-v1/reproduction."
         + ("v1.json" if version.endswith("/v1") else "v2.json"), "Reproduction filename and schema disagree")
    module = engine(reproduction)
    errors = module.outcomes_validate(outcomes, reproduction, improvement)
    need(not errors, "Invalid selected original-paper contracts: " + "; ".join(errors))
    retained_design = (identifier in RETAINED_DESIGN_READY
                       and improvement["disposition"] == retained_improvement["disposition"] == "design_ready")
    need(reproduction["eligibility"] in ("source_unresolved", "schema_blocked")
         and (improvement["disposition"] == "source_unresolved" or retained_design),
         "Source-only endpoint selection cannot promote eligibility or improvement readiness")
    need(bool(reproduction["blocking_issues"]) and bool(improvement["blocking_issues"]),
         "Source-only endpoint construction must preserve concrete unresolved requirements")
    need("admission_policy" not in reproduction and "admission_policy" not in improvement,
         "Source-only endpoint adoption cannot invent an executable admission policy")
    need(outcomes["task_id"] == identifier and outcomes["original_task_sha256"] == row["specification"]["sha256"]
         and all(pair["status"] == "unresolved" and pair["protocol"] is None for pair in outcomes["pairing"].values()),
         "Selected outcomes must bind the new task and retain uninstantiated pairing")
    scope = entry["scope"]
    need(document.get("id") == identifier and document.get("track") == "paper"
         and document.get("objective") == "recreate_and_surpass_source_paper_same_task"
         and document.get("primary_scope") == scope["primary_scope"]
         and document.get("retained_secondary_scope") == scope["retained_secondary_scope"]
         and document.get("scope_decision") == {"path": AUTHORITY_PATH, "task_entry_id": identifier},
         "Current task must explicitly distinguish selected and retained scientific scopes")
    evaluation = document.get("evaluation", {})
    need(evaluation.get("contracts") == {"reproduction": selected["reproduction"]["pin"]["path"][len(home) + 1:],
                                         "improvement": "primary-endpoint-v1/improvement.v1.json"}
         and evaluation.get("paired_protocol") == "primary-endpoint-v1/outcomes.v1.json"
         and evaluation.get("information_conditions") == ["paper_data", "paper_data_author_code"]
         and evaluation.get("executor_ref") is None and evaluation.get("scorer_ref") is None
         and evaluation.get("binary_reward_registered") is False,
         "Current task must name only the selected source contracts without claiming runtime registration")
    need(reproduction["same_task"]["target"]["description"] == scope["target_description"],
         "Selected scope and scientific target disagree")
    evidence = {item["id"] for item in reproduction["evidence"]} | {item["id"] for item in improvement["evidence"]}
    need(set(scope["source_evidence_ids"]) <= evidence
         and set(entry["access_policy"]["source_evidence_ids"]) <= evidence,
         "Endpoint/access source references must bind selected scientific evidence")
    result = module.summary(outcomes, reproduction, improvement)
    need(not result["errors"] and result["task_count"] == 1
         and all(not cell["condition_available"] and not cell["endpoint_eligible"]
                 and cell["receipt"] is None and cell["scientific_outcome"] == "unknown" for cell in result["cells"]),
         "Source selection must produce only unqualified, uninstantiated outcome cells")
    members = {item["pin"]["path"] for item in selected.values()}
    members.update(record["identity"]["pin"]["path"] for record in entry["retained_documents"])
    # The original improvement is already owned by the pre-outcomes revision.
    # Reusing its bytes is mandatory; registering it twice is not.
    members.discard(retained_pin["path"])
    members.update(extra["identity"]["pin"]["path"] for extra in entry["reviewed_evidence"])
    members.add(previous_pin["path"])
    if predecessor["route"] == "packaged_file":
        members.add(predecessor["identity"]["pin"]["path"])
    provenance = {"endpoint_selection_authority": authority.pin, "scope_decision": authority.pin,
                  "scope_policy": authority.policy_pin,
                  "access_conditions": selected["access_conditions"]["pin"],
                  "selection_kind": SELECTION_KIND}
    for index, extra in enumerate(entry["reviewed_evidence"]):
        # Existing catalog dependency collection consumes individual raw pins.
        # Stable keys keep every required source visible without dynamic reads.
        provenance["reviewed_evidence_" + str(index).zfill(3)] = extra["identity"]["pin"]
    return {"previous_row": prior, "previous_document": previous_document, "previous_pin": previous_pin,
            "improvement_contract": improvement, "improvement_contract_pin": selected["improvement"]["pin"],
            "retained_improvement_contract": retained_improvement, "retained_improvement_contract_pin": retained_pin,
            "primary_policy_revision": selected["selection"]["pin"],
            "primary_policy_provenance": provenance,
            "candidate_interface": None, "author_reproduction_routes": None,
            "continuous_outcomes_v1": None, "continuous_outcomes_v2": None, "continuous_policy": None,
            "retained_temporal_summary": None, "reproduction_contract": reproduction, "outcomes": outcomes,
            "summary": result, "availability": "available", "primary_scope_correction": None,
            "scope_decision_pin": authority.pin, "members": members}
