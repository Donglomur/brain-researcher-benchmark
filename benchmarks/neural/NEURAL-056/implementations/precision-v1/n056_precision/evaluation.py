"""NEURAL-056 evaluator successor using stable correlation and original admission.

Import with the preserved successor-v3 package and this directory on sys.path.
This is an operator API, not a candidate input interface or a runtime admission.
"""
import numpy as np

from .correlation import correlation
from n056.bank_a import macro
from n056.core import digest, need
from n056.evaluation import collect, paired_lifetime, prediction
from n056.protocol import ARMS, PEOPLE, ROLES, SHAPE


def development(panel, records, budget):
    """Retain all 27 inner person/arm products before accessing development Y."""
    need(len(records) == 27, "all nine inner people times three arms before any targets")
    held = records[0]["packet"]["person"]
    need(held in PEOPLE and all(r["packet"]["person"] == held for r in records),
         "one prescribed outer participant per development panel")
    keys = {(r["packet"]["inner_person"], r["packet"]["arm"]) for r in records}
    need(keys == {(p, a) for p in PEOPLE if p != held for a in ARMS},
         "complete distinct inner person-arm roster")
    predicted = {}
    for record in records:
        paired_lifetime(record["train"], record["query"])
        packet = record["packet"]
        predicted[(packet["inner_person"], packet["arm"])] = prediction(record["query"], 3300, budget)
    from n056.packets import inner_target
    scores = {arm: {} for arm in ARMS}
    for record in records:
        packet = record["packet"]
        key = (packet["inner_person"], packet["arm"])
        scores[packet["arm"]][packet["inner_person"]] = correlation(inner_target(panel, packet), predicted[key])["mean"]
    return {
        "score": macro([scores["representation"][p] for p in PEOPLE if p != held]),
        "all_arm_person_means": scores,
        "targets": "training partition only",
        "outer_targets_opened": False,
        "numerical_revision": "neural056-pearson-precision-v1",
    }


def _target_arrays(target):
    need(type(target) is dict and set(target) == {"mean", "half_odd", "half_even"},
         "complete private mean and descriptive reliability arrays")
    result = {}
    for name, value in target.items():
        value = np.asarray(value)
        need(value.shape == SHAPE and value.dtype.kind == "f" and value.dtype.itemsize in (4, 8)
             and np.isfinite(value).all(), "exact finite private image/coordinate/time axes")
        result[name] = value.reshape(200, 1700)
    return result


# Every unordered role pair has one predeclared direction. These descriptive
# contrasts do not select a winner or create additional independent cases.
ROLE_PAIRS = (
    ("I", "F"),
    ("F", "reference_fixed"),
    ("F", "reference_tuned"),
    ("I", "reference_fixed"),
    ("I", "reference_tuned"),
    ("reference_tuned", "reference_fixed"),
)


def _paired_roles(scores):
    """Compare complete operator-computed person scores, never actor scores."""
    def subtract(left, right):
        return None if left is None or right is None else left - right

    def summarize(by_person):
        # macro deliberately propagates any undefined person; no complete-case
        # deletion or coordinate-level pseudo-replication is permitted.
        return {"by_person": by_person, "mean": macro([by_person[p] for p in PEOPLE])}

    comparisons = {}
    for left, right in ROLE_PAIRS:
        arm_differences = {
            arm: {
                person: subtract(scores[left][arm][person]["mean"],
                                 scores[right][arm][person]["mean"])
                for person in PEOPLE
            }
            for arm in ARMS
        }
        control_differences = {}
        for control in ("low_level", "response_permuted"):
            # (left representation - left control) minus
            # (right representation - right control), paired within person.
            control_differences[control] = summarize({
                person: subtract(arm_differences["representation"][person],
                                 arm_differences[control][person])
                for person in PEOPLE
            })
        comparisons[left + "_minus_" + right] = {
            "left_role": left,
            "right_role": right,
            "direction": "left_minus_right",
            "arms": {arm: summarize(arm_differences[arm]) for arm in ARMS},
            "control_effect_differences": control_differences,
        }
    return comparisons


def grade(panel, records, protocol, budget):
    """Admit every original output first; retain the complete original endpoint."""
    admitted = collect(records, protocol, budget)
    scores = {role: {arm: {} for arm in ARMS} for role in ROLES}
    reliability = {}
    for person in PEOPLE:
        target = _target_arrays(panel.outer_target(person))
        for role in ROLES:
            for arm in ARMS:
                scores[role][arm][person] = correlation(target["mean"], admitted[(role, person, arm)])
        rel = correlation(target["half_odd"], target["half_even"])
        reliability[person] = {
            "raw": rel["raw"],
            "mean": None if rel["constant_target"] or rel["constant_prediction"] else rel["mean"],
        }
    result = {}
    for role in ROLES:
        means = {arm: macro([scores[role][arm][p]["mean"] for p in PEOPLE]) for arm in ARMS}
        effects = {}
        for control in ("low_level", "response_permuted"):
            by_person = {
                p: None if scores[role]["representation"][p]["mean"] is None or scores[role][control][p]["mean"] is None
                else scores[role]["representation"][p]["mean"] - scores[role][control][p]["mean"]
                for p in PEOPLE
            }
            effects[control] = {"by_person": by_person, "mean": macro(list(by_person.values()))}
        result[role] = {
            "participant_coordinate_results": scores[role],
            "primary_equal_person_mean": means,
            "paired_controls": effects,
        }
    return {
        "schema": "neural056_complete_grade_v1",
        "protocol_id": digest(protocol),
        "roles": result,
        "paired_role_comparisons": _paired_roles(scores),
        "split_half_reliability": reliability,
        "correction_applied": False,
        "all_final_blocks": 120,
        "conditions_are_not_new_benchmarks": True,
        "population_scope": "ten exposed people conditional on200shared concepts",
        "historical_score_reproduction": False,
        "scientifically_qualified": False,
        "source_note": "Original endpoint retained; native numerical/environment/reference qualifications remain external.",
        "numerical_revision": "neural056-pearson-precision-v1",
    }
