"""Trace the deposited coactivity script's response/animal row permutations.

This audits source table construction. It does not fit or score a model, fix
author results, or establish that an authentic dataset contains a mismatch.
Input rows must already match the source's per-session pair-array order.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

SOURCE_SHA256 = "ca6c2b52ecb07662722a81b78c513708a2ba36177193f6b9c5a5f562d9fb0c83"
AREA_CUTOFF_UM2 = 1.0960


def _number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def validate(rows):
    if not isinstance(rows, list):
        raise ValueError("rows must be a list in native pair-array order")
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("every row must be an object")
        for field in ("row_id", "animal_id"):
            if not isinstance(row.get(field), str) or not row[field]:
                raise ValueError(f"missing {field}")
        if row["row_id"] in seen:
            raise ValueError("duplicate row_id")
        seen.add(row["row_id"])
        if row.get("session") not in ("early", "middle"):
            raise ValueError("session must be early or middle")
        if row.get("stability") not in ("stable", "eliminated"):
            raise ValueError("only source stable/eliminated tagged rows are accepted")
        for field in ("distance_um", "area_um2"):
            if field not in row or (row[field] is not None and not _number(row[field])):
                raise ValueError(f"{field} must be nonnegative finite or null for source NaN")


def _compare(response_rows, animal_tag_rows):
    paired = list(zip(response_rows, animal_tag_rows))
    mismatches = [
        {"position_one_based": index, "response_row_id": response["row_id"],
         "animal_tag_row_id": tag["row_id"], "expected_animal_id": response["animal_id"],
         "source_animal_id": tag["animal_id"]}
        for index, (response, tag) in enumerate(paired, 1)
        if response["animal_id"] != tag["animal_id"]
    ]
    return {
        "response_row_ids": [row["row_id"] for row in response_rows],
        "animal_tag_row_ids": [row["row_id"] for row in animal_tag_rows],
        "response_rows": len(response_rows), "animal_tag_rows": len(animal_tag_rows),
        "table_length_mismatch": len(response_rows) != len(animal_tag_rows),
        "paired_animal_mismatches": mismatches,
        "animal_alignment_holds_for_supplied_rows": len(response_rows) == len(animal_tag_rows) and not mismatches,
    }


def audit(rows):
    """Replay the original permutations without reading coactivity responses.

    Source ClusteringbySpineSize.m lines 235-264 and 360-384. Its MATLAB
    0:5:50 loop includes distances in [50,55), not just distances <=50.
    """
    validate(rows)
    def select(bin_start, session, stability=None, size=None):
        result = []
        for row in rows:
            distance, area = row["distance_um"], row["area_um2"]
            if distance is None or not bin_start <= distance < bin_start + 5:
                continue
            if row["session"] != session or (stability and row["stability"] != stability):
                continue
            if size and (area is None or ((area <= AREA_CUTOFF_UM2) != (size == "small"))):
                continue
            result.append(row)
        return result

    # The original animal vector is binned, with early followed by middle.
    tags = [row for b in range(0, 51, 5) for s in ("early", "middle") for row in select(b, s)]
    # Responses are concatenated by stability and size after the bin loops.
    size_rows = [row for state in ("eliminated", "stable") for size in ("small", "large")
                 for b in range(0, 51, 5) for s in ("early", "middle") for row in select(b, s, state, size)]
    # The session model reuses AnimalTags_for_stats at source line 382.
    session_rows = [row for state in ("eliminated", "stable") for s in ("early", "middle")
                    for b in range(0, 51, 5) for row in select(b, s, state)]
    included = {row["row_id"] for row in tags}
    return {"schema_version": "rep011-source-row-audit-v1", "source_sha256": SOURCE_SHA256,
            "scope": "static source row-permutation audit; no authentic source execution or scientific score",
            "input_rows": len(rows), "area_cutoff_um2": AREA_CUTOFF_UM2,
            "source_distance_interval_um": "[0,55)",
            "distance_excluded_row_ids": [row["row_id"] for row in rows if row["row_id"] not in included],
            "size_models_lines_260_264": _compare(size_rows, tags),
            "session_model_lines_382_384": _compare(session_rows, tags)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.input.resolve() == args.output.resolve():
        parser.error("output must be a new file")
    result = audit(json.loads(args.input.read_text()))
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    main()
