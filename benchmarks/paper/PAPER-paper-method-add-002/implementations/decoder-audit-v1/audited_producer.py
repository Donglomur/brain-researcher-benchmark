"""Retain the original linear readout's computed operands and outputs.

This additive module keeps the immutable producer's equations, windows and
schedules. Records describe values observed by this source; they do not prove
that an untrusted submission honestly executed a fit. Authentic execution and
full artifact storage require a separately bounded operator workflow.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np


PRODUCER_SHA256 = "c7746e42f4433a128418520e466e68ae1c92461a8e7a5fce4155e9d7a6c04de9"
PRODUCER_PATH = Path(__file__).resolve().parents[1] / "source-producer-v1" / "producer.py"
if hashlib.sha256(PRODUCER_PATH.read_bytes()).hexdigest() != PRODUCER_SHA256:
    raise ValueError("immutable source producer identity differs")
_spec = importlib.util.spec_from_file_location("slicetca_audit_original_producer", PRODUCER_PATH)
p = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(p)
e = p.endpoints


def array_digest(value):
    """Bind numerical shape, dtype, extent and C-order value bytes together.

    This hashes the actual passed dtype; it does not claim a biological sample
    identity or authenticate the process that computed the array.
    """
    a = np.asarray(value)
    p.need(a.dtype.kind in "fiu" and a.size > 0 and np.isfinite(a).all(),
           "array digest requires nonempty finite real values")
    header = {"shape": list(a.shape), "dtype": a.dtype.str, "bytes": int(a.nbytes)}
    encoded = json.dumps(header, sort_keys=True, separators=(",", ":")).encode("ascii")
    digest = hashlib.sha256(encoded + b"\n")
    # C iteration is deliberate and independent of the input's strides/order.
    for row in np.nditer(a, flags=["external_loop", "buffered"],
                         op_flags=["readonly"], order="C", buffersize=65536):
        digest.update(row.tobytes(order="C"))
    return {**header, "sha256": digest.hexdigest()}


def _indices(value, label):
    result = np.asarray(value)
    p.need(result.ndim == 1 and result.size > 0 and result.dtype.kind in "iu"
           and len(np.unique(result)) == len(result)
           and np.all((result >= 0) & (result < 511)),
           label + " requires unique original row indices")
    return result


def make_fit_record(model, train_neural, train_movement, train_indices, test_indices):
    """Record exact original linear training operands, support and coefficients."""
    x = p.real(train_neural, "training neural", 3)
    y = p.real(train_movement, "training movement", 3)
    train = _indices(train_indices, "training support")
    test = _indices(test_indices, "test support")
    p.need(x.shape[:2] == y.shape[:2] and x.shape[0] >= 2 and y.shape[-1] == 2,
           "fit record neural/movement axes differ")
    p.need(not np.intersect1d(train, test).size, "training and test support overlap")
    p.need(model["recipe"] in e.RECIPES, "fit record requires an explicit recipe")
    p.need(model["bias_penalized"] is bool(e.RECIPES[model["recipe"]]),
           "fit record intercept penalty differs")
    p.need(np.asarray(model["weight"]).shape == (2, x.shape[-1])
           and np.asarray(model["bias"]).shape == (2,), "fit parameter axes differ")
    return {
        "schema": "slicetca-original-decoder-fit-record-v1",
        "source_producer_sha256": PRODUCER_SHA256,
        "recipe": model["recipe"],
        "bias_penalized": model["bias_penalized"],
        "feature_count": int(x.shape[-1]),
        "training_observations": int((x.shape[0] - 1) * x.shape[1]),
        "inputs": {
            "neural_features": array_digest(x[:-1]),
            "target_displacements": array_digest(np.diff(y, axis=0)),
            "train_indices": array_digest(train),
            "test_indices": array_digest(test),
        },
        "outputs": {"weight": array_digest(model["weight"]), "bias": array_digest(model["bias"])},
        "provenance": "source_observed_record_not_execution_authentication",
    }


def _windowed_inputs(neural, movement):
    x = p.real(neural, "windowed neural", 3)
    y = p.real(movement, "windowed movement", 3)
    p.need(x.shape[:2] == (80, 511) and x.shape[2] > 0 and y.shape == (80, 511, 2),
           "complete 80-bin/511-row window required")
    return x, y


def decoder_fold(data, movement, train, test, *, recipe):
    """One original fold/half readout, usable by a future streaming collector.

    No fit is deferred: returned parameters and displacements are those from
    this call. The caller must authenticate full schedule/coverage separately.
    """
    x = p.real(data, "decoder neural", 3)
    y = p.real(movement, "decoder movement", 3)
    train = _indices(train, "training support")
    test = _indices(test, "test support")
    p.need(x.shape[:2] == y.shape[:2] and x.shape[0] >= 2 and x.shape[1] == 511
           and y.shape[-1] == 2, "complete decoder trial support required")
    p.need(not np.intersect1d(train, test).size, "training and test support overlap")
    model = p.fit_velocity(x[:, train], y[:, train], recipe=recipe)
    delta = x[:-1, test] @ model["weight"].T + model["bias"]
    prediction = e.integrate_displacements(delta, y[0, test])
    return {
        "decoder": {**model, "feature_count": int(x.shape[-1])},
        "displacement": delta,
        "prediction": prediction,
        "train_indices": train.copy(),
        "test_indices": test.copy(),
        "fit_record": make_fit_record(model, x[:, train], y[:, train], train, test),
    }


def _repeated_windowed(neural, movement, full_movement, *, recipe):
    """Full schedules on already sliced windows; reduced features are test-only."""
    x, y = _windowed_inputs(neural, movement)
    p.need(recipe in e.RECIPES, "explicit source_code_ridge1 or paper_ols0 recipe required")
    full = p.real(full_movement, "full movement", 3)
    p.need(full.shape == (150, 511, 2) and np.array_equal(full[65:-5], y),
           "scoring movement must match the exact source window")
    results = {}
    for condition in e.CONDITIONS:
        plan = e.source_schedule(condition)
        width = plan["test"].shape[-1]
        predictions = np.empty((20, 5, 80, width, 2))
        deltas = np.empty((20, 5, 79, width, 2))
        weights = np.empty((20, 5, 2, x.shape[-1]))
        biases = np.empty((20, 5, 2))
        records = []
        for repeat in range(20):
            rows = []
            for fold in range(5):
                row = decoder_fold(x, y, plan["train"][repeat, fold], plan["test"][repeat, fold], recipe=recipe)
                predictions[repeat, fold] = row["prediction"]
                deltas[repeat, fold] = row["displacement"]
                weights[repeat, fold] = row["decoder"]["weight"]
                biases[repeat, fold] = row["decoder"]["bias"]
                rows.append(row["fit_record"])
            records.append(rows)
        summary, details = e.score_condition(full, condition, predictions, plan["test"])
        summary["descriptive_mean_within_fold_sem_ddof0"] = float(details["fold_population_sd"].mean() / np.sqrt(width))
        summary["descriptive_mean_within_fold_sem_ddof1"] = float(details["r2"].std(axis=-1, ddof=1).mean() / np.sqrt(width))
        summary["original_plot_errorbar_aggregation_authenticated"] = False
        results[condition] = {
            "prediction": predictions, "test_indices": plan["test"], "summary": summary, "details": details,
            "decoder_audit": {
                "schema": "slicetca-original-repeated-decoder-audit-v1",
                "recipe": recipe, "bias_penalized": bool(e.RECIPES[recipe]), "feature_count": int(x.shape[-1]),
                "weight": weights, "bias": biases, "displacement": deltas,
                "train_indices": plan["train"].copy(), "fit_records": records,
            },
        }
    return {"recipe": recipe, "conditions": results,
            "representation_exposure": "supplied full-data reconstruction; no representation holdout claim"}


def repeated_decoding(neural_time_trial_neuron, movement, *, recipe):
    """Original complete 150×511×182 input and all 20×5 folds, plus fit records."""
    x, y = e.source_windows(neural_time_trial_neuron, movement)
    return _repeated_windowed(x, y, movement, recipe=recipe)


def averaged_half(data, movement, angles, train, test, *, recipe):
    """Original split-first neural/movement condition means and fitted outputs."""
    x, y = _windowed_inputs(data, movement)
    a = p.real(angles, "target angles", 1)
    p.need(a.shape == (511,), "all original target-angle rows required")
    train = _indices(train, "training support")
    test = _indices(test, "test support")
    p.need(not np.intersect1d(train, test).size, "training and test support overlap")
    labels = np.unique(a[np.concatenate((train, test))])
    counts = np.array([[np.count_nonzero(a[ids] == label) for label in labels] for ids in (train, test)], dtype=np.int64)
    p.need(np.all(counts > 0), "a condition is missing from a half; source would yield NaN")

    def average(values, ids):
        return np.stack([values[:, ids[a[ids] == label]].mean(axis=1) for label in labels], axis=1)

    xtrain, ytrain = average(x, train), average(y, train)
    xtest, ytest = average(x, test), average(y, test)
    model = p.fit_velocity(xtrain, ytrain, recipe=recipe)
    delta = xtest[:-1] @ model["weight"].T + model["bias"]
    prediction = e.integrate_displacements(delta, ytest[0])
    return {
        "condition_labels": labels, "target": ytest, "prediction": prediction,
        "r2": e.trajectory_r2(ytest, prediction)["r2"], "train_indices": train.copy(), "test_indices": test.copy(),
        "decoder": {**model, "feature_count": int(x.shape[-1])}, "displacement": delta,
        "neural_train_mean": xtrain, "neural_test_mean": xtest,
        "movement_train_mean": ytrain, "movement_test_mean": ytest, "group_counts": counts,
        "fit_record": make_fit_record(model, xtrain, ytrain, train, test),
    }


def _condition_average_windowed(neural, movement, angles, *, recipe):
    """Preserve source MT19937 continuation and cumulatively permuted halves."""
    x, y = _windowed_inputs(neural, movement)
    a = p.real(angles, "target angles", 1)
    p.need(a.shape == (511,), "all source angles required")
    p.need(recipe in e.RECIPES, "explicit source_code_ridge1 or paper_ols0 recipe required")
    rng = np.random.RandomState(0)
    for _ in range(20):
        rng.permutation(246)
    result = {}
    for condition, (start, stop) in e.CONDITIONS.items():
        order = np.arange(start, stop)
        half = len(order) // 2
        rows = []
        for repeat in range(20):
            order = order[rng.permutation(len(order))]
            rows.append([averaged_half(x, y, a, current[:half], current[half:], recipe=recipe)
                         for current in (order, order[::-1])])
        scores = np.stack([np.stack([row["r2"] for row in pair]) for pair in rows])
        result[condition] = {
            "rows": rows, "r2": scores, "mean_condition_half_repeat_r2": float(scores.mean()),
            "independent_unit": "condition averages; not trial-wise five-fold control",
            "uncertainty": "none; dependent repeated halves",
            "rng_origin": "after final seed0 curved five-fold20-repeat source call",
        }
    return {"recipe": recipe, "conditions": result}


def condition_average_control(neural_time_trial_neuron, movement, angles, *, recipe):
    """Original complete input; both 20-repeat, reversed-half conditions retained."""
    x, y = e.source_windows(neural_time_trial_neuron, movement)
    return _condition_average_windowed(x, y, angles, recipe=recipe)
