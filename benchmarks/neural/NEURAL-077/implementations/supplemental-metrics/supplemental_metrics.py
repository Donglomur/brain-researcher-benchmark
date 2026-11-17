"""Observed-input supplemental metrics; no file I/O or primary-score changes."""
import math

CASES = ("development-001", "development-002")
THRESHOLD = 0.2


def need(condition, message):
    if not condition:
        raise ValueError(message)


def probabilities(values, expected=None):
    values = list(values)
    need(bool(values) and (expected is None or len(values) == expected), "complete probability vector")
    need(all(type(v) in (int, float) and math.isfinite(v) and 0 <= v <= 1 for v in values), "finite closed-interval probabilities")
    return values


def person(labels, values):
    y, p = list(labels), probabilities(values)
    need(len(y) == len(p) and all(type(v) is int and v in (0, 1) for v in y), "same-length binary integer labels")
    positives = sum(y)
    negatives = len(y) - positives
    need(positives > 0 and negatives > 0, "both classes required; never omit an undefined person")
    # Count doubled positive-negative concordance by exact-tie groups. This is
    # O(n log n), independent of the test oracle's explicit O(n^2) pair loop.
    ranked = sorted(zip(p, y))
    negative_before = doubled_credit = index = 0
    while index < len(ranked):
        end = index + 1
        while end < len(ranked) and ranked[end][0] == ranked[index][0]:
            end += 1
        group_positive = sum(label for _, label in ranked[index:end])
        group_negative = end - index - group_positive
        doubled_credit += 2 * group_positive * negative_before + group_positive * group_negative
        negative_before += group_negative
        index = end
    tp = sum(label == 1 and value >= THRESHOLD for label, value in zip(y, p))
    fp = sum(label == 0 and value >= THRESHOLD for label, value in zip(y, p))
    fn, tn = positives - tp, negatives - fp
    return {"roc_auc": doubled_credit / (2 * positives * negatives),
            "balanced_accuracy_at_0_2": math.fsum((tp / positives, tn / negatives)) / 2,
            "tp": tp, "tn": tn, "fp": fp, "fn": fn}


def summarize(ordered_probabilities, ordered_labels):
    need(type(ordered_probabilities) is dict and set(ordered_probabilities) == set(CASES), "both fixed development probability cases")
    need(type(ordered_labels) is dict and set(ordered_labels) == set(CASES), "both fixed development label cases")
    p = {case: probabilities(ordered_probabilities[case], 200) for case in CASES}
    rows = []
    for case in CASES:
        y = list(ordered_labels[case])
        need(len(y) == 200 and all(type(v) is int and v in (0, 1) for v in y)
             and sum(y) == 40, "unchanged 40-target/160-nontarget person support")
        result = person(y, p[case])
        rows.append({"person_id": case, "n": 200, "n_target": 40, "n_non_target": 160,
                     "roc_auc": result["roc_auc"],
                     "balanced_accuracy_at_0_2": result["balanced_accuracy_at_0_2"],
                     "confusion_at_0_2": {key: result[key] for key in ("tp", "tn", "fp", "fn")}})
    return {"status": "supplemental_scored", "condition": "observed_signal",
            "statistical_unit": "participant", "aggregation": "equal_person_macro",
            "per_person": rows,
            "participant_macro_roc_auc": math.fsum(row["roc_auc"] for row in rows) / 2,
            "participant_macro_balanced_accuracy_at_0_2": math.fsum(row["balanced_accuracy_at_0_2"] for row in rows) / 2,
            "decision_threshold": THRESHOLD, "positive_rule": "probability >= 0.2",
            "auc_exact_tie_credit": 0.5, "predictions_modified": False,
            "primary_metrics_replaced": False, "population_confidence_interval": False,
            "new_independent_samples": 0, "reference_auc_invented": False}
