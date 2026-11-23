#!/usr/bin/env python3
"""Check all Movie10 predictions against frozen public queries, without targets."""
from __future__ import annotations

import argparse
from pathlib import Path

import evaluate as ev


def validate_queries(queries):
    """Validate the complete public strict_v2 identities and retained row ordering.

    This establishes internal consistency, not source authenticity. The supplied
    SHA256 must have been frozen by the operator before prediction generation.
    """
    ev.fields(queries, ev.CASES)
    for case_id in ev.CASES:
        query = queries[case_id]
        ev.fields(query, ("schema", "condition", "case_id", "subject", "held_film",
                          "source_commit", "shape", "dtype", "tr_seconds",
                          "parcel_order", "runs"))
        subject, film = case_id.split("_hold-")
        expected = {
            "schema": "neural039_query_v2", "condition": ev.CONDITION,
            "case_id": case_id, "subject": subject, "held_film": film,
            "source_commit": ev.SOURCE_COMMIT, "dtype": "<f4",
            "parcel_order": "native_subject_hdf5_columns_0_through_999",
        }
        if any(query[key] != value for key, value in expected.items()):
            raise ValueError("Public query identity differs")
        if type(query["tr_seconds"]) not in (int, float) or query["tr_seconds"] != 1.49:
            raise ValueError("Original 1.49-second TR required")
        shape = query["shape"]
        if (type(shape) is not list or len(shape) != 2 or
                any(type(value) is not int for value in shape) or
                shape[0] <= 0 or shape[1] != 1000):
            raise ValueError("Complete time-by-1000 prediction shape required")
        runs = query["runs"]
        if type(runs) is not list or not runs:
            raise ValueError("Complete native run list required")
        keys, identities, offset = [], set(), 0
        for run in runs:
            ev.fields(run, ("key", "native_samples", "start", "stop", "offset"))
            key = run["key"]
            match = ev.KEY.fullmatch(key) if type(key) is str else None
            if match is None or match.group(2) != film:
                raise ValueError("Native run must belong to the held film")
            _, _, segment, viewing = match.groups()
            identity = (int(segment), int(viewing or 1))
            if identity[0] < 1 or identity in identities:
                raise ValueError("Duplicate or invalid native segment/viewing")
            if film in ("life", "figures") and viewing is None:
                raise ValueError("Repeated movies need explicit native run identity")
            if film in ("bourne", "wolf") and viewing not in (None, "1"):
                raise ValueError("Unexpected second viewing")
            identities.add(identity)
            keys.append(key)
            if any(type(run[name]) is not int for name in ("native_samples", "start", "stop", "offset")):
                raise ValueError("Integer native row metadata required")
            if (run["native_samples"] <= 15 or run["start"] != 8 or
                    run["stop"] != run["native_samples"] - 5 or run["offset"] != offset):
                raise ValueError("Exact strict_v2 guards and contiguous offsets required")
            offset += run["stop"] - run["start"]
        if keys != sorted(keys) or offset != shape[0]:
            raise ValueError("Lexicographic native run order and complete extent required")
        if film in ("life", "figures") and any((segment, 3 - viewing) not in identities
                                               for segment, viewing in identities):
            raise ValueError("Both original viewings must remain in the same film")
    return queries


def preflight(query_path, query_sha256, submission_root, np):
    """Never accepts or opens a source-response root or operator panel."""
    body = ev.read_bytes(query_path, 1024 * 1024)
    if ev.digest(body) != query_sha256:
        raise ValueError("Frozen public query digest differs")
    query = validate_queries(ev.strict_json(body))
    _, pins = ev.admit(submission_root, query, np)
    return {
        "schema": "neural039_public_prediction_preflight_v1",
        "status": "valid_predictions", "condition": ev.CONDITION,
        "public_queries_sha256": query_sha256,
        "cases": len(ev.CASES), "prediction_pins": pins,
        "primary_score": None, "target_file_opens": 0,
        "source_authenticity_verified": False,
        "runtime_or_training_provenance_verified": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--queries-sha256", required=True)
    parser.add_argument("--submission-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    import numpy as np
    result = preflight(args.queries, args.queries_sha256, args.submission_dir, np)
    with ev.ordinary(args.output).open("xb") as handle:
        handle.write(ev.canonical(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
