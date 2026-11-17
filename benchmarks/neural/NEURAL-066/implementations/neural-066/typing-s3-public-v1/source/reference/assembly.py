"""Pure captured-metadata assembly of exact reference input mount bindings.

No filesystem calls, numerical array reads, process calls or source rewrites.
The owner independently authenticates capture custody; this module joins the
captured raw JSON bytes to its output inventory and selects only role inputs.
"""
import copy, hashlib, json, re
from pathlib import PurePosixPath
from . import core
from core import CONDITIONS, R2_ARMS

def relative(path):
    core.need(type(path) is str and path and (not path.startswith('/')) and ('\\' not in path) and ('\x00' not in path) and all((p not in ('', '.', '..') for p in path.split('/'))), 'safe original relative capture path')
    return path

def absolute(path):
    core.need(type(path) is str and path.startswith('/') and ('\\' not in path) and ('\x00' not in path) and all((p not in ('.', '..') for p in path.split('/'))), 'exact absolute capture root/source')
    return path

def bare(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}

def pin(value):
    core.need(type(value) is dict and set(value) == {'bytes', 'sha256'} and (type(value['bytes']) is int) and (value['bytes'] > 0) and (type(value['sha256']) is str) and re.fullmatch('[0-9a-f]{64}', value['sha256']), 'exact positive captured file pin')
    return value

def parse(raw, cap):
    core.need(type(raw) is bytes and 0 < len(raw) <= cap, 'bounded captured JSON body')

    def pairs(rows):
        result = {}
        for key, value in rows:
            core.need(key not in result, 'duplicate captured metadata key')
            result[key] = value
        return result
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=lambda _: core.need(False, 'nonfinite captured metadata'))

def capture(value):
    core.need(type(value) is dict and set(value) == {'capture_root', 'output_files', 'metadata'}, 'exact independently captured phase metadata operand')
    absolute(value['capture_root'])
    core.need(type(value['output_files']) is dict and type(value['metadata']) is dict, 'captured output inventory and raw metadata')
    for path, item in value['output_files'].items():
        relative(path)
        pin(item)
    core.need(set(value['metadata']) <= set(value['output_files']), 'metadata must belong to captured output inventory')
    return value

def document(value, path, cap):
    relative(path)
    core.need(path in value['metadata'] and bare(value['metadata'][path]) == pin(value['output_files'][path]), 'exact original raw metadata/capture join')
    return parse(value['metadata'][path], cap)

def array_descriptor(value):
    core.need(type(value) is dict and set(value) == {'path', 'bytes', 'sha256', 'shape', 'dtype'}, 'exact original inert array descriptor')
    relative(value['path'])
    pin({k: value[k] for k in ('bytes', 'sha256')})
    core.need(type(value['shape']) is list and all((type(v) is int and v >= 0 for v in value['shape'])) and (value['dtype'] in ('<f4', '<f8', '<i8', '|u1', '|i1')), 'typed primitive array extent')
    return value

def build_request(action, context, case_capture, environment_bundle, limits, device, *, grid_index=None, cell=None, model_capture=None, inner_captures=None):
    core.need(action in {'r2_inner', 'r2_final', 'r2_infer', 'r0fit', 'r0infer', 'r1count', 'r1infer'}, 'fixed reference action')
    core.need(type(context) is dict and set(context) == {'case', 'modality', 'condition', 'generation'} and (context['modality'] in ('MEG', 'EEG')) and (context['condition'] in CONDITIONS) and all((type(context[k]) is str and context[k] for k in ('case', 'generation'))), 'exact case identity')
    core.need(type(limits) is dict and set(limits) == {'read_bytes', 'write_bytes', 'array_bytes', 'json_bytes'} and all((type(v) is int and v > 0 for v in limits.values())) and (device == 'cpu'), 'finite exact future worker policy')
    fit = action in ('r2_inner', 'r2_final', 'r0fit', 'r1count')
    is_r2 = action.startswith('r2_')
    core.need(not is_r2 or context['condition'] in R2_ARMS, 'R2 supports exactly four neural arms; no fabricated spatial adapter')
    core.need(not action.startswith('r1') or context['condition'] == 'NEURAL', 'One independent case-local count state uses canonical neural training labels only')
    if not fit:
        core.need(model_capture is not None and inner_captures is None and (grid_index is None) and (cell is None), 'only sealed final model at inference')
    else:
        core.need(model_capture is None, 'no imported preliminary state in fresh fitting')
    if action == 'r2_inner':
        core.need(type(grid_index) is int and grid_index in (0, 1) and (type(cell) is list) and (len(cell) == 2) and all((type(v) is int and v in range(3) for v in cell)) and (inner_captures is None), 'exact one inner grid/cell')
    elif action == 'r2_final':
        core.need(grid_index is None and cell is None and (type(inner_captures) is list) and (len(inner_captures) == 18), 'all18 inner outputs required for fresh final fit')
    else:
        core.need(grid_index is None and cell is None and (inner_captures is None), 'no hidden selection operands')
    case_capture = capture(case_capture)
    prefix = context['condition']
    bindings = {}
    inputs = {}
    recipe = {}

    def bind_record(destination, source, record):
        relative(destination)
        absolute(source)
        pin(record)
        core.need(destination not in bindings, 'one exact file per input namespace; no overlays')
        bindings[destination] = {'source_path': source, **record}
        return {'path': destination, **record}

    def bind(cap, source, destination, expected=None):
        relative(source)
        core.need(source in cap['output_files'], 'member present in independently captured phase')
        record = pin(cap['output_files'][source])
        if expected is not None:
            core.need(record == {k: expected[k] for k in ('bytes', 'sha256')}, 'declared original member matches capture identity')
        return bind_record(destination, str(PurePosixPath(cap['capture_root']) / source), record)

    def bind_array(cap, source, destination, desc):
        array_descriptor(desc)
        result = bind(cap, source, destination, desc)
        core.need(desc['bytes'] <= limits['array_bytes'], 'full array fits original bound; no subset replacement')
        return {**result, 'shape': desc['shape'], 'dtype': desc['dtype']}
    full = document(case_capture, prefix + '/VIEW.json', limits['json_bytes'])
    core.need(full.get('format') == 'typing_view_v3' and full.get('task') == 'NEURAL-066' and (full.get('mode') == 'reference') and all((full[k] == context[k] for k in context)), 'same original independent-reference view/context')
    filename = 'FIT_VIEW.json' if fit else 'INFER_VIEW.json'
    projected = document(case_capture, prefix + '/' + filename, limits['json_bytes'])
    expected = {k: full[k] for k in ('case', 'generation', 'condition', 'modality', 'channels', 'feature_dimensions', 'samples_per_key', 'feature_spec', 'support_commitment', 'source_contract_pin', 'projection_pin', 'language_policy_pin')}
    expected.update(format='typing_reference_view_v1', task='NEURAL-066', purpose='fit' if fit else 'infer')
    if not fit:
        expected['queries'] = full['queries']
    core.need(projected == expected, 'exact purpose projection; no query metadata in fit')
    inputs['view'] = bind(case_capture, prefix + '/' + filename, 'case/' + filename)
    inputs['geometry'] = bind(case_capture, prefix + '/GEOMETRY.json', 'case/GEOMETRY.json', full['geometry'])
    if fit:
        inputs['layout'] = bind(case_capture, prefix + '/TRAIN_LAYOUT.json', 'case/TRAIN_LAYOUT.json', full['layout'])
        train_name = 'UNSHUFFLED_TRAIN.npy' if action == 'r2_inner' and context['condition'] == 'SHUFFLE' else 'train.npy'
        desc = array_descriptor(full['unshuffled_train'] if train_name != 'train.npy' else full['arrays']['train.npy'])
        core.need(desc['path'] == train_name, 'Exact selected original/unshuffled training role')
        inputs['train'] = bind_array(case_capture, prefix + '/' + train_name, 'case/' + train_name, desc)
        if is_r2:
            plan = document(case_capture, prefix + '/REFERENCE_PLAN.json', limits['json_bytes'])
            core.need(type(plan) is dict and set(plan) == {'schema', 'case', 'modality', 'condition', 'person_buckets', 'template_buckets', 'assignment_provenance'} and (plan['schema'] == 'neural066_reference_plan_v1') and all((plan[k] == context[k] for k in ('case', 'modality', 'condition'))), 'original reference plan/context; no extra private metadata')
            pin(plan['assignment_provenance'])
            recipe = {'plan': plan}
            if context['condition'] == 'SHUFFLE':
                inputs['shuffle_groups'] = bind(case_capture, prefix + '/SHUFFLE_GROUPS.json', 'case/SHUFFLE_GROUPS.json', full['private_shuffle_groups'])
                recipe['unshuffled_source'] = {k: full['unshuffled_train'][k] for k in ('bytes', 'sha256')}
            if action == 'r2_inner':
                recipe.update(grid_index=grid_index, cell=cell)
    elif action != 'r1infer':
        desc = array_descriptor(full['arrays']['query.npy'])
        core.need(desc['path'] == 'query.npy', 'original query array name')
        inputs['query'] = bind_array(case_capture, prefix + '/query.npy', 'case/query.npy', desc)
    env = environment_bundle
    core.need(type(env) is dict and set(env) == {'descriptor', 'bindings', 'metadata'} and (type(env['bindings']) is dict) and (type(env['metadata']) is dict), 'exact environment capture bundle')
    ed = env['descriptor']
    core.need(type(ed) is dict and set(ed) == {'path', 'bytes', 'sha256'}, 'environment descriptor')

    def env_document(d):
        relative(d['path'])
        pin({k: d[k] for k in ('bytes', 'sha256')})
        record = env['bindings'][d['path']]
        core.need(type(record) is dict and set(record) == {'source_path', 'bytes', 'sha256'} and ({k: record[k] for k in ('bytes', 'sha256')} == {k: d[k] for k in ('bytes', 'sha256')}) and (bare(env['metadata'][d['path']]) == {k: d[k] for k in ('bytes', 'sha256')}), 'captured original environment/proof bytes')
        value = parse(env['metadata'][d['path']], limits['json_bytes'])
        bind_record(d['path'], record['source_path'], {k: d[k] for k in ('bytes', 'sha256')})
        return value
    envdoc = env_document(ed)
    core.need(envdoc.get('schema') == 'neural066_reference_environment_v1', 'reference environment schema')
    env_document(envdoc['independent_qualification_receipt'])
    inputs['environment'] = dict(ed)
    if not fit:
        cap = capture(model_capture)
        result = document(cap, 'RESULT.json', limits['json_bytes'])
        doc = document(cap, 'MODEL.json', limits['json_bytes'])
        expected_action = {'r2_infer': 'r2_final', 'r0infer': 'r0fit', 'r1infer': 'r1count'}[action]
        kind = {'r2_infer': 'R2', 'r0infer': 'R0', 'r1infer': 'R1'}[action]
        core.need(result.get('schema') == 'neural066_reference_result_v1' and result.get('status') == 'complete' and (result.get('action') == expected_action) and (result.get('context') == context), 'complete original fresh final model phase, not inner/preliminary weights')
        core.need(doc.get('schema') == 'neural066_inert_reference_model_v1' and doc.get('context') == context and (doc.get('kind') == kind) and (doc.get('environment') == {k: ed[k] for k in ('bytes', 'sha256')}), 'exact independent model/environment identity')
        core.need(result['model'] == {'path': 'MODEL.json', **cap['output_files']['MODEL.json']}, 'original result seals this exact model body')
        core.need(doc.get('fit_provenance') == result.get('fit_provenance') and type(doc.get('fit_provenance')) is dict, 'Actual successful own FIT result/model provenance join')
        provenance = doc['fit_provenance']
        core.need(all((provenance[k] == full[k] for k in ('feature_spec', 'support_commitment', 'source_contract_pin', 'projection_pin', 'language_policy_pin'))), 'Exact fit/infer support, typed transform and source ancestry')
        inputs['model'] = bind(cap, 'MODEL.json', 'model/MODEL.json', result['model'])
        core.need(type(doc['arrays']) is dict and doc['arrays'], 'complete typed model state')
        used = set()
        for desc in doc['arrays'].values():
            array_descriptor(desc)
            core.need(desc['path'].startswith('arrays/') and desc['path'] not in used, 'unique exact inert model member')
            used.add(desc['path'])
            bind_array(cap, desc['path'], 'model/' + desc['path'], desc)
    if action == 'r2_final':
        indexed = {}
        for value in inner_captures:
            cap = capture(value)
            doc = document(cap, 'RESULT.json', limits['json_bytes'])
            core.need(doc.get('schema') == 'neural066_reference_result_v1' and doc.get('status') == 'complete' and (doc.get('action') == 'r2_inner') and (doc.get('context') == context), 'every required captured inner fit complete')
            g = doc['grid_index']
            c = doc['cell']
            core.need(type(g) is int and g in (0, 1) and (type(c) is list) and (len(c) == 2) and all((type(v) is int and v in range(3) for v in c)), 'exact grid/cell output')
            key = (g, *c)
            core.need(key not in indexed, 'unique inner output')
            indexed[key] = (cap, doc)
        core.need(set(indexed) == {(g, p, t) for g in (0, 1) for p, t in core.CELLS}, 'complete full18 grid/cell inventory')
        wrappers = []
        for i, key in enumerate(sorted(indexed)):
            cap, doc = indexed[key]
            namespace = f'inner{i:02d}'
            rd = bind(cap, 'RESULT.json', namespace + '/RESULT.json')
            desc = array_descriptor(doc['validation'])
            core.need(desc['path'] == 'VALIDATION.npy', 'literal inner validation output')
            pd = bind_array(cap, 'VALIDATION.npy', namespace + '/VALIDATION.npy', desc)
            wrappers.append({'result': rd, 'probabilities': pd})
        inputs['inner_results'] = wrappers
    core.need(sum((d['bytes'] for d in bindings.values())) <= limits['read_bytes'], 'full selected input binding reservation before mount')
    forbidden = ('ASSIGNMENT_PRIVATE.json', 'REFERENCE_PLAN.json', 'VIEW.json', 'RESULT.json')
    for path in bindings:
        core.need(not (path.startswith('case/') and path.split('/')[-1] in forbidden), 'no source-private joins or full case metadata in worker realm')
        if fit:
            core.need(path != 'case/query.npy' and (not path.startswith('model/')), 'fresh fit has no query array or prior fitted model')
        else:
            core.need(path not in ('case/train.npy', 'case/TRAIN_LAYOUT.json'), 'inference has no training data/layout')
    request = {'schema': 'neural066_reference_request_v1', 'action': action, 'context': context, 'inputs': inputs, 'recipe': recipe, 'limits': limits, 'device': device}
    return (copy.deepcopy(request), copy.deepcopy(bindings))
