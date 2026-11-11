"""Complete stage-bound admission before the unchanged original child validator."""
from four_programmes.common import need,closed,encode,pin,same,integer
from four_programmes.channel import HostEvent,TerminalEvidence
from .stage_budget import extends,validate_state
from .output_contract import OutputContract

_ADMITTED=object()
STAGES=(("prepare",None),("independent_reference",None),("native_reference",None),
        ("candidate","paper_data"),("candidate","paper_data_author_code"))

class StageAdmission:
    __slots__=("lease","start","completion","budget_return","terminal","return_pin",
               "completion_pin","lease_pin","audit","job_evidence","output_contract","validation_meter","_token")
    def __init__(self,token,**fields):
        need(token is _ADMITTED,"complete actual stage closure consumer only")
        for key,value in fields.items():setattr(self,key,value)
        self._token=token
    @property
    def eligible(self):
        return self.budget_return["disposition"]=="eligible_exact_successor"

def consume_stage(event,*,bridge_meter,schemas,profile,profile_pin,clock,base,base_pin,
                  lease,lease_pin,authority_pin,scope_digest,census,previous_return,
                  controller,expected_operation,expected_condition,bridge_reservations,physical_limits,output_contract,authority_body):
    """C uses only its pre-reserved H bridge here, while programme Budget is suspended."""
    need(type(output_contract) is OutputContract,"actual whole source-compiled job output contract")
    output_contract.require_executable()
    need(pin(encode(authority_body))=={k:authority_pin[k] for k in ("bytes","sha256")} and
         authority_body["schema"]=="critical_init_root_operation_selection_v4" and
         authority_body["job_output_contract"]==output_contract.pin and
         authority_body["pre_run_subject"]==lease["authority_subject"],
         "same pre-run output contract through authority, subject, lease and actual start")
    need(type(event) is HostEvent,"actual independent original host channel")
    need(event.body["status"] in ("observed","failed"),"unknown original stage cannot restore Budget")
    result=event.body["result"]
    closed(result,("lease","start_binding","stage_completion","budget_return","physical_observation","evidence"))
    store=TerminalEvidence(event,bridge_meter)
    need(result["lease"]==lease_pin,"actual outstanding lease")
    for name,value in (("Profile",profile),("ClockBinding",clock),("BudgetState",base),("Lease",lease)):
        schemas.validate("ci",name,value,store.meter)
    need(lease["campaign_id"]==event.campaign==profile["campaign_id"]==clock["campaign_id"]==base["campaign_id"],
         "same original full campaign")
    need(lease["controller"]==controller and lease["profile"]==profile_pin and
         lease["observer_source"]==profile["observer_source"]==event.source,"exact H/C/profile lineage")
    need(1<=lease["sequence"]<=len(STAGES),"one of the five exact serial stages")
    need((expected_operation,expected_condition)==STAGES[lease["sequence"]-1] and
         (lease["operation"],lease["condition"])==(expected_operation,expected_condition),"full five-stage serial order")
    need(lease["base_state"]==base_pin and lease["base_generation"]==base["generation"] and
         lease["previous_return"]==previous_return,"actual frozen cumulative predecessor")
    need(pin(encode(base))=={k:base_pin[k] for k in ("bytes","sha256")},"exact base state original bytes")
    need(lease["census"]==profile["full_census"] and
         lease["ordered_job_ids"]==[j["id"] for j in census["jobs"] if j["operation"]==expected_operation],
         "entire immutable source census stage")
    need(len(set(lease["ordered_job_ids"]))==len(lease["ordered_job_ids"]),"no duplicate job alias")
    need(lease["original_run_deadline_ns"]==clock["run_deadline_ns"] and
         lease["original_evidence_deadline_ns"]==clock["evidence_deadline_ns"],"no renewed stage clock")
    need(lease["bootstrap_reservation"] in bridge_reservations and
         lease["terminal_channel_reservation"] in bridge_reservations,"earlier independently selected H shares")
    start=store.document(result["start_binding"],4194304)
    comp=store.document(result["stage_completion"],4194304)
    ret=store.document(result["budget_return"],4194304)
    for name,value in (("StartBinding",start),("StageCompletion",comp),("BudgetReturn",ret)):
        schemas.validate("ci",name,value,store.meter)
    need(start["lease"]==lease_pin and start["authority"]==authority_pin and
         start["authority_subject"]==lease["authority_subject"] and start["census"]==lease["census"] and
         start["scope_digest"]==scope_digest and start["profile"]==profile_pin,"actual pre-run start joins")
    need(start["controller"]==controller and start["campaign_id"]==event.campaign and
         start["observer_source"]==event.source,"original start owner")
    worker=start["worker"]
    need(worker["launch_nonce"]==lease["worker_nonce"] and worker!=controller and
         (worker["boot_id"],worker["pid"],worker["start_monotonic_ns"])!=
         (controller["boot_id"],controller["pid"],controller["start_monotonic_ns"]),"distinct original worker")
    need(all(start[k] is True for k in ("memory_enforced","whole_CPU_enforced","aggregate_storage_enforced")),
         "actual stage and whole envelope enforcement")
    need(clock["origin_monotonic_ns"]<=start["issued_ns"]<=comp["closed_ns"]<=clock["evidence_deadline_ns"],
         "original start-before-close within unchanged cutoff")
    need(comp["lease"]==lease_pin and comp["start_binding"]==result["start_binding"] and
         comp["campaign_id"]==event.campaign and comp["controller"]==controller and
         comp["worker"]==worker and comp["observer_source"]==event.source and
         (comp["operation"],comp["condition"])==(expected_operation,expected_condition),"original completion exact joins")
    need(comp["whole_campaign_still_open"] is True,"worker closure while actual C still alive")
    rows=comp["ordered_job_evidence"]
    need([r["job_id"] for r in rows]==lease["ordered_job_ids"],"all original failed/unattempted slots retained")
    need(ret["lease"]==lease_pin and ret["base_state"]==base_pin and ret["previous_return"]==previous_return and
         ret["stage_completion"]==result["stage_completion"] and ret["campaign_id"]==event.campaign and
         ret["sequence"]==lease["sequence"] and ret["committed_once_by_observer"] is True and
         ret["evidence_capture_reservation"]==lease["terminal_channel_reservation"],"one exact original return")
    need(ret["terminal_state"]==comp["terminal_budget_state"] and ret["terminal_state"] is not None and
         not ret["unknown_dimensions"] and ret["disposition"]!="terminal_unknown","known terminal state without refund")
    terminal=store.document(ret["terminal_state"],4194304)
    schemas.validate("ci","BudgetState",terminal,store.meter)
    extends(base,terminal,generation=base["generation"]+1)
    need(terminal["array_live"]==0,"original owned managed arrays released")
    # Physical observation is separately captured by H, not inferred from stage flags.
    physical=store.document(result["physical_observation"],4194304)
    closed(physical,("schema","observer","worker","controller","start_binding","stage_completion_subject",
                     "run_deadline_ns","evidence_deadline_ns","cpu_ns","memory_peak","storage_bytes",
                     "whole_limits","final_observation_known","controller_alive_at_close"))
    need(physical["schema"]=="four_original_stage_physical_observation_v1" and
         physical["observer"]==event.source and physical["worker"]==worker and physical["controller"]==controller and
         physical["start_binding"]==result["start_binding"] and comp["observed_physical_resources"]==result["physical_observation"],
         "actual host physical record joins")
    need(physical["run_deadline_ns"]==clock["run_deadline_ns"] and
         physical["evidence_deadline_ns"]==clock["evidence_deadline_ns"] and
         physical["controller_alive_at_close"] is True and physical["final_observation_known"] is True,
         "original physical observation and live C known")
    need(physical["whole_limits"]==physical_limits,"limits come from root opportunity, never an observation")
    for key in ("cpu_ns","memory_peak","storage_bytes"):
        integer(physical[key]);need(physical[key]<=physical["whole_limits"][key],"same original physical limit "+key)
    # Binding omits this future completion hash, preventing a physical/completion cycle.
    subject={k:comp[k] for k in ("campaign_id","lease","start_binding","controller","worker","observer_source",
                                "operation","condition","stage_receipt","ordered_job_evidence","terminal_budget_state")}
    need(physical["stage_completion_subject"]==pin(encode(subject)),"acyclic actual completion subject")
    receipt=None
    if comp["stage_receipt"] is not None:
        receipt=store.document(comp["stage_receipt"],4194304)
        need(receipt["job_output_contract"]==output_contract.pin and
             receipt["scope_digest"]==scope_digest and receipt["census"]==lease["census"] and
             receipt["operation"]==expected_operation and receipt["whole_scope_job_count"]==len(census["jobs"]) and
             receipt["selected_stage_job_count"]==len(rows) and
             [r["job_id"] for r in receipt["outcomes"]]==lease["ordered_job_ids"],"original complete stage receipt")
        for row,outcome in zip(rows,receipt["outcomes"]):
            raw=store.read(row["original_outcome"],4194304,metadata=True)
            need(raw==encode(outcome),"same actual original job outcome bytes")
            if row["status"]=="original_process_closed":
                need(outcome["status"]=="process_finished_pending_independent_outer_completion" and
                     row["original_process_record"] is not None and row["candidate_report"] is not None,
                     "original per-job artifacts complete")
                process=store.document(row["original_process_record"],4194304)
                need(process==outcome["original_process"],"actual original PROCESS object matches stage outcome")
    complete=(comp["natural_exit"] is True and type(comp["exit_code"]) is int and comp["exit_code"]==0 and
              all(comp[k] is True for k in ("outer_streams_eof","worker_descendants_empty","worker_group_removed")) and
              comp["timed_out"] is False and comp["original_failure"] is None and comp["cleanup_errors"]==[] and
              receipt is not None and all(r["status"]=="original_process_closed" for r in rows))
    for key in ("original_outer_stdout","original_outer_stderr"):
        if comp[key] is not None:store.read(comp[key],4194304)
        else:complete=False
    need(ret["disposition"]==("eligible_exact_successor" if complete else "failure_only"),
         "success cannot hide failed jobs or original outer failure")
    audit={"schema":"critical_init_full_stage_admission_v3","lease":lease_pin,
           "completion":result["stage_completion"],"return":result["budget_return"],
           "host_channel_raw":event.raw_pin,"eligible":complete,"physical_observation":result["physical_observation"],
           "original_receipt":comp["stage_receipt"],"job_output_contract":output_contract.pin,"bridge_costs":store.meter.record()}
    return StageAdmission(_ADMITTED,lease=lease,start=start,completion=comp,budget_return=ret,
                          terminal=terminal,return_pin=result["budget_return"],completion_pin=result["stage_completion"],
                          lease_pin=lease_pin,audit=audit,job_evidence={r["job_id"]:r for r in rows},
                          output_contract=output_contract,validation_meter=bridge_meter)

def project_job(admission,job_id,condition):
    need(type(admission) is StageAdmission and admission.eligible,"complete eligible original stage")
    need(admission.lease["operation"]=="candidate" and admission.lease["condition"]==condition,
         "same original candidate arm")
    row=admission.job_evidence[job_id]
    need(row["status"]=="original_process_closed","actual original job succeeded")
    return {"schema":"critical_init_stage_bound_job_outer_v3","campaign_id":admission.lease["campaign_id"],
            "lease":admission.lease_pin,"stage_completion":admission.completion_pin,"budget_return":admission.return_pin,
            "job_id":job_id,"condition":condition,"stage_worker":admission.start["worker"],
            "controller":admission.start["controller"],"original_process_record":row["original_process_record"],
            "candidate_report":row["candidate_report"],"independent_outer_natural_exit_zero":True}

def collect_outer(admission,closure,*,job_id,condition,process_pin,candidate_pin):
    expected=project_job(admission,job_id,condition)
    need(closure==expected and closure["original_process_record"]==process_pin and
         closure["candidate_report"]==candidate_pin,"exact per-job closure before original child admission")
    return {k:closure[k] for k in ("independent_outer_natural_exit_zero","original_process_record","candidate_report")}
