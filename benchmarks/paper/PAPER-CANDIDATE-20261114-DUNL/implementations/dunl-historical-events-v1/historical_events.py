"""Historical DUNL event endpoint on the explicit current-code default panel.

No Torch import, model inference, data conversion, or publication parity claim.
The owner selects all identities and targets; the participant supplies codes.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import stat


PROFILE = "dunl_current_code_defaults_30_20_11_576_v1"
SPLITS = {"train": 30, "test": 20}
CHANNELS = 11
CODE_SAMPLES = 576  # 3000 / 5 - 25 + 1
TOL_BINS = 2  # inclusive 10 ms on the source's 5 ms grid
SCHEDULE = tuple(100 + 25 * k for k in range(16))
MAX_BYTES = 16 * 1024 * 1024


class InputError(ValueError):
    pass


def _require(condition, message):
    if not condition:
        raise InputError(message)


def _keys(value, expected):
    _require(type(value) is dict and set(value) == set(expected), "unexpected fields")


def _ids(values, count):
    _require(type(values) is list and len(values) == count, "identity count mismatch")
    _require(all(type(x) is str and 0 < len(x) <= 128 and x.isascii()
                 and all(c.isalnum() or c in "_.:-" for c in x) for x in values),
             "invalid identity")
    _require(len(set(values)) == count, "duplicate identity")


def positive_support(code):
    """Validate one source nonnegative single-kernel vector, retaining all bins."""
    _require(type(code) is list and len(code) == CODE_SAMPLES, "code length mismatch")
    _require(all(type(v) in (int, float) and math.isfinite(v) and v >= 0 for v in code),
             "codes must be finite nonnegative numbers")
    return frozenset(i for i, v in enumerate(code) if v > 0)


def row_counts(target, predicted):
    """Count predictions in the UNION of inclusive target neighborhoods.

    Both arguments are sets of occupied bins. One prediction is counted once,
    even if two target neighborhoods overlap; multiple predictions may hit one
    target. This is deliberately not a one-to-one event matching metric.
    """
    near = {i + delta for i in target for delta in range(-TOL_BINS, TOL_BINS + 1)}
    hits = len(predicted & near)
    return {"target_count": len(target), "prediction_count": len(predicted),
            "neighborhood_hit_count": hits, "outside_neighborhood_count": len(predicted) - hits}


def aggregate(rows):
    """The source averages row fractions, then clips the aggregate hit at one."""
    _require(bool(rows), "empty aggregation")
    hit = sum((Fraction(r["neighborhood_hit_count"], r["target_count"])
               if r["target_count"] else Fraction(0)) for r in rows) / len(rows)
    false = sum((Fraction(r["outside_neighborhood_count"], r["prediction_count"])
                 if r["prediction_count"] else Fraction(1)) for r in rows) / len(rows)
    return {"rows": len(rows), "mean_hit_before_clip": float(hit),
            "missed_event_fraction": float(1 - min(hit, 1)),
            "false_event_fraction": float(false),
            "mean_hit_exact": [hit.numerator, hit.denominator],
            "mean_false_exact": [false.numerator, false.denominator]}


def context_id(owner):
    """Public geometry/identity binding only; no target values enter this hash."""
    metadata = {k: owner[k] for k in ("profile", "channel_ids", "trial_ids")}
    body = json.dumps(metadata, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")
    return hashlib.sha256(body).hexdigest()


def evaluate(owner, submission, *, mode):
    """Evaluate standard or group caller geometry on every declared default row.

    Owner target_codes: split -> [trial][one kernel][576].
    Submission codes: split -> [trial][11 channels][one kernel][576].
    Modes are chosen by the evaluator, never inferred from candidate labels.
    """
    _require(mode in ("standard", "group"), "unknown source caller")
    _keys(owner, ("profile", "channel_ids", "trial_ids", "target_codes"))
    _require(owner["profile"] == PROFILE, "unknown profile")
    _ids(owner["channel_ids"], CHANNELS)
    _keys(owner["trial_ids"], SPLITS)
    _keys(owner["target_codes"], SPLITS)
    for split, count in SPLITS.items():
        _ids(owner["trial_ids"][split], count)
    _require(not set(owner["trial_ids"]["train"]) & set(owner["trial_ids"]["test"]),
             "trial identity crosses train/test")
    _keys(submission, ("profile", "context_id", "channel_ids", "trial_ids", "codes"))
    _require(submission["profile"] == PROFILE and submission["context_id"] == context_id(owner),
             "submission context mismatch")
    _require(submission["channel_ids"] == owner["channel_ids"] and
             submission["trial_ids"] == owner["trial_ids"], "ordered identity mismatch")
    _keys(submission["codes"], SPLITS)
    result = {"schema": "dunl_historical_events_v1", "profile": PROFILE,
              "context_id": context_id(owner), "caller": mode,
              "bin_period_us": 5000, "inclusive_tolerance_us": 10000,
              "row_order": "trial_major_channel_minor", "splits": {},
              "qualification": "current_source_mathematical_endpoint_only",
              "publication_parity": False}
    for split, count in SPLITS.items():
        targets, codes = owner["target_codes"][split], submission["codes"][split]
        _require(type(targets) is list and len(targets) == count and
                 type(codes) is list and len(codes) == count, "trial count mismatch")
        rows, schedule_rows = [], []
        for t in range(count):
            _require(type(targets[t]) is list and len(targets[t]) == 1,
                     "exactly one target kernel required")
            truth = positive_support(targets[t][0])
            _require(type(codes[t]) is list and len(codes[t]) == CHANNELS,
                     "all eleven allocated channels required")
            supports = []
            for channel in codes[t]:
                _require(type(channel) is list and len(channel) == 1,
                         "exactly one prediction kernel required")
                supports.append(positive_support(channel[0]))
            # The group caller computes the L2 norm over channels then repeats
            # it over channels. Its mathematical positive support is this union.
            # We do not claim floating-point norm parity for underflow/overflow.
            if mode == "group":
                supports = [frozenset().union(*supports)] * CHANNELS
            for n, predicted in enumerate(supports):
                identity = {"trial_id": owner["trial_ids"][split][t],
                            "channel_id": owner["channel_ids"][n]}
                rows.append(identity | row_counts(truth, predicted))
                schedule_rows.append(identity | row_counts(truth, frozenset(SCHEDULE)))
        result["splits"][split] = {
            "candidate": aggregate(rows), "public_schedule": aggregate(schedule_rows),
            "candidate_rows": rows, "public_schedule_rows": schedule_rows}
    return result


def _pairs(items):
    result = {}
    for key, value in items:
        _require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(_):
    raise InputError("nonfinite JSON constant")


def read_json(path):
    """Bounded no-follow regular-file read; paths must be operator controlled."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        _require(stat.S_ISREG(before.st_mode) and before.st_size <= MAX_BYTES,
                 "input must be a bounded regular file")
        chunks, remaining = [], MAX_BYTES + 1
        while remaining:
            part = os.read(fd, min(65536, remaining))
            if not part:
                break
            chunks.append(part)
            remaining -= len(part)
        body = b"".join(chunks)
        after = os.fstat(fd)
        _require(len(body) == before.st_size and len(body) <= MAX_BYTES and
                 all(getattr(before, f) == getattr(after, f) for f in
                     ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")),
                 "input changed during read")
    finally:
        os.close(fd)
    try:
        value = json.loads(body.decode("utf-8"), object_pairs_hook=_pairs,
                           parse_constant=_reject_constant)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise InputError("invalid JSON input") from exc
    return value, hashlib.sha256(body).hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", type=Path, required=True)
    parser.add_argument("--owner-sha256", required=True)
    parser.add_argument("--submission", type=Path, required=True)
    parser.add_argument("--mode", choices=("standard", "group"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        owner, digest = read_json(args.owner)
        _require(digest == args.owner_sha256, "owner digest mismatch")
        submission, _ = read_json(args.submission)
        report = evaluate(owner, submission, mode=args.mode)
        report["owner_sha256"] = digest
        body = (json.dumps(report, indent=2, allow_nan=False) + "\n").encode("utf-8")
        fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(body)
    except (InputError, OSError, OverflowError, RecursionError):
        print("historical event evaluation refused")
        return 2
    print("historical event evaluation complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
