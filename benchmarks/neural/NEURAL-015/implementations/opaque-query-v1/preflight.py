#!/usr/bin/env python3
"""Check an opaque NEURAL-015 response using only its delivered public query.

No reference, operator key, targets, observations or scoring module are loaded.
The caller must obtain the query through an authenticated operator channel.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys


TASK = "NEURAL-015"
PROFILE = "opaque-word-onset-query/v1"
GRID_FIELDS = ("grid_start_sample", "grid_stop_sample_exclusive", "grid_step_samples", "n_grid_points")


class ContractError(ValueError):
    """The delivered query or complete response has an invalid public schema."""


def require(condition, message):
    if not condition:
        raise ContractError(message)


def exact(value, fields, name):
    require(isinstance(value, dict) and set(value) == set(fields), name + ": exact fields required")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode("utf-8")).hexdigest()


def sha(value, name):
    require(isinstance(value, str) and len(value) == 64
            and all(c in "0123456789abcdef" for c in value), name + ": lowercase SHA256 required")


def validate_submission(query, submission):
    """Validate complete response coverage without modifying or scoring values.

    Hash binding detects a response for a different supplied query. It cannot
    authenticate the operator, HMAC aliases, observations or hidden targets.
    """
    exact(query, ("task_id", "delivery_profile", "protocol_sha256", "recordings"), "query")
    require(query["task_id"] == TASK and query["delivery_profile"] == PROFILE, "query task/profile mismatch")
    sha(query["protocol_sha256"], "protocol hash")
    rows = query["recordings"]
    require(isinstance(rows, list) and len(rows) == 26, "query must contain all26 case grids")
    by_case = {}
    for row in rows:
        exact(row, ("case_id", "fold_id", *GRID_FIELDS), "query grid")
        cid = row["case_id"]
        sha(cid, "case ID")
        sha(row["fold_id"], "fold ID")
        require(cid not in by_case, "duplicate query case")
        for name in GRID_FIELDS:
            require(type(row[name]) is int, name + ": integer required")
        start, stop, step, count = (row[name] for name in GRID_FIELDS)
        require(start >= 0 and stop > start and step > 0, "invalid query grid bounds")
        require(count == (stop - start + step - 1) // step, "grid point count mismatch")
        by_case[cid] = row

    exact(submission, ("task_id", "delivery_profile", "query_sha256", "predictions"), "submission")
    require(submission["task_id"] == TASK and submission["delivery_profile"] == PROFILE,
            "submission task/profile mismatch")
    sha(submission["query_sha256"], "query hash")
    require(submission["query_sha256"] == digest(query), "submission query binding mismatch")
    predictions = submission["predictions"]
    require(isinstance(predictions, list) and len(predictions) == len(by_case),
            "submission must answer all26 cases exactly once")
    seen = set()
    for row in predictions:
        exact(row, ("case_id", "fold_id", "neural"), "prediction")
        cid = row["case_id"]
        require(isinstance(cid, str) and cid in by_case and cid not in seen, "unknown or duplicate response case")
        target = by_case[cid]
        require(row["fold_id"] == target["fold_id"], "response fold mismatch")
        values = row["neural"]
        require(isinstance(values, list) and len(values) == target["n_grid_points"],
                "response must cover the complete ordered grid")
        # This bound rejects NaN, infinity and booleans without converting an
        # arbitrarily large JSON integer to float.
        require(all(type(value) in (int, float) and 0 <= value <= 1 for value in values),
                "neural probabilities must be finite numbers in [0,1]")
        seen.add(cid)
    require(seen == set(by_case), "response case coverage mismatch")
    return {"task_id": TASK, "delivery_profile": PROFILE,
            "query_sha256": digest(query), "submission_sha256": digest(submission),
            "recordings_checked": len(by_case),
            "grid_probabilities_checked": sum(row["n_grid_points"] for row in rows),
            "validation": "public-schema-only", "operator_provenance_authenticated": False,
            "protected_score_computed": False, "scientific_admission": False}


def load_json(path):
    def unique_pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON key: " + key)
            result[key] = value
        return result

    def nonfinite(value):
        raise ContractError("nonfinite JSON value: " + value)

    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=unique_pairs,
                      parse_constant=nonfinite)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", help="delivered opaque query JSON")
    parser.add_argument("submission", help="complete opaque response JSON")
    parser.add_argument("--output", required=True, help="new local validation report")
    args = parser.parse_args(argv)
    try:
        output = Path(args.output)
        require(not output.exists() and not output.is_symlink(), "output must be a fresh file")
        result = validate_submission(load_json(args.query), load_json(args.submission))
        encoded = (json.dumps(result, indent=2, allow_nan=False) + "\n").encode("utf-8")
        fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(encoded)
    except (ValueError, OSError) as error:
        print("NEURAL-015 response rejected: " + str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
