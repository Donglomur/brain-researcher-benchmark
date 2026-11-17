"""Source-code-compatible Fig.2 and blocked-reconstruction scoring components.

No source fitting, data preparation, rank selection, or paper-win decision is
performed here. See SOURCE_MAP.json for the pinned author functions and README.md
for the unresolved paper/code discrepancies. NumPy is the sole dependency.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


CONDITIONS = {"straight": (0, 265), "curved": (265, 511)}
REPEATS = 20
FOLDS = 5
RECIPES = {"source_code_ridge1": 1, "paper_ols0": 0}


def _real(value, name, ndim=None):
    array = np.asarray(value)
    if array.dtype.kind not in "fiu" or (ndim is not None and array.ndim != ndim):
        raise ValueError(f"{name}: real numerical array with {ndim} dimensions required")
    if not array.size or not np.isfinite(array).all():
        raise ValueError(f"{name}: empty or nonfinite values")
    return array.astype(np.float64, copy=False)


def source_schedule(condition):
    """Original array-row identities; these are not recovered biological IDs.

    Matches np.random.seed(0); np.random.permutation used by plot_k_fold for
    each model and each condition independently. Curved position 245 in each
    permutation stays in every training fold and is never tested in that repeat.
    """
    if condition not in CONDITIONS:
        raise ValueError("condition must be straight or curved")
    start, stop = CONDITIONS[condition]
    count = stop - start
    width = count // FOLDS
    rng = np.random.RandomState(0)  # Legacy MT19937, deliberately not default_rng.
    permutations = np.stack([rng.permutation(count) + start for _ in range(REPEATS)])
    test = permutations[:, :FOLDS * width].reshape(REPEATS, FOLDS, width)
    train = np.stack([
        np.stack([np.concatenate((p[:f * width], p[(f + 1) * width:]))
                  for f in range(FOLDS)]) for p in permutations
    ])
    return {"test": test, "train": train,
            "train_only": permutations[:, FOLDS * width:],
            "permutations": permutations}


def schedule_digest(schedule):
    """Stable digest of original row-index permutations, not authentic trial IDs."""
    return hashlib.sha256(schedule["permutations"].astype("<i8").tobytes()).hexdigest()


def source_windows(neural, movement):
    """Exact Fig2.py array slices; no interpolation or time-origin inference.

    The paper/code physical-window discrepancy remains unresolved. This helper
    accepts the full source layout only: 150 bins, 511 trials, 182 neurons/2 XY.
    """
    x = _real(neural, "neural", 3)
    y = _real(movement, "movement", 3)
    if x.shape != (150, 511, 182) or y.shape != (150, 511, 2):
        raise ValueError("full source layouts must be neural[150,511,182], movement[150,511,2]")
    return x[55:-15], y[65:-5]


def integrate_displacements(displacements, initial_position):
    """Integrate per-bin displacement; do not multiply by the 10-ms bin width.

    Source velocity_decoding learns movement[1:] - movement[:-1], not a
    physical velocity divided by dt. Its first output is exactly the true start.
    """
    delta = _real(displacements, "displacements", 3)
    initial = _real(initial_position, "initial_position", 2)
    if delta.shape[2] != 2 or initial.shape != delta.shape[1:]:
        raise ValueError("expected displacements[time-1,trial,2] and initial_position[trial,2]")
    result = np.concatenate((initial[None], initial[None] + np.cumsum(delta, axis=0)))
    if not np.isfinite(result).all():
        raise ValueError("integration overflow")
    return result


def trajectory_r2(target, prediction):
    """Source trial_wise_r2: coordinate-centered, XY-pooled position R².

    A time-constant target makes the author's denominator zero. Reject it
    explicitly rather than silently dropping a trial or publishing NaN/Inf.
    Negative values are preserved, and the source population SD is returned.
    """
    truth = _real(target, "target", 3)
    pred = _real(prediction, "prediction", 3)
    if truth.shape != pred.shape or truth.shape[0] < 2 or truth.shape[2] != 2:
        raise ValueError("aligned target/prediction[time>=2,trial,2] required")
    with np.errstate(over="ignore", invalid="ignore"):
        sse = np.sum(np.square(truth - pred), axis=(0, 2))
        sst = np.sum(np.square(truth - truth.mean(axis=0, keepdims=True)), axis=(0, 2))
    if not np.isfinite(sse).all() or not np.isfinite(sst).all():
        raise ValueError("squared-error overflow")
    if np.any(sst == 0):
        raise ValueError("undefined R2: zero within-trial temporal variance")
    r2 = 1 - sse / sst
    if not np.isfinite(r2).all():
        raise ValueError("R2 overflow")
    return {"r2": r2, "sse": sse, "sst": sst,
            "mean": float(r2.mean()), "population_sd": float(r2.std())}


def score_condition(movement, condition, prediction, test_indices):
    """Score all original repeated-fold outputs for one reach condition.

    movement: full source[150,511,2]; prediction:[20,5,80,53-or-49,2].
    test_indices:[20,5,53-or-49] must match the original seed-0 permutation
    order. Test initial positions are permitted observations and checked here.
    """
    truth = _real(movement, "movement", 3)
    if truth.shape != (150, 511, 2):
        raise ValueError("movement must retain the complete source[150,511,2] layout")
    plan = source_schedule(condition)
    indices = np.asarray(test_indices)
    if indices.dtype.kind not in "iu" or not np.array_equal(indices, plan["test"]):
        raise ValueError("test indices differ from exact source fold order")
    pred = _real(prediction, "prediction", 5)
    width = plan["test"].shape[-1]
    if pred.shape != (REPEATS, FOLDS, 80, width, 2):
        raise ValueError("prediction must retain every repeat, fold, time bin, trial, and XY")
    window = truth[65:-5]
    scores = np.empty((REPEATS, FOLDS, width))
    fold_sd = np.empty((REPEATS, FOLDS))
    for repeat in range(REPEATS):
        for fold in range(FOLDS):
            selected = window[:, indices[repeat, fold], :]
            current = pred[repeat, fold]
            if not np.array_equal(current[0], selected[0]):
                raise ValueError("integrated predictions must prepend the true initial position")
            result = trajectory_r2(selected, current)
            scores[repeat, fold] = result["r2"]
            fold_sd[repeat, fold] = result["population_sd"]
    start, stop = CONDITIONS[condition]
    counts = np.bincount(indices.ravel() - start, minlength=stop - start)
    sums = np.bincount(indices.ravel() - start, weights=scores.ravel(), minlength=stop - start)
    trial_means = np.divide(sums, counts, out=np.full(len(counts), np.nan), where=counts != 0)
    summary = {
        "condition": condition, "mean_trial_fold_repeat_r2": float(scores.mean()),
        "mean_within_fold_population_sd": float(fold_sd.mean()),
        "source_trials": stop - start, "repeated_test_occurrences": int(scores.size),
        "test_trials_per_fold": width, "repeats": REPEATS, "folds": FOLDS,
        "training_only_trials_per_repeat": plan["train_only"].shape[1],
        "trial_test_count_min": int(counts.min()), "trial_test_count_max": int(counts.max()),
        "permutation_index_sha256": schedule_digest(plan),
        "independent_unit": "reaching trial within one monkey session",
        "uncertainty": "none; repeated folds are dependent and the reported SD is not a confidence interval",
    }
    details = {"r2": scores, "fold_population_sd": fold_sd, "test_indices": indices,
               "train_only_indices": plan["train_only"], "trial_test_counts": counts,
               "trial_mean_r2": trial_means, "trial_indices": np.arange(start, stop)}
    return summary, details


def source_trimmed_mask(training_mask, cut_bins):
    """Source run_tca/cv_search edge trimming on [trial,neuron,time].

    1 means observed/training, 0 means held out. The source trims the FIRST and
    LAST zero in each trace, not each interior disconnected zero block. We
    preserve that behavior and leave source mask realization recovery separate.
    """
    mask = np.asarray(training_mask)
    if mask.ndim != 3 or not mask.size or mask.dtype.kind not in "biuf":
        raise ValueError("training_mask must be a nonempty binary[trial,neuron,time] tensor")
    if not np.isin(mask, (0, 1)).all():
        raise ValueError("mask values must be exactly 0 or 1")
    if isinstance(cut_bins, bool) or not isinstance(cut_bins, (int, np.integer)) or cut_bins < 0:
        raise ValueError("cut_bins must be a nonnegative integer")
    trimmed = mask.astype(bool, copy=True)
    if cut_bins:
        for trace in trimmed.reshape(-1, trimmed.shape[-1]):
            zeros = np.flatnonzero(~trace)
            if zeros.size:
                first, last = int(zeros[0]), int(zeros[-1])
                # The second slice intentionally retains Python's negative-start
                # semantics, just like the pinned source; no silent clipping.
                trace[first:first + cut_bins] = True
                trace[last - cut_bins + 1:last + 1] = True
    return trimmed


def reconstruction_error(target, prediction, training_mask, *, cut_bins):
    """Original held-out root error plus MSE and explicit evaluation support.

    Source sqrt(mean(masked residual²)/mean(1-mask)) equals sqrt(SSE/n_holdout)
    for a binary mask. Training loss in source is zero-filled over ALL tensor
    entries, so it is reported separately from conditional training-entry MSE.
    """
    truth = _real(target, "target", 3)
    pred = _real(prediction, "prediction", 3)
    mask = np.asarray(training_mask)
    if pred.shape != truth.shape or mask.shape != truth.shape:
        raise ValueError("target, prediction and training mask must have identical shapes")
    trimmed = source_trimmed_mask(mask, cut_bins)
    heldout = ~trimmed
    count = int(heldout.sum())
    if count == 0:
        raise ValueError("undefined reconstruction error: trimming leaves no held-out entries")
    with np.errstate(over="ignore", invalid="ignore"):
        squared = np.square(pred - truth)
    if not np.isfinite(squared).all():
        raise ValueError("squared-error overflow")
    sse = float(squared[heldout].sum())
    train = mask.astype(bool)
    train_count = int(train.sum())
    train_sse = float(squared[train].sum())
    if not np.isfinite(sse) or not np.isfinite(train_sse):
        raise ValueError("squared-error sum overflow")
    return {
        "heldout_sse": sse, "heldout_mse": sse / count, "source_cv_root_error": float(np.sqrt(sse / count)),
        "heldout_entries_after_trim": count, "heldout_entries_before_trim": int((~train).sum()),
        "training_entries": train_count, "total_entries": int(truth.size), "cut_bins": int(cut_bins),
        "source_zero_filled_training_mse": train_sse / truth.size,
        "training_entry_mse": train_sse / train_count if train_count else None,
        "metric_units": "MSE: squared input units; root error: input units",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    decode = sub.add_parser("score-fig2", help="operator-only full repeated-fold position scoring")
    decode.add_argument("--input", type=Path, required=True)
    decode.add_argument("--recipe", choices=RECIPES, required=True,
                        help="declared prediction provenance, not verified fitting or paper/code reconciliation")
    decode.add_argument("--summary", type=Path, required=True)
    decode.add_argument("--private-details", type=Path, required=True)
    recon = sub.add_parser("score-reconstruction", help="one externally frozen rank/type/mask realization")
    recon.add_argument("--input", type=Path, required=True)
    recon.add_argument("--cut-bins", type=int, required=True)
    recon.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()
    with np.load(args.input, allow_pickle=False) as bundle:
        if args.command == "score-fig2":
            expected = {"movement", "straight_prediction", "straight_test_indices", "curved_prediction", "curved_test_indices"}
            if set(bundle.files) != expected:
                raise ValueError("Fig.2 bundle must contain exactly movement and predictions/test indices for both conditions")
            summaries, details = {}, {}
            for condition in CONDITIONS:
                summary, private = score_condition(bundle["movement"], condition,
                    bundle[condition + "_prediction"], bundle[condition + "_test_indices"])
                summaries[condition] = summary
                details.update({condition + "_" + key: value for key, value in private.items()})
            report = {"scope": "source-code-compatible Fig.2 scoring component",
                      "declared_decoder_recipe": args.recipe,
                      "recipe_provenance_authenticated": False, "conditions": summaries,
                      "combined_decoding_reconstruction_paper_win": "not_evaluated"}
            # All validation completes before output. Refuse accidental overwrite.
            with args.private_details.open("xb") as handle:
                np.savez(handle, **details)
        else:
            if set(bundle.files) != {"target", "prediction", "training_mask"}:
                raise ValueError("reconstruction bundle requires exactly target, prediction, training_mask")
            report = reconstruction_error(bundle["target"], bundle["prediction"], bundle["training_mask"], cut_bins=args.cut_bins)
            report["scope"] = "one source-code-compatible reconstruction cell; original mask/rank roster is not authenticated"
    with args.summary.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, allow_nan=False)
        handle.write("\n")


if __name__ == "__main__":
    main()
