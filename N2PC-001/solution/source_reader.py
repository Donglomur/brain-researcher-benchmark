"""Owned source authentication and metadata extraction; MNE supplies EEG volts.

No network, helper imports, cache discovery or import-time source access.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import warnings

import numpy as np
from set_metadata import MatScan,records,scalar

METHOD_SHA256='1da14bc2c9dc043a881c82f3b540c9f82fc71737ce2b0e829c62f8a9a23d319c'
SOURCE_SHA256='ada7a37ede5c498063d324bc9d5c254b457c5aecab9d41c622c66c38a8e21541'
NOTICE_SHA256='6cc59f632b1fd5868fd3abc99ef2bb28f32b92c861198759a56577550305628e'
SUBJECTS=(1,3,4,5,6,7,8,9,10,11,12,13)


def need(ok,reason):
    if not ok:raise ValueError(reason)


def safe_path(value):
    text=os.fspath(value)
    need(isinstance(text,str) and text.startswith('/') and '\0' not in text,'absolute_path_required')
    need(not any(x in ('.','..') for x in text.split('/')),'path_traversal')
    p=Path(text)
    for x in (*reversed(p.parents),p):
        if os.path.lexists(x):
            mode=x.lstat().st_mode;need(not stat.S_ISLNK(mode),'symlink_path')
            if x!=p:need(stat.S_ISDIR(mode),'non_directory_ancestor')
    return p


def identity(s):return (s.st_dev,s.st_ino,s.st_mode,s.st_size,s.st_mtime_ns,s.st_ctime_ns)


def read_bytes(path,limit):
    p=safe_path(path);before=p.lstat();need(stat.S_ISREG(before.st_mode) and before.st_size<=limit,'regular_bounded_file')
    with os.fdopen(os.open(p,os.O_RDONLY|os.O_NOFOLLOW),'rb') as stream:
        need(identity(os.fstat(stream.fileno()))==identity(before),'file_replaced')
        raw=stream.read(limit+1)
        need(identity(os.fstat(stream.fileno()))==identity(before),'file_changed')
    need(len(raw)==before.st_size and identity(p.lstat())==identity(before),'file_changed')
    return raw


def strict_json(raw):
    def pairs(items):
        obj={}
        for k,v in items:need(k not in obj,'duplicate_json_key');obj[k]=v
        return obj
    def invalid(_):raise ValueError('nonfinite_json')
    obj=json.loads(raw,object_pairs_hook=pairs,parse_constant=invalid)
    def finite(v):
        if isinstance(v,float):need(math.isfinite(v),'nonfinite_json')
        elif isinstance(v,dict):
            for x in v.values():finite(x)
        elif isinstance(v,list):
            for x in v:finite(x)
    finite(obj);return obj


def authenticated_json(path,pin,limit=1024**2):
    raw=read_bytes(path,limit);need(hashlib.sha256(raw).hexdigest()==pin,'public_json_sha256')
    return strict_json(raw)


def authenticate_file(path,row):
    p=safe_path(path);before=p.lstat();need(stat.S_ISREG(before.st_mode) and before.st_size==row['size_bytes'],'source_regular_size')
    sha=hashlib.sha256();md5=hashlib.md5();size=0
    with os.fdopen(os.open(p,os.O_RDONLY|os.O_NOFOLLOW),'rb') as stream:
        need(identity(os.fstat(stream.fileno()))==identity(before),'source_replaced')
        while chunk:=stream.read(1024**2):
            size+=len(chunk);need(size<=row['size_bytes'],'source_grew');sha.update(chunk);md5.update(chunk)
        need(identity(os.fstat(stream.fileno()))==identity(before),'source_changed')
    need(identity(p.lstat())==identity(before) and size==row['size_bytes'],'source_changed')
    need(sha.hexdigest()==row['sha256'] and md5.hexdigest()==row['md5'],'source_digest')
    return identity(before)


def load_inputs(data_dir,method_path):
    root=safe_path(data_dir);method_path=safe_path(method_path)
    need(root.is_dir(),'source_directory')
    contract=authenticated_json(method_path,METHOD_SHA256)
    manifest=authenticated_json(root/'source_manifest.json',SOURCE_SHA256,65536)
    notice=read_bytes(root/'SOURCE_NOTICE.md',65536)
    need(hashlib.sha256(notice).hexdigest()==NOTICE_SHA256,'source_notice_sha256')
    need(contract['subjects']==list(SUBJECTS) and manifest['subjects']==list(SUBJECTS),'fixed_cohort')
    rows=manifest['files'];need(len(rows)==24,'source_count')
    keys={(r['subject'],r['role']) for r in rows}
    need(keys=={(s,r) for s in SUBJECTS for r in ('set','fdt')},'source_keys')
    expected={r['path'] for r in rows}|{'source_manifest.json','SOURCE_NOTICE.md'}
    observed=set()
    for p in root.iterdir():
        need(stat.S_ISREG(p.lstat().st_mode),'source_nonregular_or_directory');observed.add(p.name)
    need(observed==expected,'closed_source_inventory')
    identities={}
    for row in rows:
        need(row['path']==f"sub-{row['subject']:03d}_task-N2pc_eeg.{row['role']}",'source_basename')
        identities[row['path']]=authenticate_file(root/row['path'],row)
    return dict(data_dir=root,contract=contract,manifest=manifest,identities=identities,by_key={(r['subject'],r['role']):r for r in rows})


def check_pair_identity(inputs,subject):
    for role in ('set','fdt'):
        name=inputs['by_key'][subject,role]['path'];p=safe_path(inputs['data_dir']/name)
        need(identity(p.lstat())==inputs['identities'][name],'source_pair_changed_after_authentication')


def read_metadata(inputs,subject):
    check_pair_identity(inputs,subject)
    contract=inputs['contract'];s=inputs['by_key'][subject,'set'];f=inputs['by_key'][subject,'fdt']
    raw=read_bytes(inputs['data_dir']/s['path'],16*1024**2)
    need(hashlib.sha256(raw).hexdigest()==s['sha256'],'set_changed_after_authentication')
    scanner=MatScan(raw);nodes,layout=scanner.fields()
    need('data' in nodes and nodes['data']['matlab_class']==4,'external_character_data_required')
    pointer=scalar(scanner.decode(nodes['data']));need(pointer==f['path'],'literal_fdt_pointer')
    wanted=('nbchan','pnts','trials','srate','xmin','ref','unit','units','history','chanlocs','event')
    decoded={k:scanner.decode(nodes[k]) for k in wanted if k in nodes}
    values={k:scalar(v) for k,v in decoded.items() if k not in ('event','chanlocs')}
    for key,expected in (('nbchan',33),('trials',1),('srate',1024),('xmin',0)):
        need(type(values.get(key)) in (int,float) and values[key]==expected,'source_header_'+key)
    n=values.get('pnts');need(type(n) in (int,float) and math.isfinite(n) and n>0 and n==int(n),'source_pnts');n=int(n)
    need(f['size_bytes']==4*33*n,'fdt_float32_byte_equation')
    channel_rows=records(decoded.get('chanlocs'))
    need(len(channel_rows)==33 and all(isinstance(x,dict) for x in channel_rows),'source_channel_metadata')
    labels=[scalar(x.get('labels')) for x in channel_rows]
    need(labels==contract['source']['channel_labels'],'source_channel_labels')
    need(values.get('ref')=='common' and 'unit' not in nodes and 'units' not in nodes,'source_reference_units')
    history=values.get('history');need(isinstance(history,str),'source_history')
    events=records(decoded.get('event'));need(len(events)<=10000 and all(isinstance(x,dict) for x in events),'source_events')
    events=[{k:scalar(v) for k,v in e.items()} for e in events]
    check_pair_identity(inputs,subject)
    observed=dict(subject=subject,set_path=s['path'],fdt_path=f['path'],literal_fdt_pointer=pointer,
                  sfreq_hz=1024,n_samples=n,n_channels=33,channel_labels=labels,
                  source_reference_json=values['ref'],source_units_json=None,source_bad_channels=None,
                  n_source_events=len(events),event_type_counts={},n_target_left=0,n_target_right=0,
                  n_boundary_events=0,n_bad_annotations=0,history_sha256=hashlib.sha256(history.encode('utf-8')).hexdigest())
    return dict(subject=subject,n_samples=n,events=events,observed=observed,mat_layout=layout)


def capture_warnings(destination,subject,stage,operation):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        try:return operation()
        finally:
            destination.extend(dict(subject=subject,stage=stage,category=w.category.__name__,message=str(w.message)) for w in caught)


def load_mne_eeg(inputs,metadata,warning_records):
    import mne
    subject=metadata['subject'];path=inputs['data_dir']/inputs['by_key'][subject,'set']['path']
    check_pair_identity(inputs,subject)
    contract=inputs['contract'];eog=contract['filter']['excluded_eog_channels'];eeg=contract['filter']['eeg_reference_channels']
    raw=capture_warnings(warning_records,subject,'read_raw_eeglab',lambda:mne.io.read_raw_eeglab(
        path,eog=eog,preload=False,uint16_codec=None,montage_units='auto',verbose=False))
    try:
        check_pair_identity(inputs,subject)
        need(raw.ch_names==contract['source']['channel_labels'] and raw.n_times==metadata['n_samples']
             and raw.info['sfreq']==1024 and raw.first_samp==0,'mne_source_header_mismatch')
        data=capture_warnings(warning_records,subject,'read_eeg_values',lambda:raw.get_data(picks=eeg))
        check_pair_identity(inputs,subject)
        need(data.shape==(30,metadata['n_samples']) and data.dtype==np.float64 and np.isfinite(data).all(),'source_eeg_finite_shape')
        return data
    finally:raw.close()
