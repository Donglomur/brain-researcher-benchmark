"""Operator-side descriptive comparison of all original cardiac decoding cells.

Exported numbers and matching declared support hashes do not authenticate a
decoder execution or its recording/partition mapping. No scientific decision is
made. The original published CSV must pass the existing source authenticator.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import statistics

_SOURCE = Path(__file__).resolve().parent.parent / "published-decoding-panel-v1/published_panel.py"
_SPEC = importlib.util.spec_from_file_location("cardiac_published_panel", _SOURCE)
P = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(P)

TASK_ID = "PAPER-ROOT-ADD-016"
SCHEMA = "cardiac_decoding_score_export_v1"
ROLES = ("author_export", "paper_data", "paper_data_author_code")
KEYS = tuple((str(i), d, c) for d in P.DEVICES for c in P.CONDITIONS
             for i in range(P.N_SUBJECTS))
CONTRASTS = {
    "author_minus_published": ("author_export", "published"),
    "paper_data_minus_published": ("paper_data", "published"),
    "paper_data_author_code_minus_published": ("paper_data_author_code", "published"),
    "paper_data_minus_author": ("paper_data", "author_export"),
    "paper_data_author_code_minus_author": ("paper_data_author_code", "author_export"),
    "paper_data_author_code_minus_paper_data": ("paper_data_author_code", "paper_data"),
}
MAX_EXPORT_BYTES = 65536


class ComparisonError(ValueError):
    """An input cannot support the complete declared comparison."""


def _require(condition, message):
    if not condition:
        raise ComparisonError(message)


def _index(rows):
    _require(type(rows) is list, "Scores must be a list")
    values = {}
    for row in rows:
        _require(type(row) is dict and set(row) == {"subject_id", "device", "condition", "r"},
                 "Unexpected score fields")
        _require(all(type(row[name]) is str for name in ("subject_id", "device", "condition")),
                 "Coordinate identifiers must be exact strings")
        key = row["subject_id"], row["device"], row["condition"]
        _require(key in KEYS, "Unknown original published coordinate")
        _require(key not in values, "Duplicate coordinate")
        value = row["r"]
        _require(type(value) in (int, float) and math.isfinite(value) and -1 <= value <= 1,
                 "Pearson r must be finite in [-1, 1]")
        values[key] = float(value)
    _require(set(values) == set(KEYS), "Expected every original 20 x 2 x 3 coordinate")
    return values


def validate_export(document, role):
    _require(type(document) is dict and set(document) == {
        "schema", "task_id", "role", "declared_support_sha256", "producer_sha256", "scores"},
        "Unexpected export fields")
    _require(document["schema"] == SCHEMA and document["task_id"] == TASK_ID,
             "Wrong export schema or task")
    _require(role in ROLES and document["role"] == role, "Export role mismatch")
    for name in ("declared_support_sha256", "producer_sha256"):
        _require(type(document[name]) is str and re.fullmatch(r"[0-9a-f]{64}", document[name]),
                 "Invalid " + name)
    return _index(document["scores"])


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "Duplicate JSON field")
        result[key] = value
    return result


def load_export(path, role):
    with Path(path).open("rb") as stream:
        data = stream.read(MAX_EXPORT_BYTES + 1)
    _require(len(data) <= MAX_EXPORT_BYTES, "Export exceeds 64 KiB")
    try:
        document = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ComparisonError("Malformed score export: " + str(exc)) from exc
    validate_export(document, role)
    return document, {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def compare(published_rows, exports):
    """Arithmetic only; callers supply authenticated published rows at the CLI.

    This API also accepts generated controls. It does not declare their origin
    authentic. Exact original aliases enforce table support, not recording joins.
    """
    _require(type(exports) is dict and set(exports) == set(ROLES), "All three export roles required")
    panels = {"published": _index(published_rows)}
    panels.update({role: validate_export(exports[role], role) for role in ROLES})
    supports = {exports[role]["declared_support_sha256"] for role in ROLES}
    _require(len(supports) == 1, "Exported recording/partition support declarations differ")
    cells = []
    for device in P.DEVICES:
        for condition in P.CONDITIONS:
            rows = []
            for subject in range(P.N_SUBJECTS):
                key = str(subject), device, condition
                scores = {role: panel[key] for role, panel in panels.items()}
                deltas = {name: scores[left] - scores[right]
                          for name, (left, right) in CONTRASTS.items()}
                rows.append({"subject_id": str(subject), "scores": scores, "paired_deltas_r": deltas})
            summaries = {}
            for name in CONTRASTS:
                values = [row["paired_deltas_r"][name] for row in rows]
                summaries[name] = {"mean_paired_delta_r": statistics.fmean(values),
                                   "sample_sd_paired_delta_r": statistics.stdev(values)}
            cells.append({"device": device, "condition": condition, "n_participants": 20,
                          "participants": rows, "descriptive_paired_summaries": summaries})
    return {
        "schema": "cardiac_complete_paired_decoding_comparison_v1", "task_id": TASK_ID,
        "qualification": "descriptive_export_comparison_only",
        "published_input_authentication": "not_established_by_arithmetic_api",
        "n_participants": 20, "n_coordinates_per_panel": 120, "independent_unit": "participant",
        "metric": "exported original-test Pearson r", "scalar_aggregation": "none",
        "declared_support_sha256": next(iter(supports)),
        "export_producers": {role: exports[role]["producer_sha256"] for role in ROLES},
        "cells": cells,
        "reproduction": None, "improvement": None, "assistance_effect": None,
        "limits": [
            "All original released aliases and six conditions are retained; aliases are not authenticated recording IDs.",
            "Matching support hashes are supplied declarations, not proof of recording/fold/channel/exclusion equivalence.",
            "Author export is supplied arithmetic input, not a verified independently executed author baseline.",
            "No confidence interval, multiplicity rule, meaningful-gain margin, tolerance or superiority decision is inferred.",
            "The two assistance exports do not demonstrate matched participant execution or a causal assistance effect.",
            "This operator report includes evaluator-only published scores and must not enter participant inputs.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--published", required=True, type=Path)
    for role in ROLES:
        parser.add_argument("--" + role.replace("_", "-"), required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    published = P.load_published(args.published)
    exports, receipts = {}, {}
    for role in ROLES:
        exports[role], receipts[role] = load_export(getattr(args, role), role)
    result = compare(published, exports)
    result["published_input_authentication"] = "exact_existing_published_source_hash_and_byte_count"
    result["inputs"] = {"published": {"bytes": P.SOURCE_BYTES, "sha256": P.SOURCE_SHA256}, **receipts}
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"qualification": result["qualification"], "n_coordinates_per_panel": 120}))


if __name__ == "__main__":
    main()
