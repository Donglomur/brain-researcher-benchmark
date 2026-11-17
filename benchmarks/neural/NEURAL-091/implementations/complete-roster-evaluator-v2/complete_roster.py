"""NEURAL-091 scorer with complete declared-roster reconciliation.

This validates an existing export, not native recording authenticity. The
preserved v1 scorer owns counts, exposure, controls and the original estimand.
"""
import argparse
from collections import defaultdict
import importlib.util
from pathlib import Path


_V1_PATH = Path(__file__).resolve().parents[1] / "initial-evaluator-v1" / "evaluator.py"
_SPEC = importlib.util.spec_from_file_location("neural091_preserved_evaluator_v1", _V1_PATH)
v1 = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(v1)

PUBLIC_KEYS = {"schema_version", "task_id", "protocol_sha256", "heldout_families",
               "state_prior_seconds", "training", "query"}
PRIVATE_KEYS = {"schema_version", "task_id", "public_sha256", "targets",
                "exclusions", "source_roster"}
PRESENTATION_FIELDS = ("mouse_id", "family", "condition_id", "start_time", "stop_time",
                       "stimulus", "running_speed", "running_coverage", "pupil_area",
                       "pupil_coverage")


def _identifiers(values, name):
    v1.require(isinstance(values, list) and bool(values), "nonempty " + name + " required")
    for value in values:
        v1.identifier(value, name)
    v1.unique(values, name)
    return set(values)


def _sha256(value, name):
    v1.require(isinstance(value, str) and len(value) == 64
               and all(c in "0123456789abcdef" for c in value), "invalid " + name)


def validate_public(public):
    """Preserve v1 validation and enforce calibrated-unit/presentation identity."""
    v1.require(isinstance(public, dict) and set(public) == PUBLIC_KEYS,
               "unexpected public packet fields")
    v1.validate_public(public)
    _sha256(public["protocol_sha256"], "protocol digest")
    families = set(public["heldout_families"])
    train_units, query_units = set(), defaultdict(set)
    presentations, conditions = {}, defaultdict(set)
    for split in ("training", "query"):
        for row in public[split]:
            sid, uid, pid = row["key"]
            v1.identifier(row["family"], "family")
            identity = {field: row[field] for field in PRESENTATION_FIELDS}
            if (sid, pid) in presentations:
                v1.require(presentations[sid, pid] == identity,
                           "inconsistent presentation identity across units")
            else:
                presentations[sid, pid] = identity
            conditions[sid, row["condition_id"]].add(row["family"])
            if split == "training":
                train_units.add((sid, uid))
            else:
                query_units[sid, uid].add(row["family"])
    v1.require(train_units == set(query_units), "calibration/query unit roster mismatch")
    v1.require(all(value == families for value in query_units.values()),
               "each calibrated unit must retain every heldout family")
    v1.require(all(len(value) == 1 for value in conditions.values()),
               "condition identity crosses stimulus families")


def validate_packet(public, private):
    """Account for every declared session/unit/presentation exactly once.

    Positive-exposure rows, whole-presentation exclusions and per-unit zero
    exposure exclusions must partition the original declared Cartesian roster.
    Exclusion truth and initial roster completeness still require native audit.
    """
    validate_public(public)
    v1.require(isinstance(private, dict) and set(private) == PRIVATE_KEYS,
               "unexpected protected packet fields")
    v1.require(type(private["schema_version"]) is int and private["schema_version"] == 1
               and private["task_id"] == v1.TASK_ID, "wrong protected packet")
    v1.require(private["public_sha256"] == v1.digest(public), "protected packet binding mismatch")
    roster = private["source_roster"]
    v1.require(isinstance(roster, list) and bool(roster), "nonempty protected source roster required")
    sessions = {}
    for selected in roster:
        sid = v1.identifier(selected["session_id"], "session_id")
        v1.require(sid not in sessions, "duplicate protected roster session")
        mouse = v1.identifier(selected["mouse_id"], "mouse_id")
        units = _identifiers(selected["unit_ids"], "protected unit roster")
        presentations = _identifiers(selected["presentation_ids"], "protected presentation roster")
        _sha256(selected["source_file_sha256"], "source digest")
        _sha256(selected["presentation_table_sha256"], "presentation table digest")
        v1.require(type(selected["source_file_bytes"]) is int and selected["source_file_bytes"] > 0,
                   "invalid declared source size")
        sessions[sid] = (mouse, units, presentations)

    observed = defaultdict(set)
    actual_units = set()
    for row in public["training"] + public["query"]:
        sid, uid, pid = row["key"]
        v1.require(sid in sessions, "observation session outside source roster")
        mouse, units, presentations = sessions[sid]
        v1.require(uid in units and pid in presentations, "observation outside source roster")
        v1.require(row["mouse_id"] == mouse, "observation mouse disagrees with source roster")
        observed[sid, pid].add(uid)
        actual_units.add((sid, uid))
    expected_units = {(sid, uid) for sid, (_, units, _) in sessions.items() for uid in units}
    v1.require(actual_units == expected_units, "complete selected unit roster required")

    exclusions = private["exclusions"]
    v1.require(isinstance(exclusions, list), "exclusions must be a list")
    whole, zero = set(), defaultdict(set)
    for row in exclusions:
        v1.require(isinstance(row, dict), "malformed exclusion")
        reason = row.get("reason")
        if reason == "zero_valid_exposure":
            v1.require(set(row) == {"key", "reason"}, "malformed zero-exposure exclusion")
            key = row["key"]
            v1.require(isinstance(key, list) and len(key) == 3, "malformed exclusion key")
            sid, uid, pid = (v1.identifier(value, "exclusion key") for value in key)
            v1.require(sid in sessions and uid in sessions[sid][1] and pid in sessions[sid][2],
                       "exclusion outside source roster")
            v1.require(uid not in zero[sid, pid], "duplicate zero-exposure exclusion")
            zero[sid, pid].add(uid)
        else:
            v1.require(reason in {"invalid_stimulus", "temporal_guard"}, "unknown exclusion reason")
            v1.require(set(row) == {"session_id", "presentation_id", "reason"},
                       "malformed whole-presentation exclusion")
            sid = v1.identifier(row["session_id"], "exclusion session")
            pid = v1.identifier(row["presentation_id"], "exclusion presentation")
            v1.require(sid in sessions and pid in sessions[sid][2], "exclusion outside source roster")
            v1.require((sid, pid) not in whole, "duplicate whole-presentation exclusion")
            whole.add((sid, pid))

    expected_rows = excluded_rows = 0
    for sid, (_, units, presentations) in sessions.items():
        expected_rows += len(units) * len(presentations)
        for pid in presentations:
            seen, removed = observed.get((sid, pid), set()), zero.get((sid, pid), set())
            if (sid, pid) in whole:
                v1.require(not seen and not removed, "whole exclusion overlaps an accounted row")
                excluded_rows += len(units)
            else:
                v1.require(not seen.intersection(removed), "zero exposure exclusion overlaps an observation")
                v1.require(seen | removed == units, "unaccounted source-roster observation")
                excluded_rows += len(removed)
    expected_query = {tuple(row["key"]) for row in public["query"]}
    counts = v1.keyed_rows(private["targets"], expected_query, "count")
    v1.require(all(type(value) is int and value >= 0 for value in counts.values()),
               "target count must be a nonnegative integer")
    return {"declared_observations": expected_rows,
            "training_observations": len(public["training"]),
            "query_observations": len(public["query"]),
            "excluded_observations": excluded_rows,
            "selected_units": len(expected_units), "selected_sessions": len(sessions)}


def score(public, private, predictions, bootstrap_seed=0, bootstrap_replicates=1000):
    coverage = validate_packet(public, private)
    result = v1.score(public, private, predictions, bootstrap_seed, bootstrap_replicates)
    result["declared_roster_coverage"] = coverage
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("public", "private", "predictions", "output"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--bootstrap-seed", type=int, default=0)
    args = parser.parse_args()
    result = score(v1.read_json(args.public), v1.read_json(args.private),
                   v1.read_json(args.predictions), args.bootstrap_seed)
    v1.write_json(args.output, result)


if __name__ == "__main__":
    main()
