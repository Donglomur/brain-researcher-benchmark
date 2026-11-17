"""Full native sweep expansion and independently checked model summaries.

No re-invented TD/SOP/ANCCR simulator replaces absent original model bodies.
"""
import itertools
import math
from reward_common import need,finite_number,object_sha256


def learning_rate(alpha0,iri,dt):
    alpha0,iri,dt=[finite_number(x) for x in (alpha0,iri,dt)]
    need(0<alpha0<1 and iri>0 and dt>0,'ANCCR scaling domain')
    return -math.expm1((iri/dt)*math.log1p(-alpha0))


def configurations(programme,family,sop_resolution=None):
    rows={x['family']:x for x in programme['families']};row=rows[family]
    if family=='SOP':
        need(sop_resolution is not None and sop_resolution['independently_adjudicated'] is True,
             'Printed SOP grid conflicts with reported optimum; no invented repair')
        grid=sop_resolution['grid']
    elif family=='IRI-scaled microstimulus TD':grid={'k':row['k_sweep']}
    else:grid=row['sweep']
    keys=sorted(grid)
    need(all(type(grid[k]) is list and grid[k] for k in keys),'Complete parameter dimensions')
    for values in itertools.product(*(grid[k] for k in keys)):
        config=dict(zip(keys,values))
        if family=='SOP' and sop_resolution.get('constrained'):
            if not(config['pd1cs']>config['pd2cs'] and config['pd1us']>config['pd2us']):continue
        yield config


def sweep_cases(programme,family,sop_resolution=None):
    for config in configurations(programme,family,sop_resolution):
        for condition,ntrials in zip(programme['conditions'],programme['native_simulated_trials']):
            for iteration in range(programme['iterations_per_case']):
                yield {'family':family,'configuration_sha256':object_sha256(config),'parameters':config,
                       'condition':condition,'iteration':iteration,'n_trials':ntrials,
                       'required_trajectories':{'Microstimulus TD':['value','cue_rpe'],
                         'IRI-scaled microstimulus TD':['value','cue_rpe'],'SOP':['value','reward_A2'],
                         'ANCCR':['value','dopamine','prospective_association']}[family],
                       'fixed_seed_required':True}


def compare_models(observed,model_cases,n_parameters,log_base):
    """Native log-onset RSS and both displayed k=0 / penalized AIC.

    Missing/noncrossing outcomes remain unscorable, not substituted max trials.
    """
    log_base=finite_number(log_base);need(log_base>0 and log_base!=1,'Explicit adjudicated log base')
    need(observed and all(finite_number(x)>0 for x in observed),'Positive observed onset')
    summaries=[]
    for name,predicted in model_cases.items():
        if len(predicted)!=len(observed) or any(x is None or x<=0 for x in predicted):
            summaries.append({'model':name,'status':'required-unscorable','reason':'missing_or_nonpositive_onset'});continue
        rss=sum((math.log(y,log_base)-math.log(finite_number(p),log_base))**2 for y,p in zip(observed,predicted))
        if rss==0:
            summaries.append({'model':name,'status':'degenerate','reason':'zero_RSS_log_undefined','rss':0});continue
        aic=len(observed)*math.log(rss/len(observed))
        summaries.append({'model':name,'status':'computed','rss':rss,'AIC_k0':aic,
                          'AIC_parameter_penalized':aic+2*n_parameters[name],'onset_log_base':log_base})
    good=[s for s in summaries if s['status']=='computed']
    if good:
        best=min(s['AIC_k0'] for s in good)
        for s in good:s['relative_weight_k0']=math.exp(-.5*(s['AIC_k0']-best))
    return summaries


def sigmoid_fit(x,y,max_iterations=250):
    """Independent four-parameter damped Gauss-Newton; native scipy fit separate."""
    need(len(x)==len(y)>=6,'Sigmoid observations');x=[finite_number(v) for v in x];y=[finite_number(v) for v in y]
    need(max(x)>min(x),'Sigmoid x range')
    def curve(p):
        L,x0,k,b=p
        return [L/(1+math.exp(max(-700,min(700,-k*(v-x0)))))+b for v in x]
    def solve(A,b):
        A=[list(r)+[v] for r,v in zip(A,b)]
        for j in range(4):
            i=max(range(j,4),key=lambda i:abs(A[i][j]));A[j],A[i]=A[i],A[j]
            need(abs(A[j][j])>1e-20,'Singular sigmoid system');v=A[j][j];A[j]=[z/v for z in A[j]]
            for i in range(4):
                if i!=j:
                    v=A[i][j];A[i]=[a-v*b for a,b in zip(A[i],A[j])]
        return [r[-1] for r in A]
    p=[max(y)-min(y),(max(x)+min(x))/2,4/(max(x)-min(x)),min(y)];damping=.01
    old=sum((a-b)**2 for a,b in zip(curve(p),y));history=[old];converged=False
    for iteration in range(max_iterations):
        f=curve(p);J=[]
        for j in range(4):
            h=1e-5*(1+abs(p[j]));hi=p[:];lo=p[:];hi[j]+=h;lo[j]-=h
            J.append([(a-b)/(2*h) for a,b in zip(curve(hi),curve(lo))])
        A=[[sum(a*b for a,b in zip(J[j],J[k]))+(damping if j==k else 0) for k in range(4)] for j in range(4)]
        rhs=[sum(a*(b-c) for a,b,c in zip(j,y,f)) for j in J];step=solve(A,rhs);proposed=[a+b for a,b in zip(p,step)]
        new=sum((a-b)**2 for a,b in zip(curve(proposed),y))
        if new<old:
            p=proposed;history.append(new);damping=max(1e-12,damping/3)
            if abs(old-new)<1e-10*(1+old):converged=True;old=new;break
            old=new
        else:damping*=10
    return {'status':'computed' if converged else 'nonconverged','parameters':dict(zip(['L','x0','k','b'],p)),
            'fitted':curve(p),'rss':old,'iterations':iteration+1,'loss_history':history,
            'branch':'independent_damped_Gauss_Newton_not_native_scipy_parity'}
