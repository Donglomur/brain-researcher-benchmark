"""Compare complete direct and frozen-program responses on one N068 target panel.

Trusted operator assessment only. Prediction labels do not prove access-mode,
observation, compute-budget or fitting compliance. No participant code runs.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path


_spec = importlib.util.spec_from_file_location(
    "_neural068_access_scorer", Path(__file__).with_name("scorer.py"))
scorer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(scorer)

VERSION = "neural068-paired-access-comparison-v1"
CONDITIONS = ("direct_observation", "frozen_program")


def compare(layout, direct_submission, program_submission, target_loader):
    """Keep both original endpoints and report program-minus-direct contrasts.

    Admit both complete 84-context submissions before invoking the target
    loader. Capture each of fourteen target runs once, then score both modes
    with the unchanged session-weighted scorer. Callers must independently
    establish matched permitted observations and frozen condition provenance.
    """
    for submission in (direct_submission, program_submission):
        scorer.validate_submission(layout, submission)

    targets = {}

    def captured(run):
        if run not in targets:
            gold = target_loader(run)
            scorer.exact(gold, ("row_ids", "targets"), "Evaluator targets")
            row = next(row for row in layout["runs"] if row["run"] == run)
            scorer.require(gold["row_ids"] == row["row_ids"], "Exact evaluator target row order")
            scorer.matrix(gold["targets"], len(row["row_ids"]), "Targets")
            # Freeze values even when a loader reuses mutable buffers across runs.
            targets[run] = {"row_ids": list(gold["row_ids"]),
                            "targets": [list(values) for values in gold["targets"]]}
        return targets[run]

    scores = {name: scorer.score(layout, submission, captured)
              for name, submission in zip(CONDITIONS, (direct_submission, program_submission))}
    base = {"schema": VERSION, "packet_id": layout["packet_id"],
            "contrast_direction": "frozen_program_minus_direct_observation",
            "condition_scores": scores,
            "matched_panel": {"runs": 14, "sessions": 7, "contexts_per_condition": 84,
                              "biological_participants": 1,
                              "full_rows": scores[CONDITIONS[0]]["full_rows"],
                              "scored_rows": scores[CONDITIONS[0]]["scored_rows"]},
            "access_compliance_verified": False, "scientific_qualification": False,
            "uncertainty_scope": "Descriptive paired sessions from one person; no population confidence interval."}
    if any(scores[name]["status"] != "scored" for name in CONDITIONS):
        return {**base, "status": "undefined_constant_target_session", "by_session": None,
                "absolute_r2_difference": None, "recalibration_gain_difference": None,
                "neural_minus_clock_recalibration_gain_difference": None}

    paired = []
    for direct, program in zip(*(scores[name]["by_session"] for name in CONDITIONS)):
        scorer.require(direct["session"] == program["session"] and direct["runs"] == program["runs"],
                       "Exact paired session/run support")
        absolute, gain = {}, {}
        for arm in scorer.ARMS:
            absolute[arm], gain[arm] = {}, {}
            for budget in scorer.BUDGETS:
                key = str(budget)
                d, p = direct["metrics"][arm], program["metrics"][arm]
                absolute[arm][key] = scorer.finite_sum((p[key]["r2"], -d[key]["r2"]))
                gain[arm][key] = scorer.finite_sum(
                    (p[key]["r2"], -p["0"]["r2"], -d[key]["r2"], d["0"]["r2"]))
        adjusted = {str(b): scorer.finite_sum((gain["neural_clock"][str(b)],
                                             -gain["clock_only"][str(b)])) for b in scorer.BUDGETS}
        paired.append({"session": direct["session"], "runs": direct["runs"],
                       "absolute_r2_difference": absolute, "recalibration_gain_difference": gain,
                       "neural_minus_clock_recalibration_gain_difference": adjusted})

    def average(values):
        return scorer.finite_sum(value / len(paired) for value in values)

    def average_curve(field):
        return {arm: {str(b): average(row[field][arm][str(b)] for row in paired)
                      for b in scorer.BUDGETS} for arm in scorer.ARMS}

    return {**base, "status": "compared", "by_session": paired,
            "absolute_r2_difference": average_curve("absolute_r2_difference"),
            "recalibration_gain_difference": average_curve("recalibration_gain_difference"),
            "neural_minus_clock_recalibration_gain_difference": {
                str(b): average(row["neural_minus_clock_recalibration_gain_difference"][str(b)]
                                for row in paired) for b in scorer.BUDGETS}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--layout", required=True)
    parser.add_argument("--direct", required=True)
    parser.add_argument("--program", required=True)
    parser.add_argument("--targets", required=True, help="Operator-only complete target panel")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    layout, direct, program = (scorer.read_json(path) for path in (args.layout, args.direct, args.program))
    for submission in (direct, program):
        scorer.validate_submission(layout, submission)
    targets = scorer.read_json(args.targets)
    scorer.exact(targets, (run for run, _ in scorer.RUNS), "Target roster")
    result = compare(layout, direct, program, targets.__getitem__)
    Path(args.output).write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
