"""Independent, pure-stdlib reference for assumed-support spike counts.

Direction: each absolute window edge searches a sorted source spike chunk using
bisect_left; adjacent insertion positions give half-open bin counts. This does
not share a production event-to-bin histogram or floor relative spike times.
No files, scientific arrays, HDF5 objects, models or external tools are opened.
The caller supplies authenticated anchors, frozen membership and source chunks;
this module cannot authenticate those inputs or verify physical observation.
"""

from bisect import bisect_left
from fractions import Fraction
import math


BIN_COUNT = 100
MAX_CHUNK_SIZE = 65536
NAMED_REGIONS = frozenset(("BIC", "MGd", "MGm", "MGv", "MZMG", "SG"))
HISTORY_MICROSECONDS = tuple(range(-100000, 1, 1000))
RESPONSE_MICROSECONDS = tuple(range(0, 100001, 1000))


def _integer(value, name, minimum=None):
    if type(value) is not int or (minimum is not None and value < minimum):
        raise ValueError("Invalid " + name)
    return value


def _finite_float(value, name):
    if type(value) not in (int, float):
        raise ValueError("Invalid " + name)
    try:
        result = float(value)
    except OverflowError as error:
        raise ValueError("Nonfinite " + name) from error
    if not math.isfinite(result):
        raise ValueError("Nonfinite " + name)
    return result


def _sequence(value, name, *, nonempty=False):
    if type(value) not in (list, tuple) or (nonempty and not value):
        raise ValueError("Invalid " + name)
    return value


def _edges(anchor, offsets):
    # This exact operation order is the canonical boundary definition. Do not
    # subtract the anchor from spikes or accumulate a floating bin width.
    values = tuple(anchor + microseconds / 1_000_000 for microseconds in offsets)
    if any(not math.isfinite(edge) for edge in values):
        raise ValueError("Nonfinite absolute window edge")
    if any(right <= left for left, right in zip(values, values[1:])):
        raise ValueError("Absolute bin edges collapse or reverse at this clock scale")
    return values


def make_windows(anchors_seconds):
    """Build every supplied row's canonical windows, retaining input row order.

    Negative clock references are allowed. No nominal inter-click interval is
    substituted for actual anchors. Duplicate anchors are not silently removed.
    All history windows must be disjoint from all response windows in this
    recording; touching half-open intervals are allowed. That prohibition is a
    selected information-access rule, not evidence of recording continuity.
    """
    _sequence(anchors_seconds, "anchors", nonempty=True)
    windows = []
    for row, value in enumerate(anchors_seconds):
        anchor = _finite_float(value, "click anchor")
        windows.append({
            "source_trial_row": row,
            "anchor_seconds": anchor,
            "history_edges_seconds": _edges(anchor, HISTORY_MICROSECONDS),
            "response_edges_seconds": _edges(anchor, RESPONSE_MICROSECONDS),
        })
    responses = sorted((window["response_edges_seconds"][0],
                        window["response_edges_seconds"][-1],
                        window["source_trial_row"]) for window in windows)
    histories = sorted((window["history_edges_seconds"][0],
                        window["history_edges_seconds"][-1],
                        window["source_trial_row"]) for window in windows)
    cursor = 0
    for start, end, row in histories:
        while cursor < len(responses) and responses[cursor][1] <= start:
            cursor += 1
        if cursor < len(responses) and responses[cursor][0] < end:
            raise ValueError("History row %s overlaps scored response row %s" %
                             (row, responses[cursor][2]))
    return windows


def _chunk_limit(max_chunk_size):
    _integer(max_chunk_size, "maximum chunk size", 1)
    if max_chunk_size > MAX_CHUNK_SIZE:
        raise ValueError("Chunk size exceeds the bounded source-chunk contract")
    return max_chunk_size


def _zero_counts(number_of_trials):
    return [[0] * BIN_COUNT for _ in range(number_of_trials)]


def _count_cluster(windows, chunks, declared_spike_count, max_chunk_size):
    _integer(declared_spike_count, "declared spike count", 0)
    history = _zero_counts(len(windows))
    response = _zero_counts(len(windows))
    seen, last = 0, None
    for chunk in chunks:
        if type(chunk) is not dict or set(chunk) != {"source_start", "spikes"}:
            raise ValueError("Invalid source chunk fields")
        start = _integer(chunk["source_start"], "chunk source offset", 0)
        if start != seen:
            raise ValueError("Source chunks have a gap, overlap or repeated offset")
        _sequence(chunk["spikes"], "spike chunk", nonempty=True)
        if len(chunk["spikes"]) > max_chunk_size:
            raise ValueError("Source spike chunk exceeds its size bound")
        if seen + len(chunk["spikes"]) > declared_spike_count:
            raise ValueError("Source chunks exceed the declared unit spike count")
        spikes = tuple(_finite_float(value, "source spike") for value in chunk["spikes"])
        if any(right < left for left, right in zip(spikes, spikes[1:])):
            raise ValueError("Source spike chunk is not sorted")
        if last is not None and spikes[0] < last:
            raise ValueError("Spike ordering reverses across source chunks")
        for row, window in enumerate(windows):
            for field, output in (("history_edges_seconds", history),
                                  ("response_edges_seconds", response)):
                positions = [bisect_left(spikes, edge) for edge in window[field]]
                for index, (left, right) in enumerate(zip(positions, positions[1:])):
                    output[row][index] += right - left
        seen += len(spikes)
        last = spikes[-1]
    if seen != declared_spike_count:
        raise ValueError("Source chunks do not cover the declared unit spike count")
    return {
        "history_counts": history,
        "response_counts": response,
        "source_spikes_consumed": seen,
    }


def count_cluster(anchors_seconds, chunks, *, declared_spike_count,
                  max_chunk_size=MAX_CHUNK_SIZE):
    """Count one retained cluster, including an empty cluster with chunks=[].

    Each nonempty chunk is {source_start: contiguous zero-based offset,
    spikes: sorted finite list/tuple}. Equal-valued spikes are distinct deposited
    events, including equal values crossing a chunk boundary. Source offsets
    must refer to disjoint contiguous slices; replaying a chunk is refused.
    The chunk iterator is trusted orchestration, not participant-controlled code.
    """
    return _count_cluster(make_windows(anchors_seconds), chunks, declared_spike_count,
                          _chunk_limit(max_chunk_size))


def nominal_rates(counts, source_cluster_count):
    """Counts / (fixed retained cluster count * exact nominal 0.001 seconds).

    Represented absolute edge gaps never determine exposure. Empty retained
    clusters remain in source_cluster_count. Zero counts assert no deposited
    event, not verified neuronal silence.
    """
    _integer(source_cluster_count, "source cluster count", 1)
    _sequence(counts, "count rows", nonempty=True)
    rates = []
    for vector in counts:
        _sequence(vector, "count vector")
        if len(vector) != BIN_COUNT:
            raise ValueError("Count vector must have exactly 100 bins")
        row = []
        for count in vector:
            _integer(count, "deposited bin count", 0)
            try:
                value = float(Fraction(count * 1000, source_cluster_count))
            except OverflowError as error:
                raise ValueError("Nominal rate is outside finite float range") from error
            if not math.isfinite(value):
                raise ValueError("Nominal rate is outside finite float range")
            row.append(value)
        rates.append(row)
    return rates


def count_region(anchors_seconds, frozen_cluster_ids, cluster_streams, *, region,
                 max_chunk_size=MAX_CHUNK_SIZE):
    """Sum all and only supplied frozen named-region good+MUA source clusters.

    Call once per source asset: deposited cluster IDs are asset-scoped.
    A stream descriptor has exactly cluster_id, declared_spike_count and chunks.
    Membership is checked completely before any spike iterator is consumed.
    Eligibility/labels and membership authentication remain the caller's job;
    this function validates exact roster coverage, not biological provenance.
    """
    if type(region) is not str or region not in NAMED_REGIONS:
        raise ValueError("Unsupported or unassigned source region")
    _sequence(frozen_cluster_ids, "frozen cluster roster", nonempty=True)
    for cluster_id in frozen_cluster_ids:
        _integer(cluster_id, "source cluster ID")
    if len(set(frozen_cluster_ids)) != len(frozen_cluster_ids):
        raise ValueError("Duplicate frozen source cluster ID")
    _sequence(cluster_streams, "cluster stream descriptors")
    streams = {}
    for descriptor in cluster_streams:
        if type(descriptor) is not dict or set(descriptor) != {
                "cluster_id", "declared_spike_count", "chunks"}:
            raise ValueError("Invalid cluster stream descriptor fields")
        cluster_id = _integer(descriptor["cluster_id"], "source cluster ID")
        _integer(descriptor["declared_spike_count"], "declared spike count", 0)
        if cluster_id in streams:
            raise ValueError("Duplicate source cluster stream")
        streams[cluster_id] = descriptor
    if set(streams) != set(frozen_cluster_ids):
        raise ValueError("Source streams do not exactly cover frozen cluster membership")
    windows = make_windows(anchors_seconds)
    bound = _chunk_limit(max_chunk_size)
    history = _zero_counts(len(windows))
    response = _zero_counts(len(windows))
    consumed = 0
    for cluster_id in frozen_cluster_ids:
        descriptor = streams[cluster_id]
        counted = _count_cluster(windows, descriptor["chunks"],
                                 descriptor["declared_spike_count"], bound)
        consumed += counted["source_spikes_consumed"]
        for target, key in ((history, "history_counts"), (response, "response_counts")):
            for row, vector in enumerate(counted[key]):
                for index, count in enumerate(vector):
                    target[row][index] += count
    return {
        "schema": "neural099-independent-window-count-oracle/v1",
        "region": region,
        "source_cluster_ids": list(frozen_cluster_ids),
        "source_cluster_count": len(frozen_cluster_ids),
        "source_spikes_consumed": consumed,
        "trial_rows": len(windows),
        "history_counts": history,
        "response_counts": response,
        "history_nominal_rates": nominal_rates(history, len(frozen_cluster_ids)),
        "response_nominal_rates": nominal_rates(response, len(frozen_cluster_ids)),
        "bin_count": BIN_COUNT,
        "nominal_bin_seconds": 0.001,
        "counting": "bisect_left of every canonical absolute edge within each source chunk",
        "interval_convention": "left closed, right open; final edge excluded",
        "observation_coverage_verified": False,
        "input_authentication_performed": False,
        "empirical_readiness_claim": False,
    }
