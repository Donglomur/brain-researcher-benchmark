"""Actual authored fit/predict computation with safe sealed state and typed later replies."""
from core import need, parse, capture, encoded, publish, fresh, pin
from contracts import recipe as admit_recipe
from array_io import pack, unpack, save
from worker_common import start, seed_numpy, view, method, finish, failure


def run(config):
    request, budget, limits, output = start(config)
    try:
        seed_numpy(request['seed']); batch = view(request, limits); code = method(request, budget)
        plan = admit_recipe(request['recipe']); artifacts = {}; fresh(output/'arrays', budget)
        context = {'seed': request['seed'], 'view': batch['view'], 'endpoints': ['angle', 'magnitude', 'speed'],
                   'query_ids': [x for p in batch['query'] for x in p['ids']],
                   'training_ids': [x for p in batch['train'] for x in p['ids']]}
        if request['kind'] == 'fit':
            need(callable(code.get('fit')), 'authored fit implementation')
            # Complete permitted label-free query batch is equally available to F and I.
            # Candidate-internal work is enclosed by the qualified native memory/
            # CPU profile. These reservations cover this trusted wrapper's copies.
            limits.reserve('allocation_bytes',2*request['feature_bytes'])
            limits.reserve('serialized_bytes',request['feature_bytes'])
            state, features = code['fit'](batch, context)
            tree, arrays = pack(state, output, limits, plan['state_array_cap'], plan['state_metadata_bytes'])
            state_body = {'schema': 'neural049_candidate_state_v1', 'method': request['method']['pin'],
                          'recipe': pin(encoded(plan)), 'view': request['view']['pin'], 'scope': request['scope'],
                          'seed': request['seed'], 'state': tree}
            artifacts['STATE.json'] = publish(output/'STATE.json', encoded(state_body), budget, readonly=True)
            need(type(features) is dict and set(features) == {s['name'] for s in plan['provider_slots']}, 'only frozen provider slots')
            for slot in plan['provider_slots']:
                value = features[slot['name']]
                import numpy as np
                n = 1 if slot['axis'] == 'one' else len(context['training_ids' if slot['axis'] == 'training' else 'query_ids'])
                need(type(value) is np.ndarray and value.dtype.str == '<f8' and value.shape == (n, slot['input_width'])
                     and bool(np.isfinite(value).all()), 'complete typed numerical provider features')
                features[slot['name']] = value.tolist()
            raw = encoded({'schema': 'neural049_fixed_features_v1', 'slots': features, 'state': artifacts['STATE.json']})
            need(len(raw) <= request['feature_bytes'], 'full feature matrix cap, no truncated rows')
            artifacts['FEATURES.json'] = publish(output/'FEATURES.json', raw, budget, readonly=True)
            for d in arrays: artifacts[d['path'].split('/output/')[-1]] = d['pin']
        elif request['kind'] == 'predict':
            raw, _ = capture(request['state']['path'], request['state']['pin'], plan['state_metadata_bytes'] + request['view_cap'], budget, readonly=True)
            sealed = parse(raw)
            need(sealed['schema'] == 'neural049_candidate_state_v1' and sealed['method'] == request['method']['pin']
                 and sealed['recipe'] == pin(encoded(plan)) and sealed['view'] == request['view']['pin']
                 and sealed['scope'] == request['scope'] and sealed['seed'] == request['seed'], 'exact same case fitted state')
            state = unpack(sealed['state'], request['state_root'], limits)
            need(callable(code.get('predict')), 'authored predict implementation')
            replies = request['provider_values']
            need(set(replies) == {s['name'] for s in plan['provider_slots']}, 'complete fixed numerical replies')
            import numpy as np
            for slot in plan['provider_slots']:
                n = 1 if slot['axis'] == 'one' else len(context['training_ids' if slot['axis'] == 'training' else 'query_ids'])
                limits.reserve('allocation_bytes',n*slot['output_width']*8)
                limits.reserve('elements',n*slot['output_width'])
                arr = np.asarray(replies[slot['name']], dtype=np.float64)
                if n == 0: arr = arr.reshape((0,slot['output_width']))
                need(arr.shape == (n, slot['output_width']) and bool(np.isfinite(arr).all()), 'typed frozen reply shape')
                replies[slot['name']] = arr
            raw = code['predict'](state, batch, replies, context)
            need(type(raw) is np.ndarray and raw.dtype.str == '<f8' and raw.shape == (len(context['query_ids']), 3)
                 and bool(np.isfinite(raw).all()), 'all raw rows/endpoints finite before projection')
            limits.reserve('allocation_bytes', 4*raw.nbytes); projected = raw.copy(order='C')
            projected[:, 0] = np.clip(projected[:, 0], -90., 90.); projected[:, 1:] = np.maximum(projected[:, 1:], 0.)
            r = save(np.ascontiguousarray(raw), output/'raw.npy', limits)
            p = save(projected, output/'projected.npy', limits)
            artifacts['raw.npy'] = r['pin']; artifacts['projected.npy'] = p['pin']
            result = {'schema': 'neural049_candidate_predictions_v1', 'ids': context['query_ids'], 'raw': r, 'projected': p,
                      'state': request['state'], 'method': request['method']['pin'], 'view': request['view']['pin'],
                      'scope': request['scope'], 'endpoints': context['endpoints']}
            artifacts['RESULT.json'] = publish(output/'RESULT.json', encoded(result), budget, readonly=True)
        else: raise ValueError('candidate kind')
        return finish(output, request, budget, limits, artifacts)
    except BaseException as error:
        failure(output, error, budget, limits); raise
