"""Independent numerical endpoints for the Jaxley paper benchmark.

Only declared mathematics lives here. This module does not read data, invoke a
simulator, choose a historical protocol, or certify scientific results.
"""

import math


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("expected a finite real number, excluding bool")
    try:
        result = float(value)
    except (ValueError, OverflowError) as exc:
        raise ValueError("number is outside finite binary64 range") from exc
    if not math.isfinite(result):
        raise ValueError("nonfinite number")
    return result


def _sequence(value, *, empty=False):
    if not isinstance(value, (list, tuple)) or (not empty and not value):
        raise ValueError("expected a nonempty list or tuple")
    return list(value)


def _vector(value, *, empty=False):
    return [_number(x) for x in _sequence(value, empty=empty)]


def _integer(value, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("expected an integer, excluding bool")
    if value < (1 if positive else 0):
        raise ValueError("integer outside permitted range")
    return value


def _paired(first, second, *, empty=False):
    a, b = _vector(first, empty=empty), _vector(second, empty=empty)
    if len(a) != len(b):
        raise ValueError("vector lengths differ")
    return a, b


def _sum(values):
    try:
        result = math.fsum(values)
    except (ValueError, OverflowError) as exc:
        raise ValueError("sum outside finite numeric range") from exc
    return _number(result)


def _mean(values):
    scale = max(abs(x) for x in values)
    if scale == 0.0:
        return 0.0
    return _number(scale * (_sum(x / scale for x in values) / len(values)))


def _scalar(value):
    return {"defined": True, "value": _number(value)}


def _undefined(reason):
    return {"defined": False, "reason": reason}


def _matrix(value):
    rows = [_vector(row) for row in _sequence(value)]
    if any(len(row) != len(rows[0]) for row in rows):
        raise ValueError("ragged matrix")
    return rows


def paired_errors(observed, predicted):
    observed, predicted = _paired(observed, predicted)
    differences = [_number(a - b) for a, b in zip(observed, predicted)]
    squares = [_number(d * d) for d in differences]
    return {"mae": _mean([abs(d) for d in differences]),
            "mse": _mean(squares), "count": len(differences)}


def pearson(observed, predicted):
    observed, predicted = _paired(observed, predicted, empty=True)
    if len(observed) < 2:
        return _undefined("insufficient_observations")
    if min(observed) == max(observed) or min(predicted) == max(predicted):
        return _undefined("constant_vector")
    # Independent positive rescaling avoids overflow when centering or squaring.
    xscale, yscale = max(map(abs, observed)), max(map(abs, predicted))
    xs, ys = [x / xscale for x in observed], [y / yscale for y in predicted]
    xm, ym = _mean(xs), _mean(ys)
    dx, dy = [x - xm for x in xs], [y - ym for y in ys]
    xx, yy = _sum(x * x for x in dx), _sum(y * y for y in dy)
    if xx == 0 or yy == 0:
        return _undefined("unresolvable_variation")
    value = (_sum(x * y for x, y in zip(dx, dy)) / math.sqrt(xx)) / math.sqrt(yy)
    if abs(value) > 1 + 1e-12:
        raise ValueError("correlation outside numeric tolerance")
    return _scalar(max(-1.0, min(1.0, value)))


def masked_metrics(observed, predicted, mask):
    observed, predicted = _paired(observed, predicted, empty=True)
    selected = _sequence(mask, empty=True)
    if len(selected) != len(observed) or any(type(x) is not bool for x in selected):
        raise ValueError("mask must contain exactly one bool per observation")
    left = [x for x, use in zip(observed, selected) if use]
    right = [x for x, use in zip(predicted, selected) if use]
    if not left:
        return {"count": 0, "pearson": _undefined("no_observations"),
                "mae": _undefined("no_observations"),
                "mse": _undefined("no_observations")}
    errors = paired_errors(left, right)
    return {"count": len(left), "pearson": pearson(left, right),
            "mae": _scalar(errors["mae"]), "mse": _scalar(errors["mse"])}


def window_summaries(trace, windows, mean_scale, std_scale):
    trace = _vector(trace)
    mean_scale, std_scale = _number(mean_scale), _number(std_scale)
    if mean_scale <= 0 or std_scale <= 0:
        raise ValueError("scales must be positive")
    intervals = []
    for interval in _sequence(windows):
        pair = _sequence(interval)
        if len(pair) != 2:
            raise ValueError("window must contain two indices")
        lo, hi = (_integer(x) for x in pair)
        if lo >= hi or hi > len(trace):
            raise ValueError("invalid half-open window")
        intervals.append((lo, hi))
    ordered = sorted(intervals)
    if any(left[1] > right[0] for left, right in zip(ordered, ordered[1:])):
        raise ValueError("overlapping windows")
    output = []
    for lo, hi in intervals:
        values = trace[lo:hi]
        scale = max(map(abs, values))
        if scale:
            reduced = [v / scale for v in values]
            center = _mean(reduced)
            variance = _sum((v - center) ** 2 for v in reduced) / len(values)
            std = _number(scale * math.sqrt(variance))
        else:
            std = 0.0
        output.extend([_number(_mean(values) / mean_scale), _number(std / std_scale)])
    return output


def window_max(trace, width, stride):
    trace = _vector(trace)
    width, stride = _integer(width, positive=True), _integer(stride, positive=True)
    if width > len(trace):
        raise ValueError("no valid window")
    return [max(trace[start:start + width]) for start in range(0, len(trace) - width + 1, stride)]


def soft_dtw(x, y, gamma, time_penalty):
    x, y = _vector(x), _vector(y)
    gamma, time_penalty = _number(gamma), _number(time_penalty)
    if gamma <= 0 or time_penalty < 0:
        raise ValueError("invalid soft-DTW parameters")
    previous = [0.0] + [math.inf] * len(y)
    for i, left in enumerate(x):
        current = [math.inf]
        for j, right in enumerate(y):
            incoming = [previous[j], previous[j + 1], current[j]]
            smallest = min(incoming)
            exponential_sum = _sum(math.exp(-(v - smallest) / gamma)
                                   for v in incoming if math.isfinite(v))
            soft_minimum = _number(smallest - gamma * math.log(exponential_sum))
            cost = _number(abs(left - right) + time_penalty * abs(i - j))
            current.append(_number(cost + soft_minimum))
        previous = current
    return {"value": _number(previous[-1])}


def classification(logits, labels):
    logits = _matrix(logits)
    labels = _sequence(labels)
    if len(labels) != len(logits) or len(logits[0]) < 2:
        raise ValueError("classification shape mismatch")
    predictions, losses = [], []
    for row, label in zip(logits, labels):
        label = _integer(label)
        if label >= len(row):
            raise ValueError("label outside class range")
        maximum = max(row)
        predictions.append(row.index(maximum))
        log_normalizer = math.log(_sum(math.exp(v - maximum) for v in row))
        losses.append(_number((maximum - row[label]) + log_normalizer))
    return {"accuracy": sum(a == b for a, b in zip(predictions, labels)) / len(labels),
            "cross_entropy": _mean(losses), "predictions": predictions}


def regularizer(physical_values, edges):
    physical_values = _vector(physical_values)
    unique, terms = set(), []
    for edge in _sequence(edges, empty=True):
        pair = _sequence(edge)
        if len(pair) != 2:
            raise ValueError("edge must contain child and parent")
        edge = tuple(_integer(index) for index in pair)
        if max(edge) >= len(physical_values) or edge in unique:
            raise ValueError("out-of-range or duplicate directed edge")
        unique.add(edge)
        difference = _number(physical_values[edge[0]] - physical_values[edge[1]])
        terms.append(_number(difference * difference))
    return _scalar(_sum(terms))


def _bounded_inputs(unconstrained, lowers, uppers):
    unconstrained, lowers = _paired(unconstrained, lowers)
    uppers = _vector(uppers)
    if len(uppers) != len(lowers) or any(lo >= hi for lo, hi in zip(lowers, uppers)):
        raise ValueError("bounds must be finite, ordered and dimension-matched")
    return unconstrained, lowers, uppers


def bounded_forward(unconstrained, lowers, uppers):
    us, lowers, uppers = _bounded_inputs(unconstrained, lowers, uppers)
    result = []
    for u, lo, hi in zip(us, lowers, uppers):
        if u >= 0:
            p = 1 / (1 + math.exp(-u))
        else:
            e = math.exp(u)
            p = e / (1 + e)
        # Convex combination remains representable when hi-lo would overflow.
        result.append(_sum([lo * (1 - p), hi * p]))
    return result


def bounded_log_jacobian(unconstrained, lowers, uppers):
    us, lowers, uppers = _bounded_inputs(unconstrained, lowers, uppers)
    terms = []
    for u, lo, hi in zip(us, lowers, uppers):
        width = hi - lo
        if math.isfinite(width):
            # Nearby finite endpoints must be subtracted before taking logs.
            # Scaling each endpoint first destroys a narrow interval's precision.
            log_width = math.log(width)
        else:
            # Overflow implies a wide opposite-sign interval. Halving both
            # endpoints makes its difference representable; restore log(2).
            log_width = math.log(hi / 2.0 - lo / 2.0) + math.log(2.0)
        softplus_positive = max(u, 0.0) + math.log1p(math.exp(-abs(u)))
        softplus_negative = max(-u, 0.0) + math.log1p(math.exp(-abs(u)))
        terms.append(_number(log_width - softplus_positive - softplus_negative))
    return _scalar(_sum(terms))


def posterior_log_density(mae, scale, physical_regularizer, log_jacobian):
    mae, scale = _number(mae), _number(scale)
    physical_regularizer, log_jacobian = _number(physical_regularizer), _number(log_jacobian)
    if mae < 0 or physical_regularizer < 0 or scale <= 0:
        raise ValueError("invalid posterior density inputs")
    return _scalar(_sum([-_number(mae / scale), -physical_regularizer, log_jacobian]))


def quantiles(values, probabilities):
    values = sorted(_vector(values))
    probabilities = _vector(probabilities)
    if any(p < 0 or p > 1 for p in probabilities):
        raise ValueError("quantile probability outside [0,1]")
    result = []
    for probability in probabilities:
        index = probability * (len(values) - 1)
        lower = math.floor(index)
        fraction = index - lower
        upper = min(lower + 1, len(values) - 1)
        result.append(_sum([values[lower] * (1 - fraction), values[upper] * fraction]))
    return result


def distance_binned_quantiles(distances, samples, edges, probabilities):
    distances, edges = _vector(distances), _vector(edges)
    samples = _matrix(samples)
    probabilities = _vector(probabilities)
    if len(edges) < 2 or any(a >= b for a, b in zip(edges, edges[1:])):
        raise ValueError("edges must be strictly increasing")
    if len(samples[0]) != len(distances):
        raise ValueError("distance/sample parameter dimensions differ")
    # Validate probability range even when a bin will be empty.
    if any(p < 0 or p > 1 for p in probabilities):
        raise ValueError("quantile probability outside [0,1]")
    bins = [[] for _ in range(len(edges) - 1)]
    for column, distance in enumerate(distances):
        matches = [i for i in range(len(bins))
                   if edges[i] <= distance and
                   (distance < edges[i + 1] or (i == len(bins) - 1 and distance == edges[i + 1]))]
        if len(matches) != 1:
            raise ValueError("parameter distance not assigned exactly once")
        bins[matches[0]].append(column)
    rows = []
    for index, columns in enumerate(bins):
        values = [sample[column] for sample in samples for column in columns]
        rows.append({"bin_index": index, "count": len(values), "parameter_count": len(columns),
                     "quantiles": quantiles(values, probabilities) if values else _undefined("empty_bin")})
    return rows


def lyapunov(norms, step_counts, dt):
    norms = _vector(norms)
    step_counts = [_integer(x, positive=True) for x in _sequence(step_counts)]
    dt = _number(dt)
    if len(norms) != len(step_counts) or any(x <= 0 for x in norms) or dt <= 0:
        raise ValueError("invalid Lyapunov normalization inputs")
    total_steps = sum(step_counts)
    per_step = _number(_sum(math.log(x) for x in norms) / _number(total_steps))
    return {"per_step": per_step, "per_time": _number(per_step / dt), "total_steps": total_steps}


def jacobian_sign(matrix):
    return [[1 if x > 0 else (-1 if x < 0 else 0) for x in row] for row in _matrix(matrix)]


def parameter_reset(initial, trained, indices):
    initial, trained = _paired(initial, trained)
    indices = [_integer(x) for x in _sequence(indices, empty=True)]
    if len(indices) != len(set(indices)) or any(x >= len(initial) for x in indices):
        raise ValueError("duplicate or invalid reset index")
    for index in indices:
        trained[index] = initial[index]
    return trained


def perturbation_norms(clean, adversarial):
    clean, adversarial = _paired(clean, adversarial)
    if any(x < 0 or x > 1 for x in clean + adversarial):
        raise ValueError("pixels must be in [0,1]")
    differences = [a - b for a, b in zip(clean, adversarial)]
    return {"l2": _number(math.sqrt(_sum(x * x for x in differences))),
            "linf": max(abs(x) for x in differences)}


def receptive_field_normalize(values):
    values = _vector(values)
    if min(values) == max(values):
        return _undefined("constant_receptive_field")
    scale = max(map(abs, values))
    values = [v / scale for v in values]
    lo, hi = min(values), max(values)
    normalized = [_number((v - lo) / (hi - lo)) for v in values]
    return {"defined": True, "values": normalized, "contour": [v >= 0.6 for v in normalized]}


def paired_mean_difference(reference, candidate, higher_is_better):
    reference, candidate = _paired(reference, candidate)
    if type(higher_is_better) is not bool:
        raise ValueError("direction must be bool")
    direction = 1 if higher_is_better else -1
    differences = [_number(direction * (c - r)) for r, c in zip(reference, candidate)]
    return {"mean_improvement": _mean(differences), "paired_differences": differences,
            "n_units": len(differences)}
