"""Independent, generated-input-only scalar oracle for supplemental EEG metrics.

This is a test oracle, not the production evaluator.  It deliberately computes
ROC AUC by examining every positive-negative pair rather than sorting ranks.
The author used only the requested metric definitions and hand calculations;
no production implementation, authentic data, or fitted model was consulted.
"""

import math


def oracle(labels, probabilities):
    """Return pairwise ROC AUC and balanced accuracy at inclusive cutoff 0.2.

    Inputs are finite iterables of builtin integer labels (0 or 1) and builtin
    integer/float probabilities in [0, 1].  Boolean values are not accepted.
    Both classes must occur, since both returned metrics require them here.
    Invalid inputs raise ValueError.  This intentionally quadratic oracle is
    intended only for small generated controls.
    """
    try:
        labels = tuple(labels)
        probabilities = tuple(probabilities)
    except TypeError as exc:
        raise ValueError("labels and probabilities must be iterable") from exc
    if not labels or len(labels) != len(probabilities):
        raise ValueError("inputs must be nonempty and have equal lengths")
    if any(type(label) is not int or label not in (0, 1) for label in labels):
        raise ValueError("labels must be builtin integers 0 or 1")
    for probability in probabilities:
        if type(probability) not in (int, float):
            raise ValueError("probabilities must be builtin numeric scalars")
        if not 0 <= probability <= 1 or not math.isfinite(probability):
            raise ValueError("probabilities must be finite and in [0, 1]")

    positive = []
    negative = []
    tp = tn = fp = fn = 0
    for label, probability in zip(labels, probabilities):
        predicted_positive = probability >= 0.2
        if label == 1:
            positive.append(probability)
            if predicted_positive:
                tp += 1
            else:
                fn += 1
        else:
            negative.append(probability)
            if predicted_positive:
                fp += 1
            else:
                tn += 1
    if not positive or not negative:
        raise ValueError("both label classes are required")

    pair_credit = 0.0
    for positive_probability in positive:
        for negative_probability in negative:
            if positive_probability > negative_probability:
                pair_credit += 1.0
            elif positive_probability == negative_probability:
                pair_credit += 0.5

    return {
        "roc_auc": pair_credit / (len(positive) * len(negative)),
        "balanced_accuracy_at_0_2": (tp / (tp + fn) + tn / (tn + fp)) / 2.0,
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
    }
