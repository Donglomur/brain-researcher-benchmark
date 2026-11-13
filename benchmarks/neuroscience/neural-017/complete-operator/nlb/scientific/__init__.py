"""Complete NLB R0–R8 scientific API. Importing this API performs no numerics.

Scientific libraries are imported only inside separately authorized calls.
Current controls parse this source and never import or invoke these functions.
"""
from .common import (ScientificFailure, Recorder, configuration, require,
                     primitive_state, state_digest, check_state, training_view,
                     query_view, split_rows, valid_rates, finish)


def train(reference_id, training, split, config, trace):
    configuration(config)
    require(reference_id in tuple(f"R{i}" for i in range(9)),"complete fixed R0–R8 family")
    record=Recorder(trace,config,reference_id)
    try:
        training_view(training,reference_id)
        record.event("training_producer_started",training_binding=config["bindings"]["training"])
        if reference_id in ("R0","R1","R2"):
            from . import linear_bank
            fit,val=split_rows(training,split) if reference_id=="R2" else (None,None)
            payload,certificate=linear_bank.context_train(reference_id,training,fit,val,record)
        elif reference_id in ("R3","R4"):
            from . import glm
            payload,certificate=glm.fixed_train(training,record) if reference_id=="R3" else glm.sweep_train(training,record)
        elif reference_id=="R5":
            from . import gpfa
            payload,certificate=gpfa.train(training,config,record)
        elif reference_id in ("R6","R7"):
            from . import linear_bank
            fit,val=split_rows(training,split)
            payload,certificate=linear_bank.ridge_train(reference_id,training,fit,val,record)
        else:
            from . import linear_bank
            payload,certificate=linear_bank.temporal_train(training,record)
        return finish(reference_id,payload,certificate,training,config,record)
    except BaseException as exc:
        carrier=record.failure(exc)
        if carrier is exc:raise
        raise carrier from exc


def adapt(state, training, query, config, trace):
    configuration(config)
    record=Recorder(trace,config,state.get("reference_id","UNADMITTED"))
    try:
        original=check_state(state,config)
        require(original["phase"]=="trained","query adaptation exactly once from TrainingState")
        training_view(training,original["reference_id"])
        query_view(query,original,config,full=True)
        parent=state_digest(original)
        record.event("query_adaptation_started",parent_state_digest=parent,query_binding=config["bindings"]["query"])
        payload=original["payload"]
        if original["reference_id"]=="R5":
            from . import gpfa
            payload=gpfa.adapt(payload,training,query,config,record)
        # Every other recipe has no query-learned parameters. An explicit bound
        # AdaptationState still fixes the actual pool and immutable parent.
        out={**original,"payload":payload,"phase":"adapted","query_binding":config["bindings"]["query"],
             "query_trial_ids":query["eval_trial_ids"],"bin_left_edges_ms":query["bin_left_edges_ms"],"parent_state_digest":parent}
        out=primitive_state(out,config)
        record.event("query_adaptation_complete",state_digest=state_digest(out),parameter_learning=original["reference_id"]=="R5")
        return out
    except BaseException as exc:
        carrier=record.failure(exc)
        if carrier is exc:raise
        raise carrier from exc


def predict(state, query, config, trace):
    configuration(config)
    record=Recorder(trace,config,state.get("reference_id","UNADMITTED"))
    try:
        frozen=check_state(state,config)
        require(frozen["phase"]=="adapted","complete original bound QueryAdaptState required")
        n=query_view(query,frozen,config)
        before=state_digest(frozen);reference_id=frozen["reference_id"]
        record.event("frozen_state_prediction_started",state_digest=before,query_trials=n)
        if reference_id in ("R0","R1","R2"):
            from . import linear_bank
            output=linear_bank.context_predict(reference_id,frozen["payload"],query)
        elif reference_id in ("R3","R4"):
            from . import glm
            output=glm.predict(frozen["payload"],query)
        elif reference_id=="R5":
            from . import gpfa
            output=gpfa.predict(frozen["payload"],query,config,record)
        elif reference_id in ("R6","R7"):
            from . import linear_bank
            output=linear_bank.ridge_predict(frozen["payload"],query)
        else:
            from . import linear_bank
            output=linear_bank.temporal_predict(frozen["payload"],query)
        output=valid_rates(output,n)
        require(state_digest(frozen)==before,"frozen state mutated during inference")
        record.event("frozen_state_prediction_complete",state_digest=before,query_trials=n,bins=140,units=45)
        return output
    except BaseException as exc:
        carrier=record.failure(exc)
        if carrier is exc:raise
        raise carrier from exc


def development(reference_id, training, split, config, trace):
    """Return actual D0 fixed exercise or reuse the original complete search.

R0/R1 share exactly one statistics-producing exercise. The controller supplies
the first returned joint certificate as config.joint_development on the second
call, never runs an unmetered duplicate. Other searched references reuse the
config.training_state bound to their actual prior source/training producer.
"""
    configuration(config)
    require(reference_id in tuple(f"R{i}" for i in range(9)),"exact development reference")
    record=Recorder(trace,config,reference_id)
    try:
        training_view(training,reference_id)
        bindings={k:config["bindings"][k] for k in ("programme","source","dependencies","training")}
        if reference_id not in ("R0","R1","R3"):
            state=check_state(config["training_state"],config,reference_id)
            require(state["phase"]=="trained" and type(state["development"]) is dict,"complete original search development required before query adaptation")
            record.event("development_search_receipts_reused",state_digest=state_digest(state),no_new_grid=True)
            return primitive_state({"schema":"nlb017-development-certificate-v1","reference_id":reference_id,
                                    "bindings":bindings,"origin":"actual_original_training_search",
                                    "training_state_digest":state_digest(state),"development":state["development"],
                                    "assessment_target_access":False,"independent_performance_estimate":False},config)
        fit,val=split_rows(training,split)
        if reference_id in ("R0","R1") and "joint_development" in config:
            joint=primitive_state(config["joint_development"],config)
            require(joint["schema"]=="nlb017-joint-R0-R1-development-v1" and joint["bindings"]==bindings and set(joint["results"])=={"R0","R1"},"exact bound joint development producer")
            import numpy as np
            require(np.array_equal(joint["fit_indices"],fit) and np.array_equal(joint["validation_indices"],val),"same original D0 support on joint reuse")
            record.event("joint_development_reused",joint_digest=state_digest(joint),no_new_statistics_fit=True)
            return joint
        import numpy as np
        from .common import pooled_ll,native_development_bps
        y=training["train_counts_heldout"]
        record.event("fixed_development_exercise_started",fit_trials=1381,validation_trials=340)
        if reference_id in ("R0","R1"):
            from . import _context as c
            # One actual shared statistics fit supplies both fixed outputs.
            statistics=c.fit_statistics(y[fit],training["train_condition_ids"][fit])
            baseline=np.broadcast_to(statistics["mu"],(340,140,45)).copy()
            model=c.profiles_for_hypothesis(statistics,c.ordered_hypotheses()[0])
            condition=c.predict_profiles(model,training["train_condition_ids"][val])
            results={}
            for rid,rates in (("R0",baseline),("R1",condition)):
                valid_rates(rates,340)
                results[rid]={"pooled_poisson_ll":pooled_ll(y[val],rates),"native_inner_co_bps":native_development_bps(y[val],rates),"prediction_support":[340,140,45]}
            out={"schema":"nlb017-joint-R0-R1-development-v1","bindings":bindings,"fit_indices":fit,"validation_indices":val,
                 "original_split_descriptor":split["descriptor"],"statistics_producer_count":1,"results":results,
                 "assessment_target_access":False,"selection_optimism":False,"query_state_not_produced":True}
        else:
            from . import glm
            model=glm.fit_models(glm.smoothing_features(training["train_counts_heldin"][fit],50),y[fit].reshape(-1,45),.01,False,record,"R3_D0_development",True)
            pred=glm.apply_models(model,glm.smoothing_features(training["train_counts_heldin"][val],50),(340,140,45))
            out={"schema":"nlb017-development-certificate-v1","reference_id":"R3","bindings":bindings,"origin":"additional_fixed_D0_exercise",
                 "fit_indices":fit,"validation_indices":val,"original_split_descriptor":split["descriptor"],
                 "pooled_poisson_ll":pooled_ll(y[val],pred),"native_inner_co_bps":native_development_bps(y[val],pred),
                 "unit_attempts":model["unit_attempts"],"selection_optimism":False,"assessment_target_access":False,"query_state_not_produced":True}
        record.event("fixed_development_exercise_complete",references=["R0","R1"] if reference_id in ("R0","R1") else ["R3"])
        return primitive_state(out,config)
    except BaseException as exc:
        carrier=record.failure(exc)
        if carrier is exc:raise
        raise carrier from exc
