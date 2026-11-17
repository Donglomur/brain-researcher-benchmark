"""Matched-information baselines; no fit or scientific import occurs on import.

This is a new statistical reference, not an exact author Julia model port.
"""
import math
from collections import Counter,defaultdict
from consumer import ContractError,validate_observation,probability_vector

LAMBDAS=(0.01,0.1,1.0)

def relative_action(action,x):
    current_left=x["gL"]
    return (0 if (action==1)==current_left else 1) if action<3 else (2 if (action==3)==current_left else 3)

def absolute_probabilities(relative,x):
    return probability_vector(relative if x["gL"] else (relative[1],relative[0],relative[3],relative[2]))

def design(x):
    validate_observation(x);left=x["gL"]
    # nB in the source means BLOCKED, whereas nR means the right patch.
    # Below use explicit fields so right-attended trials never alias blocked/right.
    na=x["nL"] if left else x["nR"];nb=x["nR"] if left else x["nL"];nc=x["nB"]
    ra=x["rL"] if left else x["rR"];rb=x["rR"] if left else x["rL"]
    ma=x["muL"] if left else x["muR"];mb=x["muR"] if left else x["muL"]
    la,lb,lc=math.log1p(na),math.log1p(nb),math.log1p(nc);clock=math.log1p(x["t"])
    first=float(x["first_visit"]);diff=ma-mb;side=1.0 if left else -1.0
    # Coded count/cover variables are not relabelled as evidence precision.
    return (1.,la,lb,lc,ra/100,rb/100,ma,mb,diff,abs(diff),clock,first,side,
            diff*clock,diff*first,la-lb,la*first,lb*first,lc*first,clock*first,
            ma*lb,mb*la,side*diff,side*clock,side*first)

class Uniform:
    def predict(self,x):validate_observation(x);return (.25,.25,.25,.25)

class ContextCounts:
    """Smoothed train-only relative stay/switch/stop propensity."""
    def __init__(self,train):
        self.global_counts=[1.,1.,1.,1.];self.by_context=defaultdict(lambda:[1.,1.,1.,1.])
        for d in train:
            x=d.observation();a=relative_action(d.action,x);self.global_counts[a]+=1
            self.by_context[self.context(x)][a]+=1
    @staticmethod
    def context(x):
        return (x["first_visit"],min(int(math.log2(x["t"]+1)),5))
    def predict(self,x):
        validate_observation(x);v=self.by_context.get(self.context(x),self.global_counts)
        return absolute_probabilities(tuple(z/math.fsum(v) for z in v),x)

class RidgeSoftmax:
    def __init__(self,mean,scale,weights,fit_trace):
        self.mean,self.scale,self.weights=mean,scale,weights;self.fit_trace=fit_trace
    def predict(self,x):
        import numpy as np
        z=(np.asarray(design(x),dtype=np.float64)-self.mean)/self.scale
        logits=z@self.weights;logits-=np.max(logits)
        p=np.exp(logits);p/=np.sum(p)
        if np.any(p<=0):raise ContractError("numerical probability underflow, no silent clipping")
        return absolute_probabilities(tuple(float(v) for v in p),x)

def fit_ridge(train, penalty, *, max_iter=4000, tolerance=1e-6):
    """Deterministic all-weight multinomial ridge with Armijo search.

    All normalization and optimization use only supplied training observations.
    Every coefficient, including all four class intercepts, receives L2 penalty.
    Positive penalty gives a finite optimum even for an absent training class;
    this is a declared new reference, not the original unpenalized-intercept fit.
    A convergence failure is a whole-reference failure, never an omitted subject.
    """
    import numpy as np
    if penalty not in LAMBDAS or not train:raise ContractError("prespecified penalty/train")
    raw=np.asarray([design(d.observation()) for d in train],dtype=np.float64)
    y=np.asarray([relative_action(d.action,d.observation()) for d in train],dtype=np.int64)
    mean=raw.mean(axis=0);scale=raw.std(axis=0)
    mean[0]=0.;scale[0]=1.;scale[scale<1e-12]=1.
    x=(raw-mean)/scale;n=len(y);w=np.zeros((x.shape[1],4),dtype=np.float64)
    def value_grad(weight):
        z=x@weight;m=z.max(axis=1);e=np.exp(z-m[:,None]);den=e.sum(axis=1)
        p=e/den[:,None];loss=float(np.mean(m+np.log(den)-z[np.arange(n),y]))
        loss+=penalty*.5*float(np.sum(weight**2))
        p[np.arange(n),y]-=1;g=x.T@p/n;g+=penalty*weight
        return loss,g
    loss,g=value_grad(w);initial=loss;accepted=0;converged=False
    for iteration in range(max_iter):
        norm=float(np.max(np.abs(g)))
        if not math.isfinite(loss) or not np.isfinite(g).all():raise ContractError("nonfinite optimizer")
        if norm<=tolerance:converged=True;break
        step=1.;squared=float(np.sum(g*g));found=False
        for _ in range(40):
            candidate=w-step*g;new_loss,new_g=value_grad(candidate)
            if math.isfinite(new_loss) and new_loss<=loss-1e-4*step*squared:
                w,loss,g=candidate,new_loss,new_g;accepted+=1;found=True;break
            step*=.5
        if not found:raise ContractError("line search failed")
    if not converged and float(np.max(np.abs(g)))<=tolerance:converged=True
    if not converged:raise ContractError("reference did not converge within fixed complete budget")
    return RidgeSoftmax(mean,scale,w,{"penalty":penalty,"iterations":accepted,
        "initial_objective":initial,"final_objective":loss,"gradient_max":float(np.max(np.abs(g))),
        "training_rows":n,"converged":True,"normalization":"training only",
        "penalty_scope":"all coefficients, including four class intercepts",
        "implementation":"new deterministic regularized multinomial reference, not Julia parity"})

def mean_nll(model,data):
    if not data:raise ContractError("empty validation session")
    return math.fsum(-math.log(model.predict(d.observation())[d.action-1]) for d in data)/len(data)

def select_reference(train):
    """Inner leave-session-out selection among fixed families and penalties.

    Exactly the three outer-training sessions; outer-test states and labels are
    not arguments. Equal inner-session weighting avoids long-session selection.
    """
    sessions=sorted({d.session for d in train})
    if len(sessions)!=3 or len({d.subject for d in train})!=1:raise ContractError("three-session per-person inner design")
    specs=[("uniform",None),("context_counts",None)]+[("ridge",p) for p in LAMBDAS]
    ledger=[]
    for family,p in specs:
        losses=[]
        for held in sessions:
            fit=tuple(d for d in train if d.session!=held);valid=tuple(d for d in train if d.session==held)
            model=Uniform() if family=="uniform" else ContextCounts(fit) if family=="context_counts" else fit_ridge(fit,p)
            losses.append(mean_nll(model,valid))
        ledger.append({"family":family,"penalty":p,"inner_session_losses":losses,"mean":math.fsum(losses)/3})
    winner=min(range(len(ledger)),key=lambda i:(ledger[i]["mean"],i));spec=ledger[winner]
    model=Uniform() if spec["family"]=="uniform" else ContextCounts(train) if spec["family"]=="context_counts" else fit_ridge(train,spec["penalty"])
    return model,{"selection":"train-only inner held-session NLL","ledger":ledger,"winner":spec,
        "all_outer_test_inputs_unavailable_to_selector":True}

