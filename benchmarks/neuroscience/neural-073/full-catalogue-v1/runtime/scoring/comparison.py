"""Paired, person-cluster comparisons: repetitions never increase biological n."""
from fractions import Fraction
import math
import random
from .core import QualificationError, PERSONS, fraction_json


def _rational(obj):
    try:
        n, d = obj["numerator"], obj["denominator"]
        if type(n) is not int or type(d) is not int or d <= 0:
            raise ValueError
        return Fraction(n, d)
    except (TypeError, KeyError, ValueError, ZeroDivisionError):
        raise QualificationError("invalid exact score fraction") from None


def _quantile(sorted_values, p):
    pos = (len(sorted_values) - 1) * p
    lower = int(math.floor(pos))
    upper = int(math.ceil(pos))
    return sorted_values[lower] + (pos - lower) * (sorted_values[upper] - sorted_values[lower])


def person_uncertainty(person_differences, *, production=True):
    """10,000 fixed-seed cluster draws; 2.5/97.5% linear percentiles.

    Input values must already average the three paired repetitions per person.
    Seed73001 is restarted for each contrast: matched draws across contrasts.
    The result is conditional descriptive support, not a population-validity claim.
    """
    if production and set(person_differences) != set(PERSONS):
        raise QualificationError("all 13 persons required for production uncertainty")
    people = sorted(person_differences)
    if len(people) < 2:
        raise QualificationError("at least two persons required")
    values = [float(person_differences[p]) for p in people]
    if any(not math.isfinite(v) for v in values):
        raise QualificationError("nonfinite person difference")
    mean = math.fsum(values) / len(values)
    rng = random.Random(73001)
    draws = sorted(math.fsum(values[rng.randrange(len(values))] for _ in values) / len(values)
                   for _ in range(10000))
    leave_one = {p: math.fsum(v for j, v in enumerate(values) if j != i) / (len(values) - 1)
                 for i, p in enumerate(people)}
    return {"mean": mean, "biological_persons": len(people), "bootstrap_resamples": 10000,
            "bootstrap_seed": 73001, "interval_probability": 0.95,
            "percentile_interval": [_quantile(draws, 0.025), _quantile(draws, 0.975)],
            "percentile_rule": "linear interpolation at (10000-1)*p",
            "person_difference_range": [min(values), max(values)],
            "leave_one_person_out_mean": leave_one,
            "leave_one_person_out_range": [min(leave_one.values()), max(leave_one.values())],
            "interpretation": "conditional catalogue/person-support descriptive uncertainty"}


def aggregate_repetitions(panels, *, production=True):
    """Three complete panels, equal repetition means; no chosen-best retry.

    Panel rows are outputs of score_panel. Equality of cell membership and labels
    is certified by the private record registry in the parent; here require exact
    case-ID and person rosters, with no missing panel. Person-mean averaging equals
    averaging per-record losses before the same fixed hierarchy by linearity.
    """
    if len(panels) != 3:
        raise QualificationError("exactly three repetitions required")
    ids = set(panels[0]["rows"])
    people = set(panels[0]["people"])
    if any(p.get("records_digest") != panels[0].get("records_digest") for p in panels):
        raise QualificationError("repetition private record bindings differ")
    if production and any(p.get("mode") != "production-authorized" or
        not p.get("authority_digest") or p.get("closure_digest") != panels[0].get("closure_digest") for p in panels):
        raise QualificationError("production comparisons require authorized closed panels")
    if production and people != set(PERSONS):
        raise QualificationError("production repetitions require all 13 persons")
    if any(set(p["rows"]) != ids or set(p["people"]) != people for p in panels):
        raise QualificationError("repetition panels have different support")
    averages = {}
    for person in sorted(people):
        acc = sum((_rational(p["people"][person]["accuracy_exact"]) for p in panels), Fraction()) / 3
        averages[person] = {"accuracy": float(acc), "accuracy_exact": fraction_json(acc),
            "brier_with_failure_penalty": math.fsum(p["people"][person]["brier_with_failure_penalty"] for p in panels) / 3}
    rows = {case: {"accuracy": math.fsum(p["rows"][case]["accuracy"] for p in panels) / 3,
                  "brier_with_failure_penalty": math.fsum(p["rows"][case]["brier_with_failure_penalty"] for p in panels) / 3,
                  "valid_repetitions": sum(p["rows"][case]["valid"] for p in panels)} for case in sorted(ids)}
    accuracy = sum((_rational(p["accuracy_exact"]) for p in panels), Fraction()) / 3
    return {"repetitions": 3, "people": averages, "rows": rows,
            "records_digest": panels[0].get("records_digest"), "closure_digest": panels[0].get("closure_digest"),
            "accuracy": float(accuracy), "accuracy_exact": fraction_json(accuracy),
            "brier_with_failure_penalty": math.fsum(p["brier_with_failure_penalty"] for p in panels) / 3,
            "weighted_coverage": math.fsum(p["weighted_coverage"] for p in panels) / 3,
            "unweighted_coverage": math.fsum(p["unweighted_coverage"] for p in panels) / 3,
            "selection": "all_three_equal_weight_no_best_repetition"}


def paired_comparison(frozen_panels, interactive_panels, *, production=True):
    frozen = aggregate_repetitions(frozen_panels, production=production)
    interactive = aggregate_repetitions(interactive_panels, production=production)
    if (set(frozen["rows"]) != set(interactive["rows"]) or set(frozen["people"]) != set(interactive["people"])
            or frozen["records_digest"] != interactive["records_digest"]
            or (production and frozen["closure_digest"] != interactive["closure_digest"])):
        raise QualificationError("paired arms have different support")
    accuracy, brier_diff, repetitions = {}, {}, []
    for person in sorted(frozen["people"]):
        accuracy[person] = float(_rational(interactive["people"][person]["accuracy_exact"]) - _rational(frozen["people"][person]["accuracy_exact"]))
        brier_diff[person] = frozen["people"][person]["brier_with_failure_penalty"] - interactive["people"][person]["brier_with_failure_penalty"]
    for fp, ip in zip(frozen_panels, interactive_panels):
        repetitions.append({"accuracy_I_minus_F": float(_rational(ip["accuracy_exact"]) - _rational(fp["accuracy_exact"])),
            "brier_F_minus_I": fp["brier_with_failure_penalty"] - ip["brier_with_failure_penalty"],
            "people": {p: {"accuracy_I_minus_F": float(_rational(ip["people"][p]["accuracy_exact"]) - _rational(fp["people"][p]["accuracy_exact"])),
                "brier_F_minus_I": fp["people"][p]["brier_with_failure_penalty"] - ip["people"][p]["brier_with_failure_penalty"]}
                for p in sorted(accuracy)}})
    return {"positive_favors": "interactive", "paired_repetitions": repetitions,
            "accuracy_I_minus_F_by_person": accuracy, "brier_F_minus_I_by_person": brier_diff,
            "accuracy_uncertainty": person_uncertainty(accuracy, production=production),
            "brier_uncertainty": person_uncertainty(brier_diff, production=production),
            "n_biological": len(accuracy), "candidate_repetitions": 3}


def compare_reference(candidate_panels, reference_panel, *, production=True):
    """Candidate minus preselected reference; immutable reference is reused, not rerun."""
    paired = paired_comparison([reference_panel] * 3, candidate_panels, production=production)
    return {"positive_favors": "candidate", "reference_evaluations": 1,
            "candidate_repetitions": 3, "n_biological": paired["n_biological"],
            "accuracy_candidate_minus_reference_by_person": paired["accuracy_I_minus_F_by_person"],
            "brier_reference_minus_candidate_by_person": paired["brier_F_minus_I_by_person"],
            "accuracy_uncertainty": paired["accuracy_uncertainty"], "brier_uncertainty": paired["brier_uncertainty"],
            "per_repetition": [{"accuracy_candidate_minus_reference": p["accuracy_I_minus_F"],
                "brier_reference_minus_candidate": p["brier_F_minus_I"]} for p in paired["paired_repetitions"]],
            "reference_selection_requirement": "training-selected existing model; never outer-best"}
