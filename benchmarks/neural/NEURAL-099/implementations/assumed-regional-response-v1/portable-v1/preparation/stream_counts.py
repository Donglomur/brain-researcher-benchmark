"""Production-direction event-to-absolute-bin counting, with no I/O.

This intentionally does not call the independent edge-on-spikes oracle. Events
search a single absolute edge grid whose gaps are explicitly unscored. Physical
observation and authentic input provenance are external to both algorithms.
"""
from array import array
from bisect import bisect_right
import math

MAX_CHUNK_EVENTS = 65536
MAX_DECLARED_EVENTS = 1224589
MAX_TRIAL_ROWS = 206
BINS_PER_WINDOW = 100


def _integer(value, name, lower=0, upper=None):
    if type(value) is not int or value < lower or (upper is not None and value > upper):
        raise ValueError('Invalid ' + name)
    return value


def _number(value, name):
    if type(value) not in (int, float):
        raise ValueError('Invalid ' + name)
    try:
        result = float(value)
    except OverflowError as error:
        raise ValueError('Nonfinite ' + name) from error
    if not math.isfinite(result):
        raise ValueError('Nonfinite ' + name)
    return result


def make_grid(anchors_seconds):
    """Explicit gap bins preserve actual onsets; no nominal 0.5-s schedule."""
    if type(anchors_seconds) not in (list, tuple) or not 1 <= len(anchors_seconds) <= MAX_TRIAL_ROWS:
        raise ValueError('Invalid complete source trial roster')
    anchors = [_number(value, 'click anchor') for value in anchors_seconds]
    if any(right <= left for left, right in zip(anchors, anchors[1:])):
        raise ValueError('Source trial rows must be strictly chronological')
    edges, coordinates = [], []
    for trial, anchor in enumerate(anchors):
        local = [anchor + offset / 1000000 for offset in range(-100000, 100001, 1000)]
        if any(not math.isfinite(value) for value in local) or any(b <= a for a, b in zip(local, local[1:])):
            raise ValueError('Selected absolute bin edges are not representable')
        if edges:
            if local[0] < edges[-1]:
                raise ValueError('Selected history/response extents overlap across trials')
            if local[0] > edges[-1]:
                edges.append(local[0])
                coordinates.append(-1)
        else:
            edges.append(local[0])
        for index in range(200):
            edges.append(local[index+1])
            coordinates.append(trial*200 + index)
    return tuple(edges), tuple(coordinates)


def count_cluster(anchors_seconds, chunks, *, declared_spike_count,
                  max_chunk_size=MAX_CHUNK_EVENTS):
    """Read each supplied event once and assign it using absolute boundaries.

    Chunks have contiguous *unit-relative* source_start offsets. Equal timestamps
    are distinct deposited events, even across chunks. No sorting, deduplication,
    response-dependent eligibility, clipping or duration inference is performed.
    """
    _integer(declared_spike_count, 'declared spike count', 0, MAX_DECLARED_EVENTS)
    _integer(max_chunk_size, 'chunk limit', 1, MAX_CHUNK_EVENTS)
    edges, coordinates = make_grid(anchors_seconds)
    values = array('Q', [0]) * (len(anchors_seconds)*200)
    if values.itemsize != 8:
        raise ValueError('Runtime does not provide the required uint64 counter width')
    seen, previous, selected, gaps, before, after = 0, None, 0, 0, 0, 0
    for chunk in chunks:
        if type(chunk) is not dict or set(chunk) != {'source_start', 'spikes'}:
            raise ValueError('Invalid source chunk descriptor')
        if _integer(chunk['source_start'], 'source chunk offset') != seen:
            raise ValueError('Source chunk offset gap, repetition or overlap')
        spikes = chunk['spikes']
        if type(spikes) not in (list, tuple) or not 1 <= len(spikes) <= max_chunk_size:
            raise ValueError('Invalid bounded nonempty spike chunk')
        if seen + len(spikes) > declared_spike_count:
            raise ValueError('Source chunks exceed the declared unit extent')
        for item in spikes:
            spike = _number(item, 'source spike')
            if previous is not None and spike < previous:
                raise ValueError('Source spikes reverse order within or between chunks')
            previous = spike
            interval = bisect_right(edges, spike) - 1
            if interval < 0:
                before += 1
            elif interval >= len(coordinates):
                after += 1
            elif coordinates[interval] < 0:
                gaps += 1
            else:
                values[coordinates[interval]] += 1
                selected += 1
        seen += len(spikes)
    if seen != declared_spike_count:
        raise ValueError('Source chunks do not completely cover the declared unit extent')
    if seen != selected + gaps + before + after:
        raise ValueError('Source event partition accounting mismatch')
    history, response = [], []
    for trial in range(len(anchors_seconds)):
        start = trial*200
        history.append(list(values[start:start+100]))
        response.append(list(values[start+100:start+200]))
    return {'history_counts': history, 'response_counts': response,
            'source_spikes_consumed': seen,
            'event_partition': {'selected_windows': selected, 'gaps': gaps,
                                'before_first_window': before, 'at_or_after_final_edge': after},
            'observation_coverage_verified': False}


def compare_cluster(production, reference, *, asset_id, cluster_id):
    """Verify each cluster before sums can hide offsetting errors."""
    if production['source_spikes_consumed'] != reference['source_spikes_consumed']:
        raise ValueError('Independent source-consumption mismatch')
    checked = 0
    for window in ('history_counts', 'response_counts'):
        actual, expected = production[window], reference[window]
        if len(actual) != len(expected):
            raise ValueError('Independent trial count mismatch')
        for trial, (left, right) in enumerate(zip(actual, expected)):
            if len(left) != 100 or len(right) != 100:
                raise ValueError('Independent bin support mismatch')
            for bin_index, (a, b) in enumerate(zip(left, right)):
                if type(a) is not int or type(b) is not int or a < 0 or b < 0 or a != b:
                    raise ValueError('Independent count mismatch at asset=%s cluster=%s trial=%s window=%s bin=%s' %
                                     (asset_id, cluster_id, trial, window, bin_index))
                checked += 1
    return checked
