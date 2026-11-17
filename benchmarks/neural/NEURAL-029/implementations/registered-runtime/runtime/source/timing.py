"""Fixed source-only timing comparator; NumPy is supplied by an authorized caller."""
import math


def source_times(query_times):
    """Inverse author-derived warp, with the postreward branch at exactly t=2."""
    if (type(query_times) is not list or not query_times or
            any(type(t) not in (int, float) or not math.isfinite(t) or not 0 <= t <= 3
                for t in query_times)):
        raise ValueError('finite query times within 0..3 seconds')
    return [t / 2 if t < 2 else t - 1 for t in query_times]


def fixed_warp_mean(mean_source, source_time, query_time, np):
    """Interpolate the all-public-trial mean on exactly the candidate-visible grid.

    No target responses, target outcomes, actual reward times, fitted parameters,
    extrapolation, clamping or negative-time additive comparator are used.
    """
    mapped = source_times(query_time)
    if (type(source_time) is not list or len(source_time) < 2 or
            any(type(t) not in (int, float) or not math.isfinite(t) for t in source_time) or
            any(a >= b for a, b in zip(source_time, source_time[1:])) or
            min(mapped) < source_time[0] or max(mapped) > source_time[-1] or
            mean_source.ndim != 2 or mean_source.shape[1] != len(source_time) or
            not np.isfinite(mean_source).all()):
        raise ValueError('finite mean trajectory and exact interpolation support; no extrapolation')
    out = np.empty((mean_source.shape[0], len(mapped)), dtype=np.float64)
    for cell in range(mean_source.shape[0]):
        out[cell] = np.interp(mapped, source_time, mean_source[cell])
    if not np.isfinite(out).all():
        raise ValueError('representable fixed-warp mean')
    return out
