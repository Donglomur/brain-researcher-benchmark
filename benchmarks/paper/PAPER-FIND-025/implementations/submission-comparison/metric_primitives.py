"""Independent arithmetic for FIND025 contracts; NOT a paper scorer or executor.

The caller must establish endpoint, cohort, support, preprocessing and split.
No function here establishes provenance or resolves the paper/code mismatch.
"""
from math import fsum, isfinite, sqrt


class UndefinedMetric(ValueError):
    pass


def _values(values):
    result = tuple(values)
    if not result or any(type(x) not in (int, float) or not isfinite(x) for x in result):
        raise ValueError("nonempty finite numeric values required")
    return result


def _pair(observed, predicted):
    observed, predicted = _values(observed), _values(predicted)
    if len(observed) != len(predicted):
        raise ValueError("support lengths differ")
    return observed, predicted


def signed_variance_explained(observed, predicted):
    """1-SSE/SST on one explicitly declared support. Negative scores survive."""
    y, p = _pair(observed, predicted)
    center = fsum(y) / len(y)
    denominator = fsum((v-center)**2 for v in y)
    if denominator == 0 or not isfinite(denominator):
        raise UndefinedMetric("constant observed support")
    value = 1-fsum((v-w)**2 for v, w in zip(y, p))/denominator
    if not isfinite(value):
        raise UndefinedMetric("nonfinite arithmetic")
    return value


def squared_pearson_correlation(observed, predicted):
    """Squared centered correlation, distinct from signed variance explained."""
    y, p = _pair(observed, predicted)
    ym, pm = fsum(y)/len(y), fsum(p)/len(p)
    yc, pc = tuple(v-ym for v in y), tuple(v-pm for v in p)
    yy, pp = fsum(v*v for v in yc), fsum(v*v for v in pc)
    if yy == 0 or pp == 0 or not isfinite(yy) or not isfinite(pp):
        raise UndefinedMetric("constant correlation support")
    corr = fsum(v*w for v, w in zip(yc, pc))/sqrt(yy)/sqrt(pp)
    value = corr*corr
    if not isfinite(value):
        raise UndefinedMetric("nonfinite arithmetic")
    return value


def binary_accuracy(observed, predicted):
    """Fraction correct on explicit -1/+1 label predictions; no pooled sessions."""
    y, p = _pair(observed, predicted)
    if any(v not in (-1, 1) for v in y+p):
        raise ValueError("explicit -1/+1 classes required")
    return sum(v == w for v, w in zip(y, p))/len(y)


def first_strict_90pct_latency(times, trace, delay_onset):
    """First t with trace(t)>0.9*max(trace), minus delay onset.

    Caller supplies the already filtered, correctly oriented pre-go trace and
    exact time window. This function does not fit, smooth, orient or select it.
    """
    t, y = _pair(times, trace)
    if any(a >= b for a, b in zip(t, t[1:])):
        raise ValueError("times must strictly increase")
    delay_onset = _values((delay_onset,))[0]
    threshold = 0.9*max(y)
    for time, value in zip(t, y):
        if value > threshold:
            latency = time-delay_onset
            if not isfinite(latency):
                raise UndefinedMetric("nonfinite latency")
            return latency
    raise UndefinedMetric("no strict threshold crossing")
