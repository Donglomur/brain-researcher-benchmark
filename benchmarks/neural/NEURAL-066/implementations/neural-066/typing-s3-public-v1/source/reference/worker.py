"""Concrete isolated reference actions with inert model publication.

The outer controller supplies authenticated source/image/input mounts and its
original deadline. This worker enforces its explicit logical I/O allowance;
it does not claim physical I/O, RSS, process custody, or scientific readiness.
"""
import failures
import hashlib, json, math, os
from pathlib import Path
from . import core, model, numeric, shuffle
from core import CONDITIONS, R2_ARMS
from features import validate as validate_features
ACTIONS = {'r2_inner', 'r2_final', 'r2_infer', 'r0fit', 'r0infer', 'r1count', 'r1infer'}

def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()

class IO:

    def __init__(self, inputroot, outputroot, limits):
        import safe_io
        self.api = safe_io
        self.input = Path(inputroot)
        self.output = Path(outputroot)
        self.limits = limits
        self.read_bytes = 0
        self.write_bytes = 0
        self.capture_observations = []
        core.need(type(limits) is dict and set(limits) == {'read_bytes', 'write_bytes', 'array_bytes', 'json_bytes'} and all((type(v) is int and v > 0 for v in limits.values())), 'explicit finite logical I/O caps')

    def reserve_read(self, d, cap):
        core.need(type(d) is dict and type(d.get('bytes')) is int and (0 < d['bytes'] <= cap), 'bounded descriptor extent')
        core.need(self.read_bytes + d['bytes'] <= self.limits['read_bytes'], 'original reference read allowance')
        self.read_bytes += d['bytes']

    def reserve_extent(self, n):
        core.need(type(n) is int and n >= 0 and self.read_bytes + n <= self.limits['read_bytes'], 'original reference read allowance before body effects')
        self.read_bytes += n

    def capture(self, path, cap, expected=None):
        observation = {}
        self.capture_observations.append(observation)
        return self.api.capture(path, cap, expected, reserve=self.reserve_extent, observation=observation)

    def source(self,path,expected=None):
        cap=self.limits['json_bytes'] if expected is None else max(1, expected['bytes'])
        return self.capture(path,cap,expected)

    def document(self, d):
        core.need(set(d) == {'path', 'bytes', 'sha256'}, 'exact JSON descriptor')
        return self.api.strict(self.capture(self.api.child(self.input, d['path']), self.limits['json_bytes'], {k: d[k] for k in ('bytes', 'sha256')}))

    def array(self, d):
        observation = {}
        self.capture_observations.append(observation)
        return self.api.array(self.input, d, self.limits['array_bytes'], reserve=self.reserve_extent, observation=observation)

    def put(self, name, body):
        core.need(type(body) is bytes and self.write_bytes + len(body) <= self.limits['write_bytes'], 'original reference write allowance')
        self.write_bytes += len(body)
        path = self.api.child(self.output, name)
        self.api.durable_new(path, body)
        return {'path': name, 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}

    def json(self, name, obj):
        raw = encoded(obj)
        core.need(len(raw) <= self.limits['json_bytes'], 'bounded JSON result')
        return self.put(name, raw)

    def array_out(self, name, value):
        import numpy as np
        value = np.asarray(value)
        if not value.flags.c_contiguous:
            value = np.ascontiguousarray(value)
        core.need(value.dtype.kind in 'fiu' and value.dtype.itemsize in (4, 8) and np.isfinite(value).all(), 'finite primitive model/prediction array')
        reservation = value.nbytes + 1024
        core.need(reservation <= self.limits['array_bytes'] and self.write_bytes + reservation <= self.limits['write_bytes'], 'prospective full NPY write bound')
        self.write_bytes += reservation
        desc = self.api.write_array(self.api.child(self.output, name), value, self.limits['array_bytes'])
        core.need(desc['bytes'] <= reservation, 'reserved NPY extent')
        return {**desc, 'path': name}

def prefixed(descriptor, parent):
    return {**descriptor, 'path': (Path(parent) / descriptor['path']).as_posix()}

def admit_environment(io, descriptor):
    """Only an independently qualified, root-bound actual image may execute.

    This validates captured proof joins; it does not manufacture an independent
    observation or claim that a hash alone certifies a complete environment.
    """
    raw = io.source(Path(__file__).parent / 'SOURCE_LOCK.json')
    lock = json.loads(raw)
    source = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    doc = io.document(descriptor)
    fields = {'schema', 'qualification', 'source_lock', 'image_digest', 'wheel_artifacts', 'complete_dependency_lock', 'independent_qualification_receipt'}
    core.need(type(doc) is dict and set(doc) == fields and (doc['schema'] == 'neural066_reference_environment_v1') and (doc['qualification'] == 'qualified'), 'actual root-bound qualified reference environment')
    core.need(doc['source_lock'] == source and doc['wheel_artifacts'] == lock['wheel_artifacts'], 'exact full source/wheel identity')
    digest = doc['image_digest']
    core.need(type(digest) is str and digest.startswith('sha256:') and (len(digest) == 71) and all((c in '0123456789abcdef' for c in digest[7:])), 'immutable actual image digest')
    deps = doc['complete_dependency_lock']
    core.need(type(deps) is list and deps, 'complete declared transitive/native artifact lock')
    indexed = {}
    for item in deps:
        core.need(type(item) is dict and set(item) == {'name', 'version', 'artifact'} and (type(item['name']) is str) and item['name'] and (type(item['version']) is str) and item['version'] and (item['name'] not in indexed), 'unique typed dependency artifact')
        pin = item['artifact']
        core.need(type(pin) is dict and set(pin) == {'bytes', 'sha256'} and (type(pin['bytes']) is int) and (pin['bytes'] > 0) and (type(pin['sha256']) is str) and (len(pin['sha256']) == 64) and all((c in '0123456789abcdef' for c in pin['sha256'])), 'exact artifact identity')
        indexed[item['name']] = item
    core.need(all((name in indexed and indexed[name]['version'] == version for name, version in lock['versions'].items())), 'all exact numerical dependencies locked')
    core.need(all((indexed[name]['artifact'] == artifact for name, artifact in lock['wheel_artifacts'].items())), 'complete dependency lock agrees with every exact fullwheel identity')
    receipt = io.document(doc['independent_qualification_receipt'])
    core.need(type(receipt) is dict and receipt.get('schema') == 'neural066_independent_reference_environment_qualification_v1' and (receipt.get('qualified') is True) and (receipt.get('actual_image_digest') == digest) and (receipt.get('source_lock') == source) and (receipt.get('wheel_artifacts') == doc['wheel_artifacts']) and (receipt.get('complete_dependency_lock') == deps) and (receipt.get('native_and_transitive_closure_verified') is True), 'authentic independently admitted environment proof join')
    io.source_lock=lock
    model.SOURCE_IO=io
    io.environment_pin = {k: descriptor[k] for k in ('bytes', 'sha256')}

def model_write(io, context, kind, config, arrays):
    reserve = sum((a.nbytes + 1024 for a in arrays.values())) + 8192 + 1024 * len(arrays)
    core.need(io.write_bytes + reserve <= io.limits['write_bytes'], 'complete inert model reservation')
    folder = io.api.child(io.output, 'arrays')
    folder.mkdir(mode=448)
    fd = os.open(io.output, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    owner=failures.FailureOwner()
    owner.attempt('model_directory_fsync',os.fsync,fd)
    owner.attempt('model_directory_close',os.close,fd)
    owner.raise_first()
    descriptors = {}
    for i, (name, value) in enumerate(sorted(arrays.items())):
        descriptors[name] = io.array_out(f'arrays/{i:04d}.npy', value)
    source = io.source(Path(__file__).parent / 'SOURCE_LOCK.json')
    document = {'schema': 'neural066_inert_reference_model_v1', 'context': context, 'kind': kind, 'config': config, 'arrays': descriptors, 'source_lock': {'bytes': len(source), 'sha256': hashlib.sha256(source).hexdigest()}, 'environment': io.environment_pin, 'fit_provenance': io.fit_provenance, 'scientific_qualification': False}
    return io.json('MODEL.json', document)

def model_read(io, descriptor, context, kind):
    doc = io.document(descriptor)
    core.need(type(doc) is dict and set(doc) == {'schema', 'context', 'kind', 'config', 'arrays', 'source_lock', 'environment', 'fit_provenance', 'scientific_qualification'} and (doc['schema'] == 'neural066_inert_reference_model_v1') and (doc['context'] == context) and (doc['kind'] == kind) and (doc['environment'] == io.environment_pin) and (doc['scientific_qualification'] is False), 'exact independent model context/type/environment')
    raw = io.source(Path(__file__).parent / 'SOURCE_LOCK.json')
    core.need(doc['source_lock'] == {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}, 'exact reference source lock')
    core.need(type(doc['fit_provenance']) is dict and all((doc['fit_provenance'][k] == io.current_view[k] for k in ('feature_spec', 'support_commitment', 'source_contract_pin', 'projection_pin', 'language_policy_pin'))), 'Exact current fit/infer source and support provenance before model/query bodies')
    core.need(type(doc['arrays']) is dict, 'explicit inert model arrays')
    arrays = {k: io.array(prefixed(v, Path(descriptor['path']).parent)) for k, v in doc['arrays'].items()}
    return (doc['config'], arrays)

def result(io, doc):
    """Publish completion last, with its own exact logical publication cost."""
    # This channel contains source-owned metadata, never captured input bytes.
    # Preserve the exact ordered safe_io observations on both normal returns.
    io.read_custody = {
        'schema': 'neural066_reference_read_custody_v1',
        'observations': [dict(value) for value in io.capture_observations],
        'logical_read_reservation': io.read_bytes,
        'acknowledged_prefix_bytes': sum(value.get('acknowledged_bytes', 0) for value in io.capture_observations),
        'unknown_pending_upper': sum(value.get('unknown_pending_upper', 0) for value in io.capture_observations),
        'raw_input_exported': False,
        'physical_IO_or_RSS_certified': False,
    }
    doc = {**doc, 'read_custody': io.read_custody}
    doc = {**doc, 'costs': {'read_bytes': io.read_bytes, 'write_bytes': 0, 'physical_IO_or_RSS_certified': False}}
    prior = io.write_bytes
    last = None
    for _ in range(8):
        raw = encoded(doc)
        total = prior + len(raw)
        if total == last:
            break
        doc['costs']['write_bytes'] = total
        last = total
    else:
        raise ValueError('bounded result cost fixed point')
    core.need(doc['costs']['write_bytes'] == prior + len(raw), 'complete result cost')
    core.need(len(raw) <= io.limits['json_bytes'], 'Complete result and private diagnostic channel fit the original JSON cap')
    io.put('RESULT.json', raw)
    return doc

def run(request, inputroot, outputroot):
    core.need(type(request) is dict and set(request) == {'schema', 'action', 'context', 'inputs', 'recipe', 'limits', 'device'} and (request['schema'] == 'neural066_reference_request_v1') and (request['action'] in ACTIONS), 'exact reference action request')
    core.need(request['device']=='cpu','Exact source CPU-only transport; no unqualified CUDA')
    context = request['context']
    action = request['action']
    inputs = request['inputs']
    recipe = request['recipe']
    core.need(type(context) is dict and set(context) == {'case', 'modality', 'condition', 'generation'} and (context['modality'] in ('MEG', 'EEG')) and (context['condition'] in CONDITIONS) and all((type(context[k]) is str and context[k] for k in ('case', 'generation'))), 'exact private reference context')
    core.need(type(inputs) is dict and type(recipe) is dict, 'explicit input roles/recipe')
    io = IO(inputroot, outputroot, request['limits'])
    core.need(io.output.is_dir() and (not any(io.output.iterdir())) and (not any((p.is_symlink() for p in (io.output, *io.output.parents)))), 'fresh isolated output namespace')
    original_failure=None
    base = {'schema': 'neural066_reference_result_v1', 'status': 'incomplete', 'action': action, 'context': context, 'scientific_qualification': False}
    try:
        fit = action in ('r2_inner', 'r2_final', 'r0fit', 'r1count')
        expected = {'view', 'layout', 'geometry', 'train'} if fit else {'view', 'geometry', 'model'} | ({'query'} if action != 'r1infer' else set())
        expected.add('environment')
        if action == 'r2_final':
            expected.add('inner_results')
        if action in ('r2_inner', 'r2_final') and context['condition'] == 'SHUFFLE':
            expected.add('shuffle_groups')
        core.need(set(inputs) == expected, 'exact train/inference input separation; no unrelated state')
        admit_environment(io, inputs['environment'])
        view = io.document(inputs['view'])
        geom = io.document(inputs['geometry'])
        channels = 306 if context['modality'] == 'MEG' else 61
        view_keys = {'format', 'task', 'purpose', 'case', 'generation', 'condition', 'modality', 'channels', 'feature_dimensions', 'samples_per_key', 'feature_spec', 'support_commitment', 'source_contract_pin', 'projection_pin', 'language_policy_pin'} | (set() if fit else {'queries'})
        core.need(type(view) is dict and set(view) == view_keys and (view['format'] == 'typing_reference_view_v1') and (view['task'] == 'NEURAL-066') and (view['purpose'] == ('fit' if fit else 'infer')), 'Exact purpose view and no query metadata in fitting')
        core.need(all((view[k] == context[k] for k in context)), 'Current exact case/arm/generation/modality')
        dimensions = validate_features(view['feature_spec'], context['condition'], context['modality'])
        core.need(view['feature_dimensions'] == dimensions and view['samples_per_key'] == view['feature_spec']['samples_per_key'] and (view['channels'] == geom['channel_names']), 'Exact full typed feature/schema order')
        io.current_view = view
        positions = None
        if action.startswith('r2_'):
            core.need(context['condition'] in R2_ARMS, 'R2 EOG/TIMING structurally unsupported; no fake geometry')
            positions = model.geometry(geom, channels, context['modality'])
        if fit:
            layout_doc = io.document(inputs['layout'])
            core.need(type(layout_doc) is dict and set(layout_doc) == {'schema', 'sentences'} and (layout_doc['schema'] == 'neural066_train_layout_v1'), 'Exact opaque training layout')
            rows = layout_doc['sentences']
            train = io.array(inputs['train'])
            flat, labels, weights = numeric.training_flat(train, rows, dimensions)
            features = flat.reshape(len(flat), channels, 25) if action.startswith('r2_') else flat
            io.fit_provenance = {k: view[k] for k in ('feature_spec', 'support_commitment', 'source_contract_pin', 'projection_pin', 'language_policy_pin')}
            io.fit_provenance.update(context=context, inputs=inputs, recipe=recipe, environment=io.environment_pin, final_state_is_fresh=True, query_or_candidate_state_consumed=False)
            base['fit_provenance'] = io.fit_provenance
        private_groups = None
        if 'shuffle_groups' in inputs:
            document = io.document(inputs['shuffle_groups'])
            core.need(set(document) == {'schema', 'groups'} and document['schema'] == 'neural066_private_shuffle_groups_v1', 'Exact operator-private shuffle membership')
            private_groups = document['groups']
        if action == 'r2_inner':
            core.need(set(recipe) == ({'plan', 'grid_index', 'cell', 'unshuffled_source'} if context['condition'] == 'SHUFFLE' else {'plan', 'grid_index', 'cell'}) and type(recipe['cell']) is list and (len(recipe['cell']) == 2) and all((type(v) is int and v in range(3) for v in recipe['cell'])), 'fixed exact inner recipe')
            cell = core.cells(rows, recipe['plan'], context)[tuple(recipe['cell'])]
            core.need(cell['status'] == 'complete', 'required inner cell empty; no skip or rebalance')
            if context['condition'] == 'SHUFFLE':
                core.need({k: inputs['train'][k] for k in ('bytes', 'sha256')} == recipe['unshuffled_source'], 'Inner fit mounts only exact original unshuffled training vectors')
                perm = shuffle.mapping(rows, cell['fit'], private_groups, context, recipe['grid_index'], recipe['cell'])
                perm['source_vectors'] = recipe['unshuffled_source']
                base['inner_shuffle'] = perm
                io.fit_provenance['inner_shuffle'] = perm
                features = shuffle.apply(features, perm)
            config, arrays, fit_result = model.fit(features, labels, rows, cell['fit'], cell['validation'], positions, recipe['grid_index'], request['device'])
            base.update(grid_index=recipe['grid_index'], cell=recipe['cell'], fit_sentences=cell['fit'], validation_sentences=cell['validation'], best_epoch=fit_result['best_epoch'], history=fit_result['history'])
            base['model'] = model_write(io, context, 'R2', config, arrays)
            base['validation'] = io.array_out('VALIDATION.npy', fit_result['validation_probabilities'])
        elif action == 'r2_final':
            core.need(set(recipe) == ({'plan', 'unshuffled_source'} if context['condition'] == 'SHUFFLE' else {'plan'}) and type(inputs['inner_results']) is list and (len(inputs['inner_results']) == 18), 'complete final selection request')
            operand = []
            for wrapper in inputs['inner_results']:
                core.need(type(wrapper) is dict and set(wrapper) == {'result', 'probabilities'}, 'exact inner result wrapper')
                r = io.document(wrapper['result'])
                core.need(wrapper['probabilities'] == prefixed(r['validation'], Path(wrapper['result']['path']).parent), 'exact original validation capture under mounted namespace')
                if context['condition'] == 'SHUFFLE':
                    chosen = core.cells(rows, recipe['plan'], context)[tuple(r['cell'])]
                    perm = shuffle.mapping(rows, chosen['fit'], private_groups, context, r['grid_index'], r['cell'])
                    perm['source_vectors'] = recipe['unshuffled_source']
                    core.need(r.get('inner_shuffle') == perm and r['fit_provenance'].get('inner_shuffle') == perm, 'Exact all18 original fit-local source/ordinal joins')
                core.need(all((r['fit_provenance'][k] == view[k] for k in ('feature_spec', 'support_commitment', 'source_contract_pin', 'projection_pin', 'language_policy_pin'))), 'All inner fits share exact outer support/source/arm ancestry')
                prob = io.array(wrapper['probabilities'])
                operand.append({'result': r, 'probabilities': prob.tolist()})
            selection = core.choose_oof(rows, labels, recipe['plan'], context, operand)
            config, arrays, fit_result = model.fit(features, labels, rows, [r['id'] for r in rows], None, positions, selection['selected_grid'], request['device'], selection['final_epochs'])
            base.update(selection=selection, history=fit_result['history'], best_epoch=fit_result['best_epoch'], fit_sentences=[r['id'] for r in rows], fresh_initialization=True)
            base['model'] = model_write(io, context, 'R2', config, arrays)
        elif action == 'r0fit':
            core.need(recipe == {} and context['condition'] in CONDITIONS, 'Independent R0 for every selected arm')
            model.environment()
            config, arrays = numeric.fit_r0(train, rows, dimensions)
            base['model'] = model_write(io, context, 'R0', config, arrays)
        elif action == 'r1count':
            core.need(recipe == {} and context['condition'] == 'NEURAL', 'one R1 private count build per case')
            counts = core.bigram_count([core.truth_by_sentence([r], labels)[r['id']] for r in rows])
            import numpy as np
            arrays = {k: np.asarray(v, dtype='int64') for k, v in counts.items()}
            base['model'] = model_write(io, context, 'R1', {'kind': 'R1', 'training_sentences': len(rows)}, arrays)
            base['language_state'] = io.json('LANGUAGE_STATE.json', {'schema': 'neural066_training_language_state_v1', 'context': context, 'fit_provenance': io.fit_provenance, 'model': base['model'], 'counts': counts})
        else:
            core.need(recipe == {}, 'fixed sealed inference recipe')
            queries = core.layout(view['queries'], sum((r['n_keys'] for r in view['queries'])), False)
            kind = {'r2_infer': 'R2', 'r0infer': 'R0', 'r1infer': 'R1'}[action]
            if kind == 'R1':
                core.need(context['condition'] == 'NEURAL', 'Canonical case-only independent counts')
            config, arrays = model_read(io, inputs['model'], context, kind)
            if kind == 'R1':
                core.need(set(arrays) == {'starts', 'transition'}, 'complete R1 count arrays')
                counts = {k: v.tolist() for k, v in arrays.items()}
                flat = []
                for r in queries:
                    for target in core.viterbi_length(r['n_keys'], counts):
                        flat.append([float(i == target) for i in range(29)])
            else:
                import numpy as np
                x = io.array(inputs['query'])
                core.need(x.dtype == np.dtype('<f4') and x.shape == (sum((r['n_keys'] for r in queries)), dimensions) and x.flags.c_contiguous and np.isfinite(x).all(), 'complete finite query extent')
                if kind == 'R0':
                    model.environment()
                    flat = numeric.predict_r0(config, arrays, x).tolist()
                else:
                    native, norm = model.restore(config, arrays, request['device'])
                    import torch
                    pos = torch.as_tensor(positions, dtype=torch.float32, device=request['device'])
                    flat = model.predict(native, x.reshape(len(x), channels, 25), queries, [r['id'] for r in queries], norm, pos, request['device']).tolist()
            core.probabilities(flat, sum((r['n_keys'] for r in queries)))
            sentences = [{'id': r['id'], 'p': flat[r['begin']:r['begin'] + r['n_keys']]} for r in queries]
            prediction = {'format': 'typing_predictions_v1', 'task': 'NEURAL-066', 'generation': context['generation'], 'case': context['case'], 'arm': context['condition'], 'sentences': sentences}
            base['predictions'] = io.json('PREDICTIONS.json', prediction)
        base['status'] = 'complete'
    except Exception as error:
        failures.hold(error, 'caught')
        original_failure=failures.hold(error,'reference_action')
        base['status'] = 'incomplete'
        base['error'] = failures.projection(error)
        if failures.evidence(error,'fit_failure') is not None:
            base.update(failures.evidence(error,'fit_failure'))
    try:
        return result(io,base)
    except BaseException as publication:
        if hasattr(io, 'read_custody'):
            failures.remember(publication, 'reference_read_custody', io.read_custody)
        if original_failure is not None:
            if hasattr(io, 'read_custody'):
                original_failure.attach('reference_read_custody', io.read_custody)
            original_failure.hold(publication,'reference_result_publication')
            original_failure.raise_first()
        raise
if __name__ == '__main__':
    import argparse, safe_io
    parser = argparse.ArgumentParser()
    parser.add_argument('--request', required=True)
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    request = safe_io.strict(safe_io.capture(Path(args.request), 1048576))
    value = run(request, args.input, args.output)
    raise SystemExit(0 if value['status'] == 'complete' else 2)
