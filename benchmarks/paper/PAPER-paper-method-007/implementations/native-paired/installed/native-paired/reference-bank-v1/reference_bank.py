"""Independent UnitMatch functional arithmetic from MATH_CONTRACT_V1.md only.

Python standard library only. Input unit order and opaque identity fields are
retained. The caller supplies the exact 42 shared edge operands. No producer,
NumPy/SciPy, native profile, historical edge recipe, or authentic cohort is read.
All public input domains are validated before result-sized allocation.
"""
from bisect import bisect_left, bisect_right
from collections.abc import Sequence
import math
from numbers import Real

BINS = 41
ENGINEERING_ABS_TOLERANCE = 1e-12
ENGINEERING_REL_TOLERANCE = 1e-10


def _sequence(value, name):
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise TypeError(f"{name} must be a sequence")


def _number(value, name, allow_nonfinite=False):
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a non-boolean real number")
    try:
        numeric = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError(f"{name} is not representable as binary64") from exc
    if not allow_nonfinite and not math.isfinite(numeric):
        raise ValueError(f"{name} must be finite")
    return numeric


def _edges(edges):
    _sequence(edges, "edges")
    if len(edges) != BINS + 1:
        raise ValueError("edges must contain exactly 42 values")
    previous = None
    for edge in edges:
        edge = _number(edge, "edge")
        if previous is not None and edge <= previous:
            raise ValueError("edges must be strictly increasing")
        previous = edge


def _spikes(spikes):
    _sequence(spikes, "spikes")
    previous = None
    for spike in spikes:
        spike = _number(spike, "spike")
        if previous is not None and spike < previous:
            raise ValueError("spikes must be nondecreasing in recorded order")
        previous = spike


def _half(spikes, start, stop, edges):
    counts = [0] * BINS
    below = above = 0
    for index in range(start + 1, stop):
        interval = float(spikes[index]) - float(spikes[index - 1])
        if interval < edges[0]:
            below += 1
        elif interval > edges[-1]:
            above += 1
        else:
            bucket = min(BINS - 1, bisect_right(edges, interval) - 1)
            counts[bucket] += 1
    total = max(0, stop - start - 1)
    in_range = sum(counts)
    assert total == in_range + below + above
    return counts, {'intervals': total, 'in_range': in_range,
                    'below_range': below, 'above_range': above,
                    'outside': below + above}


def histograms(spikes, edges):
    """Return first/second 41-bin lists (or None), exact slices, and counts.

    Slices use Python [start, stop) indexing. N<2 has no admitted split, so its
    split endpoints are None and both interval/support records are zero.
    """
    _edges(edges)
    _spikes(spikes)
    n = len(spikes)
    if n < 2:
        empty = {'intervals': 0, 'in_range': 0, 'below_range': 0,
                 'above_range': 0, 'outside': 0}
        return {'first': None, 'second': None, 'n_spikes': n,
                'split': {'first_start': None, 'first_stop': None,
                          'second_start': None, 'second_stop': None,
                          'shared_boundary_index': None},
                'counts': {'first': dict(empty), 'second': dict(empty)}}
    first_stop = n // 2
    second_start = (n + 1) // 2 - 1
    first, first_counts = _half(spikes, 0, first_stop, edges)
    second, second_counts = _half(spikes, second_start, n, edges)
    return {'first': first, 'second': second, 'n_spikes': n,
            'split': {'first_start': 0, 'first_stop': first_stop,
                      'second_start': second_start, 'second_stop': n,
                      'shared_boundary_index': first_stop - 1 if n % 2 == 0 else None},
            'counts': {'first': first_counts, 'second': second_counts}}


def _fingerprints(vectors, name):
    _sequence(vectors, name)
    for vector in vectors:
        if vector is None:
            continue
        _sequence(vector, name + ' fingerprint')
        if len(vector) != BINS:
            raise ValueError("fingerprints must contain exactly 41 bins")
        for value in vector:
            if _number(value, "fingerprint count") < 0:
                raise ValueError("fingerprint counts must be nonnegative")


def _center(vector):
    if vector is None:
        return None
    values = [float(value) for value in vector]
    if all(value == values[0] for value in values):
        return None
    # Positive rescaling preserves correlation and bounds the arithmetic mean.
    # This is algebraically the vector's own centering, in scaled units.
    peak = max(values)
    values = [value / peak for value in values]
    mean = math.fsum(values) / BINS
    centered = [value - mean for value in values]
    scale = max(abs(value) for value in centered)
    if scale == 0:
        return None
    # Independent rescaling avoids overflowing the squared centered norm.
    centered = [value / scale for value in centered]
    norm = math.sqrt(math.fsum(value * value for value in centered))
    return centered, norm


def correlations(first, second):
    """Return every ordered first-versus-second entry; None means undefined."""
    _fingerprints(first, "first")
    _fingerprints(second, "second")
    if len(first) != len(second):
        raise ValueError("first and second must contain the same number of units")
    left = [_center(vector) for vector in first]
    right = [_center(vector) for vector in second]
    result = []
    for a in left:
        row = []
        for b in right:
            if a is None or b is None:
                row.append(None)
            else:
                numerator = math.fsum(x * y for x, y in zip(a[0], b[0]))
                value = numerator / (a[1] * b[1])
                row.append(min(1.0, max(-1.0, value)))
        result.append(row)
    return result


def _auc_values(values, name):
    _sequence(values, name)
    for value in values:
        if value is not None:
            _number(value, name + ' value', allow_nonfinite=True)


def auc(positive, negative):
    """Return (P(positive>negative)+0.5*P(tie), finite counts).

    None, NaN, and +/-infinity are excluded separately from both classes.
    Excluded counts are len(class)-returned_count; score exposes them explicitly.
    """
    _auc_values(positive, "positive")
    _auc_values(negative, "negative")
    negatives = sorted(float(value) for value in negative
                       if value is not None and math.isfinite(float(value)))
    positives = [float(value) for value in positive
                 if value is not None and math.isfinite(float(value))]
    np, nn = len(positives), len(negatives)
    if not np or not nn:
        return None, np, nn
    twice_wins = 0
    for value in positives:
        less = bisect_left(negatives, value)
        at_most = bisect_right(negatives, value)
        twice_wins += less + at_most
    return twice_wins / (2 * np * nn), np, nn


def _units(units):
    if not isinstance(units, list):
        raise TypeError("units must be an ordered list of dictionaries")
    for unit in units:
        if not isinstance(unit, dict):
            raise TypeError("each unit must be a dictionary")
        session = unit.get('session')
        if type(session) is not int or session not in (1, 2):
            raise ValueError("each unit must have integer session 1 or 2")


def _matrix(matrix, n, name, undefined=False):
    _sequence(matrix, name)
    if len(matrix) != n:
        raise ValueError(f"{name} must have one row per unit")
    for row in matrix:
        _sequence(row, name + ' row')
        if len(row) != n:
            raise ValueError(f"{name} must be square")
        for value in row:
            if undefined and value is None:
                continue
            value = _number(value, name + ' entry')
            lower = -1 if undefined else 0
            if value < lower or value > 1:
                raise ValueError(f"{name} entries must lie in [{lower},1]")


def _decode_validated(probabilities, units):
    candidates = []
    for i, first in enumerate(units):
        if first['session'] != 1:
            continue
        for j, second in enumerate(units):
            if second['session'] != 2:
                continue
            mean = (float(probabilities[i][j]) + float(probabilities[j][i])) / 2
            if mean > 0.5:
                candidates.append((-mean, i, j))
    candidates.sort()
    used = set()
    matches = set()
    for _, i, j in candidates:
        if i not in used and j not in used:
            matches.add((i, j))
            used.update((i, j))
    return matches


def decode(probabilities, units):
    """Return greedy canonical (original day1 index, original day2 index) pairs."""
    _units(units)
    _matrix(probabilities, len(units), 'probabilities')
    return _decode_validated(probabilities, units)


def score(probabilities, units, correlations):
    """Return complete ordered-direction per-mouse functional proxy support."""
    _units(units)
    n = len(units)
    _matrix(probabilities, n, 'probabilities')
    _matrix(correlations, n, 'correlations', undefined=True)
    matches = _decode_validated(probabilities, units)
    cross_positive, cross_negative, within_positive, within_negative = [], [], [], []
    for i, row in enumerate(correlations):
        for j, value in enumerate(row):
            if units[i]['session'] != units[j]['session']:
                pair = (i, j) if units[i]['session'] == 1 else (j, i)
                group = cross_positive if pair in matches else cross_negative
            else:
                group = within_positive if i == j else within_negative
            group.append(value)
    cross_auc, cp, cn = auc(cross_positive, cross_negative)
    within_auc, wp, wn = auc(within_positive, within_negative)
    day1 = sum(unit['session'] == 1 for unit in units)
    day2 = n - day1
    minimum = min(day1, day2)
    return {'matches': len(matches), 'decoded_pairs': [list(pair) for pair in sorted(matches)],
            'available_min_day_units': minimum,
            'stable_unit_yield': len(matches) / minimum if minimum else None,
            'isi_auc': cross_auc, 'within_session_isi_auc': within_auc,
            'finite_cross_match_directions': cp, 'finite_cross_nonmatch_directions': cn,
            'finite_within_same': wp, 'finite_within_other': wn,
            'undefined_cross_directions': len(cross_positive) + len(cross_negative) - cp - cn,
            'undefined_cross_match_directions': len(cross_positive) - cp,
            'undefined_cross_nonmatch_directions': len(cross_negative) - cn,
            'undefined_within_directions': len(within_positive) + len(within_negative) - wp - wn,
            'undefined_within_same': len(within_positive) - wp,
            'undefined_within_other': len(within_negative) - wn,
            'total_cross_directions': len(cross_positive) + len(cross_negative),
            'total_within_directions': len(within_positive) + len(within_negative),
            'isi_auc_eligible': len(matches) >= 20 and cp >= 40 and cross_auc is not None}
