"""Fixed N098 projections and source-owned structural checks; never authority."""
from .common import need,closed,integer,descriptor,encode,parse,pin,bounded_size
from .schema import check
from .n098_tables import RECORD_DEFINITIONS

def validate(name,value,meter):
    need(name in RECORD_DEFINITIONS,"fixed adopted N098 record")
    meter.charge("work_units",bounded_size(value))
    check(value,RECORD_DEFINITIONS[name],root={"$defs":RECORD_DEFINITIONS})
    return value

def capture(store,expected,name,cap):
    descriptor(expected)
    raw=store.read(expected,cap,metadata=True)
    value=parse(raw,cap);need(raw==encode(value),"exact original canonical N098 bytes")
    validate(name,value,store.meter)
    return raw,value

def resource_projection(final_plan):
    # Exactly the two adopted projections. No other late field is erased.
    need(type(final_plan) is dict and "programme_budget" in final_plan,"full final resource plan")
    out={k:v for k,v in final_plan.items() if k!="programme_budget"}
    budget=final_plan["programme_budget"];need("legacy_selection" in budget,"original final legacy pin")
    out["programme_budget_except_legacy_selection"]={k:v for k,v in budget.items() if k!="legacy_selection"}
    return out

def selection_projection(final_selection):
    need(type(final_selection) is dict and "qualifications" in final_selection,"whole final original selection")
    qualifications=final_selection["qualifications"]
    need(type(qualifications) is dict and "controller-envelope" in qualifications,"actual later controller envelope")
    out={k:v for k,v in final_selection.items() if k!="qualifications"}
    out["qualifications_except_controller_envelope"]={k:v for k,v in qualifications.items() if k!="controller-envelope"}
    return out

def validate_selection_projection(value,source_sha,resource,meter):
    # Exact original selection fields; only envelope qualification is absent.
    fields=("schema","enabled","task_id","operation","whole_source_sha256","execution_authority", "budget",
            "output_parent","output_name","operands","qualifications_except_controller_envelope","exposure","conditions")
    closed(value,fields);meter.charge("work_units",bounded_size(value))
    need(value["schema"]=="neural098-complete-programme-selection-v1" and value["enabled"] is True and
         value["task_id"]=="NEURAL-098" and value["operation"]=="campaign" and value["whole_source_sha256"]==source_sha,
         "exact original complete future campaign projection")
    need(value["conditions"]==["A_F","A_I","B_F","B_I"],"all four original conditions")
    authority=value["execution_authority"]
    closed(authority,("root_selected","scientific_execution_selected","operation","whole_source_sha256","selection_id","expires_utc"))
    need(authority["root_selected"] is True and authority["scientific_execution_selected"] is True and
         authority["operation"]=="campaign" and authority["whole_source_sha256"]==source_sha,
         "original later root operation selection; projection does not grant it")
    need(type(authority["selection_id"]) is str and len(authority["selection_id"])==32 and
         all(c in "0123456789abcdef" for c in authority["selection_id"]),"original selection identity")
    need(type(authority["expires_utc"]) is str,"original explicit expiry")
    # The independently qualified original selection source checks current UTC
    # and every original qualification before final binding and again after exec.
    need(type(value["operands"]) is dict and type(value["qualifications_except_controller_envelope"]) is dict and
         "controller-envelope" not in value["qualifications_except_controller_envelope"],"no hidden future envelope")
    budget=resource["programme_budget_except_legacy_selection"]
    need(value["budget"]==budget["whole"] and value["operands"].get("condition_limits")==budget["condition"],
         "complete preselected original whole and condition budgets")
    for b in (value["budget"],value["operands"]["condition_limits"]):
        for v in b.values():integer(v,1);need(v<=2**50,"original selected resource maximum")
    exposure=value["exposure"]
    need(type(exposure) is dict and exposure.get("family")=="cogitate-family" and
         exposure.get("no_prior_related_hidden_label_claim") is True and exposure.get("fresh_independent_sessions") is True,
         "original full exposure restrictions")
    return value

def original_interval(resource,subject):
    hard=resource["hard_envelope"];clock=subject["original_clock"];window=subject["startup_window"]
    need(clock=={k:hard[k] for k in ("origin_monotonic_ns","run_deadline_ns","evidence_deadline_ns")},
         "same original hard clock")
    need(clock["origin_monotonic_ns"]<=window["start_ns"]<window["stop_ns"]<=clock["run_deadline_ns"]<=
         clock["evidence_deadline_ns"],"one original encompassing interval")
    need(clock["origin_monotonic_ns"]<clock["run_deadline_ns"],"nonempty original run opportunity")

def rows_valid(resource):
    rows=resource["adapter_reservations"];hard=resource["hard_envelope"]
    need(len({r["reservation_id"] for r in rows})==len(rows) and
         len({(r["owner_role"],r["stage"]) for r in rows})==len(rows),"exact unique original shares")
    need(sum(r["cpu_ns"] for r in rows)<=hard["cpu_ns"] and
         sum(r["retained_bytes"] for r in rows)<=hard["retained_storage_bytes"],"all adapter rows inside original opportunity")
    b=resource["programme_budget_except_legacy_selection"]
    need(4*b["condition"]["agent_tokens"]<=b["whole"]["agent_tokens"] and
         4*b["condition"]["agent_invocations"]<=b["whole"]["agent_invocations"],"all four original candidate opportunities")
    return {(r["owner_role"],r["stage"]):r for r in rows}
