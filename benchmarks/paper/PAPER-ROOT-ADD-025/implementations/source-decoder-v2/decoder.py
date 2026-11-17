"""Source row selection and held-out decoder scoring for Park et al. (2025).

This module neither fits a model nor chooses an S11 group/PC/time aggregate.
Inputs and returned trial identities are operator artifacts, not public assets.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

import numpy as np

SOURCE_COMMIT = "8b79caa5b95fadce826ea39bf6c69828991a4b28"
CONTEXTS = {"attn": (1, 2), "choice": (3, 4)}
CLASSES = ("consistent", "inconsistent", "all")
METRICS = ("corr_S_Shat", "corr_E_Ehat", "corr_E_Shat")
BEHAVIOR_FIELDS = {
    "trial_ids", "sess", "samples", "binary_choices", "interm_cues",
    "estimations", "gen_means", "consistent_samples", "inconsistent_samples",
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def _behavior(value: dict[str, Any]) -> dict[str, np.ndarray]:
    _require(set(value) == BEHAVIOR_FIELDS, "exact behavior fields required")
    ids = np.asarray(value["trial_ids"])
    _require(ids.ndim == 1 and ids.dtype.kind in "US", "trial IDs must be strings")
    _require(len(ids) > 0 and len(set(ids.tolist())) == len(ids)
             and all(x.strip() for x in ids), "trial IDs must be nonempty and unique")
    result = {"trial_ids": ids.astype(str)}
    for name in BEHAVIOR_FIELDS - {"trial_ids"}:
        a = np.asarray(value[name], dtype=np.float64)
        shape = (len(ids), 12) if name.endswith("samples") else (len(ids),)
        _require(a.shape == shape and not np.isinf(a).any(), f"invalid {name} shape/infinity")
        result[name] = a
    _require(np.isin(result["sess"], [1, 2, 3, 4]).all(), "sessions must be 1..4")
    _require(np.isin(result["binary_choices"], [-1, 1, 99]).all(), "invalid binary choices")
    _require(np.isin(result["interm_cues"], [-1, 1]).all(), "invalid intermediate cues")
    for name in ("consistent_samples", "inconsistent_samples"):
        present = np.isfinite(result[name])
        _require(np.array_equal(result[name][present], result["samples"][present]),
                 f"{name} must contain the source sample or NaN")
    _require(not (np.isfinite(result["consistent_samples"][:, 6:])
                  & np.isfinite(result["inconsistent_samples"][:, 6:])).any(),
             "second-interval consistency masks overlap")
    return result


def _behavior_digest(b: dict[str, np.ndarray]) -> str:
    """Bind private values without serializing target values into the row plan."""
    h = hashlib.sha256()
    for name in sorted(b):
        a = b[name]
        h.update(json.dumps([name, list(a.shape)], separators=(",", ":")).encode())
        if name == "trial_ids":
            h.update(json.dumps(a.tolist(), ensure_ascii=True, separators=(",", ":")).encode())
        else:
            # Normalize endianness and NaN payload bits for a portable value pin.
            a = a.astype("<f8", copy=True)
            a[np.isnan(a)] = np.nan
            h.update(a.tobytes(order="C"))
    return h.hexdigest()


def prepare_design(behavior: dict[str, Any], neural_trial_ids: Any, *, participant: str,
                   parcel: str, context: str, n_components: int, seed: int) -> dict[str, Any]:
    """Freeze all six pairs, three classes and five matched row-fold repeats.

    The seed defines a recorded protocol-equivalent NumPy rerun. It does not
    reconstruct historical MATLAB RNG, including draws consumed by shuffles.
    No 81-observation information-analysis threshold is applied to this decoder.
    """
    _require(context in CONTEXTS, "invalid context")
    _require(all(isinstance(x, str) and x.strip() for x in (participant, parcel)),
             "participant and parcel identities required")
    _require(type(seed) is int and seed >= 0, "seed must be a nonnegative integer")
    _require(type(n_components) is int and 1 <= n_components <= 15,
             "expected 1..15 source components")
    b = _behavior(behavior)
    rows = np.flatnonzero(np.isin(b["sess"], CONTEXTS[context]))
    _require(len(rows) > 0, "context has no trials")
    ids = b["trial_ids"][rows]
    _require(np.array_equal(np.asarray(neural_trial_ids), ids),
             "neural trial identity/order differs from complete context behavior")
    samples = b["samples"][rows]
    valid = ((b["binary_choices"][rows] != 99) & np.isfinite(b["estimations"][rows])
             & np.isfinite(b["gen_means"][rows]))  # S11 fgmu=0
    intermediate = b["interm_cues" if context == "attn" else "binary_choices"][rows]
    consistent = np.concatenate((samples[:, :6] * intermediate[:, None] > 0,
                                 np.isfinite(b["consistent_samples"][rows, 6:])), axis=1)
    inconsistent = np.concatenate((samples[:, :6] * intermediate[:, None] < 0,
                                   np.isfinite(b["inconsistent_samples"][rows, 6:])), axis=1)
    masks = [x & valid[:, None] for x in (consistent, inconsistent, np.isfinite(samples))]
    design = {
        "schema": "park_source_decoder_design/v2", "source_commit": SOURCE_COMMIT,
        "participant": participant, "parcel": parcel, "context": context,
        "n_components": n_components, "n_times": 129, "n_folds": 10, "n_repeats": 5,
        "generative_selection": "fgmu_0_all_finite", "fold_unit": "pooled_sample_row",
        "rng": "numpy.PCG64", "numpy_version": np.__version__, "seed": seed,
        "context_trial_ids": ids.tolist(), "behavior_sha256": _behavior_digest(b), "cells": [],
    }
    for pair in range(6):
        eligible = [np.flatnonzero(m[:, 2*pair:2*pair+2].reshape(-1, order="F")) for m in masks]
        n = min(map(len, eligible))
        for name, available in zip(CLASSES, eligible):
            identity = [seed, participant, parcel, context, pair + 1, name]
            cell_seed = int.from_bytes(hashlib.sha256(json.dumps(identity).encode()).digest()[:16], "little")
            rng = np.random.Generator(np.random.PCG64(cell_seed))
            cell = {"pair": pair + 1, "consistency": name, "available_rows": len(available),
                    "matched_rows": n, "status": "planned" if n >= 10 else "insufficient_rows_for_10_folds",
                    "repeats": []}
            if n >= 10:
                for _ in range(5):
                    take = np.sort(rng.choice(available, n, replace=False))
                    folds = np.empty(n, dtype=int)
                    for f, positions in enumerate(np.array_split(rng.permutation(n), 10)):
                        folds[positions] = f
                    cell["repeats"].append({"pooled_row_indices": take.tolist(), "fold_ids": folds.tolist()})
            design["cells"].append(cell)
    design["design_sha256"] = _digest(design)
    return design


def _pearson(target: np.ndarray, predicted: np.ndarray) -> np.ndarray:
    """Pearson per PC/time; constants and singleton folds remain undefined."""
    out = np.full(predicted.shape[1:], np.nan)
    if len(target) < 2 or np.ptp(target) == 0:
        return out
    y = target - target.mean()
    p = predicted - predicted.mean(axis=0)
    y = y / np.max(np.abs(y))
    scale = np.max(np.abs(p), axis=0)
    p = np.divide(p, scale, out=np.zeros_like(p), where=scale > 0)
    denominator = np.sqrt(np.sum(y*y) * np.sum(p*p, axis=0))
    usable = (np.ptp(predicted, axis=0) > 0) & (denominator > 0)
    np.divide(np.sum(y[:, None, None]*p, axis=0), denominator, out=out, where=usable)
    return np.clip(out, -1, 1)


def score_predictions(design: dict[str, Any], behavior: dict[str, Any],
                      prediction_cells: list[dict[str, Any]]) -> dict[str, Any]:
    """Score already-frozen predictions; no fitting or target-dependent selection.

    Supply exactly one prediction cell for each planned design cell, with its
    pair/class, complete row/fold metadata, and stimulus/estimate predictions of
    shape [repeat, selected row, PC, time]. Unsupported cells stay in results.
    The evaluator owner must enforce prediction freezing and target isolation.
    """
    expected = prepare_design(behavior, design["context_trial_ids"],
                              participant=design["participant"], parcel=design["parcel"],
                              context=design["context"], n_components=design["n_components"],
                              seed=design["seed"])
    _require(design == expected, "design differs from its source selection/fold replay or behavior pin")
    keys = [(x["pair"], x["consistency"]) for x in prediction_cells]
    planned = [x for x in design["cells"] if x["status"] == "planned"]
    _require(len(keys) == len(set(keys)) and set(keys) == {(x["pair"], x["consistency"]) for x in planned},
             "prediction cell coverage incomplete, duplicated or unexpected")
    supplied = dict(zip(keys, prediction_cells))
    b = _behavior(behavior)
    rows = np.flatnonzero(np.isin(b["sess"], CONTEXTS[design["context"]]))
    estimates = np.tile(b["estimations"][rows], 2)
    result = {"schema": "park_source_decoder_scores/v2", "design_sha256": design["design_sha256"],
              "participant": design["participant"], "parcel": design["parcel"], "context": design["context"],
              "metric_names": list(METRICS), "fold_score_axes": ["repeat", "fold", "metric", "PC", "time"],
              "mean_fold_axes": ["repeat", "metric", "PC", "time"], "cells": []}
    for cell in design["cells"]:
        out = {k: cell[k] for k in ("pair", "consistency", "available_rows", "matched_rows", "status")}
        if cell["status"] != "planned":
            out.update(fold_scores=None, mean_fold_scores=None, undefined_fold_correlations=None)
            result["cells"].append(out)
            continue
        pred = supplied[(cell["pair"], cell["consistency"])]
        _require(set(pred) == {"pair", "consistency", "repeats", "stimulus", "estimate"},
                 "exact prediction cell fields required")
        _require(pred["repeats"] == cell["repeats"], "prediction row/fold identity differs from frozen design")
        shape = (5, cell["matched_rows"], design["n_components"], 129)
        arrays = [np.asarray(pred[name], dtype=float) for name in ("stimulus", "estimate")]
        _require(all(a.shape == shape and np.isfinite(a).all() for a in arrays),
                 "prediction shape mismatch or nonfinite predictions")
        score = np.full((5, 10, 3, design["n_components"], 129), np.nan)
        start = 2 * (cell["pair"] - 1)
        stimulus = b["samples"][rows, start:start+2].reshape(-1, order="F")
        for repeat, selection in enumerate(cell["repeats"]):
            take, fold_ids = np.asarray(selection["pooled_row_indices"]), np.asarray(selection["fold_ids"])
            for f in range(10):
                held = fold_ids == f
                shat, ehat = (a[repeat, held] for a in arrays)
                score[repeat, f, 0] = _pearson(stimulus[take[held]], shat)
                score[repeat, f, 1] = _pearson(estimates[take[held]], ehat)
                score[repeat, f, 2] = _pearson(estimates[take[held]], shat)
        undefined = int((~np.isfinite(score)).sum())
        out.update(status="scored" if undefined == 0 else "undefined_fold_correlations",
                   fold_scores=score, mean_fold_scores=np.mean(score, axis=1),
                   undefined_fold_correlations=undefined,
                   prediction_sha256=[hashlib.sha256(a.astype("<f8").tobytes()).hexdigest() for a in arrays])
        result["cells"].append(out)
    return result


def json_safe(value: Any) -> Any:
    """Encode undefined correlations as null without excluding their axes."""
    if isinstance(value, np.ndarray):
        return json_safe(value.tolist())
    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_safe(v) for v in value]
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value
