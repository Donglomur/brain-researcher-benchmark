"""Bounded engineering fixtures. These are not neural data or a model run."""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path

import evaluator as e


def make_training():
    protocol = {
        "task_id": e.TASK_ID, "profile": "prospective_causal",
        "reference_kind": "generated_engineering_control",
        "sessions": list(e.SESSIONS), "dimensions": list(e.DIMENSIONS),
        "folds": [1, 2, 3, 4, 5], "filter_past_support_samples": 0,
        "filter_future_support_samples": 0, "purge_samples": 0,
        "neural_lag_samples": 1, "held_behavior_used": False,
        "session_sample_counts": {s: 20 for s in e.SESSIONS},
        "animal_ids": {s: "indy" for s in e.SESSIONS},
    }
    cases = []
    for s in e.SESSIONS:
        for fold in range(1, 6):
            ids = [x for x in range(20) if x not in e.held_ids(protocol, s, fold)]
            dimensions = {}
            for d in e.DIMENSIONS:
                candidates = {}
                for a in e.ARCHITECTURES:
                    candidates[a] = {
                        "inner_neural_cc": [.8, .8] if a == "Cy:1x64" else [.3, .3],
                        "inner_behavior_cc": [.8, .8] if a == "Cz:1x64" else [.3, .3],
                        "training_neural_cc": .8 if d == 4 else .4,
                        "training_behavior_cc": .8 if d == 8 else .4,
                    }
                dimensions[str(d)] = candidates
            cases.append({"session_id": s, "fold": fold, "fit_sample_ids": ids,
                          "selection_sample_ids": ids, "dimensions": dimensions})
    return {"protocol": protocol, "cases": cases}


def make_artifacts(training, plan):
    p = training["protocol"]
    targets = {"protocol": p, "cases": []}
    predictions = {"protocol": p, "selection_plan_sha256": e.digest(plan), "cases": []}
    x, z = [-1., -1., 1., 1.], [-1., 1., -1., 1.]
    for case in plan["cases"]:
        s, f = case["session_id"], case["fold"]
        common = {"session_id": s, "fold": f, "sample_ids": e.held_ids(p, s, f)}
        truth = [[a, b] for a, b in zip(x, z)]
        targets["cases"].append({**common, "neural": truth, "behavior": truth})
        for m in e.METHODS:
            for d in e.DIMENSIONS:
                rho_n = .2 + .06 * e.METHODS.index(m)
                rho_b = .6 - .04 * e.METHODS.index(m)
                def correlated(rho):
                    return [[rho*a + math.sqrt(1-rho*rho)*b,
                             rho*b + math.sqrt(1-rho*rho)*a] for a, b in zip(x, z)]
                predictions["cases"].append({**common, "method": m, "dimension": d,
                    "architecture": case["methods"][m]["architectures"][str(d)],
                    "neural": correlated(rho_n), "behavior": correlated(rho_b)})
    return targets, predictions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    training = make_training()
    plan = e.select(training)
    targets, predictions = make_artifacts(training, plan)
    for name, value in (("training", training), ("selection", plan), ("targets", targets), ("predictions", predictions)):
        (out / (name + ".json")).write_text(json.dumps(value, separators=(",", ":"), allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
