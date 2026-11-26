"""Closed REVE development/test metadata views; no materialization or execution.

Compile only from an independently pinned complete packet. The returned ``info``
is trusted operator metadata and must never be included in either data directory.
Each directory has exactly view.json, positions.json and its own phase signals.
Paper/code/common assets are separate mounts controlled by the episode owner.

Descriptor validation does not inspect host files. The existing Provider's
metered bounds.tree must authenticate the actual closed tree, including absence
of extra files/directories, ordinary inodes and immutable contents, before use.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path
import re
from types import ModuleType

HERE = Path(__file__).resolve().parent
RECIPE = HERE.parent / 'matched-reference-v1/recipe.py'
RECIPE_SHA = '0d515204b447d343b10dc9687d5d63e901f46b77e5dad69f1a2daebae9d88b0a'
raw = RECIPE.read_bytes()
if hashlib.sha256(raw).hexdigest() != RECIPE_SHA:
    raise ValueError('matched reference recipe changed')
r = ModuleType('_reve_closed_view_recipe'); r.__file__ = str(RECIPE)
exec(compile(raw, str(RECIPE), 'exec'), r.__dict__)
a = r.adapter()
m = a.materials_module()
Refusal = r.Refusal
need = r.need

SCHEMAS = {'development': 'reve-development-data-view-v1', 'test': 'reve-test-data-view-v1'}
COUNTS = {'development': {'train': 6300, 'val': 1734}, 'test': {'test': 1803}}
FIELDS = {'schema', 'phase', 'profile', 'units', 'dtype', 'sampling_hz', 'channels',
          'class_order', 'counts', 'geometry', 'records', 'view_identity'}
DEV_FIELDS = {'participant', 'run', 'split', 'shape', 'sha256', 'event_ids', 'signal', 'labels'}
TEST_FIELDS = {'split', 'shape', 'sha256', 'event_ids', 'signal'}
CLASS_ORDER = ['left_fist', 'right_fist', 'both_fists', 'feet']


def identity(value):
    try:
        return r.identity(value)
    except (TypeError, ValueError, OverflowError, RecursionError) as error:
        raise Refusal('ordinary finite canonical JSON metadata required') from error


def pin_json(value):
    """Exact immutable view.json representation, including its final newline."""
    return a.pin(a.canonical(value) + b'\n')


def _geometry():
    return {'path': 'positions.json', 'sha256': m.POSITIONS_SHA256,
            'bytes': m.POSITIONS_BYTES, 'electrodes_in_signal_channel_order': list(m.ELECTRODES),
            'coordinate_convention': 'unchanged numeric coordinates in the pinned author bank'}


def validate_view(view):
    """Reject open schemas/private fields; caller binds the compiled view identity.

    A self-consistent digest is not an external source-authentication claim.
    ``compile_views`` supplies that binding; an episode must retain its result,
    rather than accepting a replacement view supplied by a candidate.
    """
    need(type(view) is dict and set(view) == FIELDS, 'exact closed phase data schema')
    phase = view['phase']
    need(type(phase) is str and phase in SCHEMAS and view['schema'] == SCHEMAS[phase],
         'known exact phase schema')
    need(view['profile'] == m.PROFILE and view['units'] == 'uV' and view['dtype'] == 'float64'
         and type(view['sampling_hz']) is int and view['sampling_hz'] == 200
         and type(view['channels']) is list and view['channels'] == m.CHANNELS
         and type(view['class_order']) is list and view['class_order'] == CLASS_ORDER,
         'unchanged original physical signal contract')
    need(type(view['counts']) is dict and view['counts'] == COUNTS[phase]
         and all(type(n) is int for n in view['counts'].values()), 'complete exact phase counts')
    need(type(view['geometry']) is dict and view['geometry'] == _geometry()
         and type(view['geometry']['bytes']) is int,
         'exact original shared geometry; no extra metadata')
    rows = view['records']
    need(type(rows) is list and len(rows) == (534 if phase == 'development' else 1803),
         'complete original phase recording roster')
    totals = {split: 0 for split in COUNTS[phase]}
    events, signals = set(), set()
    expected = [(person, run) for person in range(1, 90) for run in m.RUNS]
    for index, row in enumerate(rows):
        need(type(row) is dict and set(row) == (DEV_FIELDS if phase == 'development' else TEST_FIELDS),
             'exact phase row fields; no private or foreign data')
        shape = row['shape']; ids = row['event_ids']
        need(type(shape) is list and len(shape) == 3 and all(type(n) is int for n in shape)
             and shape[0] > 0 and shape[1:] == [64, 800], 'full original epoch geometry')
        need(type(row['sha256']) is str and a.HEX.fullmatch(row['sha256']), 'original signal digest')
        need(type(ids) is list and len(ids) == shape[0] and all(type(eid) is str for eid in ids),
             'complete ordinary event identities')
        if phase == 'development':
            person, run = expected[index]
            split = 'train' if person <= 70 else 'val'
            need(type(row['participant']) is type(row['run']) is int and row['participant'] == person
                 and row['run'] == run and row['split'] == split
                 and row['signal'] == f'signals/S{person:03d}R{run:02d}.npy',
                 'exact subjects 1-89, original six runs and split order')
            need(type(row['labels']) is list and len(row['labels']) == shape[0]
                 and all(type(label) is int and label in ((0, 1) if run in (4, 8, 12) else (2, 3))
                         for label in row['labels']), 'all and only original development labels')
            need(all(re.fullmatch(fr'S{person:03d}R{run:02d}-event[0-9]{{3,}}', eid) for eid in ids),
                 'original development event mapping')
        else:
            split = 'test'
            need(row['split'] == split and shape == [1, 64, 800]
                 and type(row['signal']) is str
                 and re.fullmatch(r'signals/query-[0-9a-f]{32}\.npy', row['signal'])
                 and re.fullmatch(r'trial-[0-9a-f]{32}', ids[0]),
                 'one opaque epoch per test file; no source identity or grouping')
        need(row['signal'] not in signals and not events.intersection(ids)
             and len(set(ids)) == len(ids), 'unique phase files and complete event bijection')
        signals.add(row['signal']); events.update(ids); totals[split] += shape[0]
    need(totals == COUNTS[phase], 'complete original phase epoch support')
    claimed = view['view_identity']
    need(type(claimed) is str and a.HEX.fullmatch(claimed), 'phase view digest required')
    body = {key: value for key, value in view.items() if key != 'view_identity'}
    need(identity(body) == claimed, 'phase view changed after compilation')
    return view


def compile_views(document, expected_materials_identity, expected_panel_identity):
    """Authenticate a detached full packet BEFORE selecting any phase metadata.

    The resulting data documents are identical for literal paper/data and
    paper/data/code conditions over the same original data. Neither document
    contains condition assets, full-packet identities or private join commitments.
    This function allocates metadata only and does not read any signal body.
    """
    need(type(document) is dict, 'complete public material document required')
    snapshot = deepcopy(document)
    try:
        info = a.packet_info(snapshot, expected_materials_identity, expected_panel_identity)
    except a.Refusal as error:
        raise Refusal(str(error)) from error
    result = {'info': deepcopy(info)}
    data = snapshot['data']
    for phase in SCHEMAS:
        view = {'schema': SCHEMAS[phase], 'phase': phase,
                **{key: deepcopy(data[key]) for key in
                   ('profile', 'units', 'dtype', 'sampling_hz', 'channels', 'class_order', 'geometry')},
                'counts': deepcopy(COUNTS[phase]),
                'records': deepcopy(r.phase_data(info, 'fit' if phase == 'development' else 'predict'))}
        view['view_identity'] = identity(view)
        validate_view(view)
        result[phase] = view
    return result


def _root(root):
    need(isinstance(root, (str, Path)), 'explicit absolute phase directory path')
    path = Path(root)
    need(path.is_absolute() and path != Path(path.anchor) and '..' not in path.parts,
         'absolute non-root phase directory without parent traversal')
    return str(path)


def data_mount(view, root, signal_sizes):
    """Compile ONE closed data-directory descriptor; no filesystem operations.

    ``signal_sizes`` must contain exactly this phase's paths, not the full source
    packet. The existing Provider authenticates exact physical membership and
    bodies. A full original packet directory fails that authentication.
    """
    validate_view(view)
    need(type(signal_sizes) is dict and set(signal_sizes) == {row['signal'] for row in view['records']},
         'all and only this phase signal extents')
    files = {'view.json': pin_json(view),
             'positions.json': {key: view['geometry'][key] for key in ('bytes', 'sha256')}}
    for row in view['records']:
        size = signal_sizes[row['signal']]
        payload = row['shape'][0] * 64 * 800 * 8
        need(type(size) is int and payload + 10 <= size <= payload + 65548,
             'bounded full original float64 NPY extent')
        files[row['signal']] = {'bytes': size, 'sha256': row['sha256']}
    return {'path': _root(root), 'kind': 'directory', 'purpose': 'input', 'files': files}


def validate_mount(view, desc):
    """Reject full packet/subset/extra/private *descriptors*, without reading files.

    Actual tree closure is enforced by the Provider, not asserted by this
    metadata function. The owner must compare against its compiled trusted view.
    """
    validate_view(view)
    need(type(desc) is dict and set(desc) == {'path', 'kind', 'purpose', 'files'}
         and type(desc['path']) is str and desc['kind'] == 'directory' and desc['purpose'] == 'input',
         'one exact closed input-directory descriptor')
    expected_paths = {'view.json', 'positions.json'} | {row['signal'] for row in view['records']}
    need(type(desc['files']) is dict and set(desc['files']) == expected_paths,
         'exact closed phase membership; no omissions, extra files or condition/private assets')
    for pin in desc['files'].values():
        try:
            a.descriptor(pin)
        except a.Refusal as error:
            raise Refusal(str(error)) from error
    sizes = {row['signal']: desc['files'][row['signal']]['bytes'] for row in view['records']}
    need(desc == data_mount(view, desc['path'], sizes), 'exact compiled phase file pins and canonical root')
    return desc
