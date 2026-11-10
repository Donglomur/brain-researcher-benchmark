"""Numerical leaves: executed only after separate runtime/science qualification."""
from .errors import need

def numpy():
    import numpy as np
    return np

def matrix(a, columns=None):
    np = numpy()
    a = np.asarray(a,dtype=np.float64)
    need(a.ndim==2 and len(a)>0 and np.isfinite(a).all() and
         (columns is None or a.shape[1]==columns), "finite-matrix")
    return a

def weights(w, n):
    np = numpy()
    w=np.asarray(w,dtype=np.float64)
    need(w.shape==(n,) and np.isfinite(w).all() and (w>0).all(), "positive-weights")
    return w/w.sum()

def mean(a,w):
    np=numpy();a=matrix(a);w=weights(w,len(a))
    return np.where(np.all(a==a[0],axis=0),a[0],(a*w[:,None]).sum(axis=0))

def fit_mean(y,w):
    return {"kind":"Rmean","mean":mean(matrix(y,400),w)}

def fit_r0(x,y,w):
    np=numpy();x=matrix(x);y=matrix(y,400);w=weights(w,len(x))
    need(len(x)==len(y), "r0-fit-support")
    mu=mean(x,w);sd=np.sqrt(((x-mu)**2*w[:,None]).sum(axis=0));sd=np.where(sd>1e-12,sd,1.)
    a=(x-mu)/sd
    _,s,vt=np.linalg.svd(a*np.sqrt(w[:,None]),full_matrices=False)
    need(len(s)>=16 and np.isfinite(s).all() and s[0]>0 and s[15]>s[0]*1e-10, "r0-rank16")
    basis=vt[:16].T;z=a@basis;my=mean(y,w);wn=w*len(x)
    coefficient=np.linalg.solve(z.T@(wn[:,None]*z)+100*np.eye(16),z.T@(wn[:,None]*(y-my)))
    need(np.isfinite(coefficient).all(), "r0-finite-solve")
    return {"kind":"R0","mean":my,"x_mean":mu,"x_sd":sd,"basis":basis,"coefficient":coefficient}

def config_grid(groups):
    need(type(groups)is int and 1<=groups<=4, "kernel-groups")
    gamma=[[1/groups]*groups]
    if groups>1:
        gamma += [[float(i==j) for i in range(groups)] for j in range(groups)]
        gamma += [[(4 if i==j else 1)/(groups+3) for i in range(groups)] for j in range(groups)]
    return [{"gamma":g,"alpha":a} for g in gamma for a in (0.0001,0.01,1.,100.,10000.)]

def fit_kernel(groups,y,w,config):
    np=numpy();y=matrix(y);w=weights(w,len(y));mu=mean(y,w);states=[];kernels=[]
    need(len(groups)==len(config["gamma"]), "gamma-groups")
    for group in groups:
        x=matrix(group);need(len(x)==len(y), "kernel-fit-support")
        mx=mean(x,w);sd=np.sqrt(((x-mx)**2*w[:,None]).sum(axis=0));sd=np.where(sd>1e-12,sd,1.)
        z=(x-mx)/sd;trace=float((w[:,None]*z*z).sum())
        need(np.isfinite(trace) and trace>=0, "kernel-trace")
        k=np.zeros((len(x),len(x))) if trace==0 else z@z.T/trace
        states.append({"mean":mx,"sd":sd,"trace":trace,"train_z":z});kernels.append(k)
    k=sum(g*a for g,a in zip(config["gamma"],kernels))
    need(np.isfinite(k).all(), "finite-kernel")
    from himalaya.backend import set_backend
    from himalaya.kernel_ridge import KernelRidge
    set_backend("numpy")
    model=KernelRidge(kernel="precomputed",alpha=config["alpha"],fit_intercept=False,
                      solver="eigenvalues",solver_params={"method":"svd"},force_cpu=True)
    model.fit(k.copy(),y-mu,sample_weight=w)
    dual=np.asarray(model.dual_coef_,dtype=np.float64)
    a=dual/np.sqrt(w[:,None]);rhs=np.sqrt(w[:,None])*(y-mu)
    residual=(np.sqrt(w[:,None])*k*np.sqrt(w[None,:])+config["alpha"]*np.eye(len(w)))@a-rhs
    ratio=np.linalg.norm(residual)/max(1.,np.linalg.norm(rhs))
    need(np.isfinite(dual).all() and np.isfinite(ratio) and ratio<=1e-8, "kernel-solve-residual")
    return {"kind":"kernel","mean":mu,"groups":states,"config":config,"dual":dual,
            "residual":float(ratio)}

def infer(state,x):
    np=numpy()
    if state["kind"]=="Rmean":
        return np.repeat(state["mean"][None,:],len(x),axis=0)
    if state["kind"]=="R0":
        return ((matrix(x)-state["x_mean"])/state["x_sd"])@state["basis"]@state["coefficient"]+state["mean"]
    need(state["kind"]=="kernel" and len(x)==len(state["groups"]), "infer-state")
    kernels=[]
    for group,s in zip(x,state["groups"]):
        z=(matrix(group)-s["mean"])/s["sd"]
        kernels.append(np.zeros((len(z),len(s["train_z"]))) if s["trace"]==0
                       else z@s["train_z"].T/s["trace"])
    k=sum(g*a for g,a in zip(state["config"]["gamma"],kernels))
    return k@state["dual"]+state["mean"]

def weighted_errors(pred,target,w):
    np=numpy();pred=matrix(pred,400);target=matrix(target,400)
    need(pred.shape==target.shape,"oof-shape")
    result=((pred-target)**2*weights(w,len(pred))[:,None]).sum(axis=0)
    need(np.isfinite(result).all(),"finite-oof-errors")
    return result

def prediction(a,rows):
    np=numpy();a=matrix(a,400);need(len(a)==rows,"prediction-rows")
    a=np.ascontiguousarray(a,dtype="<f4");need(np.isfinite(a).all(),"finite-float32-cast")
    return a
