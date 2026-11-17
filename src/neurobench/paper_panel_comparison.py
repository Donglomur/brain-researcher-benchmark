"""Complete, role-aware paper panels; declared metadata is never scientific proof.

This additive interface reuses the scalar contract's strict JSON, source anchors,
provenance, freeze, evaluator and cumulative-budget vocabulary. It does not read
artifacts, execute a scorer, authenticate source interpretation or infer SOTA.
"""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from . import paper_improvement as scalar

VERSION = "paper-panel-comparison/v1"
RESULT_VERSION = "paper-panel-comparison-result/v1"
ASSURANCE = scalar.ASSURANCE
obj, enum, array = scalar._obj, scalar._enum, scalar._array
TEXT, SHA, REFS, POS_REFS = scalar.TEXT, scalar.SHA, scalar.REFS, scalar.POS_REFS
NULL_NUMBER = scalar.NULL_NUMBER
PIN = obj({"path": TEXT, "bytes": {"type": "integer", "minimum": 1}, "sha256": SHA})
DECLARED_NUMBER = obj({"status": enum("justified", "unresolved", "not_applicable"),
    "value": NULL_NUMBER, "rationale": TEXT, "evidence_ids": REFS})
CONTROL_RULE = obj({"status": enum("specified", "unresolved", "not_applicable"),
    "minimum": NULL_NUMBER, "maximum": NULL_NUMBER, "rationale": TEXT, "evidence_ids": REFS})
GROUP = obj({"id": TEXT, "role": enum("score", "control"), "description": TEXT,
    "independent_unit": TEXT, "support_description": TEXT, "evidence_ids": POS_REFS})
COORDINATE = obj({"id": TEXT, "group_id": TEXT, "role": enum("score", "control"),
    "support_key": TEXT, "metric": TEXT, "unit": TEXT,
    "direction": enum("higher", "lower", "unresolved", "not_applicable"),
    "published_baseline": scalar.BASELINE_SCHEMA,
    "reproduced_author_baseline": scalar.BASELINE_SCHEMA,
    "reproduction_tolerance": DECLARED_NUMBER,
    "minimum_gain": DECLARED_NUMBER, "gain_eligible": {"type": "boolean"},
    "gain_operator": enum(">", ">="), "control_rule": CONTROL_RULE,
    "metric_domain": obj({"minimum": NULL_NUMBER, "maximum": NULL_NUMBER,
                          "rationale": TEXT, "evidence_ids": POS_REFS}),
    "evidence_ids": POS_REFS})
_BINDING_POLICY = obj({
    "evaluator": deepcopy(scalar.POLICY_SCHEMA["properties"]["evaluator"]),
    "budgets": deepcopy(scalar.POLICY_SCHEMA["properties"]["budgets"]),
    "conditions": obj({
        "paper_data": obj({"paper_sha256": SHA, "data_sha256": SHA,
            "official_code_sha256": {"type": "null"}, "tool_policy_sha256": SHA}),
        "paper_data_official_code": obj({"paper_sha256": SHA, "data_sha256": SHA,
            "official_code_sha256": SHA, "tool_policy_sha256": SHA})})})
CONTRACT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://neurobench.org/schemas/paper-panel-comparison/v1",
    "title": "Complete paper panel comparison v1",
    "description": "Metadata consistency and finite numerical policy only. This interface cannot qualify scientific superiority.",
    **obj({"schema_version": {"const": VERSION}, "task_id": TEXT,
        "objective": {"const": "reproduce_and_surpass_source_paper_same_panel"},
        "disposition": enum("source_unresolved", "design_ready", "metadata_ready"),
        "disposition_reason": TEXT,
        "source_paper": deepcopy(scalar.CONTRACT_SCHEMA["properties"]["source_paper"]),
        "evidence": deepcopy(scalar.CONTRACT_SCHEMA["properties"]["evidence"]),
        "same_task": scalar.SAME_TASK_SCHEMA,
        "episode": deepcopy(scalar.CONTRACT_SCHEMA["properties"]["episode"]),
        "lineage": obj({"scalar_contract": PIN, "selected_endpoint_contract": {"anyOf": [PIN, {"type": "null"}]},
                        "notes": TEXT}),
        "panel": obj({"source_manifest": PIN, "support_scope": TEXT,
            "groups": array(GROUP, 1), "coordinates": array(COORDINATE, 1),
            "reference_selection": obj({"status": enum("verified", "unresolved"),
                "description": TEXT, "evidence_ids": POS_REFS}),
            "comparison_target": {"const": "stronger_of_published_and_reproduced_author_per_score_coordinate"},
            "score_rule": {"const": "no_regression_on_every_score_coordinate_and_meaningful_gain_on_at_least_one_eligible_score_coordinate"},
            "control_rule": {"const": "all_required_controls_pass_their_frozen_constraints_without_contributing_improvement"},
            "scalar_aggregation": {"const": "none"}}),
        "scientific_inference": obj({"status": enum("specified", "unresolved"),
            "method": TEXT, "independent_unit": TEXT, "multiplicity_policy": TEXT,
            "evidence_ids": REFS}),
        "blocking_issues": array(TEXT, unique=True),
        "binding_policy": _BINDING_POLICY}, optional=("binding_policy",))}
_RESULT_PROPS = scalar.RESULT_SCHEMA["properties"]
_CONDITION_FIELDS = {"access_condition": enum("paper_data", "paper_data_official_code"),
                     "condition_binding_digest": SHA}
def _conditioned(schema):
    result = deepcopy(schema)
    result["properties"].update(_CONDITION_FIELDS)
    result["required"].extend(_CONDITION_FIELDS)
    return result

RESULT_SCHEMA = obj({"schema_version": {"const": RESULT_VERSION}, "task_id": TEXT,
    "claim": {"const": "same_task_finite_panel_numerical_comparison"},
    "phase": enum("validation", "final"), "contract_digest": SHA, "candidate_sha256": SHA,
    "same_task": scalar.SAME_TASK_SCHEMA, "source_evidence_ids": POS_REFS,
    "access_condition": enum("paper_data", "paper_data_official_code"),
    "condition_binding": obj({"paper_sha256": SHA, "data_sha256": SHA,
        "official_code_sha256": {"anyOf": [SHA, {"type": "null"}]}, "tool_policy_sha256": SHA}),
    "freeze": _conditioned(_RESULT_PROPS["freeze"]),
    "evaluation": _conditioned(_RESULT_PROPS["evaluation"]),
    "reproduced_author_baseline": obj({"role": {"const": "evaluator_owned_reference_shared_between_assistance_arms"},
        "same_task": scalar.SAME_TASK_SCHEMA, "evidence_ids": POS_REFS}),
    "measurements": array(obj({"id": TEXT, "group_id": TEXT, "role": enum("score", "control"),
        "support_key": TEXT, "metric": TEXT, "unit": TEXT,
        "direction": enum("higher", "lower", "not_applicable"),
        "candidate_value": scalar.NUMBER, "published_value": scalar.NUMBER,
        "reproduced_value": scalar.NUMBER}), 1),
    "budget_usage": deepcopy(_RESULT_PROPS["budget_usage"]),
    "evidence": deepcopy(_RESULT_PROPS["evidence"])})
CONTRACT_SCHEMA["$defs"] = {"admission_result": RESULT_SCHEMA}
def _json_errors(document):
    errors = scalar._json_errors(document)
    if errors:
        return errors
    def visit(value):
        if type(value) is str:
            try:
                value.encode("utf-8", errors="strict")
            except UnicodeEncodeError:
                errors.append("JSON string contains an unpaired Unicode surrogate")
        elif type(value) is dict:
            for key, item in value.items():
                visit(key); visit(item)
        elif type(value) is list:
            for item in value:
                visit(item)
    visit(document)
    return errors


def contract_digest(document):
    errors = _json_errors(document)
    if errors:
        raise ValueError("; ".join(errors))
    return scalar.contract_digest(document)


def loads_contract(text):
    document = scalar.loads_contract(text)
    errors = _json_errors(document)
    if errors:
        raise ValueError("; ".join(errors))
    return document


def load_contract(path):
    from pathlib import Path
    return loads_contract(Path(path).read_text(encoding="utf-8"))


def _decimal(value):
    return Decimal(str(value))


def _in_domain(value, domain):
    number = _decimal(value)
    return ((domain["minimum"] is None or number >= _decimal(domain["minimum"]))
            and (domain["maximum"] is None or number <= _decimal(domain["maximum"])))


def contract_validate(document, task_id=None):
    errors = _json_errors(document)
    if not errors:
        errors = scalar._schema_errors(document, CONTRACT_SCHEMA)
    if errors:
        return errors
    if task_id is not None and document["task_id"] != task_id:
        errors.append("task_id differs from expected task")
    sources = scalar._evidence_map(document["evidence"], errors)
    for path, refs in scalar._refs_in(document):
        for ref in refs:
            if ref not in sources:
                errors.append(f"{path}: unknown evidence {ref}")
    def primary(record, label):
        if not any(sources.get(ref, {}).get("kind") in ("paper", "author_code", "author_data") for ref in record["evidence_ids"]):
            errors.append(f"{label}: primary source evidence required")
    for name, anchor in document["same_task"].items():
        if anchor["status"] in ("verified", "not_applicable"):
            primary(anchor, "same_task." + name)
    panel = document["panel"]
    groups = {}
    for group in panel["groups"]:
        if group["id"] in groups:
            errors.append("duplicate endpoint group")
        groups[group["id"]] = group
        primary(group, "group " + group["id"])
    seen, supports, used_groups = set(), set(), set()
    for coordinate in panel["coordinates"]:
        name = coordinate["id"]
        if name in seen:
            errors.append("duplicate coordinate id: " + name)
        seen.add(name)
        support = (coordinate["group_id"], coordinate["support_key"])
        if support in supports:
            errors.append("duplicate support key within endpoint group")
        supports.add(support); used_groups.add(coordinate["group_id"])
        group = groups.get(coordinate["group_id"])
        if group is None or group["role"] != coordinate["role"]:
            errors.append("coordinate group/role mismatch: " + name)
        primary(coordinate, "coordinate " + name)
        for key in ("published_baseline", "reproduced_author_baseline"):
            row = coordinate[key]
            if row["status"] == "verified":
                if row["value"] is None:
                    errors.append(name + ": verified baseline requires numeric value")
                primary(row, name + "." + key)
            elif row["value"] is not None:
                errors.append(name + ": unresolved baseline value must be null")
        for key in ("reproduction_tolerance", "minimum_gain"):
            row = coordinate[key]
            if row["status"] == "justified":
                if row["value"] is None or _decimal(row["value"]) < 0 or (key == "minimum_gain" and _decimal(row["value"]) == 0):
                    errors.append(name + ": invalid justified " + key)
                primary(row, name + "." + key)
            elif row["value"] is not None:
                errors.append(name + ": unjustified threshold must be null")
        domain = coordinate["metric_domain"]
        primary(domain, name + ".metric_domain")
        if domain["minimum"] is not None and domain["maximum"] is not None and _decimal(domain["minimum"]) >= _decimal(domain["maximum"]):
            errors.append(name + ": invalid metric domain")
        for key in ("published_baseline", "reproduced_author_baseline"):
            value = coordinate[key]["value"]
            if value is not None and not _in_domain(value, domain):
                errors.append(name + ": baseline outside metric domain")
        rule = coordinate["control_rule"]
        if coordinate["role"] == "control":
            if coordinate["direction"] != "not_applicable" or coordinate["gain_eligible"] or coordinate["minimum_gain"]["status"] != "not_applicable":
                errors.append(name + ": controls cannot be improvement dimensions")
            if rule["status"] == "not_applicable":
                errors.append(name + ": mandatory control needs specified or unresolved constraint")
        else:
            if coordinate["direction"] == "not_applicable" or rule["status"] != "not_applicable":
                errors.append(name + ": score direction/control rule mismatch")
            if coordinate["gain_eligible"] and coordinate["minimum_gain"]["status"] == "not_applicable":
                errors.append(name + ": eligible score needs gain policy or explicit unresolved policy")
        if rule["status"] == "specified":
            primary(rule, name + ".control_rule")
            if rule["minimum"] is None and rule["maximum"] is None:
                errors.append(name + ": specified control needs a bound")
            if rule["minimum"] is not None and rule["maximum"] is not None and _decimal(rule["minimum"]) > _decimal(rule["maximum"]):
                errors.append(name + ": invalid control interval")
        elif rule["minimum"] is not None or rule["maximum"] is not None:
            errors.append(name + ": unspecified control bounds must be null")
    if used_groups != set(groups):
        errors.append("every endpoint group must have source coordinates")
    if not any(row["role"] == "score" and row["gain_eligible"] for row in panel["coordinates"]):
        errors.append("panel needs at least one prespecified eligible score coordinate")
    if panel["reference_selection"]["status"] == "verified":
        primary(panel["reference_selection"], "reference_selection")
    inference = document["scientific_inference"]
    if inference["status"] == "specified":
        primary(inference, "scientific_inference")
    policy = document.get("binding_policy")
    if policy:
        primary(policy["evaluator"], "binding_policy.evaluator")
        conditions = policy["conditions"]
        for key in ("paper_sha256", "data_sha256", "tool_policy_sha256"):
            if conditions["paper_data"][key] != conditions["paper_data_official_code"][key]:
                errors.append("assistance arms must bind the same paper, data and tool policy")
    if document["source_paper"]["url"] is None and (document["disposition"] != "source_unresolved" or not document["blocking_issues"]):
        errors.append("missing source URL requires unresolved disposition and blocker")
    if document["disposition"] == "metadata_ready":
        errors.extend(_unresolved(document))
    return errors


def _unresolved(contract):
    missing = list(contract["blocking_issues"])
    for key, row in contract["same_task"].items():
        if row["status"] not in ("verified", "not_applicable"):
            missing.append("unresolved same-task anchor: " + key)
    if contract["panel"]["reference_selection"]["status"] != "verified":
        missing.append("strongest relevant author comparator selection unresolved")
    for row in contract["panel"]["coordinates"]:
        for key in ("published_baseline", "reproduction_tolerance"):
            expected = "verified" if key == "published_baseline" else "justified"
            if row[key]["status"] != expected or row[key]["value"] is None:
                missing.append(row["id"] + ": unresolved " + key)
        if row["role"] == "score":
            if row["direction"] not in ("higher", "lower"):
                missing.append(row["id"] + ": unresolved direction")
            if row["gain_eligible"] and row["minimum_gain"]["status"] != "justified":
                missing.append(row["id"] + ": meaningful gain unresolved")
        elif row["control_rule"]["status"] != "specified":
            missing.append(row["id"] + ": mandatory control constraint unresolved")
    if "binding_policy" not in contract:
        missing.append("frozen evaluator, condition and cumulative-budget bindings absent")
    for key in ("access_budget", "resource_budget"):
        if contract["episode"][key] is None:
            missing.append("episode." + key + " unresolved")
    return missing


def compare(contract, result):
    """Check complete final metadata and finite no-regression/gain constraints.

    There is deliberately no scientific-superiority boolean input or output path.
    A task-specific inferential evaluator, multiplicity control, provenance and
    independent evidence review are still required, even for a numerical pass.
    """
    errors = contract_validate(contract)
    out = {"schema_version": "paper-panel-comparison-report/v1", "status": "rejected",
        "metadata_admitted": False, "finite_numerical_dominance": None,
        "reproduction_matches": None, "score_nonregression": None,
        "required_controls_pass": None, "coordinate_results": [], "errors": errors,
        "unresolved": [], "paper_win": None, "scientific_superiority": None,
        "scientific_verification": "not_qualified_by_metadata_comparator",
        "current_sota": "not_assessed", "assurance": ASSURANCE}
    if errors:
        return out
    errors.extend(_json_errors(result))
    if not errors:
        errors.extend(scalar._schema_errors(result, RESULT_SCHEMA))
    if errors:
        return out
    out["unresolved"] = _unresolved(contract)
    if contract["disposition"] != "metadata_ready":
        out["unresolved"].append("contract disposition is not metadata_ready")
    if out["unresolved"]:
        out["status"] = "unqualified_contract"
        return out
    digest = contract_digest(contract); policy = contract["binding_policy"]
    if result["task_id"] != contract["task_id"] or result["phase"] != "final":
        errors.append("expected exact task and final evaluation")
    for label, row in (("result", result), ("freeze", result["freeze"]), ("evaluation", result["evaluation"])):
        if row["contract_digest"] != digest or row["candidate_sha256"] != result["candidate_sha256"]:
            errors.append(label + ": frozen contract/candidate mismatch")
    if scalar._timestamp(result["freeze"]["frozen_at"]) >= scalar._timestamp(result["evaluation"]["started_at"]):
        errors.append("candidate freeze must precede final evaluation")
    for label, anchors in (("result", result["same_task"]), ("reproduced_author_baseline", result["reproduced_author_baseline"]["same_task"])):
        if anchors != contract["same_task"]:
            errors.append(label + ": same-task source anchors differ")
    if result["condition_binding"] != policy["conditions"][result["access_condition"]]:
        errors.append("assistance condition binding differs from frozen contract")
    condition_digest = contract_digest({"access_condition": result["access_condition"],
                                        "condition_binding": result["condition_binding"]})
    for label in ("freeze", "evaluation"):
        row = result[label]
        if row["access_condition"] != result["access_condition"] or row["condition_binding_digest"] != condition_digest:
            errors.append(label + ": assistance condition is not bound to this comparison")
    for key in ("id", "sha256"):
        if result["evaluation"]["evaluator_" + key] != policy["evaluator"][key]:
            errors.append("evaluator identity mismatch")
    required_sources = {ref for _, refs in scalar._refs_in(contract) for ref in refs}
    if set(result["source_evidence_ids"]) != required_sources:
        errors.append("source evidence set differs from frozen contract")
    evidence = scalar._evidence_map(result["evidence"], errors, "result.evidence")
    def refs(row, kind, label):
        for ref in row["evidence_ids"]:
            if evidence.get(ref, {}).get("kind") != kind:
                errors.append(label + ": wrong or missing evidence kind")
    candidate_rows = [row for row in result["evidence"] if row["kind"] == "candidate"]
    if not candidate_rows or any(row["sha256"] != result["candidate_sha256"] for row in candidate_rows):
        errors.append("candidate provenance does not bind frozen candidate")
    for key, kind in (("freeze", "freeze"), ("evaluation", "evaluation"), ("reproduced_author_baseline", "reproduced_baseline")):
        refs(result[key], kind, key)
    for key, budget in policy["budgets"].items():
        usage = result["budget_usage"][key]; refs(usage, "budget", "budget_usage." + key)
        if usage["unit"] != budget["unit"] or usage["scope"] != budget["scope"] or _decimal(usage["used"]) > _decimal(budget["limit"]):
            errors.append("cumulative budget unit/scope/limit mismatch: " + key)
    actual = {}
    for row in result["measurements"]:
        if row["id"] in actual:
            errors.append("duplicate measurement coordinate")
        actual[row["id"]] = row
    expected = {row["id"]: row for row in contract["panel"]["coordinates"]}
    if set(actual) != set(expected):
        errors.append("measurement roster must equal complete frozen source panel")
    if errors:
        return out
    reproduction_ok, nonregression, controls_ok, meaningful = True, True, True, False
    for name, declared in expected.items():
        row = actual[name]
        for key in ("group_id", "role", "support_key", "metric", "unit", "direction"):
            if row[key] != declared[key]:
                errors.append(name + ": measurement identity/role/units/direction mismatch")
        domain = declared["metric_domain"]
        if any(not _in_domain(row[key], domain) for key in ("candidate_value", "published_value", "reproduced_value")):
            errors.append(name + ": measured score outside declared domain")
        published = declared["published_baseline"]["value"]
        if _decimal(row["published_value"]) != _decimal(published):
            errors.append(name + ": published score differs from frozen reference")
        tolerance = Decimal(str(declared["reproduction_tolerance"]["value"]))
        reproduced = row["reproduced_value"]
        reproduces = scalar._difference(reproduced, published).copy_abs() <= tolerance
        reproduction_ok &= reproduces
        pinned = declared["reproduced_author_baseline"]["value"]
        if pinned is not None and scalar._difference(reproduced, pinned).copy_abs() > tolerance:
            errors.append(name + ": reproduced reference differs from pinned value beyond tolerance")
        record = {"id": name, "group_id": declared["group_id"], "role": declared["role"],
                  "reproduction_matches": reproduces, "gain": None, "meaningful_gain": False,
                  "nonregression": None, "control_pass": None}
        if declared["role"] == "score":
            sign = 1 if declared["direction"] == "higher" else -1
            references = [_decimal(value) for value in [published, reproduced] + ([] if pinned is None else [pinned])]
            stronger = max(references) if sign > 0 else min(references)
            gain = scalar._difference(row["candidate_value"], stronger)
            if sign < 0:
                gain = gain.copy_negate()
            record["gain"] = str(gain)
            record["nonregression"] = gain >= 0
            nonregression &= gain >= 0
            if declared["gain_eligible"]:
                record["meaningful_gain"] = scalar._passes(gain, declared["gain_operator"], declared["minimum_gain"]["value"])
                meaningful |= record["meaningful_gain"]
        else:
            record["control_pass"] = _in_domain(row["candidate_value"], declared["control_rule"])
            controls_ok &= record["control_pass"]
        out["coordinate_results"].append(record)
    if errors:
        out["coordinate_results"] = []
        return out
    out.update(status="admitted_on_declared_evidence", metadata_admitted=True,
        reproduction_matches=reproduction_ok, score_nonregression=nonregression,
        required_controls_pass=controls_ok,
        finite_numerical_dominance=bool(reproduction_ok and nonregression and controls_ok and meaningful))
    return out


validate_contract = contract_validate
admit_comparison = compare
