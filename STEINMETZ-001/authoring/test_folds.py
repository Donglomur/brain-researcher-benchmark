"""Small arithmetic/split fixtures only; these are not a scientific reference bank."""
import copy
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "tests"))
from proof_of_work import (RECIPES, SPLITS, PIPELINE_ID, expected_folds, train_majority,
                           timing_counts, sigmoid, recipe_split)
from decoding_contract import fold_metrics, result_metrics, validate_folds


def mechanics_fixture():
    """Tiny explicitly invented arrays for schema/arithmetic tests, never saved as a bank."""
    n = 17
    y = np.array([-1, 1] * 8 + [-1])
    reference = {"trial_ids": np.arange(100, 100+n), "unit_ids": np.array([4, 7, 11]),
                 "true_choice": y, "stimulus_times": np.arange(n, dtype=float),
                 "response_times": np.arange(n, dtype=float)+.25}
    selection = dict(n_source_trials=21, n_not_included=1, n_included_nonbinary_choice=2,
                     n_included_binary_invalid_alignment=1, n_selected_trials=n, n_source_units=3)
    hashes = {"mechanics-only-not-a-source.nwb": "a"*64}
    reference["stats"] = {"pipeline_id": PIPELINE_ID, "source_sha256": hashes,
        "metadata_contract": {"pipeline_id": PIPELINE_ID, "source_sha256": hashes},
        "selection_counts": selection,
        "response_timing_counts": timing_counts(reference["stimulus_times"], reference["response_times"])}
    for split in SPLITS:
        folds = expected_folds(y, split)
        reference[f"fold_{split}"] = folds
        reference[f"baseline_choice_{split}"] = train_majority(y, folds)
    arrays, groups = {}, {}
    for recipe in RECIPES:
        split = recipe_split(recipe)
        pred = y.copy()
        pred[:4] *= -1
        decision = pred.astype(float)*.75
        probability = sigmoid(decision)
        reference[f"predicted_choice_{recipe}"] = pred
        reference[f"decision_{recipe}"] = decision
        reference[f"probability_left_{recipe}"] = probability
        arrays[recipe] = {"fold": reference[f"fold_{split}"].copy(), "true_choice": y.copy(),
            "predicted_choice": pred.copy(), "baseline_choice": reference[f"baseline_choice_{split}"].copy(),
            "decision_value": decision, "probability_left": probability}
        groups[recipe] = {int(trial): {field: value[i].item() for field, value in arrays[recipe].items()}
                          for i, trial in enumerate(reference["trial_ids"])}
    return reference, arrays, groups


@pytest.mark.parametrize("first", [-1, 1])
@pytest.mark.parametrize("split", SPLITS)
def test_numpy_split_matches_published_sklearn_assignment(first, split):
    model_selection = pytest.importorskip("sklearn.model_selection")
    y = np.array([first, -first] * 8 + [first])
    splitter = (model_selection.KFold(5, shuffle=False) if split == "blocked" else
                model_selection.StratifiedKFold(5, shuffle=True, random_state=0))
    expected = np.empty(len(y), int)
    for fold, (_, test) in enumerate(splitter.split(np.zeros((len(y), 1)), y)):
        expected[test] = fold
    np.testing.assert_array_equal(expected_folds(y, split), expected)


def test_blocked_remainder_is_in_first_folds():
    np.testing.assert_array_equal(expected_folds(np.array([-1, 1]*8+[-1]), "blocked"),
                                  [0]*4+[1]*4+[2]*3+[3]*3+[4]*3)


def test_training_majority_tie_is_right_and_does_not_read_test_labels():
    y = np.array([-1, 1]*5)
    folds = np.repeat(np.arange(5), 2)
    np.testing.assert_array_equal(train_majority(y, folds), -np.ones(10))
    changed = y.copy(); changed[folds == 0] = 1
    np.testing.assert_array_equal(train_majority(changed, folds)[folds == 0], [-1, -1])


def test_registered_response_half_open_boundaries():
    assert timing_counts(np.zeros(5), np.array([-.1, 0., .249, .25, .7])) == {
        "before_stimulus": 1, "within_stimulus_window": 2, "at_or_after_window_end": 2}


def test_unweighted_headline_is_not_pooled_accuracy():
    reference, arrays, _ = mechanics_fixture()
    metrics = result_metrics(arrays, reference)
    assert metrics["cross_validated_accuracy"] == pytest.approx(.8)
    assert metrics["pooled_accuracy_by_window_and_split"]["stimulus_blocked"] == pytest.approx(13/17)
    assert metrics["accuracy_std_by_window_and_split"]["stimulus_blocked"] == pytest.approx(.4)
    assert metrics["cross_validated_accuracy"] != metrics["pooled_accuracy_by_window_and_split"]["stimulus_blocked"]


@pytest.mark.parametrize("field", ["n_train", "n_test", "n_correct", "baseline_n_correct", "accuracy", "baseline_accuracy"])
def test_each_fold_field_is_recomputed(field):
    _, arrays, _ = mechanics_fixture()
    rows = copy.deepcopy(fold_metrics(arrays))
    rows[("stimulus_blocked", 0)][field] += .05 if "accuracy" in field else 1
    with pytest.raises(AssertionError):
        validate_folds(rows, arrays)


def test_no_required_window_effect_direction_or_accuracy_band():
    reference, arrays, _ = mechanics_fixture()
    for recipe, values in arrays.items():
        values["predicted_choice"] = -values["true_choice"]
    metrics = result_metrics(arrays, reference)
    assert all(value == 0 for value in metrics["accuracy_by_window_and_split"].values())
    validate_folds(fold_metrics(arrays), arrays)
