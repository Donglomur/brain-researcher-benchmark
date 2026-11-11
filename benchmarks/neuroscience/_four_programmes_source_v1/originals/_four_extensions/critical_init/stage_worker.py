"""One actual enclosing W stage, distinct from original numerical children.

The qualified root launches this fixed function inside the captured original
package. Source/clock/environment admission occurs before entry. This module
does not manufacture independent completion: H must observe this process exit.
"""
from pathlib import Path
from .stage_budget import ExclusiveBudget,validate_state
from .workflow_v4 import execute_selected
from .authorization_v4 import Selection
from .custody import read_pin,encode as original_encode,pin as original_pin
from four_programmes.common import need,closed,pin,encode,failure,bounded_size
from four_programmes.source_session import SourceSession

STAGES=(("prepare",None),("independent_reference",None),("native_reference",None),
        ("candidate","paper_data"),("candidate","paper_data_author_code"))

def run(*,session,root,request,bootstrap_store,terminal_store,schemas,bridge_meter,mapping):
    """Source-owned producer; scientific leaves are the whole original stage.

    All bootstrap and terminal transport uses already selected H shares. The
    exact cumulative programme budget has one writer and is never reset.
    An exception remains the original exception after bounded failure capture.
    """
    need(type(session) is SourceSession and session.programme=="PAPER-FIND-050",
         "actual admitted original CI source session")
    closed(request,("schema","lease","authority","start_binding","profile","clock",
                    "output_parent","terminal_name"))
    need(request["schema"]=="critical_init_original_worker_request_v3","fixed worker request")
    meter=bootstrap_store.meter
    need(terminal_store.meter is bridge_meter,"earlier H terminal store share")
    lease=bootstrap_store.document(request["lease"],4194304)
    profile=bootstrap_store.document(request["profile"],4194304)
    clock=bootstrap_store.document(request["clock"],4194304)
    base=bootstrap_store.document(lease["base_state"],4194304)
    for name,value in (("Lease",lease),("Profile",profile),("ClockBinding",clock),("BudgetState",base)):
        schemas.validate("ci",name,value,meter)
    need(1<=lease["sequence"]<=len(STAGES) and
         (lease["operation"],lease["condition"])==STAGES[lease["sequence"]-1],"entire fixed stage order")
    need(lease["profile"]==request["profile"] and lease["census"]==profile["full_census"] and
         base["clock_binding"]==request["clock"]==profile["clock_binding"] and
         base["campaign_id"]==lease["campaign_id"]==clock["campaign_id"]==profile["campaign_id"],
         "original source/profile/clock campaign")
    need(base["generation"]==lease["base_generation"] and
         base["origin_seconds"]==clock["origin_seconds"] and
         base["deadline_seconds"]==clock["run_deadline_seconds"] and
         lease["original_run_deadline_ns"]==clock["run_deadline_ns"] and
         lease["original_evidence_deadline_ns"]==clock["evidence_deadline_ns"],"no changed stage interval")
    need(pin(encode(base))=={k:lease["base_state"][k] for k in ("bytes","sha256")},"exact original frozen base bytes")
    context={"lease":lease,"lease_pin":request["lease"],"profile_pin":request["profile"],
             "clock":clock,"mapping":mapping,"meter":meter,"schemas":schemas}
    budget=None;primary=None;cleanup=[];result=None;receipt=None;state=None;terminal_pin=None;output_contract_pin=None
    try:
        budget=ExclusiveBudget(base,owner="W",lease_pin=request["lease"],previous_return=lease["previous_return"])
        # Selection's actual PID/start/boot check is before the original stage
        # loop and all gate/method dispatch. No injected execute callback.
        selected=Selection(root,request["authority"],budget)
        output_contract_pin=selected.body["job_output_contract"]
        need(selected.body["condition"]==lease["condition"] and
             selected.body["pre_run_subject"]==lease["authority_subject"],"exact worker arm and authority subject")
        result=execute_selected(root,request["authority"],request["output_parent"],budget,
                                operation=lease["operation"],start_binding_pin=request["start_binding"],
                                start_context=context)
        raw=original_encode(result)
        receipt={"path":str(Path(request["output_parent"])/selected.body["run_nonce"]/"STAGE_RECEIPT.json"),
                 **original_pin(raw)}
        # Actual managed recapture is before terminal state. The receipt's own
        # embedded snapshot is deliberately preserved as an earlier prefix.
        need(read_pin(root,receipt,33554432,budget)==raw,"actual original full stage receipt")
    except BaseException as error:
        primary=error
        bridge_meter.own_error(error,"original_stage_api")
    try:
        session.close()
    except BaseException as error:
        cleanup.append(failure(error));bridge_meter.cleanup_errors.append(failure(error))
        if primary is None:primary=error;bridge_meter.own_error(error,"original_source_session_close")
    if budget is not None:
        try:
            state=budget.export_terminal(failure_only=primary is not None)
            validate_state(state)
        except BaseException as error:
            if primary is None:primary=error;bridge_meter.own_error(error,"original_terminal_state")
            else:cleanup.append(failure(error));bridge_meter.cleanup_errors.append(failure(error))
            state=None
    body={"schema":"critical_init_worker_terminal_handoff_v4","campaign_id":lease["campaign_id"],
          "lease":request["lease"],"start_binding":request["start_binding"],"authority":request["authority"],
          "operation":lease["operation"],"condition":lease["condition"],"stage_receipt":receipt,
          "job_output_contract":output_contract_pin,
          "terminal_budget_state":state,"original_failure":None if primary is None else failure(primary),
          "cleanup_errors":cleanup,"complete_original_attempt_prefix":None,
          "worker_natural_exit_observed":False,"outer_H_observation_still_required":True}
    # Only the fixed actual API attaches this prefix. No arbitrary exception
    # property/str/repr callback is used. Managed output identity stays original.
    if primary is not None:
        try:
            attrs=BaseException.__getattribute__(primary,"__dict__")
            if type(attrs) is dict and "complete_attempt_prefix" in attrs:
                prefix=attrs["complete_attempt_prefix"]
                bridge_meter.charge("work_units",bounded_size(prefix))
                body["complete_original_attempt_prefix"]=prefix
        except BaseException as error:
            cleanup.append(failure(error));bridge_meter.cleanup_errors.append(failure(error))
    try:
        bridge_meter.check()
        terminal_pin=terminal_store.publish(request["terminal_name"],body)
    except BaseException as error:
        if primary is None:primary=error;bridge_meter.own_error(error,"worker_terminal_handoff")
        else:bridge_meter.cleanup_errors.append(failure(error))
    if primary is not None:
        # The actual W exits nonzero. H keeps the exact raw terminal artifact if
        # present and observes full process closure; no self-success marker.
        try:BaseException.__setattr__(primary,"four_stage_terminal",terminal_pin)
        except BaseException as error:bridge_meter.cleanup_errors.append(failure(error))
        raise primary
    need(terminal_pin is not None,"actual terminal publication")
    return terminal_pin
