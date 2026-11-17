#!/usr/bin/env python3
"""Source-paper Eqs. 2, 3 and 6 on supplied, already fitted held-out operands.

This module does not fit models, assign folds, select neurons or certify Figure 2.
All likelihoods are natural-log densities in the original activity coordinate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

GRID_SIZE = 200
EPOCHS = ("sample", "delay", "test", "turn", "reward")
IDENTITY_FIELDS = ("animal_id", "session_id", "neuron_id", "projection", "epoch")
MAX_INPUT_BYTES = 64 * 1024 * 1024


class Invalid(ValueError):
    """An operand is missing, nonfinite, ambiguous or outside its domain."""


def require(condition, message):
    if not condition:
        raise Invalid(message)


def finite(value, name):
    require(type(value) in (int, float), name + " must be a real number")
    try:
        valid = math.isfinite(value)
    except OverflowError:
        valid = False
    require(valid, name + " must be finite; no clipping or row omission is applied")
    return float(value)


def token(value, name):
    require(type(value) is str and 0 < len(value) <= 256, name + " must be a nonempty string")
    return value


def source_grid(bounds):
    """Inclusive source activity coordinates; Eq. 2 uses range/200, not /199."""
    require(type(bounds) is list and len(bounds) == 2, "activity_bounds must contain min and max")
    low, high = (finite(v, "activity bound") for v in bounds)
    require(0 <= low < high, "nonnegative, nondegenerate deconvolved-activity bounds required")
    width = finite(high - low, "activity range")
    delta = width / GRID_SIZE
    require(delta > 0, "activity integration step underflow")
    return [low + width * (i / (GRID_SIZE - 1)) for i in range(GRID_SIZE)], delta


def npvc_point(bounds, log_joint_grid, log_joint_observed, log_marginal_observed):
    """Normalize the SAME fitted joint density by the paper's 200-point sum.

    The observed joint density is supplied separately: the paper does not define
    a new interpolation rule here. The null is the predictor-free marginal,
    not a Poisson mean and not a trial-type-conditioned marginal.
    """
    grid, delta = source_grid(bounds)
    require(type(log_joint_grid) is list and len(log_joint_grid) == GRID_SIZE,
            "NPvC requires exactly 200 activity-grid log joint densities")
    values = [finite(v, "log joint grid density") for v in log_joint_grid]
    observed = finite(log_joint_observed, "log joint observed density")
    null = finite(log_marginal_observed, "log marginal observed density")
    peak = max(values)
    # Subtract the peak before summing: neither exp(-10000) nor exp(10000)
    # should cause a valid conditional density to disappear or overflow.
    relative_normalizer = math.log(math.fsum(math.exp(v - peak) for v in values)) + math.log(delta)
    model = finite((observed - peak) - relative_normalizer, "conditional log density")
    saturated = finite(-relative_normalizer, "peak conditional log density")
    modes = [i for i, v in enumerate(values) if v == peak]
    return {"model": model, "null": null, "saturated": saturated,
            "mode_activity": grid[modes[0]], "mode_grid_index": modes[0],
            "mode_tie_count": len(modes), "integration_delta": delta}


def poisson_log_likelihood(activity, mean):
    """Poisson log-likelihood extension for nonnegative deconvolved activity.

    lgamma(y+1) permits the source's noninteger magnitudes without rounding.
    Its value cancels in every likelihood difference used by Eq. 6.
    """
    y = finite(activity, "activity")
    mu = finite(mean, "Poisson mean")
    require(y >= 0 and mu >= 0, "activity and Poisson mean must be nonnegative")
    if mu == 0:
        require(y == 0, "zero Poisson likelihood for positive activity; no pseudocount is applied")
        return 0.0
    return finite((y * math.log(mu) if y else 0.0) - mu - math.lgamma(y + 1), "Poisson log likelihood")


def glm_point(activity, mean, null_mean):
    """The model, predictor-free fitted mean, and y-as-mean saturated GLM."""
    return {"model": poisson_log_likelihood(activity, mean),
            "null": poisson_log_likelihood(activity, null_mean),
            "saturated": poisson_log_likelihood(activity, activity)}


def fraction_deviance_explained(points):
    """Sum observation log-likelihood differences BEFORE division (Eq. 6).

    The foldwise fractions are never averaged. Negative values and values above
    one are retained. A zero denominator is reported, never dropped or clamped.
    """
    require(bool(points), "at least one observation is required")
    values = [{k: finite(p[k], k) for k in ("model", "null", "saturated")} for p in points]
    try:
        totals = {k: math.fsum(p[k] for p in values) for k in values[0]}
        numerator = math.fsum(p["model"] - p["null"] for p in values)
        denominator = math.fsum(p["saturated"] - p["null"] for p in values)
    except (OverflowError, ValueError) as exc:
        raise Invalid("log-likelihood aggregation overflow") from exc
    for k, v in {**totals, "numerator": numerator, "denominator": denominator}.items():
        finite(v, k)
    ratio = None if denominator == 0 else finite(numerator / denominator, "FDE")
    return {"observations": len(values), "log_likelihood_totals": totals,
            "numerator": numerator, "denominator": denominator, "fde": ratio,
            "denominator_state": "zero" if denominator == 0 else "positive" if denominator > 0 else "negative"}


def score(document):
    require(type(document) is dict and document.get("schema") == "npvc-fde-operands-v1", "wrong input schema")
    units = document.get("units")
    require(type(units) is list and bool(units), "nonempty units are required")
    seen_units, results, session_animals, cell_metadata = set(), [], {}, {}
    for unit in units:
        require(type(unit) is dict, "unit must be an object")
        identity = unit.get("identity")
        require(type(identity) is dict and set(identity) == set(IDENTITY_FIELDS), "complete unit identity required")
        key = tuple(token(identity[k], k) for k in IDENTITY_FIELDS)
        require(identity["epoch"] in EPOCHS, "unknown source epoch")
        require(key not in seen_units, "duplicate unit identity")
        seen_units.add(key)
        bounds = unit.get("activity_bounds")
        source_grid(bounds)
        session = identity["session_id"]
        require(session_animals.setdefault(session, identity["animal_id"]) == identity["animal_id"],
                "one session_id cannot identify multiple animals")
        cell = (session, identity["neuron_id"])
        metadata = (identity["projection"], tuple(bounds))
        require(cell_metadata.setdefault(cell, metadata) == metadata,
                "neuron projection or session activity bounds changed across epochs")
        rows = unit.get("observations")
        require(type(rows) is list and bool(rows), "nonempty observations required")
        seen_rows, npvc, glm, modes, by_fold, trial_types = set(), [], [], [], {}, {}
        for row in rows:
            require(type(row) is dict, "observation must be an object")
            trial = token(row.get("trial_id"), "trial_id")
            frame = token(row.get("frame_id"), "frame_id")
            require((trial, frame) not in seen_rows, "duplicate trial/frame within a neuron epoch")
            seen_rows.add((trial, frame))
            fold = row.get("fold_id")
            require(type(fold) is int and 1 <= fold <= 5, "fold_id must be an integer from 1 to 5")
            trial_type = row.get("trial_type")
            require(type(trial_type) is int and 1 <= trial_type <= 8, "trial_type must be an integer from 1 to 8")
            require(trial_types.setdefault(trial, trial_type) == trial_type, "trial type changed within trial")
            activity = finite(row.get("activity"), "activity")
            require(bounds[0] <= activity <= bounds[1], "activity lies outside session bounds")
            n, g = row.get("npvc"), row.get("glm")
            require(type(n) is dict and type(g) is dict, "separate NPvC and GLM operands required")
            try:
                a = npvc_point(bounds, n["log_joint_grid"], n["log_joint_observed"], n["log_marginal_observed"])
                b = glm_point(activity, g["mean"], g["null_mean"])
            except KeyError as exc:
                raise Invalid("missing model operand: " + str(exc)) from exc
            npvc.append(a); glm.append(b)
            by_fold.setdefault(fold, {"npvc": [], "glm": []})
            by_fold[fold]["npvc"].append(a); by_fold[fold]["glm"].append(b)
            modes.append({"trial_id": trial, "frame_id": frame, "fold_id": fold,
                          "trial_type": trial_type, **{k: a[k] for k in ("mode_activity", "mode_grid_index", "mode_tie_count")}})
        results.append({"identity": identity, "activity_bounds": bounds,
                        "npvc": fraction_deviance_explained(npvc),
                        "glm": fraction_deviance_explained(glm), "npvc_predictions": modes,
                        "folds": [{"fold_id": fold, **{model: fraction_deviance_explained(points)
                                   for model, points in operands.items()}} for fold, operands in sorted(by_fold.items())]})
    return {"schema": "npvc-fde-results-v1", "scope": "supplied held-out operands; cohort and fit provenance not authenticated",
            "normalizers": {"npvc": "marginal activity density; conditional peak on 200-point source grid",
                            "glm": "predictor-free mean; observed activity as saturated Poisson mean"},
            "units": results}


def unique_object(pairs):
    obj = {}
    for key, value in pairs:
        require(key not in obj, "duplicate JSON key")
        obj[key] = value
    return obj


def run(input_path, output_path):
    require(not output_path.exists(), "fresh output destination required")
    with input_path.open("rb") as stream:
        raw = stream.read(MAX_INPUT_BYTES + 1)
    require(len(raw) <= MAX_INPUT_BYTES, "input exceeds 64 MiB component limit")
    document = json.loads(raw, object_pairs_hook=unique_object,
                          parse_constant=lambda _: (_ for _ in ()).throw(Invalid("nonfinite JSON value")))
    output = score(document)
    output["input_sha256"] = hashlib.sha256(raw).hexdigest()
    with output_path.open("x") as stream:
        json.dump(output, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        run(args.input, args.output)
    except (Invalid, OSError, ValueError, TypeError, KeyError, OverflowError) as exc:
        parser.exit(2, str(exc) + "\n")
