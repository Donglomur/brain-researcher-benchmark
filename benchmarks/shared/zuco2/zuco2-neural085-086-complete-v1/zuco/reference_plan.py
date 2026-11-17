"""Full immutable reference/control coordinate specification, distinct from task counts."""
import copy
from .io import digest,need
from .reference import required

def methods(rep):
    ordinary=list(required(rep));controls=["R_MASK_ONLY","R_DURATION_COUNT","R_LABEL_SHUFFLE","R_OCULAR"]
    if rep in ("raw_waveform","cleaned_waveform"):controls += ["R_PHASE_INDEPENDENT","R_PHASE_COMMON","R_EOG_RESIDUAL"]
    return ordinary,controls

def expand(participant_plan,reference_source_sha,limits):
    result=[]
    for j in participant_plan["jobs"]:
        ordinary,controls=methods(j["identity"]["representation"])
        for method in ordinary+controls:
            i=copy.deepcopy(j["identity"]);i.update(role="reference" if method in ordinary else "control",method=method,programme_sha256=reference_source_sha);key=digest(i)
            result.append({"id":key,"identity":i,"private_person":j["private_person"],"source_sha256":reference_source_sha,"limits":copy.deepcopy(limits),"paired_participant_job":j["id"],"source_capability":method,"source_disposition":j["source_disposition"]})
    need(len({x["id"] for x in result})==len(result),"reference_control_coordinate_collision");return result
