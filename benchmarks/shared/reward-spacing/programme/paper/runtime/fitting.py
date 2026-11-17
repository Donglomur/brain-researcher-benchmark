"""Shared-support NB2 observation head for train-only mechanistic/nuisance fits.

Mechanistic features must come from the original qualified model trajectories.
These numerical heads do not invent missing TD, SOP or ANCCR dynamics.
"""
import math
import statistics as st
from reward_common import need,finite_number,integer,object_sha256
from protected_score import nb2_log_probability


def solve(a,b):
    n=len(b);need(len(a)==n and all(len(r)==n for r in a),'Square linear system')
    m=[list(r)+[v] for r,v in zip(a,b)]
    for j in range(n):
        pivot=max(range(j,n),key=lambda i:abs(m[i][j]));m[j],m[pivot]=m[pivot],m[j]
        need(abs(m[j][j])>1e-14,'Rank-deficient observation head')
        d=m[j][j];m[j]=[x/d for x in m[j]]
        for i in range(n):
            if i!=j:
                d=m[i][j];m[i]=[x-d*y for x,y in zip(m[i],m[j])]
    return [r[-1] for r in m]


def _matrix(x):
    need(type(x) is list and x and all(type(r) is list for r in x),'Feature matrix')
    p=len(x[0]);need(all(len(r)==p for r in x),'Feature dimensions')
    return [[finite_number(v) for v in r] for r in x]


def fit_nb2(x,y,kappa,l2,max_iterations=100):
    """Penalized conditional count head, standardized using training x only.

    Fixed log-link range [-30,30] is an optimization domain, recorded in the
    fit and enforced at prediction. It never clips a signed behavioral target.
    Dispersion/l2 are selected only by a separate inner validation call.
    """
    x=_matrix(x);need(len(x)==len(y),'Training observations');y=[integer(v,'A') for v in y]
    kappa=finite_number(kappa);l2=finite_number(l2);need(kappa>0 and l2>=0,'NB fit domain')
    need(type(max_iterations) is int and 1<=max_iterations<=1000,'Registered fit iteration budget')
    p=len(x[0]);center=[st.mean(r[j] for r in x) for j in range(p)]
    scale=[math.sqrt(st.mean((r[j]-center[j])**2 for r in x)) or 1 for j in range(p)]
    X=[[1]+[(v-c)/s for v,c,s in zip(row,center,scale)] for row in x]
    beta=[math.log((sum(y)+.5)/len(y))]+[0]*p;dim=p+1
    def objective(b):
        eta=[sum(a*c for a,c in zip(row,b)) for row in X]
        if any(abs(e)>30 for e in eta):return None
        return sum(nb2_log_probability(a,math.exp(e),kappa) for a,e in zip(y,eta))-.5*l2*sum(v*v for v in b[1:])
    value=objective(beta);need(value is not None,'Initial log-link domain')
    history=[value];status='nonconverged'
    for iteration in range(max_iterations):
        mu=[math.exp(sum(a*b for a,b in zip(row,beta))) for row in X]
        g=[sum(row[j]*kappa*(a-m)/(kappa+m) for row,a,m in zip(X,y,mu))-(l2*beta[j] if j else 0) for j in range(dim)]
        H=[[sum(row[j]*row[k]*kappa*m*(kappa+a)/(kappa+m)**2 for row,a,m in zip(X,y,mu))+
            (l2 if j==k and j else 0) for k in range(dim)] for j in range(dim)]
        step=solve(H,g)
        rate=1.;accepted=False
        for _ in range(40):
            proposed=[b+rate*s for b,s in zip(beta,step)];new=objective(proposed)
            if new is not None and new>=value-1e-12:accepted=True;break
            rate/=2
        if not accepted:status='line_search_failed';break
        change=abs(new-value);beta=proposed;value=new;history.append(value)
        if change<=1e-9*(1+abs(value)):status='computed';break
    return {'family':'NB2_conditional_A_given_B_H','status':status,'beta':beta,'center':center,'scale':scale,
            'kappa':kappa,'l2':l2,'log_link_domain':[-30,30],'training_observations':len(y),
            'fit_iterations':iteration+1,'objective_history':history,'scientific_qualification':False}


def predict_nb2(fit,row):
    need(fit['status']=='computed','Converged frozen head required')
    need(len(row)==len(fit['center']),'Exact feature dimensions')
    z=[1]+[(finite_number(v)-c)/s for v,c,s in zip(row,fit['center'],fit['scale'])]
    eta=sum(a*b for a,b in zip(z,fit['beta']));need(-30<=eta<=30,'Extrapolation beyond registered head domain')
    return {'mu':math.exp(eta),'kappa':fit['kappa']}


def select_nb2(training,validation,registered_options):
    """Inner selection only; test/outer labels are not arguments to this API."""
    need(training['split']=='train' and validation['split']=='validation','Inner partition roles')
    need(not(set(training['animals'])&set(validation['animals'])),'Train/validation animal separation')
    results=[];fits=[]
    for i,option in enumerate(registered_options):
        try:
            fit=fit_nb2(training['x'],training['A'],option['kappa'],option['l2'],option['iterations'])
            predictions=[predict_nb2(fit,row) for row in validation['x']]
            need(len(predictions)==len(validation['A']) and predictions,'Inner validation cases')
            # Equal animal weighting, so a long-recording animal cannot dominate.
            byanimal={}
            need(len(validation['case_animals'])==len(predictions),'Validation case identities')
            for aid,a,p in zip(validation['case_animals'],validation['A'],predictions):
                need(aid in validation['animals'],'Validation biological manifest')
                byanimal.setdefault(aid,[]).append(nb2_log_probability(a,p['mu'],p['kappa']))
            value=st.mean(st.mean(v) for v in byanimal.values());fits.append(fit)
            results.append({'option':i,'status':'computed','validation_log_score':value})
        except (ValueError,OverflowError) as exc:
            fits.append(None);results.append({'option':i,'status':'failed','reason':str(exc)})
    good=[r for r in results if r['status']=='computed'];need(good,'No valid inner fitted head')
    best=max(good,key=lambda r:(r['validation_log_score'],-r['option']))
    return {'fit':fits[best['option']],'selection':results,'selected_option':best['option'],
            'training_sha256':object_sha256(training),'validation_sha256':object_sha256(validation),
            'outer_targets_used':False,'refitted_on_outer_targets':False}
