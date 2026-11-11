"""Independent prespecified scientific reference producers; imports are lazy.
No candidate-supplied references, callbacks, query labels or outer-score selection.
"""
import copy,math
from .io import need,Refusal
from .constants import *
from .features import Encoder,public_rows
from .splits import weights,inner_groups
from .panel import text_id

LAMBDAS=(.001,.01,.1,1.,10.,100.)
def linear_fit(x,y,w,lam):
    import numpy as np
    from scipy.optimize import minimize
    from scipy.special import expit
    x=np.asarray(x,float);y=np.asarray(y,float);w=np.asarray(w,float);need(x.ndim==2 and len(x)==len(y)==len(w) and set(y)=={0.,1.},"reference_fit_shape")
    w=w/w.sum()
    def objective(v):
        z=x@v[:-1]+v[-1];p=expit(z);value=np.sum(w*(np.logaddexp(0,z)-y*z))+lam*.5*np.dot(v[:-1],v[:-1]);g=np.r_[x.T@(w*(p-y))+lam*v[:-1],np.sum(w*(p-y))];return value,g
    fitted=minimize(objective,np.zeros(x.shape[1]+1),jac=True,method="L-BFGS-B",options={"maxiter":10000,"gtol":1e-8,"ftol":1e-15,"maxls":50});value,g=objective(fitted.x)
    need(np.isfinite(value) and np.isfinite(fitted.x).all() and np.max(np.abs(g))<=1e-6 and fitted.nit<=10000,"reference_nonconvergence",{"message":str(fitted.message),"gradient_inf":float(np.max(np.abs(g)))})
    return {"coefficients":fitted.x[:-1].tolist(),"intercept":float(fitted.x[-1]),"lambda":lam,"objective":float(value),"gradient_inf":float(np.max(np.abs(g))),"iterations":int(fitted.nit)}
def linear_predict(state,x):
    import numpy as np
    from scipy.special import expit
    return expit(np.asarray(x)@np.asarray(state["coefficients"])+state["intercept"])
def validation_loss(raw,probs,task,J):
    from .metrics import loss
    # Inner validation is restored globally before the task's weighting, not equal fold averaging.
    keep=[i for i,z in enumerate(raw) if task!="NEURAL-085" or text_id(z["sentence"]["text"])in J];need(keep,"inner_primary_support")
    chosen=[raw[i] for i in keep];w=weights(chosen,task);return sum(a*loss(int(z["sentence"]["condition"]=="TSR"),float(probs[i])) for a,z,i in zip(w,chosen,keep))/sum(w)
def view_for(train,query,identity):
    return public_rows({"train":train,"query":query,"train_ids":[str(i) for i in range(len(train))],"query_ids":[str(i) for i in range(len(query))],"weights":weights(train,identity["task"])},identity)
class LinearReference:
    def fit(self,training,identity,J):
        import numpy as np
        self.identity=copy.deepcopy(identity);self.training=training;grid=[]
        for lam in LAMBDAS:
            predictions={}
            for a,b,tr,va in inner_groups(training):
                need(tr and va,"inner_complete_support",[a,b]);train=[training[i] for i in tr];validation=[training[i] for i in va];view=view_for(train,validation,identity);enc=Encoder(identity["representation"]);tw=weights(train,identity["task"]);x=enc.fit_transform(view["train"],tw);state=linear_fit(x,[r["label"] for r in view["train"]],tw,lam);y=linear_predict(state,enc.transform(view["query"]))
                for i,p in zip(va,y):need(i not in predictions,"duplicate_inner_prediction");predictions[i]=float(p)
            need(set(predictions)==set(range(len(training))),"complete_inner_validation");grid.append((validation_loss(training,[predictions[i] for i in range(len(training))],identity["task"],J),lam))
        best=min(x for x,lam in grid);lam=max(lam for x,lam in grid if x<=best+1e-12);view=view_for(training,[],identity);self.encoder=Encoder(identity["representation"]);w=weights(training,identity["task"]);x=self.encoder.fit_transform(view["train"],w);self.state=linear_fit(x,[r["label"] for r in view["train"]],w,lam);self.selection={"grid":[{"loss":x,"lambda":lam} for x,lam in grid],"chosen":lam,"outer_query_used":False};return self
    def predict(self,query):return self.predict_public(view_for(self.training,query,self.identity)["query"])
    def predict_public(self,query):return linear_predict(self.state,self.encoder.transform(query)).tolist()
class NonlinearReference:
    def fit(self,training,identity,J):
        from sklearn.ensemble import HistGradientBoostingClassifier
        need(identity["representation"] in ("released_summary","band_spatial"),"nonlinear_representation");self.training=training;self.identity=copy.deepcopy(identity);view=view_for(training,[],identity);w=weights(training,identity["task"]);self.encoder=Encoder(identity["representation"],"nonlinear");x=self.encoder.fit_transform(view["train"],w)
        self.model=HistGradientBoostingClassifier(max_iter=200,learning_rate=.05,max_leaf_nodes=15,max_depth=None,min_samples_leaf=20,l2_regularization=1,max_bins=255,early_stopping=False,random_state=0);self.model.fit(x,[r["label"] for r in view["train"]],sample_weight=w);need(list(self.model.classes_)==[0,1],"nonlinear_classes");return self
    def predict(self,query):return self.predict_public(view_for(self.training,query,self.identity)["query"])
    def predict_public(self,query):return self.model.predict_proba(self.encoder.transform(query))[:,1].tolist()
REFERENCES={"R_LINEAR_NESTED_V1":LinearReference,"R_NONLINEAR_V1":NonlinearReference}
def required(representation):return ("R_LINEAR_NESTED_V1","R_NONLINEAR_V1") if representation in ("released_summary","band_spatial") else ("R_LINEAR_NESTED_V1","R_TEMPORAL_CONV_V1")
def create(name):
    if name=="R_TEMPORAL_CONV_V1":
        from .temporal import TemporalReference
        return TemporalReference()
    if name in ("R_MASK_ONLY","R_DURATION_COUNT","R_LABEL_SHUFFLE","R_OCULAR","R_PHASE_INDEPENDENT","R_PHASE_COMMON","R_EOG_RESIDUAL"):return LinearReference()
    need(name in REFERENCES,"reference_family");return REFERENCES[name]()
