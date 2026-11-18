"""Conditional trial-support bounds for the complete NEURAL-042 cohort.

Only supplied trial metadata is inspected. No LFP, spikes, PAC or candidate
answers are loaded. A passing bound is not qualified support; a failing bound
rules support out only if the supplied original metadata has been authenticated.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

ROSTER_SHA256 = "988b0b979d9d940963ee8c0223b2e0941ef8754279f59f60afb459da91dbe548"
ROSTER_BYTES = 16501
METADATA_LIMIT = 1 << 20
MINIMUM_PAIRS = 10
COMPARISONS = ("load3_minus_load1_correct", "correct_minus_incorrect_load1",
               "correct_minus_incorrect_load3")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def exact(value, keys, message):
    require(type(value) is dict and set(value) == set(keys), message)


def strict_json(raw):
    def unique(pairs):
        out = {}
        for key, value in pairs:
            require(key not in out, "duplicate JSON key")
            out[key] = value
        return out

    def invalid_constant(value):
        raise ValueError("nonfinite JSON constant: " + value)

    return json.loads(raw, object_pairs_hook=unique, parse_constant=invalid_constant)


def source_roster(raw):
    require(type(raw) is bytes and len(raw) == ROSTER_BYTES
            and hashlib.sha256(raw).hexdigest() == ROSTER_SHA256,
            "the fixed 44-session source roster is required")
    roster = strict_json(raw)
    assets = roster["assets"]
    require(roster["dandiset"] == "000673" and roster["version"] == "0.240118.2135"
            and roster["complete"] is True and len(assets) == 44
            and len({x["asset_id"] for x in assets}) == 44
            and len({x["subject_id"] for x in assets}) == 36,
            "complete original 44-session / 36-person roster")
    return {x["asset_id"]: x for x in assets}


def _bounds(trials):
    """Exact count-only cardinalities; upper bounds on nuisance matching.

    Each tuple is (original row, load, correctness, probe). Within each fixed
    quartile/probe stratum every count-only A/B pair is allowed. Hence the
    maximum is min(n_A,n_B) per stratum. Clinical removal and nuisance calipers
    only remove vertices/edges; neither can increase this bound.
    """
    strata = {(block, probe): {} for block in range(4) for probe in range(2)}
    for row, load, correct, probe in trials:
        cell = strata[(row // 35, probe)]
        cell[(load, correct)] = cell.get((load, correct), 0) + 1
    totals = dict.fromkeys(COMPARISONS, 0)
    details = []
    for (block, probe), counts in strata.items():
        c = lambda load, accuracy: counts.get((load, accuracy), 0)
        pairs = (min(c(3, 1), c(1, 1)), min(c(1, 1), c(1, 0)),
                 min(c(3, 1), c(3, 0)))
        for name, count in zip(COMPARISONS, pairs):
            totals[name] += count
        details.append({"original_order_quartile": block, "probe": probe,
                        "maximum_count_only_pairs": dict(zip(COMPARISONS, pairs))})
    return totals, details


def audit(metadata, roster_raw):
    """Return a private conditional feasibility report, never a score."""
    assets = source_roster(roster_raw)
    exact(metadata, ("schema", "source_roster_sha256", "sessions"),
          "exact metadata envelope")
    require(metadata["schema"] == "neural042_original_trial_metadata_v1"
            and metadata["source_roster_sha256"] == ROSTER_SHA256,
            "metadata schema and fixed source-roster binding")
    sessions = metadata["sessions"]
    require(type(sessions) is list and len(sessions) == 44, "all 44 source sessions")
    indexed = {}
    for row in sessions:
        exact(row, ("asset_id", "source_sha256", "subject_id", "loads", "correct", "probe"),
              "exact source session metadata")
        identity = row["asset_id"]
        require(type(identity) is str and identity in assets and identity not in indexed,
                "unique original asset identity")
        original = assets[identity]
        require(row["source_sha256"] == original["sha256"]
                and row["subject_id"] == original["subject_id"], "source identity join")
        for key, allowed in (("loads", (1, 3)), ("correct", (0, 1)), ("probe", (0, 1))):
            values = row[key]
            require(type(values) is list and len(values) == 140
                    and all(type(x) is int and x in allowed for x in values),
                    "all 140 original typed " + key + " values; no dropped/reindexed trials")
        indexed[identity] = row
    require(set(indexed) == set(assets), "complete source identity join")
    results = []
    possible_people = {"load": set(), "correctness": set()}
    for identity in sorted(indexed):
        row = indexed[identity]
        trials = [(i, row["loads"][i], row["correct"][i], row["probe"][i])
                  for i in range(140)]
        counts, strata = _bounds(trials)
        possible = {"load": counts[COMPARISONS[0]] >= MINIMUM_PAIRS,
                    "correctness": all(counts[name] >= MINIMUM_PAIRS for name in COMPARISONS[1:])}
        for endpoint in possible_people:
            if possible[endpoint]:
                possible_people[endpoint].add(row["subject_id"])
        results.append({"asset_id": identity, "subject_id": row["subject_id"],
                        "original_trials": 140,
                        "maximum_count_only_pairs": counts,
                        "nuisance_matching_pair_upper_bounds": dict(counts),
                        "endpoint_not_ruled_out": possible,
                        "strata": strata})
    summary = {
        "source_sessions": 44, "source_people": 36, "original_trials": 6160,
        "minimum_pairs_unchanged": MINIMUM_PAIRS,
        "sessions_not_ruled_out": {key: sum(r["endpoint_not_ruled_out"][key] for r in results)
                                   for key in possible_people},
        "people_not_ruled_out": {key: len(value) for key, value in possible_people.items()},
        "primary_ruled_out_by_supplied_label_bounds": any(not x for x in possible_people.values()),
        "actual_reference_support": None, "scientific_qualification": "not_established",
        "condition": "Bounds are conditional on complete, correctly extracted original metadata; "
                     "the source hash strings alone do not authenticate those labels.",
        "passing_bound": "Not ruled out only. Clinical eligibility, exclusions, nuisance calipers, "
                         "all numerical estimators and independent reference agreement remain required.",
    }
    return {"schema": "neural042_trial_support_bounds_v1", "source_roster_sha256": ROSTER_SHA256,
            "operator_private": True, "sessions": results, "summary": summary}


def read_bounded(path, maximum):
    with Path(path).open("rb") as stream:
        raw = stream.read(maximum + 1)
    require(len(raw) <= maximum, "input byte limit")
    return raw


def audit_frozen(raw, roster_raw, expected_sha256):
    """Bind the saved report to the exact operator-frozen metadata bytes."""
    require(type(raw) is bytes and 0 < len(raw) <= METADATA_LIMIT, "bounded metadata bytes")
    actual_sha256 = hashlib.sha256(raw).hexdigest()
    require(actual_sha256 == expected_sha256, "metadata identity mismatch")
    report = audit(strict_json(raw), roster_raw)
    report["metadata_input"] = {"bytes": len(raw), "sha256": actual_sha256}
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-roster", required=True)
    parser.add_argument("--metadata", required=True)
    parser.add_argument("--metadata-sha256", required=True,
                        help="Operator-frozen metadata identity; not proof of source extraction")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    raw = read_bounded(args.metadata, METADATA_LIMIT)
    report = audit_frozen(raw, read_bounded(args.source_roster, ROSTER_BYTES), args.metadata_sha256)
    body = (json.dumps(report, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
    # Existing files are never replaced. Output includes private source identifiers.
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(body)
    print(json.dumps({"output_bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(),
                      "scientific_qualification": "not_established"}))


if __name__ == "__main__":
    main()
