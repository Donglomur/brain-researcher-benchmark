"""Exact population joins, literal descriptive summaries and prospective inference."""
from .custody import need
from .guard import distinct,integer,real,RequiredUnscorable
from .numerics import matrix

def population(rows,session_ids,*,value):
    import numpy as np
    distinct(session_ids);need(len(rows)==len({r['session_id']for r in rows}),'unique complete recording outputs')
    lookup={r['session_id']:r for r in rows};need(set(session_ids)<=set(lookup),'every exact endpoint session present')
    a=np.asarray([lookup[s][value]for s in session_ids],dtype='float64')
    need(a.size and np.isfinite(a).all(),'complete finite population values; no nan dropping')
    return {'session_ids':session_ids,'values':a,'mean':a.mean(axis=0),'sd':a.std(axis=0),
            'sem':a.std(axis=0,ddof=1)/np.sqrt(len(a))if len(a)>1 else None,'n_recordings':len(a)}

def paired_test(x,y):
    import numpy as np
    from scipy.stats import ttest_rel
    a=np.asarray(x,dtype='float64');b=np.asarray(y,dtype='float64')
    need(a.shape==b.shape and a.ndim==1 and len(a)>1 and np.isfinite(a).all()and np.isfinite(b).all(),'complete paired recording vectors')
    delta=a-b
    if np.std(delta,ddof=1)==0:
        return {'difference':float(delta.mean()),'n':len(a),'t':None,'p':None,'disposition':'degenerate paired variance'}
    result=ttest_rel(a,b)
    return {'difference':float(delta.mean()),'n':len(a),'t':float(result.statistic),'p':float(result.pvalue),'unit':'source recording; no independent animal claim'}

def normalized_acg(rows,session_ids,*,value):
    import numpy as np
    pop=population(rows,session_ids,value=value);mean=pop['mean']
    need(mean.ndim==2 and np.all(mean[:,0]!=0),'nonzero group lag-zero scale')
    normalized=mean/mean[:,0,None]
    return {'session_ids':session_ids,'raw_group_mean':mean,'normalized':normalized,
            'lag4_6_mean':normalized[:,4:7].mean(axis=1),'ordering':'group mean before lag0 normalization'}

def cluster_improvement(rows,*,clusters,bootstrap_draws,seed,delta_min,alpha,family_tests):
    import numpy as np
    integer(bootstrap_draws,100);integer(seed);integer(family_tests,1);real(alpha,0,1);real(delta_min)
    need(rows and set(clusters)=={r['session_id']for r in rows},'complete prospectively sealed biological or matrix-draw clusters')
    seen=set();effects={}
    for r in rows:
        need(r['session_id']not in seen,'one paired result per prespecified unit');seen.add(r['session_id'])
        for name in ('candidate','baseline'):real(r[name])
        effects.setdefault(clusters[r['session_id']],[]).append(r['candidate']-r['baseline'])
    need(len(effects)>1,'at least two independent clusters')
    values=np.asarray([np.mean(effects[k])for k in sorted(effects)])
    rng=np.random.Generator(np.random.PCG64(seed));means=np.empty(bootstrap_draws)
    for i in range(bootstrap_draws):means[i]=rng.choice(values,len(values),replace=True).mean()
    adjusted=alpha/family_tests;lo,hi=np.quantile(means,[adjusted/2,1-adjusted/2])
    return {'macro_paired_effect':float(values.mean()),'interval':[float(lo),float(hi)],'clusters':len(effects),
            'bootstrap_draws':bootstrap_draws,'familywise_alpha':alpha,'family_tests':family_tests,
            'practical_delta':delta_min,'improvement':bool(lo>delta_min),
            'claim':'prespecified matched-heldout endpoint only; not a whole-paper SOTA claim'}

