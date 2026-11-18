#!/usr/bin/env python3
"""Opaque identities for the existing complete-cohort NEURAL-015 evaluator.

This is an operator-side codec, not an execution sandbox or signal renderer.
Only generated controls have exercised it; native scientific admission is held.
"""
import argparse
import hashlib
import hmac
import importlib.util
import json
import os
from pathlib import Path
import sys


BASE = Path(__file__).resolve().parents[1] / "initial-evaluator-v1"
PINS = {
    "evaluator.py": "366dff43d2624a1cbdf7651a7f0ef00f0dad6cae01480e75d600a7c969096f2a",
    "catalog.json": "31aab0168d2f6dcf2c230a6649320d03f53f415b726991eb8f12c02d3a800942",
}
for filename, expected in PINS.items():
    if hashlib.sha256((BASE / filename).read_bytes()).hexdigest() != expected:
        raise RuntimeError("NEURAL-015 predecessor source changed: " + filename)
_spec = importlib.util.spec_from_file_location("neural015_opaque_base", BASE / "evaluator.py")
e = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(e)
ContractError = e.ContractError
PROFILE = "opaque-word-onset-query/v1"
GRID_FIELDS = ("grid_start_sample", "grid_stop_sample_exclusive", "grid_step_samples", "n_grid_points")


def _identity_map(reference, secret):
    e.require(type(secret) is bytes and len(secret) == 32,
              "operator alias secret must contain exactly 32 bytes")
    original = e.public_query(reference)
    # Include only observation identity and the existing target-independent grid.
    # Onset labels, transcript/alignment hashes and comparator values are absent.
    context = e.digest({
        "profile": PROFILE,
        "query": original,
        # Public grids expose only the test assignment. Bind training/unused
        # membership too, without making collection depend on label values.
        "folds": sorted([
            {"fold_id": fold["fold_id"],
             **{part: sorted(fold[part]) for part in ("train", "test", "unused")}}
            for fold in reference["folds"]], key=lambda fold: fold["fold_id"]),
        "neural_inputs": sorted((r["recording_id"], r["neural_sha256"])
                                for r in reference["recordings"]),
    })

    def alias(kind, value):
        message = json.dumps([PROFILE, e.TASK, context, kind, value],
                             separators=(",", ":"), ensure_ascii=True).encode("ascii")
        return hmac.new(secret, message, hashlib.sha256).hexdigest()

    by_case = {}
    fold_ids = {}
    for row in original["recordings"]:
        cid = alias("case", row["recording_id"])
        fid = alias("fold", row["fold_id"])
        e.require(cid not in by_case, "opaque case collision")
        e.require(fid not in fold_ids or fold_ids[fid] == row["fold_id"],
                  "opaque fold collision")
        by_case[cid] = row
        fold_ids[fid] = row["fold_id"]
    records = [{"case_id": cid, "fold_id": alias("fold", row["fold_id"]),
                **{field: row[field] for field in GRID_FIELDS}}
               for cid, row in sorted(by_case.items())]
    public = {"task_id": e.TASK, "delivery_profile": PROFILE,
              "protocol_sha256": original["protocol_sha256"], "recordings": records}
    return original, public, by_case, fold_ids


def public_query(reference, secret):
    """Return all26 grids with keyed identities and label-independent order.

    The caller retains the reference and secret in operator-only storage.
    Duration, grouping and eventual signal content can still identify a source.
    """
    return _identity_map(reference, secret)[1]


def restore_submission(reference, secret, submission):
    """Validate opaque responses and restore original IDs in operator memory.

    The restored object contains source IDs and must never be sent to entrants.
    No output row is dropped, padded, clipped or reweighted.
    """
    original, query, by_case, fold_ids = _identity_map(reference, secret)
    e.exact(submission, ["task_id", "delivery_profile", "query_sha256", "predictions"],
            "opaque submission")
    e.require(submission["task_id"] == e.TASK, "task ID mismatch")
    e.require(submission["delivery_profile"] == PROFILE, "delivery profile mismatch")
    e.sha(submission["query_sha256"], "opaque query SHA256")
    e.require(submission["query_sha256"] == e.digest(query), "opaque query binding mismatch")
    predictions = submission["predictions"]
    e.require(isinstance(predictions, list), "prediction list required")
    seen, restored = set(), []
    for row in predictions:
        e.exact(row, ["case_id", "fold_id", "neural"], "opaque prediction")
        cid, fid = row["case_id"], row["fold_id"]
        e.require(isinstance(cid, str) and cid in by_case and cid not in seen,
                  "unknown or duplicate opaque case ID")
        seen.add(cid)
        target = by_case[cid]
        e.require(isinstance(fid, str) and fid in fold_ids
                  and fold_ids[fid] == target["fold_id"], "opaque fold mismatch")
        values = row["neural"]
        e.require(isinstance(values, list) and len(values) == target["n_grid_points"],
                  "prediction must cover the exact complete grid")
        for value in values:
            e.require(0 <= e.finite(value, "neural probability") <= 1,
                      "neural probability outside [0,1]")
        restored.append({"recording_id": target["recording_id"],
                         "fold_id": target["fold_id"], "neural": list(values)})
    e.require(seen == set(by_case), "all26 opaque cases must be answered exactly once")
    restored.sort(key=lambda row: row["recording_id"])
    return {"task_id": e.TASK, "query_sha256": e.digest(original), "predictions": restored}


def evaluate(reference, secret, submission):
    """Use the unchanged predecessor estimator after exact identity restoration."""
    restored = restore_submission(reference, secret, submission)
    result = e.evaluate(reference, restored)
    return {"delivery_profile": PROFILE,
            "opaque_query_sha256": submission["query_sha256"],
            "explicit_source_ids_removed_from_query": True,
            "access_isolation_qualified": False,
            "scientific_admission": False,
            "score": result}


def _write_new(path, result):
    payload = (json.dumps(result, indent=2, allow_nan=False) + "\n").encode("utf-8")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(payload)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("query", "score"))
    parser.add_argument("reference", help="private operator reference JSON")
    parser.add_argument("--key-file", required=True, help="private32-byte binary per-run secret")
    parser.add_argument("--submission", help="opaque response JSON for scoring")
    parser.add_argument("--output", required=True, help="new output file; never overwritten")
    args = parser.parse_args(argv)
    try:
        reference = e.load_json(args.reference)
        # Bound the key read and reject extra bytes rather than silently truncating.
        with open(args.key_file, "rb") as stream:
            secret = stream.read(33)
        if args.command == "query":
            e.require(args.submission is None, "query export does not accept a submission")
            result = public_query(reference, secret)
        else:
            e.require(args.submission is not None, "score requires --submission")
            result = evaluate(reference, secret, e.load_json(args.submission))
        _write_new(args.output, result)
    except (ContractError, OSError, json.JSONDecodeError) as exc:
        print("NEURAL-015 opaque delivery rejected: " + str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
