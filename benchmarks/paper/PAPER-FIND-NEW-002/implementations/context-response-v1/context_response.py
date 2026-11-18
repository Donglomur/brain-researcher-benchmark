"""Reconstruct released Figure3 H/I response arithmetic, not paper admission.

The operator supplies already authenticated numeric arrays and safely converted
indices. This module does not open archives, unpickle data, fit a model, grade a
candidate or establish the final paper's physical timing or biological units.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

import numpy as np

TASK_ID = "PAPER-FIND-NEW-002"
CONDITIONS = ("visF1", "visF2", "vis1OptoF1", "vis2OptoF1", "optoF1")
RESPONSE_NAMES = ("matched", "unmatched", "opto_only")
EXPERIMENTS = ("expt1", "expt2", "expt3")
STIMULATED_COUNTS = (9, 13, 10)
ORIGINAL_WINDOW = (125, 128)
REVISION_WINDOW = (123, 126)
REVISION_ROWS = 108
REVISION_FRAMES = 200


def _float_matrix(value, name):
    array = np.asarray(value)
    if array.ndim != 2 or array.dtype.kind != "f" or array.dtype.itemsize > 8:
        raise ValueError(f"{name} must be a real floating-point rank-2 array of at most 64-bit precision")
    if not all(array.shape):
        raise ValueError(f"{name} has an empty axis")
    # Float64 mathematical reduction is explicit, not a claim of source-dtype
    # bitwise parity. We never replace NaN/Inf or silently exclude a row.
    return np.asarray(array, dtype=np.float64)


def _index_list(value, count, cells, name):
    if isinstance(value, np.ndarray):
        if value.ndim != 1 or value.dtype.kind not in "iu":
            raise ValueError(f"{name} must be a one-dimensional integer selection")
        values = value.tolist()
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        values = list(value)
    else:
        raise ValueError(f"{name} must be an integer selection")
    if len(values) != count:
        raise ValueError(f"{name} must retain all {count} source-selected cells")
    if any(isinstance(x, (bool, np.bool_)) or not isinstance(x, (int, np.integer)) for x in values):
        raise ValueError(f"{name} contains a noninteger cell index")
    values = [int(x) for x in values]
    if len(set(values)) != len(values) or any(x < 0 or x >= cells for x in values):
        raise ValueError(f"{name} contains duplicate or out-of-range cell indices")
    return values


def _value(number):
    number = float(number)
    return number if math.isfinite(number) else None


def _mean(values):
    # No nanmean/dropna. An undefined source row makes the corresponding source
    # aggregate undefined. Mean-before-replacement is not replacement-before-mean.
    if any(value is None for value in values):
        return None
    with np.errstate(over="ignore", invalid="ignore"):
        return _value(np.asarray(values, dtype=np.float64).mean())


def reconstruct_responses(experiments, revision):
    """Return all 140 H/I rows with literal notebook windows and provenance.

    experiments maps expt1/expt2/expt3 to {conditions: five source matrices,
    stimulated_cell_indices: ordered source indices}. revision maps matched,
    unmatched and opto_only to the released 108 x 200 matrices. The revision
    matrices already encode the source response difference; they must not have
    the original experiments' visual baselines subtracted a second time.
    """
    if not isinstance(experiments, Mapping) or set(experiments) != set(EXPERIMENTS):
        raise ValueError("all three named source experiments are required exactly once")
    if not isinstance(revision, Mapping) or set(revision) != set(RESPONSE_NAMES):
        raise ValueError("all three named revision response matrices are required")
    rows = []
    for name, count in zip(EXPERIMENTS, STIMULATED_COUNTS):
        experiment = experiments[name]
        if not isinstance(experiment, Mapping) or set(experiment) != {"conditions", "stimulated_cell_indices"}:
            raise ValueError(f"{name} must contain conditions and stimulated_cell_indices")
        conditions = experiment["conditions"]
        if not isinstance(conditions, Mapping) or set(conditions) != set(CONDITIONS):
            raise ValueError(f"{name} requires the five exact source conditions")
        arrays = {key: _float_matrix(conditions[key], f"{name}/{key}") for key in CONDITIONS}
        shape = arrays["visF1"].shape
        if any(a.shape != shape for a in arrays.values()) or shape[1] < ORIGINAL_WINDOW[1]:
            raise ValueError(f"{name} conditions must share cell/frame shape and cover the source window")
        indices = _index_list(experiment["stimulated_cell_indices"], count, shape[0], name)
        start, stop = ORIGINAL_WINDOW
        with np.errstate(over="ignore", invalid="ignore"):
            # Source H/I subtracts before averaging. Unlike source Panel G,
            # calc_single_cells_resp never applies nan_to_num.
            matched = (arrays["vis1OptoF1"][indices, start:stop]
                       - arrays["visF1"][indices, start:stop]).mean(axis=1)
            unmatched = (arrays["vis2OptoF1"][indices, start:stop]
                         - arrays["visF2"][indices, start:stop]).mean(axis=1)
            opto = arrays["optoF1"][indices, start:stop].mean(axis=1)
        for index, values in zip(indices, zip(matched, unmatched, opto)):
            response = {key: _value(value) for key, value in zip(RESPONSE_NAMES, values)}
            rows.append({"row_id": f"{name}:cell:{index}", "source_namespace": name,
                         "source_cell_index": index, "revision_row_index": None,
                         "frame_window": list(ORIGINAL_WINDOW), "responses": response})

    revised = {key: _float_matrix(revision[key], f"revision/{key}") for key in RESPONSE_NAMES}
    if any(array.shape != (REVISION_ROWS, REVISION_FRAMES) for array in revised.values()):
        raise ValueError("each revision response must retain the complete 108 x 200 source matrix")
    start, stop = REVISION_WINDOW
    with np.errstate(over="ignore", invalid="ignore"):
        values = {key: array[:, start:stop].mean(axis=1) for key, array in revised.items()}
    for index in range(REVISION_ROWS):
        response = {key: _value(values[key][index]) for key in RESPONSE_NAMES}
        rows.append({"row_id": f"revision:row:{index}", "source_namespace": "revision",
                     "source_cell_index": None, "revision_row_index": index,
                     "frame_window": list(REVISION_WINDOW), "responses": response})

    for row in rows:
        row["status"] = ("finite" if all(v is not None for v in row["responses"].values())
                         else "nonfinite_source_arithmetic")
    namespaces = (*EXPERIMENTS, "revision")
    return {
        "schema": "sequence-context-responses/v1", "task_id": TASK_ID,
        "scope": "released_notebook_Figure3_HI_response_arithmetic",
        "rows": rows,
        "source_namespace_counts": {name: sum(r["source_namespace"] == name for r in rows)
                                    for name in namespaces},
        "pooled_cell_means": {key: _mean([r["responses"][key] for r in rows]) for key in RESPONSE_NAMES},
        "source_namespace_means": {
            name: {key: _mean([r["responses"][key] for r in rows if r["source_namespace"] == name])
                   for key in RESPONSE_NAMES} for name in namespaces},
        "nonfinite_response_count": sum(v is None for r in rows for v in r["responses"].values()),
        "precision": "float64 arithmetic; no claim of bitwise source-dtype parity",
        "revision_namespace_is_one_independent_experiment": None,
        "biological_independent_units_verified": False,
        "physical_response_window_verified": False,
        "original_data_authenticated_by_this_function": False,
        "complete_primary_reproduction_established": False,
        "paper_improvement_established": False,
    }
