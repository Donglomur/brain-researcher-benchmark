"""Construct response-specific views without carrying private real-Y identities into ZERO."""
from .errors import need
from .identity import identity
from .policy import evidence
from . import features, codec
from .support import hierarchy_weights

def make(case,primitives,train_y,context,store,journal):
    import numpy as np
    arm=context["arm"];response=context["response"]
    train=case["train"];query=case["query"]
    need(len(train)==len(train_y),"view-training-rows")
    tp=[primitives[r["row"]] for r in train];qp=[primitives[r["row"]] for r in query]
    freq,fit_receipt=journal.invoke("S07","FeatureFit",{"fit_support":identity(train)},{"frequency":True},
                                    features.fit,train,tp)
    tx,train_receipt=journal.invoke("S07","FeatureTransform/train",{"fit":fit_receipt},{"features":True},
                                   features.transform,freq,tp,arm)
    qx,query_receipt=journal.invoke("S07","FeatureTransform/query",{"fit":fit_receipt,
                                    "query_support":identity(query)},{"features":True},
                                    features.transform,freq,qp,arm)
    y=np.asarray(train_y,dtype=np.float64)
    need(y.shape==(len(train),400) and np.isfinite(y).all(),"view-training-y")
    if response=="ZERO_RESPONSE":
        y=np.zeros((len(train),400),dtype="<f4")
    else:
        need(response=="REAL_RESPONSE","response-condition")
    fields={"train_x":tx,"train_y":y,"weights":hierarchy_weights(train),
            "train_rows":train,"query_x":qx,"query_rows":query,
            "frequency_state":freq,"feature_receipts":[fit_receipt,train_receipt,query_receipt],
            "response":response,"arm":arm,
            "context":context["id"],**evidence(arm=="CONTEXT")}
    # No private mean, original response digest or real response descriptor appears here.
    return codec.pack(store,"view-"+identity(context["id"]),fields)

def author_view(full_view,mode):
    need(mode in ("F","I"),"candidate-mode")
    allowed={k:v for k,v in full_view.items() if k not in ("query_x","query_rows")}
    if mode=="I":
        allowed["query_x"]=full_view["query_x"]
        allowed["query_rows"]=full_view["query_rows"]
    return allowed

def fit_view(full_view):
    return {k:v for k,v in full_view.items() if k not in ("query_x","query_rows")}

def infer_view(full_view,state):
    return {"context":full_view["context"],"arm":full_view["arm"],"response":full_view["response"],
            "query_x":full_view["query_x"],"query_rows":full_view["query_rows"],
            "state":state,**evidence(full_view["arm"]=="CONTEXT")}
