"""One invented full-panel fixture; never reads authentic neural payloads.

The geometry, context validator, array reader and scorer are the accepted task
objects. Numeric values, missingness locations, input pins, generation and packet
identity below are explicitly generated test material. The synthetic inherited
scale of 1.0 is an orchestration fixture, not a recalculated scientific scale.

Call build once per test process and reuse its twelve views. All array buffers,
ordinary copies, metadata and subsequent test artifacts must use write/copy so
snapshot includes cumulative requested and completed logical file bytes, even
after failed calls. It does not measure physical filesystem I/O, directory
metadata, Python source writes or allocation. Counters deliberately have no reset.
"""
import copy as copying
import hashlib
import io as streams
import os
from pathlib import Path
import stat

import numpy as np


CAP_BYTES = 90 * 1024 * 1024
_counts = {'requested_bytes': 0, 'completed_bytes': 0,
           'write_calls': 0, 'failed_calls': 0,
           'failed_publication_bytes_upper': 0}
_build_started = False
_STATIC = ('TASK.md', 'CANDIDATE.md', 'prediction.schema.json',
           'input.schema.json', 'DEPENDENCIES.md', 'requirements.txt',
           'delivery_io.py', 'array_io.py', 'reference_copy_condition.py')


def snapshot():
    """Non-resetting logical-write accounting for this one test process."""
    return {**_counts, 'cap_bytes': CAP_BYTES,
            'scope': 'generated fixture and artifact logical file writes only',
            'physical_io_measured': False}


def _pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def write(path, body):
    """Write an ordinary generated file, charging failures and actual progress.

    Existing ordinary files may be rewritten for negative controls. No hardlink
    or symlink output is accepted. Deleting a file never refunds its charge.
    """
    if type(body) is not bytes:
        raise TypeError('Generated file bodies must be bytes')
    _counts['write_calls'] += 1
    _counts['requested_bytes'] += len(body)
    try:
        if _counts['requested_bytes'] > CAP_BYTES:
            raise ValueError('Cumulative generated-write reservation exceeded')
        path = Path(path).absolute()
        if any(item.is_symlink() for item in (path, *path.parents)):
            raise ValueError('Generated writes require ordinary owned paths')
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            info = path.stat()
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValueError('No linked or special generated output')
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
        try:
            remaining = memoryview(body)
            while remaining:
                count = os.write(fd, remaining)
                if count <= 0:
                    raise OSError('Generated write made no progress')
                _counts['completed_bytes'] += count
                remaining = remaining[count:]
        finally:
            os.close(fd)
        return _pin(body)
    except BaseException:
        _counts['failed_calls'] += 1
        raise


def copy(source, destination):
    """Ordinary independent copy of an already generated fixture file."""
    source = Path(source).absolute()
    if any(item.is_symlink() for item in (source, *source.parents)):
        raise ValueError('Generated copy source must be ordinary')
    info = source.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError('Generated copy source must be one ordinary file')
    return write(destination, source.read_bytes())


def publication(body, function):
    """Charge one real trusted publication without replacing its transport.

    The caller supplies the exact canonical payload given to the publisher. A
    normal return confirms its completed payload; a failed publisher may have
    written partially, so its full attempted size remains charged and is also
    reported as an unknown-partial upper bound rather than invented completion.
    """
    if type(body) is not bytes or not callable(function):
        raise TypeError('Publication needs exact bytes and a trusted callable')
    _counts['write_calls'] += 1
    _counts['requested_bytes'] += len(body)
    entered = False
    try:
        if _counts['requested_bytes'] > CAP_BYTES:
            raise ValueError('Cumulative generated-write reservation exceeded')
        entered = True
        result = function()
        _counts['completed_bytes'] += len(body)
        return result
    except BaseException:
        _counts['failed_calls'] += 1
        if entered:
            _counts['failed_publication_bytes_upper'] += len(body)
        raise


def _array_body(array):
    buffer = streams.BytesIO()
    np.save(buffer, array, allow_pickle=False)
    return buffer.getvalue()


def _arrays(condition_index, shape):
    """Full original geometry, with explicit invented gaps and empty rows."""
    cells, frames = shape
    row = np.arange(cells, dtype=np.float64)[:, None]
    frame = np.arange(frames, dtype=np.float64)[None, :]
    means = np.asarray((condition_index + 1) / 8 + row / 1024 +
                       ((frame % 13) - 6) / 32, dtype='<f8')
    counts = np.full(shape, 50 - condition_index, dtype='<u2')
    counts[0, ::17] = 25
    counts[0, :2] = 0
    # Seven invented wholly empty rows in each order across all six acquisitions:
    # two in acquisition 1, one in each other acquisition. Both orders agree.
    empty = 2 if condition_index // 2 == 0 else 1
    counts[-empty:, :] = 0
    means[counts == 0] = 0
    return means, counts


def build(root, bundle):
    """Return (fixture_bundle, {context_id: ordinary_view_path}).

    Preserve bundle's real parser, contract, array and scorer modules. Deep-copy
    only panel/lock metadata; replace their content pins with invented input
    pins. The returned fixture_targets contains the invented full arrays for
    explicitly generated score callbacks, never authentic/private target data.
    """
    global _build_started
    if _build_started:
        raise ValueError('Build the full fixture once and reuse all twelve views')
    _build_started = True
    root = Path(root).absolute()
    if root.exists() and (not root.is_dir() or any(root.iterdir())):
        raise ValueError('Full generated fixture needs an absent or empty owned root')
    if any(item.is_symlink() for item in (root, *root.parents)):
        raise ValueError('No linked generated fixture root')
    root.mkdir(parents=True, exist_ok=True)
    fixture = copying.copy(bundle)
    fixture.lock = copying.deepcopy(bundle.lock)
    fixture.panel = copying.deepcopy(bundle.panel)
    original_packet = fixture.panel['packet_id']
    fixture.panel['generation'] = bundle.core.fingerprint({
        'schema': 'neural037-invented-viewer-full-panel-fixture-v1',
        'original_packet_geometry': original_packet, 'authentic_payload_reads': 0})
    fixture.panel['packet_id'] = bundle.core.fingerprint({
        k: v for k, v in fixture.panel.items() if k != 'packet_id'})
    bundle.core.public_contract(fixture.panel)
    fixture.lock['packet_id'] = fixture.panel['packet_id']
    fixture.lock['synthetic_fixture_only'] = True

    contexts = fixture.panel['contexts']
    conditions = tuple(bundle.contract.CONDITIONS)
    if len(contexts) != 12 or [c['context_id'] for c in contexts] != list(bundle.contract.CONTEXTS):
        raise ValueError('Generated fixture preserves all original context identities')
    common = [r for r in fixture.lock['files'] if r['fold'] is None]
    if len(common) != 9 or {r['target'] for r in common} != {'view/' + n for n in _STATIC}:
        raise ValueError('Exactly the original nine static view members are required')
    static_bodies = {}
    for name in _STATIC:
        if name.endswith('.json'):
            body = bundle.io.canonical({'generated_fixture_only': True, 'name': name})
        else:
            body = ('# Generated fixture only; never executed: ' + name + '\n').encode('ascii')
        static_bodies[name] = body
    for row in common:
        row.update(_pin(static_bodies[Path(row['target']).name]))

    pool = {}
    fixture.fixture_targets = {'packet_id': fixture.panel['packet_id'], 'contexts': {}}
    for index, (acquisition, order) in enumerate(conditions):
        key = acquisition + '_' + order
        shape = tuple(bundle.contract.SHAPES[index // 2])
        means, counts = _arrays(index, shape)
        item = {'acquisition': acquisition, 'order': order, 'shape': list(shape)}
        for kind, array in (('means', means), ('counts', counts)):
            path = root / 'source-pool' / (key + '_' + kind + '.npy')
            pin = write(path, _array_body(array))
            item[kind] = {'path': path, **pin}
        pool[(acquisition, order)] = item
        means.flags.writeable = counts.flags.writeable = False
        fixture.fixture_targets['contexts'][key] = {
            'means': means, 'counts': counts, 'training_scale': 1.0}

    views = {}
    input_pins = {}
    for fold, query in enumerate(contexts):
        name = query['context_id']
        view = root / 'contexts' / name
        (view / 'arrays').mkdir(parents=True)
        rows = [r for r in fixture.lock['files'] if r['fold'] is None or r['fold'] == fold]
        if len(rows) != 32 or len({r['target'] for r in rows}) != 32:
            raise ValueError('All thirty-two original view files must be retained')
        by_target = {r['target']: r for r in rows}
        for static_name, body in static_bodies.items():
            write(view / static_name, body)
        training = []
        wanted = [c for c in conditions if c != (query['acquisition'], query['query_order'])]
        for train_index, condition in enumerate(wanted):
            source = pool[condition]
            item = {k: copying.deepcopy(source[k]) for k in ('acquisition', 'order', 'shape')}
            for kind in ('means', 'counts'):
                relative = 'arrays/train_%02d_%s.npy' % (train_index, kind)
                pin = copy(source[kind]['path'], view / relative)
                item[kind] = {'path': relative, **pin}
                by_target['view/' + relative].update(pin)
            training.append(item)
        value = {'schema': 'neural037-context-v1', 'packet_id': fixture.panel['packet_id'],
                 'query': copying.deepcopy(query), 'training': training,
                 'training_scale': 1.0, 'scope': bundle.contract.SCOPE}
        raw = bundle.io.canonical(value)
        pin = write(view / 'input.json', raw)
        by_target['view/input.json'].update(pin)
        bundle.contract.validate(raw, fold, rows, fixture.panel['packet_id'])
        views[name] = view
        input_pins[name] = pin

    fixture.fixture_only = True
    fixture.fixture_pool = pool
    fixture.fixture_input_pins = input_pins
    fixture.source_binding = _pin(bundle.io.canonical({
        'schema': 'neural037-generated-fixture-binding-v1', 'synthetic': True,
        'source_binding_lineage': bundle.source_binding,
        'packet_id': fixture.panel['packet_id'], 'inputs': input_pins}))
    fixture.fixture_write_accounting = snapshot()
    return fixture, views
