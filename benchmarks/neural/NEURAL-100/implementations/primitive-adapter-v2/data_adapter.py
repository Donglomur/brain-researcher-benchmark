"""Validated primitive-to-count adapter for the unchanged NEURAL-100 analysis.

Successor to investigation/source_repository/private/data_adapter.py. The
operator must repin this source before selecting it; this module does not alter
an existing source capsule or authorize a scientific run. Input timestamps are
native seconds. Output is integer spike counts in the original 100 half-open
1-ms bins [-50, 50) relative to each native click trial start.

Trial stops describe the stimulus pulse, not recording observation intervals.
Valid primitives do not establish complete observation or physical calibration.
"""
import ast
import hashlib
import io
from pathlib import Path
import zipfile

import numpy as np
from artifact_io import capture_regular, decode_json


CODES = {0: 'outside', 1: 'L1', 23: 'L23', 4: 'L4', 5: 'L5', 6: 'L6'}
KEYS = {'unit_id', 'unit_electrode', 'spike_times', 'spike_end',
        'trial_start', 'trial_stop', 'electrode_id', 'electrode_y', 'electrode_layer'}
MAX_COUNT_BYTES = 100_000_000
MAX_ARRAY_BYTES = 8_000_000
MAX_NPY_HEADER_BYTES = 10_000


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _vector(value, name, integer=False):
    _need(isinstance(value, np.ndarray) and value.ndim == 1 and
          value.dtype.kind in 'iuf', name + ': one-dimensional numeric array required')
    _need(np.isfinite(value).all(), name + ': finite values required')
    if integer and value.dtype.kind == 'f':
        _need((np.abs(value) <= 2 ** 53).all() and (value == np.floor(value)).all(),
              name + ': exactly represented integer values required')
    return value


def validate_primitives(arrays):
    """Validate all joins and ragged segments before allocating count storage.

    Preserve released order, coincident spikes, contacts without units, and
    different layer labels at the same depth. Reject malformed input rather
    than sorting, truncating, relabeling, or dropping a unit/trial.
    """
    _need(type(arrays) is dict and set(arrays) == KEYS, 'exact primitive array fields required')
    integer_fields = {'unit_id', 'unit_electrode', 'spike_end', 'electrode_id', 'electrode_layer'}
    a = {key: _vector(arrays[key], key, key in integer_fields) for key in KEYS}
    units, trials, contacts = len(a['unit_id']), len(a['trial_start']), len(a['electrode_id'])
    _need(len(a['unit_electrode']) == len(a['spike_end']) == units,
          'one contact-table row and ragged endpoint per source unit required')
    _need(len(a['trial_stop']) == trials, 'one native pulse stop per trial start required')
    _need(contacts > 0 and len(a['electrode_y']) == len(a['electrode_layer']) == contacts,
          'complete nonempty contact table required')
    _need(len(np.unique(a['unit_id'])) == units, 'unique source unit IDs required')
    _need(len(np.unique(a['electrode_id'])) == contacts, 'unique source contact IDs required')
    indices = a['unit_electrode']
    _need((indices >= 0).all() and (indices < contacts).all(),
          'unit_electrode must be a nonnegative contact-table row, not a contact ID')
    _need(np.isin(a['electrode_layer'], tuple(CODES)).all(), 'known released layer codes required')

    ends = a['spike_end']
    spike_count = len(a['spike_times'])
    _need((ends >= 0).all() and (ends <= spike_count).all() and
          (ends[1:] >= ends[:-1]).all() and
          (int(ends[-1]) == spike_count if units else spike_count == 0),
          'ragged endpoints must partition the entire spike vector without reversal')
    lo = 0
    for endpoint in ends:
        hi = int(endpoint)
        segment = a['spike_times'][lo:hi]
        _need((segment[1:] >= segment[:-1]).all(), 'each unit spike segment must be chronological')
        lo = hi

    starts, stops = a['trial_start'], a['trial_stop']
    _need((stops > starts).all(), 'native click pulse stop must follow its start')
    _need((starts - .05 >= 0).all() and (starts[1:] - .05 >= starts[:-1] + .05).all(),
          'nonnegative nonoverlapping complete analysis windows required')
    _need(trials * units * 100 * np.dtype(np.uint32).itemsize <= MAX_COUNT_BYTES,
          'per-record count memory cap')
    return a


def normalized(record, arrays):
    """Return the existing analysis_core record shape without changing units."""
    _need(type(record) is dict and all(type(record.get(key)) is str and record[key]
          for key in ('asset_id', 'participant_id')) and record.get('area') in ('A1', 'A2'),
          'source recording, participant and area identities required')
    a = validate_primitives(arrays)
    starts = a['trial_start']
    edges = np.arange(-50, 51, dtype=np.float64) / 1000
    counts = np.empty((len(starts), len(a['unit_id']), 100), dtype=np.uint32)
    lo = 0
    for unit, endpoint in enumerate(a['spike_end']):
        hi = int(endpoint)
        spikes = a['spike_times'][lo:hi]
        lo = hi
        for trial, start in enumerate(starts):
            bins = np.diff(np.searchsorted(spikes, start + edges, side='left'))
            _need((bins <= np.iinfo(np.uint32).max).all(), 'spike count exceeds uint32 storage')
            counts[trial, unit] = bins
    depths = sorted(set(a['electrode_y'].tolist()))
    rank = {depth: index for index, depth in enumerate(depths)}
    contacts = [{'electrode_id': int(identifier), 'depth_rank': rank[depth],
                 'layer': CODES[int(layer)]}
                for identifier, depth, layer in zip(a['electrode_id'], a['electrode_y'], a['electrode_layer'])]
    return {'recording_id': record['asset_id'], 'participant_id': record['participant_id'],
            'area': record['area'], 'counts': counts,
            'unit_electrode_id': [int(a['electrode_id'][int(index)]) for index in a['unit_electrode']],
            'electrodes': contacts}


def _preflight_npy(archive, member):
    """Validate bounded NPY declarations without materializing an array.

    ZIP file_size alone does not bound np.load's allocation: its allocation
    follows the NPY header's shape, even for a truncated physical payload.
    Check every member before loading any of them.
    """
    _need(member.compress_type == zipfile.ZIP_STORED and not member.flag_bits & 1,
          'uncompressed unencrypted primitive NPY members required')
    with archive.open(member) as stream:
        prefix = stream.read(8)
        _need(len(prefix) == 8 and prefix[:6] == b'\x93NUMPY', 'primitive NPY magic required')
        version = tuple(prefix[6:8])
        _need(version in ((1, 0), (2, 0), (3, 0)), 'supported primitive NPY version required')
        size_bytes = 2 if version == (1, 0) else 4
        raw_size = stream.read(size_bytes)
        _need(len(raw_size) == size_bytes, 'complete primitive NPY header length required')
        header_size = int.from_bytes(raw_size, 'little')
        _need(0 < header_size <= MAX_NPY_HEADER_BYTES, 'bounded primitive NPY header required')
        header = stream.read(header_size)
        _need(len(header) == header_size and header.endswith(b'\n'), 'complete primitive NPY header required')
        try:
            declaration = ast.literal_eval(header.decode('utf-8' if version == (3, 0) else 'latin1'))
        except (ValueError, SyntaxError, UnicodeError, RecursionError) as error:
            raise ValueError('invalid primitive NPY header') from error
        _need(type(declaration) is dict and set(declaration) == {'descr', 'fortran_order', 'shape'},
              'exact primitive NPY header fields required')
        shape = declaration['shape']
        _need(type(shape) is tuple and len(shape) == 1 and type(shape[0]) is int and shape[0] >= 0,
              'one-dimensional primitive NPY shape required')
        _need(type(declaration['fortran_order']) is bool and type(declaration['descr']) is str,
              'primitive NPY dtype/order declarations required')
        try:
            dtype = np.dtype(declaration['descr'])
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError('invalid primitive NPY dtype') from error
        _need(dtype.kind in 'iuf' and not dtype.hasobject and dtype.itemsize > 0,
              'nonobject numeric primitive NPY dtype required')
        payload_size = shape[0] * dtype.itemsize
        _need(payload_size <= MAX_ARRAY_BYTES and
              8 + size_bytes + header_size + payload_size == member.file_size,
              'primitive NPY declared payload must exactly match bounded physical bytes')


def records(packet, manifest):
    """Consume the same pinned primitive NPZ members, one recording at a time."""
    for row in manifest['recordings']:
        rel = Path(row['file'])
        if rel.is_absolute() or len(rel.parts) != 1 or rel.suffix != '.npz':
            raise ValueError('pinned sibling array archive')
        body = capture_regular(packet / rel, MAX_ARRAY_BYTES)
        if len(body) != row['pin']['bytes'] or hashlib.sha256(body).hexdigest() != row['pin']['sha256']:
            raise ValueError('selected array identity')
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            members = archive.infolist()
            if ({member.filename for member in members} != {key + '.npy' for key in KEYS}
                    or len(members) != len(KEYS) or sum(member.file_size for member in members) > MAX_ARRAY_BYTES):
                raise ValueError('primitive NPZ bounds')
            for member in members:
                _preflight_npy(archive, member)
        with np.load(io.BytesIO(body), allow_pickle=False) as archive:
            arrays = {key: archive[key] for key in KEYS}
        yield normalized(row, arrays)


def load_manifest(path, expected_sha):
    body = capture_regular(path, 4_000_000)
    if hashlib.sha256(body).hexdigest() != expected_sha:
        raise ValueError('operator packet manifest pin')
    manifest = decode_json(body)
    if manifest['status'] != 'complete' or len(manifest['recordings']) != 47:
        raise ValueError('complete47 source packet')
    return manifest
