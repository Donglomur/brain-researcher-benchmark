"""Trusted actor-boundary composition; real providers and their host authority stay unavailable."""
import time
import resource
from copy import deepcopy
from .contracts import need, pin, canonical, CONDITIONS, STATUS
from .campaign import calibration

def build_actor_panel(sessions, builders, project_case, physical_views, ledger,*,records=None):
    """Call each selected training boundary on its own session/condition only.

    A boundary is explicitly inert in this source-control phase. This API does not
    authenticate an untrusted provider or execute submitted source as a sandbox.
    """
    expected={(a,c) for a in ("F","I") for c in CONDITIONS}
    need(type(builders) is dict and set(builders)==expected,"all eight actor boundaries")
    for (arm,condition),b in builders.items():
        need(type(b) is dict and set(b)=={"source_body","build","profile"}, "actor boundary schema")
        need(type(b["source_body"]) is bytes and b["source_body"] and callable(b["build"]),
             "captured source plus fixed boundary")
        need(b["profile"]=={"kind":"explicit_inert_source_control","qualified":False},
             "no actual provider profile selected")
        if arm=="F":
            need(pin(b["source_body"])==physical_views.source_pins[condition],
                 "F source fixed before every calibration")
    handles={};records=[] if records is None else records
    need(type(records) is list and not records,"fresh retained actor records")
    method_rows={"F":[],"I":[]};sources={"F":[],"I":[]}
    for s in sessions:
        sid=s["session_id"]
        for condition in CONDITIONS:
            train,val=calibration(s,condition,project_case)
            for arm in ("F","I"):
                b=builders[(arm,condition)]
                local=physical_views.children[(sid,arm,condition)]
                inp={"session_id":sid,"condition":condition,"train":train,"val":val,
                     "view_root":local["path"],"source_identity":pin(b["source_body"])}
                start=time.monotonic();cpu=resource.getrusage(resource.RUSAGE_SELF)
                try:
                    out=b["build"](deepcopy(inp))
                    need(type(out) is dict and set(out)=={"source_body","config_body","state_body",
                         "predict","complete","fit_calls","tool_calls"},"complete actor result")
                    need(all(type(out[k]) is bytes and out[k] for k in
                             ("source_body","config_body","state_body")),"actual source/config/state bodies")
                    need(callable(out["predict"]) and callable(out["complete"]),"fixed held/close boundaries")
                    need(all(type(out[k]) is int and out[k]>=0 for k in ("fit_calls","tool_calls")),
                         "explicit inert-boundary work counters")
                    if arm=="F":
                        need(out["source_body"]==b["source_body"],"F procedure cannot change after values")
                    captured=physical_views.commit_actor(sid,arm,condition,out["source_body"],
                                                         out["config_body"],out["state_body"])
                    need(captured=={"source":pin(out["source_body"]),"configuration":pin(out["config_body"]),
                                    "state":pin(out["state_body"])},"durable captured actor bodies")
                    end=resource.getrusage(resource.RUSAGE_SELF)
                    work={"wall_seconds":time.monotonic()-start,
                        "cpu_seconds":end.ru_utime+end.ru_stime-cpu.ru_utime-cpu.ru_stime,
                        "read_bytes":len(canonical(inp)),
                        "write_bytes":sum(len(out[k]) for k in ("source_body","config_body","state_body")),
                        "tool_calls":out["tool_calls"],"fit_calls":out["fit_calls"],"provider_tokens":0}
                    ledger.charge(sid,condition,arm,"fit" if arm=="F" else "investigation",work,
                        evidence={"profile":b["profile"],"source":pin(out["source_body"]),
                                  "external_costs":"no external provider selected"})
                    handles[(sid,condition,arm)]=out
                    method_rows[arm].append({"session_id":sid,"condition":condition,
                        "config_identity":pin(out["config_body"]),"parameter_identity":pin(out["state_body"])})
                    sources[arm].append({"session_id":sid,"condition":condition,"source":pin(out["source_body"])})
                    records.append({"session_id":sid,"condition":condition,"arm":arm,"cost":work,
                                    "source":pin(out["source_body"]),"captured_bodies":captured,"status":STATUS})
                except BaseException as error:
                    end=resource.getrusage(resource.RUSAGE_SELF)
                    failed={"wall_seconds":time.monotonic()-start,
                        "cpu_seconds":end.ru_utime+end.ru_stime-cpu.ru_utime-cpu.ru_stime,
                        "read_bytes":len(canonical(inp)),"write_bytes":0,
                        "tool_calls":0,"fit_calls":0,"provider_tokens":0}
                    try:
                        ledger.charge(sid,condition,arm,"failed_work",failed,
                            evidence={"profile":b["profile"],"output_and_internal_counts_unknown":True},failed=True)
                    except BaseException as accounting_error:
                        error.add_note("Failure accounting also refused: "+repr(accounting_error))
                    raise
    methods=[{"method_id":"actor","kind":"actor","arm":a,
              "method_source_identity":{"source_table":pin(sources[a]),"status":STATUS},
              "commitments":method_rows[a]} for a in ("F","I")]
    return handles,methods,records

def actor_predictor(handles):
    def respond(method_id,arm,session_id,condition,view):
        need(method_id=="actor" and (session_id,condition,arm) in handles,"fixed actor route")
        need("y" not in view,"held target absent")
        return handles[(session_id,condition,arm)]["predict"](deepcopy(view))
    return respond

def close_actor_panel(handles):
    evidence=[]
    for key,handle in handles.items():
        record=handle["complete"]()
        need(type(record) is dict and record.get("status")==STATUS
             and record.get("closed") is True,"inert external boundary completion")
        evidence.append({"cell":list(key),"result":record})
    return {"capture_identity":pin(evidence),"all_selected_processes_exited":True,
            "status":STATUS}
