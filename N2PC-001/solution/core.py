"""Frozen signed N2pc method: literal events, segmented FIR, own-epoch algebra."""
from __future__ import annotations

from collections import Counter
import json
import math

import numpy as np
from source_reader import capture_warnings,need

OFFSETS=np.arange(-205,462,dtype=np.int64)
BASELINE=(OFFSETS>=-204)&(OFFSETS<=0)
WINDOW=(OFFSETS>=205)&(OFFSETS<=307)
LEFT={111,112,211,212};RIGHT={121,122,221,222}
MEASURES=('po7_baseline_uv','po8_baseline_uv','po7_prebaseline_window_uv','po8_prebaseline_window_uv',
          'po7_corrected_window_uv','po8_corrected_window_uv','trial_contra_minus_ipsi_uv','trial_po8_minus_po7_uv')
FIELDS=('left_po7_uv','left_po8_uv','right_po7_uv','right_po8_uv','contra_uv','ipsi_uv','n2pc_uv','fixed_po8_minus_po7_pooled_uv')


def numeric(v):return type(v) in (int,float) and math.isfinite(v)


def finite_number(v,name):
    need(numeric(v),name);return float(v)


def integer(v,name):
    need(numeric(v) and v==int(v) and -(2**63)<=v<2**63,name);return int(v)


def duration(event):
    if 'duration' not in event:return 'absent',None
    value=event['duration']
    if value is None:return 'empty',None
    if isinstance(value,dict) and set(value)=={'source_nonfinite'}:return 'nonfinite',None
    return 'finite',finite_number(value,'unsupported_duration')


def annotate_and_select(metadata):
    subject=metadata['subject'];n=metadata['n_samples'];annotations=[];cuts=[];target_samples=set()
    for index,event in enumerate(metadata['events']):
        code=integer(event.get('type'),'integral_numeric_event_type_required')
        latency=finite_number(event.get('latency'),'finite_event_latency_required')
        onset=float((np.float64(latency)-np.float64(1))/np.float64(1024))
        sample=integer(float(np.rint(np.float64(onset)*np.float64(1024))),'event_sample_int64')
        field='left' if code in LEFT else 'right' if code in RIGHT else 'none'
        is_boundary=code==-99;cut=None
        if is_boundary:
            cut=math.floor(latency)
            need(latency==cut+0.5 and 0<=cut<=n,'boundary_half_sample_cut')
            cuts.append(cut)
        if field!='none':
            need(sample not in target_samples,'duplicate_target_samples');target_samples.add(sample)
        status,dur=duration(event);urevent=event.get('urevent')
        need(urevent is None or numeric(urevent) or isinstance(urevent,(str,list)),'unsupported_urevent_literal')
        annotations.append(dict(subject=subject,source_event_index=index,
                                event_type_json=json.dumps(event['type'],allow_nan=False,separators=(',',':')),
                                latency_samples=latency,duration_samples=dur,
                                urevent_json=json.dumps(urevent,allow_nan=False,separators=(',',':')),
                                event_description=str(code),onset_s=onset,sample=sample,target_field=field,
                                is_boundary=is_boundary,is_bad=False,duration_status=status,boundary_cut_sample=cut))
    cuts=sorted(set([0,n,*cuts]));segments=[[a,b] for a,b in zip(cuts,cuts[1:]) if a<b]
    trials=[]
    for row in annotations:
        if row['target_field']=='none':continue
        start=row['sample']-205;stop=row['sample']+462
        outside=start<0 or stop>n;crosses=any(start<c<stop for c in cuts if 0<c<n)
        reason='out_of_data' if outside else 'boundary_crossing' if crosses else 'retained'
        trials.append(dict(subject=subject,source_event_index=row['source_event_index'],event_code=int(row['event_description']),
                           target_field=row['target_field'],sample=row['sample'],epoch_start_sample=start,epoch_end_sample=stop-1,
                           out_of_data=outside,crosses_boundary=crosses,overlaps_bad=False,retained=reason=='retained',drop_reason=reason,
                           **{k:None for k in MEASURES}))
    observed=dict(metadata['observed'])
    observed.update(event_type_counts=dict(sorted(Counter(r['event_description'] for r in annotations).items())),
                    n_target_left=sum(r['target_field']=='left' for r in trials),n_target_right=sum(r['target_field']=='right' for r in trials),
                    n_boundary_events=sum(r['is_boundary'] for r in annotations))
    return annotations,trials,segments,observed


def filter_reference(eeg_volts,segments,contract,subject,warning_records):
    import mne
    x=np.asarray(eeg_volts,dtype=np.float64)
    need(x.ndim==2 and x.shape[0]==30 and x.shape[1]>0 and np.isfinite(x).all(),'finite_30_channel_source')
    need(segments and segments[0][0]==0 and segments[-1][1]==x.shape[1] and
         all(a<b and (i==0 or a==segments[i-1][1]) for i,(a,b) in enumerate(segments)),'complete_filter_segments')
    names=contract['filter']['eeg_reference_channels'];po=[names.index('PO7'),names.index('PO8')]
    pair=np.empty((2,x.shape[1]),dtype=np.float64)
    for start,stop in segments:
        segment=np.array(x[:,start:stop],dtype=np.float64,order='C',copy=True)
        filtered=capture_warnings(warning_records,subject,f'filter_segment_{start}_{stop}',lambda:mne.filter.filter_data(
            segment,sfreq=1024,l_freq=0.1,h_freq=30,filter_length=33793,l_trans_bandwidth=0.1,h_trans_bandwidth=7.5,
            n_jobs=1,method='fir',iir_params=None,copy=False,phase='zero',fir_window='hamming',fir_design='firwin',
            pad='reflect_limited',verbose=False))
        need(filtered.shape==segment.shape and np.isfinite(filtered).all(),'finite_filtered_source')
        pair[:,start:stop]=(filtered[po]-filtered.mean(axis=0,dtype=np.float64)[None,:])*1e6
    need(np.isfinite(pair).all(),'finite_referenced_source');return pair


def extract_epochs(pair_uv,trials):
    kept=[r for r in trials if r['retained']]
    x=np.stack([pair_uv[:,r['epoch_start_sample']:r['epoch_end_sample']+1] for r in kept]) if kept else np.empty((0,2,len(OFFSETS)))
    need(x.shape==(len(kept),2,len(OFFSETS)) and np.isfinite(x).all(),'epoch_shape_finite')
    return dict(subject=np.array([r['subject'] for r in kept],dtype=np.int64),
                source_event_index=np.array([r['source_event_index'] for r in kept],dtype=np.int64),
                channel_labels=np.array(['PO7','PO8']),sample_offsets=OFFSETS.copy(),epochs_uv=x)


def field_algebra(left,right):
    result={k:None for k in FIELDS}
    if left is not None:result.update(left_po7_uv=left[0],left_po8_uv=left[1])
    if right is not None:result.update(right_po7_uv=right[0],right_po8_uv=right[1])
    if left is not None and right is not None:
        contra=(left[1]+right[0])/2;ipsi=(left[0]+right[1])/2
        result.update(contra_uv=contra,ipsi_uv=ipsi,n2pc_uv=contra-ipsi,
                      fixed_po8_minus_po7_pooled_uv=((left[1]-left[0])+(right[1]-right[0]))/2)
    return result


def scalarize(value):
    return None if value is None else float(value)


def derive(trials,arrays,subjects,pilot=False):
    subjects=list(subjects);x=np.asarray(arrays['epochs_uv'],dtype=np.float64)
    need(x.shape==(len(arrays['subject']),2,667) and np.isfinite(x).all(),'finite_epoch_shape')
    need(np.array_equal(arrays['sample_offsets'],OFFSETS) and list(arrays['channel_labels'])==['PO7','PO8'],'canonical_epoch_axes')
    keys=list(zip(map(int,arrays['subject']),map(int,arrays['source_event_index'])))
    need(len(keys)==len(set(keys)),'unique_retained_epoch_keys')
    index={key:i for i,key in enumerate(keys)}
    need(set(keys)=={(r['subject'],r['source_event_index']) for r in trials if r['retained']},'complete_epoch_keys')
    baseline=x[:,:,BASELINE].mean(axis=2,dtype=np.float64)
    corrected=x-baseline[:,:,None];prewindow=x[:,:,WINDOW].mean(axis=2,dtype=np.float64)
    window=corrected[:,:,WINDOW].mean(axis=2,dtype=np.float64)
    trial_rows=[]
    for trial in trials:
        row=dict(trial)
        if row['retained']:
            i=index[row['subject'],row['source_event_index']];fixed=window[i,1]-window[i,0]
            vals=[*baseline[i],*prewindow[i],*window[i],fixed if row['target_field']=='left' else -fixed,fixed]
            row.update({k:float(v) for k,v in zip(MEASURES,vals)})
        trial_rows.append(row)
    person_rows=[];person_traces=[];waveforms=[]
    for subject in subjects:
        rows=[r for r in trials if r['subject']==subject]
        by_field={side:[index[r['subject'],r['source_event_index']] for r in rows
                        if r['retained'] and r['target_field']==side] for side in ('left','right')}
        nl,nr=(len(by_field[side]) for side in ('left','right'))
        status='defined' if nl and nr else 'empty_both' if not(nl or nr) else 'empty_left' if not nl else 'empty_right'
        means=[window[by_field[side]].mean(axis=0,dtype=np.float64) if by_field[side] else None for side in ('left','right')]
        traces=[corrected[by_field[side]].mean(axis=0,dtype=np.float64) if by_field[side] else None for side in ('left','right')]
        scalar=field_algebra(*means);trace=field_algebra(*traces);person_traces.append(trace)
        counts=Counter(r['drop_reason'] for r in rows)
        person_rows.append(dict(subject=subject,n_target_events=len(rows),n_left_candidates=sum(r['target_field']=='left' for r in rows),
                                n_right_candidates=sum(r['target_field']=='right' for r in rows),n_left_trials=nl,n_right_trials=nr,
                                n_dropped_out_of_data=counts['out_of_data'],n_dropped_boundary_crossing=counts['boundary_crossing'],
                                n_dropped_bad_annotation=0,status=status,**{k:scalarize(v) for k,v in scalar.items()}))
        for i,offset in enumerate(OFFSETS):
            waveforms.append(dict(scope='subject',subject=subject,sample_offset=int(offset),time_s=float(offset/1024),n_expected_subjects=1,
                                  n_left_defined_subjects=int(nl>0),n_right_defined_subjects=int(nr>0),n_contrast_defined_subjects=int(nl>0 and nr>0),status=status,
                                  **{k:None if v is None else float(v[i]) for k,v in trace.items()}))
    expected=len(subjects);defined=sum(r['status']=='defined' for r in person_rows)
    group={k:np.mean([r[k] for r in person_traces],axis=0) if all(r[k] is not None for r in person_traces) else None for k in FIELDS}
    for i,offset in enumerate(OFFSETS):
        waveforms.append(dict(scope='group',subject=None,sample_offset=int(offset),time_s=float(offset/1024),n_expected_subjects=expected,
                              n_left_defined_subjects=sum(r['n_left_trials']>0 for r in person_rows),n_right_defined_subjects=sum(r['n_right_trials']>0 for r in person_rows),
                              n_contrast_defined_subjects=defined,status='defined' if defined==expected else 'incomplete_field_support',
                              **{k:None if v is None else float(v[i]) for k,v in group.items()}))
    summary=dict(status='resource_pilot' if pilot else 'ok',analysis_status='defined' if defined==expected else 'incomplete_field_support',subjects=subjects,
                 n_subjects=expected,n_subjects_with_defined_n2pc=defined,n_subjects_negative=sum(r['n2pc_uv'] is not None and r['n2pc_uv']<0 for r in person_rows),
                 n_left_target_trials_total=sum(r['n_left_trials'] for r in person_rows),n_right_target_trials_total=sum(r['n_right_trials'] for r in person_rows),
                 n_target_events_total=len(trials),n_dropped_target_events_total=sum(not r['retained'] for r in trials),electrode_pair='PO7/PO8',units='uV',window_ms=[200,300],
                 field_weights=dict(left=0.5,right=0.5),subject_weighting='equal_pilot_scope' if pilot else 'equal_fixed12',measure='signed mean contralateral-minus-ipsilateral amplitude')
    for out,key in (('n2pc_amplitude_uv','n2pc_uv'),('contralateral_amplitude_uv','contra_uv'),('ipsilateral_amplitude_uv','ipsi_uv'),('fixed_po8_minus_po7_pooled_uv_for_reference','fixed_po8_minus_po7_pooled_uv')):
        summary[out]=float(np.mean([r[key] for r in person_rows])) if defined==expected else None
    return trial_rows,person_rows,waveforms,summary
