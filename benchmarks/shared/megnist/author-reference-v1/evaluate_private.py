"""Evaluator-private MegNIST complete-case accuracy; no public target output.

The functions return private observation-level evidence and the author's
100*correct/total accuracy. A returned score is not reproduction, meaningful
improvement, inferred uncertainty, or a runtime-isolation qualification.
Authentic scoring requires separate authorization; module import reads none.
"""
from __future__ import annotations

import h5py
import numpy as np

from prediction_interface import _local_dataset, case_id_keys, normalize_case_ids, read_predictions, validate_logits


def score_predictions(case_ids, logits, target_case_ids, target_labels, *, expected_rows=1000):
    """Join complete opaque case support privately and derive source accuracy.

    Prediction input may arrive in a different order, but membership must equal
    the exact private canonical support. No candidate architecture grid is
    imposed here. Targets and the returned per-case evidence stay evaluator-
    private; callers must not place this result in candidate-visible logs.
    """
    ids, scores, predictions = validate_logits(case_ids, logits, expected_rows=expected_rows)
    target_ids = normalize_case_ids(target_case_ids)
    labels = np.asarray(target_labels)
    if labels.ndim != 1 or labels.shape != (len(target_ids),) or labels.dtype.kind not in "iu":
        raise ValueError("target labels must be one integer per canonical case")
    if len(target_ids) != len(ids):
        raise ValueError("target and prediction support differ")
    if np.any(labels < 0) or np.any(labels >= 10):
        raise ValueError("target labels must be original digit classes 0..9")
    prediction_keys = case_id_keys(ids)
    target_keys = case_id_keys(target_ids)
    if set(prediction_keys) != set(target_keys):
        raise ValueError("prediction cases do not equal canonical evaluator cases")
    positions = {key: index for index, key in enumerate(prediction_keys)}
    order = np.asarray([positions[key] for key in target_keys], dtype=np.int64)
    ordered_predictions = predictions[order]
    correct = ordered_predictions == labels
    count = int(len(correct))
    correct_count = int(correct.sum())
    return {
        "num_cases": count,
        "correct_count": correct_count,
        "accuracy_percent": 100.0 * correct_count / count,
        "case_ids": target_ids,
        "predictions": ordered_predictions,
        "correct": correct,
        "metric": "original argmax accuracy: 100 * correct / total",
        "scientific_qualification": False,
        "runtime_isolation_qualified": False,
        "scope": "evaluator-private complete-case score; scientific outcomes remain unknown",
    }


def evaluate_files(prediction_path, private_join_path, *, expected_rows=1000):
    """Score strict predictions against a supplied trusted private HDF5 join.

    The exact prepared join contains case_ids (N,16) uint8, labels (N,) int32,
    and original_row (N,) uint32. Joins use all16 opaque token bytes, never the
    original row map as a surrogate. The operator must bind the file to the
    accepted preparation receipt before invoking this function.
    """
    predictions = read_predictions(prediction_path, expected_rows=expected_rows)
    with h5py.File(private_join_path, "r") as handle:
        if set(handle.keys()) != {"case_ids", "labels", "original_row"} or handle.attrs or handle.userblock_size:
            raise ValueError("private join differs from the prepared schema")
        ids_ds = _local_dataset(handle, "case_ids")
        labels_ds = _local_dataset(handle, "labels")
        rows_ds = _local_dataset(handle, "original_row")
        n = len(predictions["case_ids"])
        if ids_ds.shape != (n, 16) or ids_ds.dtype != np.dtype("uint8"):
            raise ValueError("invalid private case ID metadata")
        if labels_ds.shape != (n,) or labels_ds.dtype.kind != "i" or labels_ds.dtype.itemsize != 4:
            raise ValueError("invalid private label metadata")
        if rows_ds.shape != (n,) or rows_ds.dtype != np.dtype("uint32"):
            raise ValueError("invalid private original-row metadata")
        ids = ids_ds[...]
        labels = labels_ds[...]
        original_rows = rows_ds[...]
        if not np.array_equal(np.sort(original_rows), np.arange(n, dtype=np.uint32)):
            raise ValueError("private original-row support is incomplete or duplicated")
    return score_predictions(predictions["case_ids"], predictions["logits"], ids, labels, expected_rows=expected_rows)

