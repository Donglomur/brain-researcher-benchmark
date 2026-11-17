"""Full organizer-derived GPFA search, train state, query adaptation and inference.

Elephant scientific internals/state fields remain a separately qualified source
dependency. No native call or numerical routine was imported/executed here.
"""
from .common import require, native_development_bps
from ..contracts import diagnostic


def spiketrains(counts):
    import numpy as np
    import neo
    import quantities as pq
    result=[]
    for trial in counts:
        units=[]
        for unit in range(trial.shape[1]):
            positions=np.nonzero(trial[:,unit])[0]
            repetitions=trial[positions,unit].astype(int)
            times=np.repeat(positions,repetitions)
            units.append(neo.SpikeTrain(times*5*pq.ms,t_stop=700*pq.ms))
        result.append(units)
    return result


def factor_array(native,n,latent):
    import numpy as np
    require(len(native)==n,"complete GPFA factor trial roster")
    factors=np.stack([native[i].T for i in range(n)])
    require(factors.shape==(n,140,latent) and np.isfinite(factors).all(),"source GPFA trial x bin x latent factors")
    return factors


def fit_latent(observed,latent,config,record,scope):
    import warnings
    from .native_state import qualification,constructor,export,observe_fit
    from .gpfa_audit import NativeOptimizerAudit
    from sklearn.exceptions import ConvergenceWarning
    qualification(config)  # refuse before importing/calling an unqualified model
    record.event("gpfa_fit_started",scope=scope,latent=latent,trials=len(observed))
    model=constructor(latent)
    seen=[]
    try:
        with warnings.catch_warnings(record=True) as seen,NativeOptimizerAudit(latent,record,scope) as audit:
            warnings.simplefilter("always")
            raw=model.fit_transform(spiketrains(observed))
    except BaseException as original:
        record.custody.fail(original,'gpfa_fit_body')
        record.original_warning_records.extend(seen)
        try:observe_fit(model,record,scope)
        except BaseException as secondary:record.custody.fail(secondary,'gpfa_failed_fit_observation')
        try:record.event("gpfa_fit_failed",scope=scope,scientific_reason="native_fit_failed",original_cause=diagnostic(original),warnings=[diagnostic(w.message)for w in seen])
        except BaseException as secondary:
            from .common import ScientificFailure
            if type(secondary) is not ScientificFailure or secondary.custody is not record.custody:
                record.custody.fail(secondary,'gpfa_failure_trace')
        raise
    observe_fit(model,record,scope)
    record.original_warning_records.extend(seen)
    record.event("gpfa_fit_returned",scope=scope,latent=latent,warnings=[diagnostic(w.message) for w in seen])
    require(not any(issubclass(w.category,(RuntimeWarning,ConvergenceWarning)) for w in seen),"GPFA numerical/initialization convergence warning")
    factors=factor_array(raw,len(observed),latent)
    state=export(model,latent,config,audit.rows)
    record.event("gpfa_state_export_complete",scope=scope,latent=latent)
    return state,factors


def transform(state,observed,config,record,scope):
    from .native_state import restore
    record.event("gpfa_transform_started",scope=scope,latent=state["latent"],trials=len(observed))
    model=restore(state,config)
    out=factor_array(model.transform(spiketrains(observed)),len(observed),state["latent"])
    record.event("gpfa_transform_complete",scope=scope,trials=len(observed))
    return out


def observed_readout(train_factors,query_factors,train_observed,query_observed,alpha,record,scope):
    import numpy as np
    from sklearn.linear_model import Ridge
    ft=train_factors.reshape(-1,train_factors.shape[2]);fq=query_factors.reshape(-1,query_factors.shape[2])
    record.event("combined_observed_readout_started",scope=scope,alpha=alpha,training_rows=len(ft),query_observed_rows=len(fq))
    model=Ridge(alpha=alpha)
    model.fit(np.vstack([ft,fq]),np.vstack([train_observed.reshape(-1,137),query_observed.reshape(-1,137)]))
    tr=model.predict(ft);qr=model.predict(fq)
    # Preserve the organizer's otherwise-unused positive-minimum operation.
    # Empty positive support is an observed native failure, not a license to
    # synthesize a rectified constant and continue.
    positive_min=float(np.min([np.min(tr[tr>0]),np.min(qr[qr>0])]))
    true_min=float(np.min([np.min(tr),np.min(qr)]))
    require(np.isfinite(tr).all() and np.isfinite(qr).all() and np.isfinite(model.coef_).all() and np.isfinite(model.intercept_).all(),"finite complete observed readout")
    tr[tr<1e-10]=1e-10;qr[qr<1e-10]=1e-10
    state={"coefficients":np.asarray(model.coef_).copy(),"intercepts":np.asarray(model.intercept_).copy(),"alpha":alpha,"floor":1e-10}
    record.event("combined_observed_readout_complete",scope=scope,positive_min=positive_min,true_min=true_min)
    return state,tr,qr


def apply_readout(state,factors):
    import numpy as np
    flat=factors.reshape(-1,factors.shape[2]);coef=state["coefficients"];intercept=state["intercepts"]
    require(coef.shape==(137,factors.shape[2]) and intercept.shape==(137,),"frozen observed-readout axes")
    rates=flat@coef.T+intercept
    require(np.isfinite(rates).all() and state["floor"]==1e-10,"finite original observed readout")
    return np.maximum(rates,1e-10)


def train(training,config,record):
    import numpy as np
    from . import glm
    from .native_state import qualification
    qualification(config)
    x,y=training["train_counts_heldin"],training["train_counts_heldout"]
    splits=[]
    for f in range(3):
        val=np.arange(1721)[f::3];fit=np.setdiff1d(np.arange(1721),val);splits.append((fit,val))
    rows=[];best=None
    for latent in (32,36,40,44,48,52):
        factors=[]
        for f,(fit,val) in enumerate(splits):
            latent_state,tr=fit_latent(x[fit],latent,config,record,f"R5_k{latent}_fold{f}")
            qr=transform(latent_state,x[val],config,record,f"R5_k{latent}_fold{f}_observed_validation")
            factors.append((tr,qr))
        for alpha1 in (0.0,.0001,.001,.01):
            for alpha2 in (0.0,.0001,.001,.01):
                scores=[];fold_records=[]
                for f,((fit,val),(tf,qf)) in enumerate(zip(splits,factors)):
                    scope=f"R5_k{latent}_a1{alpha1}_a2{alpha2}_fold{f}"
                    # Validation observed counts calibrate readout; validation
                    # withheld labels are used solely by the development metric.
                    readout,tr,qr=observed_readout(tf,qf,x[fit],x[val],alpha1,record,scope)
                    model=glm.fit_models(tr,y[fit].reshape(-1,45),alpha2,True,record,scope,False)
                    pred=glm.apply_models(model,qr,(len(val),140,45))
                    score=native_development_bps(y[val],pred)
                    scores.append(score);fold_records.append({"fold":f,"native_co_bps":score,"unit_attempts":model["unit_attempts"]})
                    record.event("gpfa_readout_fold_complete",scope=scope,native_co_bps=score)
                value=float(np.mean(scores));require(np.isfinite(value),"complete finite three-fold GPFA mean")
                row={"latent":latent,"alpha1":alpha1,"alpha2":alpha2,"folds":fold_records,"native_fold_mean_co_bps":value};rows.append(row)
                if best is None or value>best["native_fold_mean_co_bps"]:best=row
                record.event("gpfa_grid_row_complete",latent=latent,alpha1=alpha1,alpha2=alpha2,native_fold_mean_co_bps=value)
    require(len(rows)==96 and all(len(r["folds"])==3 for r in rows),"complete 96x3 GPFA selection")
    selected={k:best[k] for k in ("latent","alpha1","alpha2")}
    final,train_factors=fit_latent(x,selected["latent"],config,record,"R5_full_training")
    certificate={"support":"three_interleaved_whole_training_trial_folds","fold_indices":splits,"selection_optimism":True,
                 "metric":"arithmetic_mean_of_native_fold_co_bps","selection_rows":rows,"selected":selected,
                 "latent_fits_in_search":18,"observed_readouts_in_search":288,"unit_glm_fits_before_restarts":12960}
    # No final heldout-unit GLM exists yet: it follows legal query calibration.
    return {"selected":selected,"native_state":final,"training_factors":train_factors,
            "readout":None,"models":None,"adaptation_complete":False},certificate


def adapt(payload,training,query,config,record):
    from . import glm
    selected=payload["selected"]
    query_factors=transform(payload["native_state"],query["eval_counts_heldin"],config,record,"R5_full_observed_query")
    readout,tr,qr=observed_readout(payload["training_factors"],query_factors,training["train_counts_heldin"],query["eval_counts_heldin"],selected["alpha1"],record,"R5_final_combined_observed")
    model=glm.fit_models(tr,training["train_counts_heldout"].reshape(-1,45),selected["alpha2"],True,record,"R5_final_training_labels_after_observed_adaptation",False)
    # Check complete output domain now without target labels; predict later still
    # executes native transform and fixed-state readout, not a stored-output cache.
    glm.apply_models(model,qr,(574,140,45))
    return {**payload,"readout":readout,"models":model,"adaptation_complete":True}


def predict(payload,query,config,record):
    from . import glm
    require(payload["adaptation_complete"] is True and payload["readout"] is not None and payload["models"] is not None,"R5 final query adaptation required before prediction")
    factors=transform(payload["native_state"],query["eval_counts_heldin"],config,record,"R5_frozen_state_inference")
    rates=apply_readout(payload["readout"],factors)
    return glm.apply_models(payload["models"],rates,(len(query["eval_trial_ids"]),140,45))
