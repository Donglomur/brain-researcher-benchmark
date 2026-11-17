"""Compact permitted source-fold inputs; no cache, file store or native boundary.

The trusted operator supplies one validated Selection, its full allowed qid/time
maps and exactly the selected training-response shards. Features remain separate.
The codec preserves primitive bits and original equality-based row membership.
No held target, private object ID or response-class identity is serialized.

Logical allocations cover this component's snapshots/results/temporaries, not
caller-owned inputs, Python/kernel RSS or concurrent mutation by a hostile host.
No array files are opened. Only the pinned sibling Python source is loaded.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import struct
import sys
import types

import numpy as np


VIEWS_SHA256 = 'a8338621338680eac8a7673ea3a14b6567d1800b6f36168ad03eebb5ccf28eb6'
_dependency = Path(__file__).resolve().parent.parent / 'original-immutable-views-v1/views.py'
with _dependency.open('rb') as _handle:
    _source = _handle.read(65537)
if len(_source) != 31537 or hashlib.sha256(_source).hexdigest() != VIEWS_SHA256:
    raise ValueError('Exact reviewed immutable-view source dependency required')
V = types.ModuleType('_language_compact_views_a8338621')
V.__file__ = str(_dependency)
V.__package__ = ''
sys.modules[V.__name__] = V
exec(compile(_source, str(_dependency), 'exec', dont_inherit=True), V.__dict__)
del _source, _handle, _dependency

MAGIC = b'LCBNDL01'
VERSION = 1
HEADER = struct.Struct('<8sIIQQQd16x')
BUNDLE_SCHEMA = 'language-permitted-response-maps-bundle/v1'
REQUEST_SCHEMA = 'language-compact-selected-request/v1'
MAX_BUNDLE_BYTES = 128 * 1024**2
MAX_WORKING_BYTES = 1024**3
MAX_DESCRIPTOR_BYTES = 8192


def need(ok, message):
    if not ok:
        raise ValueError(message)


def _integer(value, low, high):
    return type(value) is int and low <= value <= high


def _limits(byte_limit, working_limit):
    need(_integer(byte_limit, HEADER.size, MAX_BUNDLE_BYTES)
         and _integer(working_limit, 1, MAX_WORKING_BYTES),
         'Finite primitive byte and logical working limits required')


def _context_snapshot(context, output_columns):
    need(type(context) is V.JobContext, 'Exact original typed context required')
    for name in ('session', 'field', 'family'):
        value = getattr(context, name)
        need(type(value) is str and 0 < len(value) <= 32, 'Bounded primitive source context')
    need(all(type(getattr(context, k)) is int for k in ('layer', 'lag_index', 'lag_bins')),
         'Primitive original layer/lag context')
    snapshot = V.JobContext(context.session, context.field, context.family,
                            context.layer, context.lag_index, context.lag_bins)
    need(snapshot.field == 'unit' or output_columns == 1, 'Context agrees with target width')
    return snapshot


def _extent(rows, training_rows, columns):
    need(_integer(rows, 2, V.MAX_ROWS) and _integer(training_rows, 1, rows-1)
         and _integer(columns, 1, V.MAX_COLUMNS), 'Bounded nonempty source dimensions')
    return HEADER.size + 16*rows + 8*training_rows*columns


def _decode_reserve(extent, rows):
    return 4*extent + 64*rows + 8192


def _inspect(raw, byte_limit, working_limit):
    """Bound an immutable primitive header before any NumPy allocation."""
    _limits(byte_limit, working_limit)
    need(type(raw) is bytes and HEADER.size <= len(raw) <= byte_limit,
         'Immutable exact bytes within the supplied bundle bound')
    magic, version, flags, rows, training_rows, columns, held = HEADER.unpack_from(raw)
    need(magic == MAGIC and version == VERSION and flags == 0
         and raw[48:64] == b'\x00'*16, 'Canonical header, version, flags and zero padding')
    held = V.label(held)
    extent = _extent(rows, training_rows, columns)
    need(extent <= byte_limit and len(raw) == extent, 'Exact body extent; no truncation or suffix')
    need(HEADER.pack(MAGIC, VERSION, 0, rows, training_rows, columns, held) == raw[:64],
         'Canonical primitive header encoding')
    return rows, training_rows, columns, held, extent


def _maps(qid, times, rows):
    need(type(qid) is np.ndarray and qid.dtype == np.dtype('<f8') and qid.shape == (rows,)
         and type(times) is np.ndarray and times.dtype == np.dtype('<i8') and times.shape == (rows,),
         'Exact little-endian primitive full permitted maps')
    need(np.isfinite(qid).all() and np.all(qid == np.floor(qid))
         and np.all(np.abs(qid) < 2**53) and np.all(qid < 99990),
         'Original finite represented qid domain')
    need(np.all(times >= 0) and np.all(times < V.MAX_ROWS)
         and np.all(times[1:] > times[:-1]), 'Strict globally ordered original time map')


@dataclass(frozen=True)
class DecodedBundle:
    """Read-only views into immutable bytes, for inspection, never authority.

    Public operations accept raw bytes and revalidate; a forged dataclass cannot
    bypass their guards. Views' metadata may be changed by a caller, but their
    immutable byte backing cannot be changed, nor reused as trusted validation.
    """
    raw: bytes
    rows: int
    training_rows: int
    output_columns: int
    held_qid: float
    qid: np.ndarray
    time_indices: np.ndarray
    train_y: np.ndarray
    train_positions: np.ndarray
    query_positions: np.ndarray
    working_admission_bytes: int


def decode_bundle(raw, *, byte_limit, working_limit):
    """Validate the complete primitive bundle; reject mutable buffers and extras."""
    rows, training_rows, columns, held, extent = _inspect(raw, byte_limit, working_limit)
    reserve = _decode_reserve(extent, rows)
    need(reserve <= working_limit, 'Complete decode admission before NumPy views or masks')
    qid = np.frombuffer(raw, dtype='<f8', count=rows, offset=HEADER.size)
    times = np.frombuffer(raw, dtype='<i8', count=rows, offset=HEADER.size+8*rows)
    y = np.frombuffer(raw, dtype='<f8', count=training_rows*columns,
                      offset=HEADER.size+16*rows).reshape(training_rows, columns)
    _maps(qid, times, rows)
    need(int(np.count_nonzero(qid != held)) == training_rows,
         'Header training count agrees with original held-qid equality partition')
    need(np.isfinite(y).all(), 'Finite permitted training responses')
    # Immutable backing also protects row-index results against setflags(write=True).
    train = np.frombuffer(np.flatnonzero(qid != held).astype('<i8', copy=False).tobytes(), dtype='<i8')
    query = np.frombuffer(np.flatnonzero(qid == held).astype('<i8', copy=False).tobytes(), dtype='<i8')
    need(len(train) == training_rows and len(query) == rows-training_rows,
         'Complete nonempty original row partition')
    return DecodedBundle(raw, rows, training_rows, columns, held,
                         qid, times, y, train, query, reserve)


def build_bundle(selection, qid, time_indices, response_arrays, *, byte_limit, working_limit):
    """Freeze exactly the allowed maps and selected Y, with no feature payload.

    Explicit full maps preserve original f64 qid bits, including mixed signed
    zero in the held group. Selection supplies the authoritative ordered join;
    its exact-class dataclass is revalidated before indexing or bulk copying.
    """
    _limits(byte_limit, working_limit)
    V._selection_preflight(selection, working_limit)
    _context_snapshot(selection.context, selection.output_columns)
    rows, columns = selection.rows, selection.output_columns
    extent = _extent(rows, len(selection.train_positions), columns)
    reserve = selection.working_admission_bytes + 8*extent + 128*rows + 8192
    need(extent <= byte_limit and reserve <= working_limit,
         'Complete snapshot, output and temporary admission before allocation')
    need(type(qid) is np.ndarray and qid.dtype == np.dtype('<f8') and qid.shape == (rows,)
         and type(time_indices) is np.ndarray and time_indices.dtype == np.dtype('<i8')
         and time_indices.shape == (rows,), 'Bounded primitive map operands before copying')
    need(type(response_arrays) is dict and len(response_arrays) == len(selection.selected_shards),
         'Bounded concrete exact selected-response dictionary')
    selection = V._selection_snapshot(selection)
    need(all(type(k) is str and len(k) == 40 for k in response_arrays)
         and set(response_arrays) == {s.object_id for s in selection.selected_shards},
         'Exactly selected private shard IDs; no held or unrelated target objects')
    arrays = dict(response_arrays)
    for shard in selection.selected_shards:
        value = arrays[shard.object_id]
        need(type(value) is np.ndarray and value.dtype == np.dtype('<f8')
             and value.shape == (len(shard.row_positions), columns),
             'Exact primitive selected training-response shape')
    qid = np.array(qid, dtype='<f8', order='C', copy=True)
    times = np.array(time_indices, dtype='<i8', order='C', copy=True)
    _maps(qid, times, rows)
    train = np.asarray(selection.train_positions, dtype='<i8')
    query = np.asarray(selection.query_positions, dtype='<i8')
    need(np.array_equal(np.flatnonzero(qid != selection.held_qid), train)
         and np.array_equal(np.flatnonzero(qid == selection.held_qid), query),
         'Selection matches the exact full-map held partition and row order')
    need(qid[train].tobytes() == np.asarray(selection.train_qid, dtype='<f8').tobytes()
         and np.array_equal(times[train], selection.train_time_indices)
         and np.array_equal(times[query], selection.query_time_indices),
         'Exact training-qid bits and ordered train/query time join')
    y = np.empty((len(train), columns), dtype='<f8', order='C')
    positions = np.full(rows, -1, dtype='<i8')
    positions[train] = np.arange(len(train), dtype='<i8')
    occupied = np.zeros(len(train), dtype=bool)
    for shard in selection.selected_shards:
        dest = positions[np.asarray(shard.row_positions, dtype='<i8')]
        need(np.all(dest >= 0) and not occupied[dest].any(), 'No held or repeated target assignment')
        y[dest] = arrays[shard.object_id]
        occupied[dest] = True
    need(occupied.all() and np.isfinite(y).all(), 'Complete finite ordered selected training responses')
    header = HEADER.pack(MAGIC, VERSION, 0, rows, len(train), columns, selection.held_qid)
    raw = b''.join((header, qid.tobytes(order='C'), times.tobytes(order='C'), y.tobytes(order='C')))
    need(len(raw) == extent, 'Exact primitive output extent')
    return raw


def assemble_request(full_x, raw, context, *, byte_limit, working_limit):
    """Recover the unchanged original callback operands, never execute a candidate."""
    rows, training_rows, columns, held, extent = _inspect(raw, byte_limit, working_limit)
    context = _context_snapshot(context, columns)
    need(type(full_x) is np.ndarray and full_x.dtype == np.dtype('<f8')
         and full_x.shape == (rows, 30), 'One exact original feature job only')
    reserve = _decode_reserve(extent, rows) + 4*full_x.nbytes + 2*extent + 64*rows + 8192
    need(reserve <= working_limit, 'Joint decode/feature/response/output admission before allocation')
    data = decode_bundle(raw, byte_limit=byte_limit, working_limit=working_limit)
    need(np.isfinite(full_x).all(), 'Finite permitted source features')
    train, query = data.train_positions, data.query_positions
    original = context.descriptor(held)
    original.update(train_time_indices=data.time_indices[train].copy(),
                    test_time_indices=data.time_indices[query].copy(),
                    train_qid=data.qid[train].copy())
    return full_x[train].copy(), data.train_y.copy(), full_x[query].copy(), original


@dataclass(frozen=True)
class RequestDescriptor:
    public_json: bytes
    public_id: str


def make_descriptor(raw, context, *, feature_sha256, feature_bytes,
                    feature_fortran_order=False, byte_limit, working_limit,
                    descriptor_limit=MAX_DESCRIPTOR_BYTES):
    """Bind selected content only; supplied feature SHA is an operator assertion.

    This helper does not open/authenticate X, and cannot establish that a caller's
    feature hash names the actual future feature object. A separately reviewed
    provider must join that assertion to immutable X and enforce its visibility.
    No private class key, object UUID, source-FR hash or held-target hash is used.
    """
    rows, training_rows, columns, held, extent = _inspect(raw, byte_limit, working_limit)
    context = _context_snapshot(context, columns)
    need(V.digest(feature_sha256) and _integer(feature_bytes, rows*30*8+1, rows*30*8+8192)
         and type(feature_fortran_order) is bool,
         'One declared primitive NPY feature hash, bounded extent and order')
    need(_integer(descriptor_limit, 1, MAX_DESCRIPTOR_BYTES), 'Finite compact descriptor output cap')
    reserve = _decode_reserve(extent, rows) + 3*MAX_DESCRIPTOR_BYTES
    need(reserve <= working_limit, 'Joint decode/descriptor admission before allocation')
    decode_bundle(raw, byte_limit=byte_limit, working_limit=working_limit)
    public = {
        'schema': REQUEST_SCHEMA,
        'context': context.descriptor(held),
        'features': {'sha256': feature_sha256, 'bytes': feature_bytes,
                     'format': 'npy', 'dtype': '<f8', 'shape': [rows, 30],
                     'fortran_order': feature_fortran_order},
        'response_maps': {'schema': BUNDLE_SCHEMA, 'sha256': hashlib.sha256(raw).hexdigest(),
                          'bytes': extent, 'rows': rows, 'training_rows': training_rows,
                          'output_columns': columns},
        'row_selection': 'original-order:qids!=held(train);qids==held(query)',
        'prediction_shape': [rows-training_rows, columns],
    }
    encoded = (json.dumps(public, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()
    need(len(encoded) <= descriptor_limit, 'Compact descriptor exceeds supplied output cap')
    return RequestDescriptor(encoded, hashlib.sha256(encoded).hexdigest())
