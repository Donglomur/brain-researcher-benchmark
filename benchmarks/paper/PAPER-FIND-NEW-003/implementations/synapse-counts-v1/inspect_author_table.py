"""Authenticate and reduce a local original-author evaluation count table.

No network, image processing, prediction matching, fitting or model execution.
The caller owns the external output location; authentic source bytes remain
outside this package.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path

from counts import CountError, reduce_rows, rows_from_csv

HERE = Path(__file__).resolve().parent


def inspect_table(source_path, pin):
    payload = Path(source_path).read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    if len(payload) != pin["bytes"] or digest != pin["sha256"]:
        raise CountError("Author count source size or SHA-256 differs from the frozen source")
    rows = rows_from_csv(payload)
    result = reduce_rows(rows, pin["cutout_rows"], pin.get("pooled_row"))
    geometry = []
    for row in rows:
        if "Resolution" not in row:
            continue
        vectors = [ast.literal_eval(row[key]) for key in ("Resolution", "Bbox start", "Bbox end")]
        if any(not isinstance(vector, tuple) or len(vector) != 3 or
               any(type(value) is not int for value in vector) for vector in vectors):
            raise CountError("Invalid source resolution/bounding-box tuple")
        resolution, start, end = vectors
        extent = [stop - begin for begin, stop in zip(start, end)]
        if min(resolution) <= 0 or min(extent) <= 0:
            raise CountError("Source geometry must have positive resolution and extent")
        geometry.append({"cutout_id": row["cutouts"], "resolution_nm": resolution,
                         "extent_voxels": extent,
                         "extent_nm": [size * step for size, step in zip(extent, resolution)],
                         "matches_majority_box_shape": extent == [128, 128, 16]})
    return {
        "schema": "banc-original-synapse-count-reduction/v1",
        "task_id": "PAPER-FIND-NEW-003",
        "source_sha256": digest,
        "source_commit": pin["commit"],
        "source_role": "published_author_baseline_counts",
        "qualification": "authenticated_source_count_reduction_only",
        "independent_animals": 1,
        "scored_unit": "synaptic_link_with_both_partners_correct",
        "uncertainty_unit": "cutout_conditional_on_one_fly",
        "candidate_scored": False,
        "author_detector_rerun": False,
        "matching_rules_recovered": False,
        "source_geometry": geometry,
        "geometry_interpretation": "literal source tuples; no coordinate repair or image retrieval",
        **result,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_csv", type=Path)
    parser.add_argument("--output", type=Path, required=True,
                        help="External evidence JSON; output must not exist")
    args = parser.parse_args()
    try:
        pin = json.loads((HERE / "source_pin.json").read_text())
        result = inspect_table(args.source_csv, pin)
        output = args.output.resolve()
        for parent in (HERE, *HERE.parents):
            if (parent / ".git").exists():
                if output.is_relative_to(parent):
                    raise CountError("Write authentic source reports outside the repository")
                break
        with output.open("x") as handle:
            json.dump(result, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
    except (OSError, ValueError, KeyError) as error:
        parser.exit(2, f"Author count inspection failed: {error}\n")
    print(json.dumps({"source_sha256": result["source_sha256"],
                      "cutout_count": result["cutout_count"],
                      "qualification": result["qualification"]}))


if __name__ == "__main__":
    main()
