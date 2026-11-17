"""Figure 5i circular prediction score; no fitting, data import or split drawing.

The operator supplies the independently authenticated original reference. Merely
passing its structural checks does not authenticate the cohort or original RNG.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

TASK = "PAPER-FIND-039"
SOURCE_REVISION = "1a9dd3040c9f77662caf26a34c9452403579087a"
AGE_COUNTS = {"young": 34, "aged": 27}
REPEATS = 10


def _ids(values, name):
    if (not isinstance(values, list) or not values
            or any(not isinstance(x, str) or not x for x in values)
            or len(set(values)) != len(values)):
        raise ValueError(f"{name}: nonempty unique string IDs required")
    return values


def _angles(values, name):
    if (not isinstance(values, list) or not values
            or any(type(x) not in (int, float) or not math.isfinite(x) for x in values)):
        raise ValueError(f"{name}: nonempty finite numeric radians required")
    return values


def cosine_score(target_radians, predicted_radians):
    """Mean cos(target - prediction), with every observation retained."""
    target = _angles(target_radians, "target_radians")
    predicted = _angles(predicted_radians, "predicted_radians")
    if len(target) != len(predicted):
        raise ValueError("target and prediction lengths differ")
    # Reduce individually before subtraction to avoid overflow for finite inputs.
    return math.fsum(math.cos(math.remainder(t, math.tau) - math.remainder(p, math.tau))
                     for t, p in zip(target, predicted)) / len(target)


def reference_digest(reference):
    """Canonical reference digest binds targets, cohort, cells and realized folds."""
    body = json.dumps(reference, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def _session_key(session):
    key = session.get("mouse_id"), session.get("session_id")
    if any(not isinstance(x, str) or not x for x in key):
        raise ValueError("mouse_id and session_id must be nonempty strings")
    return key


def _sessions(packet):
    rows = packet.get("sessions")
    if not isinstance(rows, list) or not rows:
        raise ValueError("sessions must be a nonempty list")
    result = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("session must be an object")
        key = _session_key(row)
        if key in result:
            raise ValueError("duplicate mouse/session")
        result[key] = row
    return result


def _folds(session):
    folds = session.get("folds")
    if not isinstance(folds, list) or len(folds) != REPEATS:
        raise ValueError("each session requires exactly ten folds")
    result = {}
    for fold in folds:
        if not isinstance(fold, dict):
            raise ValueError("fold must be an object")
        repeat = fold.get("repeat")
        if type(repeat) is not int or repeat not in range(REPEATS) or repeat in result:
            raise ValueError("fold repeat IDs must be exactly 0..9")
        result[repeat] = fold
    return result


def validate_reference(reference):
    if (not isinstance(reference, dict)
            or reference.get("schema") != "figure5i-reference/v1"
            or reference.get("task_id") != TASK
            or reference.get("source_revision") != SOURCE_REVISION
            or reference.get("condition") != "spatial_cells_both_maps"):
        raise ValueError("reference identity or Figure 5i condition differs")
    for name in ("cohort_receipt_sha256", "preprocessing_receipt_sha256", "split_receipt_sha256"):
        value = reference.get(name)
        if (not isinstance(value, str) or len(value) != 64
                or any(c not in "0123456789abcdef" for c in value)):
            raise ValueError(f"{name}: lowercase SHA-256 required")
    sessions = _sessions(reference)
    counts = dict.fromkeys(AGE_COUNTS, 0)
    mouse_ages = {}
    for (mouse, _), session in sessions.items():
        age = session.get("age_group")
        if age not in counts:
            raise ValueError("only original young and aged strata are supported")
        counts[age] += 1
        if mouse in mouse_ages and mouse_ages[mouse] != age:
            raise ValueError("mouse belongs to multiple age strata")
        mouse_ages[mouse] = age
        if type(session.get("optimal_k")) is not int or session["optimal_k"] != 2:
            raise ValueError("Figure 5i requires optimal k=2")
        if session.get("source_onemap") is not False:
            raise ValueError("Figure 5i requires explicit source onemap=False")
        if len(_ids(session.get("spatial_cell_ids"), "spatial_cell_ids")) <= 10:
            raise ValueError("Figure 5i requires more than ten spatial cells")
        observations = _ids(session.get("downsampled_observation_ids"), "downsampled_observation_ids")
        if len(observations) < REPEATS:
            raise ValueError("at least one observation per test fold required")
        folds = _folds(session)
        start = 0
        quotient, remainder = divmod(len(observations), REPEATS)
        for repeat in range(REPEATS):
            fold = folds[repeat]
            test = _ids(fold.get("test_observation_ids"), "test_observation_ids")
            end = start + quotient + (repeat < remainder)
            if test != observations[start:end]:
                raise ValueError("test fold differs from source array_split partition")
            start = end
            train = _ids(fold.get("train_observation_ids"), "train_observation_ids")
            if len(train) != int(len(observations) * 0.9):
                raise ValueError("training count differs from source int(n * 0.9)")
            if not set(train) <= set(observations) - set(test):
                raise ValueError("training includes held-out or unknown observations")
            if len(_angles(fold.get("target_radians"), "target_radians")) != len(test):
                raise ValueError("target count differs from test identities")
    if counts != AGE_COUNTS:
        raise ValueError("the complete original panel requires 34 young and 27 aged sessions")
    return sessions


def _score_predictions(packet, reference, reference_sessions, digest):
    if (not isinstance(packet, dict) or packet.get("schema") != "figure5i-predictions/v1"
            or packet.get("reference_sha256") != digest):
        raise ValueError("prediction schema or reference digest differs")
    sessions = _sessions(packet)
    if sessions.keys() != reference_sessions.keys():
        raise ValueError("prediction session coverage differs from reference")
    result = {}
    for key, expected in reference_sessions.items():
        expected_folds, folds = _folds(expected), _folds(sessions[key])
        scores = []
        for repeat in range(REPEATS):
            expected_fold, fold = expected_folds[repeat], folds[repeat]
            if fold.get("test_observation_ids") != expected_fold["test_observation_ids"]:
                raise ValueError("prediction observation identities/order differ")
            scores.append(cosine_score(expected_fold["target_radians"], fold.get("predicted_radians")))
        result[key] = {"fold_scores": scores, "session_score": math.fsum(scores) / REPEATS}
    return result


def score_panel(reference, candidate, author, shuffle):
    """Score three complete prediction packets against one operator reference.

    `author` is an actual replay, never published stratum means. `shuffle` is
    the original companion spike-shuffle decoder on these same test identities.
    Method/input authenticity is checked upstream; this is an arithmetic and
    identity component, not a sandbox or a superiority/admission decision.
    """
    sessions = validate_reference(reference)
    digest = reference_digest(reference)
    arms = {name: _score_predictions(packet, reference, sessions, digest)
            for name, packet in (("candidate", candidate), ("author", author), ("shuffle", shuffle))}
    rows = []
    for (mouse, session), expected in sessions.items():
        row = {"mouse_id": mouse, "session_id": session, "age_group": expected["age_group"],
               "arms": {name: values[(mouse, session)] for name, values in arms.items()}}
        row["candidate_minus_author"] = (row["arms"]["candidate"]["session_score"]
                                         - row["arms"]["author"]["session_score"])
        rows.append(row)
    strata = {}
    for age in AGE_COUNTS:
        group = [row for row in rows if row["age_group"] == age]
        strata[age] = {
            "n_sessions": len(group), "n_mice": len({row["mouse_id"] for row in group}),
            "session_mean": {name: math.fsum(row["arms"][name]["session_score"] for row in group) / len(group)
                             for name in arms},
            "candidate_minus_author": math.fsum(row["candidate_minus_author"] for row in group) / len(group),
        }
    return {"schema": "figure5i-score-report/v1", "task_id": TASK, "reference_sha256": digest,
            "scope": "complete-panel arithmetic conditional on operator reference authenticity",
            "sessions": rows, "age_strata": strata,
            "aggregation": "equal ten fold means, then equal session means within each age stratum",
            "qualification": "No author reproduction, uncertainty decision or paper improvement established."}


def _unique_json(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("reference", "candidate", "author", "shuffle", "report"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    paths = [getattr(args, name) for name in ("reference", "candidate", "author", "shuffle")]
    if args.report.resolve() in {path.resolve() for path in paths}:
        parser.error("report cannot overwrite an input")
    packets = [json.loads(path.read_text(), object_pairs_hook=_unique_json) for path in paths]
    report = score_panel(*packets)
    args.report.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
