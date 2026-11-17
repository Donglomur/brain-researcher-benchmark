"""Unexecuted fixed evaluator reference recipes. Imports of sklearn/numpy are lazy.
These functions consume admitted FIT/validation cases; they are not issuers.
No fitting, prediction, numerical tuning or query evaluation occurred in BUILD.
"""
from .design import NUISANCE_CATEGORICAL,NUISANCE_CONTINUOUS,REFERENCE_GRID,POLICIES
from .lifecycle import require_native_producers

def allowed_inputs(policy,arm):
    if policy not in POLICIES or arm not in ('NUISANCE','JOINT'):raise ValueError('analysis/arm')
    return list(NUISANCE_CATEGORICAL)+list(NUISANCE_CONTINUOUS)+(['outcome'] if policy=='outcome_conditioned_sensitivity' else [])+(['phase'] if arm=='JOINT' else [])

def _hierarchy_keys(row,policy,arm):
    # Same FIT-weighted hierarchical baseline family as the inherited source.
    # Its transparent coarse fallback uses the permitted categorical subset;
    # continuous depth/running/count and area remain available to HGB/candidates.
    base=(row['cre_line'],row['image_set'],row['image'],row['change'])
    if policy=='outcome_conditioned_sensitivity':base+=(tuple(row['outcome']),)
    state=(row['running_bin'],row['pupil_bin'],row['history_bin'])
    phase=(row['phase'],) if arm=='JOINT' else ()
    return [base+state+phase,base+phase,base[:3]+phase,base[:1]+phase,()]

class HierarchicalMean:
    def __init__(self,fit,policy,arm,core):
        if not fit or any(r['split']!='fit' for r in fit):raise ValueError('FIT only')
        self.policy=policy;self.arm=arm;self.core=core;self.tables={};weights=core.weights(fit)
        for r in fit:
            for level,key in enumerate(_hierarchy_keys(r,policy,arm)):
                self.tables.setdefault((level,key),[]).append((r['target'],weights[r['id']]))
    def predict(self,rows):
        out={}
        for r in rows:
            for level,key in enumerate(_hierarchy_keys(r,self.policy,self.arm)):
                values=self.tables.get((level,key))
                if values:
                    scale=max(abs(v) for v,w in values);den=sum(w for v,w in values)
                    out[r['id']]=0.0 if not scale else scale*sum((v/scale)*(w/den) for v,w in values);break
        return out

class FitOnlyEncoder:
    """Vocabulary/medians fit exclusively to FIT. Query never creates columns.
    Categorical one-hot is fixed by FIT, with explicit UNKNOWN and MISSING bins;
    continuous values have FIT median fill plus a missingness indicator.
    """
    def __init__(self,fit,policy,arm):
        import numpy as np
        self.categorical=list(NUISANCE_CATEGORICAL)+(['phase'] if arm=='JOINT' else [])
        self.continuous=list(NUISANCE_CONTINUOUS)
        if policy=='outcome_conditioned_sensitivity':self.categorical+=['outcome']
        self.vocabulary={};self.medians={}
        for key in self.categorical:
            values={self.token(r.get(key)) for r in fit if r.get(key) is not None};self.vocabulary[key]=sorted(values)
        for key in self.continuous:
            values=[r[key] for r in fit if r.get(key) is not None and np.isfinite(r[key])]
            self.medians[key]=float(np.median(values)) if values else 0.0
    @staticmethod
    def token(value):
        import json
        return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
    def transform(self,rows):
        import numpy as np
        out=[]
        for row in rows:
            result=[]
            for key in self.categorical:
                vocab=self.vocabulary[key];value=row.get(key);tok=self.token(value) if value is not None else None
                result += [int(tok==v) for v in vocab]+[int(value is not None and tok not in vocab),int(value is None)]
            for key in self.continuous:
                value=row.get(key);missing=value is None or not np.isfinite(value)
                result += [self.medians[key] if missing else float(value),int(missing)]
            out.append(result)
        return np.asarray(out,dtype=float)

class HGBReference:
    def __init__(self,fit,policy,arm,parameters,core):
        from sklearn.ensemble import HistGradientBoostingRegressor
        self.encoder=FitOnlyEncoder(fit,policy,arm);self.model=HistGradientBoostingRegressor(**parameters)
        weights=core.weights(fit)
        self.model.fit(self.encoder.transform(fit),[r['target'] for r in fit],sample_weight=[weights[r['id']]*len(fit) for r in fit])
    def predict(self,rows):return dict(zip((r['id'] for r in rows),map(float,self.model.predict(self.encoder.transform(rows)))))

def _fit_and_freeze_references(fit,validation,policy,core):
    if not fit or not validation or any(r['split']!='fit' for r in fit) or any(r['split']!='validation' for r in validation):raise ValueError('separate FIT/validation roles')
    if {r['mouse'] for r in fit}&{r['mouse'] for r in validation}:raise ValueError('whole-mouse separation')
    # Fixed primary new-image denominator; all predictions are still published.
    f=fit;v=[r for r in validation if r['subset']=='new_image']
    sd=core.training_scale([r for r in fit if r['subset']=='new_image']);models={};selection={}
    for arm in ('NUISANCE','JOINT'):
        hierarchy=HierarchicalMean(f,policy,arm,core);hier_loss=core.macro_error(hierarchy.predict(v),v,sd)
        candidates=[]
        for index,parameters in enumerate(REFERENCE_GRID):
            model=HGBReference(f,policy,arm,parameters,core);loss=core.macro_error(model.predict(v),v,sd)
            if not core.finite(loss):raise ValueError('invalid validation loss')
            candidates.append((loss,index,model))
        loss,index,best=min(candidates,key=lambda item:(item[0],item[1]));models[arm]={'hierarchical_mean':hierarchy,'hist_gradient_boosting':best}
        if not core.finite(hier_loss):raise ValueError('invalid hierarchy validation loss')
        selection[arm]={'hierarchical_validation_loss':hier_loss,'hgb_grid_validation_losses':[x[0] for x in candidates],'hgb_grid_index':index,
            'validation_only_selected':'hierarchical_mean' if hier_loss<=loss else 'hist_gradient_boosting','fit_refit_on_validation':False}
    # Primary gain uses the independently fixed NUISANCE choice. Both references
    # and both arms are retained; query cannot select/reverse this decision.
    return models,{'policy':policy,'selection':selection,'primary_nuisance':selection['NUISANCE']['validation_only_selected'],
                   'training_target_sd':sd,'tuning_budget_per_arm':{'hgb_fits':len(REFERENCE_GRID),'hierarchy_fits':1},'empirical_competence':'unqualified_until_native_validation'}

def run_references(*args,**kwargs):require_native_producers()
