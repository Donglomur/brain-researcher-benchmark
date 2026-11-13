"""Genuine R0/R1/R2/R6/R7/R8 fit, selection, refit and frozen-state inference.

All numerical functions are source only in this build. Exact donor mathematics
live in the adjacent extracted modules; orchestration adds complete provenance.
"""
from .common import require, pooled_ll


def context_train(reference_id, training, fit, validation, record):
    import numpy as np
    from . import _context as c
    if "train_count_totals" in training:
        mu=(np.asarray(training["train_count_totals"],dtype=np.float64)+.5)/(training["train_bin_opportunities"]+1)
        require(np.isfinite(mu).all() and (mu>0).all(),"positive rate-only training constant")
        record.event("rate_only_statistics_complete", opportunities=training["train_bin_opportunities"])
        return {"constant":mu,"input_projection":"rate_only"},None
    y,conditions=training["train_counts_heldout"],training["train_condition_ids"]
    record.event("context_statistics_started",trials=len(y))
    if reference_id=="R0":
        mu=(y.sum(axis=(0,1),dtype=np.float64)+.5)/(len(y)*140+1)
        require(np.isfinite(mu).all() and (mu>0).all(),"positive training constant")
        payload={"constant":mu,"input_projection":"full_or_context"};certificate=None
    elif reference_id=="R1":
        payload=c.profiles_for_hypothesis(c.fit_statistics(y,conditions),c.ordered_hypotheses()[0]);certificate=None
    else:
        certificate=c.select_model(y,conditions,fit,validation,
                     progress=lambda name,facts: record.event(name,**facts))
        record.event("full_training_refit_started",selected=certificate["selected_hypothesis_id"],trials=1721)
        payload=c.refit_selected(y,conditions,certificate["selected_hypothesis_id"])
        certificate={"support":"D0","fit_indices":fit,"validation_indices":validation,
                     "selection_optimism":True,"metric":"pooled_validation_poisson_log_likelihood",**certificate}
    record.event("context_full_training_complete",trials=len(y))
    return payload,certificate


def context_predict(reference_id,payload,query):
    import numpy as np
    from . import _context as c
    if reference_id=="R0":
        return np.broadcast_to(payload["constant"],(len(query["eval_trial_ids"]),140,45)).copy()
    return c.predict_profiles(payload,query["eval_condition_ids"])


def ridge_train(reference_id,training,fit,validation,record):
    import numpy as np
    from . import _nystrom as m
    x,y,conditions=(training[k] for k in ("train_counts_heldin","train_counts_heldout","train_condition_ids"))
    native_fit,native_validation=m.training_split(conditions)
    require(np.array_equal(fit,native_fit) and np.array_equal(validation,native_validation),"R6/R7 original split must equal admitted D0")
    families=("direct","residual")
    target,residual=m.target_fit(y[fit],conditions[fit])
    baseline=m.target_predict(target,conditions[validation])
    yy=y[validation].astype(np.float32)
    base_ll=m.log_likelihood(yy,baseline)
    require(np.isfinite(base_ll),"finite original baseline likelihood")
    # R6 source gain uses this fixed positive denominator; retain its strict tie
    # comparison rather than silently selecting by a differently rounded scalar.
    spikes=int(y[validation].sum(dtype=np.int64));require(spikes>0,"zero D0 spike support")
    denominator=spikes*np.log(2)
    features,fs=m.feature_fit(x[fit],conditions[fit],families)
    eval_features=m.feature_predict(x[validation],conditions[validation],fs,families)
    direct=m.pool(y[fit].astype(np.float32)).reshape(-1,45)
    best={"kind":"condition_time","family":"condition_time","alpha":None,"weight":0.0,"gamma_multiplier":None,"validation_ll":base_ll,"gain":0.0}
    rows=[];geometry=[]
    record.event("condition_only_selection",ll=base_ll,fit_trials=len(fit),validation_trials=len(validation))

    def assess(kind,family,alpha,weight,multiplier,raw):
        record.event("candidate_started",kind=kind,family=family,alpha=alpha,weight=weight,gamma_multiplier=multiplier)
        pred=m.safe_combine(baseline,raw,family,weight)
        ll=m.log_likelihood(yy,pred);require(np.isfinite(ll),"finite complete validation likelihood")
        gain=float((ll-base_ll)/denominator);require(np.isfinite(gain),"finite original pooled gain")
        row={"kind":kind,"family":family,"alpha":alpha,"weight":weight,"gamma_multiplier":multiplier,"validation_ll":ll,"gain":gain}
        rows.append(row)
        criterion="gain" if reference_id=="R6" else "validation_ll"
        if row[criterion]>best[criterion]:best.update(row)
        record.event("candidate_complete",**row)

    for family in families:
        response=direct if family=="direct" else residual
        record.event("ridge_path_started",kind="linear",family=family,alphas=list(m.ALPHAS))
        models=m.finite_models(m.ridge_path(features[family].copy(),response,m.ALPHAS))
        record.event("ridge_path_complete",kind="linear",family=family,solutions=3)
        for alpha in m.ALPHAS:
            raw=m.raw_predict(eval_features[family],models[alpha],baseline.shape)
            for weight in m.WEIGHTS:assess("linear",family,alpha,weight,None,raw)
    if reference_id=="R7":
        for family in families:
            response=direct if family=="direct" else residual
            scaler,scaled,indices,median=m.kernel_geometry(features[family])
            geometry.append({"family":family,"landmarks":len(indices),"positive_distance_median":median,"indices":indices})
            for multiplier in m.GAMMA_MULTIPLIERS:
                record.event("kernel_map_started",family=family,multiplier=multiplier,landmarks=512)
                mapper=m.fit_map(scaled,indices,median,multiplier)
                models=m.fit_kernel_path(scaled,mapper,response)
                record.event("kernel_map_and_ridge_path_complete",family=family,multiplier=multiplier,solutions=3)
                predictions=m.kernel_predict_many(eval_features[family],scaler,mapper,models,baseline.shape)
                for alpha in m.ALPHAS:
                    for weight in m.WEIGHTS:assess("nystrom",family,alpha,weight,multiplier,predictions[alpha])
    require(len(rows)==(24 if reference_id=="R6" else 96),"full native candidate roster before refit")
    certificate={"support":"D0","fit_indices":fit,"validation_indices":validation,
                 "metric":"strict_pooled_likelihood_gain" if reference_id=="R6" else "strict_pooled_likelihood",
                 "selection_optimism":True,"condition_only_validation_ll":base_ll,
                 "selection_rows":rows,"selected":best.copy(),"kernel_geometry":geometry,
                 "selection_map_fits":6 if reference_id=="R7" else 0,
                 "selection_ridge_paths":8 if reference_id=="R7" else 2,
                 "selection_coefficient_solutions":24 if reference_id=="R7" else 6}
    record.event("selected_full_refit_started",selected=best,trials=1721)
    family=best["family"]
    target,residual=m.target_fit(y,conditions,need_residual=family=="residual")
    payload={"choice":best.copy(),"target_state":target,"feature_state":None,"model":None,"scaler":None,"mapper_state":None}
    if family!="condition_time":
        features,fs=m.feature_fit(x,conditions,(family,))
        response=m.pool(y.astype(np.float32)).reshape(-1,45) if family=="direct" else residual
        if best["kind"]=="linear":
            model=m.finite_models(m.ridge_path(features[family],response,(best["alpha"],)))[best["alpha"]]
        else:
            scaler,scaled,indices,median=m.kernel_geometry(features[family])
            mapper=m.fit_map(scaled,indices,median,best["gamma_multiplier"])
            model=m.fit_kernel_path(scaled,mapper,response,(best["alpha"],))[best["alpha"]]
            payload.update(scaler=scaler,mapper_state={"components":mapper.components_.copy(),
                          "component_indices":mapper.component_indices_.copy(),"normalization":mapper.normalization_.copy(),
                          "gamma":float(mapper.gamma),"input_features":int(mapper.components_.shape[1])})
        payload.update(feature_state=fs,model=model)
    record.event("selected_full_refit_complete",trials=1721)
    return payload,certificate


def ridge_predict(payload,query):
    import numpy as np
    from sklearn.metrics.pairwise import rbf_kernel
    from . import _nystrom as m
    choice=payload["choice"]
    expected=m.target_predict(payload["target_state"],query["eval_condition_ids"])
    if choice["kind"]=="condition_time":return np.maximum(expected,m.FLOOR).astype(np.float32)
    family=choice["family"]
    features=m.feature_predict(query["eval_counts_heldin"],query["eval_condition_ids"],payload["feature_state"],(family,))[family]
    if choice["kind"]=="linear":raw=m.raw_predict(features,payload["model"],expected.shape)
    else:
        native=payload["mapper_state"]
        require(native["components"].shape==(512,features.shape[1]) and native["normalization"].shape==(512,512),"exact trained Nystroem geometry")
        require(np.isfinite(native["gamma"]) and native["gamma"]>0,"positive trained RBF gamma")
        coefficient,intercept=payload["model"]
        raw=np.empty((len(features),45),dtype=np.float32)
        for start in range(0,len(features),4096):
            scaled=m.standardized(features[start:start+4096],payload["scaler"])
            # sklearn Nystroem.transform's declared RBF map; no fit/reselection.
            embedded=(rbf_kernel(scaled,native["components"],gamma=native["gamma"]) @ native["normalization"].T).astype(np.float32)
            block=embedded@coefficient+intercept
            require(np.isfinite(block).all(),"finite trained-kernel prediction")
            raw[start:start+len(block)]=block
        raw=raw.reshape(expected.shape)
    return m.safe_combine(expected,raw,family,choice["weight"])


def temporal_train(training,record):
    import numpy as np
    from . import _temporal as t
    x,y,c=(training[k] for k in ("train_counts_heldin","train_counts_heldout","train_condition_ids"))
    fit,val=t.split_trials(c)  # original R8 singleton rule, never substitute D0
    stats=t.profile_statistics(y[fit],c[fit]);context_rows=[];best_context=None
    for i,specification in enumerate(t.CONTEXTS):
        record.event("context_candidate_started",index=i)
        model=t.context_model(stats,specification)
        pred=t.context_prediction(model,c[val])
        ll=float(t.unit_log_likelihood(y[val],pred).sum(dtype=np.float64))
        row={"index":i,"sigma_bins":specification[0],"pseudotrials":specification[1],"ll":ll}
        context_rows.append(row)
        if best_context is None or ll>context_rows[best_context]["ll"]:best_context=i
        record.event("context_candidate_complete",**row)
    baseline=t.context_prediction(t.context_model(stats,t.CONTEXTS[best_context]),c[val])
    record.event("temporal_ridge_path_started",alphas=list(t.ALPHAS))
    models=t.ridge_models(t.feature_matrix(x[fit],True),t.reduced(y[fit].astype(np.float32),True).reshape(-1,45),t.ALPHAS)
    record.event("temporal_ridge_path_complete",solutions=3)
    features=t.feature_matrix(x[val],False)
    best_ll=float(t.unit_log_likelihood(y[val],baseline).sum(dtype=np.float64));best_alpha=None;best_weight=0.0;rows=[]
    for alpha in t.ALPHAS:
        neural=t.ridge_prediction(features,models[alpha],baseline.shape)
        for weight in t.GLOBAL_BLENDS:
            record.event("global_blend_started",alpha=alpha,weight=weight)
            ll=float(t.unit_log_likelihood(y[val],t.blend_prediction(baseline,neural,weight)).sum(dtype=np.float64))
            row={"alpha":alpha,"blend":weight,"ll":ll};rows.append(row)
            if ll>best_ll:best_ll,best_alpha,best_weight=ll,alpha,weight
            record.event("global_blend_complete",**row)
    weights=np.zeros(45,dtype=np.float32);local_rows=[]
    if best_alpha is not None:
        neural=t.ridge_prediction(features,models[best_alpha],baseline.shape)
        weights=np.full(45,best_weight,dtype=np.float32)
        best=t.unit_log_likelihood(y[val],t.blend_prediction(baseline,neural,best_weight))
        for weight in t.LOCAL_BLENDS:
            record.event("unit_blend_started",weight=weight)
            ll=t.unit_log_likelihood(y[val],t.blend_prediction(baseline,neural,weight))
            penalized=ll-t.LOCAL_PENALTY_NATS*(weight-best_weight)**2
            improved=penalized>best;weights[improved]=weight;best[improved]=penalized[improved]
            row={"weight":weight,"raw_pooled_ll":float(ll.sum()),"penalty_per_unit":t.LOCAL_PENALTY_NATS*(weight-best_weight)**2}
            local_rows.append(row);record.event("unit_blend_complete",**row)
    require(len(context_rows)==13 and len(rows)==12 and len(local_rows)==(0 if best_alpha is None else 9),"complete temporal selection support")
    certificate={"support":"R8_original_singleton_retention_split","fit_indices":fit,"validation_indices":val,
                 "metric":"pooled_likelihood_then_per_unit_20_nat_penalized_selection","selection_optimism":True,
                 "context_index":best_context,"context_hypotheses":context_rows,"global_alpha":best_alpha,
                 "global_blend":best_weight,"neural_hypotheses":rows,"unit_blends":weights,
                 "local_penalty_nats":20.0,"local_blend_checks":local_rows}
    record.event("temporal_full_refit_started",alpha=best_alpha,trials=1721)
    context=t.context_model(t.profile_statistics(y,c),t.CONTEXTS[best_context]);model=None
    if best_alpha is not None:
        model=t.ridge_models(t.feature_matrix(x,True),t.reduced(y.astype(np.float32),True).reshape(-1,45),(best_alpha,))[best_alpha]
    record.event("temporal_full_refit_complete",trials=1721)
    return {"context":context,"model":model,"unit_weights":weights},certificate


def temporal_predict(payload,query):
    import numpy as np
    from . import _temporal as t
    p=t.context_prediction(payload["context"],query["eval_condition_ids"])
    if payload["model"] is not None:
        neural=t.ridge_prediction(t.feature_matrix(query["eval_counts_heldin"],False),payload["model"],p.shape)
        p=t.blend_prediction(p,neural,payload["unit_weights"][None,None,:])
    return np.maximum(p,t.RATE_FLOOR)
