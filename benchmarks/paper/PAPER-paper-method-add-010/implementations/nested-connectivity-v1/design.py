"""Outcome-blind fold proposal for the separately documented prospective design.

Exactly 94 supplied canonical identifiers are required. Cardinality and hashes
cannot establish that those identifiers actually represent the paper cohort.
The resulting proposal still requires independent cohort and policy admission.
"""
import hashlib


def _ordered(people, salt):
    return sorted(people, key=lambda person: (hashlib.sha256((salt + person).encode("utf-8")).hexdigest(), person))


def recommended_fold_plan(participants):
    if not isinstance(participants, list) or len(participants) != 94:
        raise ValueError("The proposed paper-cohort design requires exactly 94 identifiers")
    if any(not isinstance(p, str) or not p or p != p.strip() or len(p) > 200
           or any(ord(c) < 32 for c in p) for p in participants):
        raise ValueError("Invalid canonical participant identifier")
    if len(set(participants)) != 94:
        raise ValueError("Participant identifiers must be unique")
    ordered = _ordered(participants, "meg-policy-v1|outer|")
    outer = [ordered[index::10] for index in range(10)]
    result = []
    for index, test in enumerate(outer):
        fold_id = "outer-%02d" % index
        train = sorted(set(participants) - set(test))
        inner_order = _ordered(train, "meg-policy-v1|" + fold_id + "|inner|")
        result.append({"id": fold_id, "test_participants": test,
                       "inner_validation_participants": [inner_order[j::5] for j in range(5)]})
    return {"schema": "meg_recommended_fold_plan_v1", "outer_folds": result,
            "construction_uses_outcomes": False, "authentic_cohort_verified": False,
            "scientific_policy_frozen": False, "scientific_qualification": False}
