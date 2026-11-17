"""Finite-roster, local geometry and explicitly selected preparation source."""
from .common import require,result,ScientificGate

def population(payload):
    import numpy as np
    G=np.asarray(payload['arrays']['matrix'],dtype=float)
    require(G.ndim==2 and min(G.shape)>0 and np.isfinite(G).all(),'finite matrix')
    axis=payload['request'].get('axis','task')
    require(axis in ('task','neuron','uncentered'),'target axis')
    if axis=='neuron':G=G.T
    H=G if axis=='uncentered' else G-G.mean(axis=0,keepdims=True)
    R,C=H.shape;A=float(np.mean(H*H)**2);K=H@H.T/C;B=float(np.mean(K*K))
    return result({'A':A,'B':B,'gamma':A/B if B else None},dict(R=R,C=C,target='complete_finite_roster',axis=axis),status='ok' if B else 'undefined_denominator')

def local(payload):
    import numpy as np
    a=payload['arrays'];r=payload['request'];p=payload['protocol']
    X=np.asarray(a['coordinates'],dtype=float);z=np.asarray(a['center'],dtype=float);M=np.asarray(a['metric'],dtype=float)
    require(X.ndim==2 and z.shape==(X.shape[1],) and M.shape==(X.shape[1],X.shape[1]),'local coordinate shapes')
    require(np.isfinite(X).all() and np.isfinite(M).all() and np.isfinite(z).all(),'local finite values')
    require(p.get('metric_ancestry_admitted') is True and p.get('metric_state_id'),'metric must be fixed or training-only sealed','qualification_required')
    tol=r['psd_tolerance'];require(tol>=0,'explicit PSD tolerance')
    require(np.allclose(M,M.T,atol=tol,rtol=0) and np.linalg.eigvalsh(M).min()>=-tol,'metric not PSD')
    radius=r['radius'];require(radius>=0,'radius')
    delta=X-z;d2=np.einsum('ij,jk,ik->i',delta,M,delta)
    require((d2>=-tol).all(),'negative quadratic distance')
    selected=np.flatnonzero(d2<=radius*radius)
    return result({'indices':selected,'squared_distances':d2},dict(requested_center=r.get('center_id'),radius=radius,selected_rows=int(len(selected)),requested_rows=len(X),metric_state_id=p['metric_state_id']),['PSD pseudometric can have null directions; this does not prove intrinsic dimension.'],status='ok' if len(selected)>=4 else 'insufficient_support')

def twonn(payload):
    import numpy as np
    X=np.asarray(payload['arrays']['coordinates'],dtype=float);r=payload['request']
    require(X.ndim==2 and X.shape[0]>=3 and np.isfinite(X).all(),'TwoNN coordinates')
    require(r.get('twonn_algorithm')=='empirical_cdf_origin_regression_v1','TwoNN numerical definition must be explicit')
    require(payload['protocol'].get('twonn_source_qualification_id'),'Exact original TwoNN variant/source correspondence remains separately qualified','qualification_required')
    # Standard independent source formulation: least-squares through origin of
    # -log(1-F(mu)) against log(mu), omitting the divergent final empirical CDF.
    d=np.sqrt(np.maximum(0,((X[:,None,:]-X[None,:,:])**2).sum(axis=2)))
    np.fill_diagonal(d,np.inf);nearest=np.partition(d,1,axis=1)[:,:2];nearest.sort(axis=1)
    require((nearest[:,0]>0).all(),'zero nearest-neighbour distances','insufficient_support')
    mu=np.sort(nearest[:,1]/nearest[:,0]);xx=np.log(mu[:-1]);yy=-np.log1p(-np.arange(1,len(mu))/len(mu))
    den=float(xx@xx);require(den>0,'degenerate distance ratios','insufficient_support')
    return result({'intrinsic_dimension':float(xx@yy/den)},dict(points=len(X),fit_points=len(xx),target='intrinsic_local'),['Requires locally constant density and qualified manifold assumptions.','Not a finite-radius PR estimator.'])

def transform(payload):
    import numpy as np
    a=payload['arrays'];p=payload['protocol'];r=payload['request'];op=r['operation']
    if op=='majaj_producer':
        from .majaj import prepare
        return prepare(payload)
    if op in ('things_beta_roi','llama_flores','tvsd_lfp','final_figure_grid'):
        raise ScientificGate('unavailable_source','Required final-paper scientific producer is not authenticated: '+op)
    require(p.get('transform_ancestry_admitted') is True,'stage/group/coordinate ancestry must be admitted','qualification_required')
    x=np.asarray(a['matrix'],dtype=float);require(x.ndim==2 and np.isfinite(x).all(),'preparation matrix')
    if op=='task_center':out=x-x.mean(axis=0,keepdims=True);return result({'matrix':out},dict(operation=op,within_case=True))
    if op=='standardize_apply':
        mean=np.asarray(a['mean']);scale=np.asarray(a['scale']);require(mean.shape==(x.shape[1],) and scale.shape==mean.shape and (scale>0).all(),'frozen coordinate scale')
        return result({'matrix':(x-mean)/scale},dict(state_id=p['transform_state_id'],operation=op))
    if op=='spontaneous_fit':
        require(p.get('stage')=='training' or p.get('lane')=='LITERAL_LEGACY','spontaneous fit stage')
        rank=r['rank'];require(type(rank)is int and 0<rank<=min(x.shape),'basis rank')
        # Covariance eigenvectors, equivalent subspace to SVD of centered time x neurons.
        centered=x-x.mean(axis=0,keepdims=True);_,_,v=np.linalg.svd(centered,full_matrices=False)
        return result({'basis':v[:rank].T,'mean':x.mean(axis=0)},dict(rank=rank,training_groups=p['training_group_ids'],coordinate_id=p['coordinate_id']))
    if op=='spontaneous_apply':
        b=np.asarray(a['basis']);require(b.ndim==2 and b.shape[0]==x.shape[1],'basis coordinate map')
        return result({'matrix':x-(x@b)@b.T},dict(state_id=p['transform_state_id'],coordinate_id=p['coordinate_id']))
    if op=='chronological_trial_means':
        ids=r['presentation_stimulus_ids'];roster=r['stimulus_roster'];require(len(ids)==len(x) and len(set(roster))==len(roster),'stimulus roster')
        groups=[];counts=[];missing=[]
        for ident in roster:
            pos=[i for i,k in enumerate(ids) if k==ident];split=len(pos)//2;counts.append([split,len(pos)-split])
            if split==0:missing.append(ident);groups.append(None)
            else:groups.append(np.stack([x[pos[:split]].mean(axis=0),x[pos[split:]].mean(axis=0)]))
        return result({'trial_means_by_stimulus':groups},dict(stimulus_roster=roster,repeat_counts=counts,unsupported_stimuli=missing),status='insufficient_support' if missing else 'ok')
    if op=='tv_sd_roi':
        selected=r['selected_column_indices'];require(len(set(selected))==len(selected) and all(type(i)is int and 0<=i<x.shape[1] for i in selected),'ROI coordinates')
        require(p.get('measurement')=='normalized_MUA_source_diagnostic','MUA cannot be relabeled LFP')
        return result({'matrix':x[:,selected]},dict(indices=selected,measurement=p['measurement']))
    if op=='fixed_window_mean':
        times=np.asarray(a['times']);require(times.shape==(len(x),),'time alignment')
        lo,hi=r['window'];take=(times>=lo)&(times<hi);require(take.any(),'empty measurement window','insufficient_support')
        return result({'mean':x[take].mean(axis=0)},dict(samples=int(take.sum()),window=[lo,hi],endpoint='left_closed_right_open'))
    raise ScientificGate('invalid_protocol','unknown preparation operation')


def stringer_source(payload):
    """Exact operations from on_Stringer cell0, with explicit lineage and I/O outside."""
    import numpy as np
    from scipy.sparse.linalg import eigsh
    a=payload['arrays'];p=payload['protocol'];r=payload['request']
    require(p.get('lane')=='LITERAL_LEGACY' and p.get('transform_ancestry_admitted') is True,'whole-session legacy preprocessing cannot enter I fit')
    resp=np.asarray(a['responses'],dtype=float);spont=np.asarray(a['spontaneous'],dtype=float);ids=np.asarray(a['stimulus_ids'],dtype=int)
    require(resp.ndim==2 and spont.ndim==2 and resp.shape[1]==spont.shape[1] and ids.shape==(len(resp),),'Stringer coordinate/time alignment')
    require(p.get('stimulus_id_base')==1,'source MATLAB 1-based identity convention')
    ids=ids-1;nimg=int(ids.max());take=ids<nimg;resp=resp[take];ids=ids[take]
    mu=spont.mean(axis=0);sd=spont.std(axis=0)+1e-6;resp=(resp-mu)/sd;spont=(spont-mu)/sd
    require(spont.shape[1]>32,'source eigsh32 dimension')
    # Explicit source RNG/initial-vector qualification required for eigsh reproducibility.
    require(p.get('eigsh_environment_qualification_id'),'legacy eigsh environment/seed qualification','qualification_required')
    start=r.get('eigensolver_start','literal_default')
    require(start in ('literal_default','explicit_v0'),'eigensolver start version')
    if start=='literal_default':sv,u=eigsh(spont.T@spont,k=32)
    else:sv,u=eigsh(spont.T@spont,k=32,v0=np.asarray(a['eigsh_v0']))
    resp=resp-(resp@u)@u.T;resp-=resp.mean(axis=0)
    means=[];kept=[];unsupported=[];counts=[]
    for ident in range(nimg):
        positions=np.flatnonzero(ids==ident);split=len(positions)//2;counts.append([split,len(positions)-split])
        if split<1:unsupported.append(ident);continue
        means.append(np.stack([resp[positions[:split]].mean(axis=0),resp[positions[split:]].mean(axis=0)]));kept.append(ident)
    return result({'trial_means':np.stack(means,axis=1) if means else None,'stimulus_ids':kept,'mean':mu,'scale':sd,'basis':u,'eigenvalues':sv},dict(original_presentations=len(take),nonblank_presentations=int(take.sum()),all_stimulus_count=nimg,repeat_counts=counts,excluded_insufficient_repeats=unsupported,source_version='on_Stringer_cell000_001',legacy_global_center=True,eigensolver_start=start),['Original whole-session R operation; no held-group I transform qualification.'],status='ok' if means else 'insufficient_support')
