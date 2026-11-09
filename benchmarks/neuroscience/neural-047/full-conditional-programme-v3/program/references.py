"""Concrete unexecuted native reference implementations with complete inner-animal development."""
import math,warnings
from .common import need
from .development import validate,weights,inner_contexts,macro_loss,LOGISTIC_C,BOOST_GRID
from .legacy.features import summaries
def fit_predict(train,query,arm,family,config):
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.exceptions import ConvergenceWarning
    x=np.asarray([summaries(r["features"],arm) for r in train],dtype=np.float64)
    q=np.asarray([summaries(r["features"],arm) for r in query],dtype=np.float64)
    y=np.asarray([r["dorsal"] for r in train],dtype=np.int64)
    need(set(y.tolist())=={0,1},"Training class support")
    mean=x.mean(axis=0);scale=x.std(axis=0);scale[scale==0]=1
    x=(x-mean)/scale;q=(q-mean)/scale
    need(np.isfinite(x).all() and np.isfinite(q).all(),"Finite training-only scaling")
    w=np.asarray(weights([r["group"] for r in train],y.tolist()),dtype=np.float64)
    if family=="logistic":
        model=LogisticRegression(C=config["C"],solver="liblinear",max_iter=1000,random_state=47047)
    elif family=="boost":
        model=HistGradientBoostingClassifier(**config,early_stopping=False,random_state=47047)
    else:raise ValueError("Unknown prespecified reference family")
    with warnings.catch_warnings():
        warnings.simplefilter("error",ConvergenceWarning);model.fit(x,y,sample_weight=w)
    need(model.classes_.tolist()==[0,1],"Dorsal column is 1")
    p=model.predict_proba(q)[:,1].tolist()
    need(len(p)==len(query) and all(math.isfinite(z) and 0<=z<=1 for z in p),"Full finite reference")
    return p
def run(packet,reference,fit=fit_predict,observe=lambda event:None):
    validate(packet);need(reference in ("R0","R1","R2"),"Exact reference")
    family="boost" if reference=="R2" else "logistic"
    grid=[{"C":1.0}] if reference=="R0" else ([{"C":c} for c in LOGISTIC_C] if reference=="R1" else list(BOOST_GRID))
    history=[];started=0
    def invoke(train,query,config,stage):
        nonlocal started
        seq=started;started+=1
        observe({"schema":"neural047-fit-lifecycle-v1","sequence":seq,"event":"start","stage":stage,"family":family,"configuration":config,"training_events":len(train),"query_events":len(query)})
        probs=fit(train,query,packet["arm"],family,config)
        observe({"schema":"neural047-fit-lifecycle-v1","sequence":seq,"event":"end","stage":stage})
        return probs
    if reference=="R0":chosen=grid[0]
    else:
        contexts=inner_contexts(packet);losses=[]
        for cfg in grid:
            values=[]
            for c in contexts:
                probs=invoke(c["training"],c["validation"],cfg,"inner")
                value=macro_loss(c["validation"],probs);values.append(value)
                history.append({"configuration":cfg,"inner_animal":c["held_group"],"log_loss":value,"training_events":len(c["training"]),"validation_events":len(c["validation"])})
            losses.append(math.fsum(values)/len(values))
        best=min(range(len(grid)),key=lambda i:(losses[i],i));chosen=grid[best]
    probs=invoke(packet["training"],packet["query"],chosen,"final")
    output={"schema":"neural047-fold-predictions-v1","packet_id":packet["packet_id"],"outcome":{"fold_id":packet["fold_id"],"arm":packet["arm"],"status":"complete","predictions":[{"case_key":r["case_key"],"p_dorsal":p} for r,p in zip(packet["query"],probs)]}}
    report={"schema":"neural047-reference-development-v1","reference":reference,"family":family,"chosen":chosen,"grid":grid,"inner_history":history,"fits":len(history)+1,"selection":"macro inner-animal log loss; deterministic grid-order tie break","assessment_target_accesses":0,"backend_qualified":False}
    return output,report

