"""Full54/270-phase structural closure with all model/view bodies retired."""
import os
MODES=('candidate','cca','constant','frequency-permuted')
def native(c,root,pin,source,kind,ordinal,read,tick):
    v=c.parse(c.capture(root/'NATIVE.json',262144,pin,tick,read))
    c.need(v['schema']=='neural084-sequential-native-phase-v2' and v['kind']==kind and type(v['ordinal'])is int and v['ordinal']==ordinal and v['source']==source and v['status']=='captured','same selected native phase')
    for k in ('all_native_resources_closed','cli_reaped','producer_closed_before_capture'):c.need(v[k]is True,'closed native capture')
    c.need(v['private_scoring_called']is False and v['error_type']is None and len(v['closures'])==3 and all(r['closed']is True for r in v['closures']) and sorted(r['kind'] for r in v['closures'])==['container','container','volume'],'all owned native resources closed')
    c.validate_natural_exit(v['natural_exit']);c.validate_cli_commands(v['command_metadata'],715840000 if kind=='fit' else 400000);return v

def admit(c,contracts,unused,root,terminal,source,s,deadline,read):
    tick=lambda:c.before(deadline)
    def get(p,pin=None,cap=262144):return c.parse(c.capture(p,cap,pin,tick,read))
    c.need(type(terminal)is dict and terminal.get('schema')=='neural084-sequential-worker-v2' and terminal.get('status')=='complete_unqualified' and terminal.get('source')==source and type(terminal.get('query_count'))is int and terminal['query_count']==21600,'complete scientific query scope')
    c.need(not os.path.lexists(root/'FAILURE.json') and not os.path.lexists(root/'current'),'no failure/current view')
    done=get(root/'COMPLETE.json',terminal['complete']);bundle=get(root/'submission.json',terminal['submission'])
    c.need(done['schema']=='neural084-sequential-complete-v2' and done['status']=='complete_unqualified' and done['source']==source and done['program']==c.only_pin(s['program']) and done['pool']==s['pool'] and done['preparation']==s['preparation'] and done['plan']==s['plan'] and done['submission']==terminal['submission'],'same complete source/program/canonical selection')
    for k in ('all_views_and_models_retired','canonical_store_unchanged','labels_opened_for_trusted_staging'):c.need(done[k]is True,'truthful complete staging/custody')
    for k in ('canonical_store_or_private_gold_candidate_mounted','identity_keys_opened','private_scoring_performed','runtime_qualified','scientific_qualified'):c.need(done[k]is False,'restricted unscored source route')
    c.need(type(bundle)is dict and set(bundle)=={'schema','pool','modes','folds'} and bundle['schema']=='neural084-sequential-submission-v2' and bundle['pool']==c.only_pin(s['pool']) and bundle['modes']==list(MODES) and bundle['folds']==done['folds'],'all four unchanged scorer endpoints')
    rows=done['folds'];c.need(type(rows)is list and len(rows)==54 and [r['person'] for r in rows]==list(range(1,55)),'all54 original held-person folds')
    pool=get(s['pool']['path'],c.only_pin(s['pool']),5000000)
    c.need(pool['schema']=='neural084_pool_v1' and len(pool['assets'])==216,'original full canonical metadata only; no outer gold read')
    for ordinal,row in enumerate(rows):
        person=ordinal+1;fold='fold%03d'%person;folder=root/'phases'/fold
        c.need(type(row['person'])is int and type(row['ordinal'])is int and row['ordinal']==ordinal and row['fold']==fold and row['all_current_and_model_absent']is True,'same literal fold identity')
        c.need(get(folder/'CLOSED.json')==row and not os.path.lexists(folder/'model.bin') and not os.path.lexists(folder/'fit/model.bin'),'closed fold, no accumulated model body')
        c.need(set(row['native'])=={'fit','infer','cca','constant','frequency-permuted'} and set(row['outputs'])==set(MODES),'all270 phase identities')
        seal=get(folder/'MODEL_SEAL.json',row['seal']);train=get(folder/'TRAIN_RETIRED.json',row['train_retired']);query=get(folder/'QUERY_RETIRED.json',row['query_retired']);model=get(folder/'MODEL_RETIRED.json',row['model_retired'])
        c.need(seal['schema']=='neural084-model-seal-v2' and seal['source']==source and seal['program']==done['program'] and seal['person']==person and seal['model']==row['model'] and seal['fit_native']==row['native']['fit'] and seal['fit_closed']is True and seal['query_exposed']is False and seal['single_model_body']is True,'fit-closed one-body model seal before query')
        c.need(train['schema']=='neural084-train-retired-v2' and train['person']==person and train['seal']==row['seal'] and train['absent']is True and train['parent_fsynced']is True and train['query_exposed']is False and set(train['training'])=={'train.json','training.json','training.npy'},'durable training retirement before held features')
        meta=get(folder/'FOLD.json',row['fold_metadata']);ids=sorted(q for a in pool['assets'] if a['person']==person for q in a['ids'])
        contracts._fold_contract(meta,person,pool['generation']);c.need(meta['ids']==ids and len(ids)==400 and c.only_pin(meta['training'])==train['training']['training.npy'] and c.only_pin(meta['training_metadata'])==train['training']['training.json'],'same original query IDs and retired training pins')
        c.need(query['schema']=='neural084-query-retired-v2' and query['person']==person and query['fold']==row['fold_metadata'] and query['absent']is True and query['parent_fsynced']is True and query['all_query_native_closed']is True and set(query['query'])=={'fold.json','queries.npy'},'durable standalone query retirement')
        c.need(query['query']['fold.json']==row['fold_metadata'] and query['query']['queries.npy']==c.only_pin(meta['queries']),'retired query pins equal admitted fold and array evidence')
        c.need(model['schema']=='neural084-model-retired-v2' and model['person']==person and model['model']==row['model'] and model['seal']==row['seal'] and model['fit_native']==row['native']['fit'] and model['infer_native']==row['native']['infer'] and model['model_stamp']==seal['model_stamp'] and model['absent']is True and model['parent_fsynced']is True and model['fit_copy_absent']is True,'same sealed model retired durably without accumulated copies')
        fit=native(c,folder/'fit',row['native']['fit'],source,'fit',ordinal,read,tick);c.need(fit['output']==row['model'],'sealed captured fit bytes')
        for kind in ('infer','cca','constant','frequency-permuted'):
            mode='candidate' if kind=='infer' else kind;value=native(c,folder/kind,row['native'][kind],source,kind,ordinal,read,tick)
            c.need(value['output']==row['outputs'][mode],'same inference/reference bytes')
            raw=c.capture(folder/kind/'predictions.json',262144,row['outputs'][mode],tick,read);contracts.prediction(raw,meta)
            c.need(c.capture(root/'predictions'/mode/(fold+'.json'),262144,row['outputs'][mode],tick,read)==raw,'same original scorer raw output')
    names={'fold%03d.json'%p for p in range(1,55)}
    for mode in MODES:
        files,dirs,_=c.inventory(root/'predictions'/mode,54*262144+1048576,60);c.need(set(files)==names and len(dirs)==1,'complete54 predictions each mode')
    handoff=get(root/'GRADE_HANDOFF.json',done['grade_handoff']);c.need(handoff['execution_authorized']is False and handoff['all54_required_per_mode']is True and handoff['pool']==s['pool'],'separate future complete-cohort grade')
    c.need(c.inventory(root,s['limits']['retained'],400200)[2]<=s['limits']['retained']-16384,'whole retained allocation plus outer slot');tick()
    return done['submission'],terminal['complete']
