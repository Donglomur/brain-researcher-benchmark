"""Replay NEDS's source trial partition without acquiring or fitting data.

Inputs are operator-owned post-alignment identities, never candidate inputs.
Replay equivalence is conditional on supplied identities and RNG history.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path

import numpy as np

COMMIT = "61d2ef65556dbbc2b828d542f19bd4e7134c92f3"
SPLITS = ("train", "validation", "test")


class ReplayError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ReplayError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def encode_state(rng):
    algorithm, keys, position, has_gauss, cached = rng.get_state()
    return {"algorithm": algorithm, "keys": keys.tolist(), "position": position,
            "has_gauss": has_gauss, "cached_gaussian": cached}


def decode_state(state):
    require(isinstance(state, dict) and set(state) ==
            {"algorithm", "keys", "position", "has_gauss", "cached_gaussian"},
            "closed MT19937 state fields required")
    require(state["algorithm"] == "MT19937", "legacy MT19937 state required")
    keys = state["keys"]
    require(isinstance(keys, list) and len(keys) == 624 and
            all(type(k) is int and 0 <= k <= 2**32 - 1 for k in keys) and any(keys),
            "624 nondegenerate uint32 MT19937 keys required")
    require(type(state["position"]) is int and 0 <= state["position"] <= 624,
            "invalid MT19937 position")
    require(type(state["has_gauss"]) is int and state["has_gauss"] in (0, 1),
            "invalid Gaussian-cache flag")
    require(type(state["cached_gaussian"]) in (float, int) and
            np.isfinite(state["cached_gaussian"]), "nonfinite Gaussian cache")
    rng = np.random.RandomState(0)
    rng.set_state(("MT19937", np.asarray(keys, dtype=np.uint32), state["position"],
                   state["has_gauss"], state["cached_gaussian"]))
    return rng


def _trial_rows(event):
    require(isinstance(event, dict) and set(event) == {"eid", "trial_ids", "stim_on_seconds"},
            "each split event needs exactly eid, trial_ids, stim_on_seconds")
    ids = event["trial_ids"]
    require(isinstance(ids, list) and ids and
            all(isinstance(x, str) and x for x in ids) and len(set(ids)) == len(ids),
            "ordered unique nonempty original trial IDs required")
    times = event["stim_on_seconds"]
    require(isinstance(times, list) and len(times) == len(ids) and
            all(type(x) in (int, float) for x in times), "one numeric stimulus time per trial required")
    times = np.asarray(times, dtype=float)
    with np.errstate(over="ignore", invalid="ignore"):
        windows = np.column_stack((times - 0.5, times + 1.5))
    require(np.isfinite(windows).all() and np.all(windows[:, 1] > windows[:, 0]),
            "stimulus times must yield finite nonempty two-second windows")
    return ids, windows


def physical_overlap(partitions, example_limit=10):
    """Cross-split half-open window intersections; never purge or redraw trials."""
    require(type(example_limit) is int and example_limit >= 0, "invalid example limit")
    result = {}
    for left_name, right_name in itertools.combinations(SPLITS, 2):
        left, right = partitions[left_name], partitions[right_name]
        # Both lists are sorted only for the sweep, not in the exported split.
        lrows = sorted(zip(left["windows_seconds"], left["trial_ids"]))
        rrows = sorted(zip(right["windows_seconds"], right["trial_ids"]))
        count, total, cursor = 0, 0.0, 0
        touched_left, touched_right, examples = set(), set(), []
        for (lo, hi), lid in lrows:
            while cursor < len(rrows) and rrows[cursor][0][1] <= lo:
                cursor += 1
            for index in range(cursor, len(rrows)):
                (rlo, rhi), rid = rrows[index]
                if rlo >= hi:
                    break
                seconds = min(hi, rhi) - max(lo, rlo)
                if seconds > 0:
                    count += 1
                    total += seconds
                    touched_left.add(lid)
                    touched_right.add(rid)
                    if len(examples) < example_limit:
                        examples.append({"left_trial_id": lid, "right_trial_id": rid,
                                         "overlap_seconds": seconds})
        result[left_name + ":" + right_name] = {
            "overlapping_pair_count": count, "sum_pair_overlap_seconds": total,
            "left_affected_trials": len(touched_left), "right_affected_trials": len(touched_right),
            "examples": examples, "examples_truncated": count > len(examples)}
    return result


def replay(request):
    """Replay only calls that reached the author's split line, in process order.

    Source skips before the split do not appear. Restarts are separate requests.
    An explicit pre-split state can preserve unknown earlier RNG consumption.
    """
    require(isinstance(request, dict) and set(request) ==
            {"schema", "source_commit", "evidence_kind", "rng_origin", "events"},
            "closed replay request fields required")
    require(request["schema"] == "neds-source-split-request-v1" and
            request["source_commit"] == COMMIT, "schema or source commit mismatch")
    require(request["evidence_kind"] in ("generated_engineering", "operator_supplied_unqualified"),
            "unknown evidence kind")
    origin = request["rng_origin"]
    require(isinstance(origin, dict), "explicit RNG origin required")
    if origin == {"kind": "source_process_seed", "seed": 42} and type(origin["seed"]) is int:
        rng = np.random.RandomState(42)
        assumption = "No unrecorded NumPy random draws since source process seed(42)."
    else:
        require(set(origin) == {"kind", "state"} and origin["kind"] == "captured_pre_split_state",
                "use source_process_seed 42 or captured_pre_split_state")
        rng = decode_state(origin["state"])
        assumption = "Supplied state is immediately before the first declared source split call."
    roster = json.loads((Path(__file__).parents[1] / "initial-evaluator-v1" / "cohort.json").read_text())
    membership = set(roster["training_eids"] + roster["heldout_eids"])
    events = request["events"]
    require(isinstance(events, list) and events, "nonempty ordered split events required")
    seen, sessions = set(), []
    for event in events:
        ids, windows = _trial_rows(event)
        eid = event["eid"]
        require(isinstance(eid, str) and eid in membership and eid not in seen,
                "source EID must be known and unique within invocation")
        seen.add(eid)
        before = encode_state(rng)
        # Preserve legacy np.random.choice and literal floating floor boundaries.
        n = len(ids)
        order = rng.choice(np.arange(n), n, replace=False)
        cuts = (0, int(0.7 * n), int(0.8 * n), n)
        partitions = {}
        for name, start, stop in zip(SPLITS, cuts[:-1], cuts[1:]):
            indices = order[start:stop]
            partitions[name] = {"aligned_row_indices": indices.tolist(),
                                "trial_ids": [ids[i] for i in indices],
                                "windows_seconds": windows[indices].tolist()}
        sessions.append({"eid": eid, "aligned_trial_count": n,
                         "aligned_identity_sha256": digest(ids),
                         "rng_state_before_sha256": digest(before),
                         "rng_state_after_sha256": digest(encode_state(rng)),
                         "partitions": partitions, "physical_overlap": physical_overlap(partitions)})
    return {"schema": "neds-source-split-replay-v1", "source_commit": COMMIT,
            "request_sha256": digest(request), "evidence_kind": request["evidence_kind"],
            "numpy_version": np.__version__, "rng_assumption": assumption,
            "sessions": sessions, "rng_state_after": encode_state(rng),
            "qualification": "conditional source split replay; original trial and RNG provenance unqualified",
            "scope": "One declared preparation invocation; not full-cohort or historical-result admission."}


def verify_partition_ids(replayed, evaluator_sessions):
    """Require exact session coverage and exact ordered evaluator split identities."""
    require(isinstance(evaluator_sessions, list), "evaluator sessions must be a list")
    observed = {}
    for session in evaluator_sessions:
        require(isinstance(session, dict) and isinstance(session.get("eid"), str), "session EID required")
        require(session["eid"] not in observed, "duplicate evaluator EID")
        observed[session["eid"]] = session
    require(set(observed) == {s["eid"] for s in replayed["sessions"]}, "replay/evaluator session coverage differs")
    for session in replayed["sessions"]:
        for split in SPLITS:
            actual = observed[session["eid"]].get(split)
            require(isinstance(actual, dict) and actual.get("trial_ids") == session["partitions"][split]["trial_ids"],
                    f"{session['eid']} {split}: ordered trial partition mismatch")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--verify-bundle", type=Path,
                        help="Compare ordered IDs only; use the existing evaluator for array and full-cohort validation")
    args = parser.parse_args()
    report = replay(json.loads(args.request.read_text()))
    if args.verify_bundle:
        verify_partition_ids(report, json.loads(args.verify_bundle.read_text())["sessions"])
        report["evaluator_trial_identity_check"] = "matched exact ordered partitions"
    # Operator must choose an external evidence path; contains original trial identities.
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
