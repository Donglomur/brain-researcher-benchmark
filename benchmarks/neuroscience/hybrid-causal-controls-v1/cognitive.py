"""Source-derived active Linear/UCB forward adapter, Float64, no fit on import.

Omits the unused initial_visit loader dependency. This is a source-derived
calculation, not original Julia-loader or Float32 numerical parity.
"""
import math
from consumer import validate_observation,probability_vector,ContractError

def logistic(x):
    if type(x) not in (int,float) or not math.isfinite(x):raise ContractError("finite parameter")
    return 1/(1+math.exp(-x)) if x>=0 else math.exp(x)/(1+math.exp(x))

def subjective(x, lambda0, omega, decay):
    validate_observation(x)
    if any(not 0<=v<=1 for v in (lambda0,omega,decay)):raise ContractError("transformed cognitive parameters")
    counts={};reds={}
    for side,other,attended in (("L","R",x["gL"]),("R","L",x["gR"])):
        if attended:
            n=2+x["n"+side];r=1+x["r"+side]
        elif x["first_visit"]:
            n=2+omega*x["n"+side]+(1-omega)*x["nB"]
            r=n*(.5+(x["mu"+other]-.5)*lambda0)
        else:
            factor=math.exp(-decay*x["t"])
            n=2+x["n"+side]*factor;r=1+x["r"+side]*factor
        counts[side]=n;reds[side]=r
    return counts["L"],counts["R"],reds["L"],reds["R"]

def logits(x, theta, family):
    length=7 if family=="linear" else 6 if family=="ucb" else 0
    if len(theta)!=length or not length or any(type(v) not in (int,float) or not math.isfinite(v) for v in theta):
        raise ContractError("exact finite cognitive parameter vector")
    lambda0,omega,cost,decay=map(logistic,theta[:4]);temperature=logistic(theta[-1])
    if temperature<=0:raise ContractError("temperature underflow")
    nl,nr,rl,rr=subjective(x,lambda0,omega,decay)
    if family=="linear":vl,vr=(theta[4]+theta[5]*n/100 for n in (nl,nr))
    else:vl,vr=(abs(theta[4])*math.sqrt(math.log(nl+nr)/n) for n in (nl,nr))
    return ((vl-(not x["gL"])*cost)/temperature,
            (vr-(not x["gR"])*cost)/temperature,
            (rl/nl-rr/nr)/temperature,(rr/nr-rl/nl)/temperature)

def predict(x,theta,family):
    z=logits(x,theta,family);m=max(z);e=[math.exp(v-m) for v in z];total=math.fsum(e)
    return probability_vector([v/total for v in e])

def training_objective(theta,train,family):
    if not train:raise ContractError("nonempty training only")
    return math.fsum(-math.log(predict(d.observation(),theta,family)[d.action-1]) for d in train)/len(train)

