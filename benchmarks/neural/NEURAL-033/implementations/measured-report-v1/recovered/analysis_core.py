"""NEURAL033's prospective rank-interaction estimand; no implicit execution."""
import math

GROUPS = ('apical_control', 'apical_kir', 'basal_control', 'basal_kir')
CONTRASTS = ('apical_kir_minus_control_activity_slope',
             'basal_kir_minus_control_activity_slope', 'apical_minus_basal_slope_difference')

def stable(flag):
    if not isinstance(flag, dict) or set(flag) != {'kind','value'} or flag['kind'] not in ('str','list','tuple'):
        raise ValueError('Typed source flag required')
    value=flag['value']
    if flag['kind']=='str':
        if type(value) is not str: raise ValueError('Source string flag')
    elif type(value) is not list or any(type(x) is not str for x in value):
        raise ValueError('Source sequence flag')
    return not any(x in value for x in ('New Spine','Eliminated Spine','Absent'))

def exclusion(row):
    if not stable(row['baseline_flag']): return 'baseline_not_stable'
    if not stable(row['followup_flag']): return 'followup_not_stable'
    if 'Shaft Spine' in row['baseline_flag']['value']: return 'baseline_shaft'
    if 'Shaft Spine' in row['followup_flag']['value']: return 'followup_shaft'
    for field in ('baseline_volume','followup_volume','event_rate'):
        value=row[field]
        if value is None or type(value) not in (int,float) or not math.isfinite(value): return 'nonfinite_'+field
        if value < 0 or (field!='event_rate' and value==0): return 'invalid_'+field
    return None

def validate_rows(rows):
    if type(rows) is not list or not 0 < len(rows) <= 20000: raise ValueError('Bounded full row list')
    seen=set();mouse_treatments={}
    fields={'row_id','mouse_id','compartment','treatment','member_index0','source_row0',
            'baseline_flag','followup_flag','baseline_volume','followup_volume','event_rate'}
    for row in rows:
        if type(row) is not dict or set(row)!=fields: raise ValueError('Exact primitive row fields')
        for key in ('row_id','mouse_id'):
            if type(row[key]) is not str or not 0<len(row[key])<=100:raise ValueError('Row identity')
        if row['row_id'] in seen:raise ValueError('Duplicate row ID')
        seen.add(row['row_id'])
        if row['compartment'] not in ('apical','basal') or row['treatment'] not in ('control','kir'):raise ValueError('Group')
        if row['mouse_id'] in mouse_treatments and mouse_treatments[row['mouse_id']] != row['treatment']:
            raise ValueError('Mouse occurs in both treatments')
        mouse_treatments[row['mouse_id']]=row['treatment']
        for key in ('member_index0','source_row0'):
            if type(row[key]) is not int or row[key]<0:raise ValueError('Source index')
        exclusion(row)

def midcdf(values,weights,np):
    """Weighted mid-distribution ranks; tied values get exactly the same rank."""
    order=np.argsort(values,kind='stable');result=np.empty(len(values),dtype=float)
    at=0;mass=0.0;total=float(np.sum(weights))
    while at<len(order):
        end=at+1
        while end<len(order) and values[order[end]]==values[order[at]]:end+=1
        tie=float(np.sum(weights[order[at:end]]))
        result[order[at:end]]=(mass+0.5*tie)/total
        mass+=tie;at=end
    return result

def group_data(rows,np):
    output={}
    for group in GROUPS:
        compartment,treatment=group.split('_')
        chosen=[r for r in rows if r['compartment']==compartment and r['treatment']==treatment and exclusion(r) is None]
        mice=sorted({r['mouse_id'] for r in chosen})
        counts={m:sum(r['mouse_id']==m for r in chosen) for m in mice}
        w=np.array([1.0/(len(mice)*counts[r['mouse_id']]) for r in chosen],dtype=float)
        if chosen:
            q=midcdf(np.array([r['event_rate'] for r in chosen]),w,np)
            s=midcdf(np.array([r['baseline_volume'] for r in chosen]),w,np)
        else:q=s=np.array([],dtype=float)
        y=np.array([math.log2(r['followup_volume'])-math.log2(r['baseline_volume']) for r in chosen])
        x=np.column_stack((np.ones(len(chosen)),q,s))
        bins=np.minimum((q*3).astype(int),2)*3+np.minimum((s*3).astype(int),2)
        output[group]={'rows':chosen,'weights':w,'x':x,'y':y,'bins':bins}
    return output

def fit_group(data,weights,np):
    keep=weights>0;rows=[r for r,k in zip(data['rows'],keep) if k]
    mice=sorted({r['mouse_id'] for r in rows});w=weights[keep]
    result={'row_ids':[r['row_id'] for r in rows],'mice':mice,'n_rows':len(rows),'n_mice':len(mice),
            'effective_mice':None,'rank':0,'coefficients':None,'status':'unavailable','reason':'insufficient_support'}
    if len(rows)<3 or len(mice)<2 or float(np.sum(w))<=0:return result
    w=w/np.sum(w)
    masses=[float(np.sum(w[[r['mouse_id']==m for r in rows]])) for m in mice]
    result['effective_mice']=1.0/sum(v*v for v in masses)
    a=data['x'][keep]*np.sqrt(w[:,None]);b=data['y'][keep]*np.sqrt(w)
    u,s,vh=np.linalg.svd(a,full_matrices=False)
    rank=int(np.sum(s>s[0]*1e-10)) if len(s) and s[0]>0 else 0
    result['rank']=rank
    if rank!=3:result['reason']='rank_deficient';return result
    coef=vh.T @ ((u.T @ b)/s)
    if not np.isfinite(coef).all():raise ValueError('Nonfinite trusted linear algebra')
    result.update(status='defined',reason=None,coefficients={'intercept':float(coef[0]),'activity_rank':float(coef[1]),'baseline_rank':float(coef[2])})
    return result

def panel(rows,balanced,np):
    data=group_data(rows,np);weights={g:d['weights'].copy() for g,d in data.items()}
    matched={}
    if balanced:
        for compartment in ('apical','basal'):
            names=[compartment+'_'+t for t in ('control','kir')]
            mass={g:np.array([np.sum(weights[g][data[g]['bins']==b]) for b in range(9)]) for g in names}
            target=np.minimum(mass[names[0]],mass[names[1]])
            matched[compartment]=[float(v) for v in target]
            for g in names:
                for b in range(9):
                    selected=data[g]['bins']==b
                    weights[g][selected]*=float(target[b]/mass[g][b]) if mass[g][b]>0 else 0.0
    groups={g:fit_group(data[g],weights[g],np) for g in GROUPS}
    values=[]
    for compartment in ('apical','basal'):
        c=groups[compartment+'_control']['coefficients'];k=groups[compartment+'_kir']['coefficients']
        values.append(None if c is None or k is None else k['activity_rank']-c['activity_rank'])
    values.append(None if any(x is None for x in values) else values[0]-values[1])
    return {'groups':groups,'matched_bin_mass':matched,
            'contrasts':{name:{'estimate':value,'jackknife_se':None,'deletion_min':None,'deletion_max':None,
                               'uncertainty_status':'not_computed'} for name,value in zip(CONTRASTS,values)}}

def analyze(rows):
    """Recompute only when explicitly called by an operator or generated test."""
    import numpy as np
    validate_rows(rows)
    eligible=[r for r in rows if exclusion(r) is None]
    excluded=[{'row_id':r['row_id'],'reason':exclusion(r)} for r in rows if exclusion(r) is not None]
    result={'excluded':excluded,'eligible_row_ids':[r['row_id'] for r in eligible],'panels':{}}
    # Unique mouse identities, not FOVs or rows, are jackknife deletion units.
    mice={t:sorted({r['mouse_id'] for r in eligible if r['treatment']==t}) for t in ('control','kir')}
    for name,balanced in [('all',False),('balanced',True)]:
        value=panel(eligible,balanced,np);deletions={}
        for treatment in ('control','kir'):
            for mouse in mice[treatment]:
                p=panel([r for r in eligible if r['mouse_id']!=mouse],balanced,np)
                deletions[mouse]={key:item['estimate'] for key,item in p['contrasts'].items()}
        for key,item in value['contrasts'].items():
            if item['estimate'] is None:
                item['uncertainty_status']='point_unavailable';continue
            if any(len(ms)<2 for ms in mice.values()) or any(d[key] is None for d in deletions.values()):
                item['uncertainty_status']='deletion_unavailable';continue
            variance=0.0;all_values=[]
            for treatment,ms in mice.items():
                vals=[deletions[m][key] for m in ms];mean=sum(vals)/len(vals)
                variance+=(len(vals)-1)/len(vals)*sum((x-mean)**2 for x in vals)
                all_values.extend(vals)
            item.update(jackknife_se=math.sqrt(variance),deletion_min=min(all_values),deletion_max=max(all_values),uncertainty_status='defined')
        value['delete_one_mouse']=deletions;result['panels'][name]=value
    return result
