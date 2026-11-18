"""Prospectively declared descriptive Set–Go trajectory summaries.

The eight-value outcome is a new benchmark summary, not an original paper metric.
It describes this exposed session and does not identify a causal or population
effect. No observations are loaded and no fitting is performed on import.
"""
from __future__ import annotations

from fractions import Fraction
import math

import numpy as np

from support import validate_metadata


METHOD = "neural096-split-stratified-quarter-rate-contrasts/v1"
QUARTERS = ((0, 5), (5, 10), (10, 15), (15, 20))
REASONS = (
    "single_exposed_animal_session",
    "assignment_and_dependence_unverified",
    "recording_segments_not_randomized_blocks",
)
CELL_FIELDS = ("cell_id", "source_split", "observation_segment", "is_eye", "theta",
               "n_long", "n_short", "supported", "missing_priors")


class TrajectoryError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise TrajectoryError(message)


def _array(arrays, name, shape, dtype):
    value = arrays.get(name)
    require(isinstance(value, np.ndarray) and value.shape == shape
            and value.dtype == np.dtype(dtype), "invalid array layout: " + name)
    return value


def validate_arrays(validated, arrays):
    """Validate the selected numeric operands against the complete metadata.

    Caller authenticity is separate: the operator route first uses packet.py's
    exact preparation-receipt loader. Generated controls call these arithmetic
    primitives directly and never confer authentic-source qualification.
    """
    require(type(arrays) is dict, "array dictionary required")
    counts = _array(arrays, "counts", (204, 54, 20), "<u4")
    edges = _array(arrays, "phase_edges_seconds", (204, 21), "<f8")
    exposures = _array(arrays, "exposure_seconds", (204, 20), "<f8")
    trial_ids = _array(arrays, "trial_ids", (204,), "<i8")
    unit_ids = _array(arrays, "unit_ids", (54,), "<i8")
    flags = _array(arrays, "nlb_heldout_unit_flags", (54,), "u1")
    require(trial_ids.tolist() == validated["trial_ids"], "trial identity/order differs")
    require(unit_ids.tolist() == validated["unit_ids"], "unit identity/order differs")
    require(flags.tolist() == [int(x) for x in validated["nlb_heldout_unit_flags"]],
            "unit roles differ")
    require(np.isfinite(edges).all() and np.isfinite(exposures).all()
            and (exposures > 0).all(), "finite positive exposure required")
    require(np.array_equal(np.diff(edges, axis=1), exposures),
            "exposure differs from native phase edges")
    for index, row in enumerate(validated["trials"]):
        left, right = Fraction(row["set_time"]), Fraction(row["go_time"])
        expected = np.asarray([float(left + (right-left) * k / 20)
                               for k in range(21)], dtype="<f8")
        require(np.array_equal(edges[index], expected),
                "phase edges differ from original represented endpoints")
    with np.errstate(over="ignore", divide="ignore", invalid="ignore"):
        rates = counts.astype(np.float64) / exposures[:, None, :]
    require(np.isfinite(rates).all(), "rates exceed finite representation")
    return rates


def _mean_rates(rates, indices):
    if not indices:
        return None
    # Divide before reducing to avoid avoidable overflow for nonnegative rates.
    with np.errstate(over="ignore", invalid="ignore"):
        result = np.sum(rates[indices] / len(indices), axis=0)
    require(np.isfinite(result).all(), "mean rates exceed finite representation")
    return result


def quarter_summary(difference):
    require(isinstance(difference, np.ndarray) and difference.shape == (54, 20)
            and difference.dtype.kind == "f" and np.isfinite(difference).all(),
            "finite complete signed difference required")
    rms, signed = [], []
    for begin, end in QUARTERS:
        piece = difference[:, begin:end]
        scale = float(np.max(np.abs(piece)))
        if scale == 0.0:
            rms.append(0.0)
            signed.append(0.0)
        else:
            normalized = piece / scale
            rms.append(scale * math.sqrt(float(np.mean(normalized * normalized))))
            signed.append(scale * float(np.mean(normalized)))
    require(all(math.isfinite(value) for value in rms + signed),
            "summary exceeds finite representation")
    return {"quarter_rms_hz": rms, "quarter_signed_mean_hz": signed}


def build_reference(metadata, arrays):
    """Produce evaluator-private vectors and their declared compact answer."""
    validated = validate_metadata(metadata)
    rates = validate_arrays(validated, arrays)
    cells = []
    rate_max = 0.0
    for supported_cell in validated["cells"]:
        cell = {key: supported_cell[key] for key in CELL_FIELDS}
        long = _mean_rates(rates, supported_cell["long_trial_indices"])
        short = _mean_rates(rates, supported_cell["short_trial_indices"])
        for name, value in (("long_rate_hz", long), ("short_rate_hz", short)):
            cell[name] = None if value is None else value.tolist()
            if value is not None:
                rate_max = max(rate_max, float(np.max(value)))
        if long is None or short is None:
            cell["difference_hz"] = None
            cell["summary"] = None
        else:
            difference = long - short
            cell["difference_hz"] = difference.tolist()
            cell["summary"] = quarter_summary(difference)
        cells.append(cell)
    return {
        "schema": "neural096-descriptive-reference/v1",
        "method": METHOD,
        "unit_ids": validated["unit_ids"],
        "phase_bins": 20,
        "quarter_bin_slices": [list(x) for x in QUARTERS],
        "rate_units": "spikes/s/source unit",
        "prior_orientation": "long minus short",
        "trial_weighting": "equal-trial mean of individual count/exposure rates",
        "cell_order": "train,val; segment0..5; is_eyeFalse,True; theta0,180",
        "display_rate_max_hz": rate_max if rate_max > 0 else 1.0,
        "cells": cells,
        "complete_support_aggregate": None,
        "aggregate_reason": "No aggregate over selected support is part of this outcome.",
        "uncertainty": {"status": "not_qualified", "reason_codes": list(REASONS)},
        "interpretation": "Finite-sample descriptive phase summaries only; no inference of significance or complete unit-level geometry.",
        "source_verification": "Caller must supply authenticated saved preparation; arithmetic consistency alone is not provenance.",
    }


def matched_observation(reference):
    """Whitelist identical prior means/support for viewer and programme arms."""
    require(type(reference) is dict and reference.get("method") == METHOD,
            "declared reference method required")
    cells = []
    for source in reference["cells"]:
        row = {key: source[key] for key in CELL_FIELDS}
        # Fresh lists prevent a later observation edit from altering the private reference.
        for name in ("long_rate_hz", "short_rate_hz"):
            values = source[name]
            row[name] = None if values is None else [list(unit) for unit in values]
        row["missing_priors"] = list(row["missing_priors"])
        cells.append(row)
    return {
        "schema": "neural096-matched-prior-mean-observations/v1",
        "method": METHOD,
        "unit_ids": list(reference["unit_ids"]),
        "phase_bins": 20,
        "quarter_bin_slices": [list(x) for x in QUARTERS],
        "rate_units": reference["rate_units"],
        "display_rate_max_hz": reference["display_rate_max_hz"],
        "cells": cells,
        "information_condition": "matched_prior_specific_aggregate_trajectories",
        "limits": [
            "One previously exposed animal/session; these are response-conditioned observations.",
            "Recording segments and original train/validation labels are not established randomization or independence blocks.",
            "Aggregate rates omit individual-trial detail in BOTH matched access arms.",
            "Typed SVG viewing has finite visual precision; numerical programme inputs retain numeric precision.",
            "No computed difference, reference summary or numerical answer is delivered.",
        ],
    }
