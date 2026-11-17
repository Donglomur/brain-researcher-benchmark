"""Prospective matched-contrast investigation. No classifier or model fitting.

This source was authored after the protocol freeze; it has only generated-data
checks. Real-data contrast calculation is not part of the construction receipt.
"""
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile
import numpy as np

PROTOCOL_SHA256='3424a79612d5a157377fd32615834652623edfb2fd662b56d89c2acf06fb71e2'
PEOPLE=tuple('sub-'+p for p in ('001','002','003','004','005','006','007','010'))
STRATA=('hand1_congruency1','hand1_congruency2','hand2_congruency1','hand2_congruency2')
COUNTS=('eligible_error_n','eligible_correct_n','matched_pairs_n')
NUMBERS=('mean_RT_difference_ms','max_abs_RT_difference_ms','unmatched_FCz_contrast',
         'matched_FCz_contrast','matched_HEOG_contrast','matched_VEOG_contrast',
         'matched_preresponse_FCz_placebo')
ARRAY_KEYS={'trial_ids','participant_id','epochs','response_error','response_hand',
            'stimulus_congruency','rt_samples','sample_offsets','channels','units'}
OFFSETS=np.arange(-614,410,dtype=np.int16)


def need(condition,message):
    if not condition:raise ValueError(message)


def validate_packet(d,person):
    need(type(d) is dict and set(d)==ARRAY_KEYS,'Exact packet keys')
    need(person in PEOPLE and d['participant_id'].shape==() and str(d['participant_id'])==person,'Person identity')
    ids=d['trial_ids']; n=len(ids)
    need(ids.ndim==1 and ids.dtype.kind=='U' and 1<=n<=512,'Bounded Unicode trial identities')
    need(len(set(ids.tolist()))==n and all(re.fullmatch(person+r'-[0-9a-f]{24}',x) for x in ids),'Unique opaque identities')
    need(d['epochs'].shape==(n,3,1024) and d['epochs'].dtype==np.dtype('float64')
         and np.isfinite(d['epochs']).all(),'Finite float64 trial/channel/time array')
    for name,allowed in [('response_error',{0,1}),('response_hand',{1,2}),('stimulus_congruency',{1,2})]:
        need(d[name].shape==(n,) and d[name].dtype==np.dtype('uint8')
             and set(d[name].tolist())<=allowed,'Exact covariate '+name)
    rt=d['rt_samples']
    # At 1024 Hz, 200..1000 ms admits exactly integer samples 205..1024.
    # Compare before scaling: int64 multiplication can wrap unrelated values.
    need(rt.shape==(n,) and rt.dtype==np.dtype('int64') and np.all((rt>=205)&(rt<=1024)),'Eligible marker RT')
    need(d['sample_offsets'].dtype==np.dtype('int16') and np.array_equal(d['sample_offsets'],OFFSETS),'Exact sample axis')
    need(d['channels'].dtype.kind=='U' and d['channels'].tolist()==['FCz_reref','HEOG_bipolar','VEOG_bipolar'],'Exact channel axis')
    need(d['units'].shape==() and str(d['units'])=='native_EEGLAB_amplitude','Native amplitude units')
    return d


def read_bounded_file(path,cap):
    p=Path(path)
    need(p.is_file() and not p.is_symlink() and p.stat().st_size<=cap,'Ordinary bounded input')
    with p.open('rb') as f:raw=f.read(cap+1)
    need(len(raw)<=cap,'Captured byte bound')
    return raw


def load_packet_bytes(raw,person):
    need(type(raw) is bytes and len(raw)<=15000000,'Bounded captured packet bytes')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        members=z.infolist()
        need(len(members)==len(ARRAY_KEYS) and {m.filename for m in members}=={k+'.npy' for k in ARRAY_KEYS},'Exact NPZ members')
        need(sum(m.file_size for m in members)<=15000000 and all(m.file_size<=14000000 for m in members),'Uncompressed packet bound')
    with np.load(io.BytesIO(raw),allow_pickle=False) as f:d={k:f[k] for k in f.files}
    return validate_packet(d,person)


def load_packet(path,person):
    return load_packet_bytes(read_bounded_file(path,15000000),person)


def optimal_pairs(error_indices,correct_indices,rt,ids):
    """Noncrossing max-cardinality, min-L1 match; match > skip C > skip E."""
    errors=sorted(error_indices,key=lambda i:(int(rt[i]),str(ids[i])))
    correct=sorted(correct_indices,key=lambda i:(int(rt[i]),str(ids[i])))
    m,n=len(errors),len(correct)
    count=np.zeros((m+1,n+1),dtype=np.int16)
    cost=np.zeros((m+1,n+1),dtype=np.int64)
    action=np.zeros((m,n),dtype=np.uint8)
    for i in range(m-1,-1,-1):
        for j in range(n-1,-1,-1):
            distance=abs(int(rt[errors[i]])-int(rt[correct[j]]))
            options=[]
            if distance*1000<=25*1024:
                options.append((int(count[i+1,j+1])+1,-int(cost[i+1,j+1])-distance,2,1))
            options.extend([(int(count[i,j+1]),-int(cost[i,j+1]),1,2),
                            (int(count[i+1,j]),-int(cost[i+1,j]),0,3)])
            best=max(options)
            count[i,j],cost[i,j],action[i,j]=best[0],-best[1],best[3]
    pairs=[];i=j=0
    while i<m and j<n:
        a=action[i,j]
        if a==1:pairs.append((errors[i],correct[j]));i+=1;j+=1
        elif a==2:j+=1
        else:i+=1
    return pairs


def match_covariates(d):
    """Timing/motor control: no epoch values are read by this function."""
    pairs=[];support={}
    for hand in (1,2):
        for congruency in (1,2):
            mask=(d['response_hand']==hand)&(d['stimulus_congruency']==congruency)
            errors=np.flatnonzero(mask&(d['response_error']==1)).tolist()
            correct=np.flatnonzero(mask&(d['response_error']==0)).tolist()
            selected=optimal_pairs(errors,correct,d['rt_samples'],d['trial_ids'])
            support[f'hand{hand}_congruency{congruency}']={
                'error_n':len(errors),'correct_n':len(correct),'pairs_n':len(selected)}
            pairs.extend(selected)
    # Canonical digest independent of input row order and numeric array layout.
    names=sorted([[str(d['trial_ids'][e]),str(d['trial_ids'][c])] for e,c in pairs])
    digest=hashlib.sha256(json.dumps(names,separators=(',',':'),ensure_ascii=True).encode()).hexdigest()
    return pairs,support,digest


def summarize(d,person):
    validate_packet(d,person)
    pairs,support,digest=match_covariates(d)
    error=d['response_error']==1
    result={'participant_id':person,'eligible_error_n':int(error.sum()),
       'eligible_correct_n':int((~error).sum()),'matched_pairs_n':len(pairs),
       'pair_digest':digest,'stratum_support':support,
       'status':'supported' if len(pairs)>=10 else 'insufficient_matched_pairs'}
    result.update({k:None for k in NUMBERS})
    if len(pairs)<10:return result
    ei,ci=np.asarray(pairs,dtype=np.int64).T
    rt=(d['rt_samples'][ei]-d['rt_samples'][ci]).astype(np.float64)*1000/1024
    post=d['epochs'][:,:,(OFFSETS>=0)&(OFFSETS<103)].mean(axis=2)
    pre=d['epochs'][:,0,(OFFSETS>=-512)&(OFFSETS< -409)].mean(axis=1)
    contrasts=(post[ei]-post[ci]).mean(axis=0)
    result.update({'mean_RT_difference_ms':float(rt.mean()),'max_abs_RT_difference_ms':float(np.abs(rt).max()),
        'unmatched_FCz_contrast':float(post[error,0].mean()-post[~error,0].mean()),
        'matched_FCz_contrast':float(contrasts[0]),'matched_HEOG_contrast':float(contrasts[1]),
        'matched_VEOG_contrast':float(contrasts[2]),
        'matched_preresponse_FCz_placebo':float((pre[ei]-pre[ci]).mean())})
    return result


def aggregate(records):
    need([r['participant_id'] for r in records]==list(PEOPLE),'Complete fixed ordered eight-person panel')
    all_supported=all(r['status']=='supported' for r in records)
    out={'status':'all_participants_supported' if all_supported else 'not_all_participants_supported',
         'matched_FCz_equal_person_mean':None,'matched_FCz_between_person_descriptive_SE':None}
    if all_supported:
        x=np.asarray([r['matched_FCz_contrast'] for r in records],dtype=np.float64)
        out.update(matched_FCz_equal_person_mean=float(x.mean()),
                   matched_FCz_between_person_descriptive_SE=float(x.std(ddof=1)/np.sqrt(len(x))))
    return out


def make_report(packets):
    need(set(packets)==set(PEOPLE),'All eight packets required, no cohort replacement')
    records=[summarize(packets[p],p) for p in PEOPLE]
    return {'schema':'neural078_contrast_submission_v1','protocol_sha256':PROTOCOL_SHA256,
            'participants':records,'aggregate':aggregate(records)}


def strict_json_bytes(raw):
    need(type(raw) is bytes and len(raw)<=65536,'Captured 64KiB JSON')
    def pairs(items):
        result={}
        for k,v in items:
            need(k not in result,'Duplicate JSON key');result[k]=v
        return result
    def invalid_constant(value):raise ValueError('Nonfinite JSON constant')
    return json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,parse_constant=invalid_constant)


def strict_json(path):
    return strict_json_bytes(read_bounded_file(path,65536))


def validate_report(report):
    need(type(report) is dict and set(report)=={'schema','protocol_sha256','participants','aggregate'},'Exact report keys')
    need(report['schema']=='neural078_contrast_submission_v1' and report['protocol_sha256']==PROTOCOL_SHA256,'Exact report version')
    records=report['participants']
    need(type(records) is list and len(records)==8,'All eight participant records')
    seen=[]
    for row in records:
        need(type(row) is dict and set(row)==set(COUNTS+NUMBERS+('participant_id','pair_digest','stratum_support','status')),'Exact participant fields')
        need(row['participant_id'] in PEOPLE,'Known participant');seen.append(row['participant_id'])
        for k in COUNTS:need(type(row[k]) is int and 0<=row[k]<=512,'Bounded count '+k)
        need(row['eligible_error_n']+row['eligible_correct_n']<=512,'Total trial bound')
        need(row['matched_pairs_n']<=min(row['eligible_error_n'],row['eligible_correct_n']),'Pair support bound')
        need(type(row['pair_digest']) is str and re.fullmatch(r'[0-9a-f]{64}',row['pair_digest']) is not None,'Pair identity digest')
        support=row['stratum_support'];need(type(support) is dict and set(support)==set(STRATA),'All four strata')
        for s in support.values():
            need(type(s) is dict and set(s)=={'error_n','correct_n','pairs_n'},'Exact stratum fields')
            need(all(type(v) is int and 0<=v<=512 for v in s.values()),'Bounded stratum counts')
            need(s['pairs_n']<=min(s['error_n'],s['correct_n']),'Stratum pair support')
        for total,sub in [('eligible_error_n','error_n'),('eligible_correct_n','correct_n'),('matched_pairs_n','pairs_n')]:
            need(row[total]==sum(s[sub] for s in support.values()),'Stratum totals')
        supported=row['matched_pairs_n']>=10
        need(row['status']==('supported' if supported else 'insufficient_matched_pairs'),'Status matches frozen support threshold')
        for k in NUMBERS:
            v=row[k]
            need((type(v) in (int,float) and np.isfinite(v)) if supported else v is None,'Finite supported values; null unsupported')
    need(len(set(seen))==8 and set(seen)==set(PEOPLE),'Exactly one record per person')
    a=report['aggregate'];need(type(a) is dict and set(a)=={'status','matched_FCz_equal_person_mean','matched_FCz_between_person_descriptive_SE'},'Exact aggregate fields')
    supported=all(r['status']=='supported' for r in records)
    need(a['status']==('all_participants_supported' if supported else 'not_all_participants_supported'),'Aggregate support status')
    for k in ('matched_FCz_equal_person_mean','matched_FCz_between_person_descriptive_SE'):
        v=a[k];need((type(v) in (int,float) and np.isfinite(v)) if supported else v is None,'Finite/null aggregate')
    need(not supported or a['matched_FCz_between_person_descriptive_SE']>=0,'Nonnegative descriptive SE')
    return report
