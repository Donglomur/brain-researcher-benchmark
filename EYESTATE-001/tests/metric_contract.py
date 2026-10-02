"""Public source-free numerical contract; no fitted answer or outcome target."""
import numpy as np


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def connectivity(timeseries):
    """Population z-scoring and direct Ledoit-Wolf moments, independently per person."""
    raw = np.asarray(timeseries, dtype=np.float64)
    require(raw.ndim == 2 and raw.shape[0] > 1 and raw.shape[1] > 1 and np.isfinite(raw).all(),
            'finite two-dimensional source time series')
    centered = raw - raw.mean(axis=0)
    sd = centered.std(axis=0, ddof=0)
    denominator = np.where(sd < np.finfo(float).eps, 1., sd)
    standardized = centered / denominator
    q = standardized - standardized.mean(axis=0)
    n, p = q.shape
    empirical = (q.T @ q) / n
    mu = float(np.trace(empirical) / p)
    empirical_square = float(np.sum(empirical * empirical))
    fourth = float(np.sum(np.sum(q * q, axis=1) ** 2))
    beta = (fourth / n - empirical_square) / (p * n)
    delta = (empirical_square - 2 * mu * float(np.trace(empirical)) + p * mu * mu) / p
    beta = min(beta, delta)
    shrinkage = 0. if beta == 0 else beta / delta
    require(np.isfinite(shrinkage) and 0 <= shrinkage <= 1, 'finite valid Ledoit-Wolf shrinkage')
    covariance = (1 - shrinkage) * empirical
    covariance.flat[::p + 1] += shrinkage * mu
    diagonal = np.diag(covariance)
    require(np.isfinite(covariance).all() and np.all(diagonal > 0), 'defined covariance correlation')
    correlation = covariance / np.sqrt(diagonal[:, None] * diagonal[None, :])
    i, j = np.tril_indices(p, -1)
    vector = correlation[i, j]
    require(np.isfinite(vector).all() and np.all(np.abs(vector) <= 1 + 1e-12), 'correlation domain')
    return dict(correlation=vector, shrinkage=float(shrinkage), roi_i=i, roi_j=j)


def make_folds(labels, sites, n_splits=10):
    labels = np.asarray(labels, dtype=np.int64); sites = np.asarray(sites)
    require(labels.ndim == sites.ndim == 1 and len(labels) == len(sites) and set(labels) == {0, 1},
            'two-class complete cohort')
    unique, inverse = np.unique(sites, return_inverse=True)
    # Match SKF class numbering by first appearance, not sorted source label.
    _, first, encoded_sorted = np.unique(labels, return_index=True, return_inverse=True)
    encoded = np.argsort(first)[encoded_sorted]
    counts = np.bincount(encoded)
    require(counts.min() >= n_splits, 'enough source members for stratified folds')
    ordered = np.sort(encoded)
    allocation = np.array([np.bincount(ordered[i::n_splits], minlength=len(counts)) for i in range(n_splits)])
    random_fold = np.empty(len(labels), dtype=np.int64)
    rng = np.random.RandomState(0)
    for c in range(len(counts)):
        assignment = np.repeat(np.arange(n_splits), allocation[:, c])
        rng.shuffle(assignment)
        random_fold[encoded == c] = assignment
    records = []
    for scheme, membership in [('loso', inverse), ('random10', random_fold)]:
        for fold_id in sorted(set(map(int, membership))):
            test = np.flatnonzero(membership == fold_id); train = np.flatnonzero(membership != fold_id)
            require(len(test) > 0 and set(labels[train]) == {0, 1}, 'nonempty test and two-class training required')
            records.append(dict(scheme=scheme, fold_id=fold_id, held_out_site=str(unique[fold_id]) if scheme == 'loso' else None,
                                train=train, test=test))
    return records


def scale_training(features):
    x = np.asarray(features, dtype=np.float64)
    require(x.ndim == 2 and len(x) > 0 and np.isfinite(x).all(), 'finite training features')
    n = len(x); mean = x.sum(axis=0) / n
    deviation = x - mean
    variance = ((deviation * deviation).sum(axis=0) - deviation.sum(axis=0) ** 2 / n) / n
    require(np.isfinite(variance).all() and np.all(variance >= 0), 'nonnegative population variance')
    eps = np.finfo(float).eps
    constant = variance <= n * eps * variance + (n * mean * eps) ** 2
    scale = np.sqrt(variance); scale[constant] = 1
    require(np.isfinite(mean).all() and np.isfinite(scale).all() and np.all(scale > 0), 'finite scaler')
    return dict(mean=mean, variance=variance, scale=scale, constant=constant)


def fit_certificate(z, labels, coefficient, intercept):
    z = np.asarray(z, dtype=float); w = np.asarray(coefficient, dtype=float)
    t = 2 * np.asarray(labels, dtype=np.int64) - 1
    require(z.ndim == 2 and w.shape == (z.shape[1],) and len(t) == len(z), 'model/training dimensions')
    require(np.isfinite(z).all() and np.isfinite(w).all() and np.isfinite(intercept) and set(t) == {-1, 1},
            'finite model and binary signed labels')
    score = z @ w + float(intercept)
    hinge = np.maximum(0, 1 - t * score)
    alpha = 2 * hinge
    residual_w = w - z.T @ (t * alpha)
    residual_b = float(intercept) - float(np.sum(t * alpha))
    primal = float(.5 * (np.dot(w, w) + intercept ** 2) + np.dot(hinge, hinge))
    gap = float(.5 * (np.dot(residual_w, residual_w) + residual_b ** 2))
    require(np.isfinite(primal) and np.isfinite(gap) and primal >= 0 and gap >= 0, 'finite objective certificate')
    return dict(primal_objective=primal, certificate_gap=gap, certificate_limit=1e-6 * (1 + primal))


def confusion(labels, predictions):
    y = np.asarray(labels); predicted = np.asarray(predictions)
    require(y.shape == predicted.shape and y.ndim == 1 and set(y) <= {0, 1} and set(predicted) <= {0, 1},
            'binary prediction support')
    tn = int(np.count_nonzero((y == 0) & (predicted == 0)))
    fp = int(np.count_nonzero((y == 0) & (predicted == 1)))
    fn = int(np.count_nonzero((y == 1) & (predicted == 0)))
    tp = int(np.count_nonzero((y == 1) & (predicted == 1)))
    closed = tn / (tn + fp) if tn + fp else None
    opened = tp / (tp + fn) if tp + fn else None
    recalls = [v for v in (closed, opened) if v is not None]
    return dict(tn=tn, fp=fp, fn=fn, tp=tp, open_recall=opened, closed_recall=closed,
                balanced_accuracy=float(np.mean(recalls)) if recalls else None)


def summarize(labels, sites, folds, predictions, method_id, n_source_rows, n_unavailable):
    labels = np.asarray(labels); sites = np.asarray(sites)
    scheme_records, per_fold = {}, []
    for scheme in ('loso', 'random10'):
        pred = np.asarray(predictions[scheme])
        require(pred.shape == labels.shape, 'complete OOF subject axis')
        fallback = np.empty(len(labels), dtype=np.int64); fold_values = []
        scheme_folds = [f for f in folds if f['scheme'] == scheme]
        for fold in scheme_folds:
            tr, te = fold['train'], fold['test']
            majority = int(np.count_nonzero(labels[tr] == 1) >= np.count_nonzero(labels[tr] == 0))
            fallback[te] = majority
            metrics = confusion(labels[te], pred[te]); fold_values.append(metrics['balanced_accuracy'])
            per_fold.append(dict(scheme=scheme, fold_id=fold['fold_id'], held_out_site=fold['held_out_site'],
                n_train=len(tr), n_test=len(te), n_train_open=int(np.sum(labels[tr] == 1)),
                n_train_closed=int(np.sum(labels[tr] == 0)), n_test_open=int(np.sum(labels[te] == 1)),
                n_test_closed=int(np.sum(labels[te] == 0)), training_majority_prediction=majority, **metrics))
        pooled = confusion(labels, pred)
        scheme_records[scheme] = dict(n_folds=len(scheme_folds),
            **{k: pooled[k] for k in ('tn', 'fp', 'fn', 'tp', 'open_recall', 'closed_recall')},
            pooled_balanced_accuracy=pooled['balanced_accuracy'], equal_fold_mean_recall=float(np.mean(fold_values)),
            training_majority_pooled_balanced_accuracy=confusion(labels, fallback)['balanced_accuracy'])
    counts = [len(set(labels[sites == site])) for site in np.unique(sites)]
    result = dict(status='ok', method_id=method_id, cv_balanced_accuracy=scheme_records['loso']['pooled_balanced_accuracy'],
        site_blocked_balanced_accuracy=scheme_records['loso']['pooled_balanced_accuracy'],
        random_kfold_balanced_accuracy=scheme_records['random10']['pooled_balanced_accuracy'],
        legacy_equal_site_mean_recall=scheme_records['loso']['equal_fold_mean_recall'],
        site_only_unseen_site_baseline=scheme_records['loso']['training_majority_pooled_balanced_accuracy'],
        always_open_pooled_balanced_accuracy=confusion(labels, np.ones(len(labels), int))['balanced_accuracy'],
        always_closed_pooled_balanced_accuracy=confusion(labels, np.zeros(len(labels), int))['balanced_accuracy'],
        n_source_rows=n_source_rows, n_unavailable_derivatives=n_unavailable, n_subjects=len(labels), n_features=19900,
        n_sites=len(counts), n_eyes_open=int(np.sum(labels == 1)), n_eyes_closed=int(np.sum(labels == 0)),
        single_class_sites=counts.count(1), mixed_class_sites=counts.count(2), chance=.5, schemes=scheme_records)
    return per_fold, result
