"""Selected deterministic ridge-Poisson Newton/Armijo implementation source.

Explicit float64 buffers and scalar Cholesky avoid opaque BLAS/LAPACK workspaces.
No numerical function is run during construction. Every selected public entry
requires the absent genuine runtime issuer before any array allocation/work.
"""
from array import array
from dataclasses import dataclass
import math
from .authority import require_live
from .constants import MAX_UPDATES,LINE_ATTEMPTS,ARMIJO,GRADIENT_TOL

class FitFailure(ArithmeticError):pass

@dataclass
class FitResult:
    status:str
    beta:object
    updates:int
    error:object

def zeros(n,calls):
    calls.enter('float64_allocation')
    result=array('d',[0.0])*n
    if result.itemsize!=8:raise FitFailure('float64 storage unavailable')
    return result

def dot_row(x,row,p,beta,calls):
    calls.enter('dot_row');total=0.
    for j in range(p):total+=x[row*p+j]*beta[j]
    return total

def objective(x,p,rows,y,offset,beta,lam,eta,mu,calls):
    calls.enter('objective');value=0.
    for i,row in enumerate(rows):
        eta[i]=offset+dot_row(x,row,p,beta,calls)
        calls.enter('exp_scalar');mu[i]=math.exp(eta[i])
        value+=mu[i]-float(y(i))*eta[i]
    value/=len(rows)
    for b in beta:value+=.5*lam*b*b
    if not math.isfinite(value)or any(not math.isfinite(eta[i])or not math.isfinite(mu[i])for i in range(len(rows))):raise FitFailure('nonfinite objective')
    return value

def derivatives(x,p,rows,y,beta,lam,mu,g,h,calls):
    calls.enter('gradient_hessian');n=len(rows)
    for j in range(p):
        total=0.
        for i,row in enumerate(rows):total+=x[row*p+j]*(mu[i]-float(y(i)))
        g[j]=total/n+lam*beta[j]
        for k in range(j+1):
            total=0.
            for i,row in enumerate(rows):total+=x[row*p+j]*mu[i]*x[row*p+k]
            value=total/n+(lam if j==k else 0.)
            h[j*p+k]=h[k*p+j]=value
    if any(not math.isfinite(v)for v in g)or any(not math.isfinite(v)for v in h):raise FitFailure('nonfinite derivatives')

def cholesky_solve(h,g,p,lower,delta,calls):
    calls.enter('cholesky_solve')
    for i in range(p*p):lower[i]=0.
    for i in range(p):
        for j in range(i+1):
            value=h[i*p+j]
            for k in range(j):value-=lower[i*p+k]*lower[j*p+k]
            if i==j:
                if not math.isfinite(value)or value<=0:raise FitFailure('nonpositive or nonfinite Cholesky pivot')
                calls.enter('sqrt_scalar');lower[i*p+j]=math.sqrt(value)
            else:lower[i*p+j]=value/lower[j*p+j]
    # Same direction buffer holds the intermediate triangular solve.
    for i in range(p):
        value=g[i]
        for k in range(i):value-=lower[i*p+k]*delta[k]
        delta[i]=value/lower[i*p+i]
    for i in range(p-1,-1,-1):
        value=delta[i]
        for k in range(i+1,p):value-=lower[k*p+i]*delta[k]
        delta[i]=value/lower[i*p+i]
    if any(not math.isfinite(v)for v in delta):raise FitFailure('nonfinite Newton solve')

def fit(x,p,rows,y,offset,lam,host,calls):
    require_live(host,'fit selected ridge-Poisson model')
    calls.enter('fit_attempt');updates=0
    try:
        if not rows or not math.isfinite(offset)or not math.isfinite(lam)or lam<=0:raise FitFailure('invalid fitted support/offset/lambda')
        beta=zeros(p,calls);trial=zeros(p,calls);g=zeros(p,calls);delta=zeros(p,calls)
        h=zeros(p*p,calls);lower=zeros(p*p,calls);eta=zeros(len(rows),calls);mu=zeros(len(rows),calls)
        f=objective(x,p,rows,y,offset,beta,lam,eta,mu,calls)
        tolerance=GRADIENT_TOL*(1+sum(y(i)for i in range(len(rows)))/len(rows))
        for iteration in range(MAX_UPDATES+1):
            derivatives(x,p,rows,y,beta,lam,mu,g,h,calls)
            if max(abs(v)for v in g)<=tolerance:
                calls.enter('fit_success');return FitResult('success',beta,updates,None)
            if iteration==MAX_UPDATES:raise FitFailure('200-update limit without convergence')
            cholesky_solve(h,g,p,lower,delta,calls)
            slope=sum(g[j]*delta[j]for j in range(p))
            if not math.isfinite(slope)or slope<=0:raise FitFailure('invalid descent direction')
            accepted=False
            for k in range(LINE_ATTEMPTS):
                calls.enter('line_search_attempt');step=2.**(-k)
                for j in range(p):trial[j]=beta[j]-step*delta[j]
                try:new_f=objective(x,p,rows,y,offset,trial,lam,eta,mu,calls)
                except (ArithmeticError,ValueError)as error:
                    calls.failure('nonfinite_line_search_trial',error);continue
                if new_f<=f-ARMIJO*step*slope:
                    for j in range(p):beta[j]=trial[j]
                    f=new_f;updates+=1;accepted=True;break
            if not accepted:raise FitFailure('31-attempt Armijo search exhausted')
        raise FitFailure('unreachable fit terminal')
    except (ArithmeticError,ValueError)as error:
        calls.enter('fit_failure');calls.failure('fit',error)
        return FitResult('failed',None,updates,error)

def predicted_mean(x,p,row,beta,offset,calls):
    calls.enter('prediction_row');calls.enter('exp_scalar')
    mu=math.exp(offset+dot_row(x,row,p,beta,calls))
    if not math.isfinite(mu)or mu<=0:raise FitFailure('nonpositive/nonfinite mean; no clipping')
    return mu

def deviance_term(y,mu,calls):
    calls.enter('deviance_row')
    if type(y)is not int or y<0 or not math.isfinite(mu)or mu<=0:raise ValueError('integer nonnegative count/positive finite mean')
    if y==0:value=2*mu
    elif y==mu:value=0.
    else:
        calls.enter('log_scalar');value=2*(y*math.log(y/mu)-y+mu)
    if not math.isfinite(value)or value<0:raise FitFailure('unsupported deviance arithmetic; no negative clipping')
    return value

def prediction_deviance(x,p,rows,y,beta,offset,host,calls):
    require_live(host,'validation loss for fixed model')
    calls.enter('validation_deviance')
    if not rows:raise FitFailure('complete validation rows required')
    return sum(deviance_term(y(i),predicted_mean(x,p,row,beta,offset,calls),calls)for i,row in enumerate(rows))/len(rows)

def frozen_deviance(counts,predictions,nrows,units,unit,host,calls):
    require_live(host,'private QUERY loss after genuine freeze')
    calls.enter('query_deviance')
    return sum(deviance_term(counts[i*units+unit],predictions[i*units+unit],calls)for i in range(nrows))/nrows
