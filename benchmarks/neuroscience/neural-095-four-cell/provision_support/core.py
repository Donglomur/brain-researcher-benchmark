"""Conversion-only closure extracted verbatim from the accepted authored core."""
import numpy as np

PUBLIC_KEYS = {'case_id', 'counts', 'condition', 'context', 'nominal_ts_ms', 'clock_seconds'}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def conditions(short, eye, theta, ts):
    short, eye, theta, ts = map(np.asarray, (short, eye, theta, ts))
    require(short.ndim == 1 and all(a.shape == short.shape for a in (eye, theta, ts)), 'parallel cues')
    require(short.dtype.kind == eye.dtype.kind == 'b', 'boolean source prior/effector')
    require(np.isfinite(ts).all() and np.isin(theta, [0, 180]).all(), 'finite exact cue levels')
    context = short.astype(np.int64) * 4 + eye.astype(np.int64) * 2 + (theta == 180)
    condition = np.empty(len(ts), dtype=np.int64)
    for i in range(len(ts)):
        levels = [480., 560., 640., 720., 800.] if short[i] else [800., 900., 1000., 1100., 1200.]
        require(float(ts[i]) in levels, 'unknown nominal interval for source prior')
        condition[i] = int(context[i]) * 5 + levels.index(float(ts[i]))
    return condition, context


def support_gate(start, stop, ready, anchor, observation_intervals):
    """All-or-nothing preflight. Never touches spike arrays or outcome values."""
    start, stop, ready, anchor = map(lambda a: np.asarray(a, dtype=np.float64), (start, stop, ready, anchor))
    require(anchor.ndim == 1 and len(anchor) > 0 and all(a.shape == anchor.shape for a in (start, stop, ready)), 'parallel trial clocks')
    require(all(np.isfinite(a).all() for a in (start, stop, ready, anchor)), 'finite selected clocks')
    left = anchor - .2
    require(np.all(left >= start) and np.all(anchor <= stop), 'window inside own trial')
    require(np.all(left >= ready), 'window begins at or after Ready')
    order = np.argsort(left, kind='stable')
    require(np.all(left[order][1:] >= anchor[order][:-1]), 'selected windows mutually nonoverlapping')
    require(len(observation_intervals) > 0, 'unit observation support required')
    for spans in observation_intervals:
        spans = np.asarray(spans, dtype=np.float64)
        require(spans.ndim == 2 and spans.shape[1] == 2 and len(spans) > 0, 'unit support schema')
        require(np.isfinite(spans).all() and np.all(spans[:, 1] > spans[:, 0]), 'positive finite observation intervals')
        require(np.all(spans[1:, 0] >= spans[:-1, 1]), 'ordered nonoverlapping observation intervals')
        covered = np.any((left[:, None] >= spans[:, 0]) & (anchor[:, None] <= spans[:, 1]), axis=1)
        require(covered.all(), 'every selected window covered by every selected unit')
    return left


def bin_spikes(spikes, anchor):
    spikes, anchor = np.asarray(spikes), np.asarray(anchor, dtype=np.float64)
    require(spikes.ndim == 1 and spikes.dtype.kind == 'f' and np.isfinite(spikes).all(), 'finite spike vector')
    require(np.all(spikes[1:] >= spikes[:-1]), 'monotonic spike timestamps')
    # Construct the Set endpoint directly, with left-search at both ends.
    edges = anchor[:, None] + np.array([-.2, -.15, -.1, -.05, 0.], dtype=np.float64)
    positions = np.searchsorted(spikes, edges, side='left')
    counts = np.diff(positions, axis=1)
    require(np.all(counts >= 0) and np.all(counts <= np.iinfo(np.uint32).max), 'safe unsigned counts')
    require(np.array_equal(counts.sum(axis=1), positions[:, -1] - positions[:, 0]), 'count conservation')
    return counts.astype(np.uint32)


def validate_packet(packet, training=False):
    keys = PUBLIC_KEYS | ({'tp_ms', 'fold'} if training else set())
    require(set(packet) == keys, 'exact public packet allowlist')
    ids = packet['case_id']; n = len(ids)
    require(ids.ndim == 1 and ids.dtype.kind == 'U' and n > 0 and len(set(ids.tolist())) == n, 'unique Unicode case IDs')
    require(all(isinstance(x, str) and x.startswith('dmfc-') and len(x) == 11 and x[5:].isdigit() for x in ids.tolist()), 'canonical case IDs')
    counts = packet['counts']
    require(counts.shape == (n, 4, 40) and counts.dtype == np.dtype('uint32'), 'four bins by all40 held-in units')
    for field, size in [('condition', 40), ('context', 8)]:
        a = packet[field]
        require(a.shape == (n,) and a.dtype.kind in 'iu' and np.all((a >= 0) & (a < size)), 'valid ' + field)
    require(np.array_equal(packet['condition'] // 5, packet['context']), 'condition/context agreement')
    for field in ('nominal_ts_ms', 'clock_seconds'):
        a = packet[field]
        require(a.shape == (n,) and a.dtype.kind == 'f' and np.isfinite(a).all(), 'finite ' + field)
    nominal = np.array(([800, 900, 1000, 1100, 1200] * 4) + ([480, 560, 640, 720, 800] * 4))
    require(np.array_equal(packet['nominal_ts_ms'], nominal[packet['condition']]), 'condition and nominal interval agree')
    require(np.all(packet['clock_seconds'] >= 0), 'nonnegative elapsed observation clock')
    if training:
        y, fold = packet['tp_ms'], packet['fold']
        require(y.shape == (n,) and y.dtype.kind == 'f' and np.isfinite(y).all() and np.all(y > 0), 'all training targets positive finite; no filtering')
        require(fold.shape == (n,) and fold.dtype.kind in 'iu' and set(fold.tolist()) == set(range(5)), 'five fixed folds')
        require(set(packet['condition'].tolist()) == set(range(40)), 'all40 conditions in full training')
    return n
