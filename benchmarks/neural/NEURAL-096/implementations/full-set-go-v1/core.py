"""Full observed Set–Go intervals, without fitting or biological inference."""
from fractions import Fraction
import math
import numpy as np


class ContractError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ContractError(message)


def real_scalar(value):
    require(isinstance(value, (float, np.floating)) and not isinstance(value, (bool, np.bool_)),
            "clock values must be floating point seconds")
    require(not isinstance(value, np.floating) or value.dtype.itemsize <= 8,
            "clock values wider than binary64 are unsupported")
    number = float(value)
    require(math.isfinite(number), "clock value is nonfinite")
    return number


def phase_edges(start, stop, bins=20):
    start, stop = real_scalar(start), real_scalar(stop)
    require(type(bins) is int and 1 <= bins <= 1024, "invalid phase-bin count")
    require(stop > start, "Set–Go duration must be positive")
    left, right = Fraction(start), Fraction(stop)
    edges = np.asarray([float(left + (right-left)*i/bins) for i in range(bins+1)], dtype='<f8')
    require(bool(np.isfinite(edges).all()) and bool((edges[1:] > edges[:-1]).all()),
            "phase edges cannot be represented distinctly")
    with np.errstate(over='ignore', invalid='ignore', under='ignore'):
        exposure = edges[1:] - edges[:-1]
    require(bool(np.isfinite(exposure).all()) and bool((exposure > 0).all()),
            "phase exposures cannot be represented")
    return edges


def observed_union(intervals):
    values = np.asarray(intervals)
    require(values.ndim == 2 and values.shape[1] == 2 and values.shape[0] > 0
            and values.dtype.kind == 'f' and values.dtype.itemsize <= 8,
            "observation intervals must be a nonempty floating Nx2 array")
    values = values.astype(np.float64)
    require(bool(np.isfinite(values).all()) and bool((values[:,1] > values[:,0]).all()),
            "invalid observation interval")
    result = []
    for left, right in sorted(map(tuple, values.tolist())):
        if result and left <= result[-1][1]:
            result[-1] = (result[-1][0], max(right, result[-1][1]))
        else:
            result.append((left, right))
    return result


def containing_segment(start, stop, intervals):
    start, stop = real_scalar(start), real_scalar(stop)
    require(stop > start, "Set–Go duration must be positive")
    merged = observed_union(intervals)
    matches = [i for i,(left,right) in enumerate(merged) if left <= start and stop <= right]
    require(len(matches) == 1, "complete Set–Go interval is not observed")
    return matches[0]


def count_phase_spikes(spikes, edges):
    spikes, edges = np.asarray(spikes), np.asarray(edges)
    require(spikes.ndim == 1 and spikes.dtype.kind == 'f' and spikes.dtype.itemsize <= 8,
            "spikes must be a one-dimensional floating time vector")
    require(edges.ndim == 1 and len(edges) >= 2 and edges.dtype.kind == 'f'
            and edges.dtype.itemsize <= 8, "invalid time edges")
    require(bool(np.isfinite(spikes).all()) and bool((spikes[1:] >= spikes[:-1]).all()),
            "spike times must be finite and sorted")
    require(bool(np.isfinite(edges).all()) and bool((edges[1:] > edges[:-1]).all()),
            "time edges must be finite and increasing")
    positions = np.searchsorted(spikes, edges, side='left')
    counts = np.diff(positions)
    require(bool((counts >= 0).all()) and bool((counts <= np.iinfo(np.uint32).max).all()),
            "spike counts cannot be represented")
    require(int(counts.sum()) == int(positions[-1]-positions[0]), "count conservation failed")
    return counts.astype('<u4')


def matched_support(rows, segments):
    require(type(segments) is int and segments > 0, "invalid temporal segment count")
    counts = np.zeros((segments, 2, 2, 2), dtype=np.int64)
    for row in rows:
        segment = row['observation_segment']
        require(type(segment) is int and 0 <= segment < segments, "unknown observation segment")
        require(type(row['is_eye']) is bool and type(row['is_short']) is bool
                and isinstance(row['theta'], (int, float, np.integer, np.floating))
                and not isinstance(row['theta'], (bool, np.bool_))
                and row['theta'] in (0, 180), "invalid cue identity")
        counts[segment, int(row['is_eye']), int(row['theta'] == 180), int(row['is_short'])] += 1
    return {
        'axes': ['observation_segment', 'is_eye', 'theta', 'is_short'],
        'levels': {'is_eye':[False,True], 'theta':[0,180], 'is_short':[False,True]},
        'counts': counts.tolist(),
        'zero_cells': np.argwhere(counts == 0).tolist(),
        'all_cells_present': bool((counts > 0).all()),
        'interpretation': 'Recording observation segments, not certified randomized assignment blocks.'
    }
