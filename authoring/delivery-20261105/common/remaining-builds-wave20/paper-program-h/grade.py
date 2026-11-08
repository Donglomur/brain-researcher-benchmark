"""Private complete-support metrics; no fitter, selection feedback, or reduced cohort."""
import math
from pathlib import Path
from core import DAYS,FAMILIES,NATIVE_FAMILIES,ROLES,VARIANTS,finite,need,model_key
from safe_io import capture,child,new_json,strict


def mean_complete(values):
    return sum(values)/len(values) if values and all(finite(x) for x in values) else None


def classify(rows):
    """One day/window after all seven outer folds, never per-fold rescued BA."""
    need(len(rows)==140 and {r['trial'] for r in rows}==set(range(140)),'All original OOF trials exactly once')
    confusion=[[0,0],[0,0]];support=[0,0];failed=[]
    for r in rows:
        if r.get('label') not in (0,1):failed.append({'trial':r['trial'],'reason':'missing authenticated label'});continue
        support[r['label']]+=1
        if r['status']!='finite' or r.get('prediction') not in (0,1) or not finite(r.get('margin')):failed.append({'trial':r['trial'],'reason':r.get('reason',r['status'])});continue
        confusion[r['label']][r['prediction']]+=1
    recall=[confusion[c][c]/support[c] if support[c] and not any(r['label']==c and r['status']!='finite' for r in rows if r.get('label') in (0,1)) else None for c in (0,1)]
    ba=.5*(recall[0]+recall[1]) if not failed and all(x is not None for x in recall) else None
    strata=[]
    for condition in (11,12,21,22,511,512,521,522):
        group=[r for r in rows if r.get('condition')==condition];target=int(condition in (21,22,521,522))
        support_n=len(group);closed=all(r.get('status')=='finite' and r.get('label')==target for r in group)
        strata.append({'condition':condition,'target_class':target,'support':support_n,'recall':sum(r['prediction']==target for r in group)/support_n if support_n and closed else None,'balanced_accuracy':None,'reason':'Single-target condition: recall/support only'})
    return {'unknown_label_support':sum(r.get('label') not in (0,1) for r in rows),'unknown_condition_support':sum(r.get('condition') not in (11,12,21,22,511,512,521,522) for r in rows),'condition_strata':strata,'confusion':confusion,'class_support':support,'class_recall':recall,'balanced_accuracy':ba,'status':'finite' if ba is not None else 'undefined','failures':failed,'paired_class_support':all(support),'aggregation':'Complete140trial OOF before paired-class BA; no per-odor BA'}


def prospective(index,root,cap,truth_index):
    by={};evidence=[];truth={}
    for entry in truth_index:
        raw=capture(child(root,entry['path']),cap,entry['pin']);value=strict(raw)
        need(value['case']==entry['case'] and len(value['records'])==100,'Complete private truth/query identity')
        from core import identity
        key=identity(entry['case']);need(key not in truth,'One private truth set per original fold')
        truth[key]=value['records']
    for entry in index:
        key=model_key(entry['case'],entry['role'],entry['family']);need(key not in by,'One captured evaluation per complete slot')
        raw=capture(child(root,entry['path']),cap,entry['pin']);p=strict(raw)
        need(p['case']==entry['case'] and p['role']==entry['role'] and p['family']==entry['family'],'Exact private prediction identity')
        by[key]=p;evidence.append(entry)
    summaries=[];animal_means={}
    for role in ROLES:
        for variant in VARIANTS:
            for family in FAMILIES:
                animals=[]
                for animal in range(11):
                    blocks=[]
                    for day in DAYS:
                        for window in range(5):
                            rows=[]
                            for fold in range(7):
                                case={'variant':variant,'animal_ordinal':animal,'day':day,'fold':fold};value=by.get(model_key(case,role,family))
                                selected=[] if value is None else [r for r in value['records'] if r['window']==window]
                                expected=set(range(20*fold,20*fold+20))
                                need(not selected or len(selected)==20 and {r['trial'] for r in selected}==expected,'Complete grouped query membership')
                                from core import identity
                                original=[r for r in truth.get(identity(case),[]) if r['window']==window]
                                original_map={r['trial']:r for r in original}
                                if selected:
                                    for r in selected:
                                        source=original_map.get(r['trial']);need(source is not None and all(r.get(k)==source.get(k) for k in ('opaque_id','trial','window','label','condition')),'Prediction metadata equals independently retained private truth')
                                rows.extend(selected or [{**original_map.get(t,{'trial':t,'window':window,'label':None,'condition':None}),'status':'unstarted','reason':'No independently admitted evaluation'} for t in sorted(expected)])
                            result=classify(rows);blocks.append(result['balanced_accuracy']);summaries.append({'role':role,'variant':variant,'family':family,'animal_ordinal':animal,'day':day,'window':window,**result})
                    value=mean_complete(blocks);animals.append(value)
                animal_means[(role,variant,family)]=animals
    macros=[{'role':key[0],'variant':key[1],'family':key[2],'animal_values':values,'equal_animal_mean':mean_complete(values),'complete':all(v is not None for v in values)} for key,values in animal_means.items()]
    contrasts=[]
    for role in ('A','B'):
        for variant in VARIANTS:
            left=animal_means[(role,variant,'combined')];right=animal_means[('reference',variant,'combined')]
            deltas=[a-b if finite(a) and finite(b) else None for a,b in zip(left,right)];mean=mean_complete(deltas)
            sem=math.sqrt(sum((x-mean)**2 for x in deltas)/10)/math.sqrt(11) if mean is not None else None
            contrasts.append({'role':role,'variant':variant,'primary':variant=='no_smoothing_no_flooring','animal_deltas':deltas,'mean_delta':mean,'descriptive_SEM':sem,'scientific_significance_test':None})
    return {'schema':'h_complete_prospective_metrics_v1','blocks':summaries,'macros':macros,'paired_combined_reference_contrasts':contrasts,'prediction_sources':evidence,'expected_prediction_records':924000,'complete':all(row['complete'] for row in macros),'limitations':['Within-animal held trials; not held-animal generalization','Public original inputs; no unseen-data claim','Combined improvement alone does not establish neural causality','All controls and both variants remain mandatory; no favorable support dropping']}


def native(index,root,cap):
    outputs={};errors=[];macros=[]
    for role in ROLES:
        e=index.get(role)
        if e is None:outputs[role]={};continue
        value=strict(capture(child(root,e['path']),cap,e['pin']))
        slots=value['slots'];need(len(slots)==56868,'All eight families/two variants native dispositions')
        table={}
        for s in slots:
            key=(s['variant'],s['family'],s['animal_ordinal'],s['index']);need(key not in table,'Unique original native scalar slot');table[key]=s
        outputs[role]=table
    reference=outputs['reference']
    # If reference is absent, full expected positions remain provided by the
    # private immutable native roster rather than guessed from a candidate.
    roster=index['slot_roster'];need(len(roster)==56868,'Complete private native slot identity roster')
    for role in ('A','B'):
        groups={}
        for slot in roster:
            key=tuple(slot[k] for k in ('variant','family','animal_ordinal','index'));left=outputs[role].get(key);right=reference.get(key)
            status='incomplete';error=None
            if left is not None and right is not None:
                if left['status']==right['status']=='finite' and finite(left['value']) and finite(right['value']):status='finite';error=abs(left['value']-right['value'])
                elif left['status']==right['status']=='source_undefined' and left.get('undefined_kind')==right.get('undefined_kind'):status='matched_source_undefined'
                else:status='disposition_mismatch'
            row={**slot,'role':role,'status':status,'absolute_error':error,'candidate_status':None if left is None else left['status'],'reference_status':None if right is None else right['status']};errors.append(row)
            groups.setdefault(key[:3],[]).append(row)
        per_family={}
        for (variant,family,animal),rows in sorted(groups.items()):
            closed=all(r['status'] in ('finite','matched_source_undefined') for r in rows);values=[r['absolute_error'] for r in rows if r['status']=='finite']
            item={'role':role,'variant':variant,'family':family,'animal_ordinal':animal,'mean_absolute_error':sum(values)/len(values) if closed and values else None,'finite_pairs':len(values),'source_undefined_pairs':sum(r['status']=='matched_source_undefined' for r in rows),'total_slots':len(rows),'support_closed':closed}
            per_family.setdefault((variant,family),[]).append(item)
        for (variant,family),animals in sorted(per_family.items()):macros.append({'role':role,'variant':variant,'family':family,'animals':animals,'equal_animal_MAE':mean_complete([r['mean_absolute_error'] for r in animals]),'units':'original family units; never combined across families'})
    return {'schema':'h_native_comparison_v1','dispositions':errors,'macros':macros,'complete':all(e['status'] in ('finite','matched_source_undefined') for e in errors),'scientific_qualification':False}


def run(index,root,limits,output):
    p=prospective(index['prospective'],root,limits['max_prediction_bytes'],index['truth']);n=native(index['native'],root,limits['max_native_bytes'])
    out=Path(output);new_json(out/'PROSPECTIVE_METRICS.json',p);new_json(out/'NATIVE_METRICS.json',n)
    result={'schema':'h_complete_private_grade_v1','native_complete':n['complete'],'prospective_complete':p['complete'],'numerical_complete':n['complete'] and p['complete'],'scientific_qualification':False,'no_aggregate_across_native_units':True}
    new_json(out/'RESULT.json',result);return result
