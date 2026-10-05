"""Small mechanical fixtures, never a substitute for the real NWB bank."""
import importlib.util
from pathlib import Path

import numpy as np
import pytest

TASK = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


oracle = module("steinmetz_oracle_numerics", TASK / "solution/compute.py")
independent = module("steinmetz_independent_numerics", TASK / "authoring/check_independent.py")


def test_half_open_counts_preserve_duplicate_timestamps():
    trains = [np.array([-0.1, 0.0, 0.0, 0.1, 0.25, 0.5]), np.array([])]
    counts = oracle.spike_counts(trains, np.array([0.0, 0.25]), 0.0, 0.25)
    np.testing.assert_array_equal(counts, [[3, 0], [1, 0]])
    np.testing.assert_array_equal(counts, independent.count_with_bisect(trains, [0.0, 0.25], 0.0, 0.25))


@pytest.mark.parametrize("times", [[0.2, 0.1], [0.0, np.nan], [0.0, np.inf]])
def test_invalid_spike_train_is_not_silently_sorted_or_dropped(times):
    with pytest.raises(ValueError, match="nondecreasing"):
        oracle.spike_counts([times], [0.0], 0.0, 0.25)


def test_selection_is_binary_finite_shared_support_and_preserves_original_ids():
    ids = np.arange(100, 118)
    y = np.tile([-1.0, 1.0], 9)
    inc = np.ones(18, dtype=bool); inc[0] = False
    y[1] = 0; y[2] = np.nan; y[3] = 2
    st = np.arange(18, dtype=float); rt = st + 0.7; rt[4] = np.nan
    selected, counts = oracle.select_trials(ids, inc, y, st, rt)
    np.testing.assert_array_equal(ids[selected], np.arange(105, 118))
    assert counts == {"n_source_trials": 18, "n_not_included": 1,
                      "n_included_nonbinary_choice": 3, "n_included_binary_invalid_alignment": 1,
                      "n_selected_trials": 13}


def test_nonchronological_trial_order_fails_instead_of_silently_reordering():
    st = np.arange(12, dtype=float); st[[4, 5]] = st[[5, 4]]
    with pytest.raises(ValueError, match="chronological"):
        oracle.select_trials(np.arange(12), np.ones(12, bool), np.tile([-1, 1], 6), st, st + 0.6)


def test_nonconsecutive_unit_ids_are_retained_but_duplicates_fail():
    np.testing.assert_array_equal(oracle.integer_ids([9, 103, 2], "unit"), [9, 103, 2])
    with pytest.raises(ValueError, match="duplicate"):
        oracle.integer_ids([9, 103, 9], "unit")


@pytest.mark.parametrize("first", [-1, 1])
def test_explicit_split_allocation_matches_sklearn_including_class_appearance(first):
    y = np.asarray([first] * 7 + [-first] * 9 + [first, -first, first])
    expected = oracle.fold_assignments(y)
    actual = independent.explicit_folds(y)
    for split in ["blocked", "random"]:
        np.testing.assert_array_equal(actual[split], expected[split])
        assert set(actual[split]) == set(range(5))


def test_training_majority_tie_is_right_choice():
    assert oracle.majority_choice([-1, 1]) == -1
    assert oracle.majority_choice([-1, 1, 1]) == 1


def test_manual_standardizer_constant_column_and_test_only_outlier():
    train = np.array([[1, 5], [3, 5], [5, 5]], dtype=float)
    test = np.array([[101, 5]], dtype=float)
    standardized, heldout, means, scales = independent.manual_standardization(train, test)
    np.testing.assert_array_equal(means, [3, 5])
    np.testing.assert_array_equal(scales[1:], [1])
    np.testing.assert_allclose(standardized.mean(axis=0), 0, atol=1e-15)
    assert heldout[0, 0] > 50 and heldout[0, 1] == 0


def test_tiny_fits_agree_with_manual_training_only_scaling():
    # Mechanical fixture only: no scientific reference is written from this.
    rng = np.random.RandomState(31)
    x = rng.poisson(2, size=(20, 4)); x[:, 3] = 4
    y = np.tile([-1, 1], 10)
    folds = oracle.fold_assignments(y)["blocked"]
    actual = oracle.fit_recipe(x, y, folds)
    check = independent.fit_independent(x, y, folds)
    np.testing.assert_array_equal(actual["predicted_choice"], check["predicted_choice"])
    np.testing.assert_allclose(actual["decision"], check["decision"], atol=1e-10, rtol=1e-10)
    np.testing.assert_allclose(actual["probability_left"], check["probability_left"], atol=1e-12, rtol=1e-12)


def test_stable_sigmoid_and_zero_decision_label_contract():
    decision = np.array([-1000.0, -1.0, 0.0, 1.0, 1000.0])
    probabilities = independent.probability_left(decision)
    assert np.isfinite(probabilities).all()
    assert probabilities[0] == 0 and probabilities[2] == 0.5 and probabilities[-1] == 1
    assert oracle.metadata_contract()["classifier"]["decision_zero_choice"] == -1


def test_public_contract_is_no_fit_configuration_not_hidden_answers():
    contract = oracle.metadata_contract()
    assert contract["choice_labels"] == {"-1": "right", "1": "left"}
    assert contract["units"]["quality_filter"] is None
    assert contract["baseline"]["tie_choice"] == -1
    assert contract["classifier"]["tol"] == 0.0001
    assert not any(key in contract for key in ["accuracy", "n_trials", "n_units", "predictions"])
