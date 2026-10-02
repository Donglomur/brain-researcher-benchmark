"""Original-byte reader for the supplied oracle, independent of grader code."""
from __future__ import annotations
import csv
import gzip
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import re
import stat

import nibabel as nib
import numpy as np
import core

SOURCE_SHA='70000c5c93c2c43f1e7968feb38aaebb4e7622a5f6d2ec1167191337614ef950'
IDS=tuple(f'sub-{v:04d}' for v in (*range(2,10),*range(11,23)))
MISSING={'','n/a'}
require=core.require


def safe_path(value):
    text=os.fspath(value)
    require(text.startswith('/') and '\0' not in text and all(v not in ('.','..') for v in text.split('/')),'absolute lexical path required')
    p=Path(text)
    for q in (*reversed(p.parents),p):
        if os.path.lexists(q):
            require(not q.is_symlink(),'symlink path refused')
            require(q==p or q.is_dir(),'non-directory ancestor')
    return p


def signature(info):
    return (info.st_dev,info.st_ino,info.st_mode,info.st_size,info.st_mtime_ns,info.st_ctime_ns)


def stable_bytes(path,limit,*,sha256=None):
    p=safe_path(path);before=p.lstat();require(stat.S_ISREG(before.st_mode) and 0<before.st_size<=limit,'bounded regular file required')
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as f:
        require(signature(os.fstat(f.fileno()))==signature(before),'source replaced before read')
        raw=f.read(limit+1)
        require(len(raw)==before.st_size and signature(os.fstat(f.fileno()))==signature(before),'source changed during read')
    require(signature(p.lstat())==signature(before),'source replaced after read')
    if sha256 is not None:require(hashlib.sha256(raw).hexdigest()==sha256,'source SHA256 mismatch')
    return raw


def read_member(root,row):
    raw=stable_bytes(root/row['path'],row['size_bytes'],sha256=row['sha256'])
    require(len(raw)==row['size_bytes'],'source size mismatch')
    if row['md5'] is not None:require(hashlib.md5(raw).hexdigest()==row['md5'],'source MD5 mismatch')
    if row['content_git_blob_sha1'] is not None:
        require(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==row['content_git_blob_sha1'],'source Git-blob mismatch')
    return raw


def strict_json(raw,*,documentary_path=None):
    duplicates=[]
    def pairs(items):
        out={};counts={}
        for key,value in items:
            counts[key]=counts.get(key,0)+1
            if key in out:
                same=json.dumps(out[key],sort_keys=True,allow_nan=False)==json.dumps(value,sort_keys=True,allow_nan=False)
                require(documentary_path=='participants.json' and key=='NEO_A' and same and counts[key]==2,'duplicate JSON key')
                duplicates.append(dict(path=documentary_path,key=key,occurrences=counts[key],identical=same,analysis_use=False))
            else:out[key]=value
        return out
    def bad(_):raise core.PreconditionError('nonfinite JSON number')
    result=json.loads(raw.decode('utf-8-sig'),object_pairs_hook=pairs,parse_constant=bad)
    def finite(value):
        if isinstance(value,float):require(math.isfinite(value),'nonfinite JSON number')
        elif isinstance(value,dict):
            for x in value.values():finite(x)
        elif isinstance(value,list):
            for x in value:finite(x)
    finite(result);return result,duplicates


def table(raw):
    reader=csv.reader(io.StringIO(raw.decode('utf-8-sig'),newline=''),delimiter='\t')
    header=next(reader,None);require(header and len(set(header))==len(header) and all(header),'unique TSV headers')
    records=[]
    for row in reader:
        require(len(row)==len(header),'TSV field count')
        records.append(dict(zip(header,row)))
    return header,records


def number(token,*,missing=False):
    require(isinstance(token,str),'source token string')
    if missing and token in MISSING:return None
    require(token not in MISSING,'required source number')
    try:value=float(token)
    except ValueError as exc:raise core.PreconditionError('invalid source numeric token') from exc
    require(math.isfinite(value),'finite source number');return value


def authenticate(root,manifest_path):
    root=safe_path(root);manifest_path=safe_path(manifest_path)
    raw=stable_bytes(manifest_path,256*1024,sha256=SOURCE_SHA)
    helper=Path('/opt/source/stage_data.py')
    if not helper.is_file():helper=Path(__file__).parents[1]/'environment'/'stage_data.py'
    helper=safe_path(helper);require(helper.is_file(),'source authentication helper absent')
    spec=importlib.util.spec_from_file_location('emomatch_source_stager',helper)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    manifest=module.verify_staged(root,manifest_path)
    require(manifest==strict_json(raw)[0],'manifest changed across authentication')
    return manifest,{(r['participant_id'],r['role']):r for r in manifest['files']}


def decode_nifti(raw,*,full=False):
    # The gzip decoder consumes only the already-authenticated compressed buffer.
    with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:head=stream.read(352)
    require(len(head)==352,'complete NIfTI header')
    header=nib.Nifti1Header.from_fileobj(io.BytesIO(head),check=True)
    shape=tuple(int(v) for v in header.get_data_shape());require(len(shape) in (3,4) and all(v>0 for v in shape),'NIfTI dimensions')
    dtype=header.get_data_dtype();require(dtype.kind in 'iuf' and math.prod(shape)*dtype.itemsize<=1024**3,'bounded real NIfTI payload')
    offset=float(header['vox_offset']);require(math.isfinite(offset) and offset>=352 and offset==int(offset),'NIfTI data offset')
    slope=float(header['scl_slope']);inter=float(header['scl_inter'])
    effective_slope,effective_inter=(1.,0.) if not math.isfinite(slope) or slope==0 else (slope,inter)
    require(math.isfinite(effective_inter),'finite effective intercept')
    matrix=core.affine(header.get_best_affine());units=header.get_xyzt_units()
    meta=dict(shape=list(shape),affine=matrix.tolist(),spatial_units=units[0],temporal_units=units[1],
        source_dtype=dtype.str,qform_code=int(header['qform_code']),sform_code=int(header['sform_code']),
        scaling_slope=effective_slope,scaling_intercept=effective_inter,
        raw_scaling_slope=slope if math.isfinite(slope) else None,raw_scaling_intercept=inter if math.isfinite(inter) else None,
        raw_scaling_nonfinite=dict(slope=not math.isfinite(slope),intercept=not math.isfinite(inter)),
        header_toffset_raw=float(header['toffset']) if math.isfinite(float(header['toffset'])) else None,
        header_toffset_nonfinite=not math.isfinite(float(header['toffset'])),
        header_TR=float(header.get_zooms()[3]) if len(shape)==4 else None)
    if not full:return None,meta
    length=int(offset)+math.prod(shape)*dtype.itemsize
    with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:logical=stream.read(length+1)
    require(len(logical)==length,'exact uncompressed NIfTI payload length')
    image=nib.Nifti1Image.from_bytes(logical)
    data=np.asarray(image.get_fdata(dtype=np.float64),dtype=np.float64)
    require(data.shape==shape and np.isfinite(data).all(),'finite complete scaled source image')
    return data,meta


def events(raw,participant):
    header,source=table(raw);require({'onset','duration','response_time','trial_type'}<=set(header),'required event columns')
    result=[];target_rt=[];missing=[]
    for index,row in enumerate(source):
        onset=number(row['onset']);duration=number(row['duration']);require(onset>=-24 and duration>=0,'event clock/duration')
        included=row['trial_type'] in ('emotion','control');rt=number(row['response_time'],missing=True)
        if included:require(rt is None or rt>0,'positive included response time');target_rt.append(rt or 0.);missing.append(rt is None)
        result.append(dict(participant_id=participant,source_event_row=index,trial_type_token=row['trial_type'],
            onset_token=row['onset'],duration_token=row['duration'],rt_token=row['response_time'],onset_s=onset,
            source_duration_s=duration,response_time_s=rt,included=included,
            inclusion_reason='included_target' if included else 'unsupported_trial_type',
            rt_status=('missing' if rt is None else 'valid') if included else 'not_target',
            modelA_duration_s=None,modelB_duration_s=None,modelB_imputed=False,
            source_duration_minus_rt_s=None,source_duration_minus_modelB_s=None))
    a,b,median=core.duration_models(target_rt,np.asarray(missing,dtype=bool));j=0
    for row in result:
        if row['included']:
            row.update(modelA_duration_s=float(a[j]),modelB_duration_s=float(b[j]),modelB_imputed=bool(missing[j]),
                source_duration_minus_rt_s=row['source_duration_s']-row['response_time_s'] if not missing[j] else None,
                source_duration_minus_modelB_s=row['source_duration_s']-float(b[j]));j+=1
    valid=[r['source_duration_minus_rt_s'] for r in result if r['included'] and r['rt_status']=='valid']
    imputed=[r['source_duration_minus_modelB_s'] for r in result if r['included'] and r['rt_status']=='missing']
    diagnostic=dict(participant_id=participant,n_target_with_source_duration=j,n_valid_rt_and_duration=len(valid),
        n_imputed_rt_and_duration=len(imputed),n_exact_source_duration_rt_differences=sum(v!=0 for v in valid),
        max_abs_source_duration_minus_rt_s=max(map(abs,valid),default=None),
        max_abs_source_duration_minus_imputed_modelB_s=max(map(abs,imputed),default=None))
    return header,result,median,diagnostic


def confounds(raw,n_frames):
    header,rows=table(raw);require(set(core.CONFOUNDS)<=set(header) and len(rows)==n_frames,'confound support')
    values=np.zeros((n_frames,len(core.CONFOUNDS)));missing=np.zeros_like(values,dtype=bool)
    for i,row in enumerate(rows):
        for j,key in enumerate(core.CONFOUNDS):
            value=number(row[key],missing=True);missing[i,j]=value is None;values[i,j]=value or 0.
    return header,core.impute_confounds(values,missing),missing


def atlas(root,rows):
    data,head=decode_nifti(read_member(root,rows[(None,'atlas_image')]),full=True)
    require(data.ndim==3 and head['spatial_units']=='mm' and np.array_equal(data,np.rint(data)),'integer atlas in mm')
    require(set(np.unique(data))==set(range(101)),'released atlas labels0..100')
    columns,lut=table(read_member(root,rows[(None,'atlas_labels')]))
    require({'index','name','color'}<=set(columns),'atlas LUT columns')
    labels={}
    for row in lut:
        require(re.fullmatch(r'[0-9]+',row['index']) is not None,'integer LUT index')
        index=int(row['index'])
        if index==0:continue
        match=re.fullmatch(r'7Networks_(LH|RH)_([^_]+)_.+',row['name'])
        require(match is not None and match[2] in core.NETWORKS and index not in labels,'unique named network label')
        labels[index]=dict(label_name=row['name'],network=match[2])
    require(set(labels)==set(range(1,101)) and {r['network'] for r in labels.values()}==set(core.NETWORKS),'all100 labels/seven networks')
    meta=dict(image_path=rows[(None,'atlas_image')]['path'],labels_path=rows[(None,'atlas_labels')]['path'],
        template_name='MNI152NLin2009cAsym',shape=head['shape'],affine=head['affine'],label_ids=list(range(1,101)),
        network_names=list(core.NETWORKS),spatial_units=head['spatial_units'])
    return data.astype(np.int16),np.asarray(head['affine']),labels,meta


def metadata(root,rows):
    _,participants=table(read_member(root,rows[(None,'participants')]))
    require(participants and 'participant_id' in participants[0],'participant column')
    ids=[r['participant_id'] for r in participants]
    require(len(set(ids))==len(ids) and set(IDS)<=set(ids),'literal participant membership')
    _,duplicates=strict_json(read_member(root,rows[(None,'participants_schema')]),documentary_path='participants.json')
    task,_=strict_json(read_member(root,rows[(None,'task_bold_json')]))
    derivative,_=strict_json(read_member(root,rows[(None,'derivative_description')]))
    version=derivative['PipelineDescription']['Version']
    observed=dict(participants=[],event_column_names={},confound_column_names={},duration_rt_comparison=[],
        documentary_duplicate_keys=duplicates,documented_timing=dict(task_bold_path=rows[(None,'task_bold_json')]['path'],
        raw_bold_paths={},preproc_bold_paths={},scanner_discarded_volumes={},inherited_slice_timing_s=task['SliceTiming'],
        frame_origin_s=0.,exporter_frame_reference='unknown',additional_discarded_frames=0,fmriprep_version_literal=version))
    cohort=[];all_events=[];person={}
    for index,source in enumerate(participants):
        pid=source['participant_id'];selected=pid in IDS
        row=dict(source_row=index,participant_id=pid,selected=selected,
            selection_reason='selected_fixed_cohort' if selected else 'not_in_fixed_cohort',source_status='ok' if selected else 'not_selected')
        nullable=['bold_path','confounds_path','events_path','n_frames','n_emotion','n_control','n_valid_rt_emotion',
            'n_valid_rt_control','n_missing_rt_emotion','n_missing_rt_control','median_rt_s']
        row.update({k:None for k in nullable})
        if selected:
            _,head=decode_nifti(read_member(root,rows[(pid,'bold')]))
            require(head['shape']==[65,77,60,135] and np.dtype(head['source_dtype']).kind=='f' and np.dtype(head['source_dtype']).itemsize==4,'fixed source dimensions/dtype')
            require(head['spatial_units']=='mm' and head['temporal_units']=='sec' and head['header_TR']==2.,'source units/TR')
            evhead,ev,median,diagnostic=events(read_member(root,rows[(pid,'events')]),pid)
            cfhead,cf,mask=confounds(read_member(root,rows[(pid,'confounds')]),135)
            rawjson,_=strict_json(read_member(root,rows[(pid,'raw_bold_json')]))
            prejson,_=strict_json(read_member(root,rows[(pid,'preproc_bold_json')]))
            require(rawjson['RepetitionTime']==prejson['RepetitionTime']==2.,'documented TR')
            timing=observed['documented_timing'];timing['raw_bold_paths'][pid]=rows[(pid,'raw_bold_json')]['path']
            timing['preproc_bold_paths'][pid]=rows[(pid,'preproc_bold_json')]['path']
            timing['scanner_discarded_volumes'][pid]=rawjson['NumberOfVolumesDiscardedByScanner']
            header={k:v for k,v in head.items() if k!='shape'}
            header.update(participant_id=pid,bold_shape=head['shape'],effective_TR_s=2.,effective_origin_s=0.,
                n_confound_rows=135,grid_id=core.grid_id(tuple(head['shape'][:3]),head['affine']))
            observed['participants'].append(header);observed['event_column_names'][pid]=evhead
            observed['confound_column_names'][pid]=cfhead;observed['duration_rt_comparison'].append(diagnostic)
            for role in ('bold','confounds','events'):row[role+'_path']=rows[(pid,role)]['path']
            row.update(n_frames=135,median_rt_s=median)
            for condition in ('emotion','control'):
                items=[e for e in ev if e['included'] and e['trial_type_token']==condition]
                row['n_'+condition]=len(items);row['n_valid_rt_'+condition]=sum(e['rt_status']=='valid' for e in items)
                row['n_missing_rt_'+condition]=sum(e['rt_status']=='missing' for e in items)
            all_events.extend(ev);person[pid]=dict(header=header,events=ev,confound_effective=cf,confound_was_missing=mask)
        cohort.append(row)
    return cohort,all_events,person,observed
