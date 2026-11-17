"""Minimal portable metadata seam for the fixed conditional source profile.

The caller authenticates the complete source file before opening the supplied
handle and establishes the approved runtime/plugin environment. This module
imports no HDF5/NumPy package and opens no file. It reads only four metadata
columns, never spike, index, trial, waveform, or image values.

String rows are decoded individually and returned labels are bounded. Variable
length strings still require native heap allocation before Python can inspect
their length: dtype itemsize, row/slice limits and chunk descriptor bounds do NOT
bound that heap or total native RAM. The separately admitted process must account
for this limitation. Complete authenticated source hashes precede these reads.
"""

from collections import Counter
import re


REGIONS = ('BIC', 'MGd', 'MGm', 'MGv', 'MZMG', 'SG')
QUALITIES = ('good', 'mua')
MAX_UNITS = 153
MAX_EVENTS = 86703
MAX_ELECTRODES = 4096
MAX_TRIALS = 206
MAX_STRING_BYTES = 64
MAX_CHUNK_BYTES = 1048576
FILTERS = (1, 2, 3)
TABLE = 'general/extracellular_ephys/electrodes'
VALUE_PATHS = ('units/id', 'units/electrodes', 'units/quality', TABLE + '/location')
PROTECTED_PATHS = ('units/spike_times', 'units/spike_times_index',
                   'intervals/trials/id', 'intervals/trials/start_time',
                   'intervals/trials/stop_time')
OPTIONAL_PROTECTED = ('units/waveforms', 'units/waveforms_index')


class MetadataSourceError(ValueError):
    pass


def _require(condition, message):
    if not condition:
        raise MetadataSourceError(message)


def _field(obj, key, label):
    _require(type(obj) is dict and key in obj, label + ' is missing ' + key)
    return obj[key]


def _integer(value, label, minimum=0, maximum=None):
    _require(type(value) is int and value >= minimum
             and (maximum is None or value <= maximum), 'Invalid ' + label)
    return value


def _text(value, label, maximum=4096):
    _require(type(value) is str and 0 < len(value) <= maximum
             and all(ord(c) >= 32 for c in value), 'Invalid ' + label)
    return value


def _ids(value, label):
    _require(type(value) is list and len(value) <= MAX_UNITS, 'Invalid ' + label)
    for number in value:
        _integer(number, label)
    _require(len(set(value)) == len(value), 'Repeated source unit identifier')
    return set(value)


def _quality_counts(value, count):
    _require(type(value) is dict and set(value) <= set(QUALITIES), 'Unknown declared quality')
    for number in value.values():
        _integer(number, 'declared quality count', 1, MAX_UNITS)
    _require(sum(value.values()) == count, 'Declared quality counts differ from membership')
    return dict(value)


def _declaration(source, declared):
    identity = {key: _text(_field(source, key, 'source'), key)
                for key in ('asset_id', 'path', 'sha256', 'subject_id')}
    identity['bytes'] = _integer(_field(source, 'bytes', 'source'), 'source bytes', 1)
    _require(re.fullmatch(r'[0-9a-f]{64}', identity['sha256']) is not None,
             'Source SHA-256 must be explicit')
    _require(_field(declared, 'asset_id', 'declared support') == identity['asset_id']
             and _field(declared, 'source_subject_id', 'declared support') == identity['subject_id']
             and _field(declared, 'source_asset', 'declared support') ==
             {key: identity[key] for key in ('path', 'bytes', 'sha256')},
             'Source and declared support identities differ')
    trial_rows = _integer(_field(declared, 'source_trial_rows', 'declared support'),
                          'source trial rows', 1, MAX_TRIALS)
    regions = _field(declared, 'regions', 'declared support')
    _require(type(regions) is list and 0 < len(regions) <= len(REGIONS), 'Named support is required')
    membership, qualities, all_ids = {}, {}, set()
    for cell in regions:
        region = _field(cell, 'region', 'region support')
        _require(type(region) is str and region in REGIONS and region not in membership,
                 'Unknown or repeated named region')
        ids = _ids(_field(cell, 'cluster_ids', 'region support'), 'declared region cluster IDs')
        count = _integer(_field(cell, 'cluster_count', 'region support'), 'region count', 1, MAX_UNITS)
        _require(count == len(ids) and not all_ids & ids, 'Overlapping or inconsistent regional membership')
        membership[region] = ids
        qualities[region] = _quality_counts(_field(cell, 'quality_counts', 'region support'), count)
        all_ids.update(ids)
    unassigned = _ids(_field(declared, 'unassigned_cluster_ids', 'declared support'),
                      'declared unassigned cluster IDs')
    _require(not all_ids & unassigned, 'Assigned and unassigned source membership overlap')
    _require(_integer(_field(declared, 'unassigned_cluster_count', 'declared support'),
                      'unassigned count', 0, MAX_UNITS) == len(unassigned),
             'Unassigned count differs from membership')
    qualities[' '] = _quality_counts(_field(declared, 'unassigned_quality_counts', 'declared support'),
                                     len(unassigned))
    all_ids.update(unassigned)
    _require(0 < len(all_ids) <= MAX_UNITS, 'Source units exceed the fixed profile')
    membership[' '] = unassigned
    return identity, trial_rows, membership, qualities, all_ids


def _hard_object(handle, path, h5api, *, optional=False):
    current = handle
    parts = path.split('/')
    for index, name in enumerate(parts):
        link = current.get(name, getlink=True)
        if link is None and optional and index == len(parts) - 1:
            return None
        _require(isinstance(link, h5api.HardLink), 'Indirect or missing source path component')
        current = current[name]
        if index < len(parts) - 1:
            _require(isinstance(current, h5api.Group), 'Source path ancestor is not a group')
    return current


def _storage(dataset, h5api):
    _require(isinstance(dataset, h5api.Dataset), 'Expected a source dataset')
    _require(not dataset.is_virtual and not dataset.external, 'External or virtual source storage is forbidden')
    dtype = dataset.dtype
    _require(dtype.fields is None and dtype.subdtype is None, 'Compound/subarray metadata dtype is unreviewed')
    itemsize = _integer(dtype.itemsize, 'dtype itemsize', 1, MAX_CHUNK_BYTES)
    chunks = dataset.chunks
    if chunks is not None:
        _require(type(chunks) is tuple and chunks and all(type(n) is int and n > 0 for n in chunks),
                 'Invalid source storage chunk shape')
        size = itemsize
        for extent in chunks:
            size *= extent
            _require(size <= MAX_CHUNK_BYTES, 'Source chunk exceeds the reviewed descriptor/element bound')
    creation = dataset.id.get_create_plist()
    count = creation.get_nfilters()
    _require(type(count) is int and 0 <= count <= len(FILTERS), 'Unreviewed filter pipeline')
    seen = set()
    for i in range(count):
        filter_id = creation.get_filter(i)[0]
        _require(type(filter_id) is int and filter_id in FILTERS and filter_id not in seen,
                 'Unreviewed HDF5 filter or plugin')
        seen.add(filter_id)
    _require(not seen or chunks is not None, 'Filtered source storage lacks a bounded chunk layout')


def _numeric(dataset, h5api, kinds, expected=None, maximum=None, itemsize=8):
    _storage(dataset, h5api)
    shape = dataset.shape
    _require(type(shape) is tuple and len(shape) == 1 and type(shape[0]) is int
             and shape[0] >= 0, 'Expected a one-dimensional numeric metadata/header array')
    if expected is not None:
        _require(shape == (expected,), 'Source shape differs from declared membership')
    if maximum is not None:
        _require(shape[0] <= maximum, 'Source header exceeds the fixed profile')
    _require(dataset.dtype.kind in kinds and dataset.dtype.itemsize == itemsize, 'Unreviewed numeric source dtype')
    return shape[0]


def _string(dataset, h5api, *, expected=None):
    _storage(dataset, h5api)
    shape = dataset.shape
    _require(type(shape) is tuple and len(shape) == 1 and type(shape[0]) is int
             and 0 < shape[0] <= MAX_ELECTRODES, 'String row count exceeds the metadata bound')
    if expected is not None:
        _require(shape == (expected,), 'String row count differs from source membership')
    info = h5api.check_string_dtype(dataset.dtype)
    _require(info is not None and info.encoding in ('utf-8', 'ascii'),
             'Only reviewed HDF5 UTF-8/ASCII string dtypes are permitted')
    if info.length is None:
        _require(dataset.dtype.kind == 'O', 'Unexpected variable-length string representation')
    else:
        _integer(info.length, 'fixed string length', 1, MAX_STRING_BYTES)
        _require(dataset.dtype.kind == 'S' and dataset.dtype.itemsize == info.length,
                 'Unexpected fixed string representation')
    if dataset.chunks is not None:
        _require(len(dataset.chunks) == 1 and dataset.chunks[0] <= MAX_ELECTRODES,
                 'String storage chunk contains too many descriptors')
    return shape[0], info.encoding


def _integer_values(dataset, count):
    values = dataset[()].tolist()
    _require(type(values) is list and len(values) == count
             and all(type(value) is int for value in values), 'Decoded integer metadata shape/type differs')
    return values


def _string_values(dataset, count, encoding):
    result = []
    for i in range(count):
        values = dataset[i:i + 1].tolist()
        _require(type(values) is list and len(values) == 1, 'String metadata row did not preserve shape')
        value = values[0]
        try:
            if type(value) is bytes:
                _require(len(value) <= MAX_STRING_BYTES, 'Decoded string exceeds the output bound')
                value = value.decode(encoding, errors='strict')
            elif type(value) is str:
                _require(len(value.encode(encoding, errors='strict')) <= MAX_STRING_BYTES,
                         'Decoded string exceeds the output bound')
            else:
                raise MetadataSourceError('HDF5 string row decoded to an unreviewed type')
        except UnicodeError as exc:
            raise MetadataSourceError('String metadata violates its declared encoding') from exc
        result.append(value)
    return result


def _header(path, count, dtype):
    # Storage layout was checked but is not added to this frozen schema seam.
    return {'path': path, 'shape': [count], 'dtype': dtype, 'logical_bytes': count * 8,
            'storage_chunk_shape': None, 'filter_pipeline': None, 'values_decoded': False}


def read_metadata(handle, *, h5api, source, declared):
    """Return one SCHEMA_BOUNDS-compatible asset without event/index/trial values.

    Numeric unit columns are read once; strings are read in one-row slices.
    All headers, protected-object aliases, and the contact-table reference are
    checked before the first metadata value read. No group-location fallback,
    label trimming, quality reclassification, or unit sorting is applied.
    """
    identity, trial_rows, membership, quality_counts, all_ids = _declaration(source, declared)
    unit_count = len(all_ids)
    units = _hard_object(handle, 'units', h5api)
    _require(isinstance(units, h5api.Group), 'Units must be a group')
    _require(units.get('electrodes_index', getlink=True) is None,
             'Ragged/multiple-contact units need separate source review')
    protected = {path: _hard_object(handle, path, h5api) for path in PROTECTED_PATHS}
    events = _numeric(protected['units/spike_times'], h5api, 'f', maximum=MAX_EVENTS)
    _numeric(protected['units/spike_times_index'], h5api, 'u', expected=unit_count, maximum=MAX_UNITS)
    _numeric(protected['intervals/trials/id'], h5api, 'i', expected=trial_rows, maximum=MAX_TRIALS)
    for path in ('intervals/trials/start_time', 'intervals/trials/stop_time'):
        _numeric(protected[path], h5api, 'f', expected=trial_rows, maximum=MAX_TRIALS)
    for path in OPTIONAL_PROTECTED:
        value = _hard_object(handle, path, h5api, optional=True)
        if value is not None:
            _storage(value, h5api)
            protected[path] = value
    metadata = {path: _hard_object(handle, path, h5api) for path in VALUE_PATHS}
    for dataset in metadata.values():
        _require(isinstance(dataset, h5api.Dataset), 'Metadata column must be a dataset')
        _require(all(dataset.id != target.id for target in protected.values()),
                 'Metadata aliases a protected event/index/trial/waveform object')
    # All 26 authenticated source headers use signed32 IDs and signed64 contacts.
    # This field-specific requirement does not relax 64-bit event/index/timing guards.
    _numeric(metadata['units/id'], h5api, 'i', expected=unit_count, maximum=MAX_UNITS, itemsize=4)
    _numeric(metadata['units/electrodes'], h5api, 'i', expected=unit_count, maximum=MAX_UNITS)
    quality_rows, quality_encoding = _string(metadata['units/quality'], h5api, expected=unit_count)
    location_rows, location_encoding = _string(metadata[TABLE + '/location'], h5api)
    table = _hard_object(handle, TABLE, h5api)
    _require(isinstance(table, h5api.Group), 'Electrode table must be the selected group')
    reference = metadata['units/electrodes'].attrs.get('table')
    _require(type(reference) is h5api.Reference and bool(reference), 'Contact table needs an object reference')
    try:
        target = handle[reference]
    except (KeyError, ValueError, TypeError, RuntimeError) as exc:
        raise MetadataSourceError('Contact table reference could not be resolved') from exc
    _require(isinstance(target, h5api.Group) and target.id == table.id,
             'Contact reference points outside the exact electrode table')
    identifiers = _integer_values(metadata['units/id'], unit_count)
    contacts = _integer_values(metadata['units/electrodes'], unit_count)
    qualities = _string_values(metadata['units/quality'], quality_rows, quality_encoding)
    locations = _string_values(metadata[TABLE + '/location'], location_rows, location_encoding)
    _require(len(set(identifiers)) == unit_count and set(identifiers) == all_ids,
             'Source unit membership differs from the declaration')
    _require(all(0 <= contact < location_rows for contact in contacts), 'Contact row is outside electrode table')
    _require(all(value in QUALITIES for value in qualities), 'Unreviewed source quality label')
    rows = [[identifier, locations[contact], quality]
            for identifier, contact, quality in zip(identifiers, contacts, qualities)]
    _require(all(row[1] in REGIONS + (' ',) for row in rows), 'Unreviewed literal unit location')
    observed_membership = {region: {row[0] for row in rows if row[1] == region}
                           for region in REGIONS + (' ',)}
    for region in REGIONS + (' ',):
        _require(observed_membership[region] == membership.get(region, set()),
                 'Assigned/unassigned anatomical membership differs from the declaration')
        observed_quality = dict(Counter(row[2] for row in rows if row[1] == region))
        _require(observed_quality == quality_counts.get(region, {}),
                 'Source quality counts differ from the declaration')
    selected = [i for i, row in enumerate(rows) if row[1] in REGIONS]
    unassigned = [i for i, row in enumerate(rows) if row[1] == ' ']
    named_count = len([region for region in REGIONS if observed_membership[region]])
    return {
        'asset_id': identity['asset_id'], 'source_subject_id': identity['subject_id'],
        'source_path': identity['path'], 'source_bytes': identity['bytes'], 'source_sha256': identity['sha256'],
        'spike_times': _header('units/spike_times', events, 'float64'),
        'spike_times_index': _header('units/spike_times_index', unit_count, 'uint64'),
        'source_unit_row_values': rows, 'eligible_unit_row_ordinals': selected,
        'unassigned_unit_row_ordinals': unassigned, 'eligible_cluster_count': len(selected),
        'unassigned_cluster_count': len(unassigned), 'source_trial_rows': trial_rows,
        'named_region_cell_count': named_count, 'trial_region_case_count': trial_rows * named_count,
        'selected_spike_event_count': None, 'selected_contiguous_event_slice_bounds': None,
        'observed_per_unit_event_counts': None,
    }
