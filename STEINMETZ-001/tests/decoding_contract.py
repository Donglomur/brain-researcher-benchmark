"""Recompute every fold and window×split summary from source-bound OOF rows."""
from pathlib import Path
import numpy as np

from proof_of_work import (PIPELINE_ID, RECIPES, SPLITS, PRIMARY_RECIPE, N_FOLDS,
    ARITHMETIC_ATOL, NUMERICAL_ATOL, NUMERICAL_RTOL, TIMING_KEYS, number, integer,
    fraction, match_contract, recipe_split, train_majority, sigmoid, timing_counts,
    validate_selection_counts, load_trial_predictions, load_folds, read_json)


def validate_predictions(groups, reference):
    assert set(groups) == set(RECIPES), "all four OOF recipes required"
    ids, y = reference["trial_ids"], reference["true_choice"]
    arrays = {}
    for recipe in RECIPES:
        rows = groups[recipe]
        assert set(rows) == set(ids), "exact complete source trial IDs required for each recipe"
        ordered = [rows[int(trial_id)] for trial_id in ids]
        values = {field: np.asarray([row[field] for row in ordered]) for field in (
            "fold", "true_choice", "predicted_choice", "baseline_choice", "decision_value", "probability_left")}
        split = recipe_split(recipe)
        assert np.array_equal(values["fold"], reference[f"fold_{split}"]), "OOF fold identity differs from declared split"
        assert np.array_equal(values["true_choice"], y), "OOF signed truth differs from source"
        assert np.array_equal(values["predicted_choice"], reference[f"predicted_choice_{recipe}"]), "OOF predictions differ from declared source recipe"
        baseline = train_majority(y, values["fold"])
        assert np.array_equal(values["baseline_choice"], baseline), "OOF baseline must use training-fold majority"
        for field, source in (("decision_value", f"decision_{recipe}"), ("probability_left", f"probability_left_{recipe}")):
            assert np.isfinite(values[field]).all() and np.allclose(values[field], reference[source],
                atol=NUMERICAL_ATOL, rtol=NUMERICAL_RTOL), f"OOF {field} differs from declared source recipe"
        assert np.allclose(values["probability_left"], sigmoid(values["decision_value"]),
                           atol=NUMERICAL_ATOL, rtol=NUMERICAL_RTOL), "OOF probability/decision linkage differs"
        assert np.array_equal(values["predicted_choice"], np.where(values["decision_value"] > 0, 1, -1)), "OOF predicted label/decision sign differs"
        arrays[recipe] = values
    return arrays


def fold_metrics(arrays):
    metrics = {}
    for recipe, values in arrays.items():
        y, predictions, folds = values["true_choice"], values["predicted_choice"], values["fold"]
        baseline = train_majority(y, folds)
        for fold in range(N_FOLDS):
            test = folds == fold
            assert test.any(), "empty held-out fold"
            correct = int(np.sum(predictions[test] == y[test]))
            baseline_correct = int(np.sum(baseline[test] == y[test]))
            n = int(test.sum())
            metrics[(recipe, fold)] = {"n_train": len(y)-n, "n_test": n, "n_correct": correct,
                "accuracy": correct/n, "baseline_choice": int(baseline[test][0]),
                "baseline_n_correct": baseline_correct, "baseline_accuracy": baseline_correct/n}
    return metrics


def validate_folds(submitted, arrays, reference=None):
    expected = fold_metrics(arrays)
    assert set(submitted) == set(expected), "exact20 recipe/fold rows required"
    for key, metrics in expected.items():
        actual = submitted[key]
        for field in ("n_train", "n_test", "n_correct", "baseline_n_correct"):
            assert integer(actual[field]) == metrics[field], f"incorrect {key} {field}"
        assert number(actual["baseline_choice"]) == metrics["baseline_choice"], "fold baseline label differs from train majority"
        for field in ("accuracy", "baseline_accuracy"):
            assert abs(fraction(actual[field])-metrics[field]) <= ARITHMETIC_ATOL, f"incorrect {key} recomputed {field}"
    return expected


def result_metrics(arrays, reference):
    folds = fold_metrics(arrays)
    means, pooled, deviations = {}, {}, {}
    baseline_means, baseline_pooled = {}, {}
    for recipe in RECIPES:
        values = [folds[(recipe, fold)]["accuracy"] for fold in range(N_FOLDS)]
        means[recipe], deviations[recipe] = float(np.mean(values)), float(np.std(values, ddof=0))
        pooled[recipe] = float(np.mean(arrays[recipe]["predicted_choice"] == arrays[recipe]["true_choice"]))
    for split in SPLITS:
        values = [folds[(f"stimulus_{split}", fold)]["baseline_accuracy"] for fold in range(N_FOLDS)]
        baseline_means[split] = float(np.mean(values))
        baseline_pooled[split] = float(np.mean(reference[f"baseline_choice_{split}"] == reference["true_choice"]))
    y = reference["true_choice"]
    return {"cross_validated_accuracy": means[PRIMARY_RECIPE], "accuracy_by_window_and_split": means,
        "pooled_accuracy_by_window_and_split": pooled, "accuracy_std_by_window_and_split": deviations,
        "baseline_accuracy_by_split": baseline_means, "pooled_baseline_accuracy_by_split": baseline_pooled,
        "global_majority_fraction": float(max(np.mean(y == -1), np.mean(y == 1)))}


def validate_results(result, arrays, reference):
    assert result.get("status") == "ok" and result.get("pipeline_id") == PIPELINE_ID, "incorrect result status/pipeline"
    assert integer(result["n_trials"]) == len(reference["trial_ids"]), "incorrect source trial count"
    assert integer(result["n_units"]) == len(reference["unit_ids"]), "incorrect source unit count"
    validate_selection_counts(result["selection_counts"], len(reference["trial_ids"]), len(reference["unit_ids"]))
    assert result["selection_counts"] == reference["stats"]["selection_counts"], "incorrect source selection counts"
    expected_timing = timing_counts(reference["stimulus_times"], reference["response_times"])
    assert set(result["response_timing_counts"]) == TIMING_KEYS
    for key, expected in expected_timing.items():
        assert integer(result["response_timing_counts"][key]) == expected, "incorrect half-open registered-response timing count"
    expected = result_metrics(arrays, reference)
    for key, values in expected.items():
        actual = result[key]
        if isinstance(values, dict):
            assert isinstance(actual, dict) and set(actual) == set(values), f"incorrect {key} recipe/split keys"
            for name, value in values.items():
                assert abs(fraction(actual[name])-value) <= ARITHMETIC_ATOL, f"incorrect recomputed {key}/{name}"
        else:
            assert abs(fraction(actual)-values) <= ARITHMETIC_ATOL, f"incorrect recomputed {key}"
    return expected


def validate_metadata(metadata, reference):
    assert metadata.get("status") == "ok", "metadata status must be ok"
    match_contract(metadata, reference["stats"]["metadata_contract"])
    assert metadata["source_sha256"] == reference["stats"]["source_sha256"], "source SHA256 mapping differs"
    assert metadata["primary_recipe"] == PRIMARY_RECIPE, "primary recipe is stimulus_blocked"
    assert integer(metadata["n_trials"]) == len(reference["trial_ids"]), "incorrect metadata trial count"
    assert integer(metadata["n_units"]) == len(reference["unit_ids"]), "incorrect metadata unit count"
    validate_selection_counts(metadata["selection_counts"], len(reference["trial_ids"]), len(reference["unit_ids"]))
    assert metadata["selection_counts"] == reference["stats"]["selection_counts"], "metadata selection counts differ"
    expected_timing = timing_counts(reference["stimulus_times"], reference["response_times"])
    assert set(metadata["response_timing_counts"]) == TIMING_KEYS
    for key, expected in expected_timing.items():
        assert integer(metadata["response_timing_counts"][key]) == expected, "metadata timing counts differ"


def validate_output_directory(output, reference):
    output = Path(output)
    arrays = validate_predictions(load_trial_predictions(output / "trial_predictions.csv"), reference)
    validate_folds(load_folds(output / "folds.csv"), arrays, reference)
    result = validate_results(read_json(output / "results.json"), arrays, reference)
    validate_metadata(read_json(output / "run_metadata.json"), reference)
    assert (output / "findings.md").read_text(encoding="utf-8").strip(), "nonempty findings required"
    return result
