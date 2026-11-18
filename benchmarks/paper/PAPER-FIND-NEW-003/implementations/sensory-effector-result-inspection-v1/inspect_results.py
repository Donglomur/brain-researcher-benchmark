"""Inspect one complete BANC sensory-effector source-result table.

This does not execute the author pipeline, select a primary panel, certify the
input's producer, compute inferential p-values, or award a scientific outcome.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import re
from pathlib import Path

SOURCE_COMMIT = "2e78ce38e946ab80e120a42f504a019b3a567fef"
SOURCE_PANEL_SHA256 = "76149a9bea40688bdef0d2867c9c63ce22cc11d16a0b06d50c03cc461b4581df"
BODY_PARTS = (
    "hemolymph", "enteric", "pharynx", "proboscis", "antenna", "eye", "neck",
    "wing", "haltere", "front leg", "middle leg", "hind leg", "abdomen", "reproductive",
)
COLUMNS = ("source_bp", "target_bp", "cosine_similarity", "influence", "is_same_bp")
METRICS = ("influence_log", "influence_norm_log", "influence_log_minmax")
MAX_CSV_BYTES = 262144
COSINE_SERIALIZATION_ATOL = 1e-10
NUMERIC_TOKEN = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z")


class ResultError(ValueError):
    """The supplied result table is not the complete declared source quantity."""


def _number(text: str, field: str) -> float:
    if not text or len(text) > 64 or not NUMERIC_TOKEN.fullmatch(text):
        raise ResultError(f"invalid {field} token")
    try:
        value = float(text)
    except (ValueError, OverflowError) as exc:
        raise ResultError(f"invalid {field} token") from exc
    if not math.isfinite(value):
        raise ResultError(f"nonfinite {field}")
    mantissa = re.split("[eE]", text, maxsplit=1)[0]
    if value == 0 and any(c in "123456789" for c in mantissa):
        raise ResultError(f"underflow changes nonzero {field} to zero")
    return value


def _cosine(a: list[float], b: list[float]) -> float:
    # Scaling avoids overflow for otherwise finite source values. This is an
    # arithmetic consistency check, not a substitute for native R replay.
    sa, sb = max(map(abs, a)), max(map(abs, b))
    if sa == 0 or sb == 0:
        return 0.0
    aa, bb = [x / sa for x in a], [x / sb for x in b]
    return math.fsum(x * y for x, y in zip(aa, bb)) / (
        math.sqrt(math.fsum(x * x for x in aa)) * math.sqrt(math.fsum(x * x for x in bb))
    )


def _display_row(row: list[float]) -> list[float]:
    lo, hi = min(row), max(row)
    return [0.0] * len(row) if hi == lo else [(x - lo) / (hi - lo) for x in row]


def inspect_csv(body: bytes, *, metric: str) -> dict:
    """Validate a source CSV and separate statistical from displayed quantities.

    Rows in author CSV may be in a seriation-dependent order. The returned
    matrices use the fixed source-map order, without dropping any body part.
    The metric is supplied from the independently bound producer/filename;
    it cannot be recovered or authenticated from the CSV's numeric cells.
    """
    if metric not in METRICS:
        raise ResultError("unrecognized source metric")
    if not isinstance(body, bytes) or not body or len(body) > MAX_CSV_BYTES:
        raise ResultError("empty, nonbytes, or oversized CSV")
    try:
        text = body.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ResultError("CSV must be UTF-8") from exc
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    try:
        if tuple(next(reader)) != COLUMNS:
            raise ResultError("source CSV columns or column order differ")
        cells: dict[tuple[str, str], tuple[float, float]] = {}
        names = set(BODY_PARTS)
        for row in reader:
            if len(row) != len(COLUMNS):
                raise ResultError("malformed CSV row")
            source, target, cosine_text, influence_text, same = row
            if source not in names or target not in names:
                raise ResultError("body-part support differs")
            key = (target, source)
            if key in cells:
                raise ResultError("duplicate target/source pair")
            if same not in ("TRUE", "FALSE") or (same == "TRUE") != (source == target):
                raise ResultError("incorrect source diagonal flag")
            influence = _number(influence_text, "influence")
            cosine = _number(cosine_text, "cosine_similarity")
            if metric == "influence_log_minmax" and not 0 <= influence <= 1:
                raise ResultError("minmax source influence outside [0,1]")
            if not -1 - COSINE_SERIALIZATION_ATOL <= cosine <= 1 + COSINE_SERIALIZATION_ATOL:
                raise ResultError("cosine outside [-1,1]")
            cells[key] = (influence, cosine)
        if len(cells) != len(BODY_PARTS) ** 2:
            raise ResultError("incomplete 14-by-14 source support")
    except (csv.Error, StopIteration) as exc:
        raise ResultError("malformed or missing CSV") from exc

    matrix = [[cells[target, source][0] for source in BODY_PARTS] for target in BODY_PARTS]
    cosine_matrix = [[cells[target, source][1] for source in BODY_PARTS] for target in BODY_PARTS]
    max_error = 0.0
    for i, target in enumerate(BODY_PARTS):
        for j, source in enumerate(BODY_PARTS):
            error = abs(cosine_matrix[i][j] - _cosine(matrix[i], matrix[j]))
            if error > COSINE_SERIALIZATION_ATOL:
                raise ResultError(f"cosine does not match statistical matrix at {target}/{source}")
            max_error = max(max_error, error)
    display = [_display_row(row) for row in matrix] if "minmax" in metric else [row[:] for row in matrix]
    diagonal = [matrix[i][i] for i in range(len(BODY_PARTS))]
    off_diagonal = [matrix[i][j] for i in range(len(BODY_PARTS)) for j in range(len(BODY_PARTS)) if i != j]
    return {
        "schema_version": "banc-sensory-effector-source-inspection/v1",
        "source_commit": SOURCE_COMMIT,
        "source_panel_sha256": SOURCE_PANEL_SHA256,
        "input_sha256": hashlib.sha256(body).hexdigest(),
        "input_bytes": len(body),
        "metric_declaration": metric,
        "metric_and_producer_authenticated": False,
        "body_parts": list(BODY_PARTS),
        "matrix_axes": {"rows": "effector_target", "columns": "sensory_source"},
        "statistical_paired_matrix": matrix,
        "paired_heatmap_display_matrix": display,
        "display_renormalized_on_paired_subset": "minmax" in metric,
        "source_cosine_matrix": cosine_matrix,
        "cosine_max_absolute_residual": max_error,
        "cosine_serialization_absolute_tolerance": COSINE_SERIALIZATION_ATOL,
        "same_body_part_values": diagonal,
        "different_body_part_values": off_diagonal,
        "support_counts": {"body_parts": 14, "cells": 196, "same": 14, "different": 182},
        "qualification": "source_table_shape_and_internal_arithmetic_only",
        "source_pipeline_reproduced": False,
        "primary_panel_selected": False,
        "reproduction_outcome": None,
        "improvement_outcome": None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--metric", choices=METRICS, required=True)
    args = parser.parse_args()
    try:
        with args.csv.open("rb") as handle:
            body = handle.read(MAX_CSV_BYTES + 1)
        result = inspect_csv(body, metric=args.metric)
    except (OSError, ResultError) as exc:
        parser.exit(2, f"result inspection refused: {exc}\n")
    print(json.dumps(result, allow_nan=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
