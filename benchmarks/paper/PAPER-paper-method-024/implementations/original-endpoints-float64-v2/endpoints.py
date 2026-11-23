"""Original CBraMod endpoint arithmetic on ordered post-head outputs.

This is an operator-side numerical component, not a cohort admission or a
paper-win grader. No model, EEG loader, private path, or source execution occurs.
"""
import argparse
import json
import warnings
from pathlib import Path

import numpy as np
import sklearn
from sklearn.metrics import (auc, balanced_accuracy_score, cohen_kappa_score,
                             confusion_matrix, f1_score, mean_squared_error,
                             precision_recall_curve, r2_score, roc_auc_score)


# Paper's complete primary panel; no universal person-held-out replacement.
DATASETS = {
    "FACED": ("multiclass", 9), "SEED-V": ("multiclass", 5),
    "PhysioNet-MI": ("multiclass", 4), "SHU-MI": ("binary", 2),
    "ISRUC": ("multiclass", 5), "CHB-MIT": ("binary", 2),
    "BCIC2020-3": ("multiclass", 5), "Mumtaz2016": ("binary", 2),
    "SEED-VIG": ("regression", None), "MentalArithmetic": ("binary", 2),
    "TUEV": ("multiclass", 6), "TUAB": ("binary", 2),
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def _numeric(value, name):
    value = np.asarray(value)
    require(value.dtype.kind in "fiu", name + " must be a real numeric array")
    require(np.isfinite(value).all(), name + " must be finite")
    return value


def score(dataset, targets, outputs):
    """Return the original dataset's three metrics, pooled over output rows.

    Multiclass outputs are raw class scores [N,C], binary outputs are the
    author's already-sigmoided scores [N,1], and regression outputs are [N,1].
    ISRUC alone requires targets [N,20] and scores [N,20,5]. No group weighting,
    averaging of per-batch scores, or cross-dataset aggregate is performed.
    Caller must establish identical source row order before this function.
    """
    require(dataset in DATASETS, "unknown original primary dataset")
    kind, classes = DATASETS[dataset]
    y, out = _numeric(targets, "targets"), _numeric(outputs, "outputs")
    require(y.size > 0, "empty target support")
    if dataset == "ISRUC":
        require(y.ndim == 2 and y.shape[1] == 20, "ISRUC targets require 20-epoch blocks")
        require(out.shape == (*y.shape, 5), "ISRUC outputs require [blocks,20,5]")
        y = y.reshape(-1)
        out = out.reshape(-1, 5)
    else:
        require(y.ndim == 1, "targets require one ordered vector")
        columns = classes if kind == "multiclass" else 1
        require(out.shape == (len(y), columns), "wrong original head output shape")
    if kind != "regression":
        require(np.equal(y, np.floor(y)).all() and (y >= 0).all() and (y < classes).all(),
                "targets violate the original class ontology")
        y = y.astype(np.int64)
    if kind == "binary":
        require((out >= 0).all() and (out <= 1).all(), "binary scores must already be sigmoid probabilities")
        require(len(np.unique(y)) == 2, "binary ROC area is undefined on one-class support")

    # Preserve the source .tolist()/np.array reconstruction for floating inputs,
    # including extended precision. Only integer regression operands need explicit
    # promotion: older sklearn otherwise squares residuals with modular overflow.
    # Binary ranking retains its source path without recomputing sigmoid.
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        if kind == "regression":
            truth = np.array(y.tolist())
            pred = np.array(out[:, 0].tolist())
            if truth.dtype.kind in "iu":
                truth = truth.astype(np.float64)
            if pred.dtype.kind in "iu":
                pred = pred.astype(np.float64)
            metrics = {"pearson": np.corrcoef(truth, pred)[0, 1],
                       "r2": r2_score(truth, pred),
                       "rmse": mean_squared_error(truth, pred) ** 0.5}
            details = {"target_unit": "source SEED-VIG PERCLOS scale; no conversion",
                       "rmse_unit": "same as target", "metric_units": "Pearson and R2 dimensionless"}
        else:
            pred = (out[:, 0] > 0.5).astype(np.int64) if kind == "binary" else np.argmax(out, axis=-1)
            metrics = {"balanced_accuracy": balanced_accuracy_score(y, pred)}
            if kind == "binary":
                scores = np.array(out.tolist())
                precision, recall, _ = precision_recall_curve(y, scores, pos_label=1)
                metrics.update(auc_pr=auc(recall, precision), auroc=roc_auc_score(y, scores))
            else:
                metrics.update(cohen_kappa=cohen_kappa_score(y, pred),
                               weighted_f1=f1_score(y, pred, average="weighted"))
            labels = np.union1d(y, pred)
            details = {"confusion_labels": labels.tolist(),
                       "confusion": confusion_matrix(y, pred).tolist(),
                       "target_class_support": np.bincount(y, minlength=classes).tolist(),
                       "metric_units": "fraction, not percent"}

    undefined = [key for key, value in metrics.items() if not np.isfinite(value)]
    return {"dataset": dataset, "metrics": {key: float(value) if np.isfinite(value) else None
                                             for key, value in metrics.items()},
            "undefined_metrics": undefined, "rows": len(y),
            "aggregation": "pooled source output positions", **details,
            "runtime": {"numpy": np.__version__, "scikit_learn": sklearn.__version__},
            "numerical_warnings": [str(w.message) for w in caught]}


def _position_ids(value, shape, name):
    """Validate one identity per target position without changing its order."""
    require(type(value) is list and len(value) == shape[0],
            name + " must match the target position layout")
    if len(shape) == 2:
        require(all(type(block) is list and len(block) == shape[1] for block in value),
                name + " must preserve ISRUC block and 20-position axes")
        ids = [key for block in value for key in block]
    else:
        ids = value
    require(all(type(key) is str and key.strip() for key in ids),
            name + " must contain nonempty string identities")
    require(len(set(ids)) == len(ids), name + " contains duplicate position identities")
    return ids


def score_aligned(dataset, targets, outputs, *, target_row_ids, output_row_ids):
    """Score only if both declared position layouts match exactly.

    IDs must be JSON-style lists matching the targets: [N] for ordinary datasets
    or [blocks,20] for ISRUC. Every position ID must be unique. No sorting,
    intersection, padding or weighting occurs. The caller still authenticates
    the source support and the association of each ID with its numeric value.
    """
    require(dataset in DATASETS, "unknown original primary dataset")
    shape = np.asarray(targets).shape
    if dataset == "ISRUC":
        require(len(shape) == 2 and shape[1] == 20 and shape[0] > 0,
                "ISRUC targets require nonempty 20-epoch blocks")
    else:
        require(len(shape) == 1 and shape[0] > 0, "targets require one nonempty ordered vector")
    target_ids = _position_ids(target_row_ids, shape, "target row IDs")
    output_ids = _position_ids(output_row_ids, shape, "output row IDs")
    require(target_ids == output_ids, "target/output position identities or order differ")
    result = score(dataset, targets, outputs)
    result["row_alignment"] = "exact declared position order"
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", choices=DATASETS)
    parser.add_argument("targets", type=Path, help="operator-owned numeric NPY in original row order")
    parser.add_argument("outputs", type=Path, help="numeric NPY in the identical original row order")
    parser.add_argument("--target-row-ids", type=Path,
                        help="JSON position IDs associated with the target values")
    parser.add_argument("--output-row-ids", type=Path,
                        help="JSON position IDs associated with the output values")
    args = parser.parse_args(argv)
    if (args.target_row_ids is None) != (args.output_row_ids is None):
        parser.error("--target-row-ids and --output-row-ids must be supplied together")
    targets = np.load(args.targets, allow_pickle=False)
    outputs = np.load(args.outputs, allow_pickle=False)
    if args.target_row_ids is None:
        result = score(args.dataset, targets, outputs)
    else:
        result = score_aligned(
            args.dataset, targets, outputs,
            target_row_ids=json.loads(args.target_row_ids.read_text(encoding="utf-8")),
            output_row_ids=json.loads(args.output_row_ids.read_text(encoding="utf-8")))
    print(json.dumps(result, allow_nan=False, sort_keys=True))


if __name__ == "__main__":
    main()
