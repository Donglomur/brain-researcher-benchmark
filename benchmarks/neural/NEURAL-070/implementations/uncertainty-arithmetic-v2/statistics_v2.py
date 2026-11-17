"""Finite crossed-bootstrap successor for the unchanged NEURAL-070 estimand.

Load alongside registered-runtime/programme, then call crossed_bootstrap with
the existing evaluator's protected arrays. This module does not open files,
fit a model, change the primary score, or select an active runtime.
"""
import math
from fractions import Fraction

from n070.core import need
from n070.metrics import coordinate_scores
from n070.protocol import PARTICIPANTS, ROIS, PRIMARY, REFERENCE_MODELS


class ArithmeticRangeError(ValueError):
    """A required finite result cannot be represented as nonzero binary64."""


FAMILIES = ("primary_dynamic_R2",) + tuple(
    "improvement_vs_fixed_" + model for model in REFERENCE_MODELS
)


def _rounded(exact):
    try:
        value = float(exact)
    except OverflowError as error:
        raise ArithmeticRangeError("Unrepresentable uncertainty arithmetic") from error
    if not math.isfinite(value) or (value == 0 and exact != 0):
        raise ArithmeticRangeError("Unrepresentable uncertainty arithmetic")
    return value


def _fractions(values):
    result = []
    for value in values:
        value = float(value)
        if not math.isfinite(value):
            raise ArithmeticRangeError("Nonfinite uncertainty input")
        result.append(Fraction(value))
    need(bool(result), "Nonempty uncertainty support")
    return result


def _mean(values):
    values = _fractions(values)
    return _rounded(sum(values, Fraction()) / len(values))


def _paired_mean(candidate, reference):
    """Mean coordinate-paired differences, with no overflowing partial sum."""
    candidate, reference = _fractions(candidate), _fractions(reference)
    need(len(candidate) == len(reference), "Identical paired coordinate support")
    return _rounded(sum((a - b for a, b in zip(candidate, reference)), Fraction())
                    / len(candidate))


def _linear_quantile(values, probability):
    """The usual linear sample quantile, evaluated as an exact convex sum.

    Rational probabilities preserve the declared 0.05/46 Bonferroni family.
    Exact interpolation avoids overflow in the intermediate right-left span.
    This is mathematical estimator parity, not low-bit NumPy parity.
    """
    values = sorted(float(value) for value in values)
    need(bool(values), "Nonempty uncertainty support")
    if not all(math.isfinite(value) for value in values):
        raise ArithmeticRangeError("Nonfinite uncertainty input")
    probability = Fraction(probability)
    need(0 <= probability <= 1, "Quantile probability lies in [0, 1]")
    position = (len(values) - 1) * probability
    left = position.numerator // position.denominator
    fraction = position - left
    if fraction == 0:
        return values[left]
    return _rounded((1 - fraction) * Fraction(values[left])
                    + fraction * Fraction(values[left + 1]))


def _score_draw(targets, predictions, references, selected_people, indices):
    """Score one shared crossed resample, retaining all ten people/46 ROIs."""
    need(len(selected_people) == len(PARTICIPANTS), "Ten participant selections")
    draw = {name: {} for name in FAMILIES}
    for roi in ROIS:
        participant_values = {name: [] for name in FAMILIES}
        for person_index in selected_people:
            person = PARTICIPANTS[int(person_index)]
            target = targets[person, roi][indices]
            candidate = coordinate_scores(target, predictions[person, roi, PRIMARY][indices])
            fixed = {
                model: coordinate_scores(target, references[person, roi, model][indices])
                for model in REFERENCE_MODELS
            }
            if candidate["status"] != "defined" or any(
                    result["status"] != "defined" for result in fixed.values()):
                return {"status": "undefined_coordinate_score", "values": None}
            try:
                participant_values["primary_dynamic_R2"].append(_mean(candidate["r2"]))
                for model in REFERENCE_MODELS:
                    participant_values["improvement_vs_fixed_" + model].append(
                        _paired_mean(candidate["r2"], fixed[model]["r2"]))
            except ArithmeticRangeError:
                return {"status": "undefined_arithmetic_range", "values": None}
        try:
            for name in FAMILIES:
                draw[name][roi] = _mean(participant_values[name])
        except ArithmeticRangeError:
            return {"status": "undefined_arithmetic_range", "values": None}
    return {"status": "defined", "values": draw}


def crossed_bootstrap(targets, predictions, references, video_order, groups, draws, seed):
    """Same shared participant/source-group bootstrap and complete denominator.

    The public entry retains the >=20000-draw floor. Unit controls may exercise
    _score_draw separately; a small control is never an accepted uncertainty run.
    """
    import numpy as np

    need(type(draws) is int and draws >= 20000 and type(seed) is int,
         "Precommitted finite uncertainty run")
    need(bool(video_order) and len(video_order) == len(set(video_order)),
         "Nonempty unique video order")
    group_names = sorted(set(groups[video] for video in video_order))
    group_indices = {
        group: [i for i, video in enumerate(video_order) if groups[video] == group]
        for group in group_names
    }
    rng = np.random.default_rng(seed)
    values = {name: {roi: [] for roi in ROIS} for name in FAMILIES}
    undefined = {}
    for _ in range(draws):
        selected_people = rng.integers(0, len(PARTICIPANTS), size=len(PARTICIPANTS))
        selected_groups = rng.integers(0, len(group_names), size=len(group_names))
        indices = [i for group in selected_groups
                   for i in group_indices[group_names[int(group)]]]
        draw = _score_draw(targets, predictions, references, selected_people, indices)
        if draw["status"] != "defined":
            undefined[draw["status"]] = undefined.get(draw["status"], 0) + 1
            continue
        for name in FAMILIES:
            need(set(draw["values"][name]) == set(ROIS), "Complete ROI resample")
            for roi in ROIS:
                values[name][roi].append(draw["values"][name][roi])
    # All requested draws are attempted; no failed draw is silently replaced.
    if undefined:
        return {"status": "unavailable_undefined_resample", "undefined_draws": sum(undefined.values()),
                "undefined_by_reason": undefined, "draws": draws, "seed": seed, "intervals": None}
    try:
        tail = Fraction(1, 1840)  # (0.05 / 46) / 2
        intervals = {
            name: {roi: [_linear_quantile(values[name][roi], tail),
                         _linear_quantile(values[name][roi], 1 - tail)] for roi in ROIS}
            for name in FAMILIES
        }
    except ArithmeticRangeError:
        return {"status": "unavailable_interval_arithmetic_range", "draws": draws,
                "seed": seed, "undefined_draws": 0, "intervals": None}
    return {
        "status": "descriptive_uncalibrated", "draws": draws, "seed": seed, "roi_family": 46,
        "intervals": intervals,
        "multiplicity": "two_sided_Bonferroni_46_ROIs_within_each_separately_labelled_metric_family",
        "joint_simultaneous_coverage_across_metric_families": False,
        "shared_indices_across_primary_comparisons_and_ROIs": True,
        "candidate_self_contrast_in_primary_or_uncertainty": False,
        "refitting": False, "conditioning": "fixed fitted predictions and released joint measurement",
        "finite_10_person_calibration": "required before inferential claims",
        "arithmetic": "exact_finite_means_and_linear_quantiles_rounded_once_to_binary64",
    }
