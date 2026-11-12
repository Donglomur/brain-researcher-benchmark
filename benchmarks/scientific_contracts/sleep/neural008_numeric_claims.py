"""Check six full-panel EOG numerical claims, including null definedness.

This pure checker accepts trusted expected values; it does not authenticate their
data, provenance, fitting procedure, or scientific interpretation. Its rate is
numerical consistency, not a scientific-reasoning score. No actual roster is
embedded. All six targets must describe the same 78 supplied person identities.

An assertion is {"id": ..., "value": number_or_None}, optionally with
"per_person": None or a complete 78-person mapping. Explicit abstention is
exactly {"id": ..., "abstain": True}. Omission is distinct from abstention.
Well-formed unknown IDs receive no credit. Malformed inputs raise ValueError.
"""

import math


TOLERANCE = 1e-10
PERSON_COUNT = 78
TARGET_IDS = (
    "frozen_program:eog_gain:macro_f1",
    "case_adaptive_equal_inputs_tools_compute:eog_gain:macro_f1",
    "mode_interaction:eog_gain:macro_f1",
    "frozen_program:eog_gain:rem_recall",
    "case_adaptive_equal_inputs_tools_compute:eog_gain:rem_recall",
    "mode_interaction:eog_gain:rem_recall",
)


def _number(value, location, bound=None):
    """Return a finite Python float or None, rejecting booleans and overflow."""
    if value is None:
        return None
    if type(value) not in (int, float):
        raise ValueError(location + " must be a finite number or None")
    try:
        value = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError(location + " must be a finite number or None") from exc
    if not math.isfinite(value):
        raise ValueError(location + " must be finite")
    if bound is not None and not -bound <= value <= bound:
        raise ValueError(location + " is outside the target's difference bound")
    return value


def _person_id(value):
    return (
        type(value) is str
        and bool(value)
        and value.isascii()
        and value.isdigit()
        and (value == "0" or not value.startswith("0"))
    )


def _person_values(values, location, bound, people=None):
    if type(values) is not dict or len(values) != PERSON_COUNT:
        raise ValueError(location + " must contain exactly 78 person IDs")
    if not all(_person_id(person) for person in values):
        raise ValueError(location + " requires canonical nonnegative decimal IDs")
    if people is not None and set(values) != people:
        raise ValueError(location + " must use the exact expected person IDs")
    # Decimal-string ordering avoids parsing potentially very large identifiers.
    return {
        person: _number(values[person], location + "/" + person, bound)
        for person in sorted(values, key=lambda p: (len(p), p))
    }


def _bound(target_id):
    return 2.0 if target_id.startswith("mode_interaction:") else 1.0


def _expected(expected_targets):
    if type(expected_targets) is not dict or set(expected_targets) != set(TARGET_IDS):
        raise ValueError("expected_targets must contain exactly the six target IDs")
    cleaned = {}
    people = None
    for target_id in TARGET_IDS:
        row = expected_targets[target_id]
        if type(row) is not dict or set(row) != {"aggregate", "per_person"}:
            raise ValueError(target_id + " expected row has an invalid shape")
        bound = _bound(target_id)
        values = _person_values(row["per_person"], target_id, bound, people)
        if people is None:
            people = set(values)
        aggregate = _number(row["aggregate"], target_id + "/aggregate", bound)
        if any(value is None for value in values.values()):
            if aggregate is not None:
                raise ValueError(target_id + " aggregate must be None if any person is undefined")
        else:
            mean = math.fsum(values.values()) / PERSON_COUNT
            if aggregate is None or abs(aggregate - mean) > TOLERANCE:
                raise ValueError(target_id + " aggregate must be the all-78-person mean")
        cleaned[target_id] = {"aggregate": aggregate, "per_person": values}
    return cleaned, people


def _claims(claims, people):
    if type(claims) is not list:
        raise ValueError("claims must be a list")
    cleaned = {}
    for row in claims:
        if type(row) is not dict or type(row.get("id")) is not str or not row["id"]:
            raise ValueError("each claim requires a nonempty string id")
        target_id = row["id"]
        if target_id in cleaned:
            raise ValueError("duplicate claim id: " + target_id)
        if set(row) == {"id", "abstain"} and row["abstain"] is True:
            cleaned[target_id] = {"id": target_id, "abstain": True}
            continue
        if set(row) not in ({"id", "value"}, {"id", "value", "per_person"}):
            raise ValueError(target_id + " is neither an assertion nor explicit abstention")
        # Unknown IDs have no target-specific numeric bound but still must obey
        # the same syntax, finite-number, and supplied-person-support rules.
        bound = _bound(target_id) if target_id in TARGET_IDS else None
        value = _number(row["value"], target_id + "/value", bound)
        values = row.get("per_person")
        if values is not None:
            values = _person_values(values, target_id + "/per_person", bound, people)
        cleaned[target_id] = {"id": target_id, "value": value, "per_person": values}
    return cleaned


def _compare(value, expected):
    same_definedness = (value is None) == (expected is None)
    error = None if value is None or expected is None else abs(value - expected)
    return {
        "value": value,
        "expected": expected,
        "definedness_match": same_definedness,
        "absolute_error": error,
        "consistent": same_definedness and (error is None or error <= TOLERANCE),
    }


def check_claims(claims, expected_targets):
    """Return numerical comparisons without modifying either input.

    Counts ``asserted`` and ``evaluable`` include recognized assertions only,
    including asserted None values: definedness itself is checkable. ``abstain``
    counts recognized explicit abstentions. ``unsupported`` counts all unknown
    IDs regardless of payload kind. ``undefined_assertions`` counts recognized
    assertions with aggregate None, and ``finite_assertions`` counts the rest.
    ``negative_expected`` counts recognized assertions whose expected aggregate
    is finite and negative; negative results can be completely consistent.

    A recognized assertion is consistent only if its aggregate and every
    optionally asserted person value agree, with exact None definedness and
    absolute tolerance 1e-10. Expected aggregates obey the all-person None rule
    and must agree with the finite 78-person mean within the same tolerance.
    The checker cannot identify a false supplied roster or fabricated expected
    measurements. Upstream report admission is a separate responsibility.
    """
    expected, people = _expected(expected_targets)
    supplied = _claims(claims, people)
    counts = dict.fromkeys(
        ("submitted", "asserted", "evaluable", "consistent", "inconsistent",
         "abstain", "not_submitted", "unsupported", "undefined_assertions",
         "finite_assertions", "negative_expected"), 0
    )
    counts["submitted"] = len(supplied)
    recognized = []
    for target_id in TARGET_IDS:
        claim = supplied.get(target_id)
        result = {
            "id": target_id,
            "status": "not_submitted",
            "aggregate_comparison": None,
            "per_person_comparison": None,
        }
        if claim is None:
            counts["not_submitted"] += 1
        elif claim.get("abstain") is True:
            result["status"] = "abstain"
            counts["abstain"] += 1
        else:
            counts["asserted"] += 1
            counts["evaluable"] += 1
            kind = "undefined_assertions" if claim["value"] is None else "finite_assertions"
            counts[kind] += 1
            aggregate = expected[target_id]["aggregate"]
            if aggregate is not None and aggregate < 0:
                counts["negative_expected"] += 1
            comparison = _compare(claim["value"], aggregate)
            result["aggregate_comparison"] = comparison
            consistent = comparison["consistent"]
            if claim["per_person"] is not None:
                mismatches = []
                for person, value in claim["per_person"].items():
                    check = _compare(value, expected[target_id]["per_person"][person])
                    if not check["consistent"]:
                        mismatches.append({"person": person, **check})
                result["per_person_comparison"] = {
                    "checked": PERSON_COUNT,
                    "consistent": PERSON_COUNT - len(mismatches),
                    "inconsistent": len(mismatches),
                    "mismatches": mismatches,
                }
                consistent = consistent and not mismatches
            result["status"] = "consistent" if consistent else "inconsistent"
            counts[result["status"]] += 1
        recognized.append(result)
    unsupported = [
        {"id": target_id, "status": "unsupported",
         "submission_kind": "abstain" if claim.get("abstain") is True else "assertion"}
        for target_id, claim in supplied.items() if target_id not in expected
    ]
    counts["unsupported"] = len(unsupported)
    numerator = counts["consistent"]
    denominator = counts["evaluable"]
    return {
        "schema": "neural008_numeric_claims_v1",
        "recognized_claims": recognized,
        "unsupported_claims": unsupported,
        "counts": counts,
        "verification_numerator": numerator,
        "verification_denominator": denominator,
        "numeric_verification_rate": numerator / denominator if denominator else None,
        "scientific_claim_validity": "not_assessed",
        "empirical_provenance": "not_authenticated",
    }
