"""Recorded-sample provenance for epochs, including reordered and padding segments.

These coordinates concern the released preprocessed recordings. They do not prove
raw-signal independence across the original continuous preprocessing filter.
"""
from dataclasses import dataclass
from .core import Refusal


@dataclass(frozen=True, order=True)
class Interval:
    recording: str
    start: int
    stop: int

    def __post_init__(self):
        if type(self.recording) is not str or not self.recording:
            raise Refusal('recording identity required')
        if type(self.start) is not int or type(self.stop) is not int or not 0 <= self.start < self.stop:
            raise Refusal('nonempty original sample interval required')


@dataclass(frozen=True)
class Piece:
    destination_start: int
    destination_stop: int
    original: Interval

    def __post_init__(self):
        if self.destination_start < 0 or self.destination_stop <= self.destination_start:
            raise Refusal('invalid destination interval')
        if self.destination_stop - self.destination_start != self.original.stop - self.original.start:
            raise Refusal('source/destination sample extents differ')


class SupportMap:
    def __init__(self, pieces):
        self.pieces = tuple(pieces)
        end = 0
        for piece in self.pieces:
            if piece.destination_start != end:
                raise Refusal('support map must exactly cover the complete sequence')
            end = piece.destination_stop
        if not end:
            raise Refusal('empty support map')
        self.samples = end

    @classmethod
    def original(cls, identity, samples):
        return cls((Piece(0, samples, Interval(identity, 0, samples)),))

    def epoch(self, start, stop):
        if type(start) is not int or type(stop) is not int or not 0 <= start < stop <= self.samples:
            raise Refusal('epoch extends beyond complete mapped recording')
        result = []
        for piece in self.pieces:
            a, b = max(start, piece.destination_start), min(stop, piece.destination_stop)
            if a < b:
                offset = piece.original.start - piece.destination_start
                result.append(Interval(piece.original.recording, a + offset, b + offset))
        return tuple(result)


def overlap(a, b):
    return a.recording == b.recording and max(a.start, b.start) < min(a.stop, b.stop)


def disjoint(a, b):
    return not any(overlap(x, y) for x in a for y in b)


def purge_training(train_ids, train_supports, all_test_supports):
    """Preserve the fixed evaluation set; discard overlapping training support only."""
    test = tuple(x for sample in all_test_supports for x in sample)
    return tuple(i for i in train_ids if disjoint(train_supports[i], test))


def require_disjoint(train_ids, train_supports, test_supports):
    test = tuple(x for sample in test_supports for x in sample)
    if any(not disjoint(train_supports[i], test) for i in train_ids):
        raise Refusal('same released recording samples cross the train/test boundary')


def reorder_plan(random_events, target_events, *, recording, sample_count,
                 segment_samples, padding_samples, stop_at_exhaustion):
    """Return a source-owned sample-copy plan; never open a recording here.

    Each input event is (sample_relative_to_recording_start, event_code).
    Plans preserve all event codes supplied by the selected scientific route.
    """
    if segment_samples <= 0 or padding_samples <= 0 or sample_count < 2 * padding_samples:
        raise Refusal('invalid source reordering extents')
    available = {}
    for index, (sample, code) in enumerate(random_events):
        if type(sample) is not int or not 0 <= sample < sample_count:
            raise Refusal('event outside recording')
        if sample + segment_samples > sample_count:
            raise Refusal('source segment extends beyond recording')
        available.setdefault(code, []).append((index, sample))
    positions = {code: 0 for code in available}
    pieces = [Piece(0, padding_samples, Interval(recording, 0, padding_samples))]
    events, selected = [], []
    destination = padding_samples
    for _, code in target_events:
        index = positions.get(code, 0)
        candidates = available.get(code, ())
        if index == len(candidates):
            if stop_at_exhaustion:
                break
            continue
        origin_index, origin_sample = candidates[index]
        positions[code] = index + 1
        pieces.append(Piece(destination, destination + segment_samples,
                            Interval(recording, origin_sample, origin_sample + segment_samples)))
        events.append((destination, code))
        selected.append(origin_index)
        destination += segment_samples
    pieces.append(Piece(destination, destination + padding_samples,
                        Interval(recording, sample_count - padding_samples, sample_count)))
    if not events:
        raise Refusal('empty empirical-null sequence')
    return SupportMap(pieces), tuple(events), tuple(selected)
