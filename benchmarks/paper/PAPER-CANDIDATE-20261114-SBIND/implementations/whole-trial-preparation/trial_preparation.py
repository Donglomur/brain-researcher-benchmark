"""Prospective full-census SBIND whole-trial preparation, without numerical transforms."""
from __future__ import annotations

from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import dataclass
import hashlib
import json
import re

TASK = "PAPER-CANDIDATE-20261114-SBIND"
COUNTS = {"WFCI1": 248, "WFCI2": 412}
SHAPE = (1, 128, 128)
MAX_METADATA = 2 * 1024 * 1024


class AdmissionError(ValueError):
    pass


def _require(ok, message):
    if not ok:
        raise AdmissionError(message)


def _hash(value):
    _require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value), "literal SHA256 required")
    return value


def _name(value):
    _require(isinstance(value, str) and 0 < len(value) <= 128 and
             all(33 <= ord(c) <= 126 for c in value), "nonempty printable ASCII identity required")
    return value


def _keys(value, keys):
    _require(type(value) is dict and set(value) == set(keys), "unexpected object members")


def _integer(value, low, high):
    _require(type(value) is int and low <= value <= high, "invalid integer")
    return value


def _load(raw, expected):
    _hash(expected)
    _require(type(raw) is bytes and 0 < len(raw) <= MAX_METADATA, "bounded metadata bytes required")
    _require(hashlib.sha256(raw).hexdigest() == expected, "metadata identity mismatch")
    def pairs(items):
        out = {}
        for key, value in items:
            _require(key not in out, "duplicate JSON key")
            out[key] = value
        return out
    def bad_constant(value):
        raise AdmissionError("nonfinite JSON constant")
    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=bad_constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise AdmissionError("invalid JSON") from exc


@dataclass(frozen=True)
class Span:
    trial_id: str
    source_start: int
    length: int
    local_start: int


@dataclass(frozen=True)
class Fold:
    number: int
    train: tuple[Span, ...]
    validation: tuple[Span, ...]
    test: tuple[Span, ...]


@dataclass(frozen=True)
class Assay:
    assay_id: str
    source_sha256: str
    representation_sha256: str
    channels: tuple[str, ...]
    total_frames: int
    trials: tuple[tuple[str, int, int], ...]
    folds: tuple[Fold, ...]


@dataclass(frozen=True)
class Protocol:
    census_sha256: str
    split_sha256: str
    assays: tuple[Assay, ...]


def compile_protocol(census_bytes, split_bytes, *, census_sha256, split_sha256):
    """Validate both complete assays and all five folds before returning any plan.

    The expected digests must be independently frozen by the trusted operator.
    This function never chooses a fold assignment or invents an authentic census.
    """
    census = _load(census_bytes, census_sha256)
    split = _load(split_bytes, split_sha256)
    _keys(census, ("schema", "task_id", "assays"))
    _keys(split, ("schema", "task_id", "census_sha256", "assays"))
    _require(census["schema"] == "sbind-complete-widefield-census-v1" and census["task_id"] == TASK,
             "wrong census contract")
    _require(split["schema"] == "sbind-prospective-whole-trial-folds-v1" and split["task_id"] == TASK,
             "wrong prospective split contract")
    _require(split["census_sha256"] == census_sha256, "split belongs to another census")
    for value in (census["assays"], split["assays"]):
        _require(type(value) is list and len(value) == 2, "both complete assays required")
        _require([a.get("assay_id") if type(a) is dict else None for a in value] == list(COUNTS),
                 "assay identity/order mismatch")
    assays = []
    for source, assignment in zip(census["assays"], split["assays"]):
        _keys(source, ("assay_id", "source_sha256", "representation_sha256", "neural_shape",
                       "behavior_channels", "trials"))
        _keys(assignment, ("assay_id", "folds"))
        assay_id = source["assay_id"]
        _hash(source["source_sha256"]); _hash(source["representation_sha256"])
        _require(source["neural_shape"] == list(SHAPE) and
                 all(type(x) is int for x in source["neural_shape"]), "complete neural field required")
        channels = source["behavior_channels"]
        _require(type(channels) is list and 0 < len(channels) <= 4096, "complete declared channels required")
        channels = tuple(_name(x) for x in channels)
        _require(len(set(channels)) == len(channels), "duplicate behavior channel")
        rows = source["trials"]
        _require(type(rows) is list and len(rows) == COUNTS[assay_id], "complete trial count required")
        trials = []; seen = set(); cursor = 0
        for row in rows:
            _keys(row, ("trial_id", "source_start", "length"))
            trial_id = _name(row["trial_id"])
            _require(trial_id not in seen, "duplicate trial identity")
            seen.add(trial_id)
            start = _integer(row["source_start"], 0, (1 << 63) - 1)
            length = _integer(row["length"], 1, (1 << 63) - 1)
            _require(start == cursor and cursor + length <= (1 << 63) - 1,
                     "missing, reordered or overlapping source frame extent")
            trials.append((trial_id, start, length)); cursor += length
        folds = assignment["folds"]
        _require(type(folds) is list and len(folds) == 5, "all five frozen folds required")
        compiled = []; test_counts = dict.fromkeys(seen, 0)
        for number, fold in enumerate(folds):
            _keys(fold, ("fold", "train", "validation", "test"))
            _require(type(fold["fold"]) is int and fold["fold"] == number, "fold identity/order mismatch")
            owned = set(); spans = {}
            for role in ("train", "validation", "test"):
                ids = fold[role]
                _require(type(ids) is list and len(ids) > 0, "each role must contain whole trials")
                ids = [_name(x) for x in ids]
                _require(len(set(ids)) == len(ids), "duplicate role trial")
                ids = set(ids)
                _require(ids <= seen and not (ids & owned), "unknown or cross-role trial")
                owned |= ids
                local = 0; selected = []
                for trial_id, start, length in trials:
                    if trial_id in ids:
                        selected.append(Span(trial_id, start, length, local)); local += length
                        if role == "test": test_counts[trial_id] += 1
                spans[role] = tuple(selected)
            _require(owned == seen, "incomplete fold population")
            compiled.append(Fold(number, **spans))
        _require(set(test_counts.values()) == {1}, "each trial must be tested once across all folds")
        assays.append(Assay(assay_id, source["source_sha256"], source["representation_sha256"],
                            channels, cursor, tuple(trials), tuple(compiled)))
    return Protocol(census_sha256, split_sha256, tuple(assays))


@dataclass(frozen=True)
class SourceRows:
    """Trusted-loader result: identities are assertions, not proof of body authentication.

    rows[i] is (complete neural field, all declared behavior channels). The loader
    must authenticate the actual prepared artifact and check numeric shape/type;
    this indexing repair deliberately neither normalizes nor copies those values.
    """
    source_sha256: str
    representation_sha256: str
    neural_shape: tuple[int, ...]
    behavior_channels: tuple[str, ...]
    rows: Sequence


@dataclass(frozen=True)
class Frame:
    source_index: int
    trial_id: str
    trial_offset: int
    reset: bool
    neural: object
    behavior: object


class TrialView(Sequence):
    """A lazy ordered view. Payload objects are shared, not a sandbox or immutable copy."""
    def __init__(self, rows, spans):
        self._rows = rows
        self.spans = spans
        self._starts = tuple(s.local_start for s in spans)
        self._length = sum(s.length for s in spans)

    def __len__(self):
        return self._length

    def __getitem__(self, index):
        if type(index) is not int:
            raise TypeError("integer frame index required; no implicit bulk copy")
        if index < 0:
            index += self._length
        if index < 0 or index >= self._length:
            raise IndexError(index)
        span = self.spans[bisect_right(self._starts, index) - 1]
        offset = index - span.local_start
        source_index = span.source_start + offset
        try:
            row = self._rows[source_index]
        except IndexError as exc:
            # Sequence iteration interprets IndexError as normal exhaustion.
            # This index is within the admitted view: missing backing data is
            # an incomplete source, not the end of the selected trial support.
            raise AdmissionError("source row missing within admitted frame extent") from exc
        _require(isinstance(row, (tuple, list)) and len(row) == 2, "source row must contain neural and behavior")
        return Frame(source_index, span.trial_id, offset, offset == 0, row[0], row[1])

    def reset_mask(self):
        """Yield 0 at every true trial start and 1 otherwise; no fixed stride."""
        for span in self.spans:
            yield 0
            for _ in range(span.length - 1):
                yield 1


def prepare_fold(census_bytes, split_bytes, *, census_sha256, split_sha256,
                 assay_id, fold, source_loader):
    """Compile complete public support before one trusted full-assay loader call.

    The loader receives the exact admitted Assay descriptor, including full row
    extent and provenance identities. It must return SourceRows. This is a data
    preparation API, not a scorer, model executor, numerical transform or grader.
    """
    protocol = compile_protocol(census_bytes, split_bytes, census_sha256=census_sha256,
                                split_sha256=split_sha256)
    _require(assay_id in COUNTS, "unknown assay")
    _integer(fold, 0, 4)
    assay = next(a for a in protocol.assays if a.assay_id == assay_id)
    source = source_loader(assay)
    _require(isinstance(source, SourceRows), "trusted SourceRows required")
    _require(source.source_sha256 == assay.source_sha256 and
             source.representation_sha256 == assay.representation_sha256,
             "source/representation receipt mismatch")
    _require(source.neural_shape == SHAPE and source.behavior_channels == assay.channels,
             "representation shape/channel mismatch")
    _require(isinstance(source.rows, Sequence) and len(source.rows) == assay.total_frames,
             "full source row extent required")
    chosen = assay.folds[fold]
    return {role: TrialView(source.rows, getattr(chosen, role))
            for role in ("train", "validation", "test")}
