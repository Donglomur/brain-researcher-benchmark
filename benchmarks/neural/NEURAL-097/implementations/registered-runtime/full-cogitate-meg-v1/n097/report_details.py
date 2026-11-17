"""Full matched-person descriptive records and safe aggregate evidence projection."""
import math
from .io import need
from .contract import ARMS,RELEVANCES,DURATIONS,ORIENTATIONS,SEEDS,condition
UNITS={'balanced_accuracy':('fraction','higher'),'legacy_logloss':('natural-log nats per trial','lower'),'balanced_logloss':('class-reweighted natural-log nats','lower'),'balanced_brier':('squared probability','lower')}
FAILURES=('not_started','source_or_contract_refused','missing_artifact','resource_or_io_failure','process_or_worker_failure','invalid_submission','unexpected_controller_failure')

def public_failure(exc,stage):
    """Fixed source-owned reason codes; never release exception text/private paths."""
    name=type(exc).__name__
    code={'Refusal':'source_or_contract_refused','FileNotFoundError':'missing_artifact','OSError':'resource_or_io_failure','MemoryError':'resource_or_io_failure','TimeoutError':'process_or_worker_failure','KeyError':'invalid_submission','ValueError':'invalid_submission','TypeError':'invalid_submission'}.get(name,'unexpected_controller_failure')
    return {'code':code,'stage':stage,'original_exception_type':name if name in ('Refusal','FileNotFoundError','OSError','MemoryError','TimeoutError','KeyError','ValueError','TypeError')else'other'}

def validate_public_failure(value):
    need(type(value)is dict and set(value)=={'code','stage','original_exception_type'}and value['code']in FAILURES and value['stage']in ('preflight','view_preparation','training_queries','collection','grading','interpretation')and value['original_exception_type']in ('none','Refusal','FileNotFoundError','OSError','MemoryError','TimeoutError','KeyError','ValueError','TypeError','other'),'Typed original safe failure classification')
    return value

def person_component(grade,arm,relevance,metric,reference=None):
    if grade is None or grade.get('status')!='complete_descriptive_score':return None,'condition_unavailable'
    source=grade
    if reference is not None:
        source=grade['references'].get(reference)
        if not source or source['status']!='complete':return None,'reference_unavailable'
    people=source['metrics']['persons']
    need(len(people)==33 and {p['person_index']for p in people}==set(range(33)),'Exact all33 matched person metrics')
    out={}
    for p in people:
        item=p['arms'][arm][relevance];cells=item['cells']
        need(len(cells)==9 and {(c['duration'],c['orientation'])for c in cells}=={(d,o)for d in DURATIONS for o in ORIENTATIONS},'All nine original nuisance cells, no omit/renormalize')
        by={(c['duration'],c['orientation']):c for c in cells};support=[]
        for d in DURATIONS:
            for o in ORIENTATIONS:
                c=by[d,o];need(len(c['class_counts'])==2 and all(type(v)is int and v>=0 for v in c['class_counts']),'Exact nonnegative class support')
                support.append(c['class_counts'])
        value=item[metric];need(value is None or type(value)in (int,float)and math.isfinite(value),'Typed finite or unavailable person metric')
        out[p['person_index']]={'value':value,'nine_cell_class_support':support,'status':'available'if value is not None else'unavailable_support'}
    return out,None

def pair_record(row,grades):
    kind=row['kind'];need(kind!='absolute','Only paired contrast records')
    reference=None
    if kind in ('candidate_minus_reference','feature_pair'):
        left=right=grades[condition(row['access'],row['mode'],row['seed'])]
        la=row.get('arm',row.get('left_arm'));ra=row.get('arm',row.get('right_arm'))
        if kind=='candidate_minus_reference':reference=row['reference']
    else:
        left=grades[condition(row['left_access'],row['left_mode'],row['seed'])];right=grades[condition(row['right_access'],row['right_mode'],row['seed'])];la=ra=row['arm']
    l,lr=person_component(left,la,row['relevance'],row['metric']);r,rr=person_component(right,ra,row['relevance'],row['metric'],reference)
    comparable=not any(x=='comparison_scope_or_generation_policy_unqualified'for x in row['unavailable_reasons'])
    persons=[]
    for i in range(33):
        lv=l[i]['value']if l else None;rv=r[i]['value']if r else None
        reason=[x for x in (lr,rr)if x]
        if not comparable:reason.append('comparison_scope_or_generation_policy_unqualified')
        if lv is None or rv is None:reason.append('operand_unavailable_or_missing_support')
        persons.append({'person_index':i,'left':lv,'right':rv,'value':lv-rv if comparable and lv is not None and rv is not None else None,'left_support':l[i]['nine_cell_class_support']if l else None,'right_support':r[i]['nine_cell_class_support']if r else None,'status':'available'if comparable and lv is not None and rv is not None else'unavailable','unavailable_reasons':reason})
    unit,direction=UNITS[row['metric']]
    return {'context':{k:v for k,v in row.items()if k not in ('left','right','value','unavailable_reasons')},'units':unit,'metric_direction':direction,'sign':'left-minus-right','panel_left':row['left'],'panel_right':row['right'],'panel_delta':row['value'],'panel_unavailable_reasons':row['unavailable_reasons'],'persons':persons}

def paired_seed_summaries(pairs,grades):
    from .reporting import comparison_scope,summary
    from .io import canonical
    groups={}
    for pair in pairs:
        context={k:v for k,v in pair['context'].items()if k!='seed'};key=canonical(context).decode();groups.setdefault(key,[]).append(pair)
    out=[]
    for values in groups.values():
        values.sort(key=lambda x:x['context']['seed']);need([x['context']['seed']for x in values]==list(SEEDS),'All three paired-person seed records')
        c={k:v for k,v in values[0]['context'].items()if k!='seed'}
        settings=[(c['access'],c['mode'])]if 'access'in c else[(c['left_access'],c['left_mode']),(c['right_access'],c['right_mode'])]
        comparable=all(comparison_scope(grades[condition(a,m,SEEDS[0])],grades[condition(a,m,s)])for a,m in settings for s in SEEDS)
        people=[]
        for i in range(33):
            need(all(x['persons'][i]['person_index']==i for x in values),'Original fixed person pairing across seeds')
            result=summary([x['persons'][i]['value']for x in values])if comparable else{'mean':None,'min':None,'max':None,'reason':'incomplete_or_incomparable_three_seed_generation_policy'}
            people.append({'person_index':i,**result})
        out.append({'context':c,'persons':people})
    return out

def safe_support(metrics):
    """Lossless compact fixed axes; identical case supports are shared by all arms."""
    people=metrics['persons']
    need(len(people)==33 and {p['person_index']for p in people}==set(range(33))and all(type(p['person_index'])is int for p in people),'All33 fixed support indices')
    people=sorted(people,key=lambda p:p['person_index']);counts={}
    for arm in ARMS:
        rows=[]
        for p in people:
            rr=[]
            for rel in RELEVANCES:
                cells=p['arms'][arm][rel]['cells'];by={(c['duration'],c['orientation']):c for c in cells}
                need(len(cells)==9 and set(by)=={(d,o)for d in DURATIONS for o in ORIENTATIONS},'Complete support grid')
                values=[by[d,o]['class_counts']for d in DURATIONS for o in ORIENTATIONS]
                need(all(len(v)==2 and all(type(n)is int and n>=0 for n in v)for v in values),'Typed complete support counts')
                rr.append(values)
            rows.append(rr)
        counts[arm]=rows
    need(all(v==counts['SIGNAL']for v in counts.values()),'Five matched arms have identical support; cannot prune a differing arm')
    return {'axes':{'person_index':list(range(33)),'relevance':list(RELEVANCES),'duration_orientation':[[d,o]for d in DURATIONS for o in ORIENTATIONS],'class':[0,1]},'identical_for_arms':list(ARMS),'counts':counts['SIGNAL']}

def safe_condition(grade):
    """Complete fixed aggregate attempt classifications/costs, no private joins."""
    need('original_condition_closures'in grade,'Safe report requires original complete attempt dispositions')
    rows=grade['original_condition_closures'];need(len(rows)==330,'All330 safe attempt dispositions')
    attempts=[]
    for r in rows:
        j=r['job'];safe={k:j[k]for k in ('access','mode','seed','person_index','half','arm')}
        safe['status']=r['status'];safe['failure']=validate_public_failure(r['public_failure'])if r['status']!='complete'else None
        resources=r.get('resources');costs=None
        if resources:
            from .custody import RESOURCE_KEYS,numeric
            need(all(set(RESOURCE_KEYS)<=set(v)and all(numeric(v[k])for k in RESOURCE_KEYS)for v in resources),'Original public resource observations')
            additive=('cpu_seconds','wall_seconds','model_input_tokens','model_output_tokens','tool_calls')
            costs={k:sum(v[k]for v in resources)if k in additive else max(v[k]for v in resources)for k in RESOURCE_KEYS}
        safe['observed_resources']=costs;safe['resource_status']='observed'if costs is not None else'unavailable_original_observation'
        attempts.append(safe)
    support=None
    if grade.get('status')=='complete_descriptive_score':
        metrics=grade['metrics'];need(len(metrics['persons'])==33,'All33 support summaries')
        support=safe_support(metrics)
    return {'condition':grade['condition'],'status':grade['status'],'attempts':attempts,'support':support,'grading_failure':validate_public_failure(grade['grading_failure'])if grade.get('grading_failure')else None,'qualification':False}

def safe_references(refs):
    """All absolute reference scores and full fixed support without fitted states."""
    out={}
    for name in ('R0','R1','R2','R3','R4'):
        r=refs[name]
        if r['status']!='complete':
            reason=r.get('reason','reference_unavailable');need(reason in ('reference_not_qualified','reference_unavailable','original_reference_custody_refused'),'Fixed public reference failure code')
            out[name]={'status':r['status'],'metrics':None,'reason':reason};continue
        metrics=r['metrics']
        support=safe_support(metrics)
        out[name]={'status':'complete','seed':97097,'absolute_macro_metrics':metrics['macro'],'support':support,'reference_reuse':'One fixed recipe panel; not independent seed/setting replicates'}
    return out
