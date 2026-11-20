"""Scale-stable arithmetic for FIND025 contracts; NOT a paper qualification.

The caller must establish endpoint, cohort, support, preprocessing and split.
No function here establishes provenance or resolves the paper/code mismatch.
"""
from math import fsum, isfinite, sqrt, ulp


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


def _scaled(values):
    """Normalize before centering/squaring; do not alter the metric formula."""
    scale = max(abs(v) for v in values)
    return tuple(v / scale for v in values) if scale else values


def signed_variance_explained(observed, predicted):
    """1-SSE/SST with a common scale; negative scores survive.

    Scaling both vectors by the observed magnitude cancels from SSE/SST and
    avoids declaring small, nonconstant finite observations to be constant
    merely because their squares underflow. True zero-variance targets remain
    undefined. An unrepresentable prediction/target ratio remains undefined.
    """
    y, p = _pair(observed, predicted)
    scale = max(abs(v) for v in y)
    if scale == 0:
        raise UndefinedMetric("constant observed support")
    y = tuple(v / scale for v in y)
    p = tuple(v / scale for v in p)
    if not all(isfinite(v) for v in p):
        raise UndefinedMetric("nonfinite arithmetic")
    center = fsum(y) / len(y)
    denominator = fsum((v-center)**2 for v in y)
    if denominator == 0 or not isfinite(denominator):
        raise UndefinedMetric("constant observed support")
    try:
        value = 1-fsum((v-w)**2 for v, w in zip(y, p))/denominator
    except OverflowError as exc:
        raise UndefinedMetric("nonfinite arithmetic") from exc
    if not isfinite(value):
        raise UndefinedMetric("nonfinite arithmetic")
    return value


def squared_pearson_correlation(observed, predicted):
    """Squared centered correlation after independent positive rescaling.

    Positive vector scales cancel from Pearson correlation. This prevents
    square underflow for valid tiny operands, without fitting the prediction,
    dropping rows, changing supports, or replacing signed variance explained.
    """
    y, p = _pair(observed, predicted)
    y, p = _scaled(y), _scaled(p)
    ym, pm = fsum(y)/len(y), fsum(p)/len(p)
    yc, pc = tuple(v-ym for v in y), tuple(v-pm for v in p)
    yy, pp = fsum(v*v for v in yc), fsum(v*v for v in pc)
    if yy == 0 or pp == 0 or not isfinite(yy) or not isfinite(pp):
        raise UndefinedMetric("constant correlation support")
    corr = fsum(v*w for v, w in zip(yc, pc))/sqrt(yy)/sqrt(pp)
    value = corr*corr
    if not isfinite(value):
        raise UndefinedMetric("nonfinite arithmetic")
    if value > 1 + 8*ulp(1.0):
        raise UndefinedMetric("correlation arithmetic outside [0,1]")
    return min(value, 1.0)


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
