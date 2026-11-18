"""Read already-produced Figure 5 fit tables into the existing keyed diagnostic.

No fitting, pickle/array loading, historical-version inference or branch choice.
Objects and factor bindings are trusted operator inputs, not participant inputs.
Matching model.data is not proof of R's fitted model-frame support.
"""
from __future__ import annotations

import hashlib
import json
import math
from numbers import Integral, Real
from pathlib import Path
import types

TASK = "PAPER-FIND-ADD-015"
GROUPS = ("activated", "suppressed")
MODEL_COLUMNS = ("cell", "basef", "preceding", "opto")
ALIGNMENT_SHA256 = "4a3e82e7dffbd947bb20c48ca557522bfeac7baae784c17bb56d9eb6cb691891"
ALIGNMENT_BYTES = 8380
SOURCE_FORMULA = "opto ~ 1 + basef + (1 + preceding|cell)"


class ExportError(ValueError):
    """Native objects cannot support this declared, narrow export interface."""


def require(condition, message):
    if not condition:
        raise ExportError(message)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def identity(value, label):
    # pandas/NumPy integer scalars normalize without converting string factors.
    if isinstance(value, Integral) and not isinstance(value, bool):
        return int(value)
    if isinstance(value, str) and value:
        return str(value)
    raise ExportError(label + ": integer or nonempty text identity required")


def key(value):
    return (type(value).__name__, value)


def binary64(value, label):
    try:
        result = float(value)
    except (OverflowError, ValueError, TypeError) as exc:
        raise ExportError(label + ": unsupported binary64 conversion") from exc
    # A genuine source NaN is preserved only in ancillary raw-table states.
    # Finite wider scalars may not become rounded values, zeros or infinity.
    if math.isnan(result):
        require(value != value, label + ": conversion created NaN")
    else:
        require(result == value, label + ": lossy binary64 conversion")
    return result


def number(value, label):
    require(isinstance(value, Real) and not isinstance(value, bool),
            label + ": real numeric scalar required")
    result = int(value) if isinstance(value, Integral) else binary64(value, label)
    try:
        finite = math.isfinite(result)
    except OverflowError:
        finite = False
    require(finite, label + ": finite modeled value required; no row deletion")
    return result


def raw_scalar(value):
    """Retain ancillary nonfinite coefficient cells as explicit JSON states."""
    if value is None or type(value) is bool:
        return value
    if isinstance(value, str):
        return str(value)
    if isinstance(value, Integral):
        return int(value)
    if isinstance(value, Real):
        value = binary64(value, "raw coefficient scalar")
        if math.isnan(value):
            return {"nonfinite": "nan"}
        if math.isinf(value):
            return {"nonfinite": "+inf" if value > 0 else "-inf"}
        return value
    raise ExportError("unsupported coefficient-table scalar; no silent coercion")


def exact_fields(value, fields, label):
    require(type(value) is dict and set(value) == set(fields), label + ": exact fields required")


def shape(frame, max_rows, max_columns, label):
    try:
        dimensions = frame.shape
        require(type(dimensions) is tuple and len(dimensions) == 2,
                label + ": two-dimensional dataframe required")
        rows, cols = dimensions
        require(type(rows) is int and type(cols) is int and
                0 < rows <= max_rows and 0 < cols <= max_columns,
                label + ": whole-table capacity exceeded or empty")
        columns = list(frame.columns)
        index = list(frame.index)
        require(len(columns) == cols and len(index) == rows, label + ": inconsistent axes")
        require(all(type(c) is str and c for c in columns) and len(set(columns)) == cols,
                label + ": unique named columns required")
        indices = [identity(v, label + " index") for v in index]
        # Access the native dataframe interface, without importing pandas here.
        dtypes = [str(frame.dtypes.iloc[i]) for i in range(cols)]
        frame.iloc
    except AttributeError as exc:
        raise ExportError(label + ": unsupported dataframe interface") from exc
    return columns, indices, dtypes


def coefficient_snapshot(frame, limits, label):
    columns, indices, dtypes = shape(frame, limits["max_cells"], limits["max_columns"], label)
    require(len({key(v) for v in indices}) == len(indices), label + ": duplicate coefficient index")
    values = [[raw_scalar(frame.iloc[i, j]) for j in range(len(columns))]
              for i in range(len(indices))]
    return {"index": indices, "columns": columns, "dtypes": dtypes, "values": values}


def modeled_rows(frame, limits, label):
    columns, indices, dtypes = shape(frame, limits["max_rows"], limits["max_columns"], label)
    require(set(MODEL_COLUMNS) <= set(columns), label + ": source model columns missing")
    locations = {name: columns.index(name) for name in MODEL_COLUMNS}
    rows = []
    for position, index in enumerate(indices):
        row = {"position": position, "index_label": index,
               "cell_id": identity(frame.iloc[position, locations["cell"]], label + " cell")}
        for name in MODEL_COLUMNS[1:]:
            row[name] = number(frame.iloc[position, locations[name]], label + "." + name)
        rows.append(row)
    return {"source_columns": columns, "source_dtypes": dtypes,
            "projection_columns": list(MODEL_COLUMNS), "rows": rows}


def factor_map(bindings, roster, label):
    require(type(bindings) is list and len(bindings) == len(roster), label + ": complete factor bindings required")
    result, normalized, cells = {}, [], set()
    expected = {key(v) for v in roster}
    for binding in bindings:
        exact_fields(binding, ("factor_level", "cell_id"), label)
        factor = identity(binding["factor_level"], label + " factor")
        cell = identity(binding["cell_id"], label + " cell")
        require(key(factor) not in result and key(cell) not in cells,
                label + ": factor/cell mapping must be bijective")
        result[key(factor)] = cell
        cells.add(key(cell))
        normalized.append({"factor_level": factor, "cell_id": cell})
    require(cells == expected, label + ": mapping differs from complete supplied cell roster")
    return result, normalized


def coefficient_rows(raw, factors, label):
    require({"(Intercept)", "preceding"} <= set(raw["columns"]),
            label + ": named intercept/preceding columns required")
    require({key(v) for v in raw["index"]} == set(factors),
            label + ": native factor levels differ from complete explicit mapping")
    intercept, preceding = raw["columns"].index("(Intercept)"), raw["columns"].index("preceding")
    return [{"cell_id": factors[key(level)],
             "intercept": number(values[intercept], label + " intercept"),
             "preceding": number(values[preceding], label + " preceding")}
            for level, values in zip(raw["index"], raw["values"])]


def load_alignment(path=None):
    if path is None:
        path = Path(__file__).resolve().parent.parent / "fig5-coefficient-alignment-v1" / "coefficient_alignment.py"
    path = Path(path)
    with path.open("rb") as stream:
        raw = stream.read(ALIGNMENT_BYTES + 1)
    require(len(raw) == ALIGNMENT_BYTES and hashlib.sha256(raw).hexdigest() == ALIGNMENT_SHA256,
            "existing alignment source pin mismatch")
    module = types.ModuleType("_fig5_alignment_frozen")
    module.__file__ = str(path)
    exec(compile(raw, str(path), "exec"), module.__dict__)
    return module


def export_panel(models, source_frames, expected_cell_ids, factor_bindings, *,
                 conditional_semantics, runtime_record, limits, alignment_source=None):
    """Export a complete two-group fit snapshot and reuse the old diagnostic.

    Supported fit objects expose coefs/fixef/ranef/data as dataframes; lists,
    missing tables and other historical APIs are refused, not guessed. An
    explicit fixed_plus_random declaration is not runtime authentication.
    """
    for name, panel in (("models", models), ("source_frames", source_frames),
                        ("expected_cell_ids", expected_cell_ids), ("factor_bindings", factor_bindings)):
        exact_fields(panel, GROUPS, name)
    require(conditional_semantics == "fixed_plus_random", "conditional semantics require explicit declaration")
    exact_fields(runtime_record, ("python", "pymer4", "lme4"), "runtime record")
    require(all(v is None or (type(v) is str and v) for v in runtime_record.values()),
            "runtime versions are observed strings or unknown; no inferred versions")
    exact_fields(limits, ("max_rows", "max_cells", "max_columns", "max_output_bytes"), "limits")
    require(all(type(v) is int and v > 0 for v in limits.values()), "positive complete-export limits required")
    alignment = load_alignment(alignment_source)
    exports, lineage = {}, {}
    for group in GROUPS:
        roster = expected_cell_ids[group]
        require(type(roster) is list and 0 < len(roster) <= limits["max_cells"], "bounded complete roster required")
        roster = [identity(v, "roster") for v in roster]
        require(len({key(v) for v in roster}) == len(roster), "duplicate roster cell")
        factors, bindings = factor_map(factor_bindings[group], roster, group)
        frame = modeled_rows(source_frames[group], limits, group + " source frame")
        try:
            model_frame = modeled_rows(models[group].data, limits, group + " model.data")
            fixed = coefficient_snapshot(models[group].coefs, limits, group + " coefs")
            conditional = coefficient_snapshot(models[group].fixef, limits, group + " fixef")
            random = coefficient_snapshot(models[group].ranef, limits, group + " ranef")
        except AttributeError as exc:
            raise ExportError("already-produced fit must expose data/coefs/fixef/ranef") from exc
        require(frame["rows"] == model_frame["rows"], "model.data modeled projection/index differs from supplied frame")
        require({key(r["cell_id"]) for r in frame["rows"]} == {key(v) for v in roster},
                "source frame omits/adds cells relative to complete supplied roster")
        # Notebook cell9 uses Estimate.iloc[0]/[1]. Do not silently reinterpret
        # a different native coefficient order as that literal notebook branch.
        require(fixed["index"] == ["(Intercept)", "basef"], "notebook fixed-effect row identity/order unsupported")
        require("Estimate" in fixed["columns"], "fixed Estimate column missing")
        estimate = fixed["columns"].index("Estimate")
        require(set(random["columns"]) == {"(Intercept)", "preceding"}, "unexpected random-effect terms")
        observed_formula = getattr(models[group], "formula", None)
        require(observed_formula is None or type(observed_formula) is str,
                "unsupported native formula representation")
        if observed_formula is not None:
            require("".join(observed_formula.split()) == "".join(SOURCE_FORMULA.split()),
                    "model-exposed formula differs from the source Figure5 formula")
        exports[group] = {
            "group": group, "expected_cell_ids": roster,
            "fixed": {"intercept": number(fixed["values"][0][estimate], "population intercept"),
                      "basef": number(fixed["values"][1][estimate], "basef coefficient")},
            "conditional": coefficient_rows(conditional, factors, "conditional"),
            "random": coefficient_rows(random, factors, "random"),
            "trial_covariates": [{"cell_id": r["cell_id"], "basef": r["basef"]} for r in frame["rows"]],
            "conditional_semantics": conditional_semantics,
        }
        lineage[group] = {"source_frame_projection": frame, "model_data_projection": model_frame,
                          "source_projection_sha256": digest(frame), "factor_bindings": bindings,
                          "raw_coefficients": {"coefs": fixed, "fixef": conditional, "ranef": random},
                          "source_row_count": len(frame["rows"]),
                          "formula": {"source": SOURCE_FORMULA, "model_exposed": observed_formula,
                                      "matches_exposed_string": True if observed_formula is not None else None},
                          "actual_R_model_frame_verified": False,
                          "original_cohort_authenticated": False}
    result = {"schema_version": "fig5-native-keyed-fit-export/v1", "task_id": TASK,
              "exports": exports, "lineage": lineage,
              "diagnostic": alignment.diagnose_panel(exports),
              "runtime_record": dict(runtime_record), "runtime_record_kind": "operator_declared_not_authenticated",
              "historical_runtime_verified": False, "scientific_qualification": False,
              "reproduction_accepted": None, "improvement_accepted": None}
    require(len(encoded(result)) <= limits["max_output_bytes"], "complete output capacity exceeded; no truncation")
    return result
