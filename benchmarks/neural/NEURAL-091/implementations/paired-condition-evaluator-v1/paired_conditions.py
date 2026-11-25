"""Compare declared restricted-observation and frozen-program rate predictions.

Both submissions must cover one identical public packet. This is operator-side
assessment, not evidence that either access condition was actually enforced.
"""
import argparse
import importlib.util
import math
from pathlib import Path
import random


_ROSTER_PATH = Path(__file__).resolve().parents[1] / "complete-roster-evaluator-v2" / "complete_roster.py"
_SPEC = importlib.util.spec_from_file_location("neural091_complete_roster_v2", _ROSTER_PATH)
roster = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(roster)
v1 = roster.v1
CONDITIONS = ("restricted_observation", "frozen_program")
SUBMISSION_FIELDS = {"schema_version", "task_id", "condition", "public_sha256", "predictions"}


def admit_submissions(public, restricted, program):
    """Validate both complete submissions using public information only."""
    roster.validate_public(public)
    expected = {tuple(row["key"]) for row in public["query"]}
    public_hash = v1.digest(public)
    for condition, submission in zip(CONDITIONS, (restricted, program)):
        v1.require(isinstance(submission, dict) and set(submission) == SUBMISSION_FIELDS,
                   "unexpected submission fields")
        v1.require(submission["schema_version"] == "neural091-paired-submission/v1"
                   and submission["task_id"] == v1.TASK_ID, "wrong submission contract")
        v1.require(submission["condition"] == condition, "wrong declared access condition")
        v1.require(submission["public_sha256"] == public_hash,
                   "submission must bind the identical public calibration/query packet")
        rates = v1.keyed_rows(submission["predictions"], expected, "rate_hz")
        for rate in rates.values():
            v1.number(rate, "predicted rate", 0)
    return public_hash


def _uncertainty(values, seed, replicates):
    result = {"method": "paired_mouse_percentile_bootstrap", "seed": seed,
              "replicates": replicates, "confidence": 0.95, "limits": None}
    if len(values) >= 2 and all(value is not None for value in values):
        rng = random.Random(seed)
        draws = sorted(roster.finite_mean(rng.choices(values, k=len(values)))
                       for _ in range(replicates))
        result["limits"] = [roster.finite_quantile(draws, 0.025), roster.finite_quantile(draws, 0.975)]
    return result


def _difference(restricted, program, seed, replicates):
    left = {row["mouse_id"]: row for row in restricted["mice"]}
    right = {row["mouse_id"]: row for row in program["mice"]}
    v1.require(set(left) == set(right), "paired mouse roster mismatch")
    mice = []
    for mouse in sorted(left):
        a, b = left[mouse], right[mouse]
        v1.require((a["spikes"], a["observations"]) == (b["spikes"], b["observations"]),
                   "paired target support mismatch")
        reason = None
        delta = None
        if a["status"].startswith("undefined") or b["status"].startswith("undefined"):
            status, reason = "undefined", "original_endpoint_undefined"
        elif a["status"] == b["status"] == "negative_infinity":
            status, reason = "undefined", "both_condition_scores_negative_infinity"
        elif a["status"] == "negative_infinity":
            status = "positive_infinity"
        elif b["status"] == "negative_infinity":
            status = "negative_infinity"
        else:
            delta = b["bits_per_spike"] - a["bits_per_spike"]
            v1.require(math.isfinite(delta), "nonfinite paired difference from numeric overflow")
            status = "finite"
        mice.append({"mouse_id": mouse, "spikes": a["spikes"], "observations": a["observations"],
                     "difference_bits_per_spike": delta, "status": status, "reason": reason})
    statuses = {row["status"] for row in mice}
    if "undefined" in statuses or {"positive_infinity", "negative_infinity"} <= statuses:
        status = "undefined"
    elif "positive_infinity" in statuses:
        status = "positive_infinity"
    elif "negative_infinity" in statuses:
        status = "negative_infinity"
    else:
        status = "finite"
    values = [row["difference_bits_per_spike"] for row in mice]
    return {"contrast": "frozen_program_minus_restricted_observation", "mouse_count": len(mice),
            "mice": mice, "status": status,
            "mouse_macro_difference_bits_per_spike": roster.finite_mean(values) if status == "finite" else None,
            "uncertainty": _uncertainty(values, seed, replicates)}


def compare(public, private, restricted, program, bootstrap_seed=0, bootstrap_replicates=1000):
    # Do not inspect the protected object until both submissions are admitted.
    public_hash = admit_submissions(public, restricted, program)
    v1.require(type(bootstrap_seed) is int, "bootstrap seed must be integer")
    v1.require(type(bootstrap_replicates) is int and 1 <= bootstrap_replicates <= 100000,
               "invalid bootstrap count")
    scores = {condition: roster.score(public, private, submission["predictions"],
                                     bootstrap_seed, bootstrap_replicates)
              for condition, submission in zip(CONDITIONS, (restricted, program))}
    a, b = (scores[condition] for condition in CONDITIONS)
    return {"schema_version": "neural091-paired-comparison/v1", "task_id": v1.TASK_ID,
            "scope": "construction_component_only", "research_qualified": False,
            "public_sha256": public_hash, "query_observations": len(public["query"]),
            "access_conditions_enforced": False, "actual_information_access_verified": False,
            "condition_scores": scores,
            "paired_overall": _difference(a["overall"], b["overall"], bootstrap_seed, bootstrap_replicates),
            "paired_stimulus_families": {
                family: _difference(a["stimulus_families"][family], b["stimulus_families"][family],
                                    bootstrap_seed, bootstrap_replicates)
                for family in public["heldout_families"]}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("public", "private", "restricted", "program", "output"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--bootstrap-seed", type=int, default=0)
    parser.add_argument("--bootstrap-replicates", type=int, default=1000)
    args = parser.parse_args()
    # In the CLI, complete public-only admission occurs before private-file I/O.
    public = v1.read_json(args.public)
    restricted, program = v1.read_json(args.restricted), v1.read_json(args.program)
    admit_submissions(public, restricted, program)
    result = compare(public, v1.read_json(args.private), restricted, program,
                     args.bootstrap_seed, args.bootstrap_replicates)
    v1.write_json(args.output, result)


if __name__ == "__main__":
    main()
