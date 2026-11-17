"""Complete owner-side Bugeon archive, native arrays and ordered unit joins.

No downloader, representation learner or readout fitting is performed here.
Original source labels and these owner objects must not enter a participant.
"""
from __future__ import annotations

import argparse
import ast
import csv
from copy import deepcopy
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import stat
import struct
import sys
import zipfile

from dependencies import SourceError, identity, load_dependencies, need, read_file

HERE = Path(__file__).resolve().parent
PROFILE_SHA256 = '37dd8e6bd6d377acee3f7b349887e1fb6a94f9541ae51805e306b091d46c41fb'
ORDER_ADOPTION_SHA256 = 'f79d8725150d777a32be5d629f5ec7f0803c0a3a886134fe5eed2b90bea480d1'
ORDER_POLICY = 'nuclr_current_release_zip_experiment_order_v1'
SCHEMA = 'nuclr_complete_native_inputs_v1'
MAX_MEMBER = 128 * 1024 * 1024


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def profile():
    result = json.loads(read_file(HERE / 'source-profile.json', 1024 * 1024, PROFILE_SHA256))
    adoption = json.loads(read_file(HERE / 'order-adoption.json', 65536, ORDER_ADOPTION_SHA256))
    need(adoption['source_profile_sha256'] == PROFILE_SHA256 and adoption['policy_id'] == ORDER_POLICY,
         'reviewed current-release ordering differs')
    return result


def safe_name(value):
    need(type(value) is str and value and '\\' not in value and '\x00' not in value,
         'ordinary source member name required')
    path = PurePosixPath(value)
    need(not path.is_absolute() and all(p not in ('', '.', '..') for p in value.split('/')),
         'unsafe source member path')
    return path


class SourceZip:
    """Authenticate a whole original archive before extracting any member."""
    def __init__(self, path, specification, *, sha256=None):
        self.handle = None
        self.archive = None
        fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
        self.handle = os.fdopen(fd, 'rb')
        try:
            info = os.fstat(fd)
            need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size == specification['bytes'],
                 'complete original archive size/type differs')
            self.identity = identity(info)
            sha, md5 = hashlib.sha256(), hashlib.md5(usedforsecurity=False)
            while block := self.handle.read(1024 * 1024):
                sha.update(block)
                md5.update(block)
            self.sha256 = sha.hexdigest()
            self.check()
            if sha256 is not None:
                need(self.sha256 == sha256, 'original archive SHA256 differs')
            if 'publisher_md5' in specification:
                need(md5.hexdigest() == specification['publisher_md5'], 'publisher archive MD5 differs')
            self.handle.seek(0)
            self.archive = zipfile.ZipFile(self.handle)
            names = self.archive.namelist()
            need(len(names) == len(set(names)) and len(names) <= 1200, 'duplicate or excessive archive members')
            if 'members' in specification:
                expected = specification['members']
                need(names == [r['name'] for r in expected], 'complete original member order differs')
                for row, item in zip(expected, self.archive.infolist()):
                    need((item.file_size, item.compress_size, f'{item.CRC:08x}', item.compress_type) ==
                         (row['bytes'], row['compressed'], row['crc32'], row['method']) and not item.flag_bits & 1,
                         'original member geometry/checksum differs')
            self.check()
        except BaseException:
            self.close()
            raise

    def check(self):
        need(self.handle is not None and not self.handle.closed and
             identity(os.fstat(self.handle.fileno())) == self.identity, 'source archive changed or closed')

    def read(self, name, limit):
        self.check()
        safe_name(name)
        item = self.archive.getinfo(name)
        need(0 <= item.file_size <= limit and not item.flag_bits & 1, 'member exceeds bound or is encrypted')
        with self.archive.open(item) as handle:
            body = handle.read(limit + 1)
        need(len(body) == item.file_size <= limit, 'member length differs')
        self.check()
        return body

    def extract_new(self, name, destination, expected):
        self.check()
        safe_name(name)
        item = self.archive.getinfo(name)
        need(0 < item.file_size == expected['bytes'] <= MAX_MEMBER, 'native member exceeds fixed bound')
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        need(not destination.exists(), 'new member output required')
        fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        sha, count = hashlib.sha256(), 0
        try:
            with os.fdopen(fd, 'wb') as output, self.archive.open(item) as source:
                while block := source.read(min(1024 * 1024, item.file_size - count + 1)):
                    count += len(block)
                    need(count <= item.file_size, 'native member expanded beyond declared extent')
                    sha.update(block)
                    output.write(block)
            need(count == item.file_size, 'truncated native member')
            self.check()
        except BaseException:
            destination.unlink(missing_ok=True)
            raise
        return {'source_member': name, 'relative_path': 'native/' + name,
                'bytes': count, 'sha256': sha.hexdigest()}

    def close(self):
        if self.archive is not None:
            self.archive.close()
        if self.handle is not None:
            self.handle.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class NativeArray:
    """Descriptor-bound numeric NPY memory map, preserving C/Fortran order."""
    def __init__(self, path, *, sha256=None):
        import numpy as np
        self.handle, self.values = None, None
        fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
        self.handle = os.fdopen(fd, 'rb')
        try:
            info = os.fstat(fd)
            need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and 0 < info.st_size <= MAX_MEMBER,
                 'bounded ordinary native NPY required')
            self.identity = identity(info)
            need(self.handle.read(6) == b'\x93NUMPY', 'NPY magic differs')
            version = self.handle.read(2)
            need(version in (b'\x01\x00', b'\x02\x00', b'\x03\x00'), 'unsupported NPY version')
            width = 2 if version[0] == 1 else 4
            raw_length = self.handle.read(width)
            need(len(raw_length) == width, 'short NPY length')
            length = int.from_bytes(raw_length, 'little')
            need(0 < length <= 16384, 'NPY header bound exceeded')
            header = self.handle.read(length)
            need(len(header) == length and header.endswith(b'\n'), 'short or malformed NPY header')
            try:
                doc = ast.literal_eval(header.decode('utf8' if version[0] == 3 else 'latin1'))
            except (ValueError, SyntaxError, UnicodeError, RecursionError) as exc:
                raise SourceError('invalid literal NPY header') from exc
            need(type(doc) is dict and set(doc) == {'descr', 'fortran_order', 'shape'}, 'exact NPY fields required')
            need(type(doc['descr']) is str and doc['descr'] in ('<f4', '<f8', '<i4', '<i8', '<u4', '<u8', '|u1'),
                 'only explicit little-endian numeric NPY is admitted; no object dtype')
            shape = doc['shape']
            need(type(shape) is tuple and 1 <= len(shape) <= 2 and
                 all(type(n) is int and n > 0 for n in shape) and type(doc['fortran_order']) is bool,
                 'native NPY dimensions/order differ')
            dtype = np.dtype(doc['descr'])
            offset = self.handle.tell()
            need(offset + math.prod(shape) * dtype.itemsize == info.st_size, 'NPY payload extent differs')
            self.check()
            if sha256 is not None:
                self.handle.seek(0)
                sha = hashlib.sha256()
                while block := self.handle.read(1024 * 1024):
                    sha.update(block)
                need(sha.hexdigest() == sha256, 'prepared NPY SHA256 differs')
                self.check()
            self.values = np.memmap(self.handle, dtype=dtype, mode='r', offset=offset,
                                   shape=shape, order='F' if doc['fortran_order'] else 'C')
            self.header = {'shape': list(shape), 'dtype': doc['descr'], 'fortran_order': doc['fortran_order'],
                           'header_bytes': offset, 'npy_version': list(version)}
        except BaseException:
            self.close()
            raise

    def check(self):
        need(self.handle is not None and not self.handle.closed and
             identity(os.fstat(self.handle.fileno())) == self.identity, 'native NPY changed or closed')

    def close(self):
        if self.values is not None:
            self.values._mmap.close()
            self.values = None
        if self.handle is not None:
            self.handle.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def metadata_rows(archive, specification):
    body = archive.read(specification['member'], 2_000_000)
    need(len(body) == specification['member_bytes'] and
         hashlib.sha256(body).hexdigest() == specification['member_sha256'], 'author CSV identity differs')
    reader = csv.DictReader(io.StringIO(body.decode('utf8')))
    need(reader.fieldnames == specification['columns'], 'author CSV columns/order differ')
    rows = list(reader)
    need(len(rows) == specification['rows'] and len({r['id'] for r in rows}) == len(rows),
         'complete unique author CSV rows required')
    need(all(set(r) == set(reader.fieldnames) and all(type(v) is str for v in r.values()) for r in rows),
         'malformed author CSV rows')
    return rows


def session_neurons(session_id, definition, owner_root, author_rows):
    """Join source-native vector rows to exact session-local author identifiers."""
    import numpy as np
    count, directory = definition['neurons'], definition['source_directory']
    source = Path(owner_root) / 'native' / directory
    labels = read_file(source / 'neuron.ttype.txt', 256 * 1024).decode('utf8').splitlines()
    need(len(labels) == count and all(x for x in labels), 'complete native neuron label vector required')
    session_rows = [r for r in author_rows if r['session_id'] == session_id]
    expected = {r['id']: r for r in session_rows}
    need(len(expected) == len(session_rows), 'duplicate author neuron ID in session join')
    need(set(expected) == {f'{session_id}_u{i}' for i in range(count)}, 'author/session/native columns differ')
    arrays, values, headers = [], {}, {}
    try:
        for name in ('depth', 'plane', 'rfCenter_Xvis', 'rfCenter_Yvis', 'stackPosCorrected', 'UniqueID'):
            array = NativeArray(source / ('neuron.' + name + '.npy'))
            arrays.append(array)
            value = array.values
            if name == 'stackPosCorrected':
                need(value.shape == (count, 2), 'native stack position rows differ')
            else:
                need(value.shape in ((count,), (count, 1)), 'native neuron vector rows differ')
                value = value.reshape(-1)
            values[name], headers[name] = value, array.header
        result = []
        for index, label in enumerate(labels):
            uid = f'{session_id}_u{index}'
            row = expected[uid]
            subject = session_id.split('_')[0]
            ei = label if label in ('EC', 'IN') else 'IN'
            subclass = 'unknown' if label in ('EC', 'IN') else label.split('-')[0]
            need(row['subject_id'].lower() == subject and row['ttype'] == label and
                 row['ei_class'] == ei and row['subclass'] == subclass,
                 'author/source identity or transcription label differs')
            unique = values['UniqueID'][index].item()
            if type(unique) is int:
                need(unique >= 0, 'integer UniqueID must be nonnegative')
                raw_unique = unique
            else:
                need(math.isnan(unique) or math.isfinite(unique) and 0 <= unique <= 2**53 and unique.is_integer(),
                     'float UniqueID must be an exactly representable integer match or NaN unmatched')
                raw_unique = None if math.isnan(unique) else int(unique)
            def numeric(value):
                value = value.item()
                if type(value) is int or math.isfinite(value):
                    return {'kind': 'finite', 'value': value}
                return {'kind': 'NaN' if math.isnan(value) else '+Infinity' if value > 0 else '-Infinity'}
            native_numeric = {name: numeric(values[name][index]) for name in
                              ('depth', 'plane', 'rfCenter_Xvis', 'rfCenter_Yvis')}
            native_numeric['stackPosCorrected_x'] = numeric(values['stackPosCorrected'][index, 0])
            native_numeric['stackPosCorrected_y'] = numeric(values['stackPosCorrected'][index, 1])
            result.append({'id': uid, 'session_id': session_id, 'subject_id': subject,
                           'source_neuron_index': index, 'ttype': label, 'ei_class': ei, 'subclass': subclass,
                           'source_unique_id': raw_unique,
                           'source_unique_id_missing': 'NaN_unmatched' if raw_unique is None else None,
                           'repeated_cell_id': None if raw_unique is None else f'{subject}:UniqueID:{raw_unique}',
                           'repeated_cell_namespace': 'subject_scoped_source_match; global namespace unspecified',
                           'native_numeric_metadata': native_numeric,
                           'author_numeric_metadata_join': 'not_asserted; native values and author CSV strings retained separately',
                           'author_metadata': deepcopy(row)})
        for array in arrays:
            array.check()
        return result, headers
    finally:
        for array in arrays:
            array.close()


def inspect_session(session_id, definition, owner_root):
    """Read all native blocks, retain source offsets, compute author percentile.

    Low-level numerical preparation only; complete archive custody is supplied
    by prepare_source. No historical filesystem-order equivalence is asserted.
    """
    import numpy as np
    arrays, activity, blocks = [], [], []
    try:
        previous_end, total_frames, row_start = None, 0, 0
        for index, experiment in enumerate(definition['experiments']):
            directory = definition['source_directory'] + '/' + experiment
            data = NativeArray(Path(owner_root) / 'native' / directory / 'frame.neuralActivity.npy')
            arrays.append(data)
            times = NativeArray(Path(owner_root) / 'native' / directory / 'frame.times.npy')
            arrays.append(times)
            need(data.values.dtype.kind == 'f' and len(data.values.shape) == 2 and
                 data.values.shape[1] == definition['neurons'], 'native frame/neuron activity geometry differs')
            frames = data.values.shape[0]
            need(times.values.dtype.kind == 'f' and times.values.shape in ((frames,), (frames, 1)),
                 'native frame clock geometry differs')
            clock = times.values.reshape(-1)
            need(bool(np.isfinite(clock).all()) and bool((np.diff(clock) >= 0).all()),
                 'nonfinite or unsorted native frame clock')
            for first in range(0, frames, max(1, 262144 // definition['neurons'])):
                need(bool(np.isfinite(data.values[first:first + max(1, 262144 // definition['neurons'])]).all()),
                     'nonfinite native activity; no silent cell/frame exclusions')
            offset = index * 3600
            start, stop = float(clock[0] + offset), float(clock[-1] + offset)
            gap = None if previous_end is None else start - previous_end
            need(gap is None or gap >= 0, 'source i*3600 offsets yield unsorted concatenation; no fabricated gap')
            blocks.append({'experiment_id': experiment, 'source_directory': directory,
                           'frames': frames, 'row_start': row_start, 'row_stop': row_start + frames,
                           'native_first_second': float(clock[0]), 'native_last_second': float(clock[-1]),
                           'source_offset_seconds': offset, 'shifted_first_second': start,
                           'shifted_last_second': stop, 'gap_from_previous_seconds': gap,
                           'activity_header': data.header, 'timestamp_header': times.header})
            activity.append(data.values)
            previous_end, total_frames, row_start = stop, total_frames + frames, row_start + frames
        need(activity, 'complete nonempty source experiments required')
        # Match the author's array axis and percentile call. One session only;
        # neither reorder columns nor substitute per-neuron normalization.
        session_values = np.concatenate(activity, axis=0)
        quantile = np.percentile(session_values.flatten(), 99.0)
        need(math.isfinite(float(quantile)) and float(quantile) != 0, 'invalid source normalization denominator')
        normalized_dtype = (np.zeros(1, dtype=session_values.dtype) / quantile).dtype.str
        with np.errstate(over='ignore', invalid='ignore', divide='ignore'):
            stride = max(1, 262144 // definition['neurons'])
            for first in range(0, total_frames, stride):
                need(bool(np.isfinite(session_values[first:first + stride] / quantile).all()),
                     'nonfinite normalized source activity; no silent clipping')
        for array in arrays:
            array.check()
        return {'session_id': session_id, 'neurons': definition['neurons'], 'frames': total_frames,
                'experiments': blocks, 'order_policy': ORDER_POLICY,
                'potential_cross_experiment_240s_pairs': [
                    {'earlier': left['experiment_id'], 'later': right['experiment_id'],
                     'boundary_distance_seconds': right['shifted_first_second'] - left['shifted_last_second'],
                     'interpretation': 'possible source second-view boundary; no sampler execution'}
                    for i, left in enumerate(blocks) for right in blocks[i + 1:]
                    if right['shifted_first_second'] - left['shifted_last_second'] <= 240],
                'normalization': {'method': 'numpy_percentile_flattened_session_99_default_linear',
                                  'percentile': float(quantile), 'numpy_version': np.__version__,
                                  'percentile_scalar_dtype': np.asarray(quantile).dtype.str,
                                  'native_concatenated_dtype': session_values.dtype.str,
                                  'normalized_dtype': normalized_dtype},
                'signal_units': 'deconvolved_calcium_arbitrary_units',
                'plane_offset_times_applied': False,
                'historical_experiment_order_verified': False}
    finally:
        for array in arrays:
            array.close()


def join_projections(sessions, neurons, projections):
    """Preserve all nine current source projections, including invalid topology."""
    source = load_dependencies()
    need(len(sessions) == 17 and {r['session_id'] for r in sessions} == source.evaluator.SOURCE_SESSIONS,
         'complete original 17-session observation manifest required')
    by_id = {row['id']: row for row in neurons}
    need(len(by_id) == len(neurons) == 10153, 'complete unique original neuron roster required')
    need({(p['label_level'], p['panel']) for p in projections} ==
         {(l, p) for l in source.splits.LABELS for p in source.splits.PANEL_SUFFIX} and len(projections) == 9,
         'all nine original label/exposure records required')
    result = []
    for projection in projections:
        need(projection.get('source_archive_sha256') == source.splits.ARCHIVE_SHA256 and
             projection.get('source_commit') == source.splits.SOURCE_COMMIT, 'source split binding differs')
        ordered = list(projection['label_map'])
        need(set(ordered) <= set(by_id), 'original label-map row lacks a native neuron column')
        fields = ('id', 'session_id', 'subject_id', 'source_neuron_index', 'ttype', 'ei_class',
                  'subclass', 'source_unique_id', 'source_unique_id_missing', 'repeated_cell_id',
                  'repeated_cell_namespace')
        metadata = [{key: deepcopy(by_id[uid][key]) for key in fields} for uid in ordered]
        original_metadata = {row['id']: row for row in projection['metadata']}
        need(len(original_metadata) == len(projection['metadata']) == len(ordered),
             'complete unique original split metadata required')
        for uid, row in zip(ordered, metadata):
            expected = original_metadata.get(uid)
            need(expected is not None and all(expected[k] == row[k] for k in
                 ('id', 'session_id', 'subject_id', 'source_neuron_index')), 'split/native column identity differs')
            if projection['label_level'] in ('ei', 'subclass'):
                field = 'ei_class' if projection['label_level'] == 'ei' else 'subclass'
                need(projection['label_map'][uid] == row[field], 'split/source label differs')
        # Eleven-class source mappings contain explicit merged author categories.
        # Their original label map remains authoritative; do not invent a ttype rule.
        result.append({'projection': deepcopy(projection), 'ordered_ids': ordered, 'metadata': metadata,
                       'ordered_native_addresses': [{'session_id': row['session_id'],
                                                     'column': row['source_neuron_index']} for row in metadata],
                       'topology_audit': source.splits.topology_audit(projection),
                       'required_readout_class_balance': 'resample',
                       'transductive_source_route_unresolved': projection['panel'] == 'transductive'})
    return result


def readout_packet(joined, checkpoints, context_variant, representation_training_sessions, data_receipt_sha256):
    """Build the existing owner readout packet; does not fit or qualify it."""
    source = load_dependencies()
    projection = joined['projection']
    selected = source.splits.select_readout_panel([projection], projection['label_level'], projection['panel'])
    need(type(checkpoints) is list and checkpoints and
         all(c.get('ids') == joined['ordered_ids'] for c in checkpoints if type(c) is dict),
         'checkpoints must preserve the original ordered label-map join')
    packet = source.splits._validation_packet(selected, module=source.evaluator)
    packet.update({'input_role': 'authentic_candidate', 'class_balance': 'resample',
                   'metadata': deepcopy(joined['metadata']), 'checkpoints': deepcopy(checkpoints),
                   'context_variant': context_variant,
                   'representation_training_sessions': list(representation_training_sessions)})
    packet['provenance']['metadata_sha256'] = digest(joined['metadata'])
    packet['provenance']['data_receipt_sha256'] = data_receipt_sha256
    packet['provenance']['native_preparation_order_policy'] = ORDER_POLICY
    packet['provenance']['historical_experiment_order_verified'] = False
    packet['provenance']['transductive_source_route_unresolved'] = joined['transductive_source_route_unresolved']
    source.evaluator.validate_packet(packet)
    return packet


def write_new(path, document):
    body = canonical(document) + b'\n'
    need(len(body) <= 32 * 1024 * 1024, 'owner JSON output exceeds fixed bound')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    with os.fdopen(fd, 'wb') as output:
        output.write(body)


def read_json(path, limit=32 * 1024 * 1024):
    def pairs(rows):
        result = {}
        for key, value in rows:
            need(key not in result, 'duplicate owner JSON key')
            result[key] = value
        return result
    return json.loads(read_file(path, limit), object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(SourceError('nonfinite owner JSON')))


def read_prepared_block(owner_root, session, experiment_id, assets, start, stop, *, normalized=True):
    """Read a source-bound native block with every neuron column, in row order.

    Numerical owner-side primitive; NativeInputs supplies complete-manifest
    admission. A caller-supplied generated manifest is not authentic custody.
    """
    import numpy as np
    matches = [row for row in session['experiments'] if row['experiment_id'] == experiment_id]
    need(len(matches) == 1, 'unique original experiment required')
    block = matches[0]
    need(type(start) is int and type(stop) is int and 0 <= start < stop <= block['frames'],
         'half-open frame interval outside native block')
    need(type(normalized) is bool, 'normalization choice must be Boolean')
    directory = block['source_directory']
    names = (directory + '/frame.neuralActivity.npy', directory + '/frame.times.npy')
    selected = [assets[name] for name in names]
    for name, row in zip(names, selected):
        need(row['source_member'] == name and row['relative_path'] == 'native/' + name,
             'prepared native member path differs')
        safe_name(row['relative_path'])
    with NativeArray(Path(owner_root) / selected[0]['relative_path'], sha256=selected[0]['sha256']) as activity, \
         NativeArray(Path(owner_root) / selected[1]['relative_path'], sha256=selected[1]['sha256']) as times:
        need(activity.header == block['activity_header'] and times.header == block['timestamp_header'] and
             activity.values.shape == (block['frames'], session['neurons']) and
             times.values.shape in ((block['frames'],), (block['frames'], 1)), 'prepared native geometry differs')
        result = np.array(activity.values[start:stop], copy=True, order='C')
        clock = np.array(times.values.reshape(-1)[start:stop], copy=True)
        if normalized:
            denominator = session['normalization']['percentile']
            need(type(denominator) in (int, float) and math.isfinite(denominator) and denominator != 0,
                 'source normalization identity differs')
            scalar_dtype = session['normalization']['percentile_scalar_dtype']
            need(scalar_dtype in ('<f4', '<f8'), 'unsupported source percentile scalar dtype')
            result = result / np.asarray(denominator, dtype=scalar_dtype)[()]
            need(result.dtype.str == session['normalization']['normalized_dtype'],
                 'normalization runtime dtype differs from prepared source runtime')
        need(bool(np.isfinite(result).all()), 'nonfinite prepared activity')
        clock = clock + block['source_offset_seconds']
        need(bool(np.isfinite(clock).all()), 'nonfinite prepared timestamps')
        activity.check()
        times.check()
        return {'activity': result, 'timestamps': clock, 'normalized': normalized,
                'source_units': session['signal_units'], 'order_policy': session['order_policy']}


class NativeInputs:
    """Read a completed private source preparation; never a participant object."""
    def __init__(self, owner_root):
        self.root = Path(owner_root)
        need(not (self.root / 'INCOMPLETE.json').exists(), 'partial native preparation refused')
        completion = read_json(self.root / 'COMPLETE.json', 65536)
        manifest = read_json(self.root / 'native-manifest.json')
        joined = read_json(self.root / 'joined-panels.json')
        need(completion.get('schema') == 'nuclr-native-preparation-complete-v1' and
             completion.get('manifest_sha256') == digest(manifest) and
             completion.get('joined_panels_sha256') == digest(joined), 'complete private preparation binding differs')
        source = profile()
        need(manifest.get('schema') == SCHEMA and manifest.get('source_profile_sha256') == PROFILE_SHA256 and
             manifest.get('order_adoption_sha256') == ORDER_ADOPTION_SHA256 and
             manifest.get('split_archive_sha256') == load_dependencies().splits.ARCHIVE_SHA256 and
             manifest.get('metadata_archive_sha256') == source['metadata_archive']['sha256'] and
             manifest.get('dependencies') == load_dependencies().pins and
             manifest.get('order_policy') == ORDER_POLICY, 'source preparation identities differ')
        self.sessions = {r['session_id']: r for r in manifest['sessions']}
        self.assets = {r['source_member']: r for r in manifest['assets']}
        need(len(self.sessions) == len(manifest['sessions']) == 17 and
             set(self.sessions) == set(source['sessions']) and
             len(self.assets) == len(manifest['assets']) == 257 and
             set(self.assets) == {r['name'] for r in source['required_members']}, 'complete native population required')
        for name, definition in source['sessions'].items():
            row = self.sessions[name]
            need(row['neurons'] == definition['neurons'] and
                 [b['experiment_id'] for b in row['experiments']] == definition['experiments'],
                 'complete source experiment/column order differs')
        for row in source['required_members']:
            need(self.assets[row['name']]['bytes'] == row['bytes'], 'original member byte extent differs')
        self.neurons = {row['id']: row for row in manifest['neurons']}
        need(len(self.neurons) == len(manifest['neurons']) == 10153, 'complete source neuron count differs')
        need(join_projections(manifest['sessions'], manifest['neurons'], [r['projection'] for r in joined]) == joined,
             'native ordered panel join differs')
        self.manifest, self.joined = manifest, joined
        self.receipt_sha256 = digest(manifest)

    def native_addresses(self, ordered_ids):
        need(type(ordered_ids) is list and len(ordered_ids) == len(set(ordered_ids)) and
             all(uid in self.neurons for uid in ordered_ids), 'unique known native neuron IDs required')
        return [(self.neurons[uid]['session_id'], self.neurons[uid]['source_neuron_index']) for uid in ordered_ids]

    def read_block(self, session_id, experiment_id, start, stop, *, normalized=True):
        need(session_id in self.sessions, 'unknown original session')
        return read_prepared_block(self.root, self.sessions[session_id], experiment_id,
                                   self.assets, start, stop, normalized=normalized)


def prepare_source(raw_archive, metadata_archive, split_archive, output):
    """Complete original-input construction. Requires separate native admission."""
    spec, source = profile(), load_dependencies()
    output = Path(output)
    need(output.parent.is_dir() and not output.exists(), 'new private output directory required')
    # Metadata/split reads precede scientific array preparation; all remain private.
    with SourceZip(metadata_archive, spec['metadata_archive'], sha256=spec['metadata_archive']['sha256']) as metadata:
        rows = metadata_rows(metadata, spec['metadata_archive'])
    projections = source.splits.read_archive(split_archive)
    output.mkdir(mode=0o700)
    complete = False
    try:
        assets, sessions, neurons = [], [], []
        with SourceZip(raw_archive, spec['raw_archive']) as raw:
            for row in spec['required_members']:
                assets.append(raw.extract_new(row['name'], output / 'native' / safe_name(row['name']), row))
            for sid, definition in spec['sessions'].items():
                cells, headers = session_neurons(sid, definition, output, rows)
                session = inspect_session(sid, definition, output)
                session['neuron_headers'] = headers
                sessions.append(session)
                neurons.extend(cells)
            joined = join_projections(sessions, neurons, projections)
            raw.check()
            manifest = {'schema': SCHEMA, 'source_profile_sha256': PROFILE_SHA256,
                        'order_adoption_sha256': ORDER_ADOPTION_SHA256,
                        'raw_archive_sha256': raw.sha256, 'metadata_archive_sha256': spec['metadata_archive']['sha256'],
                        'split_archive_sha256': source.splits.ARCHIVE_SHA256, 'dependencies': source.pins,
                        'order_policy': ORDER_POLICY, 'assets': assets, 'sessions': sessions, 'neurons': neurons,
                        'subjects': 4, 'session_count': 17, 'neuron_observations': len(neurons),
                        'subrecordings': sum(len(s['experiments']) for s in sessions),
                        'source_unique_id_namespace': 'matched IDs subject-scoped; global source namespace unspecified',
                        'historical_order_verified': False, 'scientific_qualification': False,
                        'downstream_sampler_configuration': None, 'downstream_observation_limit_seconds': None,
                        'downstream_device_count': None, 'input_preparation_crops_or_samples': False,
                        'remaining_holds': ['Invalid current E/I inductive split remains refused.',
                                            'Transductive resample command conflicts with pinned single-split script.',
                                            'Conference-era artifact equality, native references and protected candidates unqualified.']}
        need(manifest['subrecordings'] == 69 and len(assets) == 257, 'incomplete source-native preparation')
        write_new(output / 'native-manifest.json', manifest)
        write_new(output / 'joined-panels.json', joined)
        # A completion record is last; partial failed directories stay explicit.
        write_new(output / 'COMPLETE.json', {'schema': 'nuclr-native-preparation-complete-v1',
                                           'manifest_sha256': digest(manifest), 'joined_panels_sha256': digest(joined),
                                           'scientific_qualification': False})
        complete = True
        return manifest
    finally:
        if not complete:
            write_new(output / 'INCOMPLETE.json', {'schema': 'nuclr-native-preparation-incomplete-v1',
                                                 'scientific_qualification': False})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-archive', required=True, type=Path)
    parser.add_argument('--metadata-archive', required=True, type=Path)
    parser.add_argument('--split-archive', required=True, type=Path)
    parser.add_argument('--owner-output', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = prepare_source(args.raw_archive, args.metadata_archive, args.split_archive, args.owner_output)
    except (ValueError, OSError, KeyError, zipfile.BadZipFile) as exc:
        print('NuCLR source preparation refused: ' + str(exc), file=sys.stderr)
        return 2
    print(json.dumps({'sessions': result['session_count'], 'subrecordings': result['subrecordings'],
                      'neuron_observations': result['neuron_observations'], 'scientific_qualification': False}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
