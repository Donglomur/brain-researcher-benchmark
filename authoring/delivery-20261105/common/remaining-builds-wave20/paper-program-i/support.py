"""Operator-only complete physical-acquisition joins from reviewed released rows.

A model unit is a physical acquisition/modality, never a saved-source fragment.
Original arrays/clocks remain separate; no behavior resampling or cohort subset
is introduced. Every excluded released row and alias remains in the private census.
"""
import secrets
import numpy as np
from core import need, descriptor, identity, MODALITIES
from lineage import validate, partitions
from views import one_record, context_categories


def prepare(payload, prepared_store, output_store):
    keys={'schema','prepared_path','prepared_pin','certificate','certificate_pin','review','review_pin','evidence_pins','max_queries','max_units'}
    need(type(payload) is dict and set(payload)==keys and payload['schema']=='paper_i_worker_support_v1','Exact operator support request')
    p=prepared_store.json(payload['prepared_path'],payload['prepared_pin'])
    need(p['schema']=='filio_i_prepared_v1','Original prepared artifact')
    cert=payload['certificate'];review=payload['review']
    descriptor(payload['certificate_pin']);descriptor(payload['review_pin'])
    need(type(review) is dict and set(review)=={'schema','certificate','prepared','evidence','accepted','direct_alias_support_complete','biological_hierarchy_complete','processed_target_estimand','reviewer'},'Exact independently approved actual-data lineage review')
    need(review['schema']=='filio_i_actual_lineage_review_v1' and review['certificate']==payload['certificate_pin'] and review['prepared']==payload['prepared_pin'] and review['evidence']==payload['evidence_pins'],'Actual source/review join')
    need(all(review[k] is True for k in ('accepted','direct_alias_support_complete','biological_hierarchy_complete','processed_target_estimand')) and type(review['reviewer']) is str and review['reviewer'],'Unresolved empirical support cannot start encoding')
    need(all(type(payload[k]) is int and payload[k]>0 for k in ('max_queries','max_units')),'Explicit complete support bounds')
    cache={};descriptors={}
    def array(desc):
        path=desc['path']
        need(path not in descriptors or descriptors[path]==desc,'One immutable primitive descriptor per original source path')
        descriptors[path]=desc
        if path not in cache:cache[path]=prepared_store.numeric(desc)
        return cache[path]
    eligible={};sources={a['key']:a for a in p['acquisitions']}
    need(len(sources)==len(p['acquisitions']),'Every original source collection unique')
    for key,a in sources.items():
        if a.get('status')=='structural_absence':eligible[key]=[];continue
        e=array(a['arrays']['eligible'])
        need(e.shape==(a['original_trial_count'],) and np.isin(e,[0,1]).all(),'Literal complete source eligibility flags')
        eligible[key]=np.flatnonzero(e).astype(int).tolist() if a['views'] else []
        need(not eligible[key] or any(m['status']=='present' for m in a['modalities']),'Selected source recording has an observed target modality')
    admitted=validate(p,payload['prepared_pin'],cert,payload['certificate_pin'],payload['evidence_pins'],eligible)
    outer=[partitions(admitted,eligible,f) for f in range(5)]
    inner={(f,g):partitions(admitted,eligible,f,g) for f in range(5) for g in range(5) if f!=g}
    units=[];joined_acquisitions=[];aliases=[];total_queries=0
    for physical,g in admitted['physical_acquisitions'].items():
        key='joined_'+identity({'physical_acquisition':physical})[:32]
        source_acquisitions={source_key:{**sources[source_key],
            'encoding_binding':admitted['rows'][source_key]['encoding_binding']} for source_key in g['source_keys']}
        n=len(g['chronology'])
        joined={'schema':'paper_i_joined_acquisition_v1','key':key,'original_trial_count':n,
                'views':[],'source_acquisitions':source_acquisitions,'trial_sources':{},
                'released_chronology':g['chronology'],'chronology_evidence':g['chronology_evidence'],
                'modalities':[],'private_unit_metadata':{}}
        for modality in MODALITIES:
            required=any(a['views'] and any(m['name']==modality and m['status']=='present' and m['required_cells']>0
                                          for m in a['modalities']) for a in source_acquisitions.values())
            cells=g['cells'][modality]
            need(bool(cells)==required,'Canonical cells exactly represent the complete selected physical modality')
            refs=[None]*n;prior={};view_sets={};vocab={name:set() for name in
                ('planned_delay','reinforcer','first_reward_order','delivered_outcome')}
            target_grid=None;target_desc=None
            for source_key,a in source_acquisitions.items():
                if not eligible[source_key]:continue
                modal=next(m for m in a['modalities'] if m['name']==modality)
                if modal['status']!='present':continue
                lin=admitted['rows'][source_key]
                order=[lin['cells'][modality].index(cell) for cell in cells]
                arrays={desc['path']:array(desc) for desc in a['arrays'].values()
                        if type(desc) is dict and 'path' in desc}
                grid=array(modal['target_time']);y=array(modal['targets'])
                need(grid.ndim==1 and len(grid)>=2 and np.isfinite(grid).all() and np.all(np.diff(grid)>0),
                     'Complete native target grid for every selected fragment')
                need(y.shape==(a['original_trial_count'],len(cells),len(grid)) and
                     np.isfinite(y[eligible[source_key]]).all(),'Full selected fragment target/cell/time axes; no dropping')
                if target_grid is None:target_grid=grid;target_desc=modal['target_time']
                else:need(np.array_equal(grid,target_grid),'Physical model unit requires an exact common native target grid; no resampling')
                arrays[modal['target_time']['path']]=grid
                for rewarded in (False,True):
                    for name,value in context_categories(a,rewarded).items():vocab[name].add(value)
                for source_row in eligible[source_key]:
                    row=g['source_to_joined'][(source_key,source_row)]
                    reference={'source_key':source_key,'row':source_row,'cell_indices':order}
                    records=[one_record(a,arrays,modality,source_row,t,'CM') for t in range(len(grid))]
                    values=y[source_row,order,:]
                    if refs[row] is not None:
                        previous=prior[row]
                        need(np.array_equal(values,previous['targets']),
                             'Physical trial aliases require complete equal target/cell/grid bijection')
                        need(records==previous['records'],'Physical aliases require identical legal retrospective records')
                        aliases.append({'source_key':source_key,'modality':modality,'row':source_row,
                                        'canonical_source_key':refs[row]['source_key'],'canonical_row':refs[row]['row'],
                                        'joined_source_key':key,'joined_row':row,'physical_trial':g['trials'][row]})
                    else:
                        refs[row]=reference;prior[row]={'targets':values,'records':records}
                    view_sets.setdefault(row,set()).update(a['views'])
            joined['trial_sources'][modality]=refs
            selected=[row for row,ref in enumerate(refs) if ref is not None]
            if not required:
                joined['modalities'].append({'name':modality,'status':'structural_absence','cell_count':0,'required_cells':0})
                continue
            need(selected,'Required physical acquisition/modality has no eligible released trial; no source-fragment substitution')
            need(len(units)<payload['max_units'],'Prospective complete physical-unit cap; never truncate')
            folds=[]
            def selected_partition(parts,field,allowed=None):
                return [row for row in selected if (allowed is None or row in allowed) and
                        refs[row]['row'] in parts[refs[row]['source_key']][field]]
            for f in range(5):
                op=outer[f]
                training=selected_partition(op,'train')
                nested=[]
                for g_inner in range(5):
                    if g_inner==f:continue
                    ip=inner[(f,g_inner)]
                    nested.append({'fold':g_inner,**{name:selected_partition(ip,name,set(training))
                                                    for name in ('train','validation','purged_train')}})
                fold={'fold':f,'train':training,'query':selected_partition(op,'query'),
                      'purged_train':selected_partition(op,'purged_train'),'inner':nested}
                need(fold['train'] and fold['query'] and all(part['train'] and part['validation'] for part in nested),
                     'Every required physical acquisition/cell requires five supported outer and four supported inner folds after training-only purge')
                folds.append(fold)
            total_queries+=len(selected)*len(target_grid)
            need(total_queries<=payload['max_queries'],'Full physical query census exceeds explicit cap')
            public_cells=[secrets.token_hex(16) for _ in cells]
            joined['modalities'].append({'name':modality,'status':'present','cell_count':len(cells),
                                         'required_cells':len(cells),'target_time':target_desc})
            joined['private_unit_metadata'][modality]={'animal':g['animal'],'session':g['session'],
                'acquisition':physical,'trials':g['trials'],'cells':cells,
                'categorical_vocabulary':{name:sorted(values) for name,values in vocab.items()},
                'trial_views':{str(row):sorted(view_sets[row]) for row in selected}}
            joined['views']=sorted(set(joined['views']).union(*(view_sets[row] for row in selected)))
            units.append({'unit_id':secrets.token_hex(16),'source_key':key,'modality':modality,
                          'cell_tokens':public_cells,'time_count':len(target_grid),'selected_rows':selected,'outer':folds})
        joined['observed_modalities']=[[m for m in MODALITIES if joined['trial_sources'][m][row] is not None]
                                      for row in range(n)]
        for row,observed in enumerate(joined['observed_modalities']):
            contexts=[]
            for modality in observed:
                ref=joined['trial_sources'][modality][row]
                source=source_acquisitions[ref['source_key']]
                rewarded=bool(array(source['arrays']['rewarded'])[ref['row']])
                contexts.append(context_categories(source,rewarded))
            need(not contexts or all(value==contexts[0] for value in contexts),
                 'Paired observed modalities share the same authenticated discrete physical-trial context')
        joined_acquisitions.append(joined)
    need(units and {u['modality'] for u in units}==set(MODALITIES),'Both complete selected neural modalities required')
    result={'schema':'paper_i_full_support_v1','prepared':payload['prepared_pin'],'certificate':payload['certificate_pin'],
            'review':payload['review_pin'],'units':units,'acquisitions':joined_acquisitions,
            'original_source_acquisitions':p['acquisitions'],'aliases':aliases,
            'all_original_row_dispositions':eligible,'processing':admitted['processing'],
            'unique_outer_queries':total_queries,'actual_animal_count':len({a['private_unit_metadata'][m]['animal']
                for a in joined_acquisitions for m in a['private_unit_metadata']}),
            'model_unit':'authenticated_physical_acquisition_and_modality','scientific_qualification':False}
    support_pin=output_store.put_json('SUPPORT.json',result)
    return {'schema':'paper_i_support_result_v1','support_path':'SUPPORT.json','support_pin':support_pin,
            'unique_outer_queries':total_queries,'unit_count':len(units)}
