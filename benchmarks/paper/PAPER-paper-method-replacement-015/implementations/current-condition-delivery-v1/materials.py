"""Operator-only projection of protected current-condition participant materials.

Returns bounded in-memory bytes; it neither writes an export nor isolates a
process. Only the runner may publish a packet into its controlled fold context.
"""
import builtins
from copy import deepcopy
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import types

import numpy as np

HERE = Path(__file__).resolve().parent
EVALUATOR_SHA256 = '3cfdecb445c678be0ad9bef57186c230272d9cbfdf169a7af110aef2cc628cc5'
ARTIFACT_IO_SHA256 = 'ea37f8f03ba74c837582199f8f80e251b083f0077a74b5da5c0e1659dfe08344'
ASSETS_SHA256 = '0e51909ec008a8e4feab14bd5fb9e4b694a9f45ec03e7d9a10ad1bd3c65c4869'
CONDITION_ID = 'current_source_noise7_eligible_v1'
ARMS = ('paper_data', 'paper_data_author_code')
PURPOSES = ('reproduction', 'improvement')
MAX_PACKET_BYTES = 32 * 1024 * 1024
MAX_ASSET_BYTES = 1024 * 1024
MAX_MANIFEST_BYTES = 1024 * 1024
TRAINING_FIELDS = ('fluorescence', 'target_hz', 'counts', 'support', 'bin_centers_seconds')
QUERY_FIELDS = ('fluorescence', 'support', 'bin_centers_seconds')
DTYPES = {'fluorescence': np.dtype('<f8'), 'target_hz': np.dtype('<f8'),
          'counts': np.dtype('<i8'), 'support': np.dtype('bool'),
          'bin_centers_seconds': np.dtype('<f8')}
ROW_FIELDS = {'recording_id', 'neuron_id', 'offset', 'samples'}
MANIFEST_FIELDS = {'schema', 'condition_id', 'held_neuron', 'cohort', 'arm', 'purpose',
                   'nominal_rate_hz', 'target_sigma_seconds', 'context_margin_bins',
                   'training_records', 'query_records'}
SHA = re.compile(r'[0-9a-f]{64}\Z')


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _encoded(value):
    return (json.dumps(value, allow_nan=False, sort_keys=True, separators=(',', ':')) + '\n').encode()


def _read_source(path, expected_sha, cap=65536):
    path = Path(path)
    _need(not path.is_symlink(), 'source symlink refused')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        _need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= cap,
              'bounded ordinary pinned source required')
        body = stream.read(cap + 1)
        after = os.fstat(stream.fileno())
    named = path.lstat()
    stamp = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    _need(stamp(before) == stamp(after) == stamp(named) and len(body) == before.st_size
          and hashlib.sha256(body).hexdigest() == expected_sha, 'pinned source identity mismatch')
    return body


def load_current():
    """Load both pinned source bodies; never import an ambient artifact_io module."""
    folder = HERE.parent / 'current-condition-evaluator-v1'
    io_bytes = _read_source(folder / 'artifact_io.py', ARTIFACT_IO_SHA256)
    evaluator_bytes = _read_source(folder / 'evaluate.py', EVALUATOR_SHA256)
    reader = types.ModuleType('_spinal_delivery_pinned_artifact_io')
    reader.__file__ = str(folder / 'artifact_io.py')
    exec(compile(io_bytes, reader.__file__, 'exec'), reader.__dict__)
    module = types.ModuleType('_spinal_delivery_current_evaluator')
    module.__file__ = str(folder / 'evaluate.py')
    ordinary_import = builtins.__import__

    def pinned_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == 'artifact_io' and level == 0:
            return reader
        return ordinary_import(name, globals, locals, fromlist, level)

    module.__dict__['__builtins__'] = dict(vars(builtins), __import__=pinned_import)
    previous_module = sys.modules.get(module.__name__)
    previous_path = list(sys.path)
    sys.modules[module.__name__] = module  # dataclass resolves its defining module.
    try:
        exec(compile(evaluator_bytes, module.__file__, 'exec'), module.__dict__)
    except BaseException:
        if previous_module is None:
            sys.modules.pop(module.__name__, None)
        else:
            sys.modules[module.__name__] = previous_module
        raise
    finally:
        sys.path[:] = previous_path
    return module


def select_fold(bank, held):
    """Return an operator-only plan; callers must keep the complete census private."""
    metadata = bank.metadata
    condition = metadata['condition']
    _need(condition['name'] == 'current_source_recipe_single_realization_v1'
          and condition['nominal_rate_hz'] == 30 and condition['requested_noise_level'] == 7
          and condition['target_sigma_seconds'] == .05 and condition['context_window_bins'] == 64
          and condition['historical_paper_realization'] is False, 'adopted current condition required')
    neurons = metadata['expected_neurons']
    rows = metadata['recordings']
    _need(isinstance(neurons, dict) and len(neurons) == 44
          and list(neurons.values()).count('glutamatergic') == 21
          and list(neurons.values()).count('gabaergic') == 23, 'complete44 neuron/cohort census required')
    _need(isinstance(held, str) and held in neurons, 'known held neuron required')
    _need(isinstance(rows, list) and len(rows) == 132 and metadata['source_recordings'] == 132,
          'complete132 source recording census required')
    _need(isinstance(bank.manifest_sha256, str) and SHA.fullmatch(bank.manifest_sha256), 'bank identity required')
    seen = set()
    ordinals = {neuron: [] for neuron in neurons}
    eligible = []
    census = []
    for row in rows:
        neuron, identity = row['neuron_id'], row['recording_id']
        ordinal = row['source_recording_index_zero_based']
        _need(neuron in neurons and row['cohort'] == neurons[neuron] and type(ordinal) is int
              and ordinal >= 0 and identity == f'{neuron}/recording-{ordinal:03d}'
              and identity not in seen, 'distinct source neuron/recording identities required')
        seen.add(identity)
        ordinals[neuron].append(ordinal)
        if row['status'] == 'prepared':
            _need(type(row['output_samples']) is int and 64 < row['output_samples'] <= 1_000_000,
                  'bounded current observation geometry required')
            eligible.append(row)
        else:
            _need(row['status'] == 'unavailable' and row.get('reason') == 'native_noise_exceeds_requested_noise',
                  'only adopted input-noise exclusions permitted')
        census.append({k: row[k] for k in ('recording_id', 'neuron_id', 'cohort',
                                           'source_recording_index_zero_based', 'status')})
    _need(len(eligible) == 116 and all(values == list(range(len(values))) and values
                                     for values in ordinals.values()), 'complete116 eligible/original order required')
    _need({row['neuron_id'] for row in eligible} == set(neurons), 'eligible support for all44 neurons required')
    cohort = neurons[held]
    training = [row for row in eligible if row['neuron_id'] != held and row['cohort'] == cohort]
    query = [row for row in eligible if row['neuron_id'] == held]
    return {'schema': 'spinal_current_operator_fold_plan_v1', 'condition_id': CONDITION_ID,
            'bank_manifest_sha256': bank.manifest_sha256, 'held_neuron': held, 'cohort': cohort,
            'training_rows': deepcopy(training), 'query_rows': deepcopy(query),
            'held_source_excluded_ids': [row['recording_id'] for row in rows if row['neuron_id'] == held],
            'source_census': census, 'expected_neurons': dict(neurons),
            'source_recordings': 132, 'eligible_recordings': 116, 'source_excluded_recordings': 16}


def _record_map(rows):
    offset = 0
    result = []
    for row in rows:
        n = row['output_samples']
        result.append({'recording_id': row['recording_id'], 'neuron_id': row['neuron_id'],
                       'offset': offset, 'samples': n})
        offset += n
    return result


def _participant_manifest(plan, arm, purpose):
    _need(arm in ARMS and purpose in PURPOSES, 'explicit paired arm and purpose required')
    return {'schema': 'spinal_current_fold_materials_v1', 'condition_id': CONDITION_ID,
            'held_neuron': plan['held_neuron'], 'cohort': plan['cohort'], 'arm': arm, 'purpose': purpose,
            'nominal_rate_hz': 30., 'target_sigma_seconds': .05, 'context_margin_bins': 32,
            'training_records': _record_map(plan['training_rows']),
            'query_records': _record_map(plan['query_rows'])}


def _source_arrays(arrays, n):
    _need(isinstance(arrays, dict) and set(arrays) == set(TRAINING_FIELDS), 'exact five source arrays required')
    for key, values in arrays.items():
        _need(isinstance(values, np.ndarray) and values.shape == (n,)
              and values.dtype.kind == DTYPES[key].kind and values.dtype.itemsize == DTYPES[key].itemsize,
              'exact source dtype and record shape required')
        if key != 'support':
            _need(np.isfinite(values).all(), 'source arrays must be finite')
    mask = np.zeros(n, dtype=bool)
    mask[32:-32] = True
    _need(np.array_equal(arrays['support'], mask) and np.all(arrays['target_hz'] >= 0)
          and np.all(arrays['counts'] >= 0) and np.all(np.diff(arrays['bin_centers_seconds']) > 0),
          'source support/rate/count/clock mismatch')
    return arrays


def build_materials(bank, held, arm, purpose, array_loader=None):
    """Project the fixed bank into one fold; injected loaders are for generated controls."""
    plan = select_fold(bank, held)
    manifest = _participant_manifest(plan, arm, purpose)
    expected_body = sum(row['samples'] for row in manifest['training_records']) * 33
    expected_body += sum(row['samples'] for row in manifest['query_records']) * 17
    _need(expected_body + MAX_ASSET_BYTES + MAX_MANIFEST_BYTES + 16384 <= MAX_PACKET_BYTES,
          'participant material budget exceeded before array reads')
    loader = array_loader if array_loader is not None else load_current()._source_arrays

    def project(rows, fields):
        pieces = {key: [] for key in fields}
        for row in rows:
            arrays = _source_arrays(loader(bank, row), row['output_samples'])
            for key in fields:
                pieces[key].append(arrays[key])
        result = {}
        for key in fields:
            result[key] = np.concatenate(pieces[key]).astype(DTYPES[key], copy=False)
            result[key].flags.writeable = False
        return result

    return {'manifest': manifest, 'training': project(plan['training_rows'], TRAINING_FIELDS),
            'query': project(plan['query_rows'], QUERY_FIELDS), 'operator_plan': plan}


def _asset_manifest():
    reader = load_current()
    descriptor, _ = reader.read_json(HERE / 'ASSETS.json', expected_sha=ASSETS_SHA256, limit=65536)
    _need(set(descriptor) == {'schema', 'author_revision', 'paper', 'author_code'}
          and descriptor['schema'] == 'spinal_current_delivery_assets_v1'
          and descriptor['author_revision'] == '1f9f98bf93b9b554ab68d6304aa365ab7c7ee34f'
          and len(descriptor['paper']) == 1 and len(descriptor['author_code']) == 18,
          'frozen paper and18 official source files required')
    return descriptor


def _asset_rows(arm):
    _need(arm in ARMS, 'explicit paired arm required')
    descriptor = _asset_manifest()
    selected = descriptor['paper'] + (descriptor['author_code'] if arm == 'paper_data_author_code' else [])
    result = {}
    total = 0
    for row in selected:
        _need(isinstance(row, dict) and set(row) == {'path', 'bytes', 'sha256'}, 'exact asset descriptor required')
        if row['path'] == 'public/common/paper.xml':
            target = 'paper.xml'
        else:
            _need(isinstance(row['path'], str) and row['path'].startswith('public/author-code/'), 'official asset path required')
            target = row['path'][len('public/'):]
        relative = PurePosixPath(target)
        _need(not relative.is_absolute() and str(relative) == target and '..' not in relative.parts
              and '\\' not in target and target not in result, 'canonical distinct asset names required')
        _need(type(row['bytes']) is int and 0 < row['bytes'] <= MAX_ASSET_BYTES
              and isinstance(row['sha256'], str) and SHA.fullmatch(row['sha256']), 'bounded pinned asset required')
        total += row['bytes']
        _need(total <= MAX_ASSET_BYTES, 'total asset budget exceeded')
        result[target] = row
    _need('paper.xml' in result and len(result) == (19 if arm == 'paper_data_author_code' else 1),
          'exact paired asset roster required')
    return result


def capture_assets(root, arm):
    """Capture only the fixed paper and, in B, the18 unchanged source files."""
    reader = load_current()
    return {target: reader.read_pinned(root, pin, limit=MAX_ASSET_BYTES)
            for target, pin in _asset_rows(arm).items()}


def material_bytes(materials, assets):
    """Serialize an exact participant whitelist; never serialize operator_plan."""
    _need(isinstance(materials, dict) and set(materials) == {'manifest', 'training', 'query', 'operator_plan'},
          'exact material sections required')
    manifest = materials['manifest']
    _need(isinstance(manifest, dict) and set(manifest) == MANIFEST_FIELDS, 'participant manifest whitelist required')
    expected_manifest = _participant_manifest(materials['operator_plan'], manifest['arm'], manifest['purpose'])
    _need(manifest == expected_manifest, 'participant rows must match the selected operator plan')
    files = {'FOLD.json': _encoded(manifest)}
    _need(len(files['FOLD.json']) <= MAX_MANIFEST_BYTES, 'participant manifest budget exceeded')
    expected_assets = _asset_rows(manifest['arm'])
    _need(isinstance(assets, dict) and set(assets) == set(expected_assets), 'exact arm assets required')
    for name, payload in assets.items():
        pin = expected_assets[name]
        _need(type(payload) is bytes and len(payload) == pin['bytes']
              and hashlib.sha256(payload).hexdigest() == pin['sha256'], 'captured asset identity mismatch')
        files[name] = payload
    body_bytes = 0
    for role, fields in (('training', TRAINING_FIELDS), ('query', QUERY_FIELDS)):
        arrays = materials[role]
        _need(isinstance(arrays, dict) and set(arrays) == set(fields), 'participant array whitelist required')
        records = manifest[role + '_records']
        n = sum(row['samples'] for row in records)
        for row in records:
            _need(set(row) == ROW_FIELDS, 'participant record whitelist required')
        for name, values in arrays.items():
            _need(isinstance(values, np.ndarray) and values.shape == (n,) and values.dtype == DTYPES[name],
                  'participant array geometry/dtype mismatch')
            body_bytes += values.nbytes
    _need(body_bytes + sum(map(len, files.values())) + 16384 <= MAX_PACKET_BYTES,
          'packet byte budget exceeded before serialization')
    for role in ('training', 'query'):
        stream = io.BytesIO()
        np.savez(stream, **materials[role])
        files[role + '.npz'] = stream.getvalue()
    _need(all(0 < len(body) <= MAX_PACKET_BYTES for body in files.values())
          and sum(map(len, files.values())) <= MAX_PACKET_BYTES, 'bounded complete packet required')
    return files
