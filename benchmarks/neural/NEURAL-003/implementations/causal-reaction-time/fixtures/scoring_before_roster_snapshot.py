"""Protected participant-macro MAE; never invoked in BUILD ONLY."""
import math
from .prediction_schema import admit_predictions, ARMS, _admit_rt_seconds


class InvalidTargetRT(ValueError):
    """Operator target fault after candidate admission; no candidate score."""


def _finite_mean(values):
    """Average admitted finite floats without overflowing an intermediate sum.

    Keep the original arithmetic whenever it succeeds. On sum overflow,
    accumulate exact binary ratios with integer arithmetic; their mean stays
    within the finite input range, including for signed, cancelling gains.
    """
    values = tuple(values)
    try:
        return math.fsum(values) / len(values)
    except OverflowError:
        total, denominator = 0, 1
        for value in values:
            numerator, divisor = value.as_integer_ratio()
            if divisor > denominator:
                total *= divisor // denominator
                denominator = divisor
            total += numerator * (denominator // divisor)
        return total / (denominator * len(values))


def grade(outputs, expected, sealed_targets):
    """sealed_targets() is called only after full public output admission.

    The actual protected target store and isolated producer are unresolved.
    This arithmetic implementation does not manufacture either authority.
    """
    predictions = admit_predictions(outputs, expected)
    target_rows = sealed_targets()
    if (type(target_rows) is not dict or any(type(k) is not int for k in target_rows)
            or set(target_rows) != set(range(26))):
        raise ValueError("complete private26-person target roster")
    targets = {}
    for person in range(26):
        ids = tuple(expected[(person, "eeg")])
        rows = target_rows[person]
        if type(rows) is not list or len(rows) != len(ids):
            raise ValueError("complete finite observed first-response targets required")
        vals = []
        for ident, row in zip(ids, rows):
            if type(row) is not dict or set(row) != {"trial_id", "rt_seconds"}:
                raise ValueError("private target fields")
            if row["trial_id"] != ident:
                raise ValueError("private target join")
            try:
                vals.append(_admit_rt_seconds(row["rt_seconds"]))
            except ValueError as error:
                raise InvalidTargetRT(
                    f"invalid private target RT; operator target fault: {error}; "
                    "never impute3s") from error
        targets[person] = tuple(vals)
    per_person = []
    for person in range(26):
        actual = targets[person]
        losses = {arm: _finite_mean(abs(v - t) for v, t in
                  zip(predictions[(person, arm)], actual))
                  for arm in ARMS}
        if any(not math.isfinite(v) for v in losses.values()):
            raise ValueError("nonfinite loss")
        per_person.append({"person": person, "trials": len(actual), **losses,
                           "gain": losses["contrast_instruction"] - losses["eeg"]})
    macro = {arm: _finite_mean(r[arm] for r in per_person) for arm in ARMS}
    gains = tuple(r["gain"] for r in per_person)
    return {"schema": "neural003_observed_at_risk_mae_v1",
            "people": 26, "per_person": per_person, "macro_mae_seconds": macro,
            "paired_gain_seconds": _finite_mean(gains),
            "paired_person_gains": gains,
            "uncertainty": "Paired person values; overlapping LOPO training makes naive trial or person independence claims inappropriate.",
            "constant_outputs_valid": True,
            "positive_eeg_gain_required": False,
            "qualification": False}
