"""Operator comparison of both Figure 4D outcomes and information conditions.

One independently supplied source/draw/reference panel binds all four submissions.
Generated arithmetic and supplied lineage do not qualify scientific outcomes.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
from pathlib import Path

DRAW_SHA256 = "53956356d16a88d4212c440727e3572753849ae562c2eb23c1ae6b855edd7f91"
OUTCOMES = ("reproduction", "improvement")
CONDITIONS = ("paper_data", "paper_data_author_code")
METRICS = ("exact_match_accuracy", "normalized_absolute_error")


def draw_module():
    path = Path(__file__).resolve().parent.parent / "figure4d-paired-draws-v1" / "paired_draws.py"
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != DRAW_SHA256:
        raise ValueError("paired-draw dependency changed; review it before use")
    spec = importlib.util.spec_from_file_location("hierarchy_comparison_draws", path)
    module = importlib.util.module_from_spec(spec)
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module


def difference(left, right):
    """Signed left-minus-right diagnostics, retaining undefined condition scores."""
    return {name: None if left[name] is None or right[name] is None
            else left[name] - right[name] for name in METRICS}


def contrasts(left, right):
    """Use only reports scored against the same validated operator draw ledger."""
    repetitions = []
    for lrep, rrep in zip(left["repetitions"], right["repetitions"]):
        repetitions.append({
            "Boot_rep": lrep["Boot_rep"], **difference(lrep, rrep),
            "conditions": [{"condition": lg["condition"], "count": lg["count"],
                            **difference(lg, rg)}
                           for lg, rg in zip(lrep["conditions"], rrep["conditions"])],
        })
    return {"repetitions": repetitions,
            "repeat_summary": {"role": "descriptive_equal_repeat_difference; not a paper decision",
                               **difference(left["repeat_summary"], right["repeat_summary"])}}


def score_session(source, ledger, source_sha256, reference, submissions, draws, scoring):
    validated = draws.validate_session(source, ledger, source_sha256, scoring)
    draws.exact(reference, scoring.ARMS, "reference arms")
    draws.exact(submissions, OUTCOMES, "submission outcomes")

    def score(exports):
        draws.exact(exports, scoring.ARMS, "submission arms")
        return {arm: scoring.score_rows(
            draws.bound_prediction_rows(exports[arm], validated),
            context_labels=validated["contexts"], condition_labels=validated["conditions"],
            condition_column="Condition",
            aggregation="global" if arm.startswith("global") else "conditional")
            for arm in scoring.ARMS}

    author = score(reference)
    outcomes = {}
    for outcome in OUTCOMES:
        draws.exact(submissions[outcome], CONDITIONS, "information conditions")
        candidates = {condition: score(submissions[outcome][condition]) for condition in CONDITIONS}
        outcomes[outcome] = {
            "conditions": candidates,
            "candidate_minus_author": {
                condition: {arm: contrasts(candidates[condition][arm], author[arm])
                            for arm in scoring.ARMS} for condition in CONDITIONS},
            "author_code_minus_paper_data": {
                arm: contrasts(candidates[CONDITIONS[1]][arm], candidates[CONDITIONS[0]][arm])
                for arm in scoring.ARMS},
            "scientific_outcome": "unknown",
        }
    return {"animal": validated["animal"], "date": validated["date"],
            "draw_support": validated["summaries"], "reference": author, "outcomes": outcomes,
            "prediction_rows_bound_to_shared_occurrences": True,
            "training_execution_verified": False, "source_preparation_verified": False,
            "stratification_algorithm_verified": False, "information_exposure_verified": False}


def score_panel(manifest, base_directory):
    draws = draw_module()
    scoring = draws.scorer_module()
    draws.exact(manifest, {"schema", "sessions"}, "condition-comparison panel")
    draws.require(manifest["schema"] == "hierarchy-figure4d-condition-comparison/v1",
                  "unknown condition-comparison schema")
    roster = [(animal, date) for animal, dates in scoring.ROSTER.items() for date in dates]
    draws.require(type(manifest["sessions"]) is list and len(manifest["sessions"]) == len(roster),
                  "complete 25-session source panel required")
    sessions = {}
    for session in manifest["sessions"]:
        draws.exact(session, {"animal", "date", "source", "ledger", "reference", "submissions"},
                    "comparison session")
        identity = (draws.literal(session["animal"], "animal"), draws.literal(session["date"], "date"))
        draws.require(identity in roster and identity not in sessions, "unknown or duplicate source session")
        sessions[identity] = session
    results, used_exports = [], set()

    def exports(descriptors):
        draws.exact(descriptors, scoring.ARMS, "prediction arms")
        result = {}
        for arm in scoring.ARMS:
            descriptor = descriptors[arm]
            body = draws.pinned_body(base_directory, descriptor)
            identity = str((Path(base_directory) / descriptor["path"]).resolve())
            draws.require(identity not in used_exports,
                          "same prediction export reused across submission/reference/arm/session")
            used_exports.add(identity)
            result[arm] = draws.csv_rows(body)
        return result

    for identity in roster:
        session = sessions[identity]
        source = draws.json_body(draws.pinned_body(base_directory, session["source"]))
        ledger = draws.json_body(draws.pinned_body(base_directory, session["ledger"]))
        draws.require(type(source) is dict and type(ledger) is dict, "source and ledger must be objects")
        draws.require((source.get("animal"), source.get("date")) == identity, "source session identity mismatch")
        reference = exports(session["reference"])
        draws.exact(session["submissions"], OUTCOMES, "submission outcomes")
        submissions = {}
        for outcome in OUTCOMES:
            draws.exact(session["submissions"][outcome], CONDITIONS, "information conditions")
            submissions[outcome] = {condition: exports(session["submissions"][outcome][condition])
                                    for condition in CONDITIONS}
        report = score_session(source, ledger, session["source"]["sha256"], reference,
                               submissions, draws, scoring)
        report["input_sha256"] = {
            "source": session["source"]["sha256"], "ledger": session["ledger"]["sha256"],
            "reference": {arm: session["reference"][arm]["sha256"] for arm in scoring.ARMS},
            "submissions": {outcome: {condition: {
                arm: session["submissions"][outcome][condition][arm]["sha256"] for arm in scoring.ARMS}
                for condition in CONDITIONS} for outcome in OUTCOMES},
        }
        results.append(report)
    return {"schema": "hierarchy-figure4d-condition-diagnostics/v1", "task_id": draws.TASK,
            "session_count": len(roster), "animal_count": len(scoring.ROSTER), "sessions": results,
            "qualification": "operator_metadata_and_paired_prediction_arithmetic_only",
            "published_metric_convention_selected": False,
            "cross_session_aggregate": None, "biological_uncertainty": None,
            "reproduction_outcome": "unknown", "improvement_outcome": "unknown", "paper_win": None}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args(argv)
    try:
        draws = draw_module()
        with args.manifest.open("rb") as handle:
            body = handle.read(draws.MAX_MEMBER_BYTES + 1)
        draws.require(len(body) <= draws.MAX_MEMBER_BYTES, "panel manifest exceeds operator limit")
        print(json.dumps(score_panel(draws.json_body(body), args.manifest.resolve().parent), allow_nan=False))
    except (ValueError, OSError, UnicodeError, csv.Error) as exc:
        parser.exit(2, f"compare: {exc}\n")


if __name__ == "__main__":
    main()
