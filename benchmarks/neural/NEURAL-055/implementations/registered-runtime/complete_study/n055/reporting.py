"""Real complete paired descriptive inference, invoked only beyond protected safety.

No scientific operation in this module is executed by BUILD ONLY controls.
"""
import math
from .common import require
from .registry import PEOPLE,token,VALID

METRICS=('assignment_accuracy','independent_accuracy','NLL','Brier','Top5','assignment_minus_independent')
RUBRIC=('estimand_and_access','training_selection_calibration','paired_quantitative_evidence','control_interpretation',
        'uncertainty_failure_multiplicity','reproducible_supported_limitations')

def extended(value):
    if value is None:return {'status':'undefined','reason':'infinite_minus_infinite'}
    if math.isinf(value):return {'status':'positive_infinity' if value>0 else 'negative_infinity','value':None}
    require(math.isfinite(value),'no NaN scientific serialization')
    return {'status':'finite','value':float(value)}

def difference(a,b):
    return None if math.isinf(a) and math.isinf(b) and a==b else a-b

def mean(values):
    return math.fsum(values)/len(values)

def query_outcomes(case,prediction,target):
    """Target-private rows, in original CASE query order. Never public output."""
    qindex={x:i for i,x in enumerate(prediction['query_ids'])};cindex={x:i for i,x in enumerate(prediction['candidate_ids'])}
    require(set(target['query_to_candidate'])==set(case['query_ids']),'full protected target join')
    result={m:[] for m in METRICS};zeros=0
    for query in case['query_ids']:
        i=qindex[query];truth=target['query_to_candidate'][query];probs=prediction['probabilities'][i]
        order=sorted(case['candidate_ids'],key=lambda c:(-probs[cindex[c]],case['candidate_ids'].index(c)))
        a=int(prediction['assignment'][i]==truth);u=int(order[0]==truth);p=probs[cindex[truth]]
        nll=math.inf if p==0 else -math.log(p);zeros+=int(p==0)
        result['assignment_accuracy'].append(a);result['independent_accuracy'].append(u);result['NLL'].append(nll)
        result['Brier'].append(math.fsum((probs[cindex[c]]-int(c==truth))**2 for c in case['candidate_ids']))
        result['Top5'].append(int(truth in order[:5]));result['assignment_minus_independent'].append(a-u)
    return {'query_ids':case['query_ids'],'metrics':result,'zero_true_probabilities':zeros}

def condition_key(cell):
    return (cell['evaluated_system'],cell['mode'],cell['tool_setting'],cell['arm'])

def complete_conditions(expected,terminals,outcomes,pairing):
    grouped={}
    for cell in expected:grouped.setdefault(condition_key(cell),{}).setdefault(cell['outer_person'],[]).append(cell)
    values={};missing={}
    for group,persons in grouped.items():
        require(set(persons)==set(PEOPLE),'full all-ten condition support')
        result={m:[] for m in METRICS};unavailable=[]
        for person in PEOPLE:
            cs=persons[person];rows=[]
            for c in cs:
                ident=token(c);t=terminals[ident]
                if t['status'] not in VALID or ident not in outcomes:
                    unavailable.append({'cell':c,'status':t['status']});continue
                row=outcomes[ident];case=t['public_case_identity'];order=pairing['query_order'][case]
                require(len(order)==200 and set(order)==set(row['query_ids']) and len(set(order))==200,'exact qualified common-image order')
                indices={q:i for i,q in enumerate(row['query_ids'])}
                rows.append({m:[row['metrics'][m][indices[q]] for q in order] for m in METRICS})
            if len(rows)!=len(cs):continue
            for m in METRICS:result[m].append([mean([r[m][i] for r in rows]) for i in range(200)])
        if unavailable:
            missing[group]={'status':'unavailable','required_cells':sum(map(len,persons.values())),'missing':unavailable}
        else:
            require(all(len(result[m])==10 and all(len(row)==200 for row in result[m]) for m in METRICS),'full replicate-averaged10x200')
            values[group]=result
    return values,missing

def schedules_check(schedule):
    require(schedule['schema']=='neural055-shared-paired-schedules-v1' and schedule['draws']==10000,'full frozen10000 schedules')
    for name,n in [('people',10),('images',200)]:
        require(len(schedule[name])==10000,'all schedule rows')
        require(all(type(row)is list and len(row)==n and all(type(i)is int and 0<=i<n for i in row) for row in schedule[name]),'original complete paired draw indices')

def bootstraps(tensors,schedule,guard):
    """All requested finite endpoints share one pair of resampling matrices."""
    import numpy as np
    schedules_check(schedule);guard('before complete paired bootstrap')
    v=np.asarray(tensors,dtype=np.float64);require(v.ndim==3 and v.shape[1:]==(10,200) and np.isfinite(v).all(),'finite full outcome tensor')
    pw=np.asarray([np.bincount(row,minlength=10)/10 for row in schedule['people']],dtype=np.float64)
    iw=np.asarray([np.bincount(row,minlength=200)/200 for row in schedule['images']],dtype=np.float64)
    person=pw@v.mean(axis=2).T
    crossed=np.zeros((10000,len(v)),dtype=np.float64)
    # Fixed predictions/assignments; no refitting or solving duplicated rows.
    for p in range(10):
        guard('crossed paired person contribution');crossed+=(iw@v[:,p,:].T)*pw[:,p,None]
    guard('after complete paired bootstrap')
    return person,crossed

def quantile(values,p):
    # Explicit linear interpolation; no version-dependent default quantile method.
    ordered=sorted(float(x) for x in values);require(len(ordered)==10000 and all(math.isfinite(x) for x in ordered),'complete finite schedule support')
    position=(len(ordered)-1)*p;lo=math.floor(position);hi=math.ceil(position)
    return ordered[lo]+(position-lo)*(ordered[hi]-ordered[lo])

def intervals(point,person,crossed):
    return {'point':extended(point),'person':{'percentile_2_5':quantile(person,.025),'percentile_97_5':quantile(person,.975),'valid_draws':10000},
            'crossed_person_image':{'percentile_2_5':quantile(crossed,.025),'percentile_97_5':quantile(crossed,.975),'valid_draws':10000},
            'interpretation':'conditional sensitivity of fixed outputs; no population or validated familywise coverage claim'}

def contrast_terms(row,system,metric='assignment_accuracy'):
    s=row['setting'];kind=row['kind']
    def candidate(mode,tool,arm='FULL'):return ((system,mode,tool,arm),metric)
    if kind=='investigation_minus_fixed':return candidate('I',s['tool']),candidate('F',s['tool'])
    if kind=='tool_benefit':return candidate(s['mode'],'T1'),candidate(s['mode'],'T0')
    if kind=='candidate_minus_learned_reference':return candidate(row['left']['mode'],row['left']['tool']),((row['right'],'REFERENCE','REFERENCE','FULL'),metric)
    if kind=='full_minus_control':return candidate(s['mode'],s['tool']),candidate(s['mode'],s['tool'],row['right'])
    require(kind=='assignment_minus_independent','declared full32 contrast kind')
    return ((system,s['mode'],s['tool'],'FULL'),'assignment_accuracy'),((system,s['mode'],s['tool'],'FULL'),'independent_accuracy')

def interpretation(records):
    result={}
    for comparison in ('C01','C02','C03','C04'):
        r=records.get(comparison)
        if r is None:result[comparison]={'status':'unavailable','reason':'missing_interpretation_evidence'};continue
        require(set(r['initial'])=={'reviewer_1','reviewer_2'} and r['blinded_to_system'] is True,'two original blinded reviewer records')
        for value in r['initial'].values():
            require(set(value['scores'])==set(RUBRIC) and all(type(s)is int and s in (0,1,2) for s in value['scores'].values()),'all six initial rubric anchors')
        one=r['initial']['reviewer_1']['scores'];two=r['initial']['reviewer_2']['scores'];ad=r.get('adjudication')
        if one!=two and ad is None:
            result[comparison]={'status':'unavailable','reason':'adjudication_missing','initial':r['initial']};continue
        scores=one if ad is None else ad['scores']
        require(set(scores)==set(RUBRIC) and all(type(s)is int and s in (0,1,2) for s in scores.values()),'all adjudicated dimensions')
        if ad is not None:require(type(ad['rationale'])is str and ad['rationale'],'retained adjudication rationale')
        require(type(r['machine_interpretation'])is dict and type(r['scientific_report'])is str and r['scientific_report'],'both interpretation artifacts')
        result[comparison]={'status':'available','initial':r['initial'],'adjudication':ad,'scores':scores,'total_out_of_12':sum(scores.values()),
                            'machine_interpretation':r['machine_interpretation'],'scientific_report':r['scientific_report'],'separate_from_identification_accuracy':True}
    return result

def paired_report(system,expected,terminals,outcomes,pairing,schedule,contrast_registry,interpretation_records,guard):
    guard('paired scientific report entry');values,missing=complete_conditions(expected,terminals,outcomes,pairing)
    require(contrast_registry['count']==32 and [r['id'] for r in contrast_registry['contrasts']]==['C%02d'%i for i in range(1,33)],'unchanged full32 family')
    tensor=[];requests=[];reports={};contrasts=[]
    for group,rows in values.items():
        reports[group]={}
        for metric in METRICS:
            v=rows[metric];point=mean([mean(row) for row in v])
            if math.isinf(point):reports[group][metric]={'point':extended(point),'interval_status':'unavailable','reason':'extended_infinite_loss'}
            else:requests.append(('absolute',group,metric,point));tensor.append(v)
    primary_indices=[]
    for row in contrast_registry['contrasts']:
        left,right=contrast_terms(row,system);out={'id':row['id'],'definition':row,'status':'unavailable'};contrasts.append(out)
        if left[0] not in values or right[0] not in values:
            out['reason']='required_complete_condition_unavailable';continue
        a=values[left[0]][left[1]];b=values[right[0]][right[1]]
        v=[[a[p][q]-b[p][q] for q in range(200)] for p in range(10)]
        point=mean([mean(r) for r in v]);out['status']='available'
        primary_indices.append(len(tensor));requests.append(('contrast',out,None,point));tensor.append(v)
        if row['kind']!='assignment_minus_independent':
            out['exploratory_secondary']={}
            for metric in ('independent_accuracy','NLL','Brier','Top5'):
                av=values[left[0]][metric];bv=values[right[0]][metric]
                delta=difference(mean([mean(r) for r in av]),mean([mean(r) for r in bv]))
                secondary={'point':extended(delta),'favorable_direction':'negative; lower loss' if metric in ('NLL','Brier') else 'positive; higher accuracy','exploratory':True}
                out['exploratory_secondary'][metric]=secondary
                if delta is None or math.isinf(delta):
                    secondary['interval_status']='unavailable_extended_or_undefined_loss'
                else:
                    nv=[[av[p][q]-bv[p][q] for q in range(200)] for p in range(10)]
                    requests.append(('secondary',out,metric,delta));tensor.append(nv)
    if tensor:
        pdraw,idraw=bootstraps(tensor,schedule,guard)
        for i,(kind,key,metric,point) in enumerate(requests):
            result=intervals(point,pdraw[:,i],idraw[:,i])
            if kind=='absolute':reports[key][metric]=result
            elif kind=='secondary':key['exploratory_secondary'][metric]['paired']=result
            else:key['paired']=result
        if len(primary_indices)==32:
            for name,draws in [('person',pdraw),('crossed_person_image',idraw)]:
                deviations=[max(abs(float(draws[d,i])-requests[i][3]) for i in primary_indices) for d in range(10000)]
                q=quantile(deviations,.95)
                for i in primary_indices:
                    out=requests[i][1];point=requests[i][3]
                    out.setdefault('joint_conditional_band',{})[name]={'lower':max(-1.,point-q),'upper':min(1.,point+q),'full_family':32,'quantile':q,'validated_familywise_coverage':False}
    if len(primary_indices)!=32:
        for row in contrasts:row['joint_conditional_band']={'status':'unavailable','reason':'at_least_one_required_member_of_full32_family_unavailable'}
    guard('after full paired scientific report')
    return {'schema':'neural055-complete-paired-report-v1','conditions':[{'key':list(k),'metrics':v} for k,v in reports.items()],
            'unavailable_conditions':[{'key':list(k),**v} for k,v in missing.items()],'contrasts':contrasts,
            'interpretation':interpretation(interpretation_records),'schedule_draws':10000,'replicate_aggregation':'mean before paired draws',
            'reference_competence':'separate independent qualification evidence required','whole_paper_noncoverage':True,
            'scientific_qualification_claim':False,'population_pvalues':None,'raw_target_maps_or_per_query_outcomes_public':False}
