"""Whole production campaign driver; only explicit scientific selection can call it."""
import argparse,copy,resource,time
from pathlib import Path
from zuco.io import *
from zuco.authority import Authority
from zuco.budget import Ledger
from zuco.programme import admit
from zuco.panel import load_source
from zuco.engine import Engine
from zuco.splits import plan
from zuco.reference_plan import expand

def main(request_path,output):
    request=decode(read(request_path,1024**2));authority=Authority(request["review"]["path"],request["review"]);authority.require_inputs();review=authority.review;ledger=Ledger(review["budget"]);programme=admit(request["program"],ledger.guard);need(programme["manifest_pin"]==review["programme_pin"],"selected_programme_raw_bytes")
    need(all(mode==programme["manifest"]["mode"] for task,rep,mode in review["selected"]),"programme_mode_selection")
    runtime=decode(read(review["runtime_manifest_pin"]["path"],8*1024**2,review["runtime_manifest_pin"],ledger.guard));runtime_root=Path(review["runtime_manifest_pin"]["path"]).parent
    for d in runtime["files"]:read(below(runtime_root,d["path"]),d["bytes"],d,ledger.guard)
    source=review["reference_source"];need(source["files"]==runtime["files"] and Path(source["root"]).absolute()==runtime_root.absolute(),"independent_reference_source_closure")
    reference={"manifest":{"entry":["python3","reference_worker.py"]},"files":source["files"],"source_root":str(runtime_root),"source_bytes":sum(d["bytes"] for d in source["files"]),"manifest_pin":review["runtime_manifest_pin"]}
    panel,abi=load_source(review["source"],ledger)
    for g in authority.gates.values():need(g["source_sha256"]==panel["source_sha256"],"gate_source_binding",g["gate"])
    root=Path(output)/"campaign";engine=Engine(root,authority,ledger,programme,reference);selected=plan(panel,review["selected"],engine.key,programme["manifest_pin"]["sha256"])
    selected.update(runtime_source_sha256=digest(runtime["files"]),driver_request_sha256=digest(request))
    for j in selected["jobs"]:j.update(limits=copy.deepcopy(review["job_limits"]),source_sha256=digest(programme["files"]))
    references=expand(selected,digest(reference["files"]),review["job_limits"]);reservation=review["whole_campaign_reservation"]
    need(reservation["participant_chains"]==len(selected["jobs"]) and reservation["reference_control_chains"]==len(references),"full_grid_reservation_count")
    active=[(j,programme) for j in selected['jobs'] if j.get('source_disposition')!='required_unscorable_secondary_context']+[(j,reference) for j in references if j.get('source_disposition')!='required_unscorable_secondary_context']
    # Complete planned ceilings are checked before the first worker. Optional
    # diagnostic gaps do not buy a cheaper unplanned campaign in advance.
    planned_cpu=sum(2*j['limits']['cpu_seconds'] for j,p in active)+review['budget']['controller_cpu_reserve']
    views=reservation['view_bytes_per_chain'];need(type(views)is int and views>0,'complete_view_reservation')
    planned_storage=sum(2*p['source_bytes']+2*(2*j['limits']['output_bytes']+4*j['limits']['stream_bytes']+4*j['limits']['receipt_bytes'])+views for j,p in active)
    need(ledger.cpu+planned_cpu<=ledger.spec['cpu_seconds'],'complete_grid_CPU_ceiling')
    need(ledger.bytes+planned_storage<=ledger.spec['storage_bytes'],'complete_grid_storage_ceiling')
    selected['complete_planned_ceiling']={'worker_CPU_seconds':planned_cpu,'source_output_view_bytes':planned_storage,'view_bytes_per_chain':views,'chains':len(active),'includes_all_original_prior_costs':review['original_prior_attempts']}
    result=engine.run(selected,references,panel);write(Path(output)/"result.json",{"campaign_pin":{**pin(read(root/"CAMPAIGN.json",review["budget"]["storage_bytes"])),"path":str(root/"CAMPAIGN.json")},"status":"closed" if result["original_failure"]is None else "failed","all_scientific_gates_external":True})
if __name__=="__main__":
    a=argparse.ArgumentParser();a.add_argument("--request",required=True);a.add_argument("--output",required=True);args=a.parse_args();main(args.request,args.output)
