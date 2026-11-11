"""Protected finite-panel reports; fixed and candidate comparisons are separate."""
from collections import defaultdict
from .io import *
from .metrics import n085,paired_contrast,metric_equal,n085_contrast
from .constants import *
from .qualification import status

def joined(admitted,targets):
    # Targets are supplied only by collector.target_last after global admission.
    need(targets["rows"] and len(set(targets["people"]))==18,"target_people")
    by=defaultdict(list)
    for bank in ("candidate","reference"):
        for jid,r in admitted[bank].items():
            i=r["identity"];gold=targets["rows"][targets["job_target_keys"][jid]];lookup={x["id"]:x for x in gold};need(set(lookup)==set(r["probabilities"]) and len(lookup)==len(gold),"protected_query_target_join")
            key=(i["task"],i["representation"],i["mode"],i["context"],i["method"],i["arm"])
            by[key].extend({**lookup[rid],"p":p} for rid,p in r["probabilities"].items())
    return by

def shuffled_evidence(groups,admitted,prefix,context,people,J,control_evidence):
    """Every family's signed diagnostic on the existing equal-cell estimand."""
    scope=prefix+(context,)
    def matches(identity):return tuple(identity[k] for k in ("task","representation","mode","context"))==scope
    unavailable=[x for name in ("diagnostic_unavailable","secondary_context_unavailable") for x in control_evidence.get(name,[]) if matches(x["identity"])]
    observations=[x for x in control_evidence.get("actual_job_control_observations",[]) if matches(x["identity"]) and x["identity"]["arm"]=="COVARIATES_SHUFFLED_E"]
    methods={"candidate","R_LINEAR_NESTED_V1"}|{k[4] for k in groups if k[:4]==scope}|{x["identity"]["method"] for x in unavailable}
    result={}
    for method in sorted(methods):
        arms={arm:groups.get(scope+(method,arm),[]) for arm in ("COVARIATES","PLUS_EEG","COVARIATES_SHUFFLED_E")}
        custody=[]
        for bank in ("candidate","reference"):
            for jid,record in admitted[bank].items():
                if matches(record["identity"]) and record["identity"]["method"]==method:
                    custody.append({"job_id":jid,"bank":bank,"identity":record["identity"],"original_record_sha256":record["receipt_sha256"]})
        custody.sort(key=lambda x:(x["bank"],x["job_id"]))
        absent=[arm for arm,rows in arms.items() if not rows]
        record={"method":method,"status":"required_unscorable" if absent else "computed_unqualified","missing_prediction_arms":absent,
                "source_custody":{"records":custody,"sha256":digest(custody)},
                "original_unavailable_dispositions":[x for x in unavailable if x["identity"]["method"]==method],
                "original_effectiveness_observations":[x for x in observations if x["identity"]["method"]==method],
                "baseline_minus_shuffled":None,"shuffled_minus_aligned":None,"ranked_score":None,
                "interpretation":"Prespecified alignment diagnostic only; no favorable-control ranking, exchangeable conditional null or neural-origin claim. D_R is unchanged."}
        if not absent:
            # First loss(COVARIATES)-loss(SHUFFLED); second loss(SHUFFLED)-loss(PLUS_EEG).
            # Both retain full signed matrices, equal-person/item support and null semantics.
            record["baseline_minus_shuffled"]=paired_contrast(arms["COVARIATES"],arms["COVARIATES_SHUFFLED_E"],people,J)
            record["shuffled_minus_aligned"]=paired_contrast(arms["COVARIATES_SHUFFLED_E"],arms["PLUS_EEG"],people,J)
        result[method]=record
    return result

def score(admitted,targets,authority,control_evidence):
    need(admitted["protected_query_targets_opened"] and admitted["target_attempt"]["outcome"]=="read_and_bound","scorer_target_barrier");groups=joined(admitted,targets);people=targets["people"];J=targets["J"];reports=[]
    for task,rep,mode in authority.review["selected"]:
        prefix=(task,rep,mode)
        if task=="NEURAL-085":
            arms={arm:n085(groups[prefix+("sentence","candidate",arm)],people,J) for arm in ARMS[task]};ref={}
            for method in sorted({k[4] for k in groups if k[:3]==prefix and k[4]!="candidate"}):ref[method]={arm:n085(groups[prefix+("sentence",method,arm)],people,J) for arm in ARMS[task] if prefix+("sentence",method,arm) in groups}
            c=arms["NTGE"]["matched"]["log_loss"];base=arms["NTG"]["matched"]["log_loss"];fixed=ref["R_LINEAR_NESTED_V1"];f=fixed["NTGE"]["matched"]["log_loss"];b=fixed["NTG"]["matched"]["log_loss"];delta=lambda x,y:None if x is None or y is None else x-y;q=status(authority,task,rep,mode,c is not None,control_evidence)
            report={"task":task,"representation":rep,"mode":mode,"primary_metric":"N085_MATCHED_NTGE_LOG_LOSS","raw_primary_loss":c,"primary_score":-c if c is not None and q["qualified_metric"] else None,"by_arm":arms,"fixed_reference_by_arm":ref,"same_information_fixed_minus_candidate":delta(f,c),"independent_fixed_feature_procedure_contrast":delta(b,f),"candidate_self_contrast_descriptive":delta(base,c),"cross_method_cross_information_reference_base_minus_candidate_plus":delta(b,c),"qualification":q,"paired_differences":{
                "same_information_fixed_minus_candidate":n085_contrast(fixed['NTGE'],arms['NTGE'],people,J),
                "independent_fixed_feature_procedure":n085_contrast(fixed['NTG'],fixed['NTGE'],people,J),
                "candidate_self_descriptive":n085_contrast(arms['NTG'],arms['NTGE'],people,J),
                "cross_method_cross_information":n085_contrast(fixed['NTG'],arms['NTGE'],people,J)}}
        else:
            contexts={}
            for context in CONTEXTS:
                def rows(method,arm):return groups[prefix+(context,method,arm)]
                fixed=paired_contrast(rows("R_LINEAR_NESTED_V1","COVARIATES"),rows("R_LINEAR_NESTED_V1","PLUS_EEG"),people,J);candidate=paired_contrast(rows("candidate","COVARIATES"),rows("candidate","PLUS_EEG"),people,J)
                methods=sorted({k[4] for k in groups if k[:4]==prefix+(context,) and k[4] not in ("candidate","R_LINEAR_NESTED_V1") and prefix+(context,k[4],"COVARIATES") in groups and prefix+(context,k[4],"PLUS_EEG") in groups})
                contexts[context]={"D_R":fixed,"D_C":candidate,"same_information_method_contrast":None if fixed["plus_loss"]is None or candidate["plus_loss"]is None else fixed["plus_loss"]-candidate["plus_loss"],"other_references":{method:paired_contrast(rows(method,"COVARIATES"),rows(method,"PLUS_EEG"),people,J) for method in methods}}
                contexts[context]["alignment_shuffle"]=shuffled_evidence(groups,admitted,prefix,context,people,J,control_evidence)
            q=status(authority,task,rep,mode,contexts["FFD"]["D_R"]["complete_support"],control_evidence,False);report={"task":task,"representation":rep,"mode":mode,"primary_metric":"N086_EVIDENCE_GROUNDED_INVESTIGATION","primary_score":None,"primary_context":"FFD","contexts":contexts,"qualification":q,"requires_separate_executable_investigation":True}
        report['mandatory_strata']={}
        main=groups[prefix+('sentence','candidate','NTGE')] if task=='NEURAL-085' else groups[prefix+('FFD','candidate','PLUS_EEG')]
        strata={'first':[r for r in main if r.get('repetition_ordinal')==0],'later':[r for r in main if isinstance(r.get('repetition_ordinal'),int) and r['repetition_ordinal']>0]}
        strata.update({f'block_{b:02d}':[r for r in main if r.get('block')==b] for b in range(14)})
        edges=(0,1,2,4,8,16,float('inf'))
        for lo,hi in zip(edges,edges[1:]):strata[f'duration_{lo}_{hi}_seconds']=[r for r in main if finite(r.get('duration_seconds')) and lo<=r['duration_seconds']<hi]
        strata['duration_missing']=[r for r in main if not finite(r.get('duration_seconds'))]
        for name,rows0 in strata.items():
            if task=='NEURAL-085':report['mandatory_strata'][name]=n085(rows0,people,J)
            else:
                # Descriptive subset counts only; full primary D is never replaced
                # by a conveniently supported subset or independently re-fit model.
                report['mandatory_strata'][name]={'query_word_occurrences':len(rows0),'person_item_cells':len({(r['person'],r['item']) for r in rows0}),'outcome_selected':False,'not_primary_replacement':True}
        report["evidence_id"]=digest(report);reports.append(report)
    return {"schema":"zuco2-safe-evidence-v1","reports":reports,"control_evidence":control_evidence,"scope":{"people":18,"sessions":18,"source_containers":36,"presentations":13302},"prediction_campaign_sealed":True,"query_labels_or_answers_included":False,"source_custody_sha256":digest({"plan":admitted["plan_sha256"],"outer":admitted["original_outer_receipt_sha256"]}),"inference_limitations":["fixed chronology and concurrent task screen","source-native task-wide preprocessing","public/pretraining exposure","fixed-prediction descriptive crossed uncertainty"]}

def safe_projection(report):
    # Remove class-specific per-item cells (which can reveal a row label/probability).
    # Retain full class-averaged 18xJ paired matrices needed to independently recompute uncertainty.
    import copy
    out=copy.deepcopy(report)
    def clean(x):
        if isinstance(x,dict):
            for k in list(x):
                if k in ("cells","word_details","class_occurrences"):del x[k]
                else:clean(x[k])
        elif isinstance(x,list):
            for v in x:clean(v)
    clean(out);out["evidence_id"]=digest(out);return out
