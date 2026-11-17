"""Operator-only canonical store and exact globally sorted matrix construction."""
import ast
import hashlib
import math
import os
import random
import stat
import struct
from pathlib import Path


def header(shape):
    body = repr(dict(descr='<f4', fortran_order=False, shape=tuple(shape))).encode('ascii')
    body += b' ' * ((64 - ((10 + len(body) + 1) % 64)) % 64) + b'\n'
    return b'\x93NUMPY\x01\x00' + struct.pack('<H', len(body)) + body


def npy_header(handle, shape, charge=lambda size: None):
    charge(10)
    prefix = handle.read(10)
    c.need(len(prefix) == 10 and prefix[:8] == b'\x93NUMPY\x01\x00', 'NPYv1 canonical input')
    length = struct.unpack('<H', prefix[8:])[0]
    c.need(0 < length <= 1024, 'Bounded NPY header')
    charge(length)
    raw = handle.read(length)
    value = ast.literal_eval(raw.decode('ascii'))
    c.need(type(value) is dict and set(value) == {'descr', 'fortran_order', 'shape'} and
           value['descr'] == '<f4' and value['fortran_order'] is False and
           type(value['shape']) is tuple and value['shape'] == tuple(shape) and
           all(type(x) is int for x in value['shape']), 'Exact little-endian C-order dimensions')
    return 10 + length


def authenticate_array(path, expected, budget):
    path = c.path(path)
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        c.need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
               before.st_mode & 0o222 == 0 and before.st_size == expected['bytes'], 'Immutable ordinary canonical array')
        budget.read(before.st_size)
        digest = hashlib.sha256()
        with os.fdopen(os.dup(fd), 'rb') as handle:
            offset = npy_header(handle, (200, 251, 20), budget.read)
            c.need(before.st_size == offset + 200 * 251 * 20 * 4, 'Full canonical array extent')
            handle.seek(0)
            while block := handle.read(65536):
                budget.tick()
                digest.update(block)
        c.need(digest.hexdigest() == expected['sha256'] and c.stamp(before) == c.stamp(os.fstat(fd)) == c.stamp(path.lstat()),
               'Stable complete canonical content')
        return dict(path=path, pin=expected, stamp=c.stamp(before), offset=offset)
    finally:
        os.close(fd)


def load(selection, budget):
    spec = selection['canonical']
    raw = c.capture(spec['path'], 4000000, c.only_pin(spec), budget.tick, budget.read)
    index = c.parse(raw)
    panel = contracts.canonical(index)
    review_spec = selection['preparation_review']
    review = c.parse(c.capture(review_spec['path'], 262144, c.only_pin(review_spec), budget.tick, budget.read))
    c.need(index['projection_provenance'] == review.get('projection_provenance'), 'Exact projection provenance binding')
    root = c.path(selection['canonical_root'])
    arrays = {}
    for row in index['records']:
        item = row['epochs']
        arrays[row['person'], row['session']] = authenticate_array(root / item['path'], c.only_pin(item), budget)
    return dict(index=index, panel=panel, arrays=arrays, metadata_pin=c.pin(raw))


def unchanged(store, budget):
    for array in store['arrays'].values():
        budget.tick()
        c.need(c.stamp(array['path'].lstat()) == array['stamp'], 'Canonical file unchanged')


def write_array(path, shape, rows, store, budget):
    numeric_bytes = math.prod(shape) * 4
    prefix = header(shape)
    budget.write(len(prefix) + numeric_bytes)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    digest = hashlib.sha256()
    written = 0
    handles = {}
    primary_error = None
    try:
        def put(raw):
            nonlocal written
            digest.update(raw)
            view = memoryview(raw)
            while view:
                budget.tick()
                size = os.write(fd, view)
                c.need(size > 0, 'Complete array write')
                written += size
                view = view[size:]
        put(prefix)
        count = 0
        for item in rows:
            if shape[1:] == [5]:
                raw = struct.pack('<5f', *item)
            else:
                person, session, row_index = item
                key = person, session
                array = store['arrays'][key]
                if key not in handles:
                    descriptor = os.open(array['path'], os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
                    handles[key] = descriptor
                    c.need(c.stamp(os.fstat(descriptor)) == array['stamp'], 'Same original before row gathering')
                budget.read(251 * 20 * 4)
                raw = os.pread(handles[key], 251 * 20 * 4, array['offset'] + row_index * 251 * 20 * 4)
                c.need(len(raw) == 251 * 20 * 4, 'Complete original row')
            # Finite checks are source-generic and never transform the bytes.
            c.need(all(math.isfinite(v[0]) for v in struct.iter_unpack('<f', raw)), 'Finite selected values')
            put(raw)
            count += 1
        c.need(count == shape[0] and written == len(prefix) + numeric_bytes, 'Every selected row copied')
        os.fsync(fd)
    except BaseException as error:
        primary_error = error
        raise
    finally:
        cleanup_errors = []
        for key, descriptor in handles.items():
            try:
                c.need(c.stamp(os.fstat(descriptor)) == store['arrays'][key]['stamp'], 'Stable source after row gathering')
            except BaseException as error:
                cleanup_errors.append(error)
            try:
                os.close(descriptor)
            except BaseException as error:
                cleanup_errors.append(error)
        try:
            os.close(fd)
        except BaseException as error:
            cleanup_errors.append(error)
        if cleanup_errors:
            if primary_error is not None:
                primary_error.add_note('Additional source/output descriptor cleanup failure; all closes attempted')
            else:
                raise ValueError('Source/output descriptor cleanup failed after all closes attempted') from cleanup_errors[0]
    c.sync_dir(Path(path).parent, budget.tick)
    c.readable(path, budget.tick)
    return dict(bytes=written, sha256=digest.hexdigest())


def stage(store, case, setting, arm, mode, destination, budget, model_binding=None):
    c.need(setting in contracts.SETTINGS and arm in contracts.ARMS and mode in ('fit', 'infer'), 'Exact condition')
    root = c.path(destination)
    c.need(not os.path.lexists(root), 'Fresh condition view')
    records = store['index']['records']
    matches = [row for row in records if row['case'] == case]
    c.need(len(matches) == 1, 'One target source record')
    target = matches[0]
    person, session = target['person'], target['session']
    base = dict(schema='neural083_fit_input_v1' if mode == 'fit' else 'neural083_infer_input_v1',
                generation=store['index']['generation'], case=case, setting=setting, arm=arm)
    root.mkdir(mode=0o700)
    c.sync_dir(root.parent, budget.tick)
    if mode == 'fit':
        c.need(model_binding is None, 'No previous model in a fresh fit')
        picks = scientific.training_selection(person, session, setting, records)
        by = {(row['person'], row['session']): row for row in records}
        rows = []
        for pp, ss, count, role in picks:
            record = by[pp, ss]
            labels = record['offline_labels'][:count].copy()
            if arm == 'PERMUTED_EEG':
                random.Random(83083 + 1000 * pp + 10 * ss + count).shuffle(labels)
            for i in range(count):
                meta = dict(trial=record['offline_ids'][i], y=labels[i], person=record['person_id'],
                            role=role, inner_fold=i % 5 if role == 'calibration' else (pp - 1) % 5)
                values = scientific.context(ss, i, record['offline_onsets']) if arm == 'CONTEXT' else (pp, ss, i)
                rows.append((meta['trial'], meta, values))
        rows.sort(key=lambda row: row[0])
        shape = [len(rows), 5] if arm == 'CONTEXT' else [len(rows), 251, 20]
        name = 'training.npy'
        result = write_array(root / name, shape, (row[2] for row in rows), store, budget)
        base.update(training_shape=shape, training_pin=result, training=[row[1] for row in rows])
    else:
        c.need(type(model_binding) is dict and set(model_binding) == {'model', 'program'}, 'Exact sealed-model binding')
        c.exact_pin(model_binding['model'])
        c.exact_pin(model_binding['program'])
        order = sorted(range(100), key=lambda i: target['query_ids'][i])
        shape = [100, 5] if arm == 'CONTEXT' else [100, 251, 20]
        name = 'query.npy'
        values = (scientific.context(session, i, target['online_onsets']) for i in order) if arm == 'CONTEXT' else ((person, session, i + 100) for i in order)
        result = write_array(root / name, shape, values, store, budget)
        base.update(query_shape=shape, query_pin=result, query=[target['query_ids'][i] for i in order],
                    model=model_binding['model'], fitted_program=model_binding['program'])
    metadata = c.save(root / 'case.json', c.encoded(base), 2000000, budget.tick, budget.write)
    c.readable(root / 'case.json', budget.tick)
    os.chmod(root, 0o555)
    c.sync_dir(root, budget.tick)
    unchanged(store, budget)
    return {name: result, 'case.json': metadata}, base


def verify(root, pins, budget):
    c.need(set(p.name for p in Path(root).iterdir()) == set(pins), 'Only condition-permitted files')
    result = {}
    for name, expected in pins.items():
        path = Path(root) / name
        c.capture(path, expected['bytes'], expected, budget.tick, budget.read)
        result[name] = c.stamp(path.lstat())
    return result


def retire(root, pins, stamps, budget):
    c.need(set(p.name for p in Path(root).iterdir()) == set(pins), 'Exact retirement members')
    for name in pins:
        c.need(c.stamp((Path(root) / name).lstat()) == stamps[name], 'Same owned view before retirement')
    os.chmod(root, 0o700)
    for name in pins:
        budget.tick()
        (Path(root) / name).unlink()
    c.sync_dir(root, budget.tick)
    Path(root).rmdir()
    c.sync_dir(Path(root).parent, budget.tick)
    c.need(not os.path.lexists(root), 'Durable training/query absence')
