"""Owner-only complete-submission metrics for the separate deposited-label profile.

No submission is executed here. Inputs are ordinary already-parsed values from
an independently isolated participant program. The physical primary remains held.
"""
from collections import Counter, defaultdict
import math
import random
import re

import participant_core as core
import released_profile as profile

LOG_EPS = 1e-15
BOOTSTRAP_SEED = 541731
BOOTSTRAP_REPLICATES = 1000


def evaluate_physical_primary(*args, **kwargs):
    return core.current_primary_status()


def validate_owner(owner):
    if (type(owner) is not dict or owner.get("schema")!="apcx-deposited-label-owner-v1"
            or owner.get("profile")!=profile.PROFILE
            or owner.get("profile_contract_sha256")!=profile.PROFILE_CONTRACT_SHA256
            or owner.get("target_kind")!="deposited_Total_pulse_label"
            or owner.get("profile_document_sha256")!=core.digest(profile.DOCUMENTATION)
            or type(owner.get("invented")) is not bool
            or owner.get("physical_delivery_verified") is not False
            or owner.get("remaining_physical_primary_holds")!=list(core.HOLDS)
            or owner.get("historical_selection_caveat_required") is not True
            or owner.get("scientific_qualification") is not False):
        raise ValueError("trusted owner profile and unchanged primary holds")
    cases=owner["cases"];sessions=owner["sessions"]
    if type(cases) is not list or not cases or type(sessions) is not dict:
        raise ValueError("whole expected protected cases")
    by_id={};groups=defaultdict(list);animals=set()
    for c in cases:
        core.exact_keys(c,("case_id","session_id","animal","count","high","split_rank"))
        cid,sid,animal=c["case_id"],c["session_id"],c["animal"]
        if (type(cid) is not str or not re.fullmatch("[0-9a-f]{64}",cid) or cid in by_id
                or type(sid) is not str or sid not in sessions):
            raise ValueError("unique owner case/session")
        core.nonempty(animal);core.integer(c["count"]);core.integer(c["split_rank"])
        if type(c["high"]) is not int or c["high"]!=int(c["count"]>=9):
            raise ValueError("deposited-label-derived category")
        if sessions[sid]["animal"]!=animal:raise ValueError("session belongs to one animal")
        by_id[cid]=c;groups[sid].append(c);animals.add(animal)
    if set(groups)!=set(sessions) or len(animals)!=3:
        raise ValueError("all expected sessions and3 animals")
    for sid,cs in groups.items():
        s=sessions[sid]
        for key in ("n_calibration", "n_development", "n_test", "units"):
            core.integer(s[key], 1)
        if s["n_calibration"]<16 or s["n_development"]<8 or s["n_test"]<10:
            raise ValueError("session support quota")
        order=s["test_case_order"]
        if (type(order) is not list or len(order)!=len(set(order)) or len(order)!=s["n_test"]
                or set(order)!={c["case_id"] for c in cs}
                or order!=[c["case_id"] for c in sorted(cs,key=lambda x:x["split_rank"])]
                or len({c["split_rank"] for c in cs})!=len(cs)):
            raise ValueError("complete trial-level expected partition")
    core.integer(owner["input_trial_count"], 1)
    core.integer(owner["required_query_count"], 1)
    dispositions=owner["all_trial_dispositions"]
    if (owner.get("condition") not in core.CONDITIONS
            or type(owner.get("participant_packet_sha256")) is not str
            or not re.fullmatch("[0-9a-f]{64}",owner["participant_packet_sha256"])
            or owner.get("target_manifest_sha256")!=core.digest(cases)
            or owner.get("split_manifest_sha256")!=core.digest([{k:d[k] for k in
                ("case_id","session_id","split","support_exposed","required_query")} for d in dispositions])):
        raise ValueError("whole packet, split, target and support-condition binding")
    if len(dispositions)!=owner["input_trial_count"] or len({x["case_id"] for x in dispositions})!=len(dispositions):
        raise ValueError("every source trial has one disposition")
    selected={x["case_id"] for x in dispositions if x["required_query"]}
    if selected!=set(by_id) or owner["required_query_count"]!=len(by_id):
        raise ValueError("whole protected partition and query coverage")
    for d in dispositions:
        if d["split"] not in ("calibration", "development", "test") or type(d["required_query"]) is not bool:
            raise ValueError("exact trial partition disposition")
        if d["required_query"] != (d["split"] == "test"):
            raise ValueError("no silent protected-case removal")
        if d["required_query"]:
            c=by_id[d["case_id"]]
            if d["session_id"]!=c["session_id"] or d["deposited_target_owner_only"]!=c["count"]:
                raise ValueError("target provenance joins whole trial disposition")
    if not owner["invented"]:
        if (len(sessions)!=core.FULL_SCOPE["sessions"] or owner["input_trial_count"]!=core.FULL_SCOPE["trials"]
                or owner.get("original_scope")!=core.FULL_SCOPE
                or owner.get("accepted_source_binding")!=profile.BOUND_SOURCE):
            raise ValueError("full available-release binding")
    return by_id,groups


def _nonnegative_mean(values):
    """Mean of a nonempty collection of finite, nonnegative metric terms.

    Sum in units of the largest term and divide once before restoring units.
    Dividing each original term first can overflow fsum through rounding at
    the largest finite float, or erase repeated minimum-subnormal terms.
    """
    values=list(values)
    scale=max(values)
    return scale*(math.fsum(x/scale for x in values)/len(values)) if scale else 0.0


def _metrics(cases,predictions):
    n=len(cases);ys=[float(c["count"]) for c in cases]
    ps=[max(0.0,float(predictions[c["case_id"]]["count"])) for c in cases]
    errors=[p-y for p,y in zip(ps,ys)]
    scale=max(map(abs,errors))
    rmse=scale*math.sqrt(math.fsum((x/scale)**2 for x in errors)/n) if scale else 0.0
    mae=_nonnegative_mean(abs(x) for x in errors)
    mean=_nonnegative_mean(ys)
    target_norm=math.hypot(*(y-mean for y in ys))
    r2=None;r2_status="UNDEFINED_CONSTANT_TARGET"
    if target_norm:
        ratio=math.hypot(*errors)/target_norm
        squared=ratio*ratio
        if math.isfinite(squared):r2=1-squared;r2_status="DEFINED"
        else:r2_status="UNDEFINED_NUMERICAL_RANGE"
    return {"n":n,"rmse":rmse,"mae":mae,"r_squared":r2,"r_squared_status":r2_status}


def _classification(cases,predictions):
    confusion={"true_low_pred_low":0,"true_low_pred_high":0,"true_high_pred_low":0,"true_high_pred_high":0}
    losses=[];counts=Counter()
    for c in cases:
        p=predictions[c["case_id"]]["prob_high"];y=c["high"];pred=int(p>=0.5)
        counts[y]+=1;confusion[("true_high" if y else "true_low")+("_pred_high" if pred else "_pred_low")]+=1
        losses.append(-math.log(max(LOG_EPS,p if y else 1-p)))
    balanced=None
    if counts[0] and counts[1]:
        balanced=(confusion["true_low_pred_low"]/counts[0]+confusion["true_high_pred_high"]/counts[1])/2
    return {"balanced_accuracy":balanced,"balanced_accuracy_status":"DEFINED" if balanced is not None else "UNDEFINED_SINGLE_CLASS",
            "log_loss":_nonnegative_mean(losses),"log_probability_epsilon":LOG_EPS,
            "class_counts":{"low":counts[0],"high":counts[1]},"confusion":confusion}


def _validated_predictions(expected,submission):
    if type(submission) is not list:raise ValueError("prediction array required")
    errors=[];by_id={};seen=Counter();invalid=set();probability_count=0
    for i,row in enumerate(submission):
        if type(row) is not dict or set(row) not in ({"case_id","count"},{"case_id","count","prob_high"}):
            errors.append({"index":i,"reason":"CLOSED_SUBMISSION_SCHEMA"});continue
        cid=row["case_id"]
        if type(cid) is not str or cid not in expected:
            errors.append({"index":i,"reason":"UNKNOWN_CASE"});continue
        seen[cid]+=1
        if seen[cid]>1:
            errors.append({"case_id":cid,"reason":"DUPLICATE_CASE"});invalid.add(cid);continue
        if not core.finite(row["count"]):
            errors.append({"case_id":cid,"reason":"NONFINITE_OR_NONNUMERIC_COUNT"});invalid.add(cid);continue
        if "prob_high" in row and (not core.finite(row["prob_high"]) or not 0<=row["prob_high"]<=1):
            errors.append({"case_id":cid,"reason":"INVALID_PROBABILITY"});invalid.add(cid);continue
        if "prob_high" in row:probability_count+=1
        by_id[cid]=dict(row)
    for cid in invalid:by_id.pop(cid,None)
    missing=sorted(set(expected)-set(by_id))
    if missing:errors.append({"reason":"MISSING_OR_INVALID_REQUIRED_CASES","count":len(missing),"case_ids":missing})
    # Probability is optional as a complete secondary column, never cherry-picked.
    if probability_count not in (0,len(expected)):
        errors.append({"reason":"INCOMPLETE_PROBABILITY_COLUMN","submitted":probability_count,"required":len(expected)})
    return by_id,errors,probability_count


def grade_values(owner,submission):
    """Trusted-owner arithmetic kernel; public dispatch uses grade envelope."""
    expected,groups=validate_owner(owner)
    predictions,errors,pcount=_validated_predictions(expected,submission)
    base={"schema":"apcx-deposited-label-grade-v1","profile":profile.PROFILE,
          "target_kind":"deposited_Total_pulse_label","required_cases":len(expected),
          "valid_unique_cases":len(predictions),"coverage":len(predictions)/len(expected),
          "historical_selection_caveat_required":True,"physical_delivery_claim":False,
          "scientific_qualification":False,"benchmark_count_delta":0,
          "remaining_physical_primary_holds":list(core.HOLDS),"errors":errors,
          "primary_metric":None,"animal_metrics":{},"session_metrics":{},"pooled_metrics":None}
    if errors:
        base["status"]="INCOMPLETE_OR_INVALID_NO_AGGREGATE_SCORE";return base
    animals=defaultdict(list)
    for c in expected.values():animals[c["animal"]].append(c)
    am={a:_metrics(cs,predictions) for a,cs in sorted(animals.items())}
    sm={s:_metrics(cs,predictions) for s,cs in sorted(groups.items())}
    pooled=_metrics(list(expected.values()),predictions)
    if pcount:
        for a,cs in animals.items():am[a]["label_category"]=_classification(cs,predictions)
        for s,cs in groups.items():sm[s]["label_category"]=_classification(cs,predictions)
        pooled["label_category"]=_classification(list(expected.values()),predictions)
    primary=_nonnegative_mean(x["rmse"] for x in am.values())
    if not math.isfinite(primary):
        base["status"]="NUMERICAL_RANGE_NO_AGGREGATE_SCORE";return base
    base.update(status="COMPLETE_DEPOSITED_LABEL_SCORE_ONLY",primary_metric={"name":"animal_macro_rmse","value":primary},
                animal_macro_mae=_nonnegative_mean(x["mae"] for x in am.values()),
                animal_metrics=am,session_metrics=sm,pooled_metrics=pooled,
                clipping_policy="Finite negative counts clipped at0; no data-derived upper clip.",
                inference_scope="Conditional within released sessions/animals, not original chronology, physical delivery or population generalization.")
    return base


def grade(owner, envelope):
    """Participant-facing submission schema; no cross-profile/condition scoring."""
    expected,_=validate_owner(owner)
    keys={"schema","profile","profile_contract_sha256","profile_document_sha256","condition","participant_packet_sha256","records"}
    if (type(envelope) is not dict or set(envelope)!=keys
            or envelope.get("schema")!="apcx-deposited-label-submission-v1"
            or envelope.get("profile")!=profile.PROFILE
            or envelope.get("profile_contract_sha256")!=owner["profile_contract_sha256"]
            or envelope.get("profile_document_sha256")!=owner["profile_document_sha256"]
            or envelope.get("condition")!=owner["condition"]
            or envelope.get("participant_packet_sha256")!=owner["participant_packet_sha256"]):
        return {"schema":"apcx-deposited-label-grade-v1","profile":profile.PROFILE,
            "status":"INVALID_SUBMISSION_ENVELOPE_NO_AGGREGATE_SCORE","primary_metric":None,
            "required_cases":len(expected),"valid_unique_cases":0,"coverage":0,
            "errors":[{"reason":"EXACT_PROFILE_PACKET_CONDITION_BINDING_REQUIRED"}],
            "scientific_qualification":False,"benchmark_count_delta":0,
            "remaining_physical_primary_holds":list(core.HOLDS)}
    result=grade_values(owner,envelope["records"])
    result.update(condition=owner["condition"],profile_contract_sha256=owner["profile_contract_sha256"],profile_document_sha256=owner["profile_document_sha256"],
        participant_packet_sha256=owner["participant_packet_sha256"],
        split_manifest_sha256=owner["split_manifest_sha256"],target_manifest_sha256=owner["target_manifest_sha256"])
    return result


def _percentile(values,q):
    values=sorted(values);x=(len(values)-1)*q;i=math.floor(x);j=math.ceil(x)
    weight=x-i
    # Scale this signed weighted mean too: preweighting subnormal endpoints
    # can erase a nonzero interval even when every bootstrap draw agrees.
    scale=max(abs(values[i]),abs(values[j]))
    return scale*math.fsum((values[i]/scale*(1-weight),values[j]/scale*weight)) if scale else 0.0


def paired_conditional_bootstrap(owner,first,second,replicates=BOOTSTRAP_REPLICATES,seed=BOOTSTRAP_SEED):
    """Paired whole-trial bootstrap within the fixed random-holdout sessions.

    Each session contributes its original n_test in each draw. No animal, unit or
    time-bin is independently resampled. Exchangeability within a released
    session is an explicit approximation; unknown original chronology prevents
    interpreting this as an authenticated chronological block bootstrap.
    """
    if type(replicates) is not int or not 1<=replicates<=5000 or type(seed) is not int:
        raise ValueError("fixed finite bootstrap specification")
    a=grade_values(owner,first);b=grade_values(owner,second)
    if a["primary_metric"] is None or b["primary_metric"] is None:
        return {"status":"NO_PAIRED_UNCERTAINTY_INCOMPLETE_SUBMISSION","replicates":0}
    expected,groups=validate_owner(owner)
    pa={x["case_id"]:x for x in first};pb={x["case_id"]:x for x in second}
    rng=random.Random(seed);differences=[]
    for _ in range(replicates):
        sampled=defaultdict(list)
        for sid in sorted(groups):
            cases=sorted(groups[sid],key=lambda x:x["case_id"])
            for _ in cases:sampled[cases[0]["animal"]].append(cases[rng.randrange(len(cases))])
        ra=_nonnegative_mean(_metrics(cs,pa)["rmse"] for cs in sampled.values())
        rb=_nonnegative_mean(_metrics(cs,pb)["rmse"] for cs in sampled.values())
        differences.append(ra-rb)
    return {"status":"CONDITIONAL_RELEASE_TRIAL_BOOTSTRAP_ONLY","seed":seed,"replicates":replicates,
            "paired_metric":"first_minus_second_animal_macro_rmse",
            "observed_difference":a["primary_metric"]["value"]-b["primary_metric"]["value"],
            "percentile_95_interval":[_percentile(differences,.025),_percentile(differences,.975)],
            "all_draws_finite":all(math.isfinite(x) for x in differences),
            "resampling_unit":"whole trial within fixed session; same draw for both methods",
            "population_confidence_interval":False,"chronological_block_claim":False,
            "limitation":"Conditional exchangeability approximation; original chronology and exclusions unavailable."}
