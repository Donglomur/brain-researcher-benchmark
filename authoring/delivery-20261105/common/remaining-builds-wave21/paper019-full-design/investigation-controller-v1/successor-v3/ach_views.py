"""Private plan-derived history and minimal training/query view construction."""
import copy
import bisect
from ach_util import need,integer,finite,require_pin,pin,exact_fields

VARIANTS=('B','D','ACh','F')
RETAINED={'B':(),'D':('D',),'ACh':('ACh',),'F':('D','ACh')}

def obligations(core,study,cohort,animal):
    """All four variants for every original eligible query of this held animal.

    Access/reference/null realms use independent instances of this same schedule.
    No candidate supplies its obligation list or target aliases.
    """
    core.get('core','study').validate_study(study)
    rows=core.get('core','study').cohort_queries(study,cohort,animal)
    need(rows,'complete nonempty held animal support')
    result=[]
    for row in rows:
        for ordinal,variant in enumerate(VARIANTS):
            result.append({'id':row['id']+'|'+variant,'query_id':row['id'],
                'target_key':row['target_key'],'session':row['session'],'trial':row['trial'],
                'stratum':row['stratum'],'variant_ordinal':ordinal,
                'observation_end_ns':row['observation_end_ns'],'target_available_ns':row['target_available_ns']})
    return result

def logical_schedules(core,study):
    schedules={}
    for cohort,animals in core.get('core','study').cohort_sets(study).items():
        for animal in animals:
            schedules[cohort+'|'+animal]=core.get('core','history').logical_training_schedule(
                obligations(core,study,cohort,animal),study['sessions'][animal])
    return {'schedules':schedules,'schedule_pin':pin(schedules),'derived_from_study_pin':pin(study),
            'actual_runtime_closure':False}

def validate_feature_manifest(manifest):
    exact_fields(manifest,('schema','features','source_mapping_pin','availability_alias_audit_pin'),
                 'exact independently admitted feature manifest')
    need(manifest['schema']=='ach_permitted_behavior_features_v1','fixed behavior feature protocol')
    for k in ('source_mapping_pin','availability_alias_audit_pin'):require_pin(manifest[k])
    features=manifest['features'];need(type(features) is list and features,'complete ordered features')
    names=set();missing=set()
    for item in features:
        exact_fields(item,('name','kind','operation','field','lag','target_kind','parent_feature'), 'feature operator')
        need(type(item['name']) is str and item['name'] and item['name'] not in names,'unique feature name')
        names.add(item['name']);need(item['kind'] in ('continuous','indicator'),'feature type')
        need(item['operation'] in ('available_field','released_target','missing_indicator'),'source-owned feature operation')
        integer(item['lag']);need(item['lag']<=15,'original maximum15 prior records')
        if item['operation']=='missing_indicator':
            need(item['kind']=='indicator' and item['parent_feature'] in names-{item['name']},
                 'missing indicator follows its declared feature')
            missing.add(item['parent_feature'])
        else:
            need(item['parent_feature'] is None,'value feature has no indicator parent')
            if item['operation']=='released_target':
                need(item['target_kind'] in ('next_ITI','SLRT') and item['lag']>=1 and item['kind']=='continuous',
                     'past released measurement of declared target kind')
            else:need(type(item['field']) is str and item['field'],'independently admitted available field')
    need(all(f['name'] in missing for f in features if f['kind']=='continuous'),
         'every continuous field retains explicit missingness indicator')
    return ['continuous' if f['kind']=='continuous' else 'indicator' for f in features]

def behavior_at(query,field_records,target_records,released,manifest):
    """Construct permitted features from actual private field/clock records.

    Authenticated extraction/alias semantics are admission prerequisites. This
    function enforces the declared causal/target embargo predicates; inherited
    processed neural signals retain the original retrospective interpretation.
    """
    validate_feature_manifest(manifest);values=[];observed=[];by_name={}
    need(type(released) in (set,frozenset,list,tuple),'operator-owned released keys')
    released=set(released);need(query['target_key'] not in released,'current target cannot be released')
    for feature in manifest['features']:
        op=feature['operation'];value=None;seen=False
        if op=='missing_indicator':
            value=int(not by_name[feature['parent_feature']]['observed']);seen=True
        elif op=='available_field':
            key=(query['animal'],query['session'],query['trial']-feature['lag'],feature['field'])
            record=field_records.get(key)
            if record is not None:
                exact_fields(record,('value','observed','available_ns','target_aliases','source_pin'), 'private field record')
                require_pin(record['source_pin']);integer(record['available_ns'])
                need(type(record['observed']) is bool and type(record['target_aliases']) is list,'field observation/alias status')
                # Target-equivalent fields are never ordinary behavior operands;
                # only the explicit released_target operator can expose outcomes.
                need(not record['target_aliases'],'target-equivalent field requires released-target operator')
                if record['observed'] and record['available_ns']<=query['observation_end_ns']:
                    value=finite(record['value']);seen=True
        else:
            eligible=[]
            for key,record in target_records.items():
                if key not in released:continue
                if (record['animal'],record['session'],record['kind'])!=(query['animal'],query['session'],feature['target_kind']):continue
                need(record['available_ns']<=query['observation_end_ns'],'released target physically available')
                eligible.append((record['trial'],record['available_ns'],key,record))
            eligible.sort(key=lambda x:x[:3],reverse=True)
            if len(eligible)>=feature['lag']:
                value=finite(eligible[feature['lag']-1][3]['seconds']);need(value>0,'positive released history');seen=True
        if feature['kind']=='indicator':need(seen and value in (0,1),'complete literal indicator domain')
        values.append(value);observed.append(seen);by_name[feature['name']]={'value':value,'observed':seen}
    return values,observed

def window_epoch(epoch,stratum):
    """Only permitted window samples, retaining its piecewise-linear trace.

    Boundary interpolation matches captured reference-math/core.py's `at`.
    Bracketing source points remain private; this is retrospective processing,
    not a claim that filtered signals were available prospectively.
    """
    if epoch is None:return None
    exact_fields(epoch,('times','values'),'exact source epoch')
    t,y=epoch['times'],epoch['values']
    need(type(t) is list and type(y) is list and len(t)==len(y)>=2,'paired source times/values')
    t=[finite(x) for x in t];y=[finite(x) for x in y]
    need(all(a<b for a,b in zip(t,t[1:])),'strict sample chronology')
    need(stratum in ('offer_CPIn','reward_SideOff','side_on','opt_out'),'accepted event window')
    lo,hi=(-.3,.2) if stratum=='opt_out' else (-.1,.5)
    need(t[0]<=lo and t[-1]>=hi,'no extrapolated candidate signal')
    def at(x):
        j=bisect.bisect_left(t,x)
        if j<len(t) and t[j]==x:return y[j]
        need(0<j<len(t),'bracketed endpoint')
        delta=finite(x-t[j-1]);span=finite(t[j]-t[j-1]);fraction=finite(delta/span)
        need(fraction!=0 or delta==0,'interpolation quotient underflow')
        slope=finite(y[j]-y[j-1]);product=finite(fraction*slope)
        need(product!=0 or fraction==0 or slope==0,'interpolation product underflow')
        return finite(y[j-1]+product)
    a,b=bisect.bisect_right(t,lo),bisect.bisect_left(t,hi)
    return {'times':[lo]+t[a:b]+[hi],'values':[at(lo)]+y[a:b]+[at(hi)]}

def minimal_row(row,variant,public_id,*,training,animal_alias=None,session_alias=None):
    """Physical candidate payload; original paths/clock/target aliases absent."""
    need(variant in VARIANTS and type(public_id) is str and public_id,'exact variant and independent public alias')
    # Do not even inspect withdrawn neural arrays. Retained channels expose the
    # complete accepted window, not the source epoch's out-of-window samples.
    epochs={name:window_epoch(row['epochs'][name],row['stratum']) if name in RETAINED[variant] else None
            for name in ('D','ACh')}
    out={'id':public_id,'stratum':row['stratum'],'behavior':list(row['behavior']),
        'behavior_observed':list(row['behavior_observed']),'epochs':epochs,
        'channel_mask':list(row['channel_mask']),'withheld_channels':[x for x in ('D','ACh') if x not in RETAINED[variant]],
        'persistence_seconds':row['persistence_seconds']}
    if training:
        need(type(animal_alias) is str and type(session_alias) is str,'permitted training group aliases')
        out.update(animal=animal_alias,session=session_alias,seconds=finite(row['seconds']))
    return out

def training_view(core,study,rows,spec,aliases):
    """Only the full specified fitting partition, in exactly one modality arm."""
    selected=[q for q in core.get('core','study').cohort_queries(study,spec['cohort'])
              if q['animal'] in spec['training_animals']]
    need(set(rows)=={q['id'] for q in selected},'exact complete fitting view; no held or omitted row')
    exact_fields(aliases,('rows','animals','sessions'),'complete private alias namespaces')
    need(set(aliases['rows'])==set(rows),'all fresh public row aliases')
    need(set(aliases['animals'])=={r['animal'] for r in rows.values()} and
         set(aliases['sessions'])=={r['animal']+'|'+r['session'] for r in rows.values()},'exact distinct biological/session alias keys')
    alias_values=[v for mapping in aliases.values() for v in mapping.values()]
    need(all(type(v) is str and v for v in alias_values) and len(alias_values)==len(set(alias_values)),
         'bijective disjoint private/public alias mapping before staging')
    result=[]
    for q in selected:
        row=rows[q['id']]
        result.append(minimal_row(row,spec['variant'],aliases['rows'][q['id']],training=True,
            animal_alias=aliases['animals'][q['animal']],session_alias=aliases['sessions'][q['animal']+'|'+q['session']]))
    return {'schema':'ach_training_view_v1','rows':result,'variant':spec['variant'],
        'strata':list(core.get('core','common').STRATA),'inner_metric_interpretation':'adaptive_selection_diagnostics',
        'history_policy_pin':study['admission_evidence']['logical_history']}

def materialize_private_rows(core,study,private,manifest,cohort):
    """Fixed complete-success histories for fitting and source-owned row values.

    These private rows must never be passed wholesale to a candidate; training
    partitions and one-query physical views are constructed separately.
    """
    kinds=validate_feature_manifest(manifest)
    need(study['feature_schema_pin']==pin(manifest),'same fixed behavioral feature manifest')
    need(manifest['source_mapping_pin']==private['source_mapping_pin'] and
         manifest['availability_alias_audit_pin']==study['admission_evidence']['target_aliases'],
         'same admitted physical field mapping and target-alias audit')
    all_schedules=logical_schedules(core,study)
    need(study['admission_evidence']['logical_history']==all_schedules['schedule_pin'],
         'source-derived complete logical training schedule, no outcome-dependent history')
    expected={q['id']:q for q in core.get('core','study').cohort_queries(study,cohort)};result={}
    for animal in core.get('core','study').cohort_sets(study)[cohort]:
        schedule=all_schedules['schedules'][cohort+'|'+animal]
        for batch in schedule['batches']:
            released=set(batch['released_target_keys'])
            ids={obligation.rsplit('|',1)[0] for obligation in batch['obligation_ids']}
            for qid in ids:
                q=expected[qid]
                values,observed=behavior_at(q,private['fields'],private['targets'],released,manifest)
                previous=[(r['trial'],r['available_ns'],key,r['seconds']) for key,r in private['targets'].items()
                    if key in released and (r['animal'],r['session'],r['kind'])==
                       (q['animal'],q['session'],q['target_kind'])]
                previous.sort(reverse=True)
                row={'id':qid,'animal':q['animal'],'session':q['session'],'stratum':q['stratum'],
                    'seconds':private['targets'][q['target_key']]['seconds'],'behavior':values,'behavior_observed':observed,
                    'epochs':private['epochs'][qid],'channel_mask':list(q['channel_mask']),'grid_pin':q['grid_pin'],
                    'persistence_seconds':previous[0][3] if previous else None,
                    'history_schedule_pin':study['admission_evidence']['logical_history']}
                need(qid not in result or result[qid]==row,'identical tied-variant logical history')
                result[qid]=row
    need(set(result)==set(expected),'complete private row materialization')
    return result,kinds

def runtime_query_row(study,query,private,manifest,released,epochs):
    """Actual closure-driven history; no target value is read for this query."""
    values,observed=behavior_at(query,private['fields'],private['targets'],released,manifest)
    previous=[(r['trial'],r['available_ns'],key,r['seconds']) for key,r in private['targets'].items()
        if key in released and (r['animal'],r['session'],r['kind'])==
           (query['animal'],query['session'],query['target_kind'])]
    previous.sort(reverse=True)
    return {'id':query['id'],'stratum':query['stratum'],'behavior':values,'behavior_observed':observed,
        'epochs':epochs,'channel_mask':list(query['channel_mask']),'grid_pin':query['grid_pin'],
        'history_schedule_pin':study['admission_evidence']['logical_history'],
        'persistence_seconds':previous[0][3] if previous else None}
