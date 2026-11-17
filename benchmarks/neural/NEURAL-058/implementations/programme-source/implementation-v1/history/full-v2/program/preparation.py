"""Full423/29 operator preparation with physically separate C/J/label members."""
from pathlib import Path
import secrets
from core import need, finite, integer, fresh, disjoint, capture, parse, encoded, pin
from contracts import TASK, LIBRARIES, cohort
from arrays import write_array, write_json
from native_reader import original, iter_windows, versions


def validate_authority(authority, roster):
    need(authority.get('schema') == 'neural058_preparation_authority_v1' and authority.get('selected') is True,
         'separately selected complete preparation')
    need(authority.get('task') == TASK and authority.get('conditional_history') is False, 'strict primary only')
    roots = authority['roots']; keys = ('original','public','private','source','observation','operator')
    need(set(roots) == set(keys), 'complete preparation namespaces')
    for i,a in enumerate(keys):
        for b in keys[i+1:]: need(disjoint(roots[a], roots[b]), 'no overlapping preparation roots')
    rows = authority['inputs']; expected = set(roster['source']) | set(roster['evaluation'])
    need(type(rows) is list and len(rows) == 452 and {r['session'] for r in rows} == expected,
         'all452 exact original sessions; no extra evaluation-animal session')
    need(len({r['path'] for r in rows}) == 452, 'distinct physical original locators')
    for row in rows:
        eid = row['session']; r = (roster['source'] | roster['evaluation'])[eid]
        need(row['animal'] == r['animal'] and row['probes'] == r['probes'], 'complete biological/probe original join')
        need(row['unit_filtering'] == 'all_units', 'full unit build')
        need(row['units'] == 'radians' and row['sign_convention'] == authority['sign_convention'], 'independently admitted common units/sign, no silent conversion')
        need(row['extraction_lineage'] and row['original_identity'] and row['producer_version'], 'original provenance required')
    return {r['session']:r for r in rows}


def session_arrays(data, role, limits, budget):
    import numpy as np
    windows = []; ts = []; spike_times = []; spike_units = []; domains = []; labels = []
    times_offset = [0]; spikes_offset = [0]; domains_offset = [0]
    private = []; location = location_missing = regions = None
    total_elements = 0
    for w in iter_windows(data, role, limits, budget):
        budget.tick()
        if location is None: location, location_missing, regions = w['locations'], w['location_missing'], w['regions']
        else: need(np.array_equal(location,w['locations']) and np.array_equal(location_missing,w['location_missing']) and regions == w['regions'], 'unchanged full anatomical unit roster')
        total_elements += len(w['times'])*3 + len(w['spike_times'])*2 + w['neural_domain'].size
        need(total_elements <= limits['session_projected_elements'], 'complete session projected extent; no truncation')
        ts.append(w['times']); spike_times.append(w['spike_times']); spike_units.append(w['spike_units'])
        domains.append(w['neural_domain']); labels.append(np.column_stack((w['velocity'],w['speed'])))
        times_offset.append(times_offset[-1]+len(w['times']))
        spikes_offset.append(spikes_offset[-1]+len(w['spike_times']))
        domains_offset.append(domains_offset[-1]+len(w['neural_domain']))
        windows.append({'query': secrets.token_hex(16), 'context': w['context'], 'support': w['support'].tolist()})
        private.append({'query': windows[-1]['query'], 'source_split': w['source_split'],
                        'source_trial': w['source_trial'], 'source_onset': w['source_onset'],
                        'A0': w['A0'], 'native_target_origin': w['native_target_origin']})
    need(windows and location is not None, 'required full session has observations')
    # This is a complete-copy representation, not a claimed streaming-memory
    # bound; original lists plus concatenation coexist and must fit selected RAM.
    arrays = {'time_offsets': np.array(times_offset,dtype='<i8'), 'times': np.concatenate(ts).astype('<f8'),
              'spike_offsets': np.array(spikes_offset,dtype='<i8'), 'spike_times': np.concatenate(spike_times).astype('<f8'),
              'spike_units': np.concatenate(spike_units).astype('<i8'),
              'domain_offsets': np.array(domains_offset,dtype='<i8'), 'neural_domain': np.concatenate(domains).astype('<f8'),
              'locations': location.astype('<f8'), 'location_missing':location_missing.astype('|b1'), 'labels': np.concatenate(labels).astype('<f8')}
    return windows, regions, arrays, private


def run(authority, cohort_document, budget, qualify):
    """qualify is trusted evidence admission, never a data/fit/result callback.

    The concrete operator entry supplies the source-owned qualification verifier.
    It authenticates the exact effective selection, source/library image, all
    original custody and memory/IO enforcement before this function may act.
    """
    roster = cohort(cohort_document); inputs = validate_authority(authority, roster)
    need(qualify('original_preparation', authority) is True,'explicit independent original preparation admission before effects')
    versions({'numpy':'2.2.6','torch':'2.10.0','torch-brain':'0.2.0a0'})
    budget.tick(); public = fresh(authority['roots']['public'], budget); private_root = fresh(authority['roots']['private'], budget)
    limits = authority['limits']
    for key,value in limits.items(): integer(value,1)
    aliases = {animal: secrets.token_hex(16) for animal in roster['source_animals']+roster['eval_animals']}
    outcomes = []; private_rows = []; stage = None
    try:
        for role in ('source','evaluation'):
            people=roster['source_animals' if role=='source' else 'eval_animals']
            for ordinal,eid in enumerate(roster[role+'_order']):
                animal_ordinal=people.index(roster[role][eid]['animal'])
                stage = {'session': eid, 'role': role, 'status':'attempted','session_ordinal':ordinal,'animal_ordinal':animal_ordinal}; outcomes.append(stage)
                row = inputs[eid]; opaque = secrets.token_hex(16)
                out = fresh(public/opaque, budget); hidden = fresh(private_root/opaque, budget)
                original_path = Path(authority['roots']['original']) / __import__('core').relative(row['path'])
                with original(original_path,row['pin'],limits,budget) as (data,costs):
                    need(str(data.session.id) == eid and str(data.subject.id) == row['animal'], 'actual original session/animal metadata')
                    need(str(data.brainset.unit_filtering) == 'all_units', 'actual full original build')
                    windows, regions, arrays, private_joins = session_arrays(data,role,limits,budget)
                common_names = ('time_offsets','times','locations','location_missing')
                neural_names = ('spike_offsets','spike_times','spike_units','domain_offsets','neural_domain')
                common = {k:write_array(out,k+'.npy',arrays[k],budget,limits['export_array_bytes']) for k in common_names}
                neural = {k:write_array(out,k+'.npy',arrays[k],budget,limits['export_array_bytes']) for k in neural_names}
                # Evaluation labels are never present in a candidate-readable
                # directory, manifest, sidecar, image or shared cache.
                label_root = out if role == 'source' else hidden
                label = write_array(label_root,'labels.npy',arrays['labels'],budget,limits['export_array_bytes'])
                body = {'schema':'neural058_session_view_v1','task':TASK,'role':role,'session':opaque,
                        'animal':aliases[row['animal']], 'session_ordinal':ordinal,'animal_ordinal':animal_ordinal,
                        'windows':windows,'regions':regions,
                        'common':common,'neural':neural,'labels':label if role == 'source' else None,
                        'fold':roster['folds'].get(row['animal'])}
                view = write_json(out,'VIEW.json',body,budget,limits['session_metadata_bytes'])
                hidden_body = {'session':eid,'animal':row['animal'],'opaque_session':opaque,
                               'opaque_animal':aliases[row['animal']],'original':row,'joins':private_joins,
                               'labels':label,'label_root_role':'public' if role == 'source' else 'private',
                               'view':view,'original_projection_costs':costs}
                join = write_json(hidden,'JOINS.json',hidden_body,budget,limits['session_metadata_bytes'])
                private_rows.append({'path':opaque+'/JOINS.json','pin':join['pin']})
                stage.update(status='complete',session_alias=opaque,view={'path':opaque+'/VIEW.json','pin':view['pin']})
                del arrays, windows, regions, private_joins
        budget.tick()
        public_body={'schema':'neural058_full_prepared_corpus_v1','task':TASK,
                     'source':[r['view'] for r in outcomes if r['role']=='source'],
                     'evaluation':[r['view'] for r in outcomes if r['role']=='evaluation'],
                     'source_order':[r['session_alias'] for r in outcomes if r['role']=='source'],
                     'evaluation_order':[r['session_alias'] for r in outcomes if r['role']=='evaluation'],
                     'source_animal_order':[aliases[a] for a in roster['source_animals']],
                     'evaluation_animal_order':[aliases[a] for a in roster['eval_animals']],
                     'cohort':pin(encoded(cohort_document)), 'authority':pin(encoded(authority)),
                     'conditional_history':False,'all_original_support_retained':True}
        private_body={'schema':'neural058_private_preparation_v1','task':TASK,'sessions':private_rows,
                      'animal_aliases':aliases,'outcomes':outcomes,'authority':public_body['authority']}
        hidden=write_json(private_root,'COMPLETE.json',private_body,budget,limits['corpus_metadata_bytes'])
        result=write_json(public,'COMPLETE.json',public_body,budget,limits['corpus_metadata_bytes'])
        budget.tick(); return {'public':result,'private':hidden,'outcomes':outcomes}
    except BaseException as error:
        if stage is not None and stage['status']=='attempted': stage.update(status='failed',failure_type=type(error).__name__)
        # Caller retains this complete ledger and reports unattempted original
        # rows explicitly even if no failure artifact can be persisted.
        error.neural058_preparation_outcomes = outcomes
        error.neural058_unattempted = [e for r in ('source','evaluation') for e in sorted(roster[r]) if e not in {x['session'] for x in outcomes}]
        raise
