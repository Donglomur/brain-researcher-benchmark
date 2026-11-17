"""Exact paired MAE differences of submitted binary64 values for NEURAL-095.

This replaces only paired.py's arithmetic interface. Public identity alignment,
all four captures and the trusted target loader remain the scorer's job.
No dataset, candidate, reference fit, significance threshold or metric changes.
"""
from fractions import Fraction
import math
import operator


def need(ok, message):
    if not ok:
        raise ValueError(message)


def _mean(values):
    values = list(values)
    need(bool(values), "Every prespecified group must have support")
    try:
        result = float(sum(values, Fraction()) / len(values))
    except OverflowError as exc:
        raise ValueError("Unrepresentable paired mean; no clipping") from exc
    need(math.isfinite(result), "Finite paired mean; no clipping")
    return result


def _groups(values, size):
    result = []
    for value in values:
        need(not isinstance(value, bool), "Integer group IDs, not booleans")
        try:
            value = operator.index(value)
        except TypeError as exc:
            raise ValueError("Integer group IDs required") from exc
        need(0 <= value < size, "Prespecified group range required")
        result.append(value)
    need(set(result) == set(range(size)), "All prespecified groups required")
    return result


def pair_difference(cue, neural, truth, conditions, contexts):
    """Evaluate mean(|cue-y|-|neural-y|) with one final binary64 rounding.

Subtracting two rounded absolute errors can erase an actual representable
paired difference. Fractions represent the *input floats* exactly; they do not
add precision to the observations or alter the prediction values. Exact sums
also avoid dividing a subnormal increment to zero before aggregation.
"""
    cue, neural, truth = ([float(x) for x in values] for values in (cue, neural, truth))
    condition, context = _groups(conditions, 40), _groups(contexts, 8)
    need(len(cue) == len(neural) == len(truth) == len(condition) == len(context) == 258,
         "Original complete 258-case paired panel required")
    need(all(math.isfinite(x) for values in (cue, neural, truth) for x in values)
         and all(y > 0 for y in truth), "Finite predictions and positive released targets required")
    need(all(k // 5 == g for k, g in zip(condition, context)), "Condition/context agreement required")
    # Preserve the scorer's refusal of unrepresentable individual residuals.
    need(all(math.isfinite(a - y) and math.isfinite(b - y)
             for a, b, y in zip(cue, neural, truth)), "Prediction subtraction overflow; no clipping")
    rows = []
    for a, b, y in zip(cue, neural, truth):
        a, b, y = map(Fraction.from_float, (a, b, y))
        rows.append(abs(a - y) - abs(b - y))
    grouped = {}
    exact_context_means = []
    for name, assignments, size in (("by_condition", condition, 40), ("by_context", context, 8)):
        grouped[name] = {}
        for key in range(size):
            terms = [value for value, group in zip(rows, assignments) if group == key]
            grouped[name][str(key)] = {"n": len(terms), "cue_minus_neural_mae_ms": _mean(terms)}
            if name == "by_context":
                exact_context_means.append(sum(terms, Fraction()) / len(terms))
    return {
        "cue_minus_neural_mae_ms": _mean(rows),
        **grouped,
        "cue_minus_neural_eight_context_macro_mae_ms": _mean(exact_context_means),
        "sign": "positive means neural arm lower absolute error on this finite panel",
        "scientific_pass_floor": None,
        "matched_method_proven": False,
        "RL_or_neural_understanding_reward": False,
        "paired_loss_arithmetic": "exact rational evaluation of input binary64 values; final mean rounded once",
    }


def verify_paired_arithmetic(paired, cue_score, neural_score):
    """Preserve the predecessor's 64-ULP check against rounded arm metrics.

The paired mean is the reported increment. The envelope only checks arithmetic
consistency and is not a scientific threshold or an interval of uncertainty.
"""
    checks = []
    def compare(name, paired_value, cue_value, neural_value):
        direct = cue_value - neural_value
        need(all(math.isfinite(v) for v in (paired_value, cue_value, neural_value, direct)),
             "Finite derived arithmetic before consistency check")
        bound = 1e-10 + 64 * max(math.ulp(v) for v in (paired_value, cue_value, neural_value, direct))
        need(abs(paired_value - direct) <= bound, "Independent paired arithmetic outside roundoff envelope")
        checks.append({"metric": name, "aggregate_subtraction_ms": direct,
                       "absolute_difference_ms": abs(paired_value - direct), "roundoff_bound_ms": bound})
    compare("mae_ms", paired["cue_minus_neural_mae_ms"], cue_score["mae_ms"], neural_score["mae_ms"])
    for group in ("by_condition", "by_context"):
        for key, row in paired[group].items():
            cue, neural = cue_score[group][key], neural_score[group][key]
            need(row["n"] == cue["n"] == neural["n"], "Same group support for paired arithmetic")
            compare(group + "/" + key, row["cue_minus_neural_mae_ms"], cue["mae_ms"], neural["mae_ms"])
    compare("eight_context_macro_mae_ms", paired["cue_minus_neural_eight_context_macro_mae_ms"],
            cue_score["eight_context_macro_mae_ms"], neural_score["eight_context_macro_mae_ms"])
    return checks
