"""Trusted future phase worker. Imports never launch a scientific process.

The controller owns complete cohort/lineage admission, outer/inner partitions,
immutable mounts and authorization. Candidates execute their own commands and
never receive this module or its private payloads. Every action below is real;
none runs merely because this source is imported.
"""
import argparse
import ast
import hashlib
import math
import os
from pathlib import Path
import re
import stat
import struct
import subprocess
import sys
import time
import uuid

# -I removes ambient Python paths. Only this approved read-only tree is inserted.
_SOURCE = str(Path(__file__).resolve().parent)
if _SOURCE not in sys.path:
    sys.path.insert(0, _SOURCE)

import numpy as np
from artifacts import Store, load_model
from core import INPUTS, BRANCHES, descriptor, encoded, need, token
from safe_io import capture, child, pin, strict, cleanup_note
from numerical_worker import fit_reference, predict_reference, admit_candidate_model, _tokens
from reference import encoder
from views import one_record, training_view, context_categories, source_reference, context_for_row, target_trajectory
from scoring import grade

REQUEST_BOOTSTRAP_CAP = 1048576
RESOURCE_KEYS = {
    'setup_seconds', 'producer_seconds', 'capture_seconds', 'cleanup_seconds',
    'memory_bytes', 'cpu_nanos', 'pids', 'scratch_bytes', 'max_files',
    'max_directories', 'max_file_bytes', 'max_output_bytes', 'manifest_bytes',
    'max_cli_calls', 'max_cli_bytes', 'inventory_bytes', 'source_read_bytes', 'host_write_bytes',
}
ACTIONS = {'prepare_originals', 'prepare_views', 'fit', 'query', 'reconstruct',
           'selection_evaluate', 'final_evaluate', 'report'}


def _exact(value, keys, schema=None):
    need(type(value) is dict and set(value) == set(keys), 'Exact worker payload fields')
    if schema is not None:
        need(value.get('schema') == schema, 'Worker payload schema')
    return value


def _relative(name):
    need(type(name) is str and 0 < len(name) <= 4096 and not name.startswith('/') and
         '\\' not in name and all(part not in ('', '.', '..') and
         not any(ord(c) < 32 for c in part) for part in name.split('/')), 'Safe exact relative path')
    return name


class Scope:
    """A mount view sharing ONE Store's counters, file map and original deadline."""
    def __init__(self, store, prefix, writable=False):
        self.store = store
        self.prefix = _relative(prefix)
        self.writable = writable
        need(not writable or prefix == 'output' or prefix.startswith('output/'), 'Output-only writes')

    def _name(self, name):
        return self.prefix + '/' + _relative(name)

    @property
    def files(self):
        prefix = self.prefix + '/'
        return {name[len(prefix):]: value for name, value in self.store.files.items()
                if name.startswith(prefix)}

    @property
    def limits(self):
        return self.store.limits

    def tick(self):
        self.store.tick()

    def read(self, name, expected, metadata=False):
        return self.store.read(self._name(name), expected, metadata=metadata)

    def json(self, name, expected):
        return strict(self.read(name, expected, metadata=True))

    def numeric(self, desc):
        need(type(desc) is dict and 'path' in desc, 'Primitive descriptor')
        return self.store.numeric({**desc, 'path': self._name(desc['path'])})

    def put(self, name, raw):
        need(self.writable, 'Read-only mount')
        return self.store.put(self._name(name), raw)

    def put_json(self, name, value):
        raw = encoded(value)
        need(len(raw) <= self.limits['metadata_bytes'], 'Bounded complete JSON output')
        return self.put(name, raw)

    def put_numeric(self, name, value):
        need(self.writable, 'Read-only mount')
        result = self.store.put_numeric(self._name(name), value)
        return {**result, 'path': name}

    def subscope(self, relative):
        return Scope(self.store, self._name(relative), self.writable)

    def envelope(self, phase_id, request_pin, result):
        return Store.envelope(self, phase_id, request_pin, result)


def _mount_file(path, root):
    need(type(path) is str and path.startswith('/' + root + '/'), 'Exact approved mount')
    return _relative(path[len(root) + 2:])


def _validate_request(request):
    _exact(request, {'schema', 'phase_id', 'action', 'role', 'image', 'command',
                     'workdir', 'source', 'exposure', 'clock', 'resources', 'output'},
           'paper_i_owned_phase_request_v1')
    token(request['phase_id'])
    action, role = request['action'], request['role']
    need(action in ACTIONS and role == ('reference' if action in ('fit', 'query', 'reconstruct')
                                      else 'operator'), 'Trusted worker role/action boundary')
    need(type(request['image']) is str and re.fullmatch('sha256:[0-9a-f]{64}', request['image']),
         'Immutable approved image')
    argv = request['command']
    need(type(argv) is list and 1 <= len(argv) <= 64 and all(type(v) is str and
         0 < len(v.encode()) <= 4096 and '\0' not in v for v in argv) and argv[0].startswith('/'),
         'Exact bounded command')
    need(request['workdir'] == '/work' and request['output'] ==
         {'kind': 'generic', 'manifest': 'OUTPUTS.json'}, 'Exact transport locations')
    descriptor(request['source']); descriptor(request['exposure'])
    clock = _exact(request['clock'], {'origin', 'phase_deadline'})
    need(all(type(v) in (int, float) and math.isfinite(v) for v in clock.values()) and
         0 <= clock['origin'] < clock['phase_deadline'], 'Original finite phase clock')
    need(clock['origin'] <= time.monotonic() < clock['phase_deadline'], 'Phase remains on original clock')
    resources = _exact(request['resources'], RESOURCE_KEYS)
    need(all(type(v) is int and v > 0 for v in resources.values()), 'Explicit positive phase bounds')
    need(resources['memory_bytes'] >= 134217728 and resources['scratch_bytes'] % 4096 == 0 and
         resources['max_output_bytes'] % 4096 == 0 and resources['inventory_bytes'] >= 4096,
         'Transport memory/inventory bounds')
    need(resources['manifest_bytes'] <= resources['max_file_bytes'] <= resources['max_output_bytes'],
         'Nested output bounds')
    need(resources['source_read_bytes'] >= REQUEST_BOOTSTRAP_CAP, 'Pre-reserved request bootstrap cap')
    return request


def _rows(values, total, name):
    need(type(values) is list and values and all(type(v) is int and 0 <= v < total for v in values)
         and len(set(values)) == len(values), 'Complete unique ' + name)
    return values


def _training_permutation(spec, acquisition, arrays, rows, modality=None):
    """Operator-private whole-trial null; physical ordering is shared across modalities."""
    if type(spec) is list:
        need(all(type(pair) is list and len(pair) == 2 and all(type(v) is int for v in pair)
                 for pair in spec) and len({pair[0] for pair in spec}) == len(spec),
             'Private unique integer whole-trial pairs')
        return dict(spec)
    _exact(spec, {'physical_trials', 'seed'})
    physical = spec['physical_trials']
    need(type(physical) is list and physical and all(type(value) is str and
         0 < len(value.encode()) <= 1024 for value in physical) and len(set(physical)) == len(physical),
         'Complete unique private physical identities, not public opaque tokens')
    need(len(physical) == len(rows), 'Every training row has one private physical identity')
    seed = spec['seed']
    need(type(seed) is int and 0 <= seed < 2**63, 'Private shared null seed int63')
    joined = acquisition.get('schema') == 'paper_i_joined_acquisition_v1'
    if joined:
        need(modality in ('CF', 'GrC'), 'Joined null has an explicit observed modality')
        observed = acquisition.get('observed_modalities')
        need(type(observed) is list and len(observed) == acquisition['original_trial_count'],
             'Complete source-derived observed-modality census')
    else:
        rewarded = arrays[acquisition['arrays']['rewarded']['path']]
        need(rewarded.shape == (acquisition['original_trial_count'],), 'Original outcome axis for null strata')
    groups = {}
    for row, physical_id in zip(rows, physical):
        if joined:
            categories = context_for_row(acquisition, arrays, modality, row)
            availability = observed[row]
            need(type(availability) is list and modality in availability and
                 len(set(availability)) == len(availability) and set(availability) <= {'CF', 'GrC'},
                 'Exact source-derived availability stratum')
        else:
            value = rewarded[row]
            need(np.isfinite(value) and value in (0, 1), 'Literal source outcome for private strata')
            categories = context_categories(acquisition, bool(value))
            availability = ['single-source-view']
        stratum = (tuple(categories[key] for key in encoder.CATEGORIES), tuple(availability))
        groups.setdefault(stratum, []).append((physical_id, row))
    mapping = {}
    for stratum in sorted(groups):
        ordered = sorted(groups[stratum])
        # Independent deterministic stratum RNG prevents an unpaired group in
        # one modality from advancing the RNG used by shared observed groups.
        digest = hashlib.sha256(encoded({'seed': seed, 'stratum': stratum})).digest()
        rng = np.random.Generator(np.random.PCG64(int.from_bytes(digest[:16], 'big')))
        shuffled = rng.permutation(len(ordered))
        for index, (_, destination) in enumerate(ordered):
            mapping[destination] = ordered[int(shuffled[index])][1]
    need(set(mapping) == set(rows) and set(mapping.values()) == set(rows), 'Complete private training bijection')
    return mapping


def make_view(payload, prepared_store, output_store):
    """Emit a reusable public population TRAIN, single-record queries and private joins."""
    _exact(payload, {'schema', 'acquisition', 'modality', 'profile', 'train_rows', 'held_rows',
                     'cell_tokens', 'cell_indices', 'categorical_vocabulary', 'permutation',
                     'label_provenance', 'transport_seed', 'namespace'}, 'paper_i_worker_views_v1')
    acquisition, modality, profile = payload['acquisition'], payload['modality'], payload['profile']
    need(type(acquisition) is dict and profile in encoder.PROFILES, 'Admitted acquisition/profile')
    total = acquisition.get('original_trial_count')
    need(type(total) is int and total > 0, 'Full original trial count')
    train_rows = _rows(payload['train_rows'], total, 'training rows')
    held_rows = _rows(payload['held_rows'], total, 'held rows')
    need(not set(train_rows).intersection(held_rows), 'Training/held row isolation')
    modal = [m for m in acquisition.get('modalities', []) if m.get('name') == modality]
    need(len(modal) == 1 and modal[0].get('status') == 'present', 'Present selected modality')
    modal = modal[0]
    cells = _tokens(payload['cell_tokens'])
    need(modal['cell_count'] == len(cells), 'Complete selected population')
    need(payload['cell_indices'] is None or payload['cell_indices'] == list(range(len(cells))),
         'Reusable public TRAIN must retain every selected cell; final reference subsets are fit-only')
    need(type(payload['namespace']) is str and re.fullmatch('[0-9a-f]{32}', payload['namespace']),
         'Opaque public namespace')
    seed = payload['transport_seed']
    need(type(seed) is int and 0 <= seed < 2**128, 'Private transport-order seed')
    mapping = payload['permutation']
    if profile == 'CM-shuffled':
        need(type(mapping) in (dict, list), 'Private shared null seed wrapper or explicit pair list')
        provenance = payload['label_provenance']
        need(type(provenance) is dict and set(provenance) == {'kind', 'receipt_sha256'} and
             provenance['kind'] == 'whole_training_trajectory_reassignment' and
             type(provenance['receipt_sha256']) is str and re.fullmatch('[0-9a-f]{64}',
             provenance['receipt_sha256']), 'Minimal operator-only null attestation')
    else:
        need(mapping is None and payload['label_provenance'] is None, 'No null map on non-null profile')
    names = {'behavior_clock', 'rewarded', 'eligible', 'eligible_rewarded', 'eligible_omitted',
             'goodMvmt_source', 'mvlen', 'rewdel_seconds', 'trueend', 'rewtimes'}
    if profile != 'C':
        names.update(('rew_pos', 'movement_duration_ms', 'truestart'))
    arrays = {}; target_paths = set()
    def load(desc):
        if desc['path'] not in arrays: arrays[desc['path']] = prepared_store.numeric(desc)
    if acquisition.get('schema') == 'paper_i_joined_acquisition_v1':
        selected_sources = {}
        for row in train_rows + held_rows:
            source, _, _ = source_reference(acquisition, modality, row)
            selected_sources[source['key']] = source
    else:
        selected_sources = {acquisition['key']: acquisition}
    for source in selected_sources.values():
        for name in sorted(names): load(source['arrays'][name])
        source_modal = next(m for m in source['modalities'] if m['name'] == modality)
        load(source_modal['target_time']); load(source_modal['targets'])
        target_paths.add(source_modal['targets']['path'])
    load(modal['target_time'])
    if profile == 'CM-shuffled':
        mapping = _training_permutation(mapping, acquisition, arrays, train_rows, modality)
    view = training_view(acquisition, arrays, modality, train_rows, profile, permutation=mapping)
    schema = {'profile': profile}
    if profile != 'C':
        schema['movement_features'] = list(encoder.MOVEMENT_FEATURES)
    if profile != 'M':
        schema.update(categorical_vocabulary=payload['categorical_vocabulary'],
                      target_time_grid=arrays[modal['target_time']['path']].tolist())
    else:
        need(payload['categorical_vocabulary'] is None, 'M has no context vocabulary or row clock')
    schema = encoder._schema(schema)
    # Validate all records against the complete admitted structural vocabulary.
    encoder._records(view['X'], schema)
    order = np.random.Generator(np.random.PCG64(seed)).permutation(len(view['X']))
    public = output_store.subscope('public')
    private = output_store.subscope('private')
    train = {'schema': 'paper_i_training_view_v1', 'profile': profile, 'feature_schema': schema,
             'cell_tokens': cells, 'X': [view['X'][int(i)] for i in order],
             'Y': public.put_numeric('Y.npy', np.ascontiguousarray(view['Y'][order])),
             'weights': public.put_numeric('weights.npy', np.ascontiguousarray(view['weights'][order])),
             'namespace': payload['namespace']}
    train_pin = public.put_json('TRAIN.json', train)
    mean_desc = private.put_numeric('training_mean.npy', np.ascontiguousarray(view['training_mean']))
    grid = arrays[modal['target_time']['path']]
    held = np.stack([target_trajectory(acquisition, arrays, modality, row) for row in held_rows])
    held = held.transpose(0, 2, 1).reshape(-1, len(cells))
    need(np.isfinite(held).all(), 'Every required held target is finite; no dropping')
    truth_desc = private.put_numeric('TRUTH.npy', np.ascontiguousarray(held, dtype=np.float64))
    # Target body is absent from the map handed to query construction.
    query_arrays = {path: value for path, value in arrays.items() if path not in target_paths}
    query_index = []
    used = set()
    for row in held_rows:
        for time_index in range(len(grid)):
            record = one_record(acquisition, query_arrays, modality, row, time_index, profile)
            encoder._records([record], schema)
            query_token = uuid.uuid4().hex
            need(query_token not in used, 'Random query namespace collision')
            used.add(query_token)
            path = 'queries/' + query_token + '.json'
            query = {'schema': 'paper_i_query_view_v1', 'profile': profile, 'record': record,
                     'cell_tokens': cells, 'namespace': payload['namespace']}
            query_pin = public.put_json(path, query)
            query_index.append({'token': query_token, 'path': 'public/' + path, 'pin': query_pin,
                                'source_row': row, 'time_index': time_index,
                                'categories': context_for_row(acquisition, query_arrays, modality, row),
                                'truth_index': len(query_index)})
    index = {'schema': 'paper_i_private_view_index_v1', 'acquisition': acquisition['key'],
             'modality': modality, 'profile': profile, 'cell_tokens': cells,
             'training_index': [view['private_index'][int(i)] for i in order],
             'queries': query_index, 'truth': truth_desc, 'training_mean': mean_desc,
             'null_ineffective_singleton_rows': view['null_ineffective_singleton_rows'],
             'operator_private': True}
    index_pin = private.put_json('INDEX.json', index)
    if payload['label_provenance'] is not None:
        private.put_json('REFERENCE_LABEL_PROVENANCE.json', payload['label_provenance'])
    return {'schema': 'paper_i_view_result_v1', 'profile': profile, 'cell_tokens': cells,
            'train_path': 'public/TRAIN.json', 'train_pin': train_pin,
            'index_path': 'private/INDEX.json', 'index_pin': index_pin,
            'training_examples': len(view['X']), 'query_count': len(query_index),
            'public_training_contains_all_cells': True, 'operator_private': True}


def _fit(payload, input_store, output_store):
    _exact(payload, {'schema', 'train_path', 'train_pin', 'configuration', 'selected_cell_indices',
                     'label_provenance'}, 'paper_i_worker_fit_v1')
    name = _mount_file(payload['train_path'], 'input')
    train = input_store.json(name, payload['train_pin'])
    _exact(train, {'schema', 'profile', 'feature_schema', 'cell_tokens', 'X', 'Y', 'weights', 'namespace'},
           'paper_i_training_view_v1')
    need(type(train['namespace']) is str and re.fullmatch('[0-9a-f]{32}', train['namespace']),
         'Opaque public namespace')
    parent = str(Path(name).parent)
    store = input_store if parent == '.' else input_store.subscope(parent)
    reference = {key: value for key, value in train.items() if key != 'namespace'}
    reference.update(schema='paper_i_reference_train_v1', configuration=payload['configuration'],
                     selected_cell_indices=payload['selected_cell_indices'],
                     label_provenance=payload['label_provenance'])
    return fit_reference(reference, store, output_store)


def _query(payload, input_store, model_store, output_store):
    _exact(payload, {'schema', 'bundle_path', 'bundle_pin', 'query_path', 'query_pin'},
           'paper_i_worker_query_v1')
    bundle_name = _mount_file(payload['bundle_path'], 'models')
    bundle = model_store.json(bundle_name, payload['bundle_pin'])
    query = input_store.json(_mount_file(payload['query_path'], 'input'), payload['query_pin'])
    _exact(query, {'schema', 'profile', 'record', 'cell_tokens', 'namespace'}, 'paper_i_query_view_v1')
    need(query['profile'] == bundle.get('profile') and query['cell_tokens'] == bundle.get('cell_tokens')
         and type(query['namespace']) is str and re.fullmatch('[0-9a-f]{32}', query['namespace']),
         'Query/bundle axis and namespace')
    parent = str(Path(bundle_name).parent)
    store = model_store if parent == '.' else model_store.subscope(parent)
    return predict_reference(bundle, store, output_store, query['record'])


def selection_evaluate(payload, input_store):
    """Complete pooled per-cell inner errors; exact declared-order tie breaking."""
    _exact(payload, {'schema', 'profile', 'cell_tokens', 'configurations', 'fold_tokens', 'errors',
                     'fit_accounting'}, 'paper_i_worker_selection_v1')
    cells = _tokens(payload['cell_tokens'])
    profile = payload['profile']
    need(profile in encoder.PROFILES, 'Selected profile')
    configurations = payload['configurations']
    need(type(configurations) is list and configurations and all(type(c) is dict and
         type(c.get('id')) is str and c['id'] for c in configurations), 'Ordered precommitted configurations')
    ids = [c['id'] for c in configurations]
    need(len(set(ids)) == len(ids), 'Unique configuration IDs')
    # Reference family must be supplied in its exact design tie order. Candidate
    # families retain their own precommitted deterministic configuration order.
    if any(c.get('representation') in ('raw', 'spline', 'context_average') for c in configurations):
        need(configurations == encoder.configs(profile), 'Exact reference family/tie order')
    folds = _tokens(payload['fold_tokens'])
    errors = payload['errors']
    need(type(errors) is list and len(errors) == len(ids) * len(folds), 'Every inner config/fold required')
    seen, counts = set(), {}
    sums = np.zeros((len(ids), len(cells)), dtype=np.float64)
    for row in errors:
        _exact(row, {'configuration_id', 'fold_token', 'squared_error_sum', 'count'})
        config, fold, count = row['configuration_id'], row['fold_token'], row['count']
        need(config in ids and fold in folds and (config, fold) not in seen, 'Unique complete inner pair')
        need(type(count) is int and count > 0, 'Positive full-support inner example count')
        need(fold not in counts or counts[fold] == count, 'No configuration-dependent inner support')
        counts[fold] = count
        error = input_store.numeric(row['squared_error_sum'])
        need(error.shape == (len(cells),) and np.isfinite(error).all() and np.all(error >= 0),
             'Finite nonnegative per-cell full-support SSE')
        sums[ids.index(config)] += error
        seen.add((config, fold))
    need(seen == {(c, f) for c in ids for f in folds} and np.isfinite(sums).all(),
         'Complete finite pooled inner errors')
    pooled = sums / sum(counts.values())
    winners = np.argmin(pooled, axis=0)
    groups = []
    for index, configuration in enumerate(configurations):
        selected = np.flatnonzero(winners == index).tolist()
        if selected:
            groups.append({'configuration': configuration, 'configuration_id': ids[index],
                           'cell_indices': selected, 'cell_tokens': [cells[i] for i in selected]})
    accounting = _exact(payload['fit_accounting'], {'logical_cell_fits', 'fit_calls', 'svd_factorizations'})
    need(type(accounting['fit_calls']) is int and accounting['fit_calls'] >= 0,
         'Exact trusted launched fit-process count')
    need(all(accounting[key] is None or type(accounting[key]) is int and accounting[key] >= 0
             for key in ('logical_cell_fits', 'svd_factorizations')),
         'Reference work counts or explicit unknown candidate internal work')
    return {'schema': 'paper_i_selection_result_v1', 'profile': profile, 'cell_tokens': cells,
            'choices': [{'cell_token': cell, 'configuration_id': ids[int(winners[i])],
                         'pooled_mse': float(pooled[winners[i], i])} for i, cell in enumerate(cells)],
            'groups': groups, 'pooled_mse_by_configuration': [
                {'configuration_id': config, 'mse': pooled[i].tolist()} for i, config in enumerate(ids)],
            'held_example_count': sum(counts.values()), 'complete_inner_pairs': len(seen),
            'fit_accounting': accounting, 'tie_rule': 'first in complete precommitted configuration order',
            'operator_private': True}


def admit_model(payload, model_store):
    _exact(payload, {'schema', 'model_path', 'model_pin', 'profile', 'cell_tokens', 'model_kind'},
           'paper_i_worker_admit_v1')
    name = _mount_file(payload['model_path'], 'models')
    kind = payload['model_kind']
    need(kind in ('candidate', 'reference'), 'Exact operator-bound model kind')
    if kind == 'candidate':
        model = admit_candidate_model(name, payload['model_pin'], model_store,
                                      payload['profile'], payload['cell_tokens'])
    else:
        need(payload['profile'] in encoder.PROFILES, 'Reference admission profile')
        _tokens(payload['cell_tokens'])
        model = load_model(model_store, name, payload['model_pin'], payload['profile'], payload['cell_tokens'])
        need(model['metadata'].get('version') == encoder.MODEL_VERSION and
             model['metadata'].get('n_cells') == len(payload['cell_tokens']) and
             type(model['metadata'].get('schema')) is dict and
             model['metadata']['schema'].get('profile') == payload['profile'],
             'Exact trusted reference model version/profile/cell axes')
        need(all(np.isfinite(array).all() for array in model['arrays'].values()),
             'Finite complete trusted reference primitive state')
    return {'schema': 'paper_i_model_admission_v1', 'model_kind': kind, 'model_path': payload['model_path'],
            'model_pin': payload['model_pin'], 'profile': payload['profile'],
            'cell_tokens': payload['cell_tokens'], 'primitive_arrays': len(model['arrays']),
            'numeric_payload_bytes': sum(array.nbytes for array in model['arrays'].values()),
            'candidate_code_executed': False, 'candidate_internal_operations_observed': False,
            'qualification': 'primitive artifact admission only; no predictive competence claim',
            'operator_private': True}


def inner_errors(payload, input_store, output_store):
    """Complete held-vector squared-error reduction, never a fit or native call."""
    _exact(payload, {'schema', 'cell_tokens', 'truths', 'truth_rows', 'predictions'},
           'paper_i_worker_errors_v1')
    cells = _tokens(payload['cell_tokens'])
    truth = input_store.numeric(payload['truths'])
    need(truth.ndim == 2 and truth.shape[1] == len(cells), 'Complete truth matrix cell axis')
    rows = _rows(payload['truth_rows'], len(truth), 'held truth matrix rows')
    predictions = payload['predictions']
    need(type(predictions) is list and len(predictions) == len(rows), 'One complete prediction per held row')
    total = np.zeros(len(cells), dtype=np.float64)
    for row, desc in zip(rows, predictions):
        predicted = input_store.numeric(desc)
        need(predicted.shape == (len(cells),) and np.isfinite(predicted).all() and
             np.isfinite(truth[row]).all(), 'Finite complete held vectors')
        difference = predicted - truth[row]
        total += difference * difference
    need(np.isfinite(total).all(), 'Finite complete accumulated held SSE')
    desc = output_store.put_numeric('SSE.npy', total)
    return {'schema': 'paper_i_inner_errors_result_v1', 'cell_tokens': cells,
            'squared_error_sum': desc, 'count': len(rows), 'operator_private': True}


def final_evaluate(payload, input_store):
    _exact(payload, {'schema', 'support', 'truths', 'predictions', 'training_means', 'view_groups'},
           'paper_i_worker_final_v1')
    cache = {}
    def load_map(values):
        need(type(values) is dict, 'Exact private complete vector map')
        result = {}
        for key, desc in values.items():
            token(key)
            if type(desc) is dict and set(desc) == {'array', 'row'}:
                descriptor = desc['array']
                need(type(descriptor) is dict, 'Primitive matrix descriptor')
                # Full descriptor identity includes the bound path and numeric
                # axes. Repeated rows share one charged complete array read.
                identity = encoded(descriptor)
                if identity not in cache:
                    cache[identity] = input_store.numeric(descriptor)
                matrix = cache[identity]
                row = desc['row']
                need(matrix.ndim == 2 and type(row) is int and 0 <= row < len(matrix),
                     'Exact bounded private matrix row')
                result[key] = matrix[row]
            else:
                result[key] = input_store.numeric(desc)
        return result
    truths, predictions = load_map(payload['truths']), load_map(payload['predictions'])
    means = None if payload['training_means'] is None else load_map(payload['training_means'])
    metrics = grade(payload['support'], truths, predictions, training_means=means)
    groups = _exact(payload['view_groups'], {'Water', '1-s DA', 'DA-first', '2-s DA'})
    diagnostics = {}
    support_by_token = {row['token']: row for row in payload['support']}
    for name, tokens in groups.items():
        need(type(tokens) is list and all(type(value) is str for value in tokens) and
             len(tokens) == len(set(tokens)) and set(tokens) <= set(support_by_token),
             'Exact private native-view query support')
        if not tokens:
            diagnostics[name] = {'status': 'unavailable', 'reason': 'no_query_support_for_native_view',
                                 'query_count': 0}
            continue
        selected = set(tokens)
        support = [row for row in payload['support'] if row['token'] in selected]
        view_metrics = grade(support, {key: truths[key] for key in tokens},
                             {key: predictions[key] for key in tokens},
                             training_means=None if means is None else {key: means[key] for key in tokens})
        diagnostics[name] = {'status': 'available', 'query_count': len(tokens), 'metrics': view_metrics}
    return {'schema': 'paper_i_final_result_v1', 'metrics': metrics,
            'native_view_diagnostics': diagnostics,
            'native_views_are_overlapping_diagnostics_only': True, 'operator_private': True}


def report(payload, input_store):
    _exact(payload, {'schema', 'closed_results', 'status'}, 'paper_i_worker_report_v1')
    need(type(payload['closed_results']) is list and payload['closed_results'], 'Closed authenticated results')
    need(type(payload['status']) is dict and payload['status'], 'Complete operator-supplied status')
    results, seen = [], set()
    for ref in payload['closed_results']:
        _exact(ref, {'path', 'pin'})
        name = _mount_file(ref['path'], 'input')
        need(name not in seen, 'Unique closed result source')
        seen.add(name)
        results.append({'source': ref, 'result': input_store.json(name, ref['pin'])})
    return {'schema': 'paper_i_closed_report_v1', 'status': payload['status'], 'closed_results': results,
            'source_pins_authenticated': True, 'scientific_completeness': 'controller-admitted status',
            'operator_private': True}


def _stream_pin(store, relative, expected=None, publisher_md5=None, keep_prefix=0):
    """One bounded whole-file hash pass, never a numeric/native body reader."""
    path = child(store.root, _relative(relative))
    store.tick()
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    primary = None
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_size <= store.limits['file_bytes'],
             'Bounded regular full file')
        if expected is not None:
            descriptor(expected, True)
            need(before.st_size == expected['bytes'], 'Pinned whole-file extent before body read')
        need(store.reads + before.st_size <= store.limits['read_bytes'], 'Reserve whole-file hash read')
        store.reads += before.st_size
        sha, md5, prefix = hashlib.sha256(), hashlib.md5(), bytearray()
        total = 0
        while total < before.st_size:
            store.tick()
            block = os.read(fd, min(1048576, before.st_size - total))
            need(block, 'Complete file before EOF')
            total += len(block); sha.update(block); md5.update(block)
            if len(prefix) < keep_prefix:
                prefix.extend(block[:keep_prefix - len(prefix)])
        after = os.fstat(fd)
        attrs = ('st_dev', 'st_ino', 'st_mode', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
        need(all(getattr(before, k) == getattr(after, k) for k in attrs), 'Stable complete hash source')
        result = {'bytes': total, 'sha256': sha.hexdigest()}
        if expected is not None:
            descriptor(expected, True)
            need(result == expected, 'Whole immutable file pin')
        if publisher_md5 is not None:
            need(md5.hexdigest() == publisher_md5, 'Full publisher MD5')
        return result, bytes(prefix)
    except BaseException as error:
        primary = error
        raise
    finally:
        try:
            os.close(fd)
        except BaseException as error:
            if primary is None:
                raise
            cleanup_note(primary, 'whole-file-hash.close', error)


def _native_header(prefix, desc):
    need(set(desc) == {'path', 'bytes', 'sha256', 'shape', 'dtype'}, 'Exact native NPY descriptor')
    descriptor({k: desc[k] for k in ('bytes', 'sha256')}, True)
    need(len(prefix) >= 10 and prefix[:8] == b'\x93NUMPY\x01\x00', 'Primitive NPY1 native output')
    length = struct.unpack('<H', prefix[8:10])[0]
    need(10 + length <= len(prefix), 'Complete bounded native header')
    header = ast.literal_eval(prefix[10:10 + length].decode('latin1'))
    need(type(header) is dict and set(header) == {'descr', 'fortran_order', 'shape'} and
         header['fortran_order'] is False and header['descr'] in ('<f8', '<f4', '<i8', '|i1'),
         'Primitive native dtype/order')
    shape = header['shape']
    need(type(shape) is tuple and all(type(n) is int and n >= 0 for n in shape) and
         list(shape) == desc['shape'] and header['descr'] == desc['dtype'], 'Exact native numeric axes')
    extent = math.prod(shape) * {'<f8': 8, '<f4': 4, '<i8': 8, '|i1': 1}[header['descr']]
    need(10 + length + extent == desc['bytes'], 'Complete native NPY body extent')


def _admit_native(output_store, request, action):
    """Natural-exit full inventory; no partial capture or scientific readiness promotion."""
    store = output_store.store
    root = child(store.root, output_store._name('native'))
    need(root.is_dir() and not root.is_symlink(), 'Owned native output directory')
    found, directories, pending = {}, 0, [root]
    while pending:
        directory = pending.pop()
        store.tick()
        with os.scandir(directory) as entries:
            for entry in entries:
                need(not entry.is_symlink(), 'No native output symlinks')
                if entry.is_dir(follow_symlinks=False):
                    directories += 1
                    need(directories <= request['resources']['max_directories'], 'Complete bounded native directory tree')
                    pending.append(Path(entry.path))
                else:
                    need(entry.is_file(follow_symlinks=False), 'Regular native output only')
                    relative = Path(entry.path).relative_to(root).as_posix()
                    _relative(relative)
                    need(len(found) + len(store.files) < store.limits['files'], 'Native complete file ceiling')
                    state = entry.stat(follow_symlinks=False)
                    need(state.st_size <= store.limits['file_bytes'], 'Native full file ceiling')
                    found[relative] = state.st_size
    total = sum(found.values())
    need(store.writes + total <= store.limits['write_bytes'], 'Native whole output plus worker metadata ceiling')
    store.writes += total  # Actual native-produced bytes share the phase counter.
    manifest_name = 'PREPARED.json' if action == 'prepare_originals' else 'NATIVE.json'
    need(manifest_name in found and found[manifest_name] <= store.limits['metadata_bytes'],
         'Complete bounded native metadata')
    manifest_relative = output_store._name('native/' + manifest_name)
    expected = {'bytes': found[manifest_name], 'sha256': '0' * 64}
    # Native did not know the SHA; one bounded metadata read establishes it.
    need(store.reads + expected['bytes'] <= store.limits['read_bytes'], 'Reserve native metadata read')
    store.reads += expected['bytes']
    raw = capture(child(store.root, manifest_relative), store.limits['metadata_bytes'])
    need(len(raw) == found[manifest_name], 'Closed metadata extent')
    manifest_pin = pin(raw)
    manifest = strict(raw)
    store.files[manifest_relative] = manifest_pin
    if action == 'prepare_originals':
        need(manifest.get('schema') == 'filio_i_prepared_v1' and type(manifest.get('output_files')) is list,
             'Complete original preparation manifest')
        declared = {}
        for desc in manifest['output_files']:
            need(type(desc) is dict and type(desc.get('path')) is str, 'Native declared array')
            name = _relative(desc['path'])
            need(name not in declared and name.endswith('.npy'), 'Unique primitive prepared output')
            declared[name] = desc
        need(set(found) == set(declared) | {manifest_name}, 'No missing or undeclared native outputs')
        for name, desc in declared.items():
            expected = {k: desc[k] for k in ('bytes', 'sha256')}
            need(found[name] == expected['bytes'], 'Full native array extent')
            relative = output_store._name('native/' + name)
            file_pin, prefix = _stream_pin(store, relative, expected, keep_prefix=65545)
            _native_header(prefix, desc)
            store.files[relative] = file_pin
        need(type(manifest.get('files_census')) is list and
             {row.get('file') for row in manifest['files_census']} == {row['name'] for row in INPUTS}
             and len(manifest['files_census']) == len(INPUTS), 'All ten native input censuses')
    else:
        need(set(found) == {manifest_name} and manifest.get('schema') == 'filio_native_numeric_v1',
             'Complete native reconstruction single numeric JSON')
    return {'path': 'native/' + manifest_name, 'pin': manifest_pin, 'files': len(found),
            'output_bytes': total, 'expanded_native_ram_bytes': None,
            'native_decompression_and_read_traffic_bytes': None,
            'unknowns': ['Expanded native memory and native reader traffic are not inferred from serialized extent.']}


def run_native(payload, request, output_store):
    _exact(payload, {'schema', 'matlab', 'originals', 'limits', 'branch', 'initial_seed'},
           'paper_i_worker_native_v1')
    originals = payload['originals']
    need(type(originals) is dict and set(originals) == {row['name'] for row in INPUTS},
         'All ten original publisher objects')
    verification = []
    for row in INPUTS:
        supplied = _exact(originals[row['name']], {'bytes', 'sha256', 'md5'})
        need(supplied['bytes'] == row['bytes'] and supplied['md5'] == row['md5'], 'Publisher object identity')
        expected = {k: supplied[k] for k in ('bytes', 'sha256')}
        descriptor(expected)
        actual, _ = _stream_pin(output_store.store, 'originals/' + row['name'], expected, row['md5'])
        verification.append({'name': row['name'], **actual, 'publisher_md5': row['md5']})
    action = request['action']
    native_root = child(output_store.store.root, output_store._name('native'))
    need(not native_root.exists(), 'Fresh exclusively owned native destination')
    native_root.mkdir(mode=0o700)
    from native.bridge import launch_spec
    if action == 'prepare_originals':
        limits = _exact(payload['limits'], {'max_files', 'max_file_bytes', 'max_output_bytes',
                                           'max_metadata_bytes', 'max_collection_items', 'max_native_elements'})
        need(all(type(v) is int and v > 0 for v in limits.values()), 'Explicit native limits')
        need(limits['max_metadata_bytes'] <= limits['max_file_bytes'] <= limits['max_output_bytes'],
             'Nested native limits')
        need(limits['max_files'] < output_store.limits['files'] and
             limits['max_file_bytes'] <= output_store.limits['file_bytes'] and
             limits['max_metadata_bytes'] <= output_store.limits['metadata_bytes'] and
             limits['max_output_bytes'] < output_store.limits['write_bytes'] - output_store.store.writes,
             'Reserve native output under same phase allocation, with metadata room')
        need(payload['branch'] is None and payload['initial_seed'] is None, 'Preparation has no branch/seed')
        output_store.put_json('NATIVE_LIMITS.json', limits)
        spec = launch_spec('prepare', payload['matlab'], '/native', '/originals', '/output/native',
                           'operator', limits_path='/output/NATIVE_LIMITS.json')
    else:
        need(action == 'reconstruct' and payload['limits'] is None and payload['branch'] in BRANCHES,
             'Exact reference branch')
        spec = launch_spec('branch', payload['matlab'], '/native', '/originals', '/output/native',
                           'reference', branch=payload['branch'], initial_seed=payload['initial_seed'])
    output_store.tick()
    remaining = output_store.store.deadline - time.monotonic()
    need(remaining > 0, 'No fresh native clock')
    # Outer owned container handles descendants/cleanup and OS memory/process
    # limits. This call returns only after natural success, never after cropping.
    subprocess.run(spec['argv'], cwd=spec['cwd'], check=True, timeout=remaining,
                   stdin=subprocess.DEVNULL)
    output_store.tick()
    admitted = _admit_native(output_store, request, action)
    return {'schema': 'paper_i_native_result_v1', 'action': action, 'branch': payload['branch'],
            'initial_seed': payload['initial_seed'], 'originals_verified': verification,
            'capture': admitted, 'natural_exit': True, 'native_runtime_qualified': False,
            'operator_private': True}


def dispatch(request, payload, store):
    _validate_request(request)
    output = Scope(store, 'output', writable=True)
    input_store = Scope(store, 'input')
    action = request['action']
    if action == 'prepare_views':
        if payload.get('schema') == 'paper_i_worker_support_v1':
            from support import prepare
            result = prepare(payload, Scope(store, 'prepared'), output)
        else:
            result = make_view(payload, Scope(store, 'prepared'), output)
    elif action == 'fit':
        result = _fit(payload, input_store, output)
    elif action == 'query':
        result = _query(payload, input_store, Scope(store, 'models'), output)
    elif action == 'selection_evaluate':
        if payload.get('schema') == 'paper_i_worker_errors_v1':
            result = inner_errors(payload, input_store, output)
        elif payload.get('schema') == 'paper_i_worker_admit_v1':
            result = admit_model(payload, Scope(store, 'models'))
        else:
            result = selection_evaluate(payload, input_store)
    elif action == 'final_evaluate':
        if payload.get('schema') == 'paper_i_worker_native_grade_v1':
            from native_compare import grade as native_grade
            result = native_grade(payload, input_store)
        else:
            result = final_evaluate(payload, input_store)
    elif action == 'report':
        result = report(payload, input_store)
    else:
        result = run_native(payload, request, output)
    output.tick()
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description='Approved private/reference phase worker')
    parser.add_argument('--payload', required=True)
    parser.add_argument('--payload-bytes', required=True, type=int)
    parser.add_argument('--payload-sha256', required=True)
    args = parser.parse_args(argv)
    raw = capture('/request.json', REQUEST_BOOTSTRAP_CAP)
    request_pin = pin(raw)
    request = _validate_request(strict(raw))
    resources = request['resources']
    limits = {'read_bytes': resources['source_read_bytes'], 'write_bytes': resources['max_output_bytes'],
              'file_bytes': resources['max_file_bytes'], 'metadata_bytes': resources['manifest_bytes'],
              'files': resources['max_files']}
    store = Store('/', limits, request['clock']['phase_deadline'])
    store.reads = len(raw)  # Charge bootstrap to the same cumulative phase ledger.
    expected = descriptor({'bytes': args.payload_bytes, 'sha256': args.payload_sha256})
    payload = Scope(store, 'input').json(_mount_file(args.payload, 'input'), expected)
    output = Scope(store, 'output', writable=True)
    need(not any(Path('/output').iterdir()), 'Fresh empty phase output')
    result = dispatch(request, payload, store)
    result = {**result, 'phase_id': request['phase_id'], 'original_clock': request['clock'],
              'worker_io_before_envelope': {'read_bytes': store.reads, 'write_bytes': store.writes}}
    output.envelope(request['phase_id'], request_pin, result)


if __name__ == '__main__':
    main()
