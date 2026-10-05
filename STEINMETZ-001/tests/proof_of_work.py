"""Strict source-bound OOF schemas for a declared single-session method control."""
import csv
import json
import math
import os
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
REF_PATH = Path(__file__).with_name("reference.npz")
PIPELINE_ID = "registered-choice-window-split-v2"
WINDOWS = ("stimulus", "peri_response")
SPLITS = ("blocked", "random")
RECIPES = tuple(f"{window}_{split}" for window in WINDOWS for split in SPLITS)
PRIMARY_RECIPE = "stimulus_blocked"
N_FOLDS = 5
ARITHMETIC_ATOL = 1e-6
NUMERICAL_ATOL = 1e-6
NUMERICAL_RTOL = 1e-6
SELECTION_KEYS = {"n_source_trials", "n_not_included", "n_included_nonbinary_choice",
                  "n_included_binary_invalid_alignment", "n_selected_trials", "n_source_units"}
TIMING_KEYS = {"before_stimulus", "within_stimulus_window", "at_or_after_window_end"}


def number(value):
    assert not isinstance(value, (bool, np.bool_)), "finite numeric value required"
    value = float(value)
    assert math.isfinite(value), "finite numeric value required"
    return value


def integer(value):
    value = number(value)
    assert value >= 0 and value.is_integer(), "nonnegative integer required"
    return int(value)


def choice(value):
    value = number(value)
    assert value in (-1., 1.), "signed choice must be -1 or +1"
    return int(value)


def fraction(value):
    value = number(value)
    assert 0 <= value <= 1, "fraction in [0,1] required"
    return value


def read_json(path):
    def pairs(items):
        result = {}
        for key, value in items:
            assert key not in result, "duplicate JSON key"
            result[key] = value
        return result
    def constant(value):
        raise ValueError(f"nonstandard JSON number: {value}")
    result = json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=pairs, parse_constant=constant)
    assert isinstance(result, dict), "JSON object required"
    return result


def match_contract(actual, expected, field="metadata"):
    if isinstance(expected, dict):
        assert isinstance(actual, dict), f"{field} must be an object"
        for key, value in expected.items():
            assert key in actual, f"missing {field}.{key}"
            match_contract(actual[key], value, f"{field}.{key}")
    elif isinstance(expected, list):
        assert isinstance(actual, list) and len(actual) == len(expected), f"incorrect {field}"
        for index, value in enumerate(expected):
            match_contract(actual[index], value, f"{field}[{index}]")
    elif isinstance(expected, bool):
        assert actual is expected, f"incorrect {field}"
    elif isinstance(expected, (int, float)):
        assert abs(number(actual) - expected) <= 1e-12, f"incorrect {field}"
    else:
        assert actual == expected, f"incorrect {field}"


def csv_rows(path, required):
    with Path(path).open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames or []
        assert set(required) <= set(fields), f"missing required columns in {Path(path).name}"
        assert len(fields) == len(set(fields)), "duplicate CSV column name"
        rows = list(reader)
    assert rows, "empty CSV table"
    assert all(None not in row and all(value is not None for value in row.values()) for row in rows), "malformed CSV row"
    return rows


def load_trial_predictions(path):
    required = {"recipe", "trial_id", "fold", "true_choice", "predicted_choice",
                "baseline_choice", "decision_value", "probability_left"}
    groups = {}
    for row in csv_rows(path, required):
        recipe = row["recipe"].strip()
        assert recipe in RECIPES, "unknown recipe"
        trial_id, fold = integer(row["trial_id"]), integer(row["fold"])
        assert fold < N_FOLDS, "fold must be in 0..4"
        group = groups.setdefault(recipe, {})
        assert trial_id not in group, "duplicate trial/recipe row"
        group[trial_id] = {"fold": fold,
            **{field: choice(row[field]) for field in ("true_choice", "predicted_choice", "baseline_choice")},
            "decision_value": number(row["decision_value"]), "probability_left": fraction(row["probability_left"])}
    assert set(groups) == set(RECIPES), "all four window-by-split recipes required"
    return groups


def load_folds(path):
    required = {"recipe", "fold", "n_train", "n_test", "n_correct", "accuracy",
                "baseline_choice", "baseline_n_correct", "baseline_accuracy"}
    rows = {}
    for row in csv_rows(path, required):
        recipe, fold = row["recipe"].strip(), integer(row["fold"])
        assert recipe in RECIPES and fold < N_FOLDS, "invalid recipe/fold key"
        key = recipe, fold
        assert key not in rows, "duplicate recipe/fold row"
        rows[key] = {field: integer(row[field]) for field in ("n_train", "n_test", "n_correct", "baseline_n_correct")}
        rows[key].update(accuracy=fraction(row["accuracy"]), baseline_accuracy=fraction(row["baseline_accuracy"]),
                         baseline_choice=choice(row["baseline_choice"]))
    assert set(rows) == {(recipe, fold) for recipe in RECIPES for fold in range(N_FOLDS)}, "exact20 recipe/fold rows required"
    return rows


def recipe_split(recipe):
    assert recipe in RECIPES
    return recipe.rsplit("_", 1)[1]


def sigmoid(values):
    values = np.asarray(values, float)
    result = np.empty_like(values)
    positive = values >= 0
    result[positive] = 1/(1+np.exp(-values[positive]))
    exponential = np.exp(values[~positive])
    result[~positive] = exponential/(1+exponential)
    return result


def expected_folds(y, split):
    """NumPy reconstruction of public KFold/StratifiedKFold(seed0) assignment."""
    y = np.asarray(y)
    assert len(y) >= N_FOLDS and set(y) == {-1, 1}
    if split == "blocked":
        sizes = np.full(N_FOLDS, len(y)//N_FOLDS, int)
        sizes[:len(y)%N_FOLDS] += 1
        return np.repeat(np.arange(N_FOLDS), sizes)
    assert split == "random"
    # scikit-learn's stratifier encodes classes by first occurrence, allocates
    # round-robin class counts, then shuffles each class with one RandomState.
    _, first, inverse = np.unique(y, return_index=True, return_inverse=True)
    _, permutation = np.unique(first, return_inverse=True)
    encoded = permutation[inverse]
    ordered = np.sort(encoded)
    allocation = np.asarray([np.bincount(ordered[fold::N_FOLDS], minlength=2) for fold in range(N_FOLDS)])
    result = np.empty(len(y), int)
    rng = np.random.RandomState(0)
    for label in range(2):
        labels = np.repeat(np.arange(N_FOLDS), allocation[:, label])
        rng.shuffle(labels)
        result[encoded == label] = labels
    return result


def train_majority(y, folds):
    result = np.empty(len(y), int)
    for fold in range(N_FOLDS):
        train, test = folds != fold, folds == fold
        assert train.any() and test.any(), "each fold must have train and test trials"
        assert set(y[train]) == {-1, 1}, "training fold must contain both choices"
        # A tied training majority deterministically predicts right (-1).
        label = 1 if np.sum(y[train] == 1) > np.sum(y[train] == -1) else -1
        result[test] = label
    return result


def timing_counts(stimulus, response):
    stimulus, response = np.asarray(stimulus), np.asarray(response)
    assert stimulus.shape == response.shape and np.isfinite(stimulus).all() and np.isfinite(response).all()
    return {"before_stimulus": int(np.sum(response < stimulus)),
            "within_stimulus_window": int(np.sum((response >= stimulus) & (response < stimulus+.25))),
            "at_or_after_window_end": int(np.sum(response >= stimulus+.25))}


def validate_selection_counts(counts, n_trials, n_units):
    assert isinstance(counts, dict) and set(counts) == SELECTION_KEYS, "incorrect selection-count fields"
    values = {key: integer(value) for key, value in counts.items()}
    assert values["n_selected_trials"] == n_trials and values["n_source_units"] == n_units
    assert values["n_source_trials"] == sum(values[key] for key in (
        "n_not_included", "n_included_nonbinary_choice", "n_included_binary_invalid_alignment", "n_selected_trials")), "selection exclusions must partition source trials"


def exact_integer_array(value, *, nonnegative=False):
    value = np.asarray(value)
    assert value.dtype.kind in "iuf" and np.isfinite(value).all() and (value == np.floor(value)).all(), "integer array required"
    assert not nonnegative or (value >= 0).all(), "nonnegative array required"
    return value.astype(np.int64)


def load_reference(path=None):
    with np.load(REF_PATH if path is None else path, allow_pickle=False) as bank:
        stats = json.loads(str(bank["ref_stats"]))
        assert stats.get("pipeline_id") == PIPELINE_ID, "failed_precondition: stale choice reference"
        arrays = {name[4:]: bank[name].copy() for name in bank.files if name.startswith("ref_") and name != "ref_stats"}
    ids = exact_integer_array(arrays["trial_ids"], nonnegative=True)
    units = exact_integer_array(arrays["unit_ids"], nonnegative=True)
    y = exact_integer_array(arrays["true_choice"])
    assert ids.ndim == units.ndim == y.ndim == 1 and len(ids) >= N_FOLDS and len(units) > 0
    assert len(set(ids)) == len(ids) and len(set(units)) == len(units), "duplicate source identity"
    assert y.shape == ids.shape and set(y) == {-1, 1}, "source signed labels invalid"
    for name in ("stimulus_times", "response_times"):
        assert arrays[name].shape == ids.shape and np.isfinite(arrays[name]).all(), "source timing invalid"
    for window in WINDOWS:
        counts = exact_integer_array(arrays[f"counts_{window}"], nonnegative=True)
        assert counts.shape == (len(ids), len(units)), "source count-matrix shape differs"
    for split in SPLITS:
        folds = exact_integer_array(arrays[f"fold_{split}"], nonnegative=True)
        assert np.array_equal(folds, expected_folds(y, split)), "reference fold assignment differs from public split"
        baseline = exact_integer_array(arrays[f"baseline_choice_{split}"])
        assert np.array_equal(baseline, train_majority(y, folds)), "reference baseline leaks or differs"
    for recipe in RECIPES:
        pred = exact_integer_array(arrays[f"predicted_choice_{recipe}"])
        decision, probability = arrays[f"decision_{recipe}"], arrays[f"probability_left_{recipe}"]
        assert pred.shape == decision.shape == probability.shape == ids.shape
        assert set(pred) <= {-1, 1} and np.isfinite(decision).all() and np.isfinite(probability).all()
        assert np.array_equal(pred, np.where(decision > 0, 1, -1)), "reference labels differ from decision sign"
        assert np.allclose(probability, sigmoid(decision), atol=1e-12, rtol=1e-12), "reference probabilities do not reconstruct"
    validate_selection_counts(stats["selection_counts"], len(ids), len(units))
    assert stats["response_timing_counts"] == timing_counts(arrays["stimulus_times"], arrays["response_times"]), "reference response timing differs"
    hashes = stats["source_sha256"]
    assert isinstance(hashes, dict) and len(hashes) == 1
    assert all(isinstance(value, str) and len(value) == 64 and set(value) <= set("0123456789abcdef") for value in hashes.values())
    assert stats["metadata_contract"]["pipeline_id"] == PIPELINE_ID
    assert stats["metadata_contract"]["source_sha256"] == hashes
    return {**arrays, "trial_ids": ids, "unit_ids": units, "true_choice": y, "stats": stats}
