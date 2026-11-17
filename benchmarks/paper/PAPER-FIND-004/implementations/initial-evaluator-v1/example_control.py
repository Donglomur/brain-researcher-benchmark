"""Bounded generated engineering fixture; never empirical evidence."""
import argparse
import json
from pathlib import Path

import evaluator as ev


def make_control(n_trials=250):
    """One paired neural/motor session with all 200 nulls and all ten runs.

    Every null predicts the mean, neural real predictions are perfect, and motor
    real predictions are halfway to the mean. Thus expected R² is 1 versus .75,
    null R²=0 and null p=1/201. One session cannot pass regional admission.
    """
    if n_trials < 50 or n_trials % 50:
        raise ValueError("fixture n_trials must be a positive multiple of 50")
    target = [.2 if i % 2 == 0 else .8 for i in range(n_trials)]
    targets = {str(p): target for p in [-1, *range(1, 201)]}
    folds = [i % 50 for i in range(n_trials)]
    null_prediction = [.5] * n_trials
    cells, expected = [], []
    for predictor in ("neural", "motor"):
        real_prediction = target if predictor == "neural" else [.5 + (p - .5) / 2 for p in target]
        cell = {
            "subject": "generated-mouse", "eid": "generated-session", "region": "VISp",
            "predictor": predictor, "n_units": 10 if predictor == "neural" else 7,
            "trial_ids": [f"generated-trial-{i}" for i in range(n_trials)],
            "input_objects_sha256": ev.digest({"generated": predictor}),
            "target_generator_sha256": ev.digest({"generated": "alternating_prior"}),
            "targets": targets,
            "runs": [{"pseudo_id": p, "run_id": r, "test_fold": folds,
                      "predictions": real_prediction if p == -1 else null_prediction}
                     for p in [-1, *range(1, 201)] for r in range(10)],
        }
        if predictor == "motor":
            cell["feature_names"] = ev.MOTOR_FEATURES.copy()
        expected.append({**{k: cell[k] for k in ("subject", "eid", "region", "predictor", "n_units",
                                               "trial_ids", "input_objects_sha256", "target_generator_sha256")},
                         "targets_sha256": ev.digest(targets)})
        cells.append(cell)
    payload = {"cells": cells}
    manifest = {
        "task_id": ev.TASK_ID, "contract_sha256": ev.CONTRACT_SHA256,
        "protocol": ev.SOURCE_PROTOCOL.copy(), "evidence_kind": "generated_engineering_control",
        "population_scope": "declared_subset_not_paperwide", "expected_cells": expected,
        "population_manifest_sha256": ev.digest({"generated": "one_session"}),
        "exposure_policy_sha256": ev.digest({"generated": "no_authentic_data"}),
        "excluded_exposed_subjects": [], "prediction_payload_sha256": ev.digest(payload),
    }
    return manifest, payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_directory", type=Path)
    args = parser.parse_args()
    args.output_directory.mkdir(parents=True, exist_ok=True)
    manifest, payload = make_control()
    for name, data in (("manifest.json", manifest), ("predictions.json", payload)):
        (args.output_directory / name).write_text(json.dumps(data, separators=(",", ":"), allow_nan=False) + "\n")

if __name__ == "__main__":
    main()
