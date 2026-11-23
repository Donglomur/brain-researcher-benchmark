"""Published prior-decoding effect sizes from operator-owned predictions.

This is an arithmetic/identity component, not a qualified benchmark or fitting
pipeline. Input JSONL contains one real draw and 1,000 pseudosession draws per
cell; each draw contains ten out-of-fold predictions. No pickle is loaded.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path


TASK_ID = "PAPER-FIND-004"
SCHEMA = "paper-find-004/journal-metrics-v2"
RUN_IDS = set(range(10))
DRAW_IDS = {-1, *range(1, 1001)}
OUTER_FOLDS = {"ephys": 5, "wfi": 50}


class MetricError(ValueError):
    """Incomplete or incompatible prediction evidence."""


def require(condition, message):
    if not condition:
        raise MetricError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def nonfinite(value):
        raise MetricError(f"nonfinite JSON number: {value}")

    return json.loads(text, object_pairs_hook=pairs, parse_constant=nonfinite)


def vector(value, name, n=None):
    require(isinstance(value, list) and len(value) >= 2, f"{name}: nonempty vector required")
    require(n is None or len(value) == n, f"{name}: wrong trial count")
    require(all(type(x) in (int, float) and math.isfinite(x) for x in value),
            f"{name}: finite numbers required")
    return value


def pooled_r2(target, prediction):
    target = vector(target, "target")
    prediction = vector(prediction, "prediction", len(target))
    center = statistics.fmean(target)
    total = math.fsum((x - center) ** 2 for x in target)
    require(total > 0, "constant target has undefined R-squared")
    try:
        result = 1 - math.fsum((x - y) ** 2 for x, y in zip(target, prediction)) / total
    except OverflowError as exc:
        raise MetricError("prediction error overflow") from exc
    require(math.isfinite(result), "nonfinite R-squared")
    return result


def trial_ids(value):
    require(isinstance(value, list) and len(value) >= 250,
            "published session inclusion requires at least 250 retained trials")
    require(all(isinstance(x, str) and x for x in value) and len(set(value)) == len(value),
            "unique ordered original trial IDs required")
    return value


def cell_key(value):
    require(isinstance(value, dict), "cell metadata must be an object")
    fields = ("modality", "subject", "eid", "region", "predictor")
    require(all(isinstance(value.get(f), str) and value[f] for f in fields),
            "complete cell identity required")
    require(value["modality"] in OUTER_FOLDS, "unsupported modality")
    require(value["predictor"] in ("neural", "movement"), "unsupported predictor")
    require(value["region"] not in ("root", "void"), "anatomical region required")
    # The paper's DLC comparison is a separate Ephys subset, not all neural cells.
    require(value["predictor"] != "movement" or value["modality"] == "ephys",
            "the supported movement comparison belongs to the Ephys subset")
    return tuple(value[f] for f in fields)


def check_folds(assignments, n_trials, modality):
    """Validate supplied outer partitions, not the honesty of model fitting."""
    count = OUTER_FOLDS[modality]
    require(isinstance(assignments, list) and len(assignments) == n_trials and
            all(type(x) is int for x in assignments), "integer test fold per trial required")
    require(set(assignments) == set(range(count)), f"all {count} outer folds required")
    sizes = [assignments.count(i) for i in range(count)]
    require(max(sizes) - min(sizes) <= 1, "outer folds must form balanced trial partitions")


def score_draw(draw, expected_trials, modality):
    """Pool trials before scoring, then take the median of ten run scores.

    The paper separately averages predictions for decoded-prior analyses. That
    average must not be substituted into the R-squared endpoint calculated here.
    """
    require(isinstance(draw, dict), "draw must be an object")
    require(draw.get("trial_ids") == expected_trials, "draw retained trial order changed")
    target = vector(draw.get("target"), "prior target", len(expected_trials))
    require(all(0 <= x <= 1 for x in target), "prior targets must lie in [0,1]")
    runs = draw.get("runs")
    require(isinstance(runs, list) and len(runs) == 10, "exactly ten repeats required")
    scores, partitions, predictions = {}, {}, {}
    for run in runs:
        require(isinstance(run, dict), "run must be an object")
        run_id = run.get("run_id")
        require(type(run_id) is int and run_id in RUN_IDS and run_id not in scores,
                "unique run IDs 0..9 required")
        check_folds(run.get("test_fold"), len(expected_trials), modality)
        scores[run_id] = pooled_r2(target, run.get("prediction"))
        partitions[run_id] = digest(run["test_fold"])
        predictions[run_id] = digest(run["prediction"])
    return {
        "median_run_r2": statistics.median(scores.values()),
        "target_sha256": digest(target),
        "folds_sha256": digest([partitions[i] for i in range(10)]),
        "predictions_sha256": digest([predictions[i] for i in range(10)]),
    }


def export_native_draw(fits, *, ordered_trial_ids, modality, pseudo_id):
    """Convert ten trusted, already-loaded native fits into one journal draw.

    No file is opened and no pickle or model is loaded. The operator must map
    this draw's retained native indices to original trial identities using its
    actual mask. The native ``n_folds`` scalar is deliberately not authority:
    actual train/test indices must satisfy the modality's journal partition.
    This checks transport and arithmetic, not feature construction, inner CV,
    authentic execution, publication provenance or complete-panel coverage.
    """
    ids = list(trial_ids(ordered_trial_ids))
    require(isinstance(modality, str) and modality in OUTER_FOLDS, "unsupported modality")
    require(type(pseudo_id) is int and pseudo_id in DRAW_IDS,
            "expected real -1 or pseudo ID 1..1000 required")
    require(isinstance(fits, (list, tuple)) and len(fits) == 10,
            "exactly ten trusted native fits required")

    def plain(value):
        return value.tolist() if hasattr(value, "tolist") else value

    def integer(value, name):
        value = value.item() if hasattr(value, "item") else value
        require(type(value) is int, f"native {name} must be an integer")
        return value

    def number(value, name):
        value = value.item() if hasattr(value, "item") else value
        require(type(value) in (int, float) and math.isfinite(value),
                f"native {name} must be a finite number")
        return value

    def scalars(value, name):
        rows = plain(value)
        require(isinstance(rows, (list, tuple)) and len(rows) == len(ids),
                f"native {name} must match original trial identities")
        result = []
        for row in rows:
            row = plain(row)
            require(isinstance(row, (list, tuple)) and len(row) == 1,
                    f"native {name} requires exactly one scalar per trial")
            result.append(number(row[0], name))
        return result

    def indices(value):
        row = plain(value)
        require(isinstance(row, (list, tuple)), "native fold indices must be a sequence")
        result = [integer(x, "index") for x in row]
        require(len(set(result)) == len(result), "duplicate native fold indices")
        return result

    targets, runs = None, []
    universe = set(range(len(ids)))
    fields = ("target", "predictions_test", "scores_test_full", "idxes_train",
              "idxes_test", "pseudo_id", "run_id")
    for fit in fits:
        require(isinstance(fit, dict) and all(k in fit for k in fields),
                "complete trusted native fit dictionary required")
        require(integer(fit["pseudo_id"], "pseudo_id") == pseudo_id,
                "native pseudo identity differs from expected draw")
        target = scalars(fit["target"], "target")
        require(all(0 <= x <= 1 for x in target), "prior targets must lie in [0,1]")
        require(targets is None or target == targets, "target changes across native repeats")
        targets = target
        prediction = scalars(fit["predictions_test"], "prediction")
        reported = number(fit["scores_test_full"], "reported score")
        require(math.isclose(pooled_r2(target, prediction), reported,
                             rel_tol=1e-10, abs_tol=1e-12),
                "native reported score disagrees with pooled prediction score")
        train_rows, test_rows = plain(fit["idxes_train"]), plain(fit["idxes_test"])
        require(isinstance(train_rows, (list, tuple)) and
                isinstance(test_rows, (list, tuple)) and
                len(train_rows) == len(test_rows) == OUTER_FOLDS[modality],
                "wrong actual native outer fold count for modality")
        assignment = [-1] * len(ids)
        for fold_id, (train_row, test_row) in enumerate(zip(train_rows, test_rows)):
            train, test = indices(train_row), indices(test_row)
            require(set(test) <= universe and set(train) == universe - set(test),
                    "native training indices must be the held-out test complement")
            for trial in test:
                require(assignment[trial] == -1, "native trial appears in multiple test folds")
                assignment[trial] = fold_id
        check_folds(assignment, len(ids), modality)
        runs.append({"run_id": integer(fit["run_id"], "run_id"),
                     "prediction": prediction, "test_fold": assignment})
    draw = {"pseudo_id": pseudo_id, "trial_ids": ids, "target": targets, "runs": runs}
    score_draw(draw, ids, modality)
    return draw


def score_cell(metadata, draws):
    """Consume a single cell's draw iterator with O(trials * repeats) storage.

    Input/target-generator hashes are receipts supplied by the operator. They do
    not certify the Bayes model, reaction-time selection, nested inner CV, or
    feature extraction; those require the original prepared source and fitting.
    """
    key = cell_key(metadata)
    require(metadata.get("target_model") == "optBay" and metadata.get("target") == "pLeft",
            "Bayes-optimal pLeft required; block probabilityLeft is not the target")
    ids = trial_ids(metadata.get("trial_ids"))
    count = metadata.get("n_features")
    require(type(count) is int and count >= 5, "at least five units or pixels required")
    require(key[-1] != "movement" or count == 7, "seven-feature movement comparator required")
    for field in ("input_manifest_sha256", "target_generator_sha256"):
        value = metadata.get(field)
        require(isinstance(value, str) and len(value) == 64 and
                all(c in "0123456789abcdef" for c in value), f"{field}: SHA-256 required")
    scored = {}
    for draw in draws:
        require(isinstance(draw, dict), "draw must be an object")
        draw_id = draw.get("pseudo_id")
        require(type(draw_id) is int and draw_id in DRAW_IDS and draw_id not in scored,
                "unique real -1 and pseudo IDs 1..1000 required")
        scored[draw_id] = score_draw(draw, ids, key[0])
    require(set(scored) == DRAW_IDS, "complete real plus 1000 pseudosessions required")
    real = scored[-1]["median_run_r2"]
    null = [scored[i]["median_run_r2"] for i in range(1, 1001)]
    null_median = statistics.median(null)
    return {
        **{f: metadata[f] for f in ("modality", "subject", "eid", "region", "predictor")},
        "input_manifest_sha256": metadata["input_manifest_sha256"],
        "target_generator_sha256": metadata["target_generator_sha256"],
        "n_features": count, "n_trials": len(ids), "r2": real,
        "median_null_r2": null_median, "corrected_r2": real - null_median,
        "n_runs": 10, "n_pseudosessions": 1000,
        "trial_ids_sha256": digest(ids),
        "actual_target_sha256": scored[-1]["target_sha256"],
        "actual_folds_sha256": scored[-1]["folds_sha256"],
        "actual_predictions_sha256": scored[-1]["predictions_sha256"],
        # Keep target/partition identity separate from model-dependent scores
        # and predictions. This covers the null draws as well as the real draw.
        "draw_targets_sha256": digest([{"pseudo_id": i,
                                         "target_sha256": scored[i]["target_sha256"]}
                                        for i in [-1, *range(1, 1001)]]),
        "draw_folds_sha256": digest([{"pseudo_id": i,
                                       "folds_sha256": scored[i]["folds_sha256"]}
                                      for i in [-1, *range(1, 1001)]]),
        "draw_receipts_sha256": digest([{"pseudo_id": i, **scored[i]}
                                       for i in [-1, *range(1, 1001)]]),
    }


def summarize_panel(expected_cells, summaries):
    """Preserve the frozen declared roster and separate the movement subset.

    This returns a vector of regional effects. There is no source-authorized
    scalar over all regions/modalities, superiority threshold or p-value policy.
    """
    require(isinstance(expected_cells, list) and expected_cells, "frozen cell roster required")
    expected = [cell_key(x) for x in expected_cells]
    actual = [cell_key(x) for x in summaries]
    require(len(set(expected)) == len(expected) and len(set(actual)) == len(actual),
            "duplicate region-session-predictor")
    require(set(expected) == set(actual), "cell population differs from frozen roster")
    require(any(k[-1] == "neural" for k in actual), "neural cells required")
    groups, owners, by_key = defaultdict(list), {}, dict(zip(actual, summaries))
    movement, movement_sessions = [], {}
    for row in summaries:
        key = cell_key(row)
        session = key[:1] + key[2:3]
        require(session not in owners or owners[session] == row["subject"],
                "session assigned to multiple mice")
        owners[session] = row["subject"]
        if key[-1] == "neural":
            groups[(row["modality"], row["region"])].append(row)
        else:
            movement_owner = (row["subject"], row["eid"])
            if movement_owner in movement_sessions:
                previous = movement_sessions[movement_owner]
                require(all(row[f] == previous[f] for f in
                            ("trial_ids_sha256", "actual_target_sha256", "actual_folds_sha256",
                             "actual_predictions_sha256", "r2")),
                        "movement comparator must be one session-level fit across regions")
            movement_sessions[movement_owner] = row
            neural = by_key.get(key[:-1] + ("neural",))
            require(neural is not None, "unmatched movement cell")
            require(all(row[f] == neural[f] for f in
                        ("trial_ids_sha256", "actual_target_sha256")),
                    "movement and neural trial/target identities differ")
            movement.append({
                **{f: row[f] for f in ("modality", "subject", "eid", "region")},
                "neural_r2": neural["r2"], "movement_r2": row["r2"],
                "neural_minus_movement_r2": neural["r2"] - row["r2"],
                "same_outer_partitions": row["actual_folds_sha256"] == neural["actual_folds_sha256"],
                "interpretation": "descriptive_matched_decoding_not_residual_or_causal",
            })
    regions = []
    for (modality, region), rows in sorted(groups.items()):
        regions.append({
            "modality": modality, "region": region,
            "n_sessions": len(rows), "n_mice": len({r["subject"] for r in rows}),
            "mean_session_r2": statistics.fmean(r["r2"] for r in rows),
            "mean_session_corrected_r2": statistics.fmean(r["corrected_r2"] for r in rows),
        })
    return {"regional_effects": regions, "movement_comparisons": movement,
            "n_neural_cells": sum(k[-1] == "neural" for k in actual),
            "n_movement_cells": len(movement)}


def score_file(path, metadata, expected_sha256):
    """Score and hash the same bytes in one pass; only one draw is retained."""
    require(isinstance(expected_sha256, str), "prediction file hash required")
    sha = hashlib.sha256()

    def draws():
        with path.open("rb") as source:
            for line in source:
                sha.update(line)
                require(line.strip(), "blank JSONL record")
                yield strict_json(line)

    result = score_cell(metadata, draws())
    require(sha.hexdigest() == expected_sha256, "prediction file hash mismatch")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        manifest = strict_json(args.manifest.read_text())
        require(isinstance(manifest, dict) and manifest.get("schema") == SCHEMA,
                "journal-metrics-v2 manifest required")
        entries = manifest.get("cells")
        require(isinstance(entries, list) and entries, "nonempty cells required")
        summaries = [score_file(args.manifest.parent / x["prediction_file"], x,
                                x["prediction_file_sha256"]) for x in entries]
        panel = summarize_panel(manifest["expected_cells"], summaries)
        result = {
            "task_id": TASK_ID, "schema": SCHEMA,
            "scope": "published_metric_arithmetic_on_operator_declared_cells",
            "manifest_sha256": digest(manifest), "cells": summaries, **panel,
            "unresolved": ["original cohort and input objects", "publication-linked baseline vector",
                           "source runtime and exact original folds", "target and pseudosession generation",
                           "nested fitting and companion-control execution", "paired uncertainty and improvement rule"],
        }
        args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.exit(2, f"Metric input rejected: {exc}\n")


if __name__ == "__main__":
    main()
