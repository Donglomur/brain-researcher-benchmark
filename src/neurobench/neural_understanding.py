"""Source-bound neural-understanding definitions, without execution qualification.

This module authenticates declared source evidence and historical task lineage.
It never executes a submitted programme, reads external data, or treats a valid
contract/source-available mode as a successful scientific or model evaluation.
"""
from __future__ import annotations

import copy
from datetime import date
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
from urllib.parse import urlsplit

VERSION = "neural-understanding/v1"
OBJECTIVE = "infer_neural_or_behavioral_targets_from_permitted_observations"
CONTRACT = "understanding.v1.json"
HISTORY = "historical/task.pre-understanding.v1.json"
MODES = ("direct_observation", "typed_viewer", "tool_assisted", "frozen_program")
DISPOSITIONS = ("delivered_named_scope", "partial_delivery", "design_only", "target_mismatch")
MODE_STATUSES = ("source_available", "not_delivered", "not_suitable")
MAX_BYTES = 24 * 1024 * 1024


def _object(properties):
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


def _array(item, minimum=0):
    return {"type": "array", "items": item, "minItems": minimum, "uniqueItems": True}


TEXT = {"type": "string", "minLength": 1, "pattern": r"\S"}
TEXTS = _array(TEXT)
SHA = {"type": "string", "pattern": r"^[0-9a-f]{64}(?![\s\S])"}
MODE_SCHEMA = _object({"status": {"enum": list(MODE_STATUSES)}, "representation": TEXT,
                       "boundary": TEXT, "evidence_ids": TEXTS, "missing": TEXTS})
LOCAL_EVIDENCE = _object({"id": TEXT, "kind": {"enum": ["local_source", "local_review"]},
                         "path": TEXT, "sha256": SHA, "supports": TEXT})
PRIMARY_EVIDENCE = _object({"id": TEXT, "kind": {"const": "primary_source"}, "url": TEXT,
                           "locator": TEXT, "supports": TEXT})
CONTRACT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    **_object({
        "schema_version": {"const": VERSION}, "task_id": TEXT, "title": TEXT,
        "objective": {"const": OBJECTIVE}, "disposition": {"enum": list(DISPOSITIONS)},
        "disposition_reason": TEXT,
        "scientific_target": _object({
            "question": TEXT, "target_kind": {"enum": ["observation_decoding", "neural_response_prediction",
                "conditional_investigation", "measurement_reconstruction", "behavioral_prediction"]},
            "known_answer": TEXT, "answer_origin": TEXT, "case_unit": TEXT, "independent_unit": TEXT,
            "inference_scope": TEXT, "exclusions": _array(TEXT, 1)}),
        "observation_contract": _object({"inputs": _array(TEXT, 1), "forbidden_inputs": _array(TEXT, 1),
            "case_identity": TEXT, "split": TEXT, "coverage": TEXT}),
        "evaluation": _object({
            "primary": _object({"name": TEXT, "direction": {"enum": ["higher", "lower", "two_sided"]},
                                "aggregation": TEXT, "rationale": TEXT}),
            "secondary": _array(TEXT, 1), "comparators": _array(_object({"name": TEXT, "inputs": TEXT,
                "procedure": TEXT}), 1), "nuisance_controls": _array(TEXT, 1), "uncertainty": TEXT,
            "failure_policy": TEXT}),
        "implementation": _object({"reviewed_paths": _array(TEXT, 1), "scorer_target": TEXT,
            "target_fidelity": {"enum": ["full_target", "scoped_target", "different_target", "no_target_evaluator", "unresolved"]},
            "delivered_scope": TEXT, "missing": TEXTS, "execution_evidence": TEXT}),
        "access_modes": _object({mode: MODE_SCHEMA for mode in MODES}),
        "evidence": _array({"anyOf": [LOCAL_EVIDENCE, PRIMARY_EVIDENCE]}, 1),
        "empirical_claims": _object({"new_model_trials": {"type": "integer", "const": 0},
            "new_human_results": {"type": "integer", "const": 0},
            "scientific_qualification": {"const": "not_established_by_this_revision"},
            "historical_evidence": TEXT, "excluded_claims": _array(TEXT, 1)}),
        "revision": _object({"date": TEXT, "summary": _array(TEXT, 1), "source_review": TEXT}),
    })}


def _shape(value, schema, path="$", active=None):
    """Validate the small explicit JSON Schema subset above without dependencies."""
    active = set() if active is None else active
    if "anyOf" in schema:
        if any(not _shape(value, part, path, active) for part in schema["anyOf"]):
            return []
        return [path + ": does not match an allowed evidence shape"]
    errors = []
    expected = schema.get("type")
    types = {"object": dict, "array": list, "string": str, "integer": int}
    if expected and type(value) is not types[expected]:
        return [path + ": expected " + expected]
    if "const" in schema and (type(value) is not type(schema["const"]) or value != schema["const"]):
        errors.append(path + ": unexpected constant")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(path + ": value outside allowed choices")
    if type(value) in (dict, list):
        if id(value) in active:
            return [path + ": cyclic value is not JSON"]
        active.add(id(value))
    if expected == "object":
        for key in schema["required"]:
            if key not in value:
                errors.append(path + ": missing " + key)
        for key, child in value.items():
            if type(key) is not str or key not in schema["properties"]:
                errors.append(path + ": unexpected property " + repr(key))
            else:
                errors.extend(_shape(child, schema["properties"][key], path + "." + key, active))
    elif expected == "array":
        if len(value) < schema.get("minItems", 0):
            errors.append(path + ": too few items")
        for index, child in enumerate(value):
            errors.extend(_shape(child, schema["items"], f"{path}[{index}]", active))
        if schema.get("uniqueItems"):
            try:
                encoded = [json.dumps(child, sort_keys=True, allow_nan=False) for child in value]
                if len(encoded) != len(set(encoded)):
                    errors.append(path + ": duplicate items")
            except (ValueError, TypeError):
                errors.append(path + ": invalid JSON items")
    elif expected == "string":
        if len(value) < schema.get("minLength", 0) or ("pattern" in schema and not re.search(schema["pattern"], value)):
            errors.append(path + ": invalid string")
    if type(value) in (dict, list):
        active.remove(id(value))
    return errors


def _relative(value):
    if (type(value) is not str or not value or "\\" in value
            or any(ord(character) < 32 or ord(character) == 127 for character in value)):
        raise ValueError("Expected normalized repository-relative path")
    parsed = PurePosixPath(value)
    if (parsed.is_absolute() or str(parsed) != value or value == "." or ".." in parsed.parts
            or any(part.casefold() == ".git" for part in parsed.parts)):
        raise ValueError("Expected normalized repository-relative path: " + value)
    return parsed


def validate_contract(contract, task_id=None):
    """Return structural/claim-consistency errors; do not authenticate source files."""
    errors = _shape(contract, CONTRACT_SCHEMA)
    if errors:
        return errors
    if task_id is not None and contract["task_id"] != task_id:
        errors.append("$.task_id: does not match registration")
    try:
        date.fromisoformat(contract["revision"]["date"])
    except ValueError:
        errors.append("$.revision.date: expected ISO calendar date")
    evidence = {}
    for item in contract["evidence"]:
        if item["id"] in evidence:
            errors.append("$.evidence: duplicate evidence id " + item["id"])
        evidence[item["id"]] = item
        if item["kind"] == "primary_source":
            try:
                url = urlsplit(item["url"])
                if url.scheme not in ("https", "http") or not url.netloc or url.username or url.password:
                    raise ValueError("Not a public HTTP(S) URL")
            except ValueError:
                errors.append("$.evidence: expected public HTTP(S) source URL")
        else:
            try:
                _relative(item["path"])
            except ValueError as exc:
                errors.append("$.evidence: " + str(exc))
    if not any(item["kind"] == "primary_source" for item in evidence.values()):
        errors.append("$.evidence: primary source citation required")
    for path in contract["implementation"]["reviewed_paths"]:
        try:
            _relative(path)
        except ValueError as exc:
            errors.append("$.implementation.reviewed_paths: " + str(exc))
    local_paths = {item["path"] for item in evidence.values() if item["kind"] != "primary_source"}
    for path in contract["implementation"]["reviewed_paths"]:
        if path not in local_paths:
            errors.append("$.implementation.reviewed_paths: unpinned reviewed file " + path)
    for mode, record in contract["access_modes"].items():
        unknown = set(record["evidence_ids"]) - evidence.keys()
        if unknown:
            errors.append("$.access_modes." + mode + ": unknown evidence IDs " + ", ".join(sorted(unknown)))
        if record["status"] == "source_available" and not any(
                evidence.get(key, {}).get("kind") == "local_source" for key in record["evidence_ids"]):
            errors.append("$.access_modes." + mode + ": source_available requires local_source evidence")
    return errors


def summary(contract):
    """Return navigation metadata. Source availability is never readiness."""
    errors = validate_contract(contract)
    if errors:
        raise ValueError("Invalid neural understanding contract: " + "; ".join(errors))
    return {"schema_version": VERSION, "objective": OBJECTIVE,
            "disposition": contract["disposition"], "disposition_reason": contract["disposition_reason"],
            "primary_target": contract["scientific_target"]["known_answer"],
            "primary_metric": contract["evaluation"]["primary"]["name"],
            "target_fidelity": contract["implementation"]["target_fidelity"],
            "access_modes": {name: {key: copy.deepcopy(value) for key, value in record.items()
                                     if key != "evidence_ids"} for name, record in contract["access_modes"].items()},
            "blocked_by": list(contract["implementation"]["missing"]),
            "scientific_qualification": "not_established_by_this_revision"}


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key: " + key)
        result[key] = value
    return result


def _parse(body):
    def invalid(value):
        raise ValueError("Nonfinite JSON value: " + value)
    try:
        return json.loads(body, object_pairs_hook=_pairs, parse_constant=invalid)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid UTF-8 JSON") from exc


def _bytes(value):
    return (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def _sha(body):
    return hashlib.sha256(body).hexdigest()


def _path(root, relative, allow_missing=False):
    parts = _relative(relative).parts
    path = root
    for part in parts:
        path = path / part
        if path.is_symlink():
            raise ValueError("Symlink is not a public source file: " + relative)
    if not path.resolve().is_relative_to(root):
        raise ValueError("Source path escapes repository: " + relative)
    if not allow_missing and not path.is_file():
        raise ValueError("Missing public source file: " + relative)
    return path


def _read(root, relative):
    path = _path(root, relative)
    before = path.stat()
    if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_BYTES:
        raise ValueError("Source file is nonregular or exceeds read limit: " + relative)
    with path.open("rb") as handle:
        body = handle.read(MAX_BYTES + 1)
    after = path.stat()
    if len(body) != before.st_size or len(body) > MAX_BYTES or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        raise ValueError("Source file changed while reading: " + relative)
    return body


def _roster(root):
    registry = _parse(_read(root, "benchmarks/registry.json"))
    if type(registry) is not dict or type(registry.get("tasks")) is not list:
        raise ValueError("Invalid benchmark registry")
    rows = [row for row in registry["tasks"] if type(row) is dict and row.get("track") == "neural"]
    by_id = {}
    for row in rows:
        task_id = row.get("id")
        if type(task_id) is not str or not re.fullmatch(r"[A-Za-z0-9_-]+", task_id) or task_id in by_id:
            raise ValueError("Invalid or duplicate neural registration ID")
        expected = "benchmarks/neural/" + task_id
        if (row.get("task_directory") != expected or type(row.get("specification")) is not dict
                or row["specification"].get("path") != expected + "/task.json"):
            raise ValueError("Unexpected task path for " + task_id)
        by_id[task_id] = row
    counts = registry.get("source_counts", {})
    if type(counts) is not dict:
        raise ValueError("Invalid source counts in benchmark registry")
    count = counts.get("neural")
    if count is not None and (type(count) is not int or count != len(by_id)):
        raise ValueError("Neural registration count disagrees with roster")
    return by_id


def _original_pin(row):
    revision = row.get("specification_revision", {})
    if type(revision) is not dict:
        raise ValueError("Invalid specification revision for " + row["id"])
    pin = row.get("original_specification") or revision.get("previous_specification") or row.get("specification")
    if type(pin) is not dict or type(pin.get("bytes")) is not int or pin["bytes"] < 0 or not re.fullmatch(r"[0-9a-f]{64}", str(pin.get("sha256", ""))):
        raise ValueError("Missing original specification pin for " + row["id"])
    return pin


def _check_original(row, body):
    pin = _original_pin(row)
    if len(body) != pin["bytes"] or _sha(body) != pin["sha256"]:
        raise ValueError("Historical bytes differ from original registration: " + row["id"])
    doc = _parse(body)
    if type(doc) is not dict or doc.get("objective") == OBJECTIVE:
        raise ValueError("Historical definition is already revised: " + row["id"])
    # Three expansion registrations deliberately retain a HOLD-* source identity.
    expected_id = row.get("specification_id", row["id"])
    found = next((doc[key] for key in ("id", "candidate_id", "task_id") if key in doc), None)
    if found is not None and found != expected_id:
        raise ValueError("Historical specification identity mismatch: " + row["id"])
    if doc.get("track", "neural") != "neural":
        raise ValueError("Historical specification track mismatch: " + row["id"])
    return doc


def _binding(contract_body, original_body):
    return {"schema_version": VERSION, "objective": OBJECTIVE, "contract_path": CONTRACT,
            "contract_sha256": _sha(contract_body), "original_definition_path": HISTORY,
            "original_definition_sha256": _sha(original_body)}


def _source_errors(root, contract, staged=None):
    errors, cache = [], {}
    for evidence in contract["evidence"]:
        if evidence["kind"] == "primary_source":
            continue
        relative = evidence["path"]
        try:
            if relative not in cache:
                cache[relative] = staged[relative] if staged is not None and relative in staged else _read(root, relative)
            if _sha(cache[relative]) != evidence["sha256"]:
                errors.append("Evidence SHA-256 mismatch: " + relative)
        except (OSError, ValueError) as exc:
            errors.append(str(exc))
    return errors


def _load(root, task_id, row):
    home = row["task_directory"]
    current = _parse(_read(root, home + "/task.json"))
    if type(current) is not dict or current.get("objective") != OBJECTIVE:
        raise ValueError("Current task has no neural-understanding objective: " + task_id)
    original_body = _read(root, home + "/" + HISTORY)
    original = _check_original(row, original_body)
    contract_body = _read(root, home + "/" + CONTRACT)
    contract = _parse(contract_body)
    errors = validate_contract(contract, task_id)
    if errors:
        raise ValueError("Invalid " + task_id + " contract: " + "; ".join(errors))
    evaluation = current.get("evaluation")
    if type(evaluation) is not dict or evaluation.get("neural_understanding") != _binding(contract_body, original_body):
        raise ValueError("Stale or invalid neural-understanding binding: " + task_id)
    expected = _current(original, contract, _binding(contract_body, original_body), row.get("specification_id", task_id))
    if current != expected:
        raise ValueError("Current scientific definition differs from its bound contract: " + task_id)
    errors = _source_errors(root, contract)
    if errors:
        raise ValueError("Invalid " + task_id + " evidence: " + "; ".join(errors))
    return contract


def load_neural_understanding(root, task_id):
    """Load one registered contract after checking its history, binding and sources."""
    root = Path(root).resolve()
    roster = _roster(root)
    if task_id not in roster:
        raise ValueError("Unknown neural registration: " + str(task_id))
    return _load(root, task_id, roster[task_id])


def validate_neural_understanding(root):
    """Validate every registered task and exact contract coverage; return errors."""
    root = Path(root).resolve()
    try:
        roster = _roster(root)
    except (OSError, ValueError) as exc:
        return [str(exc)]
    errors = []
    expected = {row["task_directory"] + "/" + CONTRACT for row in roster.values()}
    found = {path.relative_to(root).as_posix() for path in (root / "benchmarks/neural").glob("*/" + CONTRACT)}
    for path in sorted(found - expected):
        errors.append("Unregistered neural-understanding contract: " + path)
    for path in sorted(expected - found):
        errors.append("Missing neural-understanding contract: " + path)
    for task_id, row in sorted(roster.items()):
        try:
            _load(root, task_id, row)
        except (OSError, ValueError) as exc:
            errors.append(str(exc))
    return errors


def _current(original, contract, binding, source_id):
    current = copy.deepcopy(original)
    science, observations = contract["scientific_target"], contract["observation_contract"]
    current.update({"id": source_id, "title": contract["title"], "track": "neural", "status": "specification_only", "objective": OBJECTIVE,
                    "scientific_question": science["question"], "primary_outputs": [science["known_answer"]],
                    "biological_unit": science["independent_unit"], "case_definition": science["case_unit"],
                    "allowed_inputs": copy.deepcopy(observations),
                    "split": {"policy": observations["split"], "coverage": observations["coverage"]},
                    "controls": list(contract["evaluation"]["nuisance_controls"]),
                    "access_conditions": copy.deepcopy(contract["access_modes"]),
                    "evaluation": {**copy.deepcopy(contract["evaluation"]), "neural_understanding": binding},
                    "admission": {"runnable": False, "research_qualified": False, "submission_ready": False,
                        "reason": "This revised scientific contract has no full-task execution admission; source components and scoped operator routes are described separately."}})
    # This adopted DoSEI condition supersedes five inherited dense/pre-onset
    # descriptions. Its original provenance and earlier projection stay intact.
    if contract["task_id"] == "clinical-dosei-responsiveness" and any(
            item.get("id") == "dosei-native-condition-v1"
            and item.get("kind") == "local_review"
            and item.get("path") == "benchmarks/neural/clinical-dosei-responsiveness/implementations/source-native-intake-v1/SOURCE_CONDITION_AMENDMENT.json"
            and item.get("sha256") == "d2c2514d9376948ed44234b59a553fa6ba043facfd534c1e3359c129de487719"
            for item in contract["evidence"]):
        current["participant_inputs"] = " ".join(observations["inputs"] + observations["forbidden_inputs"])
        current["complete_scope"]["input"] = current["participant_inputs"]
        current["complete_scope"]["complete_compact_representation"] = " ".join(observations["inputs"]) + " " + observations["coverage"]
        current["machine_output"]["coverage"] = observations["coverage"]
        current["resources_and_remaining_gates"]["planning"] = contract["access_modes"]["direct_observation"]["boundary"]
    # The adopted calcium successor supplies prospective code while retaining
    # the historical author-method limitation and authentic qualification holds.
    if contract["task_id"] == "NEURAL-025" and any(
            item.get("id") == "v2-condition"
            and item.get("kind") == "local_source"
            and item.get("path") == "benchmarks/neural/NEURAL-025/implementations/train-only-decoding-v2/source_condition.py"
            and item.get("sha256") == "c7ce9b2e464c262550e6e224d7d81becb1094306ff5aeedf819068eb8d14ce11"
            for item in contract["evidence"]):
        current["holds"][0]["requirement"] = "Qualify supplied native clock/ROI correction and calcium-derived feature provenance; the separately named prospective decoder already fits variance selection and PCA on declared training trials only. Authentic reference/control competence remains unverified."
        current["holds"][1]["requirement"] = "Historical author decoder PCA precedes CV; retain this restriction for any author-parity baseline. The separately named prospective v2 decoder uses train-only fitting and still requires authentic competence qualification; it does not establish author Figure5 reproduction."
        current["holds"][7]["requirement"] = "The measured-target evaluator and generated negative/control source exist. Independently qualify scoring, complete-support failure handling and controls on authentic inputs under a protected target boundary and externally frozen protocol."
        current["next_implementation_action"][0] = "Provision and authenticate supported original/locked inputs, verify native grid/trial/ROI and separately recorded exposure provenance, then qualify complete-cohort reference/control execution under the adopted v2 processed-input condition."
    return current


def build_outputs(root):
    """Plan deterministic task/history/contract bytes; never write or update registry.

    Existing historical bytes must match the immutable original registration.
    Only original task evidence references with the matching original hash move
    to historical paths. Deliberate contract edits are permitted; the original
    identity/hash cannot be changed by an edited current binding.
    """
    root = Path(root).resolve()
    roster = _roster(root)
    originals, documents, outputs = {}, {}, {}
    for task_id, row in sorted(roster.items()):
        home = row["task_directory"]
        task_path, history_path = home + "/task.json", home + "/" + HISTORY
        current_body = _read(root, task_path)
        current = _parse(current_body)
        if type(current) is not dict:
            raise ValueError("Current task definition must be an object: " + task_id)
        current_evaluation = current.get("evaluation", {})
        if type(current_evaluation) is not dict:
            raise ValueError("Current task evaluation must be an object: " + task_id)
        existing_history = _path(root, history_path, allow_missing=True)
        if existing_history.exists():
            original_body = _read(root, history_path)
        elif current.get("objective") == OBJECTIVE or "neural_understanding" in current_evaluation:
            raise ValueError("Revised task is missing historical definition: " + task_id)
        else:
            original_body = current_body
        documents[task_id] = _check_original(row, original_body)
        originals[task_path] = (history_path, original_body)
        outputs[history_path] = original_body
    for task_id, row in sorted(roster.items()):
        home = row["task_directory"]
        contract = _parse(_read(root, home + "/" + CONTRACT))
        errors = validate_contract(contract, task_id)
        if errors:
            raise ValueError("Invalid " + task_id + " contract: " + "; ".join(errors))
        contract = copy.deepcopy(contract)
        rewritten = {}
        for evidence in contract["evidence"]:
            if evidence["kind"] != "primary_source" and evidence["path"] in originals:
                old = evidence["path"]
                history_path, original_body = originals[old]
                if evidence["sha256"] != _sha(original_body):
                    raise ValueError("Task evidence does not pin the original definition: " + old)
                evidence["path"] = history_path
                rewritten[old] = history_path
        contract["implementation"]["reviewed_paths"] = [rewritten.get(path, path)
            for path in contract["implementation"]["reviewed_paths"]]
        errors = validate_contract(contract, task_id) + _source_errors(root, contract, outputs)
        if errors:
            raise ValueError("Invalid " + task_id + " evidence: " + "; ".join(errors))
        contract_body = _bytes(contract)
        original_body = originals[home + "/task.json"][1]
        outputs[home + "/" + CONTRACT] = contract_body
        outputs[home + "/task.json"] = _bytes(_current(documents[task_id], contract, _binding(contract_body, original_body), row.get("specification_id", task_id)))
    found = {path.relative_to(root).as_posix() for path in (root / "benchmarks/neural").glob("*/" + CONTRACT)}
    expected = {row["task_directory"] + "/" + CONTRACT for row in roster.values()}
    if found - expected:
        raise ValueError("Unregistered neural-understanding contracts: " + ", ".join(sorted(found - expected)))
    return {Path(path): body for path, body in outputs.items()}
