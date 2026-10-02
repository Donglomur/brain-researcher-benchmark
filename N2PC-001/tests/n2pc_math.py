"""Independent public arithmetic; no source IO, solution or historical bank."""
from collections import Counter
import json
import math
import numpy as np
from scipy.signal import fftconvolve
from io_contract import need

SUBJECTS=(1,3,4,5,6,7,8,9,10,11,12,13)
OFFSETS=np.arange(-205,462,dtype=np.int64)
LEFT={111,112,211,212};RIGHT={121,122,221,222}
MEASURES=('po7_baseline_uv','po8_baseline_uv','po7_prebaseline_window_uv',
          'po8_prebaseline_window_uv','po7_corrected_window_uv','po8_corrected_window_uv',
          'trial_contra_minus_ipsi_uv','trial_po8_minus_po7_uv')
VALUES=('left_po7_uv','left_po8_uv','right_po7_uv','right_po8_uv',
        'contra_uv','ipsi_uv','n2pc_uv','fixed_po8_minus_po7_pooled_uv')


def mean(x):
    return math.fsum(float(v) for v in x)/len(x)


def lowpass(length, cutoff):
    i=np.arange(length,dtype=np.float64);f=2*cutoff/1024
    h=f*np.sinc(f*(i-(length-1)/2))*(.54-.46*np.cos(2*np.pi*i/(length-1)))
    return h/np.sum(h,dtype=np.float64)


def kernel():
    h=-lowpass(33793,.05);h[16671:17122]+=lowpass(451,33.75)
    return h


def filter_one(x,h):
    x=np.asarray(x,dtype=np.float64)
    need(x.ndim==1 and x.size>0 and np.isfinite(x).all(),'finite_segment')
    e=min(len(h),len(x))-1
    padded=x if e==0 else np.concatenate((2*x[0]-x[1:e+1][::-1],x,2*x[-1]-x[-e-1:-1][::-1]))
    y=fftconvolve(padded,h,mode='full')[e+(len(h)-1)//2:e+(len(h)-1)//2+len(x)]
    need(np.isfinite(y).all(),'finite_filtered');return y


def annotate(subject,events,n_samples):
    annotations=[];cuts={0,n_samples};seen=set()
    for i,e in enumerate(events):
        typ=e.get('type');lat=e.get('latency')
        need(type(typ) in (int,float) and math.isfinite(typ) and typ==int(typ),'numeric_integral_event_type')
        need(type(lat) in (int,float) and math.isfinite(lat) and abs(lat)<2**52,'finite_event_latency')
        code=int(typ);onset=(np.float64(lat)-1)/1024;sample=int(np.rint(onset*1024))
        field='left' if code in LEFT else 'right' if code in RIGHT else 'none'
        if field!='none':need(sample not in seen,'duplicate_target_sample');seen.add(sample)
        boundary=code==-99;cut=None
        if boundary:
            cut=math.floor(lat)
            need(lat==cut+.5 and 0<=cut<=n_samples,'half_sample_boundary');cuts.add(cut)
        duration=e.get('duration')
        if 'duration' not in e:ds='absent'
        elif duration is None:ds='empty'
        elif isinstance(duration,dict) and set(duration)=={'source_nonfinite'}:ds='nonfinite'
        else:
            need(type(duration) in (int,float) and math.isfinite(duration),'duration_numeric')
            ds='finite'
        annotations.append(dict(subject=subject,source_event_index=i,event_type_json=json.dumps(typ,allow_nan=False),
            latency_samples=lat,duration_samples=duration if ds=='finite' else None,duration_status=ds,
            urevent_json=json.dumps(e.get('urevent'),allow_nan=False,separators=(',',':')),
            event_description=str(code),onset_s=float(onset),sample=sample,target_field=field,
            is_boundary=boundary,is_bad=False,boundary_cut_sample=cut))
    ordered=sorted(cuts);segments=[list(p) for p in zip(ordered[:-1],ordered[1:]) if p[0]<p[1]]
    trials=[]
    for a in annotations:
        if a['target_field']=='none':continue
        start=a['sample']-205;stop=a['sample']+462
        outside=start<0 or stop>n_samples;cross=any(start<c<stop for c in cuts if 0<c<n_samples)
        reason='out_of_data' if outside else 'boundary_crossing' if cross else 'retained'
        trials.append(dict(subject=subject,source_event_index=a['source_event_index'],event_code=int(a['event_description']),
            target_field=a['target_field'],sample=a['sample'],epoch_start_sample=start,epoch_end_sample=stop-1,
            out_of_data=outside,crosses_boundary=cross,overlaps_bad=False,retained=reason=='retained',drop_reason=reason))
    return annotations,trials,segments


def composites(left,right):
    result=[None,None,None,None]
    if left is not None:result[:2]=left
    if right is not None:result[2:4]=right
    if left is None or right is None:return result+[None]*4
    l7,l8=left;r7,r8=right
    c=(l8+r7)/2;i=(l7+r8)/2
    return result+[c,i,c-i,((l8-l7)+(r8-r7))/2]


def derive(trials,epochs,subjects=SUBJECTS):
    """Canonical order inputs, accepted participant epoch samples only."""
    retained=[r for r in trials if r['retained']]
    x=np.asarray(epochs,dtype=np.float64)
    need(x.shape==(len(retained),2,667) and np.isfinite(x).all(),'epoch_shape')
    baseline=np.array([[mean(c[1:206]) for c in row] for row in x],dtype=float).reshape(-1,2)
    raw=np.array([[mean(c[410:513]) for c in row] for row in x],dtype=float).reshape(-1,2)
    corrected=x-baseline[:,:,None];window=raw-baseline
    by_key={};j=0;full_trials=[]
    for row in trials:
        r=dict(row)
        if r['retained']:
            fixed=window[j,1]-window[j,0]
            values=[*baseline[j],*raw[j],*window[j],fixed if r['target_field']=='left' else -fixed,fixed]
            by_key[(r['subject'],r['source_event_index'])]=j;j+=1
            r.update(zip(MEASURES,map(float,values)))
        else:r.update({k:None for k in MEASURES})
        full_trials.append(r)
    persons=[];traces=[];support=[]
    for subject in subjects:
        rows=[r for r in trials if r['subject']==subject]
        idx={f:[by_key[(r['subject'],r['source_event_index'])] for r in rows if r['retained'] and r['target_field']==f] for f in ('left','right')}
        left,right=(idx[f] for f in ('left','right'))
        status='defined' if left and right else 'empty_both' if not left and not right else 'empty_right' if left else 'empty_left'
        scalar_values=[None if not ii else [mean(window[ii,c]) for c in range(2)] for ii in (left,right)]
        vals=composites(*scalar_values)
        person=dict(subject=subject,n_target_events=len(rows),n_left_candidates=sum(r['target_field']=='left' for r in rows),
            n_right_candidates=sum(r['target_field']=='right' for r in rows),n_left_trials=len(left),n_right_trials=len(right),
            n_dropped_out_of_data=sum(r['drop_reason']=='out_of_data' for r in rows),
            n_dropped_boundary_crossing=sum(r['drop_reason']=='boundary_crossing' for r in rows),n_dropped_bad_annotation=0,status=status)
        person.update(zip(VALUES,vals));persons.append(person)
        field_traces=[None if not ii else np.mean(corrected[ii],axis=0,dtype=np.float64) for ii in (left,right)]
        vals_trace=composites(*field_traces);traces.append(vals_trace);support.append((bool(left),bool(right)))
    waveforms=[]
    def add_wave(scope,subject,values,n,l,r,b,status):
        for k,offset in enumerate(OFFSETS):
            row=dict(scope=scope,subject=subject,sample_offset=int(offset),time_s=float(offset/1024),n_expected_subjects=n,
                n_left_defined_subjects=l,n_right_defined_subjects=r,n_contrast_defined_subjects=b,status=status)
            row.update({name:None if a is None else float(a[k]) for name,a in zip(VALUES,values)});waveforms.append(row)
    for s,p,t,(l,r) in zip(subjects,persons,traces,support):add_wave('subject',s,t,1,int(l),int(r),int(l and r),p['status'])
    n=len(subjects);defined=sum(l and r for l,r in support);all_defined=defined==n
    group=[]
    for j in range(8):
        group.append(None if any(t[j] is None for t in traces) else np.mean([t[j] for t in traces],axis=0,dtype=np.float64))
    add_wave('group',None,group,n,sum(l for l,r in support),sum(r for l,r in support),defined,'defined' if all_defined else 'incomplete_field_support')
    result=dict(status='ok',analysis_status='defined' if all_defined else 'incomplete_field_support',subjects=list(subjects),n_subjects=n,
        n_subjects_with_defined_n2pc=defined,n_subjects_negative=sum(p['n2pc_uv'] is not None and p['n2pc_uv']<0 for p in persons),
        n_left_target_trials_total=sum(p['n_left_trials'] for p in persons),n_right_target_trials_total=sum(p['n_right_trials'] for p in persons),
        n_target_events_total=len(trials),n_dropped_target_events_total=len(trials)-len(retained),electrode_pair='PO7/PO8',units='uV',
        window_ms=[200,300],field_weights={'left':.5,'right':.5},subject_weighting='equal_fixed12',
        measure='signed mean contralateral-minus-ipsilateral amplitude')
    for target,key in [('n2pc_amplitude_uv','n2pc_uv'),('contralateral_amplitude_uv','contra_uv'),('ipsilateral_amplitude_uv','ipsi_uv'),
                       ('fixed_po8_minus_po7_pooled_uv_for_reference','fixed_po8_minus_po7_pooled_uv')]:
        result[target]=mean([p[key] for p in persons]) if all_defined else None
    return dict(trials=full_trials,per_subject=persons,waveforms=waveforms,result=result)
