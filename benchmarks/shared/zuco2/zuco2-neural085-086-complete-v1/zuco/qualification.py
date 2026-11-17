"""Condition-scoped qualification preserves unavailable diagnostics and structural G14."""
from .io import need
from .constants import GATES

def status(authority,task,representation,mode,complete_support,control_evidence,rubric_qualified=False):
    holds=authority.qualify_metric(task,representation,mode)
    if not complete_support:holds.append("complete_primary_support")
    if task=="NEURAL-086" and not rubric_qualified:holds.append("independent_rubric")
    return {"condition":[task,representation,mode],"qualified_metric":not holds,"metric_holds":sorted(set(holds)),"causal_demand_identified":False,"neural_origin_identified":False,"conditional_information_identified":False,"full_task_scientifically_qualified":False,"all_gates":{k:authority.gates[k]["status"] for k in GATES},"controls":control_evidence,"secondary_unavailable_does_not_replace_primary":True}
