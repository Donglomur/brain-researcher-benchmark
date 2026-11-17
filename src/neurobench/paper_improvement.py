"""Strict, stdlib-only paper improvement contracts and evidence admission.

``contract_validate(document, task_id=None)`` returns errors, never readiness by
file existence. ``compare(contract, result)`` checks a declared final result
against the frozen policy. It neither executes an evaluator nor authenticates
artifacts, observations, independence, source interpretation, or current SOTA.
``comparison_admitted`` means the metadata satisfies the frozen policy. Even
then ``paper_win`` is null/unverified; metadata alone never verifies a victory.

The public JSON schema is generated from CONTRACT_SCHEMA. RESULT_SCHEMA (also
in that schema's $defs) documents the result accepted by compare. Digests are
SHA256 of UTF-8 canonical JSON (sorted keys, compact separators, no NaN), not
the hash of a pretty-printed contract file. No data or artifact files are read.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, localcontext
import hashlib
import json
import math
from pathlib import Path
import re
from urllib.parse import urlsplit


ANCHORS = ("target", "dataset", "cohort", "split", "inputs", "preprocessing", "metric", "aggregation")
DISPOSITIONS = ("improvement_ready", "design_ready", "source_unresolved", "ineligible")
ASSURANCE = "Declared evidence consistency only; artifacts and scientific validity are not independently authenticated."


def _obj(properties, optional=()):
    return {"type": "object", "properties": properties,
            "required": [key for key in properties if key not in optional], "additionalProperties": False}


def _enum(*values):
    return {"enum": list(values)}


def _array(items, minimum=0, unique=False):
    result = {"type": "array", "items": items, "minItems": minimum}
    if unique:
        result["uniqueItems"] = True
    return result


TEXT = {"type": "string", "minLength": 1, "pattern": r"\S"}
NULL_TEXT = {"anyOf": [TEXT, {"type": "null"}]}
NUMBER = {"type": "number"}
NULL_NUMBER = {"type": ["number", "null"]}
SHA = {"type": "string", "pattern": r"^[0-9a-f]{64}(?![\s\S])"}
URL = {"type": "string", "format": "http-url", "minLength": 1}
STAMP = {"type": "string", "format": "date-time"}
REFS = _array(TEXT, unique=True)
POS_REFS = _array(TEXT, minimum=1, unique=True)
STATUS = _enum("verified", "unresolved", "not_applicable")
ANCHOR_SCHEMA = _obj({"status": STATUS, "description": TEXT, "evidence_ids": REFS})
SAME_TASK_SCHEMA = _obj({key: ANCHOR_SCHEMA for key in ANCHORS})
BASELINE_SCHEMA = _obj({"status": STATUS, "value": NULL_NUMBER, "description": TEXT, "evidence_ids": REFS})
BUDGET_SCHEMA = _obj({"unit": TEXT, "limit": {"type": "number", "minimum": 0}, "scope": {"const": "cumulative_episode"}})
RULE_SCHEMA = _obj({
    "statistic": _enum("effect_lower_bound", "p_value", "posterior_probability"),
    "operator": _enum(">", ">=", "<", "<="), "threshold": NUMBER,
    "method": TEXT, "independent_unit": TEXT,
    "minimum_independent_units": {"type": "integer", "minimum": 1},
    "confidence_level": NULL_NUMBER, "null_effect": {"type": "number", "minimum": 0},
    "alternative": {"const": "directional_improvement"}, "evidence_ids": POS_REFS,
    "comparison_target": {"const": "stronger_of_published_and_reproduced_author"},
})
REQUIREMENT_CHECKS = ("same_task", "published_effect", "reproduced_author_effect", "uncertainty",
                      "candidate_freeze", "final_evaluation", "budgets", "provenance")
POLICY_SCHEMA = _obj({
    "evaluator": _obj({"id": TEXT, "sha256": SHA, "status": {"const": "verified"}, "evidence_ids": POS_REFS}),
    "author_baseline": _obj({"route": _enum("reproduced_author", "source_authorized_route"),
                             "description": TEXT, "tolerance": {"type": "number", "minimum": 0}, "evidence_ids": POS_REFS}),
    "comparator": {"const": "both_published_and_reproduced_author"},
    "metric_domain": _obj({"minimum": NULL_NUMBER, "maximum": NULL_NUMBER, "rationale": TEXT, "evidence_ids": POS_REFS}),
    "effect_operator": _enum(">", ">="), "uncertainty_rule": RULE_SCHEMA,
    "requirement_checks": _array(_obj({"requirement": TEXT, "checks": _array(_enum(*REQUIREMENT_CHECKS), minimum=1, unique=True)}), minimum=1),
    "budgets": _obj({"access": BUDGET_SCHEMA, "resource": BUDGET_SCHEMA}),
})

_RESULT_EVIDENCE = _obj({"id": TEXT, "kind": _enum("candidate", "freeze", "evaluation", "reproduced_baseline", "budget"),
                         "sha256": SHA, "locator": TEXT})
_USAGE = _obj({"unit": TEXT, "used": {"type": "number", "minimum": 0},
               "scope": {"const": "cumulative_episode"}, "evidence_ids": POS_REFS})
RESULT_SCHEMA = _obj({
    "schema_version": {"const": "paper-improvement-result/v1"}, "task_id": TEXT,
    "claim": _enum("same_task_paper_improvement", "prospective_extension", "reproduction_only", "candidate_vs_local_baseline"),
    "phase": _enum("validation", "final"), "contract_digest": SHA, "candidate_sha256": SHA,
    "same_task": SAME_TASK_SCHEMA,
    "source_evidence_ids": POS_REFS,
    "freeze": _obj({"contract_digest": SHA, "candidate_sha256": SHA, "frozen_at": STAMP, "evidence_ids": POS_REFS}),
    "evaluation": _obj({"evaluator_id": TEXT, "evaluator_sha256": SHA, "contract_digest": SHA,
                        "candidate_sha256": SHA, "started_at": STAMP, "evidence_ids": POS_REFS}),
    "measurement": _obj({"primary_metric": TEXT, "direction": _enum("higher", "lower"),
                         "candidate_value": NUMBER, "comparator_kind": {"const": "published_source_paper"}, "published_value": NUMBER}),
    "reproduced_author_baseline": _obj({"value": NUMBER, "same_task": SAME_TASK_SCHEMA, "evidence_ids": POS_REFS}),
    "uncertainty": _obj({"statistic": RULE_SCHEMA["properties"]["statistic"], "value": NUMBER,
                         "method": TEXT, "independent_unit": TEXT,
                         "n_independent_units": {"type": "integer", "minimum": 1},
                         "confidence_level": NULL_NUMBER, "null_effect": NUMBER,
                         "alternative": {"const": "directional_improvement"},
                         "comparison_target": {"const": "stronger_of_published_and_reproduced_author"},
                         "published_value": NUMBER, "reproduced_value": NUMBER, "comparator_value": NUMBER,
                         "candidate_sha256": SHA, "contract_digest": SHA,
                         "interval": {"anyOf": [{"type": "null"}, {"type": "array", "items": NUMBER, "minItems": 2, "maxItems": 2}]},
                         "evidence_ids": POS_REFS}),
    "budget_usage": _obj({"access": _USAGE, "resource": _USAGE}),
    "evidence": _array(_RESULT_EVIDENCE, minimum=1),
})
CONTRACT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://neurobench.org/schemas/paper-improvement/v1",
    "title": "Paper improvement contract v1",
    "description": "Structural schema. contract_validate also enforces evidence references and readiness semantics; compare enforces frozen final-result admission. A contract alone establishes no scientific result.",
    **_obj({
        "schema_version": {"const": "paper-improvement/v1"}, "task_id": TEXT,
        "objective": {"const": "surpass_source_paper_same_task"},
        "disposition": _enum(*DISPOSITIONS), "disposition_reason": TEXT,
        "source_paper": _obj({"title": TEXT, "url": {"anyOf": [URL, {"type": "null"}]}}),
        "evidence": _array(_obj({"id": TEXT, "kind": _enum("paper", "author_code", "author_data", "registration"),
                                 "url": URL, "locator": TEXT, "supports": {"anyOf": [TEXT, _array(TEXT, minimum=1)]}})),
        "same_task": SAME_TASK_SCHEMA,
        "comparison": _obj({
            "primary_metric": TEXT, "direction": _enum("higher", "lower", "unresolved"),
            "published_baseline": BASELINE_SCHEMA, "reproduced_author_baseline": BASELINE_SCHEMA,
            "minimum_effect": _obj({"status": _enum("justified", "unresolved", "not_applicable"),
                                    "value": NULL_NUMBER, "rationale": TEXT, "evidence_ids": REFS}),
            "uncertainty": _obj({"status": _enum("specified", "unresolved", "not_applicable"),
                                 "method": TEXT, "independent_unit": TEXT, "rationale": TEXT, "evidence_ids": REFS}),
            "paper_win_requires": _array(TEXT, minimum=1, unique=True),
            "current_sota": _obj({"status": _enum("not_claimed", "source_verified"), "description": TEXT, "evidence_ids": REFS}),
        }),
        "episode": _obj({"improvement_loop": TEXT, "candidate_freeze": TEXT, "final_evaluation": TEXT,
                         "access_budget": NULL_TEXT, "resource_budget": NULL_TEXT, "baseline_policy": TEXT}),
        "blocking_issues": _array(TEXT, unique=True),
        # The registry distinguishes a revision from an initial registration.
        # A new task has no invented historical reconstruction definition.
        # This schema cannot authenticate that lineage; registry checks bind it.
        "legacy": {"anyOf": [
            _obj({"role": {"const": "calibration_only"},
                  "original_task": {"const": "historical/task.pre-improvement.v1.json"}, "notes": TEXT}),
            _obj({"role": {"const": "no_predecessor"},
                  "original_task": {"type": "null"}, "notes": TEXT}),
        ]},
        "admission_policy": POLICY_SCHEMA,
    }, optional=("admission_policy",)),
    "$defs": {"admission_result": RESULT_SCHEMA},
}


def _json_errors(value, path="$", active=None):
    """Reject Python-only values, nonfinite numbers and cycles before schema use."""
    active = set() if active is None else active
    errors = []
    if type(value) in (dict, list):
        if id(value) in active:
            return [f"{path}: cyclic value is not JSON"]
        active.add(id(value))
        for key, item in (value.items() if type(value) is dict else enumerate(value)):
            if type(value) is dict and type(key) is not str:
                errors.append(f"{path}: object keys must be strings")
            errors.extend(_json_errors(item, f"{path}.{key}", active))
        active.remove(id(value))
    elif type(value) in (int, float) and not _finite_number(value):
        errors.append(f"{path}: number must be finite and within evaluator numeric range")
    elif type(value) not in (str, int, float, bool, type(None)):
        errors.append(f"{path}: value is not a JSON type")
    return errors


def _finite_number(value):
    try:
        return math.isfinite(value)
    except (OverflowError, ValueError):
        return False


def _difference(left, right):
    # JSON numeric spellings are interpreted as their declared decimal values.
    # 1000 digits covers the full accepted binary64 exponent span without an
    # arbitrary epsilon or false strict-threshold wins from binary subtraction.
    with localcontext() as context:
        context.prec = 1000
        return Decimal(str(left)) - Decimal(str(right))


def _timestamp(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timezone required")
    return parsed


def _schema_errors(value, schema, path="$"):
    """Apply only the explicit JSON Schema subset used above; no dependencies."""
    errors = []
    if "anyOf" in schema:
        if not any(not _schema_errors(value, option, path) for option in schema["anyOf"]):
            errors.append(f"{path}: does not match an allowed type/shape")
        return errors
    types = {"object": dict, "array": list, "string": str, "integer": int, "boolean": bool, "null": type(None)}
    declared = schema.get("type")
    if declared:
        allowed = declared if isinstance(declared, list) else [declared]
        if not any(type(value) in (int, float) if kind == "number" else type(value) is types[kind] for kind in allowed):
            return [f"{path}: expected {declared}"]
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: expected {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: unsupported value {value!r}")
    if type(value) is dict:
        properties = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path}.{key}: required")
        for key, item in value.items():
            if key in properties:
                errors.extend(_schema_errors(item, properties[key], f"{path}.{key}"))
            elif schema.get("additionalProperties") is False:
                errors.append(f"{path}.{key}: unknown field")
    elif type(value) is list:
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", len(value)):
            errors.append(f"{path}: invalid number of items")
        if schema.get("uniqueItems") and len({_canonical(item) for item in value}) != len(value):
            errors.append(f"{path}: duplicate items")
        for index, item in enumerate(value):
            errors.extend(_schema_errors(item, schema.get("items", {}), f"{path}[{index}]"))
    elif type(value) is str:
        if len(value) < schema.get("minLength", 0) or ("pattern" in schema and not re.search(schema["pattern"], value)):
            errors.append(f"{path}: invalid or empty string")
        if schema.get("format") == "http-url":
            try:
                parsed = urlsplit(value)
                valid = parsed.scheme in ("http", "https") and parsed.hostname and not parsed.username and not parsed.password and not re.search(r"\s", value)
            except ValueError:
                valid = False
            if not valid:
                errors.append(f"{path}: expected a public HTTP(S) source URL")
        if schema.get("format") == "date-time":
            try:
                _timestamp(value)
            except (ValueError, OverflowError):
                errors.append(f"{path}: expected an ISO timestamp with timezone")
    elif type(value) in (int, float):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: below minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: above maximum {schema['maximum']}")
    return errors


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def contract_digest(document):
    """Canonical JSON SHA256; does not validate scientific readiness."""
    errors = _json_errors(document)
    if errors:
        raise ValueError("; ".join(errors))
    return hashlib.sha256(_canonical(document).encode("utf-8")).hexdigest()


def loads_contract(text):
    """Parse strict JSON, rejecting duplicate object keys and NaN/Infinity."""
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def nonfinite(value):
        raise ValueError(f"nonfinite JSON number: {value}")

    document = json.loads(text, object_pairs_hook=pairs, parse_constant=nonfinite)
    errors = _json_errors(document)  # also catches overflow, e.g. 1e10000
    if errors:
        raise ValueError("; ".join(errors))
    return document


def load_contract(path):
    """Read only the explicitly supplied contract/result JSON metadata file."""
    return loads_contract(Path(path).read_text(encoding="utf-8"))


def _refs_in(value, path="$"):
    if type(value) is dict:
        for key, item in value.items():
            if key == "evidence_ids":
                yield f"{path}.{key}", item
            else:
                yield from _refs_in(item, f"{path}.{key}")
    elif type(value) is list:
        for index, item in enumerate(value):
            yield from _refs_in(item, f"{path}[{index}]")


def _evidence_map(evidence, errors, prefix="$.evidence"):
    result = {}
    for item in evidence:
        if item["id"] in result:
            errors.append(f"{prefix}: duplicate evidence id {item['id']!r}")
        result[item["id"]] = item
    return result


def contract_validate(document, task_id=None):
    """Return structural, reference and disposition errors for a contract."""
    errors = _json_errors(document)
    if errors:
        return errors
    errors = _schema_errors(document, CONTRACT_SCHEMA)
    if errors:
        return errors
    if task_id is not None and document["task_id"] != task_id:
        errors.append("$.task_id: does not match expected task identity")
    evidence = _evidence_map(document["evidence"], errors)
    for path, refs in _refs_in(document):
        for ref in refs:
            if ref not in evidence:
                errors.append(f"{path}: unknown evidence id {ref!r}")

    def primary(record, path):
        if not any(evidence.get(ref, {}).get("kind") in ("paper", "author_code", "author_data") for ref in record["evidence_ids"]):
            errors.append(f"{path}: requires primary source evidence; registration alone is insufficient")

    for key, record in document["same_task"].items():
        if record["status"] in ("verified", "not_applicable"):
            primary(record, f"$.same_task.{key}")
    comparison = document["comparison"]
    for key in ("published_baseline", "reproduced_author_baseline"):
        record = comparison[key]
        if record["status"] == "verified":
            primary(record, f"$.comparison.{key}")
        elif record["value"] is not None:
            errors.append(f"$.comparison.{key}.value: unresolved/not_applicable baseline must be null")
    for key, status in (("minimum_effect", "justified"), ("uncertainty", "specified"), ("current_sota", "source_verified")):
        if comparison[key]["status"] == status:
            primary(comparison[key], f"$.comparison.{key}")
    if comparison["minimum_effect"]["status"] != "justified" and comparison["minimum_effect"]["value"] is not None:
        errors.append("$.comparison.minimum_effect.value: unjustified effect must be null")
    if document["source_paper"]["url"] is None and (document["disposition"] not in ("source_unresolved", "ineligible") or not document["blocking_issues"]):
        errors.append("$.source_paper.url: missing source URL requires unresolved/ineligible disposition and an explicit blocker")
    policy = document.get("admission_policy")
    if policy:
        for key in ("evaluator", "author_baseline", "uncertainty_rule", "metric_domain"):
            primary(policy[key], f"$.admission_policy.{key}")
        domain = policy["metric_domain"]
        if domain["minimum"] is not None and domain["maximum"] is not None and domain["minimum"] >= domain["maximum"]:
            errors.append("$.admission_policy.metric_domain: minimum must be below maximum")
        for key in ("published_baseline", "reproduced_author_baseline"):
            if comparison[key]["value"] is not None and not _in_domain(comparison[key]["value"], domain):
                errors.append(f"$.comparison.{key}: score outside declared metric domain")
        rule = policy["uncertainty_rule"]
        bindings = policy["requirement_checks"]
        requirements = [binding["requirement"] for binding in bindings]
        if len(requirements) != len(set(requirements)) or set(requirements) != set(comparison["paper_win_requires"]):
            errors.append("$.admission_policy.requirement_checks: every prose requirement must have exactly one explicit supported machine-check binding")
        for key in ("method", "independent_unit"):
            if rule[key] != comparison["uncertainty"][key]:
                errors.append(f"$.admission_policy.uncertainty_rule.{key}: must match declared uncertainty")
        statistic, threshold, operator = rule["statistic"], rule["threshold"], rule["operator"]
        if statistic == "effect_lower_bound":
            if operator not in (">", ">=") or threshold < rule["null_effect"] or (threshold == rule["null_effect"] and operator == ">="):
                errors.append("$.admission_policy.uncertainty_rule: lower bound must establish directional improvement beyond null_effect")
            if rule["confidence_level"] is None or not 0 < rule["confidence_level"] < 1:
                errors.append("$.admission_policy.uncertainty_rule.confidence_level: interval rule requires explicit level in (0,1)")
        else:
            if rule["confidence_level"] is not None:
                errors.append("$.admission_policy.uncertainty_rule.confidence_level: only interval rules use this field")
            if statistic == "p_value" and (operator not in ("<", "<=") or not 0 < threshold < 1):
                errors.append("$.admission_policy.uncertainty_rule: p-value rule requires declared upper threshold in (0,1)")
            if statistic == "posterior_probability" and (operator not in (">", ">=") or not 0.5 < threshold <= 1):
                errors.append("$.admission_policy.uncertainty_rule: posterior rule requires declared lower threshold above 0.5")
    if document["disposition"] in ("design_ready", "improvement_ready"):
        for key in ("target", "metric"):
            if document["same_task"][key]["status"] != "verified":
                errors.append(f"$.same_task.{key}: source-grounded design/readiness requires a verified target and metric")
    if document["disposition"] != "improvement_ready":
        return errors
    if document["blocking_issues"]:
        errors.append("$.blocking_issues: improvement_ready cannot retain blockers")
    for key, record in document["same_task"].items():
        if record["status"] not in ("verified", "not_applicable"):
            errors.append(f"$.same_task.{key}: improvement_ready requires recovered original anchor")
    if comparison["direction"] == "unresolved":
        errors.append("$.comparison.direction: improvement_ready requires metric direction")
    published = comparison["published_baseline"]
    if published["status"] != "verified" or published["value"] is None:
        errors.append("$.comparison.published_baseline: improvement_ready requires numeric verified published score")
    effect = comparison["minimum_effect"]
    if effect["status"] != "justified" or effect["value"] is None or effect["value"] <= 0:
        errors.append("$.comparison.minimum_effect: improvement_ready requires a positive justified effect")
    if comparison["uncertainty"]["status"] != "specified":
        errors.append("$.comparison.uncertainty: improvement_ready requires specified uncertainty")
    for key in ("access_budget", "resource_budget"):
        if document["episode"][key] is None:
            errors.append(f"$.episode.{key}: improvement_ready requires a concrete budget")
    if policy is None:
        errors.append("$.admission_policy: improvement_ready requires an executable admission policy")
    else:
        reproduced = comparison["reproduced_author_baseline"]
        if policy["author_baseline"]["route"] == "reproduced_author" and (reproduced["status"] != "verified" or reproduced["value"] is None):
            errors.append("$.comparison.reproduced_author_baseline: reproduced_author route requires a numeric verified baseline")
        if reproduced["value"] is not None and published["value"] is not None and abs(_difference(reproduced["value"], published["value"])) > Decimal(str(policy["author_baseline"]["tolerance"])):
            errors.append("$.comparison.reproduced_author_baseline: exceeds predeclared reproduction tolerance from published result")
    return errors


def validate_contract(document, task_id=None, *, expected_task_id=None):
    """Compatibility spelling for catalog and binding builders."""
    if task_id is not None and expected_task_id is not None and task_id != expected_task_id:
        return ["task_id and expected_task_id disagree"]
    return contract_validate(document, task_id if task_id is not None else expected_task_id)


def summary(document):
    """Small catalog-safe metadata summary; no paper victory or SOTA inferred."""
    errors = contract_validate(document)
    valid = not errors
    safe = document if type(document) is dict else {}
    comparison = safe.get("comparison") if type(safe.get("comparison")) is dict else {}
    return {"task_id": safe.get("task_id"), "objective": safe.get("objective"),
            "disposition": safe.get("disposition"), "disposition_reason": safe.get("disposition_reason"),
            "valid": valid, "improvement_ready": valid and safe.get("disposition") == "improvement_ready",
            "primary_metric": comparison.get("primary_metric"), "direction": comparison.get("direction"),
            "blocking_issues": safe.get("blocking_issues", []), "errors": errors,
            "contract_digest": contract_digest(document) if valid else None,
            "paper_win": False, "current_sota": "not_assessed", "assurance": ASSURANCE}


contract_summary = summary


def _passes(value, operator, threshold):
    value, threshold = Decimal(str(value)), Decimal(str(threshold))
    if operator == ">":
        return value > threshold
    if operator == ">=":
        return value >= threshold
    if operator == "<":
        return value < threshold
    if operator == "<=":
        return value <= threshold
    return False


def _in_domain(value, domain):
    return ((domain["minimum"] is None or value >= domain["minimum"])
            and (domain["maximum"] is None or value <= domain["maximum"]))


def compare(contract, result):
    """Admit only a frozen, same-task, final improvement under declared rules.

    All inputs are public JSON metadata. Callers remain responsible for trusted
    evidence collection, evaluator execution, complete budget accounting and
    verifying that the frozen candidate predates any protected final feedback.
    Validation feedback is never a final paper win. Current SOTA is never inferred.
    """
    errors = contract_validate(contract)
    response = {"paper_win": False, "comparison_admitted": False, "paper_win_verification": "unverified",
                "status": "rejected", "errors": errors,
                "current_sota": "not_assessed", "assurance": ASSURANCE,
                "published_improvement": None, "reproduced_improvement": None}
    if errors:
        return response
    result_errors = _json_errors(result)
    if not result_errors:
        result_errors = _schema_errors(result, RESULT_SCHEMA)
    if result_errors:
        errors.extend(result_errors)
        return response
    if contract["disposition"] != "improvement_ready":
        errors.append("contract disposition is not improvement_ready")
        return response
    policy, comparison = contract["admission_policy"], contract["comparison"]
    if result["task_id"] != contract["task_id"]:
        errors.append("result task_id does not match contract")
    if result["claim"] != "same_task_paper_improvement":
        errors.append("only same_task_paper_improvement is admissible; extension/reproduction/local-baseline claims cannot paper-win")
    if result["phase"] != "final":
        errors.append("validation feedback cannot establish a final paper win")
    digest = contract_digest(contract)
    for path, record in (("result", result), ("freeze", result["freeze"]), ("evaluation", result["evaluation"])):
        if record["contract_digest"] != digest:
            errors.append(f"{path}.contract_digest does not match frozen contract")
        if record["candidate_sha256"] != result["candidate_sha256"]:
            errors.append(f"{path}.candidate_sha256 does not match frozen candidate")
    if _timestamp(result["freeze"]["frozen_at"]) >= _timestamp(result["evaluation"]["started_at"]):
        errors.append("candidate freeze must precede final evaluation")
    for label, anchors in (("result", result["same_task"]), ("reproduced_author_baseline", result["reproduced_author_baseline"]["same_task"])):
        for key in ANCHORS:
            if anchors[key] != contract["same_task"][key]:
                errors.append(f"{label}.same_task.{key} differs from original paper anchor")
    for key in ("id", "sha256"):
        if result["evaluation"][f"evaluator_{key}"] != policy["evaluator"][key]:
            errors.append(f"evaluation.evaluator_{key} differs from declared evaluator")
    required_source = {ref for _, refs in _refs_in(contract) for ref in refs}
    if set(result["source_evidence_ids"]) != required_source:
        errors.append("source_evidence_ids must match the frozen contract's referenced evidence")
    evidence = _evidence_map(result["evidence"], errors, "result.evidence")

    def result_refs(record, kind, label):
        for ref in record["evidence_ids"]:
            if ref not in evidence or evidence[ref]["kind"] != kind:
                errors.append(f"{label}.evidence_ids requires recorded {kind} provenance ({ref!r})")

    candidates = [item for item in result["evidence"] if item["kind"] == "candidate"]
    if not candidates or any(item["sha256"] != result["candidate_sha256"] for item in candidates):
        errors.append("candidate evidence must identify the frozen candidate hash")
    for key, kind in (("freeze", "freeze"), ("evaluation", "evaluation"), ("reproduced_author_baseline", "reproduced_baseline"), ("uncertainty", "evaluation")):
        result_refs(result[key], kind, key)
    if not set(result["uncertainty"]["evidence_ids"]).issubset(result["evaluation"]["evidence_ids"]):
        errors.append("uncertainty provenance must belong to this final evaluation")
    measurement = result["measurement"]
    for label, value in (("candidate", measurement["candidate_value"]), ("published", measurement["published_value"]),
                         ("reproduced_author", result["reproduced_author_baseline"]["value"])):
        if not _in_domain(value, policy["metric_domain"]):
            errors.append(f"{label} score is outside declared metric domain")
    for key in ("primary_metric", "direction"):
        if measurement[key] != comparison[key]:
            errors.append(f"measurement.{key} differs from original metric")
    published = comparison["published_baseline"]["value"]
    if measurement["published_value"] != published:
        errors.append("measurement.published_value differs from verified source-paper baseline")
    reproduced = result["reproduced_author_baseline"]["value"]
    tolerance = policy["author_baseline"]["tolerance"]
    if abs(_difference(reproduced, published)) > Decimal(str(tolerance)):
        errors.append("reproduced author baseline is outside declared tolerance from published score")
    pinned_reproduction = comparison["reproduced_author_baseline"]["value"]
    if pinned_reproduction is not None and abs(_difference(reproduced, pinned_reproduction)) > Decimal(str(tolerance)):
        errors.append("reproduced author baseline differs from frozen reproduced baseline beyond tolerance")
    sign = 1 if comparison["direction"] == "higher" else -1
    effect = _difference(measurement["candidate_value"], published)
    reproduction_effect = _difference(measurement["candidate_value"], reproduced)
    if sign < 0:
        effect, reproduction_effect = effect.copy_negate(), reproduction_effect.copy_negate()
    if not _finite_number(effect) or not _finite_number(reproduction_effect):
        errors.append("computed improvement must be finite")
    else:
        response["published_improvement"] = float(effect)
        response["reproduced_improvement"] = float(reproduction_effect)
        if not _passes(effect, policy["effect_operator"], comparison["minimum_effect"]["value"]):
            errors.append("candidate does not exceed published score by the declared meaningful effect")
        if not _passes(reproduction_effect, policy["effect_operator"], comparison["minimum_effect"]["value"]):
            errors.append("candidate does not exceed reproduced author score by the declared meaningful effect")
    rule, uncertainty = policy["uncertainty_rule"], result["uncertainty"]
    for key in ("statistic", "method", "independent_unit", "confidence_level", "null_effect", "alternative", "comparison_target"):
        if uncertainty[key] != rule[key]:
            errors.append(f"uncertainty.{key} differs from frozen rule")
    stronger = max(published, reproduced) if sign > 0 else min(published, reproduced)
    for key, expected in (("published_value", published), ("reproduced_value", reproduced), ("comparator_value", stronger),
                          ("contract_digest", digest), ("candidate_sha256", result["candidate_sha256"])):
        if uncertainty[key] != expected:
            errors.append(f"uncertainty.{key} does not bind the current candidate and stronger author comparator")
    if uncertainty["n_independent_units"] < rule["minimum_independent_units"]:
        errors.append("uncertainty has fewer independent units than the declared rule")
    if rule["statistic"] == "effect_lower_bound":
        interval = uncertainty["interval"]
        if interval is None or interval[0] > interval[1] or uncertainty["value"] != interval[0]:
            errors.append("uncertainty interval must be ordered improvement-oriented bounds with value equal to its lower bound")
    elif uncertainty["interval"] is not None or not 0 <= uncertainty["value"] <= 1:
        errors.append("p-value/posterior uncertainty requires a probability in [0,1] and a null interval")
    if not _passes(uncertainty["value"], rule["operator"], rule["threshold"]):
        errors.append("uncertainty fails the actual predeclared rule")
    for key, budget in policy["budgets"].items():
        usage = result["budget_usage"][key]
        result_refs(usage, "budget", f"budget_usage.{key}")
        if usage["unit"] != budget["unit"] or usage["scope"] != budget["scope"]:
            errors.append(f"budget_usage.{key}: unit/scope mismatch")
        if usage["used"] > budget["limit"]:
            errors.append(f"budget_usage.{key}: cumulative episode budget exceeded")
    if not errors:
        response.update(comparison_admitted=True, paper_win=None, status="admitted_on_declared_evidence")
    return response


admit_comparison = compare
