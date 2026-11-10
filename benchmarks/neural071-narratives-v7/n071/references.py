"""Actual nested reference FIT/state/INFER; scientific leaves are separable for controls."""
from .errors import need
from .policy import REFERENCES
from .identity import identity
from .support import inner_folds, hierarchy_weights
from . import features, scientific

def selected_groups(reference):
    if reference=="Rtemp/T":return ("T",)
    if reference=="Racoustic/A":return ("A",)
    arm=reference.split("/")[-1]
    return {"NUISANCE":("T","A"),"LEXICAL":("T","A","L"),"CONTEXT":("T","A","L","C")}[arm]

def arm_for(reference):
    need(reference in REFERENCES,"canonical-reference")
    return "NUISANCE" if reference in ("Rmean/ALL","Rtemp/T","Racoustic/A") else reference.split("/")[-1]

def choose(errors):
    return [min(range(len(errors)),key=lambda ci:(errors[ci][column],ci)) for column in range(400)]

def no_inner(reason):
    return {"disposition":reason}

def selection_summary(case_id,state,rows):
    """Closed scientific metadata from an actual completed FIT, never a state-body read by review."""
    reference=state["reference"];families=sorted({r["family"] for r in rows})
    fit_rows=identity([r["row"] for r in rows])
    need(reference in REFERENCES and families and state["fit_rows"]==fit_rows,"selection-fit-support")
    if reference=="Rmean/ALL" or reference.startswith("R0/"):
        need(state["inner"]=="not_applicable","selection-no-inner-join")
        branch="not_applicable";folds=[];configs=0;chosen={}
    else:
        selection=state["selection"];branch=selection["branch"]
        folds=[list(f) for f in selection["folds"]];configs=selection["config_count"]
        expected=[list(f) for f in inner_folds(case_id,[r["family"] for r in rows])]
        need(folds==expected and branch==("complete_inner" if expected else "one_training_family_default"),
             "actual-selection-branch-family-join")
        need(type(configs)is int and configs>0 and len(state["chosen"])==400 and
             all(type(v)is int and 0<=v<configs for v in state["chosen"]),"selection-config-coverage")
        chosen={str(k):state["chosen"].count(k) for k in sorted(set(state["chosen"]))}
        need({m["config"] for m in state["models"]}==set(state["chosen"]),"selection-actual-final-fits")
    return {"schema":"n071-fit-selection-summary-v1","reference":reference,"fit_rows":fit_rows,
            "status":"complete","branch":branch,"training_family_count":len(families),
            "training_families":families,"inner_fold_count":len(folds),"inner_folds":folds,
            "configuration_count":configs,"selected_configuration_counts":chosen,
            "validated_inner_selection":branch=="complete_inner",
            "default_is_validated_generalization":False}

class ReferenceEngine:
    def __init__(self, calls, leaves=scientific, feature_module=features):
        self.calls=calls
        self.leaves=leaves
        self.features=feature_module

    def fit(self, case_id, reference, rows, primitives, y):
        need(len(rows)==len(primitives)==len(y),"reference-fit-length")
        family=[r["family"] for r in rows]
        arm=arm_for(reference)
        receipts=[]
        def operation(label, fn, *args):
            value,receipt=self.calls(label,fn,*args)
            receipts.append(receipt)
            return value
        weights=hierarchy_weights(rows)
        fs=operation("feature-fit/outer",self.features.fit,rows,primitives)
        full=operation("feature-transform/outer",self.features.transform,fs,primitives,arm)
        if reference=="Rmean/ALL":
            operation("reference-inner-not-applicable",no_inner,"Rmean has no inner search")
            fitted=operation("reference-fit/mean",self.leaves.fit_mean,y,weights)
            return {"reference":reference,"fit_rows":identity([r["row"] for r in rows]),
                    "frequency":fs,"state":fitted,"receipts":receipts,"inner":"not_applicable"}
        if reference.startswith("R0/"):
            operation("reference-inner-not-applicable",no_inner,"R0 has no inner search")
            fitted=operation("reference-fit/r0",self.leaves.fit_r0,full["legacy"],y,weights)
            return {"reference":reference,"fit_rows":identity([r["row"] for r in rows]),
                    "frequency":fs,"state":fitted,"receipts":receipts,"inner":"not_applicable"}
        keys=selected_groups(reference)
        configs=self.leaves.config_grid(len(keys))
        folds=operation("reference-inner-plan",inner_folds,case_id,family)
        if folds:
            # Union predictions are indexed in original outer-fit row order.
            oof=[[None]*len(rows) for _ in configs]
            fold_states=[]
            for fi,held in enumerate(folds):
                ti=[i for i,r in enumerate(rows) if r["family"] not in held]
                vi=[i for i,r in enumerate(rows) if r["family"] in held]
                need(ti and vi,"inner-nonempty")
                tr=[rows[i] for i in ti];tp=[primitives[i] for i in ti];vp=[primitives[i] for i in vi]
                frequency=operation(f"feature-fit/inner/{fi}",self.features.fit,tr,tp)
                tx=operation(f"feature-transform/inner-train/{fi}",self.features.transform,frequency,tp,arm)
                vx=operation(f"feature-transform/inner-validation/{fi}",self.features.transform,frequency,vp,arm)
                for ci,config in enumerate(configs):
                    model=operation(f"reference-fit/inner/{fi}/{ci}",self.leaves.fit_kernel,
                                    [tx["groups"][k] for k in keys],[y[i] for i in ti],
                                    hierarchy_weights(tr),config)
                    pred=operation(f"reference-infer/inner/{fi}/{ci}",self.leaves.infer,
                                   model,[vx["groups"][k] for k in keys])
                    need(len(pred)==len(vi),"complete-inner-prediction")
                    for i,value in zip(vi,pred):
                        need(oof[ci][i] is None,"duplicate-oof-row")
                        oof[ci][i]=value
                    fold_states.append({"fold":fi,"config":ci,"frequency":frequency,
                                        "fit_rows":identity([rows[i]["row"] for i in ti]),
                                        "validation_rows":identity([rows[i]["row"] for i in vi]),
                                        "state":model,"prediction":pred})
            need(all(all(v is not None for v in pred) for pred in oof),"complete-oof-union")
            errors=[operation(f"reference-oof/{ci}",self.leaves.weighted_errors,pred,y,weights)
                    for ci,pred in enumerate(oof)]
            chosen=operation("reference-select",choose,errors)
            selection={"branch":"complete_inner","folds":folds,"errors":errors,
                       "inner_states":fold_states,"config_count":len(configs)}
        else:
            operation("reference-one-family-default",no_inner,"membership-only uniform gamma and alpha1")
            chosen=[2]*400 # uniform gamma, alpha=1; index2 in the frozen gamma-major grid.
            selection={"branch":"one_training_family_default","folds":[],"errors":[],
                       "inner_states":[],"config_count":len(configs)}
        models=[]
        for ci in sorted(set(chosen)):
            columns=[i for i,c in enumerate(chosen) if c==ci]
            target=[[row[i] for i in columns] for row in y]
            fitted=operation(f"reference-fit/outer/{ci}",self.leaves.fit_kernel,
                             [full["groups"][k] for k in keys],target,weights,configs[ci])
            models.append({"config":ci,"columns":columns,"state":fitted})
        return {"reference":reference,"fit_rows":identity([r["row"] for r in rows]),
                "frequency":fs,"models":models,"chosen":chosen,"selection":selection,"receipts":receipts}

    def infer(self, state, query_primitives):
        reference=state["reference"]
        x,transform_receipt=self.calls("feature-transform/query",self.features.transform,
                                      state["frequency"],query_primitives,arm_for(reference))
        if reference=="Rmean/ALL":
            result,receipt=self.calls("reference-infer/mean",self.leaves.infer,state["state"],query_primitives)
        elif reference.startswith("R0/"):
            result,receipt=self.calls("reference-infer/r0",self.leaves.infer,state["state"],x["legacy"])
        else:
            keys=selected_groups(reference);parts=[]
            for model in state["models"]:
                values,r=self.calls("reference-infer/config/"+str(model["config"]),self.leaves.infer,
                                    model["state"],[x["groups"][k] for k in keys])
                parts.append((model["columns"],values,r))
            result=[[None]*400 for _ in query_primitives]
            for columns,values,_ in parts:
                need(len(values)==len(result),"reference-infer-rows")
                for row,value in zip(result,values):
                    for column,v in zip(columns,value):
                        need(row[column] is None,"reference-column-once")
                        row[column]=v
            need(all(all(v is not None for v in row) for row in result),"reference-all400")
            receipt=[p[2] for p in parts]
        return result,{"transform":transform_receipt,"infer":receipt}
