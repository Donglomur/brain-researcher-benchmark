"""Operator installation entrypoints. The distributed installation is disabled."""
import json
import dataclasses
from pathlib import Path
from .wire import need,canonical,sha
from .basis import basis,EXPECTED,authenticate_adapters
from .runtime import construct
from .runtime import _qualification
from .authority import Authority

def status():
    return {"task_id":"PAPER-ROOT-ADD-020","runtime_adapters_source_present":True,
            "execution_enabled":False,"physically_qualified":False,"scientifically_qualified":False,
            "new_canonical_ids":0,"final_acceptance_requires_external_host_terminal_observation":True}

def run_full_study(envelope,public_key,contract,admission,mapping,*,credential_fd=None):
    """Future operator call; no externally supplied scientific executor callback.

    This function cannot attest its own eventual exit. The complete typed result
    remains provisional until the separate terminal observer admits its seal,
    actual natural host/descendant closure and the unchanged original deadline.
    """
    bound=construct(envelope,public_key,contract,admission,mapping,credential_fd=credential_fd)
    d=bound.runtime.authority.document
    plan=basis("programme").build_plan(contract);plan["implementation_digest"]=EXPECTED
    need(plan["programme_digest"]==d["programme_digest"] and len(plan["phases"])==23786,
         "Exact whole-programme source graph differs")
    result=basis("controller").execute_plan(plan,bound,bound.observe,d["profile"],origin_ns=d["origin_ns"])
    bound.runtime.authority._clock()
    return {"schema":"paper020_provisional_host_result_v1","status":"provisional_pending_external_natural_exit",
            "result":result,"result_digest":sha(canonical(result)),"origin_ns":d["origin_ns"],
            "deadline_ns":d["deadline_ns"],"host_identity":bound.monitor.host.identity,
            "source_qualification_claim":False,"scientific_qualification_claim":False}

def accept_external_terminal(envelope,public_key,provisional):
    """Run in a distinct qualified observer process after natural host exit.

    The accountant independently joins the actual published result seal. Passing
    a JSON success flag or an arbitrary caller-computed digest cannot manufacture
    natural host/child completion or make the physical resource profile pass.
    """
    from .host_observer import HostQualification,ExternalHostTerminalObserver
    from .process_control import SubprocessCommandTransport
    authority=Authority(envelope,public_key);d=authority.document
    authenticate_adapters(d)
    _validate_complete_provisional(provisional,d)
    value=dict(d["host_accounting"]);value["process"]=_qualification(value["process"])
    qualification=HostQualification(**value)
    transport=SubprocessCommandTransport(qualification.process,authority.process_qualification)
    observer=ExternalHostTerminalObserver(qualification,transport,authority.process_qualification,complete_profile=d["terminal_profile"])
    evidence=observer.observe_terminal(provisional["host_identity"],d["origin_ns"],d["deadline_ns"],sha(canonical(provisional)))
    need(evidence.natural_complete is True and evidence.all_descendants_closed is True
         and type(evidence.exit_code) is int and evidence.exit_code==0 and not evidence.failures
         and evidence.host_identity==provisional["host_identity"] and evidence.origin_ns==d["origin_ns"]
         and evidence.deadline_ns==d["deadline_ns"] and evidence.full_result_digest==sha(canonical(provisional))
         and type(evidence.host_finished_ns) is int and type(evidence.observed_ns) is int
         and provisional["result"]["finished_ns"]<=evidence.host_finished_ns<=evidence.observed_ns<d["deadline_ns"],
         "External natural-zero terminal/result/clock joins required")
    for key,value in provisional["result"]["resources"].items():
        need(type(evidence.resources.get(key)) is int and 0<=evidence.resources[key]<=d["terminal_profile"][key]
             and (key=="live_bytes" or value<=evidence.resources[key]),
             "Full terminal lifetime resources must include complete controller charges")
        # Live memory is a peak, not a lifetime counter: controller live is the
        # conservative host-peak + max(serial-worker-peak) bound. The external
        # actual simultaneous peak may be smaller; both must satisfy their
        # qualified complete profiles, without reducing lifetime I/O charges.
    return {"status":"complete_physical_execution","result":provisional["result"],
            "external_terminal_evidence":dataclasses.asdict(evidence),"scientific_qualification_claim":False}

def _validate_complete_provisional(provisional,d):
    """Complete source result semantics, separate from physical terminal proof."""
    need(type(provisional) is dict and set(provisional)=={"schema","status","result","result_digest","origin_ns",
         "deadline_ns","host_identity","source_qualification_claim","scientific_qualification_claim"},"Exact provisional envelope required")
    need(provisional["schema"]=="paper020_provisional_host_result_v1" and provisional["status"]=="provisional_pending_external_natural_exit"
         and provisional["origin_ns"]==d["origin_ns"] and provisional["deadline_ns"]==d["deadline_ns"]
         and provisional["source_qualification_claim"] is False and provisional["scientific_qualification_claim"] is False,
         "Provisional source/clock/claim envelope differs")
    result=provisional["result"]
    need(type(result) is dict and set(result)=={"status","programme_digest","origin_ns","finished_ns","phase_count",
         "resources","result","scientific_qualification_claim"},"Exact complete controller result required")
    need(provisional["result_digest"]==sha(canonical(result)) and result["status"]=="complete"
         and result["programme_digest"]==d["programme_digest"] and type(result["phase_count"]) is int and result["phase_count"]==23786
         and type(result["origin_ns"]) is int and result["origin_ns"]==d["origin_ns"]
         and type(result["finished_ns"]) is int and d["origin_ns"]<=result["finished_ns"]<d["deadline_ns"]
         and result["scientific_qualification_claim"] is False,"Whole programme/controller completion differs")
    resources=result["resources"]
    need(type(resources) is dict and set(resources)=={"read_bytes","write_bytes","retained_bytes","live_bytes"},"Complete controller resources required")
    for key,value in resources.items():need(type(value) is int and 0<=value<=d["profile"][key],"Invalid/exceeded controller resource")
    grade=result["result"]
    need(type(grade) is dict and set(grade)=={"status","prediction","reproduction","protected_reader_calls","new_canonical_ids","qualification_claim"}
         and grade["status"]=="complete" and type(grade["protected_reader_calls"]) is int and grade["protected_reader_calls"]==1
         and type(grade["new_canonical_ids"]) is int and grade["new_canonical_ids"]==0 and grade["qualification_claim"] is False,
         "Complete target-last grade envelope required")
    p=grade["prediction"];n=grade["reproduction"];programme=basis("programme")
    conditions={f"{regime}/{control}" for regime in programme.REGIMES for control in range(-1,20)}
    need(type(p) is dict and p.get("status")=="complete" and p.get("new_canonical_ids")==0
         and p.get("qualification_claim") is False and p.get("scientific_success_reward") is None
         and type(p.get("primary")) is dict and set(p["primary"])=={"A","B"}
         and type(p.get("conditions")) is dict and set(p["conditions"])==conditions,"All prediction regimes/controls required")
    for condition in p["conditions"].values():
        need(type(condition) is dict and set(condition)=={"actors","comparisons"} and set(condition["actors"])==set(programme.ACTORS)
             and set(condition["comparisons"])=={"A","B"},"All prediction actors/comparisons required")
        for actor in condition["actors"].values():
            need(type(actor) is dict and set(actor.get("case_time",{}))==set(programme.CONFIGS)
                 and set(actor.get("case_static",{}))==set(programme.CONFIGS),"All original prediction configurations required")
    diagnostics={"/".join((case,mode,v[0])) for case in programme.CONFIGS for mode in ("static","time_course") for v in programme.VARIANTS}
    need(type(n) is dict and n.get("primary_contract")=="benchmark_clarified_paired964_STA"
         and n.get("whole_paper_reproduction") is False and n.get("native_runtime_qualification_claim") is False
         and type(n.get("actors")) is dict and set(n["actors"])==set(programme.ACTORS),"Complete native grade envelope required")
    for actor in n["actors"].values():
        need(type(actor) is dict and type(actor.get("diagnostics")) is dict and set(actor["diagnostics"])==diagnostics,
             "Every complete reproduction diagnostic slot required")
    return result

if __name__=="__main__": print(json.dumps(status(),sort_keys=True))
