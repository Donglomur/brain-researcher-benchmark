"""Private original-source reconstruction; no solution/stager/bank imports."""
import csv
import hashlib
import io
import math
import os
from pathlib import Path, PurePosixPath

import numpy as np

import artifact_reader as reader
import reference_math as arithmetic

SOURCE_SHA='2e45467d3ef720a686b13a16ac33288369e3685044d243a5fe55128910adcfc8'
METHOD_SHA='260a010f65be9a850b3ff46eaed0f5c7ec9b76c2d48cddbbd15e6636eecb8178'
SCHEMA_SHA='23f68ffbbaefb40081fe9d33e1f020af85c69f0cec88d5216394766f267a97d0'
SUBJECTS=('sub-sf02','sub-sf05','sub-sf06','sub-sf07','sub-sf08','sub-sf09','sub-sf10')


def check(condition,message):
    if not condition:raise ValueError(message)


def sha(raw):return hashlib.sha256(raw).hexdigest()


def authenticated(data_dir,manifest_path,method_path,schema_path):
    pins=(SOURCE_SHA,METHOD_SHA,SCHEMA_SHA)
    check(all(type(p)is str and len(p)==64 for p in pins),'unfrozen private authority')
    raws=[reader.read_file(p,1048576) for p in (manifest_path,method_path,schema_path)]
    check(tuple(map(sha,raws))==pins,'private document identity')
    manifest,method,schema=map(reader.json_bytes,raws)
    check(manifest['task_id']=='PETVT-001' and manifest['status']=='complete_source_identity' and
          manifest['participant_ids']==list(SUBJECTS) and manifest['n_files']==31,'fixed source identity')
    rows=manifest['files']; check(len(rows)==31 and len({r['path'] for r in rows})==31,'source member count')
    expected={r['path'] for r in rows}; expected_dirs={str(p) for n in expected for p in PurePosixPath(n).parents if str(p)!='.'}
    root=Path(data_dir);check(reader.read_file(root/'source_manifest.json',1048576)==raws[0],'internal manifest identity')
    found=set();dirs=set()
    for base,children,files in os.walk(root,followlinks=False):
        for n in children:
            p=Path(base)/n;check(not p.is_symlink(),'source directory symlink');dirs.add(str(p.relative_to(root)))
        found.update(str((Path(base)/n).relative_to(root)) for n in files)
    check(found==expected|{'source_manifest.json'} and dirs==expected_dirs,'closed source namespace')
    buffers={}
    for r in rows:
        name=r['path'];p=PurePosixPath(name)
        check(not p.is_absolute() and str(p)==name and '..'not in p.parts and '\\'not in name,'source relative path')
        check(type(r['size_bytes'])is int and 0<r['size_bytes']<=1048576,'source member size')
        raw=reader.read_file(root/name,r['size_bytes'])
        check(len(raw)==r['size_bytes'] and sha(raw)==r['sha256'],'source SHA256')
        check(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==r['git_blob_sha1'],'source Git blob')
        buffers[name]=raw
    check(sum(map(len,buffers.values()))==manifest['total_bytes']<=4194304,'source total bytes')
    return manifest,method,schema,buffers


def records(raw):
    check(b'\0'not in raw,'table NUL');csv.field_size_limit(16384)
    stream=csv.DictReader(io.StringIO(raw.decode('utf-8'),newline=''),delimiter='\t',strict=True)
    names=stream.fieldnames
    check(names and len(names)<=1024 and len(set(names))==len(names) and
          all(n and n==n.strip() and all(ord(c)>=32 and ord(c)!=127 for c in n) for n in names),'table fields')
    values=[]
    for row in stream:
        check(len(values)<4096 and None not in row and all(v is not None for v in row.values()),'table row shape')
        values.append(row)
    check(values,'empty table');return names,values


def numeric(token):
    check(token not in ('','n/a') and token==token.strip(),'required numeric token')
    v=float(token);check(math.isfinite(v),'nonfinite numeric token');return v


def extract(sid,manifest,method,buffers):
    members={r['role']:r['path'] for r in manifest['files'] if r['participant_id']==sid}
    check(set(members)=={'tac','blood','pet_metadata','blood_metadata'},'participant source roles')
    pet=reader.json_bytes(buffers[members['pet_metadata']]);meta=reader.json_bytes(buffers[members['blood_metadata']])
    check(pet['Units']=='Bq/mL' and pet['ImageDecayCorrected']is True and pet['RadionuclideHalfLife']==6586.2 and
          pet['ImageDecayCorrectionTime']==pet['InjectionStart']==pet['ScanStart']==0,'source clocks')
    check(meta['time']['Units']=='s' and meta['plasma_radioactivity']['Units']=='Bq/mL','source units')
    columns,tac=records(buffers[members['tac']]); blood_columns,blood=records(buffers[members['blood']])
    cortical=[n for n in columns if n.startswith('ctx-lh-')or n.startswith('ctx-rh-')]
    check(set(cortical)==set(method['source']['cortical_columns']) and len(tac)==method['source']['frame_counts'][sid]
          and len(blood)==method['source']['blood_row_counts'][sid],'frozen table structure')
    start=np.array([numeric(r['frame_start']) for r in tac]);end=np.array([numeric(r['frame_end']) for r in tac])
    check(len(pet['FrameTimesStart'])==len(pet['FrameDuration'])==len(tac),'frame count')
    check(abs(start[0])<=1e-6 and np.all(end>start) and np.all(np.abs(start[1:]-end[:-1])<=1e-6) and
          np.all(np.abs(start-np.asarray(pet['FrameTimesStart']))<=1e-6) and
          np.all(np.abs(end-start-np.asarray(pet['FrameDuration']))<=1e-6),'frame timing')
    cortex=np.array([[numeric(row[name]) for name in method['source']['cortical_columns']] for row in tac])
    ct=arithmetic.composite(cortex)
    by_time={}; ledger=[];missing=[]
    for index,row in enumerate(blood):
        t=numeric(row['time']);check(t>=0,'negative blood time'); reasons=[];pair=[]
        for field in ('plasma_radioactivity','metabolite_parent_fraction'):
            token=row[field]
            if token in ('','n/a'):
                reasons.append('missing_'+field);missing.append(dict(source_row=index,column=field,token=token));pair.append(None)
            else:
                v=numeric(token);check(v>=0 and (field!='metabolite_parent_fraction'or v<=1),'blood domain');pair.append(v)
        ledger.append(dict(source_row=index,time_s=t,paired_eligible=not reasons,reasons=reasons))
        if not reasons:by_time.setdefault(t,[]).append((index,pair))
    knot_ledger=[];p=[];f=[]
    for t in sorted(by_time):
        entries=by_time[t]; check(all(v==entries[0][1] for _,v in entries),'ambiguous same-time blood input')
        ids=[i for i,_ in entries]
        knot_ledger.append(dict(time_s=t,representative_source_row=min(ids),contributing_row_indices=ids,multiplicity=len(ids),exact_pair_equal=True))
        p.append(entries[0][1][0]);f.append(entries[0][1][1])
    check(len(knot_ledger)==method['source']['distinct_knot_counts'][sid],'distinct knot identity')
    times=np.array([k['time_s']for k in knot_ledger]);row_ids=[k['representative_source_row']for k in knot_ledger]
    primitive=arithmetic.primitives(start,end,ct,times,p,f)
    model={(assumption,estimator):arithmetic.fit(ct,primitive,arm,estimator)
           for arm,assumption in enumerate(arithmetic.ASSUMPTIONS) for estimator in arithmetic.ESTIMATORS}
    clock=dict(time_zero=pet['TimeZero'],scan_start_s=pet['ScanStart'],injection_start_s=pet['InjectionStart'],
        image_reference_s=pet['ImageDecayCorrectionTime'],half_life_s=pet['RadionuclideHalfLife'],concentration_units=pet['Units'])
    observed=dict(subject_id=sid,tac_path=members['tac'],blood_path=members['blood'],tac_columns=columns,
        blood_columns=blood_columns,cortical_columns=cortical,frame_count=len(tac),frame_starts_s=start.tolist(),
        frame_ends_s=end.tolist(),n_blood_rows=len(blood),missing_selected_entries=missing,invalid_domain_entries=[],
        blood_row_ledger=ledger,coalesced_knot_ledger=knot_ledger,retained_knot_rows=row_ids,
        retained_knot_times_s=times.tolist(),input_time_support=bool(len(times)>=2 and times[-1]>=(start[-1]+end[-1])/2),
        inserts_zero_anchor=bool(times.size and times[0]>0),source_clock=clock)
    return dict(frame_starts_s=start,frame_ends_s=end,tissue_concentration=ct,primitive=primitive,models=model,
        knot_rows=([-1]+row_ids if primitive['inserted_anchor']else row_ids),observed=observed)


def reconstruct(data_dir,manifest_path,method_path,schema_path,*,pilot=False):
    check(type(pilot)is bool,'pilot flag')
    manifest,method,schema,buffers=authenticated(data_dir,manifest_path,method_path,schema_path)
    selected=SUBJECTS[:1] if pilot else SUBJECTS
    people={s:extract(s,manifest,method,buffers) for s in selected}
    authenticated(data_dir,manifest_path,method_path,schema_path)
    return dict(status='resource_pilot' if pilot else 'complete',subject_ids=list(selected),persons=people,
        source_observed={'persons':[people[s]['observed'] for s in selected]},
        source_files=[{k:r[k]for k in ('path','role','participant_id','size_bytes','sha256','git_blob_sha1')}for r in manifest['files']],
        pins=dict(source_manifest_sha256=SOURCE_SHA,method_contract_sha256=METHOD_SHA,output_schema_sha256=SCHEMA_SHA),
        method=method,schema=schema)
