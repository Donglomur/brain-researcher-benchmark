"""Original C1--D1 requests, pooled predictions and full source-shaped outputs.

No model is fitted on import. Reference fitting is an explicit later operation;
construction controls use deterministic callbacks. A Python callback boundary
is not an OS sandbox and cannot authenticate withheld-data custody by itself.
"""
from __future__ import annotations

import hashlib
import random
import numpy as np

from inputs import FAMILIES, need


def smooth_targets(fr):
    need(fr.ndim == 2 and len(fr) > 20 and fr.dtype == np.float64
         and np.isfinite(fr).all(), 'Source float64 neural time by unit array')
    # C1 averages units before smoothing; D1 smooths each unit separately.
    population = fr.mean(axis=1)
    cp = np.cumsum(np.insert(population, 0, 0))
    p = np.concatenate(([0.], (cp[3:] - cp[:-3]) / 3., [0.]))[:, None]
    cu = np.cumsum(np.vstack((np.zeros((1, fr.shape[1])), fr)), axis=0)
    u = np.vstack((np.zeros((1, fr.shape[1])), (cu[3:] - cu[:-3]) / 3., np.zeros((1, fr.shape[1]))))
    need(np.isfinite(p).all() and np.isfinite(u).all(), 'Source smoothing overflow')
    return p, u


def format_words(timing, qid, features, time_bins):
    need(timing.shape == (len(qid), 2) and features.ndim == 2
         and features.shape[0] == len(qid) and len(qid) > 0
         and features.dtype == np.float64 and np.isfinite(features).all(),
         'Complete ordered source words/features required')
    need(np.isfinite(timing).all() and np.isfinite(qid).all()
         and np.all(qid == np.floor(qid)) and np.all(np.abs(qid) < 2**53)
         and np.all(timing >= 0) and np.all(timing[:, 1] >= timing[:, 0])
         and np.all(timing < (time_bins + 1) / 10)
         and np.all((timing * 10).astype(np.int64) <= time_bins), 'Invalid source timing/qid')
    # Source format_conti computes a separate mean for each column.
    continuous = np.empty((time_bins, features.shape[1]), dtype=np.float64)
    for column in range(features.shape[1]):
        continuous[:, column] = features[:, column].mean()
    labels = np.full(time_bins, 99999., dtype=np.float64)
    for (start, end), label, row in zip((timing * 10).astype(np.int64), qid, features):
        continuous[start:end] = row
        if label < 99990:
            labels[start:end] = label
    return continuous, labels


def sentence_swap_indices(qid):
    """Source sorted groupby, equal-length random choices, not a permutation."""
    groups = {label: np.flatnonzero(qid == label) for label in np.unique(qid)}
    rng = random.Random(20)
    indices = []
    for label, original in groups.items():
        others = [other for other, rows in groups.items()
                  if other != label and len(rows) == len(original)]
        indices.extend(groups[rng.choice(others)] if others else original)
    return np.asarray(indices, dtype=np.int64)


def lag_rows(targets, continuous, speaker, labels, lag):
    need(type(lag) is int and abs(lag) < len(targets)
         and len(targets) == len(continuous) == len(speaker) == len(labels),
         'Exact aligned source lag operands')
    if lag < 0:
        y = np.vstack((np.zeros((-lag, targets.shape[1])), targets))[:lag]
        x, q = continuous, labels
    elif lag > 0:
        y = targets
        x = np.vstack((np.zeros((lag, continuous.shape[1])), continuous))[:-lag]
        q = np.concatenate((np.zeros(lag), labels))[:-lag]
    else:
        y, x, q = targets, continuous, labels
    support = (speaker == 1) & (q < 99990)
    indices = np.flatnonzero(support)
    return x[support], y[support], q[support], indices


def iter_jobs(session):
    """Yield all4209 original session field/layer/lag jobs, in source order."""
    p, units = smooth_targets(session['fr'])
    speaker = session['speaker'][:, 0]
    specs = [('population', 'context', p, range(-20, 20), False, False),
             ('unit', 'context', units, range(-20, 20), False, False),
             ('time_shuffle', 'context', p, range(-20, 20), True, False),
             ('random_token', 'random_token', p, (-10,), False, False),
             ('sentence_swap', 'context', p, (-10,), False, True)]
    specs += [(f, f, p, (-10,), False, False) for f in FAMILIES if f.startswith('ngram')]
    specs += [(f + suffix, f, p, (-3, -2, -1), bool(suffix), False)
              for f in ('sem_syn', 'word2vec', 'syn') for suffix in ('', '_shuffle')]
    for field, family, target, lags, shuffle, swap in specs:
        feature = session[family]
        timing, qid = session['timing'], session['qid']
        expected_layers = 1 if family in ('sem_syn', 'word2vec', 'syn') else 33
        need(feature.shape == (len(qid), 30, expected_layers) and feature.dtype == np.float64,
             'Original supplied PCA feature layout required; no PCA refit')
        if family in ('sem_syn', 'word2vec'):
            keep = ~np.isnan(feature[:, 0, 0])
            feature, timing, qid = feature[keep], timing[keep], qid[keep]
        need(len(feature) > 0 and np.isfinite(feature).all(), 'Finite retained feature rows required')
        if swap:
            feature = feature[sentence_swap_indices(qid)]
        if shuffle:
            # Each source shuffled script resets legacy NumPy seed20 per session.
            target = np.random.RandomState(20).permutation(target)
        for layer in range(expected_layers):
            x, q = format_words(timing, qid, feature[:, :, layer], len(target))
            for lag_index, lag in enumerate(lags):
                xx, yy, qq, indices = lag_rows(target, x, speaker, q, int(lag))
                yield {'session': session['session'], 'field': field, 'family': family,
                       'layer': layer, 'lag_index': lag_index, 'lag_bins': int(lag),
                       'x': xx, 'y': yy, 'qid': qq, 'time_indices': indices}


def pooled_pearson(target, prediction):
    need(target.shape == prediction.shape and target.ndim == 2 and len(target) >= 2
         and np.isfinite(target).all() and np.isfinite(prediction).all(),
         'Complete finite paired predictions')
    # Exact source operation. Constant predictions/targets remain undefined NaN.
    with np.errstate(divide='ignore', invalid='ignore'):
        values = np.array([np.corrcoef(prediction[:, i], target[:, i])[1, 0]
                           for i in range(target.shape[1])])
    need(not np.isinf(values).any(), 'Invalid source correlation')
    return values


def predict_job(job, predictor, *, remaining_requests, sink):
    """Every held-qid request contains training targets, never query targets."""
    x, y, q = job['x'], job['y'], job['qid']
    labels = np.unique(q)
    need(len(labels) >= 2 and np.isfinite(x).all() and np.isfinite(y).all(),
         'At least two finite sentence groups are required')
    need(type(remaining_requests) is int and len(labels) <= remaining_requests,
         'Prediction request allocation exhausted before job')
    predictions = np.full(y.shape, np.nan)
    fold_receipts = []
    for label in labels:
        test = np.flatnonzero(q == label)
        train = np.flatnonzero(q != label)
        context = {k: job[k] for k in ('session', 'field', 'family', 'layer', 'lag_index', 'lag_bins')}
        context.update({'held_qid': float(label), 'train_time_indices': job['time_indices'][train].copy(),
                        'test_time_indices': job['time_indices'][test].copy(),
                        'train_qid': q[train].copy()})
        # Copies prevent callback mutation of operator targets/other folds.
        predicted = np.asarray(predictor(x[train].copy(), y[train].copy(), x[test].copy(), context))
        need(predicted.shape == (len(test), y.shape[1]) and predicted.dtype.kind == 'f'
             and np.isfinite(predicted).all(), 'Missing, malformed or nonfinite held-qid predictions')
        predictions[test] = predicted
        fold_receipts.append({'held_qid': float(label), 'training_rows': len(train),
                              'query_rows': len(test), 'test_time_indices': context['test_time_indices'].tolist()})
    correlations = pooled_pearson(y, predictions)
    # The operator sink sees targets for audit; it is distinct from the predictor.
    sink({**{k: job[k] for k in ('session', 'field', 'family', 'layer', 'lag_index', 'lag_bins')},
          'qid': q.copy(), 'time_indices': job['time_indices'].copy(),
          'predictions': predictions.copy(), 'targets': y.copy(),
          'folds': fold_receipts, 'correlations': correlations.copy()})
    return correlations, len(labels)


def compute_session(session, predictor, *, max_requests, sink):
    """All16 result fields; no favorable layer/time selection or partial output."""
    need(callable(predictor) and callable(sink) and type(max_requests) is int and max_requests > 0,
         'Explicit predictor, observation sink and request allocation required')
    units = session['fr'].shape[1]
    result = {'population': np.full((40, 33), np.nan), 'unit': np.full((units, 40, 33), np.nan),
              'time_shuffle': np.full((40, 33), np.nan),
              **{f: np.full(33, np.nan) for f in ('random_token', 'sentence_swap', 'ngram1', 'ngram3', 'ngram5', 'ngram7', 'ngram10')},
              **{f + s: np.full((3, 1), np.nan) for f in ('sem_syn', 'word2vec', 'syn') for s in ('', '_shuffle')}}
    count, requests, trace = 0, 0, hashlib.sha256()
    for job in iter_jobs(session):
        values, used = predict_job(job, predictor, remaining_requests=max_requests - requests, sink=sink)
        field, lag_index, layer = job['field'], job['lag_index'], job['layer']
        if field == 'unit':
            result[field][:, lag_index, layer] = values
        elif result[field].ndim == 1:
            result[field][layer] = values[0]
        else:
            result[field][lag_index, layer] = values[0]
        trace.update(f'{field}:{lag_index}:{layer}:{used}\n'.encode())
        trace.update(np.asarray(job['time_indices'], dtype='<i8').tobytes())
        count += 1; requests += used
    need(count == 4209, 'Incomplete original job lattice')
    return result, {'jobs': count, 'sentence_prediction_requests': requests,
                    'ordered_support_trace_sha256': trace.hexdigest(),
                    'source_input_receipts': session['input_receipts'],
                    'scientific_qualification': False}


def source_ridge_predictor():
    """Explicit original reference adapter; refuses a different installed stack."""
    import sklearn
    import scipy
    need(np.__version__ == '1.24.3' and sklearn.__version__ == '1.2.2'
         and scipy.__version__ == '1.10.1', 'Historical source numerical stack required')
    from sklearn.linear_model import Ridge

    def predict(train_x, train_y, query_x, context):
        estimator = Ridge(alpha=0.01)
        estimator.fit(train_x, train_y)
        return estimator.predict(query_x)
    return predict
