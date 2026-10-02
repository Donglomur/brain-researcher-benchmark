"""N170 source-backed MNE route; imports do not access data or execute analysis.

The bounded generic MAT scanner is shared; event/scientific logic is owned here.
MNE reads private temporary files made from authenticated immutable buffers, not
mutable source pathnames. No MNE event selection, epoching or rejection defaults
are used. Only the caller emits artifacts or invokes the measurement kernel.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import tempfile
import warnings

import numpy as np
from mat_metadata import MatScan, records

SOURCE_SHA256='3970137c64990f680468baf1d51b89a73a61a748639795541e2c2734777b54cd'
METHOD_SHA256='549cf315f0175ab13c3007703cec298a6cc5080d695aecd9f93f49e98a08ce92'
SCHEMA_SHA256='fab0dbf2ff1fb60f0596b065ff5f148d9d46da8c89c6e81203dbc346a2070814'
SUBJECTS=tuple(str(s) for s in range(1,41) if s not in (1,5,16))
SOURCE_BYTES=788438272
MEMBER_LIMIT=32*1024**2


def need(ok,reason):
    if not ok:raise ValueError(reason)


def safe_path(value):
    raw=os.fspath(value)
    need(isinstance(raw,str) and raw.startswith('/') and '\0' not in raw,'absolute_path')
    need(not any(s in ('.','..') for s in raw.split('/')),'path_traversal')
    p=Path(raw)
    for q in (*reversed(p.parents),p):
        if os.path.lexists(q):
            mode=q.lstat().st_mode;need(not stat.S_ISLNK(mode),'symlink_path')
            if q!=p:need(stat.S_ISDIR(mode),'non_directory_ancestor')
    return p


def signature(s):return (s.st_dev,s.st_ino,s.st_mode,s.st_size,s.st_mtime_ns,s.st_ctime_ns)


def read_bytes(path,limit=MEMBER_LIMIT,row=None):
    p=safe_path(path);before=p.lstat()
    need(stat.S_ISREG(before.st_mode) and 0<=before.st_size<=limit,'source_regular_bound')
    if row is not None:need(before.st_size==row['size_bytes'],'source_size')
    with os.fdopen(os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK),'rb') as f:
        need(signature(os.fstat(f.fileno()))==signature(before),'source_replaced')
        raw=f.read(before.st_size+1)
        need(len(raw)==before.st_size and signature(os.fstat(f.fileno()))==signature(before),'source_changed')
        f.seek(0);h=hashlib.sha256();n=0
        while chunk:=f.read(min(65536,before.st_size-n+1)):
            n+=len(chunk);need(n<=before.st_size,'source_changed');h.update(chunk)
        need(n==len(raw) and h.digest()==hashlib.sha256(raw).digest()
             and signature(os.fstat(f.fileno()))==signature(before),'source_changed')
    need(signature(p.lstat())==signature(before),'source_changed')
    if row is not None:
        need(hashlib.sha256(raw).hexdigest()==row['sha256'],'source_sha256')
        if row.get('md5') is not None:need(hashlib.md5(raw).hexdigest()==row['md5'],'source_md5')
    return raw


def strict_json(raw):
    def pairs(items):
        out={}
        for k,v in items:need(k not in out,'duplicate_json_key');out[k]=v
        return out
    def invalid(_):raise ValueError('nonfinite_json')
    value=json.loads(raw,object_pairs_hook=pairs,parse_constant=invalid)
    def check(v,depth=0):
        need(depth<=64,'json_depth')
        if isinstance(v,float):need(math.isfinite(v),'nonfinite_json')
        elif isinstance(v,dict):
            for x in v.values():check(x,depth+1)
        elif isinstance(v,list):
            for x in v:check(x,depth+1)
    check(value);return value


def pinned_json(path,pin):
    raw=read_bytes(path,1024**2);need(hashlib.sha256(raw).hexdigest()==pin,'public_json_pin')
    return raw,strict_json(raw)


def load_inputs(data_dir,manifest_path,method_path,schema_path):
    root=safe_path(data_dir);need(root.is_dir(),'source_directory')
    manifest_raw,manifest=pinned_json(manifest_path,SOURCE_SHA256)
    _,method=pinned_json(method_path,METHOD_SHA256);_,schema=pinned_json(schema_path,SCHEMA_SHA256)
    need(read_bytes(root/'source_manifest.json',1024**2)==manifest_raw,'internal_manifest_identity')
    need(method['subjects']==list(SUBJECTS) and manifest['subjects']==[int(s) for s in SUBJECTS],'fixed_subjects')
    rows=manifest['files'];need(len(rows)==74,'source_count')
    keys=set();names=set()
    for row in rows:
        s,r=row['subject'],row['role'];need(type(s) is int and str(s) in SUBJECTS and r in ('set','fdt'),'source_key')
        need((s,r) not in keys,'duplicate_source_key');keys.add((s,r))
        need(row['path']==f'{s}_N170_shifted_ds.{r}' and row['path'] not in names,'source_path');names.add(row['path'])
        need(type(row['size_bytes']) is int and 0<row['size_bytes']<=MEMBER_LIMIT,'source_size_bound')
        need(type(row['sha256']) is str and re.fullmatch('[0-9a-f]{64}',row['sha256']),'source_sha_format')
        need(row.get('md5') is None or type(row['md5']) is str and re.fullmatch('[0-9a-f]{32}',row['md5']),'source_md5_format')
    need(keys=={(int(s),r) for s in SUBJECTS for r in ('set','fdt')},'source_membership')
    need(sum(r['size_bytes'] for r in rows)==SOURCE_BYTES,'source_total_bytes')
    observed=set()
    for p in root.iterdir():
        need(stat.S_ISREG(p.lstat().st_mode),'source_nonregular');observed.add(p.name)
    need(observed==names|{'source_manifest.json'},'closed_source_inventory')
    # No SET fields are parsed until every original member has authenticated.
    for row in rows:read_bytes(root/row['path'],row=row)
    return dict(root=root,manifest=manifest,method=method,schema=schema,
                by_key={(str(r['subject']),r['role']):r for r in rows})


def documentary(value,budget=None):
    if budget is None:budget=[2_000_000]
    budget[0]-=1;need(budget[0]>=0,'metadata_value_bound')
    if isinstance(value,np.generic):return documentary(value.item(),budget)
    if isinstance(value,np.ndarray):
        if value.size==0:return None
        if value.size==1:return documentary(value.reshape(-1)[0],budget)
        return documentary(value.tolist(),budget)
    if isinstance(value,bytes):return value.decode('utf-8')
    if value is None or isinstance(value,(str,bool,int)):return value
    if isinstance(value,float):
        if math.isfinite(value):return value
        return {'__nonfinite__':'NaN' if math.isnan(value) else 'Infinity' if value>0 else '-Infinity'}
    if isinstance(value,dict):return {str(k):documentary(v,budget) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [documentary(v,budget) for v in value]
    raise ValueError('unsupported_metadata_type')


def normalized_code(value):
    if type(value) in (int,float) and math.isfinite(value) and value==int(value):return int(value)
    if isinstance(value,str) and re.fullmatch(r'[+-]?[0-9]+',value.strip()):return int(value.strip())
    return None


def event_plan(subject,events,n_samples,method):
    annotations=[];targets=[];cuts={0,n_samples};boundary_rows=[]
    for index,event in enumerate(events):
        need(isinstance(event,dict),'event_record');typ=event.get('type');lat=event.get('latency');code=normalized_code(typ)
        boundary=code==-99 or isinstance(typ,str) and typ.strip().casefold()=='boundary'
        role='boundary' if boundary else 'face' if code is not None and 1<=code<=40 else 'car' if code is not None and 41<=code<=80 else 'other'
        row=dict(subject_id=subject,source_event_index=index,normalized_event_code=code,event_role=role)
        for field in ('type','latency','duration','urevent'):
            row[field+'_json']=json.dumps(event.get(field),sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':'))
        annotations.append(row)
        if role!='other':
            need(type(lat) in (int,float) and math.isfinite(lat),'target_or_boundary_latency')
            need(abs(lat)<2**63,'latency_integer_representability')
        if boundary:
            cut=math.ceil(lat-1);need(0<=cut<=n_samples,'boundary_cut_domain');cuts.add(cut);boundary_rows.append(index)
        elif role in ('face','car'):
            targets.append(dict(subject_id=subject,source_event_index=index,condition=role,event_sample=int(np.rint(lat-1))))
    ordered=sorted(cuts);segments=list(zip(ordered[:-1],ordered[1:]));counts=Counter(r['event_sample'] for r in targets)
    lo,hi=method['epoch']['sample_offsets_inclusive']
    for row in targets:
        first,last=row['event_sample']+lo,row['event_sample']+hi
        if first<0 or last>=n_samples:reason='out_of_bounds'
        elif counts[row['event_sample']]>1:reason='duplicate_target_sample'
        elif not any(first>=a and last<b for a,b in segments):reason='crosses_boundary'
        else:reason='accepted'
        row.update(epoch_first_sample=first,epoch_last_sample=last,epoch_status='ok' if reason=='accepted' else reason,
                   accepted=False,rejection_reason=reason)
    return annotations,targets,segments,boundary_rows,ordered


def read_metadata(inputs,subject):
    m=inputs['method'];s=inputs['by_key'][subject,'set'];f=inputs['by_key'][subject,'fdt']
    raw=read_bytes(inputs['root']/s['path'],16*1024**2,s);scan=MatScan(raw);nodes,layout=scan.fields()
    need('data' in nodes and nodes['data']['matlab_class']==4,'external_data_pointer_required')
    pointer=documentary(scan.decode(nodes['data']));need(pointer==f['path'],'literal_fdt_pointer')
    header_keys=('setname','filename','filepath','subject','group','condition','session','nbchan','trials','pnts','srate',
                 'xmin','xmax','ref','saved','datfile','history','comments','unit','units')
    wanted=header_keys+('chanlocs','event','urevent')
    decoded={k:scan.decode(nodes[k]) for k in wanted if k in nodes}
    values={k:documentary(v) for k,v in decoded.items() if k not in ('chanlocs','event','urevent')}
    for key,expected in [('nbchan',m['source']['n_channels']),('trials',m['source']['n_trials']),
                         ('srate',m['source']['sfreq_hz']),('xmin',m['source']['xmin'])]:
        need(type(values.get(key)) in (int,float) and values[key]==expected,'source_header_'+key)
    n=values.get('pnts');need(type(n) in (int,float) and math.isfinite(n) and n>0 and int(n)==n,'source_pnts');n=int(n)
    need(f['size_bytes']==4*m['source']['n_channels']*n,'fdt_byte_equation')
    channels=records(decoded.get('chanlocs'));need(len(channels)==33 and all(isinstance(v,dict) for v in channels),'channel_metadata')
    labels=[documentary(v.get('labels')) for v in channels];need(labels==m['source']['channel_labels'],'source_channels')
    need(values.get('ref')==m['source']['reference_token'],'source_reference')
    need('unit' not in nodes and 'units' not in nodes,'source_units_fields')
    for key in ('icaweights','icasphere','icawinv','icachansind','icaact'):
        if key in nodes:need(math.prod(nodes[key]['shape'])==0,'source_ica_not_empty')
    events=[documentary(v) for v in records(decoded.get('event'))];need(len(events)<=40000,'source_event_bound')
    annotations,targets,segments,boundaries,cuts=event_plan(subject,events,n,m)
    history=values.get('history');need(isinstance(history,str),'source_history')
    observed=dict(subject_id=subject,set_path=s['path'],fdt_path=f['path'],literal_data_pointer=pointer,mat_layout=layout,
                  header_fields=values,channel_labels=labels,channel_records=[documentary(v) for v in channels],
                  event_fields=sorted({k for e in events for k in e}),n_events=len(events),
                  boundary_event_indices=boundaries,boundary_cut_samples=cuts,filter_segments=[list(v) for v in segments],
                  fdt_size_bytes=f['size_bytes'],ica_field_shapes={k:nodes[k]['shape'] for k in ('icaweights','icasphere','icawinv','icachansind','icaact') if k in nodes})
    return dict(subject=subject,n_samples=n,annotations=annotations,targets=targets,segments=segments,
                observed=observed,mat_layout=layout)


def caught(warning_records,subject,stage,operation):
    with warnings.catch_warnings(record=True) as seen:
        warnings.simplefilter('always')
        try:return operation()
        finally:warning_records.extend(dict(subject_id=subject,stage=stage,category=w.category.__name__,message=str(w.message)) for w in seen)


def private_copy(path,raw):
    with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb') as f:f.write(raw)
    need(read_bytes(path)==raw,'private_copy_identity')


def read_mne_uv(inputs,meta,warning_records):
    import mne
    subject=meta['subject'];m=inputs['method'];s=inputs['by_key'][subject,'set'];f=inputs['by_key'][subject,'fdt']
    temporary_root=safe_path(tempfile.gettempdir())
    for protected in (inputs['root'],Path(__file__).absolute().parent):
        need(temporary_root!=protected and protected not in temporary_root.parents,'temporary_source_or_code_overlap')
    set_raw=read_bytes(inputs['root']/s['path'],16*1024**2,s)
    fdt_raw=read_bytes(inputs['root']/f['path'],row=f)
    # A private0700 directory and exclusive0600 members sever the source path
    # reopen gap. Rehash both exact copies before and after MNE consumes them.
    with tempfile.TemporaryDirectory(prefix='n170-oracle-',dir=temporary_root) as temporary:
        private=Path(temporary);private_copy(private/s['path'],set_raw);private_copy(private/f['path'],fdt_raw)
        raw=None
        try:
            raw=caught(warning_records,subject,'mne_eeglab_read',lambda:mne.io.read_raw_eeglab(
                private/s['path'],eog=m['source']['channel_labels'][30:],preload=False,
                uint16_codec=None,montage_units='auto',verbose=False))
            need(raw.ch_names==m['source']['channel_labels'] and raw.n_times==meta['n_samples']
                 and raw.info['sfreq']==m['source']['sfreq_hz'] and raw.first_samp==0,'mne_header_mismatch')
            volts=caught(warning_records,subject,'mne_eeglab_values',lambda:raw.get_data(picks=m['reference']['channels']))
            need(volts.shape==(30,meta['n_samples']) and volts.dtype==np.float64 and np.isfinite(volts).all(),'contributing_eeg_finite_shape')
            uv=np.ascontiguousarray(volts*1e6);need(np.isfinite(uv).all(),'calibrated_eeg_finite')
            return uv
        finally:
            if raw is not None:raw.close()
            read_bytes(private/s['path'],row=s);read_bytes(private/f['path'],row=f)


def filter_reference(eeg_uv,segments,method,subject,warning_records):
    import mne
    data=np.array(eeg_uv,dtype=np.float64,order='C',copy=True)
    need(data.ndim==2 and data.shape[0]==30 and np.isfinite(data).all(),'reference_input')
    data-=np.mean(data,axis=0,keepdims=True)
    need(np.isfinite(data).all(),'reference_finite')
    f=method['filter'];result=np.empty_like(data)
    need(segments and segments[0][0]==0 and segments[-1][1]==data.shape[1]
         and all(a<b for a,b in segments) and all(segments[i][1]==segments[i+1][0] for i in range(len(segments)-1)),'filter_segments')
    for a,b in segments:
        piece=np.ascontiguousarray(data[:,a:b])
        filtered=caught(warning_records,subject,f'mne_filter_{a}_{b}',lambda:mne.filter.filter_data(
            piece,sfreq=method['source']['sfreq_hz'],l_freq=f['low_hz'],h_freq=f['high_hz'],
            picks=None,filter_length='auto',l_trans_bandwidth=f['low_transition_hz'],h_trans_bandwidth=f['high_transition_hz'],
            n_jobs=1,method='fir',iir_params=None,copy=True,phase='zero',fir_window='hamming',fir_design='firwin',
            pad='reflect_limited',verbose=False))
        need(filtered.shape==piece.shape and np.isfinite(filtered).all(),'filtered_finite_shape');result[:,a:b]=filtered
    return result


def summarize_epochs(filtered,meta,method):
    offsets=np.arange(method['epoch']['sample_offsets_inclusive'][0],method['epoch']['sample_offsets_inclusive'][1]+1,dtype=np.int64)
    base=(offsets>=method['epoch']['baseline_offsets_inclusive'][0])&(offsets<=method['epoch']['baseline_offsets_inclusive'][1])
    po8=method['reference']['channels'].index(method['measurement']['electrode'])
    trials=[];keys=[];ptp=[];baseline=[];waves={'face':[],'car':[]}
    need(filtered.shape==(30,meta['n_samples']) and np.isfinite(filtered).all(),'epoch_input_shape')
    for original in meta['targets']:
        row=dict(original)
        if row['epoch_status']=='ok':
            epoch=np.ascontiguousarray(filtered[:,row['event_sample']+offsets])
            spans=np.max(epoch,axis=1)-np.min(epoch,axis=1)
            means=np.mean(epoch[:,base],axis=1)
            need(np.isfinite(spans).all() and np.isfinite(means).all(),'epoch_finite_reductions')
            keys.append((meta['subject'],row['source_event_index']));ptp.append(spans);baseline.append(float(means[po8]))
            row['accepted']=not bool(np.any(spans>method['epoch']['ptp_threshold_uv']))
            row['rejection_reason']='accepted' if row['accepted'] else 'peak_to_peak'
            if row['accepted']:
                epoch-=means[:,None];waves[row['condition']].append(epoch[po8].copy())
        trials.append(row)
    defined=np.array([bool(waves[c]) for c in ('face','car')],dtype=bool)
    evoked=np.zeros((2,len(offsets)),dtype=np.float64)
    for i,c in enumerate(('face','car')):
        if defined[i]:evoked[i]=np.mean(np.ascontiguousarray(waves[c]),axis=0)
    need(np.isfinite(evoked).all(),'condition_mean_finite')
    reasons=Counter(r['rejection_reason'] for r in trials)
    observed=dict(subject_id=meta['subject'],
                  n_face_candidates=sum(r['condition']=='face' for r in trials),n_car_candidates=sum(r['condition']=='car' for r in trials),
                  n_face_accepted=len(waves['face']),n_car_accepted=len(waves['car']),
                  n_face_rejected=sum(r['condition']=='face' and not r['accepted'] for r in trials),
                  n_car_rejected=sum(r['condition']=='car' and not r['accepted'] for r in trials),
                  rejection_counts={k:reasons[k] for k in method['epoch']['rejection_reason_precedence']},
                  condition_defined=defined.tolist(),n_eligible_epochs=len(keys))
    return dict(trials=trials,epoch_keys=keys,epoch_peak_to_peak_uv=np.array(ptp,dtype=np.float64).reshape(-1,30),
                epoch_po8_baseline_uv=np.array(baseline,dtype=np.float64),condition_defined=defined,
                evoked_po8_uv=evoked,analysis_observed=observed)


def reconstruct(data_dir,manifest_path,method_path,schema_path,*,pilot=False):
    need(type(pilot) is bool,'pilot_boolean')
    inputs=load_inputs(data_dir,manifest_path,method_path,schema_path)
    metadata={s:read_metadata(inputs,s) for s in SUBJECTS}
    selected=SUBJECTS[:1] if pilot else SUBJECTS;parts=[];warning_records=[]
    for subject in selected:
        meta=metadata[subject];data=read_mne_uv(inputs,meta,warning_records)
        filtered=filter_reference(data,meta['segments'],inputs['method'],subject,warning_records)
        parts.append(summarize_epochs(filtered,meta,inputs['method']))
    method=inputs['method'];lo,hi=method['epoch']['sample_offsets_inclusive']
    return dict(status='resource_pilot' if pilot else 'complete',subjects=list(selected),
                annotations=[r for s in SUBJECTS for r in metadata[s]['annotations']],trials=[r for p in parts for r in p['trials']],
                sample_offsets=np.arange(lo,hi+1,dtype=np.int64),condition_labels=['face','car'],
                condition_defined=np.stack([p['condition_defined'] for p in parts]),evoked_po8_uv=np.stack([p['evoked_po8_uv'] for p in parts]),
                rejection_channel_labels=list(method['reference']['channels']),epoch_keys=[k for p in parts for k in p['epoch_keys']],
                epoch_peak_to_peak_uv=np.concatenate([p['epoch_peak_to_peak_uv'] for p in parts]),
                epoch_po8_baseline_uv=np.concatenate([p['epoch_po8_baseline_uv'] for p in parts]),
                source_files=[dict(subject_id=str(r['subject']),role=r['role'],path=r['path'],size_bytes=r['size_bytes'],sha256=r['sha256']) for r in inputs['manifest']['files']],
                pins=dict(source_manifest_sha256=SOURCE_SHA256,method_contract_sha256=METHOD_SHA256,output_schema_sha256=SCHEMA_SHA256),
                source_observed={'persons':[metadata[s]['observed'] for s in SUBJECTS]},
                analysis_observed={'persons':[p['analysis_observed'] for p in parts]},warnings=warning_records)
