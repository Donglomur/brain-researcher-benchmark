"""Derive source-grid GLM quantities from candidate expected-count operands.

This adapter accepts no candidate counts, masks, CV scores or aggregate scores.
The operator must authenticate the reference and freeze the complete submission
before calling it. Positive expected-count arrays do not prove how a model was
trained; in particular, this adapter does not attest out-of-fold fitting.
"""
from __future__ import annotations

import copy
import re

import numpy as np

from deps import G, R, V, K


CANDIDATE_KEYS = frozenset({
    "schema", "job_id", "method_sha256", "row_ids", "unit_ids", "fold_ids",
    "alpha_oof_predictions", "full_predictions", "selected_alpha_indices",
})


def need(condition, message):
    if not condition:
        raise ValueError(message)


def _job(reference):
    need(isinstance(reference, dict), "operator reference must be a mapping")
    required = {"job", "case_id", "packet_pin", "row_ids", "unit_ids", "counts"}
    need(required <= set(reference), "complete operator GLM reference required")
    job = reference["job"]
    expected_keys = {"region", "basis_index", "basis", "animal", "session_index", "id"}
    need(isinstance(job, dict) and set(job) == expected_keys, "exact original GLM job fields required")
    region, animal = job["region"], job["animal"]
    basis, session = job["basis_index"], job["session_index"]
    need(region in K.REGIONS and animal in K.ANIMALS, "unknown original region or animal")
    need(type(basis) is int and 0 <= basis < len(G.GRID), "original basis index required")
    need(type(session) is int and 0 <= session < 8, "original session index required")
    need(job["basis"] == list(G.GRID[basis]), "basis values differ from original grid")
    need(job["id"] == f"{region}-b{basis:03d}-{animal}-s{session + 1:02d}",
         "GLM job ID differs from original coordinate")
    need(reference["case_id"] == f"{animal}-s{session + 1:02d}-{region}",
         "operator case ID differs from original coordinate")
    return job


def _expected_counts(value, shape, name):
    a = np.asarray(value)
    need(a.shape == shape and a.dtype.kind in "fiu", name + " has wrong numeric shape or dtype")
    a = a.astype(np.float64, copy=True)
    need(np.isfinite(a).all() and (a > 0).all(), name + " must contain finite positive expected counts")
    return a


def evaluate_glm(reference, candidate):
    """Evaluate one original coordinate; the outer collector requires all13,824.

    ``alpha_oof_predictions[r, u, a]`` is the prediction for row r from its
    frozen test fold at original alpha a. The new raw tensor is necessary to
    recompute all100 scores/unit: old producer checkpoints contain scores, not
    this tensor. Full-refit predictions are supplied separately. Reuse of the
    selected column supplies an explicitly labelled selected-alpha OOF output;
    it is not evidence of the original producer's ten additional refits.
    """
    job = _job(reference)
    need(isinstance(candidate, dict) and set(candidate) == CANDIDATE_KEYS,
         "exact raw GLM candidate fields required; supplied targets or scores are forbidden")
    need(candidate["schema"] == "population_glm_candidate_v1", "unknown GLM candidate schema")
    need(candidate["job_id"] == job["id"], "candidate GLM job differs from operator job")
    method = candidate["method_sha256"]
    need(isinstance(method, str) and re.fullmatch(r"[0-9a-f]{64}", method) is not None,
         "frozen candidate method SHA256 required")

    raw_counts = np.asarray(reference["counts"])
    need(raw_counts.ndim == 2 and raw_counts.dtype.kind in "fiu",
         "operator counts must be a plain numeric matrix")
    counts = K.counts_array(raw_counts, len(raw_counts)).copy()
    nrows, nunits = counts.shape
    need(nrows >= 10, "all ten contiguous folds require at least ten rows")
    row_ids = R.identities(reference["row_ids"], nrows, "operator row IDs")
    unit_ids = R.identities(reference["unit_ids"], nunits, "operator unit IDs")
    for key, expected in (("row_ids", row_ids), ("unit_ids", unit_ids)):
        supplied = R.identities(candidate[key], len(expected), "candidate " + key)
        need(np.array_equal(supplied, expected), "candidate " + key + " differs from exact source order")
    folds = V.source_fold_ids(nrows)
    supplied_folds = np.asarray(candidate["fold_ids"])
    need(supplied_folds.dtype.kind in "iu" and np.array_equal(supplied_folds, folds),
         "candidate folds differ from original unshuffled ten-fold assignment")
    held = _expected_counts(candidate["alpha_oof_predictions"], (nrows, nunits, 10),
                            "all-alpha held predictions")
    full = _expected_counts(candidate["full_predictions"], counts.shape, "full-refit predictions")
    declared_selected = np.asarray(candidate["selected_alpha_indices"])
    need(declared_selected.shape == (nunits,) and declared_selected.dtype.kind in "iu"
         and (declared_selected >= 0).all() and (declared_selected < 10).all(),
         "one in-range selected alpha index per original unit required")

    scores = np.empty((nunits, 10, 10), dtype=np.float64)
    model_deviance = np.empty_like(scores)
    null_deviance = None
    for alpha in range(10):
        model, null = V.fold_deviances(counts, held[:, :, alpha], folds)
        if null_deviance is None:
            null_deviance = null
        else:
            need(np.array_equal(null, null_deviance), "operator null deviance changed across alpha slots")
        model_deviance[:, alpha, :] = model
        # The original ratio is deliberately not clipped or made finite:
        # 0/0 gives NaN; positive/0 gives -infinity after subtraction from1.
        with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
            scores[:, alpha, :] = 1 - model / null
    means, deviations, valid = G.score_statistics(scores)
    selected = np.argmax(means, axis=1)
    need(np.array_equal(declared_selected, selected),
         "declared selected alpha differs from source nanmean then ordinary argmax")
    selected_oof = np.take_along_axis(held, selected[None, :, None], axis=2)[:, :, 0]
    selected_means = means[np.arange(nunits), selected]
    result = {
        "schema": "population_evaluator_glm_result_v1", "job": copy.deepcopy(job),
        "case_id": reference["case_id"], "packet_pin": copy.deepcopy(reference["packet_pin"]),
        "row_ids": row_ids.copy(), "unit_ids": unit_ids.copy(), "fold_ids": folds.copy(),
        "counts": counts, "predictions": full, "oof_predictions": selected_oof.copy(),
        "cv_scores": scores, "cv_model_deviance": model_deviance,
        "cv_null_deviance": null_deviance, "selected_alpha_indices": selected.copy(),
        "alpha_grid": G.ALPHAS.copy(), "selected_alphas": G.ALPHAS[selected],
        "test_scores": means, "test_devs": deviations, "num_valid": valid,
        "source_session_mean_selected_cv_d2": float(np.mean(selected_means)),
        "method_sha256": method,
        "prediction_roles": {
            "predictions": "candidate-declared full-row expectations; fitting provenance unverified",
            "oof_predictions": "selected column of submitted all-alpha held tensor; no extra refit asserted",
        },
        "score_provenance": "evaluator-owned counts, fixed test-fold null means, source nanmean/argmax",
        "numerical_metric_policy": "stable mathematical Poisson deviance via retained replay; exact constant-fold zero-null",
        "native_cv_score_bitwise_parity_established": False,
        "training_provenance_attested": False,
        "source_producer_exports_all_alpha_held_tensor": False,
        "paper_reproduction_established": False, "paper_improvement_established": False,
    }
    for key in ("source_asset_id", "source_epoch", "times", "trial_ids"):
        if key in reference:
            result[key] = copy.deepcopy(reference[key])
    return result
