"""Training-only selection and calibration over explicitly supplied complete banks."""
from fractions import Fraction
import math
from .core import (CLASSES, QualificationError, checked_records, exact_weights,
                   finite_scores, argmax, brier, fraction_json)

TEMPERATURE_EXPONENTS = tuple(range(-8, 9))
TEMPERATURES = tuple(2.0 ** (j / 2.0) for j in TEMPERATURE_EXPONENTS)
FAMILIES = ("ridge", "linear_ovr_svm", "rbf_ovr_svm", "extra_trees", "centroid")


def _complete_bank(records, scores, classes):
    if set(scores) != {r.case_id for r in records}:
        raise QualificationError("raw OOF/prediction bank must match complete explicit records")
    return {r.case_id: finite_scores(scores[r.case_id], classes) for r in records}


def select_configuration(records, indexed_score_banks, *, classes=CLASSES, expected_indices=None):
    """Accuracy only; the orchestrator certifies training/OOF provenance separately.

    Each key is the predeclared nonnegative configuration index. Expected indices
    should be supplied by the frozen grid to enforce complete block evaluation.
    Returned accuracy is an exact serializable numerator/denominator, never rounded
    for ranking. Every score vector is checked even when its configuration loses.
    """
    records = checked_records(records, classes)
    if expected_indices is None:
        raise QualificationError("explicit predeclared complete configuration index list required")
    indices = sorted(indexed_score_banks)
    if not indices or any(type(i) is not int or i < 0 for i in indices):
        raise QualificationError("nonnegative integer configuration indices required")
    if indices != sorted(expected_indices):
        raise QualificationError("incomplete or unexpected configuration grid")
    weights = exact_weights(records, classes)
    accuracies = {}
    for index in indices:
        bank = _complete_bank(records, indexed_score_banks[index], classes)
        accuracies[index] = sum((weights[r.case_id] for r in records if argmax(bank[r.case_id]) == r.label), Fraction())
    chosen = max(indices, key=lambda i: (accuracies[i], -i))
    return {"index": chosen, "accuracy_exact": fraction_json(accuracies[chosen]),
            "accuracy": float(accuracies[chosen]), "metric": "exact_hierarchical_accuracy_only",
            "tie_rule": "smallest_predeclared_configuration_index",
            "all_configurations": [{"index": i, "accuracy_exact": fraction_json(accuracies[i])}
                                   for i in indices], "records": len(records)}


def select_family(winners):
    """Require all five family winners; never select by outer outcomes or Brier."""
    if set(winners) != set(FAMILIES):
        raise QualificationError("all five family winners required")
    accuracies = {}
    for family in FAMILIES:
        try:
            val = winners[family]["accuracy_exact"]
            n, d = val["numerator"], val["denominator"]
            if type(n) is not int or type(d) is not int or d <= 0 or not 0 <= n <= d:
                raise ValueError
            accuracies[family] = Fraction(n, d)
        except (KeyError, TypeError, ValueError, ZeroDivisionError):
            raise QualificationError("malformed exact inner accuracy") from None
    index = max(range(len(FAMILIES)), key=lambda i: (accuracies[FAMILIES[i]], -i))
    family = FAMILIES[index]
    return {"family": family, "family_index": index, "accuracy_exact": fraction_json(accuracies[family]),
            "index": winners[family]["index"],
            "additional_base_fits": 0, "additional_calibrator_fits": 0,
            "metric": "inner_accuracy_only", "output_role": "alias_existing_family_predictions"}


def stable_softmax(scores, temperature, *, classes=CLASSES, require_argmax=True):
    scores = finite_scores(scores, classes)
    if type(temperature) not in (int, float) or not math.isfinite(temperature) or temperature <= 0:
        raise QualificationError("finite positive temperature required")
    maximum = max(scores)
    # Subtract first: all exponent arguments are <=0. Finite extreme endpoints
    # may subtract to -inf, whose limiting exponential is exactly zero here.
    exp_scores = [math.exp((s - maximum) / temperature) for s in scores]
    total = math.fsum(exp_scores)
    probabilities = [s / total for s in exp_scores]
    if (not math.isfinite(total) or total <= 0 or any(not math.isfinite(p) for p in probabilities)
            or (require_argmax and argmax(probabilities) != argmax(scores))):
        raise QualificationError("float64 softmax argmax/finite qualification failed")
    return probabilities


def calibrate_temperature(records, selected_oof_scores, *, classes=CLASSES):
    """17 temperatures on chosen configuration's outer-training OOF scores only.

    No lower nested fits, no calibrated inner-Brier model selection. The chosen
    temperature must pass the raw/probability argmax gate on every selected OOF
    row. Any failure invalidates reference qualification, not one candidate case.
    """
    records = checked_records(records, classes)
    bank = _complete_bank(records, selected_oof_scores, classes)
    weights = exact_weights(records, classes)
    objectives = []
    for temperature in TEMPERATURES:
        loss = math.fsum(float(weights[r.case_id]) * brier(stable_softmax(bank[r.case_id], temperature,
                         classes=classes, require_argmax=False), r.label) for r in records)
        if not math.isfinite(loss):
            raise QualificationError("nonfinite calibration objective")
        objectives.append(loss)
    chosen = min(range(17), key=lambda i: (objectives[i], abs(TEMPERATURE_EXPONENTS[i]), TEMPERATURES[i]))
    for r in records:
        stable_softmax(bank[r.case_id], TEMPERATURES[chosen], classes=classes, require_argmax=True)
    return {"temperature_index": chosen, "temperature_exponent_j": TEMPERATURE_EXPONENTS[chosen],
            "temperature": TEMPERATURES[chosen], "oof_training_brier": objectives[chosen],
            "temperature_objectives": objectives, "oof_records": len(records), "calibrator_fits": 1,
            "objective_passes": 17, "objective_row_evaluations": 17 * len(records),
            "loss_role": "calibration_training_diagnostic_not_validated_selection_metric",
            "numerical_ordering_certificate": {"checked_rows": len(records), "mismatches": 0,
                "arithmetic": "Python float IEEE-754 binary64; math.exp and math.fsum",
                "tie_rule": "smallest_ontology_index", "scope": "selected_temperature_OOF_only"}}


def apply_temperature(scores, calibration, *, classes=CLASSES):
    """Explicit outer/raw-score bank; all rows gate before any result is returned."""
    try:
        index = calibration["temperature_index"]
        temperature = calibration["temperature"]
        if type(index) is not int or not 0 <= index < 17 or temperature != TEMPERATURES[index]:
            raise ValueError
    except (KeyError, TypeError, ValueError):
        raise QualificationError("invalid frozen temperature binding") from None
    if not scores or any(not isinstance(case, str) or not case for case in scores):
        raise QualificationError("nonempty keyed prediction scores required")
    probabilities = {case: stable_softmax(values, temperature, classes=classes) for case, values in scores.items()}
    return {"probabilities": probabilities, "numerical_ordering_certificate": {
        "checked_rows": len(probabilities), "mismatches": 0,
        "scope": "entire_explicit_prediction_bank", "temperature_index": index}}
