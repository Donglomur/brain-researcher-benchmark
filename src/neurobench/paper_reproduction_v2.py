"""Opt-in indexed-array reproduction metadata; no scientific artifact execution.

V1 input delegates to the unchanged v1 API. V2 introduces explicit contract,
result and receipt versions. Its sole implemented comparison class is
``numerical_reference_equivalence``. Unsupported scientific comparison classes
are schema limitations, not evidence that a scientific question is ineligible.

Array bytes, policies and comparator programs are never read or executed here.
All scientific outcomes remain unknown, including when declared criteria match.
"""

from __future__ import annotations

import copy
from decimal import Decimal

from . import paper_improvement as improvement
from . import paper_reproduction as v1


_obj, _enum, _array = improvement._obj, improvement._enum, improvement._array
TEXT, SHA, NUMBER = improvement.TEXT, improvement.SHA, improvement.NUMBER
REFS, POS_REFS = improvement.REFS, improvement.POS_REFS
NULL_SHA, NULL_TEXT = v1.NULL_SHA, improvement.NULL_TEXT
_shape, _unique, _number = v1._shape, v1._unique, v1._number
_computation_errors = v1._computation_errors
contract_digest = improvement.contract_digest
loads_contract, load_contract = improvement.loads_contract, improvement.load_contract
ASSURANCE, OUTCOMES, CONDITIONS = v1.ASSURANCE, v1.OUTCOMES, v1.CONDITIONS
CONTRACT_VERSION = "paper-reproduction/v2"
RESULT_VERSION = "paper-reproduction-result/v2"
RECEIPT_VERSION = "paper-outcome-receipt/v2"
COMPARISON_CLASS = "numerical_reference_equivalence"
SHAPE = _array({"type": "integer", "minimum": 1})
PARTIAL_SHAPE = {"anyOf": [_array(v1.NULL_INT), {"type": "null"}]}
COORDINATES = {"anyOf": [
    _obj({"kind": {"const": "labels"}, "values": _array({"anyOf": [TEXT, NUMBER]}, minimum=1, unique=True)}),
    _obj({"kind": {"const": "arithmetic"}, "start": NUMBER, "step": NUMBER,
          "count": {"type": "integer", "minimum": 1}}),
    _obj({"kind": {"const": "manifest"}, "sha256": SHA}),
    _obj({"kind": {"const": "unresolved"}, "description": TEXT}),
]}
AXIS_SCHEMA = _obj({"name": TEXT, "units": TEXT, "identity_sha256": NULL_SHA,
                    "coordinates": COORDINATES})
CORRESPONDENCE_SCHEMA = _obj({
    "status": _enum("specified", "not_required", "unresolved"),
    "policy_sha256": NULL_SHA, "rationale": TEXT, "evidence_ids": REFS,
})
COLLECTION_SCHEMA = _obj({
    "record_key_fields": POS_REFS, "zero_records_allowed": {"type": "boolean"},
    "correspondence": CORRESPONDENCE_SCHEMA,
})
MEMBER_SCHEMA = _obj({
    "id": TEXT, "manifest_key": TEXT, "source_quantity": TEXT,
    "membership": _enum("fixed", "data_dependent"),
    "shape": PARTIAL_SHAPE,
    "axes": {"anyOf": [_array(AXIS_SCHEMA), {"type": "null"}]},
    "allowed_dtypes": {"anyOf": [_array(TEXT, minimum=1, unique=True), {"type": "null"}]},
    "units": TEXT, "semantic_identity_sha256": NULL_SHA,
    "support_manifest_sha256": NULL_SHA, "domain_policy_sha256": NULL_SHA,
    "source_aggregation": TEXT, "derivation_policy_sha256": NULL_SHA,
    "collection": {"anyOf": [COLLECTION_SCHEMA, {"type": "null"}]},
    "evidence_ids": REFS,
})
REPRESENTATION_SCHEMA = _obj({
    "status": _enum("specified", "unresolved"), "family_id": TEXT,
    "family_identity_sha256": NULL_SHA,
    "members": _array(MEMBER_SCHEMA, minimum=1), "evidence_ids": REFS,
})
REFERENCE_SCHEMA = _obj({
    "manifest_sha256": SHA,
    "provenance_role": _enum("publication_historical", "current_author_code", "operator_reconstruction"),
    "source_revision": TEXT, "provenance": TEXT,
    "publication_equivalence": _enum("verified", "unresolved"),
    "equivalence_rationale": TEXT, "evidence_ids": POS_REFS,
})
COMPARISON_SCHEMA = _obj({
    "status": _enum("specified", "unresolved", "schema_limited"),
    "comparison_class": TEXT, "reference_manifest_sha256": NULL_SHA,
    "comparison_program_sha256": NULL_SHA, "criterion_policy_sha256": NULL_SHA,
    "uncertainty_policy_sha256": NULL_SHA,
    "coverage": {"const": "complete_declared_source_support"},
    "method": TEXT, "independent_unit": TEXT, "dependence": TEXT, "multiplicity": TEXT,
    "rationale": TEXT, "evidence_ids": REFS,
})
STRUCTURED_FINDING_SCHEMA = _obj({
    "id": TEXT, "kind": {"const": "indexed_array_family"}, "description": TEXT,
    "status": _enum("verified", "unresolved"),
    "expected": {"anyOf": [REFERENCE_SCHEMA, {"type": "null"}]},
    "representation": REPRESENTATION_SCHEMA,
    "required_granular_output_ids": POS_REFS,
    "comparison": COMPARISON_SCHEMA, "evidence_ids": REFS,
})

CONTRACT_SCHEMA = copy.deepcopy(v1.CONTRACT_SCHEMA)
CONTRACT_SCHEMA["$id"] = "https://neurobench.org/schemas/paper-reproduction/v2"
CONTRACT_SCHEMA["title"] = "Opt-in source-indexed paper reproduction contract"
CONTRACT_SCHEMA["properties"]["schema_version"] = {"const": CONTRACT_VERSION}
CONTRACT_SCHEMA["properties"]["eligibility"]["enum"].append("schema_blocked")
CONTRACT_SCHEMA["properties"]["findings"] = _array({"anyOf": [
    copy.deepcopy(v1.FINDING_SCHEMA), STRUCTURED_FINDING_SCHEMA,
]}, minimum=1)

RECORD_SCHEMA = _obj({
    "key": _array(TEXT, minimum=1), "content_sha256": SHA, "shape": SHAPE, "dtype": TEXT,
    "axis_identity_sha256": _array(SHA), "support_manifest_sha256": SHA,
})
MEMBER_RESULT_SCHEMA = _obj({
    "id": TEXT, "manifest_key": TEXT, "semantic_identity_sha256": SHA,
    "shape": SHAPE, "dtype": TEXT, "units": TEXT,
    "axis_identity_sha256": _array(SHA),
    "support_manifest_sha256": SHA, "domain_policy_sha256": SHA,
    "derivation_policy_sha256": SHA,
    "content_sha256": SHA,
    "complete": {"type": "boolean", "const": True},
    "records": _array(RECORD_SCHEMA),
})
STRUCTURED_RESULT_SCHEMA = _obj({
    "id": TEXT, "kind": {"const": "indexed_array_family"},
    "output_manifest_sha256": SHA, "family_spec_digest": SHA,
    "members": _array(MEMBER_RESULT_SCHEMA, minimum=1),
})
RESULT_SCHEMA = copy.deepcopy(v1.RESULT_SCHEMA)
RESULT_SCHEMA["properties"]["schema_version"] = {"const": RESULT_VERSION}
RESULT_SCHEMA["properties"]["findings"] = _array({"anyOf": [
    copy.deepcopy(v1.RESULT_SCHEMA["properties"]["findings"]["items"]), STRUCTURED_RESULT_SCHEMA,
]}, minimum=1)
CONTRACT_SCHEMA["$defs"] = {"result": RESULT_SCHEMA}

ASSESSMENT_SCHEMA = _obj({
    "member_id": TEXT, "reference_member_key": TEXT, "submitted_member_digest": SHA,
    "status": _enum("assessed", "not_assessed"), "comparison_record_sha256": SHA,
    "correspondence_policy_sha256": NULL_SHA,
})
SCIENTIFIC_COMPARISON_SCHEMA = _obj({
    "finding_id": TEXT, "actor_role": _enum("independent_operator", "ai_solver"),
    "candidate_sha256": SHA, "contract_digest": SHA, "outcomes_digest": SHA,
    "execution_id": TEXT, "output_manifest_sha256": SHA,
    "result_digest": SHA, "finding_result_digest": SHA, "family_spec_digest": SHA,
    "reference_manifest_sha256": SHA, "reference_descriptor_digest": SHA,
    "comparison_class": {"const": COMPARISON_CLASS},
    "comparison_program_sha256": SHA, "criterion_policy_sha256": SHA,
    "uncertainty_policy_sha256": SHA,
    "coverage": {"const": "complete_declared_source_support"},
    "started_at": improvement.STAMP, "finished_at": improvement.STAMP,
    "decision_manifest_sha256": SHA, "evidence_ids": POS_REFS,
    "member_assessments": _array(ASSESSMENT_SCHEMA, minimum=1),
    "criterion_satisfied": {"type": "boolean"},
})
RECEIPT_SCHEMA = copy.deepcopy(v1.RECEIPT_SCHEMA)
RECEIPT_SCHEMA["$id"] = "https://neurobench.org/schemas/paper-outcome-receipt/v2"
RECEIPT_SCHEMA["properties"]["schema_version"] = {"const": RECEIPT_VERSION}
RECEIPT_SCHEMA["properties"]["result"] = {"anyOf": [RESULT_SCHEMA, copy.deepcopy(improvement.RESULT_SCHEMA)]}
RECEIPT_SCHEMA["properties"]["evidence"]["items"]["properties"]["kind"]["enum"].append("scientific_comparison")
RECEIPT_SCHEMA["properties"]["scientific_comparisons"] = _array(SCIENTIFIC_COMPARISON_SCHEMA)
RECEIPT_SCHEMA["required"].append("scientific_comparisons")
OUTCOMES_SCHEMA = copy.deepcopy(v1.OUTCOMES_SCHEMA)


def _source(record, evidence, label, errors, *, primary=True):
    if not record["evidence_ids"]:
        errors.append(f"{label}: evidence is required")
    if any(ref not in evidence for ref in record["evidence_ids"]):
        errors.append(f"{label}: unknown evidence reference")
    if primary and not any(evidence.get(ref, {}).get("kind") in ("paper", "author_data", "author_code")
                           for ref in record["evidence_ids"]):
        errors.append(f"{label}: primary source grounding is required")


def _structured_finding_errors(finding, evidence, computation, eligible):
    errors = []
    label = "findings." + finding["id"]
    representation, comparison, reference = finding["representation"], finding["comparison"], finding["expected"]
    specified = representation["status"] == "specified"
    if finding["status"] == "verified":
        _source(finding, evidence, label, errors)
        if reference is None or reference["publication_equivalence"] != "verified":
            errors.append(f"{label}: verified finding requires a source-equivalent expected reference")
    if specified:
        _source(representation, evidence, label + ".representation", errors)
        if representation["family_identity_sha256"] is None:
            errors.append(f"{label}: specified family needs authentic identity manifest")
    members = _unique(representation["members"], label + ".members", errors)
    keys = [member["manifest_key"] for member in members.values()]
    if len(keys) != len(set(keys)):
        errors.append(f"{label}: duplicate manifest member keys")
    for member in members.values():
        path = label + ".members." + member["id"]
        if specified:
            _source(member, evidence, path, errors)
            if any(member[key] is None for key in ("shape", "axes", "allowed_dtypes", "semantic_identity_sha256",
                                                  "support_manifest_sha256", "domain_policy_sha256", "derivation_policy_sha256")):
                errors.append(f"{path}: specified member has unresolved source identity, shape, domain or derivation")
        shape, axes = member["shape"], member["axes"]
        if shape is not None and axes is not None:
            if len(shape) != len(axes):
                errors.append(f"{path}: axis/shape rank mismatch")
            if len({axis["name"] for axis in axes}) != len(axes):
                errors.append(f"{path}: duplicate semantic axis names")
            for size, axis in zip(shape, axes):
                coordinates = axis["coordinates"]
                if specified and (size is None or axis["identity_sha256"] is None or coordinates["kind"] == "unresolved"):
                    errors.append(f"{path}: specified axis requires observed length and coordinate identity")
                count = len(coordinates["values"]) if coordinates["kind"] == "labels" else coordinates.get("count")
                if coordinates["kind"] == "labels" and len(set(coordinates["values"])) != len(coordinates["values"]):
                    errors.append(f"{path}: duplicate coordinate identity, including numerically equal labels")
                if count is not None and size is not None and count != size:
                    errors.append(f"{path}: coordinate count differs from declared dimension")
                if coordinates["kind"] == "arithmetic" and coordinates["step"] == 0:
                    errors.append(f"{path}: arithmetic coordinate step cannot be zero")
        collection = member["collection"]
        if (member["membership"] == "data_dependent") != (collection is not None):
            errors.append(f"{path}: only data-dependent members require a collection policy")
        if collection is not None:
            correspondence = collection["correspondence"]
            if correspondence["status"] == "specified":
                if correspondence["policy_sha256"] is None:
                    errors.append(f"{path}: specified correspondence needs a frozen policy")
                _source(correspondence, evidence, path + ".correspondence", errors)
            elif correspondence["policy_sha256"] is not None:
                errors.append(f"{path}: unresolved/not-required correspondence must not invent a policy hash")
            if correspondence["status"] == "not_required":
                _source(correspondence, evidence, path + ".correspondence", errors)
            if eligible and correspondence["status"] == "unresolved":
                errors.append(f"{path}: scientific correspondence is unresolved")
    if reference is not None:
        _source(reference, evidence, label + ".expected", errors)
    supported = comparison["comparison_class"] == COMPARISON_CLASS
    if supported == (comparison["status"] == "schema_limited"):
        errors.append(f"{label}: unsupported comparison classes must be schema_limited; supported classes are not schema limitations")
    if comparison["status"] == "specified":
        _source(comparison, evidence, label + ".comparison", errors, primary=False)
        if any(comparison[key] is None for key in ("reference_manifest_sha256", "comparison_program_sha256",
                                                  "criterion_policy_sha256", "uncertainty_policy_sha256")):
            errors.append(f"{label}: specified comparison requires actual reference/program/criterion/uncertainty bindings")
        if reference is None or reference["publication_equivalence"] != "verified":
            errors.append(f"{label}: numerical reference must have verified original-source equivalence")
        elif comparison["reference_manifest_sha256"] != reference["manifest_sha256"]:
            errors.append(f"{label}: comparison reference differs from expected artifact")
        if not specified:
            errors.append(f"{label}: comparison requires fully specified source family")
    if computation is not None:
        outputs = {item["id"]: item for item in computation["required_outputs"]}
        for output_id in finding["required_granular_output_ids"]:
            if output_id not in outputs or finding["id"] not in outputs[output_id]["finding_ids"]:
                errors.append(f"{label}: granular output is absent or not linked to this finding")
    elif eligible:
        errors.append(f"{label}: eligible structured finding requires an authentic computation policy")
    if eligible and (finding["status"] != "verified" or comparison["status"] != "specified" or not specified):
        errors.append(f"{label}: eligible endpoint requires source target, full representation and scientific comparison")
    return errors


def _structured_result_errors(target, observation):
    errors = []
    label = "result.findings." + target["id"]
    if observation.get("kind") != "indexed_array_family":
        return [f"{label}: structured result cannot be replaced with a scalar/category"]
    representation = target["representation"]
    if representation["status"] != "specified":
        return [f"{label}: source family is unresolved"]
    if observation["family_spec_digest"] != contract_digest(representation):
        errors.append(f"{label}: family specification digest differs")
    actual = _unique(observation["members"], label + ".members", errors)
    expected = {member["id"]: member for member in representation["members"]}
    if set(actual) != set(expected):
        errors.append(f"{label}: exact fixed-family membership required")
    for identifier in actual.keys() & expected.keys():
        value, spec = actual[identifier], expected[identifier]
        for key in ("manifest_key", "semantic_identity_sha256", "shape", "units", "support_manifest_sha256",
                    "domain_policy_sha256", "derivation_policy_sha256"):
            if value[key] != spec[key]:
                errors.append(f"{label}.{identifier}.{key}: differs from frozen source specification")
        axes = [axis["identity_sha256"] for axis in spec["axes"]] if spec["axes"] is not None else None
        if value["axis_identity_sha256"] != axes:
            errors.append(f"{label}.{identifier}: ordered semantic axes differ")
        if spec["allowed_dtypes"] is None or value["dtype"] not in spec["allowed_dtypes"]:
            errors.append(f"{label}.{identifier}: dtype violates declared representation policy")
        if spec["membership"] == "fixed":
            if value["records"]:
                errors.append(f"{label}.{identifier}: fixed array cannot masquerade as a record collection")
            continue
        collection = spec["collection"]
        if collection is None:
            errors.append(f"{label}.{identifier}: missing source collection policy")
            continue
        if not value["records"] and not collection["zero_records_allowed"]:
            errors.append(f"{label}.{identifier}: empty collection is not allowed by the source policy")
        keys = set()
        for record in value["records"]:
            key = tuple(record["key"])
            if len(key) != len(collection["record_key_fields"]) or key in keys:
                errors.append(f"{label}.{identifier}: record key arity/uniqueness violation")
            keys.add(key)
            if record["shape"] != spec["shape"] or record["axis_identity_sha256"] != axes:
                errors.append(f"{label}.{identifier}: record changes original grid/axes")
            if record["dtype"] not in (spec["allowed_dtypes"] or ()) or record["support_manifest_sha256"] != spec["support_manifest_sha256"]:
                errors.append(f"{label}.{identifier}: record changes dtype or support")
    return errors


def _structured_comparisons(contract, result, receipt, evidence, matches):
    errors = []
    if result.get("schema_version") != RESULT_VERSION:
        return ["structured comparison requires a v2 reproduction result"]
    targets = {f["id"]: f for f in contract["findings"] if f["kind"] == "indexed_array_family"}
    records = {}
    for record in receipt["scientific_comparisons"]:
        identifier = record["finding_id"]
        if identifier in records:
            errors.append("duplicate structured scientific comparison")
        records[identifier] = record
    if set(records) != set(targets):
        errors.append("every structured finding requires its own independent scientific comparison; no extras")
    observations = {f["id"]: f for f in result["findings"]}
    for identifier in records.keys() & targets.keys() & observations.keys():
        target, record, observed = targets[identifier], records[identifier], observations[identifier]
        label = "scientific_comparisons." + identifier
        policy, reference, representation = target["comparison"], target["expected"], target["representation"]
        if policy["status"] != "specified" or reference is None or observed.get("kind") != "indexed_array_family":
            errors.append(f"{label}: scientific comparison is unresolved or schema-limited")
            continue
        bindings = {
            "candidate_sha256": receipt["candidate_sha256"], "contract_digest": contract_digest(contract),
            "outcomes_digest": receipt["outcomes_digest"], "execution_id": receipt["analysis_execution"]["execution_id"],
            "output_manifest_sha256": receipt["analysis_execution"]["output_manifest_sha256"],
            "result_digest": contract_digest(result), "finding_result_digest": contract_digest(observed),
            "family_spec_digest": contract_digest(representation), "reference_manifest_sha256": reference["manifest_sha256"],
            "reference_descriptor_digest": contract_digest(reference), "comparison_class": policy["comparison_class"],
            "comparison_program_sha256": policy["comparison_program_sha256"],
            "criterion_policy_sha256": policy["criterion_policy_sha256"],
            "uncertainty_policy_sha256": policy["uncertainty_policy_sha256"],
        }
        for key, value in bindings.items():
            if record[key] != value:
                errors.append(f"{label}.{key}: differs from frozen execution/source/policy")
        if observed["output_manifest_sha256"] != record["output_manifest_sha256"]:
            errors.append(f"{label}: finding outputs differ from independently executed output manifest")
        if record["actor_role"] != "independent_operator":
            errors.append(f"{label}: candidate self-report is not independent comparison")
        for ref in record["evidence_ids"]:
            item = evidence.get(ref, {})
            if item.get("kind") != "scientific_comparison" or item.get("sha256") != record["decision_manifest_sha256"]:
                errors.append(f"{label}: scientific comparison evidence is missing or incompatible")
        start, finish = improvement._timestamp(record["started_at"]), improvement._timestamp(record["finished_at"])
        if not improvement._timestamp(receipt["output_verification"]["finished_at"]) <= start <= finish <= improvement._timestamp(receipt["evaluation"]["finished_at"]):
            errors.append(f"{label}: scientific comparison must follow derivation verification within final evaluation")
        assessments = {}
        for assessment in record["member_assessments"]:
            member_id = assessment["member_id"]
            if member_id in assessments:
                errors.append(f"{label}: duplicate member assessment")
            assessments[member_id] = assessment
        source_members = {member["id"]: member for member in representation["members"]}
        output_members = {member["id"]: member for member in observed["members"]}
        if set(assessments) != set(source_members):
            errors.append(f"{label}: incomplete scientific comparison coverage")
        for member_id in assessments.keys() & source_members.keys() & output_members.keys():
            assessment, spec = assessments[member_id], source_members[member_id]
            if assessment["reference_member_key"] != spec["manifest_key"] or assessment["submitted_member_digest"] != contract_digest(output_members[member_id]):
                errors.append(f"{label}.{member_id}: assessment changes member/output identity")
            if assessment["status"] != "assessed":
                errors.append(f"{label}.{member_id}: member has not been scientifically assessed")
            correspondence = spec["collection"]["correspondence"]["policy_sha256"] if spec["collection"] is not None else None
            if assessment["correspondence_policy_sha256"] != correspondence:
                errors.append(f"{label}.{member_id}: correspondence policy differs")
        # The independent frozen comparison program owns the declared criterion.
        # We do not invent all-close, averaging, cluster matching or a threshold.
        matches[identifier] = record["criterion_satisfied"]
    return errors


# The versioned envelope and scalar/categorical branches below preserve the
# reviewed v1 checks. They are static code, not runtime schema monkeypatching.
# V1 entry points still delegate directly to v1, with its schemas untouched.

# BEGIN STATIC V2 CORE
def _v2_contract_validate(document, task_id=None):
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
        if finding["kind"] == "indexed_array_family":
            computation = document.get("admission_policy", {}).get("computation")
            errors.extend(_structured_finding_errors(finding, evidence, computation, eligible))
            continue
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
    limited = any(finding["kind"] == "indexed_array_family" and finding["comparison"]["status"] == "schema_limited"
                  for finding in document["findings"])
    if document["eligibility"] == "schema_blocked" and not limited:
        errors.append("schema_blocked requires an explicitly unsupported scientific comparison class")
    if eligible and (document["blocking_issues"] or "admission_policy" not in document):
        errors.append("eligible endpoint requires complete admission policy and no unresolved scientific blockers")
    return errors



def _v2_outcomes_validate(document, reproduction_contract, improvement_contract):
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
        if target["kind"] == "indexed_array_family":
            errors.extend(_structured_result_errors(target, observation))
            matches[identifier] = None
            continue
        if observation.get("kind") == "indexed_array_family":
            errors.append(f"{label}: scalar/categorical result cannot change representation kind")
            continue
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



def _v2_admit_outcome(outcomes, reproduction_contract, improvement_contract, receipt):
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
        errors.extend(_structured_comparisons(reproduction_contract, result, receipt, evidence, matches))
        if not errors:
            response.update(metadata_admitted=True, finding_matches=matches, criterion_satisfied=all(matches.values()))
    else:
        if receipt["scientific_comparisons"]:
            errors.append("an improvement receipt cannot carry reproduction comparison records")
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



def _v2_summary(outcomes, reproduction_contract, improvement_contract, receipts=()):
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
                             if item["kind"] in ("evaluation", "freeze", "analysis_execution", "output_verification", "scientific_comparison")}
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




def _legacy(document):
    return type(document) is dict and document.get("schema_version") == "paper-reproduction/v1"


def contract_validate(document, task_id=None):
    """Strict version dispatch; scientific validity is never authenticated."""
    if _legacy(document):
        return v1.contract_validate(document, task_id)
    return _v2_contract_validate(document, task_id)


def outcomes_validate(document, reproduction_contract, improvement_contract):
    """Bind the same original task; preserve the old v1 validation behavior."""
    if _legacy(reproduction_contract):
        return v1.outcomes_validate(document, reproduction_contract, improvement_contract)
    return _v2_outcomes_validate(document, reproduction_contract, improvement_contract)


def admit_outcome(outcomes, reproduction_contract, improvement_contract, receipt):
    """Admit declared v2 metadata only, keeping scientific_outcome unknown."""
    if _legacy(reproduction_contract):
        return v1.admit_outcome(outcomes, reproduction_contract, improvement_contract, receipt)
    return _v2_admit_outcome(outcomes, reproduction_contract, improvement_contract, receipt)


def summary(outcomes, reproduction_contract, improvement_contract, receipts=()):
    """Four outcome/condition cells, one task; no implicit scientific results."""
    if _legacy(reproduction_contract):
        return v1.summary(outcomes, reproduction_contract, improvement_contract, receipts)
    return _v2_summary(outcomes, reproduction_contract, improvement_contract, receipts)
