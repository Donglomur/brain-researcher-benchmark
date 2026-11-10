"""Prespecified robustness-control source; never run during this build.

This is source for separately authorized complete controlled campaigns. It does
not call candidate callbacks, score labels, manufacture a null distribution, or
turn diagnostics into new benchmark IDs. Every returned control needs fresh full
source/process/reference qualification; no main-campaign score is overwritten.
"""
import copy,hashlib,random
from .io import need,canonical,identity
from .contract import require_deployment

def stable_shuffle(values,seed,context):
    need(type(seed)is int,"Explicit prespecified diagnostic seed")
    digest=hashlib.sha256(canonical({"seed":seed,"context":context})).digest()
    values=list(values);random.Random(int.from_bytes(digest,"big")).shuffle(values);return values

def control_fold(fold,control,seed):
    require_deployment();need(control in("V27","V28"),"Prespecified fold-level control")
    out=copy.deepcopy(fold);train=out["train"]
    if control=="V27":
        import math
        constant=[math.fsum(r["views"]["SIGNAL"][j]for r in train)/len(train)for j in range(60)]
        for r in train+out["query"]:
            r["views"]["SIGNAL"]=constant.copy()
            r["views"]["SIGNAL_NUISANCE"]=constant+r["views"]["NUISANCE"]
        evidence={"training_only_constant":constant,"query_labels_accessed":False}
    else:
        image_labels={}
        for row in train:
            need(image_labels.setdefault(row["image"],row["y"])==row["y"],"Physical identity/category consistency")
        names=sorted(image_labels);labels=stable_shuffle([image_labels[x]for x in names],seed,{"control":control,"outer_person":fold["person"],"outer_half":fold["half"]})
        remap=dict(zip(names,labels))
        for row in train:row["y"]=remap[row["image"]]
        evidence={"training_image_labels":remap,"image_label_counts_preserved":True,"query_labels_changed":False}
    out["diagnostic"]={"control":control,"seed":seed,"evidence":evidence,"source_main_panel":fold["source_panel"],
                       "inferential_p_value":None,"complete_new_procedures_required":True}
    return out

def alignment_control(observations,seed):
    require_deployment();out=copy.deepcopy(observations);groups={}
    for i,r in enumerate(out["rows"]):
        key=(r["person"],r["run"],*r["stratum"])
        groups.setdefault(key,[]).append(i)
    evidence=[]
    for key,indices in sorted(groups.items()):
        shuffled=stable_shuffle(indices,seed,{"control":"V29","group":key})
        # The same permutation moves both neural windows together. No label is
        # consulted, and observed identity/nuisance/target joins stay untouched.
        original=[copy.deepcopy(out["rows"][j]["views"])for j in shuffled]
        for i,views in zip(indices,original):
            row=out["rows"][i]
            for arm in("SIGNAL","PRE"):
                row["views"][arm]=views[arm]
                row["views"][arm+"_NUISANCE"]=views[arm]+row["views"]["NUISANCE"]
        evidence.append({"group":list(key),"size":len(indices),"permutable":len(indices)>1,"selected_permutation":shuffled})
    out["diagnostic"]={"control":"V29","seed":seed,"groups":evidence,"original_panel":identity(canonical(observations)),
                       "query_labels_consulted":False,"randomization_null_qualified":False,"p_value":None}
    return out

def controlled_campaign_plan(main_plan,control,seed):
    require_deployment();need(control in("V27","V28","V29","V30"),"Retained complete diagnostic family")
    return {"schema":"n097-full-diagnostic-campaign-v1","control":control,"seed":seed,"main_plan":main_plan,
            "candidate_jobs":3960,"reference_jobs":1650,"overwrite_main_results":False,
            "required":"Fresh complete controlled observation/fold views, source-specific learner policies, original reference panels, private target-panel joins, full closure, all H01-H05 and costs. No favorable subgroup or reused main references.",
            "authorized":False,"scientific_execution_gate":"Separate source/cohort/diagnostic selection and native qualification required"}
