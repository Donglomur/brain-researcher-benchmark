"""Lazy selected-cluster reader for the fixed NEURAL-099 source profile.

No h5py/NumPy import, file opening, authentication, or runtime initialization is
performed here. The caller supplies the exact pinned per-asset SCHEMA_BOUNDS
record and keeps its authenticated descriptor and HDF5 handle open throughout
iteration. The caller also establishes the approved plugin/runtime profile.

Returned logical hyperslabs contain only selected units. A native storage chunk
may span selected and unassigned units and decompress both internally. Logical
slice limits therefore do not measure physical I/O or total native memory.
"""


SPIKE_PATH = 'units/spike_times'
INDEX_PATH = 'units/spike_times_index'
NAMED_REGIONS = ('BIC', 'MGd', 'MGm', 'MGv', 'MZMG', 'SG')
MAX_SPIKES_PER_SLICE = 65536
MAX_NATIVE_CHUNK_BYTES = 1048576
ALLOWED_FILTER_IDS = (1, 2, 3)
# Exact maxima in the pinned retained metadata profile (0248fbfc...).
MAX_SOURCE_EVENTS = 86703
MAX_SOURCE_UNITS = 153


class EventSourceError(ValueError):
    """Source metadata, storage layout, or ragged index violates the profile."""


def _require(condition, message):
    if not condition:
        raise EventSourceError(message)


def _integer(value, label, minimum=0, maximum=None):
    _require(type(value) is int and value >= minimum, label + ' must be a bounded integer')
    if maximum is not None:
        _require(value <= maximum, label + ' exceeds the authenticated profile maximum')
    return value


def _field(value, key, label):
    _require(type(value) is dict and key in value, label + ' is missing ' + key)
    return value[key]


def _array_extent(asset, field, path, dtype, maximum):
    descriptor = _field(asset, field, 'asset bounds')
    _require(_field(descriptor, 'path', field) == path, 'Unexpected source array path')
    _require(_field(descriptor, 'dtype', field) == dtype, 'Unexpected declared source dtype')
    shape = _field(descriptor, 'shape', field)
    _require(type(shape) is list and len(shape) == 1, 'Expected a one-dimensional source extent')
    extent = _integer(shape[0], field + ' extent', maximum=maximum)
    _require(_field(descriptor, 'logical_bytes', field) == extent * 8,
             'Declared logical array bytes disagree with the extent')
    return extent


def _frozen_selection(asset):
    aid = _field(asset, 'asset_id', 'asset bounds')
    _require(type(aid) is str and 0 < len(aid) <= 256, 'Expected bounded source asset identity')
    event_count = _array_extent(asset, 'spike_times', SPIKE_PATH, 'float64', MAX_SOURCE_EVENTS)
    unit_count = _array_extent(asset, 'spike_times_index', INDEX_PATH, 'uint64', MAX_SOURCE_UNITS)
    rows = _field(asset, 'source_unit_row_values', 'asset bounds')
    _require(type(rows) is list and len(rows) == unit_count and unit_count > 0,
             'Frozen unit rows must match the complete index extent')
    selected, unassigned, ids = [], [], set()
    for ordinal, row in enumerate(rows):
        _require(type(row) is list and len(row) == 3, 'Unexpected frozen unit-row encoding')
        identifier, region, quality = row
        _integer(identifier, 'source unit ID')
        _require(identifier not in ids, 'Repeated source unit ID within one asset')
        ids.add(identifier)
        _require(type(region) is str and region in NAMED_REGIONS + (' ',),
                 'Unreviewed literal source anatomy')
        _require(type(quality) is str and quality in ('good', 'mua'),
                 'Unreviewed source quality')
        (selected if region in NAMED_REGIONS else unassigned).append(ordinal)
    for field, expected in (('eligible_unit_row_ordinals', selected),
                             ('unassigned_unit_row_ordinals', unassigned)):
        supplied = _field(asset, field, 'asset bounds')
        _require(type(supplied) is list and all(type(x) is int for x in supplied)
                 and supplied == expected, 'Selection must equal the complete frozen anatomy policy')
    _require(selected, 'Source asset has no selected named anatomy')
    _require(_field(asset, 'eligible_cluster_count', 'asset bounds') == len(selected)
             and _field(asset, 'unassigned_cluster_count', 'asset bounds') == len(unassigned),
             'Frozen source cluster counts disagree with row selection')
    # Copy the small frozen rows so later caller mutations cannot alter selection
    # after the index is authenticated against this descriptor.
    return aid, event_count, tuple(tuple(row) for row in rows), tuple(selected)


def _dataset(handle, path, h5api, expected_rows, expected_kind):
    _require(path in (SPIKE_PATH, INDEX_PATH), 'Array is outside the event read allowlist')
    current = handle
    parts = path.split('/')
    for position, name in enumerate(parts):
        _require(isinstance(current.get(name, getlink=True), h5api.HardLink),
                 'Indirect or missing source path component')
        current = current[name]
        if position < len(parts) - 1:
            _require(isinstance(current, h5api.Group), 'Source path ancestor is not a group')
    _require(isinstance(current, h5api.Dataset), 'Source array is not a dataset')
    _require(not current.is_virtual and not current.external,
             'Virtual or externally stored event arrays are forbidden')
    _require(current.shape == (expected_rows,), 'Source dataset shape differs from the frozen extent')
    dtype = current.dtype
    _require(dtype.kind == expected_kind and dtype.itemsize == 8
             and dtype.fields is None and dtype.subdtype is None,
             'Expected float64 events and uint64 cumulative index endpoints')
    chunks = current.chunks
    if chunks is not None:
        _require(type(chunks) is tuple and len(chunks) == 1
                 and type(chunks[0]) is int and chunks[0] > 0
                 and chunks[0] * 8 <= MAX_NATIVE_CHUNK_BYTES,
                 'Source chunk exceeds the native decoded-chunk bound')
    creation = current.id.get_create_plist()
    count = creation.get_nfilters()
    _require(type(count) is int and 0 <= count <= len(ALLOWED_FILTER_IDS),
             'Unreviewed HDF5 filter pipeline')
    seen = set()
    for position in range(count):
        identifier = creation.get_filter(position)[0]
        _require(type(identifier) is int and identifier in ALLOWED_FILTER_IDS
                 and identifier not in seen, 'Unreviewed HDF5 filter or plugin')
        seen.add(identifier)
    _require(not seen or chunks is not None, 'Filtered source array has no bounded chunk layout')
    return current


def _target_is_spikes(handle, index, spikes, h5api):
    try:
        target = index.attrs['target']
    except KeyError as exc:
        raise EventSourceError('Index has no target object reference') from exc
    # A region reference or a string path is not the NWB VectorIndex target.
    _require(type(target) is h5api.Reference and bool(target),
             'Index target must be a nonnull HDF5 object reference')
    try:
        resolved = handle[target]
    except (KeyError, ValueError, TypeError, RuntimeError) as exc:
        raise EventSourceError('Index target object cannot be resolved') from exc
    _require(isinstance(resolved, h5api.Dataset) and resolved.id == spikes.id,
             'Index target is not the exact authenticated spike_times dataset')


def _index_values(index, unit_count, event_count):
    values = index[()].tolist()
    _require(type(values) is list and len(values) == unit_count,
             'Decoded index differs from its authenticated extent')
    previous = 0
    for value in values:
        _integer(value, 'cumulative index endpoint', maximum=event_count)
        _require(value >= previous, 'Cumulative index endpoints decrease')
        previous = value
    _require(previous == event_count, 'Final cumulative endpoint does not cover the declared event extent')
    return values


def _chunks(spikes, global_start, global_stop):
    """Yield exact stored values without sorting, filtering, or concatenation.

    Counting kernels independently validate finite values and within-unit order.
    Python lists/float objects consume more RAM than their logical float64 bytes.
    """
    cursor = global_start
    while cursor < global_stop:
        stop = min(cursor + MAX_SPIKES_PER_SLICE, global_stop)
        raw = spikes[cursor:stop]
        _require(raw.shape == (stop - cursor,), 'Decoded event slice length mismatch')
        dtype = raw.dtype
        _require(dtype.kind == 'f' and dtype.itemsize == 8
                 and dtype.fields is None and dtype.subdtype is None,
                 'Decoded event slice dtype mismatch')
        values = raw.tolist()
        _require(type(values) is list and len(values) == stop - cursor
                 and all(type(value) is float for value in values),
                 'Decoded event slice must preserve every float64 value')
        yield {'source_start': cursor - global_start, 'spikes': values}
        cursor = stop


def iter_selected_clusters(handle, *, h5api, asset_bounds):
    """Yield frozen eligible clusters and their one-pass lazy spike iterators.

    All storage headers and the target identity are checked before index values
    are decoded. Only the complete, bounded index is read during descriptor
    iteration. Spike values are read when the caller consumes ``chunks``.

    Each descriptor contains asset_id, source_unit_row, cluster_id, region,
    quality, declared_spike_count, source_global_start/source_global_stop, and
    chunks. Each chunk contains exactly source_start (unit-relative offset) and
    spikes (a Python float list, at most 65,536 values). Empty eligible clusters
    remain descriptors with an empty chunk iterator. IDs are asset-scoped.
    """
    aid, event_count, rows, selected = _frozen_selection(asset_bounds)
    spikes = _dataset(handle, SPIKE_PATH, h5api, event_count, 'f')
    index = _dataset(handle, INDEX_PATH, h5api, len(rows), 'u')
    _target_is_spikes(handle, index, spikes, h5api)
    endpoints = _index_values(index, len(rows), event_count)
    for ordinal in selected:
        identifier, region, quality = rows[ordinal]
        start = endpoints[ordinal - 1] if ordinal else 0
        stop = endpoints[ordinal]
        yield {
            'asset_id': aid, 'source_unit_row': ordinal, 'cluster_id': identifier,
            'region': region, 'quality': quality, 'declared_spike_count': stop - start,
            'source_global_start': start, 'source_global_stop': stop,
            'chunks': _chunks(spikes, start, stop),
        }
