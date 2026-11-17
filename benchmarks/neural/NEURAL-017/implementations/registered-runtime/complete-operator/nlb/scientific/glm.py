"""Source-derived R3/R4 and the R5 training-label Poisson stage, never run here."""
from .common import require, native_development_bps


def smoothing_features(counts,sigma_ms):
    import numpy as np
    from scipy.signal.windows import gaussian
    require(sigma_ms in (30,40,50,60),"closed smoothing grid")
    weights=gaussian(int(6*sigma_ms/5),int(sigma_ms/5),sym=True).astype(np.float64)
    weights/=weights.sum()
    smoothed=np.apply_along_axis(lambda x:np.convolve(x,weights,"same"),1,np.asarray(counts,dtype=np.float64))
    # Organizer neural features deliberately have no convolution-of-ones edge
    # correction. This differs from context profiles and ridge feature smoothing.
    features=np.log(smoothed+1e-4).reshape(-1,counts.shape[2])
    require(np.isfinite(features).all(),"finite source log-smoothed features")
    return np.ascontiguousarray(features)


def fit_models(features,targets,alpha,retries,record,scope,clip):
    import numpy as np
    import warnings
    from sklearn.linear_model import PoissonRegressor
    from sklearn.exceptions import ConvergenceWarning
    require(features.ndim==targets.ndim==2 and len(features)==len(targets) and targets.shape[1]==45,"all 45 GLM units and complete rows")
    require(np.isfinite(features).all() and np.isfinite(targets).all() and (targets>=0).all(),"finite training GLM domain")
    coefs=[];intercepts=[];units=[]
    for unit in range(45):
        record.event("glm_unit_started",scope=scope,unit=unit,alpha=alpha)
        require(float(targets[:,unit].sum())>0,"all-zero target unit has no finite source GLM optimum")
        attempts=[]
        for max_iter in ((500,2500,12500) if retries else (500,)):
            record.event("glm_attempt_started",scope=scope,unit=unit,alpha=alpha,max_iter=max_iter)
            kwargs={"alpha":alpha,"max_iter":max_iter}
            if not retries:
                kwargs.update(tol=1e-4,solver="lbfgs",fit_intercept=True,warm_start=False)
            with warnings.catch_warnings(record=True) as captured:
                warnings.simplefilter("always")
                model=PoissonRegressor(**kwargs)
                model.fit(features,targets[:,unit])
            # Retain actual n_iter and warnings before convergence/domain checks.
            facts={"scope":scope,"unit":unit,"max_iter":max_iter,"n_iter":int(model.n_iter_),
                   "warnings":[{"category":w.category.__name__,"message":str(w.message)} for w in captured]}
            attempts.append(facts);record.event("glm_attempt_returned",**facts)
            require(0<=int(model.n_iter_)<=max_iter,"invalid native iteration observation")
            require(np.isfinite(model.coef_).all() and np.isfinite(model.intercept_),"nonfinite native GLM parameters")
            runtime=any(issubclass(w.category,RuntimeWarning) for w in captured)
            require(not runtime,"numerical warning in complete native GLM")
            if int(model.n_iter_)==max_iter:
                require(retries and max_iter<12500,"source GLM convergence exhausted; no partial unit bank")
                continue
            require(not any(issubclass(w.category,ConvergenceWarning) for w in captured),"native convergence warning before limit")
            coefs.append(np.asarray(model.coef_,dtype=np.float64).copy())
            intercepts.append(float(model.intercept_));units.append({"unit":unit,"attempts":attempts})
            break
    require(len(coefs)==45 and len(units)==45,"complete source GLM bank")
    return {"coefficients":np.stack(coefs),"intercepts":np.asarray(intercepts,dtype=np.float64),"alpha":alpha,
            "output_clip":(1e-9,1e20) if clip else None,"unit_attempts":units}


def apply_models(state,features,shape):
    import numpy as np
    coef,intercepts=state["coefficients"],state["intercepts"]
    require(coef.shape==(45,features.shape[1]) and intercepts.shape==(45,),"exact fitted GLM coefficient axes")
    # PoissonRegressor inverse log link, evaluated unit-by-unit as in the source.
    rates=np.empty((len(features),45),dtype=np.float64)
    for unit in range(45):
        rate=np.exp(features@coef[unit]+intercepts[unit])
        require(np.isfinite(rate).all() and (rate>=0).all(),"nonfinite original Poisson output before clipping")
        if state["output_clip"] is not None:
            rate=np.clip(rate,*state["output_clip"])
        require((rate>0).all(),"strict positive source output; no unselected GPFA floor")
        rates[:,unit]=rate
    require(len(features)==shape[0]*shape[1] and shape[1:]==(140,45),"full GLM output support")
    return rates.reshape(shape)


def fixed_train(training,record):
    features=smoothing_features(training["train_counts_heldin"],50)
    models=fit_models(features,training["train_counts_heldout"].reshape(-1,45),.01,False,record,"R3_final",True)
    return {"sigma_ms":50,"models":models},None


def sweep_train(training,record):
    import numpy as np
    x,y=training["train_counts_heldin"],training["train_counts_heldout"]
    rows=[];best=None;fold_indices=[]
    for f in range(5):
        validation=np.arange(1721)[f::5]
        fit=np.setdiff1d(np.arange(1721),validation)
        fold_indices.append((fit,validation))
    for sigma in (30,40,50,60):
        for native_alpha in np.logspace(-3,0,4):
            alpha=float(native_alpha)
            scores=[];fold_records=[]
            for f,(fit,val) in enumerate(fold_indices):
                scope=f"R4_sigma{sigma}_alpha{alpha}_fold{f}"
                record.event("smoothing_fold_started",scope=scope,fit_trials=len(fit),validation_trials=len(val))
                model=fit_models(smoothing_features(x[fit],sigma),y[fit].reshape(-1,45),alpha,True,record,scope,True)
                pred=apply_models(model,smoothing_features(x[val],sigma),(len(val),140,45))
                score=native_development_bps(y[val],pred)
                fold_records.append({"fold":f,"native_co_bps":score,"unit_attempts":model["unit_attempts"]})
                scores.append(score);record.event("smoothing_fold_complete",scope=scope,native_co_bps=score)
            value=float(np.mean(scores));require(np.isfinite(value),"finite complete native five-fold mean")
            row={"sigma_ms":sigma,"alpha":alpha,"folds":fold_records,"native_fold_mean_co_bps":value}
            rows.append(row)
            if best is None or value>best["native_fold_mean_co_bps"]:best=row
            record.event("smoothing_grid_row_complete",sigma_ms=sigma,alpha=alpha,native_fold_mean_co_bps=value)
    require(len(rows)==16 and all(len(r["folds"])==5 for r in rows),"full16x5 native smoothing selection")
    record.event("smoothing_full_refit_started",sigma_ms=best["sigma_ms"],alpha=best["alpha"])
    final=fit_models(smoothing_features(x,best["sigma_ms"]),y.reshape(-1,45),best["alpha"],True,record,"R4_final",True)
    record.event("smoothing_full_refit_complete",units=45)
    certificate={"support":"five_interleaved_whole_training_trial_folds","fold_indices":fold_indices,
                 "selection_optimism":True,"metric":"arithmetic_mean_of_native_fold_co_bps",
                 "selection_rows":rows,"selected":{"sigma_ms":best["sigma_ms"],"alpha":best["alpha"]},
                 "planned_grid_unit_fits_before_retries":3600,"final_unit_fits_before_retries":45}
    return {"sigma_ms":best["sigma_ms"],"models":final},certificate


def predict(payload,query):
    n=len(query["eval_trial_ids"])
    return apply_models(payload["models"],smoothing_features(query["eval_counts_heldin"],payload["sigma_ms"]),(n,140,45))
