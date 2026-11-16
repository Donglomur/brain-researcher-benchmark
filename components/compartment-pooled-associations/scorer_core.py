"""Finite result-artifact scoring only; no candidate execution or empirical I/O.

The caller pins the public packet and accepted private reference. This module
contains no empirical reference values and imports only the standard library.
"""

import hashlib
import json
import math


TASK_ID = "PAPER-FIND-REP-012"
ANALYSIS_ID = "released_source_four_pooled_pearson_v1"
ENDPOINT_IDS = ("apical_local", "basal_local", "apical_coincident", "basal_coincident")
NUMERIC_FIELDS = ("r", "p", "paired_y_mean", "paired_y_sd")
COUNT_FIELDS = ("raw_rows", "eligible_rows", "paired_rows", "excluded_nan_rows")
DIGEST_FIELDS = ("eligible_row_ids_sha256", "paired_row_ids_sha256")
SUPPORT_FIELDS = COUNT_FIELDS + DIGEST_FIELDS
COHORT_FIELDS = ("member_count", "raw_rows", "unique_mice", "shared_mouse_ids", "raw_row_ids_sha256")
TOLERANCES = {"r": (1e-9, 1e-7), "p": (1e-12, 1e-6),
              "paired_y_mean": (1e-10, 1e-8), "paired_y_sd": (1e-10, 1e-8)}
MAX_SUBMISSION_BYTES = 32768
MAX_REFERENCE_BYTES = 32768
MAX_ROWS = 50000


class InvalidSubmission(ValueError):
    pass


class UnsupportedSubmission(ValueError):
    pass


def _need(ok, message):
    if not ok:
        raise InvalidSubmission(message)


def _keys(value, wanted):
    _need(type(value) is dict and set(value) == set(wanted), "Exact object fields required")


def _integer_token(text):
    # Avoid Python's process-wide decimal-string digit limit without changing
    # it. The byte cap bounds work; large values are rejected at their field.
    negative = text.startswith("-")
    digits = text[1:] if negative else text
    result = 0
    for start in range(0, len(digits), 1000):
        part = digits[start:start + 1000]
        result = result * (10 ** len(part)) + int(part)
    return -result if negative else result


def _float_token(text):
    result = float(text)
    if result == 0. and any(c in "123456789" for c in text.lower().split("e", 1)[0]):
        raise UnsupportedSubmission("Nonzero decimal scalar underflows finite binary64 to zero")
    return result


def decode(body, *, cap):
    _need(type(body) is bytes and 0 < len(body) <= cap, "Bounded nonempty UTF-8 JSON required")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            _need(key not in result, "Duplicate JSON key")
            result[key] = value
        return result

    def nonfinite(unused):
        raise InvalidSubmission("Nonfinite JSON literal")

    try:
        return json.loads(body.decode("utf-8"), object_pairs_hook=unique,
                          parse_constant=nonfinite, parse_int=_integer_token, parse_float=_float_token)
    except (UnicodeError, ValueError, RecursionError) as exc:
        if isinstance(exc, (InvalidSubmission, UnsupportedSubmission)):
            raise
        raise InvalidSubmission("Malformed JSON or UTF-8") from exc


def _sha(value):
    _need(type(value) is str and len(value) == 64
          and all(c in "0123456789abcdef" for c in value), "Lowercase SHA256 required")
    return value


def _count(value):
    _need(type(value) is int and 0 <= value <= MAX_ROWS, "Integer count in0..50000 required")
    return value


def _finite(value):
    _need(type(value) in (int, float), "Numeric scalar cannot be Boolean, string or null")
    try:
        result = float(value)
    except (OverflowError, ValueError) as exc:
        raise UnsupportedSubmission("Numeric scalar is not representable in finite binary64") from exc
    if not math.isfinite(result):
        raise UnsupportedSubmission("Numeric scalar is not representable in finite binary64")
    return result


def _cohort(value):
    _keys(value, COHORT_FIELDS)
    result = {key: _count(value[key]) for key in ("member_count", "raw_rows", "unique_mice")}
    mice = value["shared_mouse_ids"]
    _need(type(mice) is list and len(mice) <= MAX_ROWS, "Bounded shared-mouse list")
    _need(all(type(mouse) is str and 1 <= len(mouse) <= 128 for mouse in mice), "Bounded mouse strings")
    _need(len(set(mice)) == len(mice), "Duplicate shared-mouse identity")
    result["shared_mouse_ids"] = sorted(mice)
    result["raw_row_ids_sha256"] = _sha(value["raw_row_ids_sha256"])
    return result


def _result(value):
    _keys(value, (*SUPPORT_FIELDS, *NUMERIC_FIELDS))
    result = {key: _count(value[key]) for key in COUNT_FIELDS}
    result.update({key: _sha(value[key]) for key in DIGEST_FIELDS})
    result.update({key: _finite(value[key]) for key in NUMERIC_FIELDS})
    # Finite scientifically wrong values (including out-of-domain r/p/SD and
    # inconsistent denominators) are assessed, not mistaken for malformed JSON.
    return result


def _header(value, input_manifest_sha256, *, reference=False):
    _sha(input_manifest_sha256)
    _need(type(value["schema_version"]) is int, "Integer schema version required")
    if value["schema_version"] != 1 or value["task_id"] != TASK_ID:
        raise UnsupportedSubmission("Unsupported task or schema version")
    _sha(value["input_manifest_sha256"])
    if value["input_manifest_sha256"] != input_manifest_sha256:
        raise UnsupportedSubmission("Different public input packet")
    if not reference and value["analysis_id"] != ANALYSIS_ID:
        raise UnsupportedSubmission("Unsupported declared analysis")


def validate_submission(body, *, input_manifest_sha256):
    value = decode(body, cap=MAX_SUBMISSION_BYTES)
    _keys(value, ("schema_version", "task_id", "input_manifest_sha256", "analysis_id", "cohort", "endpoints"))
    _header(value, input_manifest_sha256)
    _need(type(value["endpoints"]) is list and len(value["endpoints"]) == 4,
          "All four endpoint slots required; use explicit abstention")
    endpoints = {}
    for row in value["endpoints"]:
        _keys(row, ("endpoint_id", "status", "reason", "result"))
        identifier = row["endpoint_id"]
        _need(type(identifier) is str and identifier in ENDPOINT_IDS and identifier not in endpoints,
              "Exact unique endpoint identities required")
        status = row["status"]
        _need(type(status) is str and status in ("reported", "abstained"), "Explicit endpoint status")
        if status == "reported":
            _need(row["reason"] is None, "Reported result has null reason")
            result = _result(row["result"])
        else:
            _need(row["result"] is None and type(row["reason"]) is str
                  and 1 <= len(row["reason"]) <= 512, "Abstention has null result and bounded reason")
            result = None
        endpoints[identifier] = {"endpoint_id": identifier, "status": status,
                                 "reason": row["reason"], "result": result}
    return {"cohort": _cohort(value["cohort"]), "endpoints": endpoints,
            "input_manifest_sha256": input_manifest_sha256}


def validate_reference(body, *, input_manifest_sha256):
    """Validate the private prep artifact, never synthesize expected statistics."""
    value = decode(body, cap=MAX_REFERENCE_BYTES)
    _keys(value, ("schema_version", "task_id", "input_manifest_sha256", "cohort", "endpoints"))
    _header(value, input_manifest_sha256, reference=True)
    _need(type(value["endpoints"]) is list and len(value["endpoints"]) == 4, "Four private endpoints required")
    endpoints = {}
    for row in value["endpoints"]:
        _keys(row, ("endpoint_id", *SUPPORT_FIELDS, *NUMERIC_FIELDS))
        identifier = row["endpoint_id"]
        _need(type(identifier) is str and identifier in ENDPOINT_IDS and identifier not in endpoints,
              "Private endpoint identity")
        result = _result({key: row[key] for key in (*SUPPORT_FIELDS, *NUMERIC_FIELDS)})
        _need(not _scientific_issues(result), "Private reference scientific domain/count inconsistency")
        endpoints[identifier] = result
    cohort = _cohort(value["cohort"])
    for compartment in ("apical", "basal"):
        left, right = endpoints[compartment + "_local"], endpoints[compartment + "_coincident"]
        _need(all(left[key] == right[key] for key in ("raw_rows", "eligible_rows", "eligible_row_ids_sha256")),
              "Private same-compartment eligibility disagrees")
    _need(endpoints["apical_local"]["raw_rows"] + endpoints["basal_local"]["raw_rows"] == cohort["raw_rows"],
          "Private cohort raw row count disagrees")
    return {"cohort": cohort, "endpoints": endpoints, "input_manifest_sha256": input_manifest_sha256}


def support_digest(pairs):
    """Order-independent identity digest; no row-data access or silent dedup."""
    _need(type(pairs) is list and len(pairs) <= MAX_ROWS, "Bounded support identity list")
    clean = []
    for pair in pairs:
        _need(type(pair) in (list, tuple) and len(pair) == 2
              and type(pair[0]) is str and 1 <= len(pair[0]) <= 1024,
              "Support identity is [source_member,row0]")
        _count(pair[1])
        clean.append((pair[0], pair[1]))
    _need(len(set(clean)) == len(clean), "Duplicate support identity")
    body = json.dumps(sorted(clean), ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def _scientific_issues(result):
    issues = []
    if not -1 <= result["r"] <= 1:
        issues.append("r_outside_minus1_plus1")
    if not 0 <= result["p"] <= 1:
        issues.append("p_outside_0_1")
    if result["paired_y_sd"] < 0:
        issues.append("negative_population_sd")
    if not result["raw_rows"] >= result["eligible_rows"] >= result["paired_rows"] >= 2:
        issues.append("inconsistent_or_insufficient_counts")
    if result["eligible_rows"] - result["paired_rows"] != result["excluded_nan_rows"]:
        issues.append("NaN_denominator_inconsistency")
    return issues


def _numeric_comparison(actual, expected, field):
    atol, rtol = TOLERANCES[field]
    tolerance = atol + rtol * abs(expected)
    difference = actual - expected
    if math.isfinite(difference):
        error = abs(difference)
        scale = max(tolerance, error)
        credit = (tolerance / scale) / (tolerance / scale + error / scale)
        error_state = "finite"
        within = error <= tolerance
    else:
        # Valid finite inputs can have an unrepresentable difference. Preserve
        # a finite credit using scaled subtraction instead of dropping a field.
        scale = max(abs(actual), abs(expected), tolerance)
        scaled_error = abs(actual / scale - expected / scale)
        credit = (tolerance / scale) / (tolerance / scale + scaled_error)
        error, error_state, within = None, "exceeds_binary64_range", False
    return {"absolute_error": error, "absolute_error_state": error_state,
            "tolerance": tolerance, "within_tolerance": within, "credit": credit}


def score_submission(candidate, reference):
    """Score validated artifacts. No single-field or missing-slot denominator changes."""
    cohort_matches = {key: candidate["cohort"][key] == reference["cohort"][key] for key in COHORT_FIELDS}
    rows, credits, support_matches = [], [], []
    reported, all_numerics_agree, scientific_issues = 0, True, 0
    for identifier in ENDPOINT_IDS:
        candidate_row = candidate["endpoints"][identifier]
        if candidate_row["status"] == "abstained":
            credits.extend([0.] * 4)
            support_matches.extend([False] * 6)
            all_numerics_agree = False
            rows.append({"endpoint_id": identifier, "status": "abstained",
                         "reason": candidate_row["reason"], "numeric": None,
                         "support_matches": {key: False for key in SUPPORT_FIELDS},
                         "numeric_score": 0., "scientific_issues": []})
            continue
        reported += 1
        actual, expected = candidate_row["result"], reference["endpoints"][identifier]
        numerics = {field: _numeric_comparison(actual[field], expected[field], field) for field in NUMERIC_FIELDS}
        matches = {field: actual[field] == expected[field] for field in SUPPORT_FIELDS}
        issues = _scientific_issues(actual)
        scientific_issues += len(issues)
        all_numerics_agree = all_numerics_agree and all(v["within_tolerance"] for v in numerics.values())
        credits.extend(v["credit"] for v in numerics.values())
        support_matches.extend(matches.values())
        rows.append({"endpoint_id": identifier, "status": "reported", "reason": None,
                     "numeric": numerics, "support_matches": matches,
                     "numeric_score": math.fsum(v["credit"] for v in numerics.values()) / 4,
                     "scientific_issues": issues})
    numeric_score = math.fsum(credits) / 16
    endpoint_support_score = sum(support_matches) / 24
    cohort_score = sum(cohort_matches.values()) / 5
    support_score = endpoint_support_score * cohort_score
    complete = (reported == 4 and all_numerics_agree and all(support_matches)
                and all(cohort_matches.values()) and scientific_issues == 0)
    return {"status": "scored", "scientific_outcome": "reconstructed" if complete else
            "incomplete" if reported < 4 else "discrepant",
            "score": numeric_score * support_score, "direction": "higher",
            "numeric_score": numeric_score, "endpoint_support_score": endpoint_support_score,
            "cohort_score": cohort_score, "support_score": support_score,
            "full_reconstruction": complete, "reported_endpoints": reported, "endpoint_slots": 4,
            "numeric_field_slots": 16, "compared_numeric_fields": 4 * reported,
            "endpoint_support_slots": 24, "cohort_slots": 5,
            "cohort_matches": cohort_matches, "endpoints": rows,
            "candidate_code_executed": False, "input_dependence_verified": False,
            "declared_method_is_execution_proof": False, "published_statistics_targeted": False,
            "full_paper_reproduced": False, "hierarchical_improvement_qualified": False}


def grade_submission(submission_body, reference_body, *, input_manifest_sha256):
    """Convenience boundary: candidate syntax first; private faults are operator faults."""
    try:
        candidate = validate_submission(submission_body, input_manifest_sha256=input_manifest_sha256)
    except (InvalidSubmission, UnsupportedSubmission) as exc:
        return {"status": "unsupported_submission" if isinstance(exc, UnsupportedSubmission)
                else "invalid_submission", "score": None, "full_reconstruction": False,
                "reason": str(exc), "private_reference_decoded": False, "candidate_code_executed": False}
    try:
        reference = validate_reference(reference_body, input_manifest_sha256=input_manifest_sha256)
    except (InvalidSubmission, UnsupportedSubmission) as exc:
        return {"status": "operator_error", "score": None, "full_reconstruction": False,
                "reason": str(exc), "private_reference_decoded": True, "candidate_code_executed": False}
    result = score_submission(candidate, reference)
    result["private_reference_decoded"] = True
    return result
