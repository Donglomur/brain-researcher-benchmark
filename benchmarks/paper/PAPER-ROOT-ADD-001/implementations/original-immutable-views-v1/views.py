"""Typed trusted-host immutable stores and selected source-fold view plans.

This is custody/selection machinery, not a sandbox or hostile-host attestation.
Files are authenticated once per cache lifetime and checked by stable ordinary
read-only identity on reuse. Global manifests, object IDs, source paths and cache
state are operator-private. Public identities hash selected visible content only.
No source archive, candidate, process, Docker command or model is run here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from contextlib import contextmanager
import hashlib
import io
import json
import math
import os
from pathlib import Path
import stat
from typing import Mapping
import uuid

import numpy as np

MAX_ROWS = 144111
MAX_COLUMNS = 82
MAX_OBJECT_BYTES = 128 * 1024**2
SPEC_RESERVE = 4096
CACHE_RESERVE = 2048
NPY_HEADER_LIMIT = 4096
PUBLIC_SCHEMA = 'language-selected-immutable-view/v1'
PRIVATE_SCHEMA = 'language-private-immutable-store/v1'
SESSIONS = ('p1_1', 'p1_2', 'p2_1', 'p2_2', 'p3_1', 'p3_2', 'p4_1',
            'p5_1', 'p5_2', 'p6_1', 'p7_1', 'p7_2', 'p8_1', 'p8_2')


def need(ok, message):
    if not ok:
        raise ValueError(message)


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def digest(value):
    return type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def positive(value):
    return type(value) is int and value > 0


def opaque_id(value):
    need(type(value) is str and value.startswith('obj-') and len(value) == 40,
         'Private object ID must be obj-UUIDv4, independent of content digests')
    try:
        token = uuid.UUID(value[4:])
    except (ValueError, AttributeError) as exc:
        raise ValueError('Malformed opaque private object ID') from exc
    need(str(token) == value[4:] and token.version == 4 and token.variant == uuid.RFC_4122,
         'Canonical random UUIDv4 object ID required')
    return value


def label(value):
    need(isinstance(value, (int, float, np.integer, np.floating))
         and not isinstance(value, (bool, np.bool_)), 'Numeric exact original qid')
    result = float(value)
    need(math.isfinite(result) and result == math.floor(result) and abs(result) < 2**53
         and result < 99990, 'Represented original qid domain')
    return result


def _field_profile(name):
    fields = {'population': ('context', 33, tuple(range(-20, 20))),
              'unit': ('context', 33, tuple(range(-20, 20))),
              'time_shuffle': ('context', 33, tuple(range(-20, 20))),
              'random_token': ('random_token', 33, (-10,)),
              'sentence_swap': ('context', 33, (-10,))}
    fields.update({f: (f, 33, (-10,)) for f in ('ngram1', 'ngram3', 'ngram5', 'ngram7', 'ngram10')})
    fields.update({f+s: (f, 1, (-3, -2, -1))
                   for f in ('sem_syn', 'word2vec', 'syn') for s in ('', '_shuffle')})
    need(name in fields, 'Original source field required')
    return fields[name]


@dataclass(frozen=True)
class ObjectSpec:
    object_id: str
    relative_path: str
    role: str
    bytes: int
    sha256: str
    shape: tuple[int, ...]
    dtype: str
    fortran_order: bool = False

    def __post_init__(self):
        opaque_id(self.object_id)
        need(self.relative_path == 'objects/' + self.object_id + '.npy',
             'Private paths use opaque IDs, never source/content digests')
        need(self.role in ('features', 'qid', 'time', 'responses') and digest(self.sha256)
             and positive(self.bytes) and self.bytes <= MAX_OBJECT_BYTES
             and type(self.fortran_order) is bool, 'Typed immutable object metadata')
        object.__setattr__(self, 'shape', tuple(self.shape))
        need(1 <= len(self.shape) <= 2 and all(positive(n) for n in self.shape)
             and self.shape[0] <= MAX_ROWS, 'Bounded positive source shape')
        if self.role == 'features':
            need(len(self.shape) == 2 and self.shape[1] == 30 and self.dtype == '<f8',
                 'One source feature job, float64 by30PCs')
        elif self.role == 'responses':
            need(len(self.shape) == 2 and self.shape[1] <= MAX_COLUMNS and self.dtype == '<f8',
                 'Primitive source response shard')
        else:
            need(len(self.shape) == 1 and self.dtype == ('<f8' if self.role == 'qid' else '<i8'),
                 'Original qid or ordered time map dtype')
        need(math.prod(self.shape)*8 < self.bytes <= math.prod(self.shape)*8 + 8192,
             'Exact primitive body plus bounded NPY header extent')

    def private_descriptor(self):
        return {'object_id': self.object_id, 'relative_path': self.relative_path,
                'role': self.role, 'bytes': self.bytes, 'sha256': self.sha256,
                'shape': list(self.shape), 'dtype': self.dtype, 'fortran_order': self.fortran_order}


@dataclass(frozen=True)
class JobContext:
    session: str
    field: str
    family: str
    layer: int
    lag_index: int
    lag_bins: int

    def __post_init__(self):
        family, layers, lags = _field_profile(self.field)
        need(self.session in SESSIONS and self.family == family
             and type(self.layer) is int and 0 <= self.layer < layers
             and type(self.lag_index) is int and 0 <= self.lag_index < len(lags)
             and type(self.lag_bins) is int and self.lag_bins == lags[self.lag_index],
             'Exact original session/field/family/layer/lag context')

    def descriptor(self, held_qid):
        return {'session': self.session, 'field': self.field, 'family': self.family,
                'layer': self.layer, 'lag_index': self.lag_index, 'lag_bins': self.lag_bins,
                'held_qid': label(held_qid)}


@dataclass(frozen=True)
class ResponseShard:
    label: float
    object_id: str
    row_positions: tuple[int, ...]

    def __post_init__(self):
        object.__setattr__(self, 'label', label(self.label))
        opaque_id(self.object_id)
        rows = tuple(self.row_positions)
        need(0 < len(rows) <= MAX_ROWS
             and all(isinstance(x, (int, np.integer)) and not isinstance(x, (bool, np.bool_)) for x in rows),
             'Nonempty integer shard row positions')
        rows = tuple(int(x) for x in rows)
        need(all(0 <= x < MAX_ROWS for x in rows)
             and all(a < b for a, b in zip(rows, rows[1:])), 'Strict ordered shard row positions')
        object.__setattr__(self, 'row_positions', rows)


@dataclass(frozen=True)
class FeatureJob:
    context: JobContext
    feature_id: str
    qid_id: str
    time_id: str
    response_shards: tuple[ResponseShard, ...]
    output_columns: int

    def __post_init__(self):
        need(type(self.context) is JobContext and positive(self.output_columns)
             and self.output_columns <= MAX_COLUMNS
             and (self.context.field == 'unit' or self.output_columns == 1),
             'Typed original target kind and output width')
        common = tuple(opaque_id(x) for x in (self.feature_id, self.qid_id, self.time_id))
        shards = tuple(self.response_shards)
        need(2 <= len(shards) <= MAX_ROWS and all(type(s) is ResponseShard for s in shards),
             'Complete typed response partition')
        ids = common + tuple(s.object_id for s in shards)
        need(len(set(ids)) == len(ids) and len({s.label for s in shards}) == len(shards)
             and sum(len(s.row_positions) for s in shards) <= MAX_ROWS,
             'Distinct feature/map/shard objects and qid groups')
        object.__setattr__(self, 'response_shards', shards)


@dataclass(frozen=True)
class Selection:
    context: JobContext
    held_qid: float
    rows: int
    output_columns: int
    train_positions: tuple[int, ...]
    query_positions: tuple[int, ...]
    train_time_indices: tuple[int, ...]
    query_time_indices: tuple[int, ...]
    train_qid: tuple[float, ...]
    selected_shards: tuple[ResponseShard, ...] = field(repr=False)
    working_admission_bytes: int = 0

    def __post_init__(self):
        need(type(self.context) is JobContext and positive(self.rows) and 2 <= self.rows <= MAX_ROWS
             and positive(self.output_columns) and self.output_columns <= MAX_COLUMNS
             and (self.context.field == 'unit' or self.output_columns == 1), 'Typed bounded source selection')
        object.__setattr__(self, 'held_qid', label(self.held_qid))
        for name in ('train_positions', 'query_positions', 'train_time_indices', 'query_time_indices'):
            value = tuple(getattr(self, name))
            limit = self.rows if name.endswith('positions') else MAX_ROWS
            need(value and all(type(x) is int and 0 <= x < limit for x in value)
                 and all(a < b for a, b in zip(value, value[1:])), 'Strict immutable selected row/time order')
            object.__setattr__(self, name, value)
        train, query = self.train_positions, self.query_positions
        need(len(train)+len(query) == self.rows and not set(train).intersection(query)
             and len(train) == len(self.train_time_indices) and len(query) == len(self.query_time_indices),
             'Complete disjoint original train/query positions and aligned time maps')
        joined = dict(zip(train, self.train_time_indices))
        joined.update(zip(query, self.query_time_indices))
        ordered = [joined[i] for i in range(self.rows)]
        need(all(a < b for a, b in zip(ordered, ordered[1:])), 'One globally ordered source time map')
        qid = tuple(label(x) for x in self.train_qid)
        need(len(qid) == len(train) and all(x != self.held_qid for x in qid), 'Training qids exclude held group')
        object.__setattr__(self, 'train_qid', qid)
        shards = tuple(self.selected_shards)
        need(shards and all(type(s) is ResponseShard and s.label != self.held_qid for s in shards)
             and len({s.object_id for s in shards}) == len(shards)
             and all(a.label < b.label for a, b in zip(shards, shards[1:])), 'Canonical selected training shard roster')
        assigned = [r for s in shards for r in s.row_positions]
        need(len(assigned) == len(train) and sorted(assigned) == list(train),
             'Selected response row assignment covers each training row exactly once')
        qid_by_row = dict(zip(train, qid))
        need(all(all(qid_by_row[r] == s.label for r in s.row_positions) for s in shards),
             'Selected shard label agrees with each original training row')
        need(positive(self.working_admission_bytes)
             and self.working_admission_bytes >= 512*self.rows + 8192*(len(shards)+1),
             'Complete selection working reservation')
        object.__setattr__(self, 'selected_shards', shards)


def select_rows(job, qid, time_indices, held_qid, *, working_limit):
    """Pure source row selection; no store access and no isolation claim."""
    need(type(job) is FeatureJob and positive(working_limit), 'Typed job and finite working allocation')
    held = label(held_qid)
    need(type(qid) is np.ndarray and type(time_indices) is np.ndarray
         and qid.dtype == np.dtype('<f8') and time_indices.dtype == np.dtype('<i8')
         and qid.ndim == time_indices.ndim == 1 and qid.shape == time_indices.shape,
         'Exact one-dimensional original qid/time maps')
    n = len(qid)
    reserve = 512*n + 8192*len(job.response_shards)
    need(2 <= n <= MAX_ROWS and reserve <= working_limit, 'Selection working allocation before partition')
    need(np.isfinite(qid).all() and np.all(qid == np.floor(qid)) and np.all(np.abs(qid) < 2**53)
         and np.all(qid < 99990) and np.all(time_indices >= 0) and np.all(time_indices < MAX_ROWS)
         and np.all(time_indices[1:] > time_indices[:-1]), 'Original represented qid and ordered time domain')
    need({float(x) for x in np.unique(qid)} == {s.label for s in job.response_shards}
         and any(s.label == held for s in job.response_shards), 'Every represented qid has exactly one shard')
    occupied = np.zeros(n, dtype=bool)
    for shard in job.response_shards:
        indices = np.asarray(shard.row_positions, dtype=np.int64)
        need(indices[-1] < n and not occupied[indices].any() and np.all(qid[indices] == shard.label),
             'Response shards join distinct exact qid rows')
        occupied[indices] = True
    need(occupied.all(), 'Response shard partition covers all source rows')
    train, query = np.flatnonzero(qid != held), np.flatnonzero(qid == held)
    need(len(train) > 0 and len(query) > 0, 'Nonempty original train/query partition')
    chosen = tuple(sorted((s for s in job.response_shards if s.label != held), key=lambda s: s.label))
    need(sum(len(s.row_positions) for s in chosen) == len(train), 'Selected shards cover all and only training rows')
    return Selection(job.context, held, n, job.output_columns,
                     tuple(int(x) for x in train), tuple(int(x) for x in query),
                     tuple(int(x) for x in time_indices[train]), tuple(int(x) for x in time_indices[query]),
                     tuple(float(x) for x in qid[train]), chosen, reserve)


def assemble_request(full_x, selection, response_arrays: Mapping[str, np.ndarray], *, working_limit):
    """Pure in-memory equivalent of the permitted original callback operands.

    Tests can compare all4209 source jobs without constructing physical stores.
    This helper never treats a Python callback or row selection as an OS sandbox.
    """
    # An exact-class dataclass can still be forged with object.__new__ or
    # object.__setattr__. Admit bounded primitive metadata first, then rebuild
    # the immutable snapshot so constructor invariants are not treated as proof.
    _selection_preflight(selection, working_limit)
    need(type(full_x) is np.ndarray and full_x.dtype == np.dtype('<f8')
         and full_x.shape == (selection.rows, 30), 'Exact one-job full feature matrix')
    response_bytes = len(selection.train_positions)*selection.output_columns*8
    reserve = selection.working_admission_bytes + 4*full_x.nbytes + 4*response_bytes
    need(reserve <= working_limit, 'Assembly working allocation before target/feature copies')
    need(type(response_arrays) is dict and len(response_arrays) == len(selection.selected_shards),
         'Bounded concrete selected-response dictionary')
    selection = _selection_snapshot(selection)
    need(set(response_arrays) == {s.object_id for s in selection.selected_shards},
         'Exactly selected training shards; no held or extra response arrays')
    # No NumPy row/index allocation precedes the complete working admission and
    # snapshot validation above, including the working_limit=1 failure path.
    train = np.asarray(selection.train_positions, dtype=np.int64)
    query = np.asarray(selection.query_positions, dtype=np.int64)
    need(np.isfinite(full_x).all(), 'Finite complete source features')
    train_y = np.empty((len(train), selection.output_columns), dtype=np.float64)
    position = np.full(selection.rows, -1, dtype=np.int64)
    position[train] = np.arange(len(train))
    occupied = np.zeros(len(train), dtype=bool)
    for shard in selection.selected_shards:
        value = response_arrays[shard.object_id]
        need(type(value) is np.ndarray and value.dtype == np.dtype('<f8')
             and value.shape == (len(shard.row_positions), selection.output_columns)
             and np.isfinite(value).all(), 'Exact finite selected response shard')
        dest = position[np.asarray(shard.row_positions, dtype=np.int64)]
        need(np.all(dest >= 0) and not occupied[dest].any(), 'No query response or duplicate target row in assembly')
        train_y[dest] = value
        occupied[dest] = True
    need(occupied.all(), 'Complete ordered training response assembly')
    context = selection.context.descriptor(selection.held_qid)
    context.update(train_time_indices=np.asarray(selection.train_time_indices, dtype=np.int64),
                   test_time_indices=np.asarray(selection.query_time_indices, dtype=np.int64),
                   train_qid=np.asarray(selection.train_qid, dtype=np.float64))
    return full_x[train].copy(), train_y, full_x[query].copy(), context


def _selection_preflight(selection, working_limit):
    """Bound metadata before copying or allocating arrays; never consume iterators."""
    need(type(selection) is Selection and positive(working_limit)
         and positive(selection.rows) and 2 <= selection.rows <= MAX_ROWS
         and positive(selection.output_columns) and selection.output_columns <= MAX_COLUMNS
         and type(selection.context) is JobContext, 'Typed bounded selection preflight')
    for name in ('train_positions', 'query_positions', 'train_time_indices',
                 'query_time_indices', 'train_qid'):
        value = getattr(selection, name)
        need(type(value) is tuple and 0 < len(value) <= selection.rows,
             'Bounded immutable selection tuples before iteration')
    shards = selection.selected_shards
    need(type(shards) is tuple and 1 <= len(shards) < selection.rows,
         'Bounded concrete selected-shard tuple')
    minimum = 512*selection.rows + 8192*(len(shards)+1)
    need(positive(selection.working_admission_bytes)
         and minimum <= selection.working_admission_bytes <= working_limit,
         'Selection metadata working admission before copying')
    total = 0
    for shard in shards:
        need(type(shard) is ResponseShard and type(shard.row_positions) is tuple
             and 0 < len(shard.row_positions) <= selection.rows,
             'Bounded concrete response-shard row tuple')
        total += len(shard.row_positions)
        need(total <= selection.rows, 'Cumulative selected row metadata bound')


def _selection_snapshot(selection):
    context = selection.context
    context = JobContext(context.session, context.field, context.family,
                         context.layer, context.lag_index, context.lag_bins)
    shards = tuple(ResponseShard(s.label, s.object_id, s.row_positions) for s in selection.selected_shards)
    return Selection(context, selection.held_qid, selection.rows, selection.output_columns,
                     selection.train_positions, selection.query_positions,
                     selection.train_time_indices, selection.query_time_indices,
                     selection.train_qid, shards, selection.working_admission_bytes)


def _stamp(info):
    return tuple(getattr(info, k) for k in ('st_dev', 'st_ino', 'st_mode', 'st_nlink',
                                         'st_size', 'st_mtime_ns', 'st_ctime_ns'))


@dataclass(frozen=True)
class _CachedObject:
    spec: ObjectSpec
    source_path: Path = field(repr=False)
    stamp: tuple[int, ...] = field(repr=False)
    map_value: np.ndarray | None = field(default=None, repr=False, compare=False)


class ImmutableStore:
    """Lazy bounded authentication cache for an explicitly trusted host.

    Metadata and qid/time arrays are retained. Feature/response values are checked
    once and discarded; later mounts refer to stable read-only files. Limits are
    conservative cooperative working admissions, not process-RSS enforcement.
    A failed authentication poisons the cache; no implicit retry is performed.
    Caller owns lifetimes/budgets of returned view plans and request arrays.
    """
    def __init__(self, root, specs, *, read_limit, working_limit, max_objects):
        need(all(positive(x) for x in (read_limit, working_limit, max_objects)),
             'Finite positive cache/read/working allocations')
        self.root = Path(root).absolute()
        need(not any(p.is_symlink() for p in (self.root, *self.root.parents)) and self.root.is_dir(),
             'Ordinary private store directory')
        need(type(specs) in (tuple, list) and 0 < len(specs) <= max_objects
             and len(specs)*SPEC_RESERVE <= working_limit,
             'Bounded concrete private manifest before iterator consumption or copy')
        need(all(type(s) is ObjectSpec for s in specs), 'Typed private store manifest')
        specs = tuple(specs)
        need(len({s.object_id for s in specs}) == len(specs)
             and len({s.relative_path for s in specs}) == len(specs), 'Unique opaque store identities and paths')
        metadata = sum(SPEC_RESERVE + len(encoded(s.private_descriptor())) for s in specs)
        need(metadata <= working_limit, 'Store metadata working allocation')
        self._specs = {s.object_id: s for s in specs}
        self._cache = {}
        self.read_limit, self.working_limit = read_limit, working_limit
        self.read_charged = self.bytes_read = self.full_authentications = 0
        self.retained_working_admission = metadata
        self.peak_working_admission = metadata
        self._temporary_working_admission = 0
        self.failed = False

    def _working(self, temporary):
        need(type(temporary) is int and temporary >= 0
             and self.retained_working_admission+self._temporary_working_admission+temporary <= self.working_limit,
             'Finite cache plus operation working allocation')
        self.peak_working_admission = max(self.peak_working_admission,
                                          self.retained_working_admission+self._temporary_working_admission+temporary)

    @contextmanager
    def temporary_working(self, amount):
        """Track live host-operation reservations alongside lazy file decoding."""
        self._working(amount)
        self._temporary_working_admission += amount
        try:
            yield
        finally:
            self._temporary_working_admission -= amount

    def _path(self, spec):
        path = self.root / spec.relative_path
        need(not any(p.is_symlink() for p in (path, *path.parents)), 'No private object symlink')
        return path

    def _stable(self, cached):
        path = self._path(cached.spec)
        current = path.lstat()
        need(stat.S_ISREG(current.st_mode) and current.st_nlink == 1
             and current.st_mode & 0o222 == 0 and _stamp(current) == cached.stamp,
             'Cached read-only ordinary object changed; no cached digest attestation after mutation')

    def stable(self, object_id):
        need(not self.failed and object_id in self._cache, 'Authenticated live object cache entry required')
        try:
            self._stable(self._cache[object_id])
        except BaseException:
            self.failed = True
            raise

    def authenticate(self, object_id):
        need(not self.failed and object_id in self._specs, 'Declared object and nonfailed cache required')
        if object_id in self._cache:
            self.stable(object_id)
            return self._cache[object_id]
        spec = self._specs[object_id]
        try:
            self._working(3*spec.bytes + CACHE_RESERVE + 8192)
            need(self.read_charged + spec.bytes + 1 <= self.read_limit,
                 'Cumulative read allocation before authentication')
            path = self._path(spec)
            fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
            with os.fdopen(fd, 'rb', buffering=0) as stream:
                before = os.fstat(stream.fileno())
                need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                     and before.st_mode & 0o222 == 0 and before.st_size == spec.bytes,
                     'Exact ordinary single-link read-only object')
                self.read_charged += spec.bytes + 1
                raw = stream.read(spec.bytes + 1)
                self.bytes_read += len(raw)
                after, named = os.fstat(stream.fileno()), path.lstat()
                need(_stamp(before) == _stamp(after) == _stamp(named), 'Object changed during full authentication')
            need(len(raw) == spec.bytes and hashlib.sha256(raw).hexdigest() == spec.sha256,
                 'Full immutable object digest/extent mismatch')
            stream = io.BytesIO(raw)
            version = np.lib.format.read_magic(stream)
            readers = {(1, 0): np.lib.format.read_array_header_1_0, (2, 0): np.lib.format.read_array_header_2_0}
            need(version in readers, 'Primitive NPY1/2 store object')
            shape, fortran, dtype = readers[version](stream, max_header_size=NPY_HEADER_LIMIT)
            need(tuple(shape) == spec.shape and fortran is spec.fortran_order and dtype.str == spec.dtype
                 and dtype.fields is None and dtype.subdtype is None and not dtype.hasobject
                 and stream.tell()+math.prod(shape)*dtype.itemsize == len(raw),
                 'Exact primitive store header/body geometry')
            value = np.frombuffer(raw, dtype=dtype, offset=stream.tell()).reshape(shape, order='F' if fortran else 'C')
            need(np.isfinite(value).all(), 'Finite primitive store values')
            if spec.role == 'qid':
                need(np.all(value == np.floor(value)) and np.all(np.abs(value) < 2**53)
                     and np.all(value < 99990), 'Original represented qid map')
            if spec.role == 'time':
                need(np.all(value >= 0) and np.all(value < MAX_ROWS)
                     and np.all(value[1:] > value[:-1]), 'Strict original source-time map')
            retained = value if spec.role in ('qid', 'time') else None
            extra = CACHE_RESERVE + (spec.bytes if retained is not None else 0)
            self._working(extra)
            cached = _CachedObject(spec, path, _stamp(before), retained)
            self._cache[object_id] = cached
            self.retained_working_admission += extra
            self.full_authentications += 1
            return cached
        except BaseException:
            self.failed = True
            raise

    def private_manifest(self):
        """Operator-only: never include this global identity in public requests."""
        return {'schema': PRIVATE_SCHEMA,
                'objects': [s.private_descriptor() for s in sorted(self._specs.values(), key=lambda s: s.object_id)]}

    def private_metrics(self):
        return {'schema': 'language-private-cache-accounting/v1', 'read_limit': self.read_limit,
                'read_charged': self.read_charged, 'bytes_read': self.bytes_read,
                'full_authentications': self.full_authentications,
                'retained_working_admission': self.retained_working_admission,
                'temporary_working_admission': self._temporary_working_admission,
                'peak_working_admission': self.peak_working_admission, 'working_limit': self.working_limit,
                'failed': self.failed,
                'scope': 'Conservative logical read/working admissions; not kernel-I/O/RSS or hostile-host attestation.'}


@dataclass(frozen=True)
class PrivateMount:
    source_path: Path = field(repr=False)
    visible_path: str
    object_id: str = field(repr=False)
    read_only: bool = True


@dataclass(frozen=True)
class ViewPlan:
    public_json: bytes
    public_id: str
    private_mounts: tuple[PrivateMount, ...] = field(repr=False)
    selection: Selection = field(repr=False)
    working_admission_bytes: int = 0

    def public_descriptor(self):
        """Return an independent copy; immutable public_json remains authoritative."""
        return json.loads(self.public_json)


def _public_object(cached, visible_path):
    spec = cached.spec
    # Deliberately excludes object_id, relative/source path, role/private store
    # identity, cache counters and every unselected object's digest.
    return {'path': visible_path, 'bytes': spec.bytes, 'sha256': spec.sha256,
            'shape': list(spec.shape), 'dtype': spec.dtype, 'fortran_order': spec.fortran_order}


def build_view(store, job, held_qid, *, descriptor_limit):
    """Plan one selected view; no files are mounted and no process is launched.

    Public identity is SHA256(public_json) and depends only on visible selected
    objects/row metadata plus original context. It is a new schema identity, not
    a claim of equality to the old bridge's byte/request SHA.
    """
    need(type(store) is ImmutableStore and type(job) is FeatureJob and positive(descriptor_limit)
         and descriptor_limit <= 16*1024**2, 'Typed view and finite public descriptor allocation')
    maps = [store.authenticate(job.qid_id), store.authenticate(job.time_id)]
    qid, times = maps
    need(qid.spec.role == 'qid' and times.spec.role == 'time' and qid.spec.shape == times.spec.shape,
         'Exact selected original qid/time map roles')
    n = qid.spec.shape[0]
    selection_reserve = 512*n + 8192*len(job.response_shards)
    with store.temporary_working(selection_reserve + 3*descriptor_limit):
        return _build_reserved_view(store, job, held_qid, descriptor_limit, qid, times, selection_reserve)


def _build_reserved_view(store, job, held_qid, descriptor_limit, qid, times, selection_reserve):
    selection = select_rows(job, qid.map_value, times.map_value, held_qid,
                            working_limit=selection_reserve)
    feature = store.authenticate(job.feature_id)
    need(feature.spec.role == 'features' and feature.spec.shape == (selection.rows, 30),
         'Exactly one complete feature job aligned to selected maps')
    chosen = [(feature, '/input/full_x.npy'), (qid, '/input/qid.npy'), (times, '/input/time_indices.npy')]
    response_descriptors = []
    for ordinal, shard in enumerate(selection.selected_shards):
        obj = store.authenticate(shard.object_id)
        need(obj.spec.role == 'responses' and obj.spec.shape == (len(shard.row_positions), job.output_columns),
             'Selected shard shape joins exactly its training qid rows')
        alias = '/input/responses/shard-' + str(ordinal).zfill(6) + '.npy'
        chosen.append((obj, alias))
        response_descriptors.append({'qid': shard.label, 'row_positions': list(shard.row_positions),
                                     'array': _public_object(obj, alias)})
    store._working(0)
    visible = {'schema': PUBLIC_SCHEMA, 'context': job.context.descriptor(selection.held_qid),
               'feature_array': _public_object(feature, '/input/full_x.npy'),
               'qid_array': _public_object(qid, '/input/qid.npy'),
               'time_indices_array': _public_object(times, '/input/time_indices.npy'),
               'train_positions': list(selection.train_positions), 'query_positions': list(selection.query_positions),
               'train_time_indices': list(selection.train_time_indices),
               'query_time_indices': list(selection.query_time_indices),
               'train_qid': list(selection.train_qid), 'training_response_shards': response_descriptors,
               'prediction_shape': [len(selection.query_positions), job.output_columns],
               'scope': 'One feature job; fullX is the original train/query feature union. Response files cover training rows only. New selected-view schema, not an old bridge byte-SHA assertion.'}
    raw = encoded(visible)
    need(len(raw) <= descriptor_limit, 'Public descriptor exceeds allocation')
    for obj, _ in chosen:
        store.stable(obj.spec.object_id)
    mounts = tuple(PrivateMount(obj.source_path, alias, obj.spec.object_id) for obj, alias in chosen)
    need(len({m.visible_path for m in mounts}) == len(mounts), 'Unique selected visible aliases')
    return ViewPlan(raw, hashlib.sha256(raw).hexdigest(), mounts, selection,
                    selection_reserve + 3*descriptor_limit)
