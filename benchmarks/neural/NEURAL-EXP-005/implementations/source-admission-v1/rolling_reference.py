"""Exact-byte rolling preparation for the pinned Helsinki source reader.

This is an optional assessor-side entrypoint, not a source admission mechanism.
The unchanged protocol remains the authority for packets, references and generic
readers. All public bytes/identities stay unchanged; only this implementation and
its private cache have a new identity. Never pass this cache to a participant.
"""
from __future__ import annotations

import __future__
from collections import OrderedDict
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import stat
from types import CodeType

PROTOCOL_SHA256 = "9ca5ae8f2c1085503b8775d9598c7a495ed532457fb917d4a38654144957add5"
ADAPTER_SHA256 = "34a850b2bdb97b0af71bd759a88a19e9552cce852958af58474746b3e56a6c58"
FS = 256
DEFAULT_CACHE_BYTES = 8 * 1024 * 1024
MAX_CACHE_BYTES = 64 * 1024 * 1024
PROTOCOL_CALLS = (
    "canonical_bytes", "digest", "_finite", "_binding", "_payload",
    "_validate_description", "_validate_key", "_seconds", "prepare_reference",
    "Reference.__init__", "fold_map", "_fields", "_text", "_sha", "_positive_int",
)
ADAPTER_CALLS = (
    "require", "read_calibrated_record", "IntervalReader.__call__",
    "IntervalReader.clear", "SourceCorpus._lookup", "SourceCorpus.read_samples",
)


def _resolve(root, path):
    for part in path.split("."):
        root = getattr(root, part)
    return root


def _pinned_code(module, expected, paths):
    """Bounded body and complete-code check, not hostile-runtime isolation.

    All checked functions have no defaults. Rejecting a replacement delegates
    the public call to the original generic entrypoint. Code equality includes
    constants/nested code, not only bytecode instructions. The future flag is
    inherited by the existing dynamic source loader and must be preserved.
    """
    path = Path(module.__file__)
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "rb") as handle:
        before = os.fstat(handle.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > 1024 * 1024:
            return None
        body = handle.read(1024 * 1024 + 1)
        after = os.fstat(handle.fileno())
    fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
    if (any(getattr(before, f) != getattr(after, f) for f in fields)
            or len(body) != before.st_size or hashlib.sha256(body).hexdigest() != expected):
        return None
    first = _resolve(module, paths[0])
    flags = first.__code__.co_flags & __future__.annotations.compiler_flag
    compiled = compile(body, str(path), "exec", flags=flags, dont_inherit=True)
    snapshots = []
    for dotted in paths:
        code = compiled
        for part in dotted.split("."):
            candidates = [v for v in code.co_consts if isinstance(v, CodeType) and v.co_name == part]
            if len(candidates) != 1:
                return None
            code = candidates[0]
        function = _resolve(module, dotted)
        if (getattr(function, "__code__", None) != code
                or function.__globals__ is not module.__dict__
                or function.__defaults__ is not None or function.__kwdefaults__ is not None):
            return None
        snapshots.append((module, dotted, function, function.__code__))
    return snapshots


def _bound(value, owner, function):
    return getattr(value, "__self__", None) is owner and getattr(value, "__func__", None) is function


def _eligible(protocol, adapter, description, read_samples):
    """Return an exact reader plus callable snapshots, or use generic semantics."""
    if adapter is None or type(description) is not dict:
        return None
    try:
        owner = read_samples.__self__
        if (type(owner) is not adapter.SourceCorpus
                or not _bound(read_samples, owner, adapter.SourceCorpus.read_samples)
                or not _bound(owner.read_samples, owner, adapter.SourceCorpus.read_samples)
                or type(owner.reader) is not adapter.IntervalReader
                or not _bound(owner._lookup, owner, adapter.SourceCorpus._lookup)
                or not _bound(owner.reader.lookup, owner, adapter.SourceCorpus._lookup)
                or tuple("-".join(p) for p in owner.reader.montage) != protocol.MONTAGE
                or adapter.FS != FS or adapter.MAX_WINDOW_SAMPLES != 30 * FS
                or owner.sources is not adapter.load_sources()
                or owner.sources.current is not protocol or owner._closed):
            return None
        records = description["recordings"]
        if (type(records) is not list or any(type(r) is not dict for r in records)
                or any(type(r["sample_rate"]) is not dict for r in records)):
            return None
        if {r["recording_id"] for r in records} != set(adapter.RECORD_IDS):
            return None
        for record in records:
            asset, header = owner._lookup(record["recording_id"])
            if (record["sample_rate"] != {"num": FS, "den": 1}
                    or record["units"] != "uV" or record["sample_count"] != FS * header.records
                    or record["eeg_sha256"] != asset.sha256):
                return None
        p_calls = _pinned_code(protocol, PROTOCOL_SHA256, PROTOCOL_CALLS)
        a_calls = _pinned_code(adapter, ADAPTER_SHA256, ADAPTER_CALLS)
        if p_calls is None or a_calls is None:
            return None
        return owner, p_calls + a_calls
    except (AttributeError, KeyError, TypeError, OSError, ValueError):
        return None


class _Fragment:
    """A complete second encoded by the actual canonical encoder, row-major."""
    def __init__(self, protocol, values):
        if not isinstance(values, (list, tuple)) or len(values) != FS:
            raise protocol.ContractError("reader must return exactly the requested causal sample interval")
        rows = []
        for row in values:
            if not isinstance(row, (list, tuple)) or len(row) != 18:
                raise protocol.ContractError("every sample needs exactly the ordered 18 bipolar values")
            for value in row:
                protocol._finite(value, "EEG sample")
            rows.append(list(row))
        self.body = protocol.canonical_bytes(rows)[1:-1]
        # Validated rows contain only numeric tokens: ']' can only end a row.
        self.ends = tuple(i + 1 for i, value in enumerate(self.body) if value == 93)
        if len(self.ends) != FS:
            raise protocol.ContractError("canonical second has an unexpected row layout")

    def interval(self, first, stop):
        if not (type(first) is int and type(stop) is int and 0 <= first < stop <= FS):
            raise ValueError("fragment interval must be inside one source second")
        start = 0 if first == 0 else self.ends[first - 1] + 1
        return memoryview(self.body)[start:self.ends[stop - 1]]


class _RollingSamples:
    """Private bounded fragments tied to one exact reader and immutable sources.

    SourceCorpus admission, pinned dependency closure and an unmodified trusted
    Python process remain prerequisites. This does not authenticate hand-built
    SourceCorpus lookalikes or defend against arbitrary process memory writes.
    """
    def __init__(self, protocol, adapter, owner, snapshots, cache_bytes):
        self.protocol, self.adapter, self.owner = protocol, adapter, owner
        self.reader = owner.reader
        self.montage = deepcopy(self.reader.montage)
        self.sources, self.corpus = owner.sources, owner._corpus
        self.lineage = deepcopy(owner.source_lineage)
        self.snapshots = tuple(snapshots)
        self.load_sources = adapter.load_sources
        self.cache_bytes = cache_bytes
        self.cache, self.identities = OrderedDict(), {}
        self.retained = 0
        self.stats = dict(cache_hits=0, cache_misses=0, serialized_scalars=0,
                          peak_cached_payload_bytes=0, peak_cached_seconds=0,
                          windows=0, sha256_payload_bytes=0)

    def clear(self):
        """Clear fragments, retaining source identity guards across clock resets."""
        self.cache.clear()
        self.retained = 0

    def _guard(self, rid):
        a, p, owner = self.adapter, self.protocol, self.owner
        a.require(owner.reader is self.reader and type(self.reader) is a.IntervalReader
                  and type(owner) is a.SourceCorpus and not owner._closed
                  and owner._corpus is self.corpus and owner.sources is self.sources
                  and self.sources.current is p and a.load_sources is self.load_sources
                  and a.FS == FS and a.MAX_WINDOW_SAMPLES == 30 * FS
                  and self.reader.montage == self.montage
                  and tuple("-".join(pair) for pair in self.montage) == p.MONTAGE
                  and _bound(owner._lookup, owner, a.SourceCorpus._lookup)
                  and _bound(owner.read_samples, owner, a.SourceCorpus.read_samples)
                  and _bound(self.reader.lookup, owner, a.SourceCorpus._lookup),
                  "rolling reader context changed")
        for module, path, function, code in self.snapshots:
            a.require(_resolve(module, path) is function and function.__code__ is code
                      and function.__globals__ is module.__dict__
                      and function.__defaults__ is None and function.__kwdefaults__ is None,
                      "rolling source callable changed")
        a.require(owner.source_lineage == self.lineage, "rolling source lineage changed")
        asset, header = owner._lookup(rid)
        identity = (deepcopy(asset.identity), asset.sha256, deepcopy(header))
        if rid in self.identities:
            a.require(self.identities[rid] == identity, "rolling recording descriptor changed")
        else:
            self.identities[rid] = identity
        asset.check_unchanged()
        return asset, header

    def _fragment(self, rid, second):
        key = (rid, second)
        fragment = self.cache.pop(key, None)
        if fragment is not None:
            self.stats["cache_hits"] += 1
            self.cache[key] = fragment
            return fragment
        self.stats["cache_misses"] += 1
        fragment = _Fragment(self.protocol, self.reader(rid, second * FS, (second + 1) * FS))
        self.stats["serialized_scalars"] += FS * 18
        size = len(fragment.body)
        if size <= self.cache_bytes:
            while self.cache and (len(self.cache) >= 31 or self.retained + size > self.cache_bytes):
                _, old = self.cache.popitem(last=False)
                self.retained -= len(old.body)
            self.cache[key] = fragment
            self.retained += size
            self.stats["peak_cached_payload_bytes"] = max(self.stats["peak_cached_payload_bytes"], self.retained)
            self.stats["peak_cached_seconds"] = max(self.stats["peak_cached_seconds"], len(self.cache))
        return fragment

    def sample_chunks(self, rid, start, stop):
        """Yield every original sample byte, including brackets and separators.

        Iteration must be exhausted before its digest can be used. The final
        guard executes on cache hits too; any exception discards the partial SHA.
        """
        _, header = self._guard(rid)
        self.adapter.require(type(start) is int and type(stop) is int
                             and 0 <= start < stop <= header.records * FS
                             and stop - start <= 30 * FS, "invalid rolling causal sample interval")
        yield b"["
        for second in range(start // FS, (stop - 1) // FS + 1):
            if second != start // FS:
                yield b","
            fragment = self._fragment(rid, second)
            yield fragment.interval(max(0, start - second * FS), min(FS, stop - second * FS))
        yield b"]"
        self._guard(rid)

    def payload_chunks(self, description, case_key, record, k, fold):
        p = self.protocol
        if type(k) is not int or k not in range(29, p._seconds(record)):
            raise p.ContractError("timestamp outside exact primary support")
        if record["sample_rate"] != {"num": FS, "den": 1}:
            raise p.ContractError("rolling path requires admitted 256 Hz; use generic preparation")
        metadata = p._binding(description, case_key, record["recording_id"], k, fold)
        metadata.update(schema="helsinki-causal-packet-v1", montage=list(p.MONTAGE),
                        units=record["units"], duration_seconds=30,
                        prediction_interval_seconds=[29, 30],
                        sample_clock={"first_tick": 0, "step_ticks": 1, "ticks_per_second": FS},
                        quality_flags=record["quality_flags"][k - 29:k + 1],
                        detector_sha256=description["detector_sha256"])
        yield b"{"
        for index, key in enumerate(sorted((*metadata, "samples"))):
            if index:
                yield b","
            yield p.canonical_bytes(key)
            yield b":"
            if key == "samples":
                yield from self.sample_chunks(record["recording_id"], (k - 29) * FS, (k + 1) * FS)
            else:
                yield p.canonical_bytes(metadata[key])
        yield b"}"

    def payload_digest(self, description, case_key, record, k, fold):
        hasher = hashlib.sha256()
        count = 0
        for chunk in self.payload_chunks(description, case_key, record, k, fold):
            hasher.update(chunk)
            count += len(chunk)
        self.stats["windows"] += 1
        self.stats["sha256_payload_bytes"] += count
        return hasher.hexdigest()


def prepare_reference(protocol, description, read_samples, case_key, *,
                      source_adapter=None, cache_bytes=DEFAULT_CACHE_BYTES, statistics=None):
    """Return the original Reference, with unchanged fields and full support.

    Pass the actual dynamically loaded protocol and source_adapter modules from
    the admitted owner process. Unsupported readers/calibration/rates use the
    unchanged generic function. A changed context after fast-path activation
    raises instead of using stale fragments. `statistics`, if supplied, is an
    assessor-private dict and is never inserted into any public object.
    """
    if type(cache_bytes) is not int or not 0 <= cache_bytes <= MAX_CACHE_BYTES:
        raise ValueError("cache_bytes must be an integer from 0 through 64 MiB")
    if statistics is not None and type(statistics) is not dict:
        raise TypeError("statistics must be an assessor-private dict")
    eligible = _eligible(protocol, source_adapter, description, read_samples)
    if eligible is None:
        result = protocol.prepare_reference(description, read_samples, case_key)
        if statistics is not None:
            statistics.update(path="unchanged_generic")
        return result
    protocol._validate_key(case_key)
    description = deepcopy(description)
    records, folds = protocol._validate_description(description)
    owner, snapshots = eligible
    rolling = _RollingSamples(protocol, source_adapter, owner, snapshots, cache_bytes)
    hashes = {}
    for rid in sorted(records):
        record = records[rid]
        hashes[rid] = [rolling.payload_digest(description, case_key, record, k, folds[rid])
                       for k in range(29, protocol._seconds(record))]
    document = deepcopy(description)
    document.update(schema=protocol.REFERENCE_SCHEMA, input_sha256_by_recording=hashes,
                    case_key_commitment=hashlib.sha256(case_key).hexdigest())
    result = protocol.Reference(document, case_key)
    if statistics is not None:
        statistics.update(path="pinned_source_rolling", **rolling.stats)
    return result
