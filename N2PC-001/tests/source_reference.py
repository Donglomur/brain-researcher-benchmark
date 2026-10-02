"""Trusted source reconstruction: direct FDT + analytic FIR, never oracle/bank.

Shares bounded MAT metadata decoding (scipy.io) and low-level NumPy/SciPy only.
EEGLAB stored values are interpreted as microvolts by the explicit public
convention. Referencing before filtering uses linearity of the same operator.
"""
from collections import Counter
import hashlib
from pathlib import Path
import stat
import numpy as np
import io_contract as io
import mat_metadata as mat
import n2pc_math as mathcore

METHOD_SHA='1da14bc2c9dc043a881c82f3b540c9f82fc71737ce2b0e829c62f8a9a23d319c'
SOURCE_SHA='ada7a37ede5c498063d324bc9d5c254b457c5aecab9d41c622c66c38a8e21541'
NOTICE_SHA='6cc59f632b1fd5868fd3abc99ef2bb28f32b92c861198759a56577550305628e'
SCANNER_SHA='20b7aa584b3e8f621b521d83acacd130119093c631b72bcad6e9a83f0a7d4f66'
HERE=Path(__file__).resolve().parent


def authority():
    method=io.json_bytes(io.read_bytes(HERE/'method_authority.json',262144,sha256=METHOD_SHA))
    source=io.json_bytes(io.read_bytes(HERE/'source_authority.json',65536,sha256=SOURCE_SHA))
    io.read_bytes(HERE/'mat_metadata.py',65536,sha256=SCANNER_SHA)
    return method,source


def authenticate(data_dir,method_path=None):
    method,manifest=authority();root=io.safe_path(data_dir)
    io.need(root.is_dir(),'source_directory')
    if method_path is not None:io.read_bytes(method_path,262144,sha256=METHOD_SHA)
    io.read_bytes(root/'source_manifest.json',65536,sha256=SOURCE_SHA)
    io.read_bytes(root/'SOURCE_NOTICE.md',65536,sha256=NOTICE_SHA)
    expected={r['path'] for r in manifest['files']}|{'source_manifest.json','SOURCE_NOTICE.md'}
    got=set()
    for p in root.iterdir():
        io.need(stat.S_ISREG(p.lstat().st_mode),'closed_regular_source_inventory');got.add(p.name)
    io.need(got==expected,'closed_source_inventory')
    for r in manifest['files']:
        io.read_bytes(root/r['path'],128*1024**2,size=r['size_bytes'],sha256=r['sha256'])
    return root,method,manifest


def metadata(raw,subject,srow,frow,method):
    scanner=mat.MatScan(raw);nodes,_=scanner.fields()
    io.need('data' in nodes and nodes['data']['matlab_class']==4,'external_FDT_required')
    pointer=mat.scalar(scanner.decode(nodes['data']))
    io.need(pointer==frow['path'] and '/' not in pointer and '\\' not in pointer,'exact_FDT_pointer')
    selected=('nbchan','pnts','trials','srate','xmin','ref','unit','units','chanlocs','event','history')
    values={k:mat.scalar(scanner.decode(nodes[k])) for k in selected if k in nodes}
    for key,value in [('nbchan',33),('trials',1),('srate',1024),('xmin',0)]:
        io.need(type(values.get(key)) in (int,float) and values[key]==value,'header_'+key)
    n=values.get('pnts');io.need(type(n) in (int,float) and n>0 and n==int(n),'header_pnts');n=int(n)
    io.need(33*n*4==frow['size_bytes'],'FDT_byte_equation')
    io.need(values.get('ref')=='common' and values.get('unit') is None and values.get('units') is None,'source_reference_units')
    channels=mat.records(values.get('chanlocs'))
    labels=[c.get('labels') for c in channels]
    io.need(labels==method['source']['channel_labels'],'source_channel_order')
    events=mat.records(values.get('event'));io.need(len(events)<=10000,'source_event_bound')
    annotations,trials,segments=mathcore.annotate(subject,events,n)
    io.need(len(trials)<=5000,'source_trial_bound')
    history=values.get('history');io.need(isinstance(history,str),'history_string')
    observed=dict(subject=subject,set_path=srow['path'],fdt_path=frow['path'],literal_fdt_pointer=pointer,
        sfreq_hz=1024,n_samples=n,n_channels=33,channel_labels=labels,source_reference_json='common',
        source_units_json=None,source_bad_channels=None,n_source_events=len(events),
        event_type_counts=dict(Counter(a['event_description'] for a in annotations)),
        n_target_left=sum(t['target_field']=='left' for t in trials),n_target_right=sum(t['target_field']=='right' for t in trials),
        n_boundary_events=sum(a['is_boundary'] for a in annotations),n_bad_annotations=0,
        history_sha256=hashlib.sha256(history.encode('utf-8')).hexdigest())
    processing=dict(subject=subject,eeg_reference_channels=labels[:30],excluded_eog_channels=labels[30:],
        filter_segments=segments,fir_length=33793,epoch_offsets=[-205,461],baseline_offsets=[-204,0],measurement_offsets=[205,307],
        n_left_retained=sum(t['retained'] and t['target_field']=='left' for t in trials),
        n_right_retained=sum(t['retained'] and t['target_field']=='right' for t in trials),
        drop_reason_counts={k:sum(t['drop_reason']==k for t in trials) for k in ('out_of_data','boundary_crossing','bad_annotation')})
    return dict(observed=observed,processing=processing,annotations=annotations,trials=trials,n_samples=n,segments=segments)


def direct_fdt_epochs(raw,meta):
    n=meta['n_samples'];io.need(len(raw)==n*33*4,'FDT_size')
    stored=np.frombuffer(raw,dtype='<f4').reshape(n,33)
    eeg=np.asarray(stored[:,:30],dtype=np.float64)
    io.need(np.isfinite(eeg).all(),'nonfinite_source_EEG')
    reference=np.sum(eeg,axis=1,dtype=np.float64)/30
    pair=eeg[:,[9,27]].T-reference[None,:]
    del eeg
    h=mathcore.kernel();filtered=np.empty_like(pair)
    for start,stop in meta['segments']:
        for ch in range(2):filtered[ch,start:stop]=mathcore.filter_one(pair[ch,start:stop],h)
    kept=[r for r in meta['trials'] if r['retained']]
    epochs=np.empty((len(kept),2,667),dtype=np.float64)
    for j,r in enumerate(kept):epochs[j]=filtered[:,r['epoch_start_sample']:r['epoch_end_sample']+1]
    return epochs


def reconstruct(data_dir,method_path=None,*,subjects=None):
    """Production uses all12; explicit subset only for labeled authoring pilots."""
    root,method,manifest=authenticate(data_dir,method_path)
    chosen=tuple(mathcore.SUBJECTS if subjects is None else subjects)
    io.need(chosen and len(set(chosen))==len(chosen) and set(chosen)<=set(mathcore.SUBJECTS),'scope_subjects')
    by={(r['subject'],r['role']):r for r in manifest['files']}
    all_meta={}
    for subject in mathcore.SUBJECTS:
        s,f=by[subject,'set'],by[subject,'fdt']
        raw=io.read_bytes(root/s['path'],16*1024**2,size=s['size_bytes'],sha256=s['sha256'])
        all_meta[subject]=metadata(raw,subject,s,f,method)
    annotations=[];trials=[];epochs=[]
    for subject in chosen:
        f=by[subject,'fdt'];meta=all_meta[subject]
        # Authentication of the SAME bytes that enter the numerical decoder.
        raw=io.read_bytes(root/f['path'],128*1024**2,size=f['size_bytes'],sha256=f['sha256'])
        epochs.append(direct_fdt_epochs(raw,meta));annotations.extend(meta['annotations']);trials.extend(meta['trials'])
    x=np.concatenate(epochs,axis=0)
    keys=[(r['subject'],r['source_event_index']) for r in trials if r['retained']]
    fields=('subject','role','path','object_id','version','size_bytes','sha256','md5')
    metadata_target=dict(status='ok',dataset_id='erp-core-n2pc-fixed12',source_manifest_sha256=SOURCE_SHA,method_contract_sha256=METHOD_SHA,
        subjects=list(chosen),source_files=[{k:r[k] for k in fields} for r in manifest['files']],
        source_observed=[all_meta[s]['observed'] for s in chosen],processing_observed=[all_meta[s]['processing'] for s in chosen])
    return dict(method=method,manifest=manifest,subjects=list(chosen),annotations=annotations,trials=trials,epochs_uv=x,
        keys=keys,metadata=metadata_target,source_proof=dict(n_originals=24,source_bytes=sum(r['size_bytes'] for r in manifest['files']),
        source_manifest_sha256=SOURCE_SHA,method_contract_sha256=METHOD_SHA),source_route='direct little-endian FDT; analytic sinc/Hamming; scipy FFT; prefilter reference')
