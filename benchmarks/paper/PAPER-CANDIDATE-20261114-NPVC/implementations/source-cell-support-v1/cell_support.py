"""Construct source cell support from the documented NPvC selection variables.

This operates on explicitly decoded author variables, not MAT files. It makes
no archive, imaging-frame, original-study eligibility, epoch or fold assignment.
"""

import math


SOURCE_CELLS = 4732
SOURCE_SESSIONS = 64
SELECTOR_FLAGS = (
    ("okunlabeled", "unlabeled", 6),
    ("ACC", "ACC", 3),
    ("RETRO", "RETRO", 5),
    ("PPC", "cPPC", 4),
)
FLAG_COLUMNS = (("ACC", 3), ("cPPC", 4), ("RETRO", 5), ("unlabeled", 6))


class SourceCellError(ValueError):
    """The supplied decoded variables contradict their declared source schema."""


def _need(condition, message):
    if not condition:
        raise SourceCellError(message)


def _integer(value, name):
    # MATLAB double-valued integer identifiers retain their exact value. No
    # rounding, boolean-as-one, float conversion of large integers, or offsets.
    _need(type(value) in (int, float), name + " must be a numeric integer")
    if type(value) is float:
        _need(math.isfinite(value) and value.is_integer(), name + " must be finite and integral")
    return int(value)


def construct_cell_support(session, selections):
    """Return a source-specific cell table and explicit quality memberships.

    ``session`` is the decoded 4732-by-7 row table. ``selections`` contains the
    four documented *flat index vectors*, already decoded without changing
    their MATLAB one-based global cell indices. Matrix orientation and file
    provenance must be established by the caller from the original descriptors.

    Overlap across selectors is retained, not assumed invalid or counted twice.
    Each selector must agree with its own source flag. Other flags are retained
    verbatim; this function does not choose a task projection for ambiguous rows.
    """
    _need(type(session) in (list, tuple) and len(session) == SOURCE_CELLS,
          "session must contain the complete 4732 source-cell rows")
    _need(type(selections) is dict and set(selections) == {r[0] for r in SELECTOR_FLAGS},
          "all four documented quality-selection variables are required")

    rows = []
    source_sessions = {}
    for index, values in enumerate(session):
        _need(type(values) in (list, tuple) and len(values) == 7,
              "every source-cell row must contain seven columns")
        row = tuple(_integer(value, "session column") for value in values)
        _need(all(row[column] in (0, 1) for _, column in FLAG_COLUMNS),
              "projection flags must retain their source 0/1 values")
        identity = (row[1], row[2])
        if row[0] in source_sessions:
            _need(source_sessions[row[0]] == identity,
                  "one source session number has conflicting animal/session metadata")
        else:
            source_sessions[row[0]] = identity
        rows.append(row)
    _need(len(source_sessions) == SOURCE_SESSIONS,
          "complete source metadata must represent the documented 64 source sessions")

    memberships = {}
    counts = {}
    for selector, _, flag_column in SELECTOR_FLAGS:
        vector = selections[selector]
        _need(type(vector) in (list, tuple), selector + " must be a decoded flat index vector")
        observed = set()
        for value in vector:
            cell_id = _integer(value, selector + " cell index")
            _need(1 <= cell_id <= SOURCE_CELLS, selector + " contains an out-of-range global cell index")
            _need(cell_id not in observed, selector + " repeats a global cell index")
            observed.add(cell_id)
            row = rows[cell_id - 1]
            _need(row[flag_column] == 1, selector + " contradicts its documented source-table flag")
            memberships.setdefault(cell_id, []).append(selector)
        counts[selector] = len(observed)
    _need(memberships, "quality-selection variables select no source cells")

    cells = []
    selected_sessions = set()
    multiple_selectors = []
    multiple_flags = []
    for cell_id in sorted(memberships):
        row = rows[cell_id - 1]
        flags = {name: row[column] for name, column in FLAG_COLUMNS}
        sources = memberships[cell_id]
        if len(sources) > 1:
            multiple_selectors.append(cell_id)
        if sum(flags.values()) > 1:
            multiple_flags.append(cell_id)
        selected_sessions.add(row[0])
        cells.append({
            "source_global_cell_index": cell_id,
            "source_session_number": row[0],
            "source_animal_number": row[1],
            "source_animal_session_number": row[2],
            "projection_flags": flags,
            "quality_selector_memberships": list(sources),
        })

    return {
        "schema": "npvc-author-cell-support/v1",
        "source_cell_rows": SOURCE_CELLS,
        "source_session_count": len(source_sessions),
        "index_origin": "MATLAB one-based global cell row in session",
        "selected_unique_cell_count": len(cells),
        "selected_source_session_count": len(selected_sessions),
        "selection_counts": counts,
        "cells": cells,
        "not_selected_global_cell_indices": [i for i in range(1, SOURCE_CELLS + 1) if i not in memberships],
        "multiple_selector_cell_indices": multiple_selectors,
        "multiple_projection_flag_cell_indices": multiple_flags,
        "scope": {
            "original_study_eligibility_established": False,
            "archive_or_trace_row_mapping_established": False,
            "epoch_or_fold_mapping_established": False,
            "quality_selection_is_not_original_paper_cohort": True,
        },
    }
