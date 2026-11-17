"""Animal-centered endpoints with finite, overflow-safe policy aggregation.

Task-local replacement candidate for implementation-v1/program/scores.py.
The authenticated runtime is not changed by this file's presence.
"""
import math
from fractions import Fraction
from core import need


def _mean(values):
    """Average finite binary64 scores without overflowing their unscaled sum."""
    values = [float(value) for value in values]
    need(values and all(math.isfinite(value) for value in values), 'finite nonempty score average')
    try:
        result = math.fsum(values) / len(values)
    except OverflowError:
        # Dividing each summand first is insufficient at binary64's limit:
        # rounding max/3 upward can make the sum of three terms overflow.
        # The exact mean lies within the finite input range; round it once.
        result = float(sum((Fraction(value) for value in values), Fraction()) / len(values))
    need(math.isfinite(result), 'finite score average')
    return result


def _linear_quantile(values, probability):
    """NumPy's linear sample quantile, without overflowing upper - lower."""
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    fraction = position - lower
    if fraction == 0 or ordered[lower] == ordered[lower + 1]:
        return ordered[lower]
    try:
        result = math.fsum(((1 - fraction) * ordered[lower], fraction * ordered[lower + 1]))
    except OverflowError:
        weight = Fraction(fraction)
        result = float((1 - weight) * Fraction(ordered[lower]) + weight * Fraction(ordered[lower + 1]))
    need(math.isfinite(result), 'finite bootstrap percentile')
    return result


def _expected(expected):
    need(isinstance(expected, (list, tuple)) and expected and len(set(expected)) == len(expected),
         'nonempty unique required animal roster')


def animal_score(sessions):
    """Rows are complete sessions of one animal, each a list of full windows."""
    import numpy as np
    need(sessions and all(s for s in sessions), 'no empty required animal/session')
    mu=np.zeros(2,dtype=np.float64); records=[]; first=None;constant=np.ones(2,dtype=bool)
    for session in sessions:
        for y,pred in session:
            need(y.ndim==2 and y.shape[1]==2 and len(y)>0 and pred.shape==y.shape,
                 'both complete heads and all original positions')
            need(bool(np.isfinite(y).all() and np.isfinite(pred).all()), 'finite complete target/prediction')
            if first is None: first=y[0].copy()
            constant &= np.all(y==first,axis=0)
            w=1.0/(len(sessions)*len(session)*len(y))
            mu += w*y.sum(axis=0,dtype=np.float64); records.append((y,pred,w))
    mu[constant]=first[constant]
    sse=np.zeros(2,dtype=np.float64); sst=sse.copy();mae=sse.copy()
    for y,p,w in records:
        sse += w*((y-p)**2).sum(axis=0,dtype=np.float64)
        sst += w*((y-mu)**2).sum(axis=0,dtype=np.float64)
        mae += w*np.abs(y-p).sum(axis=0,dtype=np.float64)
    sst[constant]=0
    need(bool(np.all(sst[~constant]>0)), 'nonconstant denominator underflow requires explicit failed admission')
    need(bool(np.isfinite(sse).all() and np.isfinite(sst).all() and np.isfinite(mae).all()),'finite canonical diagnostic arithmetic')
    r2=[None if d==0 else 1-float(n)/float(d) for n,d in zip(sse,sst)]
    need(all(value is None or math.isfinite(value) for value in r2),
         'canonical R-squared outside finite binary64 range')
    return {'mean':mu.tolist(),'sse':sse.tolist(),'sst':sst.tolist(),'mse':sse.tolist(),'mae':mae.tolist(),
            'support':{'sessions':len(sessions),'windows':sum(len(s) for s in sessions),
                       'timestamps':sum(len(y) for s in sessions for y,_ in s),
                       'per_session':[{'windows':len(s),'timestamps':sum(len(y) for y,_ in s)} for s in sessions]},
            'weight_rule':'1/(animal sessions * session windows * window timestamps); normalized mass1',
            'undefined_reason':['exact constant target' if d==0 else None for d in sst],
            'r2':r2}


def macro(animals, expected):
    _expected(expected)
    need(set(animals)==set(expected), 'all required animals; no surviving-case scoring')
    need(all(len(animals[a]['r2']) == 2 for a in expected), 'both required endpoint heads')
    result=[]
    for h in range(2):
        values=[animals[a]['r2'][h] for a in expected]
        need(all(v is None or math.isfinite(v) for v in values), 'finite or explicitly undefined animal scores')
        result.append(None if any(v is None for v in values) else _mean(values))
    return {'velocity':result[0],'speed':result[1],'animals':animals,
            'zero_variance_disposition':'endpoint aggregate undefined; animal retained', 'negative_r2_clipped':False}


def paired_contrast(left,right,expected):
    """Each animal has three realized paired policy scores, not three animals."""
    import numpy as np
    _expected(expected)
    need(set(left)==set(right)==set(expected), 'complete paired animal contrast')
    need(all(len(left[a])==len(right[a])==3 for a in expected),'all three realizations')
    values=[v for a in expected for arm in (left[a],right[a]) for v in arm]
    need(all(v is None or math.isfinite(v) for v in values), 'finite or explicitly undefined policy scores')
    if any(v is None for v in values):
        return {'estimate':None,'interval':None,'reason':'undefined required animal endpoint'}
    delta=np.array([_mean(float(l)-float(r) for l,r in zip(left[a],right[a])) for a in expected],dtype=np.float64)
    rng=np.random.Generator(np.random.PCG64(580058)); samples=np.empty(10000,dtype=np.float64)
    for i in range(10000): samples[i]=_mean(delta[rng.integers(0,len(delta),size=len(delta))])
    return {'estimate':_mean(delta), 'interval':[_linear_quantile(samples,q) for q in (.025,.975)],
            'animal_deltas':delta.tolist(),'replicates':10000,'seed':580058,
            'interpretation':'descriptive conditional on fitted references and realized policies; no population/causal/SOTA claim'}
