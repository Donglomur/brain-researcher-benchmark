"""Concrete prospective grouped37-feature references, distinct from unit LOO.

No fit runs on import. Complete pre-exposure grids, fit seeds, biological alias
closure and independently eligible QC inputs are required; none are invented.
The tuning objective is recipe-selected and is not a new primary benchmark.
"""
from dataclasses import dataclass
from .cohort import CLASSES,SupportError
from .grouped_protocol import nested_jobs,final_job,training_labels

FAMILIES=('logistic_regression','random_forest','gaussian_process')
PARAMETERS={
 'logistic_regression':{'penalty','C','solver','tol','max_iter','fit_intercept','class_weight'},
 'random_forest':{'n_estimators','criterion','max_depth','min_samples_split','min_samples_leaf','max_features','bootstrap','class_weight'},
 'gaussian_process':{'length_scale','length_scale_bounds','optimizer','max_iter_predict','n_restarts_optimizer','multi_class'},
}

@dataclass(frozen=True)
class ReferenceRecipe:
    grids: dict
    seeds: dict
    oversampling_strategy: str
    tuning_objective: str
    provenance: str

    def validate(self,plan):
        if not self.provenance or self.tuning_objective not in ('equal_group_brier','equal_group_log_loss'):
            raise SupportError('explicit prospective TRAIN-only tuning objective/provenance required')
        if self.oversampling_strategy not in ('all','minority','not minority','not majority','auto'):
            raise SupportError('explicit RandomOverSampler strategy required')
        jobs=nested_jobs(plan,self.grids)
        for family,grid in self.grids.items():
            for params in grid:
                if set(params)!=PARAMETERS[family]:raise SupportError('complete explicit model constructor parameters required')
        expected={j.identity for j in jobs}
        expected.update(final_job(plan,f,o,0).identity for f in FAMILIES for o in plan.outer_folds())
        if set(self.seeds)!=expected or any(type(s) is not int or not 0<=s<2**32 for s in self.seeds.values()):
            raise SupportError('complete precommitted per-fit seed schedule required')
        return jobs

@dataclass(frozen=True)
class FittedGroupModel:
    job: object
    scaler: object
    oversampler: object
    model: object
    probabilities: object
    resampled_units: tuple

@dataclass(frozen=True)
class GroupedResult:
    units: tuple
    probabilities: dict
    fitted: tuple
    tuning: tuple
    selections: tuple
    plan: object
    recipe: ReferenceRecipe

def fold_training_targets(plan,outer,targets):
    """The only target mapping accepted by a fold excludes every query group."""
    job=final_job(plan,FAMILIES[0],outer,0)
    training_labels(job.training_units,targets)
    return {k:targets[k] for k in job.training_units}

def _model(family,params,seed):
    # Every method is a concrete standard-library API call, not a callback.
    if family=='logistic_regression':
        from sklearn.linear_model import LogisticRegression
        return LogisticRegression(**params,random_state=seed)
    if family=='random_forest':
        from sklearn.ensemble import RandomForestClassifier
        return RandomForestClassifier(**params,random_state=seed,n_jobs=1)
    if family=='gaussian_process':
        from sklearn.gaussian_process import GaussianProcessClassifier
        from sklearn.gaussian_process.kernels import RBF
        options=dict(params)
        kernel=RBF(length_scale=options.pop('length_scale'),length_scale_bounds=options.pop('length_scale_bounds'))
        return GaussianProcessClassifier(kernel=kernel,**options,random_state=seed,n_jobs=1)
    raise SupportError('unsupported prospective baseline')

def fit_job(table,job,targets,params,recipe):
    """Scale/oversample/fit only TRAIN, then transform/predict evaluation rows."""
    import numpy as np
    from sklearn.preprocessing import StandardScaler
    from imblearn.over_sampling import RandomOverSampler
    labels=training_labels(job.training_units,targets)
    if set(labels)!=set(CLASSES):raise SupportError('five-class TRAIN support absent; whole fold unavailable')
    rows={r.unit:r.values for r in table.rows}
    x=np.stack([rows[k] for k in job.training_units])
    query=np.stack([rows[k] for k in job.evaluation_units])
    y=np.asarray([CLASSES.index(label) for label in labels],dtype=int)
    scaler=StandardScaler();train=scaler.fit_transform(x)
    sampler=RandomOverSampler(sampling_strategy=recipe.oversampling_strategy,random_state=recipe.seeds[job.identity])
    resampled,ry=sampler.fit_resample(train,y)
    model=_model(job.family,params,recipe.seeds[job.identity]);model.fit(resampled,ry)
    if tuple(model.classes_)!=tuple(range(5)):raise SupportError('classifier changed complete class axis')
    prediction=model.predict_proba(scaler.transform(query))
    if prediction.shape!=(len(job.evaluation_units),5) or not np.isfinite(prediction).all():
        raise SupportError('incomplete or undefined prediction; no silent query removal')
    return FittedGroupModel(job,scaler,sampler,model,prediction,
                           tuple(job.training_units[int(i)] for i in sampler.sample_indices_))

def _group_losses(probabilities,units,targets,plan,objective):
    import numpy as np
    training_labels(units,targets)
    truth=np.asarray([CLASSES.index(targets[k]) for k in units])
    if objective=='equal_group_brier':loss=((probabilities-np.eye(5)[truth])**2).sum(axis=1)
    else:
        with np.errstate(divide='ignore'):loss=-np.log(probabilities[np.arange(len(units)),truth])
    if np.isnan(loss).any():raise SupportError('undefined tuning loss; no favorable omission')
    groups=tuple(dict.fromkeys(plan.group_by_unit[k] for k in units))
    return {g:float(loss[[plan.group_by_unit[k]==g for k in units]].mean()) for g in groups}

def fit_grouped(table,plan,recipe,training_targets_by_outer):
    """Full grids in each outer TRAIN; no query label enters model selection.

    This trusted evaluator orchestration retains all fold recipes/objects. It
    is not an actor isolation mechanism or an issuer of hidden-test authority.
    """
    plan.validate();table.require_complete(plan.unit_order);jobs=recipe.validate(plan)
    if set(training_targets_by_outer)!=set(plan.outer_folds()):raise SupportError('all outer TRAIN target maps required')
    scoped={o:fold_training_targets(plan,o,training_targets_by_outer[o]) for o in plan.outer_folds()}
    import numpy as np
    probabilities={f:np.empty((len(plan.unit_order),5)) for f in FAMILIES}
    fitted=[];tuning=[];selections=[]
    for family in FAMILIES:
        for outer in plan.outer_folds():
            scores=[]
            for candidate,params in enumerate(recipe.grids[family]):
                group_losses={}
                for job in (j for j in jobs if (j.family,j.outer_fold,j.candidate)==(family,outer,candidate)):
                    target={k:scoped[outer][k] for k in job.training_units}
                    fit=fit_job(table,job,target,params,recipe);fitted.append(fit)
                    validation={k:scoped[outer][k] for k in job.evaluation_units}
                    loss=_group_losses(fit.probabilities,job.evaluation_units,validation,plan,recipe.tuning_objective)
                    if set(group_losses)&set(loss):raise SupportError('validation group predicted twice')
                    group_losses.update(loss)
                    tuning.append({'job':job,'group_losses':loss})
                if set(group_losses)!=set(plan.inner_by_outer[outer]):raise SupportError('incomplete inner validation denominator')
                scores.append(float(np.mean(tuple(group_losses.values()))))
            if not any(np.isfinite(v) for v in scores):raise SupportError('all candidates undefined/infinite; no fabricated selection')
            selected=min(range(len(scores)),key=lambda i:(scores[i],i))
            job=final_job(plan,family,outer,selected)
            fit=fit_job(table,job,scoped[outer],recipe.grids[family][selected],recipe);fitted.append(fit)
            for i,key in enumerate(job.evaluation_units):probabilities[family][plan.unit_order.index(key)]=fit.probabilities[i]
            selections.append({'family':family,'outer':outer,'candidate':selected,'scores':scores,
                               'tie_rule':'first precommitted grid entry','objective':recipe.tuning_objective})
    return GroupedResult(plan.unit_order,probabilities,tuple(fitted),tuple(tuning),tuple(selections),plan,recipe)

def captured_group_scores(prediction,expected_units,protected_targets,plan):
    """Descriptive full-unit and equal-biological-group scores; no primary win."""
    from .evaluation import probability_products
    if tuple(expected_units)!=plan.unit_order:raise SupportError('scoring denominator differs from full group plan')
    products=probability_products(prediction,expected_units,protected_targets,(),threshold_rule='paper_survival_gt')
    import numpy as np
    groups=tuple(dict.fromkeys(plan.group_by_unit.values()))
    result={}
    for name in ('brier','log_loss'):
        loss=products['per_unit_'+name]
        per_group={g:float(np.mean([loss[i] for i,k in enumerate(expected_units) if plan.group_by_unit[k]==g])) for g in groups}
        result[name]={'per_group':per_group,'equal_group_mean':float(np.mean(tuple(per_group.values())))}
    return {'full_unit_products':products,'group_products':result,'groups':groups,
            'status':'prospective descriptive comparison; no selected primary or historical parity'}
