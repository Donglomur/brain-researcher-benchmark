"""Exact class-neutral093 metric kernels, reused for094 final-choice probabilities.

No old093 class labels, predictions, five-view model panel or bootstrap is reused.
NumPy is an explicit future isolated-grader dependency; no empirical I/O here.
"""
import math
SUM_TOLERANCE = 1e-8

def need(ok, label):
    if not ok:
        raise ValueError(label)

def extended(value):
    value = float(value)
    if math.isnan(value):
        return {'status': 'undefined', 'value': None}
    if math.isinf(value):
        return {'status': 'positive_infinity' if value > 0 else 'negative_infinity', 'value': None}
    return {'status': 'finite', 'value': value}

def number(record):
    need(type(record) is dict and set(record) == {'status', 'value'}, 'Exact extended number')
    if record['status'] == 'finite':
        need(type(record['value']) in (int, float) and math.isfinite(record['value']), 'Finite scalar')
        return float(record['value'])
    need(record['value'] is None, 'Nonfinite scalar has no JSON number')
    if record['status'] == 'positive_infinity':
        return math.inf
    if record['status'] == 'negative_infinity':
        return -math.inf
    need(record['status'] == 'undefined', 'Known extended scalar status')
    return math.nan

def probabilities(values, np):
    p = np.asarray(values)
    need(p.ndim == 2 and p.shape[1] == 3 and p.shape[0] > 0 and p.dtype.kind == 'f',
         'Nonempty three-column floating probabilities')
    need(bool(np.isfinite(p).all()) and bool(((p >= 0) & (p <= 1)).all()),
         'Finite probabilities in closed unit interval')
    p = np.array(p, dtype=np.float64, order='C', copy=True)
    sums = p.sum(axis=1)
    need(bool((np.abs(sums - 1) <= SUM_TOLERANCE).all()), 'Probability sum within fixed tolerance')
    p /= sums[:, None]
    return p

def mean_log_loss(p, y, np):
    need(p.shape == (len(y), 3) and len(y) > 0, 'Full paired loss support')
    chosen = p[np.arange(len(y)), y]
    zero = chosen == 0
    if bool(zero.any()):
        return math.inf
    return float(-np.log(chosen).mean())

