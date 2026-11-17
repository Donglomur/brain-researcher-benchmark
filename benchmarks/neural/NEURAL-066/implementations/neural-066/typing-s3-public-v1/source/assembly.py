"""Host-only exact preparation and public realm construction; no numerical reads."""
from pathlib import Path
from core import encoded, identity, need
from safe_io import child, strict, npy_header
from workspace import descriptor

def relative(d, name):
    return {'path': name, 'bytes': d['bytes'], 'sha256': d['sha256']}

def output_metadata(ws, capture, names):
    return {'capture_root': capture['capture_root'], 'output_files': capture['output_files'], 'metadata': {name: ws.budget.read_file(ws.from_capture(capture, name)['source_path'], capture['output_files'][name], ws.metadata['json_bytes']) for name in names}}

def public_view(ws, capture, condition=None):
    prefix = '' if condition is None else condition + '/'
    d = ws.from_capture(capture, prefix + 'VIEW.json')
    view = ws.read(d['source_path'], d)
    result = ws.result(capture)
    if condition is not None:
        result = result['reference_views'][condition]
    need(view['condition'] == result['context']['condition'] and view['case'] == result['context']['case'], 'Exact public/private context join')
    return {'capture': capture, 'prefix': prefix, 'view': view, 'private': result}

def candidate_bindings(ws, public, realm, name):
    """No private RESULT/source keys, query labels, original neural pins or peers."""
    need(realm in ('train', 'query', 'diagnostic'), 'Declared single-context realm')
    view = public['view']
    prefix = public['prefix']
    capture = public['capture']
    selected = ['GEOMETRY.json']
    if realm in ('train', 'diagnostic'):
        selected += ['train.npy', 'TRAIN_LAYOUT.json']
    if realm in ('query', 'diagnostic'):
        selected += ['query.npy']
    bindings = {p: ws.from_capture(capture, prefix + p) for p in selected}
    for artifact_name,d in bindings.items():
        declared=view['arrays'][artifact_name] if artifact_name in ('train.npy','query.npy') else view['geometry'] if artifact_name=='GEOMETRY.json' else view['layout']
        need(all(d[k]==declared[k]for k in ('bytes','sha256')),'Actual captured public role matches complete prepared view declaration')
    manifest = {k: view[k] for k in ('case', 'generation', 'condition', 'arm', 'mode', 'modality', 'channels', 'feature_dimensions', 'samples_per_key', 'feature_spec', 'support_commitment', 'source_contract_pin', 'projection_pin', 'language_policy_pin')}
    manifest.update(schema='neural066_candidate_input_v3', task='NEURAL-066', realm=realm, arrays={n: view['arrays'][n] for n in ('train.npy', 'query.npy') if n in selected}, geometry=relative(bindings['GEOMETRY.json'], 'GEOMETRY.json'), event_assisted=True, full_current_case_batch=realm != 'train', zero_labeled_target_person_calibration=True)
    if 'TRAIN_LAYOUT.json' in selected:
        manifest['training_layout'] = relative(bindings['TRAIN_LAYOUT.json'], 'TRAIN_LAYOUT.json')
    if 'query.npy' in selected:
        manifest['queries'] = view['queries']
    d = ws.json(name + '/INPUT.json', manifest)
    bindings['INPUT.json'] = d
    return (bindings, manifest)

def model_bindings(ws, capture, expected_context, model_cap):
    """Inert typed final computational state; no pickle/executable deserialization."""
    model_d = ws.from_capture(capture, 'MODEL.json')
    model = ws.read(model_d['source_path'], model_d)
    need(model.get('schema') == 'neural066_candidate_model_v1' and type(model.get('configuration')) is dict and (type(model.get('arrays')) is dict) and (type(model.get('stateless')) is bool), 'Explicit candidate state schema')
    need(model.get('context') == expected_context, 'Full final model current-case identity')
    result = ws.result(capture)
    need(result.get('schema') == 'neural066_candidate_result_v1' and result.get('status') == 'complete' and (result.get('action') == 'candidate_fit') and (result.get('model_context') == expected_context), 'Own original complete FIT result/context')
    need(result.get('model') == {k: model_d[k] for k in ('bytes', 'sha256')}, 'Original FIT result seals exactly this model')
    need(not model['stateless'] or not model['arrays'], 'No fitted arrays in stateless declaration; independent semantic gate remains')
    bindings = {'MODEL.json': model_d}
    total = model_d['bytes']
    for key, d in model['arrays'].items():
        need(type(key) is str and type(d) is dict and (set(d) == {'path', 'bytes', 'sha256', 'shape', 'dtype'}), 'Exact inert array descriptor')
        need(d['path'].endswith('.npy') and d['path'] not in bindings and (d['dtype'] in ('<f4', '<f8', '<i8', '|u1', '|i1')) and (type(d['shape']) is list) and all((type(n) is int and n >= 0 for n in d['shape'])), 'Primitive tensor metadata')
        b = ws.from_capture(capture, d['path'])
        need(all((b[k] == d[k] for k in ('bytes', 'sha256'))), 'Captured model array pin')
        raw = ws.budget.read_file(b['source_path'], {k: b[k] for k in ('bytes', 'sha256')}, model_cap)
        header = npy_header(raw)
        need(list(header['shape']) == d['shape'] and header['descr'] == d['dtype'] and (header['fortran_order'] is False), 'Actual inert C-order tensor framing, not descriptor-only acceptance')
        bindings[d['path']] = b
        total += b['bytes']
    need(total <= model_cap, 'Complete final model extent; no prefix acceptance')
    return (bindings, model)

def prediction_record(ws, capture, public):
    d = ws.from_capture(capture, 'PREDICTIONS.json')
    body = ws.read(d['source_path'], d)
    from protected_score import admit_predictions
    admitted = admit_predictions(body, public['view'])
    return (admitted, d)
