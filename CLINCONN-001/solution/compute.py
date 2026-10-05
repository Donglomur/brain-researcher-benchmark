"""Offline original-source CNP association/sensitivity oracle, not a paper-finding claim."""
import argparse
import copy
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import sys
import traceback

import nibabel as nib
import numpy as np
import scipy
from scipy import linalg, signal, stats

TASK_ID='CLINCONN-001'
METHOD_SHA256='7378a0ccd4663907e2e8df3db724ba9caa3e21ee80b955ea637863db1769a23c'
SOURCE_SHA256='f4ea1c9f5a3a75d722fedd2cece082dd84502f20c5c7d2d11704c5bcc45594e3'
EPS=np.finfo(np.float64).eps
TINY=np.finfo(np.float64).tiny
CONF=['X','Y','Z','RotX','RotY','RotZ','aCompCor00','aCompCor01','aCompCor02','aCompCor03','aCompCor04','aCompCor05','WhiteMatter']
MODELS=('all_crude','all_fd_adjusted')


def require(condition,message):
    if not condition:raise ValueError(message)


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()


def reject_symlinks(path):
    p=Path(path).absolute()
    require(not any(x.is_symlink() for x in (p,*p.parents)),'Symlinked evidence/source path forbidden')


def validate_destinations(source,output,private):
    paths=[Path(p).absolute() for p in (source,output,private)]
    for p in paths:reject_symlinks(p)
    for i,p in enumerate(paths):
        for q in paths[i+1:]:require(p!=q and p not in q.parents and q not in p.parents,'Source/output/private must be distinct and nonnested')
    for p in paths[1:]:require(not p.exists(),'Refuse existing output/evidence destination')


def stager_module():
    local=Path(__file__).resolve().parents[1]/'environment/stage_data.py'
    path=local if local.is_file() else Path('/opt/source/stage_data.py')
    require(path.is_file(),'Original source integrity checker missing')
    spec=importlib.util.spec_from_file_location('clinconn_source_integrity',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def load_inputs(data_dir,method_contract):
    data_dir=Path(data_dir);method_contract=Path(method_contract)
    reject_symlinks(method_contract)
    require(digest(method_contract)==METHOD_SHA256,'Public method bytes changed')
    method=json.loads(method_contract.read_text())
    manifest=stager_module().verify_staged(data_dir)
    require(digest(data_dir/'source_manifest.json')==SOURCE_SHA256,'Original bundle manifest changed')
    require(method['source']['source_manifest_sha256']==SOURCE_SHA256,'Method/source identity mismatch')
    paths={}
    for record in manifest['files']:
        key=(record['role'],record.get('participant'))
        if record['role']=='legacy_metadata':key=(record['role'],Path(record['path']).name)
        require(key not in paths,'Duplicate original role/participant')
        paths[key]=data_dir/record['path']
    return dict(data_dir=data_dir,method=method,manifest=manifest,paths=paths,
                source_sha256={r['path']:r['sha256'] for r in manifest['files']})


def source_cohort(inputs):
    with inputs['paths'][('legacy_metadata','participants.tsv')].open(newline='') as f:
        participants=list(csv.DictReader(f,delimiter='\t'))
    frozen={r['participant_id']:r for r in inputs['manifest']['cohort']['rows']}
    rows=[]
    for index,p in enumerate(participants):
        if p['rest']!='1' or p['diagnosis'] not in ('SCHZ','CONTROL'):continue
        pid=p['participant_id'];require(pid in frozen,'Source candidate absent from frozen availability ledger')
        r=frozen[pid];selected=r['selected']
        require(type(selected) is bool and r['diagnosis']==p['diagnosis'],'Frozen phenotype/source differs')
        for role in ('surface_left','surface_right','confounds'):
            require(((role,pid) in inputs['paths'])==selected,'Availability does not match frozen original inventory')
        rows.append(dict(source_participant_row=index,subject_id=pid,group=p['diagnosis'],source_rest=p['rest'],
                         available_left=selected,available_right=selected,available_confounds=selected,selected=selected,
                         exclusion_reason='selected' if selected else 'unavailable_released_derivatives'))
    require(len(participants)==272 and len(rows)==177 and len({r['subject_id'] for r in rows})==177,'Original phenotype identity/count mismatch')
    selected=sorted((r for r in rows if r['selected']),key=lambda r:r['subject_id'])
    require(len(selected)==172 and sum(r['group']=='SCHZ' for r in selected)==50,'Fixed cohort/group counts differ')
    return rows,selected


def load_atlas(inputs):
    method=inputs['method'];required=method['outputs']['run_metadata.json']['source_observed']['atlas']['required_value']
    observed={k:copy.deepcopy(v) for k,v in required.items() if k!='hemispheres'};observed['hemispheres']={}
    parcels=[];label_arrays={};members=[];centroids=[]
    for hemi,long in [('L','left'),('R','right')]:
        annot=inputs['paths'][('annotation_'+long,None)];pial=inputs['paths'][('pial_'+long,None)]
        labels,colors,names=nib.freesurfer.read_annot(annot,orig_ids=False);names=[x.decode('utf8') for x in names]
        image=nib.load(pial);pointsets=[a for a in image.darrays if a.intent==1008];meshes=[a for a in image.darrays if a.intent==1009]
        require(len(pointsets)==len(meshes)==1,'Pial pointset/triangle identities differ')
        pointset=pointsets[0];xyz=np.asarray(pointset.data,dtype=np.float64);faces=np.asarray(meshes[0].data);cs=pointset.coordsys;meta=dict(pointset.meta)
        require(xyz.ndim==2 and xyz.shape[1]==3 and np.isfinite(xyz).all(),'Invalid original pial coordinates')
        require(len(xyz)==len(labels) and faces.ndim==2 and faces.shape[1]==3 and faces.dtype.kind in 'iu' and faces.min()>=0 and faces.max()<len(labels),'Invalid original surface topology')
        observed['hemispheres'][hemi]=dict(annotation_sha256=digest(annot),pial_sha256=digest(pial),n_vertices=len(labels),n_faces=len(faces),n_annotation_rows=len(names),
            unknown_annotation_index=names.index('Unknown'),medial_wall_annotation_index=names.index('Medial_wall'),n_unknown_vertices=int(np.sum(labels==names.index('Unknown'))),
            n_medial_wall_vertices=int(np.sum(labels==names.index('Medial_wall'))),n_unassigned_vertices=int(np.sum(labels<0)),pointset_structure=meta.get('AnatomicalStructurePrimary'),
            pointset_surface=meta.get('AnatomicalStructureSecondary'),pointset_dataspace=int(cs.dataspace),pointset_xformspace=int(cs.xformspace),pointset_xform=cs.xform.tolist())
        require(observed['hemispheres'][hemi]==required['hemispheres'][hemi],'Pinned original atlas geometry/legend metadata differs')
        label_arrays[hemi]=labels
        indices=([-1] if np.any(labels<0) else [])+list(range(len(names)))
        for index in indices:
            mask=labels==index;count=int(mask.sum());name='unassigned' if index==-1 else names[index]
            reason=('unassigned' if index==-1 else 'unknown_label' if name=='Unknown' else 'medial_wall' if name=='Medial_wall' else 'empty_label' if count==0 else 'included')
            center=xyz[mask].mean(axis=0) if count else [None]*3
            row=dict(parcel_id=f'{hemi}:{index}',hemisphere=hemi,annotation_index=index,annotation_name=name,n_vertices=count,included=reason=='included',exclusion_reason=reason,
                     centroid_x=center[0],centroid_y=center[1],centroid_z=center[2]);parcels.append(row)
            if reason=='included':members.append((hemi,index,mask));centroids.append(center)
    require(observed==required,'Original atlas observed metadata differs')
    included=[p['parcel_id'] for p in parcels if p['included']]
    require(len(included)==148,'Canonical cortical parcel inventory differs')
    xyz=np.asarray(centroids);ij=np.triu_indices(len(included),1);distance=np.linalg.norm(xyz[ij[0]]-xyz[ij[1]],axis=1)
    return dict(parcels=parcels,parcel_id=np.asarray(included),members=members,labels=label_arrays,edge_i=ij[0],edge_j=ij[1],distance=distance,observed=observed)


def centered(values):
    values=np.asarray(values,dtype=np.float64)
    if values.ndim==1:
        return np.zeros_like(values) if len(values) and np.all(values==values[0]) else values-values.mean()
    out=values-values.mean(axis=0)
    out[:,np.all(values==values[:1],axis=0)]=0
    return out


def detrended(values):
    out=centered(values);time=centered(np.arange(len(out),dtype=np.float64));norm=np.dot(time,time)
    require(norm>0,'At least two original frames required')
    return out-np.outer(time,time@out/norm)


def clean_parcels(raw,confounds):
    raw=np.asarray(raw,dtype=np.float64);confounds=np.asarray(confounds,dtype=np.float64)
    require(raw.ndim==confounds.ndim==2 and len(raw)==len(confounds) and len(raw)>33 and confounds.shape[1]==13,'Signal/confound frame support differs')
    require(np.isfinite(raw).all() and np.isfinite(confounds).all(),'Nonfinite original parcel/nuisance inputs')
    original_centered=centered(raw);original_norm=np.linalg.norm(original_centered,axis=0);constant=np.all(raw==raw[:1],axis=0)
    sos=signal.butter(5,[.009,.08],btype='bandpass',fs=.5,output='sos')
    filtered=signal.sosfiltfilt(sos,detrended(raw),axis=0,padtype='odd',padlen=33)
    cf=signal.sosfiltfilt(sos,detrended(confounds),axis=0,padtype='odd',padlen=33)
    cs=centered(cf);sd=np.std(cs,axis=0,ddof=0);sd[sd<EPS]=1;cs=cs/sd
    q,r,piv=linalg.qr(cs,mode='economic',pivoting=True)
    keep=np.abs(np.diag(r))>100*EPS;q=q[:,keep]
    residual=centered(filtered-q@(q.T@filtered));norm=np.linalg.norm(residual,axis=0)
    bound=10*max(len(raw),13)*EPS*np.maximum(original_norm,TINY)
    status=np.full(raw.shape[1],'ok',dtype='<U24');status[norm<=bound]='numerical_zero_residual';status[constant]='constant_input'
    valid=status=='ok';standardized=np.zeros_like(residual)
    standardized[:,valid]=residual[:,valid]/(norm[valid]/np.sqrt(len(raw)-1))
    require(np.isfinite(standardized).all() and np.isfinite(norm).all(),'Nonfinite cleaned parcel values')
    return dict(raw_parcel=raw,filtered_parcel=filtered,residual=residual,standardized=standardized,confounds_original=confounds,
                confounds_filtered=cf,confounds_standardized=cs,nuisance_q=q,nuisance_rank=q.shape[1],nuisance_pivots=piv,
                parcel_status=status,parcel_original_centered_l2=original_norm,parcel_residual_l2=norm,parcel_zero_bound=bound,sos=sos)


def fd_summary(values):
    fd=np.asarray(values,dtype=np.float64)
    require(fd.ndim==1 and len(fd)>0,'Empty original FD column')
    require(np.isfinite(fd[1:]).all() and np.all(fd[1:]>=0),'Missing/negative later FD')
    require(np.isnan(fd[0]) or (np.isfinite(fd[0]) and fd[0]>=0),'Invalid first FD')
    valid=np.isfinite(fd);require(valid.any(),'No defined source FD')
    total=float(np.sum(fd[valid],dtype=np.float64));mean=total/int(valid.sum())
    return dict(fd_sum=total,n_fd_defined=int(valid.sum()),first_fd_defined=bool(valid[0]),mean_fd=mean,qc_fd_lt_0_2=bool(mean<.2))


def subject_data(inputs,atlas,row):
    pid=row['subject_id'];hemis={};dtypes={}
    for hemi,long in [('L','left'),('R','right')]:
        image=nib.load(inputs['paths'][('surface_'+long,pid)])
        require(dict(image.meta).get('AnatomicalStructurePrimary')=='Cortex'+long.title(),'Source hemisphere metadata differs')
        require(image.darrays and all(a.data.shape==(10242,) and a.intent==2001 and str(a.data.dtype)=='float32' and dict(a.meta).get('TimeStep')=='2000.000000' for a in image.darrays),'Source vertex/frame/dtype/time metadata differs')
        values=np.stack([a.data for a in image.darrays]).astype(np.float64)
        require(np.isfinite(values).all(),'Nonfinite original functional values')
        hemis[hemi]=values;dtypes[hemi]=str(image.darrays[0].data.dtype)
    n=len(hemis['L']);require(len(hemis['R'])==n and n==(128 if pid=='sub-10524' else 152),'Original subject-specific frame support differs')
    timing=json.loads(inputs['paths'][('acquisition_metadata',pid)].read_text());require(timing['RepetitionTime']==2,'Original source TR differs')
    raw=np.column_stack([hemis[h][:,mask].mean(axis=1,dtype=np.float64) for h,index,mask in atlas['members']])
    with inputs['paths'][('confounds',pid)].open(newline='') as f:reader=csv.DictReader(f,delimiter='\t');cr=list(reader)
    require(len(cr)==n and set(CONF+['FramewiseDisplacement'])<=set(reader.fieldnames),'Confound/source support differs')
    conf=np.array([[float(r[c]) for c in CONF] for r in cr],dtype=np.float64)
    fd=np.array([np.nan if r['FramewiseDisplacement'] in ('','n/a','NA') else float(r['FramewiseDisplacement']) for r in cr])
    cleaned=clean_parcels(raw,conf);cleaned['fd']=fd
    valid=cleaned['parcel_status']=='ok';i,j=atlas['edge_i'],atlas['edge_j'];edge_valid=valid[i]&valid[j]
    z=cleaned['standardized'];zc=centered(z);norm=np.linalg.norm(zc,axis=0);unit=np.zeros_like(zc);unit[:,valid]=zc[:,valid]/norm[valid]
    correlations=(unit.T@unit)[i,j];require(np.all(np.abs(correlations[edge_valid])<=1+1e-12),'Pearson exceeds public numerical domain')
    correlations=np.clip(correlations,-1,1);correlations[~edge_valid]=np.nan
    fisher=np.full_like(correlations,np.nan);fisher[edge_valid]=np.arctanh(np.clip(correlations[edge_valid],-.999,.999))
    summary=dict(subject_id=pid,group=row['group'],n_frames=n,tr_s=2.,**fd_summary(fd),n_confound_columns=13,
                 nuisance_rank=cleaned['nuisance_rank'],nuisance_rank_threshold=100*EPS,n_valid_parcels=int(valid.sum()),n_invalid_parcels=int((~valid).sum()))
    observed=dict(subject_id=pid,n_frames=n,n_vertices_left=10242,n_vertices_right=10242,n_confounds_rows=len(cr),tr_s=2.,surface_dtype_left=dtypes['L'],surface_dtype_right=dtypes['R'])
    return dict(cleaned=cleaned,summary=summary,observed=observed,raw_r=correlations,fisher_z=fisher,edge_valid=edge_valid,fisher_clipped=edge_valid&(np.abs(correlations)>.999))


def pearson(x,y,constant_x='constant_fd',constant_y='constant_edge'):
    x=np.asarray(x,dtype=np.float64);y=np.asarray(y,dtype=np.float64)
    require(x.shape==y.shape and np.isfinite(x).all() and np.isfinite(y).all(),'Invalid Pearson inputs')
    if len(x)<2:return 'insufficient_n',None
    a=centered(x);b=centered(y);na=np.linalg.norm(a);nb=np.linalg.norm(b)
    if na==0:return constant_x,None
    if nb==0:return constant_y,None
    value=float(np.dot(a/na,b/nb));require(abs(value)<=1+1e-12,'Descriptive Pearson outside domain')
    return 'ok',float(np.clip(value,-1,1))


def ols_effect(y,group,fd=None,empty=False):
    group=np.asarray(group,dtype=np.float64);n=len(group)
    require(group.ndim==1 and np.all(np.isin(group,[0,1])),'Invalid diagnosis coding')
    x=np.column_stack([np.ones(n),group] if fd is None else [np.ones(n),group,np.asarray(fd,dtype=np.float64)])
    require(np.isfinite(x).all(),'Nonfinite model design')
    p=x.shape[1];u,s,vt=np.linalg.svd(x,full_matrices=False)
    keep=s>max(n,p)*EPS*(s[0] if len(s) else 0);rank=int(keep.sum());df=n-rank
    xp=(vt[keep].T/s[keep])@u[:,keep].T if rank else np.zeros((p,n))
    contrast=np.zeros(p);contrast[1]=1
    estimable=np.linalg.norm(contrast-vt[keep].T@(vt[keep]@contrast))<=100*max(n,p)*EPS
    result=dict(status='ok',n=n,n_schz=int(group.sum()),n_control=int(n-group.sum()),rank=rank,df=df,
                estimate=None,se=None,ci95=[None,None],t=None,p=None,sse=None)
    private=dict(design=x,singular_values=s,retained=keep,xplus=xp,estimability_residual=float(np.linalg.norm(contrast-vt[keep].T@(vt[keep]@contrast))))
    if empty:result['status']='empty_response_bin';return result,private
    if result['n_schz']==0 or result['n_control']==0:result['status']='missing_group';return result,private
    if df<=0:result['status']='insufficient_df';return result,private
    if not estimable:result['status']='rank_deficient';return result,private
    y=np.asarray(y,dtype=np.float64);require(y.shape==(n,) and np.isfinite(y).all(),'Invalid model response')
    beta=xp@y;residual=y-x@beta;raw_sse=float(residual@residual);cy=centered(y);zero_bound=10*max(n,p)*EPS*max(float(np.linalg.norm(cy)),TINY)
    constant=bool(np.all(y==y[0]));zero=constant or np.linalg.norm(residual)<=zero_bound
    estimate=0. if constant else float(beta[1]);sse=0. if zero else raw_sse
    variance=float(np.dot(xp[1],xp[1]));se=float(np.sqrt(sse/df*variance))
    result.update(estimate=estimate,se=se,sse=sse,ci95=[estimate-1.96*se,estimate+1.96*se])
    if se==0:result['status']='zero_se'
    else:result.update(t=estimate/se,p=float(2*stats.t.sf(abs(estimate/se),df)))
    private.update(beta=beta,residual=residual,raw_sse=raw_sse,residual_zero_bound=zero_bound)
    return result,private


def common_families(distance,valid):
    common=np.all(valid,axis=0);bins=np.full(len(distance),'excluded_not_common',dtype='<U24')
    q1=q2=None
    if common.any():
        q1,q2=[float(v) for v in np.quantile(distance[common],[1/3,2/3],method='linear')]
        bins[common]='middle';bins[common&(distance<q1)]='short';bins[common&(distance>q2)]='long'
    return common,bins,dict(q1=q1,q2=q2,n_short=int(np.sum(bins=='short')),n_middle=int(np.sum(bins=='middle')),n_long=int(np.sum(bins=='long')))


def summarize(atlas,selected,subjects,pilot=False):
    raw=np.stack([s['raw_r'] for s in subjects]);fisher=np.stack([s['fisher_z'] for s in subjects]);valid=np.stack([s['edge_valid'] for s in subjects]);clipped=np.stack([s['fisher_clipped'] for s in subjects])
    common,bins,bin_summary=common_families(atlas['distance'],valid);edges=[];e_count=len(common)
    for e,(i,j,distance) in enumerate(zip(atlas['edge_i'],atlas['edge_j'],atlas['distance'])):
        edges.append(dict(edge_id=e,parcel_i=str(atlas['parcel_id'][i]),parcel_j=str(atlas['parcel_id'][j]),distance=float(distance),n_valid_subjects=int(valid[:,e].sum()),common_valid=bool(common[e]),distance_bin=str(bins[e])))
    summaries=[]
    for s,sub in enumerate(subjects):
        row=dict(sub['summary'],n_common_edges=int(common.sum()),n_saturated_common_edges=int(np.sum(clipped[s]&common)))
        for name,mask in [('mean_fc',common),('short_range_fc',bins=='short'),('long_range_fc',bins=='long')]:row[name]=float(np.mean(fisher[s,mask])) if mask.any() else None
        summaries.append(row)
    arrays=dict(subject_id=np.asarray([r['subject_id'] for r in selected]),parcel_id=atlas['parcel_id'],edge_id=np.arange(e_count,dtype=np.int64),raw_r=raw,fisher_z=fisher,edge_valid=valid,fisher_clipped=clipped)
    for key in ('parcel_status','parcel_original_centered_l2','parcel_residual_l2','parcel_zero_bound'):arrays[key]=np.stack([s['cleaned'][key] for s in subjects])
    private={};edge_stats=[];group=np.asarray([r['group']=='SCHZ' for r in selected],dtype=np.float64);fd=np.asarray([r['mean_fd'] for r in summaries]);qc=fd<.2
    results=dict(status='resource_pilot' if pilot else 'complete',task_id=TASK_ID,n_candidates=177,n_subjects=len(selected),group_counts={g:sum(r['group']==g for r in selected) for g in ('SCHZ','CONTROL')},
                 n_candidate_edges=e_count,n_common_edges=int(common.sum()),distance_bins=bin_summary,group_means={},short_range_effects={},edgewise_abs_t_gt_2={},group_map_vs_qcfc={})
    if pilot:return edges,summaries,arrays,edge_stats,results,private
    for key in ('mean_fc','short_range_fc','long_range_fc','mean_fd'):
        results['group_means'][key]={}
        for g in ('SCHZ','CONTROL'):
            values=[r[key] for r in summaries if r['group']==g]
            results['group_means'][key][g]=float(np.mean(values)) if values and values[0] is not None else None
    for model in (*MODELS,'qc_fd_lt_0_2'):
        mask=qc if model=='qc_fd_lt_0_2' else np.ones(len(selected),dtype=bool)
        y=np.asarray([r['short_range_fc'] for r in summaries],dtype=object)[mask]
        effect,ev=ols_effect(y,group[mask],fd[mask] if model=='all_fd_adjusted' else None,empty=bin_summary['n_short']==0)
        results['short_range_effects'][model]=effect
        for key,value in ev.items():private['short_'+model+'_'+key]=np.asarray(value)
    qcfc=np.full(e_count,np.nan);qcstatus=np.full(e_count,'excluded_not_common',dtype='<U24')
    for e in np.flatnonzero(common):qcstatus[e],value=pearson(fd,fisher[:,e]);qcfc[e]=np.nan if value is None else value
    for model in MODELS:
        tvalues=np.full(e_count,np.nan);raw_residual=np.full((len(selected),e_count),np.nan);beta=np.full((3 if model=='all_fd_adjusted' else 2,e_count),np.nan)
        for e in range(e_count):
            if common[e]:
                effect,ev=ols_effect(fisher[:,e],group,fd if model=='all_fd_adjusted' else None)
                if 'residual' in ev:raw_residual[:,e]=ev['residual'];beta[:,e]=ev['beta']
            else:effect=dict(status='excluded_not_common',n=0,n_schz=0,n_control=0,rank=0,df=0,estimate=None,se=None,ci95=[None,None],t=None,p=None,sse=None)
            row={k:v for k,v in effect.items() if k!='ci95'};row.update(edge_id=e,model=model,ci95_low=effect['ci95'][0],ci95_high=effect['ci95'][1],qcfc_status=str(qcstatus[e]),qcfc_r=None if np.isnan(qcfc[e]) else float(qcfc[e]));edge_stats.append(row)
            if effect['t'] is not None:tvalues[e]=effect['t']
        defined=common&np.isfinite(tvalues);threshold=defined&(np.abs(tvalues)>2);nd=int(defined.sum());nt=int(threshold.sum());higher=int(np.sum(defined&(tvalues>2)))
        results['edgewise_abs_t_gt_2'][model]=dict(n_common_edges=int(common.sum()),n_defined_t=nd,n_undefined_t=int(common.sum())-nd,n_abs_t_gt_2=nt,fraction_abs_t_gt_2=nt/nd if nd else None,n_patient_higher=higher,patient_higher_fraction=higher/nt if nt else None)
        joint=defined&np.isfinite(qcfc);status,value=pearson(tvalues[joint],qcfc[joint],'constant_group_t','constant_qcfc')
        results['group_map_vs_qcfc'][model]=dict(status=status,n_edges=int(joint.sum()),r=value)
        private['edge_'+model+'_raw_residual']=raw_residual;private['edge_'+model+'_beta']=beta
    private['qcfc']=qcfc
    return edges,summaries,arrays,edge_stats,results,private


def make_metadata(inputs,atlas,subjects,status):
    cohort,selected=source_cohort(inputs)
    return dict(status=status,task_id=TASK_ID,dataset_id='ds000030',source_manifest_sha256=SOURCE_SHA256,method_contract_sha256=METHOD_SHA256,
        source_sha256=inputs['source_sha256'],method_contract=inputs['method'],source_observed=dict(n_source_participants=272,n_candidates=177,n_selected=172,n_unavailable=5,
        group_counts={g:sum(r['group']==g for r in selected) for g in ('SCHZ','CONTROL')},atlas=atlas['observed'],subjects=[s['observed'] for s in subjects]),
        software=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,nibabel=nib.__version__))


def jsonable(value):
    if isinstance(value,np.generic):return value.item()
    if isinstance(value,dict):return {k:jsonable(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [jsonable(v) for v in value]
    return value


def write_json(path,value):
    with Path(path).open('x') as f:json.dump(jsonable(value),f,indent=2,allow_nan=False);f.write('\n')


def write_csv(path,columns,rows):
    with Path(path).open('x',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=columns,extrasaction='ignore');writer.writeheader()
        for row in rows:writer.writerow({k:('' if row.get(k) is None else str(row[k]).lower() if isinstance(row[k],(bool,np.bool_)) else row[k]) for k in columns})


def findings(results):
    if results['status']=='resource_pilot':return 'Resource pilot: one predeclared participant, no group models or scientific conclusion.\n'
    lines=['# Released-surface CNP method sensitivity','',f"Analyzed {results['n_subjects']} original participants on {results['n_common_edges']} common-valid edges.",
           '', '| Short-range model | SCHZ minus CONTROL estimate | 95% normal-Wald interval | Status |','|---|---:|---|---|']
    for name,e in results['short_range_effects'].items():lines.append(f"| {name} | {e['estimate']} | {e['ci95']} | {e['status']} |")
    lines+=['','These are signed observational associations on one released derivative pipeline. FD adjustment/restriction does not establish causality or motion-independent disease effects. The reference group, nuisance adjustment and FD restriction do not establish exchangeability. Distances are template-pial centroid Euclidean distances, not geodesics or tract lengths. No direction, attenuation, null result, or paper finding was required.','']
    return '\n'.join(lines)


def run(data_dir,method_contract,output_dir,private_dir,pilot_subject=None):
    validate_destinations(data_dir,output_dir,private_dir)
    output_dir=Path(output_dir);private_dir=Path(private_dir);output_dir.mkdir(parents=True);private_dir.mkdir(parents=True)
    try:
        require(pilot_subject in (None,'sub-10159'),'Pilot is fixed to sub-10159; no alternative selection')
        inputs=load_inputs(data_dir,method_contract);cohort,selected=source_cohort(inputs);atlas=load_atlas(inputs)
        if pilot_subject:selected=[r for r in selected if r['subject_id']==pilot_subject]
        subjects=[];private={}
        for row in selected:
            sub=subject_data(inputs,atlas,row);subjects.append(sub);suffix=row['subject_id'].replace('-','_')
            for key,value in sub['cleaned'].items():private[key+'_'+suffix]=np.asarray(value)
            print(f"Original participant complete: {row['subject_id']}, {sub['summary']['n_frames']} frames",flush=True)
        edges,summaries,arrays,edge_stats,results,model_private=summarize(atlas,selected,subjects,pilot=pilot_subject is not None)
        metadata=make_metadata(inputs,atlas,subjects,results['status']);private.update(model_private)
        private.update(arrays);private.update(metadata_json=np.asarray(json.dumps(jsonable(metadata),sort_keys=True,allow_nan=False)),results_json=np.asarray(json.dumps(jsonable(results),sort_keys=True,allow_nan=False)))
        # Preserve primitive computation evidence before exposing complete status markers.
        with (private_dir/'analysis_arrays.npz').open('xb') as f:np.savez_compressed(f,**private)
        tables={'cohort.csv':cohort,'parcels.csv':atlas['parcels'],'edges.csv':edges,'connectivity.csv':summaries,'edge_stats.csv':edge_stats}
        for name,rows in tables.items():write_csv(output_dir/name,inputs['method']['outputs'][name]['columns'],rows)
        with (output_dir/'subject_edge_fc.npz').open('xb') as f:np.savez_compressed(f,**arrays)
        with (output_dir/'findings.md').open('x') as f:f.write(findings(results))
        write_json(output_dir/'run_metadata.json',metadata);write_json(output_dir/'group_stats.json',results)
        return results
    except BaseException as error:
        reason=str(error) or type(error).__name__
        failure=dict(status='failed_precondition',task_id=TASK_ID,reason=reason,error_type=type(error).__name__,error=str(error))
        for name in ('group_stats.json','run_metadata.json'):
            if not (output_dir/name).exists():write_json(output_dir/name,failure)
        if not (output_dir/'findings.md').exists():
            with (output_dir/'findings.md').open('x') as f:f.write('Execution failed without cohort substitution or numerical fallback: '+reason+'\n')
        if not (private_dir/'failure.json').exists():write_json(private_dir/'failure.json',failure)
        raise


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--data-dir',type=Path,default=Path('/app/data/clinconn'));p.add_argument('--method-contract',type=Path,default=Path('/app/method_contract.json'))
    p.add_argument('--output-dir',type=Path,default=Path(os.environ.get('OUTPUT_DIR','/app/output')));p.add_argument('--private-dir',type=Path,default=Path(os.environ.get('PRIVATE_DIR','/app/oracle_private')));p.add_argument('--pilot-subject',choices=['sub-10159']);a=p.parse_args()
    result=run(a.data_dir,a.method_contract,a.output_dir,a.private_dir,a.pilot_subject);print(json.dumps(result,allow_nan=False),flush=True)


if __name__=='__main__':main()
