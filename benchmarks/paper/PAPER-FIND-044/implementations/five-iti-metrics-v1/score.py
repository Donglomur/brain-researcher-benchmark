#!/usr/bin/env python3
"""Original five-ITI log-RSS selection and raw-scale AIC, from numeric exports.

This implements metric arithmetic, not source-data preparation or native MATLAB
qualification. Inputs are post-filtering/post-censoring simulation summaries.
See README.md for the source indexing issue that remains before preparation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

CONDITIONS = [30, 60, 300, 600, 3600]
ITERATIONS = 20
SCHEMA = "reward-five-iti-model-scores/v1"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def onset(value):
    """JSON null represents source NaN; real, finite positive onsets otherwise."""
    require(value is None or (type(value) in (int, float)
                             and math.isfinite(value) and value > 0),
            "onsets must be finite positive numbers or null (source NaN)")
    return value


def behavior_matrix(rows):
    require(type(rows) is list and bool(rows), "behavior matrix must be nonempty")
    require(all(type(row) is list and len(row) == 5 for row in rows),
            "behavior matrix must have five ordered ITI columns")
    result = [[onset(value) for value in row] for row in rows]
    require(all(any(row[j] is not None for row in result) for j in range(5)),
            "each original ITI must retain observed animal support")
    return result


def iteration_means(rows):
    """Source mean(TTL,3) propagates NaN; it does not omit failed iterations."""
    require(type(rows) is list and len(rows) == ITERATIONS,
            "exactly twenty simulation iterations are required")
    require(all(type(row) is list and len(row) == 5 for row in rows),
            "each simulation iteration must have five ordered ITI columns")
    values = [[onset(value) for value in row] for row in rows]
    means = []
    for column in zip(*values):
        means.append(None if any(value is None for value in column)
                     else math.fsum(value / ITERATIONS for value in column))
    return means


def source_metrics(behavior, predictions, num_parameters):
    """Port calculate_rss.m and calculate_aic.m without merging their losses.

    Source nAnimals counts non-NaN behavior cells. Raw MSE omits NaN residuals,
    even if caused by a missing prediction; nAnimals is *not* recomputed from
    those residuals. The unequal counts are exposed, never treated as complete.
    """
    observed = behavior_matrix(behavior)
    require(type(predictions) is list and len(predictions) == 5,
            "predictions must have all five ordered ITIs")
    predicted = [onset(value) for value in predictions]
    require(type(num_parameters) is int and num_parameters >= 0,
            "num_parameters must be a nonnegative integer")
    residuals = []
    log_residuals = []
    count = 0
    for row in observed:
        for value, prediction in zip(row, predicted):
            if value is None:
                continue
            count += 1
            if prediction is None:
                # calculate_rss changes log(NaN) predictions to positive inf.
                log_residuals.append(math.inf)
            else:
                log_residuals.append((math.log(value) - math.log(prediction)) ** 2)
                # Multiplication yields inf for out-of-range IEEE residuals.
                difference = value - prediction
                residuals.append(difference * difference)
    raw_mse = (math.fsum(value / len(residuals) for value in residuals)
               if residuals else math.nan)
    log_mse = -math.inf if raw_mse == 0 else math.log(raw_mse)
    aic_k0 = count * log_mse
    aic = aic_k0 + 2 * num_parameters
    denominator = count - num_parameters - 1
    numerator = 2 * num_parameters * (num_parameters + 1)
    correction = (numerator / denominator if denominator
                  else math.inf if numerator else math.nan)
    return {
        "selection_log_rss": math.fsum(log_residuals),
        "raw_scale_mse": raw_mse,
        "AIC_k0": aic_k0,
        "AIC_parameter_penalized": aic,
        "AICc_parameter_penalized_source_value": aic + correction,
        "AICc_sample_size_condition_met": denominator > 0,
        "source_nAnimals": count,
        "raw_residual_count": len(residuals),
        "complete_prediction_support": len(residuals) == count,
    }


def evaluate(document):
    require(type(document) is dict and document.get("schema") == SCHEMA,
            "unsupported input schema")
    require(document.get("conditions_s") == CONDITIONS,
            "exact original ITI order [30,60,300,600,3600] required")
    require(document.get("prediction_stage") == "after_source_filtering_and_censoring",
            "supply post-filtering/post-censoring tensors; this scorer does not prepare them")
    observed = behavior_matrix(document.get("behavior_trials_to_learn"))
    families = document.get("families")
    require(type(families) is list and bool(families), "families must be nonempty")
    result = []
    family_names = set()
    for family in families:
        require(type(family) is dict, "family must be an object")
        name = family.get("name")
        require(type(name) is str and name and name not in family_names,
                "family names must be nonempty and unique")
        family_names.add(name)
        candidates = family.get("candidates")
        require(type(candidates) is list and bool(candidates), "candidate grid must be nonempty")
        summaries = []
        ids = set()
        for index, candidate in enumerate(candidates):
            require(type(candidate) is dict, "candidate must be an object")
            identity = candidate.get("id")
            require(type(identity) is str and identity and identity not in ids,
                    "candidate IDs must be nonempty and unique within family")
            ids.add(identity)
            means = iteration_means(candidate.get("trials_to_learn_by_iteration"))
            summaries.append({"id": identity, "source_order_zero_based": index,
                              "mean_trials_to_learn": means,
                              **source_metrics(observed, means, family.get("num_parameters"))})
        # Stable order preserves the supplied source tensor order on ties.
        order = sorted(range(len(summaries)),
                       key=lambda index: summaries[index]["selection_log_rss"])
        first = summaries[order[0]]
        usable = math.isfinite(first["selection_log_rss"])
        result.append({"name": name, "num_parameters": family["num_parameters"],
                       "candidates": summaries, "log_rss_rank_zero_based": order,
                       "source_first_ranked_id": first["id"],
                       "finite_selection_available": usable,
                       "selected_id": first["id"] if usable else None})
    return {
        "schema": SCHEMA, "conditions_s": CONDITIONS,
        "scope": "five_ITI_metric_arithmetic_only",
        "selection_metric": "natural_log_RSS",
        "reporting_metric": "raw_scale_AIC",
        "families": result,
        "qualification": "source_data_and_native_author_baseline_unqualified",
        "source_preprocessing_authenticated": False,
        "paper_improvement_claim": False,
        "nonfinite_encoding": "NaN, Infinity and -Infinity are JSON strings",
    }


def json_safe(value):
    if isinstance(value, float) and not math.isfinite(value):
        return "NaN" if math.isnan(value) else "Infinity" if value > 0 else "-Infinity"
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = args.input.read_bytes()
    result = evaluate(json.loads(payload))
    result["input_sha256"] = hashlib.sha256(payload).hexdigest()
    result["scorer_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    encoded = json.dumps(json_safe(result), indent=2, allow_nan=False) + "\n"
    if args.output:
        with args.output.open("x") as handle:
            handle.write(encoded)
    else:
        print(encoded, end="")


if __name__ == "__main__":
    main()
