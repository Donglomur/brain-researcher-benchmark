"""Joint-moment set inversion and separately gated design-aware uncertainty."""
import math
from statistics import NormalDist
from .common import LEVELS,require,result,ScientificGate

def quadratic_set(a,b,c):
    # Solve a*g^2+b*g+c<=0 on the real line, retain unbounded/disconnected sets.
    if a==0:
        if b==0:return [[None,None]] if c<=0 else []
        root=-c/b;return [[None,root]] if b>0 else [[root,None]]
    disc=b*b-4*a*c
    if disc<0:return [[None,None]] if a<0 else []
    root=math.sqrt(disc);lo,hi=sorted(((-b-root)/(2*a),(-b+root)/(2*a)))
    return [[lo,hi]] if a>0 else [[None,lo],[hi,None]]

def sets(payload):
    import numpy as np
    req=payload['request'];p=payload['protocol'];a=payload['arrays'];rule=req['rule'];scale=req.get('scale',1)
    require(scale in (1,1.25,1.5,2),'uncertainty scale')
    require(tuple(req.get('levels',LEVELS))==LEVELS,'all four levels required')
    require(p.get('uncertainty_structural_admitted') is True,'structural rule/point compatibility required','qualification_required')
    from .catalog import UNCERTAINTY_RULES
    require(rule in UNCERTAINTY_RULES and p.get('family') in UNCERTAINTY_RULES[rule]['families'] and p.get('trial_view') in UNCERTAINTY_RULES[rule]['views'],'structural family/view exclusion')
    out={};support={'rule':rule,'scale':scale,'levels':list(LEVELS)}
    if rule in ('U01_FIELLER','U02_LOG_DELTA'):
        require(p.get('covariance_qualification_id'),'joint moment covariance remains G14 gated','qualification_required')
        V=np.asarray(a['covariance'],float);require(V.shape==(2,2) and np.isfinite(V).all(),'joint covariance')
        tol=req['covariance_psd_tolerance'];require(tol>=0,'nonnegative covariance tolerance');require(np.allclose(V,V.T,rtol=0,atol=tol) and np.linalg.eigvalsh(V).min()>=-tol,'covariance PSD')
        A=req['A'];B=req['B'];require(math.isfinite(A) and math.isfinite(B),'moments finite')
        for level in LEVELS:
            z=NormalDist().inv_cdf((1+level)/2)*scale
            if rule=='U01_FIELLER':intervals=quadratic_set(B*B-z*z*V[1,1],-2*A*B+2*z*z*V[0,1],A*A-z*z*V[0,0]);space='gamma'
            else:
                if A<=0 or B<=0:out[str(level)]={'status':'nonphysical_estimate','space':'log_gamma','intervals':[]};continue
                v=V[0,0]/A**2+V[1,1]/B**2-2*V[0,1]/(A*B);require(v>=-tol,'negative delta variance')
                center=math.log(A/B);width=z*math.sqrt(max(0,v));intervals=[[center-width,center+width]];space='log_gamma'
            out[str(level)]={'status':'ok','space':space,'intervals':intervals}
    elif rule=='U03_TWO_AXIS_PERCENTILE':
        require(p.get('resampling_qualification_id'),'design-specific resampling qualification absent','qualification_required')
        samples=np.asarray(a['bootstrap_gamma'],float);require(samples.shape==(999,),'exact 999 resamples')
        if not np.isfinite(samples).all() or (samples<=0).any():return result({'sets':{str(c):{'status':'nonphysical_estimate','space':'gamma','intervals':[]} for c in LEVELS}},support,status='nonphysical_estimate')
        for level in LEVELS:
            endpoints=np.quantile(samples,[(1-level)/2,(1+level)/2],method='linear').tolist();out[str(level)]={'status':'ok','space':'gamma','intervals':[endpoints]}
    elif rule=='U04_DEVELOPMENT_RESIDUAL':
        require(p.get('residual_pool_ancestry_admitted') is True,'exact disjoint residual pool required','qualification_required')
        residuals=None
        if 'residual_quantiles' in req:
            quantiles=req['residual_quantiles'];n=req['residual_n'];require(type(n)is int and n>0,'residual fit count')
            require(set(quantiles)==set(map(str,LEVELS)),'all fitted residual levels')
        else:
            residuals=list(a['residuals']);require(len(residuals)>0,'empty residual pool','insufficient_support')
            residuals=sorted(math.inf if v is None else v for v in residuals);require(all(v>=0 for v in residuals),'residual support');n=len(residuals)
        gamma=req['gamma'];support['residual_n']=n
        if gamma is None or not math.isfinite(gamma) or gamma<=0:return result({'sets':{str(c):{'status':'nonphysical_estimate','space':'log_gamma','intervals':[]} for c in LEVELS}},support,status='nonphysical_estimate')
        for level in LEVELS:
            k=math.ceil((n+1)*level)
            if residuals is None:
                fitted=quantiles[str(level)];require(fitted['order_index']==k,'residual order index identity')
                radius=math.inf if fitted['unbounded'] else fitted['radius']*scale
                require(radius>=0,'nonnegative fitted radius')
            else:radius=residuals[k-1]*scale if k<=n else math.inf
            intervals=[[None,None]] if not math.isfinite(radius) else [[math.log(gamma)-radius,math.log(gamma)+radius]]
            out[str(level)]={'status':'ok','space':'log_gamma','intervals':intervals,'order_index':k}
    else:raise ScientificGate('invalid_protocol','unknown uncertainty rule')
    status='ok' if all(value['status']=='ok' for value in out.values()) else 'nonphysical_estimate'
    return result({'sets':out},support,['Asymptotic/empirically qualified sets; no universal finite-sample guarantee.'],status=status)

def resample(payload):
    # One exact, source-selected provider for all three predeclared designs.
    from .design_resampling import resample as design_resample
    return design_resample(payload)
