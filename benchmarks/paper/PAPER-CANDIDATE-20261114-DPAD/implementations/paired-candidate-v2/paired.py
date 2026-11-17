"""Paired candidate/author prediction evaluation for the original DPAD endpoint.

No fitting, data preparation, source equivalence or paper-win admission is done.
The owner must protect training records, targets, plans and reference digests.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
from statistics import mean

LEGACY = Path(__file__).resolve().parents[1] / "initial-evaluator-v1" / "evaluator.py"
LEGACY_SHA256 = "719931616b93504815b0becc0135278d4e55d41ce689b681f241bf79d7a6d3f3"
if hashlib.sha256(LEGACY.read_bytes()).hexdigest() != LEGACY_SHA256:
    raise RuntimeError("predecessor evaluator changed; review metric lineage before use")
_spec = importlib.util.spec_from_file_location("dpad_initial_evaluator", LEGACY)
e = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(e)

FOLDS = set(itertools.product(e.SESSIONS, range(1, 6)))
BEHAVIOR = ("position_x", "position_y", "velocity_x", "velocity_y")
LIMITS = [
    "Strict finite/full-coverage channel means retain predecessor semantics; original invalid-row and channel sanitization equivalence is unresolved.",
    "Seven session IDs remain the predecessor's unverified wideband crosswalk; supplied channel identities do not authenticate the original 32-electrode sample.",
    "Frozen predictions and training-score declarations do not certify native author reproduction, allowed observations, training-only selection or chronology.",
    "All 35 folds come from seven sessions of one monkey with overlapping training data; descriptive SEM and frontier diagnostics are not independent-animal inference.",
    "No numerical published Figure 6i baseline, meaningful joint-effect admission rule, scientific reproduction or scientific improvement is established.",
]


def sha(value, label):
    e.require(isinstance(value, str) and len(value) == 64
              and all(c in "0123456789abcdef" for c in value), label + " needs lowercase SHA256")
    return value


def identifier(value, label):
    e.require(isinstance(value, str) and value.strip() == value and 0 < len(value) <= 160,
              label + " needs a nonempty identifier")
    return value


def original_protocol(p):
    e.protocol(p)
    e.require(p["profile"] == "historical_symmetric", "causal filtering is a separate task extension")
    e.require(type(p["neural_lag_samples"]) is int and p["neural_lag_samples"] == 1,
              "original endpoint requires exactly one-step-ahead predictions")
    return p


def layout_check(layout):
    """Ordered acquisition-channel identities and units, fixed across folds."""
    e.require(isinstance(layout, dict) and set(layout) == set(e.SESSIONS), "incomplete channel layout")
    for session, kinds in layout.items():
        e.require(set(kinds) == {"neural", "behavior"}, "layout requires both endpoints")
        for kind in ("neural", "behavior"):
            channels = kinds[kind]
            e.require(isinstance(channels, list), "channel layout must be ordered")
            e.require(77 <= len(channels) <= 99 if kind == "neural" else len(channels) == 4,
                      "original cohort requires 77-99 units and four behavior channels")
            for channel in channels:
                e.require(isinstance(channel, dict) and set(channel) == {"id", "unit"}, "channel requires id and unit")
                identifier(channel["id"], "channel id")
                identifier(channel["unit"], "channel unit")
            e.require(len({c["id"] for c in channels}) == len(channels), "duplicate channel identity")
        e.require([c["id"] for c in kinds["behavior"]] == list(BEHAVIOR), "behavior coordinates/order changed")
    return layout


def case_key(row):
    key = (row["session_id"], row["fold"])
    e.require(type(row["fold"]) is int and key in FOLDS, "unknown session/fold")
    return key


def complete_grid(artifact, role, dimensions=False, methods=False):
    """Reject missing/duplicate identities before any array statistics."""
    observed = set()
    for row in artifact["cases"]:
        key = case_key(row)
        if methods:
            e.require(row["method"] in e.METHODS, "unknown author method")
            key += (row["method"],)
        if dimensions:
            e.require(type(row["dimension"]) is int and row["dimension"] in e.DIMENSIONS,
                      "unknown prediction dimension")
            key += (row["dimension"],)
        e.require(key not in observed, "duplicate " + role + " case")
        observed.add(key)
    expected = FOLDS
    if methods:
        expected = {(*k, m) for k in expected for m in e.METHODS}
    if dimensions:
        expected = {(*k, d) for k in expected for d in e.DIMENSIONS}
    e.require(observed == expected, "incomplete " + role + " grid")


def aligned_rows(artifact, p, layout, role):
    e.require(artifact["protocol"] == p and artifact["channel_layout"] == layout,
              role + " protocol/channel identity/unit drift")
    for row in artifact["cases"]:
        session, fold = case_key(row)
        e.require(isinstance(row["sample_ids"], list) and all(type(v) is int for v in row["sample_ids"])
                  and row["sample_ids"] == e.held_ids(p, session, fold), role + " sample identity/order drift")
        for kind in ("neural", "behavior"):
            e.require(row[kind + "_channel_ids"] == [c["id"] for c in layout[session][kind]],
                      role + " per-case channel order drift")
            values = e.matrix(row[kind], role + " " + kind)
            e.require(len(values) == len(row["sample_ids"])
                      and len(values[0]) == len(layout[session][kind]), role + " matrix/identity shape mismatch")


def freeze_reference(training, targets, predictions):
    """Run the unchanged full author-grid scorer, then retain scores and hashes."""
    p = original_protocol(targets["protocol"])
    layout = layout_check(targets["channel_layout"])
    e.require(training["protocol"] == p and training["channel_layout"] == layout,
              "author training protocol/channel layout drift")
    complete_grid(targets, "target")
    complete_grid(predictions, "author", dimensions=True, methods=True)
    aligned_rows(targets, p, layout, "targets")
    aligned_rows(predictions, p, layout, "author")
    plan = e.select(training)
    result = e.evaluate(targets, predictions, plan)
    return {
        "schema": "dpad-author-reference-v2", "protocol": p, "channel_layout": layout,
        "targets_sha256": e.digest(targets), "training_sha256": e.digest(training),
        "predictions_sha256": e.digest(predictions), "selection_plan_sha256": e.digest(plan),
        "predecessor_sha256": LEGACY_SHA256, "source_grid_results": result,
        "qualification": "unverified_author_prediction_reference", "scientific_reproduction": "not_assessed",
        "limitations": LIMITS,
    }


def select_candidate(training):
    """Freeze arbitrary candidate configurations using original train-only peaks.

    The candidate is not forced to use DPAD's 90 author architectures or n1.
    Complete author controls remain in the separate reference artifact.
    """
    p = original_protocol(training["protocol"])
    layout = layout_check(training["channel_layout"])
    method = identifier(training["candidate_id"], "candidate id")
    e.require(method not in e.METHODS, "candidate id collides with an author method")
    sha(training["code_sha256"], "candidate code")
    rows = {}
    for row in training["cases"]:
        key = e.check_provenance(p, row)
        e.require(key not in rows, "duplicate candidate training fold")
        curve = row["dimensions"]
        e.require(set(curve) == set(map(str, e.DIMENSIONS)), "candidate dimension grid incomplete")
        for values in curve.values():
            sha(values["configuration_sha256"], "candidate configuration")
        dimension = e.choose_dimension({int(d): values for d, values in curve.items()})
        rows[key] = {"session_id": key[0], "fold": key[1], "selected_dimension": dimension,
                     "dimensions": curve}
    e.require(set(rows) == FOLDS, "candidate training must cover all 35 folds")
    return {"schema": "dpad-candidate-plan-v2", "protocol": p, "channel_layout": layout,
            "candidate_id": method, "code_sha256": training["code_sha256"],
            "training_sha256": e.digest(training), "cases": [rows[k] for k in sorted(rows)],
            "qualification": "training_metadata_selection_only"}


def compare(targets, reference, plan, predictions, reference_sha256, plan_sha256):
    """Evaluate all candidate dimensions and pair against all seven author arms.

    The two expected hashes must come from the owner's protected freeze record,
    not from the submitting participant. Hashes bind content, not chronology.
    """
    e.require(e.digest(reference) == sha(reference_sha256, "frozen author reference"), "author reference changed")
    e.require(e.digest(plan) == sha(plan_sha256, "frozen candidate plan"), "candidate selection plan changed")
    e.require(reference["schema"] == "dpad-author-reference-v2"
              and reference["predecessor_sha256"] == LEGACY_SHA256, "unknown author reference lineage")
    e.require(plan["schema"] == "dpad-candidate-plan-v2", "unknown candidate plan")
    p = original_protocol(targets["protocol"])
    layout = layout_check(targets["channel_layout"])
    e.require(reference["protocol"] == p and plan["protocol"] == p
              and reference["channel_layout"] == layout and plan["channel_layout"] == layout,
              "paired protocol/channel layout changed")
    e.require(reference["targets_sha256"] == e.digest(targets), "paired targets changed")
    e.require(predictions["selection_plan_sha256"] == plan_sha256
              and predictions["candidate_id"] == plan["candidate_id"]
              and predictions["code_sha256"] == plan["code_sha256"], "candidate binding changed")
    identifier(plan["candidate_id"], "candidate id")
    e.require(plan["candidate_id"] not in e.METHODS, "candidate id collides with author")
    sha(plan["code_sha256"], "candidate code")
    complete_grid(targets, "target")
    complete_grid(predictions, "candidate", dimensions=True)
    aligned_rows(targets, p, layout, "targets")
    aligned_rows(predictions, p, layout, "candidate")
    target_rows, plan_rows = {}, {}
    for row in targets["cases"]:
        key = case_key(row)
        e.require(key not in target_rows, "duplicate target fold")
        target_rows[key] = row
    for row in plan["cases"]:
        key = case_key(row)
        e.require(key not in plan_rows, "duplicate candidate plan fold")
        chosen = e.choose_dimension({int(d): v for d, v in row["dimensions"].items()})
        e.require(type(row["selected_dimension"]) is int and chosen == row["selected_dimension"], "candidate dimension changed")
        plan_rows[key] = row
    e.require(set(target_rows) == FOLDS and set(plan_rows) == FOLDS, "paired folds incomplete")
    grid = {}
    for row in predictions["cases"]:
        key, dimension = case_key(row), row["dimension"]
        e.require(type(dimension) is int and dimension in e.DIMENSIONS, "unknown candidate dimension")
        full_key = (*key, dimension)
        e.require(full_key not in grid, "duplicate candidate dimension/fold")
        e.require(sha(row["configuration_sha256"], "prediction configuration")
                  == plan_rows[key]["dimensions"][str(dimension)]["configuration_sha256"], "candidate configuration changed")
        scores = {kind: e.channel_cc(target_rows[key][kind], row[kind]) for kind in ("neural", "behavior")}
        e.require(all(score["mean_cc"] is not None for score in scores.values()), "undefined candidate channel cannot be omitted")
        grid[full_key] = {"session_id": key[0], "fold": key[1], "dimension": dimension, **scores}
    expected = {(*key, d) for key in FOLDS for d in e.DIMENSIONS}
    e.require(set(grid) == expected, "complete 280-case candidate dimension grid required")
    selected = {key: grid[(*key, plan_rows[key]["selected_dimension"])] for key in sorted(FOLDS)}

    author = {}
    source_result = reference["source_grid_results"]
    e.require(source_result["targets_sha256"] == reference["targets_sha256"], "reference target lineage mismatch")
    for row in source_result["selected_scores"]:
        key = (*case_key(row), row["method"])
        e.require(row["method"] in e.METHODS and key not in author, "invalid author contrast identity")
        author[key] = row
        for kind in ("neural", "behavior"):
            e.cc_number(row[kind]["mean_cc"], "author " + kind)
    e.require(set(author) == {(*key, m) for key in FOLDS for m in e.METHODS}, "all 245 author controls required")
    paired = []
    for key, method in itertools.product(sorted(FOLDS), e.METHODS):
        paired.append({"session_id": key[0], "fold": key[1], "comparator": method,
                       **{kind + "_cc_delta": selected[key][kind]["mean_cc"] - author[(*key, method)][kind]["mean_cc"]
                          for kind in ("neural", "behavior")}})
    vectors = {m: {kind + "_cc": [author[(*key, m)][kind]["mean_cc"] for key in sorted(FOLDS)]
                   for kind in ("neural", "behavior")} for m in e.METHODS}
    vectors[plan["candidate_id"]] = {kind + "_cc": [selected[key][kind]["mean_cc"] for key in sorted(FOLDS)]
                                     for kind in ("neural", "behavior")}
    return {"schema": "dpad-paired-candidate-results-v2", "task_id": e.TASK_ID,
            "candidate_id": plan["candidate_id"], "reference_sha256": reference_sha256,
            "plan_sha256": plan_sha256, "predictions_sha256": e.digest(predictions),
            "targets_sha256": reference["targets_sha256"],
            "candidate_grid_scores": [grid[k] for k in sorted(grid)],
            "candidate_selected_scores": list(selected.values()), "paired_fold_deltas": paired,
            "paper_unit_summary": {m: {metric: e.summary(values) for metric, values in scores.items()}
                                   for m, scores in vectors.items()},
            "paired_session_deltas": [{"session_id": s, "comparator": m,
                                       **{kind + "_cc_delta": mean(r[kind + "_cc_delta"] for r in paired
                                                                  if r["session_id"] == s and r["comparator"] == m)
                                          for kind in ("neural", "behavior")}}
                                      for s, m in itertools.product(e.SESSIONS, e.METHODS)],
            "frontier_calibration_diagnostic": e.frontier(vectors),
            "qualification": "prediction_scoring_component_only", "scientific_reproduction": "not_assessed",
            "scientific_improvement": "not_assessed",
            "limitations": LIMITS}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    freeze = sub.add_parser("freeze-author")
    for name in ("training", "targets", "predictions"):
        freeze.add_argument("--" + name, required=True)
    select = sub.add_parser("select-candidate")
    select.add_argument("--training", required=True)
    score = sub.add_parser("compare")
    for name in ("targets", "reference", "plan", "predictions", "reference-sha256", "plan-sha256"):
        score.add_argument("--" + name, required=True)
    for command in (freeze, select, score):
        command.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        if args.command == "freeze-author":
            result = freeze_reference(e.read_json(args.training), e.read_json(args.targets), e.read_json(args.predictions))
        elif args.command == "select-candidate":
            result = select_candidate(e.read_json(args.training))
        else:
            result = compare(e.read_json(args.targets), e.read_json(args.reference), e.read_json(args.plan),
                             e.read_json(args.predictions), args.reference_sha256, args.plan_sha256)
        Path(args.output).write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
        print(json.dumps({"schema": result["schema"], "canonical_sha256": e.digest(result)}))
    except (e.ContractError, KeyError, TypeError, ValueError, OSError) as exc:
        parser.exit(2, "DPAD paired input rejected: " + str(exc) + "\n")


if __name__ == "__main__":
    main()
