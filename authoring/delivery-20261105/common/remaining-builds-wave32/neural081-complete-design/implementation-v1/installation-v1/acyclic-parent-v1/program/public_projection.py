"""Controller-safe V4 projection: metadata reads and original opaque mounts only.

The trusted G0/issuer owns numerical projection and private HMAC material. This
module never opens, hashes, copies, permutes or decodes model/input/label arrays.
"""
from pathlib import Path
import common as c
import protocol as p
import reference_tools as public

INPUTS = ('train.npy', 'train_labels.npy', 'train_rows.json', 'query.npy')
CONTEXT_KEYS = ('schema', 'task_id', 'access_policy', 'mode', 'replication', 'view',
                'context_alias', 'class_ids', 'representation', 'query', 'training',
                'models', 'tools', 'remaining')


def _read(desc, budget, protected, maximum=16*2**20):
    c.descriptor(desc); c.integer(desc['bytes'], 1, maximum)
    path = c.absolute(desc['path'])
    c.need(path.suffix == '.json' and not any(path == c.absolute(d['path']) or path.is_relative_to(c.absolute(d['path'])) for d in protected), 'selected metadata only, protected bodies excluded')
    return c.parse(c.capture(desc, budget, [path.parent]))


def _sealed(value, budget, protected, maximum=64*2**20):
    c.need(type(value) is dict and 'descriptor' in value, 'sealed concrete source-owned record')
    body = _read(value['descriptor'], budget, protected, maximum)
    c.need(c.typed_equal(body, {k: v for k, v in value.items() if k != 'descriptor'}), 'exact original metadata record')
    return body


def _seal(root, name, value, budget):
    result = dict(value)
    result['descriptor'] = c.publish_json(root/name, value, budget)
    return result


def _protected(index):
    return [index['protected_support_descriptor'], index['protected_assessment_descriptor']]


def _mount(desc, target, opaque):
    c.descriptor(desc); c.absolute(target)
    return {'source': desc, 'target': target, 'opaque_host': opaque}


def _mounts(rows):
    c.need(len({x['target'] for x in rows}) == len(rows), 'unique complete generic mount map')
    for row in rows:
        c.exact(row, ('source', 'target', 'opaque_host')); c.descriptor(row['source'])
        c.need(type(row['opaque_host']) is bool and row['target'].startswith(('/input/', '/models/', '/tools/')), 'generic candidate-only mount')
    return rows


def remaining_snapshot(value, mode):
    c.exact(value, ('native_seconds', 'native_actions', 'provider_requests', 'scratch_write_bytes',
                    'managed_read_bytes', 'source_bytes', 'normal_seconds_remaining'))
    for key, item in value.items():
        if key == 'normal_seconds_remaining': c.finite(item, 0)
        else: c.integer(item)
    c.need(mode in c.MODES and value['native_actions'] <= (1 if mode == 'F' else 8), 'fixed action ceiling')
    c.need(value['provider_requests'] <= (0 if mode == 'F' else 9), 'no fixed-query provider capability')
    c.need(value['native_seconds'] <= 480 and value['source_bytes'] <= 65536, 'relative native/source ceilings')
    return dict(value)


def _role(meta, index, view, outer):
    c.exact(meta, ('schema', 'generation', 'view', 'outer_person', 'inner_person_or_FINAL', 'kind', 'people', 'ids', 'windows', 'labels', 'rows'))
    people = [x for x in c.PEOPLE if x != outer]
    expected = {r['canonical_id']: r for r in index['rows'] if r['person'] != outer}
    c.need(meta['schema'] == 'neural081_role_v1' and meta['generation'] == index['preparation_generation']
           and meta['view'] == view and meta['outer_person'] == outer and meta['inner_person_or_FINAL'] == meta['kind'] == 'FINAL'
           and meta['people'] == people, 'exact final training role')
    c.need(type(meta['ids']) is list and len(meta['ids']) == len(expected) and len(set(meta['ids'])) == len(expected)
           and set(meta['ids']) == set(expected), 'complete nine-person model support')
    c.need(c.typed_equal(meta['rows'], [{'canonical_id': i, 'person': expected[i]['person']} for i in meta['ids']]), 'exact role order and private inverse')
    c.need(c.typed_equal(meta['windows'], [expected[i]['window_descriptor'] for i in meta['ids']] if view == 'EEG' else []), 'same original permitted windows')
    c.descriptor(meta['labels']); return len(expected)


def issue_models(index, reference_run, model_row_tokens, tool_source, budget, output_root):
    """Issue exactly 80 reusable public metadata files, never copy model arrays.

    model_row_tokens is the exact G0 closure's 20-row list. tool_source is the
    selected public reference_tools.py descriptor. Return a sealed registry with
    folds in view/person order; each fold has its own descriptor and mount map.
    """
    p.validate_index(index); protected = _protected(index); generation = index['preparation_generation']
    refs = _sealed(reference_run, budget, protected)
    c.exact(refs, ('schema', 'generation', 'numeric_source', 'source_manifest', 'jobs', 'models', 'selections', 'panels', 'counts', 'R2_qualification_study_executed'))
    c.need(refs['schema'] == 'neural081_reference_run_v1' and refs['generation'] == generation
           and refs['R2_qualification_study_executed'] is False and len(refs['models']) == 80 and len(refs['selections']) == 20
           and refs['counts'] == {'fit': 3660, 'historical': 20, 'inner_infer': 3600, 'infer': 80, 'select': 20}, 'complete original reference run')
    numeric = c.descriptor(refs['numeric_source']); c.descriptor(tool_source)
    c.need(numeric['bytes'] == public.NUMERIC_BYTES and numeric['sha256'] == public.NUMERIC_SHA256, 'accepted unchanged numerical source')
    c.need(Path(tool_source['path']).name == 'reference_tools.py', 'fixed public tool source')
    # Source bytes are public and authenticated by the actual native closure;
    # no numerical/model bodies are read by this controller.
    c.authenticate_stream(tool_source, budget, [Path(tool_source['path']).parent])
    closure = _read(index['preparation_closure'], budget, protected, 128*2**20)
    c.need(closure.get('schema') == 'neural081_preparation_closure_v1' and closure.get('generation') == generation
           and closure.get('complete') is True and c.typed_equal(closure.get('model_row_tokens'), model_row_tokens), 'exact G0-issued complete token registry')
    c.need(type(model_row_tokens) is list and [(r['view'], r['outer']) for r in model_row_tokens] == [(v, o) for v in c.VIEWS for o in c.PEOPLE], 'all20 fixed model-token folds')
    root = c.new_directory(output_root, budget); folds = []
    for token_row in model_row_tokens:
        c.exact(token_row, ('view', 'outer', 'training_role', 'tokens_descriptor'))
        view, outer = token_row['view'], token_row['outer']; role_desc = token_row['training_role']
        n = _role(_read(role_desc, budget, protected), index, view, outer)
        tokens = _read(token_row['tokens_descriptor'], budget, protected)
        c.exact(tokens, ('schema', 'generation', 'view', 'outer', 'training_role', 'tokens'))
        c.need(tokens['schema'] == 'neural081_model_row_tokens_v1' and tokens['generation'] == generation
               and tokens['view'] == view and tokens['outer'] == outer and c.typed_equal(tokens['training_role'], role_desc), 'same pre-fit token role')
        values = tokens['tokens']; c.need(type(values) is list and len(values) == n, 'complete original model tokens')
        for value in values: c.ident(value)
        c.need(values == sorted(values) and len(set(values)) == n, 'fixed collision-free model order')
        chosen = [s for s in refs['selections'] if s['view'] == view and s['outer'] == outer]
        c.need(len(chosen) == 1, 'one concrete original selection'); chosen = chosen[0]
        c.exact(chosen, ('view', 'outer', 'result', 'body', 'closure'))
        result = _read(chosen['result'], budget, protected)
        c.exact(result, ('schema', 'operation', 'generation', 'numeric_source', 'body'))
        c.need(result['schema'] == 'neural081_reference_result_v1' and result['operation'] == 'select' and result['generation'] == generation
               and c.typed_equal(result['numeric_source'], numeric) and c.typed_equal(result['body'], chosen['body']), 'actual closed selection metadata')
        body = chosen['body']; c.need(c.typed_equal(body['role'], role_desc) and body['view'] == view and body['outer'] == outer, 'selection same permitted final training role')
        select = body['selection']; priors = body['priors']; c.exact(priors, ('uniform', 'laplace'))
        c.need([r['family'] for r in select['selected_per_family']] == list(p.FAMILIES)
               and [r['family'] for r in select['selected_temperatures']] == list(p.FAMILIES), 'complete selected family axes')
        directory = c.new_directory(root/(view+'-'+outer), budget)
        mounts = [_mount(tool_source, '/tools/reference_tools.py', False), _mount(numeric, '/tools/numeric.py', False)]
        models = []
        for handle in p.HANDLES:
            edges = [m for m in refs['models'] if (m['view'], m['outer'], m['family']) == (view, outer, handle)]
            c.need(len(edges) == 1, 'one original model per fold and family'); edge = edges[0]
            c.exact(edge, ('model', 'configuration', 'state_artifacts', 'training_role', 'view', 'outer', 'family', 'selection', 'closure', 'result'))
            c.need(c.typed_equal(edge['training_role'], role_desc) and c.typed_equal(edge['selection'], chosen['result']), 'original fit/selection role edge')
            meta = _read(edge['model'], budget, protected)
            c.exact(meta, ('schema', 'family', 'configuration', 'class_ids', 'n_train', 'n_features', 'temperature', 'diagnostics', 'state', 'training_role', 'selection', 'numeric_source'))
            d = 1024 if handle == 'TM_LDA' else 320
            c.need(meta['schema'] == 'neural081_numeric_model_v1' and meta['family'] == handle
                   and type(meta['n_train']) is int and meta['n_train'] == n and type(meta['n_features']) is int and meta['n_features'] == d
                   and c.typed_equal(meta['class_ids'], list(c.CLASSES)) and c.typed_equal(meta['configuration'], edge['configuration'])
                   and c.typed_equal(meta['numeric_source'], numeric) and c.typed_equal(meta['training_role'], role_desc)
                   and c.typed_equal(meta['selection'], chosen['result']) and type(meta['temperature']) in (int, float) and meta['temperature'] == 1., 'exact original model metadata/producer join')
            if handle == 'HISTORICAL_BP_LDA': temperature = 1.
            else:
                recipe = next(x for x in select['selected_per_family'] if x['family'] == handle)
                calibration = next(x for x in select['selected_temperatures'] if x['family'] == handle)
                c.need(recipe['configuration_id'] == calibration['configuration_id'] == meta['configuration']['id'], 'same selected train-only recipe')
                temperature = calibration['temperature']
            shapes = {'scaler_mean': [d], 'scaler_scale': [d], **public.parameter_shapes(handle, n)}
            c.exact(meta['state'], shapes); state_descriptors = []
            scaler, parameters = {}, {}
            for name, shape in shapes.items():
                state = meta['state'][name]; c.exact(state, ('array', 'dtype', 'shape')); desc = c.descriptor(state['array'])
                c.need(state['dtype'] == 'float64' and c.typed_equal(state['shape'], shape)
                       and Path(desc['path']).parent == Path(edge['model']['path']).parent and Path(desc['path']).name == name+'.npy', 'original fixed state name/shape')
                state_descriptors.append(desc)
                exposed = {'relative_path': name+'.npy', 'dtype': 'float64', 'shape': shape, 'bytes': desc['bytes'], 'sha256': desc['sha256']}
                (scaler if name.startswith('scaler_') else parameters)[name] = exposed
                mounts.append(_mount(desc, '/models/'+handle+'/'+name+'.npy', True))
            c.need(len(edge['state_artifacts']) == len(state_descriptors)+1
                   and sorted(edge['state_artifacts'], key=lambda x: x['path']) == sorted([edge['model'], *state_descriptors], key=lambda x: x['path']), 'complete exact original model artifact closure')
            model = dict(schema='neural081_candidate_model_v2', handle=handle, family=handle,
                         configuration=meta['configuration'], class_ids=list(c.CLASSES),
                         feature_definition='TM' if handle == 'TM_LDA' else 'BP', scaler=scaler,
                         parameters=parameters, calibration={'temperature': temperature},
                         training_row_tokens_or_null=values if handle == 'RBF_KRR' else None,
                         strongest_family=select['strongest_family'], uniform_probabilities=priors['uniform'], laplace_probabilities=priors['laplace'])
            public.validate_model(model, handle)
            projected = c.publish_json(directory/(handle+'.json'), model, budget)
            mounts.append(_mount(projected, '/models/'+handle+'/model.json', False))
            models.append({'handle': handle, 'public': projected, 'original': edge['model'], 'state_artifacts': state_descriptors, 'producer': edge['closure'], 'result': edge['result']})
        fold = dict(schema='neural081_public_model_fold_v1', generation=generation, view=view, outer=outer, n_train=n,
                    training_role=role_desc, row_tokens=token_row['tokens_descriptor'], selection=chosen['result'],
                    selection_closure=chosen['closure'], numeric_source=numeric, tool_source=tool_source,
                    reference_run=reference_run['descriptor'], models=models, mounts=_mounts(mounts))
        folds.append(_seal(directory, 'BINDING.json', fold, budget))
    return _seal(root, 'MODEL_REGISTRY.json', dict(schema='neural081_public_model_registry_v1', generation=generation,
        reference_run=reference_run['descriptor'], preparation_closure=index['preparation_closure'], folds=folds), budget)


def issue_context(index, issued_context_map_descriptor, issuer_bundle, model_fold, remaining, budget, output_root):
    """Publish one exact public context and private binding, without array reads.

    issuer_bundle is {descriptors, reply} from the concrete trusted broker.project.
    Return {context, context_descriptor, mounts, input_manifest, binding}.
    """
    p.validate_index(index); protected = _protected(index); generation = index['preparation_generation']
    fold = _sealed(model_fold, budget, protected)
    c.exact(fold, ('schema', 'generation', 'view', 'outer', 'n_train', 'training_role', 'row_tokens', 'selection', 'selection_closure', 'numeric_source', 'tool_source', 'reference_run', 'models', 'mounts'))
    c.need(fold['schema'] == 'neural081_public_model_fold_v1' and fold['generation'] == generation, 'same closed model generation')
    context = _read(issued_context_map_descriptor, budget, protected)
    c.exact(context, ('schema', 'generation', 'mode', 'replication', 'view', 'context_alias', 'outer_person', 'canonical_id', 'training_permutation', 'query_window', 'training_role', 'global_labels_required'))
    c.need(context['schema'] == 'neural081_issued_context_map_v1' and context['generation'] == generation and context['mode'] in c.MODES
           and context['replication'] in c.REPS and context['view'] == fold['view'] and context['outer_person'] == fold['outer']
           and c.typed_equal(context['training_role'], fold['training_role']) and context['global_labels_required'] is False, 'same one-query private context/fold')
    alias = c.ident(context['context_alias']); ident = c.ident(context['canonical_id'])
    rows = {r['canonical_id']: r for r in index['rows']}; query = rows.get(ident)
    c.need(query is not None and query['person'] == fold['outer']
           and c.typed_equal(context['query_window'], query['window_descriptor'] if fold['view'] == 'EEG' else None), 'exact one held-person query window')
    training = {i: row for i, row in rows.items() if row['person'] != fold['outer']}
    permutation = context['training_permutation']; c.need(type(permutation) is list and len(permutation) == fold['n_train'] == len(training), 'complete training bijection')
    group_people = {}; aliases = []; inverse = []
    for row in permutation:
        c.exact(row, ('canonical_id', 'row_alias', 'group_alias')); i = c.ident(row['canonical_id']); c.need(i in training, 'permitted training row')
        a, g = c.ident(row['row_alias']), c.ident(row['group_alias']); aliases.append(a); inverse.append(i)
        c.need(g not in group_people or group_people[g] == training[i]['person'], 'group alias never merges people'); group_people[g] = training[i]['person']
    c.need(len(set(inverse)) == len(training) and len(set(aliases)) == len(aliases) and aliases == sorted(aliases)
           and len(group_people) == 9 and len(set(group_people.values())) == 9, 'complete source-issued row/group aliases')
    c.exact(issuer_bundle, ('descriptors', 'reply')); descriptors, reply = issuer_bundle['descriptors'], issuer_bundle['reply']
    c.exact(descriptors, INPUTS)
    c.exact(reply, ('schema', 'ordinal', 'context', 'role', 'generation', 'context_alias', 'mode', 'replication', 'view', 'n_train', 'outputs', 'global_label_opens', 'budget', 'previous_reply'))
    c.integer(reply['ordinal']); c.need(reply['schema'] == 'neural081_projection_reply_v1' and c.typed_equal(reply['context'], issued_context_map_descriptor)
           and c.typed_equal(reply['role'], fold['training_role']) and reply['generation'] == generation and reply['context_alias'] == alias
           and all(reply[k] == context[k] for k in ('mode', 'replication', 'view')) and type(reply['n_train']) is int and reply['n_train'] == len(training)
           and type(reply['global_label_opens']) is int and reply['global_label_opens'] == 0, 'actual current issuer output identity')
    c.exact(reply['outputs'], INPUTS)
    mounts = list(fold['mounts'])
    for name in INPUTS:
        desc = c.descriptor(descriptors[name]); c.exact(reply['outputs'][name], ('bytes', 'sha256'))
        c.need(c.typed_equal(reply['outputs'][name], {k: desc[k] for k in ('bytes', 'sha256')}), 'complete issuer-attested opaque output')
        mounts.append(_mount(desc, '/input/'+name, True))
    remaining = remaining_snapshot(remaining, context['mode'])
    exposed = dict(schema='neural081_candidate_context_v4', task_id=c.TASK, access_policy=p.POLICY,
                   mode=context['mode'], replication=context['replication'], view=context['view'], context_alias=alias,
                   class_ids=list(c.CLASSES), representation=p.REPRESENTATION,
                   query={'path': '/input/query.npy', 'row_alias': alias},
                   training={'eeg_path': '/input/train.npy', 'labels_path': '/input/train_labels.npy', 'rows_path': '/input/train_rows.json', 'shape': [len(training), 64, 512]},
                   models=[{'handle': h, 'path': '/models/'+h+'/model.json'} for h in p.HANDLES],
                   tools={'api_version': 'neural081_tools_v2', 'module': 'reference_tools', 'source_path': '/tools/reference_tools.py', 'source_sha256': fold['tool_source']['sha256']}, remaining=remaining)
    c.exact(exposed, CONTEXT_KEYS)
    root = c.new_directory(output_root, budget); public_desc = c.publish_json(root/'CONTEXT.json', exposed, budget)
    mounts.append(_mount(public_desc, '/input/context.json', False)); _mounts(mounts)
    manifest = [dict(row['source'], path=row['target']) for row in mounts]
    binding = _seal(root, 'BINDING.json', dict(schema='neural081_projection_binding_v4', access_policy=p.POLICY,
        generation=generation, context_alias=alias, source={'public_tools': fold['tool_source'], 'numeric': fold['numeric_source']},
        support_index_pin=c.pin(c.encoded(index)), preparation_closure=index['preparation_closure'],
        protected_support=index['protected_support_descriptor'], protected_assessment=index['protected_assessment_descriptor'],
        issued_context=issued_context_map_descriptor, alias_inverse=issued_context_map_descriptor,
        frozen_model_fold=model_fold['descriptor'], public_context=public_desc, issuer_reply=reply,
        issued_arrays=descriptors, mounts=mounts, input_manifest=manifest, clock=budget.snapshot(),
        complete_support_bijection=True, query_count=1, model_bodies_copied=False,
        controller_array_or_label_body_reads=0), budget)
    return {'context': exposed, 'context_descriptor': public_desc, 'mounts': mounts, 'input_manifest': manifest, 'binding': binding}
