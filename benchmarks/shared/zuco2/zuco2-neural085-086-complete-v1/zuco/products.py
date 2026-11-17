"""Captured ordinary output bytes, not participant self-attested completion."""
from pathlib import Path
from .io import *
from .contracts import prediction

def success(receipt,engineering=False):
    need(receipt["failure"]is None and receipt["original_observed_exit"]==0 and receipt["original_final_wait"]==0 and not receipt["forced_cleanup"] and receipt["streams_complete"] and receipt["stdin_delivery_complete"] and not receipt["capture_failures"],"original_process_failure")
    need(engineering or (receipt["engineering_only"]is False and receipt["cleanup"]["all_descendants_dead"] and receipt["cleanup"]["mounts_removed"]),"unqualified_process_containment")
def capture(job,receipt,destination,ledger,engineering=False):
    success(receipt,engineering);guard=lambda:ledger.guard(closing=True);guard();source=Path(job["directory"])/"output";rows=verify_inventory(source,receipt["outputs"],job["limits"]["files"],job["limits"]["output_bytes"],guard);guard();exists=Path(destination).exists();guard();need(not exists,"fresh_capture")
    ledger.reserve_bytes(sum(x["bytes"] for x in rows),"stable captured output copies")
    for d in rows:
        guard();src=below(source,d["path"],guard);dst=below(destination,d["path"],guard)
        body=read(src,job["limits"]["output_bytes"],d,guard)
        write(dst,body,ledger,guard=guard,pre_reserved=True)
    guard();need(verify_inventory(destination,rows,job["limits"]["files"],job["limits"]["output_bytes"],guard)==rows,"capture_identity");guard()
    return {"root":str(Path(destination).absolute()),"files":rows,"source_receipt_sha256":digest(receipt),"source_job_id":job["id"],"identity":job["identity"],"sha256":digest(rows)}
def result(product,cap,guard=lambda:None):
    d=next((x for x in product["files"] if x["path"]=="result.json"),None);need(d is not None,"result_missing");return decode(read(below(product["root"],d["path"]),cap,d,guard))
def state(product,cap,guard=lambda:None):
    obj=result(product,cap,guard);exact(obj,["status","state_files","analysis_trace"]);need(obj["status"]=="fit_complete" and type(obj["state_files"])is list and obj["state_files"],"fit_state")
    files={x["path"]:x for x in product["files"]};declared=obj["state_files"]+obj["analysis_trace"]
    need(len({x["path"] for x in declared})==len(declared) and {x["path"] for x in declared}|{"result.json"}==set(files),"complete_fit_inventory")
    for d in declared:descriptor(d);need(d==files[d["path"]],"fit_declared_identity")
    return {**product,"state_sha256":digest({"files":product["files"],"job":product["source_job_id"],"receipt":product["source_receipt_sha256"]})}
def probabilities(product,request,cap,guard=lambda:None):
    obj=result(product,cap,guard);values=prediction(obj,request["identity"],request["query_ids"],request["state_sha256"]);files={x["path"]:x for x in product["files"]};trace=obj["analysis_trace"]
    need({x["path"] for x in trace}|{"result.json"}==set(files) and len({x["path"] for x in trace})==len(trace),"complete_infer_inventory")
    for d in trace:descriptor(d);need(d==files[d["path"]],"analysis_trace_pin")
    return values
