"""Prospective twelve-family known-truth generators; issuer-only future calls.

No arrays are generated at import. Private full populations, latent variables,
truth and generator parameters must never be released to participant CaseView.
"""
import math
import json
from .common import require,result,ScientificGate

def world(payload):
    import numpy as np
    r=payload['request'];p=payload['protocol']
    require(p.get('issuer_role')=='protected_generator','generator is trusted issuer-only')
    require(p.get('generation_stage') in ('development','calibration','evaluation'),'sealed generation stage required')
    truth_certificate=None
    family=r['family'];require(family in tuple('F%02d'%i for i in range(1,13)),'family')
    P,Q,T=r['P'],r['Q'],4;rank=r['rank'];cell=r['cell_index'];seed=r['seed']
    require(all(type(n)is int and n>0 for n in (P,Q,rank)) and type(cell)is int and 0<=cell<6,'generator dimensions/cell')
    require(rank in p['allowed_rank_prior'],'rank does not belong to sealed stage prior')
    rng=np.random.default_rng(seed);rows,cols=(512,256) if family=='F10' else (P,Q)
    require(P<=rows and Q<=cols,'finite sample dimensions')
    X=rng.standard_normal((rows,rank));W=rng.standard_normal((cols,rank));params={'rank':rank,'family':family};lam=np.ones(rank)/rank
    if family in ('F02','F10'):
        exponent=float(rng.choice([0,.5,1,2]));lam=np.arange(1,rank+1,dtype=float)**(-exponent);lam/=lam.sum();params['exponent']=exponent
    if family=='F04':
        law=int(rng.integers(2));params['coordinate_law']='rademacher' if law==0 else 'uniform'
        X=(rng.integers(2,size=(rows,rank))*2-1) if law==0 else rng.uniform(-math.sqrt(3),math.sqrt(3),(rows,rank))
        W=(rng.integers(2,size=(cols,rank))*2-1) if law==0 else rng.uniform(-math.sqrt(3),math.sqrt(3),(cols,rank))
    if family=='F05':
        nu=int(rng.choice([3,5,9]));params['nu']=nu
        X=rng.standard_t(nu,(rows,rank))*math.sqrt((nu-2)/nu);W=rng.standard_t(nu,(cols,rank))*math.sqrt((nu-2)/nu)
    weights=np.ones(P);mask=np.ones((T,P,Q),dtype=bool)
    if family=='F11':
        # The exact shifted-versus-mask alternate case must be bound by the
        # generator manifest; don't infer an unpublished alternation convention.
        require(r.get('shift_enabled') in (True,False) and r.get('mask_enabled') in (True,False),'F11 explicit presealed alternation required')
        h=[0,.25,.5,.75,1,1.5][cell] if r['shift_enabled'] else 0.
        X[:,0]+=h;weights=np.exp(-h*X[:,0]+.5*h*h);params['shift']=h
        probability=[1,.9,.8,.7,.5,.3][cell] if r['mask_enabled'] else 1.
        shared=rng.random((P,Q))<probability;mask=np.broadcast_to(shared,(T,P,Q)).copy();params['mask_probability']=probability
    f=(X*np.sqrt(lam))@W.T;truth=float(lam.sum()**2/(lam@lam))
    if family=='F03':
        require(rank>=2,'F03 needs x2')
        h=float(rng.choice([0,.5,2]));f=f+h*W[None,:,0]+h*X[:,1,None]+h;params['offset_h']=h
        truth=(1+h*h)**2/(1/rank+2*h*h/rank+h**4)
    if family=='F10':
        from .geometry import population
        full=f.copy();finite=population(dict(arrays={'matrix':full},request={'axis':'task'},protocol={},lineage={}))
        truth=finite['outputs']['gamma'];ir=rng.choice(rows,P,replace=False);ic=rng.choice(cols,Q,replace=False);f=f[ir][:,ic]
        params.update(finite_R=rows,finite_C=cols,row_sample=ir.tolist(),column_sample=ic.tolist())
    if family=='F12':
        d=rank;radius=[.05,.1,.2,.35,.5,.75][cell]
        direction=rng.standard_normal((P,d));length=np.linalg.norm(direction,axis=1)
        require((length>0).all(),'zero random direction draw')
        X=direction/length[:,None]*radius*rng.random(P)[:,None]**(1/d)
        W=rng.standard_normal((Q,d));phase=rng.uniform(-math.pi/2,math.pi/2,Q);f=np.sin(X@W.T+phase)
        from .finite_ball_truth import truth as certified_truth, TruthCertificateError, RADII
        try:certified=certified_truth(d,RADII[cell])
        except TruthCertificateError as error:
            raise ScientificGate('qualification_required','F12 certified preparation failed: '+str(error)) from error
        truth=certified['gamma'];truth_certificate=certified['certificate']
        params.update(radius=radius,radius_rational=list(RADII[cell]),intrinsic_dimension=d)
    Y=np.broadcast_to(f,(T,P,Q)).copy()
    if family=='F06':
        sigma=[0,.1,.3,1,3,10][cell];Y+=sigma*np.sqrt((1+X[:,0]**2)/2)[None,:,None]*rng.standard_normal(Y.shape);params['sigma']=sigma
    if family=='F07':
        sigma=[0,.1,.3,1,2,4][cell];Y*=1+sigma*rng.standard_normal(Y.shape);params['sigma']=sigma
    if family=='F08':
        sigma=[0,.1,.3,1,2,4][cell];law=int(rng.integers(4));params.update(sigma=sigma,noise_case=law)
        if law==0:noise=rng.standard_normal((T,P,1))*f
        elif law==1:noise=rng.standard_normal((T,1,Q))*f
        elif law==2:noise=rng.standard_normal((T,(P+3)//4,(Q+3)//4))[:,np.arange(P)//4][:,:,np.arange(Q)//4]*f
        else:
            r2=int(rng.choice(p['allowed_rank_prior']));H=rng.standard_normal((P,r2))@rng.standard_normal((Q,r2)).T/math.sqrt(r2)
            noise=rng.standard_normal((T,1,1))*H;params['orthogonal_noise_rank']=r2
        Y+=sigma*noise
    if family=='F09':
        rho=[0,.1,.3,.5,.8,.95][cell];law=r['trial_covariance_law'];require(law in ('common','ar1'),'presealed covariance law')
        if law=='common':noise=math.sqrt(rho)*rng.standard_normal((1,P,Q))+math.sqrt(1-rho)*rng.standard_normal(Y.shape)
        else:
            noise=rng.standard_normal(Y.shape)
            for t in range(1,T):noise[t]=rho*noise[t-1]+math.sqrt(1-rho*rho)*noise[t]
        Y+=noise;params.update(rho=rho,sigma=1,noise_law=law)
    if family=='F12':Y+=.3*rng.standard_normal(Y.shape)
    outputs={'trials':Y,'mask':mask,'row_weights':weights,'column_weights':np.ones(Q),'private_truth':np.asarray([truth],dtype=np.float64),'private_parameters':params}
    if family=='F10':outputs['private_full_population']=full
    if family=='F12':
        outputs['private_latent_coordinates']=X
        # Exact certificate strings travel as a protected artifact, without clipping.
        encoded=json.dumps(truth_certificate,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
        require(len(encoded)<=262144,'F12 exact certificate artifact reservation exceeded')
        outputs['private_truth_certificate']=np.frombuffer(encoded,dtype=np.uint8).copy()
    return result(outputs,dict(seed=seed,views=[2,4],view_relation='T2 is first two of T4',truth_status='certified_exact_rational_kernel_moments' if family=='F12' else 'analytic_or_exact_finite_source'),['Generated source is prospective; no numerical qualification is inferred.'],status='ok')
