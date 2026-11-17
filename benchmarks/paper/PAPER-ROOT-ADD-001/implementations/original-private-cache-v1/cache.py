"""Trusted-host private file/body and selected compact-bundle caches.

This module performs ordinary bounded file reads, not native isolation. It is for
an explicitly nonhostile host: a stable read-only authenticated file may be read
again without another full digest. Every actual reread and EOF probe is charged.
No private cache identity is a public request identity. Cache hits are exact
selected-input reuse, never a claim of measured campaign-wide throughput.

Caller-owned returned arrays/bytes have independent lifetimes. Logical admissions
cover this store and active bundle assembly, not kernel/Python RSS enforcement or
unbounded retention by callers. No file descriptors are retained between calls.
"""
from __future__ import annotations

from collections import OrderedDict
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import io
import math
import os
from pathlib import Path
import stat
import struct
import sys
import types

import numpy as np


BUNDLE_SHA256 = 'a54bdb02d3d9d0be74bafaab3503175a6eaf867ee5299b97c5983bc2ea30a8a7'
_path = Path(__file__).resolve().parent.parent / 'original-compact-bundles-v1/bundle.py'
with _path.open('rb') as _stream:
    _code = _stream.read(32769)
if len(_code) != 14088 or hashlib.sha256(_code).hexdigest() != BUNDLE_SHA256:
    raise ValueError('Exact reviewed compact-bundle dependency required')
_name = '_language_compact_bundle_a54bdb02'
if _name in sys.modules:
    B = sys.modules[_name]
    if (type(B) is not types.ModuleType or getattr(B, '_authenticated_source_sha256', None) != BUNDLE_SHA256
            or getattr(B, '__file__', None) != str(_path)):
        raise ValueError('Conflicting trusted-host compact-bundle module identity')
else:
    B = types.ModuleType(_name)
    B.__file__ = str(_path)
    B.__package__ = ''
    sys.modules[_name] = B
    try:
        exec(compile(_code, str(_path), 'exec', dont_inherit=True), B.__dict__)
        B._authenticated_source_sha256 = BUNDLE_SHA256
    except BaseException:
        del sys.modules[_name]
        raise
V = B.V
del _path, _stream, _code, _name

MAX_COUNTER = 2**63-1
MAX_OBJECTS = 262144
ENTRY_RESERVE = 4096


def need(ok, message):
    if not ok:
        raise ValueError(message)


def integer(value, low=0, high=MAX_COUNTER):
    return type(value) is int and low <= value <= high


def _add(owner, name, amount=1):
    current = getattr(owner, name)
    need(integer(amount) and integer(current) and current+amount <= MAX_COUNTER,
         'Finite monotonic private counter')
    setattr(owner, name, current+amount)


def _spec_snapshot(value):
    need(type(value) is V.ObjectSpec, 'Exact typed object specification')
    for name, length in (('object_id', 40), ('relative_path', 52), ('sha256', 64)):
        item = getattr(value, name)
        need(type(item) is str and len(item) == length, 'Bounded primitive object identity')
    need(type(value.role) is str and value.role in ('features', 'qid', 'time', 'responses')
         and type(value.dtype) is str and value.dtype in ('<f8', '<i8')
         and integer(value.bytes, 1, V.MAX_OBJECT_BYTES) and type(value.fortran_order) is bool,
         'Bounded primitive object metadata')
    need(type(value.shape) is tuple and 1 <= len(value.shape) <= 2
         and all(integer(n, 1, V.MAX_ROWS) for n in value.shape), 'Bounded primitive shape before copy')
    return V.ObjectSpec(value.object_id, value.relative_path, value.role, value.bytes,
                        value.sha256, value.shape, value.dtype, value.fortran_order)


@dataclass(frozen=True)
class _Record:
    spec: object
    stamp: tuple
    header_end: int
    map_raw: bytes | None


class FileStore:
    """One finite immutable-manifest cache, optionally hosting one BundleCache.

    load() returns a fresh array view with immutable bytes backing. Cached map
    shape metadata is never returned as shared authority. Nonmap bodies are not
    retained: a later load performs and charges a stable authenticated reread.
    authenticate() returns operator-private immutable identity bytes, not an
    internal mutable record. Any failed operation poisons the store.
    """
    def __init__(self, root, specs, *, read_limit, working_limit, max_objects):
        need(integer(read_limit, 1) and integer(working_limit, 1, B.MAX_WORKING_BYTES)
             and integer(max_objects, 1, MAX_OBJECTS), 'Finite private-store allocations')
        need(type(specs) in (list, tuple) and 0 < len(specs) <= max_objects
             and len(specs)*8192 <= working_limit, 'Bounded concrete manifest before snapshot')
        root = Path(root).absolute()
        need(not any(p.is_symlink() for p in (root, *root.parents)) and root.is_dir(),
             'Ordinary private store root')
        frozen = tuple(_spec_snapshot(s) for s in specs)
        need(len({s.object_id for s in frozen}) == len(frozen)
             and len({s.relative_path for s in frozen}) == len(frozen), 'Unique private objects and paths')
        metadata = sum(V.SPEC_RESERVE+len(V.encoded(s.private_descriptor())) for s in frozen)
        need(metadata <= working_limit, 'Complete private manifest metadata admission')
        self.root, self._specs, self._records = root, {s.object_id: s for s in frozen}, {}
        self.read_limit, self.working_limit, self.max_objects = read_limit, working_limit, max_objects
        self.retained_metadata_bytes, self.retained_map_bytes = metadata, 0
        self.bundle_payload_bytes = self.bundle_metadata_bytes = self.temporary_working_bytes = 0
        self.peak_working_admission = max(metadata, len(frozen)*8192)
        self.read_charged = self.bytes_read = self.auth_bytes_read = self.reread_bytes_read = 0
        self.full_authentications = self.rereads = self.map_hits = self.stability_checks = 0
        self.failed = False
        self._bundle_owner = None

    def _total(self):
        return (self.retained_metadata_bytes + self.retained_map_bytes
                + self.bundle_payload_bytes + self.bundle_metadata_bytes + self.temporary_working_bytes)

    def _admit(self, extra):
        need(not self.failed and integer(extra) and self._total()+extra <= self.working_limit,
             'Joint store/maps/bundles/live-temporary working allocation')
        self.peak_working_admission = max(self.peak_working_admission, self._total()+extra)

    @contextmanager
    def _temporary(self, amount):
        self._admit(amount)
        self.temporary_working_bytes += amount
        try:
            yield
        finally:
            self.temporary_working_bytes -= amount

    def _read_admission(self, amount):
        need(not self.failed and integer(amount) and self.read_charged+amount <= self.read_limit,
             'Cumulative logical read plus EOF allocation before body I/O')

    def _spec(self, object_id):
        need(type(object_id) is str and len(object_id) == 40 and object_id in self._specs,
             'Declared private object identity')
        return self._specs[object_id]

    def _path(self, spec):
        path = self.root / spec.relative_path
        need(not any(p.is_symlink() for p in (path, *path.parents)), 'No private object symlink')
        return path

    def _stable(self, record):
        path = self._path(record.spec)
        current = path.lstat()
        _add(self, 'stability_checks')
        need(stat.S_ISREG(current.st_mode) and current.st_nlink == 1
             and current.st_mode & 0o222 == 0 and V._stamp(current) == record.stamp,
             'Authenticated ordinary read-only file identity changed')

    def stable(self, object_id):
        try:
            need(not self.failed and object_id in self._records, 'Live authenticated private object required')
            self._stable(self._records[object_id])
        except BaseException:
            self.failed = True
            raise

    def _parse(self, raw, spec):
        stream = io.BytesIO(raw)
        version = np.lib.format.read_magic(stream)
        readers = {(1, 0): np.lib.format.read_array_header_1_0, (2, 0): np.lib.format.read_array_header_2_0}
        need(version in readers, 'Primitive NPY1/2 object only')
        shape, fortran, dtype = readers[version](stream, max_header_size=V.NPY_HEADER_LIMIT)
        need(tuple(shape) == spec.shape and fortran is spec.fortran_order and dtype.str == spec.dtype
             and dtype.fields is None and dtype.subdtype is None and not dtype.hasobject
             and stream.tell()+math.prod(shape)*dtype.itemsize == len(raw),
             'Exact declared primitive NPY extent/dtype/shape/order')
        offset = stream.tell()
        value = np.frombuffer(raw, dtype=dtype, offset=offset).reshape(shape, order='F' if fortran else 'C')
        need(np.isfinite(value).all(), 'Finite primitive private object')
        if spec.role == 'qid':
            need(np.all(value == np.floor(value)) and np.all(np.abs(value) < 2**53)
                 and np.all(value < 99990), 'Original represented qid domain')
        if spec.role == 'time':
            need(np.all(value >= 0) and np.all(value < V.MAX_ROWS)
                 and np.all(value[1:] > value[:-1]), 'Original strict ordered time domain')
        return offset, value

    def _body(self, spec, previous):
        # Every full response load is one actual read, cold or warm, including
        # one explicit EOF probe. First loads do not authenticate then reread.
        self._read_admission(spec.bytes+1)
        with self._temporary(3*spec.bytes+V.CACHE_RESERVE+8192):
            path = self._path(spec)
            fd = None
            try:
                fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
                with os.fdopen(fd, 'rb', buffering=0) as stream:
                    fd = None
                    before = os.fstat(stream.fileno())
                    need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                         and before.st_mode & 0o222 == 0 and before.st_size == spec.bytes,
                         'Exact ordinary single-link read-only object')
                    if previous is not None:
                        need(V._stamp(before) == previous.stamp, 'Reread starts at authenticated identity')
                    _add(self, 'read_charged', spec.bytes+1)
                    raw = stream.read(spec.bytes+1)
                    _add(self, 'bytes_read', len(raw))
                    _add(self, 'auth_bytes_read' if previous is None else 'reread_bytes_read', len(raw))
                    after, named = os.fstat(stream.fileno()), path.lstat()
                    need(V._stamp(before) == V._stamp(after) == V._stamp(named),
                         'Private file identity stable before/after read and named lookup')
            finally:
                if fd is not None:
                    os.close(fd)
            need(len(raw) == spec.bytes, 'Exact object body; no short read or suffix')
            if previous is None:
                need(hashlib.sha256(raw).hexdigest() == spec.sha256, 'First full object authentication')
            offset, value = self._parse(raw, spec)
            if previous is not None:
                need(offset == previous.header_end, 'Stable authenticated NPY header extent')
                _add(self, 'rereads')
            else:
                keep = raw if spec.role in ('qid', 'time') else None
                extra = V.CACHE_RESERVE+(len(raw) if keep is not None else 0)
                self._admit(extra)
                self._records[spec.object_id] = _Record(spec, V._stamp(before), offset, keep)
                self.retained_metadata_bytes += V.CACHE_RESERVE
                self.retained_map_bytes += len(raw) if keep is not None else 0
                _add(self, 'full_authentications')
            return value

    def load(self, object_id):
        try:
            need(not self.failed, 'Nonfailed store required')
            spec = self._spec(object_id)
            previous = self._records.get(object_id)
            if previous is not None:
                self._stable(previous)
                if previous.map_raw is not None:
                    self._admit(8192)
                    _add(self, 'map_hits')
                    return np.frombuffer(previous.map_raw, dtype=spec.dtype,
                                         offset=previous.header_end).reshape(spec.shape,
                                             order='F' if spec.fortran_order else 'C')
            return self._body(spec, previous)
        except BaseException:
            self.failed = True
            raise

    def authenticate(self, object_id):
        try:
            need(not self.failed, 'Nonfailed store required')
            spec = self._spec(object_id)
            if object_id in self._records:
                self._stable(self._records[object_id])
            else:
                self._body(spec, None)
            with self._temporary(4096):
                record = self._records[object_id]
                return V.encoded({'spec': spec.private_descriptor(), 'stamp': list(record.stamp)})
        except BaseException:
            self.failed = True
            raise

    def private_metrics(self):
        return {**{k: getattr(self, k) for k in (
            'read_limit', 'working_limit', 'max_objects', 'read_charged', 'bytes_read', 'auth_bytes_read',
            'reread_bytes_read', 'full_authentications', 'rereads', 'map_hits', 'stability_checks',
            'retained_metadata_bytes', 'retained_map_bytes', 'bundle_payload_bytes', 'bundle_metadata_bytes',
            'temporary_working_bytes', 'peak_working_admission', 'failed')},
            'schema': 'language-private-file-cache-accounting/v1',
            'declared_objects': len(self._specs), 'authenticated_objects': len(self._records),
            'scope': 'Logical body+EOF and working accounting; trusted host, not RSS or native attestation.'}


@dataclass(frozen=True)
class _Entry:
    identity: bytes
    raw: bytes
    payload_sha256: str
    metadata_bytes: int


class BundleCache:
    """Finite private LRU over internally constructed exact permitted bundles.

    Keys bind authenticated map/spec identities and held row support, not caller
    class labels. The full immutable identity is retained beside its digest to
    reject collisions. Layer/feature identities are absent: this does not expose
    any extra features. Only actual hits establish reuse. Every post-eviction
    rebuild increments builds; no unbounded seen-key set is maintained.
    """
    def __init__(self, store, *, payload_limit, entry_limit, metadata_limit, bundle_byte_limit):
        need(type(store) is FileStore and not store.failed and store._bundle_owner is None,
             'One live private bundle cache per exact FileStore')
        need(integer(payload_limit, B.HEADER.size, store.working_limit)
             and integer(entry_limit, 1, MAX_OBJECTS)
             and integer(metadata_limit, ENTRY_RESERVE, store.working_limit)
             and integer(bundle_byte_limit, B.HEADER.size, B.MAX_BUNDLE_BYTES), 'Finite private LRU allocations')
        self.store = store
        self.payload_limit, self.entry_limit = payload_limit, entry_limit
        self.metadata_limit, self.bundle_byte_limit = metadata_limit, bundle_byte_limit
        self._entries = OrderedDict()
        self.payload_bytes = self.metadata_bytes = 0
        self.requests = self.hits = self.misses = self.builds = self.evictions = 0
        self.evicted_payload_bytes = self.built_payload_bytes = self.key_bytes_generated = 0
        self.failed = False
        # Only an attachment guard, never a strong store -> cache reference:
        # dropping one session must not wait for cyclic garbage collection.
        store._bundle_owner = True

    def _job_preflight(self, job):
        need(type(job) is V.FeatureJob and integer(job.output_columns, 1, V.MAX_COLUMNS),
             'Exact bounded original feature job')
        B._context_snapshot(job.context, job.output_columns)
        for name in ('feature_id', 'qid_id', 'time_id'):
            value = getattr(job, name)
            need(type(value) is str and len(value) == 40, 'Bounded private job identity')
        shards = job.response_shards
        need(type(shards) is tuple and 2 <= len(shards) <= V.MAX_ROWS, 'Bounded concrete response roster')
        total = 0
        for shard in shards:
            need(type(shard) is V.ResponseShard and type(shard.row_positions) is tuple
                 and 0 < len(shard.row_positions) <= V.MAX_ROWS, 'Bounded immutable response row roster')
            total += len(shard.row_positions)
            need(total <= V.MAX_ROWS, 'Cumulative row support bound')
        return total, 512*total+8192*len(shards)+8192

    def _job_snapshot(self, job):
        context = B._context_snapshot(job.context, job.output_columns)
        shards = tuple(V.ResponseShard(s.label, s.object_id, s.row_positions) for s in job.response_shards)
        return V.FeatureJob(context, job.feature_id, job.qid_id, job.time_id, shards, job.output_columns)

    def _identity(self, job, selection):
        # Operator-only bytes. No private ID/digest returned to a candidate.
        selected = []
        for shard in selection.selected_shards:
            spec = self.store._spec(shard.object_id)
            need(spec.role == 'responses' and spec.shape == (len(shard.row_positions), selection.output_columns),
                 'Selected response specification joins exact source row support')
            selected.append({'spec': spec.private_descriptor(), 'rows': list(shard.row_positions)})
        return V.encoded({'schema': 'language-private-selected-bundle-key/v1',
            'session': job.context.session, 'held_f64le': struct.pack('<d', selection.held_qid).hex(),
            'rows': selection.rows, 'output_columns': selection.output_columns,
            'qid': self.store._spec(job.qid_id).private_descriptor(),
            'time': self.store._spec(job.time_id).private_descriptor(),
            'train_positions': list(selection.train_positions), 'query_positions': list(selection.query_positions),
            'selected': selected})

    def _evict(self):
        _, old = self._entries.popitem(last=False)
        self.payload_bytes -= len(old.raw)
        self.metadata_bytes -= old.metadata_bytes
        self.store.bundle_payload_bytes = self.payload_bytes
        self.store.bundle_metadata_bytes = self.metadata_bytes
        _add(self, 'evictions')
        _add(self, 'evicted_payload_bytes', len(old.raw))

    def _get_reserved(self, job, held_qid, rows, selection_reserve):
        job = self._job_snapshot(job)
        held = V.label(held_qid)
        for object_id, role in ((job.qid_id, 'qid'), (job.time_id, 'time')):
            spec = self.store._spec(object_id)
            need(spec.role == role and spec.shape == (rows,), 'Full permitted maps match declared job support')
        qid = self.store.load(job.qid_id)
        times = self.store.load(job.time_id)
        selection = V.select_rows(job, qid, times, held, working_limit=selection_reserve)
        extent = B._extent(rows, len(selection.train_positions), selection.output_columns)
        need(extent <= self.bundle_byte_limit and extent <= self.payload_limit,
             'Single bundle must fit byte and retained payload caps')
        identity_ceiling = 4096+768*(len(selection.selected_shards)+2)+64*rows
        with self.store._temporary(3*identity_ceiling):
            identity = self._identity(job, selection)
            need(len(identity) <= identity_ceiling, 'Bounded canonical private key serialization')
            _add(self, 'key_bytes_generated', len(identity))
            key = hashlib.sha256(identity).hexdigest()
            entry = self._entries.get(key)
            if entry is not None:
                need(type(entry.identity) is bytes and entry.identity == identity,
                     'Private digest collision or selected-identity mismatch')
                need(type(entry.raw) is bytes and len(entry.raw) == extent,
                     'Immutable exact-sized cache payload authority')
                for shard in selection.selected_shards:
                    self.store.stable(shard.object_id)
                header = B._inspect(entry.raw, self.bundle_byte_limit, self.store.working_limit)
                need(header[:3] == (rows, len(selection.train_positions), selection.output_columns)
                     and struct.pack('<d', header[3]) == struct.pack('<d', held),
                     'Cached bundle header matches exact selected support and held bits')
                self._entries.move_to_end(key)
                _add(self, 'hits')
                return entry.raw
            _add(self, 'misses')
            metadata = ENTRY_RESERVE+len(identity)
            need(metadata <= self.metadata_limit, 'Single exact key must fit retained metadata allocation')
            specs = tuple(self.store._spec(s.object_id) for s in selection.selected_shards)
            self.store._read_admission(sum(s.bytes+1 for s in specs))
            build_reserve = selection.working_admission_bytes+8*extent+128*rows+8192
            response_bytes = sum(s.bytes for s in specs)
            miss_reserve = response_bytes+build_reserve+extent+metadata
            # Forecast retained authentication entries and one active read before
            # reading the first target. Response bodies are caller-owned while
            # gathered, so the outer reservation covers their complete sum.
            new_auth = V.CACHE_RESERVE*sum(s.object_id not in self.store._records for s in specs)
            read_peak = max(3*s.bytes+V.CACHE_RESERVE+8192 for s in specs)
            required = miss_reserve+new_auth+read_peak+extent+metadata
            while self._entries and (len(self._entries)+1 > self.entry_limit
                    or self.payload_bytes+extent > self.payload_limit
                    or self.metadata_bytes+metadata > self.metadata_limit
                    or self.store._total()+required > self.store.working_limit):
                self._evict()
            need(len(self._entries)+1 <= self.entry_limit
                 and self.payload_bytes+extent <= self.payload_limit
                 and self.metadata_bytes+metadata <= self.metadata_limit, 'Finite LRU admission after bounded evictions')
            self.store._admit(required)
            with self.store._temporary(miss_reserve):
                arrays = {s.object_id: self.store.load(s.object_id) for s in specs}
                raw = B.build_bundle(selection, qid, times, arrays,
                                     byte_limit=self.bundle_byte_limit, working_limit=build_reserve)
                need(type(raw) is bytes and len(raw) == extent, 'Exact immutable builder output')
                payload_sha = hashlib.sha256(raw).hexdigest()
                self.store._admit(extent+metadata)
                self._entries[key] = _Entry(identity, raw, payload_sha, metadata)
                self.payload_bytes += extent
                self.metadata_bytes += metadata
                self.store.bundle_payload_bytes = self.payload_bytes
                self.store.bundle_metadata_bytes = self.metadata_bytes
                _add(self, 'builds')
                _add(self, 'built_payload_bytes', extent)
                return raw

    def get(self, job, held_qid):
        try:
            need(not self.failed and not self.store.failed, 'Nonfailed selected private cache required')
            _add(self, 'requests')
            rows, reserve = self._job_preflight(job)
            with self.store._temporary(reserve):
                return self._get_reserved(job, held_qid, rows, reserve)
        except BaseException:
            self.failed = True
            self.store.failed = True
            raise

    def private_metrics(self):
        return {**{k: getattr(self, k) for k in (
            'payload_limit', 'entry_limit', 'metadata_limit', 'bundle_byte_limit',
            'requests', 'hits', 'misses', 'builds', 'evictions', 'evicted_payload_bytes',
            'built_payload_bytes', 'key_bytes_generated', 'payload_bytes', 'metadata_bytes', 'failed')},
            'schema': 'language-private-selected-bundle-cache-accounting/v1', 'entries': len(self._entries),
            'scope': 'Actual exact-input hits/builds; builds include rebuilding after eviction; no unique-key history.'}
