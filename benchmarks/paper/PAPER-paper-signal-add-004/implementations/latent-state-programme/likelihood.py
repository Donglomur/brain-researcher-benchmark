"""Unchanged selected Gaussian-HMM likelihood math; source attribution in SOURCE_BINDINGS.
No source state, query arrays or scientific runtime is loaded at import.
"""
import math
from core import need

def validate_hmm(model,dimensions,states):
    import numpy as np
    need(type(model) is dict and set(model)=={'means','covariances','transition','initial'},'HMM parameter fields')
    m=np.asarray(model['means'],dtype='float64');c=np.asarray(model['covariances'],dtype='float64')
    a=np.asarray(model['transition'],dtype='float64');pi=np.asarray(model['initial'],dtype='float64')
    need(m.shape==(states,dimensions) and c.shape==(states,dimensions,dimensions) and a.shape==(states,states) and pi.shape==(states,), 'Frozen dimensions/states')
    need(all(np.isfinite(x).all() for x in (m,c,a,pi)) and (a>=0).all() and (pi>=0).all(), 'Finite Gaussian/simplex inputs')
    need(np.allclose(a.sum(axis=1),1.,rtol=0,atol=1e-10) and abs(float(pi.sum())-1.)<=1e-10,'Transition and initial probability rows')
    need(np.allclose(c,np.swapaxes(c,-1,-2),rtol=1e-10,atol=1e-12),'Symmetric covariances')
    factors=[]
    for covariance in c:
        try:factors.append(np.linalg.cholesky(covariance))
        except np.linalg.LinAlgError as error:raise ValueError('Positive definite covariance, no scoring-time ridge') from error
    return m,np.asarray(factors),a,pi

def gaussian_log_emissions(x,means,factors):
    import numpy as np
    x=np.asarray(x,dtype='float64')
    need(x.ndim==2 and x.shape[1]==means.shape[1] and len(x)>0 and np.isfinite(x).all(),'Finite observed representation')
    columns=[]
    with np.errstate(over='raise',invalid='raise',divide='raise'):
        for m,l in zip(means,factors):
            z=np.linalg.solve(l,(x-m).T)
            columns.append(-.5*(means.shape[1]*math.log(2*math.pi)+2*np.log(np.diag(l)).sum()+(z*z).sum(axis=0)))
    answer=np.column_stack(columns);need(np.isfinite(answer).all(),'Representable density arithmetic')
    return answer

def logsumexp(x,axis=None):
    import numpy as np
    x=np.asarray(x,dtype='float64');m=np.max(x,axis=axis,keepdims=True)
    # All-impossible columns retain -inf; elsewhere subtracting a finite max is safe.
    safe=np.where(np.isfinite(m),m,0.)
    with np.errstate(divide='ignore'):
        value=safe+np.log(np.exp(x-safe).sum(axis=axis,keepdims=True))
    return np.squeeze(value,axis=axis) if axis is not None else float(value.squeeze())

def hmm_loglikelihood(observations,model,dimensions,states):
    """Exact finite-state Gaussian marginal on THIS represented run.

    Initial probability is logged, including structural zeros. Reset per run.
    Overlapping TDE observations define an embedded-space objective, not the
    original continuous raw-signal joint density. No sequence truncation.
    """
    import numpy as np
    means,factors,a,pi=validate_hmm(model,dimensions,states)
    emissions=gaussian_log_emissions(observations,means,factors)
    with np.errstate(divide='ignore'):log_a=np.log(a);log_p=np.log(pi)
    total=0.
    for i,e in enumerate(emissions):
        if i:log_p=logsumexp(log_p[:,None]+log_a,axis=0)
        update=log_p+e;normalizer=logsumexp(update)
        need(math.isfinite(normalizer),'At least one finite model path')
        total+=normalizer;log_p=update-normalizer
    need(math.isfinite(total),'Finite total run evidence')
    return {'log_likelihood':total,'samples':len(emissions),'nats_per_observation':total/len(emissions),'objective':'exact_gaussian_hmm_embedded_run_marginal'}

def static_loglikelihood(observations,mean,covariance):
    dimensions=len(mean)
    return hmm_loglikelihood(observations,{'means':[mean],'covariances':[covariance],'transition':[[1.]],'initial':[1.]},dimensions,1)
