"""Operator-only reader for the existing reward-spacing native exporter.

No discovery, downloads, trial inference, resampling or target normalization.
Source event row joins and unit evidence are supplied by the operator. The reader
authenticates the exact file before opening HDF5 and preserves stored samples.
"""
from contextlib import contextmanager
import copy
import hashlib
import math
import os
from pathlib import Path
import stat


class SourceError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise SourceError(message)


def sha256_text(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def stamp(info):
    return tuple(getattr(info, field) for field in
                 ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns'))


@contextmanager
def authenticated_file(item):
    """Hash and parse the same ordinary file descriptor, then recheck stability."""
    path = Path(item['path'])
    require(path.is_absolute(), 'explicit absolute source path required')
    require(type(item['bytes']) is int and 0 < item['bytes'] <= 1024 ** 3,
            'positive source size at most 1 GiB')
    require(sha256_text(item['sha256']), 'source SHA-256 required')
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode), 'source must be a regular file')
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, 'rb') as stream:
        opened = os.fstat(stream.fileno())
        require(stamp(before) == stamp(opened) and opened.st_size == item['bytes'],
                'source size or identity mismatch')
        checksum = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            checksum.update(block)
        require(checksum.hexdigest() == item['sha256'], 'source digest mismatch')
        stream.seek(0)
        yield stream
        require(stamp(opened) == stamp(os.fstat(stream.fileno())) == stamp(path.lstat()),
                'source changed during read')


def dataset(handle, path, h5py, cap, text=False, scalar=False):
    """Resolve only hard links; external/virtual storage cannot escape the pin."""
    group = handle
    parts = path.strip('/').split('/')
    for index, part in enumerate(parts):
        require(isinstance(group, h5py.Group), 'non-group in source path: ' + path)
        require(isinstance(group.get(part, getlink=True), h5py.HardLink),
                'missing or nonlocal HDF5 link: ' + path)
        group = group[part]
        if index < len(parts) - 1:
            require(isinstance(group, h5py.Group), 'non-group source ancestor')
    require(isinstance(group, h5py.Dataset), 'source dataset required: ' + path)
    require(not group.is_virtual and not group.external, 'external or virtual dataset')
    require(group.shape == () if scalar else group.ndim == 1 and len(group) <= cap,
            'bounded native dataset shape: ' + path)
    if text:
        require(h5py.check_string_dtype(group.dtype) is not None, 'text dataset required')
    else:
        require(group.dtype.kind in 'iuf', 'real numeric dataset required')
    return group


def decoded_text(value):
    if isinstance(value, bytes):
        value = value.decode('utf-8', errors='strict')
    require(isinstance(value, str) and 0 < len(value) <= 1024, 'bounded UTF-8 text')
    return value


def numbers(ds, label):
    values = ds[:].tolist()
    require(all(type(v) in (int, float) and math.isfinite(v) for v in values),
            'nonfinite or invalid ' + label)
    return values


def unit(ds):
    value = ds.attrs.get('unit')
    return None if value is None else decoded_text(value)


def read_session(item):
    """Return an exporter-compatible source object and a value-free receipt.

    `event_rows` maps source zero-based row numbers to reviewed id/trial_id.
    `excluded_event_rows` accounts for every remaining source row with a reason.
    Cues, outcomes and licking may not be excluded in appetitive recordings;
    cue_on, shock_on and shock_off may not be excluded in aversive recordings.
    Trial IDs are verified source joins supplied by the operator, not inferred.
    """
    import h5py

    require(type(item['max_samples']) is int and 2 <= item['max_samples'] <= 5_000_000,
            'explicit bounded native sample allocation')
    require(type(item['max_events']) is int and 1 <= item['max_events'] <= 1_000_000,
            'explicit bounded event allocation')
    require(item['event_layout'] in ('appetitive', 'aversive'), 'event layout')
    require(item['units_verified'] is True and sha256_text(item['unit_evidence_sha256']),
            'independent unit evidence required')
    require(sha256_text(item['event_join_evidence_sha256']), 'reviewed event join evidence required')
    require(set(item['expected_units']) == {'fluorescence', 'photometry_time', 'event_time'},
            'complete exact unit annotations')
    for name, value in item['expected_units'].items():
        require(value is None or isinstance(value, str) and value, 'unit annotation: ' + name)
    photo = '/processing/photometry/photometry_dff/'
    with authenticated_file(item) as stream:
        with h5py.File(stream, 'r') as handle:
            subject_ds = dataset(handle, '/general/subject/subject_id', h5py, 1, text=True, scalar=True)
            subject = decoded_text(subject_ds[()])
            require(subject == item['expected_source_subject_id'], 'source subject mismatch')
            clock_ds = dataset(handle, photo + 'timestamps', h5py, item['max_samples'])
            values_ds = dataset(handle, photo + 'data', h5py, item['max_samples'])
            require(clock_ds.shape == values_ds.shape and len(clock_ds) >= 2, 'native signal shape')
            if item['event_layout'] == 'appetitive':
                root = '/acquisition/eventLog/'
                event_ds = dataset(handle, root + 'event_code', h5py, item['max_events'])
                flag_ds = dataset(handle, root + 'event_flag', h5py, item['max_events'])
                event_clock_ds = dataset(handle, root + 'timestamp', h5py, item['max_events'])
                require(event_ds.shape == flag_ds.shape == event_clock_ds.shape, 'event table shape')
                codes, flags = numbers(event_ds, 'event codes'), numbers(flag_ds, 'event flags')
                require(all(float(x).is_integer() for x in codes + flags), 'integer event code and flag')
                raw_events = [{'code': int(code), 'flag': int(flag)} for code, flag in zip(codes, flags)]
            else:
                root = '/acquisition/photometry_event_times/'
                event_ds = dataset(handle, root + 'event_type', h5py, item['max_events'], text=True)
                event_clock_ds = dataset(handle, root + 'timestamp', h5py, item['max_events'])
                require(event_ds.shape == event_clock_ds.shape, 'aversive event table shape')
                names = [decoded_text(x) for x in event_ds[:].tolist()]
                raw_events = [{'kind': 'cue' if name == 'cue_on' else name} for name in names]
            actual_units = {'fluorescence': unit(values_ds), 'photometry_time': unit(clock_ds),
                            'event_time': unit(event_clock_ds)}
            require(actual_units == item['expected_units'], 'source unit annotation mismatch')
            times, values = numbers(clock_ds, 'native clock'), numbers(values_ds, 'stored fluorescence')
            event_times = numbers(event_clock_ds, 'event clock')
            require(all(b > a for a, b in zip(times, times[1:])), 'strictly increasing native clock')
            require(all(b >= a for a, b in zip(event_times, event_times[1:])), 'ordered source events')
            for event, time in zip(raw_events, event_times):
                event['time'] = time
    mapped, exclusions = {}, {}
    for row in item['event_rows']:
        require(set(row) == {'source_row', 'id', 'trial_id'}, 'source event join fields')
        position = row['source_row']
        require(type(position) is int and 0 <= position < len(raw_events) and position not in mapped,
                'duplicate or invalid source event join')
        require(all(isinstance(row[k], str) and row[k] for k in ('id', 'trial_id')), 'event and trial identity')
        mapped[position] = row
    require(len({row['id'] for row in mapped.values()}) == len(mapped), 'duplicate exported event identity')
    for row in item['excluded_event_rows']:
        require(set(row) == {'source_row', 'reason'}, 'event exclusion fields')
        position = row['source_row']
        require(type(position) is int and 0 <= position < len(raw_events)
                and position not in mapped and position not in exclusions, 'invalid event exclusion')
        require(isinstance(row['reason'], str) and row['reason'].strip(), 'event exclusion reason')
        exclusions[position] = row['reason']
    require(set(mapped) | set(exclusions) == set(range(len(raw_events))), 'incomplete source event ledger')
    for position, event in enumerate(raw_events):
        required = (event.get('code') in (5, 6, 10, 15) or
                    event.get('code') == 7 and item['condition'] in ('60s-CSminus', '600s-bgdmilk') or
                    event.get('kind') in ('cue', 'shock_on', 'shock_off'))
        require(not required or position in mapped, 'required source event excluded')
        if position in mapped:
            if item['event_layout'] == 'appetitive':
                require(event['code'] in (5, 6, 10, 15) or event['code'] == 7 and
                        item['condition'] in ('60s-CSminus', '600s-bgdmilk'), 'unregistered event semantics')
                require(event['code'] != 10 or event['flag'] in (0, 1), 'outcome omission flag')
            else:
                require(event['kind'] in ('cue', 'shock_on', 'shock_off'), 'unregistered aversive event')
    events = [dict(raw_events[i], id=mapped[i]['id'], trial_id=mapped[i]['trial_id']) for i in sorted(mapped)]
    receipt = {'schema': 'authenticated_reward_nwb_read_v1', 'asset_id': item['asset_id'],
               'source_sha256': item['sha256'], 'source_bytes': item['bytes'],
               'subject_id': subject, 'native_samples': len(times), 'source_event_rows': len(raw_events),
               'exported_event_rows': len(events), 'source_row_order': sorted(mapped),
               'excluded_event_rows': copy.deepcopy(item['excluded_event_rows']), 'unit_annotations': actual_units,
               'unit_evidence_sha256': item['unit_evidence_sha256'],
               'event_join_evidence_sha256': item['event_join_evidence_sha256'],
               'stored_values_transformed': False, 'native_clock_resampled': False,
               'biological_identity_inferred': False, 'scientific_qualification': False}
    return {'subject_id': subject, 'photometry_times': times, 'photometry_values': values,
            'events': events}, receipt


class _AuthenticatedNWBReader:
    """Internal decoder; the public export wrapper binds condition semantics."""

    def __init__(self, items):
        self.items, self.receipts = {}, []
        for item in items:
            require(isinstance(item['asset_id'], str) and item['asset_id']
                    and item['asset_id'] not in self.items, 'unique source asset identity')
            require(item['condition'].startswith('FC-') == (item['event_layout'] == 'aversive'),
                    'condition and event layout mismatch')
            self.items[item['asset_id']] = copy.deepcopy(item)

    def __call__(self, asset_id, sha256):
        require(asset_id in self.items and self.items[asset_id]['sha256'] == sha256,
                'exporter source binding mismatch')
        value, receipt = read_session(self.items[asset_id])
        self.receipts.append(receipt)
        return value


def export_authenticated_corpus(manifest, items, exporter):
    """Bind the full operator manifest before invoking the unchanged exporter.

    Pass the existing native_export.export_corpus as `exporter`. A bare
    reader(asset_id, sha256) call cannot bind a condition: code 7 means distractor
    under 60s-CSminus and delivered milk under 600s-bgdmilk. This preflight checks
    every asset's condition and source identity before any file can be opened.
    Reader receipts are retained in the returned corpus's operator-only ledger.
    """
    manifest = copy.deepcopy(manifest)
    native_reader = _AuthenticatedNWBReader(items)
    require(manifest['schema'] == 'reward_neural_native_export_manifest_v1'
            and manifest['source_access_authorized'] is True, 'authorized native export manifest')
    joined = set()
    for animal in manifest['animals']:
        for session in animal['sessions']:
            asset = session['asset_id']
            require(asset in native_reader.items and asset not in joined,
                    'complete unique exporter asset binding')
            joined.add(asset)
            item = native_reader.items[asset]
            require(item['condition'] == animal['condition'], 'reader/exporter condition mismatch')
            require(item['sha256'] == session['sha256'] and
                    item['expected_source_subject_id'] == session['expected_source_subject_id'],
                    'reader/exporter source identity mismatch')
            require(session['units_verified'] is True and item['units_verified'] is True,
                    'reader/exporter unit evidence missing')
            require(all(type(session[key]) in (int, float) for key in
                        ('timestamp_scale', 'clock_offset', 'fluorescence_scale'))
                    and session['timestamp_scale'] == 1 and session['clock_offset'] == 0
                    and session['fluorescence_scale'] == 1,
                    'native stored target and clock must remain untransformed')
            require(all(item['expected_units'][key] in ('seconds', 's', None)
                        for key in ('photometry_time', 'event_time')),
                    'native exporter requires source seconds evidence')
    require(joined == set(native_reader.items) and joined, 'complete reader/exporter asset set')
    corpus = exporter(manifest, native_reader)
    require(isinstance(corpus, dict) and isinstance(corpus.get('source_receipts'), list),
            'native exporter receipt ledger required')
    require(len(native_reader.receipts) == len(joined)
            and {r['asset_id'] for r in native_reader.receipts} == joined,
            'all bound source assets read exactly once')
    corpus['source_receipts'].extend(copy.deepcopy(native_reader.receipts))
    return corpus
