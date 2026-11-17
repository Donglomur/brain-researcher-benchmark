"""Independent MotorMINT assessment primitives; standard library only.

This bank does not establish input provenance, historical/native equivalence,
independence of samples, or scientific-execution permission. See README.md.
"""

import math


_TAU = 2.0 * math.pi
MAX_INTERPOLATED_NEURONS = 4096


def _number(value, name):
    if type(value) not in (int, float):
        raise ValueError(name + " must be a finite number, not bool")
    try:
        result = float(value)
    except (ValueError, OverflowError) as exc:
        raise ValueError(name + " is outside finite numerical support") from exc
    if not math.isfinite(result):
        raise ValueError(name + " must be finite")
    return result


def _integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(name + " must be an integer in range, not bool")
    return value


def _text(value, name):
    if type(value) is not str or not value.strip():
        raise ValueError(name + " must be a nonempty string")
    return value


def _keys(value, expected, name="payload"):
    if type(value) is not dict or set(value) != set(expected):
        raise ValueError(name + " must have exactly the declared fields")


def _vector(value, name):
    if type(value) is not list or not value:
        raise ValueError(name + " must be a nonempty list")
    for item in value:
        _number(item, name)
    return value


def _matrix(value, name):
    if type(value) is not list or not value:
        raise ValueError(name + " must be a nonempty matrix")
    width = None
    for row in value:
        _vector(row, name + " row")
        if width is None:
            width = len(row)
        if len(row) != width:
            raise ValueError(name + " must be rectangular")
    return len(value), width


def _matched(a, b, aname="truth", bname="prediction"):
    shape = _matrix(a, aname)
    if _matrix(b, bname) != shape:
        raise ValueError("matrix support differs")
    return shape


def _mean(values):
    # Divide before summation to avoid overflowing a representable mean.
    count = len(values)
    return math.fsum(float(x) / count for x in values)


def _linear_r2(truth, prediction, column):
    n = len(truth)
    if all(row[column] == truth[0][column] for row in truth):
        raise ValueError("R2 requires positive truth variance")
    center = math.fsum(float(row[column]) / n for row in truth)
    sst = math.fsum((float(row[column]) - center) ** 2 for row in truth)
    if not sst > 0.0:
        raise ValueError("R2 requires positive truth variance")
    sse = math.fsum(
        (float(truth[i][column]) - float(prediction[i][column])) ** 2
        for i in range(n)
    )
    return 1.0 - sse / sst


def _wrapped_difference(a, b, period):
    # Reducing each argument first avoids overflow in a - b for finite inputs.
    left = math.remainder(float(a), period)
    right = math.remainder(float(b), period)
    return math.remainder(left - right, period)


def _circular_r2(truth, prediction, column, period):
    n = len(truth)
    if all(_wrapped_difference(row[column], truth[0][column], period) == 0 for row in truth):
        raise ValueError("circular R2 requires positive truth dispersion")
    cosine = math.fsum(
        math.cos((math.remainder(float(row[column]), period) / period) * _TAU)
        for row in truth
    )
    sine = math.fsum(
        math.sin((math.remainder(float(row[column]), period) / period) * _TAU)
        for row in truth
    )
    # A numerically indistinguishable zero resultant cannot define a mean.
    if math.hypot(cosine, sine) <= 1.0e-12 * n:
        raise ValueError("circular mean is undefined or numerically degenerate")
    center = (math.atan2(sine, cosine) / _TAU) * period
    sst = math.fsum(
        _wrapped_difference(row[column], center, period) ** 2 for row in truth
    )
    if not sst > 0.0:
        raise ValueError("circular R2 requires positive truth dispersion")
    sse = math.fsum(
        _wrapped_difference(truth[i][column], prediction[i][column], period) ** 2
        for i in range(n)
    )
    return 1.0 - sse / sst


def _behavior(payload):
    _keys(payload, ["truth", "prediction", "groups", "circular_columns", "phase_period"])
    truth, prediction = payload["truth"], payload["prediction"]
    _, width = _matched(truth, prediction)
    groups = payload["groups"]
    if type(groups) is not dict or not groups:
        raise ValueError("groups must be a nonempty dictionary")
    assigned = set()
    for name, columns in groups.items():
        _text(name, "group name")
        if type(columns) is not list or not columns:
            raise ValueError("group columns must be nonempty lists")
        for column in columns:
            _integer(column, "group column")
            if column >= width or column in assigned:
                raise ValueError("groups must be a disjoint in-range cover")
            assigned.add(column)
    if assigned != set(range(width)):
        raise ValueError("groups must cover every prediction column")
    circular = payload["circular_columns"]
    if type(circular) is not list:
        raise ValueError("circular_columns must be a list")
    circular_set = set()
    for column in circular:
        _integer(column, "circular column")
        if column >= width or column in circular_set:
            raise ValueError("circular columns must be unique and in range")
        circular_set.add(column)
    period = payload["phase_period"]
    if circular:
        period = _number(period, "phase_period")
        if not period > 0:
            raise ValueError("phase_period must be positive")
    elif period is not None:
        raise ValueError("phase_period must be null without circular columns")
    scores = []
    for column in range(width):
        if column in circular_set:
            scores.append(_circular_r2(truth, prediction, column, period))
        else:
            scores.append(_linear_r2(truth, prediction, column))
    return {
        "per_dimension_r2": scores,
        "groups": {name: _mean([scores[c] for c in columns]) for name, columns in groups.items()},
    }


def _neural_state(payload):
    _keys(payload, ["spikes", "rates", "mean_rates", "bin_seconds"])
    spikes, rates = payload["spikes"], payload["rates"]
    rows, width = _matched(spikes, rates, "spikes", "rates")
    baseline = _vector(payload["mean_rates"], "mean_rates")
    if len(baseline) != width or any(float(x) <= 0 for x in baseline):
        raise ValueError("mean_rates must contain one positive rate per neuron")
    dt = _number(payload["bin_seconds"], "bin_seconds")
    if not dt > 0:
        raise ValueError("bin_seconds must be positive")
    total = 0
    for i in range(rows):
        for j in range(width):
            total += _integer(spikes[i][j], "spike count")
            if float(rates[i][j]) <= 0:
                raise ValueError("rates must be strictly positive")
    if total == 0:
        raise ValueError("bits per spike is undefined without spikes")

    def terms():
        for i in range(rows):
            for j in range(width):
                rate = float(rates[i][j])
                mean = float(baseline[j])
                # Difference of logs avoids overflow/underflow of rate / mean.
                yield spikes[i][j] * (math.log(rate) - math.log(mean)) - dt * (rate - mean)

    value = math.fsum(terms()) / (math.log(2.0) * total)
    return {"bits_per_spike": value}


def _psth(payload):
    _keys(payload, ["truth", "prediction"])
    _, width = _matched(payload["truth"], payload["prediction"])
    scores = [_linear_r2(payload["truth"], payload["prediction"], j) for j in range(width)]
    return {"per_neuron_r2": scores, "mean_r2": _mean(scores)}


def _distance(a, b):
    value = math.dist(a, b)
    if not math.isfinite(value):
        raise ValueError("distance is outside finite numerical support")
    return value


def _pair_indices(n, block_size):
    # Blocks bound the number of outer-loop indices, not a materialized matrix.
    for start in range(0, n, block_size):
        for i in range(start, min(start + block_size, n)):
            for j in range(i + 1, n):
                yield i, j


def _geometry(payload):
    _keys(payload, ["states", "comparison_states", "block_size"])
    states = payload["states"]
    other = payload["comparison_states"]
    rows, _ = _matrix(states, "states")
    other_rows, _ = _matrix(other, "comparison_states")
    if rows != other_rows or rows < 3:
        raise ValueError("geometry requires matched support of at least three states")
    block = _integer(payload["block_size"], "block_size", 1)
    count = rows * (rows - 1) // 2
    mx = math.fsum(_distance(states[i], states[j]) / count for i, j in _pair_indices(rows, block))
    my = math.fsum(_distance(other[i], other[j]) / count for i, j in _pair_indices(rows, block))
    if mx <= 0 or my <= 0:
        raise ValueError("pairwise mean distance must be positive")
    # Normalize first: Pearson is invariant under positive scale and this avoids
    # needless squaring of large raw distances. Passes use O(1) pair workspace.
    xx = math.fsum((_distance(states[i], states[j]) / mx - 1.0) ** 2 for i, j in _pair_indices(rows, block))
    yy = math.fsum((_distance(other[i], other[j]) / my - 1.0) ** 2 for i, j in _pair_indices(rows, block))
    if xx <= 0 or yy <= 0:
        raise ValueError("Pearson correlation requires nonconstant pair distances")
    xy = math.fsum(
        (_distance(states[i], states[j]) / mx - 1.0)
        * (_distance(other[i], other[j]) / my - 1.0)
        for i, j in _pair_indices(rows, block)
    )
    pearson = xy / math.sqrt(xx) / math.sqrt(yy)
    # Cauchy-Schwarz limits this quantity; clipping is rounding protection only.
    if abs(pearson) > 1.0 + 1.0e-12:
        raise ValueError("correlation calculation exceeded its numerical domain")
    discrepancy = math.fsum(
        abs(_distance(states[i], states[j]) / mx - _distance(other[i], other[j]) / my) / count
        for i, j in _pair_indices(rows, block)
    )
    return {
        "pair_count": count,
        "mean_distance": mx,
        "mean_comparison_distance": my,
        "pearson": min(1.0, max(-1.0, pearson)),
        "mean_absolute_normalized_difference": discrepancy,
    }


def _nearest_library(payload):
    _keys(payload, ["states", "library"])
    states, library = payload["states"], payload["library"]
    _, width = _matrix(states, "states")
    n, library_width = _matrix(library, "library")
    if n < 2 or width != library_width:
        raise ValueError("library needs at least two states and matching width")
    count = n * (n - 1) // 2
    mean = math.fsum(_distance(library[i], library[j]) / count for i, j in _pair_indices(n, 1))
    if mean <= 0:
        raise ValueError("library mean pair distance must be positive")
    distances = [min(_distance(row, point) for point in library) for row in states]
    return {
        "distances": distances,
        "normalized_distances": [x / mean for x in distances],
        "library_mean_pair_distance": mean,
    }


def _contrasts(payload):
    _keys(payload, ["candidate", "reference"])
    candidate = _vector(payload["candidate"], "candidate")
    reference = _vector(payload["reference"], "reference")
    if len(candidate) != len(reference):
        raise ValueError("contrast support differs")
    gain = [float(x) - float(y) for x, y in zip(candidate, reference)]
    return {
        "signed_gain": gain,
        "mean_gain": _mean(gain),
        "mean_absolute_difference": _mean([abs(x) for x in gain]),
        "worst_gain": min(gain),
    }


def _neuron_loss_curve(payload):
    _keys(payload, ["counts", "scores", "max_neurons", "threshold_fraction"])
    counts = payload["counts"]
    if type(counts) is not list or not counts:
        raise ValueError("counts must be a nonempty list")
    maximum = _integer(payload["max_neurons"], "max_neurons", 1)
    previous = 0
    for count in counts:
        _integer(count, "count", 1)
        if count <= previous or count > maximum:
            raise ValueError("counts must be sorted, unique and at most max_neurons")
        previous = count
    rows, repeats = _matrix(payload["scores"], "scores")
    if rows != len(counts) or repeats < 2:
        raise ValueError("scores need matched count rows and at least two repeats")
    fraction = _number(payload["threshold_fraction"], "threshold_fraction")
    if fraction <= 0 or fraction > 1:
        raise ValueError("threshold_fraction must be in (0,1]")
    means = [_mean(row) for row in payload["scores"]]
    deviations = [
        math.sqrt(math.fsum((float(x) - means[i]) ** 2 / (repeats - 1) for x in row))
        for i, row in enumerate(payload["scores"])
    ]
    points, interpolated = [], []
    if counts[0] == 1 and counts[-1] == maximum:
        if maximum > MAX_INTERPOLATED_NEURONS:
            raise ValueError("interpolated output exceeds the declared 4096-point resource bound")
        points = list(range(1, maximum + 1))
        right = 0
        for count in points:
            while counts[right] < count:
                right += 1
            if counts[right] == count:
                interpolated.append(means[right])
            else:
                left = right - 1
                weight = (count - counts[left]) / (counts[right] - counts[left])
                interpolated.append((1.0 - weight) * means[left] + weight * means[right])
    threshold = fraction * max(means)
    eligible_counts = points if points else counts
    eligible_means = interpolated if points else means
    first = next((count for count, score in zip(eligible_counts, eligible_means) if score >= threshold), None)
    return {
        "counts": list(counts),
        "means": means,
        "sample_sd": deviations,
        "interpolated_counts": points,
        "interpolated_means": interpolated,
        "threshold": threshold,
        "first_count_at_or_above_threshold": first,
    }


def _cost(payload):
    _keys(payload, ["attempts"])
    attempts = payload["attempts"]
    if type(attempts) is not list or not attempts:
        raise ValueError("attempts must be a nonempty list")
    timing = ("wall_seconds", "cpu_seconds", "gpu_seconds")
    counting = ("token_count", "bytes_written", "peak_rss_bytes")
    fields = ("id", "role", "status") + timing + counting
    identities = set()
    for attempt in attempts:
        _keys(attempt, fields, "attempt")
        identity = _text(attempt["id"], "attempt id")
        if identity in identities:
            raise ValueError("attempt ids must be unique")
        identities.add(identity)
        _text(attempt["role"], "attempt role")
        _text(attempt["status"], "attempt status")
        for name in timing:
            if _number(attempt[name], name) < 0:
                raise ValueError("attempt times cannot be negative")
        for name in counting:
            _integer(attempt[name], name)
    totals = {name: math.fsum(float(row[name]) for row in attempts) for name in timing}
    for name in ("token_count", "bytes_written"):
        totals[name] = sum(row[name] for row in attempts)
    return {
        "attempt_count": len(attempts),
        "totals": totals,
        "peak_rss_bytes": max(row["peak_rss_bytes"] for row in attempts),
    }


_HANDLERS = {
    "behavior": _behavior,
    "neural_state": _neural_state,
    "psth": _psth,
    "geometry": _geometry,
    "nearest_library": _nearest_library,
    "contrasts": _contrasts,
    "neuron_loss_curve": _neuron_loss_curve,
    "cost": _cost,
}


def _finite_output(value):
    if type(value) is float and not math.isfinite(value):
        raise ValueError("computed metric is outside finite numerical support")
    if type(value) is list:
        for item in value:
            _finite_output(item)
    elif type(value) is dict:
        for item in value.values():
            _finite_output(item)


def evaluate(kind, payload):
    """Compute a declared primitive; malformed/undefined metrics raise ValueError.

    No files, processes, network, native libraries or global mutable state are
    accessed. Inputs are not mutated. Returned dictionaries use the shared ABI.
    """
    if type(kind) is not str or kind not in _HANDLERS:
        raise ValueError("unknown numerical kind")
    try:
        result = _HANDLERS[kind](payload)
        _finite_output(result)
        return result
    except (OverflowError, ZeroDivisionError) as exc:
        raise ValueError("computed metric is outside finite numerical support") from exc
