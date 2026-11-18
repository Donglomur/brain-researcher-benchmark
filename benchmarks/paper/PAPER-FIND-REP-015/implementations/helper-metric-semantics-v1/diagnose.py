"""Distinguish reward-class metrics from a two-class macro definition.

This is an operator-side definition diagnostic, not a scorer or a claim that
the observed HappyML branch produced the paper's historical saved results.
No source outputs, trial identities, data, models, splits or thresholds load.
"""
from __future__ import annotations

from fractions import Fraction

KEYS = frozenset(("tp", "tn", "fp", "fn"))


def _ratio(numerator: int, denominator: int):
    return Fraction(numerator, denominator) if denominator else None


def _class_metrics(tp: int, fp: int, fn: int):
    return {
        "recall": _ratio(tp, tp + fn),
        "precision": _ratio(tp, tp + fp),
        "f1": _ratio(2 * tp, 2 * tp + fp + fn),
    }


def diagnose_counts(counts: dict) -> dict:
    """Describe both definitions on one complete, trusted confusion matrix.

    Reward is label 1. The macro definition gives both fixed labels 0 and 1
    equal weight; it does not substitute a library's inferred label set or
    undefined-metric convention. Undefined terms propagate as None.
    Source-unit aggregation is deliberately outside this diagnostic.
    """
    if not isinstance(counts, dict) or set(counts) != KEYS:
        raise ValueError("Exactly tp, tn, fp and fn counts are required")
    if any(type(value) is not int or value < 0 for value in counts.values()):
        raise ValueError("Confusion counts must be nonnegative integers, not booleans")
    tp, tn, fp, fn = (counts[k] for k in ("tp", "tn", "fp", "fn"))
    total = tp + tn + fp + fn
    if not total:
        raise ValueError("An empty confusion matrix has no diagnostic meaning")
    positive = _class_metrics(tp, fp, fn)
    negative = _class_metrics(tn, fn, fp)
    macro = {
        key: None if positive[key] is None or negative[key] is None
        else (positive[key] + negative[key]) / 2
        for key in positive
    }
    # Compare exact fractions. Rounded floats must not create a false mismatch.
    differs = {
        key: None if positive[key] is None or macro[key] is None
        else positive[key] != macro[key]
        for key in positive
    }
    def numeric(values):
        return {key: None if value is None else float(value)
                for key, value in values.items()}
    return {
        "schema": "cerebellar-svm-metric-definition-diagnostic/v1",
        "confusion": dict(counts),
        "trial_count": total,
        "accuracy": float(Fraction(tp + tn, total)),
        "reward_class": numeric(positive),
        "fixed_two_class_macro": numeric(macro),
        "definitions_differ": differs,
        "undefined_macro_metrics": [key for key, value in macro.items() if value is None],
        "historical_helper_equivalence": "unresolved",
        "source_scope": "operator_definition_diagnostic_only",
    }
