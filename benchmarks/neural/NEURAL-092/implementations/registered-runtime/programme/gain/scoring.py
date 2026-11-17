"""Full-panel prediction admission, actual loss/gain and all15 matched contrasts."""
from array import array
from bisect import bisect_right
from itertools import combinations
import hashlib,math
from .authority import require_live
from .constants import AREAS,MODELS,MATCH_BINS,CONTRASTS
from .features import validate_counts
from .solver import frozen_deviance

def admit_prediction(value,meta,info):
    if type(value)is not dict or set(value)!={'session_id','unit_ids','query_ids','means'}:raise ValueError('closed candidate prediction carrier')
    if value['session_id']!=meta['session_id']or value['unit_ids']!=list(info['unit_ids'])or value['query_ids']!=[r['id']for r in info['rows']['QUERY']]:raise ValueError('complete original prediction axes')
    x=value['means'];n=len(info['rows']['QUERY'])*len(info['unit_ids'])
    if type(x)is not array or x.typecode!='d'or x.itemsize!=8 or len(x)!=n or any(not math.isfinite(v)or v<=0 for v in x):raise ValueError('all positive finite float64 query means; no clipping/drop')
    return x

def matched_indices(meta,pair):
    # Exact source-defined bins/hash ordering, implemented without NumPy.
    groups={};indices={uid:i for i,uid in enumerate(meta['unit_ids'])}
    for row in meta['unit_metadata']:
        if row['area']not in pair:continue
        key=tuple(bisect_right(bounds,row[name])for name,bounds in MATCH_BINS.items())
        groups.setdefault(key,{a:[]for a in pair})[row['area']].append(row['unit_id'])
    selected={a:[]for a in pair};strata=[];unmatched=[]
    for key in sorted(groups):
        order=lambda uid:(hashlib.sha256(uid.encode('utf8')).hexdigest(),uid)
        values={a:sorted(groups[key][a],key=order)for a in pair};count=min(len(values[a])for a in pair)
        for a in pair:
            selected[a].extend(indices[uid]for uid in values[a][:count]);unmatched.extend(values[a][count:])
        strata.append({'bin_indices':key,'counts':{a:len(values[a])for a in pair},'selected_per_area':count})
    return selected,{'strata':strata,'unmatched_unit_ids':sorted(unmatched),'selected_unit_ids':{a:[meta['unit_ids'][j]for j in selected[a]]for a in pair},'source':'FIT/QC only; bisect_right; SHA256 then ID'}

def mean(values):
    if not values or any(v is None for v in values):return None
    value=sum(values)/len(values)
    if not math.isfinite(value):raise ArithmeticError('aggregate overflow; no clipping')
    return value

def difference(left,right):
    if left is None or right is None:return None
    value=left-right
    if not math.isfinite(value):raise ArithmeticError('pair difference overflow; no clipping')
    return value

def score_session(meta,reference,candidate,query_counts,host,calls):
    require_live(host,'score genuine frozen complete query predictions')
    if not reference.complete:raise ValueError('failed fixed reference cannot establish candidate improvement')
    info=reference.info;nr=len(info['rows']['QUERY']);u=len(info['unit_ids']);validate_counts(query_counts,nr,u)
    # Candidate must already have been admitted for the entire32-panel before
    # the host opens any targets. Revalidate these borrowed frozen axes locally.
    cp=admit_prediction(candidate,meta,info)
    pred={**reference.predictions,'candidate':cp}
    for model,values in pred.items():
        if type(values)is not array or values.typecode!='d'or len(values)!=nr*u or any(not math.isfinite(v)or v<=0 for v in values):raise ValueError('all frozen fixed/candidate predictions complete')
    losses={model:[frozen_deviance(query_counts,values,nr,u,j,host,calls)for j in range(u)]for model,values in pred.items()}
    out={};pairs=tuple(combinations(AREAS,2));matching={a+'|'+b:matched_indices(meta,(a,b))for a,b in pairs}
    for name,(left,right)in CONTRASTS.items():
        missing=name=='pupil_conditional_sensitivity'and not info['pupil_supported']
        gains=[None if missing else losses[left][j]-losses[right][j]for j in range(u)]
        if any(v is not None and not math.isfinite(v)for v in gains):raise ArithmeticError('gain overflow')
        areas={a:mean([gains[j]for j in range(u)if meta['areas'][j]==a])for a in AREAS}
        pair_values={};matched_values={};support={}
        for a,b in pairs:
            key=a+'|'+b;pair_values[key]=difference(areas[a],areas[b])
            selected,evidence=matching[key];la=mean([gains[j]for j in selected[a]]);lb=mean([gains[j]for j in selected[b]])
            matched_values[key]=difference(la,lb);support[key]=evidence
        out[name]={'unit_gains':gains,'areas':areas,'session_mean':mean([v for v in areas.values()if v is not None]),
          'area_pairs':pair_values,'matched_area_pairs':matched_values,'matched_support':support,
          'pupil_attribution_available':not missing,'missing_pupil_disposition':'unavailable_pupil_information'if missing else None}
    return {'session_id':meta['session_id'],'mouse_id':meta['mouse_id'],'losses':losses,'contrasts':out,
      'unknown_FIT_conditions':info['unknown_conditions'],'query_rows':nr,'units':u,'causal_effect_identified':False}

def aggregate_panel(sessions,expected_session_to_mouse):
    if len(expected_session_to_mouse)!=32 or len(set(expected_session_to_mouse.values()))!=32 or set(sessions)!=set(expected_session_to_mouse):raise ValueError('exact full32 mouse panel')
    output={}
    for name in CONTRASTS:
        groups={}
        for sid,row in sessions.items():
            mouse=expected_session_to_mouse[sid]
            if row['mouse_id']!=mouse:raise ValueError('original animal identity')
            groups.setdefault(mouse,[]).append(row['contrasts'][name]['session_mean'])
        mice={m:mean(v)for m,v in groups.items()}
        output[name]={'mouse_values':mice,'full_panel_mean':mean(list(mice.values())),
          'undefined_mice':[m for m,v in mice.items()if v is None],
          'area_vectors':{a:{sid:s['contrasts'][name]['areas'][a]for sid,s in sessions.items()}for a in AREAS},
          'weighting':'same-support units -> available fixed areas -> required sessions/mouse -> all required mice',
          'confirmatory_significance':None}
    return {'task_id':'NEURAL-092','condition':'held_out_same_unit_prediction','sessions':sessions,'aggregate':output,
      'new_mouse_transfer':False,'causal_interpretation':False,'reference_competence_measured':False,'qualified':False}
