"""Strict parser/source-identity mechanics; no downloaded data or model fitting."""
import copy
import csv
import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "tests"))
from proof_of_work import (RECIPES, PIPELINE_ID, integer, choice, fraction, number,
    read_json, load_trial_predictions, load_folds, match_contract, validate_selection_counts)
from decoding_contract import (validate_predictions, validate_results, validate_metadata,
    result_metrics, fold_metrics)
from test_folds import mechanics_fixture


def write_csv(path, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def trial_rows(groups):
    return [{"recipe": recipe, "trial_id": trial, **row}
            for recipe, values in groups.items() for trial, row in values.items()]


@pytest.mark.parametrize("value", [True, False, "NaN", "inf", "-inf"])
def test_nonfinite_and_boolean_numbers_fail(value):
    with pytest.raises((AssertionError, ValueError)):
        number(value)


@pytest.mark.parametrize("value", [-1, .5, "1.1"])
def test_integer_identity_is_not_rounded(value):
    with pytest.raises(AssertionError):
        integer(value)


def test_reasonable_integer_numeric_notation():
    assert integer("4.0") == integer("4e0") == 4
    assert choice("+1.0") == 1 and choice("-1") == -1


@pytest.mark.parametrize("value", [0, 2, -.5])
def test_choice_is_signed_not_boolean_or_zero_one(value):
    with pytest.raises(AssertionError):
        choice(value)


@pytest.mark.parametrize("value", [-.01, 1.01])
def test_probability_range(value):
    with pytest.raises(AssertionError):
        fraction(value)


@pytest.mark.parametrize("text", ['{"a": 1, "a": 2}', '{"a": NaN}', '[]'])
def test_json_is_strict(tmp_path, text):
    path = tmp_path / "result.json"; path.write_text(text)
    with pytest.raises((AssertionError, ValueError)):
        read_json(path)


def test_metadata_expected_subset_allows_descriptive_extras():
    match_contract({"seed": 0.0, "config": {"enabled": True}, "note": "extra"},
                   {"seed": 0, "config": {"enabled": True}})
    with pytest.raises(AssertionError):
        match_contract({"enabled": 1}, {"enabled": True})


def test_trial_table_is_order_free_and_allows_extra_named_columns(tmp_path):
    reference, _, groups = mechanics_fixture()
    rows = trial_rows(groups)[::-1]
    for row in rows:
        row["trial_id"] = f'{row["trial_id"]}.0'
        row["note"] = "descriptive"
    path = tmp_path / "trials.csv"; write_csv(path, rows)
    validate_predictions(load_trial_predictions(path), reference)


@pytest.mark.parametrize("mutation", ["duplicate", "missing_recipe", "fractional_id", "zero_choice", "nan_decision", "probability_range", "unknown_recipe"])
def test_strict_trial_parser_negative(tmp_path, mutation):
    _, _, groups = mechanics_fixture(); rows = trial_rows(groups)
    if mutation == "duplicate": rows.append(rows[0].copy())
    elif mutation == "missing_recipe": rows = [r for r in rows if r["recipe"] != RECIPES[0]]
    elif mutation == "fractional_id": rows[0]["trial_id"] = 1.25
    elif mutation == "zero_choice": rows[0]["true_choice"] = 0
    elif mutation == "nan_decision": rows[0]["decision_value"] = "NaN"
    elif mutation == "probability_range": rows[0]["probability_left"] = 1.01
    else: rows[0]["recipe"] = "made_up"
    path = tmp_path / "trials.csv"; write_csv(path, rows)
    with pytest.raises((AssertionError, ValueError)):
        load_trial_predictions(path)


@pytest.mark.parametrize("mutation", ["drop", "foreign_id", "wrong_fold", "wrong_signed_truth", "wrong_pred", "wrong_baseline", "wrong_decision"])
def test_source_recipe_identity_is_not_just_aggregate_accuracy(mutation):
    reference, _, groups = mechanics_fixture(); recipe = RECIPES[0]
    trial = next(iter(groups[recipe])); row = groups[recipe][trial]
    if mutation == "drop": del groups[recipe][trial]
    elif mutation == "foreign_id": groups[recipe][9999] = groups[recipe].pop(trial)
    elif mutation == "wrong_fold": row["fold"] = (row["fold"]+1) % 5
    elif mutation == "wrong_signed_truth": row["true_choice"] *= -1
    elif mutation == "wrong_pred": row["predicted_choice"] *= -1
    elif mutation == "wrong_baseline": row["baseline_choice"] *= -1
    else: row["decision_value"] += .01
    with pytest.raises(AssertionError):
        validate_predictions(groups, reference)


def test_full_fake_factorial_numbers_are_insufficient_without_trial_rows(tmp_path):
    path = tmp_path / "folds.csv"
    write_csv(path, [{"fold": fold, "accuracy": .8} for fold in range(5)])
    with pytest.raises(AssertionError, match="missing required columns"):
        load_folds(path)


def test_selection_counts_are_mutually_exclusive_source_partition():
    reference, _, _ = mechanics_fixture()
    counts = copy.deepcopy(reference["stats"]["selection_counts"])
    validate_selection_counts(counts, 17, 3)
    counts["n_not_included"] += 1
    with pytest.raises(AssertionError, match="partition"):
        validate_selection_counts(counts, 17, 3)


def test_result_and_metadata_share_source_counts_and_timing():
    reference, arrays, _ = mechanics_fixture(); stats = reference["stats"]
    common = {"status": "ok", "pipeline_id": PIPELINE_ID, "n_trials": 17, "n_units": 3,
              "selection_counts": stats["selection_counts"], "response_timing_counts": stats["response_timing_counts"]}
    result = {**common, **result_metrics(arrays, reference)}
    metadata = {**common, **stats["metadata_contract"], "primary_recipe": "stimulus_blocked"}
    validate_results(result, arrays, reference); validate_metadata(metadata, reference)
    result["cross_validated_accuracy"] = result["pooled_accuracy_by_window_and_split"]["stimulus_blocked"]
    with pytest.raises(AssertionError, match="cross_validated_accuracy"):
        validate_results(result, arrays, reference)


def test_probability_decision_link_is_independent_of_rounded_label():
    reference, _, groups = mechanics_fixture()
    groups[RECIPES[0]][100]["probability_left"] += .01
    with pytest.raises(AssertionError, match="probability_left"):
        validate_predictions(groups, reference)
