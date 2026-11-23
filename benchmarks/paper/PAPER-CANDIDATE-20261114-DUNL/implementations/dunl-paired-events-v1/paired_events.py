"""Matched DUNL event comparisons on the current-code default panel only."""
from __future__ import annotations

import argparse
from fractions import Fraction
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import stat
import types

ENDPOINT_BYTES = 9780
ENDPOINT_SHA256 = "ddfa29861f8d942b4dd37bac4ca8163c084e7be476bdf5ddee2e31c40b619df0"


class Refusal(ValueError):
    pass


@lru_cache(maxsize=1)
def endpoint():
    """Load only the previously published endpoint's captured source bytes."""
    path = Path(__file__).resolve().parent.parent / "dunl-historical-events-v1" / "historical_events.py"
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size != ENDPOINT_BYTES:
            raise Refusal("published endpoint missing or changed")
        raw = handle.read(ENDPOINT_BYTES + 1)
    if len(raw) != ENDPOINT_BYTES or hashlib.sha256(raw).hexdigest() != ENDPOINT_SHA256:
        raise Refusal("published endpoint identity mismatch")
    module = types.ModuleType("dunl_paired_original_endpoint")
    module.__file__ = str(path)
    exec(compile(raw, str(path), "exec"), module.__dict__)
    return module


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def rational(value):
    return {"value": float(value), "exact": [value.numerator, value.denominator]}


def compare(owner, candidate, reference, *, mode):
    """Score two full submissions on one owner and one operator-selected mode.

    The reference is supplied by the operator. Its author-model identity,
    training lineage and competence are not established by these arithmetic
    comparisons. No mode, threshold or split is selected from the result.
    """
    h = endpoint()
    # The original evaluator validates the complete owner and each ordered
    # submission, including every channel, trial, kernel and sample.
    candidate_report = h.evaluate(owner, candidate, mode=mode)
    reference_report = h.evaluate(owner, reference, mode=mode)
    report = {
        "schema": "dunl_paired_current_code_events_v1",
        "profile": h.PROFILE, "context_id": h.context_id(owner), "caller": mode,
        "endpoint_sha256": ENDPOINT_SHA256,
        "content_sha256": {"owner": digest(owner), "candidate": digest(candidate),
                           "reference": digest(reference)},
        "content_digest_scope": "canonical in-memory values, not input-file bytes",
        "row_order": "trial_major_channel_minor", "splits": {},
        "delta_convention": "candidate minus reference; negative values mean lower missed/false fractions under the source convention",
        "comparison_scope": "current-source mathematical endpoint only",
        "source_runtime_parity_verified": False, "authentic_cohort_verified": False,
        "reference_training_lineage_verified": False, "publication_parity": False,
        "same_task_improvement_established": False, "scientific_qualification": False,
        "minimum_effect_rule": None, "biological_uncertainty": None,
        "scalarized_score": None,
    }
    for split in h.SPLITS:
        c = candidate_report["splits"][split]
        r = reference_report["splits"][split]
        c_hit, r_hit = (Fraction(*x["candidate"]["mean_hit_exact"]) for x in (c, r))
        c_false, r_false = (Fraction(*x["candidate"]["mean_false_exact"]) for x in (c, r))
        # Clip only the complete row mean, exactly as the original endpoint.
        missed_delta = (1 - min(c_hit, 1)) - (1 - min(r_hit, 1))
        report["splits"][split] = {
            "matched_rows": c["candidate"]["rows"],
            "candidate": c["candidate"], "reference": r["candidate"],
            "public_schedule": c["public_schedule"],
            "delta": {"missed_event_fraction": rational(missed_delta),
                      "false_event_fraction": rational(c_false - r_false),
                      "mean_hit_before_clip": rational(c_hit - r_hit)},
            "ordered_row_counts_sha256": {
                "candidate": digest(c["candidate_rows"]),
                "reference": digest(r["candidate_rows"]),
                "public_schedule": digest(c["public_schedule_rows"])},
        }
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", type=Path, required=True)
    parser.add_argument("--owner-sha256", required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--mode", choices=("standard", "group"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        h = endpoint()
        owner, owner_sha = h.read_json(args.owner)
        if owner_sha != args.owner_sha256:
            raise Refusal("owner digest mismatch")
        candidate, candidate_sha = h.read_json(args.candidate)
        reference, reference_sha = h.read_json(args.reference)
        report = compare(owner, candidate, reference, mode=args.mode)
        report["input_file_sha256"] = {"owner": owner_sha, "candidate": candidate_sha,
                                       "reference": reference_sha}
        raw = canonical(report) + b"\n"
        fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
        print("paired historical event comparison complete")
        return 0
    except (OSError, ValueError, OverflowError, RecursionError):
        print("paired historical event comparison refused")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
