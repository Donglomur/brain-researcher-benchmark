"""Deterministic data summaries only. No model, candidate or metric execution."""
import math
from delivery_io import need

PROTOCOL = 'neural037-six-DE-observed-support-condition-native-frame-v2'
ORDERS = ('ABC', 'CBA')


def summarize(traces, np):
    need(traces.dtype.str == '<f8' and traces.ndim == 3 and traces.shape[1] == 50,
         'Original float64 cell x50trial xframe source required')
    need(not np.isinf(traces).any(), 'Infinite source values unsupported, never filled')
    valid = np.isfinite(traces)
    counts = valid.sum(axis=1, dtype=np.uint16)
    totals = np.where(valid, traces, 0.0).sum(axis=1, dtype=np.float64)
    means = np.divide(totals, counts, out=np.zeros_like(totals), where=counts > 0)
    need(np.isfinite(means).all(), 'Finite arithmetic required')
    # Keep every original row. Missing rows are explicit zero-plus-count0,
    # never fabricated measurements; a wholly absent condition blocks the panel.
    need(np.any(counts > 0), 'Entire condition unobserved; complete panel unsupported')
    return np.ascontiguousarray(means), np.ascontiguousarray(counts)


def training_scale(mean, counts, np):
    """Pooled within-cell temporal SD of the observed TRAIN condition only."""
    mask = counts > 0
    lengths = mask.sum(axis=1)
    observed = lengths > 0
    need(np.any(observed), 'Training condition has no observed ROI')
    centers = np.divide(np.where(mask, mean, 0).sum(axis=1), lengths,
                        out=np.zeros(len(lengths),dtype=np.float64), where=observed)
    variance = np.divide(np.where(mask, (mean - centers[:, None]) ** 2, 0).sum(axis=1), lengths,
                         out=np.zeros(len(lengths),dtype=np.float64), where=observed)
    scale = math.sqrt(float(variance[observed].mean()))
    need(math.isfinite(scale) and scale > 0, 'Zero/undefined training SD blocks complete panel; no epsilon or query fallback')
    return scale


def select_training(pool, query_acquisition, query_order):
    """All other source conditions; the entire queried acquisition/order is absent."""
    expected = {(f'acquisition_{i}', order) for i in range(1, 7) for order in ORDERS}
    need(type(pool) is list and len(pool) == 12 and
         {(r['acquisition'], r['order']) for r in pool} == expected,
         'Exactly twelve unique original acquisition/order conditions')
    need((query_acquisition, query_order) in expected, 'Exact withheld acquisition and order')
    selected = [r for r in pool if (r['acquisition'], r['order']) != (query_acquisition, query_order)]
    need(len(selected) == len(pool) - 1 and
         len([r for r in selected if r['acquisition'] == query_acquisition]) == 1,
         'One complete target condition withheld')
    return selected
