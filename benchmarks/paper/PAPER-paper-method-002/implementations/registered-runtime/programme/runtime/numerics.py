"""Invoke two frozen independent banks on the same complete mathematical inputs."""
import types
import math
from .strict import require, digest
from .errors import Refusal

ALLOWED=frozenset({"paired_errors","pearson","masked_metrics","window_summaries","window_max",
"soft_dtw","classification","regularizer","bounded_forward","bounded_log_jacobian",
"posterior_log_density","quantiles","distance_binned_quantiles","lyapunov","jacobian_sign",
"parameter_reset","perturbation_norms","receptive_field_normalize","paired_mean_difference"})

def load_bank(path,pin):
    # This source is part of the frozen benchmark package, never candidate code.
    from pathlib import Path
    p=Path(path);require(p.is_file() and not p.is_symlink(),"bank source")
    b=p.read_bytes();require(len(b)==pin["bytes"] and digest(b)==pin["sha256"],"bank pin")
    module=types.ModuleType("jaxley_bank_"+pin["sha256"][:12])
    exec(compile(b,str(p),"exec"),module.__dict__)
    return module

def compare(a,b,*,atol=1e-10,rtol=1e-9):
    if type(a) in (int,float) and type(b) in (int,float):
        require(math.isfinite(a) and math.isfinite(b),"nonfinite bank output")
        require(abs(a-b)<=atol+rtol*max(abs(a),abs(b)),"independent bank disagreement")
    elif isinstance(a,dict) and isinstance(b,dict):
        if a.get("defined") is False and b.get("defined") is False:
            require(a.get("reason") and b.get("reason"),"undefined reason missing");return
        require(set(a)==set(b),"bank object mismatch")
        for k in a:compare(a[k],b[k],atol=atol,rtol=rtol)
    elif isinstance(a,list) and isinstance(b,list):
        require(len(a)==len(b),"bank list mismatch")
        for x,y in zip(a,b):compare(x,y,atol=atol,rtol=rtol)
    else:require(type(a)==type(b) and a==b,"bank semantic disagreement")

def evaluate(banks,operation,args,kwargs=None):
    require(operation in ALLOWED,"unrecognized mathematical endpoint")
    require(type(args) is list and type(kwargs or {}) is dict,"endpoint arguments")
    a=getattr(banks[0],operation)(*args,**(kwargs or {}))
    b=getattr(banks[1],operation)(*args,**(kwargs or {}))
    compare(a,b)
    return {"value":a,"independent_numeric_agreement":True,
            "historical_native_parity":"separately_required"}

