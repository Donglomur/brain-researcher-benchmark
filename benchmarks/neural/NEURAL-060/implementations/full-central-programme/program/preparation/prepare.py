"""Concrete future full-cohort preparation; never invoked during source building.

The caller owns execution authority, storage selection and an independent outer
clock/process observer. This module does not establish those qualifications.
"""
import argparse
from collections import Counter
from contextlib import ExitStack
import hashlib
import io
import json
import math
import os
from pathlib import Path
import secrets
import stat
import time
import types

SOURCE_PIN = {'bytes': 17391, 'sha256': 'c62ba1c5161287d1915d7dd49165be79ca93632dee686be0ea29f0929c1791cf'}
FAILURE_RESERVE = 16384
LIMIT_KEYS = {'max_read_bytes', 'max_write_bytes', 'max_output_bytes', 'max_seconds',
              'max_session_cases', 'max_units', 'max_count_window_bytes'}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def pin_bytes(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def stamp(st):
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


class Budget:
    """Reservations/logical transfer counts, not physical I/O, RSS or disk blocks."""
    def __init__(self, limits, origin):
        need(type(limits) is dict and set(limits) == LIMIT_KEYS, 'Complete explicit preparation limits')
        need(all(type(v) is int and v > 0 for v in limits.values()), 'Positive integer preparation limits')
        need(limits['max_output_bytes'] > FAILURE_RESERVE and limits['max_write_bytes'] > FAILURE_RESERVE,
             'Reserve failure metadata within selected byte caps')
        need(type(origin) in (int, float) and math.isfinite(origin) and 0 <= origin <= time.monotonic(),
             'Original enclosing monotonic origin')
        self.limits, self.origin = limits, float(origin)
        self.deadline = self.origin + limits['max_seconds']
        self.read_reserved = self.read_actual = self.write_reserved = self.write_actual = self.retained_reserved = 0
        self.tick()

    def tick(self):
        need(time.monotonic() < self.deadline, 'Original preparation deadline exceeded')

    def reading(self, n):
        self.tick()
        need(type(n) is int and n >= 0 and self.read_reserved + n <= self.limits['max_read_bytes'],
             'Logical read allowance exceeded before read')
        self.read_reserved += n

    def writing(self, n, growth):
        self.tick()
        need(self.write_reserved + n <= self.limits['max_write_bytes'] - FAILURE_RESERVE,
             'Logical write allowance exceeded before write')
        need(self.retained_reserved + growth <= self.limits['max_output_bytes'] - FAILURE_RESERVE,
             'Retained logical extent allowance exceeded before write')
        self.write_reserved += n
        self.retained_reserved += growth

    def record(self):
        return dict(read_reserved=self.read_reserved, read_actual=self.read_actual,
                    write_reserved=self.write_reserved, write_actual=self.write_actual,
                    retained_extent_reserved=self.retained_reserved,
                    original_origin=self.origin, original_deadline=self.deadline,
                    observed_at=time.monotonic(), physical_io_or_rss_measured=False)


class CountedFile(io.RawIOBase):
    """HDF5's file-object driver passes reads/writes through this budget boundary."""
    def __init__(self, raw, budget, writable=False):
        self.raw, self.budget, self._writable = raw, budget, writable
        self.extent = os.fstat(raw.fileno()).st_size

    def readable(self): return True
    def writable(self): return self._writable
    def seekable(self): return True
    def tell(self): return self.raw.tell()
    def seek(self, offset, whence=0): return self.raw.seek(offset, whence)
    def fileno(self): return self.raw.fileno()

    def read(self, n=-1):
        left = max(0, os.fstat(self.raw.fileno()).st_size - self.tell())
        size = left if n is None or n < 0 else min(n, left)
        self.budget.reading(size)
        data = self.raw.read(size)
        self.budget.read_actual += len(data)
        return data

    def readinto(self, target):
        view = memoryview(target).cast('B')
        data = self.read(len(view))
        view[:len(data)] = data
        return len(data)

    def write(self, data):
        need(self._writable, 'Read-only original')
        data = memoryview(data).cast('B')
        end = self.tell() + len(data)
        self.budget.writing(len(data), max(0, end - self.extent))
        self.extent = max(self.extent, end)
        count = self.raw.write(data)
        self.budget.write_actual += count
        need(count == len(data), 'Partial native write; no retry')
        return count

    def truncate(self, size=None):
        need(self._writable, 'Read-only original')
        size = self.tell() if size is None else size
        self.budget.writing(0, max(0, size - self.extent))
        self.extent = max(self.extent, size)
        return self.raw.truncate(size)

    def flush(self):
        if not self.raw.closed:
            self.raw.flush()

    def close(self):
        if not self.closed:
            self.flush()
            super().close()
            self.raw.close()


def ordinary(path, budget, *, output=False):
    flags = os.O_NOFOLLOW | os.O_NONBLOCK | (os.O_RDWR | os.O_CREAT | os.O_EXCL if output else os.O_RDONLY)
    fd = os.open(path, flags, 0o600)
    st = os.fstat(fd)
    if not stat.S_ISREG(st.st_mode):
        os.close(fd)
        raise ValueError('Ordinary file required')
    return CountedFile(os.fdopen(fd, 'r+b' if output else 'rb', buffering=0), budget, output)


def capture(path, budget, maximum):
    with ordinary(path, budget) as stream:
        before = os.fstat(stream.fileno())
        need(before.st_size <= maximum, 'Bounded metadata capture')
        body = stream.read(before.st_size)
        need(len(body) == before.st_size and stamp(before) == stamp(os.fstat(stream.fileno())), 'Stable capture')
    need(stamp(before) == stamp(os.stat(path, follow_symlinks=False)), 'Captured path changed')
    return body


def file_pin(path, budget):
    with ordinary(path, budget) as stream:
        before = os.fstat(stream.fileno())
        digest, count = hashlib.sha256(), 0
        while True:
            data = stream.read(1024 * 1024)
            if not data: break
            count += len(data)
            digest.update(data)
        need(count == before.st_size and stamp(before) == stamp(os.fstat(stream.fileno())), 'Stable full-file pin')
    need(stamp(before) == stamp(os.stat(path, follow_symlinks=False)), 'Pinned path changed')
    return {'bytes': count, 'sha256': digest.hexdigest()}


def sync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try: os.fsync(fd)
    finally: os.close(fd)


def publish(path, raw, budget):
    path.parent.mkdir(parents=True, exist_ok=True)
    with ordinary(path, budget, output=True) as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    sync_dir(path.parent)
    return pin_bytes(raw)


def descriptor(root, relative, budget):
    return {'path': relative, **file_pin(root / relative, budget)}


def modules(budget):
    folder = Path(__file__).resolve().parent
    bodies = {name: capture(folder / name, budget, 200000) for name in ('prepare.py', 'native.py', 'projection.py')}
    loaded = {}
    for name in ('projection.py', 'native.py'):
        module = types.ModuleType('neural060_preparation_' + name[:-3])
        module.__file__ = str(folder / name)
        exec(compile(bodies[name], module.__file__, 'exec'), module.__dict__)
        loaded[name] = module
    return loaded['projection.py'], loaded['native.py'], {k: pin_bytes(v) for k, v in bodies.items()}


def _mark(path, state, budget):
    """Same owned attempt file, durable replacement; no success after timeout."""
    raw = encoded(state)
    temporary = path.with_suffix('.next')
    need(not temporary.exists(), 'Unresolved marker update requires manual inspection')
    publish(temporary, raw, budget)
    os.replace(temporary, path)
    sync_dir(path.parent)


def _failure_mark(path, state, budget):
    """Bounded reserved failure evidence may follow the expired producer clock."""
    raw = encoded(state)
    need(len(raw) <= FAILURE_RESERVE, 'Failure evidence exceeds reserved extent')
    temporary = path.with_suffix('.failure')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'wb') as stream:
            need(stream.write(raw) == len(raw), 'Partial failure marker write')
            stream.flush(); os.fsync(stream.fileno())
        budget.write_reserved += len(raw); budget.write_actual += len(raw); budget.retained_reserved += len(raw)
        os.replace(temporary, path); sync_dir(path.parent)
    except BaseException:
        # Preserve the original attempt and any partial evidence. No retry.
        raise


def _safe_roots(sources_path, raw_root, output):
    # Validate spelling before lstat/lexists or any original/output effects.
    # Path.absolute() does not eliminate '..'; lexical overlap tests therefore
    # require already canonical absolute POSIX spellings rather than guessing.
    values = tuple(os.fspath(v) for v in (sources_path, raw_root, output))
    for value in values:
        need(type(value) is str and value.startswith('/') and not value.startswith('//')
             and '\x00' not in value and not any(part in ('.', '..') for part in value.split('/'))
             and str(Path(value)) == value, 'Canonical absolute paths without dot components required')
    sources_path, raw_root, output = map(Path, values)
    for directory in (sources_path.parent, raw_root, output.parent):
        for parent in (directory, *directory.parents):
            st = os.lstat(parent)
            need(stat.S_ISDIR(st.st_mode) and not stat.S_ISLNK(st.st_mode), 'Ordinary existing path parents')
    need(not os.path.lexists(output) and output != raw_root and raw_root not in output.parents
         and output not in raw_root.parents and output not in sources_path.parents,
         'Fresh output disjoint from source tree')
    return sources_path, raw_root, output


def prepare(sources_path, raw_root, output, limits, original_origin):
    budget = Budget(limits, original_origin)
    p, n, producer = modules(budget)
    sources_path, raw_root, output = _safe_roots(sources_path, raw_root, output)
    sources = p.admit_sources(capture(sources_path, budget, SOURCE_PIN['bytes']))
    assets = sorted(sources['assets'], key=lambda x: x['eid'])
    # Inventory the whole cohort before opening any source body or creating output.
    for asset in assets:
        st = os.lstat(raw_root / (asset['eid'] + '.h5'))
        need(stat.S_ISREG(st.st_mode) and st.st_size == asset['bytes'], 'All29 exact-size ordinary originals required')
    # Setup can fail before a complete ATTEMPT exists. The caller must retain
    # its external intent and inspect any partial tree; it must never auto-retry.
    output.mkdir(mode=0o700)
    for name in ('public', 'operator', 'private'): (output / name).mkdir(mode=0o700)
    marker = output / 'operator/ATTEMPT.json'
    state = {'schema': 'neural060_preparation_attempt_v2', 'status': 'started', 'entered_session': None,
             'completed_sessions': 0, 'sources': SOURCE_PIN, 'producer_sources': producer,
             'original_origin': budget.origin, 'original_deadline': budget.deadline,
             'scientific_scores': 0, 'models_run': 0}
    publish(marker, encoded(state), budget)
    try:
        n.libraries(budget.tick)
        key = secrets.token_bytes(32)
        # Write once from in-memory random bytes. Never read/hash/log this key body.
        with ordinary(output / 'private/OPERATOR_ID_KEY.hex', budget, output=True) as key_file:
            key_file.write(key.hex().encode() + b'\n')
            key_file.flush(); os.fsync(key_file.fileno())
        sync_dir(output / 'private')
        query, gold, hierarchy, rows, dispositions = [], [], {}, [], []
        seen_cases, seen_sessions = set(), set()
        for ordinal, asset in enumerate(assets, 1):
            state['entered_session'] = ordinal
            _mark(marker, state, budget)
            row, private_rows, target_rows, diagnostic = _session(
                p, n, asset, ordinal, key, raw_root, output, budget, seen_cases, seen_sessions)
            rows.append(row); dispositions.append(diagnostic); gold.extend(target_rows)
            session = row['session_id']
            hierarchy[session] = {'animal_id': n.token(key, 'animal', asset['subject']),
                                  'lab_id': n.token(key, 'lab', asset['lab'])}
            query.extend({'case_id': c, 'session_id': session} for c in row['splits']['test']['case_ids'])
            need(private_rows == len(target_rows), 'Complete session target capture')
            state['completed_sessions'] = ordinal
            _mark(marker, state, budget)
        del key
        need(len(hierarchy) == 29 and len({v['animal_id'] for v in hierarchy.values()}) == 13 and
             len({v['lab_id'] for v in hierarchy.values()}) == 7, 'No opaque biological ID collision')
        q = {'schema': 'neural060_query_v2', 'cases': query, 'sessions': [r['session_id'] for r in rows]}
        publish(output / 'public/QUERY_INDEX.json', encoded(q), budget)
        publish(output / 'private/gold.json', encoded({'schema': 'neural060_gold_v1', 'cases': gold,
                'hierarchy': hierarchy}), budget)
        publish(output / 'operator/DISPOSITIONS.json', encoded({'schema': 'neural060_dispositions_v2',
                'sessions': dispositions}), budget)
        totals = dict(sessions=29, mice=13, labs=7, source_bytes=49113902269,
                      train_cases=0, val_cases=0, test_cases=0, movements=0, included=0, excluded=0,
                      uncompressed_count_bytes=0)
        for row in rows:
            for split in p.SPLITS: totals[split + '_cases'] += len(row['splits'][split]['case_ids'])
            for name in ('movements', 'included', 'excluded'): totals[name] += row['disposition_summary'][name]
            totals['uncompressed_count_bytes'] += 200 * row['unit_count'] * (
                row['disposition_summary']['included'] + len(row['splits']['test']['case_ids']))
        projection = {'schema': 'neural060_projection_v2', 'task_id': 'NEURAL-060',
                      'source_manifest': SOURCE_PIN, 'producer_sources': producer,
                      'query': descriptor(output, 'public/QUERY_INDEX.json', budget), 'sessions': rows,
                      'dispositions': descriptor(output, 'operator/DISPOSITIONS.json', budget),
                      'protected_gold': descriptor(output, 'private/gold.json', budget), 'totals': totals,
                      'shift': dict(p.SHIFT)}
        p.admit_projection(projection, sources); p.admit_query(q, projection)
        projection_pin = publish(output / 'operator/PROJECTION.json', encoded(projection), budget)
        binding = {'schema': 'neural060_binding_v2', 'query': projection['query'], 'gold': projection['protected_gold'],
                   'projection': {'path': 'operator/PROJECTION.json', **projection_pin}}
        binding_pin = publish(output / 'private/BINDING.json', encoded(binding), budget)
        # Direct runtime mounts require separately verified readonly custody.
        # These mode changes are source preparation, not sandbox qualification.
        for relative in p.public_file_map(projection):
            os.chmod(output / relative, 0o444, follow_symlinks=False)
        os.chmod(output / 'operator/PROJECTION.json', 0o444, follow_symlinks=False)
        for directory in sorted((v for v in (output / 'public').rglob('*') if v.is_dir()),
                                key=lambda v: len(v.parts), reverse=True):
            os.chmod(directory, 0o555, follow_symlinks=False)
        os.chmod(output / 'public', 0o555, follow_symlinks=False)
        for name, expected in producer.items():
            need(pin_bytes(capture(Path(__file__).resolve().parent / name, budget, 200000)) == expected,
                 'Preparation source changed during invocation')
        budget.tick()
        receipt = {'schema': 'neural060_preparation_v2', 'complete': True, 'projection': projection_pin,
                   'binding': binding_pin, 'source_manifest': SOURCE_PIN, 'producer_sources': producer,
                   'totals': totals, 'all_public_views_readback_admitted': True,
                   'test_shift_relation_readback_verified': True, 'all_raw_source_bodies_authenticated': True,
                   'key_body_read_or_hashed': False, 'models_run': 0, 'scientific_scores': 0,
                   'budget_snapshot_before_terminal_publications': budget.record(),
                   'later_writes': ['operator/PREPARATION.json', 'operator/ATTEMPT.json'],
                   'external_observer_qualification': 'required separately; not established by producer receipt'}
        receipt_pin = publish(output / 'operator/PREPARATION.json', encoded(receipt), budget)
        state.update(status='completed', receipt=receipt_pin, budget_snapshot=budget.record())
        _mark(marker, state, budget)
        budget.tick()
        return {'projection': projection_pin, 'preparation': receipt_pin, 'totals': totals,
                'budget_snapshot_after_terminal_publications': budget.record()}
    except BaseException as exc:
        state.update(status='failed', error_type=type(exc).__name__, error=str(exc)[:2048],
                     budget_snapshot=budget.record(), manual_inspection_required=True,
                     cleanup='Artifacts retained; no automatic retry or rollback')
        try: _failure_mark(marker, state, budget)
        except BaseException: pass  # Original attempt/partial evidence still requires manual inspection.
        raise


def _session(p, n, asset, ordinal, key, raw_root, output, budget, seen_cases, seen_sessions):
    path = raw_root / (asset['eid'] + '.h5')
    with ordinary(path, budget) as stream:
        before = os.fstat(stream.fileno())
        need(before.st_size == asset['bytes'], 'Selected source byte size')
        sha = n.source_identity(stream, asset)
        with n.h5py.File(stream, 'r') as source:
            units = len(n.dataset(source, 'units/id'))
            need(units <= budget.limits['max_units'] and 200 * units <= budget.limits['max_count_window_bytes'],
                 'Full native all-unit window exceeds selected resource domain; no subset')
            movements = len(n.dataset(source, 'task_aligned_intervals/movement_window/start'))
            need(movements <= budget.limits['max_session_cases'], 'Complete movement census exceeds selected cap')
            axis = n.unit_axis(source)
            native_rows, dispositions, units_checked = n.metadata_rows(source, asset)
            need(units_checked == units and len(dispositions) == movements, 'Complete native-axis/movement census')
            n.validate_spikes(source, units)
            session = n.token(key, 'session', asset['eid'])
            need(session not in seen_sessions, 'Session-ID collision')
            seen_sessions.add(session)
            targets, splits = [], {}
            for split in p.SPLITS:
                selected = [r for r in native_rows if r['split'] == split]
                for row in selected:
                    case = n.token(key, 'case', asset['eid'] + ':' + str(row['trial_index']))
                    need(case not in seen_cases, 'Case-ID collision or repeated original trial')
                    seen_cases.add(case); row['case_id'] = case
                    dispositions[row['movement_row']]['case_id'] = case
                splits[split], captured_targets = _write_split(p, n, source, selected, session, split, axis,
                                                               units, output, budget)
                targets.extend(captured_targets)
            need(stamp(before) == stamp(os.fstat(stream.fileno())), 'Original source changed during projection')
        need(stamp(before) == stamp(os.fstat(stream.fileno())), 'Original source changed on native close')
    need(stamp(before) == stamp(os.stat(path, follow_symlinks=False)), 'Original source path replaced')
    reasons = dict(Counter(d['reason'] for d in dispositions if not d['included']))
    summary = {'movements': len(dispositions), 'included': len(native_rows),
               'excluded': len(dispositions) - len(native_rows), 'reasons': reasons}
    overlap = n.overlap_counts(native_rows)
    result = {'ordinal': ordinal, 'session_id': session,
              'source': {'eid': asset['eid'], 'bytes': asset['bytes'], 'etag': asset['etag'], 'sha256': sha},
              'unit_count': units, 'unit_axis_sha256': axis, 'splits': splits,
              'disposition_summary': summary, 'overlap': overlap}
    diagnostic = {'ordinal': ordinal, 'session_id': session, 'source_eid': asset['eid'],
                  'movements': dispositions, 'overlap': overlap,
                  'boundary_distances_are_not_preprocessing_leakage_guarantees': True}
    return result, len(splits['test']['case_ids']), targets, diagnostic


def _write_split(p, n, source, selected, session, split, axis, units, output, budget):
    relative = 'public/' + session + '/' + split
    directory = output / relative
    directory.mkdir(parents=True)
    public_rows, targets = [], []
    paths = [('neural.h5', 'original')]
    if split == 'test': paths.append(('neural_shift10.h5', 'test_roll10'))
    with ExitStack() as stack:
        handles, streams = [], []
        for name, transform in paths:
            stream = stack.enter_context(ordinary(directory / name, budget, output=True))
            handle = stack.enter_context(n.h5py.File(stream, 'w'))
            for key, value in {'schema': 'neural060_counts_v2', 'session_id': session, 'split': split,
                               'unit_axis_sha256': axis}.items():
                handle.attrs[key] = value
            handle.create_dataset('counts', shape=(len(selected), 50, units), dtype='<u4',
                                  chunks=(1, 50, min(units, 2048)), compression='gzip')
            handle.create_dataset('case_ids', shape=(len(selected),), dtype='S32')
            handles.append(handle); streams.append(stream)
        for index, row in enumerate(selected):
            budget.tick()
            counts = n.counts_for(source, row, units)
            handles[0]['counts'][index] = counts
            handles[0]['case_ids'][index] = row['case_id'].encode('ascii')
            if split == 'test':
                handles[1]['counts'][index] = n.np.roll(counts, 10, axis=0)
                handles[1]['case_ids'][index] = row['case_id'].encode('ascii')
            public = {'case_id': row['case_id'], 'session_id': session, **row['context']}
            if split != 'test': public['wheel_speed'] = row['wheel_speed']
            else: targets.append({'case_id': row['case_id'], 'session_id': session, 'wheel_speed': row['wheel_speed']})
            public_rows.append(public)
        for handle in handles: handle.flush()
        # ExitStack closes HDF5 before its corresponding file-object wrapper.
    for name, _ in paths:
        with ordinary(directory / name, budget) as stream: os.fsync(stream.fileno())
    sync_dir(directory)
    context = {'schema': 'neural060_context_v2', 'split': split, 'session_id': session,
               'unit_count': units, 'unit_axis_sha256': axis, 'rows': public_rows}
    publish(directory / 'context.json', encoded(context), budget)
    _verify_split(p, n, directory, context, split, axis, units, budget)
    result = {'case_ids': [r['case_id'] for r in public_rows],
              'context': descriptor(output, relative + '/context.json', budget),
              'neural': descriptor(output, relative + '/neural.h5', budget)}
    if split == 'test': result['neural_shift10'] = descriptor(output, relative + '/neural_shift10.h5', budget)
    return result, targets


def _verify_split(p, n, directory, expected_context, split, axis, units, budget):
    actual = p.decode(capture(directory / 'context.json', budget, budget.limits['max_output_bytes']))
    need(encoded(actual) == encoded(expected_context), 'Complete context readback identity')
    ids = [r['case_id'] for r in actual['rows']]
    for row in actual['rows']:
        need(set(row) == p.CONTEXT_FIELDS | ({'wheel_speed'} if split != 'test' else set()),
             'No undeclared or test-target context fields')
        for name, length in [('history_speed', 50), ('history_position', 50), ('history_offsets', 50),
                             ('target_offsets', 50), ('stimulus_block', 12)]:
            need(type(row[name]) is list and len(row[name]) == length and
                 all(type(v) in (int, float) and math.isfinite(v) for v in row[name]), 'Finite exact nuisance geometry')
        need(type(row['stimulus_latency_s']) in (int, float) and math.isfinite(row['stimulus_latency_s'])
             and row['stimulus_latency_s'] > 0, 'Finite positive stimulus latency')
        if split != 'test':
            need(type(row['wheel_speed']) is list and len(row['wheel_speed']) == 50 and
                 all(type(v) in (int, float) and math.isfinite(v) and v >= 0 for v in row['wheel_speed']),
                 'Complete finite absolute training/validation targets')
    paths = [('neural.h5', 'original')]
    if split == 'test': paths.append(('neural_shift10.h5', 'test_roll10'))
    else: need(not (directory / 'neural_shift10.h5').exists(), 'No shifted fitting stream')
    with ExitStack() as stack:
        handles = []
        for name, transform in paths:
            stream = stack.enter_context(ordinary(directory / name, budget))
            handle = stack.enter_context(n.h5py.File(stream, 'r'))
            need(set(handle) == {'case_ids', 'counts'}, 'Exact count-file dataset allowlist')
            attrs = {k: n.text(v) for k, v in handle.attrs.items()}
            need(attrs == {'schema': 'neural060_counts_v2', 'session_id': actual['session_id'], 'split': split,
                           'unit_axis_sha256': axis}, 'Exact common count-file attributes; no replay flag')
            counts, case_ids = n.dataset(handle, 'counts'), n.dataset(handle, 'case_ids')
            need(counts.shape == (len(ids), 50, units) and counts.dtype.str == '<u4' and
                 case_ids.shape == (len(ids),) and case_ids.dtype.str == '|S32', 'Complete count geometry/ID width')
            need([bytes(v).decode('ascii') for v in case_ids[()]] == ids, 'Complete ordered count/context ID join')
            handles.append(handle)
        for index in range(len(ids)):
            budget.tick()
            original = handles[0]['counts'][index]
            need(original.shape == (50, units) and original.dtype.kind == 'u', 'Full native unsigned count window')
            if split == 'test':
                need(n.np.array_equal(handles[1]['counts'][index], n.np.roll(original, 10, axis=0)),
                     'Actual stored test-only shift relationship')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('sources', 'raw-root', 'output', 'limits'):
        parser.add_argument('--' + name, required=True, type=Path)
    parser.add_argument('--original-origin', required=True, type=float)
    args = parser.parse_args()
    # The limits document is operator metadata; no source/array body is touched here.
    fd = os.open(args.limits, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_size <= 16384, 'Bounded ordinary limits metadata')
        raw = stream.read(16385)
        need(stamp(before) == stamp(os.fstat(stream.fileno())) and len(raw) == before.st_size, 'Stable limits capture')
    limits = json.loads(raw)
    print(json.dumps(prepare(args.sources, args.raw_root, args.output, limits, args.original_origin), allow_nan=False))


if __name__ == '__main__':
    main()
