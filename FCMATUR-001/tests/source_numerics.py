"""Private independent original-table primitive; no source loading or fitting.

This implements the declared signed equal-edge Fisher mean from full original
time-by-column values. It does not import the oracle or public statistics
kernel. Column-wise normalization and an explicit einsum Pearson matrix form
the reconstruction route; downstream associations are deliberately absent.
"""
import math

import numpy as np

EDGE_CLIP = 0.999


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def _reject_bool(value):
    if isinstance(value, (list, tuple)):
        for child in value:
            _reject_bool(child)
    else:
        need(not isinstance(value, (bool, np.bool_)), 'Boolean source value')


def unit_column(values):
    """Anchor centering followed by stable normalization, no SD floor."""
    x = np.asarray(values, dtype=np.float64)
    if np.all(x == x[0]):
        return None
    with np.errstate(over='ignore', invalid='ignore'):
        delta = x-x[0]
    if not np.isfinite(delta).all():
        scale = float(np.max(np.abs(x)))
        delta = x/scale - x[0]/scale
    try:
        average = math.fsum(float(t) for t in delta)/len(delta)
    except OverflowError:
        scale = float(np.max(np.abs(delta)))
        delta = delta/scale
        average = math.fsum(float(t) for t in delta)/len(delta)
    with np.errstate(over='ignore', invalid='ignore'):
        centered = delta-average
    if not np.isfinite(centered).all():
        scale = float(np.max(np.abs(delta)))
        centered = delta/scale - average/scale
    magnitude = float(np.max(np.abs(centered)))
    if magnitude == 0:
        return None
    scaled = centered/magnitude
    norm = math.sqrt(math.fsum(float(t)*float(t) for t in scaled))
    need(math.isfinite(norm) and norm > 0, 'source normalization failure')
    return scaled/norm


def connectivity(time_by_column):
    _reject_bool(time_by_column)
    raw = np.asarray(time_by_column)
    need(raw.ndim == 2 and raw.dtype.kind in 'iuf', 'source matrix type')
    values = np.asarray(raw, dtype=np.float64, order='C')
    need(values.shape[0] >= 2 and values.shape[1] >= 1, 'source matrix shape')
    need(bool(np.isfinite(values).all()), 'source matrix nonfinite')
    active, vectors = [], []
    for column in values.T:
        vector = unit_column(column)
        active.append(vector is not None)
        if vector is not None:
            vectors.append(vector)
    k = len(vectors)
    result = dict(n_frames=values.shape[0], n_columns=values.shape[1], active_columns=active,
                  n_active_columns=k, n_edges=k*(k-1)//2, connectivity=None,
                  status='insufficient_active_columns')
    if k < 2:
        return result
    normalized = np.ascontiguousarray(np.stack(vectors, axis=1), dtype=np.float64)
    correlations = np.einsum('ti,tj->ij', normalized, normalized, optimize=False)
    edges = correlations[np.triu_indices(k, 1)]
    need(bool(np.isfinite(edges).all()) and float(np.max(np.abs(edges))) <= 1+64*np.finfo(float).eps,
         'source correlation domain')
    transformed = np.arctanh(np.clip(edges, -EDGE_CLIP, EDGE_CLIP))
    mean = math.fsum(float(z) for z in transformed)/len(transformed)
    need(math.isfinite(mean), 'source connectivity nonfinite')
    result.update(status='ok', connectivity=mean)
    return result
