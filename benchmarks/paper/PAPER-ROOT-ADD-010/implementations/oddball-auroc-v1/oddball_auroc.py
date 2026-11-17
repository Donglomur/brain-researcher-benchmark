"""Score frozen predictions on the source's six directional run folds.

No fitting, source-data preparation, cluster selection, or paper-win decision.
Inputs are evaluator-owned retained-epoch metadata and frozen prediction rows.
The caller must establish their source/preprocessing identity independently.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


SOURCE_REVISION = "133669b577b5ae341cd0842dfb0e7f0af85c0020"
SUBJECTS = tuple(f"sub-{n:02}" for n in range(1, 21))
SHAPES = ("rectangle", "square", "isoTrapezoid", "parallelogram", "losange",
          "kite", "rightKite", "rustedHinge", "hinge", "trapezoid", "random")
TIMES = np.arange(301, dtype=float) / 250 - 0.1
BRANCHES = ("unsmoothed", "smoothed")
# Source script order; misleading source variable names even/odd are avoided.
FOLDS = (
    ("1357_to_2468", (1, 3, 5, 7), (2, 4, 6, 8)),
    ("2468_to_1357", (2, 4, 6, 8), (1, 3, 5, 7)),
    ("1256_to_3478", (1, 2, 5, 6), (3, 4, 7, 8)),
    ("3478_to_1256", (3, 4, 7, 8), (1, 2, 5, 6)),
    ("1234_to_5678", (1, 2, 3, 4), (5, 6, 7, 8)),
    ("5678_to_1234", (5, 6, 7, 8), (1, 2, 3, 4)),
)


def auroc(labels, scores):
    """Mann–Whitney AUROC per column; ties contribute one half.

    Label 1 is reference, exactly as in the archived source decoder. Scores
    must increase towards reference. Arbitrary finite margins are supported.
    """
    labels = np.asarray(labels)
    scores = np.asarray(scores)
    if labels.ndim != 1 or not np.isin(labels, [0, 1]).all():
        raise ValueError("labels must be a binary vector")
    if scores.ndim != 2 or scores.shape[0] != len(labels) or not scores.shape[1]:
        raise ValueError("scores must be trial by time")
    if scores.dtype.kind not in "fiu" or not np.isfinite(scores).all():
        raise ValueError("scores must be finite real numbers")
    n_pos = int(np.sum(labels == 1))
    n_neg = len(labels) - n_pos
    if not n_pos or not n_neg:
        raise ValueError("each evaluated cell must contain both classes")
    result = np.empty(scores.shape[1], dtype=float)
    # Rank using exact score ties, without rounding margins or sigmoid fitting.
    for t in range(scores.shape[1]):
        order = np.argsort(scores[:, t], kind="stable")
        values = scores[order, t]
        starts = np.r_[0, np.flatnonzero(values[1:] != values[:-1]) + 1]
        stops = np.r_[starts[1:], len(values)]
        ranks = np.repeat((starts + stops + 1) / 2, stops - starts)
        rank_sum = np.sum(ranks[labels[order] == 1])
        result[t] = (rank_sum - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)
    return result


def run_inventory(subject):
    if subject not in SUBJECTS:
        raise ValueError("subject must belong to the original twenty-person cohort")
    return tuple(range(1, 8 if subject in ("sub-10", "sub-11") else 9))


def fold_plan(subject, trials):
    """Return exact retained late-epoch identities for all six source folds.

    Metadata is supplied for all retained epochs, including early epochs.
    Identity is an opaque stable string; it must survive rejection/reordering.
    The scorer does not reconstruct early/late status from retained row order.
    """
    expected_runs = set(run_inventory(subject))
    if not isinstance(trials, list) or not trials:
        raise ValueError("trials must be a nonempty list")
    by_id = {}
    observed_runs = set()
    for row in trials:
        if set(row) != {"trial_id", "run", "shape", "condition", "is_early"}:
            raise ValueError("unexpected trial metadata fields")
        identity = row["trial_id"]
        if not isinstance(identity, str) or not identity or identity in by_id:
            raise ValueError("trial identities must be unique nonempty strings")
        if type(row["run"]) is not int or row["run"] not in expected_runs:
            raise ValueError("run must be an original integer run identity")
        if row["shape"] not in SHAPES or row["condition"] not in ("reference", "outlier"):
            raise ValueError("unknown shape or condition")
        if row["is_early"] not in ("early", "late"):
            raise ValueError("is_early must preserve source early/late metadata")
        observed_runs.add(row["run"])
        by_id[identity] = row
    if observed_runs != expected_runs:
        raise ValueError("incomplete original run inventory")
    late = [r for r in trials if r["is_early"] == "late"]
    plans = []
    for name, train_runs, test_runs in FOLDS:
        train = [r for r in late if r["run"] in train_runs]
        test = [r for r in late if r["run"] in test_runs]
        # Source trains jointly across all eleven shapes; every directional
        # test cell must have both classes, otherwise AUROC is undefined.
        for side, rows in (("train", train), ("test", test)):
            if {r["shape"] for r in rows} != set(SHAPES):
                raise ValueError(f"{name}: {side} does not contain all eleven shapes")
            if {r["condition"] for r in rows} != {"reference", "outlier"}:
                raise ValueError(f"{name}: {side} must contain both classes")
        for shape in SHAPES:
            if {r["condition"] for r in test if r["shape"] == shape} != {"reference", "outlier"}:
                raise ValueError(f"{name}: {shape} test cell must contain both classes")
        plans.append({"fold": name, "train_ids": [r["trial_id"] for r in train],
                      "test_ids": [r["trial_id"] for r in test]})
    return plans


def score_subject(subject, trials, predictions, times):
    """Score one branch, with one identity-aligned prediction matrix per fold.

    Each fold supplies {fold, trial_ids, scores}; only that fold's test rows
    are accepted. Prediction order may differ from metadata order.
    """
    times = np.asarray(times)
    if times.shape != TIMES.shape or times.dtype.kind not in "fiu" or not np.allclose(
            times, TIMES, atol=1e-12, rtol=0):
        raise ValueError("require the pinned code's 301 times, -0.1 to 1.1 seconds")
    plans = fold_plan(subject, trials)
    if not isinstance(predictions, list) or len(predictions) != len(FOLDS):
        raise ValueError("require exactly six directional prediction folds")
    by_fold = {}
    for prediction in predictions:
        if set(prediction) != {"fold", "trial_ids", "scores"}:
            raise ValueError("unexpected prediction fields")
        name = prediction["fold"]
        if not isinstance(name, str) or name in by_fold:
            raise ValueError("duplicate or invalid prediction fold")
        by_fold[name] = prediction
    if set(by_fold) != {f[0] for f in FOLDS}:
        raise ValueError("prediction fold names differ from the source")
    by_id = {r["trial_id"]: r for r in trials}
    fold_scores, counts = [], []
    for plan in plans:
        prediction = by_fold[plan["fold"]]
        ids = prediction["trial_ids"]
        if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
            raise ValueError("prediction trial_ids must be a string list")
        if len(ids) != len(set(ids)) or set(ids) != set(plan["test_ids"]):
            raise ValueError("prediction identities must match every late test epoch exactly")
        scores = np.asarray(prediction["scores"])
        if scores.shape != (len(ids), len(TIMES)) or scores.dtype.kind not in "fiu" or not np.isfinite(scores).all():
            raise ValueError("prediction scores must be finite test trial by 301 times")
        rows = [by_id[i] for i in ids]
        shapes = np.array([r["shape"] for r in rows])
        labels = np.array([r["condition"] == "reference" for r in rows], dtype=int)
        shape_scores, shape_counts = [], []
        for shape in SHAPES:
            use = shapes == shape
            shape_scores.append(auroc(labels[use], scores[use]))
            shape_counts.append([int(np.sum(labels[use] == 0)), int(np.sum(labels[use] == 1))])
        fold_scores.append(shape_scores)
        counts.append(shape_counts)
    fold_scores = np.asarray(fold_scores)
    return {"subject": subject, "fold_auroc": fold_scores,
            "shape_time_auroc": fold_scores.mean(axis=0),
            "test_counts_outlier_reference": np.asarray(counts)}


def score_cohort(packet):
    """Compute both branches for the complete source cohort; never select a peak."""
    if set(packet) != {"source_revision", "score_orientation", "times", "subjects"}:
        raise ValueError("unexpected cohort packet fields")
    if packet["source_revision"] != SOURCE_REVISION:
        raise ValueError("source revision mismatch")
    if packet["score_orientation"] != "higher_is_reference":
        raise ValueError("source labels require higher_is_reference scores")
    subjects = packet["subjects"]
    if not isinstance(subjects, list) or len(subjects) != 20:
        raise ValueError("require the complete twenty-person sensor cohort")
    by_subject = {}
    for entry in subjects:
        if set(entry) != {"subject", "trials", "branches"}:
            raise ValueError("unexpected subject fields")
        name = entry["subject"]
        if name not in SUBJECTS or name in by_subject:
            raise ValueError("duplicate or unknown subject")
        if set(entry["branches"]) != set(BRANCHES):
            raise ValueError("both smoothing branches must be supplied separately")
        by_subject[name] = entry
    branches = {}
    for branch in BRANCHES:
        results = [score_subject(subject, by_subject[subject]["trials"],
                                 by_subject[subject]["branches"][branch], packet["times"])
                   for subject in SUBJECTS]
        curves = np.stack([r["shape_time_auroc"] for r in results])
        branches[branch] = {
            "subject_fold_shape_time_auroc": np.stack([r["fold_auroc"] for r in results]).tolist(),
            "subject_shape_time_auroc": curves.tolist(),
            "mean_shape_time_auroc": curves.mean(axis=0).tolist(),
            "test_counts_outlier_reference": np.stack([r["test_counts_outlier_reference"] for r in results]).tolist(),
        }
    return {"scope": "source_code_prediction_scoring_only", "source_revision": SOURCE_REVISION,
            "subject_order": list(SUBJECTS), "shape_order": list(SHAPES),
            "fold_order": [f[0] for f in FOLDS], "times_seconds": TIMES.tolist(),
            "score_orientation": "higher_is_reference", "branches": branches}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    raw = args.packet.read_bytes()
    result = score_cohort(json.loads(raw))
    result["input_sha256"] = hashlib.sha256(raw).hexdigest()
    with args.output.open("x") as handle:
        json.dump(result, handle, allow_nan=False, separators=(",", ":"))
        handle.write("\n")


if __name__ == "__main__":
    main()
