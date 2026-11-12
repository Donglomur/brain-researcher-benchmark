"""Continuous multiclass/midrank metrics. No threshold, fit or significance test."""
import numpy as np
from delivery_io import need


def metrics(scores, labels):
    scores = np.asarray(scores, dtype=np.float64)
    labels = np.asarray(labels)
    need(scores.ndim == 2 and labels.shape == (len(scores),) and labels.dtype.kind in 'iu' and
         np.all((labels >= 0) & (labels < scores.shape[1])) and np.all(np.isfinite(scores)), 'Exact score/target geometry')
    n = scores.shape[1]
    need(n >= 2, 'At least two candidates')
    correct = scores[np.arange(len(scores)), labels][:, None]
    greater = (scores > correct).sum(1)
    tied_other = (scores == correct).sum(1) - 1
    top = np.where(greater == 0, 1 / (tied_other + 1), 0)
    rank = 1 + greater + tied_other / 2
    pairwise = (n - 1 - greater - .5 * tied_other) / (n - 1)
    historical = (n - 1 - greater) / (n - 1)
    return {'top1_tie_fraction': float(np.mean(top)), 'mean_midrank': float(np.mean(rank)),
            'pairwise_half_ties': float(np.mean(pairwise)),
            'author_strict_greater_rank_fraction_diagnostic': float(np.mean(historical))}


def summarize(scores, labels, repeats):
    need(scores.shape[1] == 50 and len(labels) == 50 * repeats and
         all(np.sum(labels == i) == repeats for i in range(50)), 'Complete50 categories/all repeats')
    trial = metrics(scores, labels)
    # This is score-vector averaging after freeze; not averaging decoded features
    # before correlations, so it is deliberately NOT historical paper scoring.
    category_scores = np.vstack([scores[labels == i].mean(0) for i in range(50)])
    return {'trial': trial, 'private_category_mean_scores': metrics(category_scores, np.arange(50))}
