"""Offline, source-bound duration-model sensitivity oracle. Import-safe."""
from __future__ import annotations
import argparse
import csv
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import sys
import warnings

import numpy as np
import core
import source_reader as sr

METHOD_SHA='d86db9e607dfe1668b2aa6883c83a463895beb352712c8d6a53ebfe895e99234'
SCHEMA_SHA='7beec618b63f86fbe66d6223be7e3702ca3bdb8bcc384ed2c651fbf02ccd8b8b'
MODELS=('modelA','modelB')
AGGREGATES={'amygdala':['amy_L','amy_R'],'fusiform':['ffa_L','ffa_R'],
    'control':['dACC','aIns_L','aIns_R','dlPFC_L','dlPFC_R','IPS_L','IPS_R']}
require=core.require


def protected_destinations(output,private,protected):
    dests=[sr.safe_path(p) for p in (output,private) if p is not None]
    protected=[sr.safe_path(p) for p in protected]
    for index,a in enumerate(dests):
        require(a!=Path('/') and a.parent.is_dir(),'output parent must exist')
        if a.exists():require(a.is_dir() and not any(a.iterdir()),'fresh or empty output directory required')
        for b in dests[index+1:]+protected:
            require(a!=b and a not in b.parents and b not in a.parents,'overlapping source/output/private paths')
    return dests


def write_bytes(path,raw):
    with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb') as f:f.write(raw)


def write_json(path,value):
    write_bytes(path,(json.dumps(value,indent=2,allow_nan=False)+'\n').encode())


def write_csv(path,rows,columns):
    with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=columns,extrasaction='ignore',lineterminator='\n')
        writer.writeheader()
        for row in rows:
            writer.writerow({k:int(v) if isinstance(v,(bool,np.bool_)) else v for k,v in row.items()})


def write_npz(path,arrays):
    for key,value in arrays.items():
        a=np.asarray(value);require(a.dtype.kind in 'biufUS','primitive evidence array '+key)
        if a.dtype.kind in 'iuf':require(np.isfinite(a).all(),'finite evidence array '+key)
    with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb') as f:
        np.savez_compressed(f,**arrays)


def support_rows(pid,header,atlas_labels,atlas_affine,label_info):
    supports,geometry=core.geometric_supports(tuple(header['bold_shape'][:3]),header['affine'],atlas_labels,atlas_affine)
    rows=[]
    for key,indices in supports.items():
        require(len(indices)>0,'empty required support: '+pid+'/'+key)
        sphere=key in core.SPHERES;center=core.SPHERES[key] if sphere else (None,None,None)
        rows.append(dict(participant_id=pid,roi_id=key,family='sphere' if sphere else 'parcel',
            label_name=key if sphere else label_info[int(key)]['label_name'],
            network=None if sphere else label_info[int(key)]['network'],atlas_label=None if sphere else int(key),
            center_x=center[0],center_y=center[1],center_z=center[2],radius=6. if sphere else None,
            grid_id=geometry['grid_id'],n_voxels=len(indices),support_sha256=core.support_digest(indices),support_status='ok'))
    return supports,rows


def fit_person(pid,raw,person):
    y,mean,sd,denominator,constant=core.normalize_roi(raw)
    frames=np.arange(len(raw),dtype=np.float64)*person['header']['effective_TR_s']
    included=[e for e in person['events'] if e['included']];fits=[]
    for model in MODELS:
        seen=[]
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            x,names,contrast,presence=core.construct_design([e['onset_s'] for e in included],
                [e['trial_type_token'] for e in included],[e[model+'_duration_s'] for e in included],frames,person['confound_effective'])
            fit=core.minimum_norm(x,y,contrast,conditions_present=all(presence.values()))
        for w in caught:
            seen.append(dict(category=w.category.__name__,message=str(w.message)))
            print('warning: '+str(w.message),file=sys.stderr,flush=True)
        diagnostic=dict(participant_id=pid,model=model,status=fit['status'],n_observations=len(raw),n_columns=len(names),
            rank=fit['rank'],residual_df=fit['residual_df'],singular_values=fit['singular_values'].tolist(),
            rank_cutoff=fit['rank_cutoff'],contrast_rowspace_residual=fit['contrast_rowspace_residual'],
            estimability_bound=fit['estimability_bound'],n_exact_constant_rois=int(constant.sum()),
            solver='NumPy float64 SVD minimum norm; pinned Nilearn SPM/cosine; public fsum normalization',warnings=seen)
        fits.append(dict(model=model,design=x,names=names,contrast=contrast,fit=fit,diagnostic=diagnostic))
    return dict(participant_id=pid,raw=raw,normalized=y,mean=mean,sd=sd,denominator=denominator,constant=constant,
        frames=frames,confounds=person['confound_effective'],missing=person['confound_was_missing'],fits=fits)


def compile_arrays(people,roi_ids):
    columns=[]
    for person in people:
        for fit in person['fits']:
            for key in fit['names']:
                if key not in columns:columns.append(key)
    per_frame={k:[] for k in ('frame_subject_index','source_frame_index','frame_time_s','roi_mean','roi_normalized','confound_effective','confound_was_missing')}
    per_fit={k:[] for k in ('fit_subject_index','fit_model','column_present','beta','contrast_vector','contrast_estimate','contrast_defined','design_rank','residual_df','contrast_estimable','residual_sse')}
    observations={k:[] for k in ('observation_fit_index','observation_frame_index','design_matrix')}
    offset=0;fit_index=0
    for subject_index,person in enumerate(people):
        n=len(person['raw']);per_frame['frame_subject_index'].append(np.full(n,subject_index,dtype=np.int64))
        per_frame['source_frame_index'].append(np.arange(n,dtype=np.int64))
        for key,value in [('frame_time_s','frames'),('roi_mean','raw'),('roi_normalized','normalized'),('confound_effective','confounds'),('confound_was_missing','missing')]:per_frame[key].append(person[value])
        for item in person['fits']:
            index=[columns.index(k) for k in item['names']];fit=item['fit'];j=len(columns)
            x=np.zeros((n,j));x[:,index]=item['design'];beta=np.zeros((j,len(roi_ids)));beta[index]=fit['beta']
            contrast=np.zeros(j);contrast[index]=item['contrast'];present=np.zeros(j,dtype=bool);present[index]=True
            values=dict(fit_subject_index=subject_index,fit_model=item['model'],column_present=present,beta=beta,
                contrast_vector=contrast,contrast_estimate=fit['contrast_estimate'],contrast_defined=fit['contrast_defined'],
                design_rank=fit['rank'],residual_df=fit['residual_df'],contrast_estimable=fit['contrast_estimable'],residual_sse=fit['residual_sse'])
            for key,value in values.items():per_fit[key].append(value)
            observations['observation_fit_index'].append(np.full(n,fit_index,dtype=np.int64))
            observations['observation_frame_index'].append(np.arange(offset,offset+n,dtype=np.int64))
            observations['design_matrix'].append(x);fit_index+=1
        offset+=n
    arrays=dict(participant_id=np.asarray([p['participant_id'] for p in people]),roi_id=np.asarray(roi_ids),
        confound_name=np.asarray(core.CONFOUNDS),column_key=np.asarray(columns),
        roi_raw_mean=np.asarray([p['mean'] for p in people]),roi_raw_sd=np.asarray([p['sd'] for p in people]),
        normalization_denominator=np.asarray([p['denominator'] for p in people]))
    arrays.update({key:np.concatenate(value,axis=0) for key,value in per_frame.items()})
    arrays.update({key:np.asarray(value) for key,value in per_fit.items()})
    arrays.update({key:np.concatenate(value,axis=0) for key,value in observations.items()})
    return arrays


def summaries(people,roi_ids,label_info,all_events,status,schema_id):
    subjects={p['participant_id']:p for p in people};groups={key:[key] for key in core.SPHERES}
    groups.update(AGGREGATES)
    for network in core.NETWORKS:groups[network]=[str(i) for i in range(1,101) if label_info[i]['network']==network]
    require(all(groups.values()),'nonempty endpoint supports')
    person_values={};activation=[]
    for pid in sr.IDS:
        if pid not in subjects:continue
        row=dict(participant_id=pid)
        for item in subjects[pid]['fits']:
            fit=item['fit'];model=item['model']
            for endpoint,keys in groups.items():
                index=[roi_ids.index(key) for key in keys]
                value=math.fsum(float(fit['contrast_estimate'][i]) for i in index)/len(index) if all(fit['contrast_defined'][index]) else None
                person_values[(pid,model,endpoint)]=value
                if endpoint in AGGREGATES:row[endpoint+'_'+model]=value;row[endpoint+'_'+model+'_status']='ok' if value is not None else 'incomplete_support'
        activation.append(row)
    expected=len(sr.IDS);model_records=[]
    for model in MODELS:
        for endpoint,keys in groups.items():
            model_records.append(dict(model=model,endpoint=endpoint,roi_ids=keys,weights=[1/len(keys)]*len(keys),
                statistic=core.complete_statistic([person_values.get((pid,model,endpoint)) for pid in sr.IDS],expected)))
    changes={};paired=[]
    for endpoint in AGGREGATES:
        values=[]
        for pid in sr.IDS:
            a=person_values.get((pid,'modelA',endpoint));b=person_values.get((pid,'modelB',endpoint))
            values.append(b-a if a is not None and b is not None else None)
        changes[endpoint]=values
        paired.append(dict(endpoint=endpoint+'_B_minus_A',statistic=core.complete_statistic(values,expected)))
    diff=[a-b if a is not None and b is not None else None for a,b in zip(changes['amygdala'],changes['control'])]
    paired.append(dict(endpoint='amygdala_change_minus_control_change',statistic=core.complete_statistic(diff,expected)))
    rt=[]
    for pid in sr.IDS:
        row=dict(participant_id=pid)
        for condition in ('emotion','control'):
            values=[e['response_time_s'] for e in all_events if e['participant_id']==pid and e['included'] and e['trial_type_token']==condition and e['rt_status']=='valid']
            row['n_valid_'+condition]=len(values);row['mean_'+condition+'_s']=math.fsum(values)/len(values) if values else None
        a,b=row['mean_emotion_s'],row['mean_control_s'];row['difference_s']=a-b if a is not None and b is not None else None;rt.append(row)
    rt_summary=dict(per_subject=rt)
    for key,field in [('emotion','mean_emotion_s'),('control','mean_control_s'),('emotion_minus_control','difference_s')]:
        # The pilot does not turn 20 source-metadata records into full-cohort inference.
        values=[r[field] if status=='complete' or r['participant_id'] in subjects else None for r in rt]
        rt_summary[key]=core.complete_statistic(values,expected)
    return activation,dict(schema_id=schema_id,status=status,n_expected=expected,models=model_records,paired_changes=paired,rt_summary=rt_summary)


def failure_evidence(output,error):
    reason=str(error) or type(error).__name__;receipt=dict(status='failed_precondition',error_type=type(error).__name__,reason=reason)
    write_json(output/'failure_report.json',receipt)
    for name in ('run_metadata.json','group_stats.json'):
        if not os.path.lexists(output/name):write_json(output/name,receipt)
    if not os.path.lexists(output/'findings.md'):write_bytes(output/'findings.md',('Source or analysis precondition failed: '+reason+'\n').encode())


def run(args):
    root=sr.safe_path(args.data_dir);output=sr.safe_path(args.output_dir)
    private=sr.safe_path(args.private_dir) if args.private_dir else None
    source_manifest=sr.safe_path(args.source_manifest);method_path=sr.safe_path(args.method_contract);schema_path=sr.safe_path(args.output_schema)
    protected_destinations(output,private,[root,source_manifest,method_path,schema_path,Path(__file__).parent])
    for path in (output,private):
        if path is not None:path.mkdir(mode=0o755,exist_ok=True)
    try:
        method=sr.strict_json(sr.stable_bytes(method_path,1024**2,sha256=METHOD_SHA))[0]
        schema=sr.strict_json(sr.stable_bytes(schema_path,1024**2,sha256=SCHEMA_SHA))[0]
        require(method['participant_ids']==list(sr.IDS) and list(method['spatial']['spheres'])==list(core.SPHERES),'method implementation identities')
        manifest,rows=sr.authenticate(root,source_manifest)
        cohort,events,person,observed=sr.metadata(root,rows)
        labels,atlas_affine,label_info,atlas_meta=sr.atlas(root,rows);observed['atlas']=atlas_meta
        selected=[args.pilot_subject] if args.pilot_subject else list(sr.IDS)
        require(not args.pilot_subject or args.pilot_subject=='sub-0002','only fixed first-person pilot supported')
        status='resource_pilot' if args.pilot_subject else 'complete';roi_ids=method['spatial']['roi_ids']
        supports_by_person={};support_table=[]
        for pid in sr.IDS:
            supports,records=support_rows(pid,person[pid]['header'],labels,atlas_affine,label_info)
            supports_by_person[pid]=supports;support_table.extend(records)
        people=[]
        for pid in selected:
            print(json.dumps(dict(participant_id=pid,phase='read_original_values')),flush=True)
            data,header=sr.decode_nifti(sr.read_member(root,rows[(pid,'bold')]),full=True)
            require(header['shape']==person[pid]['header']['bold_shape'] and header['affine']==person[pid]['header']['affine'],'source header changed')
            raw=core.voxel_means(data,[supports_by_person[pid][key] for key in roi_ids]);del data
            record=fit_person(pid,raw,person[pid]);people.append(record)
            if private is not None:
                arrays=dict(roi_id=np.asarray(roi_ids),raw_mean=raw,normalized=record['normalized'],raw_time_mean=record['mean'],
                    raw_time_sd=record['sd'],denominator=record['denominator'],constant=record['constant'],
                    confounds=record['confounds'],confound_missing=record['missing'])
                for item in record['fits']:
                    model=item['model'];fit=item['fit'];arrays[model+'_design']=item['design']
                    for key in ('beta','singular_values','u','vt','retained_singular_mask','residual_sse'):arrays[model+'_'+key]=fit[key]
                write_npz(private/(pid+'.npz'),arrays)
            print(json.dumps(dict(participant_id=pid,phase='fits_complete',ranks=[x['fit']['rank'] for x in record['fits']])),flush=True)
        arrays=compile_arrays(people,roi_ids)
        activation,groups=summaries(people,roi_ids,label_info,events,status,schema['schema_id'])
        fits=[item['diagnostic'] for p in people for item in p['fits']]
        versions={name:importlib.metadata.version(name) for name in ('numpy','scipy','nibabel','nilearn')};versions['python']=platform.python_version()
        metadata=dict(schema_id=schema['schema_id'],task_id='EMOMATCH-001',status=status,source_manifest_sha256=sr.SOURCE_SHA,
            method_contract_sha256=METHOD_SHA,method=method,selected_participant_ids=list(sr.IDS),
            source_files=[{key:r[key] for key in ('path','role','participant_id','size_bytes','sha256')} for r in manifest['files']],
            source_observed=observed,fits=fits,software_versions=versions,warnings=[w for f in fits for w in f['warnings']])
        if args.pilot_subject:
            scope=dict(authenticated_participants=list(sr.IDS),header_and_event_metadata_participants=list(sr.IDS),
                signal_and_fit_participants=selected,not_complete_production=True)
            metadata['resource_pilot_scope']=scope;groups['resource_pilot_scope']=scope
        if private is not None:write_json(private/'fit_diagnostics.json',fits)
        tables={'cohort.csv':cohort,'events.csv':events,'roi_support.csv':support_table,'activation.csv':activation}
        for name,records in tables.items():write_csv(output/name,records,list(schema['tables'][name]['required_columns']))
        write_npz(output/'glm_arrays.npz',arrays)
        lines=['# Fixed-cohort duration-model sensitivity','',
            'Both models use identical source frames, spatial measurements and nuisance regressors. The signed emotion-minus-control contrast changes with regressor duration/scale; it is not a causal RT adjustment or proof of emotion specificity.','',
            'Run status: '+status+'. Processed '+str(len(people))+' of '+str(len(sr.IDS))+' fixed participants.','',
            '| Paired endpoint | Defined / expected | Mean B-minus-A |','|---|---:|---:|']
        for row in groups['paired_changes']:
            s=row['statistic'];mean='undefined' if s['mean'] is None else format(s['mean'],'.12g')
            lines.append('| '+row['endpoint']+' | '+str(s['n_defined'])+'/'+str(s['n_expected'])+' | '+mean+' |')
        lines+=['','Uncertainty is descriptive and uncorrected across the declared endpoint families. Missing response times use the pooled median, not an asserted observed display duration. Source frame origin zero is a computational convention.']
        write_bytes(output/'findings.md',('\n'.join(lines)+'\n').encode())
        # Complete JSON markers are last; any later error creates authoritative failure_report.json.
        write_json(output/'group_stats.json',groups);write_json(output/'run_metadata.json',metadata)
        if private is not None:write_json(private/'completion.json',dict(status=status,participants=selected,source_manifest_sha256=sr.SOURCE_SHA,method_contract_sha256=METHOD_SHA))
        return dict(status=status,participants=len(people),fits=len(fits),arrays={key:list(value.shape) for key,value in arrays.items()},warnings=len(metadata['warnings']))
    except BaseException as error:
        failure_evidence(output,error);raise


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir',default=os.environ.get('DATA_DIR','/app/data/emomatch'))
    parser.add_argument('--source-manifest',default=os.environ.get('SOURCE_MANIFEST','/app/source_manifest.json'))
    parser.add_argument('--method-contract',default=os.environ.get('METHOD_CONTRACT','/app/method_contract.json'))
    parser.add_argument('--output-schema',default=os.environ.get('OUTPUT_SCHEMA','/app/output_schema.json'))
    parser.add_argument('--output-dir',default=os.environ.get('OUTPUT_DIR','/app/output'))
    parser.add_argument('--private-dir',default=os.environ.get('PRIVATE_DIR'))
    parser.add_argument('--pilot-subject',choices=['sub-0002'])
    args=parser.parse_args(argv)
    try:print(json.dumps(run(args),allow_nan=False),flush=True);return 0
    except BaseException as error:
        print(json.dumps(dict(status='failed_precondition',error_type=type(error).__name__,reason=str(error) or type(error).__name__)),file=sys.stderr,flush=True);return 1


if __name__=='__main__':raise SystemExit(main())
