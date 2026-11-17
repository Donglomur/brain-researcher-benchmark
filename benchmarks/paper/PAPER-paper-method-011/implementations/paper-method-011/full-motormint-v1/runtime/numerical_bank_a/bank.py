"""Independent MotorMINT numerical bank A; no file access or native dependency.

The inputs are already authenticated, support-aligned assessment arrays. This
module neither authenticates provenance nor establishes native Cycle/NLB parity.
The circular and neuron-threshold conventions are expressly prospective.
"""

import math


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _keys(value, names, label="payload"):
    _require(type(value) is dict and set(value) == set(names),
             label + " must have exactly the declared fields")


def _number(value, label):
    _require(type(value) in (int, float), label + " must be numeric, not boolean")
    try:
        result = float(value)
    except (OverflowError, ValueError):
        raise ValueError(label + " is not representable as a finite float") from None
    _require(math.isfinite(result), label + " must be finite")
    return result


def _integer(value, label, minimum=0):
    _require(type(value) is int and value >= minimum,
             label + " must be an integer >= " + str(minimum))
    return value


def _string(value, label):
    _require(type(value) is str and bool(value.strip()), label + " must be nonempty")
    return value


def _vector(value, label, integers=False):
    _require(type(value) is list and bool(value), label + " must be a nonempty list")
    validate = _integer if integers else _number
    return [validate(x, label) for x in value]


def _matrix(value, label, integers=False):
    _require(type(value) is list and bool(value), label + " must be a nonempty matrix")
    rows = [_vector(row, label + " row", integers) for row in value]
    _require(all(len(row) == len(rows[0]) for row in rows), label + " must be rectangular")
    return rows


def _matched(left, right):
    _require(len(left) == len(right) and len(left[0]) == len(right[0]),
             "truth/prediction shapes must match exactly")


def _mean(values):
    return math.fsum(x / len(values) for x in values)


def _r2(truth, prediction, period=None):
    if period is None:
        center = _mean(truth)
        residual = math.fsum((a - b) ** 2 for a, b in zip(truth, prediction))
        total = math.fsum((a - center) ** 2 for a in truth)
    else:
        angles = [(x % period) / period * math.tau for x in truth]
        cosine = _mean([math.cos(x) for x in angles])
        sine = _mean([math.sin(x) for x in angles])
        # Antipodal samples yield small nonzero trig roundoff; declare the
        # resultant ambiguous instead of choosing a numerical accident.
        _require(math.hypot(cosine, sine) > 1e-12,
                 "circular mean resultant is degenerate (<=1e-12)")
        center = math.atan2(sine, cosine) / math.tau * period

        def difference(a, b):
            # Reduce before subtraction to avoid overflow from large angles.
            return ((a % period - b % period) / period + 0.5) % 1.0 * period - period / 2.0

        residual = math.fsum(difference(a, b) ** 2 for a, b in zip(truth, prediction))
        total = math.fsum(difference(a, center) ** 2 for a in truth)
    _require(math.isfinite(total) and total > 0, "R2 is undefined for zero/nonfinite SST")
    result = 1.0 - residual / total
    _require(math.isfinite(result), "R2 arithmetic is not finite")
    return result


def _behavior(p):
    _keys(p, ("truth", "prediction", "groups", "circular_columns", "phase_period"))
    truth = _matrix(p["truth"], "truth")
    prediction = _matrix(p["prediction"], "prediction")
    _matched(truth, prediction)
    width = len(truth[0])
    groups = p["groups"]
    _require(type(groups) is dict and bool(groups), "groups must be a nonempty object")
    seen = set()
    for name, columns in groups.items():
        _string(name, "group name")
        _require(type(columns) is list and bool(columns), "group columns must be nonempty")
        for column in columns:
            _integer(column, "column")
            _require(column < width and column not in seen, "group columns must be a disjoint cover")
            seen.add(column)
    _require(seen == set(range(width)), "groups must cover every column")
    circular = p["circular_columns"]
    _require(type(circular) is list, "circular_columns must be a list")
    for column in circular:
        _integer(column, "circular column")
        _require(column < width, "circular column out of range")
    _require(len(set(circular)) == len(circular), "duplicate circular column")
    if circular:
        period = _number(p["phase_period"], "phase_period")
        _require(period > 0, "phase_period must be positive")
    else:
        _require(p["phase_period"] is None, "phase_period must be null without circular columns")
        period = None
    scores = [_r2([r[j] for r in truth], [r[j] for r in prediction],
                  period if j in circular else None) for j in range(width)]
    return {"per_dimension_r2": scores,
            "groups": {name: _mean([scores[j] for j in columns]) for name, columns in groups.items()}}


def _neural_state(p):
    _keys(p, ("spikes", "rates", "mean_rates", "bin_seconds"))
    spikes = _matrix(p["spikes"], "spikes", integers=True)
    rates = _matrix(p["rates"], "rates")
    _matched(spikes, rates)
    means = _vector(p["mean_rates"], "mean_rates")
    _require(len(means) == len(spikes[0]), "one mean rate required for each neuron")
    duration = _number(p["bin_seconds"], "bin_seconds")
    _require(duration > 0 and all(x > 0 for x in means) and
             all(x > 0 for row in rates for x in row), "rates and bin duration must be positive")
    count = sum(sum(row) for row in spikes)
    _require(count > 0, "bits/spike undefined with zero observed spikes")
    # Subtract logs rather than forming an overflowing rate ratio. Poisson
    # factorial and bin-width log terms cancel against the same-bin baseline.
    gain = math.fsum(n * (math.log(rate) - math.log(means[j])) -
                     duration * (rate - means[j])
                     for sr, rr in zip(spikes, rates)
                     for j, (n, rate) in enumerate(zip(sr, rr)))
    return {"bits_per_spike": gain / count / math.log(2.0)}


def _psth(p):
    _keys(p, ("truth", "prediction"))
    truth = _matrix(p["truth"], "truth")
    prediction = _matrix(p["prediction"], "prediction")
    _matched(truth, prediction)
    scores = [_r2([r[j] for r in truth], [r[j] for r in prediction])
              for j in range(len(truth[0]))]
    return {"per_neuron_r2": scores, "mean_r2": _mean(scores)}


def _distance(a, b):
    distance = math.hypot(*(x - y for x, y in zip(a, b)))
    _require(math.isfinite(distance), "distance arithmetic is not finite")
    return distance


def _pairs(states, comparison, block):
    # Block outer indices, never materialize an N by N distance matrix.
    for start in range(0, len(states), block):
        for i in range(start, min(start + block, len(states))):
            for j in range(i + 1, len(states)):
                yield (_distance(states[i], states[j]), _distance(comparison[i], comparison[j]))


def _geometry(p):
    _keys(p, ("states", "comparison_states", "block_size"))
    states = _matrix(p["states"], "states")
    comparison = _matrix(p["comparison_states"], "comparison_states")
    _require(len(states) == len(comparison) and len(states) >= 3,
             "geometry requires equal row counts and at least three states")
    block = _integer(p["block_size"], "block_size", 1)
    count = len(states) * (len(states) - 1) // 2
    # Multiple constant-memory passes avoid retaining pair distances.
    mx = math.fsum(x / count for x, _ in _pairs(states, comparison, block))
    my = math.fsum(y / count for _, y in _pairs(states, comparison, block))
    _require(mx > 0 and my > 0, "mean pair distances must be positive")
    xx = math.fsum((x / mx - 1) ** 2 for x, _ in _pairs(states, comparison, block))
    yy = math.fsum((y / my - 1) ** 2 for _, y in _pairs(states, comparison, block))
    _require(xx > 0 and yy > 0, "paired-distance Pearson undefined for constant distances")
    xy = math.fsum((x / mx - 1) * (y / my - 1)
                   for x, y in _pairs(states, comparison, block))
    pearson = xy / math.sqrt(xx) / math.sqrt(yy)
    _require(-1.000000000001 <= pearson <= 1.000000000001, "invalid Pearson arithmetic")
    discrepancy = math.fsum(abs(x / mx - y / my) / count
                            for x, y in _pairs(states, comparison, block))
    return {"pair_count": count, "mean_distance": mx, "mean_comparison_distance": my,
            "pearson": max(-1.0, min(1.0, pearson)),
            "mean_absolute_normalized_difference": discrepancy}


def _nearest_library(p):
    _keys(p, ("states", "library"))
    states = _matrix(p["states"], "states")
    library = _matrix(p["library"], "library")
    _require(len(library) >= 2 and len(states[0]) == len(library[0]),
             "library must contain at least two same-width states")
    count = len(library) * (len(library) - 1) // 2
    mean = math.fsum(_distance(library[i], library[j]) / count
                     for i in range(len(library)) for j in range(i + 1, len(library)))
    _require(mean > 0, "library pair-distance normalization is degenerate")
    distances = [min(_distance(s, row) for row in library) for s in states]
    return {"distances": distances, "normalized_distances": [x / mean for x in distances],
            "library_mean_pair_distance": mean}


def _contrasts(p):
    _keys(p, ("candidate", "reference"))
    candidate = _vector(p["candidate"], "candidate")
    reference = _vector(p["reference"], "reference")
    _require(len(candidate) == len(reference), "paired contrasts require identical support")
    gains = [x - y for x, y in zip(candidate, reference)]
    return {"signed_gain": gains, "mean_gain": _mean(gains),
            "mean_absolute_difference": _mean([abs(x) for x in gains]), "worst_gain": min(gains)}


def _neuron_loss_curve(p):
    _keys(p, ("counts", "scores", "max_neurons", "threshold_fraction"))
    counts = _vector(p["counts"], "counts", integers=True)
    _require(all(x >= 1 for x in counts) and all(a < b for a, b in zip(counts, counts[1:])),
             "counts must be strictly increasing positive integers")
    scores = _matrix(p["scores"], "scores")
    _require(len(scores) == len(counts) and len(scores[0]) >= 2,
             "each count needs the same number of at least two repetitions")
    maximum = _integer(p["max_neurons"], "max_neurons", 1)
    _require(counts[-1] <= maximum, "observed count exceeds max_neurons")
    fraction = _number(p["threshold_fraction"], "threshold_fraction")
    _require(0 < fraction <= 1, "threshold_fraction must lie in (0,1]")
    means = [_mean(row) for row in scores]
    deviation = [math.sqrt(math.fsum((x - mean) ** 2 for x in row) / (len(row) - 1))
                 for row, mean in zip(scores, means)]
    dense_counts, dense_scores = [], []
    if counts[0] == 1 and counts[-1] == maximum:
        _require(maximum <= 4096, "dense interpolation exceeds 4096-count resource bound")
        segment = 0
        for count in range(1, maximum + 1):
            while segment + 1 < len(counts) and counts[segment + 1] < count:
                segment += 1
            if count == counts[segment]:
                value = means[segment]
            elif segment + 1 < len(counts):
                weight = (count - counts[segment]) / (counts[segment + 1] - counts[segment])
                value = means[segment] * (1 - weight) + means[segment + 1] * weight
            else:
                value = means[segment]
            dense_counts.append(count)
            dense_scores.append(value)
    threshold = fraction * max(means)
    threshold_counts = dense_counts if dense_counts else counts
    threshold_scores = dense_scores if dense_scores else means
    first = next((n for n, value in zip(threshold_counts, threshold_scores)
                  if value >= threshold), None)
    return {"counts": counts, "means": means, "sample_sd": deviation,
            "interpolated_counts": dense_counts, "interpolated_means": dense_scores,
            "threshold": threshold, "first_count_at_or_above_threshold": first}


def _cost(p):
    _keys(p, ("attempts",))
    attempts = p["attempts"]
    _require(type(attempts) is list and bool(attempts), "attempts must be nonempty")
    times = ("wall_seconds", "cpu_seconds", "gpu_seconds")
    integers = ("token_count", "bytes_written", "peak_rss_bytes")
    collected = {name: [] for name in times + integers}
    ids = set()
    for attempt in attempts:
        _keys(attempt, ("id", "role", "status") + times + integers, "attempt")
        identity = _string(attempt["id"], "attempt id")
        _require(identity not in ids, "duplicate attempt id")
        ids.add(identity)
        _string(attempt["role"], "attempt role")
        _string(attempt["status"], "attempt status")
        for name in times:
            value = _number(attempt[name], name)
            _require(value >= 0, name + " must not be negative")
            collected[name].append(value)
        for name in integers:
            collected[name].append(_integer(attempt[name], name))
    totals = {name: math.fsum(collected[name]) for name in times}
    totals.update({name: sum(collected[name]) for name in ("token_count", "bytes_written")})
    return {"attempt_count": len(attempts), "totals": totals,
            "peak_rss_bytes": max(collected["peak_rss_bytes"])}


_OPERATIONS = {"behavior": _behavior, "neural_state": _neural_state, "psth": _psth,
               "geometry": _geometry, "nearest_library": _nearest_library,
               "contrasts": _contrasts, "neuron_loss_curve": _neuron_loss_curve, "cost": _cost}


def _finite_result(value):
    if type(value) is float:
        _require(math.isfinite(value), "nonfinite result")
    elif type(value) is dict:
        for item in value.values():
            _finite_result(item)
    elif type(value) is list:
        for item in value:
            _finite_result(item)


def evaluate(kind, payload):
    """Evaluate one strict declared operation; malformed/undefined inputs fail.

    It is the caller's duty to authenticate provenance, protect targets,
    validate complete original support and admit historical/native policies.
    No operation opens a file, mutates its inputs or launches another process.
    """
    _require(type(kind) is str and kind in _OPERATIONS, "unknown numerical kind")
    try:
        result = _OPERATIONS[kind](payload)
        _finite_result(result)
        return result
    except (OverflowError, ZeroDivisionError) as exc:
        raise ValueError("undefined or unrepresentable numerical result: " + type(exc).__name__) from None
