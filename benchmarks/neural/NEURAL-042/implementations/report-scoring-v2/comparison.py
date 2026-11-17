"""Complete report reconstruction, using the frozen programme report contract.

This pure calculation module performs no target acquisition or scientific run.
The protected owner must retain producer admission and target-last access before
calling it. Put the pinned predecessor's program directory on the import path.
"""
import math

from contracts import CONTRASTS, DESIGNS, METRICS, report
from core import need


METRIC_UNITS = {
    "corrected_mi": "dimensionless",
    "mi": "dimensionless",
    "trial_null": "dimensionless",
    "shift_null": "dimensionless",
    "early_mi": "dimensionless",
    "late_mi": "dimensionless",
    "theta_power": "volts_squared",
    "gamma_power": "volts_squared",
    "firing_rate": "hertz",
    "harmonic_plv": "dimensionless",
    "waveform_asymmetry": "dimensionless",
}


def _admit_pair(candidate, target):
    """Validate both complete ordered reports before any zip-based comparison."""
    need(type(target) is dict and type(target.get("patients")) is list
         and len(target["patients"]) == 144, "complete target patient rows")
    roster = []
    for row in target["patients"][::4]:
        need(type(row) is dict and "patient" in row, "target patient identity")
        roster.append(row["patient"])
    report(target, roster)
    report(candidate, roster)


def _error(value, target):
    error = abs(value - target)
    need(math.isfinite(error), "finite reconstruction error")
    return error


def _close(value, target):
    return _error(value, target) <= 1e-10 + 1e-6 * abs(target)


def _mean(values):
    # Scaling before summation avoids overflowing finite large power/rate MAEs.
    return math.fsum(value / len(values) for value in values)


def _group(candidate, target, endpoint):
    matched = endpoint["status"] != "support_mismatch"
    n = target["n_patients"]
    errors = {"mean": None, "ci95": None, "sign_flip_p": None}
    if not matched:
        status, agreement = "support_mismatch", False
    elif n < 2:
        # Both report contracts require all group statistics null at n < 2.
        status, agreement = "insufficient_group_support", True
    else:
        status = "matched_support"
        errors = {
            "mean": _error(candidate["mean"], target["mean"]),
            "ci95": [_error(a, b) for a, b in zip(candidate["ci95"], target["ci95"])],
            "sign_flip_p": _error(candidate["sign_flip_p"], target["sign_flip_p"]),
        }
        agreement = all(value <= 1e-10 for value in
                        (errors["mean"], *errors["ci95"], errors["sign_flip_p"]))
    return {
        "design": target["design"],
        "contrast": target["contrast"],
        "status": status,
        "target_supported_people": n,
        "absolute_error": errors,
        "within_tolerance": agreement,
    }


def compare(candidate, target):
    """Keep the primary MAE; expose all four group reconstruction discrepancies.

    Full numerical agreement includes every supported patient metric and group
    statistic. It is independent of the primary scalar: wrong group summaries
    cannot be hidden behind a perfect patient score, and do not redefine it.
    """
    _admit_pair(candidate, target)
    endpoints = {}
    patient_agreement = True
    for design in DESIGNS:
        for contrast in CONTRASTS:
            pairs = [(a, b) for a, b in zip(candidate["patients"], target["patients"])
                     if a["design"] == design and a["contrast"] == contrast]
            mismatches = []
            errors = {metric: [] for metric in METRICS}
            for a, b in pairs:
                same_support = ((a["metrics"] is None) == (b["metrics"] is None)
                                and (a["n_channels"], a["n_sessions"])
                                == (b["n_channels"], b["n_sessions"]))
                if not same_support:
                    mismatches.append(a["patient"])
                    patient_agreement = False
                if a["metrics"] is not None and b["metrics"] is not None:
                    for metric in METRICS:
                        errors[metric].append(_error(a["metrics"][metric], b["metrics"][metric]))
                        patient_agreement &= _close(a["metrics"][metric], b["metrics"][metric])
            supported = sum(b["metrics"] is not None for _, b in pairs)
            ok = not mismatches and supported > 0
            status = ("support_mismatch" if mismatches else
                      "matched_support" if supported else "no_target_support")
            endpoints[design + "/" + contrast] = {
                "status": status,
                "target_supported_people": supported,
                "mismatched_people": mismatches,
                "mae": {metric: _mean(values) if ok and len(values) == supported else None
                        for metric, values in errors.items()},
            }
    groups = [_group(a, b, endpoints[b["design"] + "/" + b["contrast"]])
              for a, b in zip(candidate["groups"], target["groups"])]
    primary = [endpoints["nuisance_matched/" + contrast]["mae"]["corrected_mi"]
               for contrast in CONTRASTS]
    return {
        "endpoints": endpoints,
        "primary_equal_endpoint_mae": _mean(primary) if all(v is not None for v in primary) else None,
        "neural_gain_scalar": None,
        "groups": groups,
        "full_numerical_agreement": patient_agreement and all(g["within_tolerance"] for g in groups),
        "metric_units": dict(METRIC_UNITS),
        "group_error_units": {"mean": "corrected_mi", "ci95": "corrected_mi",
                              "sign_flip_p": "probability"},
    }


def reference_agreement(first, second):
    """Fail closed on complete support, all eleven metrics and group summaries."""
    result = compare(first, second)
    need(result["full_numerical_agreement"], "independent full report agreement")
    return True
