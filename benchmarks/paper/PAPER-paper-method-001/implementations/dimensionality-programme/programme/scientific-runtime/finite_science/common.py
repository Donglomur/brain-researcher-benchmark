"""Shared typed protocol handling; no numerical dependencies at import time."""
from itertools import permutations, product
import math

PATTERNS = ((0,0,1,1),(0,0,1,2),(0,1,0,1),(0,1,1,2),(0,1,2,3))
LEVELS = (.5,.8,.9,.95)
class ScientificGate(Exception):
    def __init__(self, status, reason, support=None):
        super().__init__(reason); self.status=status; self.support=support or {}

def require(condition, reason, status='invalid_protocol'):
    if not condition: raise ScientificGate(status,reason)

def result(outputs=None, support=None, assumptions=None, diagnostics=None, status='ok'):
    return dict(status=status, outputs=outputs or {}, support=support or {}, assumptions=assumptions or [], diagnostics=diagnostics or {})

def falling(n,k):
    return math.prod(range(n-k+1,n+1)) if n>=k else 0

def prepare(payload):
    import numpy as np
    arrays=payload['arrays']; protocol=payload['protocol']; req=payload['request']
    x=np.asarray(arrays['trials'],dtype=np.float64)
    require(x.ndim==3 and min(x.shape)>0,'trials must have shape T,P,Q')
    mask=np.asarray(arrays.get('mask',np.ones_like(x,dtype=bool)),dtype=bool)
    require(mask.shape==x.shape,'mask shape')
    require(np.isfinite(x[mask]).all(),'nonfinite observed input')
    # Absent entries are zeroed only inside the explicit mask estimator, never imputed.
    x=np.where(mask,x,0.)
    axis=protocol.get('axis','task')
    require(axis in ('task','neuron','uncentered'),'unknown axis')
    if axis=='neuron':
        x=x.transpose(0,2,1);mask=mask.transpose(0,2,1)
    T,P,Q=x.shape
    ids=protocol.get('row_ids'); cols=protocol.get('column_ids')
    if ids is not None: require(len(ids)==(Q if axis=='neuron' else P) and len(set(ids))==len(ids),'row identity alignment')
    if cols is not None: require(len(cols)==(P if axis=='neuron' else Q) and len(set(cols))==len(cols),'column identity alignment')
    require(protocol.get('trials_aligned') is True,'trial alignment must be explicit')
    rw=np.asarray(arrays.get('column_weights' if axis=='neuron' else 'row_weights',np.ones(P)),dtype=float)
    cw=np.asarray(arrays.get('row_weights' if axis=='neuron' else 'column_weights',np.ones(Q)),dtype=float)
    require(rw.shape==(P,) and cw.shape==(Q,) and np.isfinite(rw).all() and np.isfinite(cw).all() and (rw>=0).all() and (cw>=0).all(),'importance weights')
    require(rw.sum()>0 and cw.sum()>0,'zero weight support','unidentified_target')
    if ('row_weights' in arrays or 'column_weights' in arrays) and (not (rw==1).all() or not (cw==1).all()):
        require(protocol.get('weight_law')=='known_density_ratio','unknown importance law','unidentified_target')
    law=protocol.get('mask_law','complete')
    require(law in ('complete','independent_entry_bernoulli','literal_valid_count'),'unknown joint inclusion law','unidentified_target')
    if law=='complete': require(mask.all(),'missing entries under complete law')
    if law=='independent_entry_bernoulli':
        require(protocol.get('mask_unit') in ('entry_shared_trials','trial_entry'),'explicit mask dependence across trials required')
        if protocol['mask_unit']=='entry_shared_trials':require((mask==mask[0]).all(),'shared-entry mask must agree across trials')
        require(0 < protocol.get('mask_probability',0)<=1,'positive joint mask support','unidentified_target')
    normalization=req.get('weight_normalization','fixed_tuple_count')
    require(normalization in ('fixed_tuple_count','self_normalized_diagnostic'),'weight normalization')
    if normalization=='self_normalized_diagnostic':
        require(protocol.get('target')=='SELF_NORMALIZED_DIAGNOSTIC' and req.get('finite_population') is None and law!='literal_valid_count','self-normalized diagnostic is separate from fixed target/finite/literal-mask estimators')
    finite=req.get('finite_population')
    if protocol.get('target')=='TASK_FINITE':require(finite is not None,'finite roster dimensions cannot be assumed infinite','unidentified_target')
    if finite is not None:
        require(len(finite)==2 and all(type(v)is int for v in finite),'integer finite roster dimensions')
        if axis=='neuron':finite=finite[::-1]
        require(finite[0]>=P and finite[1]>=Q,'finite roster smaller than sample')
        require(protocol.get('sampling')=='uniform_without_replacement','finite inclusion law')
        require((rw==1).all() and (cw==1).all(),'finite uniform roster target does not admit nonunit importance weights')
        require(law!='literal_valid_count','literal valid-count is not finite HT')
    mode=req.get('correction','both');require(mode in ('naive','row','column','both'),'correction')
    kernel=req.get('trial_kernel','ordered_pairs')
    if kernel=='single':
        k=req.get('trial_index',0);require(type(k)is int and 0<=k<T,'trial index');assignments=[(k,)*4]
    elif kernel=='ordered_pairs':
        require(T>=2,'two aligned trials required','insufficient_support');assignments=[(a,b,a,b) for a,b in permutations(range(T),2)]
    elif kernel=='four_distinct':
        require(T>=4,'four aligned trials required','insufficient_support');assignments=list(permutations(range(T),4))
        require(protocol.get('conditional_independent_trials') is True,'four-trial independence absent','unsupported_noise_assumption')
    else:raise ScientificGate('invalid_protocol','trial kernel')
    if req.get('known_noise'):
        require(protocol.get('noise_law') in ('gaussian_entry_common','gaussian_entry_ar1'),'known Gaussian coordinate covariance required','unsupported_noise_assumption')
        require(0<=protocol.get('rho',-1)<1 and protocol.get('sigma',-1)>=0,'noise covariance parameters')
    return x,mask,rw,cw,assignments,finite

def finalize(values, support, assumptions=None):
    require(len(values)==5,'five moments')
    t=[float(v) for v in values]; A=t[0]-2*t[1]+t[4];B=t[2]-2*t[3]+t[4]
    gamma=A/B if B!=0 and math.isfinite(A) and math.isfinite(B) else None
    status='ok' if gamma is not None and math.isfinite(gamma) and gamma>0 else ('undefined_denominator' if B==0 else 'nonphysical_estimate')
    raw=dict(t1=t[0],t2=t[1],t3=t[2],t4=t[3],t5=t[4],A=A,B=B,gamma=gamma)
    nonfinite={k:str(v) for k,v in raw.items() if v is not None and not math.isfinite(v)}
    clean={k:(None if k in nonfinite else v) for k,v in raw.items()}
    return result(clean,support,assumptions or ['Moment unbiasedness does not imply ratio unbiasedness.','Two-trial correction requires appropriate within-trial covariance restrictions; whole-trial independence alone is insufficient.'],diagnostics={'nonfinite_scalar_kinds':nonfinite},status=status)
