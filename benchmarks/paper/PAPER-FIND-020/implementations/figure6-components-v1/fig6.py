"""Numerical components for Ding et al. Figure 6d, not an admitted benchmark.

The operator must recover and authenticate original image/condition membership
before using these components on scientific predictions. No source memberships,
random strength-matching algorithm, fit seeds, or curve aggregation are invented.
"""

from dataclasses import dataclass
import math
from numbers import Real


MODES = frozenset(("like_to_like", "strength_matched_random"))


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite real number")
    return float(value)


def like_to_like_eligible(weight, signal_correlation):
    """The two strict thresholds in Methods, RNN model (Par144).

    Signed weight, not magnitude or a recomputed quantile. This predicate does
    not determine the correlation image roster, recurrent-matrix orientation,
    diagonal policy, or random comparator. Those require source recovery.
    """
    weight = _number(weight, "weight")
    corr = _number(signal_correlation, "signal_correlation")
    # Validate the supplied Real before float conversion can round an invalid
    # correlation onto an endpoint (for example Fraction(1) + 10**-100).
    if not -1 <= signal_correlation <= 1:
        raise ValueError("signal_correlation must lie in [-1, 1]")
    return weight > 0.01 and corr > 0.2


@dataclass(frozen=True, order=True)
class Condition:
    """A declared source condition; IDs must come from the operator's roster."""

    network_id: str
    realization_id: str
    ablated_connections: int
    mode: str

    def __post_init__(self):
        if not all(isinstance(x, str) and x for x in (self.network_id, self.realization_id)):
            raise ValueError("network and realization IDs must be nonempty strings")
        if type(self.ablated_connections) is not int or self.ablated_connections < 0:
            raise ValueError("ablated_connections must be a nonnegative integer")
        if self.mode not in MODES:
            raise ValueError("both paper ablation modes have explicit names")


@dataclass(frozen=True)
class Accuracy:
    correct: int
    images: int

    @property
    def fraction(self):
        return self.correct / self.images


def _labels(rows, role):
    """Accept pairs rather than a dict, so duplicate image IDs cannot vanish."""
    result = {}
    for image_id, label in rows:
        if not isinstance(image_id, str) or not image_id:
            raise ValueError(f"{role}: image IDs must be nonempty strings")
        if image_id in result:
            raise ValueError(f"{role}: duplicate image ID")
        if type(label) is not int or not 0 <= label < 10:
            raise ValueError(f"{role}: MNIST class labels must be integers 0 through 9")
        result[image_id] = label
    if not result:
        raise ValueError(f"{role}: empty image support")
    return result


def _conditions(expected):
    expected = tuple(expected)
    if not expected or not all(isinstance(c, Condition) for c in expected):
        raise ValueError("declare nonempty source condition support")
    if len(set(expected)) != len(expected):
        raise ValueError("duplicate source condition")
    pairs = {}
    for c in expected:
        pairs.setdefault((c.network_id, c.realization_id, c.ablated_connections), set()).add(c.mode)
    if any(modes != MODES for modes in pairs.values()):
        raise ValueError("each count/network/realization requires both paper control modes")
    return expected


def _predictions(expected, predictions, targets):
    result = {}
    for condition, rows in predictions:
        if not isinstance(condition, Condition):
            raise ValueError("prediction conditions must be Condition instances")
        if condition in result:
            raise ValueError("duplicate prediction condition")
        labels = _labels(rows, "predictions")
        if labels.keys() != targets.keys():
            raise ValueError("prediction image membership differs from the complete target roster")
        result[condition] = labels
    if result.keys() != set(expected):
        raise ValueError("prediction condition membership differs from the declared source roster")
    return result


def score_curve(target_rows, expected_conditions, prediction_rows):
    """Count image correctness separately for every declared original condition.

    Conditions and targets are operator inputs, never inferred from submissions.
    Missing/extra images or conditions fail. The denominator is image count,
    not an average of possibly unequal batch accuracies. Output fractions use
    [0, 1]; no uncertainty, overall curve score, or scientific pass is produced.
    Naming a condition strength_matched_random does not verify its intervention.
    """
    targets = _labels(target_rows, "targets")
    expected = _conditions(expected_conditions)
    predictions = _predictions(expected, prediction_rows, targets)
    return {
        c: Accuracy(sum(predictions[c][i] == label for i, label in targets.items()), len(targets))
        for c in expected
    }


def paired_differences(target_rows, expected_conditions, author_rows, candidate_rows):
    """Image-paired counts per condition; images are not independent networks.

    Both methods must already have comparable interventions, original support,
    observations and budgets. This calculation does not authenticate those facts
    or turn supplied author predictions into a qualified author replay.
    """
    targets = _labels(target_rows, "targets")
    expected = _conditions(expected_conditions)
    author = _predictions(expected, author_rows, targets)
    candidate = _predictions(expected, candidate_rows, targets)
    result = {}
    for c in expected:
        improved = regressed = both_correct = both_wrong = 0
        for image_id, target in targets.items():
            a = author[c][image_id] == target
            b = candidate[c][image_id] == target
            improved += not a and b
            regressed += a and not b
            both_correct += a and b
            both_wrong += not a and not b
        result[c] = {
            "images": len(targets),
            "candidate_only_correct": improved,
            "author_only_correct": regressed,
            "both_correct": both_correct,
            "both_wrong": both_wrong,
            "accuracy_difference_fraction": (improved - regressed) / len(targets),
        }
    return result
