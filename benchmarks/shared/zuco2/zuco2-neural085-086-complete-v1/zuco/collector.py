"""Global coordinate and source/custody admission before query-target access."""
from pathlib import Path
from .io import *
from .products import success,probabilities

def admit(plan,records,program,ledger,reference_plan,reference_records,outer_receipt,engineering=False):
    ledger.final();need(plan.get("query_census_frozen_before_first_exposure")is True,"complete_pre_exposure_query_census");need(outer_receipt["original_final_wait"]==0 and outer_receipt["failure"]is None and outer_receipt["streams_complete"],"outer_driver_not_complete")
    need(outer_receipt["source_pin"]["sha256"]==plan["runtime_source_sha256"] and outer_receipt["request_pin"]["sha256"]==plan["driver_request_sha256"],"actual_outer_source_request")
    expected={j["id"]:j for j in plan["jobs"] if j.get("source_disposition")!="required_unscorable_secondary_context"};need(len({j["id"] for j in plan["jobs"]})==len(plan["jobs"]) and len(records)==len(expected),"complete_candidate_records")
    def bank(expected,actual,role):
        seen=set();admitted={}
        for r in actual:
            exact(r,["job_id","identity","fit","fit_request","state","infer","product","request","support_dispositions_sha256","support_dispositions","control_observations"]);key=r["job_id"];need(key in expected and key not in seen,"unknown_duplicate_job");seen.add(key);need(r["support_dispositions_sha256"]==digest(r["support_dispositions"]),"support_disposition_identity");j=expected[key];need(r["identity"]==j["identity"],"coordinate_mismatch")
            for receipt in (r["fit"],r["infer"]):
                success(receipt,engineering);need(receipt["identity"]==r["identity"] and receipt["source_pin"]["sha256"]==j["source_sha256"],"receipt_source_coordinates")
                need(receipt["resources"]["cpu_seconds"]<=j["limits"]["cpu_seconds"] and receipt["resources"]["wall_seconds"]<=j["limits"]["wall_seconds"],"final_per_job_resource")
                need(receipt["ended_after_collection"]<ledger.spec["deadline_monotonic"],"late_receipt")
            need(r["state"]["source_receipt_sha256"]==digest(r["fit"]) and r["product"]["source_receipt_sha256"]==digest(r["infer"]),"actual_producer_custody")
            need(r["fit"]["request_pin"]["sha256"]==digest(r["fit_request"]) and r["request"]["query_ids"]==j["query_ids"],"frozen_issuer_request_census");need(r["request"]["state_sha256"]==r["state"]["state_sha256"] and r["infer"]["request_pin"]["sha256"]==digest(r["request"]),"current_state_request")
            for prod in (r["state"],r["product"]):verify_inventory(prod["root"],prod["files"],j["limits"]["files"],j["limits"]["output_bytes"],lambda:ledger.guard(closing=True))
            values=probabilities(r["product"],r["request"],j["limits"]["output_bytes"],lambda:ledger.guard(closing=True));admitted[key]={"identity":r["identity"],"probabilities":values,"receipt_sha256":digest(r)}
        need(seen==set(expected),"missing_jobs",role);return admitted
    candidates=bank(expected,records,"participant");refs=bank({j["id"]:j for j in reference_plan},reference_records,"reference")
    ledger.final();return {"schema":"zuco2-admitted-campaign-v1","plan_sha256":digest(plan),"programme_sha256":program["manifest_pin"]["sha256"],"candidate":candidates,"reference":refs,"original_outer_receipt_sha256":digest(outer_receipt),"ledger":ledger.snapshot(),"protected_query_targets_opened":False}

def target_last(admitted,target_pin,plan,ledger):
    need(admitted["protected_query_targets_opened"]is False and admitted["plan_sha256"]==digest(plan),"target_read_barrier")
    # Mark the attempted access before opening; an exception is not silently retried.
    admitted["protected_query_targets_opened"]=True;admitted["target_attempt"]={"pin":dict(target_pin),"outcome":"attempted"}
    try:
        body=decode(read(target_pin["path"],target_pin["bytes"],target_pin,lambda:ledger.guard(closing=True)));need(body["split_sha256"]==plan["split_sha256"] and body["source_sha256"]==plan["source_sha256"],"target_source_split");admitted["target_attempt"]["outcome"]="read_and_bound";return body
    except BaseException as e:admitted["target_attempt"].update(outcome="failed",failure=failure(e));raise
