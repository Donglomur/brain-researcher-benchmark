"""Independent stdlib numerical bank B for declared Jaxley metric contracts.

This module contains no file IO, model execution, source fetching or native
simulator calls. Numerical definitions are those of NUMERICAL_API.json, not
a claim that an unresolved historical experiment used these exact settings.
"""
import math
from bisect import bisect_right


def _number(value, label="number"):
    if type(value) not in (int, float):
        raise ValueError(label + " must be a JSON number, not bool")
    try:
        out = float(value)
    except (OverflowError, ValueError):
        raise ValueError(label + " is outside finite float range") from None
    if not math.isfinite(out):
        raise ValueError(label + " must be finite")
    return out


def _finite(value):
    if not math.isfinite(value):
        raise ValueError("finite result is not representable")
    return float(value)


def _sum(values):
    try:
        return _finite(math.fsum(values))
    except OverflowError:
        raise ValueError("finite result is not representable") from None


def _sequence(value, label):
    if type(value) not in (list, tuple):
        raise ValueError(label + " must be a list or tuple")
    return list(value)


def _vector(value, label="vector", nonempty=True):
    result = [_number(x, label) for x in _sequence(value, label)]
    if nonempty and not result:
        raise ValueError(label + " must not be empty")
    return result


def _pair(left, right, nonempty=True):
    x = _vector(left, "left vector", nonempty)
    y = _vector(right, "right vector", nonempty)
    if len(x) != len(y):
        raise ValueError("paired lengths differ")
    return x, y


def _integer(value, label, lower=0):
    if type(value) is not int or value < lower:
        raise ValueError(label + " must be an integer >= " + str(lower))
    return value


def _positive(value, label):
    result = _number(value, label)
    if result <= 0:
        raise ValueError(label + " must be positive")
    return result


def _mean(values):
    return _sum(x / len(values) for x in values)


def _defined(value):
    return {"defined": True, "value": _finite(value)}


def _undefined(reason):
    return {"defined": False, "reason": reason}


def _scaled_center(values):
    scale = max(abs(x) for x in values)
    if scale == 0:
        return [0.0 for _ in values], 0.0
    scaled = [x / scale for x in values]
    centre = _mean(scaled)
    return [x - centre for x in scaled], scale


def paired_errors(observed, predicted):
    x, y = _pair(observed, predicted)
    differences = [_finite(a - b) for a, b in zip(x, y)]
    return {
        "mae": _mean([abs(d) for d in differences]),
        "mse": _mean([_finite(d * d) for d in differences]),
        "count": len(x),
    }


def pearson(observed, predicted):
    x, y = _pair(observed, predicted, nonempty=False)
    if len(x) < 2:
        return _undefined("fewer_than_two_observations")
    dx, _ = _scaled_center(x)
    dy, _ = _scaled_center(y)
    nx = math.sqrt(_sum(t * t for t in dx))
    ny = math.sqrt(_sum(t * t for t in dy))
    if nx == 0 or ny == 0:
        return _undefined("constant_vector")
    # Normalize the centred vectors before taking their inner product. This
    # avoids forming a potentially overflowing unnormalised covariance.
    corr = _sum((a / nx) * (b / ny) for a, b in zip(dx, dy))
    return _defined(max(-1.0, min(1.0, corr)))


def masked_metrics(observed, predicted, mask):
    x, y = _pair(observed, predicted, nonempty=False)
    selected = _sequence(mask, "mask")
    if len(selected) != len(x) or any(type(v) is not bool for v in selected):
        raise ValueError("mask must contain one boolean per observation")
    a = [v for v, use in zip(x, selected) if use]
    b = [v for v, use in zip(y, selected) if use]
    if not a:
        return {
            "count": 0,
            "pearson": _undefined("no_observations"),
            "mae": _undefined("no_observations"),
            "mse": _undefined("no_observations"),
        }
    errors = paired_errors(a, b)
    return {
        "count": len(a),
        "pearson": pearson(a, b),
        "mae": _defined(errors["mae"]),
        "mse": _defined(errors["mse"]),
    }


def window_summaries(trace, windows, mean_scale, std_scale):
    values = _vector(trace)
    ranges = _sequence(windows, "windows")
    if not ranges:
        raise ValueError("at least one explicit window is required")
    intervals = []
    for item in ranges:
        bounds = _sequence(item, "window")
        if len(bounds) != 2:
            raise ValueError("window must have two bounds")
        lo = _integer(bounds[0], "window start")
        hi = _integer(bounds[1], "window stop")
        if not lo < hi <= len(values):
            raise ValueError("window must be nonempty and within trace")
        intervals.append((lo, hi))
    ordered = sorted(intervals)
    if any(a[1] > b[0] for a, b in zip(ordered, ordered[1:])):
        raise ValueError("windows overlap")
    ms = _positive(mean_scale, "mean scale")
    ss = _positive(std_scale, "standard deviation scale")
    output = []
    for lo, hi in intervals:
        selected = values[lo:hi]
        centered, magnitude = _scaled_center(selected)
        std = _finite(magnitude * math.sqrt(_mean([v * v for v in centered])))
        output.extend([_finite(_mean(selected) / ms), _finite(std / ss)])
    return output


def window_max(trace, width, stride):
    values = _vector(trace)
    width = _integer(width, "width", 1)
    stride = _integer(stride, "stride", 1)
    if width > len(values):
        raise ValueError("no complete window")
    return [max(values[i:i + width]) for i in range(0, len(values) - width + 1, stride)]


def soft_dtw(x, y, gamma, time_penalty):
    a = _vector(x)
    b = _vector(y)
    temperature = _positive(gamma, "gamma")
    penalty = _number(time_penalty, "time penalty")
    if penalty < 0:
        raise ValueError("time penalty must be nonnegative")
    previous = [0.0] + [math.inf] * len(b)
    for i, left in enumerate(a):
        current = [math.inf]
        for j, right in enumerate(b):
            choices = (previous[j], previous[j + 1], current[j])
            minimum = min(choices)
            # At least one predecessor is finite for every reachable cell.
            weights = math.fsum(
                math.exp(-(v - minimum) / temperature)
                for v in choices if math.isfinite(v)
            )
            soft_minimum = _finite(minimum - temperature * math.log(weights))
            cost = _finite(abs(left - right) + penalty * abs(i - j))
            current.append(_finite(cost + soft_minimum))
        previous = current
    return {"value": previous[-1]}


def classification(logits, labels):
    rows = _sequence(logits, "logits")
    targets = _sequence(labels, "labels")
    if not rows or len(rows) != len(targets):
        raise ValueError("nonempty matching logits and labels required")
    matrix = [_vector(row, "logit row") for row in rows]
    classes = len(matrix[0])
    if classes < 2 or any(len(row) != classes for row in matrix):
        raise ValueError("logits must be rectangular with at least two classes")
    predictions, losses = [], []
    for row, label in zip(matrix, targets):
        _integer(label, "class label")
        if label >= classes:
            raise ValueError("class label outside row")
        maximum = max(row)
        prediction = row.index(maximum)
        predictions.append(prediction)
        partition = math.log(math.fsum(math.exp(v - maximum) for v in row))
        losses.append(_finite((maximum - row[label]) + partition))
    return {
        "accuracy": sum(p == y for p, y in zip(predictions, targets)) / len(targets),
        "cross_entropy": _mean(losses),
        "predictions": predictions,
    }


def regularizer(physical_values, edges):
    values = _vector(physical_values)
    pairs = _sequence(edges, "edges")
    seen, terms = set(), []
    for item in pairs:
        pair = _sequence(item, "edge")
        if len(pair) != 2:
            raise ValueError("edge must contain two indices")
        left, right = (_integer(v, "edge index") for v in pair)
        if left >= len(values) or right >= len(values):
            raise ValueError("edge index outside parameter vector")
        if (left, right) in seen:
            raise ValueError("duplicate directed edge")
        seen.add((left, right))
        difference = _finite(values[left] - values[right])
        terms.append(_finite(difference * difference))
    return _defined(_sum(terms))


def _bounded_vectors(unconstrained, lowers, uppers):
    u = _vector(unconstrained, "unconstrained")
    low = _vector(lowers, "lowers")
    high = _vector(uppers, "uppers")
    if not len(u) == len(low) == len(high):
        raise ValueError("bounded parameter lengths differ")
    if any(a >= b for a, b in zip(low, high)):
        raise ValueError("bounds must be strictly increasing")
    return u, low, high


def bounded_forward(unconstrained, lowers, uppers):
    u, low, high = _bounded_vectors(unconstrained, lowers, uppers)
    result = []
    for value, a, b in zip(u, low, high):
        if value >= 0:
            decay = math.exp(-value)
            sigmoid = 1.0 / (1.0 + decay)
            complement = decay / (1.0 + decay)
        else:
            rise = math.exp(value)
            sigmoid = rise / (1.0 + rise)
            complement = 1.0 / (1.0 + rise)
        # Weighted endpoints avoid an overflow in (upper - lower).
        result.append(_sum((a * complement, b * sigmoid)))
    return result


def bounded_log_jacobian(unconstrained, lowers, uppers):
    u, low, high = _bounded_vectors(unconstrained, lowers, uppers)
    terms = []
    for value, a, b in zip(u, low, high):
        width = b - a
        if math.isfinite(width):
            log_width = math.log(width)
        else:
            magnitude = max(abs(a), abs(b))
            log_width = math.log(magnitude) + math.log(b / magnitude - a / magnitude)
        log_derivative = log_width - abs(value) - 2.0 * math.log1p(math.exp(-abs(value)))
        terms.append(_finite(log_derivative))
    return _defined(_sum(terms))


def posterior_log_density(mae, scale, physical_regularizer, log_jacobian):
    loss = _number(mae, "MAE")
    likelihood_scale = _positive(scale, "likelihood scale")
    roughness = _number(physical_regularizer, "physical regularizer")
    jacobian = _number(log_jacobian, "log Jacobian")
    if loss < 0 or roughness < 0:
        raise ValueError("MAE and physical regularizer must be nonnegative")
    return _defined(_sum((-loss / likelihood_scale, -roughness, jacobian)))


def quantiles(values, probabilities):
    observations = sorted(_vector(values, "values"))
    ps = _vector(probabilities, "probabilities")
    if any(p < 0 or p > 1 for p in ps):
        raise ValueError("quantile probabilities must be within [0,1]")
    result = []
    for p in ps:
        position = p * (len(observations) - 1)
        left = int(math.floor(position))
        right = int(math.ceil(position))
        fraction = position - left
        result.append(_sum((
            observations[left] * (1.0 - fraction),
            observations[right] * fraction,
        )))
    return result


def distance_binned_quantiles(distances, samples, edges, probabilities):
    positions = _vector(distances, "distances")
    draws = _sequence(samples, "samples")
    if not draws:
        raise ValueError("at least one posterior draw required")
    matrix = [_vector(row, "sample row") for row in draws]
    if any(len(row) != len(positions) for row in matrix):
        raise ValueError("sample columns do not match parameter distances")
    boundaries = _vector(edges, "edges")
    if len(boundaries) < 2 or any(a >= b for a, b in zip(boundaries, boundaries[1:])):
        raise ValueError("bin edges must be strictly increasing")
    ps = _vector(probabilities, "probabilities")
    if any(p < 0 or p > 1 for p in ps):
        raise ValueError("quantile probabilities must be within [0,1]")
    groups = [[] for _ in boundaries[:-1]]
    for column, distance in enumerate(positions):
        if distance < boundaries[0] or distance > boundaries[-1]:
            raise ValueError("parameter distance outside bins")
        index = min(bisect_right(boundaries, distance) - 1, len(groups) - 1)
        groups[index].append(column)
    result = []
    for index, columns in enumerate(groups):
        pooled = [row[column] for row in matrix for column in columns]
        result.append({
            "bin_index": index,
            "count": len(pooled),
            "parameter_count": len(columns),
            "quantiles": quantiles(pooled, ps) if pooled else _undefined("empty_bin"),
        })
    return result


def lyapunov(norms, step_counts, dt):
    values = _vector(norms, "norms")
    counts = _sequence(step_counts, "step counts")
    if len(values) != len(counts):
        raise ValueError("norm and interval counts differ")
    if any(value <= 0 for value in values):
        raise ValueError("norms must be positive")
    steps = [_integer(n, "step count", 1) for n in counts]
    delta_t = _positive(dt, "dt")
    total = sum(steps)
    per_step = _finite(_sum(math.log(value) for value in values) / total)
    return {"per_step": per_step, "per_time": _finite(per_step / delta_t), "total_steps": total}


def jacobian_sign(matrix):
    rows = _sequence(matrix, "matrix")
    if not rows:
        raise ValueError("Jacobian matrix must not be empty")
    validated = [_vector(row, "matrix row") for row in rows]
    if any(len(row) != len(validated[0]) for row in validated):
        raise ValueError("Jacobian matrix must be rectangular")
    return [[1 if v > 0 else -1 if v < 0 else 0 for v in row] for row in validated]


def parameter_reset(initial, trained, indices):
    original, current = _pair(initial, trained)
    selected = _sequence(indices, "indices")
    seen = set()
    for index in selected:
        _integer(index, "reset index")
        if index >= len(current) or index in seen:
            raise ValueError("reset index outside vector or duplicated")
        seen.add(index)
        current[index] = original[index]
    return current


def perturbation_norms(clean, adversarial):
    original, changed = _pair(clean, adversarial)
    if any(v < 0 or v > 1 for v in original + changed):
        raise ValueError("pixels must be within [0,1]")
    differences = [abs(a - b) for a, b in zip(original, changed)]
    return {"l2": _finite(math.hypot(*differences)), "linf": max(differences)}


def receptive_field_normalize(values):
    original = _vector(values)
    magnitude = max(abs(v) for v in original)
    if magnitude == 0:
        return _undefined("constant_receptive_field")
    scaled = [v / magnitude for v in original]
    low, high = min(scaled), max(scaled)
    if low == high:
        return _undefined("constant_receptive_field")
    normalized = [(v - low) / (high - low) for v in scaled]
    return {
        "defined": True,
        "values": normalized,
        "contour": [v >= 0.6 for v in normalized],
    }


def paired_mean_difference(reference, candidate, higher_is_better):
    baseline, proposed = _pair(reference, candidate)
    if type(higher_is_better) is not bool:
        raise ValueError("metric direction must be a boolean")
    direction = 1.0 if higher_is_better else -1.0
    differences = [_finite(direction * (b - a)) for a, b in zip(baseline, proposed)]
    return {
        "mean_improvement": _mean(differences),
        "paired_differences": differences,
        "n_units": len(differences),
    }

