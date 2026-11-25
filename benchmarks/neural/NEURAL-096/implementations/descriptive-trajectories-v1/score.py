"""Continuous descriptive errors and separate support/qualification checks."""
from __future__ import annotations

from fractions import Fraction
import math
import sys

from trajectory import METHOD, REASONS, TrajectoryError, require


NUMERIC_FIELDS = ("quarter_signed_mean_hz", "quarter_rms_hz")
ANSWER_KEYS = {"schema", "method", "prior_orientation", "cells",
               "support_conclusion", "interpretation_scope", "uncertainty"}
CELL_KEYS = {"cell_id", "support_status", "n_long", "n_short", *NUMERIC_FIELDS}


def _number(value):
    require(type(value) in (int, float), "finite real numerical estimate required")
    try:
        number = float(value)
    except (OverflowError, ValueError) as exc:
        raise TrajectoryError("numerical estimate exceeds finite range") from exc
    require(math.isfinite(number), "finite real numerical estimate required")
    return number


def _candidate(answer, expected_ids):
    require(type(answer) is dict and set(answer) == ANSWER_KEYS,
            "complete declared answer fields required")
    require(answer["schema"] == "neural096-descriptive-answer/v1"
            and answer["method"] == METHOD
            and answer["prior_orientation"] == "long minus short",
            "answer must name the selected method and orientation")
    cells = answer["cells"]
    require(type(cells) is list and len(cells) == len(expected_ids),
            "complete cell roster required")
    result = {}
    for cell in cells:
        require(type(cell) is dict and set(cell) == CELL_KEYS, "exact cell fields required")
        cell_id = cell["cell_id"]
        require(type(cell_id) is str and cell_id in expected_ids and cell_id not in result,
                "unknown or duplicate cell identity")
        require(cell["support_status"] in ("supported", "unsupported"),
                "explicit supported/unsupported status required")
        require(all(type(cell[key]) is int and 0 <= cell[key] <= 204
                    for key in ("n_long", "n_short")), "bounded integer support counts required")
        for field in NUMERIC_FIELDS:
            value = cell[field]
            if cell["support_status"] == "unsupported":
                require(value is None, "unsupported numerical estimate must be null")
            else:
                require(type(value) is list and len(value) == 4,
                        "all four fixed quarter estimates required")
                for entry in value:
                    number = _number(entry)
                    require(field != "quarter_rms_hz" or number >= 0,
                            "RMS estimates must be nonnegative")
        result[cell_id] = cell
    uncertainty = answer["uncertainty"]
    require(type(uncertainty) is dict and set(uncertainty) == {"status", "reason_codes"}
            and type(uncertainty["status"]) is str and len(uncertainty["status"]) <= 80,
            "uncertainty status and rationale codes required")
    codes = uncertainty["reason_codes"]
    require(type(codes) is list and len(codes) <= 8
            and all(type(code) is str and len(code) <= 80 for code in codes)
            and len(set(codes)) == len(codes), "bounded unique uncertainty reasons required")
    require(type(answer["interpretation_scope"]) is str
            and len(answer["interpretation_scope"]) <= 80, "interpretation scope required")
    require(answer["support_conclusion"] in ("complete_support", "partial_support", "no_supported_cells"),
            "support conclusion required")
    return result


def expected_answer(reference):
    """Evaluator-only expected schema, never part of participant observations."""
    require(reference.get("method") == METHOD, "reference method mismatch")
    cells = []
    for cell in reference["cells"]:
        row = {"cell_id": cell["cell_id"],
               "support_status": "supported" if cell["supported"] else "unsupported",
               "n_long": cell["n_long"], "n_short": cell["n_short"]}
        for field in NUMERIC_FIELDS:
            row[field] = list(cell["summary"][field]) if cell["supported"] else None
        cells.append(row)
    supported = sum(row["support_status"] == "supported" for row in cells)
    return {"schema": "neural096-descriptive-answer/v1", "method": METHOD,
            "prior_orientation": "long minus short", "cells": cells,
            "support_conclusion": ("complete_support" if supported == len(cells) else
                                   "no_supported_cells" if supported == 0 else "partial_support"),
            "interpretation_scope": "descriptive_phase_summary",
            "uncertainty": {"status": "not_qualified", "reason_codes": list(REASONS)}}


def _mean_absolute_error(values):
    """Keep ordinary reduction, without erasing representable tiny errors."""
    count = len(values)
    scaled = [value / count for value in values]
    # The complete answer has at most192 values per field. Exact binary
    # accumulation is bounded and avoids rounding every subnormal term away.
    if any(value > 0 and part < sys.float_info.min
           for value, part in zip(values, scaled)):
        return float(sum((Fraction(value) for value in values), Fraction()) / count)
    try:
        return math.fsum(scaled)
    except OverflowError:
        # Finite nonnegative operands have a finite mean even when the
        # rounded intermediate sum overflows.
        return float(sum((Fraction(value) for value in values), Fraction()) / count)


def grade(reference, answer):
    """Grade against an operator-owned frozen reference; no binary paper win.

    A missing supported-cell estimate prevents a numerical aggregate. Correctly
    marking unsupported cells cannot manufacture zero numerical error, and the
    aggregate never averages only a favourable subset of supplied estimates.
    """
    expected = expected_answer(reference)
    ids = {cell["cell_id"] for cell in expected["cells"]}
    require(len(ids) == 48 and len(expected["cells"]) == 48, "complete reference cells required")
    candidate = _candidate(answer, ids)
    errors = {field: [] for field in NUMERIC_FIELDS}
    support_errors, count_errors, missing_numeric, extra_numeric, per_cell = [], [], [], [], []
    for target in expected["cells"]:
        cell_id = target["cell_id"]
        actual = candidate[cell_id]
        support_correct = actual["support_status"] == target["support_status"]
        counts_correct = (actual["n_long"], actual["n_short"]) == (target["n_long"], target["n_short"])
        if not support_correct:
            support_errors.append(cell_id)
        if not counts_correct:
            count_errors.append(cell_id)
        row = {"cell_id": cell_id, "support_correct": support_correct,
               "counts_correct": counts_correct}
        if target["support_status"] == "supported":
            if actual["support_status"] != "supported":
                missing_numeric.append(cell_id)
                row["absolute_errors_hz"] = None
            else:
                row["absolute_errors_hz"] = {}
                for field in NUMERIC_FIELDS:
                    values = [abs(float(a)-float(b)) for a, b in zip(actual[field], target[field])]
                    require(all(math.isfinite(value) for value in values),
                            "numeric error exceeds finite representation")
                    errors[field].extend(values)
                    row["absolute_errors_hz"][field] = values
        else:
            row["absolute_errors_hz"] = None
            if actual["support_status"] == "supported":
                extra_numeric.append(cell_id)
        per_cell.append(row)
    complete_numeric = not missing_numeric and bool(errors[NUMERIC_FIELDS[0]])
    numerical = {}
    for field, values in errors.items():
        numerical[field] = ({"mean_absolute_error_hz": _mean_absolute_error(values),
                             "max_absolute_error_hz": max(values), "scored_values": len(values)}
                            if complete_numeric else None)
    return {
        "schema": "neural096-descriptive-grade/v1", "method": METHOD,
        "numeric_errors": numerical,
        "numeric_status": ("complete" if complete_numeric else
                           "missing_supported_cell_estimates" if missing_numeric else "no_supported_reference_cells"),
        "support_error_cells": support_errors, "count_error_cells": count_errors,
        "missing_numeric_cells": missing_numeric, "unsupported_cells_given_numbers": extra_numeric,
        "support_conclusion_correct": answer["support_conclusion"] == expected["support_conclusion"],
        "uncertainty_qualification_correct": (answer["uncertainty"]["status"] == "not_qualified"
                                              and set(answer["uncertainty"]["reason_codes"]) == set(REASONS)),
        "interpretation_scope_correct": answer["interpretation_scope"] == "descriptive_phase_summary",
        "per_cell": per_cell,
        "binary_win": None,
        "meaning": "Continuous descriptive reconstruction error with separate support and scientific-qualification checks; no model result or significance claim.",
    }
