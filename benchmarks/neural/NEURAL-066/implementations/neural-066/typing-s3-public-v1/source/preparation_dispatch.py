"""Concrete complete operator preparation actions for isolated workers."""
from pathlib import Path
from core import encoded, identity, need
from safe_io import array, capture, child, new_json, pin, strict
import preparation as prep
import operator_policy

def read(root, desc, cap):
    return strict(capture(child(root, desc['path']), cap, {k: desc[k] for k in ('bytes', 'sha256')}))

def projected_view(view, purpose):
    out = {k: view[k] for k in ('case', 'generation', 'condition', 'modality', 'channels', 'feature_dimensions', 'samples_per_key', 'feature_spec', 'support_commitment', 'source_contract_pin', 'projection_pin', 'language_policy_pin')}
    out.update(format='typing_reference_view_v1', task='NEURAL-066', purpose=purpose)
    if purpose == 'infer':
        out['queries'] = view['queries']
    return out

def case_views(case, logs, joined, projections, roots, seed, output, limits, mode, contracts, policy):
    results = {}
    for condition in prep.CONDITIONS:
        destination = Path(output) / condition
        result = prep.make_view(case, logs, joined, projections, roots, seed, mode, condition, destination, limits, contracts, policy)
        view = read(destination, {'path': 'VIEW.json', **result['view']}, limits['json_bytes'])
        for purpose in ('fit', 'infer'):
            name = purpose.upper() + '_VIEW.json'
            result[purpose + '_view'] = {'path': name, **new_json(destination / name, projected_view(view, purpose))}
        if mode == 'reference':
            from reference.core import derive_buckets
            private = {prep.key(r): r for r in logs['records'] if prep.eligible(r, policy)}
            layout = read(destination, {'path': 'TRAIN_LAYOUT.json', **result['layout']}, limits['json_bytes'])['sentences']
            pmap = {}
            tmap = {}
            for row in layout:
                r = private[result['training_private_join'][row['id']]]
                pmap[row['person']] = r['person']
                tmap[row['template']] = r['group']
            pb = derive_buckets(case['modality'], case['person'], case['fold'], 'person', list(pmap.values()))
            tb = derive_buckets(case['modality'], case['person'], case['fold'], 'template', list(tmap.values()))
            provenance = {'case_slot': case['slot'], 'person_private_map': pmap, 'template_private_map': tmap, 'source_method': 'accepted private SHA256 rankmod3'}
            provpin = new_json(destination / 'ASSIGNMENT_PRIVATE.json', provenance)
            plan = {'schema': 'neural066_reference_plan_v1', 'case': view['case'], 'modality': view['modality'], 'condition': condition, 'person_buckets': {k: pb[v] for k, v in pmap.items()}, 'template_buckets': {k: tb[v] for k, v in tmap.items()}, 'assignment_provenance': provpin}
            result['plan'] = {'path': 'REFERENCE_PLAN.json', **new_json(destination / 'REFERENCE_PLAN.json', plan)}
        results[condition] = result
    return results

def run(request, inputroot, outputroot):
    limits = request['limits']
    inputs = request['inputs']
    action = request['action']
    out = Path(outputroot)
    policy = operator_policy.load(inputroot, inputs.get('membership_policy'),
                                  request.get('membership_policy_pin'), limits['json_bytes'])
    if action == 'native_project':
        record = read(inputroot, inputs['record'], limits['json_bytes'])
        records = read(inputroot, inputs['records'], limits['json_bytes'])
        assets = read(inputroot, inputs['assets'], limits['json_bytes'])
        need(type(request.get('native_originals')) is dict and request['native_originals'] == assets and set(record['raw_assets']) == set(assets), 'Actual loader originals equal the complete exact transport asset roster')
        loader = capture(child(inputroot, inputs['loader']['path']), policy['asset_pins']['loader']['bytes'], policy['asset_pins']['loader'])
        return prep.native_project('/input/originals', record, records, assets, loader, out, limits, policy)
    if action == 'membership':
        membership = read(inputroot, inputs['membership'], limits['json_bytes'])
        logs = read(inputroot, inputs['logs'], limits['json_bytes'])
        projected = [read(inputroot, d, limits['json_bytes']) for d in inputs['projections']]
        result = prep.join_projections(membership, logs, projected, policy)
        new_json(out / 'RESULT.json', result)
        return result
    if action in ('case_plan', 'candidate_view'):
        case = read(inputroot, inputs['case'], limits['json_bytes'])
        logs = read(inputroot, inputs['logs'], limits['json_bytes'])
        joined = read(inputroot, inputs['joined'], limits['json_bytes'])
        projected = [read(inputroot, d, limits['json_bytes']) for d in inputs['projections']]
        roots = [str(child(inputroot, p)) for p in inputs['projection_roots']]
        seed = capture(child(inputroot, inputs['opaque_seed_path']), 32)
        if action == 'case_plan':
            result = {'schema': 'neural066_case_plan_result_v1', 'case_slot': case['slot'], 'reference_views': case_views(case, logs, joined, projected, roots, seed, out, limits, 'reference', request['contracts'], policy)}
        else:
            result = prep.make_view(case, logs, joined, projected, roots, seed, request['mode'], request['condition'], out, limits, request['contracts'], policy)
            view = read(out, {'path': 'VIEW.json', **result['view']}, limits['json_bytes'])
            for purpose in ('fit', 'infer'):
                name = purpose.upper() + '_VIEW.json'
                result[purpose + '_view'] = {'path': name, **new_json(out / name, projected_view(view, purpose))}
        new_json(out / 'RESULT.json', result)
        return result
    raise ValueError('Exact operator action required')
