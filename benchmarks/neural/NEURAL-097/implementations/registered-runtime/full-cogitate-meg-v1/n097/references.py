"""Complete R0-R4 numerical source, intentionally unexecuted during build.

Scientific imports occur only inside separately authorized fit/inference calls.
The reference bank uses non-executable JSON numeric state. No candidate receives
reference outputs or fitted states.
"""
from .io import need, Refusal
from .contract import require_deployment

def weights(rows):
    import numpy as np
    groups={r["opaque_person_group"]for r in rows}
    classes={g:{r["yface"]for r in rows if r["opaque_person_group"]==g}for g in groups}
    counts={(g,y):sum(r["opaque_person_group"]==g and r["yface"]==y for r in rows)for g in groups for y in classes[g]}
    return np.asarray([len(rows)/(len(groups)*len(classes[r["opaque_person_group"]])*counts[r["opaque_person_group"],r["yface"]])for r in rows],dtype=float)

def config_grid(reference):
    if reference in ("R0","R1"):return [{}]
    if reference=="R2":return [{"C":x}for x in (.0001,.01,.1,1.,10.,100.)]
    if reference=="R3":return [{"lambda":x}for x in (.1,.5,1.)]
    if reference=="R4":return [{"max_leaf_nodes":n,"learning_rate":lr,"l2_regularization":reg}for n in (7,31)for lr in (.05,.1)for reg in (0.,1.)]
    raise Refusal("Unknown reference")

def _scalar(value):
    return value.item()if hasattr(value,"item")else value

def fit_one(reference,config,rows):
    require_deployment()
    import numpy as np
    need(rows and {r["yface"]for r in rows}=={0,1},"Both training classes")
    x=np.asarray([r["x"]for r in rows],dtype=np.float64);y=np.asarray([r["yface"]for r in rows],dtype=int)
    need(x.ndim==2 and np.isfinite(x).all(),"Finite complete training matrix")
    w=weights(rows)
    if reference=="R0":
        return {"kind":"constant","p_face":.5},None
    if reference in ("R1","R2","R3"):
        mean=x.mean(0);scale=x.std(0);scale[scale==0]=1.;z=(x-mean)/scale
        need(np.isfinite(z).all(),"Representable training-only moments")
    if reference in ("R1","R2"):
        from sklearn.linear_model import LogisticRegression
        from sklearn.exceptions import ConvergenceWarning
        import warnings
        cap=1000 if reference=="R1"else 5000
        model=LogisticRegression(C=1. if reference=="R1"else config["C"],penalty="l2",solver="liblinear",
             fit_intercept=True,intercept_scaling=1,tol=1e-4 if reference=="R1"else 1e-6,
             max_iter=cap,random_state=97097,class_weight=None)
        with warnings.catch_warnings():
            warnings.simplefilter("error",ConvergenceWarning);model.fit(z,y,sample_weight=w)
        need(list(model.classes_)==[0,1]and int(model.n_iter_.max())<cap,"Converged reference, explicit face column")
        state={"kind":"logistic","mean":mean.tolist(),"scale":scale.tolist(),
               "coef":model.coef_[0].tolist(),"intercept":float(model.intercept_[0])}
        return state,model
    if reference=="R3":
        means=[np.sum(z[y==c]*w[y==c,None],axis=0)/np.sum(w[y==c])for c in (0,1)]
        residual=z-np.asarray(means)[y]
        cov=(residual*w[:,None]).T@residual/w.sum()
        lam=config["lambda"];cov=(1-lam)*cov+lam*np.diag(np.diag(cov))+1e-8*np.eye(x.shape[1])
        need(np.isfinite(cov).all()and np.linalg.cond(cov)<=1e12,"Finite conditioned shrinkage covariance")
        vector=np.linalg.solve(cov,means[1]-means[0]);bias=-.5*np.dot(means[1]+means[0],vector)
        need(np.isfinite(vector).all()and np.isfinite(bias),"Finite independent discriminant")
        return {"kind":"linear_discriminant","mean":mean.tolist(),"scale":scale.tolist(),"coef":vector.tolist(),"intercept":float(bias)},None
    from sklearn.ensemble import HistGradientBoostingClassifier
    model=HistGradientBoostingClassifier(loss="log_loss",max_iter=200,early_stopping=False,
       max_depth=None,min_samples_leaf=20,max_bins=255,max_leaf_nodes=config["max_leaf_nodes"],
       learning_rate=config["learning_rate"],l2_regularization=config["l2_regularization"],random_state=97097)
    model.fit(x,y,sample_weight=w)
    need(list(model.classes_)==[0,1]and model.n_iter_==200,"Exact prescribed boosting procedure")
    # This version-dependent state export must be checked against qualified
    # sklearn1.6.1 native output. A missing layout fails, never pickles a model.
    trees=[]
    for round_ in model._predictors:
        need(len(round_)==1,"Binary one-tree-per-round reference")
        nodes=round_[0].nodes
        required={"value","feature_idx","num_threshold","missing_go_to_left","left","right","is_leaf","is_categorical"}
        need(required<=set(nodes.dtype.names),"Qualified numeric tree layout")
        tree=[{name:_scalar(row[name])for name in sorted(required)}for row in nodes]
        need(all(not row["is_categorical"]for row in tree),"Numerical-only feature projection")
        trees.append(tree)
    state={"kind":"hist_gradient_boosting","baseline":float(model._baseline_prediction[0,0]),"trees":trees}
    need(len(trees)==200,"Complete boosting state")
    return state,model

def bank_predict(state,x):
    """Independent non-executable state evaluation, not a trained-model import."""
    import math
    need(all(type(v)in(int,float)and math.isfinite(v)for v in x),"Finite single query")
    def sigmoid(z):
        if z>=0:return 1./(1.+math.exp(-z))
        e=math.exp(z);return e/(1.+e)
    kind=state["kind"]
    if kind=="constant":return state["p_face"]
    if kind in ("logistic","linear_discriminant"):
        need(len(x)==len(state["mean"])==len(state["scale"])==len(state["coef"]),"Exact fitted feature dimension")
        z=math.fsum(((v-m)/s)*w for v,m,s,w in zip(x,state["mean"],state["scale"],state["coef"]))+state["intercept"]
        need(math.isfinite(z),"Representable prediction");return sigmoid(z)
    need(kind=="hist_gradient_boosting","Declared inference state kind")
    value=state["baseline"]
    for tree in state["trees"]:
        node=0;seen=set()
        while not tree[node]["is_leaf"]:
            need(node not in seen and 0<=node<len(tree),"Acyclic bounded inference tree");seen.add(node)
            row=tree[node];feature=row["feature_idx"]
            need(type(feature)is int and 0<=feature<len(x),"Tree feature index")
            node=row["left"]if x[feature]<=row["num_threshold"]else row["right"]
            need(type(node)is int and 0<=node<len(tree),"Tree child index")
        value+=tree[node]["value"]
    need(math.isfinite(value),"Finite native tree bank value");return sigmoid(value)

def inner_criterion(rows,predictions):
    import math
    need(set(predictions)==set(range(len(rows))),"Every inner row predicted exactly once across eight folds")
    values=[];losses=[]
    for person in sorted({r["opaque_person_group"]for r in rows}):
        group=[i for i,r in enumerate(rows)if r["opaque_person_group"]==person and r["validation_stratum"][0]=="Irrelevant"]
        recalls=[];closs=[]
        for y in (0,1):
            ids=[i for i in group if rows[i]["yface"]==y];need(ids,"Both classes per held training person")
            recalls.append(sum((predictions[i]>=.5)==bool(y)for i in ids)/len(ids))
            closs.append(math.fsum(-math.log(max(1e-15,predictions[i]if y else 1-predictions[i]))for i in ids)/len(ids))
        values.append(sum(recalls)/2);losses.append(sum(closs)/2)
    return sum(values)/len(values),sum(losses)/len(losses)

def complexity(reference,config):
    if reference=="R2":return (config["C"],)
    if reference=="R3":return (-config["lambda"],)
    if reference=="R4":return (config["max_leaf_nodes"],-config["l2_regularization"],config["learning_rate"])
    return ()

def fit_reference(reference,rows,inner,journal=None):
    require_deployment()
    attempts=[];valid=[]
    def retain(name,record):
        if journal is not None:
            from pathlib import Path
            from .io import write_json
            write_json(Path(journal)/name,record,4_000_000)
    if reference in ("R0","R1"):
        retain("fixed-start.json",{"reference":reference,"config":{},"status":"started"})
        try:
            state,native=fit_one(reference,{},rows)
        except Exception as exc:
            retain("fixed-failure.json",{"status":"failed","reason":type(exc).__name__+": "+str(exc)})
            raise
        retain("fixed-complete.json",{"reference":reference,"status":"complete"})
        return state,{"reference":reference,"config":{},"attempts":[],"final_fit_complete":True},native
    need(len(inner)==8,"All eight crossed grouped inner folds")
    for config in config_grid(reference):
        predictions={};record={"config":config,"folds":[],"status":"started"}
        try:
            for fold in inner:
                tr,va=fold["train"],fold["validation"]
                state,_=fit_one(reference,config,[rows[k]for k in tr])
                for k in va:
                    need(k not in predictions,"Unique pooled inner validation row")
                    predictions[k]=bank_predict(state,rows[k]["x"])
                record["folds"].append({"person_group":fold["person_group"],"image_group":fold["image_group"],"status":"complete"})
            ba,ll=inner_criterion(rows,predictions)
            record.update(status="complete",balanced_accuracy=ba,balanced_logloss=ll)
            valid.append(((-ba,ll,*complexity(reference,config)),config))
        except Exception as exc:
            record.update(status="invalid_configuration",reason=type(exc).__name__+": "+str(exc))
        attempts.append(record)
        retain(f"configuration-{len(attempts):03d}.json",record)
    need(valid,"No valid complete training-only reference configuration")
    selected=min(valid,key=lambda x:x[0])[1]
    retain("selected-final-start.json",{"reference":reference,"config":selected,"status":"started"})
    try:
        state,native=fit_one(reference,selected,rows)
    except Exception as exc:
        retain("selected-final-failure.json",{"reference":reference,"config":selected,"status":"failed","reason":type(exc).__name__+": "+str(exc)})
        raise
    retain("selected-final-complete.json",{"reference":reference,"config":selected,"status":"complete"})
    return state,{"reference":reference,"config":selected,"attempts":attempts,"final_fit_complete":True},native

def complete_reference_bank(reference,rows,inner,queries,journal=None):
    require_deployment()
    import math
    state,fit,native=fit_reference(reference,rows,inner,journal)
    out=[]
    for q in queries:
        value=bank_predict(state,q["x_numeric_vector"])
        need(math.isfinite(value)and 0<=value<=1,"Complete finite face probability")
        out.append({"opaque_query_nonce":q["opaque_query_nonce"],"p_face":value})
    # Original native-versus-independent bank observations are required later.
    # This function records raw values; tolerance/stack qualification is not
    # manufactured from a source-only build or a shared-solver comparison.
    native_values=None
    if native is not None:
        import numpy as np
        x=np.asarray([q["x_numeric_vector"]for q in queries],dtype=np.float64)
        if reference in ("R1","R2"):x=(x-np.asarray(state["mean"]))/np.asarray(state["scale"])
        native_values=native.predict_proba(x)[:,1].tolist()
    return {"schema":"n097-reference-bank-v1","reference":reference,"seed":97097,"fit":fit,
            "numeric_state":state,"predictions":out,"native_prediction_values":native_values,
            "independent_numerical_qualification":False}
