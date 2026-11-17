"""External scientific selection is explicit; authoring/design acceptance cannot enable it."""
import time,copy
from pathlib import Path
from .io import *
from .constants import *
def condition(value):
    need(type(value)is list and len(value)==3,"condition_tuple")
    task,representation,mode=value
    need(all(type(x)is str for x in value) and task in ARMS and representation in REPRESENTATIONS and mode in MODES,"condition_coordinates")
    return value

def gate_scope(value):
    if value=="all":return value
    need(type(value)is list and value,"gate_condition_scope")
    for item in value:condition(item)
    need(len({tuple(item) for item in value})==len(value),"duplicate_gate_condition")
    return value

def covers(value,selected):
    condition(selected);gate_scope(value)
    return value=="all" or selected in value

class Authority:
    def __init__(self,path,expected=None):
        raw=read(path,8*1024**2,expected);self.pin={"path":str(Path(path).absolute()),**pin(raw)};self.review=decode(raw)
        required=("schema","scientific_execution_authorized","selection_id","created_before_outer_exposure","programme_pin","runtime_manifest_pin","output_root","deadline_monotonic","budget","job_limits","selected","source","qualification_records","OCI_profile","reference_source","raters","original_prior_attempts","whole_campaign_reservation","mode_policy","external_driver_receipt")
        exact(self.review,required);r=self.review;need(r["schema"]=="zuco2-execution-selection-v1" and r["scientific_execution_authorized"]is True,"execution_not_authorized","BUILD ONLY/design review is not scientific authority")
        need(r["created_before_outer_exposure"]is True and r["mode_policy"]=="global_freeze_fresh_job_no_feedback_v1","global_exposure_selection");need(type(r["selected"])is list and r["selected"],"conditions")
        for selected in r["selected"]:condition(selected)
        need(len({tuple(x) for x in r["selected"]})==len(r["selected"]),"duplicate_selected_condition")
        need(r["budget"]["deadline_monotonic"]==r["deadline_monotonic"],"single_original_deadline");self.guard();self.gates={}
        for g in r["qualification_records"]:
            descriptor(g);x=decode(read(g["path"],1024**2,g,self.guard));exact(x,["gate","status","source_sha256","programme_sha256","runtime_sha256","evidence","reviewer","condition"]);need(x["gate"] in GATES and x["gate"] not in self.gates and x["status"]in("open","qualified","structurally_unresolved"),"gate_record")
            need(x["programme_sha256"]==r["programme_pin"]["sha256"] and x["runtime_sha256"]==r["runtime_manifest_pin"]["sha256"],"qualification_current_source")
            need(type(x["evidence"])is list and type(x["reviewer"])is str and x["reviewer"] and (x["status"]!="qualified" or x["evidence"]),"qualification_requires_original_evidence_and_reviewer")
            for d in x["evidence"]:descriptor(d);read(d["path"],d["bytes"],d,self.guard)
            gate_scope(x["condition"]);self.gates[x["gate"]]=x
        need(set(self.gates)==set(GATES),"complete_gate_ledger");need(self.gates["G14"]["status"]!="qualified","causal_gate_structural")
        need(r["whole_campaign_reservation"]["complete_grid"]is True and r["whole_campaign_reservation"]["previous_attempts"]==r["original_prior_attempts"],"campaign_reservation")
    def guard(self):need(time.monotonic()<self.review["deadline_monotonic"],"selected_deadline")
    def require_inputs(self):
        for k in ("G01","G02","G03","G04","G05","G06","G10","G13"):
            need(self.gates[k]["status"]=="qualified" and all(covers(self.gates[k]["condition"],s) for s in self.review["selected"]),"source_gate_open",k)
    def qualify_metric(self,task,representation,mode):
        selected=condition([task,representation,mode]);need(selected in self.review["selected"],"metric_condition_not_selected")
        required={"G01","G02","G03","G04","G05","G06","G10","G13","G15","G16","G17","G18","G19","G20","G22","G23","G25"}
        required.add("G11" if task=="NEURAL-085" else "G12")
        if task=="NEURAL-086":required.add("G24")
        if representation in ("released_summary","band_spatial"):required.add("G08")
        else:required.add("G07")
        return sorted(g for g in required if self.gates[g]["status"]!="qualified" or not covers(self.gates[g]["condition"],selected))
