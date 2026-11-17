"""Complete operator-only ordinary contrast reconciliation, without native I/O.

The caller authenticates the two complete Parquet tables and supplies the schemas
observed by the same decoder. The accepted scalar policy is an explicit argument.
This module neither reads tables nor establishes scientific execution readiness.
"""
import math

IDENTITIES = ("subject", "experiment")
SOURCE_ROWS = 344
TARGET_ROWS = 29


def need(ok, message):
    if not ok:
        raise ValueError(message)


def schema_map(schema):
    need(type(schema) is list and 0 < len(schema) <= 128, "Bounded decoded schema required")
    out = {}
    for field in schema:
        need(type(field) is dict and set(field) == {"name", "type", "nullable"}
             and type(field["name"]) is str and bool(field["name"])
             and type(field["type"]) is str and type(field["nullable"]) is bool,
             "Exact decoded field descriptor required")
        need(field["name"] not in out, "Duplicate decoded schema name")
        out[field["name"]] = field["type"]
    return out


def reconcile(measures, contrasts, source_schema, target_schema, *, policy):
    """Preserve all 783 target positions and all 344 source rows.

    Exact target fields, source/target types and complete row counts are barriers.
    Invalid identities and duplicates remain explicit failures, including where
    the source declares an expected missing target. Expected missing targets are
    accounted exclusions, never numerical matches or imputed zeroes.
    """
    need(type(measures) is list and len(measures) == SOURCE_ROWS,
         "Complete 344-row original ordinary measures required")
    need(type(contrasts) is list and len(contrasts) == TARGET_ROWS,
         "Complete 29-row original ordinary contrast table required")
    definitions = policy.DEFINITIONS
    need(len(definitions) == 27, "Complete accepted 27-column policy required")
    source_types, target_types = schema_map(source_schema), schema_map(target_schema)
    need(set(target_types) == set(IDENTITIES) | set(definitions),
         "Exact complete target schema required")
    needed = set(IDENTITIES) | {"condition"} | {x[0] for x in definitions.values()}
    need(needed <= set(source_types), "Complete ordinary source operands required")
    dtype_names = {"float": "float32", "double": "float64"}
    dtypes = {}
    for column, (measure, _plus, _minus) in definitions.items():
        pair = (dtype_names.get(source_types[measure]), dtype_names.get(target_types[column]))
        expected = "float32" if measure == "Cortical.SWA" else "float64"
        need(pair == (expected, expected), "Source/target decoded dtype differs from accepted policy")
        dtypes[column] = pair
    for rows, names in ((measures, source_types), (contrasts, target_types)):
        need(all(type(row) is dict and set(row) == set(names) for row in rows),
             "Every complete row must match its decoded schema")

    def identity(row):
        return all(type(row[k]) is str and bool(row[k]) for k in IDENTITIES)

    source, target = {}, {}
    invalid_source = []
    for i, row in enumerate(measures):
        if not identity(row) or type(row["condition"]) is not str or not row["condition"]:
            invalid_source.append(i)
            continue
        key = tuple(row[k] for k in IDENTITIES) + (row["condition"],)
        source.setdefault(key, []).append((i, row))
    invalid_target = []
    for i, row in enumerate(contrasts):
        if not identity(row):
            invalid_target.append(i)
            continue
        target.setdefault(tuple(row[k] for k in IDENTITIES), []).append(i)
    source_duplicates = [list(k) for k, rows in source.items() if len(rows) > 1]
    target_duplicates = [list(k) for k, rows in target.items() if len(rows) > 1]
    cells = []
    for i, row in enumerate(contrasts):
        for column, (measure, plus, minus) in definitions.items():
            result = {"target_row": i, "column": column}
            if not identity(row):
                result["status"] = "missing_or_invalid_target_identity"
                cells.append(result)
                continue
            base = tuple(row[k] for k in IDENTITIES)
            a, b = source.get(base + (plus,), []), source.get(base + (minus,), [])
            result["source_rows"] = {"minuend": [j for j, _ in a],
                                     "subtrahend": [j for j, _ in b]}
            if len(target[base]) != 1:
                result["status"] = "duplicate_target_key"
            elif len(a) > 1 or len(b) > 1:
                result["status"] = "duplicate_source_condition"
            else:
                exclusion = policy.expected_export_exclusion_status(
                    row["subject"], row["experiment"], column, row[column])
                if len(a) != 1:
                    result["status"] = "missing_source_condition"
                elif exclusion is not None:
                    # Late.BSL.NREM may deliberately be absent. Structural
                    # failures above cannot be laundered by this exclusion.
                    result["status"] = exclusion
                elif len(b) != 1:
                    result["status"] = "missing_source_condition"
                elif any(type(v) is not float or not math.isfinite(v)
                         for v in (a[0][1][measure], b[0][1][measure], row[column])):
                    result["status"] = "missing_or_nonfinite_value"
                else:
                    try:
                        sd, td = dtypes[column]
                        # This also checks exact decoded binary32 target values.
                        policy.subtract_source_dtype(column, row[column], 0.0, td, td)
                        computed = policy.subtract_source_dtype(
                            column, a[0][1][measure], b[0][1][measure], sd, td)
                    except ValueError as exc:
                        result.update(status="unsupported_source_dtype_value", reason=str(exc))
                    else:
                        delta = computed - row[column]
                        result.update(reconstructed=computed, stored=row[column],
                                      absolute_difference=abs(delta) if math.isfinite(delta) else None,
                                      status="exact_match" if computed == row[column] else "numeric_mismatch")
            cells.append(result)
    statuses = {}
    for cell in cells:
        statuses[cell["status"]] = statuses.get(cell["status"], 0) + 1
    allowed = {"exact_match", "expected_export_exclusion"}
    reconciled = (not invalid_source and not invalid_target and not source_duplicates
                  and not target_duplicates and set(statuses) <= allowed)
    need(len(cells) == TARGET_ROWS * 27, "Every original target cell retained")
    return {
        "schema": "findlay-ordinary-contrast-reconciliation/v1",
        "keys": list(IDENTITIES), "source_rows": len(measures), "target_rows": len(contrasts),
        "target_columns": 27, "target_cells": len(cells),
        "definitions": {k: list(v) for k, v in definitions.items()},
        "source_schema": source_schema, "target_schema": target_schema,
        "source_duplicate_keys": source_duplicates, "target_duplicate_keys": target_duplicates,
        "invalid_source_identity_rows": invalid_source, "invalid_target_identity_rows": invalid_target,
        "cells": cells, "status_counts": statuses,
        "numeric_matches": statuses.get("exact_match", 0),
        "expected_exclusions": statuses.get("expected_export_exclusion", 0),
        "all_target_cells_accounted": True, "all_target_cells_reconciled": reconciled,
        "comparison": "Exact accepted source-dtype subtraction; exclusions are not numeric matches",
        "scientific_ready": False, "models_fitted": 0,
    }
