"""Fit-local frequency transforms over immutable, aligned primitive rows."""
from collections import Counter
import math
from .errors import need
from .identity import identity
from .policy import ARMS

def fit(rows, primitives):
    need(len(rows)==len(primitives) and rows, "feature-fit-support")
    counts=Counter(w for p in primitives for lag in p["terms"] for w in lag)
    return {"counts":dict(counts),"total":sum(counts.values()),
            "fit_rows":identity([r["row"] for r in rows])}

def transform(state,primitives,arm):
    import numpy as np
    need(arm in ARMS and primitives, "feature-arm")
    legacy=[];groups={k:[] for k in ("T","A","L","C")}
    counts=state["counts"];den=state["total"]+len(counts)+1
    for p in primitives:
        b=np.asarray(p["legacy"],dtype=np.float64);t=np.asarray(p["T"],dtype=np.float64).copy()
        need(b.shape==(4,139) and t.shape==(4,11) and len(p["terms"])==4, "feature-primitives")
        freq=np.asarray([sum(math.log((counts.get(w,0)+1)/den) for w in lag)/max(1,len(lag))
                         for lag in p["terms"]],dtype=np.float64)
        t[:,2]=freq
        common=np.concatenate((b[:,:11],freq[:,None]),axis=1)
        parts=[common]
        if arm!="NUISANCE":parts.append(b[:,11:75])
        if arm=="CONTEXT":parts.append(b[:,75:])
        legacy.append(np.concatenate(parts,axis=1).reshape(-1))
        groups["T"].append(t.reshape(-1))
        for key,columns in (("A",72),("L",768),("C",768)):
            value=np.asarray(p[key],dtype=np.float64)
            need(value.shape==(4,columns) and np.isfinite(value).all(), "strong-primitive-"+key)
            groups[key].append(value.reshape(-1))
    keys={"NUISANCE":("T","A"),"LEXICAL":("T","A","L"),"CONTEXT":("T","A","L","C")}[arm]
    result={"legacy":np.ascontiguousarray(legacy,dtype="<f4"),
            "groups":{k:np.ascontiguousarray(groups[k],dtype="<f4") for k in keys}}
    need(np.isfinite(result["legacy"]).all() and all(np.isfinite(v).all() for v in result["groups"].values()),
         "finite-fit-transform")
    return result
