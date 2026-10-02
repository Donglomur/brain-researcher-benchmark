"""Public-recipe numerical primitives for the duration-sensitivity oracle.

No source reads, output writes, grader imports, or import-time execution.
"""
from __future__ import annotations
import hashlib
import math

import numpy as np
from nilearn.glm.first_level.design_matrix import create_cosine_drift
from nilearn.glm.first_level.hemodynamic_models import compute_regressor
from scipy.stats import t as student_t

EPS=np.finfo(np.float64).eps
SPHERES={'amy_L':(-23,-5,-19),'amy_R':(23,-5,-19),'ffa_L':(-40,-52,-18),'ffa_R':(42,-52,-18),
    'dACC':(0,20,38),'aIns_L':(-34,20,4),'aIns_R':(36,22,2),'dlPFC_L':(-44,20,30),
    'dlPFC_R':(46,22,28),'IPS_L':(-28,-58,46),'IPS_R':(30,-56,46)}
CONFOUNDS=tuple([f'trans_{v}' for v in 'xyz']+[f'rot_{v}' for v in 'xyz']+
    [f'a_comp_cor_{i:02d}' for i in range(5)]+['white_matter','csf'])
NETWORKS=('Vis','SomMot','DorsAttn','SalVentAttn','Limbic','Cont','Default')


class PreconditionError(ValueError):pass


def require(ok,message):
    if not ok:raise PreconditionError(message)


def real_array(value,ndim,name):
    def leaves(x):
        if isinstance(x,(list,tuple)):
            for v in x:leaves(v)
        elif isinstance(x,(bool,np.bool_)):raise PreconditionError(name+': Boolean is not a real measurement')
    leaves(value);a=np.asarray(value)
    require(a.ndim==ndim and a.dtype.kind in 'iuf',name+': numeric dimensions')
    a=np.asarray(a,dtype=np.float64)
    require(np.isfinite(a).all(),name+': finite values required')
    return a


def affine(value):
    a=real_array(value,2,'affine')
    require(a.shape==(4,4) and np.array_equal(a[3],[0,0,0,1]),'homogeneous affine required')
    require(np.linalg.det(a[:3,:3])!=0,'invertible affine required')
    return a


def grid_id(shape,matrix):
    require(len(shape)==3 and all(type(v) in (int,np.int64,np.int32) and v>0 for v in shape),'three positive integer dimensions')
    a=affine(matrix).copy();a[a==0]=0.0
    payload=b'EMOMATCH_grid_v1\n'+np.asarray(shape,dtype='<i8').tobytes()+a.astype('<f8').tobytes(order='C')+b'mm\n'
    return 'grid_'+hashlib.sha256(payload).hexdigest()


def support_digest(indices):
    a=np.asarray(indices)
    require(a.ndim==1 and a.dtype.kind in 'iu' and np.all(a>=0),'support integer indices')
    require(len(a)<2 or np.all(a[1:]>a[:-1]),'support indices must be ascending and unique')
    return hashlib.sha256(b'EMOMATCH_support_v1\n'+a.astype('<i8').tobytes()).hexdigest()


def nearest_labels(coordinates,labels):
    u=real_array(coordinates,2,'atlas coordinates');labels=np.asarray(labels)
    require(u.shape[1]==3 and labels.ndim==3 and labels.dtype.kind in 'iu','coordinate/label dimensions')
    half=.5*np.rint(2*u);u=np.where(np.abs(u-half)<=1e-7,half,u)
    inside=np.all((u>=0)&(u<=np.asarray(labels.shape)-1),axis=1)
    out=np.zeros(len(u),dtype=labels.dtype);index=np.floor(u[inside]+.5).astype(np.int64)
    out[inside]=labels[tuple(index.T)];return out


def geometric_supports(shape,bold_affine,labels,atlas_affine,*,chunk_size=65536):
    shape=tuple(shape);gid=grid_id(shape,bold_affine);b=affine(bold_affine);a=affine(atlas_affine)
    labels=np.asarray(labels);require(labels.ndim==3 and labels.dtype.kind in 'iu','integer atlas labels')
    require(set(np.unique(labels))<=set(range(101)),'atlas labels outside0..100')
    mapping=np.linalg.inv(a)@b;roi_ids=[str(i) for i in range(1,101)]+list(SPHERES)
    parts={key:[] for key in roi_ids};nvox=math.prod(shape)
    require(type(chunk_size) is int and chunk_size>0,'positive chunk size')
    overlap_count=cortex_overlap=0
    for start in range(0,nvox,chunk_size):
        flat=np.arange(start,min(nvox,start+chunk_size),dtype=np.int64)
        ijk=np.column_stack(np.unravel_index(flat,shape,order='C'))
        assigned=nearest_labels(ijk@mapping[:3,:3].T+mapping[:3,3],labels)
        for label in np.unique(assigned):
            if label:parts[str(label)].append(flat[assigned==label])
        world=ijk@b[:3,:3].T+b[:3,3];multiplicity=np.zeros(len(flat),dtype=np.int16)
        for key,center in SPHERES.items():
            keep=np.sum((world-np.asarray(center))**2,axis=1,dtype=np.float64)<=36.0
            parts[key].append(flat[keep]);multiplicity+=keep
        overlap_count+=int(np.count_nonzero(multiplicity>1))
        cortex_overlap+=int(np.count_nonzero((multiplicity>0)&(assigned>0)))
    supports={key:np.concatenate(value) if value else np.empty(0,dtype=np.int64) for key,value in parts.items()}
    return supports,dict(grid_id=gid,voxels_in_multiple_spheres=overlap_count,sphere_cortex_overlap_voxels=cortex_overlap)


def duration_models(response_times,missing):
    rt=real_array(response_times,1,'target response times');missing=np.asarray(missing)
    require(missing.dtype.kind=='b' and missing.shape==rt.shape,'explicit Boolean RT missing mask')
    valid=rt[~missing];require(valid.size and np.all(valid>0),'at least one finite positive target RT; all nonmissing RT positive')
    median=float(np.median(valid));a=np.full(rt.shape,median,dtype=np.float64);b=rt.copy();b[missing]=median
    return a,b,median


def impute_confounds(values,missing):
    x=real_array(values,2,'confounds');missing=np.asarray(missing)
    require(missing.dtype.kind=='b' and missing.shape==x.shape,'explicit Boolean confound missing mask')
    out=x.copy()
    for col in range(x.shape[1]):
        valid=x[~missing[:,col],col]
        mean=math.fsum(float(v) for v in valid)/len(valid) if len(valid) else 0.0
        out[missing[:,col],col]=mean
    require(np.isfinite(out).all(),'finite imputed confounds');return out


def normalize_roi(raw):
    x=real_array(raw,2,'ROI means');require(min(x.shape)>0,'nonempty ROI means')
    means=np.empty(x.shape[1]);sd=np.empty(x.shape[1]);normalized=np.empty_like(x)
    constants=np.empty(x.shape[1],dtype=bool)
    for col in range(x.shape[1]):
        values=x[:,col];constants[col]=bool(np.all(values==values[0]))
        if constants[col]:means[col]=values[0];sd[col]=0.0;normalized[:,col]=0.0
        else:
            means[col]=math.fsum(float(v) for v in values)/len(values)
            deviations=[float(v-means[col]) for v in values]
            sd[col]=math.sqrt(math.fsum(v*v for v in deviations)/len(values))
            normalized[:,col]=(values-means[col])/(sd[col]+1e-8)
    require(np.isfinite(means).all() and np.isfinite(sd).all() and np.isfinite(normalized).all(),'finite normalization')
    return normalized,means,sd,sd+1e-8,constants


def voxel_means(data,supports):
    x=real_array(data,4,'scaled BOLD');require(min(x.shape)>0,'nonempty BOLD')
    selected=[]
    for support in supports:
        indices=np.asarray(support);support_digest(indices)
        require(len(indices)>0 and indices[-1]<math.prod(x.shape[:3]),'nonempty in-grid ROI support')
        selected.append(indices)
    require(len(selected)>0,'required ROI supports')
    result=np.empty((x.shape[3],len(selected)),dtype=np.float64)
    for frame in range(x.shape[3]):
        volume=x[:,:,:,frame].ravel(order='C')
        for col,index in enumerate(selected):
            values=np.ascontiguousarray(volume[index],dtype=np.float64)
            result[frame,col]=np.mean(values,dtype=np.float64)
    require(np.isfinite(result).all(),'finite ROI means');return result


def construct_design(onsets,conditions,durations,frame_times,nuisance):
    onset=real_array(onsets,1,'onsets');duration=real_array(durations,1,'durations')
    frames=real_array(frame_times,1,'frame times');conf=real_array(nuisance,2,'nuisance')
    condition=np.asarray(conditions)
    require(condition.ndim==1 and condition.dtype.kind in 'US' and len(condition)==len(onset)==len(duration),'event identities')
    require(set(condition)<=set(('control','emotion')) and np.all(duration>0),'included target events only')
    require(len(frames)>=2 and np.all(np.diff(frames)>0) and conf.shape==(len(frames),13),'frame/confound shape')
    columns=[];names=['control','emotion'];presence={}
    for name in names:
        keep=condition==name;presence[name]=bool(np.any(keep))
        if presence[name]:
            reg,_=compute_regressor(np.vstack([onset[keep],duration[keep],np.ones(np.count_nonzero(keep))]),
                'spm',frames,con_id=name,oversampling=50,min_onset=-24)
            columns.append(reg[:,0])
        else:columns.append(np.zeros(len(frames),dtype=np.float64))
    drift=create_cosine_drift(.008,frames)
    for index in range(drift.shape[1]-1):columns.append(drift[:,index]);names.append('drift_'+str(index+1))
    for index,name in enumerate(CONFOUNDS):columns.append(conf[:,index]);names.append(name)
    columns.append(drift[:,-1]);names.append('constant')
    design=np.ascontiguousarray(np.column_stack(columns),dtype=np.float64)
    require(np.isfinite(design).all(),'finite unregularized design')
    contrast=np.zeros(len(names));contrast[names.index('emotion')]=1;contrast[names.index('control')]=-1
    return design,names,contrast,presence


def minimum_norm(design,response,contrast,*,conditions_present=True):
    x=real_array(design,2,'design');y=real_array(response,2,'response');c=real_array(contrast,1,'contrast')
    require(x.shape[0]==y.shape[0] and x.shape[1]==len(c) and min(x.shape)>0 and y.shape[1]>0,'fit dimensions')
    require(type(conditions_present) is bool,'condition presence Boolean')
    u,s,vt=np.linalg.svd(x,full_matrices=False)
    cutoff=max(x.shape)*EPS*float(s[0]);keep=s>cutoff;rank=int(keep.sum())
    v=vt[keep].T
    beta=(v/s[keep])@(u[:,keep].T@y) if rank else np.zeros((x.shape[1],y.shape[1]))
    error=c-v@(v.T@c);rowspace_residual=float(np.linalg.norm(error))
    bound=100*EPS*max(x.shape)*float(np.linalg.norm(c));estimable=rowspace_residual<=bound
    status='missing_condition' if not conditions_present else 'ok' if estimable else 'contrast_nonestimable'
    defined=status=='ok';d=c@beta if defined else np.zeros(y.shape[1])
    residual=y-x@beta;sse=np.sum(residual*residual,axis=0,dtype=np.float64)
    require(np.isfinite(beta).all() and np.isfinite(d).all() and np.isfinite(sse).all(),'finite fit outputs')
    return dict(beta=beta,contrast_estimate=d,contrast_defined=np.full(y.shape[1],defined,dtype=bool),
        rank=rank,residual_df=x.shape[0]-rank,singular_values=s,rank_cutoff=cutoff,
        contrast_estimable=bool(estimable),contrast_rowspace_residual=rowspace_residual,estimability_bound=bound,
        residual_sse=sse,status=status,u=u,vt=vt,retained_singular_mask=keep)


def complete_statistic(values,n_expected):
    require(type(n_expected) is int and n_expected>=0,'expected participant count')
    values=list(values);require(len(values)==n_expected,'complete fixed participant ledger')
    require(all(isinstance(v,(int,float,np.integer,np.floating)) and not isinstance(v,(bool,np.bool_)) for v in values if v is not None),'real scalar group inputs')
    defined=[float(v) for v in values if v is not None]
    require(all(math.isfinite(v) for v in defined),'finite scalar group inputs')
    base=dict(status='incomplete_support',n_expected=n_expected,n_defined=len(defined),mean=None,sample_sd=None,df=None,t=None,p=None,ci95=None)
    if len(defined)!=n_expected:return base
    if n_expected<2:base['status']='insufficient_n';return base
    mean=defined[0] if all(v==defined[0] for v in defined) else math.fsum(defined)/n_expected
    deviations=[v-mean for v in defined];sd=math.hypot(*deviations)/math.sqrt(n_expected-1)
    if sd==0:return dict(base,status='zero_variance',mean=mean,sample_sd=0.0,df=n_expected-1,ci95=[mean,mean])
    se=sd/math.sqrt(n_expected);t=mean/se;p=float(2*student_t.sf(abs(t),n_expected-1))
    margin=float(student_t.ppf(.975,n_expected-1))*se
    require(all(math.isfinite(v) for v in (mean,sd,t,p,margin)),'finite group statistics')
    return dict(base,status='ok',mean=mean,sample_sd=sd,df=n_expected-1,t=t,p=p,ci95=[mean-margin,mean+margin])
