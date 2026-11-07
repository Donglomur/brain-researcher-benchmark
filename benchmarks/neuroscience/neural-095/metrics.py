"""Scalar arithmetic for an arbitrary DMFC prediction, with no model execution.

Metric definitions and five reference names are pinned to preset-pilot-v1/core.py.
This implementation independently uses math.fsum rather than importing that core.
"""
from __future__ import annotations

import math
import numpy as np

METHODS = ("nominal_sample_interval", "exact_condition_training_median",
           "cue_clock_ridge", "cue_clock_total_spike_ridge", "cue_clock_temporal_spike_ridge")
TOP_METRICS = ("mae_ms", "rmse_ms", "eight_context_macro_mae_ms")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def _finite(value, description, nonnegative=False):
    require(type(value) in (int, float) and math.isfinite(value)
            and (not nonnegative or value >= 0), "Finite " + description + " required")
    return float(value)


def _sum(values):
    try:
        out = math.fsum(values)
    except (OverflowError, ValueError) as exc:
        raise ValueError("Metric arithmetic overflow; no clipping or omitted cases") from exc
    require(math.isfinite(out), "Finite metric sum required; no clipping")
    return out


def _close(a, b):
    return abs(a - b) <= 1e-10 + 1e-10 * abs(b)


def _mean_nonnegative(values, weights=None):
    """Scale before summing so representable means need no overflowing total."""
    values = list(values)
    require(bool(values) and all(math.isfinite(v) and v >= 0 for v in values),
            "Finite nonnegative metric terms required")
    maximum = max(values)
    if maximum == 0:
        return 0.0
    if weights is None:
        normalized = _sum(v / maximum for v in values) / len(values)
    else:
        weights = list(weights)
        require(len(weights) == len(values) and all(type(w) is int and w > 0 for w in weights),
                "Positive metric weights required")
        normalized = _sum((v / maximum) * w for v, w in zip(values, weights, strict=True)) / sum(weights)
    result = maximum * normalized
    require(math.isfinite(result), "Unrepresentable mean; no clipping")
    return result


def _predictions(ordered):
    p = np.asarray(ordered)
    require(p.ndim == 1 and 40 <= len(p) <= 512 and p.dtype.kind == "f"
            and p.dtype.itemsize in (4, 8) and np.isfinite(p).all(),
            "Complete finite prediction vector required before private loading")
    return [float(x) for x in p]


def _references(reference_scores, n):
    require(isinstance(reference_scores, dict) and isinstance(reference_scores.get("scores"), dict)
            and set(reference_scores["scores"]) == set(METHODS), "Exactly five saved reference scores required")
    reports = {}
    support = None
    for arm in METHODS:
        saved = reference_scores["scores"][arm]
        require(isinstance(saved, dict) and type(saved.get("n")) is int and saved["n"] == n,
                "Saved reference must use the complete candidate panel")
        row = {"n": n, **{key: _finite(saved.get(key), "reference " + key, True) for key in TOP_METRICS}}
        for group, size in (("by_condition", 40), ("by_context", 8)):
            values = saved.get(group)
            require(isinstance(values, dict) and set(values) == {str(k) for k in range(size)},
                    "All prespecified reference groups required; no missing-group dropping")
            row[group] = {}
            for k in range(size):
                v = values[str(k)]
                require(isinstance(v, dict) and type(v.get("n")) is int and 1 <= v["n"] <= n,
                        "Positive complete reference group count required")
                row[group][str(k)] = {"n": v["n"], "mae_ms": _finite(v.get("mae_ms"), "group MAE", True)}
            require(sum(v["n"] for v in row[group].values()) == n, "Reference group counts must cover panel")
            weighted = _mean_nonnegative((v["mae_ms"] for v in row[group].values()),
                                         (v["n"] for v in row[group].values()))
            require(_close(row["mae_ms"], weighted), "Reference group and pooled MAE inconsistent")
        for k in range(8):
            require(row["by_context"][str(k)]["n"] == sum(row["by_condition"][str(j)]["n"] for j in range(k * 5, k * 5 + 5)),
                    "Reference condition/context support inconsistent")
        macro = _mean_nonnegative(v["mae_ms"] for v in row["by_context"].values())
        require(_close(row["eight_context_macro_mae_ms"], macro), "Reference context-macro MAE inconsistent")
        current = {group: [v["n"] for v in row[group].values()] for group in ("by_condition", "by_context")}
        require(support is None or current == support, "Reference arms use different group support")
        support = current
        reports[arm] = row
    return reports, support


def _private(value, n, support):
    require(isinstance(value, dict) and set(value) == {"case_id", "tp_ms", "condition", "context"},
            "Exact private schema required")
    arrays = {k: np.asarray(v) for k, v in value.items()}
    require(all(v.shape == (n,) for v in arrays.values()), "Private parallel complete panel required")
    ids = arrays["case_id"]
    require(ids.dtype.kind == "U" and len(set(ids.tolist())) == n
            and all(len(x) == 11 and x.startswith("dmfc-") and all(c in "0123456789" for c in x[5:]) for x in ids.tolist()),
            "Unique canonical private identities required")
    y, condition, context = (arrays[k] for k in ("tp_ms", "condition", "context"))
    require(y.dtype.kind == "f" and y.dtype.itemsize in (4, 8)
            and np.isfinite(y).all() and np.all(y > 0), "Finite positive released targets required; no filtering")
    require(condition.dtype.kind in "iu" and context.dtype.kind in "iu"
            and set(condition.tolist()) == set(range(40)) and set(context.tolist()) == set(range(8))
            and np.array_equal(context, condition // 5), "All 40 conditions and eight contexts required")
    groups = {"by_condition": [int(x) for x in condition], "by_context": [int(x) for x in context]}
    for group, size in (("by_condition", 40), ("by_context", 8)):
        require([groups[group].count(k) for k in range(size)] == support[group],
                "Private group support differs from frozen references")
    return [float(x) for x in y], groups


def _candidate(p, y, groups):
    errors = [a - b for a, b in zip(p, y, strict=True)]
    require(all(math.isfinite(e) for e in errors), "Prediction subtraction overflow; no clipping")
    absolute = [abs(e) for e in errors]
    maximum = max(absolute)
    rms = 0.0 if maximum == 0 else maximum * math.sqrt(_mean_nonnegative((e / maximum) ** 2 for e in absolute))
    require(math.isfinite(rms), "Unrepresentable RMSE; no clipping")
    result = {"n": len(y), "mae_ms": _mean_nonnegative(absolute), "rmse_ms": rms}
    for group, size in (("by_condition", 40), ("by_context", 8)):
        result[group] = {}
        for k in range(size):
            values = [e for e, g in zip(absolute, groups[group], strict=True) if g == k]
            require(bool(values), "Missing prespecified group; entire score undefined")
            result[group][str(k)] = {"n": len(values), "mae_ms": _mean_nonnegative(values)}
    result["eight_context_macro_mae_ms"] = _mean_nonnegative(v["mae_ms"] for v in result["by_context"].values())
    return result


def score_candidate(ordered, private_loader, reference_scores):
    """Score after public validation, invoking the trusted private loader once.

The caller must first validate the candidate and bind its ordered vector to the
verified public identity list. private_loader() must verify the private file's
hash and exact identity order before returning case_id/tp_ms/condition/context.
Use validator.validate_and_score for a combined file-validation entry point.
reference_scores is the pinned preset grade object containing `scores`.
"""
    p = _predictions(ordered)
    references, support = _references(reference_scores, len(p))
    require(callable(private_loader), "Trusted private loader required")
    y, groups = _private(private_loader(), len(p), support)
    candidate = _candidate(p, y, groups)
    differences = {}
    for arm, reference in references.items():
        row = {key: candidate[key] - reference[key] for key in TOP_METRICS}
        for group in ("by_condition", "by_context"):
            row[group] = {key: {"n": value["n"], "mae_ms": value["mae_ms"] - reference[group][key]["mae_ms"]}
                          for key, value in candidate[group].items()}
        differences[arm] = row
    return {"status": "scored", "candidate": candidate, "reference_values": references,
            "candidate_minus_reference": differences, "primary_metric": "mae_ms",
            "secondary_metrics": ["rmse_ms", "eight_context_macro_mae_ms", "by_condition", "by_context"],
            "difference_sign": "candidate error minus reference error; negative is better",
            "prediction_units": "milliseconds", "prediction_values_modified": False,
            "private_loader_invocations": 1, "public_validation_before_private_decode": True,
            "scientific_pass_floor": None, "comparison_defined": True,
            "scope": "One exposed development animal/session; no population CI or p-value"}
