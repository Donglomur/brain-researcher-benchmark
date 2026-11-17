"""Strict wire/object validation; qualified scientific shapes are separate from JSON validity."""
from .io import exact,need,descriptor,finite
from .constants import *
OBJECTS=("SourceClosure","CohortEventManifest","OverlapManifest","RepresentationABI","SplitPlan","BudgetSpec","ParticipantProgram","FitRequest","SealedState","QueryView","InferRequest","PredictionProduct","AnalysisTrace","ProcessReceipt","ReferenceBank","CollectedCampaign","ProtectedTargets","SafeEvidenceReport","InvestigationRequest","InvestigationProduct","RubricRecord","FinalReport")
def envelope(obj,kind):
    exact(obj,["schema","kind","identity","body"]);need(obj["schema"]=="zuco2-object-v1" and obj["kind"]==kind and kind in OBJECTS,"object_kind");need(type(obj["identity"])is dict and type(obj["body"])is dict,"object_maps");return obj["body"]
def identity(i):
    exact(i,["task","person_token","item_fold","context","arm","representation","mode","seed","programme_sha256","source_sha256","split_sha256","information_set","generation","role","method"])
    need(i["task"] in ARMS and i["arm"] in ARMS[i["task"]] and i["representation"] in REPRESENTATIONS and i["mode"] in MODES,"job_coordinates")
    need(type(i["item_fold"])is int and 0<=i["item_fold"]<5 and i["seed"]==0 and type(i["seed"])is int,"fold_seed")
    need(i["context"] in (("sentence",) if i["task"]=="NEURAL-085" else CONTEXTS) and i["information_set"]==INFORMATION_SET,"context_information")
    for k in ("programme_sha256","source_sha256","split_sha256"):
        need(type(i[k])is str and len(i[k])==64 and set(i[k])<=set("0123456789abcdef"),"identity_hash",k)
    need(i["role"] in ("participant","reference","control") and type(i["method"])is str and i["method"],"role_method");return i
def prediction(obj,expected_identity,query_ids,state_sha):
    exact(obj,["identity","state_sha256","probabilities","analysis_trace"]);need(obj["identity"]==expected_identity and obj["state_sha256"]==state_sha,"prediction_lineage");need(type(obj["probabilities"])is list,"probability_list")
    out={}
    for row in obj["probabilities"]:
        exact(row,["id","p_tsr"]);need(type(row["id"])is str and row["id"] not in out,"duplicate_prediction");need(finite(row["p_tsr"]) and 0<=row["p_tsr"]<=1,"finite_probability");out[row["id"]]=row["p_tsr"]
    need(set(out)==set(query_ids) and len(out)==len(query_ids),"full_query_census");need(type(obj["analysis_trace"])is list,"analysis_trace");return out
def rubric(rows):
    need(type(rows)is list and len(rows)==6,"rubric_dimensions")
    for i,r in enumerate(rows,1):
        exact(r,["dimension","ratings","adjudicator","evidence_ids"]);need(r["dimension"]==f"R{i}" and type(r["ratings"])is list and len(r["ratings"])==2,"rubric_row")
        seen=set()
        for a in r["ratings"]+([] if r["adjudicator"]is None else [r["adjudicator"]]):
            exact(a,["rater_id","value","rationale","conflict_disclosure"]);need(type(a["value"])is int and 0<=a["value"]<=2 and type(a["rater_id"])is str and a["rater_id"] not in seen,"independent_rater_value");seen.add(a["rater_id"]);need(type(a["rationale"])is str and a["rationale"],"rating_rationale")
        disagree=r["ratings"][0]["value"]!=r["ratings"][1]["value"];need(disagree==(r["adjudicator"]is not None),"adjudication_required");need(type(r["evidence_ids"])is list and r["evidence_ids"],"rubric_evidence")
    return rows
