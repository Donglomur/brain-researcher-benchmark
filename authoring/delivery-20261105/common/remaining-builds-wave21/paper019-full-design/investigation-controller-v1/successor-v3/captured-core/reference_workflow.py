"""Concrete complete nested reference computations; no supplied-result callbacks.

Input rows are operator-private already-admitted records, not original MAT
readers or candidate views. Numeric source is loaded from the pinned helper.
"""
import math
import numeric_backend as numeric
from common import STRATA, VARIANTS, need, finite, pin, integer
from study import cohort_queries, cohort_sets, validate_study

def validate_rows(study, rows, behavior_kinds, cohort, animals):
    expected = {q['id']: q for q in cohort_queries(study,cohort) if q['animal'] in animals}
    need(type(rows) is dict and set(rows) == set(expected), 'complete exact fitting-partition rows; no outer held rows')
    need(type(behavior_kinds) is list and behavior_kinds and
         all(k in ('continuous','indicator') for k in behavior_kinds), 'fixed behavior schema')
    targets = {}
    for q, row in rows.items():
        need(type(row) is dict and set(row) == {'id','animal','session','stratum','seconds','behavior',
             'behavior_observed','epochs','channel_mask','grid_pin','persistence_seconds','history_schedule_pin'},
             'exact private row schema')
        meta = expected[q]
        need(row['id'] == q and all(row[k] == meta[k] for k in
             ('animal','session','stratum','channel_mask','grid_pin')), 'typed row joins authenticated metadata')
        need(type(row['behavior']) is list and type(row['behavior_observed']) is list and
             len(row['behavior']) == len(row['behavior_observed']) == len(behavior_kinds), 'fixed behavior dimensions')
        from common import require_pin
        require_pin(row['history_schedule_pin'])
        need(row['history_schedule_pin'] == study['admission_evidence']['logical_history'],
             'exact independently frozen logical training schedule')
        value = finite(row['seconds']); need(value > 0, 'positive private time')
        target = meta['target_key']
        need(target not in targets or targets[target] == value, 'shared target alias equality')
        targets[target] = value
        need(type(row['epochs']) is dict and set(row['epochs']) == {'D','ACh'}, 'exact channel blocks')
        for i, name in enumerate(('D','ACh')):
            if row['channel_mask'][i] == 0:
                need(row['epochs'][name] is None, 'absent channel has no invented measurement')
            else:
                need(type(row['epochs'][name]) is dict and set(row['epochs'][name]) == {'times','values'},
                     'actual channel epoch; numeric admissibility checked when retained')
        history = row['persistence_seconds']
        need(history is None or finite(history) > 0, 'permitted persistence history or explicit unavailable')
    return {'rows': len(rows), 'feature_schema_pin': study['feature_schema_pin'],
            'actual_field_clock_alias_or_history_admission': False}

def selected_rows(study, rows, cohort, animals, stratum):
    allowed = set(animals)
    metadata = [q for q in cohort_queries(study, cohort) if q['animal'] in allowed and q['stratum'] == stratum]
    need(set(q['animal'] for q in metadata) == allowed, 'all fitting animals and stratum support')
    return [rows[q['id']] for q in sorted(metadata, key=lambda q: q['id'])]

def weight_rows(rows, animals):
    sessions = {a: sorted({r['session'] for r in rows if r['animal']==a}) for a in animals}
    descriptors = [{'row_id': r['id'], 'animal': r['animal'], 'session': r['session']} for r in rows]
    weights = numeric.group_weights(descriptors, list(animals), sessions)
    return weights, descriptors, sessions

def retained(variant):
    need(variant in VARIANTS, 'known exact ablation')
    return {'B': (), 'D': ('D',), 'ACh': ('ACh',), 'F': ('D','ACh')}[variant]

def preprocessing_extent(rows, behavior_kinds, variant, limits, budget, phase):
    n = len(rows); b = len(behavior_kinds)
    need(n > 0 and n <= limits['numeric']['max_rows'] and b <= limits['max_behavior_features'],
         'preprocessing dimensions before allocation')
    stratum = rows[0]['stratum']; need(all(r['stratum']==stratum for r in rows), 'one event head')
    f = 11 if stratum == 'opt_out' else 13
    p = 4*b + (2+len(retained(variant)))*f + 2
    need(p <= limits['numeric']['max_features'], 'complete feature extent')
    epoch_samples = 0
    for row in rows:
        need(len(row['behavior']) == len(row['behavior_observed']) == b, 'full behavior width')
        for name in retained(variant):
            epoch = row['epochs'][name]
            if epoch is not None:
                need(type(epoch['times']) is list and type(epoch['values']) is list and
                     len(epoch['times']) == len(epoch['values']) <= limits['max_epoch_samples'], 'bounded full epoch')
                epoch_samples += len(epoch['times'])
    budget.reserve({'feature_cells': n*p, 'epoch_samples': epoch_samples}, phase)
    return f, p

def features_fit(rows, behavior_kinds, variant, weights, limits, budget, phase):
    f, p = preprocessing_extent(rows, behavior_kinds, variant, limits, budget, phase)
    bvalues = [r['behavior'] for r in rows]; bobs = [r['behavior_observed'] for r in rows]
    behavior = numeric.fit_standardizer(bvalues,bobs,behavior_kinds,weights)
    transformed_b = numeric.transform_standardizer(behavior,bvalues,bobs)
    channels, values = {}, {}
    for name in retained(variant):
        i = 0 if name=='D' else 1
        observed = [[bool(r['channel_mask'][i])]*f for r in rows]
        raw = [numeric.epoch_features(r['epochs'][name]['times'],r['epochs'][name]['values'],r['stratum'])['features']
               if r['channel_mask'][i] else [None]*f for r in rows]
        need(any(r['channel_mask'][i] for r in rows), 'required retained modality training support')
        state = numeric.fit_standardizer(raw,observed,['continuous']*f,weights)
        channels[name] = state
        values[name] = numeric.transform_standardizer(state,raw,observed)
    matrix = []
    for index,row in enumerate(rows):
        cD,cA = row['channel_mask']
        matrix.append(numeric.build_variant(transformed_b[index],[cD]*f,[cA]*f,cD,cA,
            variant=variant,n_D=values['D'][index] if 'D' in values else None,
            n_A=values['ACh'][index] if 'ACh' in values else None))
    need(all(len(v)==p for v in matrix), 'exact common G/value/T geometry')
    return {'variant': variant, 'stratum': rows[0]['stratum'], 'behavior': behavior,
            'behavior_kinds': list(behavior_kinds), 'channels': channels, 'neural_features': f,
            'feature_count': p}, matrix

def features_apply(state, rows, limits, budget, phase):
    variant = state['variant']; f,p = preprocessing_extent(rows,state['behavior_kinds'],variant,limits,budget,phase)
    need(state['stratum'] == rows[0]['stratum'] and f==state['neural_features'] and p==state['feature_count'],
         'same sealed head geometry')
    values_b = numeric.transform_standardizer(state['behavior'],[r['behavior'] for r in rows],
                                             [r['behavior_observed'] for r in rows])
    channels = {}
    for name in retained(variant):
        i=0 if name=='D' else 1
        raw=[numeric.epoch_features(r['epochs'][name]['times'],r['epochs'][name]['values'],r['stratum'])['features']
             if r['channel_mask'][i] else [None]*f for r in rows]
        observed=[[bool(r['channel_mask'][i])]*f for r in rows]
        channels[name]=numeric.transform_standardizer(state['channels'][name],raw,observed)
    return [numeric.build_variant(values_b[i],[r['channel_mask'][0]]*f,[r['channel_mask'][1]]*f,
             *r['channel_mask'],variant=variant,n_D=channels['D'][i] if 'D' in channels else None,
             n_A=channels['ACh'][i] if 'ACh' in channels else None) for i,r in enumerate(rows)]

def fit_one(study, rows, cohort, animals, stratum, variant, setting, behavior_kinds, limits, budget, phase):
    partition = selected_rows(study,rows,cohort,animals,stratum)
    budget.reserve({'head_fits':1,'row_uses':len(partition)},phase)
    try:
        weights,descriptors,sessions = weight_rows(partition,animals)
        transform,matrix = features_fit(partition,behavior_kinds,variant,weights,limits,budget,phase+'/features')
        estimate = numeric.resource_plan(len(matrix),len(matrix[0]),setting,limits['numeric'])
        model = numeric.fit_head(matrix,[r['seconds'] for r in partition],weights,setting,
                                 [r['id'] for r in partition],limits=limits['numeric'])
        budget.tick()
        return {'model':model,'transform':transform,'training_animals':list(animals),
                'training_row_ids':[r['id'] for r in partition],'training_sessions':sessions,
                'phase':phase,'resource_plan':estimate}
    except BaseException as error:
        budget.failed(phase,error)
        raise

def predict_one(bundle, rows, limits, budget, phase):
    budget.reserve({'predictions':len(rows),'row_uses':len(rows)},phase)
    try:
        numeric.resource_plan(len(bundle['model']['row_ids']),bundle['model']['feature_count'],
                              bundle['model']['setting'],limits['numeric'])
        matrix=features_apply(bundle['transform'],rows,limits,budget,phase+'/features')
        result=numeric.predict_head(bundle['model'],matrix)
        budget.tick()
        need(len(result)==len(rows),'all predictions')
        return result
    except BaseException as error:
        budget.failed(phase,error)
        raise

def nested_panel(study, rows, panel, behavior_kinds, limits, budget):
    """Compute one complete operator bundle; every setting/head/inner animal runs.

    The caller must invoke every panel from the complete plan, then admit the
    complete graph before grading. This function does not claim whole-study use.
    """
    need(panel['actor']=='operator','independent source-owned reference only')
    validate_study(study)
    cohort,variant,training=panel['cohort'],panel['variant'],panel['training_animals']
    need(cohort in cohort_sets(study) and panel['animal'] in cohort_sets(study)[cohort] and
         training==[a for a in cohort_sets(study)[cohort] if a!=panel['animal']],
         'complete original full/paired outer training')
    need(panel['query_ids']==[q['id'] for q in cohort_queries(study,cohort,panel['animal'])]
         and panel['heads']==list(STRATA),'full original held query support and four heads')
    validate_rows(study,rows,behavior_kinds,cohort,training)
    settings=numeric.settings(); losses=[]; fit_records=[]
    prefix=panel['bundle_fit_id']
    for setting in settings:
        for validation in training:
            inner=[a for a in training if a!=validation]
            for stratum in STRATA:
                phase=prefix+'|inner|'+validation+'|'+stratum+'|'+setting['id']
                bundle=fit_one(study,rows,cohort,inner,stratum,variant,setting,behavior_kinds,limits,budget,phase)
                held=selected_rows(study,rows,cohort,[validation],stratum)
                predictions=predict_one(bundle,held,limits,budget,phase+'/validate')
                _,descriptors,sessions=weight_rows(held,[validation])
                loss=numeric.validation_loss(predictions,[r['seconds'] for r in held],descriptors,
                    validation,sessions[validation],bundle['model']['target']['variance'])
                losses.append({'setting_id':setting['id'],'animal':validation,'stratum':stratum,'loss':loss})
                fit_records.append({'phase':phase,'training_animals':inner,'training_rows_pin':pin(bundle['training_row_ids']),
                    'model_pin':pin(bundle['model']),'transform_pin':pin(bundle['transform']),
                    'validation_predictions_pin':pin(dict(zip((r['id'] for r in held),predictions))),
                    'normalized_loss':loss,'resource_plan':bundle['resource_plan']})
    selection=numeric.select_setting(losses,training)
    final = {}
    for stratum in STRATA:
        phase=prefix+'|refit|'+stratum
        bundle=fit_one(study,rows,cohort,training,stratum,variant,selection['setting'],behavior_kinds,limits,budget,phase)
        final[stratum]=bundle
        fit_records.append({'phase':phase,'training_animals':training,'training_rows_pin':pin(bundle['training_row_ids']),
            'model_pin':pin(bundle['model']),'transform_pin':pin(bundle['transform']), 'resource_plan':bundle['resource_plan']})
    need(set(final)==set(STRATA) and len(fit_records)==4*(20*len(training)+1),
         'complete original reference fit graph')
    return {'panel_key':prefix.removesuffix('|final'),'selection':selection,'selection_pin':pin(selection),
            'history_schedule_pin':study['admission_evidence']['logical_history'],
            'loss_cells':losses,
            'fitted_state':final,'pending_query_ids':list(panel['query_ids']),
            'fit_records':fit_records,'fit_record_pin':pin(fit_records),
            'logical_budget':budget.report(),'scientific_qualified':False}

def infer_reference_query(fit, view, entitlement, limits, budget):
    """Exactly one admitted query; no full future table or protected label input.

    The authentic minimized view constructor and actual durable query/realm
    observer remain separately qualified infrastructure. This function verifies
    their exact source-level entitlement and uses only the frozen head.
    """
    need(type(view) is dict and set(view)=={'id','stratum','behavior','behavior_observed','epochs',
         'channel_mask','grid_pin','history_schedule_pin','persistence_seconds'}, 'minimal single-query view')
    need(type(entitlement) is dict and set(entitlement)=={'panel_key','query_id','view_pin',
         'active_obligation','batch_pin','view_admission_pin'}, 'exact current query entitlement')
    from common import require_pin
    for key in ('batch_pin','view_admission_pin'):
        require_pin(entitlement[key])
    need(entitlement['panel_key']==fit['panel_key'] and entitlement['query_id']==view['id']
         and entitlement['view_pin']==pin(view) and view['id'] in fit['pending_query_ids'],
         'same active fitted panel/query/view')
    need(view['history_schedule_pin']==fit['history_schedule_pin'],'same fitted query-history policy')
    need(type(entitlement['active_obligation']) is str and entitlement['active_obligation'], 'fresh obligation identity')
    need(set(fit['fitted_state'])==set(STRATA),'complete frozen four-head bundle before inference')
    stratum=view['stratum']; need(stratum in STRATA, 'same event head')
    head=fit['fitted_state'][stratum]
    prediction=predict_one(head,[view],limits,budget,entitlement['active_obligation']+'/query')[0]
    persistence=view['persistence_seconds']
    need(persistence is None or finite(persistence)>0, 'eligible history only')
    return {'panel_key':fit['panel_key'],'query_id':view['id'],'stratum':stratum,'prediction':prediction,
            'bundle_state_pin':pin(fit['fitted_state']), 'head_state_pin':pin(head),
            'entitlement_pin':pin(entitlement),
            'diagnostics':{'training_mean_log_seconds':head['model']['target']['mean'],
                'persistence_status':'unavailable_history' if persistence is None else 'available',
                'persistence_log_seconds':None if persistence is None else math.log(persistence)},
            'actual_view_custody_or_process_closure_qualified':False}

def reference_model_record(study, panel_key, panel, fit, source_pin):
    """Assemble the operator model artifact from its actual complete fitted state.

    Full fit-record/selection/source joins are repeated by protected grading;
    this pure assembly function is not a qualification or a transport callback.
    """
    from common import require_pin
    require_pin(source_pin)
    need(panel['actor']=='operator' and fit['panel_key']==panel_key and
         panel['bundle_fit_id']==panel_key+'|final','same operator fitted panel')
    need(set(fit['fitted_state'])==set(STRATA) and fit['selection_pin']==pin(fit['selection']),
         'whole four-head state and exact selection')
    return {'model_id':panel['bundle_fit_id'],'panel_key':panel_key,'source_pin':source_pin,
        'training_animals':panel['training_animals'],'state_pin':pin(fit['fitted_state']),
        'selection_pin':fit['selection_pin'],'feature_schema_pin':study['feature_schema_pin']}

def reference_prediction_panel(study, panel, model_record, final_state, receipts):
    """Join every one-query reference receipt to the same frozen bundle."""
    need(type(receipts) is dict and set(receipts)==set(panel['query_ids']), 'all reference query receipts')
    need(type(final_state) is dict and set(final_state)==set(STRATA) and
         model_record['state_pin']==pin(final_state), 'same complete reference bundle for query assembly')
    query_strata={q['id']:q['stratum'] for q in cohort_queries(study,panel['cohort'],panel['animal'])}
    need(set(receipts)==set(query_strata),'full original query support for reference assembly')
    predictions={}
    for query_id,receipt in receipts.items():
        need(type(receipt) is dict and set(receipt)=={'panel_key','query_id','stratum','prediction','bundle_state_pin',
             'head_state_pin','entitlement_pin','diagnostics','actual_view_custody_or_process_closure_qualified'},
             'exact reference query receipt')
        need(receipt['query_id']==query_id and receipt['panel_key']==model_record['panel_key'] and
             receipt['bundle_state_pin']==model_record['state_pin'],'reference prediction belongs to final bundle')
        stratum=query_strata[query_id]
        need(receipt['stratum']==stratum and receipt['head_state_pin']==pin(final_state[stratum]),
             'reference prediction belongs to exact stratum head')
        from common import require_pin
        require_pin(receipt['head_state_pin']);require_pin(receipt['entitlement_pin'])
        predictions[query_id]=finite(receipt['prediction'])
    return {'panel_key':model_record['panel_key'],'model_id':model_record['model_id'],
        'model_record_pin':pin(model_record),'source_pin':model_record['source_pin'],'predictions':predictions}
