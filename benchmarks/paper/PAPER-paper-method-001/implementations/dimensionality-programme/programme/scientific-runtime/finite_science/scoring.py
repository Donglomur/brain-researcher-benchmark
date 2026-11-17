"""Protected metrics with complete denominators; no hidden reference selection."""
import math
from decimal import Decimal,ROUND_HALF_EVEN
from .common import LEVELS,require,result,ScientificGate

INFRA={'timeout','resource_exceeded','process_failure','invalid_artifact','unavailable_source','qualification_required'}

def loss(record,truth):
    require(type(truth) in (int,float) and math.isfinite(truth) and truth>0,'identified positive truth required','unidentified_target')
    value=record.get('gamma');good=record.get('status')=='ok' and type(value) in (int,float) and math.isfinite(value) and value>0
    error=(math.log(value)-math.log(truth))**2 if good else None
    return {'loss':min(error,math.log(256)**2)/math.log(256)**2 if good else 1.,'uncapped_log_squared_error':error,'original_estimate':value,'original_status':record.get('status')}

def point(payload):
    r=payload['request'];return result(loss(r['estimate'],r['truth']),{'denominator':1})

def interval_value(conf,truth,level):
    require(level in LEVELS and type(truth) in (int,float) and math.isfinite(truth) and 1<=truth<=128,'fixed interval support and level')
    fail={'coverage':0.,'normalized_interval_score':1.,'log_width':math.log(128),'topology':'invalid','clipped_components':[]}
    if conf.get('status')!='ok' or conf.get('space') not in ('gamma','log_gamma'):return fail
    spans=conf.get('intervals');
    if not isinstance(spans,list) or not spans:return dict(fail,topology='empty')
    H=math.log(128);z=math.log(truth);clipped=[];last=-math.inf
    for span in spans:
        if not isinstance(span,(list,tuple)) or len(span)!=2:return fail
        lo,hi=span
        if any(v is not None and (type(v) not in (int,float) or not math.isfinite(v)) for v in span):return fail
        lo=-math.inf if lo is None else lo;hi=math.inf if hi is None else hi
        if lo>hi or lo<last:return fail
        last=hi
        if conf['space']=='gamma':
            if hi<1 or lo>128:continue
            lo=math.log(max(1,lo));hi=math.log(min(128,hi))
        else:lo=max(0.,lo);hi=min(H,hi)
        if lo<=hi:clipped.append([lo,hi])
    if not clipped:return dict(fail,topology='empty_intersection')
    coverage=float(any(lo<=z<=hi for lo,hi in clipped));lo=clipped[0][0];hi=clipped[-1][1];alpha=1-level
    score=hi-lo+2/alpha*max(lo-z,0)+2/alpha*max(z-hi,0)
    return dict(coverage=coverage,normalized_interval_score=score/(2*H/alpha),log_width=sum(hi-lo for lo,hi in clipped),hull_width=hi-lo,topology='union' if len(spans)>1 else ('unbounded' if None in spans[0] else 'interval'),clipped_components=clipped)

def interval(payload):
    r=payload['request'];return result(interval_value(r['confidence_set'],r['truth'],r['level']),{'denominator':1})

def rounded(value):return Decimal(str(value)).quantize(Decimal('0.000000000001'),rounding=ROUND_HALF_EVEN)

def select(payload,uncertainty=False):
    r=payload['request'];p=payload['protocol'];expected=r['expected_worlds'];variants=r['variants'];planned=r['expected_variant_ids']
    require(len(expected)==240 and len({x['world_id'] for x in expected})==240,'exact calibration roster')
    cells={x['cell'] for x in expected};require(len(cells)==6 and all(sum(x['cell']==c for x in expected)==40 for c in cells),'six equal forty-world cells')
    require(p.get('selection_stage')=='public_calibration' and p.get('bank_presealed') is True,'presealed public calibration bank')
    require(set(variants)==set(planned) and len(set(planned))==len(planned),'complete variant bank')
    from .catalog import REFERENCE_BANK,PRIMARY_KEYS,UNCERTAINTY_RULES
    key=next((x for x in PRIMARY_KEYS if x['id']==p['primary_key']),None)
    require(key is not None,'primary selection key')
    required={}
    for ref in REFERENCE_BANK:
        if ref['id'] not in key['eligible_reference_ids_before_qualification']:continue
        for variant in ref['variants']:
            point_id=f"{key['id']}/{ref['id']}/{variant}"
            if not uncertainty:required[point_id]=(ref['id'],variant,None,None)
            else:
                for rule,law in UNCERTAINTY_RULES.items():
                    if key['family'] not in law['families'] or key['trial_view'] not in law['views']:continue
                    for scale in ((1,) if rule=='U03_TWO_AXIS_PERCENTILE' else (1,1.25,1.5,2)):
                        required[f'{point_id}/{rule}/{scale}']=(ref['id'],variant,rule,scale)
    require(set(planned)==set(required),'sealed bank differs from complete accepted finite variant expansion')
    require(cells==set(key['cells']),'key calibration cells')
    roster={x['world_id']:x for x in expected};ranking=[];incomplete=[]
    for ident in planned:
        v=variants[ident]
        ref,var,rule,scale=required[ident]
        require(v['key_id']==key['id'] and v['reference_id']==ref and v['variant']==var,'structured point identity')
        if uncertainty:require(v['rule']==rule and v['scale']==scale,'structured uncertainty identity')
        records=v['records'];by={x['world_id']:x for x in records}
        require(len(by)==len(records) and set(by)==set(roster),'full calibration records per variant')
        if not v.get('qualification_id') or not v.get('source_sha256') or not v.get('state_id'):incomplete.append(ident)
        for w,row in by.items():
            require(row['cell']==roster[w]['cell'] and row['input_identity']==roster[w]['input_identity'],'calibration identity join')
            require(row['source_sha256']==v['source_sha256'] and row['state_id']==v['state_id'] and row['variant_id']==ident,'fixed reference source/state/variant across calibration worlds')
            if row['status'] in INFRA:incomplete.append(ident)
        if uncertainty:
            scores=[];cover={c:[] for c in LEVELS};percell={c:{k:[] for k in cells} for c in LEVELS}
            weights=[(1-c)/2 for c in LEVELS]
            for w in roster:
                row=by[w];ss=[]
                for c in LEVELS:
                    m=interval_value(row.get('sets',{}).get(str(c),{}),roster[w]['truth'],c);ss.append(m['normalized_interval_score']);cover[c].append(m['coverage']);percell[c][row['cell']].append(m['coverage'])
                scores.append(sum(a*b for a,b in zip(weights,ss))/sum(weights))
            objective=math.fsum(scores)/240
            eligible=all(abs(math.fsum(cover[c])/240-c)<=.03+1e-12 and all(math.fsum(percell[c][k])/40>=c-.10-1e-12 for k in cells) for c in LEVELS)
        else:objective=math.fsum(loss(by[w],roster[w]['truth'])['loss'] for w in roster)/240;eligible=True
        ranking.append(dict(variant_id=ident,objective=objective,eligible=eligible,source_sha256=v['source_sha256']))
    ranking.sort(key=lambda x:(rounded(x['objective']),x['variant_id'].encode('utf8'),x['source_sha256']))
    candidates=[x for x in ranking if x['eligible']]
    selected=None if incomplete or not candidates else candidates[0]['variant_id']
    status='INCOMPLETE_REFERENCE_BANK' if incomplete else ('ok' if selected else ('NO_CALIBRATION_QUALIFIED_UNCERTAINTY_REFERENCE' if uncertainty else 'NO_ELIGIBLE_COMPETENT_REFERENCE'))
    return result({'selected_id':selected,'ranking':ranking},dict(worlds=240,variants=len(planned),incomplete_variants=sorted(set(incomplete))),status=status)

def select_point(payload):return select(payload)
def select_uncertainty(payload):return select(payload,True)

def holm(pvalues):
    order=sorted(range(len(pvalues)),key=lambda k:pvalues[k]);out=[None]*len(order);last=0.
    for rank,k in enumerate(order):last=max(last,min(1.,pvalues[k]*(len(order)-rank)));out[k]=last
    return out

def paired(payload, access=False):
    import numpy as np
    r=payload['request'];p=payload['protocol'];roster=r['expected_cases'];records=r['records'];by={x['case_id']:x for x in records}
    require(len(roster)==28800 and len({x['case_id'] for x in roster})==len(roster) and len(by)==len(records) and set(by)=={x['case_id'] for x in roster},'complete unique paired case roster')
    require(p.get('score_stage')=='target_last' and p.get('paired_states_sealed') is True,'target-last sealed paired states')
    worlds={};blocked=[]
    for case in roster:
        row=by[case['case_id']]
        for key in ('world_id','family','cell','view','input_identity','target_identity'):
            require(row[key]==case[key],'paired '+key+' mismatch')
        for key in ('candidate_state_id','candidate_source_sha256','reference_state_id','reference_variant_id','reference_source_sha256'):
            require(row[key]==case[key],'fixed selected evaluation identity '+key)
        if not access and (row['reference']['status'] in INFRA or row['reference']['status']!='ok'):blocked.append(row['case_id'])
        candidate=loss(row['candidate'],case['truth'])['loss'];reference=loss(row['reference'],case['truth'])['loss']
        key=(row['family'],row['cell'],row['world_id']);worlds.setdefault(key,[]).append((row['view'],candidate,reference))
    require(len(worlds)==14400,'all 14400 worlds required')
    grouped={}
    for (family,cell,world),values in worlds.items():
        require(sorted(x[0] for x in values)==[2,4],'exact dependent T2/T4 pair')
        grouped.setdefault((family,cell),[]).append([sum(x[1] for x in values)/2,sum(x[2] for x in values)/2])
    require(len(grouped)==72 and all(len(x)==200 for x in grouped.values()),'72 cells x200 worlds')
    families=sorted({k[0] for k in grouped});require(len(families)==12,'twelve family units')
    cells=sorted(grouped);data=np.asarray([grouped[k] for k in cells]);mean=data.mean(axis=(0,1));difference=float(mean[0]-mean[1]);relative=1-float(mean[0]/mean[1]) if mean[1]>0 else None
    # Paired stratified world bootstrap: each draw keeps views averaged and
    # resamples independent worlds within each fixed cell, never flattened views.
    seeds=r['bootstrap_seeds'];require(len(seeds)>=999 and len(set(seeds))==len(seeds),'presealed world-bootstrap seeds')
    rel=[];fd=[];absolute_samples=[]
    for seed in seeds:
        rng=np.random.default_rng(seed);sample=np.stack([data[k,rng.integers(200,size=200)] for k in range(72)]);m=sample.mean(axis=(0,1))
        rel.append(1-m[0]/m[1] if m[1]>0 else np.nan);absolute_samples.append(float(m[0]-m[1]))
        fd.append([sample[[k for k,c in enumerate(cells) if c[0]==f]].mean(axis=(0,1))[0]-sample[[k for k,c in enumerate(cells) if c[0]==f]].mean(axis=(0,1))[1] for f in families])
    lb=float(np.quantile(rel,.05)) if np.isfinite(rel).all() else None
    # Bonferroni simultaneous 95% one-sided family upper bounds, no re-selection.
    upper=np.quantile(np.asarray(fd),1-.05/12,axis=0).tolist()
    qualified=not blocked and p.get('inference_qualification_id') is not None
    claim=qualified and relative is not None and lb is not None and lb>.05 and all(x<=.02 for x in upper)
    if access:
        return result({'arm_B_risk':float(mean[0]),'arm_A_risk':float(mean[1]),'B_minus_A_absolute_risk':difference,'B_minus_A_two_sided95':np.quantile(absolute_samples,[.025,.975]).tolist(),'relative_B_risk_reduction':relative,'paired_lower95_relative':lb,'family_B_minus_A_upper_simultaneous95':dict(zip(families,upper))},dict(worlds=14400,views=28800,blocked_arm_cases=blocked,bootstrap_draws=len(seeds)),['Direct code-access effect, separate from candidate-versus-reference improvement.'],status='ok' if qualified else 'qualification_required')
    return result({'candidate_risk':float(mean[0]),'reference_risk':float(mean[1]),'absolute_difference':difference,'relative_improvement':relative,'relative_lower95':lb,'family_increase_upper_simultaneous95':dict(zip(families,upper)),'meaningful_improvement':bool(claim)},dict(cells=72,worlds=14400,views=28800,blocked_reference_cases=blocked,bootstrap_draws=len(seeds)),['World-stratified bootstrap requires separate empirical inference qualification.'],status='ok' if qualified else 'qualification_required')

def reproduction(payload):
    r=payload['request'];p=payload['protocol'];require(p.get('tolerance_qualification_id'),'independent floating-point qualification required','qualification_required')
    expected=r['expected_ids'];require(expected and r['field_tolerances'],'nonempty qualified reproduction contract required','qualification_required');actual={x['id']:x for x in r['actual']};reference={x['id']:x for x in r['reference']}
    require(set(actual)==set(reference)==set(expected) and len(actual)==len(r['actual']) and len(reference)==len(r['reference']),'full reproduction output membership')
    rows=[]
    for ident in expected:
        a,b=actual[ident],reference[ident];fields={}
        require(a['version']==b['version'] and a['target_identity']==b['target_identity'],'literal/corrected/legacy target mismatch')
        for key,tol in r['field_tolerances'].items():
            av=a.get(key);bv=b.get(key)
            ok=(av is None and bv is None and a['status']==b['status']) if bv is None else (type(av) in (int,float) and math.isfinite(av) and abs(av-bv)<=tol['absolute']+tol['relative']*abs(bv))
            fields[key]={'matched':bool(ok),'absolute_error':abs(av-bv) if type(av) in (int,float) and type(bv) in (int,float) else None}
        rows.append({'id':ident,'fields':fields,'status_match':a['status']==b['status']})
    return result({'comparisons':rows,'matched':all(x['status_match'] and all(y['matched'] for y in x['fields'].values()) for x in rows)},dict(planned=len(expected),retained=len(rows)))

def curves(payload):
    import numpy as np
    r=payload['request'];records=r['records'];require(len(records)==r['planned_draws'],'no omitted draws')
    require(type(r['planned_draws']) is int and r['planned_draws']>0,'nonempty homogeneous draw plan')
    good=all(x['status']=='ok' and all(type(x.get(k)) in (int,float) and math.isfinite(x[k]) for k in ('A','B','gamma')) for x in records)
    if not good:return result({'mean_ratio':None,'ratio_of_means':None,'raw_records':records},dict(planned=len(records),valid=sum(x['status']=='ok' for x in records)),status='insufficient_support')
    ratios=np.asarray([x['gamma'] for x in records]);A=np.asarray([x['A'] for x in records]);B=np.asarray([x['B'] for x in records]);den=float(B.mean())
    return result({'mean_ratio':float(ratios.mean()),'ratio_of_means':float(A.mean()/den) if den else None,'conditional_mc_sd':float(ratios.std(ddof=1)) if len(records)>1 else None,'raw_records':records},dict(planned=len(records),valid=len(records),unit=r['unit']),['Conditional subsample SD is not population uncertainty or biological truth.'])


def access_effect(payload):
    r=payload["request"];rows=[];expected=[]
    def binding(row):
        return dict(row,candidate_state_id=row['arm_B_state_id'],candidate_source_sha256=row['arm_B_source_sha256'],reference_state_id=row['arm_A_state_id'],reference_source_sha256=row['arm_A_source_sha256'],reference_variant_id='paired_arm_A')
    for case in r['expected_cases']:expected.append(binding(case))
    for row in r["records"]:
        rows.append(dict(binding(row),candidate=row["arm_B"],reference=row["arm_A"]))
    return paired(dict(payload,request=dict(r,records=rows,expected_cases=expected)),access=True)


def uncertainty_quality(payload):
    """All evaluation worlds, all four levels, and paired interval-score quality."""
    import numpy as np
    r=payload['request'];p=payload['protocol'];roster=r['expected_cases'];rows=r['records'];by={x['case_id']:x for x in rows}
    require(len(roster)==28800 and len({x['case_id'] for x in roster})==len(roster) and len(by)==len(rows) and set(by)=={x['case_id'] for x in roster},'complete unique uncertainty case roster')
    require(p.get('score_stage')=='target_last' and p.get('paired_states_sealed') is True,'target-last interval score')
    data={};blocked=[];alphaweights=np.asarray([(1-c)/2 for c in LEVELS]);alphaweights/=alphaweights.sum()
    for case in roster:
        row=by[case['case_id']]
        for key in ('world_id','family','cell','view','input_identity','target_identity'):require(row[key]==case[key],'interval paired identity '+key)
        require(all(row[k]==case[k] for k in ('candidate_state_id','candidate_source_sha256','reference_state_id','reference_source_sha256','reference_variant_id')),'frozen interval method/source identity')
        if row['reference_status']!='ok' or any(row.get('reference_sets',{}).get(str(c),{}).get('status')!='ok' for c in LEVELS):blocked.append(row['case_id'])
        cover=[];cs=[];rs=[]
        for level in LEVELS:
            cm=interval_value(row.get('candidate_sets',{}).get(str(level),{}),case['truth'],level)
            rm=interval_value(row.get('reference_sets',{}).get(str(level),{}),case['truth'],level)
            cover.append(cm['coverage']);cs.append(cm['normalized_interval_score']);rs.append(rm['normalized_interval_score'])
        key=(row['family'],row['cell']);data.setdefault(key,{}).setdefault(row['world_id'],{})[row['view']]=cover+[float(np.dot(alphaweights,cs)),float(np.dot(alphaweights,rs))]
    require(len(data)==72 and all(len(v)==200 and all(set(pair)=={2,4} for pair in v.values()) for v in data.values()),'72 cells x200 paired worlds')
    keys=sorted(data);families=sorted({k[0] for k in keys});require(len(families)==12,'all families')
    cube=np.asarray([[ [value[2],value[4]] for value in data[k].values()] for k in keys])
    overall=cube[:,:,:,:4].mean(axis=(0,1,2));candidate=float(cube[:,:,:,4].mean());reference=float(cube[:,:,:,5].mean())
    seeds=r['bootstrap_seeds'];require(len(seeds)>=999 and len(set(seeds))==len(seeds),'sealed world bootstrap')
    lower_samples=[]
    for seed in seeds:
        rng=np.random.default_rng(seed);sample=np.stack([cube[k,rng.integers(200,size=200)] for k in range(72)])
        lower_samples.append([sample[[i for i,k in enumerate(keys) if k[0]==f],:,v,:4].mean(axis=(0,1)) for f in families for v in range(2)])
    # Simultaneous lower bounds over 12 families x2 views x4 levels by Bonferroni.
    lower=np.quantile(np.asarray(lower_samples),.05/(12*2*4),axis=0)
    coverage_ok=all(abs(overall[i]-level)<=.03 for i,level in enumerate(LEVELS)) and all(lower[j,i]>=level-.03 for j in range(24) for i,level in enumerate(LEVELS))
    gain=1-candidate/reference if reference>0 else None
    qualified=not blocked and p.get('inference_qualification_id') is not None
    return result({'coverage_by_level':dict(zip(map(str,LEVELS),overall.tolist())),'simultaneous_lower_by_family_view':{f'{f}-T{v}':lower[2*k+j].tolist() for k,f in enumerate(families) for j,v in enumerate((2,4))},'candidate_interval_score':candidate,'reference_interval_score':reference,'relative_interval_score_improvement':gain,'uncertainty_improvement':bool(qualified and coverage_ok and gain is not None and gain>=.05)},dict(worlds=14400,views=28800,levels=list(LEVELS),blocked_reference_cases=blocked),['World-cluster percentile bounds remain independently qualification-gated.'],status='ok' if qualified else 'qualification_required')


def support_classification(payload):
    r=payload['request'];expected=r['expected_cases'];actual={x['case_id']:x for x in r['records']}
    require(len(actual)==len(r['records']) and set(actual)=={x['case_id'] for x in expected},'support case membership')
    rows=[]
    for case in expected:
        row=actual[case['case_id']];require(row['input_identity']==case['input_identity'],'support input identity')
        allowed=case['allowed_statuses'];matched=row['status'] in allowed and (not case['numeric_truth_identified'] or row.get('gamma') is not None)
        rows.append({'case_id':case['case_id'],'status':row['status'],'correct_disposition':matched,'false_numeric_claim':not case['numeric_truth_identified'] and row.get('gamma') is not None})
    return result({'records':rows,'correct':sum(v['correct_disposition'] and not v['false_numeric_claim'] for v in rows)},dict(planned=len(expected)),['Support classification has no fabricated numeric truth.'])


def transfer(payload):
    """Conditional descriptive summaries; every protected group stays separate."""
    req=payload['request'];p=payload['protocol'];expected=req['expected_group_ids'];groups=req['groups']
    require(p.get('score_stage')=='target_last' and p.get('transfer_group_manifest_admitted') is True,'qualified protected transfer group manifest required','qualification_required')
    require(expected,'empty transfer group roster cannot stand for full scope','qualification_required')
    by={g['group_id']:g for g in groups}
    require(len(by)==len(groups) and len(set(expected))==len(expected) and set(by)==set(expected),'all original transfer groups and conditions required')
    outputs=[]
    for ident in expected:
        group=by[ident];identities=group['identities'];planned=group['planned_draws'];records=group['records']
        require(isinstance(identities,dict) and all(k in identities for k in ('source','animal_or_subject','condition','target_protocol','ROI_or_layer','semantic_family_policy')),'complete protected group identity fields')
        require(len(set(planned))==len(planned) and len({r['id'] for r in records})==len(records) and {r['id'] for r in records}==set(planned),'full conditional draw roster; no omission or duplicate')
        require(group['aggregation'] in ('mean_ratio','ratio_of_means'),'declared group aggregation')
        if not planned:
            summary=result({'mean_ratio':None,'ratio_of_means':None,'raw_records':records},dict(planned=0,valid=0),status='insufficient_support')
        else:
            lookup={r['id']:r for r in records}
            summary=curves(dict(payload,request={'records':[lookup[k] for k in planned],'planned_draws':len(planned),'unit':group['unit']}))
        outputs.append({'group_id':ident,'identities':identities,'unit':group['unit'],'aggregation':group['aggregation'],'selected_descriptive_value':summary['outputs'].get(group['aggregation']),'result':summary,'population_inference':False,'true_dimension_assumed_known':False})
    unsupported=[g['group_id'] for g in outputs if g['result']['status']!='ok']
    return result({'groups':outputs,'cross_group_pooled_estimate':None},dict(planned_groups=len(expected),retained_groups=len(outputs),unsupported_groups=unsupported),['Groups/conditions/languages/layers remain separate.','Sample stability is not accuracy or independently known biological/LLM dimensionality.','No animal/session/sentence population confidence interval is inferred from conditional draw SD.'],status='insufficient_support' if unsupported else 'ok')
