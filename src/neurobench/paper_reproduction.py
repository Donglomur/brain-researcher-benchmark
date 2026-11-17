"""Additive reproduction contracts and paired, dual paper-outcome admission.

This module validates *declared metadata*, never scientific truth or executable
readiness. It reads no data/artifacts, executes no evaluator and cannot turn an
author calibration, historical attempt or a matching number into an AI result.
Every scientific outcome remains ``unknown``. Existing improvement/v1 contracts
and their comparison semantics are deliberately unchanged.

CONTRACT_SCHEMA describes reproduction independently of improvement. The
OUTCOMES_SCHEMA binds both contracts to one original task and specifies matched
paper+data / paper+data+author-code protocols separately for each outcome.
RECEIPT_SCHEMA binds a new AI execution to exactly one outcome/condition cell.
"""

from __future__ import annotations

from decimal import Decimal

from . import paper_improvement as improvement


# Reuse the strict JSON/finite-number/schema implementation without changing the
# established improvement module or its public contract.
_obj, _enum, _array = improvement._obj, improvement._enum, improvement._array
TEXT, SHA, NUMBER = improvement.TEXT, improvement.SHA, improvement.NUMBER
NULL_NUMBER, NULL_TEXT = improvement.NULL_NUMBER, improvement.NULL_TEXT
REFS, POS_REFS = improvement.REFS, improvement.POS_REFS
contract_digest = improvement.contract_digest
loads_contract, load_contract = improvement.loads_contract, improvement.load_contract
ASSURANCE = improvement.ASSURANCE
OUTCOMES = ("reproduction", "improvement")
CONDITIONS = ("paper_data", "paper_data_author_code")
ANCHORS = (*improvement.ANCHORS, "full_panel", "permitted_observations")
IDENTITIES = ("cohort", "split", "panel", "observations", "metric", "aggregation")
IDENTITY_SCHEMA = _obj({key: SHA for key in IDENTITIES})
SAME_TASK_SCHEMA = _obj({key: improvement.ANCHOR_SCHEMA for key in ANCHORS})
NULL_SHA = {"anyOf": [SHA, {"type": "null"}]}
NULL_INT = {"anyOf": [{"type": "integer", "minimum": 1}, {"type": "null"}]}
INTERVAL = {"anyOf": [{"type": "array", "items": NUMBER, "minItems": 2, "maxItems": 2}, {"type": "null"}]}
VALUE = {"anyOf": [NUMBER, TEXT, {"type": "null"}]}
SOURCE_SCHEMA = improvement.CONTRACT_SCHEMA["properties"]["evidence"]

UNCERTAINTY_SCHEMA = _obj({
    "kind": _enum("interval_containment", "threshold", "deterministic", "unresolved"),
    "method": TEXT, "independent_unit": TEXT,
    "minimum_independent_units": NULL_INT, "confidence_level": NULL_NUMBER,
    "statistic": _enum("p_value", "posterior_probability", None),
    "operator": _enum("<", "<=", ">", ">=", None),
    "threshold": NULL_NUMBER, "rationale": TEXT, "evidence_ids": REFS,
})
FINDING_SCHEMA = _obj({
    "id": TEXT, "kind": _enum("scalar", "categorical"), "description": TEXT,
    "status": _enum("verified", "unresolved"), "expected": VALUE,
    "units": TEXT, "aggregation": TEXT, "evidence_ids": REFS,
    "categories": _array(TEXT, unique=True),
    "tolerance": _obj({"status": _enum("justified", "unresolved", "not_applicable"),
                       "absolute": NULL_NUMBER, "rationale": TEXT, "evidence_ids": REFS}),
    "uncertainty": UNCERTAINTY_SCHEMA,
})
EVALUATOR_SCHEMA = _obj({"id": TEXT, "sha256": SHA, "evidence_ids": POS_REFS})
COMPUTATION_SCHEMA = _obj({
    "status": _enum("specified", "published_aggregate_only", "unresolved"),
    "rationale": TEXT, "analysis_interface_sha256": NULL_SHA,
    "authentic_data_manifest_sha256": NULL_SHA, "verification_program_sha256": NULL_SHA,
    "evidence_ids": REFS,
    "required_outputs": _array(_obj({
        "id": TEXT, "kind": _enum("observation_level", "source_grounded_derived", "companion_control"),
        "description": TEXT, "identity_sha256": SHA, "finding_ids": POS_REFS, "evidence_ids": POS_REFS,
    })),
})
CONTRACT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://neurobench.org/schemas/paper-reproduction/v1",
    "title": "Independent same-task paper reproduction contract",
    **_obj({
        "schema_version": {"const": "paper-reproduction/v1"}, "task_id": TEXT,
        "objective": {"const": "recreate_original_findings_same_task"},
        "eligibility": _enum("eligible", "design_ready", "source_unresolved", "ineligible"),
        "eligibility_reason": TEXT,
        "source_paper": improvement.CONTRACT_SCHEMA["properties"]["source_paper"],
        "evidence": SOURCE_SCHEMA, "same_task": SAME_TASK_SCHEMA,
        "findings": _array(FINDING_SCHEMA, minimum=1),
        "panel_rule": {"const": "all_declared_findings_and_companions"},
        "blocking_issues": _array(TEXT, unique=True),
        "admission_policy": _obj({"evaluator": EVALUATOR_SCHEMA,
                                  "evaluation_identity": IDENTITY_SCHEMA,
                                  "computation": COMPUTATION_SCHEMA}),
    }, optional=("admission_policy",)),
}

_MEASUREMENT_UNCERTAINTY = _obj({
    "method": TEXT, "independent_unit": TEXT,
    "n_independent_units": {"type": "integer", "minimum": 0},
    "confidence_level": NULL_NUMBER, "interval": INTERVAL,
    "statistic": NULL_TEXT, "value": NULL_NUMBER,
})
RESULT_SCHEMA = _obj({
    "schema_version": {"const": "paper-reproduction-result/v1"}, "task_id": TEXT,
    "claim": {"const": "same_task_original_findings_reproduction"},
    "phase": _enum("validation", "final"), "contract_digest": SHA,
    "candidate_sha256": SHA, "same_task": SAME_TASK_SCHEMA,
    "source_evidence_ids": POS_REFS,
    "findings": _array(_obj({"id": TEXT, "value": VALUE, "units": TEXT,
                             "aggregation": TEXT, "uncertainty": _MEASUREMENT_UNCERTAINTY}), minimum=1),
})
CONTRACT_SCHEMA["$defs"] = {"result": RESULT_SCHEMA}

_BUDGETS = _obj({key: improvement.BUDGET_SCHEMA for key in ("access", "resource")})
PROTOCOL_SCHEMA = _obj({
    "pair_id": TEXT, "common_input_manifest_sha256": SHA,
    "author_code_manifest_sha256": NULL_SHA, "evaluation_identity": IDENTITY_SCHEMA,
    "evaluator": _obj({"id": TEXT, "sha256": SHA}),
    "exposure_policy_sha256": SHA,
    "author_code_is_only_information_difference": {"type": "boolean", "const": True},
    "budgets": _BUDGETS, "computation": COMPUTATION_SCHEMA,
})
OUTCOMES_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://neurobench.org/schemas/paper-outcomes/v1",
    "title": "One original paper task, two outcomes, two matched conditions",
    **_obj({
        "schema_version": {"const": "paper-outcomes/v1"}, "task_id": TEXT,
        "original_task_sha256": SHA,
        "contracts": _obj({key: SHA for key in OUTCOMES}),
        "pairing": _obj({key: _obj({
            "status": _enum("specified", "unresolved"), "rationale": TEXT,
            "protocol": {"anyOf": [PROTOCOL_SCHEMA, {"type": "null"}]},
        }) for key in OUTCOMES}),
    }),
}

_RECEIPT_EVIDENCE = _obj({"id": TEXT, "kind": _enum("ai_run", "candidate", "freeze", "evaluation", "exposure", "budget",
                                                       "analysis_execution", "output_verification"),
                          "sha256": SHA, "locator": TEXT})
_USAGE = improvement.RESULT_SCHEMA["properties"]["budget_usage"]
RECEIPT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://neurobench.org/schemas/paper-outcome-receipt/v1",
    **_obj({
        "schema_version": {"const": "paper-outcome-receipt/v1"}, "task_id": TEXT,
        "outcome": _enum(*OUTCOMES), "condition": _enum(*CONDITIONS),
        "outcomes_digest": SHA, "original_task_sha256": SHA,
        "pair_id": TEXT, "run_id": TEXT,
        "actor_role": _enum("ai_solver", "author_baseline_calibration", "software_control", "historical_attempt"),
        "ai_run": _obj({"started_at": improvement.STAMP, "trace_sha256": SHA, "evidence_ids": POS_REFS}),
        "delivery": _obj({"common_input_manifest_sha256": SHA, "author_code_manifest_sha256": NULL_SHA,
                          "exposure_policy_sha256": SHA, "exposure_manifest_sha256": SHA, "evidence_ids": POS_REFS}),
        "candidate_sha256": SHA,
        "freeze": _obj({"frozen_at": improvement.STAMP, "candidate_sha256": SHA,
                        "outcomes_digest": SHA, "evidence_ids": POS_REFS}),
        "evaluation": _obj({"started_at": improvement.STAMP, "finished_at": improvement.STAMP,
                            "evaluator_id": TEXT, "evaluator_sha256": SHA,
                            "evaluation_identity": IDENTITY_SCHEMA,
                            "candidate_sha256": SHA, "result_digest": SHA, "evidence_ids": POS_REFS}),
        "analysis_execution": _obj({
            "execution_id": TEXT, "executor_role": _enum("independent_operator", "ai_solver"),
            "candidate_sha256": SHA, "entrypoint": TEXT, "analysis_interface_sha256": SHA,
            "common_input_manifest_sha256": SHA, "authentic_data_manifest_sha256": SHA,
            "author_code_manifest_sha256": NULL_SHA,
            "runtime_manifest_sha256": SHA, "invocation_sha256": SHA,
            "started_at": improvement.STAMP, "finished_at": improvement.STAMP,
            "output_manifest_sha256": SHA, "evidence_ids": POS_REFS,
        }),
        "output_verification": _obj({
            "verifier_role": _enum("independent_operator", "ai_solver"),
            "verification_program_sha256": SHA, "execution_id": TEXT,
            "output_manifest_sha256": SHA, "result_digest": SHA,
            "started_at": improvement.STAMP, "finished_at": improvement.STAMP, "evidence_ids": POS_REFS,
            "outputs": _array(_obj({"id": TEXT, "identity_sha256": SHA,
                                     "status": _enum("verified", "mismatch", "unverified")}), minimum=1),
        }),
        "budget_usage": _USAGE, "evidence": _array(_RECEIPT_EVIDENCE, minimum=1),
        "result": {"anyOf": [RESULT_SCHEMA, improvement.RESULT_SCHEMA]},
    }),
}


def _shape(document, schema):
    return improvement._json_errors(document) or improvement._schema_errors(document, schema)


def _unique(records, label, errors):
    by_id = {}
    for record in records:
        if record["id"] in by_id:
            errors.append(f"{label}: duplicate id {record['id']!r}")
        by_id[record["id"]] = record
    return by_id


def _number(value):
    return type(value) in (int, float)


def _computation_errors(computation, evidence, finding_ids=None):
    errors = []
    _unique(computation["required_outputs"], "computation.required_outputs", errors)
    for record in (computation, *computation["required_outputs"]):
        if any(ref not in evidence for ref in record["evidence_ids"]):
            errors.append("computation: unknown source evidence reference")
        if (computation["status"] == "specified" or record is not computation) and not any(
                evidence.get(ref, {}).get("kind") in ("paper", "author_data", "author_code") for ref in record["evidence_ids"]):
            errors.append("computation: primary source grounding is required")
    if computation["status"] == "specified":
        if any(computation[key] is None for key in ("analysis_interface_sha256", "authentic_data_manifest_sha256", "verification_program_sha256")):
            errors.append("computation: specify analysis interface, authentic data and independent verifier identities")
        if not any(output["kind"] in ("observation_level", "source_grounded_derived") for output in computation["required_outputs"]):
            errors.append("computation: source-grounded granular outputs are required; published aggregate/claim alone is insufficient")
        covered = {identifier for output in computation["required_outputs"] for identifier in output["finding_ids"]}
        if finding_ids is not None and covered != set(finding_ids):
            errors.append("computation: source-native outputs must cover every required finding and companion, with no extra findings")
    return errors


def contract_validate(document, task_id=None):
    """Validate source declarations and independent reproduction eligibility.

    Eligible means a fully specified source-grounded *endpoint*, not a ready
    runtime or verified result. Justifications may cite source evidence and a
    scientific preregistration; this validator cannot verify either's contents.
    """
    errors = _shape(document, CONTRACT_SCHEMA)
    if errors:
        return errors
    if task_id is not None and task_id != document["task_id"]:
        errors.append("task_id does not match expected task")
    evidence = _unique(document["evidence"], "evidence", errors)
    for path, refs in improvement._refs_in(document):
        if any(ref not in evidence for ref in refs):
            errors.append(f"{path}: unknown evidence reference")

    def source(record, label, *, primary=True):
        if not record["evidence_ids"]:
            errors.append(f"{label}: evidence is required")
        if primary and not any(evidence.get(ref, {}).get("kind") in ("paper", "author_data", "author_code")
                               for ref in record["evidence_ids"]):
            errors.append(f"{label}: primary source evidence is required")

    eligible = document["eligibility"] == "eligible"
    for key, record in document["same_task"].items():
        if record["status"] in ("verified", "not_applicable"):
            source(record, f"same_task.{key}")
        if eligible and record["status"] == "unresolved":
            errors.append(f"same_task.{key}: eligible endpoint cannot have unresolved anchors")
    for key in ("target", "metric", "full_panel", "permitted_observations"):
        if document["eligibility"] in ("eligible", "design_ready") and document["same_task"][key]["status"] != "verified":
            errors.append(f"same_task.{key}: source-grounded endpoint requires a verified anchor")
    if document["source_paper"]["url"] is None and (
            document["eligibility"] not in ("source_unresolved", "ineligible") or not document["blocking_issues"]):
        errors.append("source_paper.url: absent source requires unresolved/ineligible status and blocker")
    _unique(document["findings"], "findings", errors)
    for finding in document["findings"]:
        label = f"findings.{finding['id']}"
        if finding["status"] == "verified":
            source(finding, label)
            if finding["expected"] is None:
                errors.append(f"{label}: verified finding requires a source target")
        elif finding["expected"] is not None:
            errors.append(f"{label}: unresolved source target must be null")
        tolerance, rule = finding["tolerance"], finding["uncertainty"]
        if finding["kind"] == "scalar":
            if finding["expected"] is not None and not _number(finding["expected"]):
                errors.append(f"{label}: scalar expected value must be numeric")
            if finding["categories"] or tolerance["status"] == "not_applicable":
                errors.append(f"{label}: scalar requires a tolerance and no categorical vocabulary")
        else:
            if not finding["categories"] or (finding["expected"] is not None and
                                              finding["expected"] not in finding["categories"]):
                errors.append(f"{label}: categorical expected value must belong to declared categories")
            if tolerance["status"] != "not_applicable":
                errors.append(f"{label}: categorical matching uses exact categories, not numeric tolerance")
        if tolerance["status"] == "justified":
            if tolerance["absolute"] is None or tolerance["absolute"] < 0:
                errors.append(f"{label}.tolerance: justified nonnegative value required")
            source(tolerance, f"{label}.tolerance", primary=False)
        elif tolerance["absolute"] is not None:
            errors.append(f"{label}.tolerance: unresolved/not_applicable tolerance must be null")
        kind = rule["kind"]
        if kind != "unresolved":
            source(rule, f"{label}.uncertainty", primary=False)
        if kind == "interval_containment":
            if finding["kind"] != "scalar" or rule["confidence_level"] is None or not 0 < rule["confidence_level"] < 1:
                errors.append(f"{label}.uncertainty: interval containment requires scalar and confidence in (0,1)")
        elif rule["confidence_level"] is not None:
            errors.append(f"{label}.uncertainty: only interval containment takes confidence_level")
        if kind in ("interval_containment", "threshold"):
            if rule["minimum_independent_units"] is None:
                errors.append(f"{label}.uncertainty: specify independent replication")
        elif rule["minimum_independent_units"] is not None:
            errors.append(f"{label}.uncertainty: deterministic/unresolved rule has no sample minimum")
        if kind == "threshold":
            if any(rule[key] is None for key in ("statistic", "operator", "threshold")):
                errors.append(f"{label}.uncertainty: threshold rule must be explicit")
            if finding["kind"] != "categorical":
                errors.append(f"{label}.uncertainty: scalar equivalence requires interval containment or source-justified deterministic comparison")
            if rule["statistic"] == "p_value" and (rule["operator"] not in ("<", "<=") or
                    rule["threshold"] is None or not 0 < rule["threshold"] < 1):
                errors.append(f"{label}.uncertainty: p-value evidence must support the finding; nonrejection is not reproduction")
            if rule["statistic"] == "posterior_probability" and (rule["operator"] not in (">", ">=") or
                    rule["threshold"] is None or not 0.5 < rule["threshold"] <= 1):
                errors.append(f"{label}.uncertainty: posterior evidence requires a declared threshold above 0.5")
        elif any(rule[key] is not None for key in ("statistic", "operator", "threshold")):
            errors.append(f"{label}.uncertainty: non-threshold rule cannot carry a test threshold")
        if eligible and (finding["status"] != "verified" or tolerance["status"] == "unresolved" or kind == "unresolved"):
            errors.append(f"{label}: eligible endpoint requires target, justified criterion and uncertainty")
    if "admission_policy" in document:
        source(document["admission_policy"]["evaluator"], "admission_policy.evaluator")
        computation = document["admission_policy"]["computation"]
        errors.extend(_computation_errors(computation, evidence, [finding["id"] for finding in document["findings"]]))
        if eligible and computation["status"] != "specified":
            errors.append("eligible computational reproduction cannot rely only on a published aggregate or claim")
    if eligible and (document["blocking_issues"] or "admission_policy" not in document):
        errors.append("eligible endpoint requires complete admission policy and no unresolved scientific blockers")
    return errors


def outcomes_validate(document, reproduction_contract, improvement_contract):
    """Validate a single task's two independent endpoints and paired protocols."""
    errors = _shape(document, OUTCOMES_SCHEMA)
    if errors:
        return errors
    for outcome, contract, validator in (
        ("reproduction", reproduction_contract, contract_validate),
        ("improvement", improvement_contract, improvement.contract_validate),
    ):
        problems = validator(contract, document["task_id"])
        errors.extend(f"{outcome}: {error}" for error in problems)
        if problems:
            continue
        if document["contracts"][outcome] != contract_digest(contract):
            errors.append(f"contracts.{outcome}: digest differs from supplied contract")
        pairing = document["pairing"][outcome]
        protocol = pairing["protocol"]
        if (pairing["status"] == "specified") != (protocol is not None):
            errors.append(f"pairing.{outcome}: specified protocol required; unresolved protocol must be null")
        if protocol is None:
            continue
        errors.extend(f"pairing.{outcome}: {error}" for error in _computation_errors(
            protocol["computation"], {item["id"]: item for item in contract["evidence"]},
            [finding["id"] for finding in reproduction_contract["findings"]] if not contract_validate(reproduction_contract) else None))
        policy = contract.get("admission_policy")
        if policy is None:
            errors.append(f"pairing.{outcome}: supplied contract has no executable admission policy")
            continue
        for key in ("id", "sha256"):
            if protocol["evaluator"][key] != policy["evaluator"][key]:
                errors.append(f"pairing.{outcome}.evaluator: differs from endpoint policy")
        if outcome == "reproduction" and protocol["evaluation_identity"] != policy["evaluation_identity"]:
            errors.append("pairing.reproduction.evaluation_identity: differs from frozen original panel")
        if outcome == "reproduction" and protocol["computation"] != policy["computation"]:
            errors.append("pairing.reproduction.computation: differs from source-grounded computation policy")
        if outcome == "improvement" and protocol["budgets"] != policy["budgets"]:
            errors.append("pairing.improvement.budgets: differs from improvement/v1 policy")
    if not errors:
        if reproduction_contract["source_paper"]["url"] != improvement_contract["source_paper"]["url"]:
            errors.append("outcomes must identify the same original source paper")
        # Legacy improvement/v1 has no immutable per-anchor identities. Until
        # migration supplies them, fail closed on changed original facts. Status
        # and evidence IDs remain independent; objective fields may differ.
        for key in improvement.ANCHORS:
            if (reproduction_contract["same_task"][key]["description"] !=
                    improvement_contract["same_task"][key]["description"]):
                errors.append(f"outcomes same_task.{key}: original scientific anchor differs")
        reproduction = document["pairing"]["reproduction"]["protocol"]
        extension = document["pairing"]["improvement"]["protocol"]
        if reproduction is not None and extension is not None and reproduction["evaluation_identity"] != extension["evaluation_identity"]:
            errors.append("outcomes evaluation_identity: both outcomes must preserve the same original scientific panel")
        if reproduction is not None and extension is not None and (reproduction["computation"]["authentic_data_manifest_sha256"] !=
                                                                  extension["computation"]["authentic_data_manifest_sha256"]):
            errors.append("outcomes computation: both outcomes must preserve authentic original data identity")
    return errors


def _reproduction_result(contract, result):
    """Return structural errors and per-finding declared matches (never truth)."""
    errors = _shape(result, RESULT_SCHEMA)
    matches = {}
    if errors:
        return errors, matches
    if contract["eligibility"] != "eligible":
        errors.append("reproduction endpoint is not eligible")
    if result["contract_digest"] != contract_digest(contract) or result["task_id"] != contract["task_id"]:
        errors.append("reproduction result differs from frozen task/contract")
    if result["phase"] != "final":
        errors.append("validation feedback is not a final reproduction result")
    if result["same_task"] != contract["same_task"]:
        errors.append("reproduction result changes original same-task anchors")
    required = {ref for _, refs in improvement._refs_in(contract) for ref in refs}
    if set(result["source_evidence_ids"]) != required:
        errors.append("reproduction source evidence differs from frozen contract")
    actual = _unique(result["findings"], "result.findings", errors)
    expected = {finding["id"]: finding for finding in contract["findings"]}
    if set(actual) != set(expected):
        errors.append("reproduction requires exactly the complete original finding/companion panel")
    for identifier in expected.keys() & actual.keys():
        target, observation = expected[identifier], actual[identifier]
        label = f"result.findings.{identifier}"
        for key in ("units", "aggregation"):
            if observation[key] != target[key]:
                errors.append(f"{label}.{key}: differs from source")
        value = observation["value"]
        if (target["kind"] == "scalar" and not _number(value)) or (
                target["kind"] == "categorical" and (type(value) is not str or value not in target["categories"])):
            errors.append(f"{label}.value: invalid value/type for declared finding")
            continue
        if target["expected"] is None or target["tolerance"]["status"] == "unresolved":
            continue
        match = value == target["expected"] if target["kind"] == "categorical" else (
            improvement._difference(value, target["expected"]).copy_abs() <= Decimal(str(target["tolerance"]["absolute"])))
        rule, observed = target["uncertainty"], observation["uncertainty"]
        for key in ("method", "independent_unit", "confidence_level", "statistic"):
            if observed[key] != rule[key]:
                errors.append(f"{label}.uncertainty.{key}: differs from frozen rule")
        minimum = rule["minimum_independent_units"]
        if minimum is not None and observed["n_independent_units"] < minimum:
            errors.append(f"{label}.uncertainty: fewer independent units than required")
        interval = observed["interval"]
        if rule["kind"] == "interval_containment":
            if interval is None or interval[0] > interval[1] or not interval[0] <= value <= interval[1]:
                errors.append(f"{label}.uncertainty: require ordered interval containing estimate")
            else:
                tolerance = Decimal(str(target["tolerance"]["absolute"]))
                match &= all(improvement._difference(bound, target["expected"]).copy_abs() <= tolerance for bound in interval)
            if observed["value"] is not None:
                errors.append(f"{label}.uncertainty: interval rule has no threshold statistic value")
        elif interval is not None:
            errors.append(f"{label}.uncertainty: only interval-containment rule uses an interval")
        if rule["kind"] == "threshold":
            if observed["value"] is None or not 0 <= observed["value"] <= 1:
                errors.append(f"{label}.uncertainty: require a probability in [0,1]")
            else:
                match &= improvement._passes(observed["value"], rule["operator"], rule["threshold"])
        elif observed["value"] is not None:
            errors.append(f"{label}.uncertainty: non-threshold statistic must be null")
        if rule["kind"] == "deterministic" and observed["n_independent_units"] != 0:
            errors.append(f"{label}.uncertainty: deterministic result cannot imply independent replication")
        matches[identifier] = bool(match)
    return errors, matches


def admit_outcome(outcomes, reproduction_contract, improvement_contract, receipt):
    """Check one final AI receipt without authenticating or scoring science.

    A valid reproduction mismatch is admitted as declared mismatch, not erased.
    A malformed or missing result has an unknown criterion, never a failed score.
    Existing improvement compare failures retain their original semantics.
    """
    errors = outcomes_validate(outcomes, reproduction_contract, improvement_contract)
    response = {"metadata_admitted": False, "criterion_satisfied": None,
                "finding_matches": {}, "scientific_outcome": "unknown",
                "errors": errors, "assurance": ASSURANCE}
    if errors:
        return response
    errors.extend(_shape(receipt, RECEIPT_SCHEMA))
    if errors:
        return response
    outcome, result = receipt["outcome"], receipt["result"]
    protocol = outcomes["pairing"][outcome]["protocol"]
    if protocol is None:
        errors.append("paired protocol is unresolved")
        return response
    for key, expected in (("task_id", outcomes["task_id"]), ("original_task_sha256", outcomes["original_task_sha256"]),
                          ("outcomes_digest", contract_digest(outcomes)), ("pair_id", protocol["pair_id"]),
                          ("actor_role", "ai_solver")):
        if receipt[key] != expected:
            errors.append(f"receipt.{key}: differs from frozen AI outcome protocol")
    if result["candidate_sha256"] != receipt["candidate_sha256"]:
        errors.append("receipt candidate differs from result candidate")
    delivery = receipt["delivery"]
    for key in ("common_input_manifest_sha256", "exposure_policy_sha256"):
        if delivery[key] != protocol[key]:
            errors.append(f"delivery.{key}: differs from matched protocol")
    code = protocol["author_code_manifest_sha256"] if receipt["condition"] == "paper_data_author_code" else None
    if receipt["condition"] == "paper_data_author_code" and code is None:
        errors.append("author-code condition unavailable: no authenticated code manifest is specified")
    if delivery["author_code_manifest_sha256"] != code:
        errors.append("delivery.author_code_manifest_sha256: violates assigned access condition")
    freeze, evaluation = receipt["freeze"], receipt["evaluation"]
    if freeze["outcomes_digest"] != receipt["outcomes_digest"]:
        errors.append("freeze outcomes digest differs from receipt")
    for label, record in (("freeze", freeze), ("evaluation", evaluation)):
        if record["candidate_sha256"] != receipt["candidate_sha256"]:
            errors.append(f"{label} candidate differs from receipt")
    stamps = [improvement._timestamp(record[key]) for record, key in (
        (receipt["ai_run"], "started_at"), (freeze, "frozen_at"), (evaluation, "started_at"), (evaluation, "finished_at"))]
    if not stamps[0] < stamps[1] < stamps[2] <= stamps[3]:
        errors.append("AI run must start before candidate freeze before final evaluation and completion")
    if evaluation["result_digest"] != contract_digest(result):
        errors.append("evaluation result digest differs from supplied result")
    if evaluation["evaluation_identity"] != protocol["evaluation_identity"]:
        errors.append("evaluation identity differs from original cohort/split/full-panel/observations/metric/aggregation")
    for key in ("id", "sha256"):
        if evaluation[f"evaluator_{key}"] != protocol["evaluator"][key]:
            errors.append(f"evaluation.evaluator_{key}: differs from paired evaluator")
    evidence = _unique(receipt["evidence"], "receipt.evidence", errors)

    def refs(record, kind, label, sha=None):
        for ref in record["evidence_ids"]:
            item = evidence.get(ref, {})
            if item.get("kind") != kind or (sha is not None and item.get("sha256") != sha):
                errors.append(f"{label}: missing or incompatible {kind} evidence")

    refs(receipt["ai_run"], "ai_run", "ai_run", receipt["ai_run"]["trace_sha256"])
    refs(delivery, "exposure", "delivery", delivery["exposure_manifest_sha256"])
    refs(freeze, "freeze", "freeze")
    refs(evaluation, "evaluation", "evaluation")
    computation = protocol["computation"]
    execution, verification = receipt["analysis_execution"], receipt["output_verification"]
    if computation["status"] != "specified":
        errors.append("computational evidence is unresolved or limited to published aggregates")
    refs(execution, "analysis_execution", "analysis_execution")
    refs(verification, "output_verification", "output_verification")
    for key in ("analysis_interface_sha256", "authentic_data_manifest_sha256"):
        if execution[key] != computation[key]:
            errors.append(f"analysis_execution.{key}: differs from source-grounded computation policy")
    if execution["candidate_sha256"] != receipt["candidate_sha256"] or execution["common_input_manifest_sha256"] != protocol["common_input_manifest_sha256"]:
        errors.append("analysis execution must use the submitted candidate and exact admitted input package")
    if execution["author_code_manifest_sha256"] != delivery["author_code_manifest_sha256"]:
        errors.append("analysis execution author-code provenance differs from the assigned information condition")
    if execution["executor_role"] != "independent_operator" or verification["verifier_role"] != "independent_operator":
        errors.append("AI self-report cannot replace independent analysis execution and output verification")
    if verification["verification_program_sha256"] != computation["verification_program_sha256"]:
        errors.append("output_verification program differs from source-grounded verifier")
    for key in ("execution_id", "output_manifest_sha256"):
        if verification[key] != execution[key]:
            errors.append(f"output_verification.{key}: does not bind the independently executed analysis")
    if verification["result_digest"] != evaluation["result_digest"]:
        errors.append("output verification must bind granular analysis outputs to the reported scientific result")
    inner_stamps = [improvement._timestamp(record[key]) for record, key in (
        (execution, "started_at"), (execution, "finished_at"),
        (verification, "started_at"), (verification, "finished_at"))]
    if not stamps[2] <= inner_stamps[0] <= inner_stamps[1] <= inner_stamps[2] <= inner_stamps[3] <= stamps[3]:
        errors.append("final evaluation must contain ordered independent analysis execution and output verification")
    outputs = _unique(verification["outputs"], "output_verification.outputs", errors)
    required_outputs = {output["id"]: output for output in computation["required_outputs"]}
    if set(outputs) != set(required_outputs):
        errors.append("output verification must cover exactly every required source-native granular output and control")
    for identifier in outputs.keys() & required_outputs.keys():
        if outputs[identifier]["identity_sha256"] != required_outputs[identifier]["identity_sha256"] or outputs[identifier]["status"] != "verified":
            errors.append(f"output_verification.{identifier}: missing source identity or successful independent verification")
    candidates = [item for item in evidence.values() if item["kind"] == "candidate"]
    if not candidates or any(item["sha256"] != receipt["candidate_sha256"] for item in candidates):
        errors.append("candidate evidence must identify the frozen AI artifact")
    for key, budget in protocol["budgets"].items():
        usage = receipt["budget_usage"][key]
        refs(usage, "budget", f"budget_usage.{key}")
        if usage["unit"] != budget["unit"] or usage["scope"] != budget["scope"] or usage["used"] > budget["limit"]:
            errors.append(f"budget_usage.{key}: exceeds or differs from matched cumulative budget")
    if outcome == "reproduction":
        problems, matches = _reproduction_result(reproduction_contract, result)
        errors.extend(problems)
        if not errors:
            response.update(metadata_admitted=True, finding_matches=matches, criterion_satisfied=all(matches.values()))
    else:
        comparison = improvement.compare(improvement_contract, result)
        errors.extend(comparison["errors"])
        if not errors:
            # Bind legacy nested execution declarations to the new AI envelope.
            for label in ("freeze", "evaluation", "budget_usage"):
                if label == "budget_usage":
                    for key in protocol["budgets"]:
                        for field in ("unit", "scope", "used"):
                            if result[label][key][field] != receipt[label][key][field]:
                                errors.append(f"improvement {label}.{key}.{field}: differs from AI receipt")
                else:
                    for field in ("frozen_at",) if label == "freeze" else ("started_at", "evaluator_id", "evaluator_sha256"):
                        if result[label][field] != receipt[label][field]:
                            errors.append(f"improvement {label}.{field}: differs from AI receipt")
            inner_evidence = {item["id"]: item for item in result["evidence"]}
            for label in ("freeze", "evaluation"):
                inner_hashes = {inner_evidence[ref]["sha256"] for ref in result[label]["evidence_ids"]}
                outer_hashes = {evidence[ref]["sha256"] for ref in receipt[label]["evidence_ids"]}
                if inner_hashes != outer_hashes:
                    errors.append(f"improvement {label} provenance differs from AI receipt")
            if not errors:
                response.update(metadata_admitted=True, criterion_satisfied=True)
    return response


def summary(outcomes, reproduction_contract, improvement_contract, receipts=()):
    """Four separate cells, one task, no implicit runs or historical promotion.

    Supply one receipt per cell. Repeated trials require explicit external
    aggregation; choosing a favorable receipt here is not supported.
    """
    errors = outcomes_validate(outcomes, reproduction_contract, improvement_contract)
    report = {"task_id": outcomes.get("task_id") if type(outcomes) is dict else None,
              "task_count": 1 if not errors else 0, "cells": [], "errors": errors, "assurance": ASSURANCE,
              "paired_metadata_admitted": {outcome: False for outcome in OUTCOMES}}
    if errors:
        return report
    by_cell, identities = {}, {}
    for receipt in receipts:
        admission = admit_outcome(outcomes, reproduction_contract, improvement_contract, receipt)
        if _shape(receipt, RECEIPT_SCHEMA):
            errors.extend(admission["errors"])
            continue
        cell = receipt["outcome"], receipt["condition"]
        if cell in by_cell:
            errors.append(f"duplicate receipt for {cell}; no favorable-run selection")
        by_cell[cell] = admission
        # A single run/evaluation cannot become two independent condition runs,
        # even when task inputs and evaluator are deliberately matched.
        evaluation_hashes = {(item["kind"], item["sha256"]) for item in receipt["evidence"]
                             if item["kind"] in ("evaluation", "freeze", "analysis_execution", "output_verification")}
        tokens = {("run_id", receipt["run_id"]), ("trace", receipt["ai_run"]["trace_sha256"]),
                  ("exposure", receipt["delivery"]["exposure_manifest_sha256"]),
                  ("execution_id", receipt["analysis_execution"]["execution_id"])}
        tokens.update(evaluation_hashes)
        for token in tokens:
            if token in identities and identities[token][1] != cell[1]:
                errors.append("different access conditions reuse an AI run, trace, exposure or evaluation receipt")
            identities[token] = cell
    for outcome in OUTCOMES:
        for condition in CONDITIONS:
            admission = by_cell.get((outcome, condition))
            report["cells"].append({
                "outcome": outcome, "condition": condition,
                "eligibility": reproduction_contract["eligibility"] if outcome == "reproduction" else improvement_contract["disposition"],
                "endpoint_eligible": reproduction_contract["eligibility"] == "eligible" if outcome == "reproduction" else improvement_contract["disposition"] == "improvement_ready",
                "pairing_status": outcomes["pairing"][outcome]["status"],
                "condition_available": outcomes["pairing"][outcome]["protocol"] is not None and (
                    condition == "paper_data" or outcomes["pairing"][outcome]["protocol"]["author_code_manifest_sha256"] is not None),
                "scientific_outcome": "unknown", "receipt": admission,
            })
    if errors:
        # Pairing violations invalidate the collection, including individually
        # consistent cells. Preserve raw diagnostics without admitting the pair.
        for cell in report["cells"]:
            if cell["receipt"] is not None:
                cell["receipt"]["metadata_admitted"] = False
                cell["receipt"]["criterion_satisfied"] = None
                cell["receipt"]["finding_matches"] = {}
    else:
        report["paired_metadata_admitted"] = {
            outcome: all(by_cell.get((outcome, condition), {}).get("metadata_admitted", False)
                         for condition in CONDITIONS) for outcome in OUTCOMES}
    return report
