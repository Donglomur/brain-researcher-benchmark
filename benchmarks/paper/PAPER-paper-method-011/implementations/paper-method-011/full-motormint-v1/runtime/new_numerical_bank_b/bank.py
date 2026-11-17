"""Independent prospective MotorMINT primitives; no historical equivalence claim.

See DERIVATION.md for source boundaries and the independently derived beta series.
Inputs are explicit supplied bindings. This module reads no files and uses no RNG.
"""

import bisect
import math


def _number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(label + " must be numeric")
    try:
        result = float(value)
    except OverflowError as exc:
        raise ValueError(label + " exceeds finite float range") from exc
    return _finite(result, label)


def _finite(value, label):
    if not math.isfinite(value):
        raise ValueError(label + " must remain finite")
    return value


def _vector(value, label, minimum=1):
    if not isinstance(value, list) or len(value) < minimum:
        raise ValueError(label + " must be a list with sufficient entries")
    return [_number(item, label) for item in value]


def _matrix(value, label, rows=None, width=None):
    if not isinstance(value, list) or not value:
        raise ValueError(label + " must be a nonempty row list")
    result = [_vector(row, label) for row in value]
    if rows is not None and len(result) != rows:
        raise ValueError(label + " row count mismatch")
    columns = len(result[0]) if width is None else width
    if any(len(row) != columns for row in result):
        raise ValueError(label + " column count mismatch")
    return result


def _positive(value, label):
    value = _number(value, label)
    if value <= 0:
        raise ValueError(label + " must be positive")
    return value


def _logadd(left, right):
    high, low = (left, right) if left >= right else (right, left)
    return high + math.log1p(math.exp(low - high))


def _beta_lower_series(x, a, b, log_x=None):
    """Regularized beta from a positive-term integration-by-parts series.

    The geometric remainder bound uses monotonic term ratios. Explicit failure
    on nonconvergence avoids silently returning a truncated numerical result.
    """
    logterm = (a * (math.log(x) if log_x is None else log_x) + b * math.log1p(-x) - math.log(a)
               - math.lgamma(a) - math.lgamma(b) + math.lgamma(a + b))
    logsum = logterm
    for index in range(200000):
        ratio = x * (a + b + index) / (a + index + 1)
        upper = max(x, ratio)
        if upper < 1:
            relative_bound = math.exp(logterm - logsum) * ratio / (1 - upper)
            if relative_bound <= 2e-15:
                answer = math.exp(logsum)
                if not 0 <= answer <= 1 + 5e-12:
                    raise ArithmeticError("incomplete beta lost probability range")
                return min(answer, 1.0)
        logterm += math.log(ratio)
        logsum = _logadd(logsum, logterm)
    raise ArithmeticError("incomplete beta series did not converge")


def _student_two_sided(t_value, df):
    magnitude = abs(t_value)
    if magnitude == 0:
        return 1.0
    # hypot avoids squaring a potentially large finite t statistic.
    denominator = math.hypot(math.sqrt(df), magnitude)
    if magnitude < 1:
        y = (magnitude / denominator) ** 2
        if y == 0:
            return 1.0
        return max(0.0, 1 - _beta_lower_series(y, 0.5, df / 2))
    log_x = math.log(df) - 2 * math.log(denominator)
    x = math.exp(log_x)
    # Retain log(x): x can underflow although x**(df/2) is representable.
    return _beta_lower_series(x, df / 2, 0.5, log_x)


def _paired(payload):
    left = _vector(payload["left"], "left", 2)
    right = _vector(payload["right"], "right", 2)
    identifiers = payload["unit_ids"]
    size = len(left)
    if len(right) != size or not isinstance(identifiers, list) or len(identifiers) != size:
        raise ValueError("paired lengths must agree")
    if any(not isinstance(item, str) or not item for item in identifiers):
        raise ValueError("unit_ids must be nonempty strings")
    if len(set(identifiers)) != size:
        raise ValueError("unit_ids must be unique")
    differences = [_finite(a - b, "paired difference") for a, b in zip(left, right)]
    average = _finite(math.fsum(value / size for value in differences), "mean difference")
    residuals = [_finite(value - average, "centered difference") for value in differences]
    deviation = _finite(math.hypot(*residuals) / math.sqrt(size - 1), "sample SD")
    standard_error = _finite(deviation / math.sqrt(size), "standard error")
    statistic = None if standard_error == 0 else _finite(average / standard_error, "t statistic")
    return {
        "n": size,
        "mean_difference": average,
        "sample_sd": deviation,
        "standard_error": standard_error,
        "t_statistic": statistic,
        "degrees_of_freedom": size - 1,
        "two_sided_p": None if statistic is None else _student_two_sided(statistic, size - 1),
        "undefined_reason": "zero_standard_error" if statistic is None else None,
    }


def _interval(payload):
    draws = payload["draws"]
    if not isinstance(draws, list) or not draws:
        raise ValueError("draws must be a nonempty list")
    alpha = _number(payload["alpha"], "alpha")
    if not 0 < alpha < 1:
        raise ValueError("alpha must be strictly between zero and one")
    values = [_number(value, "draw") for value in draws if value is not None]
    undefined = len(draws) - len(values)
    answer = None
    if not undefined:
        values.sort()

        def quantile(probability):
            location = (len(values) - 1) * probability
            lower = int(math.floor(location))
            upper = int(math.ceil(location))
            fraction = location - lower
            # Convex interpolation avoids overflowing an endpoint difference.
            return _finite((1 - fraction) * values[lower] + fraction * values[upper], "quantile")

        answer = [quantile(alpha / 2), quantile(1 - alpha / 2)]
    return {
        "draw_count": len(draws), "undefined_count": undefined, "interval": answer,
        "status": "undefined_draws" if undefined else "complete",
    }


def _geometry(payload):
    names = ("neural", "muscle", "kinematic", "partition")
    neural_a = _matrix(payload["neural_a"], "neural_a")
    size, width = len(neural_a), len(neural_a[0])
    neural_b = _matrix(payload["neural_b"], "neural_b", size, width)
    muscle = _matrix(payload["muscle"], "muscle", size, 7)
    phase = _vector(payload["phase"], "phase")
    velocity = _vector(payload["velocity"], "velocity")
    if len(phase) != size or len(velocity) != size:
        raise ValueError("behavior vector lengths must match neural rows")
    scales = payload["scales"]
    muscle_sd = _vector(scales["muscle_sd"], "muscle_sd")
    if len(muscle_sd) != 7 or any(value <= 0 for value in muscle_sd):
        raise ValueError("muscle_sd needs seven positive scales")
    phase_sd = _positive(scales["phase_sd"], "phase_sd")
    phase_period = _positive(scales["phase_period"], "phase_period")
    velocity_sd = _positive(scales["velocity_sd"], "velocity_sd")
    pair_policy = payload["pair_policy"]
    if pair_policy not in ("unique_offdiagonal", "full_ordered_with_diagonal"):
        raise ValueError("unknown pair_policy")
    count = size * (size - 1) // 2 if pair_policy == "unique_offdiagonal" else size * size
    if count == 0:
        raise ValueError("no pairs available")
    edges = {name: _vector(payload["edges"][name], name + " edges", 2) for name in names}
    if any(any(left >= right for left, right in zip(edge, edge[1:])) for edge in edges.values()):
        raise ValueError("bin edges must be strictly increasing")
    threshold = _number(payload["ordering_min_neural_difference"], "ordering threshold")
    if threshold < 0:
        raise ValueError("ordering threshold must be nonnegative")
    tie_policy = payload["ordering_tie_policy"]
    if tie_policy not in ("include_as_disagreement", "exclude"):
        raise ValueError("unknown ordering_tie_policy")
    draws = payload["ordering_draws"]
    if not isinstance(draws, list):
        raise ValueError("ordering_draws must be a list")
    for draw in draws:
        if (not isinstance(draw, list) or len(draw) != 4
                or any(isinstance(i, bool) or not isinstance(i, int) or not 0 <= i < size for i in draw)):
            raise ValueError("draws need four in-range integer indices")
        if pair_policy == "unique_offdiagonal" and (draw[0] == draw[1] or draw[2] == draw[3]):
            raise ValueError("offdiagonal draws require distinct pair endpoints")

    def pairs():
        for first in range(size):
            start = first + 1 if pair_policy == "unique_offdiagonal" else 0
            for second in range(start, size):
                yield first, second

    def distance(first, second):
        delta_phase = abs(_finite(phase[first] - phase[second], "phase difference")) % phase_period
        circular = min(delta_phase, phase_period - delta_phase)
        scaled_phase = _finite(circular / phase_sd, "scaled phase distance")
        scaled_velocity = _finite(_finite(velocity[first] - velocity[second], "velocity difference")
                                  / velocity_sd, "scaled velocity difference")
        muscle_deltas = [_finite(_finite(a - b, "muscle difference") / scale, "scaled muscle difference")
                         for a, b, scale in zip(muscle[first], muscle[second], muscle_sd)]
        result = (math.dist(neural_a[first], neural_a[second]), math.hypot(*muscle_deltas),
                  math.hypot(scaled_phase, scaled_velocity), math.dist(neural_b[first], neural_b[second]))
        return tuple(_finite(value, "distance") for value in result)

    # Repeat streamed traversals rather than storing a quadratic distance matrix.
    averages = [_finite(math.fsum(distance(a, b)[index] / count for a, b in pairs()), "pair mean")
                for index in range(4)]
    if any(value <= 0 for value in averages):
        raise ValueError("all pair means must be positive for normalization")

    def normalized(first, second):
        return tuple(_finite(value / mean, "normalized distance")
                     for value, mean in zip(distance(first, second), averages))

    def bin_index(value, edge):
        if value < edge[0] or value > edge[-1]:
            return None
        return len(edge) - 2 if value == edge[-1] else bisect.bisect_right(edge, value) - 1

    histograms = {name: {"counts": [[0] * (len(edges[name]) - 1) for _ in range(len(edges["neural"]) - 1)],
                          "outside": 0, "total": count} for name in names[1:]}
    for first, second in pairs():
        values = normalized(first, second)
        y = bin_index(values[0], edges["neural"])
        for index, name in enumerate(names[1:], 1):
            x = bin_index(values[index], edges[name])
            if x is None or y is None:
                histograms[name]["outside"] += 1
            else:
                histograms[name]["counts"][y][x] += 1

    ordering = {name: {"draw_count": len(draws), "eligible": 0, "concordant": 0, "discordant": 0,
                       "ties": 0, "neural_excluded": 0, "concordance": None} for name in names[1:]}
    for a, b, c, d in draws:
        first, second = normalized(a, b), normalized(c, d)
        neural_change = _finite(first[0] - second[0], "normalized neural difference")
        for index, name in enumerate(names[1:], 1):
            record = ordering[name]
            if abs(neural_change) <= threshold:
                record["neural_excluded"] += 1
                continue
            behavior_change = _finite(first[index] - second[index], "normalized comparison difference")
            if behavior_change == 0:
                record["ties"] += 1
                if tie_policy == "include_as_disagreement":
                    record["eligible"] += 1
            else:
                record["eligible"] += 1
                if (behavior_change > 0) == (neural_change > 0):
                    record["concordant"] += 1
                else:
                    record["discordant"] += 1
    for record in ordering.values():
        if record["eligible"]:
            record["concordance"] = record["concordant"] / record["eligible"]
    return {"pair_count": count, "means": dict(zip(names, averages)), "histograms": histograms,
            "ordering": ordering}


def evaluate(kind, payload):
    """Evaluate one declared primitive; invalid inputs raise ValueError/KeyError.

    A numerically unresolved beta series raises ArithmeticError. No undefined
    paired variance or resampling draw is silently converted to significance.
    """
    if not isinstance(payload, dict):
        raise ValueError("payload must be a dictionary")
    functions = {"cycle_geometry": _geometry, "paired_test": _paired, "draw_interval": _interval}
    if kind not in functions:
        raise ValueError("unknown numerical kind")
    return functions[kind](payload)
