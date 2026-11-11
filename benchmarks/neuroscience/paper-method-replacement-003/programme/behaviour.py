"""Full four-task population-dynamics mathematical reconstruction.

Article MathML fixes k=10*sqrt(T), not 10*T. Exact task clocks, smoothing,
baseline, soft-normalization formula and relabel-fraction grid are mandatory
operator recipe inputs; no historical equivalence is claimed for unknowns.
"""
from dataclasses import dataclass
from .cohort import SupportError
from .profiles import MethodGap

TASKS=('reward_hull','eyeblink_medina','locomotion_hausser','pursuit_lisberger')

@dataclass(frozen=True)
class DynamicsRecipe:
    task: str
    times_seconds: tuple
    baseline_indices: tuple
    causal_kernel: tuple
    baseline_ddof: int
    soft_normalization: str
    components: int
    relabel_fractions: tuple
    random_seed: int
    method_provenance: str

    def validate(self):
        if self.task not in TASKS or not self.method_provenance:raise MethodGap('task/method provenance missing')
        if not self.baseline_indices or self.baseline_ddof not in (0,1):raise MethodGap('explicit baseline convention required')
        if self.soft_normalization != 'original_denominator_producer_required':
            raise MethodGap('no prospective soft-normalization formula has been selected')
        if self.components<1 or not self.relabel_fractions or any(not 0<=f<=1 for f in self.relabel_fractions):
            raise MethodGap('complete component/fraction recipe required')
        if type(self.random_seed) is not int:raise MethodGap('explicit reconstruction seed required')
        baseline_rows(self)

def baseline_rows(recipe):
    """Explicit row selector, never tuple-as-multiple-axis indexing."""
    indices=recipe.baseline_indices
    if not indices or len(set(indices))!=len(indices) or any(type(i) is not int or i<0 or i>=len(recipe.times_seconds) for i in indices):
        raise SupportError('unique in-range baseline time rows required')
    return list(indices)

def trial_rates(spike_seconds, trials, recipe):
    """All eligible trials with real clock alignment; no synthetic event times."""
    recipe.validate()
    import numpy as np
    times=np.asarray(recipe.times_seconds,dtype=float);delta=np.diff(times)
    if len(times)<2 or not np.all(delta>0) or not np.allclose(delta,delta[0]):raise SupportError('uniform event-time grid required')
    kernel=np.asarray(recipe.causal_kernel,dtype=float)
    if not len(kernel) or not np.isfinite(kernel).all() or np.any(kernel<0) or not np.isclose(kernel.sum(),1):
        raise SupportError('causal smoothing kernel must be explicit and normalized')
    if not trials or len({t['trial_id'] for t in trials})!=len(trials):raise SupportError('complete unique trial identities required')
    rates=[];ids=[]
    for trial in trials:
        if trial.get('disposition')!='eligible' or not trial.get('clock_qualified'):
            raise SupportError('trial eligibility/clock unavailable; retain full disposition')
        onset=trial['onset_seconds'];edges=np.r_[times,times[-1]+delta[0]]+onset
        # Smoothing starts before the output window to avoid silently zero-padding
        # an unknown pre-window history. Trials supply its valid source interval.
        start=edges[0]-(len(kernel)-1)*delta[0]
        if trial['valid_start_seconds']>start or trial['valid_stop_seconds']<edges[-1]:
            raise SupportError('complete smoothing support not observed')
        extended=start+np.arange(len(times)+len(kernel))*delta[0]
        counts,_=np.histogram(spike_seconds,bins=extended)
        smoothed=np.convolve(counts/delta[0],kernel,mode='full')
        rates.append(smoothed[len(kernel)-1:len(kernel)-1+len(times)]);ids.append(trial['trial_id'])
    return {'trial_ids':tuple(ids),'time_seconds':times,'rate':np.stack(rates)}

def normalized_responses(unit_trial_rates, recipe):
    recipe.validate()
    import numpy as np
    arrays=[np.asarray(x['rate']) for x in unit_trial_rates]
    if not arrays or any(x.ndim!=2 or x.shape[1]!=len(recipe.times_seconds) for x in arrays):
        raise SupportError('complete per-unit trial/time support required')
    baseline=np.asarray(baseline_rows(recipe),dtype=int)
    responses=[];details=[]
    for x in arrays:
        scale=x[:,baseline].std(ddof=recipe.baseline_ddof)
        if not np.isfinite(scale) or scale<=0:raise SupportError('undefined baseline variance; no silent unit removal')
        mean=(x/scale).mean(axis=0);mean-=mean[baseline].mean()
        responses.append(mean);details.append({'trials':len(x),'baseline_sd':float(scale)})
    return np.stack(responses),details

def trajectory(responses, recipe, denominators):
    import numpy as np
    x=np.asarray(responses,dtype=float)
    if x.ndim!=2 or not np.isfinite(x).all() or x.shape[1]!=len(recipe.times_seconds):raise SupportError('trajectory input extent')
    centered=x-x.mean(axis=1,keepdims=True)
    # Missing original producer is explicit. Supplied denominators are scientific
    # operands, not a recipe or authority substitute; no default formula exists.
    if denominators is None:raise MethodGap('original soft-normalization denominator producer missing')
    scale=np.asarray(denominators)
    if scale.shape!=(len(x),) or not np.isfinite(scale).all() or np.any(scale<=0):raise SupportError('undefined or unaligned soft normalization')
    centered=centered/scale[:,None]
    u,s,_=np.linalg.svd(centered.T,full_matrices=False)
    if len(s)<recipe.components or s.sum()<=0:raise SupportError('unavailable full trajectory rank')
    s=(10*np.sqrt(x.shape[1]))*s/s.sum()
    z=u[:,:recipe.components]*s[:recipe.components]
    return z-z[np.asarray(baseline_rows(recipe),dtype=int),:].mean(axis=0)

def aligned_distance(full, partial):
    import numpy as np
    from scipy.linalg import orthogonal_procrustes
    if full.shape!=partial.shape:raise SupportError('trajectory time/component mismatch')
    rotation,_=orthogonal_procrustes(partial,full)
    return float(np.linalg.norm(full-partial@rotation)),rotation

def dynamics_comparisons(responses, labels, unit_keys, recipe, denominators):
    """All classes, pairwise equal-size nulls and every selected error fraction."""
    recipe.validate()
    import numpy as np
    if len(responses)!=len(labels) or len(labels)!=len(unit_keys) or len(set(unit_keys))!=len(unit_keys):
        raise SupportError('population/unit/label join mismatch')
    classes=('PkC_ss','GoC','MFB','MLI')
    if set(labels)!=set(classes):raise SupportError('complete four-class behavioral support required')
    labels=np.asarray(labels);rng=np.random.default_rng(recipe.random_seed)
    if denominators is None:raise MethodGap('original soft-normalization producer missing')
    denominators=np.asarray(denominators)
    full=trajectory(responses,recipe,denominators);z={c:trajectory(responses[labels==c],recipe,denominators[labels==c]) for c in classes}
    distances={c:aligned_distance(full,z[c])[0] for c in classes};pairs={}
    for i,a in enumerate(classes):
        for b in classes[i+1:]:
            ia=np.flatnonzero(labels==a);ib=np.flatnonzero(labels==b);n=min(len(ia),len(ib));null=[]
            if n<recipe.components:raise SupportError('insufficient equal-size permutation support')
            for _ in range(1000):
                selected=np.r_[rng.choice(ia,n,replace=False),rng.choice(ib,n,replace=False)]
                shuffled=rng.permutation(selected)
                null.append(aligned_distance(trajectory(responses[shuffled[:n]],recipe,denominators[shuffled[:n]]),
                                             trajectory(responses[shuffled[n:]],recipe,denominators[shuffled[n:]]))[0])
            pairs[(a,b)]={'observed':aligned_distance(z[a],z[b])[0],
                          'null_distances':np.asarray(null),'equal_group_size':n}
    errors={}
    for fraction in recipe.relabel_fractions:
        draws=[]
        for _ in range(1000):
            changed=labels.copy();rows=rng.choice(len(labels),int(fraction*len(labels)),replace=False)
            changed[rows]=rng.choice(classes,len(rows),replace=True)
            if any(np.sum(changed==c)<recipe.components for c in classes):
                draws.append({'disposition':'undefined_rank','labels':changed});continue
            draws.append({'disposition':'computed','labels':changed,
                'distances':{c:aligned_distance(full,trajectory(responses[changed==c],recipe,denominators[changed==c]))[0] for c in classes}})
        errors[fraction]=draws
    return {'units':tuple(unit_keys),'full':full,'trajectories':z,'distances':distances,
            'permutation_pairs':pairs,'mislabel_draws':errors,'profile':'parameter_bound_paper_reconstruction_not_historical_parity'}
