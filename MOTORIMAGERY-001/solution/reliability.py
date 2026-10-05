"""Pooled OOF inference under a fixed, original-cue-pair conditional null."""
import numpy as np


def holm_adjust(pvalues):
    p = np.asarray(pvalues, dtype=float)
    if p.ndim != 1 or not len(p) or not np.isfinite(p).all() or np.any((p < 0) | (p > 1)):
        raise ValueError("p-values must be a nonempty finite vector in [0,1]")
    order = np.argsort(p, kind="stable")
    adjusted = np.minimum(1, np.maximum.accumulate((len(p)-np.arange(len(p)))*p[order]))
    result = np.empty_like(p)
    result[order] = adjusted
    return result


def permutation_targets(labels, runs, event_index, n_permutations, run_order=(6, 10, 14), seed=0):
    labels, runs, event_index = map(np.asarray, (labels, runs, event_index))
    if labels.ndim != 1 or labels.shape != runs.shape or labels.shape != event_index.shape:
        raise ValueError("one original cue index and run per binary epoch label required")
    if not np.isin(labels, [0, 1]).all() or not np.isfinite(event_index).all():
        raise ValueError("invalid binary labels or source event indices")
    if not np.equal(event_index, np.floor(event_index)).all() or np.any((event_index < 0) | (event_index > 14)):
        raise ValueError("original source cue indices must be integers 0..14")
    if type(n_permutations) is not int or n_permutations < 1 or set(runs) != set(run_order):
        raise ValueError("positive permutation count and complete fixed run set required")
    blocks = []
    for run in run_order:
        run_indices = event_index[runs == run]
        if len(np.unique(run_indices)) != len(run_indices):
            raise ValueError("duplicate original event within run")
        for pair in range(7):
            selected = np.flatnonzero((runs == run) & (event_index//2 == pair))
            if len(selected) == 2:
                selected = selected[np.argsort(event_index[selected])]
                if set(labels[selected]) != {0, 1}:
                    raise ValueError("complete original cue pair must contain one label of each class")
                blocks.append(selected)
    rng = np.random.RandomState(seed)
    targets = np.tile(labels.astype(np.int64), (n_permutations+1, 1))
    for replicate in range(1, n_permutations+1):
        for selected in blocks:  # run6/10/14 then original pair0..6; no draw for orphans
            targets[replicate, selected] = rng.permutation(labels[selected])
    return targets


def accuracy_kappa(target, prediction):
    target, prediction = np.asarray(target), np.asarray(prediction)
    if target.ndim != 1 or not len(target) or target.shape != prediction.shape:
        raise ValueError("complete same-length target and prediction vectors required")
    if not np.isin(target, [0, 1]).all() or not np.isin(prediction, [0, 1]).all():
        raise ValueError("classes must be 0 and 1")
    observed = float(np.mean(target == prediction))
    expected = float(sum(np.mean(target == k)*np.mean(prediction == k) for k in (0, 1)))
    if expected == 1:
        raise ValueError("kappa is undefined for a degenerate single-class outcome")
    return observed, (observed-expected)/(1-expected)


def subject_statistics(subject, runs, targets, predictions):
    targets, predictions = np.asarray(targets), np.asarray(predictions)
    if targets.ndim != 2 or targets.shape != predictions.shape or targets.shape[0] < 2:
        raise ValueError("observed and complete permutation OOF matrices required")
    accuracy, kappa = accuracy_kappa(targets[0], predictions[0])
    n_correct = np.sum(targets == predictions, axis=1)
    null = n_correct[1:]/targets.shape[1]
    exceedance = int(np.count_nonzero(n_correct[1:] >= n_correct[0]))
    return {"subject": int(subject), "n_epochs": targets.shape[1], "n_runs": len(np.unique(runs)),
            "accuracy": accuracy, "kappa": kappa, "perm_p": (1+exceedance)/targets.shape[0],
            "null_mean": float(null.mean()), "null_sd": float(null.std(ddof=0)),
            "n_null_ge_observed": exceedance}


def group_statistics(rows, n_permutations):
    from scipy.stats import ttest_1samp
    if not rows:
        raise ValueError("at least one measured subject required")
    accuracy = np.array([row["accuracy"] for row in rows], dtype=float)
    p = np.array([row["perm_p"] for row in rows], dtype=float)
    adjusted = holm_adjust(p)
    for row, value in zip(rows, adjusted):
        row["holm_p"] = float(value)
    if len(accuracy) < 2 or np.all(accuracy == accuracy[0]):
        t_stat = p_group = None
    else:
        measured = ttest_1samp(accuracy, .5, alternative="two-sided")
        t_stat, p_group = float(measured.statistic), float(measured.pvalue)
        if not np.isfinite(t_stat) or not np.isfinite(p_group):
            raise ValueError("undefined nondegenerate group t statistic")
    return {"n_subjects": len(rows), "n_epochs_total": int(sum(row["n_epochs"] for row in rows)),
            "n_classes": 2, "chance_level": .5, "accuracy": float(accuracy.mean()),
            "cohen_kappa": float(np.mean([row["kappa"] for row in rows])),
            "finite_sample_null_sd": float(np.mean([row["null_sd"] for row in rows])),
            "group_t_vs_chance": t_stat, "group_p_vs_chance": p_group,
            "n_subjects_significant_perm_p05": int(np.count_nonzero(p < .05)),
            "n_subjects_significant_holm_p05": int(np.count_nonzero(adjusted < .05)),
            "n_subjects_below_chance": int(np.count_nonzero(accuracy < .5)),
            "n_subjects_above_half_nominal": int(np.count_nonzero(accuracy > .5)),
            "permutation_p_resolution": 1/(n_permutations+1)}
