"""Complete behavioral and waveform descriptors, with deferred NumPy import."""
import math
from .protocol import require, feature_order


def np_module():
    import numpy as np
    return np


def geometry(value, budget=None):
    # Inspect shape without constructing an O(number_of_scalars) shape list.
    # A bounded scalar walk precedes conversion/allocation; never call __array__.
    seen = 0
    cap = budget.profile['max_input_elements'] - budget.used['input_elements'] if budget is not None else 1000000
    def walk(item, depth):
        nonlocal seen
        require(depth <= 8, 'numeric_nesting_depth')
        if type(item) in (list, tuple):
            require(len(item) > 0, 'empty_numeric_array')
            if len(item) > cap:
                from .protocol import Refusal
                raise Refusal('resource_input_elements', budget.snapshot() if budget else {})
            first = walk(item[0], depth + 1)
            for index in range(1, len(item)):
                require(walk(item[index], depth + 1) == first, 'ragged_numeric_array')
            return (len(item),) + first
        if type(item) in (int, float):
            seen += 1
            if seen > cap:
                from .protocol import Refusal
                raise Refusal('resource_input_elements', budget.snapshot() if budget else {})
            require(math.isfinite(item), 'nonfinite_numeric_scalar')
            if budget is not None and seen % 1024 == 0:
                budget.tick()
            return ()
        np = np_module()
        require(type(item) is np.ndarray and item.dtype.kind in 'fiu' and item.dtype.itemsize <= 8, 'numeric_array_type')
        shape = tuple(int(n) for n in item.shape)
        require(all(n > 0 for n in shape), 'empty_numeric_array')
        seen += math.prod(shape)
        if seen > cap:
            from .protocol import Refusal
            raise Refusal('resource_input_elements', budget.snapshot() if budget else {})
        return shape
    if budget is not None:
        budget.tick()
    result = walk(value, 0)
    if budget is not None:
        budget.tick()
    return result


def array(value, budget, ndim=None):
    shape = geometry(value, budget)
    require(ndim is None or len(shape) == ndim, 'numeric_array_rank')
    n = math.prod(shape)
    budget.stage(elements=n, live=32 * n, work=n)
    np = np_module()
    out = np.asarray(value, dtype=np.float64)
    require(bool(np.isfinite(out).all()), 'nonfinite_numeric_array')
    budget.tick()
    return out


def behavior_features(rt_seconds, instruction, budget):
    np = np_module()
    r = array(rt_seconds, budget, 1)
    a = array(instruction, budget, 1)
    require(r.shape == a.shape and bool((r > 0).all()) and bool(((a == 0) | (a == 1)).all()), 'behavior_support')
    n = len(r)
    budget.stage(live=8 * n * 150, work=n * 160)
    u = np.log(r)
    q = np.linspace(math.log(0.1), math.log(3.0), 32)
    width = 2 * (math.log(3.0) - math.log(0.1)) / 31
    with np.errstate(over='raise', invalid='raise', divide='raise', under='ignore'):
        b = np.exp(-0.5 * ((u[:, None] - q) / width) ** 2)
        result = np.column_stack((np.ones(n), a, u, a * u, u * u, a * u * u, b, a[:, None] * b))
    require(result.shape == (n, 70) and bool(np.isfinite(result).all()), 'behavior_output')
    budget.tick()
    return result


def waveform_features(waveforms, channel_order, budget):
    np = np_module()
    feature_order('G', channel_order)
    require(type(waveforms) in (list, tuple) and len(waveforms) > 0, 'waveform_trial_list')
    ntrial = len(waveforms)
    budget.stage(live=ntrial * 1040 * 8, work=ntrial * 1040)
    G = np.empty((ntrial, 512), dtype=np.float64)
    C = np.empty((ntrial, 528), dtype=np.float64)
    upper = np.triu_indices(32)
    for i, value in enumerate(waveforms):
        shape = geometry(value, budget)
        require(len(shape) == 2 and shape[0] == 32 and shape[1] >= 8, 'waveform_shape')
        count = shape[1]
        budget.stage(live=8 * (ntrial * 1040 + 5 * 32 * count + 1024), work=32 * 32 * count + 32 * count * 10)
        x = array(value, budget, 2)
        with np.errstate(over='raise', invalid='raise', divide='raise', under='ignore'):
            bins = np.arange(count, dtype=np.int64) * 8 // count
            block = np.empty((32, 8, 2), dtype=np.float64)
            for j in range(8):
                part = x[:, bins == j]
                require(part.shape[1] > 0, 'empty_relative_bin')
                block[:, j, 0] = part.mean(axis=1)
                block[:, j, 1] = part.std(axis=1, ddof=0)
            centered = x - x.mean(axis=1, keepdims=True)
            cov = centered @ centered.T / count
            G[i] = block.reshape(512)
            C[i] = cov[upper]
        require(bool(np.isfinite(G[i]).all()) and bool(np.isfinite(C[i]).all()), 'waveform_feature_nonfinite')
        budget.tick()
    return G, C


def build_features(behavior, G, C, instruction, family, budget):
    np = np_module()
    b = array(behavior, budget, 2)
    a = array(instruction, budget, 1)
    require(b.shape == (len(a), 70) and bool((b[:, 0] == 1).all()) and bool((b[:, 1] == a).all()), 'feature_behavior_join')
    require(family in ('B', 'G', 'C', 'GC'), 'feature_family')
    if family == 'B':
        return b
    pieces = []
    if family in ('G', 'GC'):
        g = array(G, budget, 2)
        require(g.shape == (len(a), 512), 'G_shape')
        pieces.append(g)
    if family in ('C', 'GC'):
        c = array(C, budget, 2)
        require(c.shape == (len(a), 528), 'C_shape')
        pieces.append(c)
    width = 70 + 2 * sum(x.shape[1] for x in pieces)
    budget.stage(live=8 * len(a) * width * 3, work=len(a) * width)
    result = np.column_stack([b] + pieces + [a[:, None] * x for x in pieces])
    require(bool(np.isfinite(result).all()), 'feature_nonfinite')
    budget.tick()
    return result
