"""Original-source bank loader; legacy aggregate references fail closed."""
import hashlib
import json
from pathlib import Path
import numpy as np
import population_contract as q

BUILDER_ID = 'mtl-released-multiset-original-source-v2'
PAYLOAD_FIELDS = ('sessions trials units metadata provenance method_json source_manifest_json').split()


def digest(text):
    return hashlib.sha256(text.encode('utf8')).hexdigest()


def validate_reference(ref, full=True):
    q.require(set(PAYLOAD_FIELDS) <= set(ref), 'Missing bank source provenance')
    q.require(digest(ref['method_json']) == q.METHOD_SHA256, 'Wrong frozen method bank')
    q.require(digest(ref['source_manifest_json']) == q.SOURCE_SHA256, 'Wrong frozen source bank')
    method = json.loads(ref['method_json']); manifest = json.loads(ref['source_manifest_json'])
    provenance = ref['provenance']
    q.require(provenance['builder_id'] == BUILDER_ID and provenance['status'] == ('complete' if full else 'resource_pilot'),
              'Historical/pilot bank is not complete original-source evidence')
    q.require(provenance['source_manifest_sha256'] == q.SOURCE_SHA256 and provenance['method_contract_sha256'] == q.METHOD_SHA256,
              'Wrong source/recipe provenance')
    files = {r['path']: r for r in manifest['files']}
    q.require(len(files) == len(manifest['files']) == 87, 'Wrong frozen source inventory')
    sessions = q.keyed(ref['sessions'], ['asset_path'])
    expected_paths = sorted(files) if full else [sorted(files)[0]]
    q.require([r['asset_path'] for r in ref['sessions']] == expected_paths, 'Bank source session coverage/order')
    q.match(ref['metadata']['method_contract'], method, 'bank method', 'exact', closed=True)
    q.match(ref['metadata']['source_sha256'], {p: r['sha256'] for p, r in files.items()}, 'bank source hashes', 'exact', closed=True)
    q.require(ref['metadata']['source_manifest_sha256'] == q.SOURCE_SHA256 and
              ref['metadata']['method_contract_sha256'] == q.METHOD_SHA256, 'Bank metadata identity')
    q.require(ref['metadata']['status'] == ('complete' if full else 'resource_pilot'), 'Wrong bank scope status')
    trials = q.keyed(ref['trials'], ['asset_path', 'source_trial_row'])
    units = q.keyed(ref['units'], ['asset_path', 'source_unit_row'])
    q.require(all(k[0] in files for k in trials) and all(k[0] in files for k in units), 'Unknown bank source asset')
    mtls, response_keys, response_ids, response_labels, response_units = [], [], [], [], []
    for path in expected_paths:
        session = sessions[(path,)]; record = files[path]
        q.require(session['asset_id'] == record['asset_id'] and session['source_sha256'] == record['sha256'], 'Wrong source session identity')
        ts = sorted([r for k, r in trials.items() if k[0] == path], key=lambda r: r['source_trial_row'])
        us = sorted([r for k, r in units.items() if k[0] == path], key=lambda r: r['source_unit_row'])
        q.require([r['source_trial_row'] for r in ts] == list(range(len(ts))), 'Incomplete original trial rows')
        q.require([r['source_unit_row'] for r in us] == list(range(len(us))), 'Incomplete original unit rows')
        q.require(len({r['trial_id'] for r in ts}) == len(ts) and len({r['unit_id'] for r in us}) == len(us), 'Duplicate original IDs')
        learned = {r['external_image_file'] for r in ts if r['stim_phase'] == 'learn'}
        recognition = []
        for row in ts:
            q.require(row['stim_phase'] in ('learn', 'recog'), 'Unknown source phase')
            included = row['stim_phase'] == 'recog'
            q.require(type(row['included']) is bool and row['included'] == included, 'Wrong source trial inclusion')
            q.require(row['status'] == ('included_recognition' if included else 'non_recognition_phase'), 'Wrong trial status')
            for field in ('start_time_s', 'stim_on_time_s', 'stim_off_time_s', 'stop_time_s'):
                q.number(row[field])
            q.require(row['start_time_s'] == row['stim_on_time_s'] and row['stim_on_time_s'] <= row['stim_off_time_s'], 'Invalid source start/onset/offset order')
            q.require(not included or row['stim_off_time_s'] <= row['stop_time_s'], 'Invalid recognition trial end order')
            if included:
                q.require(row['source_label_token'] in ('0', '1') and type(row['source_label']) is int and
                          row['source_label'] == int(row['source_label_token']), 'Wrong source label decoding')
                q.require(type(row['image_in_learning']) is bool and row['image_in_learning'] == (row['external_image_file'] in learned), 'Wrong released image-history receipt')
                recognition.append(row)
            else:
                q.require(row['source_label'] is None and row['image_in_learning'] is None, 'Undefined learning class required')
        n_mtl = 0
        for row in us:
            q.require(row['unit_key'] == path+'::unit='+str(row['unit_id']), 'Wrong original unit key')
            q.require(type(row['n_electrode_links']) is int and row['n_electrode_links'] == 1, 'Wrong source electrode link')
            hits = [name for name in ('Hippocampus', 'Amygdala') if name in row['location']]
            q.require(len(hits) <= 1, 'Ambiguous anatomy')
            included = bool(hits)
            q.require(type(row['included']) is bool and row['included'] == included, 'Wrong MTL mapping')
            q.require(row['region'] == (hits[0] if included else None), 'Wrong mapped region')
            q.require(row['exclusion_reason'] == ('included_mtl' if included else 'non_mtl_location'), 'Wrong anatomy status')
            if included:
                unit_index = len(mtls); mtls.append(row['unit_key']); n_mtl += 1
                for trial in recognition:
                    response_keys.append(trial['source_trial_row']); response_ids.append(trial['trial_id'])
                    response_labels.append(trial['source_label']); response_units.append(unit_index)
        q.match({k: session[k] for k in ('n_source_trials', 'n_learning_trials', 'n_recognition_trials', 'n_new', 'n_old', 'n_source_units', 'n_mtl_units')},
            dict(n_source_trials=len(ts), n_learning_trials=len(ts)-len(recognition), n_recognition_trials=len(recognition),
                 n_new=sum(r['source_label'] == 0 for r in recognition), n_old=sum(r['source_label'] == 1 for r in recognition),
                 n_source_units=len(us), n_mtl_units=n_mtl), 'source ledger counts')
    q.require(ref['unit_key'].dtype.kind == 'U' and ref['unit_key'].tolist() == mtls, 'Wrong canonical MTL unit axis')
    for name, wanted in [('response_unit_index', response_units), ('source_trial_row', response_keys),
                         ('trial_id', response_ids), ('source_label', response_labels), ('repeat_id', list(range(60)))]:
        value = ref[name]
        q.require(value.dtype.kind in 'iu' and value.ndim == 1 and value.tolist() == wanted, 'Wrong bank '+name)
    n = len(response_keys)
    q.require(ref['spike_count'].dtype.kind in 'iu' and ref['spike_count'].shape == (n,) and np.all(ref['spike_count'] >= 0), 'Invalid original count bank')
    q.require(ref['rate_hz'].dtype.kind == 'f' and ref['rate_hz'].shape == (n,) and np.isfinite(ref['rate_hz']).all(), 'Invalid bank rates')
    q.require(np.array_equal(ref['rate_hz'], ref['spike_count']/1.5), 'Incorrect bank count/rate arithmetic')
    q.require(ref['train_membership'].dtype.kind == 'b' and ref['train_membership'].shape == (60, n), 'Invalid bank membership')
    q.require(np.array_equal(ref['train_membership'], q.generate_masks(ref)), 'Wrong bank global RNG schedule')
    observed = ref['metadata']['source_observed']
    q.match({k: observed[k] for k in ('n_sessions', 'n_patients', 'n_source_trials', 'n_recognition_trials', 'n_source_units', 'n_mtl_units')},
        dict(n_sessions=len(sessions), n_patients=len({r['subject_id'] for r in ref['sessions']}),
             n_source_trials=len(trials), n_recognition_trials=sum(r['included'] for r in ref['trials']),
             n_source_units=len(units), n_mtl_units=len(mtls)), 'bank observed counts')
    q.require(set(q.keyed(observed['sessions'], ['asset_path'])) == set(sessions), 'Incomplete source observation bank')
    schema = method['outputs']['run_metadata.json']['source_observed']['session_record']
    for row in observed['sessions']:
        q.require(set(schema['required_fields']) <= set(row), 'Missing typed original observations')
        for name, kind in schema['types'].items():
            value = row[name]
            if kind == 'closed_object':
                q.require(isinstance(value, dict) and set(value) == set(schema[name]['required_exact_fields']), 'Wrong observed object')
                q.require(all(type(v) is int and (v >= 0 or name == 'phase_experiment_ids') for v in value.values()), 'Wrong observation integer')
            elif kind == 'boolean': q.require(type(value) is bool, 'Wrong observed Boolean')
            elif kind == 'nonnegative_integer': q.require(type(value) is int and value >= 0, 'Wrong observation count')
            elif kind == 'nullable_string': q.require(value is None or type(value) is str, 'Wrong literal nullable field')
            else: q.require(type(value) is str and (kind != 'unknown' or value == 'unknown'), 'Wrong literal field')
        asset_trials = [r for r in ref['trials'] if r['asset_path'] == row['asset_path']]
        for phase, name in [('learn','n_learning_temporal_order_violations'),('recog','n_recognition_temporal_order_violations')]:
            actual = sum(r['stim_phase'] == phase and not
                (r['start_time_s'] <= r['stim_on_time_s'] <= r['stim_off_time_s'] <= r['stop_time_s']) for r in asset_trials)
            q.require(row[name] == actual, 'Wrong source temporal-order diagnostic')
    if full:
        q.analyze(ref)


def load_reference(path):
    with np.load(path, allow_pickle=False) as archive:
        needed = {'ref_'+k for k in q.ARRAY_FIELDS} | {'reference_json'}
        q.require(needed <= set(archive.files), 'Obsolete/unbound numerical reference')
        text = archive['reference_json']
        q.require(text.shape == () and text.dtype.kind == 'U', 'Primitive source metadata required')
        def invalid(value):
            raise AssertionError('Nonfinite reference JSON')
        payload = json.loads(str(text), parse_constant=invalid)
        q.require(isinstance(payload, dict), 'Typed bank metadata required')
        ref = {k: np.array(archive['ref_'+k]) for k in q.ARRAY_FIELDS}
    q.require(set(PAYLOAD_FIELDS) <= set(payload), 'Missing bank source provenance')
    ref.update(payload); validate_reference(ref)
    return ref
