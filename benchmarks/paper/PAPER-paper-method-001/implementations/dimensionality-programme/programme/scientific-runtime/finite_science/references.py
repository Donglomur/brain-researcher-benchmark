"""Independent reference dispatch. Literal author source is deliberately separate."""
import math
from .common import require,result,ScientificGate

IDS=('REF01_NAIVE','REF02_ROW','REF03_COLUMN','REF04_BOTH','REF05_SHRINK','REF06_FINITE_HT','REF07_FINITE_PLUGIN','REF08_FINITE_SHRINK','REF09_FOUR_TRIAL','REF10_KNOWN_NOISE','REF11_WEIGHT_MASK','REF12_LOCAL_PR','REF13_LITERAL_SOURCE','REF14_TWONN','REF15_HARMONIC','REF16_PRIOR_CONSTANT','REF17_STABLE_CONSTANT')

def point(payload):
    import numpy as np
    req=payload['request'];p=payload['protocol'];a=payload['arrays'];ident=req['reference_id'];require(ident in IDS,'reference identity')
    require(req.get('weight_normalization','fixed_tuple_count')=='fixed_tuple_count','self-normalized diagnostics cannot replace independent reference targets')
    require(p.get('reference_target_admitted') is True,'target/protocol/view compatibility absent','qualification_required')
    from .catalog import REFERENCE_BANK,PRIMARY_KEYS
    definition=next(v for v in REFERENCE_BANK if v['id']==ident)
    require(p.get('family') in definition['families'] and p.get('target') in definition['target_classes'] and p.get('trial_view') in definition['trial_views'],'reference family/target/view mismatch')
    if p.get('primary_key') is not None:
        key=next((v for v in PRIMARY_KEYS if v['id']==p['primary_key']),None)
        require(key is not None and ident in key['eligible_reference_ids_before_qualification'] and key['target_class']==p['target'] and key['protocol']==p['protocol_id'] and key['trial_view']==p['trial_view'],'reference primary-key eligibility')
        require(p.get('axis','task')=='task','primary task-centered key cannot use a neuron/uncentered target')
        if key['protocol']=='FINITE_RC512_256_V1':require(req.get('finite_population')==[512,256] or req.get('finite_population')==(512,256),'primary finite roster differs from exact512x256 protocol')
    require(req.get('variant','fixed') in definition['variants'] or ident=='REF13_LITERAL_SOURCE','unlisted fixed reference variant')

    if ident=='REF13_LITERAL_SOURCE':
        from .literal import execute
        return execute(payload)
    if ident=='REF14_TWONN':
        from .geometry import twonn
        return twonn(payload)
    if ident in ('REF07_FINITE_PLUGIN','REF08_FINITE_SHRINK'):
        finite=req.get('finite_population');require(isinstance(finite,(list,tuple)) and len(finite)==2 and all(type(v)is int and v>0 for v in finite),'finite target requires known integer R,C','unidentified_target')
    if ident=='REF16_PRIOR_CONSTANT':
        require(p.get('prior_state_ancestry_admitted') is True,'point-fit development-only prior state required','qualification_required')
        state=req.get('state');require(isinstance(state,dict) and state.get('kind')=='point_fit_log_prior','actual fitted prior state required')
        require(state['reference_id']==ident and state['target']==p['target'] and state['protocol_id']==p['protocol_id'] and state['trial_view']==p['trial_view'],'prior state target binding')
        value=state['prior_log_mean'];require(math.isfinite(value),'prior state scalar')
        return result({'gamma':math.exp(value)},dict(reference_id=ident,state_id=p['state_id']))
    if ident=='REF17_STABLE_CONSTANT':return result({'gamma':1.},dict(reference_id=ident),['Non-geometric diagnostic only.'])
    x=np.asarray(a['trials'],dtype=float);require(x.ndim==3 and x.shape[0]==p['trial_view'],'aligned trial view shape')
    require(p.get('trials_aligned') is True,'trial alignment')
    if ident in ('REF07_FINITE_PLUGIN','REF08_FINITE_SHRINK'):
        require(req['finite_population'][0]>=x.shape[1] and req['finite_population'][1]>=x.shape[2],'finite roster smaller than observed sample')
    if ident in ('REF01_NAIVE','REF05_SHRINK','REF07_FINITE_PLUGIN','REF08_FINITE_SHRINK','REF15_HARMONIC'):
        require(np.isfinite(x).all(),'complete finite trial array for covariance reference')
        require('mask' not in a or np.asarray(a['mask']).all(),'covariance control cannot hide missing entries')
        mean=x.mean(axis=0)
        if p.get('axis')=='neuron':mean=mean.T
        if p.get('axis')!='uncentered':mean=mean-mean.mean(axis=0,keepdims=True)
        P,Q=mean.shape; S=mean.T@mean/P
        variant=req.get('variant','fixed')
        lam=float(variant.split('=')[1]) if variant.startswith('lambda=') else 0.
        if 'shrinkage' in req:require(req['shrinkage']==lam,'shrinkage identity/value mismatch')
        require(lam in (0.,.01,.1,1.),'unlisted shrinkage variant')
        if ident not in ('REF05_SHRINK','REF08_FINITE_SHRINK'):require(lam==0,'unexpected shrinkage')
        S=(1-lam)*S+lam*np.trace(S)/Q*np.eye(Q)
        A=float(np.trace(S)**2/Q**2);B=float(np.sum(S*S)/Q**2);gamma=A/B if B else None
        if ident=='REF15_HARMONIC':
            require(p.get('harmonic_approximation_protocol')=='inverse_PR_minus_inverse_P_minus_inverse_Q','harmonic version must be explicit','qualification_required')
            den=(1/gamma-1/P-1/Q) if gamma else None;gamma=1/den if den and den>0 else None
        status='ok' if gamma and gamma>0 else 'undefined_denominator'
        return result({'gamma':gamma,'A':A,'B':B},dict(reference_id=ident,P=P,Q=Q,shrinkage=lam,target=p['target']),['Biased sample/finite-target risk competitor; no noise-unbiased claim.'],status=status)
    from .lattice import compute
    q=dict(req);q['correction']={'REF02_ROW':'row','REF03_COLUMN':'column'}.get(ident,'both');q['trial_kernel']='four_distinct' if ident=='REF09_FOUR_TRIAL' else 'ordered_pairs'
    if ident=='REF06_FINITE_HT':require(q.get('finite_population') is not None,'finite roster required')
    else:require(q.get('finite_population') is None,'infinite/local reference cannot change to finite target')
    if ident=='REF10_KNOWN_NOISE':q['known_noise']=True
    if ident=='REF11_WEIGHT_MASK':
        require(p.get('weight_law')=='known_density_ratio' and p.get('mask_law')=='independent_entry_bernoulli','weight/mask law')
        require('row_weights' in a and 'mask' in a,'exact observed row-ratio/mask operands required')
    if ident=='REF12_LOCAL_PR':require(p.get('local_distribution_admitted') is True,'fixed conditional local distribution','qualification_required')
    out=compute(dict(payload,request=q));out['support']['reference_id']=ident;return out
